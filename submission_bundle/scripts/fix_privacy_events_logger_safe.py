from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# ----------------------------
# 1) Remove previously injected LogEvent blocks
# ----------------------------
txt = re.sub(r"\n\s*// --- privacy event: rotation ---\s*\n\s*LogEvent\([^\n]*\);\s*\n", "\n", txt, flags=re.S)
txt = re.sub(r"\n\s*// --- privacy event: link attempt ---\s*\n\s*LogEvent\(\"LINK_ATTEMPT.*?\);\s*\n", "\n", txt, flags=re.S)

# ----------------------------
# 2) Insert global privacy logger (once)
# ----------------------------
if "PRIVACY_EVENT_LOGGER_BEGIN" not in txt:
    insert_point = None
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if m:
        insert_point = m.end()
    else:
        insert_point = 0

    logger_block = r'''
// PRIVACY_EVENT_LOGGER_BEGIN
#include <fstream>
static std::ofstream* g_eventsPtr = nullptr;

// Writes: <time>,<event_string>
static void PrivacyLogEvent(const std::string& ev)
{
  if (g_eventsPtr && g_eventsPtr->is_open())
  {
    (*g_eventsPtr) << Simulator::Now().GetSeconds() << "," << ev << "\n";
  }
}
// PRIVACY_EVENT_LOGGER_END
'''
    txt = txt[:insert_point] + logger_block + txt[insert_point:]

# ----------------------------
# 3) Hook g_eventsPtr assignment where eventsOut file is opened
#    We try multiple patterns to locate the ofstream used for events.
# ----------------------------
if "g_eventsPtr =" not in txt:
    # pattern A: std::ofstream X(eventsOut...);
    m = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut[^\)]*\)\s*;\s*\n", txt)
    if m:
        var = m.group(1)
        pos = m.end()
        txt = txt[:pos] + f"  g_eventsPtr = &{var};\n" + txt[pos:]
    else:
        # pattern B: std::ofstream X; ... X.open(eventsOut...);
        m1 = re.search(r"std::ofstream\s+(\w+)\s*;\s*\n", txt)
        if m1:
            var = m1.group(1)
            m2 = re.search(rf"\b{var}\.open\s*\(\s*eventsOut[^\)]*\)\s*;\s*\n", txt)
            if m2:
                pos = m2.end()
                txt = txt[:pos] + f"  g_eventsPtr = &{var};\n" + txt[pos:]
        # pattern C: something.open(eventsOut...)
        if "g_eventsPtr =" not in txt:
            m3 = re.search(r"(\w+)\.open\s*\(\s*eventsOut[^\)]*\)\s*;\s*\n", txt)
            if m3:
                var = m3.group(1)
                pos = m3.end()
                txt = txt[:pos] + f"  g_eventsPtr = &{var};\n" + txt[pos:]

# ----------------------------
# 4) Inject privacy events into PrivacyRotate (once)
# ----------------------------
m = re.search(r"static\s+void\s+PrivacyRotate\s*\([^\)]*\)\s*\{.*?\n\}\s*\n", txt, flags=re.S)
if not m:
    raise SystemExit("[ERR] PrivacyRotate() not found.")

func = m.group(0)
if "PRIVACY_EVT_BEGIN" not in func:
    # after g_pseudoRotations++
    func = func.replace(
        "g_pseudoRotations++;",
        "g_pseudoRotations++;\n"
        "  // PRIVACY_EVT_BEGIN\n"
        "  PrivacyLogEvent(\"PSEUDO_ROTATE v=\" + std::to_string(v) + \" reason=\" + reason);\n"
        "  // PRIVACY_EVT_END",
        1
    )

    # after k computed (works for your V3 rotate)
    func = re.sub(
        r"(const\s+uint32_t\s+k\s*=\s*CountVehNeighborsWithinRadius\s*\([^\)]*\)\s*;)",
        r"\1\n    PrivacyLogEvent(\"LINK_ATTEMPT v=\" + std::to_string(v) +"
        r" \" k=\" + std::to_string(k) +"
        r" \" p=\" + std::to_string(1.0 / double(k + 1)));",
        func,
        count=1
    )

txt = txt[:m.start()] + func + txt[m.end():]

p.write_text(txt)
print("[OK] Privacy events now use PrivacyLogEvent() (no LogEvent dependency).")
