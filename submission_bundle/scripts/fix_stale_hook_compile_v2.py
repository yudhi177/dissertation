from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def fix_backslash_n_outside_strings(txt: str) -> str:
    # Convert \n sequences that appear in code (not inside quotes) into real newlines
    # We only replace cases where after \n there is whitespace + identifier (so it’s code).
    return re.sub(r'\\n(?=\s*[A-Za-z_])', '\n', txt)

def ensure_lastFetchS_in_trustcache(txt: str) -> str:
    # If code references lastFetchS but struct doesn't have it, add it.
    if "lastFetchS" not in txt:
        return txt
    m = re.search(r'struct\s+TrustCacheEntry\s*\{', txt)
    if not m:
        return txt

    # Extract struct body crudely: from '{' to first '};'
    start = m.end()
    end = txt.find("};", start)
    if end == -1:
        return txt
    body = txt[start:end]

    if "lastFetchS" in body:
        return txt

    insert = "\n  double lastFetchS = -1e9; // cache fetch timestamp (s)\n"
    body2 = insert + body
    return txt[:start] + body2 + txt[end:]

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()
    orig = txt

    # 1) fix stray \n injected in code
    txt = fix_backslash_n_outside_strings(txt)

    # 2) ensure <cmath> exists if RecordStaleCheck uses fabs
    if "RecordStaleCheck" in txt and "#include <cmath>" not in txt:
        txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <cmath>\n", 1)

    # 3) add lastFetchS to TrustCacheEntry if required
    txt = ensure_lastFetchS_in_trustcache(txt)

    if txt != orig:
        p.write_text(txt)
        print("[OK] fixed stale hook compile issues in:", p)
    else:
        print("[OK] nothing to change in:", p)
