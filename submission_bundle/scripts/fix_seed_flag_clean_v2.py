from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

SEED_BLOCK = r'''
// SEED_FLAG_V1_BEGIN
static uint32_t g_seed = 1;
// SEED_FLAG_V1_END
'''

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove old seed blocks
    txt = re.sub(r"// SEED_FLAG_V1_BEGIN.*?// SEED_FLAG_V1_END\s*", "", txt, flags=re.S)

    # insert seed block right after baseline asserts block (or before main)
    anchor = re.search(r"// BASELINE_ASSERTS_V1_END\s*\n", txt)
    if not anchor:
        anchor = re.search(r"\nint\s+main\s*\(", txt)
    if not anchor:
        raise SystemExit(f"[ERR] cannot find anchor in {p}")
    pos = anchor.end()
    txt = txt[:pos] + SEED_BLOCK + txt[pos:]

    # ensure cmd flag seed exists
    if 'cmd.AddValue("seed"' not in txt:
        m = re.search(r'cmd\.AddValue\("baselineName".*?\);\s*\n', txt, flags=re.M)
        if not m:
            raise SystemExit(f"[ERR] baselineName cmd.AddValue not found in {p}")
        pos2 = m.end()
        txt = txt[:pos2] + '  cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);\n' + txt[pos2:]

    # ensure SeedManager set exactly once (remove duplicates then insert once)
    txt = re.sub(r'^\s*SeedManager::SetSeed\(g_seed\);\s*\n', '', txt, flags=re.M)
    txt = re.sub(r'^\s*SeedManager::SetRun\(g_seed\);\s*\n', '', txt, flags=re.M)

    # insert after AssertBaselineConfig call
    txt = txt.replace("AssertBaselineConfig();",
                      "AssertBaselineConfig();\n  SeedManager::SetSeed(g_seed);\n  SeedManager::SetRun(g_seed);", 1)

    p.write_text(txt)
    print("[OK] Clean seed flag wired in:", p)
