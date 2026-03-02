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
#include <numeric>
#include <algorithm>

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

/* --- Adaptive Trust weights (NEW) --- */
static double g_alpha = 0.40; // behavior
static double g_beta  = 0.25; // mobility
static double g_gamma = 0.25; // ledger consistency
static double g_delta = 0.10; // attack penalty

/* --- Synthetic attack knobs (NEW) --- */
static double g_attackProbPerTick = 0.15; // probability per tick that an attacker triggers a "bad" event
static double g_maliciousFraction = 0.20; // % vehicles marked malicious

/* =========================================================
   STATE
========================================================= */

struct VehicleState
{
  int32_t currentRsu = -1;
  bool authInProgress = false;
  double hoStart = 0.0;

  // NEW: mark malicious
  bool isMalicious = false;
};

static std::vector<VehicleState> g_vs;
static std::vector<Vector> g_rsuPos;

static uint64_t g_handoverCount = 0;
static double   g_handoverDelaySum = 0.0;

static std::ofstream g_evt;

/* --- Ledger / commits (NEW) --- */
static uint64_t g_reportsSent = 0;
static uint64_t g_reportsCommitted = 0;
static uint64_t g_blocks = 0;
static double   g_blockLatencySum = 0.0;
static double   g_blockStart = 0.0;
static uint32_t g_blockIntervalMs = 1000;
static uint32_t g_mineDelayMs = 50;

/* --- Adaptive trust vectors (NEW) --- */
static std::vector<uint64_t> g_txByVeh;       // synthetic "tx"
static std::vector<uint64_t> g_rxOkFromVeh;   // synthetic "ok"
static std::vector<uint64_t> g_sigBadFromVeh; // synthetic bad sig
static std::vector<uint64_t> g_replayFromVeh; // synthetic replay
static std::vector<uint64_t> g_hoCountVeh;    // handovers per veh

static std::vector<double> g_behaviorTrust;
static std::vector<double> g_mobilityStability;
static std::vector<double> g_attackPenalty;
static std::vector<double> g_adaptiveTrust;

static double g_ledgerConsistency = 0.0;

/* RNG */
static Ptr<UniformRandomVariable> g_uv = CreateObject<UniformRandomVariable>();

/* =========================================================
   HELPERS
========================================================= */

static double Clamp01(double x)
{
  if (x < 0.0) return 0.0;
  if (x > 1.0) return 1.0;
  return x;
}

static double SafeDiv(double a, double b)
{
  return (b <= 0.0) ? 0.0 : (a / b);
}

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
      bestId = (int32_t)r;
    }
  }
  return bestId;
}

static void LogEvent(const std::string& e)
{
  if (!g_evt.is_open()) return;
  g_evt << Simulator::Now().GetSeconds() << "," << e << "\n";
}

/* =========================================================
   ADAPTIVE TRUST (NEW)
========================================================= */

static void UpdateAdaptiveTrust()
{
  // ledger consistency: committed / sent
  g_ledgerConsistency = Clamp01(SafeDiv(double(g_reportsCommitted), double(g_reportsSent)));

  double sumAT = 0.0;

  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    double tx = double(g_txByVeh[v]);
    double ok = double(g_rxOkFromVeh[v]);
    double sigbad = double(g_sigBadFromVeh[v]);
    double rpl = double(g_replayFromVeh[v]);

    // behavior trust: ok/tx
    double bt = Clamp01(SafeDiv(ok, std::max(1.0, tx)));

    // mobility stability: fewer handovers -> more stable
    double ms = Clamp01(1.0 / (1.0 + double(g_hoCountVeh[v])));

    // attack penalty: (bad + replay)/tx
    double ap = Clamp01(SafeDiv(sigbad + rpl, std::max(1.0, tx)));

    // adaptive trust
    double at = g_alpha * bt + g_beta * ms + g_gamma * g_ledgerConsistency - g_delta * ap;
    at = Clamp01(at);

    g_behaviorTrust[v] = bt;
    g_mobilityStability[v] = ms;
    g_attackPenalty[v] = ap;
    g_adaptiveTrust[v] = at;

    sumAT += at;
  }

  // log snapshot periodically (once per second)
  double avgAT = (g_nVehicles > 0) ? (sumAT / g_nVehicles) : 0.0;
  LogEvent("ADAPTIVE_TRUST avgAT=" + std::to_string(avgAT) +
           " ledgerC=" + std::to_string(g_ledgerConsistency));

  Simulator::Schedule(Seconds(1.0), &UpdateAdaptiveTrust);
}

