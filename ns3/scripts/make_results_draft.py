import os
import pandas as pd

BASE = os.path.expanduser("~/dissertation/final_outputs/results_pack")
SUMO = os.path.join(BASE, "sumo_pipeline_mean_std.csv")
SWEEP = os.path.join(BASE, "final_sweep_mean_std.csv")
TABLE = os.path.join(BASE, "paper_table_default_thresholds.csv")

OUT_TXT = os.path.join(BASE, "RESULTS_DRAFT.txt")

def safe_read(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

sumo = safe_read(SUMO)
sweep = safe_read(SWEEP)
tab = safe_read(TABLE)

lines = []
lines.append("=== RESULTS DRAFT (AUTO-GENERATED) ===\n")

# -------------------------------------------------------
# 1) Density + Speed (SUMO pipeline)
# -------------------------------------------------------
if sumo is not None and not sumo.empty:
    lines.append("## 1. SUMO Mobility: Impact of Vehicle Density and Speed\n")
    lines.append(
        "We evaluate the integrated secure trust + blockchain V2X model under SUMO-generated mobility. "
        "Vehicle density is varied across {dens} and speed across {spds}, with 5 random seeds per condition.\n"
        .format(
            dens=sorted(sumo["nVehicles"].unique().tolist()),
            spds=sorted(sumo["speedTag"].unique().tolist())
        )
    )

    # Key trends
    def get_val(nveh, spd, col):
        r = sumo[(sumo["nVehicles"]==nveh) & (sumo["speedTag"]==spd)]
        if r.empty: return None
        return float(r.iloc[0][col])

    nveh_low = sorted(sumo["nVehicles"].unique())[0]
    nveh_high = sorted(sumo["nVehicles"].unique())[-1]
    spd_mid = sorted(sumo["speedTag"].unique())[len(sorted(sumo["speedTag"].unique()))//2]

    pdr_low = get_val(nveh_low, spd_mid, "pdr_norm_mean")
    pdr_high = get_val(nveh_high, spd_mid, "pdr_norm_mean")
    dly_low = get_val(nveh_low, spd_mid, "avgDelay_s_mean")
    dly_high = get_val(nveh_high, spd_mid, "avgDelay_s_mean")
    thr_low = get_val(nveh_low, spd_mid, "throughput_bps_mean")
    thr_high = get_val(nveh_high, spd_mid, "throughput_bps_mean")
    ho_low = get_val(nveh_low, spd_mid, "handoverCount_mean") if "handoverCount_mean" in sumo.columns else None
    ho_high = get_val(nveh_high, spd_mid, "handoverCount_mean") if "handoverCount_mean" in sumo.columns else None

    lines.append("### Key observations (density sweep)\n")
    if pdr_low is not None and pdr_high is not None:
        lines.append(f"- Normalized PDR remains in the same range across density (example at speed={spd_mid}: "
                     f"{nveh_low} vehicles → {pdr_low:.3f}, {nveh_high} vehicles → {pdr_high:.3f}).\n")
    if dly_low is not None and dly_high is not None:
        lines.append(f"- Average delay stays low and stable (speed={spd_mid}: "
                     f"{nveh_low} → {dly_low:.6f}s, {nveh_high} → {dly_high:.6f}s).\n")
    if thr_low is not None and thr_high is not None:
        lines.append(f"- Throughput scales with network load (speed={spd_mid}: "
                     f"{nveh_low} → {thr_low:.1f} bps, {nveh_high} → {thr_high:.1f} bps).\n")
    if ho_low is not None and ho_high is not None:
        lines.append(f"- Handover activity increases with mobility interactions when RSU coverage overlaps the road network "
                     f"(speed={spd_mid}: {nveh_low} → {ho_low:.2f}, {nveh_high} → {ho_high:.2f}).\n")

    lines.append("\n### Figures (density-speed set)\n")
    lines.append("- Fig: pdr_norm_vs_density_speed.png — Normalized PDR vs density (line per speed).\n")
    lines.append("- Fig: delay_vs_density_speed.png — Delay vs density (line per speed).\n")
    lines.append("- Fig: throughput_vs_density_speed.png — Throughput vs density (line per speed).\n")
    lines.append("- Fig: handover_count_vs_density_speed.png — Handover count vs density (line per speed).\n")
    lines.append("- Fig: handover_delay_vs_density_speed.png — Handover delay vs density (line per speed).\n")
    lines.append("- Fig: ledger_trust_vs_density_speed.png — Average ledger trust vs density (line per speed).\n\n")

# -------------------------------------------------------
# 2) Malicious rate + thresholds (Final sweep)
# -------------------------------------------------------
if sweep is not None and not sweep.empty:
    lines.append("## 2. Security Stress Tests: Malicious Rate and Trust Threshold Trade-offs\n")
    cols = sweep.columns.tolist()

    # detect grouping column names
    def findcol(name):
        if name in cols: return name
        cands = [c for c in cols if name.lower() in c.lower() and not (c.lower().endswith("_mean") or c.lower().endswith("_std"))]
        return sorted(cands, key=len)[0] if cands else None

    c_mal = findcol("maliciousRate")
    c_tf  = findcol("trustFastThresh")
    c_tm  = findcol("trustMinThresh")
    c_nv  = findcol("nVehicles") or "nVehicles"
    c_sp  = findcol("speedTag") or "speedTag"

    lines.append(
        f"We sweep maliciousRate ({sorted(sweep[c_mal].unique().tolist()) if c_mal else 'N/A'}) and trust thresholds "
        f"(fast={sorted(sweep[c_tf].unique().tolist()) if c_tf else 'N/A'}, min={sorted(sweep[c_tm].unique().tolist()) if c_tm else 'N/A'}) "
        "to quantify the trade-off between availability (FAST authentication) and security (rejecting low-trust nodes).\n"
    )

    lines.append("\n### Figures (final sweep set)\n")
    lines.append("- Fig: pdr_norm_vs_maliciousRate_nveh_*.png — PDR vs malicious rate (per density; lines by speed).\n")
    lines.append("- Fig: delay_vs_maliciousRate_nveh_*.png — Delay vs malicious rate.\n")
    lines.append("- Fig: throughput_vs_maliciousRate_nveh_*.png — Throughput vs malicious rate.\n")
    lines.append("- Fig: ledgerTrust_vs_maliciousRate_nveh_*.png — Ledger trust vs malicious rate (if enabled).\n")
    lines.append("- Fig: heatmap_pdr_norm_thresholds.png — Threshold trade-off heatmap.\n")
    lines.append("- Fig: heatmap_rejectCount_thresholds.png — Rejection behavior vs thresholds.\n\n")

# -------------------------------------------------------
# 3) Table caption
# -------------------------------------------------------
if tab is not None and not tab.empty:
    lines.append("## 3. Summary Table\n")
    lines.append("Table: paper_table_default_thresholds.csv — Mean ± std across 5 seeds under baseline thresholds "
                 "for each (density, speed, maliciousRate) condition.\n\n")

with open(OUT_TXT, "w") as f:
    f.write("\n".join(lines))

print("[OK] Wrote:", OUT_TXT)
