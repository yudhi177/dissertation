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
#include <numeric>
#include <set>
#include <sstream>

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
static uint32_t g_seed = 1;

/* --- Trust-gated handover knobs (NEW) --- */
static double   g_trustFastThresh = 0.70;
static double   g_trustMinThresh  = 0.30;
static uint32_t g_fastAuthDelayMs = 20;
static uint32_t g_fullAuthDelayMs = 120;
static uint32_t g_handoverCheckMs = 200;

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
static uint64_t g_fastAuthCount = 0;
static uint64_t g_fullAuthCount = 0;
static uint64_t g_rejectCount = 0;
static uint64_t g_malFast = 0, g_malFull = 0, g_malReject = 0;
static uint64_t g_honFast = 0, g_honFull = 0, g_honReject = 0;

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
  g_blocks++;
  double lat = Simulator::Now().GetSeconds() - g_blockStart;
  g_blockLatencySum += lat;

  uint64_t commitNow = 0;
  if (g_reportsCommitted < g_reportsSent)
  {
    uint64_t remaining = g_reportsSent - g_reportsCommitted;
    commitNow = std::min<uint64_t>(remaining, 3);
    g_reportsCommitted += commitNow;
  }

  std::ostringstream oss;
  oss << "BLOCK_COMMIT items=" << commitNow << " lat=" << lat;
  LogEvent(oss.str());

  Simulator::Schedule(MilliSeconds(g_blockIntervalMs), &StartBlockchain);
}

static void StartBlockchain()
{
  g_blockStart = Simulator::Now().GetSeconds();
  Simulator::Schedule(MilliSeconds(g_mineDelayMs), &CommitBlock);
}

/* =========================================================
   HANDOVER LOGIC
========================================================= */

static void FinishHandover(uint32_t v, int32_t target, bool fast, uint32_t authDelayMs)
{
  g_vs[v].currentRsu = target;
  g_vs[v].authInProgress = false;

  double delay = Simulator::Now().GetSeconds() - g_vs[v].hoStart;
  g_handoverDelaySum += delay;

  if (fast) g_fastAuthCount++;
  else g_fullAuthCount++;

  bool mal = g_vs[v].isMalicious;
  if (fast) { if (mal) g_malFast++; else g_honFast++; }
  else      { if (mal) g_malFull++; else g_honFull++; }

  std::ostringstream oss;
  oss << "HO_DONE v=" << v
      << " to=" << target
      << " mode=" << (fast ? "FAST" : "FULL")
      << " authMs=" << authDelayMs
      << " hoDelay=" << delay;
  LogEvent(oss.str());
}

