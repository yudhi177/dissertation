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

    # 1) Fix literal "\n" inserted into C++ code (common corruption pattern)
    # Only fix when it occurs right after a semicolon or ) which indicates broken injection
    txt = re.sub(r";\\n\s*", ";\n  ", txt)
    txt = re.sub(r"\)\\n\s*", ")\n  ", txt)

    # 2) Remove bad injected id line using undefined 'node'
    txt = re.sub(r"^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*$\n", "", txt, flags=re.M)

    # 3) Remove any broken RecordStaleCheck calls that were injected at wrong place
    txt = re.sub(r"^\s*RecordStaleCheck\s*\(.*?\);\s*$\n", "", txt, flags=re.M)

    # 4) Remove broken trust-cache lastFetchS references (if they exist)
    txt = re.sub(r"\s*&&\s*\(now\s*-\s*it->second\.lastFetchS\)\s*<=\s*ttlS", "", txt)
    txt = re.sub(r"^\s*e\.lastFetchS\s*=\s*now;\s*$\n", "", txt, flags=re.M)
    txt = re.sub(r"^\s*double\s+lastFetchS\s*=\s*-?1e9;\s*$\n", "", txt, flags=re.M)

    p.write_text(txt)
    print("[OK] cleaned corruption in:", p)

