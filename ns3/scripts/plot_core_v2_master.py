import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/core_v2_master")
SUM  = os.path.join(BASE, "summary")
PLOTS = os.path.join(BASE, "plots")
os.makedirs(PLOTS, exist_ok=True)

def must(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

def savefig(path):
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    print("[OK]", path)

def line_by_speed(df, xcol, ycol, yerrcol, title, xlabel, ylabel, outname):
    plt.figure()
    for spd in sorted(df["tag_speedTag"].unique()):
        sub = df[df["tag_speedTag"] == spd].sort_values(xcol)
        yerr = sub[yerrcol] if (yerrcol in sub.columns) else None
        plt.errorbar(sub[xcol], sub[ycol], yerr=yerr, marker="o", label=f"speed={spd}")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    savefig(os.path.join(PLOTS, outname))

def bar_attackmode(df, metric_mean, metric_std, title, ylabel, outname):
    # aggregate across nVehicles + speed to one value per mode (mean of means)
    modes = sorted(df["tag_attackMode"].unique())
    vals=[]
    errs=[]
    for m in modes:
        sub = df[df["tag_attackMode"]==m]
        vals.append(sub[metric_mean].mean())
        errs.append(sub[metric_std].mean() if metric_std in sub.columns else 0.0)

    plt.figure()
    plt.bar([str(m) for m in modes], vals, yerr=errs)
    plt.title(title)
    plt.xlabel("attackMode (0 none, 1 replay, 2 sig, 3 sybil)")
    plt.ylabel(ylabel)
    savefig(os.path.join(PLOTS, outname))

def heatmap_thresh(df, value_col, title, outname):
    # pick one (nVehicles,speed) slice for clear heatmap:
    # choose max nVehicles and mid speed if present
    nveh = df["tag_nVehicles"].max()
    spds = sorted(df["tag_speedTag"].unique())
    spd = spds[len(spds)//2] if spds else df["tag_speedTag"].iloc[0]

    sub = df[(df["tag_nVehicles"]==nveh) & (df["tag_speedTag"]==spd)].copy()
    if sub.empty:
        # fallback to first slice
        sub = df.copy()

    # pivot
    pivot = sub.pivot_table(index="tag_trustMinThresh", columns="tag_trustFastThresh", values=value_col, aggfunc="mean")
    xs = list(pivot.columns)
    ys = list(pivot.index)
    Z  = pivot.values

    plt.figure()
    plt.imshow(Z, aspect="auto", origin="lower")
    plt.title(f"{title}\n(slice: nVehicles={nveh}, speed={spd})")
    plt.xlabel("trustFastThresh")
    plt.ylabel("trustMinThresh")
    plt.xticks(range(len(xs)), [str(x) for x in xs])
    plt.yticks(range(len(ys)), [str(y) for y in ys])
    plt.colorbar()
    savefig(os.path.join(PLOTS, outname))

# -------------------- 1) AttackMode plots --------------------
attack_path = os.path.join(SUM, "attackmode_mean_std.csv")
must(attack_path)
A = pd.read_csv(attack_path)

# Ensure required columns exist
for col in ["tag_attackMode","tag_speedTag","tag_nVehicles"]:
    if col not in A.columns:
        raise RuntimeError(f"Missing {col} in {attack_path}")

# main metrics
bar_attackmode(A, "pdr_norm_mean", "pdr_norm_std", "AttackMode vs Normalized PDR", "pdr_norm", "attackmode_pdr_norm.png")
bar_attackmode(A, "sigDrops_mean", "sigDrops_std", "AttackMode vs Signature Drops", "sigDrops", "attackmode_sigDrops.png")
bar_attackmode(A, "replayDrops_mean", "replayDrops_std", "AttackMode vs Replay Drops", "replayDrops", "attackmode_replayDrops.png")
bar_attackmode(A, "reportsCommitted_mean", "reportsCommitted_std", "AttackMode vs Reports Committed", "reportsCommitted", "attackmode_reportsCommitted.png")
bar_attackmode(A, "malReject_mean", "malReject_std", "AttackMode vs Malicious Rejections", "malReject", "attackmode_malReject.png")
bar_attackmode(A, "honReject_mean", "honReject_std", "AttackMode vs Honest Rejections", "honReject", "attackmode_honReject.png")

# -------------------- 2) MaliciousRate sweep plots --------------------
mal_path = os.path.join(SUM, "malsweep_mean_std.csv")
must(mal_path)
M = pd.read_csv(mal_path)

for col in ["tag_maliciousRate","tag_speedTag","tag_nVehicles"]:
    if col not in M.columns:
        raise RuntimeError(f"Missing {col} in {mal_path}")

line_by_speed(M, "tag_maliciousRate", "pdr_norm_mean", "pdr_norm_std",
              "MaliciousRate sweep: Normalized PDR", "maliciousRate", "pdr_norm",
              "malsweep_pdr_norm.png")

line_by_speed(M, "tag_maliciousRate", "avgLedgerTrust_mean", "avgLedgerTrust_std",
              "MaliciousRate sweep: Avg Ledger Trust", "maliciousRate", "avgLedgerTrust",
              "malsweep_avgLedgerTrust.png")

line_by_speed(M, "tag_maliciousRate", "malReject_mean", "malReject_std",
              "MaliciousRate sweep: Malicious Rejects", "maliciousRate", "malReject",
              "malsweep_malReject.png")

line_by_speed(M, "tag_maliciousRate", "honReject_mean", "honReject_std",
              "MaliciousRate sweep: Honest Rejects (False Positives)", "maliciousRate", "honReject",
              "malsweep_honReject.png")

# -------------------- 3) Threshold heatmaps --------------------
thr_path = os.path.join(SUM, "thresh_mean_std.csv")
must(thr_path)
T = pd.read_csv(thr_path)

for col in ["tag_trustFastThresh","tag_trustMinThresh","tag_speedTag","tag_nVehicles"]:
    if col not in T.columns:
        raise RuntimeError(f"Missing {col} in {thr_path}")

heatmap_thresh(T, "pdr_norm_mean", "Threshold Heatmap: Normalized PDR", "thresh_heatmap_pdr_norm.png")
heatmap_thresh(T, "malReject_mean", "Threshold Heatmap: Malicious Rejects", "thresh_heatmap_malReject.png")
heatmap_thresh(T, "honReject_mean", "Threshold Heatmap: Honest Rejects", "thresh_heatmap_honReject.png")

print("[DONE] Plots in:", PLOTS)
