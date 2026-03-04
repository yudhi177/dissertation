from pathlib import Path
import re

P = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = P.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")

# Prevent double-patching
if "TRUST_ENGINE_FINAL_V1" in txt:
    print("[OK] Trust Engine FINAL v1 already applied.")
    raise SystemExit(0)

# 0) Hard safety: remove any accidental \" that breaks C++
txt = txt.replace('\\"', '"')

# 1) Ensure cmath include (exp, sqrt)
if "#include <cmath>" not in txt:
    if "#include <algorithm>" in txt:
        txt = txt.replace("#include <algorithm>\n", "#include <algorithm>\n#include <cmath>\n")
    else:
        # fallback after last include
        incs = list(re.finditer(r"^#include[^\n]*\n", txt, flags=re.M))
        if incs:
            last = incs[-1]
            txt = txt[:last.end()] + "#include <cmath>\n" + txt[last.end():]

# 2) Insert globals (after trust gate globals if present, else after blockchain globals)
trust_globals = r'''
// ===================== TRUST_ENGINE_FINAL_V1 =====================
static bool     g_enableTrustEngineFinal = true;

// Trust formula: Ti = w1*BehaviorConsistency + w2*HistoricalTrust + w3*RSUFeedback
static double   g_w1Base = 0.45;     // BehaviorConsistency
static double   g_w2Base = 0.35;     // HistoricalTrust
static double   g_w3Base = 0.20;     // RSUFeedback

// Density-based adaptive weights (global density estimate)
static double   g_densityLow  = 0.00005;  // ~10 vehicles / 600x600
static double   g_densityHigh = 0.00025;  // ~80 vehicles / 600x600

// Trust decay: drift towards neutral over time
static double   g_trustNeutral = 0.5;
static double   g_decayHalfLifeSec = 30.0;    // bigger => slower decay

// False-positive recovery: gently restore if behavior good
static double   g_recoveryTarget = 0.85;
static double   g_recoveryRatePerSec = 0.02;  // towards target when good evidence

// Local trust cache + sync interval control (blockchain query avoidance)
static uint32_t g_trustSyncIntervalMs = 1000; // cache TTL / sync interval
static uint32_t g_trustQueryDelayMs   = 10;   // extra delay when cache miss (simulated)

// Trust state/evidence per vehicle
static std::vector<double> g_histTrust;      // HistoricalTrust state (0..1)
static std::vector<double> g_behScore;       // BehaviorConsistency (EWMA 0..1)
static std::vector<double> g_rsuScore;       // RSUFeedback score (0..1)
static std::vector<double> g_lastTrustUpdate;// last update time (sec)

// Cache
static std::vector<double> g_trustCache;
static std::vector<double> g_trustCacheTs;   // last sync time (sec)
static uint64_t g_trustCacheHits = 0;
static uint64_t g_trustCacheMiss = 0;
// ================================================================
'''

inserted = False
for pat in [
    r"(static\s+bool\s+g_enableTrustGate\s*=\s*[^;]+;\s*\n)",
    r"(static\s+bool\s+g_enableBlockchain\s*=\s*[^;]+;\s*\n)",
]:
    m = re.search(pat, txt)
    if m:
        txt = txt[:m.end()] + trust_globals + txt[m.end():]
        inserted = True
        break
if not inserted:
    raise SystemExit("[ERR] Could not find insertion point for trust globals.")

# 3) Add CommandLine args (after trust gate args if possible; else after eventsOut)
trust_cmd = r'''
  cmd.AddValue("enableTrustEngineFinal", "Enable FINAL trust engine 0/1", g_enableTrustEngineFinal);
  cmd.AddValue("w1Base", "Base weight for BehaviorConsistency", g_w1Base);
  cmd.AddValue("w2Base", "Base weight for HistoricalTrust", g_w2Base);
  cmd.AddValue("w3Base", "Base weight for RSUFeedback", g_w3Base);
  cmd.AddValue("densityLow", "Low density threshold", g_densityLow);
  cmd.AddValue("densityHigh", "High density threshold", g_densityHigh);
  cmd.AddValue("decayHalfLifeSec", "Trust decay half-life seconds", g_decayHalfLifeSec);
  cmd.AddValue("trustNeutral", "Neutral trust baseline", g_trustNeutral);
  cmd.AddValue("recoveryTarget", "Recovery target trust", g_recoveryTarget);
  cmd.AddValue("recoveryRatePerSec", "Recovery rate per second", g_recoveryRatePerSec);
  cmd.AddValue("trustSyncIntervalMs", "Trust cache sync interval ms", g_trustSyncIntervalMs);
  cmd.AddValue("trustQueryDelayMs", "Simulated chain query delay ms on cache miss", g_trustQueryDelayMs);
'''
if 'cmd.AddValue("enableTrustEngineFinal"' not in txt:
    m = re.search(r'(cmd\.AddValue\("enableTrustGate"[^\n]*\);\s*\n)', txt)
    if m:
        txt = txt[:m.end()] + trust_cmd + txt[m.end():]
    else:
        m2 = re.search(r'(cmd\.AddValue\("eventsOut"[^\n]*\);\s*\n)', txt)
        if not m2:
            raise SystemExit('[ERR] Could not find cmd.AddValue("eventsOut"...).')
        txt = txt[:m2.end()] + trust_cmd + txt[m2.end():]

