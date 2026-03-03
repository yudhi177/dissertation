#include <iomanip>
// ============================================================
// secure_trust_blockchain_v2x.cc  (CORE UPGRADE v2)
// - Vehicle-only PDR/Delay/Throughput (fix correctness)
// - Event-driven reports based on observed misbehavior (realistic)
// - Trust-weighted ledger updates (report credibility)
// - Malicious vs honest HO decision stats
// - SUMO(NS2) mobility safe: RSU + fallback mobility guaranteed
// ============================================================

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/propagation-module.h"
#include "ns3/applications-module.h"
#include "ns3/ns2-mobility-helper.h"

#include <fstream>
#include <vector>
#include <deque>
#include <unordered_set>
#include <memory>
#include <cstring>
#include <numeric>
#include <algorithm>
#include <cmath>

using namespace ns3;


// PRIVACY_EVENT_LOGGER_BEGIN
#include <fstream>
static std::ofstream* g_eventsPtr = nullptr;

// Writes: <time>,<event_string>
static void PrivacyLogEvent(const std::string& ev)
{
  if (g_eventsPtr && g_eventsPtr->is_open())
  {
    (*g_eventsPtr) << Simulator::Now().GetSeconds() << "," << ev << "\n";
  }
}
// PRIVACY_EVENT_LOGGER_END
/* =======================
   GLOBAL PARAMETERS
======================= */
static uint32_t g_nVehicles = 30;
static uint32_t g_nRsu      = 2;
static double   g_simTime   = 20.0;

static bool     g_useNs2Mobility = false;
static std::string g_ns2Mobility = "";

static std::string g_csvOut    = "metrics.csv";
static std::string g_eventsOut = "events.csv";

// Map bounds (for RSU placement / fallback)
static double g_mapMinX = 0.0;
static double g_mapMaxX = 600.0;
static double g_mapMinY = 0.0;
static double g_mapMaxY = 600.0;

static double   g_rsuCoverageRadius = 300.0;
static uint32_t g_handoverCheckMs   = 200;

// V2V traffic
static uint32_t g_payloadSize = 64;
static uint32_t g_intervalMs  = 100;
static bool     g_txAllVehicles = false; // 0 => only veh0 tx, 1 => all vehicles tx

// Crypto delay simulation
static uint32_t g_cryptoDelayUsTx = 200;
static uint32_t g_cryptoDelayUsRx = 200;

// Security toggles
static bool g_enableReplayCheck = true;
static bool g_enableSigCheck    = true;

// Attacker model
// maliciousRate = fraction of malicious vehicles [0..1]
static double   g_maliciousRate = 0.2;
static uint32_t g_attackSeed    = 1;

// Attack modes:
// 0 none, 1 replay (optional), 2 signature corruption, 3 sybil-spoof (invalid senderId)
static uint32_t g_attackMode = 2;
static bool     g_enableReplayAttack = true;
static uint32_t g_replayEveryMs = 300;
static uint32_t g_sybilBurst = 2; // how many spoof packets per send tick (if mode=3)

// Reporting + blockchain + trust
static bool     g_enableReports    = true;
static bool     g_enableBlockchain = true;
static bool     g_enableTrustGate  = true;

static uint32_t g_reportTriggerK   = 3;      // suspicion threshold
static double   g_reportDeltaBad   = -0.05;  // trust penalty on commit

static uint32_t g_blockIntervalMs  = 1000;
static uint32_t g_mineDelayMs      = 50;


static bool     g_enableAdaptiveMining = true; // adaptive mining on/off
// Trust thresholds for handover
static double   g_trustFastThresh = 0.7;
static double   g_trustMinThresh  = 0.3;
static uint32_t g_fastAuthDelayMs = 20;
static uint32_t g_fullAuthDelayMs = 120;

/* ---- ports ---- */
static const uint16_t g_dataPort   = 9000;
static const uint16_t g_reportPort = 9100;


// PRIVACY_MODULE_V1_BEGIN
/* =========================================================
   PRIVACY MODULE (v1)
   - Pseudonym pool >= 5 per vehicle
   - Timer-based rotation + RSU-triggered rotation
   - On-chain registration (simulated) of pseudonym hash
   - Linkability events (LINK_ATTEMPT / LINK_SUCCESS)
========================================================= */
static bool     g_enablePrivacy       = false;

static bool g_rotateOnHandover = true; // added by fix_privacy_name_mismatch
static uint32_t g_pseudoPoolSize      = 5;
static uint32_t g_pseudoRotateSec     = 5;     // timer rotation
static bool     g_rotateOnRsuChange   = true;  // RSU-triggered rotation

// Linkability model (simple attacker using continuity + mix-zone)
static double   g_linkTimeWindowSec   = 2.0;
static double   g_linkDistThresh      = 25.0;  // meters
static double   g_linkNeighborRadius  = 30.0;  // meters
static uint32_t g_linkMixK            = 3;     // if neighbors >=K => mix-zone => harder to link

struct PseudoState
{
  std::vector<uint64_t> pool;
  uint32_t idx = 0;
  double   lastRotate = 0.0;
};

static std::vector<PseudoState> g_pseudo;
static std::vector<uint64_t>    g_activePseudo;
static std::vector<uint64_t>    g_prevPseudo;
static std::vector<Vector>      g_prevPos;
static std::vector<double>      g_prevTime;

static uint64_t g_pseudoRotations      = 0;
static uint64_t g_pseudoRegistrations  = 0;
static uint64_t g_linkAttempts         = 0;
static uint64_t g_linkSuccess          = 0;
static double   g_linkSuccessExp = 0.0; // expected-success accumulator
// PRIVACY_MODULE_V1_END



/* =======================
   METRICS / STATE
======================= */
// TX
static uint64_t g_txData = 0;

// RX (vehicle-only correctness)
static uint64_t g_rxVehData  = 0;
static uint64_t g_rxRsuData  = 0;
static uint64_t g_rxVehBytes = 0;
static double   g_delayVehSum = 0.0;

// Drops
static uint64_t g_replayDrops = 0;
static uint64_t g_sigDrops    = 0;

// Reports + blockchain
static uint64_t g_reportsSent       = 0; // reports sent by vehicles (triggered)
static uint64_t g_reportsRxAtRsu     = 0;
static uint64_t g_reportsCommitted  = 0;
static uint64_t g_blocks            = 0;
static double   g_blockLatencySum   = 0.0;
static double   g_blockStart        = 0.0;

// Handover
static uint64_t g_handoverCount     = 0;
static uint64_t g_fastAuthCount     = 0;
static uint64_t g_fullAuthCount     = 0;
static uint64_t g_rejectCount       = 0;
static double   g_handoverDelaySum  = 0.0;

// Malicious vs honest HO stats (paper gold)
static uint64_t g_malFast=0, g_malFull=0, g_malReject=0;
static uint64_t g_honFast=0, g_honFull=0, g_honReject=0;

// RSU positions + trust ledger
static std::vector<Vector> g_rsuPos;
static std::vector<double> g_ledgerTrust;     // size = nVehicles
static std::vector<uint32_t> g_keys;          // per vehicle key for signature
static std::vector<bool> g_isMalicious;       // size = nVehicles

static std::ofstream g_evt;

/* =======================
   PACKED HEADERS
======================= */
#pragma pack(push, 1)
struct DataHdr
{
  uint64_t nonce;
  double   txTime;
  uint32_t senderId;   // internal ID (trust engine uses this)
  uint32_t pseudoId;   // transmitted pseudonym (attacker sees this)
  uint32_t sig;
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

/* =======================
   REPLAY CACHE
======================= */
class ReplayCache
{
public:
  explicit ReplayCache(size_t maxSize) : m_maxSize(maxSize) {}
  bool Seen(uint64_t nonce) const { return m_set.find(nonce) != m_set.end(); }

