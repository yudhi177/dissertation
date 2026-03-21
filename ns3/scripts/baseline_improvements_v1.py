import os
import pandas as pd

INP = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/summary/summary_ci95.csv")
OUT = os.path.expanduser("~/dissertation/ns3/results/baseline_pack/summary/improvements.csv")

df = pd.read_csv(INP).set_index("baseline")

def pick_mean(col_candidates):
    for c in col_candidates:
        if c in df.columns:
            return c
    return None

pdr = pick_mean(["PDR_mean","pdr_mean"])
delay = pick_mean(["avgDelay_mean","delay_mean","handoverDelayMs_mean"])
thr = pick_mean(["throughput_mean","Throughput_mean","thr_mean"])

metrics = [("PDR", pdr, "higher"),
           ("Delay", delay, "lower"),
           ("Throughput", thr, "higher")]
metrics = [(n,c,d) for (n,c,d) in metrics if c is not None]

baseA = "PKI_ONLY"
baseB = "TRUST_ONLY"

rows = []
for b in df.index:
    for name, col, direction in metrics:
        a = df.loc[baseA, col]
        t = df.loc[b, col]
        impA = ((t - a) / a * 100.0) if a != 0 else float("nan")
        if direction == "lower":
            impA = ((a - t) / a * 100.0) if a != 0 else float("nan")

        b0 = df.loc[baseB, col]
        impB = ((t - b0) / b0 * 100.0) if b0 != 0 else float("nan")
        if direction == "lower":
            impB = ((b0 - t) / b0 * 100.0) if b0 != 0 else float("nan")

        rows.append({
            "baseline": b,
            "metric": name,
            "%_vs_PKI_ONLY": impA,
            "%_vs_TRUST_ONLY": impB,
            "value_mean": t,
        })

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False)
print("[OK] wrote", OUT)
