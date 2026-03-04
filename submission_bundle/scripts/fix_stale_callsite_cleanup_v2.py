from pathlib import Path
import re

targets = [
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
]

def extract_function(txt: str, name: str):
    key = f"static void {name}"
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
                return (s, i + 1, txt[s:i+1])
        i += 1
    return None

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    fn = extract_function(txt, "CheckHandover")
    if not fn:
        print("[WARN] CheckHandover not found in:", p)
        continue

    s, e, func = fn
    orig = func

    # remove bad injected id line (old bug)
    func = re.sub(r'^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*\n', '', func, flags=re.M)

    # if both const + non-const ageMs exist, keep only const
    func = re.sub(
        r'(const\s+uint32_t\s+ageMs\s*=\s*TrustAgeMs\(\s*id\s*\)\s*;\s*\n)\s*uint32_t\s+ageMs\s*=\s*TrustAgeMs\(\s*id\s*\)\s*;\s*\n',
        r'\1',
        func
    )

    # remove duplicate RecordStaleCheck calls, keep first only
    lines = func.splitlines(True)
    new_lines = []
    seen = False
    for ln in lines:
        if "RecordStaleCheck(" in ln:
            if not seen:
                seen = True
                new_lines.append(ln)
            else:
                continue
        else:
            new_lines.append(ln)
    func = "".join(new_lines)

    # insert RecordStaleCheck right after ageMs line if missing
    if "RecordStaleCheck(" not in func:
        m = re.search(r'^\s*(?:const\s+)?uint32_t\s+ageMs\s*=\s*TrustAgeMs\(\s*id\s*\)\s*;\s*$',
                      func, flags=re.M)
        if not m:
            print("[WARN] ageMs line not found; cannot insert in:", p)
        else:
            insert_pos = m.end()
            func = func[:insert_pos] + "\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n" + func[insert_pos:]

    if func != orig:
        txt = txt[:s] + func + txt[e:]
        p.write_text(txt)
        print("[OK] fixed stale callsite in:", p)
    else:
        print("[OK] no change needed in:", p)
