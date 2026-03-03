from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# If already present, do nothing
if "TrustEvidenceGood(hdr.senderId);" in txt:
    print("[OK] TrustEvidenceGood already used. No change.")
    raise SystemExit(0)

# Insert after successful packet accounting (after g_rxBytes += pktSize;)
pat = r'(g_rxBytes\s*\+=\s*pktSize;\s*\n)'
m = re.search(pat, txt)
if not m:
    raise SystemExit("[ERR] Could not find 'g_rxBytes += pktSize;' in file")

txt = re.sub(pat, r'\1  TrustEvidenceGood(hdr.senderId);\n', txt, count=1)

p.write_text(txt)
print("[OK] Inserted TrustEvidenceGood(hdr.senderId); after g_rxBytes update:", p)
