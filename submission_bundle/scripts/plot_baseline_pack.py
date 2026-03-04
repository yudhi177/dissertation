import os
import pandas as pd
import matplotlib.pyplot as plt

INP=os.path.expanduser("~/dissertation/ns3/results/baseline_pack/summary/summary_ci95.csv")
OUT=os.path.expanduser("~/dissertation/ns3/results/baseline_pack/plots")
os.makedirs(OUT, exist_ok=True)

df=pd.read_csv(INP)

order=["PKI_ONLY","TRUST_ONLY","BC_TRUST","BC_ALWAYS_QUERY","FULL"]
df["baseline"]=pd.Categorical(df["baseline"], categories=order, ordered=True)
df=df.sort_values("baseline")

def pick(cands):
    for c in cands:
        if c in df.columns:
            return c
    return None

pdr_col = pick(["PDR_mean","pdr_mean","pdr_mean_mean","pdr_mean"])  # fallback-safe
delay_col = pick(["avgDelay_mean","delay_mean","handoverDelayMs_mean","avgHandoverDelay_mean"])
thr_col = pick(["throughput_mean","Throughput_mean","thr_mean"])

def bar(metric_mean, title, fname):
    base = metric_mean.replace("_mean","")
    y = df[metric_mean]
    e = df[base+"_ci95"] if (base+"_ci95") in df.columns else 0
    x = list(range(len(df)))

    plt.figure()
    plt.errorbar(x, y, yerr=e, fmt="o", capsize=4)
    plt.xticks(x, df["baseline"], rotation=15)
    plt.ylabel(base)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT,fname))
    plt.close()

if pdr_col:  bar(pdr_col,  "PDR by baseline (mean ± CI95)", "pdr_baselines.png")
if delay_col: bar(delay_col, "Delay by baseline (mean ± CI95)", "delay_baselines.png")
if thr_col:  bar(thr_col,  "Throughput by baseline (mean ± CI95)", "throughput_baselines.png")

print("[OK] plots in", OUT)
