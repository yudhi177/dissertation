from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# 0) Remove old revocation block if exists
txt = re.sub(r"// REVOCATION_MODULE_V1_BEGIN.*?// REVOCATION_MODULE_V1_END\s*", "", txt, flags=re.S)

# 1) Insert revocation block BEFORE "SIGNATURE" section (after helpers exist)
sig_anchor = re.search(r"/\*\s*=================================================\s*\n\s*SIGNATURE", txt)
if not sig_anchor:
    # fallback: any "SIGNATURE" marker
    sig_anchor = re.search(r"SIGNATURE\s*\(simple hash\)", txt)
if not sig_anchor:
    raise SystemExit("[ERR] Could not find SIGNATURE section marker to insert revocation block.")

ins = sig_anchor.start()

rev_block = r'''
// REVOCATION_MODULE_V1_BEGIN
/* =========================================================
   REVOCATION (v1)
   - Minimal on-chain model (simulated): revocation flag
   - Vehicles learn revocation via periodic sync (revokeSyncIntervalMs)
   - Measures propagation delay: REVOKE_ISSUE -> REVOKE_APPLY per node
========================================================= */
static bool     g_enableRevocation = false;
static double   g_revokeTrustThresh = 0.20;         // trust below => revoke
static uint32_t g_revokeSyncIntervalMs = 1000;      // ms
static bool     g_forceRevokeVehicle0 = false;
static double   g_forceRevokeTime = 2.0;            // seconds

static std::vector<uint8_t> g_revokedVeh;           // size nVehicles
static std::vector<uint8_t> g_revokeKnown;          // size all nodes
static std::vector<double>  g_revokeKnownTime;      // seconds
static double   g_revokeIssueTime = -1e9;

static uint64_t g_revocationsIssued = 0;
static uint64_t g_revocationsApplied = 0;
static uint64_t g_revokeDrops = 0;
static double   g_revPropDelayMax = 0.0;
static double   g_revPropDelaySum = 0.0;

static void IssueRevocation(uint32_t accused, const std::string& reason)
{
  if (!g_enableRevocation) return;
  if (accused >= g_revokedVeh.size()) return;
  if (g_revokedVeh[accused]) return;

  g_revokedVeh[accused] = 1;
  g_revocationsIssued++;

  if (accused == 0 && g_revokeIssueTime < -1e8)
    g_revokeIssueTime = Simulator::Now().GetSeconds();

  LogEvent("REVOKE_ISSUE accused=" + std::to_string(accused) + " reason=" + reason);
}

static void RevocationSyncTick(uint32_t nodeId)
{
  if (!g_enableRevocation) return;
  if (nodeId >= g_revokeKnown.size()) return;

  uint32_t accused = 0; // measure propagation for attacker0
  if (accused < g_revokedVeh.size() && g_revokedVeh[accused] && !g_revokeKnown[nodeId])
  {
    g_revokeKnown[nodeId] = 1;
    double now = Simulator::Now().GetSeconds();
    g_revokeKnownTime[nodeId] = now;
    g_revocationsApplied++;

    double d = (g_revokeIssueTime > -1e8) ? (now - g_revokeIssueTime) : 0.0;
    if (d < 0) d = 0;
    g_revPropDelaySum += d;
    if (d > g_revPropDelayMax) g_revPropDelayMax = d;

    LogEvent("REVOKE_APPLY node=" + std::to_string(nodeId) +
             " accused=" + std::to_string(accused) +
             " delay=" + std::to_string(d));
  }

  Simulator::Schedule(MilliSeconds(g_revokeSyncIntervalMs), &RevocationSyncTick, nodeId);
}

static void RevocationMonitorTick()
{
  if (!g_enableRevocation) return;
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    if (v < g_ledgerTrust.size() && !g_revokedVeh[v] && g_ledgerTrust[v] < g_revokeTrustThresh)
      IssueRevocation(v, "TRUST_BELOW_THRESH");
  }
  Simulator::Schedule(Seconds(0.5), &RevocationMonitorTick);
}
// REVOCATION_MODULE_V1_END

'''

