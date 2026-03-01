#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"

#include <fstream>
#include <unordered_set>
#include <deque>
#include <vector>
#include <cstring>
#include <memory>
#include <algorithm>
#include <numeric>

using namespace ns3;

/* ===================== Replay Cache ===================== */
class ReplayCache
{
public:
  explicit ReplayCache(size_t maxSize) : m_maxSize(maxSize) {}
  bool Seen(uint64_t nonce) const { return m_set.find(nonce) != m_set.end(); }
  void Add(uint64_t nonce)
  {
    if (m_set.count(nonce)) return;
    m_q.push_back(nonce);
    m_set.insert(nonce);
    while (m_q.size() > m_maxSize)
    {
      uint64_t old = m_q.front();
      m_q.pop_front();
      m_set.erase(old);
    }
  }

private:
  size_t m_maxSize;
  std::unordered_set<uint64_t> m_set;
  std::deque<uint64_t> m_q;
};

/* ===================== Packed Headers ===================== */
#pragma pack(push, 1)
struct DataHdr
{
  uint64_t nonce;
  double   txTime;
  uint32_t senderId;
  uint32_t sig;
  uint8_t  isReplay;
};
#pragma pack(pop)

#pragma pack(push, 1)
struct ReportHdr
{
  double   t;
  uint32_t reporterId;
  uint32_t accusedId;
  float    delta;
};
#pragma pack(pop)

/* ===================== Globals / Params ===================== */
static uint64_t g_txData = 0;
static uint64_t g_rxData = 0;
static uint64_t g_replayDrops = 0;
static uint64_t g_sigDrops = 0;
static double   g_delaySum = 0.0;
static uint64_t g_rxBytes = 0;

static uint64_t g_reportsSent = 0;
static uint64_t g_reportsRxAtRsu = 0;

static uint64_t g_blocks = 0;
static uint64_t g_reportsCommitted = 0;
static double   g_blockLatencySum = 0.0;

static uint64_t g_handoverCount = 0;
static uint64_t g_fastAuthCount = 0;
static uint64_t g_fullAuthCount = 0;
static uint64_t g_rejectCount = 0;
static double   g_handoverDelaySum = 0.0;

static double   g_simTime = 20.0;
static uint32_t g_nVehicles = 10;
static uint32_t g_nRsu = 2;

static uint32_t g_payloadSize = 64;
static uint32_t g_intervalMs = 100;

static uint32_t g_cryptoDelayUsTx = 200;
static uint32_t g_cryptoDelayUsRx = 200;

static bool     g_enableReplayAttack = true;
static uint32_t g_replayEveryMs = 300;

static double   g_maliciousRate = 0.2;

static uint32_t g_blockIntervalMs = 1000;
static uint32_t g_mineDelayMs = 50;

static double   g_trustFastThresh = 0.7;
static double   g_trustMinThresh = 0.3;
static uint32_t g_fastAuthDelayMs = 20;
static uint32_t g_fullAuthDelayMs = 120;
static uint32_t g_handoverCheckMs = 200;

static std::string g_csvOut = "bc_ho_metrics.csv";
static std::string g_eventsOut = "bc_ho_events.csv";

static const uint16_t g_dataPort = 9000;
static const uint16_t g_reportPort = 9100;

/* ===================== State ===================== */
static std::vector<std::unique_ptr<ReplayCache>> g_caches;
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

static std::vector<double> g_ledgerTrust;

struct ReportItem
{
  double t;
  uint32_t reporter;
  uint32_t accused;
  double delta;
};
static std::deque<ReportItem> g_mempool;

struct VehicleState
{
  uint32_t currentRsu = 0;
  bool authed = true;
  bool authInProgress = false;
  double handoverStart = 0.0;
};
static std::vector<VehicleState> g_vs;

static std::ofstream g_evt;

static NodeContainer g_vehicles;
static NodeContainer g_rsus;

static std::vector<Ptr<Socket>> g_dataRecvSock;
static Ptr<Socket> g_sendSock;
static Ptr<Socket> g_rsuReportRecvSock;
static std::vector<Ptr<Socket>> g_vehicleReportSock;

static std::vector<Vector> g_rsuPos;
static Ipv4Address g_rsu0Addr;

static double g_blockStart = 0.0;

