from pathlib import Path
import re

# Build is compiling scratch file
paths = [
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
]

def patch_one(p: Path):
    if not p.exists():
        return
    txt = p.read_text()

    m = re.search(r"static\s+void\s+PrivacyRotate\s*\([^\)]*\)\s*\{.*?\n\}\s*\n", txt, flags=re.S)
    if not m:
        print("[WARN] PrivacyRotate() not found in", p)
        return

    func = m.group(0)

    # 1) Remove any previously injected privacy log lines (both good/bad forms)
    func = re.sub(r'^\s*PrivacyLogEvent\(.*PSEUDO_ROTATE.*\);\s*\n', '', func, flags=re.M)
    func = re.sub(r'^\s*PrivacyLogEvent\(.*LINK_ATTEMPT.*\);\s*\n', '', func, flags=re.M)

    # 2) Insert safe rotation log right after g_pseudoRotations++
    rot_log = (
        '  PrivacyLogEvent(std::string("PSEUDO_ROTATE v=") + std::to_string(v) + " reason=" + reason);\n'
    )
    if "g_pseudoRotations++;" in func:
        func = func.replace("g_pseudoRotations++;", "g_pseudoRotations++;\n" + rot_log, 1)
    else:
        print("[WARN] g_pseudoRotations++ not found in PrivacyRotate() in", p)

    # 3) Insert safe link attempt log right after k computed
    link_log = (
        '    PrivacyLogEvent(std::string("LINK_ATTEMPT v=") + std::to_string(v)'
        ' + " k=" + std::to_string(k)'
        ' + " p=" + std::to_string(1.0 / double(k + 1)));\n'
    )
    func2 = re.sub(
        r"(const\s+uint32_t\s+k\s*=\s*CountVehNeighborsWithinRadius\s*\([^\)]*\)\s*;\s*\n)",
        r"\1" + link_log,
        func,
        count=1
    )
    func = func2

    txt = txt[:m.start()] + func + txt[m.end():]
    p.write_text(txt)
    print("[OK] Fixed PrivacyLogEvent strings in:", p)

for p in paths:
    patch_one(p)
