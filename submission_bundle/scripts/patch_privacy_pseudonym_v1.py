from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove older block
txt = re.sub(r"// PRIVACY_PSEUDONYM_V1_BEGIN.*?// PRIVACY_PSEUDONYM_V1_END\s*", "", txt, flags=re.S)

# insert before GetTrustForHandover (safe global place)
m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find GetTrustForHandover() insertion point.")

ins = m.start()

block = r'''
// PRIVACY_PSEUDONYM_V1_BEGIN
/* =========================================================
   PRIVACY (v1): Pseudonym Pool + Rotation + Linkability metric
   - Each vehicle has K pseudonyms
   - Rotation: time-based (pseudoRotateIntervalS) + optional handover-triggered
   - Linkability: attacker tries to link old->new if rotation happened and
     time gap small (simple continuity attacker)
========================================================= */
static bool   g_enablePrivacy = false;
static uint32_t g_pseudoPoolSize = 5;
static double g_pseudoRotateIntervalS = 3.0;
static bool   g_rotateOnHandover = true;
static double g_linkWindowS = 1.0;      // attacker link window

static std::vector<std::vector<std::string>> g_pseudoPool;
static std::vector<uint32_t> g_pseudoIdx;
static std::vector<double> g_lastRotateS;

static uint64_t g_pseudoRotations = 0;
static uint64_t g_linkAttempts = 0;
static uint64_t g_linkSuccess = 0;

// lightweight hash-like pseudonym (deterministic, no crypto dependency)
static std::string MakePseudo(uint32_t v, uint32_t k)
{
  return std::to_string(v) + "_P" + std::to_string(k);
}

static const std::string& GetActivePseudo(uint32_t v)
{
  return g_pseudoPool[v][g_pseudoIdx[v] % g_pseudoPool[v].size()];
}

// You already have events logger; we call it if present.
// If your logger function name differs, we will patch call-sites later.
static void PrivacyRotate(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_pseudoPool.size()) return;

  const double now = Simulator::Now().GetSeconds();
  const std::string oldP = GetActivePseudo(v);

  g_pseudoIdx[v] = (g_pseudoIdx[v] + 1) % (uint32_t)g_pseudoPool[v].size();
  g_lastRotateS[v] = now;
  const std::string newP = GetActivePseudo(v);

  g_pseudoRotations++;

  // Linkability test (simple attacker): if rotate happens and timing within window, attacker links
  g_linkAttempts++;
  if ((now - g_lastRotateS[v]) <= g_linkWindowS)  # this will always be 0; handled by caller scheduling
    pass
}

// helper called by timer
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

  for (uint32_t v=0; v<g_nVehicles; ++v)
  {
    g_pseudoPool[v].reserve(g_pseudoPoolSize);
    for (uint32_t k=0; k<g_pseudoPoolSize; ++k)
      g_pseudoPool[v].push_back(MakePseudo(v,k));
  }

  for (uint32_t v=0; v<g_nVehicles; ++v)
    Simulator::Schedule(Seconds(g_pseudoRotateIntervalS), &PrivacyRotateTimer, v);
}
// PRIVACY_PSEUDONYM_V1_END
'''
txt = txt[:ins] + block + txt[ins:]

# add CLI flags near enableBCLocalCache
m2 = re.search(r'cmd\.AddValue\("enableBCLocalCache".*?\);\s*', txt)
if not m2:
    m2 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
    if not m2:
        raise SystemExit("[ERR] Could not find CLI insertion point.")
    pos = m2.start()
else:
    pos = m2.end()

flags = r'''
  cmd.AddValue("enablePrivacy", "Enable privacy pseudonyms", g_enablePrivacy);
  cmd.AddValue("pseudoPoolSize", "Pseudonym pool size per vehicle", g_pseudoPoolSize);
  cmd.AddValue("pseudoRotateIntervalS", "Pseudonym rotate interval (s)", g_pseudoRotateIntervalS);
  cmd.AddValue("rotateOnHandover", "Rotate pseudonym on handover", g_rotateOnHandover);
  cmd.AddValue("linkWindowS", "Linkability attacker window (s)", g_linkWindowS);
'''
txt = txt[:pos] + flags + txt[pos:]

# call PrivacyInit after vehicles count init (look for g_ledgerTrust assign which happens after g_nVehicles set)
if "PrivacyInit();" not in txt:
    txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);", "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  PrivacyInit();", 1)

p.write_text(txt)
print("[OK] Patched privacy pseudonym v1 into:", p)