static Ptr<UniformRandomVariable> g_uv = CreateObject<UniformRandomVariable>();

/* ===================== Helpers ===================== */
static double Clamp01(double x)
{
  if (x < 0.0) return 0.0;
  if (x > 1.0) return 1.0;
  return x;
}

/* ===== CSV-safe event logger (IMPORTANT for pandas) ===== */
static std::string CSVEscape(const std::string &s)
{
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s)
  {
    if (c == '"') out += "\"\"";
    else out += c;
  }
  return out;
}

static void LogEvent(const std::string& ev, const std::string& details)
{
  if (!g_evt.is_open()) return;
  g_evt << Simulator::Now().GetSeconds()
        << "," << ev
        << ",\"" << CSVEscape(details) << "\"\n";
}

/* ===================== Signature ===================== */
static uint32_t SimpleSig(uint32_t senderId, uint64_t nonce)
{
  uint64_t x = nonce ^ (uint64_t(senderId) * 0x9e3779b97f4a7c15ULL);
  x ^= (x >> 33);
  x *= 0xff51afd7ed558ccdULL;
  x ^= (x >> 33);
  return uint32_t(x & 0xffffffffULL);
}

/* ===================== RSU selection ===================== */
static uint32_t GetNearestRsu(const Vector& p)
{
  uint32_t best = 0;
  double bestD = 1e18;
  for (uint32_t r = 0; r < g_rsuPos.size(); r++)
  {
    double dx = p.x - g_rsuPos[r].x;
    double dy = p.y - g_rsuPos[r].y;
    double d2 = dx*dx + dy*dy;
    if (d2 < bestD) { bestD = d2; best = r; }
  }
  return best;
}

/* ===================== DATA RX processing ===================== */
static void ProcessData(uint32_t receiverId, DataHdr hdr, uint32_t pktSize)
{
  ReplayCache* cache = g_caches.at(receiverId).get();

  if (cache->Seen(hdr.nonce))
  {
    g_replayDrops++;
    LogEvent("DATA_DROP_REPLAY",
             "rx=" + std::to_string(receiverId) +
             ",sender=" + std::to_string(hdr.senderId) +
             ",nonce=" + std::to_string(hdr.nonce));
    return;
  }
  cache->Add(hdr.nonce);

  uint32_t expect = SimpleSig(hdr.senderId, hdr.nonce);
  if (expect != hdr.sig)
  {
    g_sigDrops++;
    LogEvent("DATA_DROP_SIG",
             "rx=" + std::to_string(receiverId) +
             ",sender=" + std::to_string(hdr.senderId) +
             ",nonce=" + std::to_string(hdr.nonce));
    return;
  }

  double now = Simulator::Now().GetSeconds();
  double delay = now - hdr.txTime;
  if (delay < 0) delay = 0;

  g_rxData++;
  g_delaySum += delay;
  g_rxBytes += pktSize;
}

/* ===================== DATA RX callback ===================== */
static void RxDataReady(Ptr<Socket> socket)
{
  uint32_t rid = socket->GetNode()->GetId();

  while (true)
  {
    Address from;
    Ptr<Packet> pkt = socket->RecvFrom(from);
    if (!pkt || pkt->GetSize() == 0) break;
    if (pkt->GetSize() < sizeof(DataHdr)) continue;

    std::vector<uint8_t> buf(pkt->GetSize());
    pkt->CopyData(buf.data(), buf.size());

    DataHdr hdr{};
    std::memcpy(&hdr, buf.data(), sizeof(DataHdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsRx),
                        &ProcessData, rid, hdr, pkt->GetSize());
  }
}

/* ===================== REPORT RX at RSU0 ===================== */
static void RxReportAtRsu(Ptr<Socket> sock)
{
  while (true)
  {
    Address from;
    Ptr<Packet> pkt = sock->RecvFrom(from);
    if (!pkt || pkt->GetSize() == 0) break;
    if (pkt->GetSize() < sizeof(ReportHdr)) continue;

    ReportHdr rh{};
    pkt->CopyData((uint8_t*)&rh, sizeof(rh));

    g_reportsRxAtRsu++;
    g_mempool.push_back({rh.t, rh.reporterId, rh.accusedId, rh.delta});

    LogEvent("REPORT_RX_RSU",
             "rsu=0,by=" + std::to_string(rh.reporterId) +
             ",about=" + std::to_string(rh.accusedId) +
             ",delta=" + std::to_string(rh.delta));
  }
}

