#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"

#include <fstream>
#include <vector>
#include <cstring>

using namespace ns3;

static uint64_t g_txCount = 0;
static uint64_t g_rxCount = 0;
static double   g_delaySum = 0.0;
static uint64_t g_rxBytes = 0;

static uint32_t g_nVehicles = 10;
static double   g_simTime = 20.0;
static uint32_t g_intervalMs = 100;
static uint32_t g_payloadSize = 64;
static std::string g_csvOut = "baseline_metrics.csv";

// Keep sockets alive for the full simulation.
static std::vector<Ptr<Socket>> g_recvSockets;
static Ptr<Socket> g_sendSocket;

static void RxCallback(Ptr<Socket> socket)
{
  while (true)
  {
    Address from;
    Ptr<Packet> packet = socket->RecvFrom(from);
    if (!packet || packet->GetSize() == 0)
    {
      break;
    }

    if (packet->GetSize() < sizeof(double))
    {
      continue;
    }

    double sendTime = 0.0;
    packet->CopyData(reinterpret_cast<uint8_t*>(&sendTime), sizeof(double));

    double now = Simulator::Now().GetSeconds();
    double delay = now - sendTime;
    if (delay < 0.0)
    {
      delay = 0.0;
    }

    g_rxCount++;
    g_delaySum += delay;
    g_rxBytes += packet->GetSize();
  }
}

static void SendPacket()
{
  std::vector<uint8_t> buf(sizeof(double) + g_payloadSize, 0);
  double sendTime = Simulator::Now().GetSeconds();
  std::memcpy(buf.data(), &sendTime, sizeof(double));

  Ptr<Packet> packet = Create<Packet>(buf.data(), buf.size());
  g_sendSocket->Send(packet);
  g_txCount++;

  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendPacket);
}

int main(int argc, char *argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("simTime", "Simulation time (s)", g_simTime);
  cmd.AddValue("intervalMs", "Packet interval in ms", g_intervalMs);
  cmd.AddValue("payloadSize", "Payload size in bytes after timestamp", g_payloadSize);
  cmd.AddValue("csvOut", "CSV output file", g_csvOut);
  cmd.Parse(argc, argv);

  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  MobilityHelper mobility;
  mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=500.0]"),
                                "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=500.0]"));

  mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                            "Bounds", RectangleValue(Rectangle(0, 500, 0, 500)),
                            "Speed", StringValue("ns3::ConstantRandomVariable[Constant=15.0]"),
                            "Distance", DoubleValue(20.0));
  mobility.Install(vehicles);

  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devices = wifi.Install(phy, mac, vehicles);

  InternetStackHelper internet;
  internet.Install(vehicles);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  ipv4.Assign(devices);

  const uint16_t port = 9000;

  g_recvSockets.resize(g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Ptr<Socket> recvSocket = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    recvSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
    recvSocket->SetRecvCallback(MakeCallback(&RxCallback));
    g_recvSockets[i] = recvSocket;
  }

  g_sendSocket = Socket::CreateSocket(vehicles.Get(0), UdpSocketFactory::GetTypeId());
  g_sendSocket->SetAllowBroadcast(true);
  g_sendSocket->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), port));

  Simulator::Schedule(Seconds(1.0), &SendPacket);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();

  const double expectedRx = (g_txCount > 0 && g_nVehicles > 1)
                              ? (double)g_txCount * double(g_nVehicles - 1)
                              : 0.0;
  double pdrNorm = (expectedRx > 0.0) ? (double)g_rxCount / expectedRx : 0.0;
  if (pdrNorm < 0.0) pdrNorm = 0.0;
  if (pdrNorm > 1.0) pdrNorm = 1.0;

  const double avgDelay = (g_rxCount > 0) ? (g_delaySum / g_rxCount) : 0.0;
  const double throughputBps = (g_simTime > 0.0) ? (double)g_rxBytes * 8.0 / g_simTime : 0.0;

  std::ofstream out(g_csvOut, std::ios::out | std::ios::trunc);
  out << "nVehicles,simTime,intervalMs,payloadSize,txCount,rxCount,expectedRx,pdr_norm,avgDelay_s,throughput_bps\n";
  out << g_nVehicles << "," << g_simTime << "," << g_intervalMs << "," << g_payloadSize << ","
      << g_txCount << "," << g_rxCount << "," << expectedRx << ","
      << pdrNorm << "," << avgDelay << "," << throughputBps << "\n";
  out.close();

  std::cout << "Saved baseline metrics to " << g_csvOut << "\n";
  std::cout << "TX=" << g_txCount
            << " RX=" << g_rxCount
            << " expectedRx=" << expectedRx
            << " PDR_norm=" << pdrNorm
            << " AvgDelay=" << avgDelay
            << " Throughput(bps)=" << throughputBps
            << "\n";

  Simulator::Destroy();
  return 0;
}
