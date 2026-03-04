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

    # Remove older block if exists
    txt = re.sub(r"// STALE_SAMPLING_GATE_V1_BEGIN.*?// STALE_SAMPLING_GATE_V1_END\s*", "", txt, flags=re.S)

    # 1) Insert helper near PrintStaleStats or TRUST_STALENESS block end
    anchor = re.search(r"static void PrintStaleStats\(\)\s*\{.*?\n\}\s*\n", txt, flags=re.S)
    if not anchor:
        m2 = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
        if not m2:
            raise SystemExit(f"[ERR] Could not find staleness anchor in {p}")
        ins = m2.end()
    else:
        ins = anchor.end()

    helper = r'''
// STALE_SAMPLING_GATE_V1_BEGIN
static double g_staleEps = 0.02;  // mismatch threshold

static inline void RecordStaleCheck(uint32_t v, double usedTrust, bool cacheHit, uint32_t ageMs)
{
  // count checks always (only meaningful when trust engine enabled)
  g_staleChecks++;

  // mismatch only meaningful on cacheHit AND stale
  if (cacheHit && (ageMs > g_trustMaxAgeMs) && (v < g_ledgerTrust.size()))
  {
    double ledger = g_ledgerTrust[v];
    double diff = std::fabs(usedTrust - ledger);
    if (diff > g_staleEps) g_staleMismatchCount++;
  }
}
// STALE_SAMPLING_GATE_V1_END
'''
    if "RecordStaleCheck(" not in txt:
        txt = txt[:ins] + helper + txt[ins:]

    # 2) Ensure cmd flag for staleEps exists (optional)
    if 'cmd.AddValue("staleEps"' not in txt:
        txt = txt.replace('cmd.AddValue("trustMaxAgeMs"', 
                          'cmd.AddValue("staleEps", "Stale mismatch epsilon threshold", g_staleEps);\n  cmd.AddValue("trustMaxAgeMs"', 1)

    # 3) Insert freshness computation right after GetTrustForHandover(...) call
    pat = re.compile(r"(double\s+trust\s*=\s*GetTrustForHandover\s*\(\s*id\s*,\s*&extraTrustDelayMs\s*,\s*&cacheHit\s*\)\s*;\s*\n)")
    m = pat.search(txt)
    if not m:
        # fallback: any GetTrustForHandover(id,
        pat2 = re.compile(r"(double\s+trust\s*=\s*GetTrustForHandover\s*\(\s*id[^\)]*\)\s*;\s*\n)")
        m = pat2.search(txt)
    if not m:
        raise SystemExit(f"[ERR] Could not find trust=GetTrustForHandover(id..) line in {p}")

    inject = r'''
  // Freshness gating (Δmax)
  if (!cacheHit) { TouchTrustSync(id); }  // only on miss we refresh "last sync"
  const uint32_t ageMs = TrustAgeMs(id);
  const bool freshOk = (ageMs <= g_trustMaxAgeMs);

  RecordStaleCheck(id, trust, cacheHit, ageMs);
'''
    if "const bool freshOk" not in txt[m.end():m.end()+400]:
        txt = txt[:m.end()] + inject + txt[m.end():]

    # 4) Gate FAST condition by freshOk (and confOk if present)
    # common variants:
    # if ((trust >= g_trustFastThresh) && confOk)
    # if (trust >= g_trustFastThresh)
    if "&& freshOk" not in txt:
        txt = re.sub(r"if\s*\(\s*\(\s*trust\s*>=\s*g_trustFastThresh\s*\)\s*&&\s*confOk\s*\)",
                     "if (((trust >= g_trustFastThresh) && confOk) && freshOk)", txt, count=1)
        txt = re.sub(r"if\s*\(\s*trust\s*>=\s*g_trustFastThresh\s*\)",
                     "if ((trust >= g_trustFastThresh) && freshOk)", txt, count=1)

    p.write_text(txt)
    print("[OK] Patched stale sampling + freshOk FAST gate in:", p)
