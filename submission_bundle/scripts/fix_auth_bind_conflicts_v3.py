from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

AUTH_BLOCK = r'''
// AUTH_BIND_V3_BEGIN
/* =========================================================
   AUTH Session Binding (v3): compile-safe binding + MITM + AuthReplay
   - Reuses existing global events stream: g_evt (std::ofstream)
   - No duplicate NowS(); no g_seed dependency
   - Signature-style (toy Schnorr) bind: (sender|ephPub|nonce|ts)
   - MITM: ephPub tamper -> AUTH_FAIL reason=BAD_SIG
   - Replay: same tuple -> AUTH_FAIL reason=REPLAY_AUTH
========================================================= */

static bool     g_enableAuthBind = true;
static bool     g_enableMitmAttack = false;

static bool     g_enableAuthProbe = false;
static uint32_t g_authProbeIntervalMs = 500;

static bool     g_enableAuthReplayAttack = false;
static uint32_t g_authReplayEveryN = 5;

static uint64_t g_authOk = 0;
static uint64_t g_authFail = 0;
static uint64_t g_authFailMitm = 0;
static uint64_t g_authFailReplay = 0;

// ---- Tiny Schnorr params (toy group) ----
static const uint64_t AUTH_P = 1223;
static const uint64_t AUTH_Q = 611;
static const uint64_t AUTH_G = 4;

// stable 32-bit hash (FNV-1a)
static uint32_t H32(const std::string& s)
{
  uint32_t h = 2166136261u;
  for (unsigned char c : s) { h ^= (uint32_t)c; h *= 16777619u; }
  return h;
}
static uint64_t Hq(const std::string& s) { return (uint64_t)(H32(s) % (uint32_t)AUTH_Q); }

static uint64_t ModPow(uint64_t a, uint64_t e, uint64_t m)
{
  uint64_t r = 1 % m; a %= m;
  while (e) { if (e & 1) r = (r * a) % m; a = (a * a) % m; e >>= 1; }
  return r;
}
static uint64_t ModInv(uint64_t a, uint64_t m) { return ModPow(a, m - 2, m); }

// keys per vehicle (deterministic, no g_seed dependency)
static std::vector<uint64_t> g_authPrivX; // x in [1..q-1]
static std::vector<uint64_t> g_authPubY;  // y = g^x mod p

static void AuthInitKeys(uint32_t nVehicles)
{
  g_authPrivX.assign(nVehicles, 0);
  g_authPubY.assign(nVehicles, 0);
  for (uint32_t v = 0; v < nVehicles; ++v)
  {
    uint64_t x = 1 + (H32("AUTHKEY:" + std::to_string(v)) % (uint32_t)(AUTH_Q - 1));
    g_authPrivX[v] = x;
    g_authPubY[v]  = ModPow(AUTH_G, x, AUTH_P);
  }
}

struct AuthSig { uint64_t e=0; uint64_t s=0; };

static inline std::string AuthMsg(uint32_t sender,
                                  const std::string& ephPub,
                                  uint64_t nonce,
                                  uint64_t tsMs)
{
  return std::to_string(sender) + "|" + ephPub + "|" + std::to_string(nonce) + "|" + std::to_string(tsMs);
}

static AuthSig AuthSign(uint32_t sender, const std::string& msg, uint64_t k)
{
  AuthSig sig;
  uint64_t r = ModPow(AUTH_G, k % AUTH_Q, AUTH_P);
  sig.e = Hq(msg + "|" + std::to_string(r));
  sig.s = (k + (sig.e * g_authPrivX[sender]) % AUTH_Q) % AUTH_Q;
  return sig;
}

static bool AuthVerify(uint32_t sender, const std::string& msg, const AuthSig& sig)
{
  if (sender >= g_authPubY.size()) return false;
  uint64_t gs = ModPow(AUTH_G, sig.s % AUTH_Q, AUTH_P);
  uint64_t ye = ModPow(g_authPubY[sender], sig.e % AUTH_Q, AUTH_P);
  uint64_t r  = (gs * ModInv(ye, AUTH_P)) % AUTH_P;
  uint64_t e2 = Hq(msg + "|" + std::to_string(r));
  return (e2 == (sig.e % AUTH_Q));
}

// Replay cache
static std::unordered_set<std::string> g_authReplayCache;
static inline std::string ReplayKey(uint32_t sender, uint64_t nonce, uint64_t tsMs)
{
  return std::to_string(sender) + "|" + std::to_string(nonce) + "|" + std::to_string(tsMs);
}

// Use existing global g_evt (ofstream) safely
static inline void AuthEvt(const std::string& s)
{
  if (g_evt.good())
    g_evt << Simulator::Now().GetSeconds() << "," << s << "\n";
}

static void DoAuthAttempt(uint32_t sender, uint32_t receiver, uint64_t nonce, uint64_t tsMs, uint64_t k)
{
  std::string ephPub = "E" + std::to_string(sender) + "_" + std::to_string(tsMs);
  std::string msg    = AuthMsg(sender, ephPub, nonce, tsMs);

  AuthEvt("AUTH_START sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver));

  // receiver side (MITM tamper)
  std::string ephRx = ephPub;
  if (g_enableMitmAttack) ephRx = ephPub + "_TAMPER";

  // replay check
  const std::string rk = ReplayKey(sender, nonce, tsMs);
  if (g_authReplayCache.count(rk))
  {
    g_authFail++; g_authFailReplay++;
    AuthEvt("AUTH_FAIL sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver) + " reason=REPLAY_AUTH");
    return;
  }

  AuthSig sig = AuthSign(sender, msg, k);

  std::string msgRx = AuthMsg(sender, ephRx, nonce, tsMs);
  const bool ok = AuthVerify(sender, msgRx, sig);

  if (!ok)
  {
    g_authFail++;
    if (g_enableMitmAttack) g_authFailMitm++;
    AuthEvt("AUTH_FAIL sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver) + " reason=BAD_SIG");
    return;
  }

  g_authReplayCache.insert(rk);
  g_authOk++;
  AuthEvt("AUTH_OK sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver));
}

static void AuthProbeTick()
{
  if (!g_enableAuthProbe) return;
  if (g_nVehicles < 2) return;

  static uint64_t ctr = 0;
  ctr++;

  uint64_t tsMs  = (uint64_t)Simulator::Now().GetMilliSeconds();
  uint64_t nonce = (uint64_t)H32("NONCE:" + std::to_string(ctr));
  uint64_t k     = 1 + ((uint64_t)H32("K:" + std::to_string(ctr)) % (AUTH_Q - 1));

  // replay mode: reuse tuple every N
  static uint64_t lastNonce = 0, lastTs = 0;
  if (g_enableAuthReplayAttack && (ctr % g_authReplayEveryN == 0))
  {
    nonce = lastNonce; tsMs = lastTs;
  }
  else
  {
    lastNonce = nonce; lastTs = tsMs;
  }

  DoAuthAttempt(0, 1, nonce, tsMs, k);
  Simulator::Schedule(MilliSeconds(g_authProbeIntervalMs), &AuthProbeTick);
}

static void StartAuthProbes()
{
  if (!g_enableAuthProbe) return;
  Simulator::Schedule(MilliSeconds(1), &AuthProbeTick);
}

static inline void PrintAuthStats()
{
  std::cout << "[AUTH] ok=" << g_authOk
            << " fail=" << g_authFail
            << " mitmFail=" << g_authFailMitm
            << " replayFail=" << g_authFailReplay
            << std::endl;
}
// AUTH_BIND_V3_END
'''

