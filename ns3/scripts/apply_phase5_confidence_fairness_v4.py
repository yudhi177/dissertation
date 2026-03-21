from pathlib import Path
import re

targets = [
  Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
  Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def ensure_include(txt: str, inc: str) -> str:
  if inc in txt:
    return txt
  if "#include <iostream>" in txt:
    return txt.replace("#include <iostream>\n", "#include <iostream>\n" + inc + "\n", 1)
  return inc + "\n" + txt

block = r'''
// PHASE5_CONF_FAIR_V4_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness (SAFE) ---

static bool     g_enableTrustConfidence = true;
static uint64_t g_fastDeniedLowConf = 0;

static bool     g_enableChannelFairness = true;
static double   g_badChannelLossThresh = 0.25;
static double   g_fairnessPenaltyScaleBad = 0.30;
static uint64_t g_fairnessBadChannelHits = 0;

// Manual loss proxy [0..1] for experiments (avoids tx/rx globals)
static double   g_lossProxy = 0.0;

// Per-vehicle observation count
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

static inline double ApplyFairnessPenaltyScale(double basePenalty)
{
  if (!g_enableChannelFairness) return basePenalty;

  double loss = g_lossProxy;
  if (loss < 0.0) loss = 0.0;
  if (loss > 1.0) loss = 1.0;

  if (loss > g_badChannelLossThresh)
  {
    g_fairnessBadChannelHits++;
    return basePenalty * g_fairnessPenaltyScaleBad;
  }
  return basePenalty;
}

static inline void PrintPhase5Stats()
{
  std::cout << "[PHASE5] fastDeniedLowConf=" << g_fastDeniedLowConf
            << " fairnessBadChannelHits=" << g_fairnessBadChannelHits
            << " confOn=" << (g_enableTrustConfidence ? 1 : 0)
            << " fairOn=" << (g_enableChannelFairness ? 1 : 0)
            << " lossProxy=" << g_lossProxy
            << std::endl;
}
// PHASE5_CONF_FAIR_V4_END
'''

for p in targets:
  if not p.exists():
    continue

  txt = p.read_text()
  txt = ensure_include(txt, "#include <vector>")

  # remove any older phase5 blocks
  txt = re.sub(r"// PHASE5_CONF_FAIR_V1_BEGIN.*?// PHASE5_CONF_FAIR_V1_END\s*", "", txt, flags=re.S)
  txt = re.sub(r"// PHASE5_CONF_FAIR_V2_BEGIN.*?// PHASE5_CONF_FAIR_V2_END\s*", "", txt, flags=re.S)
  txt = re.sub(r"// PHASE5_CONF_FAIR_V3_BEGIN.*?// PHASE5_CONF_FAIR_V3_END\s*", "", txt, flags=re.S)
  txt = re.sub(r"// PHASE5_CONF_FAIR_V4_BEGIN.*?// PHASE5_CONF_FAIR_V4_END\s*", "", txt, flags=re.S)

  # insert after g_confMinForFast definition
  anchor = re.search(r"^\s*static\s+double\s+g_confMinForFast\s*=\s*.*?;\s*$", txt, flags=re.M)
  if not anchor:
    raise SystemExit(f"[ERR] g_confMinForFast not found in {p}")

  pos = txt.find("\n", anchor.end())
  if pos == -1:
    pos = anchor.end()

  txt = txt[:pos+1] + block + txt[pos+1:]

  # init obsCount after cmd.Parse
  if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
    mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
    if mp:
      ip = mp.end()
      txt = txt[:ip] + "  // PHASE5 init\n  g_obsCount.assign(g_nVehicles, 0);\n" + txt[ip:]

  # add CLI flags (insert after confMinForFast AddValue)
  if 'cmd.AddValue("enableTrustConfidence"' not in txt:
    add_anchor = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
    if add_anchor:
      ip = add_anchor.end()
      txt = txt[:ip] + '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n' + txt[ip:]

  # add fairness flags (insert after trustDecayPerSec AddValue)
  if 'cmd.AddValue("enableChannelFairness"' not in txt:
    add_anchor = re.search(r'cmd\.AddValue\("trustDecayPerSec".*?\);\s*\n', txt)
    if add_anchor:
      ip = add_anchor.end()
      txt = txt[:ip] + (
        '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
        '  cmd.AddValue("badChannelLossThresh", "Loss threshold to treat channel as bad", g_badChannelLossThresh);\n'
        '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
        '  cmd.AddValue("lossProxy", "Manual loss proxy [0..1] for fairness experiments", g_lossProxy);\n'
      ) + txt[ip:]

  # print stats before Simulator::Run
  if "PrintPhase5Stats();" not in txt:
    mrun = re.search(r"\bSimulator::Run\(\);\s*\n", txt)
    if mrun:
      txt = txt[:mrun.start()] + "  PrintPhase5Stats();\n" + txt[mrun.start():]

  p.write_text(txt)
  print("[OK] Phase5 V4 applied:", p)
