import os
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV = os.path.expanduser("~/dissertation/ns3/results/sumo_pipeline/summary/sumo_pipeline_mean_std.csv")
OUT_DIR = os.path.expanduser("~/dissertation/ns3/results/sumo_pipeline/plots")
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)

def _safe_yerr(sub, metric):
    sc = f"{metric}_std"
    if sc not in sub.columns:
        return None
    y = pd.to_numeric(sub[sc], errors="coerce")
    if not y.notna().any():
        return None
    return y.fillna(0.0).values

def plot_metric(metric, ylabel, out_name):
    mc = f"{metric}_mean"
    if mc not in df.columns:
        print(f"[SKIP] missing {mc}")
        return

    plt.figure()
    for spd in sorted(df["speedTag"].unique()):
        sub = df[df["speedTag"] == spd].sort_values("nVehicles")
        x = sub["nVehicles"].values
        y = pd.to_numeric(sub[mc], errors="coerce").fillna(0.0).values
        yerr = _safe_yerr(sub, metric)

        plt.errorbar(x, y, yerr=yerr, marker="o", label=f"speedTag={spd}")

    plt.xlabel("nVehicles")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} vs Density (speed curves)")
    plt.legend()
    plt.tight_layout()

    out_path = os.path.join(OUT_DIR, out_name)
    plt.savefig(out_path, dpi=200)
    plt.close()
    print("[OK]", out_path)

plot_metric("pdr_norm", "Normalized PDR", "pdr_norm_vs_density_speed.png")
plot_metric("avgDelay_s", "Average Delay (s)", "delay_vs_density_speed.png")
plot_metric("throughput_bps", "Throughput (bps)", "throughput_vs_density_speed.png")
plot_metric("handoverCount", "Handover Count", "handover_count_vs_density_speed.png")
plot_metric("avgHandoverDelay_s", "Average Handover Delay (s)", "handover_delay_vs_density_speed.png")
plot_metric("avgLedgerTrust", "Average Ledger Trust", "ledger_trust_vs_density_speed.png")
