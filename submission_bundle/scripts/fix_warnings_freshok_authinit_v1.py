from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def patch_one(txt: str) -> str:
    # --------------------------
    # A) Fix freshOk unused
    # --------------------------
    # If fastOk exists, enforce: fastOk = fastOk && freshOk;
    if "const bool freshOk" in txt and "fastOk" in txt:
        # Insert "fastOk = fastOk && freshOk;" soon after freshOk line (once)
        pat = r'(const\s+bool\s+freshOk\s*=\s*\(.*?\);\s*\n)'
        m = re.search(pat, txt)
        if m and "fastOk = fastOk && freshOk;" not in txt[m.end():m.end()+200]:
            txt = txt[:m.end()] + "  fastOk = fastOk && freshOk;\n" + txt[m.end():]
    else:
        # fallback: explicitly mark used (removes warning, no logic change)
        txt = re.sub(
            r'(const\s+bool\s+freshOk\s*=\s*\(.*?\);\s*\n)',
            r'\1  (void)freshOk;\n',
            txt,
            count=1
        )

    # --------------------------
    # B) Fix AuthInitKeys unused
    # --------------------------
    # Prefer calling it in StartAuthProbes(), otherwise mark it unused.
    has_auth_init = re.search(r'\bstatic\s+void\s+AuthInitKeys\s*\(', txt) is not None
    if has_auth_init:
        # Choose a safe vehicle count expression
        if "g_nVehicles" in txt:
            n_expr = "g_nVehicles"
        elif "g_vehicleNodes" in txt:
            n_expr = "(uint32_t)g_vehicleNodes.size()"
        else:
            n_expr = "30"

        # Try to insert call inside StartAuthProbes()
        m = re.search(r'static\s+void\s+StartAuthProbes\s*\(\s*\)\s*\{', txt)
        if m:
            ins = m.end()
            snippet = txt[ins:ins+300]
            call = f"\n  // init deterministic auth keys once\n  AuthInitKeys({n_expr});\n"
            if "AuthInitKeys(" not in snippet:
                txt = txt[:ins] + call + txt[ins:]
        else:
            # If no StartAuthProbes exists, mark function unused correctly
            txt = re.sub(r'\bstatic\s+void\s+AuthInitKeys\s*\(',
                         'static void __attribute__((unused)) AuthInitKeys(',
                         txt,
                         count=1)

    return txt

for p in targets:
    if not p.exists():
        continue
    t = p.read_text()
    t2 = patch_one(t)
    if t2 != t:
        p.write_text(t2)
        print("[OK] patched:", p)
    else:
        print("[SKIP] no changes:", p)
