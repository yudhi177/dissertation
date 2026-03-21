from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# We assume you already compute whether FAST allowed (trust >= fastThresh etc.)
# We add: if peer requests FAST while !eligible => reject and log DOWNGRADE_DETECTED
# Anchor: in CheckHandover() near FAST decision (look for trustFastThresh usage)
m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover not found")
start = m.end()
body = txt[start:start+9000]

# Find trustFastThresh usage
a = re.search(r"g_trustFastThresh|trustFastThresh", body)
if not a:
    # if not found, do not hard fail; just report
    print("[WARN] FAST threshold anchor not found; skipping injection")
    raise SystemExit(0)

# Inject a guard around where FAST mode is selected.
# Heuristic: find the first "FAST" literal inside CheckHandover
b = re.search(r"FAST", body)
if not b:
    print("[WARN] FAST literal not found; skipping injection")
    raise SystemExit(0)

# Insert near that location (previous line boundary)
line_start = body.rfind("\n", 0, b.start())
ins = start + (line_start+1 if line_start!=-1 else b.start())

inject = (
  "  // PHASE2: anti-downgrade protection\n"
  "  // If peer tries to force FAST while not eligible => reject\n"
  "  if (g_enableAntiDowngrade)\n"
  "  {\n"
  "    const bool fastEligible = (trust >= g_trustFastThresh);\n"
  "    const bool peerWantsFast = true; // model: peer requests FAST in transcript\n"
  "    if (peerWantsFast && !fastEligible)\n"
  "    {\n"
  "      g_downgradeDetected++;\n"
  "      if (g_evt.is_open()) { g_evt << Simulator::Now().GetSeconds() << \",DOWNGRADE_DETECTED id=\" << id << \" trust=\" << trust << \"\\n\"; }\n"
  "      return;\n"
  "    }\n"
  "  }\n"
)

if "DOWNGRADE_DETECTED" not in body:
    txt = txt[:ins] + inject + txt[ins:]

p.write_text(txt)
print("[OK] wired anti-downgrade guard in CheckHandover() (best-effort)")
