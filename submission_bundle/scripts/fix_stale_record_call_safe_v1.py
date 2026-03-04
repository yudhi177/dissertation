from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def find_func(txt, name):
    m = re.search(rf"static\s+void\s+{name}\s*\([^\)]*\)\s*\{{", txt)
    if not m: return None
    s = m.start()
    i = m.end()-1
    depth = 0
    while i < len(txt):
        if txt[i] == "{": depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                return (s, i+1)
        i += 1
    return None

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove old bad insertion (node->GetId)
    txt = re.sub(r'^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*\n', '', txt, flags=re.M)

    span = find_func(txt, "CheckHandover")
    if not span:
        print("[WARN] CheckHandover not found in", p)
        p.write_text(txt)
        continue

    s,e = span
    body = txt[s:e]

    # require RecordStaleCheck definition exists
    if "RecordStaleCheck(" not in txt:
        print("[WARN] RecordStaleCheck not defined in", p, "- skipping callsite insertion")
        p.write_text(txt)
        continue

    # ensure cacheHit exists in CheckHandover
    if "bool cacheHit" not in body:
        body = re.sub(r"(uint32_t\s+id\s*=\s*.*?->GetId\(\)\s*;\s*\n)",
                      r"\1  bool cacheHit = false;\n", body, count=1)

    # insert RecordStaleCheck after existing ageMs line (const or non-const)
    if "RecordStaleCheck(" not in body:
        # find: const uint32_t ageMs = TrustAgeMs(id);
        m = re.search(r"^\s*(const\s+)?uint32_t\s+ageMs\s*=\s*TrustAgeMs\s*\(\s*id\s*\)\s*;\s*$", body, flags=re.M)
        if m:
            insert_pos = m.end()
            body = body[:insert_pos] + "\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n" + body[insert_pos:]
        else:
            print("[WARN] ageMs=TrustAgeMs(id) line not found in", p, "- no insertion made")

    txt = txt[:s] + body + txt[e:]
    p.write_text(txt)
    print("[OK] stale RecordStaleCheck callsite patched:", p)
