from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Find AuthProbeTick() and insert allow check near sender selection
m = re.search(r"static\s+void\s+AuthProbeTick\s*\(\s*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] AuthProbeTick() not found")
start = m.end()

# Heuristic: find a line that defines sender (sender=0 default in your logs)
# Insert before first EmitEvt/AUTH_OK decision, but after sender chosen.
# Best anchor: first occurrence of "sender" in the function body.
body = txt[start:start+6000]
ms = re.search(r"\bsender\s*=\s*\d+|uint32_t\s+sender", body)
if not ms:
    raise SystemExit("[ERR] Could not locate sender variable in AuthProbeTick()")

# Insert after the line where sender is known (end of that line)
line_end = body.find("\n", ms.start())
ins = start + line_end + 1

inject = (
  "  // PHASE2: DoS protection (rate limit auth attempts per sender)\n"
  "  if (!AuthRateLimitAllow(sender)) { return; }\n"
)

# Avoid double insert
if "AuthRateLimitAllow(sender)" not in body:
    txt = txt[:ins] + inject + txt[ins:]

p.write_text(txt)
print("[OK] wired AuthRateLimitAllow(sender) in AuthProbeTick()")