# 4) Insert TRUST ENGINE helper functions before CheckHandover()
helpers_marker = re.search(r"\nstatic void CheckHandover\(", txt)
if not helpers_marker:
    raise SystemExit("[ERR] Could not find CheckHandover() marker for insertion.")

trust_helpers = r'''
/* =========================================================
   TRUST ENGINE FINAL (formula + adaptive weights + decay + recovery + cache)
========================================================= */
static double SafeArea()
{
  // Use map bounds if present (some versions have g_mapMinX..), else default 600x600
  double minX = 0.0, maxX = 600.0, minY = 0.0, maxY = 600.0;

  // best-effort: detect symbols
  // (If these globals don't exist, compiler will ignore because we don't reference them directly.)
  // So we keep defaults only.

  double w = (maxX - minX);
  double h = (maxY - minY);
  if (w <= 0.0) w = 600.0;
  if (h <= 0.0) h = 600.0;
  return w * h;
}

static double EstimateDensity()
{
  double area = SafeArea();
  if (area <= 1.0) area = 360000.0;
  return double(g_nVehicles) / area; // vehicles per m^2
}

static void ComputeAdaptiveWeights(double density, double &w1, double &w2, double &w3)
{
  double t = 0.0;
  if (g_densityHigh > g_densityLow)
    t = (density - g_densityLow) / (g_densityHigh - g_densityLow);

  if (t < 0.0) t = 0.0;
  if (t > 1.0) t = 1.0;

  // Deterministic rule-based adaptation (scope-compliant)
  // density ↑ => rely more on RSU feedback; slightly less on behavior-only
  w1 = g_w1Base - 0.15 * t;
  w2 = g_w2Base;
  w3 = g_w3Base + 0.25 * t;

  if (w1 < 0.05) w1 = 0.05;
  if (w3 < 0.05) w3 = 0.05;

  double s = w1 + w2 + w3;
  if (s <= 1e-9) { w1 = 0.33; w2 = 0.33; w3 = 0.34; return; }
  w1 /= s; w2 /= s; w3 /= s;
}

static void TrustInitIfNeeded()
{
  if (!g_enableTrustEngineFinal) return;
  if (g_histTrust.size() == g_nVehicles) return;

  g_histTrust.assign(g_nVehicles, 0.8);
  g_behScore.assign(g_nVehicles, 0.8);
  g_rsuScore.assign(g_nVehicles, 0.8);
  g_lastTrustUpdate.assign(g_nVehicles, 0.0);

  g_trustCache.assign(g_nVehicles, 0.8);
  g_trustCacheTs.assign(g_nVehicles, -1e9);
}

static void TrustEvidenceGood(uint32_t v)
{
  if (!g_enableTrustEngineFinal) return;
  if (v >= g_nVehicles) return;
  TrustInitIfNeeded();

  double a = 0.10; // EWMA
  g_behScore[v] = Clamp01((1.0 - a) * g_behScore[v] + a * 1.0);
}

static void TrustEvidenceBad(uint32_t v)
{
  if (!g_enableTrustEngineFinal) return;
  if (v >= g_nVehicles) return;
  TrustInitIfNeeded();

  double a = 0.10; // EWMA
  g_behScore[v] = Clamp01((1.0 - a) * g_behScore[v] + a * 0.0);
}

static void ApplyRsuFeedback(uint32_t accused, double delta)
{
  if (!g_enableTrustEngineFinal) return;
  if (accused >= g_nVehicles) return;
  TrustInitIfNeeded();

  // RSUFeedback score update (bounded)
  g_rsuScore[accused] = Clamp01(g_rsuScore[accused] + delta);
}

static double TrustUpdateNow(uint32_t v)
{
  if (!g_enableTrustEngineFinal) return (v < g_ledgerTrust.size() ? g_ledgerTrust[v] : 0.5);
  if (v >= g_nVehicles) return 0.5;
  TrustInitIfNeeded();

  double now = Simulator::Now().GetSeconds();
  double dt = now - g_lastTrustUpdate[v];
  if (dt < 0) dt = 0;

  // Decay towards neutral (not towards zero)
  double lambda = 0.0;
  if (g_decayHalfLifeSec > 1e-6)
    lambda = std::log(2.0) / g_decayHalfLifeSec;

  double decay = std::exp(-lambda * dt);
  double hist = g_histTrust[v];
  hist = g_trustNeutral + (hist - g_trustNeutral) * decay;

  // Adaptive weights by density
  double density = EstimateDensity();
  double w1, w2, w3;
  ComputeAdaptiveWeights(density, w1, w2, w3);

  double beh = g_behScore[v];
  double rsu = g_rsuScore[v];

  // Final trust formula
  double T = w1 * beh + w2 * hist + w3 * rsu;

  // False-positive recovery (only when behavior is good)
  if (beh >= 0.80 && T < g_recoveryTarget)
  {
    double rec = g_recoveryRatePerSec * dt;
    if (rec > 0.25) rec = 0.25; // bound per update
    T = T + rec * (g_recoveryTarget - T);
  }

  T = Clamp01(T);

  g_histTrust[v] = T;
  g_lastTrustUpdate[v] = now;

  // keep ledger consistent (if used elsewhere)
  if (v < g_ledgerTrust.size())
    g_ledgerTrust[v] = T;

  return T;
}

static double GetTrustForHandover(uint32_t v, uint32_t* extraDelayMs, bool* cacheHit)
{
  if (extraDelayMs) *extraDelayMs = 0;
  if (cacheHit) *cacheHit = true;

  if (!g_enableTrustEngineFinal)
    return (v < g_ledgerTrust.size() ? g_ledgerTrust[v] : 0.5);

  if (v >= g_nVehicles) return 0.5;
  TrustInitIfNeeded();

  double now = Simulator::Now().GetSeconds();
  double ttl = double(g_trustSyncIntervalMs) / 1000.0;

  bool hit = ((now - g_trustCacheTs[v]) <= ttl);
  if (cacheHit) *cacheHit = hit;

  // always locally update (decay+recovery), but only charge delay on cache miss
  double T = TrustUpdateNow(v);

  if (hit)
  {
    g_trustCacheHits++;
    g_trustCache[v] = T;
    return g_trustCache[v];
  }

  g_trustCacheMiss++;
  g_trustCacheTs[v] = now;
  g_trustCache[v] = T;

  if (extraDelayMs) *extraDelayMs = g_trustQueryDelayMs;
  LogEvent("TRUST_CACHE_MISS v=" + std::to_string(v) + " qDelayMs=" + std::to_string(g_trustQueryDelayMs));
  return g_trustCache[v];
}
'''
txt = txt[:helpers_marker.start()] + trust_helpers + txt[helpers_marker.start():]

