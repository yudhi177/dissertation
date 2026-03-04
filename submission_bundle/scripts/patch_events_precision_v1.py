from pathlib import Path
import re

targets = [
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
]

def ensure_include(txt: str) -> str:
    if "#include <iomanip>" in txt:
        return txt
    # insert after iostream include if possible
    m = re.search(r"#include\s*<iostream>\s*\n", txt)
    if m:
        pos = m.end()
        return txt[:pos] + "#include <iomanip>\n" + txt[pos:]
    # else insert near top
    return "#include <iomanip>\n" + txt

def patch_stream_format_after_open(txt: str) -> str:
    # Pattern A: std::ofstream X(eventsOut...);
    m = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut[^\)]*\)\s*;\s*\n", txt)
    if m:
        var = m.group(1)
        pos = m.end()
        inject = f"  {var} << std::fixed << std::setprecision(6);\n"
        if inject not in txt[pos:pos+200]:
            txt = txt[:pos] + inject + txt[pos:]
        return txt

    # Pattern B: X.open(eventsOut...);
    m = re.search(r"(\w+)\.open\s*\(\s*eventsOut[^\)]*\)\s*;\s*\n", txt)
    if m:
        var = m.group(1)
        pos = m.end()
        inject = f"  {var} << std::fixed << std::setprecision(6);\n"
        if inject not in txt[pos:pos+200]:
            txt = txt[:pos] + inject + txt[pos:]
        return txt

    return txt

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()
    txt = ensure_include(txt)
    txt = patch_stream_format_after_open(txt)
    p.write_text(txt)
    print("[OK] Patched event timestamp precision in:", p)
