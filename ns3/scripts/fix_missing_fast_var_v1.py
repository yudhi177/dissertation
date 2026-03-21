from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# locate CheckHandover
m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover() not found")

start = m.end()
body = txt[start:start+20000]

# if fast already exists, skip
if re.search(r"^\s*bool\s+fast\s*=", body, flags=re.M):
    print("[SKIP] bool fast already exists")
    raise SystemExit(0)

# anchor: trust threshold usage OR authDelay line
anchor = re.search(r"g_trustFastThresh", body)
if not anchor:
    anchor = re.search(r"authDelay\s*=", body)

if not anchor:
    raise SystemExit("[ERR] Could not find anchor inside CheckHandover()")

# insert just BEFORE anchor line
line_start = body.rfind("\n", 0, anchor.start())
if line_start == -1:
    line_start = anchor.start()
ins = start + line_start + 1

inject = (
    "  // FIX_FAST_VAR_V1\n"
    "  // FAST eligibility (baseline logic)\n"
    "  bool fast = (trust >= g_trustFastThresh);\n"
)

txt = txt[:ins] + inject + txt[ins:]
p.write_text(txt)
print("[OK] inserted missing bool fast in CheckHandover()")
