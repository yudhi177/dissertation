from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove old block if any
    txt = re.sub(r"// TRUST_CONF_V1_BEGIN.*?// TRUST_CONF_V1_END\s*", "", txt, flags=re.S)

    # Insert globals near trust globals: after enableTrustEngineFinal if found
    m = re.search(r"static\s+bool\s+g_enableTrustEngineFinal.*?\n", txt)
    if not m:
        raise SystemExit(f"[ERR] could not find g_enableTrustEngineFinal in {p}")
    ins = m.end()

    block = r'''
// TRUST_CONF_V1_BEGIN
// Observation-based trust confidence (0..1)
static uint32_t g_confWindow = 20;        // observations needed for full confidence
static double   g_confMinForFast = 0.6;   // FAST allowed only if conf >= this

static std::vector<uint32_t> g_trustObs;  // per-vehicle observation count
static std::vector<double>   g_trustConf; // per-vehicle confidence 0..1

static inline double ComputeConf(uint32_t obs, uint32_t win)
{
  if (win == 0) return 1.0;
  double c = double(obs) / double(win);
  if (c < 0.0) c = 0.0;
  if (c > 1.0) c = 1.0;
  return c;
}
// TRUST_CONF_V1_END
'''
    txt = txt[:ins] + block + txt[ins:]

    # Add cmd flags if missing
    if 'cmd.AddValue("confWindow"' not in txt:
        txt = txt.replace('cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);',
                          'cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);\n'
                          '  cmd.AddValue("confWindow", "Trust confidence window (observations)", g_confWindow);\n'
                          '  cmd.AddValue("confMinForFast", "Min confidence to allow FAST", g_confMinForFast);\n', 1)

    # Initialize vectors where trust vectors are initialized (look for g_trustScore.assign)
    if "g_trustObs.assign" not in txt:
        txt = txt.replace("g_trustScore.assign(g_nVehicles, 0.80);",
                          "g_trustScore.assign(g_nVehicles, 0.80);\n"
                          "  g_trustObs.assign(g_nVehicles, 0);\n"
                          "  g_trustConf.assign(g_nVehicles, 0.0);\n", 1)

    # Update confidence inside TrustRecompute (increment obs and compute conf)
    # Insert after g_trustScore[v] is updated (look for g_trustScore[v] = Clamp01)
    if "g_trustObs[v]++" not in txt:
        txt = txt.replace("g_trustScore[v] = Clamp01(Ti);",
                          "g_trustScore[v] = Clamp01(Ti);\n"
                          "  if (v < g_trustObs.size()) {\n"
                          "    g_trustObs[v]++;\n"
                          "    g_trustConf[v] = ComputeConf(g_trustObs[v], g_confWindow);\n"
                          "  }\n", 1)

    p.write_text(txt)
    print("[OK] Patched trustConfidence into:", p)