  void Add(uint64_t nonce)
  {
    if (m_set.count(nonce)) return;
    m_q.push_back(nonce);
    m_set.insert(nonce);
    while (m_q.size() > m_maxSize)
    {
      uint64_t old = m_q.front();
      m_q.pop_front();
      m_set.erase(old);
    }
  }

private:
  size_t m_maxSize;
  std::unordered_set<uint64_t> m_set;
  std::deque<uint64_t> m_q;
};

// one cache per node (vehicles+rsus)
static std::vector<std::unique_ptr<ReplayCache>> g_replayCaches;

// last packet bytes for replay attack
static std::vector<uint8_t> g_lastWire;
static bool g_hasLast = false;

/* =======================
   MEMPOOL (reports)
======================= */
struct ReportItem
{
  double t;
  uint32_t reporter;
  uint32_t accused;
  double delta;
};
static std::deque<ReportItem> g_mempool;

/* =======================
   NODES + SOCKETS
======================= */
static NodeContainer g_vehicles;
static NodeContainer g_rsus;

static std::vector<Ptr<Socket>> g_dataRecvSock;
static std::vector<Ptr<Socket>> g_dataSendSock;    // per vehicle sender socket (simplifies txAll)
static Ptr<Socket> g_rsuReportRecvSock;
static std::vector<Ptr<Socket>> g_vehicleReportSock;

static Ipv4Address g_rsu0Addr;

/* =======================
   HANDOVER STATE
======================= */
struct VehicleState
{
  int32_t currentRsu = -1;
  bool authInProgress = false;
  double hoStart = 0.0;
};
static std::vector<VehicleState> g_vs;

/* =======================
   EVENT-DRIVEN REPORTING
   suspicion[v][sender] increments on invalid packets seen by v
======================= */
static std::vector<std::vector<uint16_t>> g_suspicion;

// RNG
static Ptr<UniformRandomVariable> g_uv = CreateObject<UniformRandomVariable>();

/* =======================
   HELPERS
======================= */
static double Clamp01(double x)
{
  if (x < 0.0) return 0.0;
  if (x > 1.0) return 1.0;
  return x;
}

// TRUST_ENGINE_FINAL_V3_BEGIN
/* =========================================================
   TRUST ENGINE (FINAL v3)
   Scope features:
   - Ti = w1*BehaviorConsistency + w2*HistoricalTrust + w3*RSUFeedback
   - Adaptive weights (density-based)
   - Trust decay + false-positive recovery
   - Local trust cache + sync interval control
========================================================= */
static bool     g_enableTrustEngineFinal = false;

// TRUST_STALENESS_V1_BEGIN
/* =========================================================
   Trust staleness control (Dmax) + staleMismatch metric
   - Tracks last-sync time per vehicle (trustAge)
   - FAST allowed only if trustAge <= trustMaxAgeMs
   - staleMismatchCount increments when cached trust differs from ledger trust while stale
========================================================= */
static uint32_t g_trustMaxAgeMs = 1000; // Dmax
static std::vector<uint64_t> g_trustLastSyncMs; // per vehicle
static uint64_t g_staleMismatchCount = 0;
static uint64_t g_staleChecks = 0;

static inline uint64_t NowMs() { return (uint64_t)Simulator::Now().GetMilliSeconds(); }

static inline void TouchTrustSync(uint32_t v)
{
  if (v >= g_trustLastSyncMs.size()) return;
  g_trustLastSyncMs[v] = NowMs();
}

static inline uint32_t TrustAgeMs(uint32_t v)
{
  if (v >= g_trustLastSyncMs.size()) return 0;
  uint64_t now = NowMs();
  uint64_t last = g_trustLastSyncMs[v];
  if (last > now) return 0;
  return (uint32_t)(now - last);
}
// TRUST_STALENESS_V1_END


static void PrintStaleStats()
{
  const double rate = g_staleChecks ? (double)g_staleMismatchCount / (double)g_staleChecks : 0.0;
  std::cout << "[STALE] maxAgeMs=" << g_trustMaxAgeMs
            << " staleChecks=" << g_staleChecks
            << " staleMismatch=" << g_staleMismatchCount
            << " mismatchRate=" << rate
            << std::endl;
}
// Cache/sync controls
static uint32_t g_trustSyncIntervalMs = 1000; // cache TTL / sync interval
static uint32_t g_trustQueryDelayMs   = 20;   // extra delay on cache miss (ms)

// Trust formula weights (base)
static double   g_w1Base = 0.45;     // BehaviorConsistency
static double   g_w2Base = 0.35;     // HistoricalTrust
static double   g_w3Base = 0.20;     // RSUFeedback

// Density thresholds (vehicles/m^2)
static double   g_densityLow  = 0.00005;  // ~10 vehicles / 600x600
static double   g_densityHigh = 0.00025;  // ~80 vehicles / 600x600

// Decay & recovery
static double   g_trustDecayPerSec = 0.002; // decay toward neutral
static double   g_recoveryPerSec   = 0.010; // recover after false-positive window
static double   g_neutralTrust     = 0.50;

// Evidence tracking
static std::vector<uint32_t> g_goodCount;
static std::vector<uint32_t> g_badCount;
static std::vector<double>   g_lastBadTime;

// Components
static std::vector<double> g_histTrust;       // 0..1
static std::vector<double> g_rsuFeedback;     // 0..1
static std::vector<double> g_lastTrustUpdate; // sec
static std::vector<double> g_trustScore;      // final Ti

// Local trust cache
static std::vector<double> g_cacheTrust;
static std::vector<double> g_cacheTime;
static uint64_t g_trustCacheHits __attribute__((unused)) = 0;
static uint64_t g_trustCacheMiss __attribute__((unused)) = 0;

static double CurrentDensity()
{
  // We use default 600x600 if map bounds aren't available here
  double area = 600.0 * 600.0;
  return (area > 1.0) ? (double(g_nVehicles) / area) : 0.0;
}

static void AdaptiveWeights(double& w1, double& w2, double& w3)
{
  double d = CurrentDensity();
  double t = 0.0;
  if (g_densityHigh > g_densityLow)
    t = (d - g_densityLow) / (g_densityHigh - g_densityLow);
  if (t < 0.0) t = 0.0;
  if (t > 1.0) t = 1.0;

  // density↑ => RSU weight↑, behavior weight↓, keep sum=1
  w1 = g_w1Base - 0.10 * t;
  w3 = g_w3Base + 0.15 * t;
  w2 = 1.0 - (w1 + w3);

  if (w1 < 0.05) w1 = 0.05;
  if (w3 < 0.05) w3 = 0.05;
  w2 = 1.0 - (w1 + w3);
  if (w2 < 0.05) w2 = 0.05;

  double s = w1 + w2 + w3;
  w1 /= s; w2 /= s; w3 /= s;
}

static double BehaviorConsistency(uint32_t v)
{
  uint32_t g = g_goodCount[v];
  uint32_t b = g_badCount[v];
  uint32_t tot = g + b;
  if (tot == 0) return g_neutralTrust;
  return double(g) / double(tot);
}

static void TrustApplyDecay(uint32_t v, double now)
{
  double last = g_lastTrustUpdate[v];
  if (last < -1e8) { g_lastTrustUpdate[v] = now; return; }
  double dt = now - last;
  if (dt <= 0.0) return;

  // exponential decay toward neutral
  double k = std::exp(-g_trustDecayPerSec * dt);
  g_histTrust[v]   = g_neutralTrust + (g_histTrust[v]   - g_neutralTrust) * k;
  g_rsuFeedback[v] = g_neutralTrust + (g_rsuFeedback[v] - g_neutralTrust) * k;

  // recovery if quiet window after bad event
  double sinceBad = now - g_lastBadTime[v];
  if (sinceBad > 2.0)
  {
    double up = 1.0 - std::exp(-g_recoveryPerSec * dt);
    g_histTrust[v] = Clamp01(g_histTrust[v] + 0.02 * up);
  }

  g_lastTrustUpdate[v] = now;
}

// BC_CACHE_SYNC_V1_FWD_BEGIN
// Forward declarations (because TrustRecompute() calls these before their definitions)
static double GetTrustScoreCached(const std::string& key, double& outExtraDelayMs, bool& outCacheHit);
static void MaybeCommitTrustUpdate(const std::string& key, double newTrust, double& outExtraDelayMs, bool& outDidUpdate);
// BC_CACHE_SYNC_V1_FWD_END

static void TrustRecompute(uint32_t v)
{
  double now = Simulator::Now().GetSeconds();
  TrustApplyDecay(v, now);

  double w1,w2,w3;
  AdaptiveWeights(w1,w2,w3);

  double bc  = BehaviorConsistency(v);
  double ht  = g_histTrust[v];
  double rsu = g_rsuFeedback[v];

  double Ti = w1*bc + w2*ht + w3*rsu;
  g_trustScore[v] = Clamp01(Ti);

  // "on-chain" (simulated) commit is throttled by bcSyncIntervalMs
  if (v < g_ledgerTrust.size())
  {
    double bcDelayMs = 0.0;
    bool didUpdate = false;
    MaybeCommitTrustUpdate(std::to_string(v), g_trustScore[v], bcDelayMs, didUpdate);
  }
}

static void TrustEvidenceBad(uint32_t sender)
{
  if (!g_enableTrustEngineFinal) return;
  if (sender >= g_nVehicles) return;
  g_badCount[sender]++;
  g_lastBadTime[sender] = Simulator::Now().GetSeconds();
  TrustRecompute(sender);
}

static void ApplyRsuFeedback(uint32_t accused, double delta)
{
  if (g_rsuFeedback.size() < g_nVehicles) return; // safety
  if (!g_enableTrustEngineFinal) return;
  if (accused >= g_nVehicles) return;
  g_rsuFeedback[accused] = Clamp01(g_rsuFeedback[accused] + delta);
  TrustRecompute(accused);
}

// BC_CACHE_SYNC_V1_BEGIN
/* =========================================================
   Blockchain Sync + Local Trust Cache (v1)
   - Uses existing simulated on-chain store: g_ledgerTrust[v]
   - Cache: key=vehicleId string -> trustScore (TTL)
   - Sync interval: throttle on-chain updates
   - Adds measurable overhead metrics (queries/updates + delays)
========================================================= */
#include <unordered_map>

static bool     g_enableBCLocalCache = true;
static uint32_t g_cacheTtlMs = 2000;            // cache freshness window
static uint32_t g_bcSyncIntervalMs = 1000;      // throttle updates to chain
static uint32_t g_bcQueryDelayMs = 12;          // simulated ledger query delay
static uint32_t g_bcUpdateDelayMs = 18;         // simulated ledger update delay

struct TrustCacheEntry
{
  double trust = 1.0;
  double lastFetchS = -1e9;
  bool valid = false;
};

static std::unordered_map<std::string, TrustCacheEntry> g_trustCache;
static std::unordered_map<std::string, double> g_lastBcUpdateS;

static uint64_t g_bcQueries = 0;
static uint64_t g_bcUpdates = 0;
static uint64_t g_cacheHits = 0;
static uint64_t g_cacheMisses = 0;
static double   g_bcQueryDelaySumMs = 0.0;
static double   g_bcUpdateDelaySumMs = 0.0;

static inline double NowS() { return Simulator::Now().GetSeconds(); }

static double OnChainGetTrustScore(const std::string& key)
{
  uint32_t v = 0;
  try { v = (uint32_t)std::stoul(key); } catch (...) { return 0.8; }
  return (v < g_ledgerTrust.size()) ? g_ledgerTrust[v] : 0.8;
}

static void OnChainSetTrustScore(const std::string& key, double trust)
{
  uint32_t v = 0;
  try { v = (uint32_t)std::stoul(key); } catch (...) { return; }
  if (v < g_ledgerTrust.size()) g_ledgerTrust[v] = trust;
    TouchTrustSync(v);
}

static double GetTrustScoreCached(const std::string& key,
                                 double& outExtraDelayMs,
                                 bool& outCacheHit)
{
  outExtraDelayMs = 0.0;
  outCacheHit = false;

  if (!g_enableBCLocalCache)
  {
    g_bcQueries++;
    g_bcQueryDelaySumMs += g_bcQueryDelayMs;
    outExtraDelayMs += g_bcQueryDelayMs;
    return OnChainGetTrustScore(key);
  }

  auto it = g_trustCache.find(key);
  const double now = NowS();
  const double ttlS = double(g_cacheTtlMs) / 1000.0;

  if (it != g_trustCache.end() && it->second.valid && (now - it->second.lastFetchS) <= ttlS)
  {
    g_cacheHits++;
    outCacheHit = true;
    return it->second.trust;
  }

  g_cacheMisses++;
  g_bcQueries++;
  g_bcQueryDelaySumMs += g_bcQueryDelayMs;
  outExtraDelayMs += g_bcQueryDelayMs;

  const double t = OnChainGetTrustScore(key);

  TrustCacheEntry e;
  e.trust = t;
  e.lastFetchS = now;
  e.valid = true;
  g_trustCache[key] = e;

  return t;
}

static void MaybeCommitTrustUpdate(const std::string& key,
                                  double newTrust,
                                  double& outExtraDelayMs,
                                  bool& outDidUpdate)
{
  outExtraDelayMs = 0.0;
  outDidUpdate = false;

  const double now = NowS();
  const double intervalS = double(g_bcSyncIntervalMs) / 1000.0;
  const double last = (g_lastBcUpdateS.count(key) ? g_lastBcUpdateS[key] : -1e9);

  // always keep local cache fresh (off-chain), even if we don't sync yet
  if (g_enableBCLocalCache)
  {
    auto &e = g_trustCache[key];
    e.trust = newTrust;
    e.lastFetchS = now;
    e.valid = true;
  }

  if ((now - last) < intervalS)
    return;

  g_lastBcUpdateS[key] = now;
  g_bcUpdates++;
  g_bcUpdateDelaySumMs += g_bcUpdateDelayMs;
  outExtraDelayMs += g_bcUpdateDelayMs;
  outDidUpdate = true;

  OnChainSetTrustScore(key, newTrust);
}

static void PrintBcCacheStats()
{
  double hitRate = (g_cacheHits + g_cacheMisses) ? (double)g_cacheHits / (double)(g_cacheHits + g_cacheMisses) : 0.0;
  double avgQ = g_bcQueries ? (g_bcQueryDelaySumMs / (double)g_bcQueries) : 0.0;
  double avgU = g_bcUpdates ? (g_bcUpdateDelaySumMs / (double)g_bcUpdates) : 0.0;

  std::cout << "[BC] queries=" << g_bcQueries
            << " updates=" << g_bcUpdates
            << " cacheHits=" << g_cacheHits
            << " cacheMisses=" << g_cacheMisses
            << " hitRate=" << hitRate
            << " avgQms=" << avgQ
            << " avgUms=" << avgU
            << std::endl;
}
// BC_CACHE_SYNC_V1_END


// PRIVACY_PSEUDONYM_V1_BEGIN
/* =========================================================
   PRIVACY (v1): Pseudonym Pool + Rotation + Linkability metric
   - Uses existing globals already in your file:
     g_enablePrivacy, g_pseudoPoolSize, g_pseudoRotateSec,
     g_rotateOnHandover, g_linkTimeWindowSec, g_pseudoRotations,
     g_linkAttempts, g_linkSuccess
   - Adds only the missing pool state + functions (no redefinitions)
========================================================= */
static std::vector<std::vector<std::string>> g_pseudoPool;
static std::vector<uint32_t> g_pseudoIdx;
static std::vector<double>   g_lastRotateS;


static double g_mixRadiusM = 50.0;  // mix-zone radius (meters)
static std::string MakePseudo(uint32_t v, uint32_t k)
{
  return std::to_string(v) + "_P" + std::to_string(k);
}

static const std::string& GetActivePseudo(uint32_t v)
{
  return g_pseudoPool[v][g_pseudoIdx[v] % g_pseudoPool[v].size()];
}


static uint32_t CountVehNeighborsWithinRadius(uint32_t v, double radiusM)
{
  // Assumption: vehicle nodes are node IDs 0..g_nVehicles-1 (true in your setup)
  Ptr<Node> nv = NodeList::GetNode(v);
  if (!nv) return 0;
  Ptr<MobilityModel> mv = nv->GetObject<MobilityModel>();
  if (!mv) return 0;

  Vector pv = mv->GetPosition();
  const double r2 = radiusM * radiusM;
  uint32_t cnt = 0;

  for (uint32_t u = 0; u < g_nVehicles; ++u)
  {
    if (u == v) continue;
    Ptr<Node> nu = NodeList::GetNode(u);
    if (!nu) continue;
    Ptr<MobilityModel> mu = nu->GetObject<MobilityModel>();
    if (!mu) continue;
    Vector pu = mu->GetPosition();
    const double dx = pv.x - pu.x;
    const double dy = pv.y - pu.y;
    if ((dx*dx + dy*dy) <= r2) cnt++;
  }
  return cnt;
}



static void PrivacyRotate(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_pseudoPool.size()) return;
  if (g_pseudoPool[v].empty()) return;

