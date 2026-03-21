from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

BLOCK_BEGIN = "// PHASE2_SECURITY_PACK_V1_BEGIN"
BLOCK_END   = "// PHASE2_SECURITY_PACK_V1_END"

block = r'''
// PHASE2_SECURITY_PACK_V1_BEGIN
// --- Phase 2: Security completeness (rekey + anti-downgrade + DoS rate limit) ---

// Rekey policy
static bool     g_enableRekey = false;
static uint32_t g_rekeyIntervalMs = 2000;
static bool     g_rekeyOnHandover = true;
static uint64_t g_rekeyEvents = 0;

// Anti-downgrade protection
static bool     g_enableAntiDowngrade = true;
static uint64_t g_downgradeDetected = 0;

// Rate limiting (token bucket) per sender for auth probes
static bool     g_enableAuthRateLimit = true;
static double   g_rlRatePerSec = 5.0;   // tokens per second
static double   g_rlBurst = 10.0;       // burst tokens
static uint64_t g_rateLimitDrop = 0;

struct RateBucket
{
  double tokens = 0.0;
  double lastS  = 0.0;
};

// senderId -> bucket
static std::unordered_map<uint32_t, RateBucket> g_authRl;

// helper: update + consume token
static inline bool AuthRateLimitAllow(uint32_t senderId)
{
  if (!g_enableAuthRateLimit) return true;
  const double now = Simulator::Now().GetSeconds();

  auto &b = g_authRl[senderId];
  if (b.lastS == 0.0) { b.lastS = now; b.tokens = g_rlBurst; }

  const double dt = now - b.lastS;
  b.lastS = now;
  b.tokens = std::min(g_rlBurst, b.tokens + dt * g_rlRatePerSec);

  if (b.tokens >= 1.0)
  {
    b.tokens -= 1.0;
    return true;
  }
  g_rateLimitDrop++;
  // events
  if (g_evt.is_open()) { g_evt << now << ",RATE_LIMIT_DROP sender=" << senderId << "\n"; }
  return false;
}

static inline void RekeyEvent(uint32_t a, uint32_t b)
{
  if (!g_enableRekey) return;
  g_rekeyEvents++;
  if (g_evt.is_open())
  {
    g_evt << Simulator::Now().GetSeconds() << ",REKEY_EVENT a=" << a << " b=" << b
          << " intervalMs=" << g_rekeyIntervalMs
          << " onHandover=" << (g_rekeyOnHandover?1:0) << "\n";
  }
}
// PHASE2_SECURITY_PACK_V1_END
'''

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # Ensure includes needed
    if "#include <unordered_map>" not in txt:
        txt = txt.replace("#include <map>\n", "#include <map>\n#include <unordered_map>\n", 1) if "#include <map>" in txt else txt.replace("#include <iostream>\n", "#include <iostream>\n#include <unordered_map>\n", 1)

    # Remove old block
    txt = re.sub(rf"{re.escape(BLOCK_BEGIN)}.*?{re.escape(BLOCK_END)}\s*", "", txt, flags=re.S)

    # Insert after using namespace ns3;
    m = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] using namespace ns3 not found in {p}")
    ins = m.end()

    txt = txt[:ins] + block + txt[ins:]

    # Add cmd flags (after trustMaxAgeMs or near cmd.Parse region)
    if 'cmd.AddValue("enableRekey"' not in txt:
        # Insert near other cmd.AddValue lines (after enableAuthReplayAttack if present else after baselineName)
        anchor = re.search(r'cmd\.AddValue\("enableAuthReplayAttack".*?\);\s*\n', txt)
        if not anchor:
            anchor = re.search(r'cmd\.AddValue\("baselineName".*?\);\s*\n', txt)
        if not anchor:
            raise SystemExit(f"[ERR] cmd.AddValue anchors not found in {p}")
        pos = anchor.end()
        txt = txt[:pos] + (
            '  cmd.AddValue("enableRekey", "Enable rekey policy 0/1", g_enableRekey);\n'
            '  cmd.AddValue("rekeyIntervalMs", "Rekey interval (ms)", g_rekeyIntervalMs);\n'
            '  cmd.AddValue("rekeyOnHandover", "Rekey on handover 0/1", g_rekeyOnHandover);\n'
            '  cmd.AddValue("enableAntiDowngrade", "Anti-downgrade protection 0/1", g_enableAntiDowngrade);\n'
            '  cmd.AddValue("enableAuthRateLimit", "Auth handshake rate limiting 0/1", g_enableAuthRateLimit);\n'
            '  cmd.AddValue("rlRatePerSec", "Rate limit tokens per second", g_rlRatePerSec);\n'
            '  cmd.AddValue("rlBurst", "Rate limit burst tokens", g_rlBurst);\n'
        ) + txt[pos:]

    p.write_text(txt)
    print("[OK] Phase2 security pack inserted:", p)
