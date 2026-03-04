from pathlib import Path
import re

targets = [
    Path.home() / "ns-3/scratch/blockchain_trust_v2x.cc",
    Path.home() / "dissertation/ns3/scenarios/blockchain_trust_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    # Make Clamp01 [[maybe_unused]] so -Werror won't fail
    txt2 = re.sub(
        r'^\s*static\s+double\s+Clamp01\s*\(',
        '[[maybe_unused]] static double Clamp01(',
        txt,
        flags=re.M
    )

    if txt2 != txt:
        p.write_text(txt2)
        print("[OK] patched:", p)
    else:
        print("[WARN] no Clamp01 pattern matched:", p)
