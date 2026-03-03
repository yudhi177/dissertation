from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Find PrivacyRotate function block
m = re.search(r"static\s+void\s+PrivacyRotate\s*\([^\)]*\)\s*\{.*?\n\}\s*\n", txt, flags=re.S)
if not m:
    raise SystemExit("[ERR] PrivacyRotate() not found.")

func = m.group(0)

# Detect event logger function name (best-effort)
# We will look for any helper like LogEvent(...) or WriteEvent(...)
candidates = ["LogEvent", "WriteEvent", "EmitEvent", "AppendEvent"]
logger = None
for c in candidates:
    if re.search(rf"\b{c}\s*\(", txt):
        logger = c
        break

if logger is None:
    # fallback: do nothing but still keep compile safe
    print("[WARN] No event logger found (LogEvent/WriteEvent...). Patch will only add counters, no events.")
    p.write_text(txt)
    raise SystemExit(0)

# Insert event logs after rotation occurs and inside link attempt block
# We log: time, type, vehicle, reason
inject1 = rf'''
  // --- privacy event: rotation ---
  {logger}("PSEUDO_ROTATE v=" + std::to_string(v) + " reason=" + reason);
'''

# Add link attempt log near expected success update
inject2 = rf'''
    // --- privacy event: link attempt ---
    {logger}("LINK_ATTEMPT v=" + std::to_string(v) +
             " k=" + std::to_string(k) +
             " p=" + std::to_string(1.0 / double(k + 1)));
'''

# place inject1 just after g_pseudoRotations++
func2 = func
if inject1.strip() not in func2:
    func2 = func2.replace("g_pseudoRotations++;", "g_pseudoRotations++;\n" + inject1, 1)

# place inject2 after k computed line
if inject2.strip() not in func2:
    func2 = re.sub(r"(const\s+uint32_t\s+k\s*=\s*CountVehNeighborsWithinRadius\s*\([^\)]*\)\s*;)",
                   r"\1\n" + inject2, func2, count=1)

txt = txt[:m.start()] + func2 + txt[m.end():]
p.write_text(txt)
print(f"[OK] Privacy events injected using logger: {logger}")
