from pathlib import Path
import re

scratch = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"

backup_candidates = [
    Path("/tmp/secure_v2x_scratch_backup.cc"),
    Path("/tmp/backup_scratch_secure_v2x.cc"),
    Path("/tmp/secure_v2x_scratch_before_phase5_fix.cc"),
]

def extract_main(txt: str):
    m = re.search(r"\bint\s+main\s*\(", txt)
    if not m:
        return None
    s = m.start()
    brace = txt.find("{", s)
    if brace == -1:
        return None
    i = brace
    depth = 0
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                return txt[s:i+1]
        i += 1
    return None

txt = scratch.read_text()

if re.search(r"\bint\s+main\s*\(", txt):
    print("[OK] main() already exists")
    raise SystemExit(0)

backup = None
for b in backup_candidates:
    if b.exists():
        backup = b
        break

if backup is None:
    raise SystemExit("[ERR] No backup found in /tmp to restore main().")

btxt = backup.read_text()
main_code = extract_main(btxt)
if not main_code:
    raise SystemExit(f"[ERR] Could not extract main() from backup: {backup}")

txt = txt.rstrip() + "\n\n" + main_code + "\n"
scratch.write_text(txt)
print(f"[OK] Restored main() into {scratch} from {backup}")
