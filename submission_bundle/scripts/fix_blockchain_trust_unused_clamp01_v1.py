from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/blockchain_trust_v2x.cc"
if not p.exists():
    raise SystemExit(f"[ERR] not found: {p}")

txt = p.read_text()

# Change: static double Clamp01(double x)  ->  [[maybe_unused]] static double Clamp01(double x)
txt2, n = re.subn(
    r'^\s*static\s+double\s+Clamp01\s*\(',
    '[[maybe_unused]] static double Clamp01(',
    txt,
    flags=re.M
)

if n == 0:
    print("[WARN] Clamp01 signature not found, nothing changed")
else:
    p.write_text(txt2)
    print("[OK] patched Clamp01 unused warning:", p)
