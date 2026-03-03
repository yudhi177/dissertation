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

    # Remove older block if exists
    txt = re.sub(r"// REPLAY_REASON_V1_BEGIN.*?// REPLAY_REASON_V1_END\s*", "", txt, flags=re.S)

    # Find events stream variable
    m = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut", txt)
    if not m:
        m = re.search(r"(\w+)\.open\s*\(\s*eventsOut", txt)
    if not m:
        raise SystemExit(f"[ERR] Could not detect events stream variable in {p}")
    evStream = m.group(1)

    # Insert global counters near top (after using namespace)
    anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not anchor:
        raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")

    block = r'''
// REPLAY_REASON_V1_BEGIN
static uint64_t g_replayDropsReason = 0;
// REPLAY_REASON_V1_END
'''
    txt = txt[:anchor.end()] + block + txt[anchor.end():]

    # Hook: whenever replay is detected / dropped
    # Your code already has replayDrops metric; we hook the event line.
    # Try several common patterns:
    patterns = [
        r"replayDrops\+\+\s*;",
        r"g_replayDrops\+\+\s*;",
        r"replayDrop\+\+\s*;",
    ]

    hooked = False
    for pat in patterns:
        if re.search(pat, txt):
            txt = re.sub(pat,
                         pat.replace(r"\+\+", "++") + rf'\n    g_replayDropsReason++;\n    AuthLog({evStream}, "AUTH_FAIL", "reason=REPLAY");',
                         txt,
                         count=1)
            hooked = True
            break

    # If no replayDrops var found, hook by detecting event string "DATA_DROP_REPLAY" or "REPLAY_DROP"
    if not hooked:
        # if code emits DATA_DROP_REPLAY, leave it, but also add counter on that emit
        txt = re.sub(r'("DATA_DROP_REPLAY[^"]*")\s*\)',
                     rf'\1);\n    g_replayDropsReason++;\n    AuthLog({evStream}, "AUTH_FAIL", "reason=REPLAY")\n    /*', txt, count=0)

    # Add final print line if not present
    if "[REPLAY]" not in txt:
        txt = txt.replace("  std::cout << \"[AUTH]\"",
                          "  std::cout << \"[REPLAY] drops=\" << g_replayDropsReason << std::endl;\n  std::cout << \"[AUTH]\"",
                          1)

    p.write_text(txt)
    print("[OK] Patched replay reason logging into:", p)