/* ===================== SEND DATA ===================== */
static void SendNewPacket(Ptr<Socket> sock, uint32_t senderId)
{
  DataHdr hdr{};
  hdr.nonce = Simulator::Now().GetNanoSeconds();
  hdr.txTime = Simulator::Now().GetSeconds();
  hdr.senderId = senderId;
  hdr.isReplay = 0;

  hdr.sig = SimpleSig(senderId, hdr.nonce);

  // malicious corruption
  if (g_uv->GetValue(0.0, 1.0) < g_maliciousRate)
    hdr.sig ^= 0x12345678;

  std::vector<uint8_t> wire(sizeof(DataHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(DataHdr));

  Ptr<Packet> p = Create<Packet>(wire.data(), wire.size());

  // store for replay attack
  g_lastWire = wire;
  g_hasLast = true;

  g_txData++;

  // simulate TX crypto delay by scheduling actual send
  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), [sock, p]() {
    sock->Send(p);
  });

  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendNewPacket, sock, senderId);
}

/* ===================== REPLAY ATTACK ===================== */
static void ReplayAttackTick(Ptr<Socket> sock)
{
  if (g_hasLast && !g_lastWire.empty())
  {
    // resend EXACT previous packet -> nonce repeats -> replay drops
    Ptr<Packet> p = Create<Packet>(g_lastWire.data(), g_lastWire.size());
    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), [sock, p]() {
      sock->Send(p);
    });
  }
  Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick, sock);
}

/* ===================== MISBEHAVIOR REPORT SENDER ===================== */
static void MaybeMisbehaviorReportTick()
{
  // Pick random reporter & accused
  uint32_t reporter = (uint32_t)g_uv->GetInteger(0, (int64_t)g_nVehicles - 1);
  uint32_t accused  = (uint32_t)g_uv->GetInteger(0, (int64_t)g_nVehicles - 1);
  if (accused == reporter) accused = (accused + 1) % g_nVehicles;

  // delta: mostly + for honest, sometimes - for malicious
  double delta = (g_uv->GetValue(0.0, 1.0) < g_maliciousRate) ? -0.05 : 0.01;

  ReportHdr rh{};
  rh.t = Simulator::Now().GetSeconds();
  rh.reporterId = reporter;
  rh.accusedId = accused;
  rh.delta = (float)delta;

  Ptr<Packet> pkt = Create<Packet>((uint8_t*)&rh, sizeof(rh));
  g_vehicleReportSock[reporter]->Send(pkt);
  g_reportsSent++;

  LogEvent("REPORT_SENT",
           "by=" + std::to_string(reporter) +
           ",about=" + std::to_string(accused) +
           ",delta=" + std::to_string(delta));

  Simulator::Schedule(Seconds(1.0), &MaybeMisbehaviorReportTick);
}

/* ===================== BLOCKCHAIN COMMIT ===================== */
static void CommitBlockDone()
{
  // Apply mempool to trust ledger
  uint32_t items = (uint32_t)g_mempool.size();
  for (auto &it : g_mempool)
  {
    if (it.accused < g_ledgerTrust.size())
    {
      g_ledgerTrust[it.accused] = Clamp01(g_ledgerTrust[it.accused] + it.delta);
      g_reportsCommitted++;
      LogEvent("BLOCK_COMMIT_ITEM",
               "accused=" + std::to_string(it.accused) +
               ",delta=" + std::to_string(it.delta) +
               ",trust=" + std::to_string(g_ledgerTrust[it.accused]));
    }
  }
  g_mempool.clear();

  g_blocks++;
  double lat = Simulator::Now().GetSeconds() - g_blockStart;
  g_blockLatencySum += lat;

  LogEvent("BLOCK_COMMIT_DONE",
           "block=" + std::to_string(g_blocks) +
           ",items=" + std::to_string(items) +
           ",lat=" + std::to_string(lat));

  Simulator::Schedule(MilliSeconds(g_blockIntervalMs), &CommitBlockDone); // keep commits periodic
}

