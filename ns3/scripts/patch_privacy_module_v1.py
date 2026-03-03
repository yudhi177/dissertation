from pathlib import Path
import re, sys

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 0) remove old privacy blocks if any
txt = re.sub(r"// PRIVACY_MODULE_V1_BEGIN.*?// PRIVACY_MODULE_V1_END\s*",
             "", txt, flags=re.S)

# 1) ensure <cmath> exists (sqrt)
if "#include <cmath>" not in txt:
    txt = txt.replace("#include <algorithm>\n", "#include <algorithm>\n#include <cmath>\n")

# 2) patch DataHdr to include pseudoId (keep senderId for internal trust)
hdr_pat = re.compile(r"#pragma pack\(push, 1\)\s*struct DataHdr\s*\{.*?\};\s*#pragma pack\(pop\)", re.S)
new_hdr = r"""#pragma pack(push, 1)
struct DataHdr
{
  uint64_t nonce;
  double   txTime;
  uint32_t senderId;   // internal ID (trust engine uses this)
  uint32_t pseudoId;   // transmitted pseudonym (attacker sees this)
  uint32_t sig;
};
#pragma pack(pop)"""
if not hdr_pat.search(txt):
    raise SystemExit("[ERR] Could not find DataHdr block to patch.")
txt = hdr_pat.sub(new_hdr, txt, count=1)

# 3) insert globals after ports section (g_reportPort)
anchor = "static const uint16_t g_reportPort"
i = txt.find(anchor)
if i == -1:
    raise SystemExit("[ERR] Could not find anchor: g_reportPort")
ins_at = txt.find("\n", i)
ins_at = txt.find("\n", ins_at+1)

privacy_globals = r"""
// PRIVACY_MODULE_V1_BEGIN
/* =========================================================
   PRIVACY MODULE (v1)
   - Pseudonym pool >= 5 per vehicle
   - Timer-based rotation + RSU-triggered rotation
   - On-chain registration (simulated) of pseudonym hash
   - Linkability events (LINK_ATTEMPT / LINK_SUCCESS)
========================================================= */
static bool     g_enablePrivacy       = false;
static uint32_t g_pseudoPoolSize      = 5;
static uint32_t g_pseudoRotateSec     = 5;     // timer rotation
static bool     g_rotateOnRsuChange   = true;  // RSU-triggered rotation

// Linkability model (simple attacker using continuity + mix-zone)
static double   g_linkTimeWindowSec   = 2.0;
static double   g_linkDistThresh      = 25.0;  // meters
static double   g_linkNeighborRadius  = 30.0;  // meters
static uint32_t g_linkMixK            = 3;     // if neighbors >=K => mix-zone => harder to link

struct PseudoState
{
  std::vector<uint64_t> pool;
  uint32_t idx = 0;
  double   lastRotate = 0.0;
};

static std::vector<PseudoState> g_pseudo;
static std::vector<uint64_t>    g_activePseudo;
static std::vector<uint64_t>    g_prevPseudo;
static std::vector<Vector>      g_prevPos;
static std::vector<double>      g_prevTime;

static uint64_t g_pseudoRotations      = 0;
static uint64_t g_pseudoRegistrations  = 0;
static uint64_t g_linkAttempts         = 0;
static uint64_t g_linkSuccess          = 0;
// PRIVACY_MODULE_V1_END
"""
txt = txt[:ins_at] + "\n" + privacy_globals + "\n" + txt[ins_at:]

# 4) insert privacy helper functions after Dist2() helper
dist2_pos = txt.find("static double Dist2")
if dist2_pos == -1:
    raise SystemExit("[ERR] Could not find Dist2() to insert privacy helpers after it.")
# find end of Dist2 function (first '}\n' after its start)
end_dist2 = txt.find("}\n", dist2_pos)
end_dist2 = txt.find("\n", end_dist2+2)

