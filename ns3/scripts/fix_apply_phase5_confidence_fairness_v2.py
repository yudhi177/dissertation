from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

OLD_BLOCKS = [
    r"//\s*PHASE5_CONF_FAIR_V1_BEGIN.*?//\s*PHASE5_CONF_FAIR_V1_END\s*",
    r"//\s*PHASE5_CONF_FAIR_V2_BEGIN.*?//\s*PHASE5_CONF_FAIR_V2_END\s*",
]

B = "// PHASE5_CONF_FAIR_V2_BEGIN"
E = "// PHASE5_CONF_FAIR_V2_END"

phase5_block = r'''
// PHASE5_CONF_FAIR_V2_BEGIN
// --- Phase 5: TrustConfidence gating + Channel-aware fairness ---
// NOTE: g_confWindow and g_confMinForFast already exist in this file -> DO NOT redeclare.

static bool     g_enableTrustConfidence = true;
static uint64_t g_fastDeniedLowConf = 0;

static bool     g_enableChannelFairness = true;
static double   g_badChannelLossThresh = 0.25;      // loss proxy threshold
static double   g_fairnessPenaltyScaleBad = 0.30;   // scale penalty under bad channel
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

static inline void RecordObservation(uint32_t id)
{
  if (id >= g_obsCount.size()) return;
  if (g_obsCount[id] < g_confWindow) g_obsCount[id]++;
}

// Loss proxy using existing global counters if available.
// We DO NOT introduce new counters here (compile-safe).
static inline double LossProxy()
{
  // If your file has g_txCount/g_rxCount (it likely does), this will compile.
  // If not, fallback to 0.0 using preprocessor-like trick is not possible;
  // instead we detect in python and patch a safe version below if needed.
  return 0.0;
}

// Apply fairness scaling to penalties
static inline double ApplyFairnessPenaltyScale(double basePenalty)
{
  if (!g_enableChannelFairness) return basePenalty;

  const double loss = LossProxy();
  if (loss > g_badChannelLossThresh)
  {
    g_fairnessBadChannelHits++;
    return basePenalty * g_fairnessPenaltyScaleBad;
  }
  return basePenalty;
}

// Print once at end (avoid -Werror unused)
static inline void PrintPhase5Stats()
{
  std::cout << "[PHASE5] enableConf=" << (g_enableTrustConfidence ? 1 : 0)
            << " fastDeniedLowConf=" << g_fastDeniedLowConf
            << " enableFair=" << (g_enableChannelFairness ? 1 : 0)
            << " badLossThresh=" << g_badChannelLossThresh
            << " penaltyScaleBad=" << g_fairnessPenaltyScaleBad
            << " fairnessBadHits=" << g_fairnessBadChannelHits
            << std::endl;
}
// PHASE5_CONF_FAIR_V2_END
'''

def ensure_include(txt: str, header: str) -> str:
    if header in txt:
        return txt
    if "#include <iostream>" in txt:
        return txt.replace("#include <iostream>\n", "#include <iostream>\n"+header+"\n", 1)
    return header + "\n" + txt

def find_addvalue_arg(txt: str, key: str):
    # cmd.AddValue("payloadSize", "...", g_payloadSize);
    m = re.search(r'cmd\.AddValue\(\s*"' + re.escape(key) + r'"\s*,[^,]*,\s*([A-Za-z_]\w*)\s*\)\s*;', txt)
    return m.group(1) if m else None

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    # 1) remove old phase5 blocks
    for pat in OLD_BLOCKS:
        txt = re.sub(pat, "", txt, flags=re.S)

    # 2) includes
    txt = ensure_include(txt, "#include <vector>")

    # 3) insert AFTER existing g_confMinForFast declaration (prevents undeclared + prevents redeclare)
    # find line like: static double g_confMinForFast = ...
    m = re.search(r'^\s*static\s+double\s+g_confMinForFast\s*=\s*[^;]+;\s*$', txt, flags=re.M)
    if not m:
        raise SystemExit(f"[ERR] g_confMinForFast declaration not found in {p}")

    insert_pos = m.end()
    txt = txt[:insert_pos] + "\n" + phase5_block + "\n" + txt[insert_pos:]

    # 4) patch LossProxy() to use g_txCount/g_rxCount ONLY if they exist
    has_tx = re.search(r'^\s*static\s+uint64_t\s+g_txCount\b', txt, flags=re.M) is not None
    has_rx = re.search(r'^\s*static\s+uint64_t\s+g_rxCount\b', txt, flags=re.M) is not None
    if has_tx and has_rx:
        loss_impl = r'''
static inline double LossProxy()
{
  if (g_txCount == 0) return 0.0;
  double p = double(g_rxCount) / double(g_txCount);
  if (p < 0.0) p = 0.0;
  if (p > 1.0) p = 1.0;
  return 1.0 - p;
}
'''
        txt = re.sub(r'static\s+inline\s+double\s+LossProxy\s*\(\s*\)\s*\{.*?\n\}\s*',
                     loss_impl.strip(), txt, flags=re.S)

    # 5) cmd flags (add if missing)
    if 'cmd.AddValue("enableTrustConfidence"' not in txt:
        # insert near confMinForFast AddValue if present
        a = re.search(r'cmd\.AddValue\(\s*"confMinForFast".*?\);\s*\n', txt, flags=re.S)
        if a:
            pos = a.end()
            add = '  cmd.AddValue("enableTrustConfidence", "Enable confidence gating 0/1", g_enableTrustConfidence);\n'
            txt = txt[:pos] + add + txt[pos:]

    if 'cmd.AddValue("enableChannelFairness"' not in txt:
        a = re.search(r'cmd\.AddValue\(\s*"confMinForFast".*?\);\s*\n', txt, flags=re.S)
        if a:
            pos = a.end()
            add = (
                '  cmd.AddValue("enableChannelFairness", "Enable channel-aware fairness 0/1", g_enableChannelFairness);\n'
                '  cmd.AddValue("badChannelLossThresh", "Loss-proxy threshold for bad channel", g_badChannelLossThresh);\n'
                '  cmd.AddValue("fairnessPenaltyScaleBad", "Penalty scaling under bad channel", g_fairnessPenaltyScaleBad);\n'
            )
            txt = txt[:pos] + add + txt[pos:]

    # 6) init g_obsCount after cmd.Parse
    if "g_obsCount.assign(g_nVehicles, 0);" not in txt:
        mp = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
        if mp:
            pos = mp.end()
            txt = txt[:pos] + "  // PHASE5: init confidence observation counters\n  g_obsCount.assign(g_nVehicles, 0);\n" + txt[pos:]

    # 7) call PrintPhase5Stats() once near end (after other summary prints if possible)
    if "PrintPhase5Stats();" not in txt:
        # safest place: just before 'return 0;' in main
        mr = re.search(r"return\s+0\s*;\s*\n\}", txt)
        if mr:
            pos = mr.start()
            txt = txt[:pos] + "  PrintPhase5Stats();\n" + txt[pos:]

    p.write_text(txt)
    print("[OK] Phase5 V2 applied:", p)

