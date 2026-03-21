from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

patterns = [
    r"//\s*PHASE5_CONF_FAIR_V1_BEGIN.*?//\s*PHASE5_CONF_FAIR_V1_END\s*",
    r"//\s*PHASE5_CONF_FAIR_V2_BEGIN.*?//\s*PHASE5_CONF_FAIR_V2_END\s*",
    r"//\s*PHASE5_CONF_FAIR_V3_BEGIN.*?//\s*PHASE5_CONF_FAIR_V3_END\s*",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()
    for pat in patterns:
        txt = re.sub(pat, "", txt, flags=re.S)
    p.write_text(txt)
    print("[OK] removed Phase5 blocks:", p)
