from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Remove any previous (partial) authProbe flags if present to avoid duplicates
txt = re.sub(r'^\s*cmd\.AddValue\("enableAuthProbe".*?\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\("authProbeIntervalMs".*?\);\s*\n', '', txt, flags=re.M)

flags = r'''
  cmd.AddValue("enableAuthProbe", "Generate periodic auth handshakes (to measure AUTH stats)", g_enableAuthProbe);
  cmd.AddValue("authProbeIntervalMs", "Auth probe interval per vehicle (ms)", g_authProbeIntervalMs);
'''

# 2) Insert flags right after enableMitmAttack if found, else after enableAuthBind, else before cmd.Parse
m = re.search(r'^\s*cmd\.AddValue\("enableMitmAttack".*?\);\s*\n', txt, flags=re.M)
if m:
    pos = m.end()
    txt = txt[:pos] + flags + txt[pos:]
else:
    m = re.search(r'^\s*cmd\.AddValue\("enableAuthBind".*?\);\s*\n', txt, flags=re.M)
    if m:
        pos = m.end()
        txt = txt[:pos] + flags + txt[pos:]
    else:
        m = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
        if not m:
            raise SystemExit("[ERR] Could not find cmd.Parse(argc, argv); to insert flags.")
        pos = m.start()
        txt = txt[:pos] + flags + txt[pos:]

# 3) Ensure StartAuthProbes() is called once
if "StartAuthProbes();" not in txt:
    if "  StartBcProbes();" in txt:
        txt = txt.replace("  StartBcProbes();", "  StartBcProbes();\n  StartAuthProbes();", 1)
    elif "  PrivacyInit();" in txt:
        txt = txt.replace("  PrivacyInit();", "  PrivacyInit();\n  StartAuthProbes();", 1)
    else:
        txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                          "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  StartAuthProbes();", 1)

p.write_text(txt)
print("[OK] Added enableAuthProbe/authProbeIntervalMs flags + ensured StartAuthProbes() call:", p)
