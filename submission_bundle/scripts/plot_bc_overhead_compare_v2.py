import os
import pandas as pd
import matplotlib.pyplot as plt

inp = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/summary/summary_ci95.csv")
out = os.path.expanduser("~/dissertation/ns3/results/bc_overhead_compare/plots")
os.makedirs(out, exist_ok=True)

df = pd.read_csv(inp)

# columns are baseline,speed
def plot_metric(metric, title, fname):
    plt.figure()
    for b in ["BC_TRUST","BC_ALWAYS_QUERY","FULL"]:
        g = df[df["baseline"] == b].sort_values("speed")
        if len(g)==0: 
            continue
        x = g["speed"]
        y = g.get(f"{metric}_mean", None)
        if y is None: 
            continue
        e = g.get(f"{metric}_ci95", 0)
        plt.errorbar(x, y, yerr=e, marker="o", capsize=3, label=b)
    plt.xlabel("Speed")
    plt.ylabel(metric)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out, fname))
    plt.close()

# try common BC metrics
for metric, title, fname in [
    ("totalOverheadMs", "Total BC overhead vs speed", "total_bc_overhead_vs_speed.png"),
    ("hitRate", "BC cache hitRate vs speed", "bc_cache_hitrate_vs_speed.png"),
    ("queries", "BC queries vs speed", "bc_queries_vs_speed.png"),
    ("updates", "BC updates vs speed", "bc_updates_vs_speed.png"),
]:
    if f"{metric}_mean" in df.columns:
        plot_metric(metric, title, fname)

print("[OK] plots in", out)
