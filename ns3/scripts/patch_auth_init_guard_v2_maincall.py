from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Remove older V2 block if exists
    txt = re.sub(r"// AUTH_INIT_GUARD_V2_BEGIN.*?// AUTH_INIT_GUARD_V2_END\s*", "", txt, flags=re.S)

    # Ensure forward decl exists (safe) if not present
    if "AuthInitKeys(" in txt and "static void AuthInitKeys(uint32_t" not in txt:
        m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
        if not m:
            raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
        ins = m.end()
        txt = txt[:ins] + "\nstatic void AuthInitKeys(uint32_t nVehicles);\n" + txt[ins:]

    # Insert guard flag near using namespace
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
    ins = m.end()

    block = r'''
// AUTH_INIT_GUARD_V2_BEGIN
static bool g_authKeysReady = false;
// AUTH_INIT_GUARD_V2_END
'''
    txt = txt[:ins] + block + txt[ins:]

    # Wire init in main AFTER cmd.Parse(argc, argv);
    # We only init if auth probe enabled (so arrays ready before scheduling)
    if "cmd.Parse(argc, argv);" not in txt:
        raise SystemExit(f"[ERR] cmd.Parse(argc, argv); not found in {p}")

    hook = r'''
  // AUTH_INIT_GUARD_V2: initialize auth keys once (needed for auth probe / replay / mitm tests)
  if (g_enableAuthProbe && !g_authKeysReady)
  {
    AuthInitKeys(g_nVehicles);
    g_authKeysReady = true;
  }
'''
    if hook.strip() not in txt:
        txt = txt.replace("cmd.Parse(argc, argv);", "cmd.Parse(argc, argv);\n" + hook, 1)

    p.write_text(txt)
    print("[OK] auth init wired in main:", p)
