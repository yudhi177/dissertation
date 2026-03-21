from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+AuthProbeTick\s*\(\s*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] AuthProbeTick() not found")

ins = m.end()

marker = "  // PHASE2_RATE_LIMIT_V2\n"
inject = (
    marker
    "  if (!AuthRateLimitAllow(0)) { return; }\n"
)

# Insert only once
if marker not in txt[m.start():m.start()+4000]:
    txt = txt[:ins] + "\n" + inject + txt[ins:]

p.write_text(txt)
print("[OK] AuthProbeTick rate limit wired (sender=0)")
