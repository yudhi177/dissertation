from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
  raise SystemExit("[ERR] CheckHandover not found")
start = m.end()
body = txt[start:start+30000]

# insert RecordObservation(id) after id assignment
if "RecordObservation(id);" not in body:
  mid = re.search(r'^\s*uint32_t\s+id\s*=\s*\w+->GetId\(\)\s*;\s*$', body, flags=re.M)
  if mid:
    ins = start + mid.end()
    txt = txt[:ins] + "\n  RecordObservation(id);\n" + txt[ins:]

# replace fast definition (first occurrence)
txt = re.sub(
  r'^\s*bool\s+fast\s*=.*;\s*$',
  '  bool fast = (trust >= g_trustFastThresh) && (!g_enableTrustConfidence || (TrustConfidence(id) >= g_confMinForFast));',
  txt,
  count=1,
  flags=re.M
)

# add deny counter block once
if "g_fastDeniedLowConf++" not in txt[start:start+30000]:
  mfast = re.search(r'^\s*bool\s+fast\s*=.*g_trustFastThresh.*;\s*$', txt[start:start+30000], flags=re.M)
  if mfast:
    ip = start + mfast.end()
    inject = (
      "\n  // PHASE5: count FAST denied due to low confidence\n"
      "  if (g_enableTrustConfidence && (TrustConfidence(id) < g_confMinForFast))\n"
      "  {\n"
      "    g_fastDeniedLowConf++;\n"
      "  }\n"
    )
    txt = txt[:ip] + inject + txt[ip:]

p.write_text(txt)
print("[OK] Phase5 FAST gate wired")