  const double now  = Simulator::Now().GetSeconds();
  const double prev = g_lastRotateS[v];

  const std::string oldP = GetActivePseudo(v);

  g_pseudoIdx[v] = (g_pseudoIdx[v] + 1) % (uint32_t)g_pseudoPool[v].size();
  g_lastRotateS[v] = now;

  const std::string newP = GetActivePseudo(v);
  (void)reason; (void)oldP; (void)newP;

  g_pseudoRotations++;
  PrivacyLogEvent(std::string("PSEUDO_ROTATE v=") + std::to_string(v) + " reason=" + reason);

  // PRIVACY_EVT_BEGIN
  // PRIVACY_EVT_END
  // ---- Linkability V3 (expected success probability) ----
  // Attempt only if rotations are within time window.
  if (prev > -1e8 && (now - prev) <= g_linkTimeWindowSec)
  {
    g_linkAttempts++;

    const uint32_t k = CountVehNeighborsWithinRadius(v, g_mixRadiusM);
    PrivacyLogEvent(std::string("LINK_ATTEMPT v=") + std::to_string(v) + " k=" + std::to_string(k) + " p=" + std::to_string(1.0 / double(k + 1)));
    // Expected attacker success if there are (k+1) plausible candidates
    g_linkSuccessExp += 1.0 / double(k + 1);

    // Keep hard-success metric too (only if no neighbors)
    if (k == 0) g_linkSuccess++;
  }
}
static void PrivacyRotateTimer(uint32_t v)
{
  if (!g_enablePrivacy) return;
  PrivacyRotate(v, "TIMER");
  Simulator::Schedule(Seconds(g_pseudoRotateSec), &PrivacyRotateTimer, v);
}

static void PrivacyInit()
{
  if (!g_enablePrivacy) return;

  g_pseudoPool.assign(g_nVehicles, {});
  g_pseudoIdx.assign(g_nVehicles, 0);
  g_lastRotateS.assign(g_nVehicles, -1e9);

  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    g_pseudoPool[v].reserve(g_pseudoPoolSize);
    for (uint32_t k = 0; k < g_pseudoPoolSize; ++k)
      g_pseudoPool[v].push_back(MakePseudo(v, k));
  }

  for (uint32_t v = 0; v < g_nVehicles; ++v)
    Simulator::Schedule(Seconds(g_pseudoRotateSec), &PrivacyRotateTimer, v);
}

static void PrintPrivacyStats()
{
  const double rate = g_linkAttempts ? (double)g_linkSuccess / (double)g_linkAttempts : 0.0;
  const double expRate = g_linkAttempts ? (g_linkSuccessExp / (double)g_linkAttempts) : 0.0;
  std::cout << "[PRIV] rotations=" << g_pseudoRotations
            << " linkAttempts=" << g_linkAttempts
            << " linkSuccess=" << g_linkSuccess
            << " linkSuccessRate=" << rate << " linkSuccessRateExp=" << expRate
            << std::endl;
}
// PRIVACY_PSEUDONYM_V1_END




// BC_PROBE_V1_BEGIN
/* =========================================================
   BC Probe (v1)
   - Periodically queries trust via GetTrustScoreCached()
   - Makes bcQueries/cacheHitRate measurable even without handovers
========================================================= */
static bool     g_enableBcProbe = false;
static uint32_t g_bcProbeIntervalMs = 200;   // query period per vehicle
static bool     g_bcProbeUsePseudonym = true;

static void BcProbeTick(uint32_t v)
{
  if (!g_enableBcProbe) return;

  double dms = 0.0;
  bool hit = false;

  std::string key = std::to_string(v);
  if (g_bcProbeUsePseudonym && g_enablePrivacy)
  {
    key = GetActivePseudo(v);
  }

  (void)GetTrustScoreCached(key, dms, hit);
  Simulator::Schedule(MilliSeconds(g_bcProbeIntervalMs), &BcProbeTick, v);
}

