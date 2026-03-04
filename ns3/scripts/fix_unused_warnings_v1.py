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

    # ---------------------------
    # 1) freshOk unused warning fix
    # ---------------------------
    # Remove existing (void)freshOk if already inserted
    txt = re.sub(r'^\s*\(void\)\s*freshOk\s*;\s*\n', '', txt, flags=re.M)

    # Insert "(void)freshOk;" right after freshOk declaration (if present)
    m = re.search(r'^(?P<indent>\s*)const\s+bool\s+freshOk\s*=\s*\(.*?\)\s*;\s*$',
                  txt, flags=re.M)
    if m:
        indent = m.group("indent")
        line_end = m.end()
        inject = f"\n{indent}(void)freshOk;"
        # only inject once
        if "(void)freshOk;" not in txt[m.start():m.start()+200]:
            txt = txt[:line_end] + inject + txt[line_end:]

    # ---------------------------
    # 2) AuthInitKeys unused function fix
    #    Best: call it inside StartAuthProbes() if available
    # ---------------------------
    if "AuthInitKeys" in txt:
        sm = re.search(r'(static\s+void\s+StartAuthProbes\s*\([^)]*\)\s*\{)', txt)
        if sm:
            pos = sm.end()
            hook = r'''
  // init deterministic auth keys once (removes unused warning + ensures stable auth)
  if (g_enableAuthProbe || g_enableAuthBind)
  {
    AuthInitKeys(g_nVehicles);
  }
'''
            if "AuthInitKeys(g_nVehicles)" not in txt[pos:pos+400]:
                txt = txt[:pos] + hook + txt[pos:]
        else:
            # fallback: silence the warning safely using C++ attribute (only if not already done)
            txt = re.sub(r'^\s*\[\[maybe_unused\]\]\s*static\s+void\s+AuthInitKeys',
                         '[[maybe_unused]] static void AuthInitKeys', txt, flags=re.M)
            txt = re.sub(r'^\s*static\s+void\s+AuthInitKeys\s*\(',
                         '[[maybe_unused]] static void AuthInitKeys(', txt, flags=re.M)

    p.write_text(txt)
    print("[OK] warnings patch applied:", p)

