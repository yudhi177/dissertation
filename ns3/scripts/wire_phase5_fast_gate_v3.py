from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover() not found")
start = m.end()
body = txt[start:start+16000]

mf = re.search(r'^\s*bool\s+fast\s*=\s*([^;]+);\s*$', body, flags=re.M)
if not mf:
    raise SystemExit("[ERR] bool fast = ... not found")

expr = mf.group(1)
gate = '(!g_enableTrustConfidence || (TrustConfidence(id) >= g_confMinForFast))'
if gate not in expr:
    new_expr = f"({expr}) && {gate}"
    new_line = "  bool fast = " + new_expr + ";"
    abs_s = start + mf.start()
    abs_e = start + mf.end()
    txt = txt[:abs_s] + new_line + txt[abs_e:]
else:
    print("[SKIP] gate already present")

p.write_text(txt)
print("[OK] FAST gate wired")
