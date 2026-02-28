#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

def main():
    base = os.path.join("ns3", "results", "blockchain_runs")
    inp = os.path.join(base, "master_summary.csv")
    if not os.path.exists(inp):
        raise SystemExit("Run aggregate first: python3 experiments/aggregate_blockchain.py")

    df = pd.read_csv(inp)

    # prefer column names from your metrics csv
    # expected: maliciousRate, pdr, avgLedgerTrust
    if "maliciousRate" not in df.columns:
        raise SystemExit("master_summary.csv missing maliciousRate column")

    df = df.sort_values("maliciousRate")

    # Plot 1: PDR vs maliciousRate
    if "pdr" in df.columns:
        plt.figure()
        plt.plot(df["maliciousRate"], df["pdr"], marker="o")
        plt.xlabel("Malicious Rate")
        plt.ylabel("PDR")
        plt.title("Blockchain Trust V2X: PDR vs Malicious Rate")
        plt.grid(True)
        out1 = os.path.join(base, "pdr_vs_malicious.png")
        plt.savefig(out1, dpi=200)
        print("Saved:", out1)

    # Plot 2: Avg Ledger Trust vs maliciousRate
    if "avgLedgerTrust" in df.columns:
        plt.figure()
        plt.plot(df["maliciousRate"], df["avgLedgerTrust"], marker="o")
        plt.xlabel("Malicious Rate")
        plt.ylabel("Avg Ledger Trust")
        plt.title("Blockchain Trust V2X: Ledger Trust vs Malicious Rate")
        plt.grid(True)
        out2 = os.path.join(base, "ledger_trust_vs_malicious.png")
        plt.savefig(out2, dpi=200)
        print("Saved:", out2)

if __name__ == "__main__":
    main()
