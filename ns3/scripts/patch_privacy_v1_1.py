from pathlib import Path
import re

P = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = P.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")

if "PRIVACY_MODULE_V1_1" in txt:
    print("[OK] Privacy patch already applied.")
    raise SystemExit(0)

# --- helper: insert after first match
def insert_after(pattern, insert_text, count=1):
    nonlocal_txt = None

def do_insert_after(text, pattern, insert_text, count=1):
    m = re.search(pattern, text)
    if not m:
        return None
    return text[:m.end()] + insert_text + text[m.end():]

# 0) Ensure <random> include
if "#include <random>" not in txt:
    if "#include <algorithm>" in txt:
        txt = txt.replace("#include <algorithm>\n", "#include <algorithm>\n#include <random>\n")
    else:
        # fallback: after last include
        incs = list(re.finditer(r"^#include[^\n]*\n", txt, flags=re.M))
        if incs:
            last = incs[-1]
            txt = txt[:last.end()] + "#include <random>\n" + txt[last.end():]

# 1) Add privacy globals near GLOBAL PARAMETERS
privacy_globals = r'''
// ======================= PRIVACY_MODULE_V1_1 =======================
static bool     g_enablePrivacy = true;
static uint32_t g_pseudoPoolSize = 5;          // >=5/vehicle
static uint32_t g_pseudoRotateSec = 5;         // time-based rotation
static bool     g_rotateOnRsuChange = true;    // RSU-triggered rotation
static bool     g_registerPseudoOnChain = true;// store pseudonym hash in chain (simulated)
static double   g_linkWindowSec = 1.0;         // attacker time window
static double   g_linkDistThresh = 25.0;       // attacker distance threshold (meters)
// ================================================================
'''
inserted = False
for pat in [
    r"(static\s+bool\s+g_enableTrustGate\s*=\s*[^;]+;\s*\n)",
    r"(static\s+bool\s+g_enableBlockchain\s*=\s*[^;]+;\s*\n)",
    r"(static\s+double\s+g_maliciousRate\s*=\s*[^;]+;\s*\n)",
]:
    m = re.search(pat, txt)
    if m:
        txt = txt[:m.end()] + privacy_globals + txt[m.end():]
        inserted = True
        break

if not inserted:
    raise SystemExit("[ERR] Could not find insertion point for privacy globals.")

# 2) Add CommandLine args after eventsOut
privacy_cmd = r'''
  cmd.AddValue("enablePrivacy", "Enable privacy/pseudonyms 0/1", g_enablePrivacy);
  cmd.AddValue("pseudoPoolSize", "Pseudonym pool size", g_pseudoPoolSize);
  cmd.AddValue("pseudoRotateSec", "Time-based pseudonym rotation seconds", g_pseudoRotateSec);
  cmd.AddValue("rotateOnRsuChange", "Rotate pseudonym on RSU change 0/1", g_rotateOnRsuChange);
  cmd.AddValue("registerPseudoOnChain", "Register pseudonym hash on chain 0/1", g_registerPseudoOnChain);
  cmd.AddValue("linkWindowSec", "Linkability time window seconds", g_linkWindowSec);
  cmd.AddValue("linkDistThresh", "Linkability distance threshold", g_linkDistThresh);
'''
if 'cmd.AddValue("enablePrivacy"' not in txt:
    m = re.search(r'(cmd\.AddValue\("eventsOut"[^\n]*\);\s*\n)', txt)
    if not m:
        raise SystemExit('[ERR] Could not find cmd.AddValue("eventsOut"...).')
    txt = txt[:m.end()] + privacy_cmd + txt[m.end():]

# 3) Patch DataHdr: add pseudoId field (public pseudonym) after senderId
if "pseudoId" not in txt:
    def patch_datahdr(block: str) -> str:
        out=[]
        in_hdr=False
        for line in block.splitlines(True):
            if re.search(r"\bstruct\s+DataHdr\b", line):
                in_hdr=True
            if in_hdr and re.search(r"\buint32_t\s+senderId\s*;", line):
                out.append(line)
                out.append("  uint32_t pseudoId; // privacy pseudonym (public)\n")
                continue
            out.append(line)
            if in_hdr and re.search(r"^\s*\};\s*$", line):
                in_hdr=False
        return "".join(out)
    txt = patch_datahdr(txt)

