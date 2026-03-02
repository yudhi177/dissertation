#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"
#include "ns3/ns2-mobility-helper.h"

#include <fstream>
#include <vector>
#include <deque>
#include <unordered_set>
#include <memory>
#include <cmath>

using namespace ns3;

/* =========================================================
   GLOBAL PARAMETERS
========================================================= */

static uint32_t g_nVehicles = 30;
static uint32_t g_nRsu = 2;
static double   g_simTime = 60;

static double   g_rsuCoverageRadius = 120.0;

static std::string g_ns2Mobility = "";
static bool g_useNs2Mobility = false;

static std::string g_csvOut = "metrics.csv";
static std::string g_eventsOut = "events.csv";

/* =========================================================
   STATE
========================================================= */

struct VehicleState
{
  int32_t currentRsu = -1;
  bool authInProgress = false;
  double hoStart = 0.0;
};

static std::vector<VehicleState> g_vs;
static std::vector<Vector> g_rsuPos;

static uint64_t g_handoverCount = 0;
static double   g_handoverDelaySum = 0.0;

static std::ofstream g_evt;

/* =========================================================
   HELPERS
========================================================= */

static double Dist2(const Vector& a, const Vector& b)
{
  double dx = a.x - b.x;
  double dy = a.y - b.y;
  return dx*dx + dy*dy;
}

static int32_t SelectServingRsu(const Vector& pos)
{
  double r2 = g_rsuCoverageRadius * g_rsuCoverageRadius;
  double best = 1e18;
  int32_t bestId = -1;

  for (uint32_t r = 0; r < g_rsuPos.size(); r++)
  {
    double d2 = Dist2(pos, g_rsuPos[r]);
    if (d2 <= r2 && d2 < best)
    {
      best = d2;
      bestId = r;
    }
  }
  return bestId;
}

static void LogEvent(const std::string& e)
{
  g_evt << Simulator::Now().GetSeconds() << "," << e << "\n";
}

/* =========================================================
   HANDOVER LOGIC
========================================================= */

static void FinishHandover(uint32_t v, int32_t target)
{
  g_vs[v].currentRsu = target;
  g_vs[v].authInProgress = false;

  double delay = Simulator::Now().GetSeconds() - g_vs[v].hoStart;
  g_handoverDelaySum += delay;

  LogEvent("HO_DONE v=" + std::to_string(v));
}

static void CheckHandover(Ptr<Node> veh)
{
  uint32_t id = veh->GetId();
  if (id >= g_nVehicles) return;

  Vector pos = veh->GetObject<MobilityModel>()->GetPosition();

  int32_t target = SelectServingRsu(pos);
  int32_t current = g_vs[id].currentRsu;

  if (target != current && !g_vs[id].authInProgress)
  {
    g_handoverCount++;
    g_vs[id].authInProgress = true;
    g_vs[id].hoStart = Simulator::Now().GetSeconds();

    LogEvent("HO_START v=" + std::to_string(id));

    Simulator::Schedule(MilliSeconds(20),
                        &FinishHandover, id, target);
  }

  Simulator::Schedule(MilliSeconds(200),
                      &CheckHandover, veh);
}

/* =========================================================
   MAIN
========================================================= */

int main(int argc, char* argv[])
{
  CommandLine cmd;
  cmd.AddValue("simTime", "Simulation time", g_simTime);
  cmd.AddValue("rsuCoverageRadius", "RSU coverage radius", g_rsuCoverageRadius);
  cmd.AddValue("useNs2Mobility", "Use NS2 mobility", g_useNs2Mobility);
  cmd.AddValue("ns2Mobility", "Path to ns2 trace", g_ns2Mobility);
  cmd.AddValue("csvOut", "CSV output", g_csvOut);
  cmd.AddValue("eventsOut", "Events output", g_eventsOut);
  cmd.Parse(argc, argv);

  g_evt.open(g_eventsOut);
  g_evt << "time,event\n";

  NodeContainer vehicles;
  vehicles.Create(g_nVehicles);

  NodeContainer rsus;
  rsus.Create(g_nRsu);

  NodeContainer all;
  all.Add(vehicles);
  all.Add(rsus);

  /* ===== INSTALL INTERNET STACK FIRST (FIX CRASH) ===== */
  InternetStackHelper internet;
  internet.Install(all);

  /* ===== MOBILITY ===== */
  if (g_useNs2Mobility && !g_ns2Mobility.empty())
  {
    NS_LOG_UNCOND("[OK] Using NS2 mobility trace: " << g_ns2Mobility);
    Ns2MobilityHelper ns2(g_ns2Mobility);
    ns2.Install();
  }
  else
  {
    MobilityHelper mob;
    mob.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                         "Bounds", RectangleValue(Rectangle(0,600,0,600)));
    mob.Install(vehicles);
  }

  MobilityHelper rsuMob;
  rsuMob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  rsuMob.Install(rsus);

  /* ===== RSU PLACEMENT (GUARANTEED CROSSING) ===== */
  g_rsuPos.clear();

  g_rsuPos.push_back(Vector(350.0, 0.0, 0.0));
  g_rsuPos.push_back(Vector(550.0, 0.0, 0.0));

  rsus.Get(0)->GetObject<MobilityModel>()
      ->SetPosition(g_rsuPos[0]);

  rsus.Get(1)->GetObject<MobilityModel>()
      ->SetPosition(g_rsuPos[1]);

  NS_LOG_UNCOND("RSU0 at (350,0)");
  NS_LOG_UNCOND("RSU1 at (550,0)");

  g_vs.resize(g_nVehicles);

  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Simulator::Schedule(MilliSeconds(200),
                        &CheckHandover, vehicles.Get(i));
  }

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  /* ===== WRITE CSV ===== */
  std::ofstream f(g_csvOut);
  f << "handoverCount,avgHandoverDelay\n";
  double avg = (g_handoverCount > 0)
               ? g_handoverDelaySum / g_handoverCount
               : 0.0;

  f << g_handoverCount << "," << avg << "\n";
  f.close();

  g_evt.close();
  return 0;
}
