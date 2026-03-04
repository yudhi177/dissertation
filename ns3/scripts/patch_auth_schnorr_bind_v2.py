from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

AUTH_BLOCK = r'''
// AUTH_BIND_V2_BEGIN
/* =========================================================
   AUTH Session Binding (v2): Signature-style bind + MITM + AuthReplay
   - Bind (pseudo + ephPub + nonce + tsMs) to a Schnorr-like toy signature.
   - No external crypto libs; deterministic + verifiable (public key).
   - MITM: tamper ephPub at receiver -> BAD_SIG
   - AuthReplay: resend same tuple -> REPLAY_AUTH
   - Logs: AUTH_START / AUTH_OK / AUTH_FAIL reason=...
========================================================= */

static bool     g_enableAuthBind = true;
static bool     g_enableMitmAttack = false;

static bool     g_enableAuthProbe = false;
static uint32_t g_authProbeIntervalMs = 500;

static bool     g_enableAuthReplayAttack = false;   // resend same tuple
static uint32_t g_authReplayEveryN = 5;             // every Nth probe uses same nonce

static uint64_t g_authOk = 0;
static uint64_t g_authFail = 0;
static uint64_t g_authFailMitm = 0;
static uint64_t g_authFailReplay = 0;

static std::ofstream* g_evt = nullptr;
static inline double NowS() { return Simulator::Now().GetSeconds(); }
static inline uint64_t NowMs64() { return (uint64_t)Simulator::Now().GetMilliSeconds(); }

static inline void EmitEvt(const std::string& s)
{
  if (g_evt && (*g_evt))
    (*g_evt) << NowS() << "," << s << "\n";
}

// ---- Tiny Schnorr parameters (safe-prime toy group) ----
// p = 1223, q = 611 (prime), g in subgroup of order q.
static const uint64_t AUTH_P = 1223;
static const uint64_t AUTH_Q = 611;
static const uint64_t AUTH_G = 4;

static uint64_t ModPow(uint64_t a, uint64_t e, uint64_t m)
{
  uint64_t r = 1 % m;
  a %= m;
  while (e)
  {
    if (e & 1) r = (r * a) % m;
    a = (a * a) % m;
    e >>= 1;
  }
  return r;
}
static uint64_t ModInv(uint64_t a, uint64_t m)
{
  // m is prime here -> Fermat
  return ModPow(a, m - 2, m);
}

// stable 32-bit hash (FNV-1a)
static uint32_t H32(const std::string& s)
{
  uint32_t h = 2166136261u;
  for (unsigned char c : s)
  {
    h ^= (uint32_t)c;
    h *= 16777619u;
  }
  return h;
}
static uint64_t Hq(const std::string& s) { return (uint64_t)(H32(s) % (uint32_t)AUTH_Q); }

// keys per vehicle
static std::vector<uint64_t> g_authPrivX; // x in [1..q-1]
static std::vector<uint64_t> g_authPubY;  // y = g^x mod p

static void AuthInitKeys(uint32_t nVehicles)
{
  g_authPrivX.assign(nVehicles, 0);
  g_authPubY.assign(nVehicles, 0);

  // deterministic from (seed, vid) without extra RNG requirements
  for (uint32_t v = 0; v < nVehicles; ++v)
  {
    uint64_t x = (uint64_t)(1 + (H32(std::to_string(g_seed) + ":" + std::to_string(v)) % (uint32_t)(AUTH_Q - 1)));
    g_authPrivX[v] = x;
    g_authPubY[v]  = ModPow(AUTH_G, x, AUTH_P);
  }
}

struct AuthSig
{
  uint64_t e = 0; // challenge
  uint64_t s = 0; // response
};

// Sign: choose k -> r=g^k, e=H(m||r), s=k+e*x mod q
static AuthSig AuthSign(uint32_t sender, const std::string& msg, uint64_t k)
{
  AuthSig sig;
  uint64_t r = ModPow(AUTH_G, k % AUTH_Q, AUTH_P);
  sig.e = Hq(msg + "|" + std::to_string(r));
  sig.s = (k + (sig.e * g_authPrivX[sender]) % AUTH_Q) % AUTH_Q;
  return sig;
}

// Verify: r' = g^s * y^{-e} mod p, check e == H(m||r')
static bool AuthVerify(uint32_t sender, const std::string& msg, const AuthSig& sig)
{
  if (sender >= g_authPubY.size()) return false;
  uint64_t gs = ModPow(AUTH_G, sig.s % AUTH_Q, AUTH_P);
  uint64_t ye = ModPow(g_authPubY[sender], sig.e % AUTH_Q, AUTH_P);
  uint64_t r  = (gs * ModInv(ye, AUTH_P)) % AUTH_P;
  uint64_t e2 = Hq(msg + "|" + std::to_string(r));
  return (e2 == (sig.e % AUTH_Q));
}

// Replay cache: (sender, nonce, tsMs) seen?
static std::unordered_set<std::string> g_authReplayCache;
static inline std::string ReplayKey(uint32_t sender, uint64_t nonce, uint64_t tsMs)
{
  return std::to_string(sender) + "|" + std::to_string(nonce) + "|" + std::to_string(tsMs);
}

// Compose binding message
static inline std::string AuthMsg(uint32_t sender,
                                  const std::string& pseudoKey,
                                  const std::string& ephPub,
                                  uint64_t nonce,
                                  uint64_t tsMs)
{
  return std::to_string(sender) + "|" + pseudoKey + "|" + ephPub + "|" +
         std::to_string(nonce) + "|" + std::to_string(tsMs);
}

// One probe attempt (sender -> receiver)
static void DoAuthAttempt(uint32_t sender, uint32_t receiver, uint64_t nonce, uint64_t tsMs, uint64_t k)
{
  // pseudoKey: if privacy enabled, use active pseudonym; else use senderId string
  std::string pseudoKey = std::to_string(sender);
  if (g_enablePrivacy)
  {
    // best-effort: use existing GetActivePseudo if present
    // If compile fails here, we'll switch to a simpler key = senderId
    extern const std::string& GetActivePseudo(uint32_t v);
    pseudoKey = GetActivePseudo(sender);
  }

  std::string ephPub = "E" + std::to_string(sender) + "_" + std::to_string(tsMs); // simulated eph pub
  std::string msg = AuthMsg(sender, pseudoKey, ephPub, nonce, tsMs);

  EmitEvt("AUTH_START sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver));

  // MITM tamper at receiver
  std::string ephRx = ephPub;
  if (g_enableMitmAttack) ephRx = ephPub + "_TAMPER";

  // replay detection (receiver side)
  const std::string rk = ReplayKey(sender, nonce, tsMs);
  if (g_authReplayCache.count(rk))
  {
    g_authFail++; g_authFailReplay++;
    EmitEvt("AUTH_FAIL sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver) + " reason=REPLAY_AUTH");
    return;
  }

  // sign using k (deterministic)
  AuthSig sig = AuthSign(sender, msg, k);

  // verify with possibly-tampered eph
  std::string msgRx = AuthMsg(sender, pseudoKey, ephRx, nonce, tsMs);
  const bool ok = AuthVerify(sender, msgRx, sig);

  if (!ok)
  {
    g_authFail++;
    if (g_enableMitmAttack) g_authFailMitm++;
    EmitEvt("AUTH_FAIL sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver) + " reason=BAD_SIG");
    return;
  }

  g_authReplayCache.insert(rk);
  g_authOk++;
  EmitEvt("AUTH_OK sender=" + std::to_string(sender) + " rx=" + std::to_string(receiver));
}

// periodic probe driver
static void AuthProbeTick()
{
  if (!g_enableAuthProbe) return;
  if (g_nVehicles < 2) return;

  static uint64_t ctr = 0;
  ctr++;

  // deterministic nonce/k
  uint64_t tsMs = NowMs64();
  uint64_t nonce = (uint64_t)H32("N:" + std::to_string(g_seed) + ":" + std::to_string(ctr));
  uint64_t k     = (uint64_t)(1 + (H32("K:" + std::to_string(g_seed) + ":" + std::to_string(ctr)) % (uint32_t)(AUTH_Q - 1)));

  // replay mode: reuse nonce every N
  static uint64_t lastNonce = 0;
  static uint64_t lastTs = 0;
  if (g_enableAuthReplayAttack && (ctr % g_authReplayEveryN == 0))
  {
    nonce = lastNonce;
    tsMs  = lastTs;
  }
  else
  {
    lastNonce = nonce;
    lastTs    = tsMs;
  }

  // pair: sender=0, receiver=1 (enough to test binding correctness)
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
// AUTH_BIND_V2_END
'''

