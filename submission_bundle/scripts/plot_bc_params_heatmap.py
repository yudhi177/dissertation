import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/bc_params_heatmap")
SUM  = os.path.join(BASE, "summary")
PLOTS= os.path.join(BASE, "plots")
os.makedirs(PLOTS, exist_ok=True)

csv = os.path.join(SUM, "bc_params_mean_std.csv")
df = pd.read_csv(csv)

# choose a clean slice for the paper: max density, mid speed
nveh = df["nVehicles"].max()
spds = sorted(df["speedTag"].unique())
spd  = spds[len(spds)//2] if spds else df["speedTag"].iloc[0]

sub = df[(df["nVehicles"]==nveh) & (df["speedTag"]==spd)].copy()
if sub.empty:
    sub = df.copy()

def heat(metric_mean, title, outname):
    if metric_mean not in sub.columns:
        print("[SKIP] missing", metric_mean)
        return

    piv = sub.pivot_table(index="mineDelayMs", columns="blockIntervalMs", values=metric_mean, aggfunc="mean")
    xs = list(piv.columns)
    ys = list(piv.index)
    Z  = piv.values

    plt.figure()
    plt.imshow(Z, aspect="auto", origin="lower")
    plt.title(f"{title}\n(slice: nVehicles={nveh}, speed={spd})")
    plt.xlabel("blockIntervalMs")
    plt.ylabel("mineDelayMs")
    plt.xticks(range(len(xs)), [str(x) for x in xs])
    plt.yticks(range(len(ys)), [str(y) for y in ys])
    plt.colorbar()
    plt.tight_layout()
    path = os.path.join(PLOTS, outname)
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

heat("avgBlockLatency_s_mean", "Blockchain Params Heatmap: Avg Block Latency (s)", "bcparam_heat_blockLatency.png")
heat("reportsCommitted_mean",  "Blockchain Params Heatmap: Reports Committed",     "bcparam_heat_reportsCommitted.png")
heat("pdr_norm_mean",          "Blockchain Params Heatmap: Normalized PDR",       "bcparam_heat_pdr_norm.png")
heat("malReject_mean",         "Blockchain Params Heatmap: Malicious Rejects",    "bcparam_heat_malReject.png")
heat("honReject_mean",         "Blockchain Params Heatmap: Honest Rejects",       "bcparam_heat_honReject.png")
heat("avgLedgerTrust_mean",    "Blockchain Params Heatmap: Avg Ledger Trust",     "bcparam_heat_ledgerTrust.png")

print("[DONE] plots in", PLOTS)
