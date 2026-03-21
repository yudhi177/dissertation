from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def drop_duplicates(txt: str, name: str) -> str:
    # match lines like: static uint32_t g_confWindow = 20;
    pat = re.compile(r'^\s*static\s+\w+\s+' + re.escape(name) + r'\s*=\s*[^;]+;\s*$', re.M)
    ms = list(pat.finditer(txt))
    if len(ms) <= 1:
        return txt
    # remove all but first
    keep = ms[0].span()
    out = []
    last = 0
    for i, m in enumerate(ms):
        if i == 0:
            continue
        s, e = m.span()
        out.append(txt[last:s])
        last = e
    out.append(txt[last:])
    txt2 = "".join(out)
    return txt2

for p in targets:
    if not p.exists():
        continue
    t = p.read_text()
    t2 = drop_duplicates(t, "g_confWindow")
    t2 = drop_duplicates(t2, "g_confMinForFast")
    p.write_text(t2)
    print("[OK] removed duplicate conf defs:", p)
