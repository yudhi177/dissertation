from pathlib import Path
import re

targets = [
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
]

def patch_file(p: Path):
    if not p.exists():
        return
    txt = p.read_text()

    # 1) Gate Print BC stats: if enableBlockchain is OFF -> print zeros and return
    if "// BC_STATS_GATE_BEGIN" not in txt:
        # find the print line for [BC]
        m = re.search(r'(std::cout\s*<<\s*"\[BC\] queries=".*?;\s*)', txt, flags=re.S)
        if m:
            start = m.start()
            # insert a guard a few lines above the BC print line
            guard = r'''
// BC_STATS_GATE_BEGIN
  if (!g_enableBlockchain)
  {
    std::cout << "[BC] queries=0 updates=0 cacheHits=0 cacheMisses=0 hitRate=0 avgQms=0 avgUms=0" << std::endl;
    return;
  }
// BC_STATS_GATE_END
'''
            txt = txt[:start] + guard + txt[start:]
        else:
            print("[WARN] Could not find [BC] print line in", p)

    # 2) Gate BC update accounting: if enableBlockchain OFF -> do not count updates/delays
    # Patch MaybeCommitTrustUpdate(...) to early-return
    pat = re.compile(r'(static\s+void\s+MaybeCommitTrustUpdate\s*\([^\)]*\)\s*\{\s*)', re.S)
    m2 = pat.search(txt)
    if m2 and "BC_COMMIT_GATE_BEGIN" not in txt[m2.end():m2.end()+400]:
        ins = m2.end()
        gate = r'''
// BC_COMMIT_GATE_BEGIN
  if (!g_enableBlockchain)
  {
    outExtraDelayMs = 0.0;
    outDidUpdate = false;
    return;
  }
// BC_COMMIT_GATE_END
'''
        txt = txt[:ins] + gate + txt[ins:]

    p.write_text(txt)
    print("[OK] Patched BC gates in:", p)

for p in targets:
    patch_file(p)
