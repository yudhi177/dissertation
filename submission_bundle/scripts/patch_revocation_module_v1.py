from pathlib import Path
import re

p = Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc"
txt = p.read_text()

# Remove old revocation block if exists
txt = re.sub(r"// REVOCATION_MODULE_V1_BEGIN.*?// REVOCATION_MODULE_V1_END\s*", "", txt, flags=re.S)

# ---------- Insert globals before METRICS section ----------
marker_metrics = "/* =========================================================\n   METRICS / STATE"
k = txt.find(marker_metrics)
if k == -1:
    raise SystemExit("[ERR] Could not find METRICS / STATE marker")

rev_globals = r'''
// REVOCATION_MODULE_V1_BEGIN
/* =========================================================
   REVOCATION (v1)
   - Minimal on-chain model (simulated): revocation flag
   - Vehicles learn revocation via periodic "sync" (blockchain sync interval)
   - Measures propagation delay: REVOKE_ISSUE -> REVOKE_APPLY per node
========================================================= */
static bool     g_enableRevocation = true;
static double   g_revokeTrustThresh = 0.20;         // trust below => revoke
static uint32_t g_revokeSyncIntervalMs = 1000;      // how often nodes sync revocation list
static bool     g_forceRevokeVehicle0 = false;      // for controlled measurement
static double   g_forceRevokeTime = 2.0;            // seconds

// Revocation state (we track vehicle IDs; keep privacy OFF in revocation experiments)
static std::vector<uint8_t> g_revokedVeh;           // size nVehicles
static std::vector<uint8_t> g_revokeKnown;          // size all nodes (vehicles+rsu)
static std::vector<double>  g_revokeKnownTime;      // seconds
static double   g_revokeIssueTime = -1e9;

// Revocation metrics
static uint64_t g_revocationsIssued = 0;
static uint64_t g_revocationsApplied = 0;
static uint64_t g_revokeDrops = 0;
static double   g_revPropDelayMax = 0.0;
static double   g_revPropDelaySum = 0.0;

// Log + apply
static void IssueRevocation(uint32_t accused, const std::string& reason)
{
  if (!g_enableRevocation) return;
  if (accused >= g_revokedVeh.size()) return;
  if (g_revokedVeh[accused]) return;

  g_revokedVeh[accused] = 1;
  g_revocationsIssued++;

  if (accused == 0 && g_revokeIssueTime < -1e8)
    g_revokeIssueTime = ns3::Simulator::Now().GetSeconds();

  LogEvent("REVOKE_ISSUE accused=" + std::to_string(accused) + " reason=" + reason);
}

// Periodic "sync" from blockchain: nodes learn revocation list
static void RevocationSyncTick(uint32_t nodeId)
{
  if (!g_enableRevocation) return;
  if (nodeId >= g_revokeKnown.size()) return;

  // For now, measure propagation of attacker0 revocation (accused=0)
  uint32_t accused = 0;
  if (accused < g_revokedVeh.size() && g_revokedVeh[accused] && !g_revokeKnown[nodeId])
  {
    g_revokeKnown[nodeId] = 1;
    double now = ns3::Simulator::Now().GetSeconds();
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

  ns3::Simulator::Schedule(ns3::MilliSeconds(g_revokeSyncIntervalMs),
                           &RevocationSyncTick, nodeId);
}

// Monitor trust -> revoke when below threshold (works with Trust Engine FINAL)
static void RevocationMonitorTick()
{
  if (!g_enableRevocation) return;
  for (uint32_t v = 0; v < g_nVehicles; v++)
  {
    if (v < g_ledgerTrust.size() && !g_revokedVeh[v] && g_ledgerTrust[v] < g_revokeTrustThresh)
    {
      IssueRevocation(v, "TRUST_BELOW_THRESH");
    }
  }
  ns3::Simulator::Schedule(ns3::Seconds(0.5), &RevocationMonitorTick);
}
// REVOCATION_MODULE_V1_END

'''
txt = txt[:k] + rev_globals + txt[k:]

# ---------- Insert DATA_DROP_REVOKED check before g_rxData++ ----------
if "DATA_DROP_REVOKED" not in txt:
    txt = re.sub(
        r'\n(\s*)g_rxData\+\+;',
        r'\n\1// Revocation drop (vehicle-id based; keep privacy OFF for revoke experiments)\n'
        r'\1if (g_enableRevocation) {\n'
        r'\1  uint32_t sid = hdr.senderId;\n'
        r'\1  if (sid < g_revokedVeh.size() && g_revokedVeh[sid]) {\n'
        r'\1    g_revokeDrops++;\n'
        r'\1    LogEvent("DATA_DROP_REVOKED rx=" + std::to_string(receiverId) + " sender=" + std::to_string(sid));\n'
        r'\1    return;\n'
        r'\1  }\n'
        r'\1}\n'
        r'\n\1g_rxData++;',
        txt,
        count=1
    )

# ---------- Add CommandLine options (after trust engine args) ----------
if 'cmd.AddValue("enableRevocation"' not in txt:
    txt = re.sub(
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

# ---------- Schedule revocation in main (after blockchain start schedule) ----------
if "RevocationMonitorTick" not in txt:
    raise SystemExit("[ERR] RevocationMonitorTick missing after insertion (unexpected).")

if "REVOKE_ISSUE" not in txt:
    raise SystemExit("[ERR] Revocation events not present (unexpected).")

# Add scheduling block once
if "Simulator::Schedule(Seconds(0.6), &RevocationMonitorTick);" not in txt:
    txt = re.sub(
        r'(Simulator::Schedule\(Seconds\(0\.0\),\s*&StartBlockchain\);\s*)',
        r'\1\n'
        r'  // Revocation scheduling\n'
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

p.write_text(txt)
print("[OK] Revocation module v1 patched:", p)
