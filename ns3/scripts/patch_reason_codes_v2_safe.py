from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Remove any previous broken insert of reason block (if partially inserted)
    txt = re.sub(r"// REASON_CODES_V1_BEGIN.*?// REASON_CODES_V1_END\s*", "", txt, flags=re.S)

    # ---- Pure string tagging (compile-safe, no stream variable needed) ----
    # Data drops
    txt = txt.replace("DATA_DROP_SIG",      "DATA_DROP_SIG reason=BAD_SIG")
    txt = txt.replace("DATA_DROP_REPLAY",   "DATA_DROP_REPLAY reason=REPLAY")
    txt = txt.replace("DATA_DROP_REVOKED",  "DATA_DROP_REVOKED reason=REVOKED")

    # Auth fails (if you already log reasons, this won't hurt)
    txt = txt.replace("AUTH_FAIL", "AUTH_FAIL")  # keep

    # Handover reject: best-effort tagging based on keywords (won't break compile)
    txt = re.sub(r"(HO_REJECT[^\n\"]*trust)", r"\1 reason=LOW_TRUST", txt)
    txt = re.sub(r"(HO_REJECT[^\n\"]*stale)", r"\1 reason=STALE_TRUST", txt)
    txt = re.sub(r"(HO_REJECT[^\n\"]*revok)", r"\1 reason=REVOKED", txt)

    p.write_text(txt)
    print("[OK] Tagged reason=... tokens in:", p)
