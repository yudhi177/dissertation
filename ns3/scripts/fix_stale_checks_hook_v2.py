from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

STALE_HELPER = r'''
// STALE_SAMPLING_GATE_V2_BEGIN
static double g_staleEps = 0.02;  // mismatch threshold (absolute trust diff)

static inline void RecordStaleCheck(uint32_t v, double usedTrust, bool cacheHit, uint32_t ageMs)
{
  // Count checks always (so staleChecks becomes meaningful)
  g_staleChecks++;

  // mismatch meaningful on cacheHit AND stale
  if (cacheHit && (ageMs > g_trustMaxAgeMs) && (v < g_ledgerTrust.size()))
  {
    const double ledger = g_ledgerTrust[v];
    const double diff = std::fabs(usedTrust - ledger);
    if (diff > g_staleEps) g_staleMismatchCount++;
  }
}
// STALE_SAMPLING_GATE_V2_END
'''

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    # Ensure <cmath> exists for std::fabs
    if "#include <cmath>" not in txt:
        m = re.search(r"#include\s*<iostream>\s*\n", txt)
        if m:
            pos = m.end()
            txt = txt[:pos] + "#include <cmath>\n" + txt[pos:]
        else:
            txt = "#include <cmath>\n" + txt

    # Remove older stale sampling blocks (v1/v2)
    txt = re.sub(r"// STALE_SAMPLING_GATE_V1_BEGIN.*?// STALE_SAMPLING_GATE_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// STALE_SAMPLING_GATE_V2_BEGIN.*?// STALE_SAMPLING_GATE_V2_END\s*", "", txt, flags=re.S)

    # Insert helper right after PrintStaleStats() (best anchor), else after TRUST_STALENESS_V1_END
    anchor = re.search(r"static\s+void\s+PrintStaleStats\s*\(\)\s*\{.*?\n\}\s*\n", txt, flags=re.S)
    if anchor:
        ins = anchor.end()
        txt = txt[:ins] + STALE_HELPER + txt[ins:]
    else:
        a2 = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
        if not a2:
            raise SystemExit(f"[ERR] Could not find staleness anchor in {p}")
        ins = a2.end()
        txt = txt[:ins] + STALE_HELPER + txt[ins:]

    # Hook call inside CheckHandover:
    # You already have: ageMs + freshOk in that function (as per warning).
    # Insert RecordStaleCheck right after freshOk line.
    pat = r'^\s*const\s+bool\s+freshOk\s*=\s*\(ageMs\s*<=\s*g_trustMaxAgeMs\)\s*;\s*$'
    m3 = re.search(pat, txt, flags=re.M)
    if m3:
        pos = m3.end()
        inject = "\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n  (void)freshOk;\n"
        if "RecordStaleCheck(id, trust, cacheHit, ageMs);" not in txt[m3.start():m3.start()+300]:
            txt = txt[:pos] + inject + txt[pos:]
    else:
        print("[WARN] freshOk line not found; skipping hook insert in", p)

    # Clean warning: AuthInitKeys defined-but-not-used (safe GCC attribute)
    txt = re.sub(r'\bstatic\s+void\s+AuthInitKeys\s*\(',
                 'static void __attribute__((unused)) AuthInitKeys(', txt)

    p.write_text(txt)
    print("[OK] stale hook + warnings patch applied:", p)
