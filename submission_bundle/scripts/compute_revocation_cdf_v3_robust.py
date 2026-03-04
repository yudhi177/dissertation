import sys, re
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_revocation_cdf_v3_robust.py <events.csv> <out.csv>")
    sys.exit(2)

inp, out = sys.argv[1], sys.argv[2]

# read raw without assuming header
raw = pd.read_csv(inp, header=None, names=["t","event"], dtype=str)

def to_float(x):
    try:
        return float(x)
    except:
        return None

issue_t = None
delays = []

for _, r in raw.iterrows():
    t = to_float(r["t"])
    if t is None:
        continue
    ev = str(r["event"])

    if "REVOKE_ISSUE" in ev and issue_t is None:
        issue_t = t

    if "REVOKE_APPLY" in ev and issue_t is not None:
        d = t - issue_t
        if d >= 0:
            delays.append(d)

delays = sorted(delays)
df = pd.DataFrame({"delay_s": delays})
if len(df) > 0:
    df["cdf"] = (df.index + 1) / len(df)
else:
    df["cdf"] = []

df.to_csv(out, index=False)
print("[OK] wrote", out, "n=", len(df))
