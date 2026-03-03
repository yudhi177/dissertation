from pathlib import Path
import re
import sys

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# ------------------------------------------------------------
# 0) Ensure <cmath>
# ------------------------------------------------------------
if "#include <cmath>" not in txt:
    txt = txt.replace("#include <algorithm>\n", "#include <algorithm>\n#include <cmath>\n")

# ------------------------------------------------------------
# 1) Remove any previous injected TRUST_ENGINE blocks (v1/v2/etc)
# ------------------------------------------------------------
txt = re.sub(
    r"// TRUST_ENGINE_FINAL_[A-Z0-9_]+_BEGIN.*?// TRUST_ENGINE_FINAL_[A-Z0-9_]+_END\s*",
    "",
    txt,
    flags=re.S
)

# Also remove any leftover single-line dupes from older broken patches
cleanup_pats = [
    r"static\s+bool\s+g_enableTrustEngineFinal\s*=.*?;\s*",
    r"static\s+uint32_t\s+g_trustSyncIntervalMs\s*=.*?;\s*",
    r"static\s+uint32_t\s+g_trustQueryDelayMs\s*=.*?;\s*",
    r"static\s+double\s+g_w1Base\s*=.*?;\s*",
    r"static\s+double\s+g_w2Base\s*=.*?;\s*",
    r"static\s+double\s+g_w3Base\s*=.*?;\s*",
    r"static\s+double\s+g_densityLow\s*=.*?;\s*",
    r"static\s+double\s+g_densityHigh\s*=.*?;\s*",
    r"static\s+double\s+g_trustDecayPerSec\s*=.*?;\s*",
    r"static\s+double\s+g_recoveryPerSec\s*=.*?;\s*",
    r"static\s+double\s+g_neutralTrust\s*=.*?;\s*",
    r"static\s+std::vector<uint32_t>\s+g_goodCount\s*;\s*",
    r"static\s+std::vector<uint32_t>\s+g_badCount\s*;\s*",
    r"static\s+std::vector<double>\s+g_lastBadTime\s*;\s*",
    r"static\s+std::vector<double>\s+g_histTrust\s*;\s*",
    r"static\s+std::vector<double>\s+g_rsuFeedback\s*;\s*",
    r"static\s+std::vector<double>\s+g_lastTrustUpdate\s*;\s*",
    r"static\s+std::vector<double>\s+g_trustScore\s*;\s*",
    r"static\s+std::vector<double>\s+g_cacheTrust\s*;\s*",
    r"static\s+std::vector<double>\s+g_cacheTime\s*;\s*",
    r"static\s+uint64_t\s+g_trustCacheHits\s*=.*?;\s*",
    r"static\s+uint64_t\s+g_trustCacheMiss\s*=.*?;\s*",
]
for pat in cleanup_pats:
    txt = re.sub(pat, "", txt)

# ------------------------------------------------------------
# 2) Find Clamp01() function and insert AFTER it
# ------------------------------------------------------------
m = re.search(r"static\s+double\s+Clamp01\s*\(\s*double\s+x\s*\)\s*\{.*?\n\}", txt, flags=re.S)
if not m:
    raise SystemExit("[ERR] Could not find Clamp01(double x) function. Search in file and ensure it exists.")

insert_pos = m.end()

trust_block = r'''

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
static uint64_t g_trustCacheHits = 0;
static uint64_t g_trustCacheMiss = 0;

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

  // "on-chain" = g_ledgerTrust (already global in your file)
  if (v < g_ledgerTrust.size())
    g_ledgerTrust[v] = g_trustScore[v];
}

static void TrustEvidenceGood(uint32_t sender)
{
  if (!g_enableTrustEngineFinal) return;
  if (sender >= g_nVehicles) return;
  g_goodCount[sender]++;
  TrustRecompute(sender);
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
  if (!g_enableTrustEngineFinal) return;
  if (accused >= g_nVehicles) return;
  g_rsuFeedback[accused] = Clamp01(g_rsuFeedback[accused] + delta);
  TrustRecompute(accused);
}

static double GetTrustForHandover(uint32_t v, uint32_t* extraDelayMs, bool* cacheHit)
{
  if (extraDelayMs) *extraDelayMs = 0;
  if (cacheHit) *cacheHit = true;

  if (!g_enableTrustEngineFinal || v >= g_nVehicles)
  {
    return (v < g_ledgerTrust.size()) ? g_ledgerTrust[v] : g_neutralTrust;
  }

  double now = Simulator::Now().GetSeconds();
  double ttl = double(g_trustSyncIntervalMs) / 1000.0;

  bool hit = (now - g_cacheTime[v]) <= ttl;
  if (hit)
  {
    g_trustCacheHits++;
    if (cacheHit) *cacheHit = true;
    return g_cacheTrust[v];
  }

  g_trustCacheMiss++;
  if (cacheHit) *cacheHit = false;
  if (extraDelayMs) *extraDelayMs = g_trustQueryDelayMs;

  double t = (v < g_ledgerTrust.size()) ? g_ledgerTrust[v] : g_neutralTrust;
  g_cacheTrust[v] = t;
  g_cacheTime[v]  = now;
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
'''

