#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"

#include <fstream>
#include <limits>
#include <string>
#include <vector>
#include <algorithm>

using namespace ns3;

struct HandoverEvent
{
  double t;
  uint32_t vehicleId;
  uint32_t from;
  uint32_t to;
  double trust;
  std::string mode;
  double delay_s;
};

struct VehicleState
{
  uint32_t currentRsu = 0;
  bool inHandover = false;
  Time handoverStart = Seconds(0.0);
};

static std::vector<HandoverEvent> g_events;
static std::vector<VehicleState> g_vehicleStates;
static std::vector<double> g_trustScores;

static uint64_t g_handoverCount = 0;
static uint64_t g_fastAuthCount = 0;
static uint64_t g_fullAuthCount = 0;
static double g_handoverDelaySum = 0.0;

static uint32_t FindNearestRsu(Ptr<Node> veh, const NodeContainer& rsus)
{
  Ptr<MobilityModel> vm = veh->GetObject<MobilityModel>();
  double best = std::numeric_limits<double>::infinity();
  uint32_t bestIdx = 0;

  for (uint32_t i = 0; i < rsus.GetN(); i++)
  {
    Ptr<MobilityModel> rm = rsus.Get(i)->GetObject<MobilityModel>();
    double d = vm->GetDistanceFrom(rm);
    if (d < best)
    {
      best = d;
      bestIdx = i;
    }
  }
  return bestIdx;
}

static inline double Clamp01(double x)
{
  return std::max(0.0, std::min(1.0, x));
}

static void TrustDecay(uint32_t vehId, double decayPerSec)
{
  if (vehId >= g_trustScores.size()) return;

  g_trustScores[vehId] = Clamp01(g_trustScores[vehId] - decayPerSec); // called every 1s
  Simulator::Schedule(Seconds(1.0), &TrustDecay, vehId, decayPerSec);
}

// Mock RSU feedback: every feedbackInterval seconds, trust += delta (or negative)
static void RsuFeedback(uint32_t vehId, double delta, double feedbackInterval)
{
  if (vehId >= g_trustScores.size()) return;

  g_trustScores[vehId] = Clamp01(g_trustScores[vehId] + delta);
  Simulator::Schedule(Seconds(feedbackInterval), &RsuFeedback, vehId, delta, feedbackInterval);
}

static void FinishHandover(uint32_t vehId, uint32_t oldIdx, uint32_t newIdx, bool isFast)
{
  if (vehId >= g_vehicleStates.size() || vehId >= g_trustScores.size()) return;

  auto &vs = g_vehicleStates[vehId];
  if (!vs.inHandover) return;

  vs.inHandover = false;
  vs.currentRsu = newIdx;

  g_handoverCount++;
  if (isFast) g_fastAuthCount++;
  else g_fullAuthCount++;

  double hd = (Simulator::Now() - vs.handoverStart).GetSeconds();
  g_handoverDelaySum += hd;

  HandoverEvent e;
  e.t = Simulator::Now().GetSeconds();
  e.vehicleId = vehId;
  e.from = oldIdx;
  e.to = newIdx;
  e.trust = g_trustScores[vehId];
  e.mode = (isFast ? "FAST" : "FULL");
  e.delay_s = hd;
  g_events.push_back(e);

  std::cout << "Handover: veh" << vehId
            << " RSU" << oldIdx << " -> RSU" << newIdx
            << " trust=" << g_trustScores[vehId]
            << " mode=" << e.mode
            << " delay=" << hd << "s\n";
}

static void CheckHandover(Ptr<Node> veh,
                          const NodeContainer& rsus,
                          uint32_t vehId,
                          Time checkInterval,
                          double trustThreshold,
                          Time fullAuthDelay,
                          Time fastAuthDelay)
{
  if (vehId >= g_vehicleStates.size() || vehId >= g_trustScores.size())
  {
    return;
  }

  auto &vs = g_vehicleStates[vehId];
  uint32_t newIdx = FindNearestRsu(veh, rsus);

  if (newIdx != vs.currentRsu && !vs.inHandover)
  {
    vs.inHandover = true;
    vs.handoverStart = Simulator::Now();

    uint32_t oldIdx = vs.currentRsu;
    bool isFast = (g_trustScores[vehId] >= trustThreshold);
    Time decisionDelay = isFast ? fastAuthDelay : fullAuthDelay;

    Simulator::Schedule(decisionDelay, &FinishHandover, vehId, oldIdx, newIdx, isFast);
  }

  Simulator::Schedule(checkInterval, &CheckHandover,
                      veh, rsus, vehId, checkInterval,
                      trustThreshold, fullAuthDelay, fastAuthDelay);
}

