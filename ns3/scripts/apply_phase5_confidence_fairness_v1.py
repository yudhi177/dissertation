from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

B = "// PHASE5_CONF_FAIR_V1_BEGIN"
E = "// PHASE5_CONF_FAIR_V1_END"

block = r'''
// PHASE5_CONF_FAIR_V1_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness ---

static bool     g_enableTrustConfidence = true;
static uint32_t g_confWindow = 20;          // already exists as cmd param in your file (keep)
static double   g_confMinForFast = 0.6;     // already exists as cmd param in your file (keep)
static uint64_t g_fastDeniedLowConf = 0;

static bool     g_enableChannelFairness = true;
static double   g_badChannelLossThresh = 0.25;  // if loss > this => "bad channel"
static double   g_fairnessPenaltyScaleBad = 0.3; // multiply penalty by this in bad channel
static uint64_t g_fairnessBadChannelHits = 0;

// Per-vehicle confidence (0..1) based on observation count window
static std::vector<uint32_t> g_obsCount;

static inline double TrustConfidence(uint32_t id)
{
  if (g_confWindow == 0) return 1.0;
  if (id >= g_obsCount.size()) return 0.0;
  double c = double(g_obsCount[id]) / double(g_confWindow);
  if (c < 0.0) c = 0.0;
  if (c > 1.0) c = 1.0;
  return c;
}

// Call this whenever an observation is recorded for vehicle id
static inline void RecordObservation(uint32_t id)
{
  if (id >= g_obsCount.size()) return;
  if (g_obsCount[id] < g_confWindow) g_obsCount[id]++;
}

// Lightweight channel health proxy:
// use recent receive ratio if available; fallback uses PDR-like variable names if present.
static inline double EstimateLossProxy()
{
  // Best effort: if you have counters g_txCount/g_rxCount style
  // we approximate loss as 1 - (rx/tx) in small windows.
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
// PHASE5_CONF_FAIR_V1_END
'''

def insert_after_using(txt: str) -> str:
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
        return txt
    if B in txt:
        return txt
    return txt[:m.end()] + block + txt[m.end():]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Ensure vector include
    if "#include <vector>" not in txt:
        if "#include <iostream>" in txt:
            txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <vector>\n", 1)
        else:
            txt = "#include <vector>\n" + txt

    txt = insert_after_using(txt)

    # Ensure g_obsCount is sized in main after g_nVehicles known (after cmd.Parse)
    if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
        mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
        if mp:
            pos = mp.end()
            hook = "  // PHASE5: init confidence observation counters\n  g_obsCount.assign(g_nVehicles, 0);\n"
            txt = txt[:pos] + hook + txt[pos:]

    # Add cmd flags if not present (safe: only add if missing)
    if 'cmd.AddValue("enableTrustConfidence"' not in txt:
        m2 = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
        if m2:
            pos = m2.end()
            txt = txt[:pos] + '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n' + txt[pos:]

    if 'cmd.AddValue("enableChannelFairness"' not in txt:
        # place near trust params
        m3 = re.search(r'cmd\.AddValue\("trustDecayPerSec".*?\);\s*\n', txt)
        if m3:
            pos = m3.end()
            add = (
                '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
                '  cmd.AddValue("badChannelLossThresh", "Loss threshold to treat channel as bad", g_badChannelLossThresh);\n'
                '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
            )
            txt = txt[:pos] + add + txt[pos:]

    p.write_text(txt)
    print("[OK] Phase5 block inserted:", p)

