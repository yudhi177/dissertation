from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

# 1) Ensure BC_ALWAYS_QUERY in BASELINES list
m = re.search(r'BASELINES=\(([^)]*)\)', txt)
if not m:
    raise SystemExit("[ERR] BASELINES=(...) not found")
if "BC_ALWAYS_QUERY" not in m.group(1):
    new = m.group(0).replace("BC_TRUST", "BC_TRUST BC_ALWAYS_QUERY")
    txt = txt.replace(m.group(0), new, 1)

# 2) Ensure pick_flag exists for enableBlockchain + probe flags
def ensure_pick(flag, after_pat):
    global txt
    if f'$(pick_flag {flag})' in txt:
        return
    m2 = re.search(after_pat, txt, flags=re.M)
    if not m2:
        return
    pos = m2.end()
    txt = txt[:pos] + f'F_{flag.upper()}=$(pick_flag {flag})\n' + txt[pos:]

ensure_pick("enableBlockchain", r'^\s*F_BC_UD=\$\(pick_flag bcUpdateDelayMs\)\s*$')
ensure_pick("enableBcProbe", r'^\s*F_ENABLEBLOCKCHAIN=\$\(pick_flag enableBlockchain\)\s*$|^\s*F_BC_UD=\$\(pick_flag bcUpdateDelayMs\)\s*$')
ensure_pick("bcProbeIntervalMs", r'^\s*F_ENABLEBLOCKCHAIN=\$\(pick_flag enableBlockchain\)\s*$|^\s*F_BC_UD=\$\(pick_flag bcUpdateDelayMs\)\s*$')
ensure_pick("bcProbeUsePseudonym", r'^\s*F_ENABLEBLOCKCHAIN=\$\(pick_flag enableBlockchain\)\s*$|^\s*F_BC_UD=\$\(pick_flag bcUpdateDelayMs\)\s*$')

# 3) Add BC_ALWAYS_QUERY case if missing
if "BC_ALWAYS_QUERY)" not in txt:
    idx = txt.find("BC_TRUST)")
    if idx == -1:
        raise SystemExit("[ERR] Could not find BC_TRUST) case")
    end = txt.find(";;", idx)
    if end == -1:
        raise SystemExit("[ERR] Could not find end of BC_TRUST case")
    insert_pos = end + 2

    case = r'''
    BC_ALWAYS_QUERY)
      # Trust ON
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      # Blockchain ON
      if [[ -n "$F_ENABLEBLOCKCHAIN" ]]; then args="$args --${F_ENABLEBLOCKCHAIN}=1"; fi
      # Cache OFF (worst case)
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi
      # Probe ON (forces queries)
      if [[ -n "$F_ENABLEBCPROBE" ]]; then args="$args --${F_ENABLEBCPROBE}=1"; fi
      if [[ -n "$F_BCPROBEINTERVALMS" ]]; then args="$args --${F_BCPROBEINTERVALMS}=200"; fi
      if [[ -n "$F_BCPROBEUSEPSEUDONYM" ]]; then args="$args --${F_BCPROBEUSEPSEUDONYM}=0"; fi
      # Privacy OFF / Revocation OFF
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      ;;
'''
    txt = txt[:insert_pos] + case + txt[insert_pos:]

p.write_text(txt)
print("[OK] Added BC_ALWAYS_QUERY baseline into make_publishable_results.sh")
