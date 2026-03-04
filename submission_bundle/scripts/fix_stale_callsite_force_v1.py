from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove any accidental bad line (past bug)
txt = re.sub(r'^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*\n', '', txt, flags=re.M)

# Find CheckHandover body
m = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] CheckHandover() not found")
start = m.end()

# Find a good anchor inside CheckHandover: after 'uint32_t id = veh->GetId();'
m2 = re.search(r"uint32_t\s+id\s*=\s*\w+->GetId\(\)\s*;\s*\n", txt[start:start+2000])
if not m2:
    raise SystemExit("[ERR] Could not find 'id = <arg>->GetId()' inside CheckHandover")
ins = start + m2.end()

# Ensure cacheHit exists (only once)
chunk = txt[ins:ins+400]
if "bool cacheHit" not in txt[start:start+2000]:
    txt = txt[:ins] + "  bool cacheHit = false;\n" + txt[ins:]

# Ensure ageMs + RecordStaleCheck exist near trust decision (insert once)
if "RecordStaleCheck(" not in txt[start:start+4000]:
    # Insert near first 'TrustAgeMs(' usage if present else near first 'trust' variable usage
    m3 = re.search(r"TrustAgeMs\s*\(\s*id\s*\)\s*;", txt[start:start+4000])
    pos = start + (m3.end() if m3 else 0)
    inject = (
        "  uint32_t ageMs = TrustAgeMs(id);\n"
        "  RecordStaleCheck(id, trust, cacheHit, ageMs);\n"
    )
    # safest: inject right after a line that defines/updates 'trust'
    # fallback: inject at end of function before return/closing brace
    if pos == start:
        # before final '}' of CheckHandover
        end = txt.find("}\n", start)
        txt = txt[:end] + inject + txt[end:]
    else:
        txt = txt[:pos] + "\n" + inject + txt[pos:]

p.write_text(txt)
print("[OK] forced RecordStaleCheck hook in scratch file:", p)
