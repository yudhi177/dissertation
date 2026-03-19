
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"

#include <fstream>
#include <unordered_set>
#include <deque>
#include <vector>
#include <cstring>
#include <memory>
#include <iostream>
#include <algorithm>

using namespace ns3;

// ===========================================================
// secure_v2x.cc (updated)
// Focus:
// - Packet-security scenario (not full integrated framework)
// - Replay protection + optional signature validation
// - Replay attack + signature-corruption attack
// - Cleaner metrics, event logging, and safer socket lifetime
// ===========================================================

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
      const uint64_t old = m_queue.front();
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
  double   txTime;      // seconds
  uint32_t senderId;
  uint32_t sig;         // simple keyed signature
  uint8_t  attackTag;   // 0=normal, 1=replay, 2=sig-corrupt (debug only)
};
#pragma pack(pop)

// ---------------- Global metrics ----------------
static uint64_t g_txCount      = 0;
static uint64_t g_rxCount      = 0;
static uint64_t g_replayDrops  = 0;
static uint64_t g_sigDrops     = 0;
static double   g_delaySum     = 0.0;
static uint64_t g_rxBytes      = 0;

// ---------------- Params ----------------
static uint32_t    g_nVehicles         = 10;
static double      g_simTime           = 20.0;
static uint32_t    g_payloadSize       = 64;
static uint32_t    g_intervalMs        = 100;
static uint32_t    g_cryptoDelayUsTx   = 0;
static uint32_t    g_cryptoDelayUsRx   = 0;
static bool        g_enableReplayCheck = true;
static bool        g_enableSigCheck    = true;
static bool        g_enableReplayAttack = false;
static bool        g_enableSigCorruptAttack = false;
static bool        g_txAllVehicles     = false;
static uint32_t    g_replayEveryMs     = 300;
static uint32_t    g_seed              = 1;
static std::string g_csvOut            = "secure_metrics.csv";
static std::string g_eventsOut         = "secure_events.csv";

// One replay cache per node
static std::vector<std::unique_ptr<ReplayCache>> g_caches;

// Keep sockets alive
static std::vector<Ptr<Socket>> g_recvSockets;
static std::vector<Ptr<Socket>> g_sendSockets;

// Per-sender simple keys
static std::vector<uint32_t> g_keys;

// Store last sent raw bytes for replay attack (sender 0 path)
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

static std::ofstream g_evt;

// ---------------- Helpers ----------------
static void LogEvent(const std::string& e)
{
  if (!g_evt.is_open())
    return;

  g_evt << Simulator::Now().GetSeconds() << "," << e << "\n";
}

static uint32_t SimpleSig(uint32_t senderId, uint64_t nonce)
{
  uint32_t key = 0xA5A5A5A5u;
  if (senderId < g_keys.size())
    key = g_keys[senderId];

  uint64_t x = nonce ^ (uint64_t(key) << 1) ^ (uint64_t(senderId) << 32);
  x ^= (x >> 33);
  x *= 0xff51afd7ed558ccdULL;
  x ^= (x >> 33);
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= (x >> 33);
  return static_cast<uint32_t>(x & 0xffffffffULL);
}

static void ProcessReceived(uint32_t receiverId, MsgHdr hdr, uint32_t pktSize)
{
  // Ignore self-receive (common in broadcast + bound sockets)
  if (receiverId == hdr.senderId)
    return;

  if (receiverId >= g_caches.size())
    return;

  ReplayCache* cache = g_caches.at(receiverId).get();

  if (g_enableReplayCheck)
  {
    if (cache->Seen(hdr.nonce))
    {
      g_replayDrops++;
      LogEvent("DROP_REPLAY rx=" + std::to_string(receiverId) +
               " sender=" + std::to_string(hdr.senderId) +
               " nonce=" + std::to_string(hdr.nonce));
      return;
    }
    cache->Add(hdr.nonce);
  }

  if (g_enableSigCheck)
  {
    const uint32_t expect = SimpleSig(hdr.senderId, hdr.nonce);
    if (expect != hdr.sig)
    {
      g_sigDrops++;
      LogEvent("DROP_SIG rx=" + std::to_string(receiverId) +
               " sender=" + std::to_string(hdr.senderId) +
               " nonce=" + std::to_string(hdr.nonce));
      return;
    }
  }

  double now = Simulator::Now().GetSeconds();
  double delay = now - hdr.txTime;
  if (delay < 0) delay = 0;

  g_rxCount++;
  g_delaySum += delay;
  g_rxBytes += pktSize;

  LogEvent("RX_OK rx=" + std::to_string(receiverId) +
           " sender=" + std::to_string(hdr.senderId) +
           " nonce=" + std::to_string(hdr.nonce));
}

