from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove any older PHASE5 blocks if present
txt = re.sub(r"//\s*PHASE5_CONF_FAIR_V[0-9]+_BEGIN.*?//\s*PHASE5_CONF_FAIR_V[0-9]+_END\s*",
             "", txt, flags=re.S)

# ensure include
if "#include <vector>" not in txt:
    if "#include <iostream>\n" in txt:
        txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <vector>\n", 1)
    else:
        txt = "#include <vector>\n" + txt

# find conf vars in scratch (they MUST exist already)
m1 = re.search(r"^\s*static\s+uint32_t\s+g_confWindow\s*=.*?;\s*$", txt, flags=re.M)
m2 = re.search(r"^\s*static\s+double\s+g_confMinForFast\s*=.*?;\s*$", txt, flags=re.M)
if not (m1 and m2):
    raise SystemExit("[ERR] g_confWindow / g_confMinForFast not found in scratch file (restore correct base first)")

# find tx/rx counters (your file usually has txCount/rxCount; accept both)
mtx = re.search(r"^\s*static\s+uint64_t\s+g_txCount\s*=.*?;\s*$", txt, flags=re.M)
mrx = re.search(r"^\s*static\s+uint64_t\s+g_rxCount\s*=.*?;\s*$", txt, flags=re.M)
if not (mtx and mrx):
    raise SystemExit("[ERR] g_txCount / g_rxCount not found in scratch file (check variable names)")

ins = max(m1.end(), m2.end(), mtx.end(), mrx.end())

BLOCK = r'''
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
  // touch helpers => never unused in debug -Werror
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

txt = txt[:ins] + "\n" + BLOCK + "\n" + txt[ins:]

# add cmd flags near existing confMinForFast
if 'cmd.AddValue("enableTrustConfidence"' not in txt:
    mm = re.search(r'cmd\.AddValue\("confMinForFast".*?\);\s*\n', txt)
    if not mm:
        raise SystemExit("[ERR] cmd.AddValue(confMinForFast...) not found")
    pos = mm.end()
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
    if not mp:
        raise SystemExit("[ERR] cmd.Parse(argc, argv) not found")
    txt = txt[:mp.end()] + "  g_obsCount.assign(g_nVehicles, 0);\n" + txt[mp.end():]

# print stats before return 0
if "PrintPhase5Stats();" not in txt:
    mr = re.search(r"\n\s*return\s+0\s*;\s*\n\}", txt)
    if not mr:
        raise SystemExit("[ERR] return 0 not found")
    txt = txt[:mr.start()] + "  PrintPhase5Stats();\n" + txt[mr.start():]

p.write_text(txt)
print("[OK] Phase5 block applied (scratch only):", p)
