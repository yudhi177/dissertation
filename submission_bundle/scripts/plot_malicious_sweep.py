#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV  = os.path.expanduser("~/dissertation/ns3/results/sensitivity/malicious_rate/summary/malicious_sweep_mean_std.csv")
OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/sensitivity/malicious_rate/plots")
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)
x = df["maliciousRate"]

def errplot(y_mean, y_std, ylabel, title, filename):
    plt.figure()
    plt.errorbar(x, df[y_mean], yerr=df[y_std], fmt='-o', capsize=4)
    plt.xlabel("maliciousRate")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, filename)
    plt.savefig(out_path, dpi=200)
    plt.close()
    print("[OK]", out_path)

errplot("pdr_norm_mean", "pdr_norm_std",
        "PDR (normalized)", "PDR_norm vs maliciousRate",
        "pdr_norm_vs_malicious.png")

errplot("avgDelay_s_mean", "avgDelay_s_std",
        "Average delay (s)", "Average delay vs maliciousRate",
        "delay_vs_malicious.png")

errplot("throughput_bps_mean", "throughput_bps_std",
        "Throughput (bps)", "Throughput vs maliciousRate",
        "throughput_vs_malicious.png")

errplot("sigDrops_mean", "sigDrops_std",
        "Signature drops", "Signature drops vs maliciousRate",
        "sigDrops_vs_malicious.png")

errplot("avgLedgerTrust_mean", "avgLedgerTrust_std",
        "Average ledger trust", "Ledger trust vs maliciousRate",
        "ledger_trust_vs_malicious.png")

errplot("avgHandoverDelay_s_mean", "avgHandoverDelay_s_std",
        "Average handover delay (s)", "Handover delay vs maliciousRate",
        "handover_delay_vs_malicious.png")
