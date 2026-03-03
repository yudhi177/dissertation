from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

if "--baselineName=" in txt:
    print("[OK] baselineName already passed by pack script")
    raise SystemExit(0)

# In run_one(), after args init, add baselineName flag
txt = txt.replace(
    'local args="--${F_SIMTIME}=${SIM} --${F_CSV}=${csv} --${F_EVT}=${evt}"',
    'local args="--${F_SIMTIME}=${SIM} --${F_CSV}=${csv} --${F_EVT}=${evt} --baselineName=${baseline}"'
)

p.write_text(txt)
print("[OK] Pack now passes --baselineName=<baseline>")
