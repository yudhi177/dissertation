from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 1) Ensure g_linkSuccessExp exists
if "g_linkSuccessExp" not in txt:
    txt = re.sub(
        r"(static\s+uint64_t\s+g_linkSuccess\s*=\s*0;\s*\n)",
        r"\1static double   g_linkSuccessExp = 0.0; // expected-success accumulator\n",
        txt,
        count=1
    )

# 2) Replace entire PrivacyRotate() with V3 implementation
pat = re.compile(r"static\s+void\s+PrivacyRotate\s*\([^\)]*\)\s*\{.*?\n\}\s*\n", re.S)
m = pat.search(txt)
if not m:
    raise SystemExit("[ERR] Could not find PrivacyRotate() to rewrite.")

new_rotate = r'''
static void PrivacyRotate(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_pseudoPool.size()) return;
  if (g_pseudoPool[v].empty()) return;

  const double now  = Simulator::Now().GetSeconds();
  const double prev = g_lastRotateS[v];

  const std::string oldP = GetActivePseudo(v);

  g_pseudoIdx[v] = (g_pseudoIdx[v] + 1) % (uint32_t)g_pseudoPool[v].size();
  g_lastRotateS[v] = now;

  const std::string newP = GetActivePseudo(v);
  (void)reason; (void)oldP; (void)newP;

  g_pseudoRotations++;

  // ---- Linkability V3 (expected success probability) ----
  // Attempt only if rotations are within time window.
  if (prev > -1e8 && (now - prev) <= g_linkTimeWindowSec)
  {
    g_linkAttempts++;

    const uint32_t k = CountVehNeighborsWithinRadius(v, g_mixRadiusM);

    // Expected attacker success if there are (k+1) plausible candidates
    g_linkSuccessExp += 1.0 / double(k + 1);

    // Keep hard-success metric too (only if no neighbors)
    if (k == 0) g_linkSuccess++;
  }
}
'''
txt = txt[:m.start()] + new_rotate + txt[m.end():]

p.write_text(txt)
print("[OK] Rewrote PrivacyRotate() to V3 expected-success in:", p)
