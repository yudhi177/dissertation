from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
txt = p.read_text()

# Add detection for enableBlockchain flag if missing
if "F_ENABLE_BC=$(pick_flag enableBlockchain)" not in txt:
    txt = txt.replace(
        "F_BC_UD=$(pick_flag bcUpdateDelayMs)\n",
        "F_BC_UD=$(pick_flag bcUpdateDelayMs)\nF_ENABLE_BC=$(pick_flag enableBlockchain)\n",
        1
    )

def insert_line_in_case(script: str, case_name: str, line: str) -> str:
    idx = script.find(f"{case_name})")
    if idx == -1:
        return script
    end = script.find(";;", idx)
    if end == -1:
        return script
    block = script[idx:end]
    if line in block:
        return script
    return script[:end] + line + "\n" + script[end:]

off_line = '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=0"; fi'
on_line  = '      if [[ -n "$F_ENABLE_BC" ]]; then args="$args --${F_ENABLE_BC}=1"; fi'

txt = insert_line_in_case(txt, "PKI_ONLY", off_line)
txt = insert_line_in_case(txt, "TRUST_ONLY", off_line)
txt = insert_line_in_case(txt, "BC_TRUST", on_line)
txt = insert_line_in_case(txt, "FULL", on_line)

p.write_text(txt)
print("[OK] enableBlockchain baseline control injected into make_publishable_results.sh")