static void StartBcProbes()
{
  if (!g_enableBcProbe) return;
  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    Simulator::Schedule(MilliSeconds(50 + (v % 10)), &BcProbeTick, v);
  }
}
// BC_PROBE_V1_END
// AUTH_BIND_V1_BEGIN
/* =========================================================
   Authenticated Session Binding (v1) + MITM test + AuthProbe
   - Simulation-friendly binding: tag = H(senderId|ephPub|nonce|tsMs)
   - MITM mode tampers ephPub at receiver => verification fails
   - AuthProbe generates periodic handshake attempts so metrics become non-zero
========================================================= */
static bool g_enableAuthBind = true;
static bool g_enableMitmAttack = false;

static bool     g_enableAuthProbe = false;
static uint32_t g_authProbeIntervalMs = 500;

static uint64_t g_authOk = 0;
static uint64_t g_authFail = 0;
static uint64_t g_authFailMitm = 0;

// SimpleSig: stable 32-bit hash (FNV-1a)
static uint32_t SimpleSig(const std::string& s)
{
  uint32_t h = 2166136261u;
  for (unsigned char c : s)
  {
    h ^= (uint32_t)c;
    h *= 16777619u;
  }
  return h;
}

static uint32_t MakeAuthTag(uint32_t senderId,
                            const std::string& ephPub,
                            uint64_t nonce,
                            uint64_t tsMs)
{
  return SimpleSig(std::to_string(senderId) + "|" + ephPub + "|" +
                   std::to_string(nonce) + "|" + std::to_string(tsMs));
}

static bool VerifyAuthTag(uint32_t senderId,
                          std::string ephPub,
                          uint64_t nonce,
                          uint64_t tsMs,
                          uint32_t recvTag,
                          bool mitmTamper)
{
  if (mitmTamper)
    ephPub += "|MITM";
  return recvTag == MakeAuthTag(senderId, ephPub, nonce, tsMs);
}

static void AuthProbeOnce(uint32_t v)
{
  if (!g_enableAuthProbe) return;

  const uint64_t tsMs = (uint64_t)Simulator::Now().GetMilliSeconds();
  const uint64_t nonce = (uint64_t)(tsMs ^ (v * 2654435761u)); // deterministic-ish
  const std::string ephPub = "E" + std::to_string(v) + "_" + std::to_string(tsMs);

  const uint32_t tag = MakeAuthTag(v, ephPub, nonce, tsMs);

  bool ok = true;
  if (g_enableAuthBind)
    ok = VerifyAuthTag(v, ephPub, nonce, tsMs, tag, g_enableMitmAttack);

  if (ok) g_authOk++;
  else
  {
    g_authFail++;
    if (g_enableMitmAttack) g_authFailMitm++;
  }

  Simulator::Schedule(MilliSeconds(g_authProbeIntervalMs), &AuthProbeOnce, v);
}

static void StartAuthProbes()
{
  if (!g_enableAuthProbe) return;
  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    Simulator::Schedule(MilliSeconds(100 + (v % 10)), &AuthProbeOnce, v);
  }
}

static void PrintAuthStats()
{
  std::cout << "[AUTH] ok=" << g_authOk
            << " fail=" << g_authFail
            << " mitmFail=" << g_authFailMitm
            << std::endl;
}
// AUTH_BIND_V1_END

static double GetTrustForHandover(uint32_t v, uint32_t* extraDelayMs, bool* cacheHit)
{
  uint32_t dummyDelay = 0;
  bool dummyHit = false;

  if (!extraDelayMs) extraDelayMs = &dummyDelay;
  if (!cacheHit) cacheHit = &dummyHit;

  double dms = 0.0;
  bool hit = false;
  const double t = GetTrustScoreCached(std::to_string(v), dms, hit);

  *extraDelayMs += (uint32_t)(dms + 0.5);
  *cacheHit = hit;

  // staleness mismatch check (only meaningful when trust is stale)
  g_staleChecks++;
  if (TrustAgeMs(v) > g_trustMaxAgeMs && v < g_ledgerTrust.size())
  {
    // if returned trust differs from ledger trust by a small epsilon, count mismatch
    if (std::fabs(t - g_ledgerTrust[v]) > 1e-6) g_staleMismatchCount++;
  }

  return t;
}

static void TrustInit()
{
  g_goodCount.assign(g_nVehicles, 0);
  g_badCount.assign(g_nVehicles, 0);
  g_lastBadTime.assign(g_nVehicles, -1e9);

  g_histTrust.assign(g_nVehicles, 0.80);
  g_rsuFeedback.assign(g_nVehicles, 0.80);
  g_lastTrustUpdate.assign(g_nVehicles, -1e9);
  g_trustScore.assign(g_nVehicles, 0.80);

  g_cacheTrust.assign(g_nVehicles, 0.80);
  g_cacheTime.assign(g_nVehicles, -1e9);

  if (g_ledgerTrust.size() != g_nVehicles)
    g_ledgerTrust.assign(g_nVehicles, 0.80);
}
// TRUST_ENGINE_FINAL_V3_END


static void LogEvent(const std::string& e)
{
  if (!g_evt.is_open()) return;
  g_evt << Simulator::Now().GetSeconds() << "," << e << "\n";
}

static double Dist2(const Vector& a, const Vector& b)
{
  double dx = a.x - b.x;
  double dy = a.y - b.y;
  return dx*dx + dy*dy;
}


/* =========================================================
   PRIVACY HELPERS
========================================================= */
static uint64_t PseudoHash64(uint64_t x)
{
  // splitmix64
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  x = x ^ (x >> 31);
  return x;
}

static uint32_t CountNeighbors(uint32_t v, double radius)
{
  if (v >= g_nVehicles) return 0;
  Ptr<MobilityModel> mv = g_vehicles.Get(v)->GetObject<MobilityModel>();
  if (!mv) return 0;
  Vector pv = mv->GetPosition();
  double r2 = radius * radius;
  uint32_t c = 0;
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    if (i == v) continue;
    Ptr<MobilityModel> mi = g_vehicles.Get(i)->GetObject<MobilityModel>();
    if (!mi) continue;
    if (Dist2(pv, mi->GetPosition()) <= r2) c++;
  }
  return c;
}

static void RegisterPseudoOnChain(uint32_t v, uint64_t pseudo)
{
  (void)pseudo;
  g_pseudoRegistrations++;
  LogEvent("PSEUDO_REG v=" + std::to_string(v));
}

static void InitPseudonyms()
{
  g_pseudo.assign(g_nVehicles, PseudoState{});
  g_activePseudo.assign(g_nVehicles, 0ULL);
  g_prevPseudo.assign(g_nVehicles, 0ULL);
  g_prevPos.assign(g_nVehicles, Vector(0,0,0));
  g_prevTime.assign(g_nVehicles, -1e9);

  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    auto &st = g_pseudo[v];
    st.pool.clear();
    for (uint32_t k = 0; k < g_pseudoPoolSize; k++)
    {
      uint64_t pseudo = PseudoHash64((uint64_t(v) << 32) ^ uint64_t(k + 1));
      st.pool.push_back(pseudo);
      RegisterPseudoOnChain(v, pseudo);
    }
    st.idx = 0;
    st.lastRotate = Simulator::Now().GetSeconds();
    g_activePseudo[v] = st.pool.empty() ? 0ULL : st.pool[0];
    
    // baseline for linkability (so 1st rotation yields LINK_ATTEMPT)
    g_prevTime[v] = Simulator::Now().GetSeconds();
    Ptr<MobilityModel> mm = g_vehicles.Get(v)->GetObject<MobilityModel>();
    if (mm) { g_prevPos[v] = mm->GetPosition(); }
    g_prevPseudo[v] = g_activePseudo[v];
LogEvent("PSEUDO_INIT v=" + std::to_string(v));
  }
}

static void EvaluateLinkability(uint32_t v, uint64_t newPseudo, const std::string& reason)
{
  double now = Simulator::Now().GetSeconds();
  if (v >= g_nVehicles) return;

  Ptr<MobilityModel> mv = g_vehicles.Get(v)->GetObject<MobilityModel>();
  if (!mv) return;

  Vector nowPos = mv->GetPosition();
  if (g_prevTime[v] > -1e8)
  {
    g_linkAttempts++;
    double dt = now - g_prevTime[v];
    double dist = std::sqrt(Dist2(nowPos, g_prevPos[v]));
    uint32_t neigh = CountNeighbors(v, g_linkNeighborRadius);

    LogEvent("LINK_ATTEMPT v=" + std::to_string(v) +
             " dt=" + std::to_string(dt) +
             " dist=" + std::to_string(dist) +
             " neigh=" + std::to_string(neigh) +
             " reason=" + reason);

    bool success = (dt <= g_linkTimeWindowSec) && (dist <= g_linkDistThresh) && (neigh < g_linkMixK);
    if (success)
    {
      g_linkSuccess++;
      LogEvent("LINK_SUCCESS v=" + std::to_string(v));
    }
  }

  g_prevTime[v] = now;
  g_prevPos[v] = nowPos;
  g_prevPseudo[v] = newPseudo;
}

static void RotatePseudonym(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  if (v >= g_pseudo.size()) return;

  auto &st = g_pseudo[v];
  if (st.pool.empty()) return;

  st.idx = (st.idx + 1) % st.pool.size();
  uint64_t newPseudo = st.pool[st.idx];

  EvaluateLinkability(v, newPseudo, reason);

  g_activePseudo[v] = newPseudo;
  st.lastRotate = Simulator::Now().GetSeconds();
  g_pseudoRotations++;

  LogEvent("PSEUDO_ROT v=" + std::to_string(v) + " reason=" + reason);
}

static void PseudoTimerTick(uint32_t v)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  if (v >= g_pseudo.size()) return;

  double now = Simulator::Now().GetSeconds();
  if ((now - g_pseudo[v].lastRotate) >= double(g_pseudoRotateSec))
  {
    RotatePseudonym(v, "TIMER");
  }
  Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
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

