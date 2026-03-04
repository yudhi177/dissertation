from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

BLOCK = r'''
// BASELINE_ASSERTS_V2_BEGIN
static std::string g_baselineName = "UNSET";

static void AssertBaselineConfig()
{
  if (g_baselineName == "PKI_ONLY")
  {
    NS_ABORT_MSG_IF(g_enableTrustEngineFinal, "PKI_ONLY violation: trust must be OFF");
    NS_ABORT_MSG_IF(g_enableBlockchain, "PKI_ONLY violation: blockchain must be OFF");
    NS_ABORT_MSG_IF(g_enableRevocation, "PKI_ONLY violation: revocation must be OFF");
    NS_ABORT_MSG_IF(g_enablePrivacy, "PKI_ONLY violation: privacy must be OFF");
    NS_ABORT_MSG_IF(g_enableBcProbe, "PKI_ONLY violation: bcProbe must be OFF");
    NS_ABORT_MSG_IF(g_enableBCLocalCache, "PKI_ONLY violation: bcCache must be OFF");
  }
  else if (g_baselineName == "TRUST_ONLY")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "TRUST_ONLY violation: trust must be ON");
    NS_ABORT_MSG_IF(g_enableBlockchain, "TRUST_ONLY violation: blockchain must be OFF");
    NS_ABORT_MSG_IF(g_enableRevocation, "TRUST_ONLY violation: revocation must be OFF");
    NS_ABORT_MSG_IF(g_enablePrivacy, "TRUST_ONLY violation: privacy must be OFF");
    NS_ABORT_MSG_IF(g_enableBcProbe, "TRUST_ONLY violation: bcProbe must be OFF");
    NS_ABORT_MSG_IF(g_enableBCLocalCache, "TRUST_ONLY violation: bcCache must be OFF");
  }
  else if (g_baselineName == "BC_TRUST")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "BC_TRUST violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain, "BC_TRUST violation: blockchain must be ON");
  }
  else if (g_baselineName == "BC_ALWAYS_QUERY")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "BC_ALWAYS_QUERY violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain, "BC_ALWAYS_QUERY violation: blockchain must be ON");
    NS_ABORT_MSG_IF(g_enableBCLocalCache, "BC_ALWAYS_QUERY violation: cache must be OFF");
    NS_ABORT_MSG_IF(!g_enableBcProbe, "BC_ALWAYS_QUERY violation: probe should be ON");
  }
  else if (g_baselineName == "FULL")
  {
    NS_ABORT_MSG_IF(!g_enableTrustEngineFinal, "FULL violation: trust must be ON");
    NS_ABORT_MSG_IF(!g_enableBlockchain, "FULL violation: blockchain must be ON");
    NS_ABORT_MSG_IF(!g_enableRevocation, "FULL violation: revocation must be ON");
    NS_ABORT_MSG_IF(!g_enablePrivacy, "FULL violation: privacy must be ON");
  }
}
// BASELINE_ASSERTS_V2_END
'''

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove any older baseline assert blocks (v1/v2)
    txt = re.sub(r"// BASELINE_ASSERTS_V1_BEGIN.*?// BASELINE_ASSERTS_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// BASELINE_ASSERTS_V2_BEGIN.*?// BASELINE_ASSERTS_V2_END\s*", "", txt, flags=re.S)

    # insert just before main
    m = re.search(r"\nint\s+main\s*\(", txt)
    if not m:
        raise SystemExit(f"[ERR] main() not found in {p}")
    ins = m.start()
    txt = txt[:ins] + "\n" + BLOCK + "\n" + txt[ins:]

    # ensure cmd.AddValue baselineName exists
    if 'cmd.AddValue("baselineName"' not in txt:
        m2 = re.search(r"CommandLine\s+cmd\s*;\s*\n", txt)
        if not m2:
            raise SystemExit(f"[ERR] CommandLine cmd not found in {p}")
        pos2 = m2.end()
        txt = txt[:pos2] + '  cmd.AddValue("baselineName", "Baseline name (PKI_ONLY/TRUST_ONLY/BC_TRUST/BC_ALWAYS_QUERY/FULL)", g_baselineName);\n' + txt[pos2:]

    # ensure AssertBaselineConfig called after cmd.Parse
    txt = re.sub(r'^\s*AssertBaselineConfig\(\);\s*\n', '', txt, flags=re.M)
    txt = txt.replace("cmd.Parse(argc, argv);", "cmd.Parse(argc, argv);\n  AssertBaselineConfig();", 1)

    p.write_text(txt)
    print("[OK] baseline asserts fixed in:", p)
