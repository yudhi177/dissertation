from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# --- sanity: must have privacy block
if "PRIVACY_PSEUDONYM_V1_BEGIN" not in txt:
    raise SystemExit("[ERR] Privacy block not found. Make sure privacy v1 is already patched.")

# 0) add mixRadius global (only if missing) inside privacy block
if "g_mixRadiusM" not in txt:
    txt = re.sub(
        r"(static\s+std::vector<double>\s+g_lastRotateS;\s*\n)",
        r"\1\nstatic double g_mixRadiusM = 50.0;  // mix-zone radius (meters)\n",
        txt,
        count=1
    )

# 1) insert neighbor counter helper inside privacy block (only if missing)
if "CountVehNeighborsWithinRadius" not in txt:
    helper = r'''
static uint32_t CountVehNeighborsWithinRadius(uint32_t v, double radiusM)
{
  // Assumption: vehicle nodes are node IDs 0..g_nVehicles-1 (true in your setup)
  Ptr<Node> nv = NodeList::GetNode(v);
  if (!nv) return 0;
  Ptr<MobilityModel> mv = nv->GetObject<MobilityModel>();
  if (!mv) return 0;

  Vector pv = mv->GetPosition();
  const double r2 = radiusM * radiusM;
  uint32_t cnt = 0;

  for (uint32_t u = 0; u < g_nVehicles; ++u)
  {
    if (u == v) continue;
    Ptr<Node> nu = NodeList::GetNode(u);
    if (!nu) continue;
    Ptr<MobilityModel> mu = nu->GetObject<MobilityModel>();
    if (!mu) continue;
    Vector pu = mu->GetPosition();
    const double dx = pv.x - pu.x;
    const double dy = pv.y - pu.y;
    if ((dx*dx + dy*dy) <= r2) cnt++;
  }
  return cnt;
}
'''
    # insert after GetActivePseudo() closing brace
    txt = re.sub(
        r"(static\s+const\s+std::string&\s+GetActivePseudo\s*\([^\)]*\)\s*\{.*?\n\}\s*\n)",
        r"\1" + helper + "\n",
        txt,
        flags=re.S,
        count=1
    )

# 2) replace PrivacyRotate() with V2 (mix-zone + time window)
rot_pat = re.compile(r"static\s+void\s+PrivacyRotate\s*\([^\)]*\)\s*\{.*?\n\}\s*\n", re.S)
m = rot_pat.search(txt)
if not m:
    raise SystemExit("[ERR] Could not find PrivacyRotate() to upgrade.")

new_rotate = r'''
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

  // ---- Linkability V2 (Mix-zone attacker) ----
  // Attacker tries to link old->new if it happens within time window.
  // Success if there are NO other nearby vehicles within mix radius at rotation time.
  if (prev > -1e8)
  {
    g_linkAttempts++;
    if ((now - prev) <= g_linkTimeWindowSec)
    {
      uint32_t k = CountVehNeighborsWithinRadius(v, g_mixRadiusM);
      if (k == 0) g_linkSuccess++;
    }
  }
}
'''
txt = txt[:m.start()] + new_rotate + txt[m.end():]

# 3) add CLI flag for mixRadiusM (only if missing)
if 'cmd.AddValue("mixRadiusM"' not in txt:
    txt = re.sub(
        r'(cmd\.AddValue\("linkWindowS"[^\n]*\n)',
        r'\1  cmd.AddValue("mixRadiusM", "Mix-zone radius in meters", g_mixRadiusM);\n',
        txt,
        count=1
    )

# 4) enrich PrintPrivacyStats (optional)
txt = re.sub(
    r'(\[PRIV\].*?linkSuccessRate= << rate\s*\n)',
    r'\1',
    txt
)

# 5) Try to append privacy metrics into main CSV header+row (best-effort, safe)
# Header: add fields after avgTrust if present
if "pseudoRotations" not in txt:
    txt = txt.replace("avgTrust\n", "avgTrust,pseudoRotations,linkAttempts,linkSuccess,linkSuccessRate\n")
    txt = txt.replace("avgTrust\\n", "avgTrust,pseudoRotations,linkAttempts,linkSuccess,linkSuccessRate\\n")

# Row: append values after avgTrust if pattern exists
if "linkSuccessRate" not in txt:
    txt = txt.replace(
        "<< avgTrust << \"\\n\"",
        "<< avgTrust"
        " << \",\" << g_pseudoRotations"
        " << \",\" << g_linkAttempts"
        " << \",\" << g_linkSuccess"
        " << \",\" << (g_linkAttempts ? (double)g_linkSuccess / (double)g_linkAttempts : 0.0)"
        " << \"\\n\""
    )

p.write_text(txt)
print("[OK] Patched linkability V2 mix-zone into:", p)
