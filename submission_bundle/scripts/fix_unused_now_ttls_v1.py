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

    # Mark now as maybe_unused
    txt = re.sub(r'^\s*const\s+double\s+now\s*=\s*NowS\(\)\s*;\s*$',
                 '  [[maybe_unused]] const double now = NowS();',
                 txt, flags=re.M)

    # Mark ttlS as maybe_unused
    txt = re.sub(r'^\s*const\s+double\s+ttlS\s*=\s*double\s*\(\s*g_cacheTtlMs\s*\)\s*/\s*1000\.0\s*;\s*$',
                 '  [[maybe_unused]] const double ttlS = double(g_cacheTtlMs) / 1000.0;',
                 txt, flags=re.M)

    p.write_text(txt)
    print("[OK] patched unused now/ttlS in:", p)
