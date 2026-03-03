from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove old hook if exists
    txt = re.sub(r"// FAST_CONF_GATE_V1_BEGIN.*?// FAST_CONF_GATE_V1_END\s*", "", txt, flags=re.S)

    # Find place where FAST vs FULL is decided.
    # We'll match a common check: "if (trust >= g_trustFastThresh)"
    m = re.search(r"if\s*\(\s*trust\s*>=\s*g_trustFastThresh\s*\)", txt)
    if not m:
        raise SystemExit(f"[ERR] Could not find FAST threshold check in {p}")

    pos = m.start()

    hook = r'''
// FAST_CONF_GATE_V1_BEGIN
// Add confidence condition into FAST eligibility
double conf = 1.0;
if (id < g_trustConf.size()) conf = g_trustConf[id];
bool confOk = (conf >= g_confMinForFast);
// FAST_CONF_GATE_V1_END
'''
    txt = txt[:pos] + hook + txt[pos:]

    # Replace condition to include confOk
    txt = re.sub(r"if\s*\(\s*trust\s*>=\s*g_trustFastThresh\s*\)",
                 "if ((trust >= g_trustFastThresh) && confOk)", txt, count=1)

    p.write_text(txt)
    print("[OK] Added FAST confidence gate in:", p)
