from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def extract_function(txt: str, func_name: str):
    key = f"static void {func_name}"
    s = txt.find(key)
    if s == -1:
        return None
    brace = txt.find("{", s)
    if brace == -1:
        return None
    i = brace
    depth = 0
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                e = i + 1
                return (s, e, txt[s:e])
        i += 1
    return None

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # A) REMOVE WRONG GLOBAL INJECTION (WriteCsv etc.)
    txt = re.sub(
        r'\n\s*//\s*FIX_FAST_VAR_V1\s*\n\s*//\s*FAST eligibility.*?\n\s*bool\s+fast\s*=\s*\(trust\s*>=\s*g_trustFastThresh\);\s*\n',
        '\n',
        txt,
        flags=re.S
    )

    # B) FIX INSIDE CheckHandover() ONLY
    fx = extract_function(txt, "CheckHandover")
    if not fx:
        print("[WARN] CheckHandover not found in", p)
        p.write_text(txt)
        continue

    s, e, fn = fx

    # remove any bad/duplicate fast declarations inside CheckHandover
    fn = re.sub(r'^\s*//\s*FIX_FAST_VAR_V1\s*$', '', fn, flags=re.M)
    fn = re.sub(r'^\s*//\s*FAST eligibility.*$', '', fn, flags=re.M)
    fn = re.sub(r'^\s*bool\s+fast\s*=.*;\s*$', '', fn, flags=re.M)

    # find trust line
    m_trust = re.search(r'^\s*double\s+trust\s*=\s*[^;]+;\s*$', fn, flags=re.M)
    if m_trust:
        # insert right AFTER trust line
        ins = m_trust.end()
        fn = fn[:ins] + "\n\n  // FIX_FAST_VAR_V1\n  // FAST eligibility (baseline logic)\n  bool fast = (trust >= g_trustFastThresh);\n" + fn[ins:]
    else:
        # fallback: insert before first usage of "fast" if present
        m_use = re.search(r'\bfast\b', fn)
        if not m_use:
            print("[WARN] no trust/fast anchors in", p)
        else:
            line_start = fn.rfind("\n", 0, m_use.start())
            if line_start == -1:
                line_start = m_use.start()
            ins = line_start + 1
            fn = fn[:ins] + "  // FIX_FAST_VAR_V1\n  bool fast = (trust >= g_trustFastThresh);\n" + fn[ins:]

    txt = txt[:s] + fn + txt[e:]
    p.write_text(txt)
    print("[OK] fixed fast scope + cleaned bad injection:", p)

