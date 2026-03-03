import sys
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_revocation_cdf_v2.py <events.csv> <out.csv>")
    sys.exit(2)

events = pd.read_csv(sys.argv[1], header=None, names=["t","event"])
issue_t = None
delays = []

for _, r in events.iterrows():
    ev = str(r["event"])
    t = float(r["t"])
    if "REVOKE_ISSUE" in ev and issue_t is None:
        issue_t = t
    if "REVOKE_APPLY" in ev and issue_t is not None:
        delays.append(t - issue_t)

delays = sorted([d for d in delays if d >= 0])
df = pd.DataFrame({"delay_s": delays})
if len(df) > 0:
    df["cdf"] = (df.index + 1) / len(df)
else:
    df["cdf"] = []
df.to_csv(sys.argv[2], index=False)
print("[OK] wrote", sys.argv[2], "n=", len(df))
