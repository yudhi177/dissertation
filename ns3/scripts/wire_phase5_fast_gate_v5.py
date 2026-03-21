from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover not found")

start = m.end()
body = txt[start:start+22000]

mf = re.search(r'^\s*bool\s+fast\s*=\s*([^;]+);\s*$', body, flags=re.M)
if not mf:
    raise SystemExit("[ERR] bool fast = ...; not found inside CheckHandover")

expr = mf.group(1)
gate = '(!g_enableTrustConfidence || (TrustConfidence(id) >= g_confMinForFast))'
if gate not in expr:
    new_line = "  bool fast = (" + expr + ") && " + gate + ";"
    abs_s = start + mf.start()
    abs_e = start + mf.end()
    txt = txt[:abs_s] + new_line + txt[abs_e:]

marker = "  // PHASE5_FAST_DENY_COUNTER_V5\n"
if marker not in txt[start:start+24000]:
    body2 = txt[start:start+22000]
    mf2 = re.search(r'^\s*bool\s+fast\s*=.*;\s*$', body2, flags=re.M)
    ins = start + mf2.end()
    inject = (
      "\n" + marker +
      "  if (g_enableTrustConfidence && (TrustConfidence(id) < g_confMinForFast))\n"
      "  {\n"
      "    g_fastDeniedLowConf++;\n"
      "    if (g_evt.is_open()) { g_evt << Simulator::Now().GetSeconds()"
      " << \",FAST_DENY_LOW_CONF id=\" << id << \" conf=\" << TrustConfidence(id) << \"\\n\"; }\n"
      "  }\n"
    )
    txt = txt[:ins] + inject + txt[ins:]

p.write_text(txt)
print("[OK] wired Phase5 FAST gate + counter:", p)
