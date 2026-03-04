from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

if "postprocess_security_pack.sh" in txt:
    print("[OK] Security postprocess already hooked.")
    raise SystemExit(0)

hook = r'''
# --- Security postprocess (revocation CDF + detection/FP) ---
"$HOME/dissertation/ns3/scripts/postprocess_security_pack.sh" "$OUTROOT/runs" "$PUB"
'''

# Insert right before final echo publish (or at end)
if "[PUBLISH]" in txt:
    # place right before final publish echo
    txt = txt.replace('echo "[PUBLISH] $PUB"\n', hook + '\n' + 'echo "[PUBLISH] $PUB"\n', 1)
else:
    txt += "\n" + hook + "\n"

p.write_text(txt)
print("[OK] Hooked security postprocess into make_publishable_results.sh")
