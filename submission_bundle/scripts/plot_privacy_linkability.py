import os
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.expanduser("~/dissertation/ns3/results/privacy_linkability_sweep")
INP  = os.path.join(BASE, "summary/privacy_linkability_mean_std.csv")
OUTD = os.path.join(BASE, "plots")
os.makedirs(OUTD, exist_ok=True)

df = pd.read_csv(INP)

if "linkabilityRate_mean" not in df.columns:
    raise SystemExit("[ERR] linkabilityRate_mean missing. Ensure LINK_ATTEMPT/LINK_SUCCESS events exist or counters are in CSV.")

df = df.dropna(subset=["linkabilityRate_mean"])

for rsu in sorted(df["rotateOnRsuChange"].unique()):
    sub0 = df[df["rotateOnRsuChange"]==rsu].copy()
    for nveh in sorted(sub0["nVehicles"].unique()):
        sub = sub0[sub0["nVehicles"]==nveh].sort_values("pseudoRotateSec")
        y = sub["linkabilityRate_mean"].astype(float)
        yerr = sub.get("linkabilityRate_std", None)
        if yerr is None or (hasattr(yerr, "isna") and yerr.isna().all()):
            yerr = None

        plt.figure()
        plt.errorbar(sub["pseudoRotateSec"], y, yerr=yerr, marker="o")
        plt.xlabel("Pseudonym rotation interval (sec)")
        plt.ylabel("Linkability rate (lower is better)")
        plt.title(f"Linkability vs Rotation (nVehicles={nveh}, rotateOnRsuChange={rsu})")
        out = os.path.join(OUTD, f"linkability_n{nveh}_rsu{rsu}.png")
        plt.savefig(out, dpi=200, bbox_inches="tight")
        plt.close()
        print("[OK]", out)
