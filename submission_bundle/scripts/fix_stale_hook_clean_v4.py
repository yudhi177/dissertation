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

    # 1) remove accidental literal "\n" inserted into code (outside strings)
    txt = txt.replace(";\\n", ";\n")
    txt = txt.replace("\\n  ", "\n  ")

    # 2) If file already has correct veh->GetId(), remove the wrong node->GetId() injection
    if "uint32_t id = veh->GetId();" in txt:
        txt = re.sub(r"^\s*uint32_t\s+id\s*=\s*node->GetId\(\);\s*\n", "", txt, flags=re.M)

    # 3) Ensure RecordStaleCheck is called right after TrustAgeMs(id) line
    # Insert ONLY if it isn't already in the nearby block
    pat = r"(uint32_t\s+ageMs\s*=\s*TrustAgeMs\(id\)\s*;\s*\n)"
    def repl(m):
        after = m.group(1)
        # look ahead a little to avoid duplicate insertion
        idx = txt.find(after)
        window = txt[idx: idx + 250] if idx != -1 else ""
        if "RecordStaleCheck(id" in window:
            return after
        return after + "  RecordStaleCheck(id, trust, cacheHit, ageMs);\n"

    txt2, n = re.subn(pat, repl, txt, count=1)
    txt = txt2

    p.write_text(txt)
    print("[OK] stale hook cleaned + wired in:", p)

