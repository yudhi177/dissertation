#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/blockchain/summary/blockchain_sweep_mean_std.csv")
OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/blockchain/plots")
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)

block_vals = sorted(df["blockIntervalMs"].unique())
mine_vals  = sorted(df["mineDelayMs"].unique())

def make_grid(col):
    grid = np.full((len(mine_vals), len(block_vals)), np.nan)
    for i, mine in enumerate(mine_vals):
        for j, block in enumerate(block_vals):
            sub = df[(df["mineDelayMs"] == mine) & (df["blockIntervalMs"] == block)]
            if len(sub) == 1:
                grid[i, j] = sub.iloc[0][col]
    return grid

def heatmap(grid, title, filename):
    plt.figure()
    plt.imshow(grid, aspect="auto")
    plt.colorbar()
    plt.xticks(range(len(block_vals)), block_vals)
    plt.yticks(range(len(mine_vals)), mine_vals)
    plt.xlabel("blockIntervalMs")
    plt.ylabel("mineDelayMs")
    plt.title(title)

    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                plt.text(j, i, f"{grid[i,j]:.3f}", ha="center", va="center", fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, filename)
    plt.savefig(out_path, dpi=200)
    plt.close()
    print("[OK]", out_path)

heatmap(make_grid("avgBlockLatency_s_mean"), "Avg Block Latency (s)", "block_latency_heatmap.png")
heatmap(make_grid("avgLedgerTrust_mean"), "Avg Ledger Trust", "ledger_trust_heatmap.png")
heatmap(make_grid("reportsCommitted_mean"), "Reports Committed", "reports_committed_heatmap.png")
heatmap(make_grid("pdr_norm_mean"), "PDR_norm", "pdr_norm_heatmap.png")
heatmap(make_grid("throughput_bps_mean"), "Throughput (bps)", "throughput_heatmap.png")