def patch(p: Path):
    txt = p.read_text()

    # remove older blocks
    txt = re.sub(r"// AUTH_BIND_V1_BEGIN.*?// AUTH_BIND_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// AUTH_BIND_V2_BEGIN.*?// AUTH_BIND_V2_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// AUTH_BIND_V3_BEGIN.*?// AUTH_BIND_V3_END\s*", "", txt, flags=re.S)

    # ensure unordered_set include
    if "#include <unordered_set>" not in txt:
        if "#include <unordered_map>" in txt:
            txt = txt.replace("#include <unordered_map>\n", "#include <unordered_map>\n#include <unordered_set>\n", 1)
        else:
            txt = "#include <unordered_set>\n" + txt

    # insert before GetTrustForHandover
    m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
    if not m:
        raise SystemExit(f"[ERR] GetTrustForHandover not found in {p}")
    ins = m.start()
    txt = txt[:ins] + "\n" + AUTH_BLOCK + "\n" + txt[ins:]

    # remove duplicate cmd flags if present
    for flag in ["enableAuthBind","enableMitmAttack","enableAuthProbe","authProbeIntervalMs","enableAuthReplayAttack","authReplayEveryN"]:
        txt = re.sub(rf'^\s*cmd\.AddValue\("{flag}".*?\);\s*\n', '', txt, flags=re.M)

    # insert cmd flags before cmd.Parse
    m2 = re.search(r"cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*\n", txt)
    if not m2:
        raise SystemExit(f"[ERR] cmd.Parse not found in {p}")
    pos = m2.start()
    flags = (
        '  cmd.AddValue("enableAuthBind", "Bind ephemeral key to auth signature", g_enableAuthBind);\n'
        '  cmd.AddValue("enableMitmAttack", "MITM test: tamper ephPub at receiver (must fail)", g_enableMitmAttack);\n'
        '  cmd.AddValue("enableAuthProbe", "Generate periodic auth handshakes (to measure AUTH)", g_enableAuthProbe);\n'
        '  cmd.AddValue("authProbeIntervalMs", "Auth probe interval (ms)", g_authProbeIntervalMs);\n'
        '  cmd.AddValue("enableAuthReplayAttack", "Replay auth tuple periodically (must fail)", g_enableAuthReplayAttack);\n'
        '  cmd.AddValue("authReplayEveryN", "Replay every N probes", g_authReplayEveryN);\n'
    )
    txt = txt[:pos] + flags + txt[pos:]

    # ensure AuthInitKeys and StartAuthProbes
    if "AuthInitKeys(" not in txt:
        txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                          "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  AuthInitKeys(g_nVehicles);", 1)
    if "StartAuthProbes();" not in txt:
        if "StartBcProbes();" in txt:
            txt = txt.replace("StartBcProbes();", "StartBcProbes();\n  StartAuthProbes();", 1)
        else:
            txt = txt.replace("PrivacyInit();", "PrivacyInit();\n  StartAuthProbes();", 1)

    # print stats once
    txt = re.sub(r'^\s*PrintAuthStats\(\);\s*\n', '', txt, flags=re.M)
    txt = txt.replace("Simulator::Destroy();", "  PrintAuthStats();\n  Simulator::Destroy();", 1)

    p.write_text(txt)
    print("[OK] fixed auth conflicts v3 in:", p)

for p in targets:
    if p.exists():
        patch(p)
