from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover() not found")
start = m.end()
body = txt[start:start+14000]

# Find definition: bool fast = ...
mf = re.search(r'^\s*bool\s+fast\s*=\s*([^;]+);\s*$', body, flags=re.M)
if not mf:
    raise SystemExit("[ERR] 'bool fast = ...;' not found inside CheckHandover()")

expr = mf.group(1)
gate = '(!g_enableTrustConfidence || (TrustConfidence(id) >= g_confMinForFast))'

if gate in expr:
    print("[SKIP] gate already present")
    raise SystemExit(0)

new_expr = f"({expr}) && {gate}"
new_line = re.sub(r'^\s*bool\s+fast\s*=\s*[^;]+;\s*$',
                  lambda _: "  bool fast = " + new_expr + ";",
                  mf.group(0))

# replace in full text
abs_s = start + mf.start()
abs_e = start + mf.end()
txt = txt[:abs_s] + new_line + txt[abs_e:]

# Add counter increment right after fast computation (once)
marker = "  // PHASE5_FAST_DENY_COUNTER_V2\n"
if marker not in txt[start:start+16000]:
    # insert after the modified bool fast line
    insert_at = abs_s + len(new_line)
    ins_nl = txt.find("\n", insert_at)
    if ins_nl == -1:
        ins_nl = insert_at
    inject = (
        "\n" + marker +
        "  if (g_enableTrustConfidence && (TrustConfidence(id) < g_confMinForFast))\n"
        "  {\n"
        "    g_fastDeniedLowConf++;\n"
        "    if (g_evt.is_open()) { g_evt << Simulator::Now().GetSeconds()"
        " << \",FAST_DENY_LOW_CONF id=\" << id"
        " << \" conf=\" << TrustConfidence(id) << \"\\n\"; }\n"
        "  }\n"
    )
    txt = txt[:ins_nl+1] + inject + txt[ins_nl+1:]

p.write_text(txt)
print("[OK] Phase5 FAST gate + counter wired")
