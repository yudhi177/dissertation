from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# collect includes
inc_re = re.compile(r'^\s*#include\s+[<"].+[>"]\s*$', re.M)
incs = [x.strip() for x in inc_re.findall(txt)]
body = inc_re.sub("", txt)

def extract_mains(code):
    mains = []
    for m in re.finditer(r'\bint\s+main\s*\(', code):
        start = m.start()
        brace = code.find("{", m.end())
        if brace == -1:
            continue
        i = brace
        depth = 0
        end = None
        while i < len(code):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        if end:
            mains.append((start, end, code[start:end]))
    return mains

mains = extract_mains(body)
if not mains:
    raise SystemExit("[ERR] No main() found")

# keep biggest main
_, _, keep_main = max(mains, key=lambda t: len(t[2]))
keep_main = keep_main.strip()

# remove all mains
for s, e, _ in sorted(mains, key=lambda t: t[0], reverse=True):
    body = body[:s] + "\n\n" + body[e:]

body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"

need = [
    '#include "ns3/core-module.h"',
    '#include "ns3/network-module.h"',
    '#include "ns3/internet-module.h"',
    '#include "ns3/mobility-module.h"',
    '#include "ns3/wifi-module.h"',
    '#include "ns3/applications-module.h"',
    "#include <cstdint>",
    "#include <vector>",
    "#include <memory>",
    "#include <fstream>",
    "#include <algorithm>",
]

seen = set()
final_incs = []
for x in need + incs:
    x = x.strip()
    if x and x not in seen:
        seen.add(x)
        final_incs.append(x)

using = "using namespace ns3;\n\n"
if re.search(r'^\s*using\s+namespace\s+ns3\s*;\s*$', body, re.M):
    using = ""

out = "\n".join(final_incs) + "\n\n" + using + body
out += "\n// ===== main() normalized to bottom =====\n" + keep_main + "\n"
p.write_text(out)

print("[OK] fixed file:", p)
print("[OK] main() found:", len(mains), "kept 1")
