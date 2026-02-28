#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"

#include <fstream>
#include <unordered_map>
#include <unordered_set>
#include <deque>
#include <vector>
#include <cstring>
#include <memory>
#include <algorithm>

using namespace ns3;

// ---------------- Replay Cache ----------------
class ReplayCache
{
public:
  explicit ReplayCache(size_t maxSize) : m_maxSize(maxSize) {}

  bool Seen(uint64_t nonce) const
  {
    return m_set.find(nonce) != m_set.end();
  }

  void Add(uint64_t nonce)
  {
    if (m_set.find(nonce) != m_set.end())
      return;

    m_queue.push_back(nonce);
    m_set.insert(nonce);

    while (m_queue.size() > m_maxSize)
    {
      uint64_t old = m_queue.front();
      m_queue.pop_front();
      m_set.erase(old);
    }
  }

private:
  size_t m_maxSize;
  std::unordered_set<uint64_t> m_set;
  std::deque<uint64_t> m_queue;
};

// ----- Packed headers -----
#pragma pack(push, 1)
struct DataHdr
{
  uint64_t nonce;
  double   txTime;     // seconds
  uint32_t senderId;   // node id
  uint32_t sig;        // simple "signature"
  uint8_t  isReplay;   // 0/1 (debug only)
};
#pragma pack(pop)

#pragma pack(push, 1)
struct ReportHdr
{
  double   t;
  uint32_t reporterId;
  uint32_t accusedId;
  float    delta;      // trust delta (+/-)
};
#pragma pack(pop)

// ---------------- Globals / Parameters ----------------
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

static std::string g_csvOut = "bc_metrics.csv";
static std::string g_eventsOut = "bc_events.csv";

static const uint16_t g_dataPort = 9000;
static const uint16_t g_reportPort = 9100;

// One replay cache per node (for all nodes that receive data)
static std::vector<std::unique_ptr<ReplayCache>> g_caches;

// Store last sent raw bytes for replay attack
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

// Vehicle trust ledger stored at RSU (0..nVehicles-1)
static std::vector<double> g_ledgerTrust;

// RSU mempool of reports
struct ReportItem
{
  double t;
  uint32_t reporter;
  uint32_t accused;
  double delta;
};
static std::deque<ReportItem> g_mempool;

// For block latency
static double g_lastBlockStart = 0.0;

// Event logging
static std::ofstream g_evt;

// RSU address (use RSU0 for simplicity)
static Ipv4Address g_rsu0Addr;

// Sockets
static Ptr<Socket> g_rsuReportSock;                 // RSU recv reports
static std::vector<Ptr<Socket>> g_vehicleReportSock; // vehicles send reports

// ---------------- Utilities ----------------
static double Clamp01(double x)
{
  if (x < 0.0) return 0.0;
  if (x > 1.0) return 1.0;
  return x;
}

static void LogEvent(const std::string& ev, const std::string& details)
{
  if (!g_evt.is_open()) return;
  g_evt << Simulator::Now().GetSeconds() << "," << ev << "," << details << "\n";
}

// Simple “signature” (NOT real crypto; just simulation)
static uint32_t ComputeSig(uint64_t nonce, uint32_t senderId)
{
  // A tiny mixing function
  uint64_t x = nonce ^ (static_cast<uint64_t>(senderId) << 32) ^ 0xA5A5A5A55A5A5A5AULL;
  x ^= (x >> 33);
  x *= 0xff51afd7ed558ccdULL;
  x ^= (x >> 33);
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= (x >> 33);
  return static_cast<uint32_t>(x & 0xFFFFFFFFu);
}

