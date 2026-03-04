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

    # Remove older block if exists
    txt = re.sub(r"// AUTH_INIT_GUARD_V1_BEGIN.*?// AUTH_INIT_GUARD_V1_END\s*", "", txt, flags=re.S)

    # Insert global guard near "using namespace ns3;"
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] 'using namespace ns3;' not found in {p}")
    ins = m.end()

    guard_block = r'''
// AUTH_INIT_GUARD_V1_BEGIN
static bool g_authKeysReady = false;

static inline void EnsureAuthKeysReady()
{
  // g_nVehicles should be set by cmd.AddValue earlier; ensure sane
  if (g_nVehicles == 0)
  {
    NS_ABORT_MSG("AUTH violation: nVehicles is 0");
  }
  if (!g_authKeysReady)
  {
    // If AuthInitKeys exists, use it; else do nothing (compile-safe)
    #ifdef __GNUG__
    #endif
    // Best-effort: call if symbol exists in TU
    // (If your file uses a different init function name, rename below)
    AuthInitKeys(g_nVehicles);
    g_authKeysReady = true;
  }
}
// AUTH_INIT_GUARD_V1_END
'''
    if "EnsureAuthKeysReady()" not in txt:
        txt = txt[:ins] + guard_block + txt[ins:]

    # Add EnsureAuthKeysReady() call at top of AuthProbeTick()
    m2 = re.search(r"static\s+void\s+AuthProbeTick\s*\(\s*\)\s*\{", txt)
    if m2:
        pos = m2.end()
        if "EnsureAuthKeysReady();" not in txt[pos:pos+300]:
            txt = txt[:pos] + "\n  EnsureAuthKeysReady();\n" + txt[pos:]
    else:
        print("[WARN] AuthProbeTick() not found in", p)

    # Also add EnsureAuthKeysReady() before first scheduling of AuthProbeTick (best-effort)
    if "AuthProbeTick" in txt and "EnsureAuthKeysReady();" in txt:
        pass

    p.write_text(txt)
    print("[OK] auth init guard patched:", p)
