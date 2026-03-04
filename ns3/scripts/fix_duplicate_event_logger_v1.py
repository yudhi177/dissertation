from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists(): 
        continue
    txt = p.read_text()

    # Remove the "pointer logger" variant block if present
    txt = re.sub(r'\nstatic\s+std::ofstream\*\s+g_evt\s*=\s*nullptr;\s*\n.*?static\s+inline\s+void\s+EmitEvt\s*\(.*?\)\s*\{.*?\n\}\s*\n',
                 '\n', txt, flags=re.S)

    # If any remaining pointer-style use exists, rewrite to object-style
    txt = txt.replace("if (g_evt && (*g_evt))", "if (g_evt.is_open())")
    txt = txt.replace("(*g_evt) <<", "g_evt <<")

    p.write_text(txt)
    print("[OK] cleaned duplicate event logger in:", p)
