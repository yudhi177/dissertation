from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

PH2_BEGIN = "// PHASE2_SECURITY_PACK_V3_BEGIN"
PH2_END   = "// PHASE2_SECURITY_PACK_V3_END"

def ensure_include(txt: str, inc: str) -> str:
    if inc in txt:
        return txt
    # insert after <iostream> if present else at top
    if "#include <iostream>" in txt:
        return txt.replace("#include <iostream>\n", "#include <iostream>\n" + inc + "\n", 1)
    return inc + "\n" + txt

phase2_block = r'''
// PHASE2_SECURITY_PACK_V3_BEGIN
// --- Phase 2: Security completeness (DoS rate-limit + Rekey policy + Anti-downgrade) ---

// Rekey policy
static bool     g_enableRekey = false;
static uint32_t g_rekeyIntervalMs = 2000;
static bool     g_rekeyOnHandover = true;
static uint64_t g_rekeyEvents = 0;

// Anti-downgrade protection
static bool     g_enableAntiDowngrade = true;
static bool     g_enableDowngradeAttack = false; // test knob
static uint64_t g_downgradeDetected = 0;

// Rate limiting (token bucket) for auth probes
static bool     g_enableAuthRateLimit = true;
static double   g_rlRatePerSec = 5.0;   // tokens/sec
static double   g_rlBurst      = 10.0;  // max tokens
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
            " intervalMs=" + std::to_string(g_rekeyIntervalMs));
}

static inline void PrintPhase2Stats()
{
  std::cout << "[PHASE2]"
            << " rekeyEvents=" << g_rekeyEvents
            << " rateLimitDrop=" << g_rateLimitDrop
            << " downgradeDetected=" << g_downgradeDetected
            << " downgradeAttackOn=" << (g_enableDowngradeAttack ? 1 : 0)
            << std::endl;
}
// PHASE2_SECURITY_PACK_V3_END
'''

rekey_tick = r'''
// PHASE2_REKEY_TICK_V3_BEGIN
static void RekeyTick()
{
  if (!g_enableRekey) return;
  RekeyEvent(0, 1);
  Simulator::Schedule(MilliSeconds(g_rekeyIntervalMs), &RekeyTick);
}
// PHASE2_REKEY_TICK_V3_END
'''

