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

using namespace ns3;

// ---------------- Replay Cache ----------------
class ReplayCache
{
public:
  explicit ReplayCache(size_t maxSize) : m_maxSize(maxSize) {}

  bool Seen(uint64_t nonce) const { return m_set.find(nonce) != m_set.end(); }

  void Add(uint64_t nonce)
  {
    if (m_set.find(nonce) != m_set.end()) return;
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

// ---------------- Globals ----------------
static uint64_t g_txData = 0;
static uint64_t g_rxData = 0;
static uint64_t g_replayDrops = 0;
static uint64_t g_sigDrops = 0;
static double   g_delaySum = 0.0;
static uint64_t g_rxBytes = 0;

static double   g_simTime = 20.0;
static uint32_t g_nVehicles = 10;

static uint32_t g_payloadSize = 64;
static uint32_t g_intervalMs = 100;

static uint32_t g_cryptoDelayUsTx = 200;
static uint32_t g_cryptoDelayUsRx = 200;

static std::string g_csvOut = "bc_metrics.csv";
static std::string g_eventsOut = "bc_events.csv";

static const uint16_t g_dataPort = 9000;

// Replay caches
static std::vector<std::unique_ptr<ReplayCache>> g_caches;

// Last packet for replay
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

// Events stream
static std::ofstream g_evt;

// ---------------- CSV-safe event logger (SAME FIX) ----------------
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
  // time_s,event,"details"
  g_evt << Simulator::Now().GetSeconds()
        << "," << ev
        << ",\"" << CSVEscape(details) << "\"\n";
}

// ---------------- Utils ----------------
static double Clamp01(double x)
{
  return std::max(0.0, std::min(1.0, x));
}

static uint32_t ComputeSig(uint64_t nonce, uint32_t senderId)
{
  uint64_t x = nonce ^ ((uint64_t)senderId << 32);
  x ^= (x >> 33);
  x *= 0xff51afd7ed558ccdULL;
  x ^= (x >> 33);
  return (uint32_t)(x & 0xffffffff);
}

// ---------------- RX ----------------
static void ProcessReceived(uint32_t rxId, DataHdr hdr, uint32_t size)
{
  // Signature check
  if (hdr.sig != ComputeSig(hdr.nonce, hdr.senderId))
  {
    g_sigDrops++;
    LogEvent("DATA_DROP_SIG",
             "rx=" + std::to_string(rxId) +
             ",sender=" + std::to_string(hdr.senderId) +
             ",nonce=" + std::to_string(hdr.nonce));
    return;
  }

  // Replay check
  ReplayCache* c = g_caches.at(rxId).get();
  if (c->Seen(hdr.nonce))
  {
    g_replayDrops++;
    LogEvent("DATA_DROP_REPLAY",
             "rx=" + std::to_string(rxId) +
             ",sender=" + std::to_string(hdr.senderId) +
             ",nonce=" + std::to_string(hdr.nonce));
    return;
  }
  c->Add(hdr.nonce);

  double d = Simulator::Now().GetSeconds() - hdr.txTime;
  if (d < 0) d = 0;

  g_rxData++;
  g_delaySum += d;
  g_rxBytes += size;
}

static void RxReady(Ptr<Socket> s)
{
  uint32_t rxId = s->GetNode()->GetId();
  while (true)
  {
    Address from;
    Ptr<Packet> p = s->RecvFrom(from);
    if (!p || p->GetSize() == 0) break;
    if (p->GetSize() < sizeof(DataHdr)) continue;

    DataHdr hdr{};
    std::vector<uint8_t> buf(p->GetSize());
    p->CopyData(buf.data(), buf.size());
    std::memcpy(&hdr, buf.data(), sizeof(DataHdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsRx),
                        &ProcessReceived, rxId, hdr, p->GetSize());
  }
}

// ---------------- TX ----------------
static void DoSend(Ptr<Socket> s, std::vector<uint8_t> wire)
{
  s->Send(Create<Packet>(wire.data(), wire.size()));
  g_txData++;
}

static void SendData(Ptr<Socket> s, uint32_t sid)
{
  DataHdr hdr{};
  hdr.nonce = ((uint64_t)sid << 48) ^ Simulator::Now().GetNanoSeconds();
  hdr.txTime = Simulator::Now().GetSeconds();
  hdr.senderId = sid;
  hdr.sig = ComputeSig(hdr.nonce, sid);

  std::vector<uint8_t> wire(sizeof(DataHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(DataHdr));

  g_lastWire = wire;
  g_hasLast = true;

  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSend, s, wire);
  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendData, s, sid);
}