// ---------------- Data Plane ----------------
static void ProcessReceivedData(uint32_t receiverId, DataHdr hdr, uint32_t pktSize)
{
  // Signature verify
  uint32_t expect = ComputeSig(hdr.nonce, hdr.senderId);
  if (hdr.sig != expect)
  {
    g_sigDrops++;
    LogEvent("DATA_DROP_SIG",
             "rx=" + std::to_string(receiverId) +
             ",sender=" + std::to_string(hdr.senderId) +
             ",nonce=" + std::to_string(hdr.nonce));
    return;
  }

  // Replay detection
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

  double now = Simulator::Now().GetSeconds();
  double delay = now - hdr.txTime;
  if (delay < 0) delay = 0;

  g_rxData++;
  g_delaySum += delay;
  g_rxBytes += pktSize;

  LogEvent("DATA_RX_OK",
           "rx=" + std::to_string(receiverId) +
           ",sender=" + std::to_string(hdr.senderId) +
           ",delay_s=" + std::to_string(delay));
}

static void RxDataSocketReady(Ptr<Socket> socket)
{
  uint32_t receiverId = socket->GetNode()->GetId();

  while (true)
  {
    Address from;
    Ptr<Packet> packet = socket->RecvFrom(from);
    if (!packet || packet->GetSize() == 0)
      break;

    if (packet->GetSize() < sizeof(DataHdr))
      continue;

    std::vector<uint8_t> buf(packet->GetSize());
    packet->CopyData(buf.data(), buf.size());

    DataHdr hdr{};
    std::memcpy(&hdr, buf.data(), sizeof(DataHdr));

    // Simulate RX verify delay
    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsRx), &ProcessReceivedData,
                        receiverId, hdr, packet->GetSize());
  }
}

static void DoSendRaw(Ptr<Socket> sock, const std::vector<uint8_t>& wire)
{
  Ptr<Packet> p = Create<Packet>(wire.data(), wire.size());
  sock->Send(p);
  g_txData++;
}

static void SendNewDataPacket(Ptr<Socket> sock, uint32_t senderId, Ptr<UniformRandomVariable> urv)
{
  DataHdr hdr{};
  // Stable unique-ish nonce based on time + sender
  hdr.nonce = (static_cast<uint64_t>(senderId) << 48) ^
              static_cast<uint64_t>(Simulator::Now().GetNanoSeconds());
  hdr.txTime = Simulator::Now().GetSeconds();
  hdr.senderId = senderId;
  hdr.isReplay = 0;

  hdr.sig = ComputeSig(hdr.nonce, hdr.senderId);

  // Malicious behavior: corrupt signature with probability maliciousRate
  if (urv->GetValue(0.0, 1.0) < g_maliciousRate)
  {
    hdr.sig ^= 0xDEADBEEF;
  }

  std::vector<uint8_t> wire(sizeof(DataHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(DataHdr));

  // Payload pattern
  for (uint32_t i = 0; i < g_payloadSize; i++)
    wire[sizeof(DataHdr) + i] = static_cast<uint8_t>(i & 0xFF);

  // store for replay
  g_lastWire = wire;
  g_hasLast = true;

  // Simulate TX sign delay then send
  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, sock, wire);

  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendNewDataPacket, sock, senderId, urv);
}

static void ReplayAttackTick(Ptr<Socket> sock)
{
  if (g_enableReplayAttack && g_hasLast)
  {
    std::vector<uint8_t> wire = g_lastWire;

    DataHdr hdr{};
    std::memcpy(&hdr, wire.data(), sizeof(DataHdr));
    hdr.isReplay = 1;
    std::memcpy(wire.data(), &hdr, sizeof(DataHdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, sock, wire);
    LogEvent("REPLAY_SENT", "nonce=" + std::to_string(hdr.nonce));
  }

  Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick, sock);
}

// ---------------- Report Plane (Vehicle -> RSU) ----------------
static void SendReport(uint32_t reporterId, uint32_t accusedId, double delta)
{
  if (reporterId >= g_vehicleReportSock.size() || g_vehicleReportSock[reporterId] == nullptr)
    return;

  ReportHdr r{};
  r.t = Simulator::Now().GetSeconds();
  r.reporterId = reporterId;
  r.accusedId = accusedId;
  r.delta = static_cast<float>(delta);

  std::vector<uint8_t> wire(sizeof(ReportHdr), 0);
  std::memcpy(wire.data(), &r, sizeof(ReportHdr));

  Ptr<Packet> p = Create<Packet>(wire.data(), wire.size());
  g_vehicleReportSock[reporterId]->Send(p);
  g_reportsSent++;

  LogEvent("REPORT_SENT",
           "by=" + std::to_string(reporterId) +
           ",about=" + std::to_string(accusedId) +
           ",delta=" + std::to_string(delta));
}

