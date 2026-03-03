from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

BLOCK = r'''
// STALE_SAMPLING_GATE_V2_BEGIN
#include <cmath>

static double g_staleEps = 0.02;  // mismatch threshold

static inline void RecordStaleCheck(uint32_t v, double usedTrust, bool cacheHit, uint32_t ageMs)
{
  g_staleChecks++;

  // mismatch only meaningful on cacheHit AND stale
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

    # 0) remove older stale sampling blocks + staleEps flag line if any
    txt = re.sub(r"// STALE_SAMPLING_GATE_V1_BEGIN.*?// STALE_SAMPLING_GATE_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// STALE_SAMPLING_GATE_V2_BEGIN.*?// STALE_SAMPLING_GATE_V2_END\s*", "", txt, flags=re.S)
    txt = re.sub(r'^\s*cmd\.AddValue\("staleEps".*?\);\s*\n', "", txt, flags=re.M)

    # 1) insert block immediately after TRUST_STALENESS end (this is BEFORE CheckHandover)
    m = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] TRUST_STALENESS_V1_END not found in {p}")
    ins = m.end()
    txt = txt[:ins] + BLOCK + txt[ins:]

    # 2) add cmd flag staleEps right after trustMaxAgeMs flag (safe place)
    if 'cmd.AddValue("staleEps"' not in txt:
        m2 = re.search(r'^\s*cmd\.AddValue\("trustMaxAgeMs".*?\);\s*$', txt, flags=re.M)
        if m2:
            pos2 = m2.end()
            txt = txt[:pos2] + '\n  cmd.AddValue("staleEps", "Stale mismatch epsilon threshold", g_staleEps);\n' + txt[pos2:]
        else:
            # fallback: insert before cmd.Parse
            mp = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
            if not mp:
                raise SystemExit(f"[ERR] cmd.Parse not found in {p}")
            pos2 = mp.start()
            txt = txt[:pos2] + '  cmd.AddValue("staleEps", "Stale mismatch epsilon threshold", g_staleEps);\n' + txt[pos2:]

    # 3) ensure trustLastSync vector is initialized (else TouchTrustSync does nothing)
    if "g_trustLastSyncMs.assign" not in txt:
        # place after g_trustScore.assign(...) first occurrence
        txt = txt.replace(
            "g_trustScore.assign(g_nVehicles, 0.80);",
            "g_trustScore.assign(g_nVehicles, 0.80);\n"
            "  g_trustLastSyncMs.assign(g_nVehicles, NowMs());\n",
            1
        )

    # 4) Make sure freshOk is actually USED in FAST decision to avoid unused warning
    # If there's an if(...) containing g_trustFastThresh, append && freshOk unless already present.
    txt = re.sub(
        r"(if\s*\([^\)]*g_trustFastThresh[^\)]*)\)(\s*\{?)",
        lambda m: (m.group(1) + (" && freshOk" if "freshOk" not in m.group(1) else "") + ")" + m.group(2)),
        txt,
        count=1
    )

    p.write_text(txt)
    print("[OK] Fixed stale sampling compile + staleEps flag in:", p)
