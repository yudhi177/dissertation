from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove older AUTH block if exists
txt = re.sub(r"// AUTH_BIND_V1_BEGIN.*?// AUTH_BIND_V1_END\s*", "", txt, flags=re.S)

# insert before GetTrustForHandover (stable insertion point)
m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find GetTrustForHandover() insertion point for AUTH block.")

ins = m.start()

block = r'''
// AUTH_BIND_V1_BEGIN
/* =========================================================
   Authenticated Session Binding (v1) + MITM test + AuthProbe
   - Simulation-friendly binding: tag = H(senderId|ephPub|nonce|tsMs)
   - MITM mode tampers ephPub at receiver => verification fails
   - AuthProbe generates periodic handshake attempts so metrics become non-zero
========================================================= */
static bool g_enableAuthBind = true;
static bool g_enableMitmAttack = false;

static bool     g_enableAuthProbe = false;
static uint32_t g_authProbeIntervalMs = 500;

static uint64_t g_authOk = 0;
static uint64_t g_authFail = 0;
static uint64_t g_authFailMitm = 0;

// SimpleSig: stable 32-bit hash (FNV-1a)
static uint32_t SimpleSig(const std::string& s)
{
  uint32_t h = 2166136261u;
  for (unsigned char c : s)
  {
    h ^= (uint32_t)c;
    h *= 16777619u;
  }
  return h;
}

static uint32_t MakeAuthTag(uint32_t senderId,
                            const std::string& ephPub,
                            uint64_t nonce,
                            uint64_t tsMs)
{
  return SimpleSig(std::to_string(senderId) + "|" + ephPub + "|" +
                   std::to_string(nonce) + "|" + std::to_string(tsMs));
}

static bool VerifyAuthTag(uint32_t senderId,
                          std::string ephPub,
                          uint64_t nonce,
                          uint64_t tsMs,
                          uint32_t recvTag,
                          bool mitmTamper)
{
  if (mitmTamper)
    ephPub += "|MITM";
  return recvTag == MakeAuthTag(senderId, ephPub, nonce, tsMs);
}

static void AuthProbeOnce(uint32_t v)
{
  if (!g_enableAuthProbe) return;

  const uint64_t tsMs = (uint64_t)Simulator::Now().GetMilliSeconds();
  const uint64_t nonce = (uint64_t)(tsMs ^ (v * 2654435761u)); // deterministic-ish
  const std::string ephPub = "E" + std::to_string(v) + "_" + std::to_string(tsMs);

  const uint32_t tag = MakeAuthTag(v, ephPub, nonce, tsMs);

  bool ok = true;
  if (g_enableAuthBind)
    ok = VerifyAuthTag(v, ephPub, nonce, tsMs, tag, g_enableMitmAttack);

  if (ok) g_authOk++;
  else
  {
    g_authFail++;
    if (g_enableMitmAttack) g_authFailMitm++;
  }

  Simulator::Schedule(MilliSeconds(g_authProbeIntervalMs), &AuthProbeOnce, v);
}

static void StartAuthProbes()
{
  if (!g_enableAuthProbe) return;
  for (uint32_t v = 0; v < g_nVehicles; ++v)
  {
    Simulator::Schedule(MilliSeconds(100 + (v % 10)), &AuthProbeOnce, v);
  }
}

static void PrintAuthStats()
{
  std::cout << "[AUTH] ok=" << g_authOk
            << " fail=" << g_authFail
            << " mitmFail=" << g_authFailMitm
            << std::endl;
}
// AUTH_BIND_V1_END
'''
txt = txt[:ins] + block + txt[ins:]

# CLI flags insert near other flags (after bcProbe flags if present)
flags = r'''
  cmd.AddValue("enableAuthBind", "Bind session ephemeral key to auth tag", g_enableAuthBind);
  cmd.AddValue("enableMitmAttack", "MITM test: tamper pubkey at receiver (should fail)", g_enableMitmAttack);
  cmd.AddValue("enableAuthProbe", "Generate periodic auth handshakes (to measure AUTH stats)", g_enableAuthProbe);
  cmd.AddValue("authProbeIntervalMs", "Auth probe interval per vehicle (ms)", g_authProbeIntervalMs);
'''

if 'cmd.AddValue("enableAuthBind"' not in txt:
    m2 = re.search(r'cmd\.AddValue\("enableBcProbe".*?\);\s*\n', txt)
    if m2:
        pos = m2.end()
        txt = txt[:pos] + flags + txt[pos:]
    else:
        m3 = re.search(r'cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*', txt)
        if not m3:
            raise SystemExit("[ERR] Could not find cmd.Parse(argc, argv);")
        pos = m3.start()
        txt = txt[:pos] + flags + txt[pos:]

# call StartAuthProbes() after StartBcProbes() if present else after PrivacyInit() else after ledger init
if "StartAuthProbes();" not in txt:
    if "  StartBcProbes();" in txt:
        txt = txt.replace("  StartBcProbes();", "  StartBcProbes();\n  StartAuthProbes();", 1)
    elif "  PrivacyInit();" in txt:
        txt = txt.replace("  PrivacyInit();", "  PrivacyInit();\n  StartAuthProbes();", 1)
    else:
        txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                          "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  StartAuthProbes();", 1)

# print stats before Destroy (ensure only once)
txt = re.sub(r"\s*PrintAuthStats\(\);\s*\n", "", txt)
txt = txt.replace("Simulator::Destroy();", "  PrintAuthStats();\n  Simulator::Destroy();", 1)

p.write_text(txt)
print("[OK] Patched AUTH probe + MITM into:", p)
