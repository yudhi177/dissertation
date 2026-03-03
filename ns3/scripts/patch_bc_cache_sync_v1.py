from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 0) Remove any older BC cache block
txt = re.sub(r"// BC_CACHE_SYNC_V1_BEGIN.*?// BC_CACHE_SYNC_V1_END\s*", "", txt, flags=re.S)

# 1) Insert module before GetTrustForHandover()
m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find GetTrustForHandover() to insert BC cache module before it.")

ins = m.start()

bc_block = r'''
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
'''

txt = txt[:ins] + bc_block + txt[ins:]

# 2) Patch GetTrustForHandover to use cache-backed lookup
func_pat = re.compile(r"static\s+double\s+GetTrustForHandover\s*\([^\)]*\)\s*\{.*?\n\}\n", re.S)
m2 = func_pat.search(txt)
if not m2:
    raise SystemExit("[ERR] Could not locate full GetTrustForHandover() body to patch.")

new_func = r'''
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
  return t;
}
'''
txt = txt[:m2.start()] + new_func + txt[m2.end():]

# 3) Throttle on-chain trust updates where you currently set g_ledgerTrust[v] = g_trustScore[v]
txt = re.sub(
    r'//\s*"on-chain"\s*=\s*g_ledgerTrust\s*\(already global in your file\)\s*\n\s*if\s*\(v\s*<\s*g_ledgerTrust\.size\(\)\)\s*\n\s*g_ledgerTrust\[v\]\s*=\s*g_trustScore\[v\]\s*;\s*',
    r'''// "on-chain" (simulated) commit is throttled by bcSyncIntervalMs
  if (v < g_ledgerTrust.size())
  {
    double bcDelayMs = 0.0;
    bool didUpdate = false;
    MaybeCommitTrustUpdate(std::to_string(v), g_trustScore[v], bcDelayMs, didUpdate);
  }
''',
    txt
)

# 4) Add CLI flags near existing revocation flags (fallback: before cmd.Parse)
addvals = r'''
  cmd.AddValue("enableBCLocalCache", "Enable local trust cache", g_enableBCLocalCache);
  cmd.AddValue("cacheTtlMs", "Trust cache TTL (ms)", g_cacheTtlMs);
  cmd.AddValue("bcSyncIntervalMs", "Blockchain update sync interval (ms)", g_bcSyncIntervalMs);
  cmd.AddValue("bcQueryDelayMs", "Simulated blockchain query delay (ms)", g_bcQueryDelayMs);
  cmd.AddValue("bcUpdateDelayMs", "Simulated blockchain update delay (ms)", g_bcUpdateDelayMs);
'''

m3 = re.search(r'cmd\.AddValue\("revokeSyncIntervalMs".*?\);\s*', txt)
if m3:
    pos = m3.end()
    txt = txt[:pos] + addvals + txt[pos:]
else:
    m4 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
    if not m4:
        raise SystemExit("[ERR] Could not find cmd.Parse(argc, argv); to insert CLI flags before it.")
    pos = m4.start()
    txt = txt[:pos] + addvals + txt[pos:]

# 5) Print BC stats after simulation run (before Destroy)
if "PrintBcCacheStats();" not in txt:
    txt = txt.replace("Simulator::Destroy();", "  PrintBcCacheStats();\n  Simulator::Destroy();", 1)

p.write_text(txt)
print("[OK] Patched BC cache + sync v1 into:", p)