static void StartBlockchain()
{
  // first block: start now, done after mineDelay
  g_blockStart = Simulator::Now().GetSeconds();
  Simulator::Schedule(MilliSeconds(g_mineDelayMs), []() {
    double lat = Simulator::Now().GetSeconds() - g_blockStart;
    g_blockLatencySum += lat;

    uint32_t items = (uint32_t)g_mempool.size();
    for (auto &it : g_mempool)
    {
      if (it.accused < g_ledgerTrust.size())
      {
        g_ledgerTrust[it.accused] = Clamp01(g_ledgerTrust[it.accused] + it.delta);
        g_reportsCommitted++;
        LogEvent("BLOCK_COMMIT_ITEM",
                 "accused=" + std::to_string(it.accused) +
                 ",delta=" + std::to_string(it.delta) +
                 ",trust=" + std::to_string(g_ledgerTrust[it.accused]));
      }
    }
    g_mempool.clear();

    g_blocks++;
    LogEvent("BLOCK_COMMIT_DONE",
             "block=" + std::to_string(g_blocks) +
             ",items=" + std::to_string(items) +
             ",lat=" + std::to_string(lat));

    // schedule next block start
    Simulator::Schedule(MilliSeconds(g_blockIntervalMs), &StartBlockchain);
  });
}

/* ===================== HANDOVER ===================== */
static void FinishHandover(uint32_t vehId, uint32_t toRsu, bool fast, uint32_t delayMs)
{
  g_vs[vehId].currentRsu = toRsu;
  g_vs[vehId].authed = true;
  g_vs[vehId].authInProgress = false;

  double hoDelay = Simulator::Now().GetSeconds() - g_vs[vehId].handoverStart;
  g_handoverDelaySum += hoDelay;

  if (fast) g_fastAuthCount++;
  else g_fullAuthCount++;

  LogEvent("HO_DONE",
           "veh=" + std::to_string(vehId) +
           ",to=" + std::to_string(toRsu) +
           ",mode=" + std::string(fast ? "FAST" : "FULL") +
           ",authDelayMs=" + std::to_string(delayMs) +
           ",hoDelay=" + std::to_string(hoDelay));
}

static void CheckHandovers(Ptr<Node> vehNode)
{
  uint32_t vehId = vehNode->GetId();
  if (vehId >= g_nVehicles)
  {
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandovers, vehNode);
    return;
  }

  Vector p = vehNode->GetObject<MobilityModel>()->GetPosition();
  uint32_t nearest = GetNearestRsu(p);

  if (nearest != g_vs[vehId].currentRsu && !g_vs[vehId].authInProgress)
  {
    double trust = (vehId < g_ledgerTrust.size()) ? g_ledgerTrust[vehId] : 0.5;

    if (trust < g_trustMinThresh)
    {
      g_rejectCount++;
      LogEvent("HO_REJECT",
               "veh=" + std::to_string(vehId) +
               ",from=" + std::to_string(g_vs[vehId].currentRsu) +
               ",to=" + std::to_string(nearest) +
               ",trust=" + std::to_string(trust));
    }
    else
    {
      bool fast = (trust >= g_trustFastThresh);
      uint32_t delayMs = fast ? g_fastAuthDelayMs : g_fullAuthDelayMs;

      g_handoverCount++;
      g_vs[vehId].authInProgress = true;
      g_vs[vehId].authed = false;
      g_vs[vehId].handoverStart = Simulator::Now().GetSeconds();

      LogEvent("HO_START",
               "veh=" + std::to_string(vehId) +
               ",from=" + std::to_string(g_vs[vehId].currentRsu) +
               ",to=" + std::to_string(nearest) +
               ",trust=" + std::to_string(trust));

      Simulator::Schedule(MilliSeconds(delayMs),
                          &FinishHandover, vehId, nearest, fast, delayMs);
    }
  }

  Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandovers, vehNode);
}