for p in targets:
    if not p.exists():
        continue

    txt = p.read_text()

    # includes needed by Phase2 block
    txt = ensure_include(txt, "#include <unordered_map>")
    txt = ensure_include(txt, "#include <algorithm>")

    # remove any older Phase2 / rekey blocks from failed tries
    txt = re.sub(r"// PHASE2_SECURITY_PACK_V1_BEGIN.*?// PHASE2_SECURITY_PACK_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// PHASE2_SECURITY_PACK_V2_BEGIN.*?// PHASE2_SECURITY_PACK_V2_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// PHASE2_SECURITY_PACK_V3_BEGIN.*?// PHASE2_SECURITY_PACK_V3_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// PHASE2_REKEY_TICK_V2_BEGIN.*?// PHASE2_REKEY_TICK_V2_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// PHASE2_REKEY_TICK_V3_BEGIN.*?// PHASE2_REKEY_TICK_V3_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// PHASE2_RATE_LIMIT_V2.*?\n", "", txt, flags=re.M)

    # INSERT Phase2 block AFTER g_evt declaration (so g_evt is in scope)
    m_evt = re.search(r"static\s+std::ofstream\s+g_evt\s*;\s*\n", txt)
    if not m_evt:
        raise SystemExit(f"[ERR] g_evt not found in {p}")
    ins = m_evt.end()
    txt = txt[:ins] + phase2_block + txt[ins:]

    # INSERT RekeyTick after PH2 end
    m_end = re.search(r"// PHASE2_SECURITY_PACK_V3_END\s*\n", txt)
    if not m_end:
        raise SystemExit(f"[ERR] PH2 end not found in {p}")
    ins2 = m_end.end()
    txt = txt[:ins2] + rekey_tick + txt[ins2:]

    # ADD cmd flags (insert after enableAuthReplayAttack if possible)
    if 'cmd.AddValue("enableRekey"' not in txt:
        anchor = re.search(r'cmd\.AddValue\("enableAuthReplayAttack".*?\);\s*\n', txt)
        if not anchor:
            anchor = re.search(r'cmd\.AddValue\("enableAuthProbe".*?\);\s*\n', txt)
        if not anchor:
            raise SystemExit(f"[ERR] cmd.AddValue anchor not found in {p}")
        pos = anchor.end()
        txt = txt[:pos] + (
            '  cmd.AddValue("enableRekey", "Enable rekey policy 0/1", g_enableRekey);\n'
            '  cmd.AddValue("rekeyIntervalMs", "Rekey interval (ms)", g_rekeyIntervalMs);\n'
            '  cmd.AddValue("rekeyOnHandover", "Rekey on handover 0/1", g_rekeyOnHandover);\n'
            '  cmd.AddValue("enableAntiDowngrade", "Anti-downgrade protection 0/1", g_enableAntiDowngrade);\n'
            '  cmd.AddValue("enableDowngradeAttack", "Test: simulate peer forcing FAST downgrade 0/1", g_enableDowngradeAttack);\n'
            '  cmd.AddValue("enableAuthRateLimit", "Auth rate limiting 0/1", g_enableAuthRateLimit);\n'
            '  cmd.AddValue("rlRatePerSec", "Rate limit tokens per second", g_rlRatePerSec);\n'
            '  cmd.AddValue("rlBurst", "Rate limit burst tokens", g_rlBurst);\n'
        ) + txt[pos:]

    # SCHEDULE RekeyTick after cmd.Parse
    sched_marker = "  // PHASE2_REKEY_SCHED_V3\n"
    if sched_marker not in txt:
        m_parse = re.search(r"cmd\.Parse\(argc,\s*argv\);\s*\n", txt)
        if m_parse:
            pos = m_parse.end()
            txt = txt[:pos] + (
                sched_marker
                "  if (g_enableRekey)\n"
                "  {\n"
                "    Simulator::Schedule(MilliSeconds(g_rekeyIntervalMs), &RekeyTick);\n"
                "  }\n"
            ) + txt[pos:]

    # PRINT Phase2 stats after Simulator::Run();
    if "PrintPhase2Stats();" not in txt:
        m_run = re.search(r"^\s*Simulator::Run\(\)\s*;\s*$", txt, flags=re.M)
        if m_run:
            pos = m_run.end()
            txt = txt[:pos] + "\n  PrintPhase2Stats();\n" + txt[pos:]

    # WIRE Rate limit in AuthProbeTick() (sender=0 model)
    m_ap = re.search(r"static\s+void\s+AuthProbeTick\s*\(\s*\)\s*\{", txt)
    if m_ap:
        body = txt[m_ap.end():m_ap.end()+1200]
        if "AuthRateLimitAllow(0)" not in body:
            txt = txt[:m_ap.end()] + "\n  // PHASE2_RATE_LIMIT_V3\n  if (!AuthRateLimitAllow(0)) { return; }\n" + txt[m_ap.end():]

    # WIRE Anti-downgrade safely: insert AFTER first 'fast =' line inside CheckHandover()
    m_ch = re.search(r"static\s+void\s+CheckHandover\s*\([^\)]*\)\s*\{", txt)
    if m_ch:
        seg = txt[m_ch.end():m_ch.end()+12000]
        if "PHASE2_DOWNGRADE_GUARD_V3" not in seg:
            mf = re.search(r"^\s*(?:const\s+)?bool\s+fast\s*=\s*.*?;\s*$", seg, flags=re.M)
            if mf:
                line_end = seg.find("\n", mf.start())
                ins3 = m_ch.end() + line_end + 1
                guard = (
                    "  // PHASE2_DOWNGRADE_GUARD_V3\n"
                    "  if (g_enableAntiDowngrade && g_enableDowngradeAttack)\n"
                    "  {\n"
                    "    // attacker tries to force FAST even when not eligible\n"
                    "    if (!fast)\n"
                    "    {\n"
                    "      g_downgradeDetected++;\n"
                    "      Phase2Evt(std::string(\"DOWNGRADE_DETECTED id=\") + std::to_string(id));\n"
                    "      return;\n"
                    "    }\n"
                    "  }\n"
                )
                txt = txt[:ins3] + guard + txt[ins3:]

    p.write_text(txt)
    print("[OK] Phase2 V3 applied:", p)

