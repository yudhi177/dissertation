from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

BASELINE_BLOCK = r'''
// BASELINE_ASSERTS_V1_BEGIN
static std::string g_baselineName = "UNSET";

static void AssertBaselineConfig()
{
  if (g_baselineName == "PKI_ONLY")
  {
    NS_ABORT_MSG_IF(g_enableTrustEngineFinal, "PKI_ONLY violation: trust must be OFF");
    NS_ABORT_MSG_IF(g_enableBlockchain,      "PKI_ONLY violation: blockchain must be OFF");
    NS_ABORT_MSG_IF(g_enableRevocation,      "PKI_ONLY violation: revocation must be OFF");
    NS_ABORT_MSG_IF(g_enablePrivacy,         "PKI_ONLY violation: privacy must be OFF");
    NS_ABORT_MSG_IF(g_enableBcProbe,         "PKI_ONLY violation: bcProbe must be OFF");
    NS_ABORT_MSG_IF(g_enableBCLocalCache,    "PKI_ONLY violation: bcCache must be OFF");
  }
  else if (g_baselineName == "TRUST_ONLY")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "TRUST_ONLY violation: trust must be ON");
    NS_ABORT_MSG_IF(g_enableBlockchain,        "TRUST_ONLY violation: blockchain must be OFF");
    NS_ABORT_MSG_IF(g_enableRevocation,        "TRUST_ONLY violation: revocation must be OFF");
    NS_ABORT_MSG_IF(g_enablePrivacy,           "TRUST_ONLY violation: privacy must be OFF");
    NS_ABORT_MSG_IF(g_enableBcProbe,           "TRUST_ONLY violation: bcProbe must be OFF");
    NS_ABORT_MSG_IF(g_enableBCLocalCache,      "TRUST_ONLY violation: bcCache must be OFF");
  }
  else if (g_baselineName == "BC_TRUST")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "BC_TRUST violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain,       "BC_TRUST violation: blockchain must be ON");
  }
  else if (g_baselineName == "BC_ALWAYS_QUERY")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "BC_ALWAYS_QUERY violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain,       "BC_ALWAYS_QUERY violation: blockchain must be ON");
    NS_ABORT_MSG_IF(g_enableBCLocalCache,      "BC_ALWAYS_QUERY violation: cache must be OFF");
    NS_ABORT_MSG_IF(!g_enableBcProbe,          "BC_ALWAYS_QUERY violation: probe should be ON");
  }
  else if (g_baselineName == "FULL")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "FULL violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain,       "FULL violation: blockchain must be ON");
    NS_ABORT_MSG_IF(!g_enableRevocation,       "FULL violation: revocation must be ON");
    NS_ABORT_MSG_IF(!g_enablePrivacy,          "FULL violation: privacy must be ON");
  }
}
// BASELINE_ASSERTS_V1_END
'''

SEED_BLOCK = r'''
// SEED_FLAG_V1_BEGIN
static uint32_t g_seed = 1;
// SEED_FLAG_V1_END
'''

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # 1) Remove any existing baseline/seed blocks (even if duplicated)
    txt = re.sub(r"// BASELINE_ASSERTS_V1_BEGIN.*?// BASELINE_ASSERTS_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// SEED_FLAG_V1_BEGIN.*?// SEED_FLAG_V1_END\s*", "", txt, flags=re.S)

    # 2) Remove duplicate cmd.AddValue lines
    txt = re.sub(r'^\s*cmd\.AddValue\("baselineName".*?\);\s*\n', "", txt, flags=re.M)
    txt = re.sub(r'^\s*cmd\.AddValue\("seed".*?\);\s*\n', "", txt, flags=re.M)

    # 3) Remove duplicate calls
    txt = re.sub(r'^\s*AssertBaselineConfig\(\);\s*\n', "", txt, flags=re.M)
    txt = re.sub(r'^\s*SeedManager::SetSeed\(g_seed\);\s*\n', "", txt, flags=re.M)
    txt = re.sub(r'^\s*SeedManager::SetRun\(g_seed\);\s*\n', "", txt, flags=re.M)

    # 4) Insert baseline+seed blocks just before main()
    mmain = re.search(r"\nint\s+main\s*\(", txt)
    if not mmain:
        raise SystemExit(f"[ERR] main() not found in {p}")
    ins = mmain.start()
    txt = txt[:ins] + "\n" + BASELINE_BLOCK + "\n" + SEED_BLOCK + "\n" + txt[ins:]

    # 5) Add cmd.AddValue flags after eventsOut if possible
    m_evt = re.search(r'^\s*cmd\.AddValue\("eventsOut".*?\);\s*$', txt, flags=re.M)
    if m_evt:
        pos = m_evt.end()
        txt = txt[:pos] + '\n  cmd.AddValue("baselineName", "Baseline label for assertions (PKI_ONLY/TRUST_ONLY/BC_TRUST/BC_ALWAYS_QUERY/FULL)", g_baselineName);\n' + txt[pos:]
        txt = txt[:pos] + '\n  cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);\n' + txt[pos:]
    else:
        # fallback: insert before cmd.Parse
        m_parse = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
        if not m_parse:
            raise SystemExit(f"[ERR] cmd.Parse not found in {p}")
        pos = m_parse.start()
        inject = '  cmd.AddValue("baselineName", "Baseline label for assertions (PKI_ONLY/TRUST_ONLY/BC_TRUST/BC_ALWAYS_QUERY/FULL)", g_baselineName);\n' \
                 '  cmd.AddValue("seed", "Global deterministic seed for all RNG", g_seed);\n'
        txt = txt[:pos] + inject + txt[pos:]

    # 6) Insert calls right after cmd.Parse(...)
    def insert_after_parse(s: str) -> str:
        if "cmd.Parse(argc, argv);" in s:
            return s.replace("cmd.Parse(argc, argv);",
                             "cmd.Parse(argc, argv);\n  AssertBaselineConfig();\n  SeedManager::SetSeed(g_seed);\n  SeedManager::SetRun(g_seed);",
                             1)
        if "cmd.Parse (argc, argv);" in s:
            return s.replace("cmd.Parse (argc, argv);",
                             "cmd.Parse (argc, argv);\n  AssertBaselineConfig();\n  SeedManager::SetSeed(g_seed);\n  SeedManager::SetRun(g_seed);",
                             1)
        return s

    txt = insert_after_parse(txt)

    p.write_text(txt)
    print("[OK] Repaired baseline+seed blocks in:", p)
