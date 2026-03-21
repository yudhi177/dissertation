from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/blockchain_trust_v2x.cc"
if not p.exists():
    print("[SKIP] not found:", p)
    raise SystemExit(0)

txt = p.read_text()

# Make Clamp01 not fail -Werror=unused-function
txt2 = re.sub(r'^\s*static\s+double\s+Clamp01\s*\(',
              '[[maybe_unused]] static double Clamp01(',
              txt, flags=re.M)

p.write_text(txt2)
print("[OK] patched:", p)
