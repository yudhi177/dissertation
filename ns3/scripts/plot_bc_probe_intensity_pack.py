import os
import pandas as pd
import matplotlib.pyplot as plt

INP = os.path.expanduser("~/dissertation/ns3/results/bc_probe_intensity_pack/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/bc_probe_intensity_pack/plots")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(INP)

def plot_metric(metric, title, fname):
    plt.figure()
    for b in ["BC_TRUST","BC_ALWAYS_QUERY"]:
        g = df[df["baseline"]==b].sort_values("bcProbeIntervalMs")
        if g.empty: 
            continue
        x = g["bcProbeIntervalMs"]
        y = g[f"{metric}_mean"]
        e = g.get(f"{metric}_ci95", 0)
        plt.errorbar(x, y, yerr=e, marker="o", capsize=3, label=b)
    plt.xlabel("bcProbeIntervalMs (lower = more load)")
    plt.ylabel(metric)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname))
    plt.close()

for metric, title, fname in [
    ("totalOverheadMs","Total BC overhead vs probe intensity","total_bc_overhead_vs_probe.png"),
    ("hitRate","BC cache hitRate vs probe intensity","bc_cache_hitrate_vs_probe.png"),
    ("queries","BC queries vs probe intensity","bc_queries_vs_probe.png"),
    ("updates","BC updates vs probe intensity","bc_updates_vs_probe.png"),
]:
    if f"{metric}_mean" in df.columns:
        plot_metric(metric, title, fname)

print("[OK] plots in", OUT)