def patch_file(p: Path):
    txt = p.read_text()

    # remove older auth blocks
    txt = re.sub(r"// AUTH_BIND_V1_BEGIN.*?// AUTH_BIND_V1_END\s*", "", txt, flags=re.S)
    txt = re.sub(r"// AUTH_BIND_V2_BEGIN.*?// AUTH_BIND_V2_END\s*", "", txt, flags=re.S)

    # ensure unordered_set include
    if "#include <unordered_set>" not in txt:
        txt = txt.replace("#include <unordered_map>\n", "#include <unordered_map>\n#include <unordered_set>\n", 1)

    # insert before GetTrustForHandover()
    m = re.search(r"\nstatic\s+double\s+GetTrustForHandover\s*\(", txt)
    if not m:
        raise SystemExit(f"[ERR] GetTrustForHandover not found in {p}")
    ins = m.start()
    txt = txt[:ins] + "\n" + AUTH_BLOCK + "\n" + txt[ins:]

    # hook events stream pointer (re-use existing events stream var)
    m2 = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut", txt)
    if m2:
        var = m2.group(1)
        line = f"  g_evt = &{var};\n"
        # inject after stream creation
        pos = m2.end()
        nxt = txt.find("\n", pos) + 1
        if line not in txt[nxt:nxt+200]:
            txt = txt[:nxt] + line + txt[nxt:]

    # ensure cmd flags exist
    def ensure_cmd(flag, desc, varname):
        nonlocal txt
        if f'cmd.AddValue("{flag}"' in txt:
            return
        # place near other auth flags if present, else near end before cmd.Parse
        anchor = re.search(r'cmd\.AddValue\("enableMitmAttack".*?\);\s*\n', txt)
        if not anchor:
            anchor = re.search(r'cmd\.AddValue\("enableAuthBind".*?\);\s*\n', txt)
        if not anchor:
            anchor = re.search(r"cmd\.Parse\s*\(\s*argc\s*,\s*argv\s*\)\s*;\s*", txt)
            if not anchor:
                raise SystemExit(f"[ERR] cmd.Parse not found in {p}")
            pos = anchor.start()
        else:
            pos = anchor.end()
        txt = txt[:pos] + f'  cmd.AddValue("{flag}", "{desc}", {varname});\n' + txt[pos:]

    ensure_cmd("enableAuthBind", "Bind ECDH ephemeral key to signature-style auth", "g_enableAuthBind")
    ensure_cmd("enableMitmAttack", "MITM test: tamper ephPub at receiver (must fail)", "g_enableMitmAttack")
    ensure_cmd("enableAuthProbe", "Generate periodic auth handshakes (to measure AUTH)", "g_enableAuthProbe")
    ensure_cmd("authProbeIntervalMs", "Auth probe interval (ms)", "g_authProbeIntervalMs")
    ensure_cmd("enableAuthReplayAttack", "Replay auth tuple periodically (must fail)", "g_enableAuthReplayAttack")
    ensure_cmd("authReplayEveryN", "Replay every N probes", "g_authReplayEveryN")

    # ensure keys init + probe start + print stats
    # after g_ledgerTrust init OR after PrivacyInit
    if "AuthInitKeys(" not in txt:
        txt = txt.replace("g_ledgerTrust.assign(g_nVehicles, 0.8);",
                          "g_ledgerTrust.assign(g_nVehicles, 0.8);\n  AuthInitKeys(g_nVehicles);", 1)
    if "StartAuthProbes();" not in txt:
        if "StartBcProbes();" in txt:
            txt = txt.replace("StartBcProbes();", "StartBcProbes();\n  StartAuthProbes();", 1)
        else:
            txt = txt.replace("PrivacyInit();", "PrivacyInit();\n  StartAuthProbes();", 1)

    if "PrintAuthStats();" not in txt:
        txt = txt.replace("Simulator::Destroy();", "  PrintAuthStats();\n  Simulator::Destroy();", 1)

    p.write_text(txt)
    print("[OK] patched AUTH schnorr bind v2 in:", p)

for p in targets:
    if p.exists():
        patch_file(p)
