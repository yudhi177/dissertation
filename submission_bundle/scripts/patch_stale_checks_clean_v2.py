from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

def find_func_block(txt: str, name: str):
    m = re.search(rf"\bstatic\s+void\s+{re.escape(name)}\s*\([^\)]*\)\s*\{{", txt)
    if not m:
        return None
    start = m.start()
    brace_start = txt.find("{", m.end()-1)
    if brace_start == -1:
        return None
    i = brace_start
    depth = 0
    while i < len(txt):
        if txt[i] == "{":
            depth += 1
        elif txt[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return (start, end, txt[start:end])
        i += 1
    return None

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Remove older clean block if exists
    txt = re.sub(r"// STALE_CHECK_HOOK_V2_BEGIN.*?// STALE_CHECK_HOOK_V2_END\s*", "", txt, flags=re.S)

    # Ensure <cmath>
    if "#include <cmath>" not in txt:
        txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <cmath>\n", 1)

    # Insert helper after TRUST_STALENESS_V1_END if present else after using namespace
    anchor = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
    if not anchor:
        anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not anchor:
        raise SystemExit(f"[ERR] Cannot find anchor in {p}")

    ins = anchor.end()
    helper = """
// STALE_CHECK_HOOK_V2_BEGIN
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
// STALE_CHECK_HOOK_V2_END
"""
    if "RecordStaleCheck(" not in txt:
        txt = txt[:ins] + helper + txt[ins:]

    # Ensure cmd flag staleEps exists (after trustMaxAgeMs flag)
    if 'cmd.AddValue("staleEps"' not in txt:
        m = re.search(r'cmd\.AddValue\("trustMaxAgeMs".*?\);\s*\n', txt)
        if m:
            pos = m.end()
            txt = txt[:pos] + '  cmd.AddValue("staleEps", "Stale mismatch epsilon threshold", g_staleEps);\n' + txt[pos:]

    # Patch ONLY inside CheckHandover()
    fb = find_func_block(txt, "CheckHandover")
    if fb:
        start, end, func = fb

        if "RecordStaleCheck(" not in func:
            # find trust line
            mtrust = re.search(r'^\s*double\s+trust\s*=.*?;\s*$', func, flags=re.M)
            if mtrust:
                insert_pos = mtrust.end()

                # ensure cacheHit exists in this function (before trust line)
                if not re.search(r'\bbool\s+cacheHit\b', func):
                    func = func[:mtrust.start()] + "  bool cacheHit = false;\n" + func[mtrust.start():]
                    # recompute trust line after modification
                    mtrust = re.search(r'^\s*double\s+trust\s*=.*?;\s*$', func, flags=re.M)
                    insert_pos = mtrust.end()

                inject = "\n  uint32_t ageMs = TrustAgeMs(id);\n  RecordStaleCheck(id, trust, cacheHit, ageMs);\n"
                func = func[:insert_pos] + inject + func[insert_pos:]

                txt = txt[:start] + func + txt[end:]

    p.write_text(txt)
    print("[OK] Clean staleChecks hook patched in:", p)
