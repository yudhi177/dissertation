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

    # 1) freshOk warning: mark it maybe_unused (C++17 safe)
    txt = re.sub(
        r'(\s*)const\s+bool\s+freshOk\s*=\s*\(([^;]+)\);\s*',
        r'\1[[maybe_unused]] const bool freshOk = (\2);\n',
        txt
    )

    # 2) AuthInitKeys warning: mark function as maybe_unused safely
    # Converts: static void AuthInitKeys( -> [[maybe_unused]] static void AuthInitKeys(
    txt = re.sub(
        r'(^\s*)static\s+void\s+AuthInitKeys\s*\(',
        r'\1[[maybe_unused]] static void AuthInitKeys(',
        txt,
        flags=re.M
    )

    p.write_text(txt)
    print("[OK] cleaned warnings in:", p)