static void CheckHandover(Ptr<Node> veh)
{
  uint32_t id = veh->GetId();
  if (id >= g_nVehicles)
  {
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, veh);
    return;
  }

  Ptr<MobilityModel> mm = veh->GetObject<MobilityModel>();
  if (!mm)
  {
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, veh);
    return;
  }

  Vector pos = mm->GetPosition();
  int32_t target = SelectServingRsu(pos);
  int32_t current = g_vs[id].currentRsu;

  if (target != -1 && target != current && !g_vs[id].authInProgress)
  {
    const double trust = (id < g_adaptiveTrust.size()) ? g_adaptiveTrust[id] : 0.0;

    if (trust < g_trustMinThresh)
    {
      g_rejectCount++;
      if (g_vs[id].isMalicious) g_malReject++; else g_honReject++;

      std::ostringstream oss;
      oss << "HO_REJECT v=" << id
          << " from=" << current
          << " to=" << target
          << " trust=" << trust;
      LogEvent(oss.str());
    }
    else
    {
      const bool fast = (trust >= g_trustFastThresh);
      const uint32_t authDelayMs = fast ? g_fastAuthDelayMs : g_fullAuthDelayMs;

      g_handoverCount++;
      g_hoCountVeh[id]++;

      g_vs[id].authInProgress = true;
      g_vs[id].hoStart = Simulator::Now().GetSeconds();

      std::ostringstream oss;
      oss << "HO_START v=" << id
          << " from=" << current
          << " to=" << target
          << " trust=" << trust
          << " mode=" << (fast ? "FAST" : "FULL");
      LogEvent(oss.str());

      Simulator::Schedule(MilliSeconds(authDelayMs),
                          &FinishHandover, id, target, fast, authDelayMs);
    }
  }

  Simulator::Schedule(MilliSeconds(g_handoverCheckMs),
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
  cmd.AddValue("seed", "Deterministic seed", g_seed);

  // trust-gated handover params
  cmd.AddValue("trustFastThresh", "Trust threshold for FAST auth", g_trustFastThresh);
  cmd.AddValue("trustMinThresh", "Trust threshold below which handover is rejected", g_trustMinThresh);
  cmd.AddValue("fastAuthDelayMs", "FAST auth delay ms", g_fastAuthDelayMs);
  cmd.AddValue("fullAuthDelayMs", "FULL auth delay ms", g_fullAuthDelayMs);
  cmd.AddValue("handoverCheckMs", "Handover check interval ms", g_handoverCheckMs);

  // ledger params
  cmd.AddValue("blockIntervalMs", "Block interval ms", g_blockIntervalMs);
  cmd.AddValue("mineDelayMs", "Mining delay ms", g_mineDelayMs);

  cmd.Parse(argc, argv);

  SeedManager::SetSeed(g_seed);
  SeedManager::SetRun(g_seed);
  g_uv->SetStream(g_seed);

  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
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

  /* ===== FALLBACK MOBILITY FOR ANY MISSING NODE ===== */
  MobilityHelper fallback;
  fallback.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  for (uint32_t i = 0; i < all.GetN(); ++i)
  {
    Ptr<Node> n = all.Get(i);
    if (n->GetObject<MobilityModel>() == nullptr)
    {
      fallback.Install(n);
      n->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 0.0));
    }
  }

  /* ===== RSU PLACEMENT ===== */
  g_rsuPos.clear();
  if (g_nRsu == 1)
  {
    g_rsuPos.push_back(Vector(450.0, 300.0, 0.0));
  }
  else
  {
    for (uint32_t r = 0; r < g_nRsu; ++r)
    {
      double x = 150.0 + (600.0 * double(r + 1) / double(g_nRsu + 1));
      g_rsuPos.push_back(Vector(x, 300.0, 0.0));
    }
  }

  for (uint32_t r = 0; r < g_nRsu; ++r)
  {
    rsus.Get(r)->GetObject<MobilityModel>()->SetPosition(g_rsuPos[r]);
    NS_LOG_UNCOND("RSU" << r << " at (" << g_rsuPos[r].x << "," << g_rsuPos[r].y << ")");
  }

  /* ===== INIT STATE ===== */
  g_vs.assign(g_nVehicles, VehicleState{});

  // pick malicious vehicles
  uint32_t mcount = (uint32_t)std::round(double(g_nVehicles) * g_maliciousFraction);
  mcount = std::min<uint32_t>(mcount, g_nVehicles);
  for (uint32_t i = 0; i < g_nVehicles; i++) g_vs[i].isMalicious = false;

  std::set<uint32_t> chosen;
  while (chosen.size() < mcount)
  {
    uint32_t id = (uint32_t)g_uv->GetInteger(0, (int64_t)g_nVehicles - 1);
    chosen.insert(id);
  }
  for (uint32_t id : chosen)
    g_vs[id].isMalicious = true;

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
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs),
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

  NS_LOG_UNCOND("[ADAPT] handovers=" << g_handoverCount
                 << " fast=" << g_fastAuthCount
                 << " full=" << g_fullAuthCount
                 << " reject=" << g_rejectCount);
  NS_LOG_UNCOND("[BC] reportsSent=" << g_reportsSent
                 << " reportsCommitted=" << g_reportsCommitted
                 << " blocks=" << g_blocks);

  Simulator::Destroy();

  /* ===== WRITE CSV ===== */
  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f << "nVehicles,nRsu,simTime,rsuCoverageRadius,maliciousFraction,alpha,beta,gamma,delta,trustFastThresh,trustMinThresh,fastAuthDelayMs,fullAuthDelayMs,handoverCheckMs,";
  f << "handoverCount,avgHandoverDelay,fastAuthCount,fullAuthCount,rejectCount,avgAdaptiveTrust,avgBehaviorTrust,avgMobilityStability,avgAttackPenalty,ledgerConsistency,reportsSent,reportsCommitted,blocks,avgBlockLatency,";
  f << "malFast,malFull,malReject,honFast,honFull,honReject\n";

  double avgHo = (g_handoverCount > 0) ? (g_handoverDelaySum / double(g_handoverCount)) : 0.0;

  double avgAT = 0.0;
  if (!g_adaptiveTrust.empty())
    avgAT = std::accumulate(g_adaptiveTrust.begin(), g_adaptiveTrust.end(), 0.0) / g_adaptiveTrust.size();

  double avgBlkLat = (g_blocks > 0) ? (g_blockLatencySum / double(g_blocks)) : 0.0;
  double avgBT = g_behaviorTrust.empty() ? 0.0 : (std::accumulate(g_behaviorTrust.begin(), g_behaviorTrust.end(), 0.0) / g_behaviorTrust.size());
  double avgMS = g_mobilityStability.empty() ? 0.0 : (std::accumulate(g_mobilityStability.begin(), g_mobilityStability.end(), 0.0) / g_mobilityStability.size());
  double avgAP = g_attackPenalty.empty() ? 0.0 : (std::accumulate(g_attackPenalty.begin(), g_attackPenalty.end(), 0.0) / g_attackPenalty.size());

  f << g_nVehicles << ","
    << g_nRsu << ","
    << g_simTime << ","
    << g_rsuCoverageRadius << ","
    << g_maliciousFraction << ","
    << g_alpha << ","
    << g_beta << ","
    << g_gamma << ","
    << g_delta << ","
    << g_trustFastThresh << ","
    << g_trustMinThresh << ","
    << g_fastAuthDelayMs << ","
    << g_fullAuthDelayMs << ","
    << g_handoverCheckMs << ","
    << g_handoverCount << ","
    << avgHo << ","
    << g_fastAuthCount << ","
    << g_fullAuthCount << ","
    << g_rejectCount << ","
    << avgAT << ","
    << avgBT << ","
    << avgMS << ","
    << avgAP << ","
    << g_ledgerConsistency << ","
    << g_reportsSent << ","
    << g_reportsCommitted << ","
    << g_blocks << ","
    << avgBlkLat << ","
    << g_malFast << ","
    << g_malFull << ","
    << g_malReject << ","
    << g_honFast << ","
    << g_honFull << ","
    << g_honReject
    << "\n";

  f.close();

  g_evt.close();
  return 0;
}