static void RsusReportSocketReady(Ptr<Socket> socket)
{
  while (true)
  {
    Address from;
    Ptr<Packet> packet = socket->RecvFrom(from);
    if (!packet || packet->GetSize() == 0)
      break;

    if (packet->GetSize() < sizeof(ReportHdr))
      continue;

    std::vector<uint8_t> buf(packet->GetSize());
    packet->CopyData(buf.data(), buf.size());

    ReportHdr r{};
    std::memcpy(&r, buf.data(), sizeof(ReportHdr));

    g_reportsRxAtRsu++;

    // push to mempool
    ReportItem it;
    it.t = r.t;
    it.reporter = r.reporterId;
    it.accused  = r.accusedId;
    it.delta    = r.delta;
    g_mempool.push_back(it);

    LogEvent("REPORT_RX_RSU",
             "rsu=" + std::to_string(socket->GetNode()->GetId()) +
             ",by=" + std::to_string(r.reporterId) +
             ",about=" + std::to_string(r.accusedId) +
             ",delta=" + std::to_string(r.delta));
  }
}

// Simple periodic reporting model: each vehicle reports on itself or random accused.
// (You can later replace this with “report on bad sender seen”.)
static void PeriodicReportTick(uint32_t reporterId, Ptr<UniformRandomVariable> urv)
{
  // pick an accused vehicle
  uint32_t accused = static_cast<uint32_t>(urv->GetInteger(0, static_cast<int64_t>(g_nVehicles - 1)));

  // maliciousRate controls negative reports frequency loosely
  double delta = (urv->GetValue(0.0, 1.0) < g_maliciousRate) ? -0.05 : +0.02;

  SendReport(reporterId, accused, delta);

  Simulator::Schedule(Seconds(1.0), &PeriodicReportTick, reporterId, urv);
}

// ---------------- Blockchain / Mining ----------------
static void CommitBlock()
{
  // Commit up to N items
  const uint32_t maxItems = 200;
  uint32_t committed = 0;

  while (!g_mempool.empty() && committed < maxItems)
  {
    ReportItem it = g_mempool.front();
    g_mempool.pop_front();

    if (it.accused < g_ledgerTrust.size())
    {
      g_ledgerTrust[it.accused] = Clamp01(g_ledgerTrust[it.accused] + it.delta);
    }

    committed++;
    g_reportsCommitted++;

    LogEvent("BLOCK_COMMIT_ITEM",
             "accused=" + std::to_string(it.accused) +
             ",delta=" + std::to_string(it.delta) +
             ",trust=" + std::to_string(g_ledgerTrust[it.accused]));
  }

  g_blocks++;
  double now = Simulator::Now().GetSeconds();
  double lat = now - g_lastBlockStart;
  g_blockLatencySum += lat;

  LogEvent("BLOCK_COMMIT_DONE",
           "block=" + std::to_string(g_blocks) +
           ",items=" + std::to_string(committed) +
           ",lat_s=" + std::to_string(lat));

  // schedule next block start
  Simulator::Schedule(MilliSeconds(g_blockIntervalMs), [](){
    g_lastBlockStart = Simulator::Now().GetSeconds();
    LogEvent("BLOCK_MINE_START", "block_next=" + std::to_string(g_blocks + 1));
    Simulator::Schedule(MilliSeconds(g_mineDelayMs), &CommitBlock);
  });
}

static void StartMiningLoop()
{
  g_lastBlockStart = Simulator::Now().GetSeconds();
  LogEvent("BLOCK_MINE_START", "block_next=1");
  Simulator::Schedule(MilliSeconds(g_mineDelayMs), &CommitBlock);
}

