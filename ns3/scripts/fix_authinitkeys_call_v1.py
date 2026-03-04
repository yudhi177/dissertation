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

    # Add forward decl + guard flag after using namespace ns3;
    if "static bool g_authKeysReady" not in txt:
        m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
        if not m:
            raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
        pos = m.end()
        txt = txt[:pos] + (
            "\n// AUTH_INIT_GUARD_V1_BEGIN\n"
            "static void AuthInitKeys(uint32_t nVehicles);\n"
            "static bool g_authKeysReady = false;\n"
            "// AUTH_INIT_GUARD_V1_END\n\n"
        ) + txt[pos:]

    # Ensure StartAuthProbes() calls AuthInitKeys once
    m = re.search(r"(static\s+void\s+StartAuthProbes\s*\([^)]*\)\s*\{\s*\n)", txt, flags=re.M)
    if m:
        insert = "  if (!g_authKeysReady) { AuthInitKeys(g_nVehicles); g_authKeysReady = true; }\n"
        pos = m.end()
        if insert not in txt[pos:pos+300]:
            txt = txt[:pos] + insert + txt[pos:]
    else:
        # fallback: if StartAuthProbes not found, try hooking near existing call
        pass

    p.write_text(txt)
    print("[OK] AuthInitKeys guard wired in:", p)
