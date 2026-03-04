from pathlib import Path
import re

p = Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# remove older block if exists
txt = re.sub(r"// AUTH_BIND_V1_BEGIN.*?// AUTH_BIND_V1_END\s*", "", txt, flags=re.S)

# insert before SimpleSig() declaration (we forward-declare it)
m = re.search(r"\nstatic\s+uint32_t\s+SimpleSig\s*\(", txt)
if not m:
    raise SystemExit("[ERR] Could not find SimpleSig() to insert AUTH block before it.")

ins = m.start()

block = r'''
// AUTH_BIND_V1_BEGIN
/* =========================================================
   Authenticated ECDH Binding (v1) + MITM Test Mode
   - We bind (ephemeralPubKey + nonce + timestamp) to a signature-like tag.
   - Uses existing SimpleSig() as lightweight binding primitive (simulation-friendly).
   - MITM mode tampers pubkey at receiver => MUST fail verification.
========================================================= */
static bool g_enableAuthBind = true;
static bool g_enableMitmAttack = false;

static uint64_t g_authOk = 0;
static uint64_t g_authFail = 0;
static uint64_t g_authFailMitm = 0;

// forward declare (definition exists later)
static uint32_t SimpleSig(const std::string& s);

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

# add CLI flags near other cmd.AddValue lines (after bcProbe flags if present)
flags = r'''
  cmd.AddValue("enableAuthBind", "Bind ECDH ephemeral key to auth tag", g_enableAuthBind);
  cmd.AddValue("enableMitmAttack", "MITM test: tamper pubkey at receiver (should fail)", g_enableMitmAttack);
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

# print auth stats before Destroy
if "PrintAuthStats();" not in txt:
    txt = txt.replace("Simulator::Destroy();", "  PrintAuthStats();\n  Simulator::Destroy();", 1)

p.write_text(txt)
print("[OK] Patched AUTH bind + MITM flags into:", p)
