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

    # Remove older helper if any
    txt = re.sub(r"// AUTH_EVENTS_REASON_V1_BEGIN.*?// AUTH_EVENTS_REASON_V1_END\s*", "", txt, flags=re.S)

    # We need access to the events output stream variable. Most of your code writes events via some stream.
    # We'll create a tiny wrapper that uses the same stream name if found.
    # Find the ofstream variable used for events: look for "std::ofstream <name>(eventsOut"
    m = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut", txt)
    if not m:
        # try open(eventsOut)
        m = re.search(r"(\w+)\.open\s*\(\s*eventsOut", txt)
    if not m:
        raise SystemExit(f"[ERR] Could not detect events stream variable in {p}")

    evStream = m.group(1)

    # Insert helper near events stream creation (just after open/constructor line)
    # We place it once globally near top: after using namespace ns3
    insert_anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not insert_anchor:
        raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")

    helper = r'''
// AUTH_EVENTS_REASON_V1_BEGIN
// Writes a standardized auth event line into the same events CSV file.
static inline void AuthLog(std::ostream& ev, const std::string& type, const std::string& msg)
{
  // events.csv already prints time in caller; this prints just event payload
  ev << Simulator::Now().GetSeconds() << "," << type << " " << msg << "\n";
}
// AUTH_EVENTS_REASON_V1_END
'''
    txt = txt[:insert_anchor.end()] + helper + txt[insert_anchor.end():]

    # Replace AUTH summary counters prints ONLY? No. We just inject logging at handshake/probe points.
    # Insert hooks: whenever auth ok/fail counters are incremented, add AuthLog.
    # Patterns are best-effort based on existing counters:
    # g_authOk++, g_authFail++, g_authFailMitm++
    txt = re.sub(r"g_authOk\+\+\s*;",
                 rf'g_authOk++;\n    AuthLog({evStream}, "AUTH_OK", "");', txt)

    txt = re.sub(r"g_authFailMitm\+\+\s*;",
                 rf'g_authFailMitm++;\n    AuthLog({evStream}, "AUTH_FAIL", "reason=MITM");', txt)

    txt = re.sub(r"g_authFail\+\+\s*;",
                 rf'g_authFail++;\n    AuthLog({evStream}, "AUTH_FAIL", "reason=BAD_SIG");', txt)

    # Also add AUTH_START where probe begins (look for StartAuthProbes or probe schedule)
    if "AUTH_START" not in txt:
        txt = txt.replace("StartAuthProbes();",
                          f'StartAuthProbes();\n  // auth probe started\n  AuthLog({evStream}, "AUTH_START", "probe=1");',
                          1)

    p.write_text(txt)
    print("[OK] Patched AUTH reason-coded events into:", p)
