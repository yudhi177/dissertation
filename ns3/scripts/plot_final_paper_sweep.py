import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/final_paper_sweep")
IN_CSV = os.path.join(BASE, "summary", "final_sweep_mean_std.csv")
PLOTS = os.path.join(BASE, "plots")
TABLES = os.path.join(BASE, "tables")
os.makedirs(PLOTS, exist_ok=True)
os.makedirs(TABLES, exist_ok=True)

df = pd.read_csv(IN_CSV)

# ---------- column auto-detect ----------
def find_group_col(key: str):
    """
    Find a non-metric column for a grouping key.
    Example: trustFastThresh might be stored as trustFastThresh_cfg
    """
    # exact match
    if key in df.columns:
        return key
    # common variants
    candidates = [c for c in df.columns if c.lower() == key.lower()]
    if candidates:
        return candidates[0]
    # prefix match but not metrics
    candidates = []
    for c in df.columns:
        cl = c.lower()
        if key.lower() in cl and not (cl.endswith("_mean") or cl.endswith("_std")):
            candidates.append(c)
    if candidates:
        # prefer shortest name
        candidates.sort(key=len)
        return candidates[0]
    return None

def require_col(colname, label):
    if colname is None:
        raise KeyError(f"Missing required column for '{label}'. Available columns: {list(df.columns)[:25]} ...")
    return colname

def pick_metric(prefix: str, stat: str):
    c = f"{prefix}_{stat}"
    if c not in df.columns:
        raise KeyError(f"Missing metric column: {c}")
    return c

# detect group columns
COL_NVEH = require_col(find_group_col("nVehicles"), "nVehicles")
COL_SPD  = require_col(find_group_col("speedTag"), "speedTag")
COL_MAL  = require_col(find_group_col("maliciousRate"), "maliciousRate")
COL_TF   = find_group_col("trustFastThresh")   # optional (needed for threshold heatmaps)
COL_TM   = find_group_col("trustMinThresh")    # optional (needed for threshold heatmaps)

# cast to numeric
for c in [COL_NVEH, COL_SPD, COL_MAL, COL_TF, COL_TM]:
    if c and c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# ---------- plot helpers ----------
def savefig(path):
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

def near(series, val, tol=1e-9):
    return (series - val).abs() <= tol

# choose default thresholds slice (if thresholds exist)
DEFAULT_TF = 0.7
DEFAULT_TM = 0.3

if COL_TF and COL_TM:
    base_line = df[ near(df[COL_TF], DEFAULT_TF) & near(df[COL_TM], DEFAULT_TM) ].copy()
    if base_line.empty:
        tf_mode = df[COL_TF].mode().iloc[0]
        tm_mode = df[COL_TM].mode().iloc[0]
        DEFAULT_TF, DEFAULT_TM = float(tf_mode), float(tm_mode)
        base_line = df[ near(df[COL_TF], DEFAULT_TF) & near(df[COL_TM], DEFAULT_TM) ].copy()
else:
    # if thresholds not present, just use whole dataframe for line plots
    base_line = df.copy()

# ========== 1) Line plots vs maliciousRate (per nVehicles) ==========
def lineplot_vs_mal(metric, ylabel, fname):
    m_mean = pick_metric(metric, "mean")
    m_std  = f"{metric}_std" if f"{metric}_std" in base_line.columns else None

    for nveh in sorted(base_line[COL_NVEH].dropna().unique()):
        subN = base_line[base_line[COL_NVEH] == nveh].copy()
        if subN.empty:
            continue

        plt.figure()
        for spd in sorted(subN[COL_SPD].dropna().unique()):
            s = subN[subN[COL_SPD] == spd].sort_values(COL_MAL)
            x = s[COL_MAL].to_numpy()
            y = s[m_mean].to_numpy()
            yerr = s[m_std].to_numpy() if m_std else None
            plt.errorbar(x, y, yerr=yerr, marker="o", label=f"speed={spd}")

        plt.xlabel("Malicious rate")
        plt.ylabel(ylabel)
        if COL_TF and COL_TM:
            plt.title(f"{metric} vs maliciousRate  (nVehicles={int(nveh)}, tf={DEFAULT_TF}, tm={DEFAULT_TM})")
        else:
            plt.title(f"{metric} vs maliciousRate  (nVehicles={int(nveh)})")
        plt.grid(True, alpha=0.3)
        plt.legend()
        savefig(os.path.join(PLOTS, f"{fname}_nveh_{int(nveh)}.png"))