int main(int argc, char* argv[])
{
  uint32_t nVehicles = 10;
  double simTime = 80.0;

  // 3 RSUs along x-axis
  double rsuSeparation = 250.0;
  double vehicleSpeed = 12.0;

  double checkMs = 100.0;

  // Auth delays
  double fullAuthMs = 30.0;
  double fastReauthMs = 5.0;

  // Trust model
  double initialTrust = 0.8;
  double trustThreshold = 0.6;
  double trustDecayPerSec = 0.003;     // every second reduce trust
  double feedbackInterval = 10.0;      // seconds
  double feedbackDelta = 0.02;         // trust boost (use negative to penalize)

  std::string summaryCsv = "handover_summary.csv";
  std::string eventsCsv  = "handover_events.csv";

  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", nVehicles);
  cmd.AddValue("simTime", "Simulation time (s)", simTime);
  cmd.AddValue("rsuSeparation", "Distance between RSUs (m)", rsuSeparation);
  cmd.AddValue("vehicleSpeed", "Vehicle speed (m/s)", vehicleSpeed);
  cmd.AddValue("checkMs", "Handover check interval (ms)", checkMs);
  cmd.AddValue("fullAuthMs", "Full authentication delay (ms)", fullAuthMs);
  cmd.AddValue("fastReauthMs", "Fast re-authentication delay (ms)", fastReauthMs);
  cmd.AddValue("initialTrust", "Initial trust score (0-1)", initialTrust);
  cmd.AddValue("trustThreshold", "Trust threshold for fast re-auth", trustThreshold);
  cmd.AddValue("trustDecayPerSec", "Trust decay per second", trustDecayPerSec);
  cmd.AddValue("feedbackInterval", "RSU feedback interval (s)", feedbackInterval);
  cmd.AddValue("feedbackDelta", "RSU feedback trust delta", feedbackDelta);
  cmd.AddValue("summaryCsv", "Summary CSV output", summaryCsv);
  cmd.AddValue("eventsCsv", "Events CSV output", eventsCsv);
  cmd.Parse(argc, argv);

  NodeContainer vehicles;
  vehicles.Create(nVehicles);

  NodeContainer rsus;
  rsus.Create(3);

  MobilityHelper rsuMob;
  rsuMob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  rsuMob.Install(rsus);

  rsus.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 0.0));
  rsus.Get(1)->GetObject<MobilityModel>()->SetPosition(Vector(rsuSeparation, 0.0, 0.0));
  rsus.Get(2)->GetObject<MobilityModel>()->SetPosition(Vector(2 * rsuSeparation, 0.0, 0.0));

  MobilityHelper vehMob;
  vehMob.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
  vehMob.Install(vehicles);

  for (uint32_t i = 0; i < nVehicles; i++)
  {
    double startX = -150.0 - 15.0 * i;
    vehicles.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(startX, 0.0, 0.0));
    vehicles.Get(i)->GetObject<ConstantVelocityMobilityModel>()->SetVelocity(Vector(vehicleSpeed, 0.0, 0.0));
  }

  // Network (not main focus)
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);

  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NodeContainer all;
  all.Add(vehicles);
  all.Add(rsus);

  NetDeviceContainer devices = wifi.Install(phy, mac, all);

  InternetStackHelper internet;
  internet.Install(all);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.3.0.0", "255.255.0.0");
  ipv4.Assign(devices);

  // Initialize per-vehicle state
  g_vehicleStates.assign(nVehicles, VehicleState{});
  g_trustScores.assign(nVehicles, Clamp01(initialTrust));
  for (uint32_t v = 0; v < nVehicles; ++v)
  {
    g_vehicleStates[v].currentRsu = FindNearestRsu(vehicles.Get(v), rsus);
  }

  Time checkInterval = MilliSeconds((uint64_t)checkMs);
  Time fullDelay = MilliSeconds((uint64_t)fullAuthMs);
  Time fastDelay = MilliSeconds((uint64_t)fastReauthMs);

  // Start trust dynamics and handover tracking for every vehicle
  for (uint32_t v = 0; v < nVehicles; ++v)
  {
    Simulator::Schedule(Seconds(1.0), &TrustDecay, v, trustDecayPerSec);
    Simulator::Schedule(Seconds(feedbackInterval), &RsuFeedback, v, feedbackDelta, feedbackInterval);
    Simulator::Schedule(Seconds(1.0 + 0.01 * v), &CheckHandover,
                        vehicles.Get(v), rsus, v,
                        checkInterval, trustThreshold,
                        fullDelay, fastDelay);
  }

  Simulator::Stop(Seconds(simTime));
  Simulator::Run();

  double avgHandoverDelay = (g_handoverCount > 0) ? (g_handoverDelaySum / static_cast<double>(g_handoverCount)) : 0.0;
  double meanFinalTrust = 0.0;
  if (!g_trustScores.empty())
  {
    for (double t : g_trustScores) meanFinalTrust += t;
    meanFinalTrust /= static_cast<double>(g_trustScores.size());
  }

  // Write events CSV
  {
    std::ofstream ev(eventsCsv, std::ios::out);
    ev << "time_s,vehicle_id,from_rsu,to_rsu,trust,mode,delay_s\n";
    for (const auto &e : g_events)
    {
      ev << e.t << "," << e.vehicleId << "," << e.from << "," << e.to << ","
         << e.trust << "," << e.mode << "," << e.delay_s << "\n";
    }
  }

  // Write summary CSV
  {
    std::ofstream out(summaryCsv, std::ios::out);
    out << "nVehicles,simTime,rsuSeparation,vehicleSpeed,checkMs,fullAuthMs,fastReauthMs,initialTrust,trustThreshold,trustDecayPerSec,feedbackInterval,feedbackDelta," \
           "handoverCount,fastAuthCount,fullAuthCount,avgHandoverDelay_s,meanFinalTrust\n";
    out << nVehicles << "," << simTime << "," << rsuSeparation << "," << vehicleSpeed << ","
        << checkMs << "," << fullAuthMs << "," << fastReauthMs << ","
        << initialTrust << "," << trustThreshold << ","
        << trustDecayPerSec << "," << feedbackInterval << "," << feedbackDelta << ","
        << g_handoverCount << "," << g_fastAuthCount << "," << g_fullAuthCount << ","
        << avgHandoverDelay << "," << meanFinalTrust << "\n";
  }

  std::cout << "Saved summary: " << summaryCsv << "\n";
  std::cout << "Saved events : " << eventsCsv << "\n";
  std::cout << "HandoverCount=" << g_handoverCount
            << " FastAuthCount=" << g_fastAuthCount
            << " FullAuthCount=" << g_fullAuthCount
            << " AvgHandoverDelay=" << avgHandoverDelay << "s"
            << " MeanFinalTrust=" << meanFinalTrust << "\n";

  Simulator::Destroy();
  return 0;
}
