#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"

#include <fstream>

using namespace ns3;

static uint64_t g_txCount = 0;
static uint64_t g_rxCount = 0;
static double   g_delaySum = 0.0;
static uint64_t g_rxBytes = 0;

static void RxCallback(Ptr<Socket> socket)
{
  Address from;
  Ptr<Packet> packet = socket->RecvFrom(from);

  double sendTime = 0.0;
  packet->CopyData(reinterpret_cast<uint8_t*>(&sendTime), sizeof(double));

  double now = Simulator::Now().GetSeconds();
  double delay = now - sendTime;

  g_rxCount++;
  g_delaySum += delay;
  g_rxBytes += packet->GetSize();
}

static void SendPacket(Ptr<Socket> socket)
{
  double sendTime = Simulator::Now().GetSeconds();
  Ptr<Packet> packet = Create<Packet>(reinterpret_cast<uint8_t*>(&sendTime), sizeof(double));
  socket->Send(packet);
  g_txCount++;

  Simulator::Schedule(MilliSeconds(100), &SendPacket, socket);
}

int main(int argc, char *argv[])
{
  uint32_t nVehicles = 10;
  double simTime = 20.0;
  std::string csvOut = "baseline_metrics.csv";

  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", nVehicles);
  cmd.AddValue("simTime", "Simulation time (s)", simTime);
  cmd.AddValue("csvOut", "CSV output file", csvOut);
  cmd.Parse(argc, argv);

  NodeContainer vehicles;
  vehicles.Create(nVehicles);

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

  uint16_t port = 9000;

  for (uint32_t i = 0; i < nVehicles; i++)
  {
    Ptr<Socket> recvSocket = Socket::CreateSocket(vehicles.Get(i), UdpSocketFactory::GetTypeId());
    recvSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
    recvSocket->SetRecvCallback(MakeCallback(&RxCallback));
  }

  Ptr<Socket> sendSocket = Socket::CreateSocket(vehicles.Get(0), UdpSocketFactory::GetTypeId());
  sendSocket->SetAllowBroadcast(true);
  sendSocket->Connect(InetSocketAddress(Ipv4Address("255.255.255.255"), port));

  Simulator::Schedule(Seconds(1.0), &SendPacket, sendSocket);

  Simulator::Stop(Seconds(simTime));
  Simulator::Run();

  double avgDelay = (g_rxCount > 0) ? (g_delaySum / g_rxCount) : 0.0;
  double pdr = (g_txCount > 0) ? (double)g_rxCount / (double)g_txCount : 0.0;
  double throughputBps = (simTime > 0) ? (double)g_rxBytes * 8.0 / simTime : 0.0;

  std::ofstream out(csvOut, std::ios::out);
  out << "nVehicles,simTime,txCount,rxCount,pdr,avgDelay_s,throughput_bps\n";
  out << nVehicles << "," << simTime << "," << g_txCount << "," << g_rxCount << ","
      << pdr << "," << avgDelay << "," << throughputBps << "\n";
  out.close();

  std::cout << "Saved metrics to " << csvOut << "\n";
  std::cout << "TX=" << g_txCount << " RX=" << g_rxCount
            << " PDR=" << pdr << " AvgDelay=" << avgDelay
            << " Throughput(bps)=" << throughputBps << "\n";

  Simulator::Destroy();
  return 0;
}
