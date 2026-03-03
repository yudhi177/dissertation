from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove older probe block if exists
txt = re.sub(r"// BC_PROBE_V1_BEGIN.*?// BC_PROBE_V1_END\s*", "", txt, flags=re.S)

# Insert AFTER privacy block end marker
m = re.search(r"//\s*PRIVACY_PSEUDONYM_V1_END\s*\n", txt)
if not m:
    raise SystemExit("[ERR] Could not find PRIVACY_PSEUDONYM_V1_END marker.")

ins = m.end()

probe_block = r'''
// BC_PROBE_V1_BEGIN
/* =========================================================
   BC Probe (v1)
   - Periodically queries trust via GetTrustScoreCached()
   - Makes bcQueries/cacheHitRate measurable even without handovers
========================================================= */
static bool     g_enableBcProbe = false;
static uint32_t g_bcProbeIntervalMs = 200;   // query period per vehicle
static bool     g_bcProbeUsePseudonym = true;

static void BcProbeTick(uint32_t v)
{
  if (!g_enableBcProbe) return;

  double dms = 0.0;
  bool hit = false;

  std::string key = std::to_string(v);
  if (g_bcProbeUsePseudonym && g_enablePrivacy)
  {
    key = GetActivePseudo(v);
  }

  (void)GetTrustScoreCached(key, dms, hit);
  Simulator::Schedule(MilliSeconds(g_bcProbeIntervalMs), &BcProbeTick, v);
}

static void StartBcProbes()
{
  if (!g_enableBcProbe) return;
  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    Simulator::Schedule(MilliSeconds(50 + (v % 10)), &BcProbeTick, v);
  }
}
// BC_PROBE_V1_END
'''
txt = txt[:ins] + probe_block + txt[ins:]

# Add CLI flags
flags = r'''
  cmd.AddValue("enableBcProbe", "Enable periodic BC trust queries (probe workload)", g_enableBcProbe);
  cmd.AddValue("bcProbeIntervalMs", "BC probe interval per vehicle (ms)", g_bcProbeIntervalMs);
  cmd.AddValue("bcProbeUsePseudonym", "Probe uses active pseudonym key when privacy enabled", g_bcProbeUsePseudonym);
'''

if 'cmd.AddValue("enableBcProbe"' not in txt:
    m2 = re.search(r'cmd\.AddValue\("mixRadiusM".*?\);\s*\n', txt)
    if m2:
        pos = m2.end()
        txt = txt[:pos] + flags + txt[pos:]
    else:
        m3 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
        if not m3:
            raise SystemExit("[ERR] Could not find cmd.Parse(argc, argv);")
        pos = m3.start()
        txt = txt[:pos] + flags + txt[pos:]

# Call StartBcProbes() after PrivacyInit() (or after ledger init)
if "StartBcProbes();" not in txt:
    if "  PrivacyInit();" in txt:
        txt = txt.replace("  PrivacyInit();", "  PrivacyInit();\n  StartBcProbes();", 1)
    else:
        txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                          "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  StartBcProbes();", 1)

p.write_text(txt)
print("[OK] Patched BC probe v1 into:", p)
