from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) In InitPseudonyms(): after setting g_activePseudo[v], set prevTime/prevPos/prevPseudo to current state
#    This makes FIRST rotation produce LINK_ATTEMPT.
pat_init = re.compile(r'(static void InitPseudonyms\(\)\s*\{[\s\S]*?\n\})', re.M)
m = pat_init.search(txt)
if not m:
    raise SystemExit("[ERR] InitPseudonyms() not found. Privacy patch must be applied first.")

init_body = m.group(1)

# Insert block just after: g_activePseudo[v] = ...
if "g_prevTime[v] = Simulator::Now().GetSeconds();" not in init_body:
    init_body2 = re.sub(
        r'(g_activePseudo\[v\]\s*=\s*st\.pool\.empty\(\)\s*\?\s*0ULL\s*:\s*st\.pool\[0\];\s*)',
        r'\1\n'
        r'    // baseline for linkability (so 1st rotation yields LINK_ATTEMPT)\n'
        r'    g_prevTime[v] = Simulator::Now().GetSeconds();\n'
        r'    Ptr<MobilityModel> mm = g_vehicles.Get(v)->GetObject<MobilityModel>();\n'
        r'    if (mm) { g_prevPos[v] = mm->GetPosition(); }\n'
        r'    g_prevPseudo[v] = g_activePseudo[v];\n',
        init_body,
        count=1
    )
    init_body = init_body2

txt = txt[:m.start(1)] + init_body + txt[m.end(1):]

# 2) Guarantee timer ticks are scheduled in main() (remove any old scheduling and re-add clean)
# Remove any existing PseudoTimerTick scheduling block to avoid duplicates
txt = re.sub(r'(?s)\n\s*if\s*\(g_enablePrivacy\)\s*\{\s*for\s*\(uint32_t v\s*=\s*0;.*?PseudoTimerTick.*?\}\s*\n', "\n", txt)

# Replace the InitPseudonyms call block with a stronger block that also schedules timer
txt = re.sub(
    r'if\s*\(g_enablePrivacy\)\s*\{\s*InitPseudonyms\(\);\s*\}',
    'if (g_enablePrivacy) {\n'
    '    InitPseudonyms();\n'
    '    for (uint32_t v = 0; v < g_nVehicles; v++)\n'
    '      Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);\n'
    '  }',
    txt,
    count=1
)

p.write_text(txt)
print("[OK] Privacy linkability fix applied:", p)