/* =======================
   SIGNATURE (keyed)
   attacker cannot forge other nodes (no key)
======================= */
// REVOCATION_MODULE_V1_BEGIN
/* =========================================================
   REVOCATION (v1)
   - Minimal on-chain model (simulated): revocation flag
   - Vehicles learn revocation via periodic sync (revokeSyncIntervalMs)
   - Measures propagation delay: REVOKE_ISSUE -> REVOKE_APPLY per node
========================================================= */
static bool     g_enableRevocation = false;
static double   g_revokeTrustThresh = 0.20;         // trust below => revoke
static uint32_t g_revokeSyncIntervalMs = 1000;      // ms
static bool     g_forceRevokeVehicle0 = false;
static double   g_forceRevokeTime = 2.0;            // seconds

static std::vector<uint8_t> g_revokedVeh;           // size nVehicles
static std::vector<uint8_t> g_revokeKnown;          // size all nodes (vehicles+rsu)
static std::vector<double>  g_revokeKnownTime;      // seconds
static double   g_revokeIssueTime = -1e9;

static uint64_t g_revocationsIssued = 0;
static uint64_t g_revocationsApplied = 0;
static uint64_t g_revokeDrops = 0;
static double   g_revPropDelayMax = 0.0;
static double   g_revPropDelaySum = 0.0;

static void IssueRevocation(uint32_t accused, const std::string& reason)
{
  if (!g_enableRevocation) return;
  if (accused >= g_revokedVeh.size()) return;
  if (g_revokedVeh[accused]) return;

  g_revokedVeh[accused] = 1;
  g_revocationsIssued++;

  if (accused == 0 && g_revokeIssueTime < -1e8)
    g_revokeIssueTime = Simulator::Now().GetSeconds();

  LogEvent("REVOKE_ISSUE accused=" + std::to_string(accused) + " reason=" + reason);
}

static void RevocationSyncTick(uint32_t nodeId)
{
  if (!g_enableRevocation) return;
  if (nodeId >= g_revokeKnown.size()) return;

  // Track propagation for accused=0 (attacker0), simple + paper-friendly
  uint32_t accused = 0;

  if (accused < g_revokedVeh.size() && g_revokedVeh[accused] && !g_revokeKnown[nodeId])
  {
    g_revokeKnown[nodeId] = 1;
    double now = Simulator::Now().GetSeconds();
    g_revokeKnownTime[nodeId] = now;
    g_revocationsApplied++;

    double d = (g_revokeIssueTime > -1e8) ? (now - g_revokeIssueTime) : 0.0;
    if (d < 0) d = 0;

    g_revPropDelaySum += d;
    if (d > g_revPropDelayMax) g_revPropDelayMax = d;

    LogEvent("REVOKE_APPLY node=" + std::to_string(nodeId) +
             " accused=" + std::to_string(accused) +
             " delay=" + std::to_string(d));
  }

  Simulator::Schedule(MilliSeconds(g_revokeSyncIntervalMs), &RevocationSyncTick, nodeId);
}

static void RevocationMonitorTick()
{
  if (!g_enableRevocation) return;
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    if (v < g_ledgerTrust.size() && !g_revokedVeh[v] && g_ledgerTrust[v] < g_revokeTrustThresh)
      IssueRevocation(v, "TRUST_BELOW_THRESH");
  }
  Simulator::Schedule(Seconds(0.5), &RevocationMonitorTick);
}
// REVOCATION_MODULE_V1_END


static uint32_t SimpleSig(uint32_t senderId, uint64_t nonce)
{
  uint32_t key = 0xA5A5A5A5;
  if (senderId < g_keys.size()) key = g_keys[senderId];

  uint64_t x = nonce ^ (uint64_t(key) << 1) ^ (uint64_t(senderId) << 32);
  x ^= (x >> 33);
  x *= 0xff51afd7ed558ccdULL;
  x ^= (x >> 33);
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= (x >> 33);
  return uint32_t(x & 0xffffffffULL);
}

/* =======================
   REPORT SENDER (vehicle -> RSU0)
======================= */
static void SendReport(uint32_t reporter, uint32_t accused, double delta)
{
  if (!g_enableReports) return;
  if (reporter >= g_nVehicles || accused >= g_nVehicles) return;

  ReportHdr rh{};
  rh.t = Simulator::Now().GetSeconds();
  rh.reporterId = reporter;
  rh.accusedId  = accused;
  rh.delta      = (float)delta;

  Ptr<Packet> pkt = Create<Packet>((uint8_t*)&rh, sizeof(rh));
  g_vehicleReportSock[reporter]->Send(pkt);
  g_reportsSent++;

  LogEvent("REPORT_SENT by=" + std::to_string(reporter) +
           " about=" + std::to_string(accused) +
           " delta=" + std::to_string(delta));
}

/* =======================
   RX REPORT AT RSU0
======================= */
static void RxReportAtRsu(Ptr<Socket> sock)
{
  while (true)
  {
    Address from;
    Ptr<Packet> pkt = sock->RecvFrom(from);
    if (!pkt || pkt->GetSize() == 0) break;
    if (pkt->GetSize() < sizeof(ReportHdr)) continue;

    ReportHdr rh{};
    pkt->CopyData((uint8_t*)&rh, sizeof(rh));

    g_reportsRxAtRsu++;
    g_mempool.push_back({rh.t, rh.reporterId, rh.accusedId, (double)rh.delta});

    LogEvent("REPORT_RX_RSU by=" + std::to_string(rh.reporterId) +
             " about=" + std::to_string(rh.accusedId) +
             " delta=" + std::to_string((double)rh.delta));
  }
}

/* =======================
   BLOCKCHAIN COMMIT
======================= */
static void StartBlockchain();

static void CommitNow()
{
  if (!g_enableBlockchain)
    return;

  // items waiting at commit time
  uint32_t items = (uint32_t)g_mempool.size();

  for (auto &it : g_mempool)
  {
    if (it.accused < g_ledgerTrust.size())
    {
      ApplyRsuFeedback(it.accused, it.delta);
      g_reportsCommitted++;
    }
  }
  g_mempool.clear();

  g_blocks++;

  double lat = Simulator::Now().GetSeconds() - g_blockStart;
  g_blockLatencySum += lat;

  LogEvent("BLOCK_COMMIT block=" + std::to_string(g_blocks) +
           " items=" + std::to_string(items) +
           " lat=" + std::to_string(lat));

  // Adaptive next scheduling: more backlog -> schedule sooner
  uint32_t nextInterval = g_blockIntervalMs;
  if (g_enableAdaptiveMining)
  {
    uint32_t denom = 1u + (items / 5u);
    if (denom > 10u) denom = 10u;
    nextInterval = std::max<uint32_t>(200u, g_blockIntervalMs / denom);
  }

  Simulator::Schedule(MilliSeconds(nextInterval), &StartBlockchain);

  // Revocation init + scheduling
  if (g_enableRevocation) {
    g_revokedVeh.assign(g_nVehicles, 0);
    g_revokeKnown.assign(NodeList::GetNNodes(), 0);
    g_revokeKnownTime.assign(NodeList::GetNNodes(), -1e9);
    Simulator::Schedule(Seconds(0.6), &RevocationMonitorTick);
    for (uint32_t i = 0; i < NodeList::GetNNodes(); i++)
      Simulator::Schedule(MilliSeconds(g_revokeSyncIntervalMs), &RevocationSyncTick, i);
    if (g_forceRevokeVehicle0)
      Simulator::Schedule(Seconds(g_forceRevokeTime), &IssueRevocation, 0, std::string("FORCED"));
  }
}

static void StartBlockchain()
{
  if (!g_enableBlockchain)
    return;

  uint32_t items = (uint32_t)g_mempool.size();

  // Adaptive skip: if empty, don't mine useless blocks
  if (g_enableAdaptiveMining && items == 0)
  {
    LogEvent("BLOCK_SKIP_EMPTY");
    Simulator::Schedule(MilliSeconds(g_blockIntervalMs), &StartBlockchain);
    return;
  }

  g_blockStart = Simulator::Now().GetSeconds();

  // Adaptive mining delay: more backlog -> mine faster
  uint32_t mineDelay = g_mineDelayMs;
  if (g_enableAdaptiveMining)
  {
    uint32_t denom = 1u + (items / 5u);
    if (denom > 10u) denom = 10u;
    mineDelay = std::max<uint32_t>(5u, g_mineDelayMs / denom);
  }

  Simulator::Schedule(MilliSeconds(mineDelay), &CommitNow);
}
/* =======================
   EVENT-DRIVEN REPORT TRIGGER
======================= */
static void TriggerSuspicion(uint32_t receiverId, uint32_t senderId, const char* reason)
{
  if (!g_enableReports) return;
  if (receiverId >= g_nVehicles) return; // only vehicles report
  if (senderId >= g_nVehicles) return;
  if (receiverId == senderId) return;

  auto &c = g_suspicion[receiverId][senderId];
  c++;

  if (c >= g_reportTriggerK)
  {
    c = 0;
    SendReport(receiverId, senderId, g_reportDeltaBad);
    LogEvent(std::string("REPORT_TRIGGER reason=") + reason +
             " reporter=" + std::to_string(receiverId) +
             " accused=" + std::to_string(senderId));
  }
}