txt = txt[:insert_pos] + trust_block + txt[insert_pos:]

# ------------------------------------------------------------
# 3) Add CommandLine args (once)
# ------------------------------------------------------------
if 'cmd.AddValue("enableTrustEngineFinal"' not in txt:
    txt = re.sub(
        r'(cmd\.AddValue\("eventsOut"[^\n]*\);\s*)',
        r'\1'
        r'  cmd.AddValue("enableTrustEngineFinal", "Enable Trust Engine FINAL v3 0/1", g_enableTrustEngineFinal);\n'
        r'  cmd.AddValue("trustSyncIntervalMs", "Trust cache TTL / sync interval ms", g_trustSyncIntervalMs);\n'
        r'  cmd.AddValue("trustQueryDelayMs", "Extra delay on trust cache miss (ms)", g_trustQueryDelayMs);\n'
        r'  cmd.AddValue("trustDecayPerSec", "Trust decay per second", g_trustDecayPerSec);\n'
        r'  cmd.AddValue("recoveryPerSec", "Recovery per second", g_recoveryPerSec);\n'
        r'  cmd.AddValue("w1Base", "Base weight BehaviorConsistency", g_w1Base);\n'
        r'  cmd.AddValue("w2Base", "Base weight HistoricalTrust", g_w2Base);\n'
        r'  cmd.AddValue("w3Base", "Base weight RSUFeedback", g_w3Base);\n'
        r'  cmd.AddValue("densityLow", "Density low threshold (veh/m^2)", g_densityLow);\n'
        r'  cmd.AddValue("densityHigh", "Density high threshold (veh/m^2)", g_densityHigh);\n',
        txt,
        count=1
    )

# ------------------------------------------------------------
# 4) Patch CommitNow: use ApplyRsuFeedback (avoid simplistic clamp)
# ------------------------------------------------------------
txt = re.sub(
    r'g_ledgerTrust\s*\[\s*it\.accused\s*\]\s*=\s*Clamp01\(\s*g_ledgerTrust\s*\[\s*it\.accused\s*\]\s*\+\s*it\.delta\s*\)\s*;\s*\n\s*g_reportsCommitted\+\+\s*;',
    r'ApplyRsuFeedback(it.accused, it.delta);\n      g_reportsCommitted++;',
    txt
)

# ------------------------------------------------------------
# 5) Patch ProcessData: add trust evidence calls (avoid duplicates)
# ------------------------------------------------------------
if "TrustEvidenceBad(hdr.senderId);" not in txt:
    txt = re.sub(
        r'(g_replayDrops\+\+;\s*\n\s*LogEvent\("DATA_DROP_REPLAY[^;]*;\s*\n\s*return;\s*)',
        r'\1\n  TrustEvidenceBad(hdr.senderId);\n',
        txt
    )
    txt = re.sub(
        r'(g_sigDrops\+\+;\s*\n\s*LogEvent\("DATA_DROP_SIG[^;]*;\s*\n\s*return;\s*)',
        r'\1\n  TrustEvidenceBad(hdr.senderId);\n',
        txt
    )

if "TrustEvidenceGood(hdr.senderId);" not in txt:
    txt = re.sub(
        r'(g_rxBytes\s*\+\=\s*pktSize;\s*)',
        r'\1\n  TrustEvidenceGood(hdr.senderId);\n',
        txt
    )

# ------------------------------------------------------------
# 6) Patch CheckHandover trust read (cache + delay)
# ------------------------------------------------------------
if "GetTrustForHandover" in txt:
    txt = re.sub(
        r'double\s+trust\s*=\s*\(id\s*<\s*g_ledgerTrust\.size\(\)\)\s*\?\s*g_ledgerTrust\[id\]\s*:\s*0\.5\s*;\s*',
        r'uint32_t extraTrustDelayMs = 0; bool cacheHit = true;\n  double trust = GetTrustForHandover(id, &extraTrustDelayMs, &cacheHit);\n',
        txt
    )

# ------------------------------------------------------------
# 7) Ensure TrustInit() called after ledger init
# ------------------------------------------------------------
if "TrustInit();" not in txt:
    txt = re.sub(
        r'(g_ledgerTrust\.assign\([^;]*\);\s*)',
        r'\1\n  TrustInit();\n',
        txt,
        count=1
    )

p.write_text(txt)
print("[OK] Trust Engine FINAL v3 applied:", p)
