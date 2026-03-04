from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

orig = txt

# 1) Fix the broken escaped quotes in std::string(\"FORCED\")
txt = txt.replace('std::string(\\"FORCED\\")', 'std::string("FORCED")')

# 2) Fix 'all.GetN()' scope issue -> use global NodeList count
txt = re.sub(r'\ball\.GetN\(\)', 'NodeList::GetNNodes()', txt)

if txt != orig:
    p.write_text(txt)
    print("[OK] Fixed revocation compile issues in:", p)
else:
    print("[WARN] No matching patterns found. Check lines around the errors manually.")
