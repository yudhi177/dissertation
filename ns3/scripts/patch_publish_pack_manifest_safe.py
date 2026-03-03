from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
if not p.exists():
    raise SystemExit("[ERR] make_publishable_results.sh not found")

txt = p.read_text()

# If already patched, exit
if "_manifest.json" in txt:
    print("[OK] manifest already present in make_publishable_results.sh")
    raise SystemExit(0)

# 1) Add 'manifest' variable next to log
needle = '  local log="$RUNSD/${tag}.log"\n'
if needle not in txt:
    raise SystemExit("[ERR] Could not find log line inside run_one()")

txt = txt.replace(needle, needle + '  local manifest="$RUNSD/${tag}_manifest.json"\n', 1)

# 2) Insert manifest writer just BEFORE ns3 run line
run_pat = r'^\s*\./ns3 run "scratch/secure_trust_blockchain_v2x \${args}".*$'
m = re.search(run_pat, txt, flags=re.M)
if not m:
    raise SystemExit("[ERR] Could not find ./ns3 run line to hook manifest write before it.")

insert_pos = m.start()

manifest_block = r'''  # write per-run manifest (reproducibility)
  python3 - "$tag" "$baseline" "$nveh" "$spd" "$seed" "$SIM" "$args" "$manifest" <<'PYEOF'
import json, sys, os, subprocess
tag, baseline, nveh, spd, seed, sim, args, manifest = sys.argv[1:]

def to_int(x):
    try: return int(float(x))
    except: return 0

data = {
  "tag": tag,
  "baseline": baseline,
  "nveh": to_int(nveh),
  "speed": to_int(spd),
  "seed": to_int(seed),
  "sim": to_int(sim),
  "args": args,
  "git_commit": subprocess.getoutput(f"git -C {os.path.expanduser('~')}/dissertation rev-parse --short HEAD 2>/dev/null").strip()
}
with open(manifest, "w") as f:
    f.write(json.dumps(data, indent=2))
PYEOF

'''

txt = txt[:insert_pos] + manifest_block + txt[insert_pos:]

p.write_text(txt)
print("[OK] Patched manifest output into:", p)