# 4) Insert privacy state (global scope) after g_vs
privacy_state = r'''
/* =========================================================
   PRIVACY / PSEUDONYM STATE (GLOBAL)
========================================================= */
struct PseudoState
{
  std::vector<uint32_t> pool;
  uint32_t idx = 0;
  double lastRotate = 0.0;
  uint32_t current() const { return pool.empty() ? 0u : pool[idx % pool.size()]; }
};

static std::vector<PseudoState> g_pseudo;       // per vehicle
static std::vector<uint32_t>    g_activePseudo; // active pseudo per vehicle

static uint64_t g_pseudoRotations = 0;
static uint64_t g_linkAttempts = 0;
static uint64_t g_linkSuccess  = 0;
static uint64_t g_pseudoRegistrations = 0;

static std::vector<uint32_t> g_prevPseudo;
static std::vector<Vector>   g_prevPos;
static std::vector<double>   g_prevTime;
'''
if "struct PseudoState" not in txt:
    m = re.search(r"(static\s+std::vector<VehicleState>\s+g_vs;[ \t]*\n)", txt)
    if not m:
        raise SystemExit("[ERR] Could not find g_vs marker for privacy insertion.")
    txt = txt[:m.end()] + privacy_state + txt[m.end():]

# 5) Insert privacy helper functions before ProcessData()
privacy_helpers = r'''
/* =========================================================
   PRIVACY HELPERS
========================================================= */
static uint32_t Hash32(uint32_t x)
{
  x ^= x >> 16;
  x *= 0x7feb352dU;
  x ^= x >> 15;
  x *= 0x846ca68bU;
  x ^= x >> 16;
  return x;
}

static void RegisterPseudoOnChain(uint32_t v, uint32_t pseudo)
{
  if (!g_registerPseudoOnChain) return;
  uint32_t h = Hash32(pseudo);
  g_pseudoRegistrations++;
  LogEvent("PSEUDO_REG v=" + std::to_string(v) + " hash=" + std::to_string(h));
}

static void InitPseudonyms()
{
  g_pseudo.assign(g_nVehicles, PseudoState{});
  g_activePseudo.assign(g_nVehicles, 0u);

  g_prevPseudo.assign(g_nVehicles, 0u);
  g_prevPos.assign(g_nVehicles, Vector(0,0,0));
  g_prevTime.assign(g_nVehicles, -1e9);

  std::mt19937 rng(1234567);

  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    g_pseudo[v].pool.clear();
    uint32_t K = (g_pseudoPoolSize < 5) ? 5 : g_pseudoPoolSize;
    for (uint32_t k = 0; k < K; k++)
      g_pseudo[v].pool.push_back(rng());

    g_pseudo[v].idx = v % g_pseudo[v].pool.size();
    g_pseudo[v].lastRotate = 0.0;

    g_activePseudo[v] = g_pseudo[v].current();
    RegisterPseudoOnChain(v, g_activePseudo[v]);

    if (v < g_vehicles.GetN() && g_vehicles.Get(v)->GetObject<MobilityModel>())
      g_prevPos[v] = g_vehicles.Get(v)->GetObject<MobilityModel>()->GetPosition();

    g_prevPseudo[v] = g_activePseudo[v];
    g_prevTime[v] = 0.0;
  }
}

static void EvaluateLinkability(uint32_t v, uint32_t newPseudo)
{
  double now = Simulator::Now().GetSeconds();
  if (g_prevTime[v] < -1e8) return;

  double dt = now - g_prevTime[v];
  if (dt < 0) dt = 0;

  if (dt <= g_linkWindowSec)
  {
    g_linkAttempts++;
    Vector nowPos = g_vehicles.Get(v)->GetObject<MobilityModel>()->GetPosition();
    double d2 = Dist2(nowPos, g_prevPos[v]);
    if (d2 <= (g_linkDistThresh * g_linkDistThresh))
      g_linkSuccess++;
  }

  g_prevPseudo[v] = newPseudo;
  g_prevPos[v] = g_vehicles.Get(v)->GetObject<MobilityModel>()->GetPosition();
  g_prevTime[v] = now;
}

static void RotatePseudonym(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  if (g_pseudo[v].pool.empty()) return;

  g_pseudo[v].idx = (g_pseudo[v].idx + 1) % g_pseudo[v].pool.size();
  g_pseudo[v].lastRotate = Simulator::Now().GetSeconds();

  uint32_t newPseudo = g_pseudo[v].current();
  g_activePseudo[v] = newPseudo;

  g_pseudoRotations++;
  LogEvent("PSEUDO_ROT v=" + std::to_string(v) + " reason=" + reason);

  RegisterPseudoOnChain(v, newPseudo);
  EvaluateLinkability(v, newPseudo);
}

static void PseudoTimerTick(uint32_t v)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  double now = Simulator::Now().GetSeconds();
  if (now - g_pseudo[v].lastRotate >= double(g_pseudoRotateSec))
    RotatePseudonym(v, "TIME");

  Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
}
'''
if "PRIVACY HELPERS" not in txt:
    m = re.search(r"(static\s+void\s+ProcessData\s*\()", txt)
    if not m:
        raise SystemExit("[ERR] Could not find ProcessData() to insert privacy helpers.")
    txt = txt[:m.start()] + privacy_helpers + txt[m.start():]

