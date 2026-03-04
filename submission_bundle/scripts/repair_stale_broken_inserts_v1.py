from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def fix_literal_backslash_n(txt: str) -> str:
    # Fix ONLY the broken injected patterns (do NOT global replace \n in strings)
    txt = txt.replace("cacheHit = false;\\n", "cacheHit = false;\n")
    txt = txt.replace("TrustAgeMs(id);\\n", "TrustAgeMs(id);\n")
    txt = txt.replace("RecordStaleCheck(id, trust, cacheHit, ageMs);\\n", "RecordStaleCheck(id, trust, cacheHit, ageMs);\n")
    # more general: if a single line contains multiple "\n" tokens (the exact failure you hit)
    txt = re.sub(r"(cacheHit\s*=\s*false;)\s*\\n\s*", r"\1\n  ", txt)
    txt = re.sub(r"(TrustAgeMs\s*\(\s*id\s*\)\s*;)\s*\\n\s*", r"\1\n  ", txt)
    txt = re.sub(r"(RecordStaleCheck\s*\(.*?\)\s*;)\s*\\n\s*", r"\1\n  ", txt)
    return txt

def remove_wrong_node_id(txt: str) -> str:
    # Remove the wrong injected line (node may not exist in function)
    txt = re.sub(r"^\s*uint32_t\s+id\s*=\s*node->GetId\(\)\s*;\s*\n", "", txt, flags=re.M)
    return txt

def ensure_trustcache_lastFetchS(txt: str) -> str:
    # If code uses lastFetchS but struct doesn't have it, add it once.
    if "lastFetchS" not in txt:
        return txt

    m = re.search(r"struct\s+TrustCacheEntry\s*\{(.*?)\};", txt, flags=re.S)
    if not m:
        return txt

    body = m.group(1)
    if re.search(r"\blastFetchS\b", body):
        return txt

    # Insert a safe default field inside struct
    insert = "\n  double lastFetchS = -1e9; // added to match cache freshness tracking\n"
    new_body = body + insert
    return txt[:m.start(1)] + new_body + txt[m.end(1):]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    txt2 = txt
    txt2 = fix_literal_backslash_n(txt2)
    txt2 = remove_wrong_node_id(txt2)
    txt2 = ensure_trustcache_lastFetchS(txt2)

    if txt2 != txt:
        p.write_text(txt2)
        print("[OK] repaired:", p)
    else:
        print("[OK] no changes needed:", p)
