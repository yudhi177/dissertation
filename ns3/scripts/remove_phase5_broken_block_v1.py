from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

B = r"// PHASE5_CONF_FAIR_V1_BEGIN"
E = r"// PHASE5_CONF_FAIR_V1_END"

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Remove the full block (BEGIN..END)
    txt2, n = re.subn(B + r".*?" + E + r"\s*", "", txt, flags=re.S)

    p.write_text(txt2)
    print(f"[OK] removed broken Phase5 block from {p} (removed={n})")
