from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/blockchain_trust_v2x.cc"
txt = p.read_text()

# already patched?
if re.search(r"\[\[maybe_unused\]\]\s*static\s+double\s+Clamp01\s*\(", txt):
    print("[SKIP] already patched:", p)
    raise SystemExit(0)

new_txt, n = re.subn(
    r"(^\s*)static\s+double\s+Clamp01\s*\(",
    r"\1[[maybe_unused]] static double Clamp01(",
    txt,
    flags=re.M
)

if n == 0:
    raise SystemExit("[ERR] Clamp01() signature not found")

p.write_text(new_txt)
print("[OK] patched Clamp01 unused warning:", p)
