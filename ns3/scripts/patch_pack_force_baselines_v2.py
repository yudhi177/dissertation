from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

def insert_after(line_pat: str, insertion: str):
    global txt
    if insertion.strip() in txt:
        return
    m = re.search(line_pat, txt, flags=re.M)
    if not m:
        raise SystemExit(f"[ERR] Could not find insertion anchor: {line_pat}")
    pos = m.end()
    txt = txt[:pos] + insertion + txt[pos:]

# 1) Ensure flags detection for enableBlockchain + bcProbe exists
# Anchor after bcUpdateDelayMs pick
insert_after(r'^\s*F_BC_UD=\$\(pick_flag bcUpdateDelayMs\)\s*$',
             '\nF_ENABLE_BC=$(pick_flag enableBlockchain)\n'
             'F_BC_PROBE=$(pick_flag enableBcProbe)\n'
             'F_BC_PROBE_INT=$(pick_flag bcProbeIntervalMs)\n'
             'F_BC_PROBE_PSEU=$(pick_flag bcProbeUsePseudonym)\n')

# 2) Ensure BC_ALWAYS_QUERY is in BASELINES list
m = re.search(r'BASELINES=\(([^)]*)\)', txt)
if m and "BC_ALWAYS_QUERY" not in m.group(1):
    new = m.group(0).replace("BC_TRUST", "BC_TRUST BC_ALWAYS_QUERY")
    txt = txt.replace(m.group(0), new, 1)

def add_line_in_case(case_name: str, line: str):
    global txt
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

# 3) Force baseline behavior
# PKI_ONLY: everything OFF
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=0"; fi')
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi')
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=0"; fi')
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line_in_case("PKI_ONLY",  '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# TRUST_ONLY: Trust ON, Blockchain OFF, Cache OFF, Probe OFF, Privacy OFF, Revocation OFF
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi')
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=0"; fi')
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line_in_case("TRUST_ONLY",'      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# BC_TRUST: Trust ON, BC ON, Cache ON, Probe ON, Privacy OFF, Revocation OFF
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi')
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi')
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi')
add_line_in_case("BC_TRUST",  '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi')

# Add BC_ALWAYS_QUERY case if missing
if "BC_ALWAYS_QUERY)" not in txt:
    pos = txt.find("BC_TRUST)")
    if pos != -1:
        end = txt.find(";;", pos)
        if end != -1:
            insert_pos = end + 2
            txt = txt[:insert_pos] + r'''
    BC_ALWAYS_QUERY)
      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi
      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi
      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=0"; fi
      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi
      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=0"; fi
      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=0"; fi
      ;;
''' + txt[insert_pos:]

# FULL: all ON
add_line_in_case("FULL",      '      if [[ -n "$F_TRUST" ]]; then args="$args --${F_TRUST}=1"; fi')
add_line_in_case("FULL",      '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')
add_line_in_case("FULL",      '      if [[ -n "$F_BC_CACHE" ]]; then args="$args --${F_BC_CACHE}=1"; fi')
add_line_in_case("FULL",      '      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${F_BC_PROBE}=1"; fi')
add_line_in_case("FULL",      '      if [[ -n "$F_REV" ]]; then args="$args --${F_REV}=1"; fi')
add_line_in_case("FULL",      '      if [[ -n "$F_PRIV" ]]; then args="$args --${F_PRIV}=1"; fi')

p.write_text(txt)
print("[OK] Patched make_publishable_results.sh: forced baselines + added enableBlockchain/probe picks + BC_ALWAYS_QUERY")
