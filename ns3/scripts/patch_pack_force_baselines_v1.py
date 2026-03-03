from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

def ensure_flag_pick(name, after):
    nonlocal txt
    if f'F_{name}=' in txt or f'F_{name}=$(pick_flag {name})' in txt:
        return
    txt = txt.replace(after, after + f'F_{name}=$(pick_flag {name})\n', 1)

# Ensure we can control enableBlockchain + probe flags
ensure_flag_pick("enableBlockchain", 'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n')
ensure_flag_pick("enableBcProbe", 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' if 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' in txt else 'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n')
ensure_flag_pick("bcProbeIntervalMs", 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' if 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' in txt else 'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n')
ensure_flag_pick("bcProbeUsePseudonym", 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' if 'F_ENABLE_BC=$(pick_flag enableBlockchain)\n' in txt else 'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n')

# Ensure BC_ALWAYS_QUERY exists in BASELINES list
m = re.search(r'BASELINES=\(([^)]*)\)', txt)
if m and "BC_ALWAYS_QUERY" not in m.group(1):
    repl = m.group(0).replace("BC_TRUST", "BC_TRUST BC_ALWAYS_QUERY")
    txt = txt.replace(m.group(0), repl, 1)

# Helper to inject a line inside a case before ';;'
def add_line(case_name, line):
    nonlocal txt
    idx = txt.find(f"{case_name})")
    if idx == -1:
        return
    end = txt.find(";;", idx)
    if end == -1:
        return
    block = txt[idx:end]
    if line in block:
        return
    txt = txt[:end] + line + "\n" + txt[end:]

# HARD FORCE BASELINES
# PKI_ONLY: everything off
add_line("PKI_ONLY",  '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=0"; fi')
add_line("PKI_ONLY",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line("PKI_ONLY",  '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi')
add_line("PKI_ONLY",  '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=0"; fi')
add_line("PKI_ONLY",  '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line("PKI_ONLY",  '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# TRUST_ONLY: trust on, blockchain off, privacy off, revocation off, probes off
add_line("TRUST_ONLY",'      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=0"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# BC_TRUST: trust on, blockchain on, cache on, probes on, privacy off, revocation off
add_line("BC_TRUST",  '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# Add BC_ALWAYS_QUERY case if missing
if "BC_ALWAYS_QUERY)" not in txt:
    # insert after BC_TRUST case end
    pos = txt.find("BC_TRUST)")
    if pos != -1:
        end = txt.find(";;", pos)
        if end != -1:
            insert_pos = end + 2
            case_block = r'''
    BC_ALWAYS_QUERY)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi
      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      ;;
'''
            txt = txt[:insert_pos] + case_block + txt[insert_pos:]

# FULL: all on (trust+BC+cache+probe+privacy+revocation)
add_line("FULL",      '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=1"; fi')

p.write_text(txt)
print("[OK] Forced baseline flags + added BC_ALWAYS_QUERY in make_publishable_results.sh")
