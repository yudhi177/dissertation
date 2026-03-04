import os
import pandas as pd
import matplotlib.pyplot as plt

INP=os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/summary/summary_ci95.csv")
OUT=os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/plots")
os.makedirs(OUT,exist_ok=True)

df=pd.read_csv(INP)

order=["AUTH_OK","AUTH_MITM","AUTH_REPLAY"]
df["scenario"]=pd.Categorical(df["scenario"], categories=order, ordered=True)
df=df.sort_values("scenario")

def bar(metric, title, fname):
    plt.figure()
    x=range(len(df))
    y=df[f"{metric}_mean"]
    e=df.get(f"{metric}_ci95",0)
    plt.errorbar(x,y,yerr=e,fmt="o",capsize=4)
    plt.xticks(list(x), df["scenario"])
    plt.ylabel(metric)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT,fname))
    plt.close()

bar("successRate","Auth success rate (OK vs MITM vs Replay)","auth_success_rate.png")
bar("failRate","Auth failure rate (OK vs MITM vs Replay)","auth_fail_rate.png")

print("[OK] plots in",OUT)
