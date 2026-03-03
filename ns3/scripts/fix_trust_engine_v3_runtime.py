from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# ------------------------------------------------------------
# 1) Remove ALL stray calls "TrustInit();" (we will add exactly one in main)
# ------------------------------------------------------------
txt = re.sub(r'^\s*TrustInit\(\);\s*\n', '', txt, flags=re.M)

# ------------------------------------------------------------
# 2) Insert TrustInit() call in main() AFTER trust ledger init
#    (only inside main area, so it never lands inside TrustInit() function)
# ------------------------------------------------------------
m = re.search(r'\bint\s+main\s*\(', txt)
if not m:
    raise SystemExit("[ERR] Could not find int main(")

pre = txt[:m.start()]
main_and_after = txt[m.start():]

# Prefer inserting after comment "// Trust ledger init"
pat1 = r'(//\s*Trust ledger init\s*\n\s*g_ledgerTrust\.assign\([^\n]*\);\s*\n)'
if re.search(pat1, main_and_after):
    main_and_after = re.sub(pat1, r'\1  TrustInit();\n', main_and_after, count=1)
else:
    # fallback: insert after first g_ledgerTrust.assign in main
    pat2 = r'(g_ledgerTrust\.assign\([^\n]*\);\s*\n)'
    if re.search(pat2, main_and_after):
        main_and_after = re.sub(pat2, r'\1  TrustInit();\n', main_and_after, count=1)
    else:
        raise SystemExit("[ERR] Could not find g_ledgerTrust.assign(...) in main to place TrustInit().")

txt = pre + main_and_after

# ------------------------------------------------------------
# 3) Make TrustEvidenceGood/Bad actually USED (remove warnings + enable trust model)
#    - add before return on drops
#    - add after successful rx
# ------------------------------------------------------------
if "TrustEvidenceBad(hdr.senderId);" not in txt:
    # Replay drop: add before return
    txt = re.sub(
        r'(g_replayDrops\+\+;\s*\n\s*LogEvent\([\s\S]*?DATA_DROP_REPLAY[\s\S]*?\);\s*\n\s*)return;',
        r'\1TrustEvidenceBad(hdr.senderId);\n    return;',
        txt,
        count=1
    )
    # Sig drop: add before return
    txt = re.sub(
        r'(g_sigDrops\+\+;\s*\n\s*LogEvent\([\s\S]*?DATA_DROP_SIG[\s\S]*?\);\s*\n\s*)return;',
        r'\1TrustEvidenceBad(hdr.senderId);\n    return;',
        txt,
        count=1
    )

if "TrustEvidenceGood(hdr.senderId);" not in txt:
    txt = re.sub(
        r'(g_rxBytes\s*\+\=\s*pktSize;\s*\n)',
        r'\1  TrustEvidenceGood(hdr.senderId);\n',
        txt,
        count=1
    )

# ------------------------------------------------------------
# 4) Safety guards to prevent crash even if someone forgets init
# ------------------------------------------------------------
# In ApplyRsuFeedback: ensure vectors sized
txt = re.sub(
    r'(static void ApplyRsuFeedback\([\s\S]*?\)\s*\{\s*\n)([\s\S]*?)\n\}',
    lambda mm: mm.group(0) if "if (g_rsuFeedback.size()" in mm.group(0) else (
        mm.group(1)
        + '  if (g_rsuFeedback.size() < g_nVehicles) return; // safety\n'
        + mm.group(2)
        + '\n}'
    ),
    txt,
    count=1
)

# In GetTrustForHandover: ensure cache vectors sized
txt = re.sub(
    r'(static double GetTrustForHandover\([\s\S]*?\)\s*\{\s*\n)',
    r'\1  if (g_cacheTrust.size() < g_nVehicles || g_cacheTime.size() < g_nVehicles) {\n'
    r'    // safety fallback\n'
    r'    return (v < g_ledgerTrust.size()) ? g_ledgerTrust[v] : 0.5;\n'
    r'  }\n',
    txt,
    count=1
)

p.write_text(txt)
print("[OK] Trust Engine v3 runtime fix applied:", p)
