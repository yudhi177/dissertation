from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def patch(txt: str) -> str:
    # Replace common integer-division patterns: 1/(k+1) -> 1.0/double(k+1)
    txt = re.sub(r'(\b1\s*/\s*\(\s*k\s*\+\s*1\s*\))', r'(1.0 / double(k + 1))', txt)
    txt = re.sub(r'(\b1\s*/\s*\(\s*k\s*\+\s*1u\s*\))', r'(1.0 / double(k + 1))', txt)
    txt = re.sub(r'(\b1\s*/\s*\(\s*k\s*\+\s*1U\s*\))', r'(1.0 / double(k + 1))', txt)
    txt = re.sub(r'(\b1\s*/\s*\(\s*k\s*\+\s*1\s*\)\s*;)', r'(1.0 / double(k + 1));', txt)

    # If there is a line like: double p = 1 / (k + 1);  -> fix
    txt = re.sub(r'\bdouble\s+p\s*=\s*1\s*/\s*\(\s*k\s*\+\s*1\s*\)\s*;',
                 'double p = 1.0 / double(k + 1);', txt)

    # If there is: auto p = 1 / (k + 1); -> fix
    txt = re.sub(r'\bauto\s+p\s*=\s*1\s*/\s*\(\s*k\s*\+\s*1\s*\)\s*;',
                 'double p = 1.0 / double(k + 1);', txt)

    # If there is: uint32_t p = 1/(k+1); -> fix
    txt = re.sub(r'\buint32_t\s+p\s*=\s*1\s*/\s*\(\s*k\s*\+\s*1\s*\)\s*;',
                 'double p = 1.0 / double(k + 1);', txt)

    # Ensure expected-success accumulator uses double prob (if present)
    txt = re.sub(r'g_linkSuccessExp\s*\+=\s*1\s*/\s*\(\s*k\s*\+\s*1\s*\)\s*;',
                 'g_linkSuccessExp += 1.0 / double(k + 1);', txt)

    return txt

for p in targets:
    if not p.exists():
        continue
    old = p.read_text()
    new = patch(old)
    if new != old:
        p.write_text(new)
        print("[OK] patched:", p)
    else:
        print("[SKIP] no change needed:", p)