// ---------------- CSV ----------------
static void WriteCsv()
{
  double pdr = (g_txData > 0) ? (double)g_rxData / (double)g_txData : 0.0;
  double avgDelay = (g_rxData > 0) ? g_delaySum / (double)g_rxData : 0.0;
  double throughputBps = (g_simTime > 0) ? (double)g_rxBytes * 8.0 / g_simTime : 0.0;

  double avgBlockLat = (g_blocks > 0) ? g_blockLatencySum / (double)g_blocks : 0.0;

  double trustSum = 0.0;
  for (double t : g_ledgerTrust) trustSum += t;
  double avgLedgerTrust = (!g_ledgerTrust.empty()) ? trustSum / (double)g_ledgerTrust.size() : 0.0;

  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f << "nVehicles,nRsu,simTime,intervalMs,payloadSize,cryptoDelayUsTx,cryptoDelayUsRx,maliciousRate,"
       "enableReplayAttack,replayEveryMs,blockIntervalMs,mineDelayMs,"
       "txData,rxData,replayDrops,sigDrops,pdr,avgDelay_s,throughput_bps,"
       "reportsSent,reportsRxAtRsu,blocks,reportsCommitted,avgBlockLatency_s,avgLedgerTrust\n";

  f << g_nVehicles << "," << g_nRsu << "," << g_simTime << ","
    << g_intervalMs << "," << g_payloadSize << ","
    << g_cryptoDelayUsTx << "," << g_cryptoDelayUsRx << ","
    << g_maliciousRate << ","
    << (g_enableReplayAttack ? 1 : 0) << "," << g_replayEveryMs << ","
    << g_blockIntervalMs << "," << g_mineDelayMs << ","
    << g_txData << "," << g_rxData << ","
    << g_replayDrops << "," << g_sigDrops << ","
    << pdr << "," << avgDelay << "," << throughputBps << ","
    << g_reportsSent << "," << g_reportsRxAtRsu << ","
    << g_blocks << "," << g_reportsCommitted << ","
    << avgBlockLat << "," << avgLedgerTrust << "\n";

  f.close();

  std::cout << "Saved blockchain trust metrics to " << g_csvOut << "\n";
  std::cout << "TX=" << g_txData
            << " RX=" << g_rxData
            << " ReplayDrops=" << g_replayDrops
            << " SigDrops=" << g_sigDrops
            << " PDR=" << pdr
            << " AvgDelay=" << avgDelay << "s"
            << " Throughput=" << throughputBps << " bps"
            << " Blocks=" << g_blocks
            << " AvgBlockLatency=" << avgBlockLat << "s"
            << " AvgLedgerTrust=" << avgLedgerTrust
            << std::endl;
}