/* =======================
   PROCESS DATA (after RX delay)
======================= */
static void ProcessData(uint32_t receiverId, DataHdr hdr, uint32_t pktSize)
{
  // Revocation drop (vehicle-id based; keep privacy OFF in revoke experiments)
  if (g_enableRevocation && hdr.senderId < g_revokedVeh.size() && g_revokedVeh[hdr.senderId])
  {
    g_revokeDrops++;
    LogEvent("DATA_DROP_REVOKED rx=" + std::to_string(receiverId) +
             " sender=" + std::to_string(hdr.senderId));
    return;
  }


  // ignore invalid senderIds for verification but still can count as suspicious if within vehicle range
  bool senderKnown = (hdr.senderId < g_nVehicles);

  ReplayCache* cache = g_replayCaches.at(receiverId).get();

  if (g_enableReplayCheck)
  {
    if (cache->Seen(hdr.nonce))
    {
      g_replayDrops++;
      LogEvent("DATA_DROP_REPLAY rx=" + std::to_string(receiverId) +
               " sender=" + std::to_string(hdr.senderId));
      if (senderKnown) TriggerSuspicion(receiverId, hdr.senderId, "REPLAY");
      TrustEvidenceBad(hdr.senderId);
    return;
    }
    cache->Add(hdr.nonce);
  }

  if (g_enableSigCheck)
  {
    uint32_t expect = SimpleSig(hdr.senderId, hdr.nonce);
    if (expect != hdr.sig)
    {
      g_sigDrops++;
      LogEvent("DATA_DROP_SIG rx=" + std::to_string(receiverId) +
               " sender=" + std::to_string(hdr.senderId));
      if (senderKnown) TriggerSuspicion(receiverId, hdr.senderId, "SIG");
      TrustEvidenceBad(hdr.senderId);
    return;
    }
  }

  // count only vehicle receptions excluding self for correct PDR_norm
  if (receiverId < g_nVehicles && receiverId != hdr.senderId)
  {
    double now = Simulator::Now().GetSeconds();
    double d = now - hdr.txTime;
    if (d < 0) d = 0;

    g_rxVehData++;
    g_delayVehSum += d;
    g_rxVehBytes += pktSize;
  }
  else
  {
    g_rxRsuData++;
  }
}

/* =======================
   RX CALLBACK
======================= */
static void RxDataReady(Ptr<Socket> socket)
{
  uint32_t rid = socket->GetNode()->GetId();

  while (true)
  {
    Address from;
    Ptr<Packet> pkt = socket->RecvFrom(from);
    if (!pkt || pkt->GetSize() == 0) break;
    if (pkt->GetSize() < sizeof(DataHdr)) continue;

    DataHdr hdr{};
    pkt->CopyData((uint8_t*)&hdr, sizeof(hdr));

    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsRx),
                        &ProcessData, rid, hdr, pkt->GetSize());
  }
}

/* =======================
   SEND DATA (one vehicle)
======================= */
static void SendNewPacket(uint32_t senderId)
{
  Ptr<Socket> sock = g_dataSendSock[senderId];

  DataHdr hdr{};
  hdr.nonce    = Simulator::Now().GetNanoSeconds() ^ (uint64_t(senderId) << 32);
  hdr.txTime   = Simulator::Now().GetSeconds();
  hdr.senderId = senderId;
  
  hdr.pseudoId = (g_enablePrivacy && senderId < g_activePseudo.size()) ? uint32_t(g_activePseudo[senderId] & 0xffffffffULL) : senderId;
  if (g_enablePrivacy) { LogEvent("PSEUDO_USE v=" + std::to_string(senderId) + " pseudo=" + std::to_string(hdr.pseudoId)); }
hdr.sig      = SimpleSig(senderId, hdr.nonce);

  // apply attacker behavior for malicious nodes
  if (senderId < g_nVehicles && g_isMalicious[senderId])
  {
    if (g_attackMode == 2)
    {
      // signature corruption
      hdr.sig ^= 0x12345678;
    }
  }

  std::vector<uint8_t> wire(sizeof(DataHdr) + g_payloadSize, 0);
  std::memcpy(wire.data(), &hdr, sizeof(DataHdr));

  Ptr<Packet> p = Create<Packet>(wire.data(), wire.size());

  // store for replay
  if (senderId == 0)
  {
    g_lastWire = wire;
    g_hasLast = true;
  }

  g_txData++;

  Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), [sock, p]() {
    sock->Send(p);
  });

  // Sybil spoof burst: send a few packets with spoofed senderId (will fail keyed sig)
  if (senderId < g_nVehicles && g_isMalicious[senderId] && g_attackMode == 3)
  {
    for (uint32_t k = 0; k < g_sybilBurst; k++)
    {
      DataHdr sh = hdr;
      sh.senderId = (senderId + 1 + k) % g_nVehicles; // spoof another real id
      sh.sig = hdr.sig; // wrong key => invalid
      std::vector<uint8_t> w2(sizeof(DataHdr) + g_payloadSize, 0);
      std::memcpy(w2.data(), &sh, sizeof(DataHdr));
      Ptr<Packet> p2 = Create<Packet>(w2.data(), w2.size());
      g_txData++;
      Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), [sock, p2]() {
        sock->Send(p2);
      });
    }
  }

  Simulator::Schedule(MilliSeconds(g_intervalMs), &SendNewPacket, senderId);
}

/* =======================
   REPLAY ATTACK (sender0)
======================= */
static void ReplayAttackTick()
{
  if (!g_enableReplayAttack) return;

  // only do replay if vehicle0 is malicious AND mode allows it
  if (g_isMalicious.size() > 0 && !g_isMalicious[0]) {
    Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick);
    return;
  }

  if (g_hasLast && !g_lastWire.empty())
  {
    Ptr<Socket> sock = g_dataSendSock[0];
    Ptr<Packet> p = Create<Packet>(g_lastWire.data(), g_lastWire.size());
    Simulator::Schedule(MicroSeconds(g_cryptoDelayUsTx), [sock, p]() {
      sock->Send(p);
    });
  }
  Simulator::Schedule(MilliSeconds(g_replayEveryMs), &ReplayAttackTick);
}

/* =======================
   TRUST-BASED HANDOVER
======================= */
static void FinishHandover(uint32_t v, int32_t target, bool fast, uint32_t authDelayMs)
{
  g_vs[v].currentRsu = target;
  g_vs[v].authInProgress = false;

  double delay = Simulator::Now().GetSeconds() - g_vs[v].hoStart;
  g_handoverDelaySum += delay;

  if (fast) g_fastAuthCount++;
  else g_fullAuthCount++;

  bool mal = (v < g_isMalicious.size()) ? g_isMalicious[v] : false;
  if (fast) { if (mal) g_malFast++; else g_honFast++; }
  else      { if (mal) g_malFull++; else g_honFull++; }

  LogEvent("HO_DONE v=" + std::to_string(v) +

" to=" + std::to_string(target) +
           " mode=" + std::string(fast ? "FAST" : "FULL") +
           " authMs=" + std::to_string(authDelayMs) +
           " hoDelay=" + std::to_string(delay));

// PRIVACY_HO_ROTATE_HOOK_BEGIN
  // Rotate pseudonym on handover completion (privacy boost at RSU boundary)
  if (g_enablePrivacy && g_rotateOnHandover)
  {
    PrivacyRotate(v, "HO_DONE");
  }
// PRIVACY_HO_ROTATE_HOOK_END
}

static void CheckHandover(Ptr<Node> veh)
{
  if (!g_enableTrustGate)
  {
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, veh);
    return;
  }

  uint32_t id = veh->GetId();
  if (id >= g_nVehicles)
  {
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, veh);
    return;
  }

  Vector pos = veh->GetObject<MobilityModel>()->GetPosition();
  int32_t target  = SelectServingRsu(pos);
  int32_t current = g_vs[id].currentRsu;

  if (target != -1 && target != current && !g_vs[id].authInProgress)
  {
    uint32_t extraTrustDelayMs = 0; bool cacheHit = true;
  double trust = GetTrustForHandover(id, &extraTrustDelayMs, &cacheHit);
if (trust < g_trustMinThresh)
    {
      g_rejectCount++;
      bool mal = g_isMalicious[id];
      if (mal) g_malReject++; else g_honReject++;

      LogEvent("HO_REJECT v=" + std::to_string(id) +
               " from=" + std::to_string(current) +
               " to=" + std::to_string(target) +
               " trust=" + std::to_string(trust));
    }
    else
    {
      bool fast = ((trust >= g_trustFastThresh && TrustAgeMs(id) <= g_trustMaxAgeMs));
      uint32_t authDelay = fast ? g_fastAuthDelayMs : g_fullAuthDelayMs;

      g_handoverCount++;
      g_vs[id].authInProgress = true;
      g_vs[id].hoStart = Simulator::Now().GetSeconds();

      LogEvent("HO_START v=" + std::to_string(id) +
               " from=" + std::to_string(current) +
               " to=" + std::to_string(target) +
               " trust=" + std::to_string(trust) +
               " mode=" + std::string(fast ? "FAST" : "FULL"));

      Simulator::Schedule(MilliSeconds(authDelay),
                          &FinishHandover, id, target, fast, authDelay);
    }
  }

  Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, veh);
}

