import sys
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_revocation_cdf.py <events.csv> <out.csv>")
    sys.exit(2)

events = pd.read_csv(sys.argv[1], header=None, names=["t","event"])
out = sys.argv[2]

issue_t = None
apply_ts = []

for _, r in events.iterrows():
    ev = str(r["event"])
    if "REVOKE_ISSUE" in ev:
        issue_t = float(r["t"])
    if "REVOKE_APPLY" in ev and issue_t is not None:
        apply_ts.append(float(r["t"]) - issue_t)

if not apply_ts:
    df = pd.DataFrame({"delay":[]})
else:
    df = pd.DataFrame({"delay": sorted(apply_ts)})

# CDF
df["cdf"] = (df.index + 1) / max(len(df), 1)
df.to_csv(out, index=False)
print("[OK] wrote", out, "n=", len(df))
