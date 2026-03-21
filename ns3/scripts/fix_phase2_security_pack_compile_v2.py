from pathlib import Path
import re

targets = [
    Path.home()/ "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home()/ "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

# Remove old Phase2 blocks (v1/v2)
rm_phase2 = [
    r"// PHASE2_SECURITY_PACK_V1_BEGIN.*?// PHASE2_SECURITY_PACK_V1_END\s*",
    r"// PHASE2_SECURITY_PACK_V2_BEGIN.*?// PHASE2_SECURITY_PACK_V2_END\s*",
]

# Remove any old RekeyTick() inserted earlier
rm_rekeytick = r"\nstatic\s+void\s+RekeyTick\s*\(\s*\)\s*\{.*?\n\}\s*\n"

# Remove any old rekey scheduling hook inserted earlier
rm_rekeyhook = r"\n\s*// PHASE2: start rekey policy timer.*?\n\s*\}\s*\n"

# Remove broken anti-downgrade injection (old)
rm_downgrade = r"\n\s*// PHASE2: anti-downgrade protection.*?\n\s*\}\s*\n"

# Remove old Phase2 stats call if present
rm_stats_call = r"^\s*PrintPhase2Stats\(\);\s*\n"

block = r'''
// PHASE2_SECURITY_PACK_V2_BEGIN
// --- Phase 2: Security completeness (rekey + anti-downgrade + DoS rate limit) ---

// Rekey policy
static bool     g_enableRekey = false;
static uint32_t g_rekeyIntervalMs = 2000;
static bool     g_rekeyOnHandover = true;
static uint64_t g_rekeyEvents = 0;

// Anti-downgrade protection
static bool     g_enableAntiDowngrade = true;
static bool     g_enableDowngradeAttack = false; // test knob
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

static std::unordered_map<uint32_t, RateBucket> g_authRl;

static inline void Phase2Evt(const std::string& s)
{
  if (g_evt.is_open())
  {
    g_evt << Simulator::Now().GetSeconds() << "," << s << "\n";
  }
}

static inline bool AuthRateLimitAllow(uint32_t senderId)
{
  if (!g_enableAuthRateLimit) return true;

  const double now = Simulator::Now().GetSeconds();
  auto &b = g_authRl[senderId];

  if (b.lastS == 0.0)
  {
    b.lastS = now;
    b.tokens = g_rlBurst;
  }

  const double dt = now - b.lastS;
  b.lastS = now;
  b.tokens = std::min(g_rlBurst, b.tokens + dt * g_rlRatePerSec);

  if (b.tokens >= 1.0)
  {
    b.tokens -= 1.0;
    return true;
  }

  g_rateLimitDrop++;
  Phase2Evt("RATE_LIMIT_DROP sender=" + std::to_string(senderId));
  return false;
}

static inline void RekeyEvent(uint32_t a, uint32_t b)
{
  if (!g_enableRekey) return;
  g_rekeyEvents++;
  Phase2Evt("REKEY_EVENT a=" + std::to_string(a) + " b=" + std::to_string(b) +
            " intervalMs=" + std::to_string(g_rekeyIntervalMs) +
            " onHandover=" + std::to_string(g_rekeyOnHandover?1:0));
}

static inline void PrintPhase2Stats()
{
  std::cout << "[PHASE2]"
            << " rekeyEvents=" << g_rekeyEvents
            << " rateLimitDrop=" << g_rateLimitDrop
            << " downgradeDetected=" << g_downgradeDetected
            << std::endl;
}
// PHASE2_SECURITY_PACK_V2_END
'''

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    # Ensure required includes
    if "#include <unordered_map>" not in txt:
        if "#include <iostream>" in txt:
            txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <unordered_map>\n", 1)
        else:
            txt = "#include <unordered_map>\n" + txt

    if "#include <algorithm>" not in txt:
        if "#include <iostream>" in txt:
            txt = txt.replace("#include <iostream>\n", "#include <iostream>\n#include <algorithm>\n", 1)
        else:
            txt = "#include <algorithm>\n" + txt

    # Cleanup old inserts
    for pat in rm_phase2:
        txt = re.sub(pat, "", txt, flags=re.S)
    txt = re.sub(rm_rekeytick, "\n", txt, flags=re.S)
    txt = re.sub(rm_rekeyhook, "\n", txt, flags=re.S)
    txt = re.sub(rm_downgrade, "\n", txt, flags=re.S)
    txt = re.sub(rm_stats_call, "", txt, flags=re.M)

    # Insert Phase2 block AFTER g_evt declaration so g_evt is in scope
    m = re.search(r"static\s+std::ofstream\s+g_evt\s*;\s*\n", txt)
    if not m:
        raise SystemExit(f"[ERR] cannot find 'static std::ofstream g_evt;' in {p}")
    ins = m.end()
    txt = txt[:ins] + block + txt[ins:]

    # Ensure cmd flags exist (insert near enableAuthReplayAttack or baselineName)
    if 'cmd.AddValue("enableRekey"' not in txt:
        anchor = re.search(r'cmd\.AddValue\("enableAuthReplayAttack".*?\);\s*\n', txt)
        if not anchor:
            anchor = re.search(r'cmd\.AddValue\("baselineName".*?\);\s*\n', txt)
        if not anchor:
            raise SystemExit(f"[ERR] cmd.AddValue anchor not found in {p}")
        pos = anchor.end()
        txt = txt[:pos] + (
            '  cmd.AddValue("enableRekey", "Enable rekey policy 0/1", g_enableRekey);\n'
            '  cmd.AddValue("rekeyIntervalMs", "Rekey interval (ms)", g_rekeyIntervalMs);\n'
            '  cmd.AddValue("rekeyOnHandover", "Rekey on handover 0/1", g_rekeyOnHandover);\n'
            '  cmd.AddValue("enableAntiDowngrade", "Anti-downgrade protection 0/1", g_enableAntiDowngrade);\n'
            '  cmd.AddValue("enableDowngradeAttack", "Test: force FAST request downgrade attempt 0/1", g_enableDowngradeAttack);\n'
            '  cmd.AddValue("enableAuthRateLimit", "Auth handshake rate limiting 0/1", g_enableAuthRateLimit);\n'
            '  cmd.AddValue("rlRatePerSec", "Rate limit tokens per second", g_rlRatePerSec);\n'
            '  cmd.AddValue("rlBurst", "Rate limit burst tokens", g_rlBurst);\n'
        ) + txt[pos:]

    # Ensure PrintPhase2Stats() called after Simulator::Run();
    if "PrintPhase2Stats();" not in txt:
        runm = re.search(r"^\s*Simulator::Run\(\)\s*;\s*$", txt, flags=re.M)
        if runm:
            pos = runm.end()
            txt = txt[:pos] + "\n  PrintPhase2Stats();\n" + txt[pos:]

    p.write_text(txt)
    print("[OK] fixed Phase2 scope + cleanup:", p)