/* =======================
   WRITE CSV
======================= */
static void WriteCsv()
{
  double expectedRx = (g_txData > 0 && g_nVehicles > 1)
                      ? (double(g_txData) * double(g_nVehicles - 1))
                      : 0.0;

  double pdr_norm = (expectedRx > 0.0) ? (double(g_rxVehData) / expectedRx) : 0.0;
  pdr_norm = std::max(0.0, std::min(1.0, pdr_norm));

  double avgDelay = (g_rxVehData > 0) ? (g_delayVehSum / double(g_rxVehData)) : 0.0;
  double thr_bps  = (g_simTime > 0) ? (double(g_rxVehBytes) * 8.0 / g_simTime) : 0.0;

  double avgTrust = 0.0;
  if (!g_ledgerTrust.empty())
    avgTrust = std::accumulate(g_ledgerTrust.begin(), g_ledgerTrust.end(), 0.0) / g_ledgerTrust.size();

  double avgBlockLat = (g_blocks > 0) ? (g_blockLatencySum / double(g_blocks)) : 0.0;
  double avgHoDelay  = (g_handoverCount > 0) ? (g_handoverDelaySum / double(g_handoverCount)) : 0.0;

  std::ofstream f(g_csvOut, std::ios::out | std::ios::trunc);
  f <<
    "nVehicles,nRsu,simTime,rsuCoverageRadius,intervalMs,payloadSize,cryptoDelayUsTx,cryptoDelayUsRx,txAllVehicles,"
    "enableReplayCheck,enableSigCheck,enableReports,enableBlockchain,enableTrustGate,attackMode,maliciousRate,"
    "txData,rxVehData,rxRsuData,expectedRx,pdr_norm,avgDelay_s,throughput_bps,"
    "replayDrops,sigDrops,reportsSent,reportsRxAtRsu,blocks,reportsCommitted,avgBlockLatency_s,avgLedgerTrust,"
    "handoverCount,avgHandoverDelay_s,fastAuthCount,fullAuthCount,rejectCount,trustFastThresh,trustMinThresh,fastAuthDelayMs,fullAuthDelayMs,"
    "malFast,malFull,malReject,honFast,honFull,honReject\n";

  f <<
    g_nVehicles << "," << g_nRsu << "," << g_simTime << "," << g_rsuCoverageRadius << ","
    << g_intervalMs << "," << g_payloadSize << ","
    << g_cryptoDelayUsTx << "," << g_cryptoDelayUsRx << ","
    << (g_txAllVehicles ? 1 : 0) << ","
    << (g_enableReplayCheck ? 1 : 0) << "," << (g_enableSigCheck ? 1 : 0) << ","
    << (g_enableReports ? 1 : 0) << "," << (g_enableBlockchain ? 1 : 0) << "," << (g_enableTrustGate ? 1 : 0) << ","
    << g_attackMode << "," << g_maliciousRate << ","
    << g_txData << "," << g_rxVehData << "," << g_rxRsuData << "," << expectedRx << ","
    << pdr_norm << "," << avgDelay << "," << thr_bps << ","
    << g_replayDrops << "," << g_sigDrops << ","
    << g_reportsSent << "," << g_reportsRxAtRsu << ","
    << g_blocks << "," << g_reportsCommitted << "," << avgBlockLat << "," << avgTrust << ","
    << g_handoverCount << "," << avgHoDelay << ","
    << g_fastAuthCount << "," << g_fullAuthCount << "," << g_rejectCount << ","
    << g_trustFastThresh << "," << g_trustMinThresh << ","
    << g_fastAuthDelayMs << "," << g_fullAuthDelayMs << ","
    << g_malFast << "," << g_malFull << "," << g_malReject << ","
    << g_honFast << "," << g_honFull << "," << g_honReject
    << "\n";

  f.close();
}

/* =======================
   MAIN
======================= */
int main(int argc, char* argv[])
{
  CommandLine cmd;
  cmd.AddValue("nVehicles", "Number of vehicles", g_nVehicles);
  cmd.AddValue("nRsu", "Number of RSUs", g_nRsu);
  cmd.AddValue("simTime", "Simulation time", g_simTime);

  cmd.AddValue("useNs2Mobility", "Use NS2 mobility", g_useNs2Mobility);
  cmd.AddValue("ns2Mobility", "Path to ns2 trace", g_ns2Mobility);

  cmd.AddValue("mapMinX","Map min X", g_mapMinX);
  cmd.AddValue("mapMaxX","Map max X", g_mapMaxX);
  cmd.AddValue("mapMinY","Map min Y", g_mapMinY);
  cmd.AddValue("mapMaxY","Map max Y", g_mapMaxY);

  cmd.AddValue("rsuCoverageRadius","RSU coverage radius", g_rsuCoverageRadius);
  cmd.AddValue("handoverCheckMs","Handover check interval", g_handoverCheckMs);

  cmd.AddValue("payloadSize","Payload size bytes", g_payloadSize);
  cmd.AddValue("intervalMs","Packet interval ms", g_intervalMs);
  cmd.AddValue("txAllVehicles","All vehicles transmit 0/1", g_txAllVehicles);

  cmd.AddValue("cryptoDelayUsTx","TX crypto delay us", g_cryptoDelayUsTx);
  cmd.AddValue("cryptoDelayUsRx","RX crypto delay us", g_cryptoDelayUsRx);

  cmd.AddValue("enableReplayCheck","Enable replay check 0/1", g_enableReplayCheck);
  cmd.AddValue("enableSigCheck","Enable signature check 0/1", g_enableSigCheck);

  cmd.AddValue("maliciousRate","Fraction of malicious vehicles", g_maliciousRate);
  cmd.AddValue("attackSeed","Seed for malicious set", g_attackSeed);
  cmd.AddValue("attackMode","0 none, 1 replay, 2 sig-corrupt, 3 sybil", g_attackMode);

  cmd.AddValue("enableReplayAttack","Enable replay sender0 0/1", g_enableReplayAttack);
  cmd.AddValue("replayEveryMs","Replay interval", g_replayEveryMs);
  cmd.AddValue("sybilBurst","Sybil spoof burst", g_sybilBurst);

  cmd.AddValue("enableReports","Enable reports 0/1", g_enableReports);
  cmd.AddValue("reportTriggerK","Suspicion threshold K", g_reportTriggerK);
  cmd.AddValue("reportDeltaBad","Trust delta for bad behavior", g_reportDeltaBad);

  cmd.AddValue("enableBlockchain","Enable blockchain commit 0/1", g_enableBlockchain);
  cmd.AddValue("blockIntervalMs","Block interval ms", g_blockIntervalMs);
  cmd.AddValue("mineDelayMs","Mining delay ms", g_mineDelayMs);

  
  cmd.AddValue("enableAdaptiveMining", "Adaptive mining on/off", g_enableAdaptiveMining);
cmd.AddValue("enableTrustGate","Enable trust-gated handover 0/1", g_enableTrustGate);
  cmd.AddValue("trustFastThresh","FAST threshold", g_trustFastThresh);
  cmd.AddValue("trustMinThresh","MIN threshold", g_trustMinThresh);
  cmd.AddValue("fastAuthDelayMs","FAST auth delay ms", g_fastAuthDelayMs);
  cmd.AddValue("fullAuthDelayMs","FULL auth delay ms", g_fullAuthDelayMs);

  cmd.AddValue("csvOut","CSV output", g_csvOut);
  cmd.AddValue("eventsOut","Events output", g_eventsOut);
  cmd.AddValue("pseudoRotateSec", "Timer-based pseudonym rotation sec", g_pseudoRotateSec);
  cmd.AddValue("rotateOnRsuChange", "Rotate pseudonym on RSU change 0/1", g_rotateOnRsuChange);
cmd.AddValue("enableTrustEngineFinal", "Enable Trust Engine FINAL v2 0/1", g_enableTrustEngineFinal);
  cmd.AddValue("trustSyncIntervalMs", "Trust cache TTL / sync interval ms", g_trustSyncIntervalMs);
  cmd.AddValue("trustQueryDelayMs", "Extra delay on trust cache miss (ms)", g_trustQueryDelayMs);
  cmd.AddValue("trustMaxAgeMs", "Max allowed trust age for FAST auth (ms)", g_trustMaxAgeMs);
  cmd.AddValue("trustDecayPerSec", "Trust decay per second", g_trustDecayPerSec);
  cmd.AddValue("recoveryPerSec", "False-positive recovery per second", g_recoveryPerSec);
  cmd.AddValue("w1Base", "Base weight BehaviorConsistency", g_w1Base);
  cmd.AddValue("w2Base", "Base weight HistoricalTrust", g_w2Base);
  cmd.AddValue("w3Base", "Base weight RSUFeedback", g_w3Base);
  cmd.AddValue("densityLow", "Density low threshold (veh/m^2)", g_densityLow);
  cmd.AddValue("densityHigh", "Density high threshold (veh/m^2)", g_densityHigh);
  cmd.AddValue("enableRevocation", "Enable revocation 0/1", g_enableRevocation);
  cmd.AddValue("revokeTrustThresh", "Trust below => revoke", g_revokeTrustThresh);
  cmd.AddValue("revokeSyncIntervalMs", "Revocation sync interval ms", g_revokeSyncIntervalMs);
  
  cmd.AddValue("enableBCLocalCache", "Enable local trust cache", g_enableBCLocalCache);
cmd.AddValue("cacheTtlMs", "Trust cache TTL (ms)", g_cacheTtlMs);
  cmd.AddValue("bcSyncIntervalMs", "Blockchain update sync interval (ms)", g_bcSyncIntervalMs);
  cmd.AddValue("bcQueryDelayMs", "Simulated blockchain query delay (ms)", g_bcQueryDelayMs);
  cmd.AddValue("bcUpdateDelayMs", "Simulated blockchain update delay (ms)", g_bcUpdateDelayMs);

  cmd.AddValue("enablePrivacy", "Enable privacy pseudonyms", g_enablePrivacy);
  cmd.AddValue("pseudoPoolSize", "Pseudonym pool size per vehicle", g_pseudoPoolSize);
  cmd.AddValue("pseudoRotateIntervalS", "Pseudonym rotate interval (s)", g_pseudoRotateSec);
  cmd.AddValue("rotateOnHandover", "Rotate pseudonym on handover", g_rotateOnHandover);
  cmd.AddValue("linkWindowS", "Linkability attacker window (s)", g_linkTimeWindowSec);
  cmd.AddValue("mixRadiusM", "Mix-zone radius in meters", g_mixRadiusM);

  cmd.AddValue("enableBcProbe", "Enable periodic BC trust queries (probe workload)", g_enableBcProbe);

  cmd.AddValue("enableAuthBind", "Bind ECDH ephemeral key to auth tag", g_enableAuthBind);
  cmd.AddValue("enableMitmAttack", "MITM test: tamper pubkey at receiver (should fail)", g_enableMitmAttack);

  cmd.AddValue("enableAuthProbe", "Generate periodic auth handshakes (to measure AUTH stats)", g_enableAuthProbe);
  cmd.AddValue("authProbeIntervalMs", "Auth probe interval per vehicle (ms)", g_authProbeIntervalMs);
  cmd.AddValue("bcProbeIntervalMs", "BC probe interval per vehicle (ms)", g_bcProbeIntervalMs);
  cmd.AddValue("bcProbeUsePseudonym", "Probe uses active pseudonym key when privacy enabled", g_bcProbeUsePseudonym);
cmd.AddValue("forceRevokeVehicle0", "Force revoke vehicle0 0/1", g_forceRevokeVehicle0);
  cmd.AddValue("forceRevokeTime", "Force revoke time (s)", g_forceRevokeTime);

cmd.Parse(argc, argv);

  g_evt.open(g_eventsOut, std::ios::out | std::ios::trunc);
  g_evt << "time,event\n";

  // Create nodes
  g_vehicles.Create(g_nVehicles);
  g_rsus.Create(g_nRsu);

  NodeContainer all;
  all.Add(g_vehicles);
  all.Add(g_rsus);

  // Internet stack
  InternetStackHelper internet;
  internet.Install(all);

  // Mobility (NS2 installs only nodes present in trace => RSU might be missing)
  if (g_useNs2Mobility && !g_ns2Mobility.empty())
  {
    NS_LOG_UNCOND("[OK] Using NS2 mobility trace: " << g_ns2Mobility);
    Ns2MobilityHelper ns2(g_ns2Mobility);
    ns2.Install();

    // Auto-set SUMO bounds (only if bounds are still default 0..600)
    if (g_mapMinX == 0.0 && g_mapMaxX == 600.0 && g_mapMinY == 0.0 && g_mapMaxY == 600.0)
    {
      g_mapMinX = 15.5;   g_mapMaxX = 604.8;
      g_mapMinY = 136.66; g_mapMaxY = 584.5;
    }
  }
  else
  {
    MobilityHelper mob;
    mob.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                         "Bounds", RectangleValue(Rectangle(g_mapMinX, g_mapMaxX, g_mapMinY, g_mapMaxY)));
    mob.Install(g_vehicles);
  }

  // RSUs always constant position
  MobilityHelper rsuMob;
  rsuMob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  rsuMob.Install(g_rsus);

  // Fallback: ensure every node has mobility
  MobilityHelper fallback;
  fallback.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  for (uint32_t i = 0; i < NodeList::GetNNodes(); i++)
  {
    Ptr<Node> n = all.Get(i);
    if (n->GetObject<MobilityModel>() == nullptr)
    {
      fallback.Install(n);
      n->GetObject<MobilityModel>()->SetPosition(Vector(g_mapMinX, g_mapMinY, 0.0));
      NS_LOG_UNCOND("[WARN] fallback mobility installed on node=" << n->GetId());
    }
  }

  // RSU placement inside map (yMid)
  g_rsuPos.clear();
  double yMid = 0.5 * (g_mapMinY + g_mapMaxY);

  if (g_nRsu == 1)
  {
    g_rsuPos.push_back(Vector(0.5 * (g_mapMinX + g_mapMaxX), yMid, 0.0));
  }
  else
  {
    g_rsuPos.push_back(Vector(g_mapMinX + (g_mapMaxX - g_mapMinX) / 3.0, yMid, 0.0));
    g_rsuPos.push_back(Vector(g_mapMinX + 2.0 * (g_mapMaxX - g_mapMinX) / 3.0, yMid, 0.0));
    for (uint32_t r = 2; r < g_nRsu; r++)
    {
      double x = g_mapMinX + (double(r) + 1.0) * (g_mapMaxX - g_mapMinX) / (double(g_nRsu) + 1.0);
      g_rsuPos.push_back(Vector(x, yMid, 0.0));
    }
  }
  for (uint32_t r = 0; r < g_nRsu; r++)
  {
    g_rsus.Get(r)->GetObject<MobilityModel>()->SetPosition(g_rsuPos[r]);
  }

  // WiFi (constant rate + range model for stable RSU connectivity)
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211a);
  wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                               "DataMode", StringValue("OfdmRate6Mbps"),
                               "ControlMode", StringValue("OfdmRate6Mbps"));

  YansWifiChannelHelper channel;
  channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
  channel.AddPropagationLoss("ns3::RangePropagationLossModel",
                             "MaxRange", DoubleValue(1200.0));

  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());
  phy.Set("TxPowerStart", DoubleValue(16.0));
  phy.Set("TxPowerEnd", DoubleValue(16.0));

  WifiMacHelper mac;
  mac.SetType("ns3::AdhocWifiMac");

  NetDeviceContainer devs = wifi.Install(phy, mac, all);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.0.0", "255.255.0.0");
  Ipv4InterfaceContainer ifs = ipv4.Assign(devs);

  g_rsu0Addr = ifs.GetAddress(g_nVehicles + 0);

  // Initialize trust + keys + malicious set
  g_ledgerTrust.assign(g_nVehicles, 0.8);
  g_trustLastSyncMs.assign(g_nVehicles, NowMs());
  PrivacyInit();
  StartBcProbes();
  StartAuthProbes();
  TrustInit();
  
  if (g_enablePrivacy) {
    InitPseudonyms();
    for (uint32_t v = 0; v < g_nVehicles; v++)
      Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
  }
