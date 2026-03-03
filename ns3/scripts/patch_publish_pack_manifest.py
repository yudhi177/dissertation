from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

if "manifest.json" in txt:
    print("[OK] manifest already present")
    raise SystemExit(0)

needle = 'local log="$RUNSD/${tag}.log"\n'
if needle not in txt:
    raise SystemExit("[ERR] Could not find run_one() log line to hook manifest write.")

manifest_snip = r'''local manifest="$RUNSD/${tag}_manifest.json"
python3 - <<PY
import json, os, subprocess
data = {
  "tag": os.environ.get("TAG",""),
  "baseline": os.environ.get("BASELINE",""),
  "nveh": int(os.environ.get("NVEH","0")),
  "speed": int(os.environ.get("SPD","0")),
  "seed": int(os.environ.get("SEED","0")),
  "sim": int(os.environ.get("SIM","0")),
  "args": os.environ.get("ARGS",""),
  "git_commit": subprocess.getoutput("git -C $HOME/dissertation rev-parse --short HEAD 2>/dev/null").strip()
}
open(os.environ["MANIFEST"],"w").write(json.dumps(data, indent=2))