# 6) In SendFromVehicle / SendNewPacket: set pseudoId + clean log line
# We patch ONLY if 'hdr.pseudoId' not present in send path.
if "hdr.pseudoId" not in txt:
    # try both function names depending on your version
    txt2 = re.sub(
        r"(hdr\.senderId\s*=\s*senderId\s*;\s*\n)",
        r"\1  hdr.pseudoId = (g_enablePrivacy ? g_activePseudo[senderId] : senderId);\n"
        r"  if (g_enablePrivacy) { LogEvent(\"PSEUDO_USE v=\" + std::to_string(senderId) + \" pseudo=\" + std::to_string(hdr.pseudoId)); }\n",
        txt,
        count=1
    )
    txt = txt2

# IMPORTANT: Fix any accidental \" in C++ source (this is what broke your build)
txt = txt.replace('\\"', '"')

# 7) Rotate on RSU change inside handover check (if present)
if "RotatePseudonym(id, \"RSU\")" not in txt:
    txt = re.sub(
        r"(if\s*\(\s*target\s*!=\s*current\s*&&\s*!g_vs\[id\]\.authInProgress\s*\)\s*\{\s*\n)",
        r"\1    if (g_enablePrivacy && g_rotateOnRsuChange) { RotatePseudonym(id, \"RSU\"); }\n",
        txt,
        count=1
    )
# cleanup \" again
txt = txt.replace('\\"', '"')

# 8) Add metrics to WriteCsv (only if header not already extended)
if "pseudoRotations" not in txt:
    # header add
    txt = re.sub(
        r"(fullAuthDelayMs\\n\")",
        r"fullAuthDelayMs,pseudoRotations,linkAttempts,linkSuccess,linkabilityProb,pseudoRegistrations\\n\"",
        txt,
        count=1
    )

    # compute linkProb after avgHoDelay
    txt = re.sub(
        r"(double\s+avgHoDelay\s*=\s*\(g_handoverCount\s*>\s*0\)[^;]*;\s*\n)",
        r"\1  double linkProb = (g_linkAttempts > 0) ? (double(g_linkSuccess) / double(g_linkAttempts)) : 0.0;\n",
        txt,
        count=1
    )

    # append values (best-effort: after fullAuthDelayMs output)
    txt = re.sub(
        r"(<<\s*g_fullAuthDelayMs\s*\n\s*<<\s*\"\n\";)",
        r"<< g_fullAuthDelayMs\n"
        r"    << \",\" << g_pseudoRotations\n"
        r"    << \",\" << g_linkAttempts\n"
        r"    << \",\" << g_linkSuccess\n"
        r"    << \",\" << linkProb\n"
        r"    << \",\" << g_pseudoRegistrations\n"
        r"    << \"\n\";",
        txt,
        count=1
    )

# 9) Init pseudonyms in main after trust ledger init (or after node create if ledger init differs)
if "InitPseudonyms();" not in txt:
    # Prefer after ledger trust assign
    m = re.search(r"(g_ledgerTrust\.assign\(g_nVehicles,[^\)]*\);\s*\n)", txt)
    if m:
        ins = r'''
  if (g_enablePrivacy)
  {
    InitPseudonyms();
    for (uint32_t v = 0; v < g_nVehicles; v++)
      Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
  }
'''
        txt = txt[:m.end()] + ins + txt[m.end():]
    else:
        # fallback: after NodeContainer all created (very safe)
        m2 = re.search(r"(all\.Add\(g_rsus\);\s*\n)", txt)
        if not m2:
            raise SystemExit("[ERR] Could not find safe insertion point for InitPseudonyms().")
        ins = r'''
  if (g_enablePrivacy)
  {
    // will be fully valid after mobility install; call again later if needed
    Simulator::Schedule(Seconds(0.1), [](){
      InitPseudonyms();
      for (uint32_t v = 0; v < g_nVehicles; v++)
        Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
    });
  }
'''
        txt = txt[:m2.end()] + ins + txt[m2.end():]

# FINAL cleanup
txt = txt.replace('\\"', '"')
txt = txt.replace("PRIVACY_MODULE_V1", "PRIVACY_MODULE_V1_1")

P.write_text(txt, encoding="utf-8")
print("[OK] Privacy patch v1.1 applied:", P)
