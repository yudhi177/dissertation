from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Remove the broken privacy block (the one we injected)
txt = re.sub(r"// PRIVACY_PSEUDONYM_V1_BEGIN.*?// PRIVACY_PSEUDONYM_V1_END\s*", "", txt, flags=re.S)

# 2) Remove duplicate CLI AddValue for privacy flags (we will insert once cleanly)
txt = re.sub(r'^\s*cmd\.AddValue\("enablePrivacy".*\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\("pseudoPoolSize".*\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\("pseudoRotateIntervalS".*\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\("rotateOnHandover".*\);\s*\n', '', txt, flags=re.M)
txt = re.sub(r'^\s*cmd\.AddValue\("linkWindowS".*\);\s*\n', '', txt, flags=re.M)

# 3) Remove any duplicate PrivacyInit(); calls (we'll insert one)
txt = re.sub(r'^\s*PrivacyInit\(\);\s*\n', '', txt, flags=re.M)

# 4) Insert a clean privacy implementation block before GetTrustForHandover()
m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find GetTrustForHandover() insertion point.")
ins = m.start()

privacy_block = r'''
// PRIVACY_PSEUDONYM_V1_BEGIN
/* =========================================================
   PRIVACY (v1): Pseudonym Pool + Rotation + Linkability metric
   - Uses existing globals already in your file:
     g_enablePrivacy, g_pseudoPoolSize, g_pseudoRotateIntervalS,
     g_rotateOnHandover, g_linkWindowS, g_pseudoRotations,
     g_linkAttempts, g_linkSuccess
   - Adds only the missing pool state + functions (no redefinitions)
========================================================= */
static std::vector<std::vector<std::string>> g_pseudoPool;
static std::vector<uint32_t> g_pseudoIdx;
static std::vector<double>   g_lastRotateS;

static std::string MakePseudo(uint32_t v, uint32_t k)
{
  return std::to_string(v) + "_P" + std::to_string(k);
}

static const std::string& GetActivePseudo(uint32_t v)
{
  return g_pseudoPool[v][g_pseudoIdx[v] % g_pseudoPool[v].size()];
}

static void PrivacyRotate(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_pseudoPool.size()) return;
  if (g_pseudoPool[v].empty()) return;

  const double now = Simulator::Now().GetSeconds();
  const double prev = g_lastRotateS[v];
  const std::string oldP = GetActivePseudo(v);

  g_pseudoIdx[v] = (g_pseudoIdx[v] + 1) % (uint32_t)g_pseudoPool[v].size();
  g_lastRotateS[v] = now;
  const std::string newP = GetActivePseudo(v);

  (void)reason; (void)oldP; (void)newP;

  g_pseudoRotations++;

  // Linkability metric (simple continuity attacker):
  // if rotations happen within a short time window, attacker can link old->new.
  if (prev > -1e8)
  {
    g_linkAttempts++;
    if ((now - prev) <= g_linkWindowS) g_linkSuccess++;
  }
}

static void PrivacyRotateTimer(uint32_t v)
{
  if (!g_enablePrivacy) return;
  PrivacyRotate(v, "TIMER");
  Simulator::Schedule(Seconds(g_pseudoRotateIntervalS), &PrivacyRotateTimer, v);
}

static void PrivacyInit()
{
  if (!g_enablePrivacy) return;

  g_pseudoPool.assign(g_nVehicles, {});
  g_pseudoIdx.assign(g_nVehicles, 0);
  g_lastRotateS.assign(g_nVehicles, -1e9);

  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    g_pseudoPool[v].reserve(g_pseudoPoolSize);
    for (uint32_t k = 0; k < g_pseudoPoolSize; ++k)
      g_pseudoPool[v].push_back(MakePseudo(v, k));
  }

  for (uint32_t v = 0; v < g_nVehicles; ++v)
    Simulator::Schedule(Seconds(g_pseudoRotateIntervalS), &PrivacyRotateTimer, v);
}

static void PrintPrivacyStats()
{
  const double rate = g_linkAttempts ? (double)g_linkSuccess / (double)g_linkAttempts : 0.0;
  std::cout << "[PRIV] rotations=" << g_pseudoRotations
            << " linkAttempts=" << g_linkAttempts
            << " linkSuccess=" << g_linkSuccess
            << " linkSuccessRate=" << rate
            << std::endl;
}
// PRIVACY_PSEUDONYM_V1_END
'''
txt = txt[:ins] + privacy_block + txt[ins:]

# 5) Insert CLI flags ONCE (after BC cache flags, fallback before cmd.Parse)
flags = r'''
  cmd.AddValue("enablePrivacy", "Enable privacy pseudonyms", g_enablePrivacy);
  cmd.AddValue("pseudoPoolSize", "Pseudonym pool size per vehicle", g_pseudoPoolSize);
  cmd.AddValue("pseudoRotateIntervalS", "Pseudonym rotate interval (s)", g_pseudoRotateIntervalS);
  cmd.AddValue("rotateOnHandover", "Rotate pseudonym on handover", g_rotateOnHandover);
  cmd.AddValue("linkWindowS", "Linkability attacker window (s)", g_linkWindowS);
'''

m2 = re.search(r'cmd\.AddValue\("bcUpdateDelayMs".*?\);\s*', txt)
if m2:
    pos = m2.end()
    txt = txt[:pos] + flags + txt[pos:]
else:
    m3 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
    if not m3:
        raise SystemExit("[ERR] Could not find cmd.Parse(argc, argv); insertion point.")
    pos = m3.start()
    txt = txt[:pos] + flags + txt[pos:]

# 6) Call PrivacyInit() once after vehicles/ledger init (use first occurrence)
if "PrivacyInit();" not in txt:
    txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                      "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  PrivacyInit();", 1)

# 7) Print privacy stats before Destroy (after BC stats if present)
if "PrintPrivacyStats();" not in txt:
    if "PrintBcCacheStats();" in txt:
        txt = txt.replace("PrintBcCacheStats();\n  Simulator::Destroy();",
                          "PrintBcCacheStats();\n  PrintPrivacyStats();\n  Simulator::Destroy();", 1)
    else:
        txt = txt.replace("Simulator::Destroy();",
                          "  PrintPrivacyStats();\n  Simulator::Destroy();", 1)

p.write_text(txt)
print("[OK] Fixed + reinserted privacy pseudonym v1 into:", p)
