#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV  = os.path.expanduser("~/dissertation/ns3/results/scalability/summary/scalability_mean_std.csv")
OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/scalability/plots")
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)
x = df["nVehicles"]

def errplot(y_mean, y_std, ylabel, title, filename):
    plt.figure()
    plt.errorbar(x, df[y_mean], yerr=df[y_std], fmt='-o', capsize=4)
    plt.xlabel("Number of vehicles")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, filename)
    plt.savefig(out_path, dpi=200)
    plt.close()
    print("[OK]", out_path)

errplot("pdr_norm_mean", "pdr_norm_std",
        "PDR (normalized)", "PDR_norm vs Vehicle Count",
        "pdr_norm_vs_vehicles.png")

errplot("avgDelay_s_mean", "avgDelay_s_std",
        "Average delay (s)", "Average Delay vs Vehicle Count",
        "delay_vs_vehicles.png")

errplot("throughput_bps_mean", "throughput_bps_std",
        "Throughput (bps)", "Throughput vs Vehicle Count",
        "throughput_vs_vehicles.png")

errplot("avgLedgerTrust_mean", "avgLedgerTrust_std",
        "Average ledger trust", "Ledger Trust vs Vehicle Count",
        "ledger_trust_vs_vehicles.png")

errplot("avgHandoverDelay_s_mean", "avgHandoverDelay_s_std",
        "Average handover delay (s)", "Handover Delay vs Vehicle Count",
        "handover_delay_vs_vehicles.png")

errplot("avgBlockLatency_s_mean", "avgBlockLatency_s_std",
        "Average block latency (s)", "Block Latency vs Vehicle Count",
        "block_latency_vs_vehicles.png")
