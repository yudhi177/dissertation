from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove old forward-decl block if exists
txt = re.sub(r"// BC_CACHE_SYNC_V1_FWD_BEGIN.*?// BC_CACHE_SYNC_V1_FWD_END\s*", "", txt, flags=re.S)

m = re.search(r"\nstatic\s+void\s+TrustRecompute\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find TrustRecompute() to insert forward declarations before it.")

ins = m.start()

fwd = r'''
// BC_CACHE_SYNC_V1_FWD_BEGIN
// Forward declarations (because TrustRecompute() calls these before their definitions)
static double GetTrustScoreCached(const std::string& key, double& outExtraDelayMs, bool& outCacheHit);
static void MaybeCommitTrustUpdate(const std::string& key, double newTrust, double& outExtraDelayMs, bool& outDidUpdate);
// BC_CACHE_SYNC_V1_FWD_END
'''

txt = txt[:ins] + fwd + txt[ins:]
p.write_text(txt)
print("[OK] Inserted BC cache forward declarations into:", p)
