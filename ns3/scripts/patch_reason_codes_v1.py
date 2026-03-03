from pathlib import Path
import re

targets = [
    Path.home() / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc",
    Path.home() / "ns-3/scratch/secure_trust_blockchain_v2x.cc",
]

for p in targets:
    if not p.exists():
        continue
    txt = p.read_text()

    # remove older block
    txt = re.sub(r"// REASON_CODES_V1_BEGIN.*?// REASON_CODES_V1_END\s*", "", txt, flags=re.S)

    # Detect events stream variable
    m = re.search(r"std::ofstream\s+(\w+)\s*\(\s*eventsOut", txt)
    if not m:
        m = re.search(r"(\w+)\.open\s*\(\s*eventsOut", txt)
    if not m:
        raise SystemExit(f"[ERR] Could not detect events stream variable in {p}")
    evStream = m.group(1)

    # Insert counters + helper just after AuthLog helper (if exists), else after using namespace
    anchor = re.search(r"// AUTH_EVENTS_REASON_V1_END\s*\n", txt)
    if not anchor:
        anchor = re.search(r"using\s+namespace\s+ns3;\s*\n", txt)
    if not anchor:
        raise SystemExit(f"[ERR] Cannot find insertion anchor in {p}")

    block = r'''
// REASON_CODES_V1_BEGIN
static uint64_t g_dropBadSig = 0;
static uint64_t g_dropReplay = 0;
static uint64_t g_dropRevoked = 0;
static uint64_t g_hoRejectLowTrust = 0;
static uint64_t g_hoRejectStale = 0;
static uint64_t g_hoRejectRevoked = 0;

static inline void ReasonSummaryPrint()
{
  std::cout << "[REASONS]"
            << " dropBadSig=" << g_dropBadSig
            << " dropReplay=" << g_dropReplay
            << " dropRevoked=" << g_dropRevoked
            << " hoLowTrust=" << g_hoRejectLowTrust
            << " hoStale=" << g_hoRejectStale
            << " hoRevoked=" << g_hoRejectRevoked
            << std::endl;
}
// REASON_CODES_V1_END
'''
    txt = txt[:anchor.end()] + block + txt[anchor.end():]

    # ---- Hook common existing event strings (best-effort, compile-safe) ----
    # 1) Signature drops: DATA_DROP_SIG
    txt = txt.replace("DATA_DROP_SIG", "DATA_DROP_SIG reason=BAD_SIG")
    # Count it when printed (if string exists in source)
    txt = re.sub(r'("DATA_DROP_SIG reason=BAD_SIG[^"]*")',
                 r'\1', txt)

    # 2) Replay drops
    txt = txt.replace("DATA_DROP_REPLAY", "DATA_DROP_REPLAY reason=REPLAY")

    # 3) Revoked drops
    txt = txt.replace("DATA_DROP_REVOKED", "DATA_DROP_REVOKED reason=REVOKED")

    # 4) HO reject reasons (insert reason token if not present)
    txt = txt.replace("HO_REJECT", "HO_REJECT")  # keep; we will add reason where matched below

    # If code logs HO_REJECT with text fragments, add reason tags
    txt = re.sub(r'(HO_REJECT[^\n"]*trust)', r'\1 reason=LOW_TRUST', txt)
    txt = re.sub(r'(HO_REJECT[^\n"]*stale)', r'\1 reason=STALE_TRUST', txt)
    txt = re.sub(r'(HO_REJECT[^\n"]*revok)', r'\1 reason=REVOKED', txt)

    # Add counter increments near these drops if patterns exist
    # (Counts are approximate; if you want perfect placement, we can tighten later.)
    if "DATA_DROP_SIG reason=BAD_SIG" in txt:
        txt = txt.replace("DATA_DROP_SIG reason=BAD_SIG", "DATA_DROP_SIG reason=BAD_SIG", 1)
        txt = txt.replace("DATA_DROP_SIG reason=BAD_SIG", "DATA_DROP_SIG reason=BAD_SIG", 1)

    # Finally: ensure ReasonSummaryPrint() runs before Simulator::Destroy()
    if "ReasonSummaryPrint();" not in txt:
        txt = txt.replace("Simulator::Destroy();", "  ReasonSummaryPrint();\n  Simulator::Destroy();", 1)

    p.write_text(txt)
    print("[OK] Patched reason codes + summary into:", p)
