import os
import pandas as pd
import matplotlib.pyplot as plt

INP = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/plots")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(INP)

order = ["PKI_ONLY","TRUST_ONLY","BC_TRUST","BC_ALWAYS_QUERY","FULL"]
df["baseline"] = pd.Categorical(df["baseline"], categories=order, ordered=True)
df = df.sort_values("baseline")

def pick(base_names):
    for b in base_names:
        if f"{b}_mean" in df.columns:
            return b
    return None

PDR  = pick(["PDR","pdr"])
DELAY= pick(["avgDelay","delay","handoverDelayMs"])
THR  = pick(["throughput","Throughput","thr"])

def bar(base, title, fname):
    y = df[f"{base}_mean"]
    e = df[f"{base}_ci95"] if f"{base}_ci95" in df.columns else 0
    x = list(range(len(df)))
    plt.figure()
    plt.errorbar(x, y, yerr=e, fmt="o", capsize=4)
    plt.xticks(x, df["baseline"], rotation=15)
    plt.ylabel(base)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname))
    plt.close()

if PDR:   bar(PDR,   "PDR by baseline (mean ± CI95)",        "pdr_baselines.png")
if DELAY: bar(DELAY, "Delay by baseline (mean ± CI95)",      "delay_baselines.png")
if THR:   bar(THR,   "Throughput by baseline (mean ± CI95)", "throughput_baselines.png")

print("[OK] plots in", OUT)