txt = txt[:ins] + rev_block + txt[ins:]

# 2) Patch ProcessData() to drop revoked sender (insert right after function open brace)
m = re.search(r"static\s+void\s+ProcessData\s*\([^)]*\)\s*\{", txt)
if not m:
    raise SystemExit("[ERR] Could not find ProcessData(...) function to patch.")
insert_pos = m.end()

drop_snip = r'''
  // Revocation drop (vehicle-id based; keep privacy OFF in revoke experiments)
  if (g_enableRevocation && hdr.senderId < g_revokedVeh.size() && g_revokedVeh[hdr.senderId])
  {
    g_revokeDrops++;
    LogEvent("DATA_DROP_REVOKED rx=" + std::to_string(receiverId) +
             " sender=" + std::to_string(hdr.senderId));
    return;
  }

'''
if "DATA_DROP_REVOKED" not in txt:
    txt = txt[:insert_pos] + drop_snip + txt[insert_pos:]

# 3) Add cmd.AddValue options (insert after densityHigh option if exists)
if 'cmd.AddValue("enableRevocation"' not in txt:
    txt2 = re.sub(
        r'(cmd\.AddValue\("densityHigh"[^\n]*\);\s*)',
        r'\1\n'
        r'  cmd.AddValue("enableRevocation", "Enable revocation 0/1", g_enableRevocation);\n'
        r'  cmd.AddValue("revokeTrustThresh", "Trust below => revoke", g_revokeTrustThresh);\n'
        r'  cmd.AddValue("revokeSyncIntervalMs", "Revocation sync interval ms", g_revokeSyncIntervalMs);\n'
        r'  cmd.AddValue("forceRevokeVehicle0", "Force revoke vehicle0 0/1", g_forceRevokeVehicle0);\n'
        r'  cmd.AddValue("forceRevokeTime", "Force revoke time (s)", g_forceRevokeTime);\n',
        txt,
        count=1
    )
    if txt2 == txt:
        raise SystemExit("[ERR] Could not insert cmd.AddValue(...) after densityHigh. (densityHigh option not found)")
    txt = txt2

# 4) Schedule revocation in main after StartBlockchain schedule
if "RevocationMonitorTick" not in txt:
    raise SystemExit("[ERR] RevocationMonitorTick missing (unexpected).")

if "RevocationSyncTick" not in txt:
    raise SystemExit("[ERR] RevocationSyncTick missing (unexpected).")

if "IssueRevocation" not in txt:
    raise SystemExit("[ERR] IssueRevocation missing (unexpected).")

if "g_revokedVeh.assign" not in txt:
    # Insert after StartBlockchain schedule line
    txt2 = re.sub(
        r'(Simulator::Schedule\(Seconds\(0\.0\),\s*&StartBlockchain\);\s*)',
        r'\1\n'
        r'  // Revocation init + scheduling\n'
        r'  if (g_enableRevocation) {\n'
        r'    g_revokedVeh.assign(g_nVehicles, 0);\n'
        r'    g_revokeKnown.assign(all.GetN(), 0);\n'
        r'    g_revokeKnownTime.assign(all.GetN(), -1e9);\n'
        r'    Simulator::Schedule(Seconds(0.6), &RevocationMonitorTick);\n'
        r'    for (uint32_t i = 0; i < all.GetN(); i++)\n'
        r'      Simulator::Schedule(MilliSeconds(g_revokeSyncIntervalMs), &RevocationSyncTick, i);\n'
        r'    if (g_forceRevokeVehicle0)\n'
        r'      Simulator::Schedule(Seconds(g_forceRevokeTime), &IssueRevocation, 0, std::string("FORCED"));\n'
        r'  }\n',
        txt,
        count=1
    )
    if txt2 == txt:
        raise SystemExit("[ERR] Could not find StartBlockchain schedule line to attach revocation scheduling.")
    txt = txt2

p.write_text(txt)
print("[OK] Revocation module v1 patched into:", p)
