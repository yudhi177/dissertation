from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def extract_function(txt: str, name: str):
    key = f"static void {name}"
    s = txt.find(key)
    if s == -1:
        return None
    brace = txt.find("{", s)
    if brace == -1:
        return None
    i = brace
    depth = 0
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                return (s, i + 1, txt[s:i+1])
        i += 1
    return None

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()
    got = extract_function(txt, "CheckHandover")
    if not got:
        print("[WARN] CheckHandover not found in:", p)
        continue

    s, e, func = got
    orig = func

    # 1) Remove wrong injected line: any id assignment using node->GetId()
    func = re.sub(r'^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*\n', '', func, flags=re.M)

    # 2) If multiple id declarations exist, keep the first one and remove the rest
    id_lines = list(re.finditer(r'^\s*uint32_t\s+id\s*=\s*\w+->GetId\(\);\s*$', func, flags=re.M))
    if len(id_lines) > 1:
        # remove all except first
        keep_span = id_lines[0].span()
        new_lines = []
        for line in func.splitlines(True):
            if re.match(r'^\s*uint32_t\s+id\s*=\s*\w+->GetId\(\);\s*$', line):
                # keep only first occurrence
                if keep_span and func.find(line) == keep_span[0]:
                    new_lines.append(line)
                    keep_span = None
                else:
                    continue
            else:
                new_lines.append(line)
        func = "".join(new_lines)

    if func != orig:
        txt = txt[:s] + func + txt[e:]
        p.write_text(txt)
        print("[OK] fixed CheckHandover id bug in:", p)
    else:
        print("[OK] no id bug found in:", p)

