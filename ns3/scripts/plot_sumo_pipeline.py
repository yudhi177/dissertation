#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

IN_CSV = Path.home() / "dissertation/ns3/results/sumo_pipeline/summary/sumo_pipeline_mean_std.csv"
OUTDIR = Path.home() / "dissertation/ns3/results/sumo_pipeline/plots"
OUTDIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(IN_CSV)

def plot_metric(metric, ylabel, outname):
    plt.figure()
    for spd in sorted(df["speedTag"].unique()):
        sub = df[df["speedTag"] == spd].sort_values("nVehicles")
        plt.errorbar(sub["nVehicles"], sub[f"{metric}_mean"], yerr=sub.get(f"{metric}_std", None), marker="o", label=f"speedTag={spd}")
    plt.xlabel("Vehicles")
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True, alpha=0.3)
    out = OUTDIR / outname
    plt.savefig(out, dpi=200, bbox_inches="tight")
    print("[OK]", out)

plot_metric("pdr_norm", "Normalized PDR", "pdr_norm_vs_density_speed.png")
plot_metric("avgDelay_s", "Avg Delay (s)", "delay_vs_density_speed.png")
plot_metric("throughput_bps", "Throughput (bps)", "throughput_vs_density_speed.png")
plot_metric("handoverCount", "Handover Count", "handover_count_vs_density_speed.png")
plot_metric("avgHandoverDelay_s", "Avg Handover Delay (s)", "handover_delay_vs_density_speed.png")
plot_metric("avgLedgerTrust", "Avg Ledger Trust", "ledger_trust_vs_density_speed.png")