privacy_helpers = r"""
/* =========================================================
   PRIVACY HELPERS
========================================================= */
static uint64_t PseudoHash64(uint64_t x)
{
  // splitmix64
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  x = x ^ (x >> 31);
  return x;
}

static uint32_t CountNeighbors(uint32_t v, double radius)
{
  if (v >= g_nVehicles) return 0;
  Ptr<MobilityModel> mv = g_vehicles.Get(v)->GetObject<MobilityModel>();
  if (!mv) return 0;
  Vector pv = mv->GetPosition();
  double r2 = radius * radius;
  uint32_t c = 0;
  for (uint32_t i = 0; i < g_nVehicles; i++)
  {
    if (i == v) continue;
    Ptr<MobilityModel> mi = g_vehicles.Get(i)->GetObject<MobilityModel>();
    if (!mi) continue;
    if (Dist2(pv, mi->GetPosition()) <= r2) c++;
  }
  return c;
}

static void RegisterPseudoOnChain(uint32_t v, uint64_t pseudo)
{
  (void)pseudo;
  g_pseudoRegistrations++;
  LogEvent("PSEUDO_REG v=" + std::to_string(v));
}

static void InitPseudonyms()
{
  g_pseudo.assign(g_nVehicles, PseudoState{});
  g_activePseudo.assign(g_nVehicles, 0ULL);
  g_prevPseudo.assign(g_nVehicles, 0ULL);
  g_prevPos.assign(g_nVehicles, Vector(0,0,0));
  g_prevTime.assign(g_nVehicles, -1e9);

  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    auto &st = g_pseudo[v];
    st.pool.clear();
    for (uint32_t k = 0; k < g_pseudoPoolSize; k++)
    {
      uint64_t pseudo = PseudoHash64((uint64_t(v) << 32) ^ uint64_t(k + 1));
      st.pool.push_back(pseudo);
      RegisterPseudoOnChain(v, pseudo);
    }
    st.idx = 0;
    st.lastRotate = Simulator::Now().GetSeconds();
    g_activePseudo[v] = st.pool.empty() ? 0ULL : st.pool[0];
    LogEvent("PSEUDO_INIT v=" + std::to_string(v));
  }
}

static void EvaluateLinkability(uint32_t v, uint64_t newPseudo, const std::string& reason)
{
  double now = Simulator::Now().GetSeconds();
  if (v >= g_nVehicles) return;

  Ptr<MobilityModel> mv = g_vehicles.Get(v)->GetObject<MobilityModel>();
  if (!mv) return;

  Vector nowPos = mv->GetPosition();
  if (g_prevTime[v] > -1e8)
  {
    g_linkAttempts++;
    double dt = now - g_prevTime[v];
    double dist = std::sqrt(Dist2(nowPos, g_prevPos[v]));
    uint32_t neigh = CountNeighbors(v, g_linkNeighborRadius);

    LogEvent("LINK_ATTEMPT v=" + std::to_string(v) +
             " dt=" + std::to_string(dt) +
             " dist=" + std::to_string(dist) +
             " neigh=" + std::to_string(neigh) +
             " reason=" + reason);

    bool success = (dt <= g_linkTimeWindowSec) && (dist <= g_linkDistThresh) && (neigh < g_linkMixK);
    if (success)
    {
      g_linkSuccess++;
      LogEvent("LINK_SUCCESS v=" + std::to_string(v));
    }
  }

  g_prevTime[v] = now;
  g_prevPos[v] = nowPos;
  g_prevPseudo[v] = newPseudo;
}

static void RotatePseudonym(uint32_t v, const std::string& reason)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  if (v >= g_pseudo.size()) return;

  auto &st = g_pseudo[v];
  if (st.pool.empty()) return;

  st.idx = (st.idx + 1) % st.pool.size();
  uint64_t newPseudo = st.pool[st.idx];

  EvaluateLinkability(v, newPseudo, reason);

  g_activePseudo[v] = newPseudo;
  st.lastRotate = Simulator::Now().GetSeconds();
  g_pseudoRotations++;

  LogEvent("PSEUDO_ROT v=" + std::to_string(v) + " reason=" + reason);
}

static void PseudoTimerTick(uint32_t v)
{
  if (!g_enablePrivacy) return;
  if (v >= g_nVehicles) return;
  if (v >= g_pseudo.size()) return;

  double now = Simulator::Now().GetSeconds();
  if ((now - g_pseudo[v].lastRotate) >= double(g_pseudoRotateSec))
  {
    RotatePseudonym(v, "TIMER");
  }
  Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);
}
"""
txt = txt[:end_dist2] + "\n" + privacy_helpers + "\n" + txt[end_dist2:]