/* ===================== CSV METRICS ===================== */
static void WriteCsv()
{
  double pdr = (g_txData > 0) ? double(g_rxData) / double(g_txData) : 0.0;
  double avgDelay = (g_rxData > 0) ? (g_delaySum / double(g_rxData)) : 0.0;
  double thr = (g_simTime > 0) ? (double(g_rxBytes) * 8.0 / g_simTime) : 0.0;
  double avgBlockLat = (g_blocks > 0) ? (g_blockLatencySum / double(g_blocks)) : 0.0;

  double avgTrust = 0.0;
  if (!g_ledgerTrust.empty())
  {
    avgTrust = std::accumulate(g_ledgerTrust.begin(), g_ledgerTrust.end(), 0.0) / g_ledgerTrust.size();
  }

  double avgHoDelay = (g_handoverCount > 0) ? (g_handoverDelaySum / double(g_handoverCount)) : 0.0;

  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f << "nVehicles,nRsu,simTime,intervalMs,payloadSize,cryptoDelayUsTx,cryptoDelayUsRx,maliciousRate,enableReplayAttack,replayEveryMs,blockIntervalMs,mineDelayMs,"
       "txData,rxData,replayDrops,sigDrops,pdr,avgDelay_s,throughput_bps,reportsSent,reportsRxAtRsu,blocks,reportsCommitted,avgBlockLatency_s,avgLedgerTrust,"
       "handoverCount,avgHandoverDelay_s,fastAuthCount,fullAuthCount,rejectCount,trustFastThresh,trustMinThresh,fastAuthDelayMs,fullAuthDelayMs\n";

  f << g_nVehicles << "," << g_nRsu << "," << g_simTime << "," << g_intervalMs << "," << g_payloadSize << ","
    << g_cryptoDelayUsTx << "," << g_cryptoDelayUsRx << "," << g_maliciousRate << "," << (g_enableReplayAttack ? 1 : 0) << ","
    << g_replayEveryMs << "," << g_blockIntervalMs << "," << g_mineDelayMs << ","
    << g_txData << "," << g_rxData << "," << g_replayDrops << "," << g_sigDrops << ","
    << pdr << "," << avgDelay << "," << thr << ","
    << g_reportsSent << "," << g_reportsRxAtRsu << ","
    << g_blocks << "," << g_reportsCommitted << "," << avgBlockLat << "," << avgTrust << ","
    << g_handoverCount << "," << avgHoDelay << ","
    << g_fastAuthCount << "," << g_fullAuthCount << "," << g_rejectCount << ","
    << g_trustFastThresh << "," << g_trustMinThresh << ","
    << g_fastAuthDelayMs << "," << g_fullAuthDelayMs
    << "\n";

  f.close();
}

