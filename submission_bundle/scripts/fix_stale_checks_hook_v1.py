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

    # 1) Ensure helper exists: RecordStaleCheck (if not already)
    if "RecordStaleCheck(" not in txt:
        m = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
        if not m:
            raise SystemExit(f"[ERR] TRUST_STALENESS_V1_END not found in {p}")
        ins = m.end()
        helper = r'''
// STALE_CHECK_HOOK_V1_BEGIN
static double g_staleEps = 0.02;  // mismatch threshold

static inline void RecordStaleCheck(uint32_t v, double usedTrust, bool cacheHit, uint32_t ageMs)
{
  g_staleChecks++;
  if (cacheHit && (ageMs > g_trustMaxAgeMs) && (v < g_ledgerTrust.size()))
  {
    double ledger = g_ledgerTrust[v];
    double diff = std::fabs(usedTrust - ledger);
    if (diff > g_staleEps) g_staleMismatchCount++;
  }
}
// STALE_CHECK_HOOK_V1_END
'''
        # ensure <cmath> exists for fabs
        if "#include <cmath>" not in txt:
            txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <cmath>\n", 1)
        txt = txt[:ins] + helper + txt[ins:]

    # 2) Ensure cmd flag exists for staleEps (optional)
    if 'cmd.AddValue("staleEps"' not in txt:
        m = re.search(r'cmd\.AddValue\("trustMaxAgeMs".*?\);\s*\n', txt)
        if m:
            pos = m.end()
            txt = txt[:pos] + '  cmd.AddValue("staleEps", "Stale mismatch epsilon threshold", g_staleEps);\n' + txt[pos:]

    # 3) Inject RecordStaleCheck call inside CheckHandover after trust is computed
    ch = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
    if ch:
        # Look for pattern: bool cacheHit ...; double trust = GetTrustForHandover(... &cacheHit ...)
        # If found, inject after 'double trust = ...;' line.
        m = re.search(r"(bool\s+cacheHit\s*=\s*false\s*;\s*\n.*?\n\s*double\s+trust\s*=\s*GetTrustForHandover[^\n]*;\s*\n)",
                      txt, flags=re.S)
        if m and "RecordStaleCheck(" not in m.group(1):
            block = m.group(1)
            inject = r"  uint32_t ageMs = TrustAgeMs(id);\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n"
            newblock = block + inject
            txt = txt.replace(block, newblock, 1)
        else:
            # fallback: if trust line exists without cacheHit, still count checks
            m2 = re.search(r"(\n\s*double\s+trust\s*=.*?;\s*\n)", txt)
            if m2 and "RecordStaleCheck(" not in txt[m2.start():m2.start()+250]:
                inject = r"  bool cacheHit = false;\n  uint32_t ageMs = TrustAgeMs(id);\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n"
                txt = txt[:m2.end()] + inject + txt[m2.end():]

    # 4) Ensure trustLastSync vector initialized (so age works)
    if "g_trustLastSyncMs.assign" not in txt:
        # Insert right after ledger init if present
        if "g_ledgerTrust.assign" in txt:
            txt = txt.replace(
                "g_ledgerTrust.assign(g_nVehicles, 0.8);",
                "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  g_trustLastSyncMs.assign(g_nVehicles, NowMs());",
                1
            )

    p.write_text(txt)
    print("[OK] staleChecks hook added in:", p)

