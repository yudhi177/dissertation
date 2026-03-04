from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scripts/make_publishable_results.sh"
if not p.exists():
    raise SystemExit("[ERR] make_publishable_results.sh not found. Create it first (the baseline pack script).")

txt = p.read_text()

# Add flag detection lines (if missing)
if "F_BC_PROBE=" not in txt:
    txt = txt.replace(
        'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n',
        'F_BC_UD=$(pick_flag bcUpdateDelayMs)\n'
        'F_BC_PROBE=$(pick_flag enableBcProbe)\n'
        'F_BC_PROBE_INT=$(pick_flag bcProbeIntervalMs)\n'
        'F_BC_PROBE_PSEU=$(pick_flag bcProbeUsePseudonym)\n'
    )

# Add to info print (optional)
if "bcProbe" not in txt:
    txt = txt.replace(
        'echo " bcCache=$F_BC_CACHE bcSync=$F_BC_SYNC bcQDelay=$F_BC_QD bcUDelay=$F_BC_UD"\n',
        'echo " bcCache=$F_BC_CACHE bcSync=$F_BC_SYNC bcQDelay=$F_BC_QD bcUDelay=$F_BC_UD"\n'
        'echo " bcProbe=$F_BC_PROBE bcProbeInt=$F_BC_PROBE_INT bcProbePseu=$F_BC_PROBE_PSEU"\n'
    )

def inject_probe(case_label: str) -> str:
    # enable probe only if flags exist
    return (
        f'\n      if [[ -n "$F_BC_PROBE" ]]; then args="$args --${{F_BC_PROBE}}=1"; fi'
        f'\n      if [[ -n "$F_BC_PROBE_INT" ]]; then args="$args --${{F_BC_PROBE_INT}}=200"; fi'
        f'\n      if [[ -n "$F_BC_PROBE_PSEU" ]]; then args="$args --${{F_BC_PROBE_PSEU}}=1"; fi'
    )

# Insert probe args inside BC_TRUST and FULL cases (if not already)
for label in ["BC_TRUST", "FULL"]:
    marker = f"{label})"
    idx = txt.find(marker)
    if idx == -1:
        continue
    block_end = txt.find(";;", idx)
    if block_end == -1:
        continue
    block = txt[idx:block_end]
    if "F_BC_PROBE" in block:
        continue
    # add just before ;; inside that case
    txt = txt[:block_end] + inject_probe(label) + "\n" + txt[block_end:]

p.write_text(txt)
print("[OK] Patched make_publishable_results.sh to enable BC probe in BC_TRUST + FULL")
