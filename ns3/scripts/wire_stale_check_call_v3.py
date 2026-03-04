from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
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

def ensure_id_at_top(func: str) -> str:
    # If already has node->GetId usage early, skip
    head = func[:400]
    if "node->GetId()" in head or re.search(r"\buint32_t\s+\w+\s*=\s*node->GetId\(\)", head):
        return func
    # insert after first '{'
    brace = func.find("{")
    return func[:brace+1] + "\n  uint32_t id = node->GetId();\n" + func[brace+1:]

def ensure_cachehit(func: str) -> str:
    if "cacheHit" in func:
        return func
    # place after id line if present, else after '{'
    if "uint32_t id = node->GetId();" in func:
        return func.replace("uint32_t id = node->GetId();",
                            "uint32_t id = node->GetId();\n  bool cacheHit = false;", 1)
    brace = func.find("{")
    return func[:brace+1] + "\n  bool cacheHit = false;\n" + func[brace+1:]

def remove_old_record_calls(func: str) -> str:
    func = re.sub(r'^\s*RecordStaleCheck\s*\(.*?\);\s*\n', '', func, flags=re.M)
    func = re.sub(r'^\s*uint32_t\s+ageMs\s*=\s*TrustAgeMs\s*\(.*?\)\s*;\s*\n', '', func, flags=re.M)
    return func

def insert_record_after_trust_fetch(func: str) -> str:
    # find first line with GetTrustScoreCached(
    m = re.search(r'^[^\n]*GetTrustScoreCached\s*\(.*?\)\s*;\s*$', func, flags=re.M)
    if not m:
        # fallback: GetTrustScore(
        m = re.search(r'^[^\n]*GetTrustScore\s*\(.*?\)\s*;\s*$', func, flags=re.M)
        if not m:
            return func

    line = m.group(0)
    # try detect assigned var name
    var = "trust"
    mm = re.search(r'(\w+)\s*=\s*GetTrustScoreCached\s*\(', line)
    if mm:
        var = mm.group(1)
    else:
        mm = re.search(r'double\s+(\w+)\s*=\s*GetTrustScoreCached\s*\(', line)
        if mm:
            var = mm.group(1)

    inject = (
        f"{line}\n"
        f"  uint32_t ageMs = TrustAgeMs(id);\n"
        f"  RecordStaleCheck(id, {var}, cacheHit, ageMs);\n"
    )
    return func[:m.start()] + inject + func[m.end():]

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    got = extract_function(txt, "CheckHandover")
    if not got:
        raise SystemExit(f"[ERR] CheckHandover not found in {p}")

    s, e, func = got
    func2 = func
    func2 = remove_old_record_calls(func2)
    func2 = ensure_id_at_top(func2)
    func2 = ensure_cachehit(func2)

    # If cacheHit exists but declared later, still fine.
    func2 = insert_record_after_trust_fetch(func2)

    if func2 == func:
        print("[WARN] No changes applied in:", p)
    else:
        txt = txt[:s] + func2 + txt[e:]
        p.write_text(txt)
        print("[OK] Wired RecordStaleCheck() into CheckHandover in:", p)

