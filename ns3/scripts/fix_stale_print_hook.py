from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# ensure staleness function exists
if "static void PrintStaleStats()" not in txt:
    m = re.search(r"// TRUST_STALENESS_V1_END\s*\n", txt)
    if not m:
        raise SystemExit("[ERR] TRUST_STALENESS_V1_END not found.")
    ins = m.end()
    txt = txt[:ins] + r'''
static void PrintStaleStats()
{
  const double rate = g_staleChecks ? (double)g_staleMismatchCount / (double)g_staleChecks : 0.0;
  std::cout << "[STALE] maxAgeMs=" << g_trustMaxAgeMs
            << " staleChecks=" << g_staleChecks
            << " staleMismatch=" << g_staleMismatchCount
            << " mismatchRate=" << rate
            << std::endl;
}
''' + txt[ins:]

# remove old calls if any
txt = re.sub(r'^\s*PrintStaleStats\(\);\s*\n', '', txt, flags=re.M)

# insert call before Simulator::Destroy()
txt = txt.replace("Simulator::Destroy();", "  PrintStaleStats();\n  Simulator::Destroy();", 1)

p.write_text(txt)
print("[OK] PrintStaleStats hook added:", p)
