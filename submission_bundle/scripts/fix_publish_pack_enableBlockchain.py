from pathlib import Path

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

if "F_ENABLE_BC=$(pick_flag enableBlockchain)" not in txt:
    txt = txt.replace('F_BC_UD=$(pick_flag bcUpdateDelayMs)\n',
                      'F_BC_UD=$(pick_flag bcUpdateDelayMs)\nF_ENABLE_BC=$(pick_flag enableBlockchain)\n', 1)

def add_line(case_name, line):
    nonlocal txt
    idx = txt.find(f"{case_name})")
    if idx == -1: return
    end = txt.find(";;", idx)
    if end == -1: return
    block = txt[idx:end]
    if line in block: return
    txt = txt[:end] + line + "\n" + txt[end:]

add_line("PKI_ONLY",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line("TRUST_ONLY",'      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi')
add_line("BC_TRUST",  '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')
add_line("FULL",      '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi')

p.write_text(txt)
print("[OK] Patched enableBlockchain baseline control.")