# 5) Patch CommitNow: replace direct ledger clamp update -> ApplyRsuFeedback + TrustUpdateNow
txt = re.sub(
    r"g_ledgerTrust\[it\.accused\]\s*=\s*Clamp01\(g_ledgerTrust\[it\.accused\]\s*\+\s*it\.delta\);\s*\n\s*g_reportsCommitted\+\+;",
    "ApplyRsuFeedback(it.accused, it.delta);\n      TrustUpdateNow(it.accused);\n      g_reportsCommitted++;",
    txt
)

# 6) Patch ProcessData: add evidence hooks on success + drop
# replay drop
txt = re.sub(
    r"(g_replayDrops\+\+;\s*\n\s*LogEvent\([^\)]*\);\s*\n\s*return;)",
    r"\1\n  TrustEvidenceBad(hdr.senderId);",
    txt
)
# sig drop
txt = re.sub(
    r"(g_sigDrops\+\+;\s*\n\s*LogEvent\([^\)]*\);\s*\n\s*return;)",
    r"\1\n  TrustEvidenceBad(hdr.senderId);",
    txt
)
# success path: after g_rxData++
txt = re.sub(
    r"(g_rxData\+\+;\s*\n)",
    r"\1  TrustEvidenceGood(hdr.senderId);\n",
    txt,
    count=1
)

# 7) Patch CheckHandover: use GetTrustForHandover + cache delay
txt = re.sub(
    r"double\s+trust\s*=\s*\(id\s*<\s*g_ledgerTrust\.size\(\)\)\s*\?\s*g_ledgerTrust\[id\]\s*:\s*0\.5\s*;",
    "uint32_t extraTrustDelayMs = 0;\n    bool cacheHit = true;\n    double trust = GetTrustForHandover(id, &extraTrustDelayMs, &cacheHit);",
    txt
)
# add extra delay into authDelay if present
txt = re.sub(
    r"(uint32_t\s+authDelay\s*=\s*fast\s*\?\s*g_fastAuthDelayMs\s*:\s*g_fullAuthDelayMs;\s*\n)",
    r"\1      authDelay += extraTrustDelayMs;\n",
    txt
)

# 8) Final cleanup of any accidental \" again
txt = txt.replace('\\"', '"')

P.write_text(txt, encoding="utf-8")
print("[OK] Trust Engine FINAL v1 applied:", P)