/* =========================================================
   SYNTHETIC "DATA" + "ATTACK" EVENTS (NEW)
   (so adaptive trust changes even without WiFi apps)
========================================================= */

static void SyntheticTrafficTick()
{
  // each tick, each vehicle "sends 1 msg"
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    g_txByVeh[v]++;

    // success ratio differs if malicious
    double okProb = g_vs[v].isMalicious ? 0.60 : 0.95;
    if (g_uv->GetValue(0.0, 1.0) < okProb)
      g_rxOkFromVeh[v]++;

    // malicious may generate bad sig/replay events
    if (g_vs[v].isMalicious && g_uv->GetValue(0.0, 1.0) < g_attackProbPerTick)
    {
      if (g_uv->GetValue(0.0, 1.0) < 0.5)
      {
        g_sigBadFromVeh[v]++;
        LogEvent("ATTACK_SIG_BAD v=" + std::to_string(v));
      }
      else
      {
        g_replayFromVeh[v]++;
        LogEvent("ATTACK_REPLAY v=" + std::to_string(v));
      }

      // also pretend a report was sent
      g_reportsSent++;
      LogEvent("REPORT_SENT by=" + std::to_string(v));
    }
  }

  Simulator::Schedule(MilliSeconds(200), &SyntheticTrafficTick);
}

/* =========================================================
   LEDGER COMMIT SIMULATION (NEW)
========================================================= */

static void CommitBlock()
{
  // commit some portion of reports sent since last commit (simulate mining/consensus)
  g_blocks++;
  double lat = Simulator::Now().GetSeconds() - g_blockStart;
  g_blockLatencySum += lat;

  // commit rate depends on mining delay / network health (simple model)
  // here: commit up to 80% of outstanding (not tracked exactly), we just add a bounded amount
  // simplest: commit 1 report per block if there exist any
  if (g_reportsCommitted < g_reportsSent)
  {
    uint64_t remaining = g_reportsSent - g_reportsCommitted;
    uint64_t commitNow = std::min<uint64_t>(remaining, 3); // commit up to 3 per block
    g_reportsCommitted += commitNow;
    LogEvent("BLOCK_COMMIT items=" + std::to_string(commitNow));
  }
  else
  {
    LogEvent("BLOCK_COMMIT items=0");
  }

  g_blockStart = Simulator::Now().GetSeconds();
  Simulator::Schedule(MilliSeconds(g_blockIntervalMs), &CommitBlock);
}

