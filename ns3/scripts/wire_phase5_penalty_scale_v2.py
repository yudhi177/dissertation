from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

hits = 0
txt, n1 = re.subn(r"(\+=\s*)g_reportDeltaBad(\s*;)", r"\1ApplyFairnessPenaltyScale(g_reportDeltaBad)\2", txt)
hits += n1
txt, n2 = re.subn(r"(\bdouble\s+\w+\s*=\s*)g_reportDeltaBad(\s*;)", r"\1ApplyFairnessPenaltyScale(g_reportDeltaBad)\2", txt)
hits += n2

p.write_text(txt)
print(f"[OK] Phase5 penalty scaling patched hits={hits}")