lineplot_vs_mal("pdr_norm", "Normalized PDR", "pdr_norm_vs_maliciousRate")
lineplot_vs_mal("avgDelay_s", "Average delay (s)", "delay_vs_maliciousRate")
lineplot_vs_mal("throughput_bps", "Throughput (bps)", "throughput_vs_maliciousRate")

if "avgLedgerTrust_mean" in base_line.columns:
    lineplot_vs_mal("avgLedgerTrust", "Average ledger trust", "ledgerTrust_vs_maliciousRate")
if "handoverCount_mean" in base_line.columns:
    lineplot_vs_mal("handoverCount", "Handover count", "handoverCount_vs_maliciousRate")
if "rejectCount_mean" in base_line.columns:
    lineplot_vs_mal("rejectCount", "Reject count", "rejectCount_vs_maliciousRate")

# ========== 2) Heatmaps for trust thresholds (only if threshold columns exist) ==========
if COL_TF and COL_TM:
    REP_NVEH = sorted(df[COL_NVEH].dropna().unique())[len(df[COL_NVEH].dropna().unique())//2]
    REP_SPD  = sorted(df[COL_SPD].dropna().unique())[len(df[COL_SPD].dropna().unique())//2]
    REP_MAL  = sorted(df[COL_MAL].dropna().unique())[min(1, len(df[COL_MAL].dropna().unique())-1)]

    rep = df[(df[COL_NVEH] == REP_NVEH) & (df[COL_SPD] == REP_SPD) & (df[COL_MAL] == REP_MAL)].copy()

    def heatmap(metric, title, fname):
        m_mean = pick_metric(metric, "mean")
        piv = rep.pivot_table(index=COL_TM, columns=COL_TF, values=m_mean, aggfunc="mean")
        if piv.empty:
            print("[WARN] heatmap empty for", metric)
            return

        x = piv.columns.to_numpy()
        y = piv.index.to_numpy()
        Z = piv.to_numpy()

        plt.figure()
        plt.imshow(Z, aspect="auto", origin="lower")
        plt.colorbar()
        plt.xticks(ticks=np.arange(len(x)), labels=[str(v) for v in x])
        plt.yticks(ticks=np.arange(len(y)), labels=[str(v) for v in y])
        plt.xlabel("trustFastThresh")
        plt.ylabel("trustMinThresh")
        plt.title(f"{title}\n(nVehicles={int(REP_NVEH)}, speed={REP_SPD}, maliciousRate={REP_MAL})")
        savefig(os.path.join(PLOTS, fname))

    heatmap("pdr_norm", "Normalized PDR heatmap", "heatmap_pdr_norm_thresholds.png")
    if "handoverCount_mean" in rep.columns:
        heatmap("handoverCount", "Handover count heatmap", "heatmap_handoverCount_thresholds.png")
    if "rejectCount_mean" in rep.columns:
        heatmap("rejectCount", "Reject count heatmap", "heatmap_rejectCount_thresholds.png")
    if "avgLedgerTrust_mean" in rep.columns:
        heatmap("avgLedgerTrust", "Average ledger trust heatmap", "heatmap_ledgerTrust_thresholds.png")
else:
    print("[WARN] Threshold columns not found; skipping threshold heatmaps.")

# ========== 3) Paper table ==========
# If thresholds exist, table is for baseline tf/tm slice. Else, table is whole df.
cols_keep = [
    COL_NVEH, COL_SPD, COL_MAL,
    COL_TF if COL_TF else None,
    COL_TM if COL_TM else None,
    "pdr_norm_mean", "pdr_norm_std",
    "avgDelay_s_mean", "avgDelay_s_std",
    "throughput_bps_mean", "throughput_bps_std",
]
for optional in ["handoverCount_mean","handoverCount_std","avgLedgerTrust_mean","avgLedgerTrust_std","rejectCount_mean","rejectCount_std"]:
    if optional in df.columns:
        cols_keep.append(optional)
cols_keep = [c for c in cols_keep if c is not None and c in df.columns]

paper_table = base_line[cols_keep].copy()
paper_table = paper_table.sort_values([COL_NVEH, COL_SPD, COL_MAL])
paper_table.to_csv(os.path.join(TABLES, "paper_table_default_thresholds.csv"), index=False)
print("[OK]", os.path.join(TABLES, "paper_table_default_thresholds.csv"))

print("[DONE] Plots in:", PLOTS)
