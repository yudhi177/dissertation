import os
import pandas as pd
import matplotlib.pyplot as plt

INP = os.path.expanduser("~/dissertation/ns3/results/trust_sensitivity_sweep/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/trust_sensitivity_sweep/plots")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(INP)

# preferred metrics (plot if present)
preferred = [
    "handoverDelayMs_mean", "handoverDelay_mean", "avgHandoverDelay_mean",
    "avgDelay_mean", "delay_mean",
    "PDR_mean", "pdr_mean",
    "throughput_mean",
    "fastRate_mean", "fullRate_mean", "rejectRate_mean"
]
present = [m for m in preferred if m in df.columns]

# fallback: any metric_mean columns
if not present:
    present = [c for c in df.columns if c.endswith("_mean") and c not in ("value_mean",)]

for (sweep, param), g in df.groupby(["sweep", "param"]):
    g = g.sort_values("value")
    x = g["value"].values

    for m in present[:6]:  # keep plots manageable
        base = m[:-5]  # remove _mean
        y = g[m].values
        ci = g.get(base + "_ci95", pd.Series([0]*len(g))).values

        plt.figure()
        plt.errorbar(x, y, yerr=ci, marker="o", capsize=3)
        plt.xlabel(param)
        plt.ylabel(base)
        plt.title(f"{sweep}: {base} vs {param}")
        plt.tight_layout()
        outp = os.path.join(OUT, f"{sweep}_{param}_{base}.png")
        plt.savefig(outp)
        plt.close()

print("[OK] plots saved in", OUT)