# 5) Add CommandLine options
if 'cmd.AddValue("enablePrivacy"' not in txt:
    txt = re.sub(r'(cmd\.AddValue\("eventsOut"[^\n]*\);\s*)',
                 r'\1'
                 r'  cmd.AddValue("enablePrivacy", "Enable privacy module 0/1", g_enablePrivacy);\n'
                 r'  cmd.AddValue("pseudoPoolSize", "Pseudonym pool size", g_pseudoPoolSize);\n'
                 r'  cmd.AddValue("pseudoRotateSec", "Timer-based pseudonym rotation sec", g_pseudoRotateSec);\n'
                 r'  cmd.AddValue("rotateOnRsuChange", "Rotate pseudonym on RSU change 0/1", g_rotateOnRsuChange);\n',
                 txt, count=1)

# 6) Patch sender to set pseudoId + PSEUDO_USE log
def patch_sender(fn_name):
    nonlocal_txt = txt
    pat = re.compile(rf"(static void {fn_name}\s*\(.*?\)\s*\{{)([\s\S]*?)(\n\}})\s*", re.M)
    m = pat.search(nonlocal_txt)
    if not m:
        return None

    body = m.group(2)
    # Insert right after hdr.senderId assignment (or after senderId set)
    if "hdr.pseudoId" in body:
        return nonlocal_txt

    body2 = re.sub(r'(hdr\.senderId\s*=\s*senderId;\s*)',
                   r'\1\n  hdr.pseudoId = (g_enablePrivacy && senderId < g_activePseudo.size()) ? uint32_t(g_activePseudo[senderId] & 0xffffffffULL) : senderId;\n'
                   r'  if (g_enablePrivacy) { LogEvent("PSEUDO_USE v=" + std::to_string(senderId) + " pseudo=" + std::to_string(hdr.pseudoId)); }\n',
                   body, count=1)

    return nonlocal_txt[:m.start(2)] + body2 + nonlocal_txt[m.end(2):]

newtxt = patch_sender("SendFromVehicle")
if newtxt is None:
    newtxt = patch_sender("SendNewPacket")
if newtxt is None:
    raise SystemExit("[ERR] Could not find SendFromVehicle or SendNewPacket to patch.")
txt = newtxt

# 7) RSU-triggered rotation: hook after handover completes (FinishHandover)
if "RotatePseudonym(" not in txt:
    txt = re.sub(r'(LogEvent\("HO_DONE[^\n]*\);\s*)',
                 r'\1\n  if (g_enablePrivacy && g_rotateOnRsuChange) { RotatePseudonym(v, "RSU"); }\n',
                 txt, count=1)

# 8) init pseudonyms in main (after TrustInit or after g_ledgerTrust.assign)
if "InitPseudonyms();" not in txt:
    txt = re.sub(r'(TrustInit\(\);\s*)',
                 r'\1\n  if (g_enablePrivacy) { InitPseudonyms(); }\n',
                 txt, count=1)

# 9) schedule timer tick per vehicle in main
if "PseudoTimerTick" not in txt:
    txt = re.sub(r'(for\s*\(uint32_t v\s*=\s*0;\s*v\s*<\s*g_nVehicles;\s*v\+\+\)\s*\n\s*Simulator::Schedule\([^\n]*&CheckHandover[^\n]*\);\s*)',
                 r'\1\n  if (g_enablePrivacy) {\n    for (uint32_t v = 0; v < g_nVehicles; v++)\n      Simulator::Schedule(Seconds(1.0), &PseudoTimerTick, v);\n  }\n',
                 txt, count=1)

p.write_text(txt)
print("[OK] Privacy module v1 patched into:", p)