g_keys.assign(g_nVehicles, 0);

  g_uv->SetStream(g_attackSeed);
  for (uint32_t v = 0; v < g_nVehicles; v++)
    g_keys[v] = (uint32_t)g_uv->GetInteger(1, 0x7fffffff);

  g_isMalicious.assign(g_nVehicles, false);
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    double r = g_uv->GetValue(0.0, 1.0);
    if (r < g_maliciousRate) g_isMalicious[v] = true;
  }

  // Ensure attacker exists when only vehicle0 transmits
  if (!g_txAllVehicles && g_attackMode != 0 && !g_isMalicious.empty())
  {
    g_isMalicious[0] = true;
    NS_LOG_UNCOND("[OK] forced attacker: vehicle0 is malicious");
  }

  // Replay caches
  g_replayCaches.resize(NodeList::GetNNodes());
  for (uint32_t i = 0; i < NodeList::GetNNodes(); i++)
    g_replayCaches[i] = std::make_unique<ReplayCache>(5000);

  // suspicion matrix
  g_suspicion.assign(g_nVehicles, std::vector<uint16_t>(g_nVehicles, 0));

  // Handover states: start unattached so first attach counts
  g_vs.assign(g_nVehicles, VehicleState{});
  for (uint32_t v = 0; v < g_nVehicles; v++)
    g_vs[v].currentRsu = -1;

  // Data recv sockets on ALL nodes
  g_dataRecvSock.resize(NodeList::GetNNodes());
  for (uint32_t i = 0; i < NodeList::GetNNodes(); i++)
  {
    Ptr<Socket> s = Socket::CreateSocket(all.Get(i), UdpSocketFactory::GetTypeId());
    s->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_dataPort));
    s->SetRecvCallback(MakeCallback(&RxDataReady));
    g_dataRecvSock[i] = s;
  }

  // RSU0 report recv
  g_rsuReportRecvSock = Socket::CreateSocket(g_rsus.Get(0), UdpSocketFactory::GetTypeId());
  g_rsuReportRecvSock->Bind(InetSocketAddress(Ipv4Address::GetAny(), g_reportPort));
  g_rsuReportRecvSock->SetRecvCallback(MakeCallback(&RxReportAtRsu));

  // Vehicle report sockets -> RSU0
  g_vehicleReportSock.resize(g_nVehicles);
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    Ptr<Socket> s = Socket::CreateSocket(g_vehicles.Get(v), UdpSocketFactory::GetTypeId());
    s->Connect(InetSocketAddress(g_rsu0Addr, g_reportPort));
    g_vehicleReportSock[v] = s;
  }

  // Data send sockets (per vehicle)
  g_dataSendSock.resize(g_nVehicles);
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    Ptr<Socket> s = Socket::CreateSocket(g_vehicles.Get(v), UdpSocketFactory::GetTypeId());
    s->SetAllowBroadcast(true);
    s->Connect(InetSocketAddress(Ipv4Address("10.1.255.255"), g_dataPort));
    g_dataSendSock[v] = s;
  }

  // Start data sending
  if (g_txAllVehicles)
  {
    for (uint32_t v = 0; v < g_nVehicles; v++)
      Simulator::Schedule(Seconds(0.5 + 0.001 * v), &SendNewPacket, v);
  }
  else
  {
    Simulator::Schedule(Seconds(0.5), &SendNewPacket, 0);
  }

  // Blockchain scheduler
  Simulator::Schedule(Seconds(0.0), &StartBlockchain);

  // Replay attack (sender0)
  Simulator::Schedule(Seconds(1.0), &ReplayAttackTick);

  // Handover check periodic
  for (uint32_t v = 0; v < g_nVehicles; v++)
    Simulator::Schedule(MilliSeconds(g_handoverCheckMs), &CheckHandover, g_vehicles.Get(v));

  // Write CSV near end
  Simulator::Schedule(Seconds(std::max(0.001, g_simTime - 0.001)), &WriteCsv);

  Simulator::Stop(Seconds(g_simTime));
  Simulator::Run();
    PrintBcCacheStats();
  PrintPrivacyStats();    PrintAuthStats();
    PrintStaleStats();
  Simulator::Destroy();

  if (g_evt.is_open()) g_evt.close();
  return 0;
}