static void RxSocketReady(Ptr<Socket> socket)
{
  const uint32_t receiverId = socket->GetNode()->GetId();

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

static void SendNewPacket(uint32_t senderId)
{
  if (senderId >= g_sendSockets.size())
    return;

  Ptr<Socket> sock = g_sendSockets[senderId];

  MsgHdr hdr{};
  hdr.nonce = (static_cast<uint64_t>(senderId) << 48) ^
              static_cast<uint64_t>(Simulator::Now().GetNanoSeconds());
  hdr.txTime = Simulator::Now().GetSeconds();
  hdr.senderId = senderId;
  hdr.sig = SimpleSig(senderId, hdr.nonce);
  hdr.attackTag = 0;

  // Optional signature-corruption attack path (keep limited to sender0 by default)
  if (g_enableSigCorruptAttack && senderId == 0)
  {
    hdr.sig ^= 0x12345678u;
    hdr.attackTag = 2;
  }

  std::vector<uint8_t> wire(sizeof(MsgHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(MsgHdr));

  for (uint32_t i = 0; i < g_payloadSize; i++)
    wire[sizeof(MsgHdr) + i] = static_cast<uint8_t>(i & 0xFF);

  // Keep last legitimate wire form for replay attack
  if (senderId == 0)
  {
    g_lastWire = wire;
    g_hasLast = true;
  }

  LogEvent("TX sender=" + std::to_string(senderId) +
           " nonce=" + std::to_string(hdr.nonce) +
           " attackTag=" + std::to_string(hdr.attackTag));

  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, sock, wire);
  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendNewPacket, senderId);
}

static void ReplayAttackTick()
{
  if (g_enableReplayAttack && g_hasLast && !g_sendSockets.empty())
  {
    std::vector<uint8_t> wire = g_lastWire;

    MsgHdr hdr{};
    std::memcpy(&hdr, wire.data(), sizeof(MsgHdr));
    hdr.attackTag = 1;
    std::memcpy(wire.data(), &hdr, sizeof(MsgHdr));

    LogEvent("ATTACK_REPLAY sender=0 nonce=" + std::to_string(hdr.nonce));
    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), &DoSendRaw, g_sendSockets[0], wire);
  }

  Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick);
}

