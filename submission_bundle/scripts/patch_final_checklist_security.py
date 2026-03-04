from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/final_checklist.sh"
txt = p.read_text()

# avoid double insert
if "revocation_cdf.png" in txt and "detect_fp.csv" in txt:
    print("[OK] final_checklist already checks security outputs")
    raise SystemExit(0)

insert = r'''
echo "[8] Security outputs exist (revocation + detection)"
test -f "$PACK/revocation_cdf.png" || { echo "  ❌ missing revocation_cdf.png"; exit 5; }
test -f "$PACK/revocation_cdf.csv" || { echo "  ❌ missing revocation_cdf.csv"; exit 5; }
test -f "$PACK/detect_fp.csv"      || { echo "  ❌ missing detect_fp.csv"; exit 5; }
echo "  ✅ security outputs OK"
'''

# place before final "✅ FINAL CHECKLIST COMPLETE"
txt = txt.replace("echo\necho \"✅ FINAL CHECKLIST COMPLETE\"",
                  insert + "\n\necho\necho \"✅ FINAL CHECKLIST COMPLETE\"", 1)

p.write_text(txt)
print("[OK] Patched final_checklist.sh to verify security outputs")
