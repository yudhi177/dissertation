from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# find main
m = re.search(r"\bint\s+main\s*\(\s*int\s+\w+\s*,\s*char\s*\*\*\s*\w+\s*\)\s*\{", txt)
if not m:
    m = re.search(r"\bint\s+main\s*\(", txt)
if not m:
    raise SystemExit("[ERR] main() not found")

s = m.start()
brace = txt.find("{", s)
if brace == -1:
    raise SystemExit("[ERR] main() brace not found")

# brace match
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

# remove main from old place
rest = (txt[:s] + "\n" + txt[end:]).strip()

# IMPORTANT: append main at very end
out = rest.rstrip() + "\n\n// ===== main() moved to bottom (SAFE v2) =====\n" + main_code + "\n"
p.write_text(out)
print("[OK] main() moved to bottom:", p)
