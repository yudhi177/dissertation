from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover() not found")
start = m.end()
body = txt[start:start+12000]

# anchor near trust usage / FAST threshold
a = re.search(r"g_trustFastThresh", body)
if not a:
    raise SystemExit("[ERR] g_trustFastThresh not found in CheckHandover()")

# insert after trust is computed (best effort: after first 'double trust' assignment)
t = re.search(r"\bdouble\s+trust\s*=\s*[^;]+;\s*\n", body)
if not t:
    # fallback: after first 'trust' mention
    t = re.search(r"\btrust\b", body)
    if not t:
        raise SystemExit("[ERR] trust variable anchor not found")

ins = start + (t.end() if hasattr(t, "end") else t.start())

marker = "  // PHASE5_CONF_GATE_V1\n"
if marker in body:
    print("[SKIP] already wired")
    raise SystemExit(0)

inject = (
    "\n" + marker +
    "  // PHASE5: TrustConfidence gating for FAST\n"
    "  const double conf = TrustConfidence(id);\n"
    "  const bool confOk = (!g_enableTrustConfidence) || (conf >= g_confMinForFast);\n"
    "  if (!confOk)\n"
    "  {\n"
    "    g_fastDeniedLowConf++;\n"
    "    if (g_evt.is_open()) { g_evt << Simulator::Now().GetSeconds() << \",FAST_DENY_LOW_CONF id=\" << id << \" conf=\" << conf << \"\\n\"; }\n"
    "  }\n"
)

txt = txt[:ins] + inject + txt[ins:]
p.write_text(txt)
print("[OK] wired confidence calc/log in CheckHandover()")
