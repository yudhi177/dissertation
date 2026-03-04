import os
import pandas as pd
import matplotlib.pyplot as plt

SUM=os.path.expanduser("~/dissertation/ns3/results/final_submission_pack/summary")
OUT=os.path.expanduser("~/dissertation/ns3/results/final_submission_pack/plots")
os.makedirs(OUT, exist_ok=True)

def dot(df, xcol, ycol, ecol, title, fname, xticks=None):
    plt.figure()
    x=list(range(len(df))) if xticks is not None else df[xcol]
    y=df[ycol]
    e=df[ecol] if ecol in df.columns else 0
    plt.errorbar(x, y, yerr=e, fmt="o", capsize=4)
    if xticks is not None:
        plt.xticks(list(range(len(df))), xticks, rotation=15)
        plt.xlabel(xcol)
    else:
        plt.xlabel(xcol)
    plt.ylabel(ycol.replace("_mean",""))
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname))
    plt.close()

# A) Baselines
bfile=os.path.join(SUM,"baseline_summary_ci95.csv")
if os.path.exists(bfile):
    df=pd.read_csv(bfile)
    order=["PKI_ONLY","TRUST_ONLY","BC_TRUST","BC_ALWAYS_QUERY","FULL"]
    df["baseline"]=pd.Categorical(df["baseline"], categories=order, ordered=True)
    df=df.sort_values("baseline")

    def pick(cands):
        for c in cands:
            if c in df.columns:
                return c
        return None

    pdr=pick(["PDR_mean","pdr_mean","pdr_mean_mean"])
    delay=pick(["avgDelay_mean","delay_mean","handoverDelayMs_mean"])
    thr=pick(["throughput_mean","Throughput_mean","thr_mean"])

    if pdr:  dot(df,"baseline",pdr,pdr.replace("_mean","")+"_ci95","PDR by baseline","baseline_pdr.png",xticks=df["baseline"].astype(str))
    if delay:dot(df,"baseline",delay,delay.replace("_mean","")+"_ci95","Delay by baseline","baseline_delay.png",xticks=df["baseline"].astype(str))
    if thr:  dot(df,"baseline",thr,thr.replace("_mean","")+"_ci95","Throughput by baseline","baseline_throughput.png",xticks=df["baseline"].astype(str))

# B) DMAX
dfile=os.path.join(SUM,"dmax_summary_ci95.csv")
if os.path.exists(dfile):
    df=pd.read_csv(dfile).sort_values("trustMaxAgeMs")
    if "staleMismatchRate_mean" in df.columns:
        dot(df,"trustMaxAgeMs","staleMismatchRate_mean","staleMismatchRate_ci95","Stale mismatch rate vs Δmax","dmax_mismatch.png")
    # optional delay if present
    for cand in ["avgDelay_mean","delay_mean","handoverDelayMs_mean"]:
        if cand in df.columns:
            dot(df,"trustMaxAgeMs",cand,cand.replace("_mean","")+"_ci95",f"{cand.replace('_mean','')} vs Δmax","dmax_delay.png")
            break

# C) Auth
afile=os.path.join(SUM,"auth_summary_ci95.csv")
if os.path.exists(afile):
    df=pd.read_csv(afile)
    order=["AUTH_OK","AUTH_MITM","AUTH_REPLAY"]
    df["scenario"]=pd.Categorical(df["scenario"], categories=order, ordered=True)
    df=df.sort_values("scenario")

    if "successRate_mean" in df.columns:
        dot(df,"scenario","successRate_mean","successRate_ci95","Auth success rate","auth_success.png",xticks=df["scenario"].astype(str))
    if "failRate_mean" in df.columns:
        dot(df,"scenario","failRate_mean","failRate_ci95","Auth failure rate","auth_fail.png",xticks=df["scenario"].astype(str))

print("[OK] plots in", OUT)
