from pathlib import Path
import re

p = Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Replace direct use of g_reportDeltaBad in updates with scaled version
# If your code does: trust += g_reportDeltaBad; we rewrite to trust += ApplyFairnessPenaltyScale(g_reportDeltaBad);
pat = re.compile(r"(\btrust\s*\+\=\s*)g_reportDeltaBad(\s*;)")
new_txt, n = pat.subn(r"\1ApplyFairnessPenaltyScale(g_reportDeltaBad)\2", txt)

# Alternative: if code uses 'delta = g_reportDeltaBad'
pat2 = re.compile(r"(\bdouble\s+\w+\s*=\s*)g_reportDeltaBad(\s*;)")
new_txt2, n2 = pat2.subn(r"\1ApplyFairnessPenaltyScale(g_reportDeltaBad)\2", new_txt)

p.write_text(new_txt2)
print(f"[OK] fairness penalty scaling applied (hits={n+n2})")