// ---------------- CSV ----------------
static void WriteCsv()
{
  double pdr = (g_txData > 0) ? (double)g_rxData / g_txData : 0.0;

  uint64_t expectedRx =
    (g_nVehicles > 1) ? g_txData * (uint64_t)(g_nVehicles - 1) : 0;

  double pdr_norm =
    (expectedRx > 0) ? (double)g_rxData / expectedRx : 0.0;

  double avgDelay = (g_rxData > 0) ? g_delaySum / g_rxData : 0.0;
  double thr = (g_simTime > 0) ? (double)g_rxBytes * 8.0 / g_simTime : 0.0;

  std::ofstream f(g_csvOut);
  f << "nVehicles,txData,rxData,pdr,pdr_norm,avgDelay_s,throughput_bps,replayDrops,sigDrops\n";
  f << g_nVehicles << "," << g_txData << "," << g_rxData << ","
    << pdr << "," << pdr_norm << "," << avgDelay << "," << thr << ","
    << g_replayDrops << "," << g_sigDrops << "\n";
  f.close();

  std::cout << "PDR_raw=" << pdr
            << " PDR_norm=" << pdr_norm
            << " AvgDelay=" << avgDelay
            << " Throughput=" << thr
            << " ReplayDrops=" << g_replayDrops
            << " SigDrops=" << g_sigDrops
            << std::endl;
}

// ---------------- main ----------------
int main(int argc, char* argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Vehicles", g_nVehicles);
  cmd.AddValue("simTime", "Sim time", g_simTime);
  cmd.AddValue("payloadSize", "Payload size bytes", g_payloadSize);
  cmd.AddValue("intervalMs", "Packet interval ms", g_intervalMs);
  cmd.AddValue("cryptoDelayUsTx", "TX crypto delay us", g_cryptoDelayUsTx);
  cmd.AddValue("cryptoDelayUsRx", "RX crypto delay us", g_cryptoDelayUsRx);
  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.AddValue("eventsOut", "Events output file", g_eventsOut);
  cmd.Parse(argc, argv);

  // open events
  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
  if (g_evt.is_open())
    g_evt << "time_s,event,details\n";

  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  MobilityHelper mob;
  mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mob.Install(vehicles);

  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiPhyHelper phy;
  phy.SetChannel(YansWifiChannelHelper::Default().Create());

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devs = wifi.Install(phy, mac, vehicles);

  InternetStackHelper internet;
  internet.Install(vehicles);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  ipv4.Assign(devs);

  // caches
  g_caches.resize(g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; i++)
    g_caches[i] = std::make_unique<ReplayCache>(5000);

  // recv sockets
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<Socket> r = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    r->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_dataPort));
    r->SetRecvCallback(MakeCallback(&RxReady));
  }

  // sender (vehicle0 broadcast)
  Ptr<Socket> send = Socket::CreateSocket(vehicles.Get(0), UdpSocketFactory::GetTypeId());
  send->SetAllowBroadcast(true);
  send->Connect(InetSocketAddress("10.1.255.255", g_dataPort));

  Simulator::Schedule(Seconds(1.0), &SendData, send, 0);
  Simulator::Schedule(Seconds(g_simTime - 0.001), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  if (g_evt.is_open()) g_evt.close();
  return 0;
}
