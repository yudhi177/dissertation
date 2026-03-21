from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

BLOCK = r'''
// PHASE5_CONF_FAIR_V3_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness ---
// IMPORTANT: g_confWindow + g_confMinForFast already exist -> DO NOT redeclare.

static bool     g_enableTrustConfidence = true;
static uint64_t g_fastDeniedLowConf = 0;

static bool     g_enableChannelFairness = true;
static double   g_badChannelLossThresh = 0.25;
static double   g_fairnessPenaltyScaleBad = 0.30;
static uint64_t g_fairnessBadChannelHits = 0;

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

static inline void RecordObservation(uint32_t id)
{
  if (id >= g_obsCount.size()) return;
  if (g_obsCount[id] < g_confWindow) g_obsCount[id]++;
}

static inline double ApplyFairnessPenaltyScale(double penalty)
{
  if (!g_enableChannelFairness) return penalty;

  double loss = 0.0;
  if (g_txCount > 0) loss = 1.0 - (double(g_rxCount) / double(g_txCount));

  if (loss > g_badChannelLossThresh)
  {
    g_fairnessBadChannelHits++;
    return penalty * g_fairnessPenaltyScaleBad;
  }
  return penalty;
}

static inline void PrintPhase5Stats()
{
  std::cout << "[PHASE5] fastDeniedLowConf=" << g_fastDeniedLowConf
            << " fairnessBadChannelHits=" << g_fairnessBadChannelHits
            << " confOn=" << (g_enableTrustConfidence ? 1 : 0)
            << " fairOn=" << (g_enableChannelFairness ? 1 : 0)
            << std::endl;
}
// PHASE5_CONF_FAIR_V3_END
'''

def remove_old(txt: str) -> str:
    pats = [
        r"//\s*PHASE5_CONF_FAIR_V1_BEGIN.*?//\s*PHASE5_CONF_FAIR_V1_END\s*",
        r"//\s*PHASE5_CONF_FAIR_V2_BEGIN.*?//\s*PHASE5_CONF_FAIR_V2_END\s*",
        r"//\s*PHASE5_CONF_FAIR_V3_BEGIN.*?//\s*PHASE5_CONF_FAIR_V3_END\s*",
    ]
    for pat in pats:
        txt = re.sub(pat, "", txt, flags=re.S)
    return txt

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()
    txt = remove_old(txt)

    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
    ins = m.end()
    txt = txt[:ins] + "\n" + BLOCK + "\n" + txt[ins:]

    if 'cmd.AddValue("enableTrustConfidence"' not in txt:
        mm = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
        if mm:
            pos = mm.end()
            add = (
                '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n'
                '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
                '  cmd.AddValue("badChannelLossThresh", "Loss threshold to treat channel as bad", g_badChannelLossThresh);\n'
                '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
            )
            txt = txt[:pos] + add + txt[pos:]

    if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
        mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
        if mp:
            pos = mp.end()
            txt = txt[:pos] + "  g_obsCount.assign(g_nVehicles, 0);\n" + txt[pos:]

    if "PrintPhase5Stats();" not in txt:
        mr = re.search(r"\s+return\s+0\s*;\s*\n\}", txt)
        if mr:
            pos = mr.start()
            txt = txt[:pos] + "  PrintPhase5Stats();\n" + txt[pos:]

    p.write_text(txt)
    print("[OK] Phase5 applied:", p)

