import os, re, glob
import pandas as pd
import numpy as np

RUNS = os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/runs")
OUT  = os.path.expanduser("~/dissertation/ns3/results/auth_security_pack/summary")
os.makedirs(OUT, exist_ok=True)

pat = re.compile(r"^(AUTH_OK|AUTH_MITM|AUTH_REPLAY)_seed(\d+)\.log$")
auth_pat = re.compile(r"\[AUTH\]\s+ok=(\d+)\s+fail=(\d+)\s+mitmFail=(\d+)\s+replayFail=(\d+)")

rows=[]
for logf in glob.glob(os.path.join(RUNS, "*.log")):
    base=os.path.basename(logf)
    m=pat.match(base)
    if not m:
        continue
    scen=m.group(1)
    seed=int(m.group(2))
    txt=open(logf,"r",errors="ignore").read()
    mm=auth_pat.search(txt)
    if not mm:
        continue

    ok=int(mm.group(1)); fail=int(mm.group(2))
    mitmFail=int(mm.group(3)); replayFail=int(mm.group(4))
    total = ok + fail
    rows.append({
        "scenario": scen, "seed": seed,
        "authOk": ok, "authFail": fail,
        "mitmFail": mitmFail, "replayFail": replayFail,
        "totalHandshakes": total,
        "successRate": (ok/total) if total>0 else np.nan,
        "failRate": (fail/total) if total>0 else np.nan,
    })

raw=pd.DataFrame(rows)
raw.to_csv(os.path.join(OUT,"raw.csv"),index=False)

if raw.empty:
    raise SystemExit(f"[ERR] No parsed logs found in {RUNS}")

def ci95(x):
    x=pd.to_numeric(x,errors="coerce").dropna()
    if len(x)<=1: return 0.0
    return 1.96*x.std(ddof=1)/np.sqrt(len(x))

metrics=[c for c in raw.columns if c not in ("scenario","seed")]
grp=raw.groupby("scenario",as_index=False)

agg = grp[metrics].agg(["mean","std","count"])
agg.columns=["_".join(c).strip("_") for c in agg.columns]
agg=agg.reset_index().rename(columns={"index":"row"})

# add ci95 columns aligned by scenario order
for m in metrics:
    agg[m+"_ci95"] = grp[m].apply(ci95).values

agg.to_csv(os.path.join(OUT,"summary_ci95.csv"),index=False)
print("[OK] wrote", os.path.join(OUT,"summary_ci95.csv"))
