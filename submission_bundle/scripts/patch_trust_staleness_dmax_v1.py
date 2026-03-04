from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove older block if exists
txt = re.sub(r"// TRUST_STALENESS_V1_BEGIN.*?// TRUST_STALENESS_V1_END\s*", "", txt, flags=re.S)

# Insert near other trust globals (after enableTrustEngineFinal if found)
m = re.search(r"static\s+bool\s+g_enableTrustEngineFinal.*?\n", txt)
if not m:
    # fallback: insert near g_ledgerTrust declaration
    m = re.search(r"static\s+std::vector<double>\s+g_ledgerTrust.*?\n", txt)
if not m:
    raise SystemExit("[ERR] Could not find insertion point near trust globals.")

ins = m.end()

block = r'''
// TRUST_STALENESS_V1_BEGIN
/* =========================================================
   Trust staleness control (Dmax) + staleMismatch metric
   - Tracks last-sync time per vehicle (trustAge)
   - FAST allowed only if trustAge <= trustMaxAgeMs
   - staleMismatchCount increments when cached trust differs from ledger trust while stale
========================================================= */
static uint32_t g_trustMaxAgeMs = 1000; // Dmax
static std::vector<uint64_t> g_trustLastSyncMs; // per vehicle
static uint64_t g_staleMismatchCount = 0;
static uint64_t g_staleChecks = 0;

static inline uint64_t NowMs() { return (uint64_t)Simulator::Now().GetMilliSeconds(); }

static inline void TouchTrustSync(uint32_t v)
{
  if (v >= g_trustLastSyncMs.size()) return;
  g_trustLastSyncMs[v] = NowMs();
}

static inline uint32_t TrustAgeMs(uint32_t v)
{
  if (v >= g_trustLastSyncMs.size()) return 0;
  uint64_t now = NowMs();
  uint64_t last = g_trustLastSyncMs[v];
  if (last > now) return 0;
  return (uint32_t)(now - last);
}
// TRUST_STALENESS_V1_END
'''
txt = txt[:ins] + block + txt[ins:]

# Add CLI flag
if 'cmd.AddValue("trustMaxAgeMs"' not in txt:
    m2 = re.search(r'cmd\.AddValue\("trustQueryDelayMs".*?\);\s*\n', txt)
    if not m2:
        m2 = re.search(r'cmd\.AddValue\("enableTrustEngineFinal".*?\);\s*\n', txt)
    if not m2:
        m2 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
        if not m2:
            raise SystemExit("[ERR] Could not find cmd.Parse insertion point.")
        pos = m2.start()
    else:
        pos = m2.end()
    txt = txt[:pos] + '  cmd.AddValue("trustMaxAgeMs", "Max allowed trust age for FAST auth (ms)", g_trustMaxAgeMs);\n' + txt[pos:]

# Initialize g_trustLastSyncMs once when vehicles are set up
if "g_trustLastSyncMs.assign" not in txt:
    txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                      "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  g_trustLastSyncMs.assign(g_nVehicles, NowMs());", 1)

# Hook: whenever ledger trust is updated/committed, touch sync time
# best-effort: after any line that writes g_ledgerTrust[v] = ...
txt = re.sub(r'(g_ledgerTrust\[\s*v\s*\]\s*=\s*[^;]+;)',
             r'\1\n    TouchTrustSync(v);', txt)

# Hook: gate FAST auth using trustAge in FinishHandover or decision point
# We'll patch the function that uses trustFastThresh/minThresh if we find it.
# Add additional condition: trustAgeMs <= trustMaxAgeMs
txt = re.sub(r'(trust\s*>=\s*g_trustFastThresh)',
             r'(trust >= g_trustFastThresh && TrustAgeMs(id) <= g_trustMaxAgeMs)', txt, count=1)

# staleMismatch metric: if cache is stale, compare ledger vs returned trust (approx)
# Patch inside GetTrustForHandover (function exists) after trust fetched
gt = re.search(r"static\s+double\s+GetTrustForHandover\s*\([^\)]*\)\s*\{.*?\n\}", txt, flags=re.S)
if gt and "g_staleMismatchCount" not in gt.group(0):
    func = gt.group(0)
    inject = r'''
  // staleness mismatch check (only meaningful when trust is stale)
  g_staleChecks++;
  if (TrustAgeMs(v) > g_trustMaxAgeMs && v < g_ledgerTrust.size())
  {
    // if returned trust differs from ledger trust by a small epsilon, count mismatch
    if (std::fabs(t - g_ledgerTrust[v]) > 1e-6) g_staleMismatchCount++;
  }
'''
    # insert before return
    func2 = func.replace("  return t;", inject + "\n  return t;", 1)
    txt = txt[:gt.start()] + func2 + txt[gt.end():]

# Print staleness stats before Destroy
if "STALE" not in txt:
    txt = txt.replace("PrintAuthStats();\n  Simulator::Destroy();",
                      'PrintAuthStats();\n  std::cout << "[STALE] maxAgeMs=" << g_trustMaxAgeMs'
                      ' << " staleChecks=" << g_staleChecks'
                      ' << " staleMismatch=" << g_staleMismatchCount'
                      ' << std::endl;\n  Simulator::Destroy();', 1)

p.write_text(txt)
print("[OK] Patched trust staleness Dmax + staleMismatch into:", p)