static void StartBlockchain()
{
  g_blockStart = Simulator::Now().GetSeconds();
  Simulator::Schedule(MilliSeconds(g_mineDelayMs), &CommitBlock);
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
    g_hoCountVeh[id]++; // NEW: per-vehicle

    g_vs[id].authInProgress = true;
    g_vs[id].hoStart = Simulator::Now().GetSeconds();

    LogEvent("HO_START v=" + std::to_string(id));

    // you can later replace 20ms with FAST/FULL auth using trust
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
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("nRsu", "Number of RSUs", g_nRsu);
  cmd.AddValue("simTime", "Simulation time", g_simTime);

  cmd.AddValue("rsuCoverageRadius", "RSU coverage radius", g_rsuCoverageRadius);

  cmd.AddValue("useNs2Mobility", "Use NS2 mobility", g_useNs2Mobility);
  cmd.AddValue("ns2Mobility", "Path to ns2 trace", g_ns2Mobility);

  cmd.AddValue("csvOut", "CSV output", g_csvOut);
  cmd.AddValue("eventsOut", "Events output", g_eventsOut);

  // adaptive trust weights
  cmd.AddValue("alpha", "Behavior weight", g_alpha);
  cmd.AddValue("beta", "Mobility weight", g_beta);
  cmd.AddValue("gamma", "Ledger weight", g_gamma);
  cmd.AddValue("delta", "Attack penalty weight", g_delta);

  // synthetic attack params
  cmd.AddValue("attackProbPerTick", "Prob of attack event per tick (malicious only)", g_attackProbPerTick);
  cmd.AddValue("maliciousFraction", "Fraction of malicious vehicles", g_maliciousFraction);

  // ledger params
  cmd.AddValue("blockIntervalMs", "Block interval ms", g_blockIntervalMs);
  cmd.AddValue("mineDelayMs", "Mining delay ms", g_mineDelayMs);

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

  rsus.Get(0)->GetObject<MobilityModel>()->SetPosition(g_rsuPos[0]);
  rsus.Get(1)->GetObject<MobilityModel>()->SetPosition(g_rsuPos[1]);

  NS_LOG_UNCOND("RSU0 at (350,0)");
  NS_LOG_UNCOND("RSU1 at (550,0)");

  /* ===== INIT STATE ===== */
  g_vs.assign(g_nVehicles, VehicleState{});

  // pick malicious vehicles
  uint32_t mcount = (uint32_t)std::round(double(g_nVehicles) * g_maliciousFraction);
  for (uint32_t i = 0; i < g_nVehicles; i++) g_vs[i].isMalicious = false;
  for (uint32_t k = 0; k < mcount; k++)
  {
    uint32_t id = (uint32_t)g_uv->GetInteger(0, (int64_t)g_nVehicles - 1);
    g_vs[id].isMalicious = true;
  }

  // init adaptive trust vectors
  g_txByVeh.assign(g_nVehicles, 0);
  g_rxOkFromVeh.assign(g_nVehicles, 0);
  g_sigBadFromVeh.assign(g_nVehicles, 0);
  g_replayFromVeh.assign(g_nVehicles, 0);
  g_hoCountVeh.assign(g_nVehicles, 0);

  g_behaviorTrust.assign(g_nVehicles, 0.8);
  g_mobilityStability.assign(g_nVehicles, 1.0);
  g_attackPenalty.assign(g_nVehicles, 0.0);
  g_adaptiveTrust.assign(g_nVehicles, 0.8);

  /* ===== START PROCESSES ===== */
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    Simulator::Schedule(MilliSeconds(200),
                        &CheckHandover, vehicles.Get(i));
  }

  // synthetic data + attack events
  Simulator::Schedule(Seconds(0.2), &SyntheticTrafficTick);

  // blockchain commit simulation
  Simulator::Schedule(Seconds(0.0), &StartBlockchain);

  // adaptive trust updates
  Simulator::Schedule(Seconds(1.0), &UpdateAdaptiveTrust);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
  Simulator::Destroy();

  /* ===== WRITE CSV ===== */
  std::ofstream f(g_csvOut);
  f << "handoverCount,avgHandoverDelay,avgAdaptiveTrust,ledgerConsistency,reportsSent,reportsCommitted,blocks,avgBlockLatency\n";

  double avgHo = (g_handoverCount > 0) ? (g_handoverDelaySum / double(g_handoverCount)) : 0.0;

  double avgAT = 0.0;
  if (!g_adaptiveTrust.empty())
    avgAT = std::accumulate(g_adaptiveTrust.begin(), g_adaptiveTrust.end(), 0.0) / g_adaptiveTrust.size();

  double avgBlkLat = (g_blocks > 0) ? (g_blockLatencySum / double(g_blocks)) : 0.0;

  f << g_handoverCount << ","
    << avgHo << ","
    << avgAT << ","
    << g_ledgerConsistency << ","
    << g_reportsSent << ","
    << g_reportsCommitted << ","
    << g_blocks << ","
    << avgBlkLat
    << "\n";

  f.close();

  g_evt.close();
  return 0;
}
