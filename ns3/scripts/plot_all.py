#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

INP = "final_results/final_master_summary.csv"
OUT_DIR = "final_results/final_compare_plots"

def save_plot(x, y, xlabel, ylabel, title, outpath):
    plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    print("Saved:", outpath)

def main():
    if not os.path.exists(INP):
        print(f"ERROR: {INP} not found. Run scripts/aggregate_all.py first.")
        return

    df = pd.read_csv(INP)

    if "scenario" not in df.columns:
        print("ERROR: 'scenario' column missing. Run scripts/aggregate_all.py first.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    # Aggregate per scenario (numeric columns only if exist)
    metrics = []
    for c in ["pdr", "avgDelay_s", "throughput_bps", "avgLedgerTrust", "avgHandoverDelay_s",
              "replayDrops", "sigDrops", "blocks", "avgBlockLatency_s"]:
        if c in df.columns:
            metrics.append(c)

    if not metrics:
        print("ERROR: No known metric columns found in final_master_summary.csv")
        print("Found columns:", list(df.columns))
        return

    # Mean per scenario for plotting
    agg = df.groupby("scenario", as_index=False)[metrics].mean(numeric_only=True)

    # Sort scenarios for stable plots
    agg = agg.sort_values("scenario")

    # 1) PDR vs scenario
    if "pdr" in agg.columns:
        save_plot(
            agg["scenario"], agg["pdr"],
            "Scenario", "PDR",
            "PDR Comparison Across Scenarios",
            os.path.join(OUT_DIR, "pdr_by_scenario.png")
        )

    # 2) Avg Delay vs scenario
    if "avgDelay_s" in agg.columns:
        save_plot(
            agg["scenario"], agg["avgDelay_s"],
            "Scenario", "Avg Delay (s)",
            "Average Delay Comparison Across Scenarios",
            os.path.join(OUT_DIR, "delay_by_scenario.png")
        )

    # 3) Throughput vs scenario
    if "throughput_bps" in agg.columns:
        save_plot(
            agg["scenario"], agg["throughput_bps"],
            "Scenario", "Throughput (bps)",
            "Throughput Comparison Across Scenarios",
            os.path.join(OUT_DIR, "throughput_by_scenario.png")
        )

    # 4) Ledger trust (where exists)
    if "avgLedgerTrust" in agg.columns:
        save_plot(
            agg["scenario"], agg["avgLedgerTrust"],
            "Scenario", "Avg Ledger Trust",
            "Ledger Trust Comparison Across Scenarios",
            os.path.join(OUT_DIR, "ledger_trust_by_scenario.png")
        )

    # 5) Handover delay (where exists)
    if "avgHandoverDelay_s" in agg.columns:
        save_plot(
            agg["scenario"], agg["avgHandoverDelay_s"],
            "Scenario", "Avg Handover Delay (s)",
            "Handover Delay Comparison Across Scenarios",
            os.path.join(OUT_DIR, "handover_delay_by_scenario.png")
        )

    print("Done. Plots in:", OUT_DIR)

if __name__ == "__main__":
    main()
