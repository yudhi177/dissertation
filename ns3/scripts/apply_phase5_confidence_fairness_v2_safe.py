from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

B = "// PHASE5_CONF_FAIR_V2_BEGIN"
E = "// PHASE5_CONF_FAIR_V2_END"

block = r'''
// PHASE5_CONF_FAIR_V2_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness (SAFE: no duplicate globals) ---

// NOTE: g_confWindow and g_confMinForFast already exist in this file. We DO NOT redeclare them here.

static bool     g_enableTrustConfidence = true;
static uint64_t g_fastDeniedLowConf = 0;

static bool     g_enableChannelFairness = true;
static double   g_badChannelLossThresh = 0.25;       // if loss > this => "bad channel"
static double   g_fairnessPenaltyScaleBad = 0.30;    // multiply penalty by this in bad channel
static uint64_t g_fairnessBadChannelHits = 0;

// Per-vehicle observation count for confidence
static std::vector<uint32_t> g_obsCount;

// Confidence in [0..1]
static inline double TrustConfidence(uint32_t id)
{
  if (g_confWindow == 0) return 1.0;
  if (id >= g_obsCount.size()) return 0.0;
  double c = double(g_obsCount[id]) / double(g_confWindow);
  if (c < 0.0) c = 0.0;
  if (c > 1.0) c = 1.0;
  return c;
}

// Call when an observation is recorded for vehicle id
static inline void RecordObservation(uint32_t id)
{
  if (id >= g_obsCount.size()) return;
  if (g_obsCount[id] < g_confWindow) g_obsCount[id]++;
}

// Channel loss proxy using global counters if present (your file already prints PDR etc.)
// If tx==0 => assume good channel.
static inline double EstimateLossProxy()
{
  extern uint64_t g_txCount;
  extern uint64_t g_rxCount;

  if (g_txCount == 0) return 0.0;
  double p = double(g_rxCount) / double(g_txCount);
  if (p < 0.0) p = 0.0;
  if (p > 1.0) p = 1.0;
  return 1.0 - p;
}

static inline double ApplyFairnessPenaltyScale(double basePenalty)
{
  if (!g_enableChannelFairness) return basePenalty;
  double loss = EstimateLossProxy();
  if (loss > g_badChannelLossThresh)
  {
    g_fairnessBadChannelHits++;
    return basePenalty * g_fairnessPenaltyScaleBad;
  }
  return basePenalty;
}
// PHASE5_CONF_FAIR_V2_END
'''

def ensure_include(txt: str, inc: str) -> str:
  if inc in txt:
    return txt
  if "#include <iostream>" in txt:
    return txt.replace("#include <iostream>\n", "#include <iostream>\n" + inc + "\n", 1)
  return inc + "\n" + txt

for p in targets:
  if not p.exists():
    continue
  txt = p.read_text()

  # includes
  txt = ensure_include(txt, "#include <vector>")

  # insert after "using namespace ns3;"
  if B not in txt:
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
      raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
    txt = txt[:m.end()] + block + txt[m.end():]

  # init g_obsCount after cmd.Parse
  if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
    mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
    if mp:
      pos = mp.end()
      txt = txt[:pos] + "  // PHASE5: init obs counters\n  g_obsCount.assign(g_nVehicles, 0);\n" + txt[pos:]

  # add cmd flags (only if missing)
  if 'cmd.AddValue("enableTrustConfidence"' not in txt:
    anchor = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
    if anchor:
      pos = anchor.end()
      txt = txt[:pos] + '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n' + txt[pos:]

  if 'cmd.AddValue("enableChannelFairness"' not in txt:
    anchor = re.search(r'cmd\.AddValue\("trustDecayPerSec".*?\);\s*\n', txt)
    if anchor:
      pos = anchor.end()
      add = (
        '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
        '  cmd.AddValue("badChannelLossThresh", "Loss threshold to treat channel as bad", g_badChannelLossThresh);\n'
        '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
      )
      txt = txt[:pos] + add + txt[pos:]

  p.write_text(txt)
  print("[OK] Phase5 SAFE inserted:", p)