// ---------------- Main ----------------
int main(int argc, char *argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("nRsu", "Number of RSUs", g_nRsu);

  cmd.AddValue("simTime", "Simulation time (s)", g_simTime);
  cmd.AddValue("intervalMs", "Data packet interval (ms)", g_intervalMs);
  cmd.AddValue("payloadSize", "Payload size (bytes)", g_payloadSize);

  cmd.AddValue("cryptoDelayUsTx", "Simulated TX crypto delay (us)", g_cryptoDelayUsTx);
  cmd.AddValue("cryptoDelayUsRx", "Simulated RX crypto delay (us)", g_cryptoDelayUsRx);

  cmd.AddValue("enableReplayAttack", "Enable replay attack (0/1)", g_enableReplayAttack);
  cmd.AddValue("replayEveryMs", "Replay interval (ms)", g_replayEveryMs);

  cmd.AddValue("maliciousRate", "Probability of malicious behavior (0..1)", g_maliciousRate);

  cmd.AddValue("blockIntervalMs", "Block interval (ms)", g_blockIntervalMs);
  cmd.AddValue("mineDelayMs", "Mining/commit delay (ms)", g_mineDelayMs);

  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.AddValue("eventsOut", "Events CSV output file", g_eventsOut);
  cmd.Parse(argc, argv);

  // Open events log
  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
  g_evt << "time_s,event,details\n";

  // Create nodes
  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  NodeContainer rsus;
  rsus.Create(g_nRsu);

  NodeContainer all;
  all.Add(vehicles);
  all.Add(rsus);

  // Mobility: keep CLOSE so RX > 0 in WSL too
  MobilityHelper mobV;
  mobV.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                            "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=50.0]"),
                            "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=50.0]"));
  mobV.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                        "Bounds", RectangleValue(Rectangle(0, 50, 0, 50)),
                        "Speed", StringValue("ns3::ConstantRandomVariable[Constant=6.0]"),
                        "Distance", DoubleValue(5.0));
  mobV.Install(vehicles);

  // RSUs fixed points
  MobilityHelper mobR;
  Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
  for (uint32_t i = 0; i < g_nRsu; i++)
  {
    pos->Add(Vector(10.0 + 20.0 * i, 10.0, 0.0));
  }
  mobR.SetPositionAllocator(pos);
  mobR.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mobR.Install(rsus);

  // WiFi ad-hoc baseline
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());
  phy.Set("TxPowerStart", DoubleValue(16.0));
  phy.Set("TxPowerEnd", DoubleValue(16.0));

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devices = wifi.Install(phy, mac, all);

  InternetStackHelper internet;
  internet.Install(all);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0"); // /16
  Ipv4InterfaceContainer ifs = ipv4.Assign(devices);

  // RSU0 address is at index g_nVehicles
  g_rsu0Addr = ifs.GetAddress(g_nVehicles);

  // Replay caches for ALL nodes (vehicles+rsus) so indexing by nodeId works
  g_caches.clear();
  g_caches.resize(all.GetN());
  for (uint32_t i = 0; i < all.GetN(); i++)
    g_caches[i] = std::make_unique<ReplayCache>(5000);

  // Trust ledger for vehicles only
  g_ledgerTrust.assign(g_nVehicles, 0.7);

  // Data recv sockets on all nodes (vehicles + rsus optional)
  for (uint32_t i = 0; i < all.GetN(); i++)
  {
    Ptr<Socket> recvSocket = Socket::CreateSocket(all.Get(i), UdpSocketFactory::GetTypeId());
    recvSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_dataPort));
    recvSocket->SetRecvCallback(MakeCallback(&RxDataSocketReady));
  }

  // RSU report recv socket (only RSU0 for simplicity)
  g_rsuReportSock = Socket::CreateSocket(rsus.Get(0), UdpSocketFactory::GetTypeId());
  g_rsuReportSock->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_reportPort));
  g_rsuReportSock->SetRecvCallback(MakeCallback(&RsusReportSocketReady));

  // Vehicle report send sockets
  g_vehicleReportSock.assign(g_nVehicles, nullptr);
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<Socket> s = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    s->Connect(InetSocketAddress(g_rsu0Addr, g_reportPort));
    g_vehicleReportSock[i] = s;
  }

  // Sender socket on vehicle 0 (broadcast within /16)
  Ptr<Socket> sendSocket = Socket::CreateSocket(vehicles.Get(0), UdpSocketFactory::GetTypeId());
  sendSocket->SetAllowBroadcast(true);
  sendSocket->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), g_dataPort));

  Ptr<UniformRandomVariable> urv0 = CreateObject<UniformRandomVariable>();
  Simulator::Schedule(Seconds(1.0), &SendNewDataPacket, sendSocket, vehicles.Get(0)->GetId(), urv0);

  if (g_enableReplayAttack)
  {
    Simulator::Schedule(Seconds(2.0), &ReplayAttackTick, sendSocket);
  }

  // Periodic reports from each vehicle
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<UniformRandomVariable> urv = CreateObject<UniformRandomVariable>();
    Simulator::Schedule(Seconds(1.0), &PeriodicReportTick, i, urv);
  }

  // Start mining loop
  Simulator::Schedule(Seconds(0.0), &StartMiningLoop);

  // Write CSV near end
  Simulator::Schedule(Seconds(g_simTime - 0.001), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  if (g_evt.is_open())
    g_evt.close();

  return 0;
}
