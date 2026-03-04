import os
import pandas as pd
import matplotlib.pyplot as plt

inp = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare_v2/summary/summary_ci95.csv")
out = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare_v2/plots")
os.makedirs(out, exist_ok=True)

df = pd.read_csv(inp)

def plot_metric(metric, title, fname):
    plt.figure()
    for b in ["BC_TRUST","BC_ALWAYS_QUERY","FULL"]:
        g = df[df["baseline"] == b].sort_values("probeIntervalMs")
        if len(g) == 0: 
            continue
        x = g["probeIntervalMs"]
        y = g[f"{metric}_mean"]
        e = g.get(f"{metric}_ci95", 0)
        plt.errorbar(x, y, yerr=e, marker="o", capsize=3, label=b)
    plt.xlabel("BC probe interval (ms)  (lower = more workload)")
    plt.ylabel(metric)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out, fname))
    plt.close()

plot_metric("totalOverheadMs", "Total blockchain overhead vs probe workload", "total_bc_overhead_vs_probeInterval.png")
plot_metric("hitRate", "BC cache hitRate vs probe workload", "bc_cache_hitrate_vs_probeInterval.png")
plot_metric("queries", "BC queries vs probe workload", "bc_queries_vs_probeInterval.png")
plot_metric("updates", "BC updates vs probe workload", "bc_updates_vs_probeInterval.png")

print("[OK] plots in", out)
