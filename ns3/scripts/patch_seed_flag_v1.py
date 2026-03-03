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

    # remove older block
    txt = re.sub(r"// SEED_FLAG_V1_BEGIN.*?// SEED_FLAG_V1_END\s*", "", txt, flags=re.S)

    # insert seed global after baseline block or near top
    anchor = re.search(r"// BASELINE_ASSERTS_V1_END\s*\n", txt)
    if not anchor:
        anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not anchor:
        raise SystemExit("[ERR] Cannot find anchor for seed insertion")

    ins = anchor.end()
    txt = txt[:ins] + r'''
// SEED_FLAG_V1_BEGIN
static uint32_t g_seed = 1;
// SEED_FLAG_V1_END
''' + txt[ins:]

    # add cmd flag near baselineName
    if 'cmd.AddValue("seed"' not in txt:
        m2 = re.search(r'cmd\.AddValue\("baselineName".*?\);\s*\n', txt)
        if not m2:
            raise SystemExit("[ERR] baselineName cmd flag not found; apply baseline asserts patch first.")
        pos2 = m2.end()
        txt = txt[:pos2] + '  cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);\n' + txt[pos2:]

    # apply seed after cmd.Parse: SeedManager::SetSeed + SetRun
    if "SeedManager::SetSeed" not in txt:
        txt = txt.replace("AssertBaselineConfig();", "AssertBaselineConfig();\n  SeedManager::SetSeed(g_seed);\n  SeedManager::SetRun(g_seed);")

    p.write_text(txt)
    print("[OK] Seed flag added in:", p)
