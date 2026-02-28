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

// ----- Message header (packed bytes) -----
#pragma pack(push, 1)
struct MsgHdr
{
  uint64_t nonce;
  double   txTime;    // seconds
  uint32_t senderId;
  uint8_t  isReplay;  // 0/1 (debug only)
};
#pragma pack(pop)

// ---------------- Global metrics ----------------
static uint64_t g_txCount = 0;
static uint64_t g_rxCount = 0;
static uint64_t g_replayDrops = 0;
static double   g_delaySum = 0.0;
static uint64_t g_rxBytes = 0;

// ---------------- Params ----------------
static uint32_t g_nVehicles = 10;
static double   g_simTime = 20.0;
static uint32_t g_payloadSize = 64;
static uint32_t g_intervalMs = 100;
static uint32_t g_cryptoDelayUsTx = 0;
static uint32_t g_cryptoDelayUsRx = 0;
static bool     g_enableReplayAttack = false;
static uint32_t g_replayEveryMs = 300;
static std::string g_csvOut = "secure_metrics.csv";

// One replay cache per node
static std::vector<std::unique_ptr<ReplayCache>> g_caches;

// Store last sent raw bytes for replay attack
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

// ---------------- Helpers ----------------
static void ProcessReceived(uint32_t receiverId, MsgHdr hdr, uint32_t pktSize)
{
  // Ignore self-receive (common in broadcast + bound sockets)
  if (receiverId == hdr.senderId)
    return;

  ReplayCache* cache = g_caches.at(receiverId).get();
  if (cache->Seen(hdr.nonce))
  {
    g_replayDrops++;
    return;
  }
  cache->Add(hdr.nonce);

  double now = Simulator::Now().GetSeconds();
  double delay = now - hdr.txTime;
  if (delay < 0) delay = 0;

  g_rxCount++;
  g_delaySum += delay;
  g_rxBytes += pktSize;
}

static void RxSocketReady(Ptr<Socket> socket)
{
  uint32_t receiverId = socket->GetNode()->GetId();

  while (true)
  {
    Address from;
    Ptr<Packet> packet = socket->RecvFrom(from);
    if (!packet || packet->GetSize() == 0)
      break;

    if (packet->GetSize() < sizeof(MsgHdr))
      continue;

    std::vector<uint8_t> buf(packet->GetSize());
    packet->CopyData(buf.data(), buf.size());

    MsgHdr hdr{};
    std::memcpy(&hdr, buf.data(), sizeof(MsgHdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsRx),
                        &ProcessReceived, receiverId, hdr, packet->GetSize());
  }
}

static void DoSendRaw(Ptr<Socket> sock, std::vector<uint8_t> wire)
{
  Ptr<Packet> p = Create<Packet>(wire.data(), wire.size());
  sock->Send(p);
  g_txCount++;
}

static void SendNewPacket(Ptr<Socket> sock, uint32_t senderId)
{
  MsgHdr hdr{};
  hdr.nonce = (static_cast<uint64_t>(senderId) << 48) ^
              static_cast<uint64_t>(Simulator::Now().GetNanoSeconds());
  hdr.txTime = Simulator::Now().GetSeconds();
  hdr.senderId = senderId;
  hdr.isReplay = 0;

  std::vector<uint8_t> wire(sizeof(MsgHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(MsgHdr));

  for (uint32_t i = 0; i < g_payloadSize; i++)
    wire[sizeof(MsgHdr) + i] = static_cast<uint8_t>(i & 0xFF);

  g_lastWire = wire;
  g_hasLast = true;

  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, sock, wire);
  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendNewPacket, sock, senderId);
}

static void ReplayAttackTick(Ptr<Socket> sock)
{
  if (g_enableReplayAttack && g_hasLast)
  {
    std::vector<uint8_t> wire = g_lastWire;

    MsgHdr hdr{};
    std::memcpy(&hdr, wire.data(), sizeof(MsgHdr));
    hdr.isReplay = 1;
    std::memcpy(wire.data(), &hdr, sizeof(MsgHdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, sock, wire);
  }

  Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick, sock);
}

