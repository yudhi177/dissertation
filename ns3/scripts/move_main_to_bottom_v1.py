from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Find main start
m = re.search(r"\bint\s+main\s*\(\s*int\s+\w+\s*,\s*char\s*\*\*\s*\w+\s*\)\s*\{", txt)
if not m:
    m = re.search(r"\bint\s+main\s*\(", txt)
if not m:
    raise SystemExit("[ERR] main() not found")

s = m.start()
brace = txt.find("{", s)
if brace == -1:
    raise SystemExit("[ERR] main() brace not found")

# Extract full main() by brace matching
i = brace
depth = 0
end = None
while i < len(txt):
    if txt[i] == "{":
        depth += 1
    elif txt[i] == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
    i += 1

if end is None:
    raise SystemExit("[ERR] could not match braces for main()")

main_code = txt[s:end].strip()

# Remove main() from its old location
new_txt = (txt[:s] + "\n" + txt[end:]).strip()

# Append it to bottom
new_txt = new_txt.rstrip() + "\n\n// ===== main() moved to bottom (auto-fix) =====\n" + main_code + "\n"

p.write_text(new_txt)
print("[OK] main() moved to bottom:", p)
