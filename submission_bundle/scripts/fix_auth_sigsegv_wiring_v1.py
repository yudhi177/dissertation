from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def insert_after_open_brace(func_txt: str, insert_txt: str) -> str:
    b = func_txt.find("{")
    if b == -1:
        return func_txt
    return func_txt[:b+1] + insert_txt + func_txt[b+1:]

def patch_one(txt: str) -> str:
    # remove older blocks if present
    txt = re.sub(r"// AUTH_INIT_WIRE_V1_BEGIN.*?// AUTH_INIT_WIRE_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// AUTH_TICK_GUARD_V1_BEGIN.*?// AUTH_TICK_GUARD_V1_END\s*", "", txt, flags=re.S)

    # 1) StartAuthProbes(): call AuthInitKeys(g_nVehicles) once at start
    m = re.search(r"static\s+void\s+StartAuthProbes\s*\([^)]*\)\s*\{", txt)
    if not m:
        raise SystemExit("[ERR] StartAuthProbes() not found")

    # Insert right after its opening '{'
    start = m.start()
    brace = txt.find("{", m.start())
    # find end of function by brace matching
    i = brace
    depth = 0
    end = None
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    if end is None:
        raise SystemExit("[ERR] Could not parse StartAuthProbes() body")

    func = txt[start:end]

    inject = r'''
// AUTH_INIT_WIRE_V1_BEGIN
  // Ensure auth key material exists BEFORE probes run (prevents SIGSEGV)
  // Safe even if called multiple times (should be idempotent inside AuthInitKeys)
  AuthInitKeys(g_nVehicles);
// AUTH_INIT_WIRE_V1_END
'''
    if "AuthInitKeys(g_nVehicles);" not in func:
        func2 = insert_after_open_brace(func, inject)
        txt = txt[:start] + func2 + txt[end:]

    # 2) AuthProbeTick(): add safety guards at top
    m2 = re.search(r"static\s+void\s+AuthProbeTick\s*\([^)]*\)\s*\{", txt)
    if not m2:
        # If tick function name differs, don't hard-fail
        return txt

    start2 = m2.start()
    brace2 = txt.find("{", start2)
    # match braces
    i = brace2
    depth = 0
    end2 = None
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                end2 = i + 1
                break
        i += 1
    if end2 is None:
        return txt

    funcT = txt[start2:end2]

    guard = r'''
// AUTH_TICK_GUARD_V1_BEGIN
  if (!g_enableAuthProbe) return;
  if (g_nVehicles == 0) return;
// AUTH_TICK_GUARD_V1_END
'''
    if "AUTH_TICK_GUARD_V1_BEGIN" not in funcT:
        funcT2 = insert_after_open_brace(funcT, guard)
        txt = txt[:start2] + funcT2 + txt[end2:]

    return txt

for p in targets:
    if not p.exists():
        continue
    t = p.read_text()
    t2 = patch_one(t)
    p.write_text(t2)
    print("[OK] Auth SIGSEGV wiring patch applied:", p)