/* ===================== main ===================== */
int main(int argc, char* argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("nRsu", "Number of RSUs", g_nRsu);
  cmd.AddValue("simTime", "Simulation time (s)", g_simTime);
  cmd.AddValue("payloadSize", "Payload size bytes", g_payloadSize);
  cmd.AddValue("intervalMs", "Data packet interval ms", g_intervalMs);
  cmd.AddValue("cryptoDelayUsTx", "TX crypto delay us", g_cryptoDelayUsTx);
  cmd.AddValue("cryptoDelayUsRx", "RX crypto delay us", g_cryptoDelayUsRx);
  cmd.AddValue("enableReplayAttack", "Enable replay attack 0/1", g_enableReplayAttack);
  cmd.AddValue("replayEveryMs", "Replay interval ms", g_replayEveryMs);
  cmd.AddValue("maliciousRate", "Probability sender corrupts signature", g_maliciousRate);
  cmd.AddValue("blockIntervalMs", "Block interval ms", g_blockIntervalMs);
  cmd.AddValue("mineDelayMs", "Mining delay ms", g_mineDelayMs);
  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.AddValue("eventsOut", "Events output file", g_eventsOut);
  cmd.AddValue("trustFastThresh", "Trust >= this => FAST auth", g_trustFastThresh);
  cmd.AddValue("trustMinThresh", "Trust < this => reject", g_trustMinThresh);
  cmd.AddValue("fastAuthDelayMs", "FAST auth delay ms", g_fastAuthDelayMs);
  cmd.AddValue("fullAuthDelayMs", "FULL auth delay ms", g_fullAuthDelayMs);
  cmd.AddValue("handoverCheckMs", "Handover check interval ms", g_handoverCheckMs);
  cmd.Parse(argc, argv);

  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
  g_evt << "time_s,event,details\n";

  g_vehicles.Create(g_nVehicles);
  g_rsus.Create(g_nRsu);

  NodeContainer all;
  all.Add(g_vehicles);
  all.Add(g_rsus);

  // Mobility: vehicles random walk, RSUs fixed
  MobilityHelper mobVeh;
  mobVeh.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                              "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=60.0]"),
                              "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=60.0]"));
  mobVeh.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                          "Bounds", RectangleValue(Rectangle(0, 60, 0, 60)),
                          "Speed", StringValue("ns3::ConstantRandomVariable[Constant=8.0]"),
                          "Distance", DoubleValue(5.0));
  mobVeh.Install(g_vehicles);

  MobilityHelper mobRsu;
  mobRsu.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mobRsu.Install(g_rsus);

  // RSU positions
  g_rsuPos.clear();
  for (uint32_t r = 0; r < g_nRsu; r++)
  {
    double x = (r == 0) ? 10.0 : 50.0;
    double y = (r == 0) ? 10.0 : 50.0;
    g_rsus.Get(r)->GetObject<MobilityModel>()->SetPosition(Vector(x, y, 0));
    g_rsuPos.push_back(Vector(x, y, 0));
  }

  // WiFi ad-hoc
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());
  phy.Set("TxPowerStart", DoubleValue(16.0));
  phy.Set("TxPowerEnd", DoubleValue(16.0));

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devs = wifi.Install(phy, mac, all);

  InternetStackHelper internet;
  internet.Install(all);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  Ipv4InterfaceContainer ifs = ipv4.Assign(devs);

  // RSU0 address
  g_rsu0Addr = ifs.GetAddress(g_nVehicles + 0);

  // Init trust ledger
  g_ledgerTrust.assign(g_nVehicles, 0.8);

  // Replay caches for ALL nodes
  g_caches.resize(all.GetN());
  for (uint32_t i = 0; i < all.GetN(); i++)
    g_caches[i] = std::make_unique<ReplayCache>(5000);

  // Vehicle states init: current RSU
  g_vs.assign(g_nVehicles, VehicleState{});
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    Vector p = g_vehicles.Get(v)->GetObject<MobilityModel>()->GetPosition();
    g_vs[v].currentRsu = GetNearestRsu(p);
  }

  // Data recv sockets on all nodes
  g_dataRecvSock.resize(all.GetN());
  for (uint32_t i = 0; i < all.GetN(); i++)
  {
    Ptr<Socket> s = Socket::CreateSocket(all.Get(i), UdpSocketFactory::GetTypeId());
    s->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_dataPort));
    s->SetRecvCallback(MakeCallback(&RxDataReady));
    g_dataRecvSock[i] = s;
  }

  // RSU0 report recv socket
  g_rsuReportRecvSock = Socket::CreateSocket(g_rsus.Get(0), UdpSocketFactory::GetTypeId());
  g_rsuReportRecvSock->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_reportPort));
  g_rsuReportRecvSock->SetRecvCallback(MakeCallback(&RxReportAtRsu));

  // Vehicles report send sockets -> RSU0
  g_vehicleReportSock.resize(g_nVehicles);
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    Ptr<Socket> s = Socket::CreateSocket(g_vehicles.Get(v), UdpSocketFactory::GetTypeId());
    s->Connect(InetSocketAddress(g_rsu0Addr, g_reportPort));
    g_vehicleReportSock[v] = s;
  }

  // Data sender: vehicle0 broadcast
  g_sendSock = Socket::CreateSocket(g_vehicles.Get(0), UdpSocketFactory::GetTypeId());
  g_sendSock->SetAllowBroadcast(true);
  g_sendSock->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), g_dataPort));

  // Start processes
  Simulator::Schedule(Seconds(0.5), &SendNewPacket, g_sendSock, 0);
  if (g_enableReplayAttack)
    Simulator::Schedule(Seconds(1.0), &ReplayAttackTick, g_sendSock);

  Simulator::Schedule(Seconds(1.0), &MaybeMisbehaviorReportTick);
  Simulator::Schedule(Seconds(0.0), &StartBlockchain);

  // Handover checks
  for (uint32_t v = 0; v < g_nVehicles; v++)
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandovers, g_vehicles.Get(v));

  Simulator::Schedule(Seconds(g_simTime - 0.001), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  if (g_evt.is_open()) g_evt.close();
  return 0;
} 