static void WriteCsv()
{
  // Broadcast expected receptions: each tx should be received by (nVehicles-1) nodes
  double expectedRx = (g_nVehicles > 1) ? (double)g_txCount * (double)(g_nVehicles - 1) : 0.0;
  double pdr = (expectedRx > 0) ? (double)g_rxCount / expectedRx : 0.0;

  double avgDelay = (g_rxCount > 0) ? g_delaySum / (double)g_rxCount : 0.0;
  double throughputBps = (g_simTime > 0) ? (double)g_rxBytes * 8.0 / g_simTime : 0.0;

  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f << "nVehicles,simTime,intervalMs,payloadSize,cryptoDelayUsTx,cryptoDelayUsRx,"
       "enableReplayAttack,replayEveryMs,txCount,rxCount,replayDrops,pdr,avgDelay_s,throughput_bps\n";
  f << g_nVehicles << "," << g_simTime << "," << g_intervalMs << "," << g_payloadSize << ","
    << g_cryptoDelayUsTx << "," << g_cryptoDelayUsRx << ","
    << (g_enableReplayAttack ? 1 : 0) << "," << g_replayEveryMs << ","
    << g_txCount << "," << g_rxCount << "," << g_replayDrops << ","
    << pdr << "," << avgDelay << "," << throughputBps << "\n";
  f.close();

  std::cout << "Saved secure metrics to " << g_csvOut << "\n";
  std::cout << "TX=" << g_txCount
            << " RX=" << g_rxCount
            << " ReplayDrops=" << g_replayDrops
            << " PDR=" << pdr
            << " AvgDelay=" << avgDelay << "s"
            << " Throughput(bps)=" << throughputBps
            << std::endl;
}

int main(int argc, char *argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("simTime", "Simulation time (s)", g_simTime);
  cmd.AddValue("intervalMs", "Packet interval (ms)", g_intervalMs);
  cmd.AddValue("payloadSize", "Payload size (bytes)", g_payloadSize);
  cmd.AddValue("cryptoDelayUsTx", "Simulated TX crypto delay (us)", g_cryptoDelayUsTx);
  cmd.AddValue("cryptoDelayUsRx", "Simulated RX crypto delay (us)", g_cryptoDelayUsRx);
  cmd.AddValue("enableReplayAttack", "Enable replay attack (0/1)", g_enableReplayAttack);
  cmd.AddValue("replayEveryMs", "Replay interval (ms)", g_replayEveryMs);
  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.Parse(argc, argv);

  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  // Keep nodes close so RX is not zero
  MobilityHelper mobility;
  mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=50.0]"),
                                "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=50.0]"));
  mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                            "Bounds", RectangleValue(Rectangle(0, 50, 0, 50)),
                            "Speed", StringValue("ns3::ConstantRandomVariable[Constant=6.0]"),
                            "Distance", DoubleValue(5.0));
  mobility.Install(vehicles);

  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());
  phy.Set("TxPowerStart", DoubleValue(16.0));
  phy.Set("TxPowerEnd", DoubleValue(16.0));

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devices = wifi.Install(phy, mac, vehicles);

  InternetStackHelper internet;
  internet.Install(vehicles);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  ipv4.Assign(devices);

  // Build replay caches
  g_caches.clear();
  g_caches.resize(g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; i++)
    g_caches[i] = std::make_unique<ReplayCache>(5000);

  uint16_t port = 9000;

  // Receiver sockets
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<Socket> recvSocket = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    recvSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
    recvSocket->SetRecvCallback(MakeCallback(&RxSocketReady));
  }

  // Sender socket on node 0 (broadcast for /16)
  Ptr<Socket> sendSocket = Socket::CreateSocket(vehicles.Get(0), UdpSocketFactory::GetTypeId());
  sendSocket->SetAllowBroadcast(true);
  sendSocket->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), port));

  Simulator::Schedule(Seconds(1.0), &SendNewPacket, sendSocket, 0);

  if (g_enableReplayAttack)
    Simulator::Schedule(Seconds(2.0), &ReplayAttackTick, sendSocket);

  Simulator::Schedule(Seconds(g_simTime - 0.001), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();
  return 0;
}
