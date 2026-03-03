from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove entire TrustEvidenceGood function block
# Matches: static void TrustEvidenceGood(...) { ... }
txt2 = re.sub(
    r'\nstatic\s+void\s+TrustEvidenceGood[^{]*\{.*?\n\}\s*\n',
    '\n',
    txt,
    flags=re.S
)

if txt2 == txt:
    # fallback: if formatting differs, try a looser match
    txt2 = re.sub(
        r'static\s+void\s+TrustEvidenceGood.*?\{.*?\}\s*',
        '',
        txt,
        flags=re.S
    )

p.write_text(txt2)
print("[OK] Removed TrustEvidenceGood() from:", p)
