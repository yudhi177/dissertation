import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("blockchain_runs/master_summary.csv")

# Prefer real column if present; else use extracted value
xcol = "maliciousRate"
if xcol not in df.columns or df[xcol].isna().all():
    xcol = "maliciousRateFromFile"

df = df.sort_values(xcol)

# Helper to plot one metric
def make_plot(ycol, ylabel, outpng, title):
    if ycol not in df.columns:
        print(f"Skip {ycol} (not found)")
        return
    plt.figure()
    plt.plot(df[xcol], df[ycol], marker="o")
    plt.xlabel("Malicious Rate")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.savefig(outpng, dpi=200)
    print("Saved", outpng)

make_plot("pdr", "PDR", "blockchain_runs/pdr_vs_malicious.png", "PDR vs Malicious Rate")
make_plot("avgDelay_s", "Avg Delay (s)", "blockchain_runs/delay_vs_malicious.png", "Avg Delay vs Malicious Rate")
make_plot("throughput_bps", "Throughput (bps)", "blockchain_runs/throughput_vs_malicious.png", "Throughput vs Malicious Rate")
make_plot("avgLedgerTrust", "Avg Ledger Trust", "blockchain_runs/ledgertrust_vs_malicious.png", "Ledger Trust vs Malicious Rate")
make_plot("avgBlockLatency_s", "Avg Block Latency (s)", "blockchain_runs/blocklat_vs_malicious.png", "Block Latency vs Malicious Rate")
