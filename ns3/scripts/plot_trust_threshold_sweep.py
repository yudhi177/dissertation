#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/trust_threshold/summary/trust_threshold_mean_std.csv")
OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/trust_threshold/plots")
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)

fast_vals = sorted(df["trustFastThresh"].unique())
min_vals  = sorted(df["trustMinThresh"].unique())

def make_grid(value_col):
    grid = np.full((len(min_vals), len(fast_vals)), np.nan)
    for i, mn in enumerate(min_vals):
        for j, fast in enumerate(fast_vals):
            sub = df[(df["trustMinThresh"] == mn) & (df["trustFastThresh"] == fast)]
            if len(sub) == 1:
                grid[i, j] = sub.iloc[0][value_col]
    return grid

def heatmap(grid, title, filename, fmt="{:.3f}"):
    plt.figure()
    plt.imshow(grid, aspect="auto")
    plt.colorbar()
    plt.xticks(range(len(fast_vals)), fast_vals)
    plt.yticks(range(len(min_vals)), min_vals)
    plt.xlabel("trustFastThresh")
    plt.ylabel("trustMinThresh")
    plt.title(title)

    # annotate values
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                plt.text(j, i, fmt.format(grid[i, j]), ha="center", va="center", fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, filename)
    plt.savefig(out_path, dpi=200)
    plt.close()
    print("[OK]", out_path)

# Heatmaps
heatmap(make_grid("avgHandoverDelay_s_mean"), "Avg Handover Delay (s) - Mean", "handover_delay_heatmap.png", fmt="{:.3f}")
heatmap(make_grid("pdr_norm_mean"), "PDR_norm - Mean", "pdr_norm_heatmap.png", fmt="{:.3f}")
heatmap(make_grid("avgLedgerTrust_mean"), "Avg Ledger Trust - Mean", "ledger_trust_heatmap.png", fmt="{:.3f}")

# Auth distribution (stacked bar)
# Use total handovers as denominator for FAST/FULL; rejectCount as separate measure.
# We'll plot proportions FAST/FULL over handoverCount_mean, and show rejectCount_mean as separate bar overlay.
df2 = df.copy()
den = df2["handoverCount_mean"].replace(0, np.nan)
df2["fast_prop"] = df2["fastAuthCount_mean"] / den
df2["full_prop"] = df2["fullAuthCount_mean"] / den
df2["fast_prop"] = df2["fast_prop"].fillna(0.0)
df2["full_prop"] = df2["full_prop"].fillna(0.0)

# Create labels per combo
df2["combo"] = df2["trustFastThresh"].astype(str) + "/" + df2["trustMinThresh"].astype(str)
df2 = df2.sort_values(["trustFastThresh", "trustMinThresh"]).reset_index(drop=True)

x = np.arange(len(df2))
plt.figure()
plt.bar(x, df2["fast_prop"], label="FAST proportion")
plt.bar(x, df2["full_prop"], bottom=df2["fast_prop"], label="FULL proportion")
plt.xticks(x, df2["combo"], rotation=45, ha="right")
plt.ylabel("Proportion of handovers")
plt.title("Auth Mode Distribution (FAST vs FULL) per Threshold Combo")
plt.legend()
plt.tight_layout()
out_path = os.path.join(OUT_DIR, "auth_mode_distribution.png")
plt.savefig(out_path, dpi=200)
plt.close()
print("[OK]", out_path)

# Reject count plot (mean)
plt.figure()
plt.bar(x, df2["rejectCount_mean"])
plt.xticks(x, df2["combo"], rotation=45, ha="right")
plt.ylabel("Reject count (mean)")
plt.title("Reject Count per Threshold Combo")
plt.tight_layout()
out_path = os.path.join(OUT_DIR, "reject_count_by_threshold.png")
plt.savefig(out_path, dpi=200)
plt.close()
print("[OK]", out_path)