static void WriteCsv()
{
  // Broadcast expected receptions: each TX should be received by (nVehicles-1) peers.
  const double expectedRx = (g_nVehicles > 1)
                              ? static_cast<double>(g_txCount) * static_cast<double>(g_nVehicles - 1)
                              : 0.0;
  double pdr = (expectedRx > 0.0) ? static_cast<double>(g_rxCount) / expectedRx : 0.0;
  pdr = std::max(0.0, std::min(1.0, pdr));

  const double avgDelay = (g_rxCount > 0) ? g_delaySum / static_cast<double>(g_rxCount) : 0.0;
  const double throughputBps = (g_simTime > 0.0) ? static_cast<double>(g_rxBytes) * 8.0 / g_simTime : 0.0;

  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f << "nVehicles,simTime,intervalMs,payloadSize,cryptoDelayUsTx,cryptoDelayUsRx,"
       "enableReplayCheck,enableSigCheck,enableReplayAttack,enableSigCorruptAttack,txAllVehicles,replayEveryMs,"
       "txCount,rxCount,replayDrops,sigDrops,pdr,avgDelay_s,throughput_bps\n";
  f << g_nVehicles << "," << g_simTime << "," << g_intervalMs << "," << g_payloadSize << ","
    << g_cryptoDelayUsTx << "," << g_cryptoDelayUsRx << ","
    << (g_enableReplayCheck ? 1 : 0) << "," << (g_enableSigCheck ? 1 : 0) << ","
    << (g_enableReplayAttack ? 1 : 0) << "," << (g_enableSigCorruptAttack ? 1 : 0) << ","
    << (g_txAllVehicles ? 1 : 0) << "," << g_replayEveryMs << ","
    << g_txCount << "," << g_rxCount << "," << g_replayDrops << "," << g_sigDrops << ","
    << pdr << "," << avgDelay << "," << throughputBps << "\n";
  f.close();

  std::cout << "Saved secure metrics to " << g_csvOut << "\n";
  std::cout << "TX=" << g_txCount
            << " RX=" << g_rxCount
            << " ReplayDrops=" << g_replayDrops
            << " SigDrops=" << g_sigDrops
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
  cmd.AddValue("enableReplayCheck", "Enable replay check (0/1)", g_enableReplayCheck);
  cmd.AddValue("enableSigCheck", "Enable signature check (0/1)", g_enableSigCheck);
  cmd.AddValue("enableReplayAttack", "Enable replay attack (0/1)", g_enableReplayAttack);
  cmd.AddValue("enableSigCorruptAttack", "Enable signature-corruption attack (0/1)", g_enableSigCorruptAttack);
  cmd.AddValue("txAllVehicles", "All vehicles transmit (0/1)", g_txAllVehicles);
  cmd.AddValue("replayEveryMs", "Replay interval (ms)", g_replayEveryMs);
  cmd.AddValue("seed", "Deterministic seed", g_seed);
  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.AddValue("eventsOut", "Event log output file", g_eventsOut);
  cmd.Parse(argc, argv);

  SeedManager::SetSeed(g_seed);
  SeedManager::SetRun(g_seed);

  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
  g_evt << "time,event\n";

  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  // Keep nodes close so RX is not near-zero.
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

  // Deterministic simple keys
  g_keys.assign(g_nVehicles, 0);
  Ptr<UniformRandomVariable> uv = CreateObject<UniformRandomVariable>();
  uv->SetStream(g_seed);
  for (uint32_t i = 0; i < g_nVehicles; ++i)
    g_keys[i] = static_cast<uint32_t>(uv->GetInteger(1, 0x7fffffff));

  const uint16_t port = 9000;

  // Keep receiver sockets alive
  g_recvSockets.clear();
  g_recvSockets.resize(g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<Socket> recvSocket = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    recvSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
    recvSocket->SetRecvCallback(MakeCallback(&RxSocketReady));
    g_recvSockets[i] = recvSocket;
  }

  // Sender sockets
  g_sendSockets.clear();
  g_sendSockets.resize(g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; ++i)
  {
    Ptr<Socket> sendSocket = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    sendSocket->SetAllowBroadcast(true);
    sendSocket->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), port));
    g_sendSockets[i] = sendSocket;
  }

  // Start transmissions
  if (g_txAllVehicles)
  {
    for (uint32_t i = 0; i < g_nVehicles; ++i)
      Simulator::Schedule(Seconds(1.0 + 0.001 * i), &SendNewPacket, i);
  }
  else
  {
    Simulator::Schedule(Seconds(1.0), &SendNewPacket, 0);
  }

  if (g_enableReplayAttack)
    Simulator::Schedule(Seconds(2.0), &ReplayAttackTick);

  Simulator::Schedule(Seconds(std::max(0.001, g_simTime - 0.001)), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  if (g_evt.is_open())
    g_evt.close();

  return 0;
}
