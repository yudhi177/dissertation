from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

if "if [[ -z \"$F_SPEED\" ]]" not in txt:
    # insert after SPEEDS array is defined (both quick/full blocks use SPEEDS)
    txt = re.sub(
        r'(SPEEDS=\([^\)]*\)\s*\n)',
        r'\1\n# If program has no speed flag, collapse speed dimension\nif [[ -z "$F_SPEED" ]]; then SPEEDS=(0); fi\n',
        txt,
        count=1
    )

p.write_text(txt)
print("[OK] Patched make_publishable_results.sh: collapse SPEEDS when F_SPEED is empty")
