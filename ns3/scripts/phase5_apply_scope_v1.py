from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

PH5 = r'''
// PHASE5_CONF_FAIR_V5_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness ---
// NOTE: g_confWindow + g_confMinForFast already exist (DO NOT redeclare).

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
  if (g_txCount > 0)
  {
    loss = 1.0 - (double(g_rxCount) / double(g_txCount));
  }

  if (loss > g_badChannelLossThresh)
  {
    g_fairnessBadChannelHits++;
    return penalty * g_fairnessPenaltyScaleBad;
  }
  return penalty;
}

static inline void PrintPhase5Stats()
{
  // Touch helpers so debug -Werror never flags unused
  (void)ApplyFairnessPenaltyScale(0.0);
  double c0 = (g_obsCount.empty() ? 0.0 : TrustConfidence(0));

  std::cout << "[PHASE5] fastDeniedLowConf=" << g_fastDeniedLowConf
            << " fairnessBadChannelHits=" << g_fairnessBadChannelHits
            << " confOn=" << (g_enableTrustConfidence ? 1 : 0)
            << " fairOn=" << (g_enableChannelFairness ? 1 : 0)
            << " conf0=" << c0
            << std::endl;
}
// PHASE5_CONF_FAIR_V5_END
'''

def ensure_include(txt: str, inc: str) -> str:
  if inc in txt:
    return txt
  if "#include <iostream>" in txt:
    return txt.replace("#include <iostream>\n", "#include <iostream>\n"+inc+"\n", 1)
  return inc+"\n"+txt

for p in targets:
  if not p.exists():
    continue
  txt = p.read_text()
  txt = ensure_include(txt, "#include <vector>")

  # insert AFTER these declarations (must exist)
  anchors = []
  for rgx in [
    r"^\s*static\s+uint32_t\s+g_confWindow\s*=.*?;\s*$",
    r"^\s*static\s+double\s+g_confMinForFast\s*=.*?;\s*$",
    r"^\s*static\s+uint64_t\s+g_txCount\s*=.*?;\s*$",
    r"^\s*static\s+uint64_t\s+g_rxCount\s*=.*?;\s*$",
  ]:
    m = re.search(rgx, txt, flags=re.M)
    if m:
      anchors.append(m.end())

  if not anchors:
    raise SystemExit(f"[ERR] missing confWindow/confMinForFast or tx/rx counters in {p}")

  ins = max(anchors)
  txt = txt[:ins] + "\n" + PH5 + "\n" + txt[ins:]

  # cmd flags after confMinForFast AddValue (fallback confWindow)
  if 'cmd.AddValue("enableTrustConfidence"' not in txt:
    m = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
    if not m:
      m = re.search(r'cmd\.AddValue\("confWindow".*?\);\s*\n', txt)
    if m:
      pos = m.end()
      add = (
        '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n'
        '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
        '  cmd.AddValue("badChannelLossThresh", "Loss threshold to treat channel as bad", g_badChannelLossThresh);\n'
        '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
      )
      txt = txt[:pos] + add + txt[pos:]

  # init obsCount after cmd.Parse
  if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
    mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
    if mp:
      txt = txt[:mp.end()] + "  g_obsCount.assign(g_nVehicles, 0);\n" + txt[mp.end():]

  # print stats before return 0
  if "PrintPhase5Stats();" not in txt:
    mr = re.search(r"\n\s*return\s+0\s*;\s*\n\}", txt)
    if mr:
      txt = txt[:mr.start()] + "  PrintPhase5Stats();\n" + txt[mr.start():]

  p.write_text(txt)
  print("[OK] Phase5 applied:", p)
