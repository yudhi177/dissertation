import sys, re
import pandas as pd

if len(sys.argv) != 3:
    print("Usage: compute_revocation_cdf_v3.py <events.csv> <out.csv>")
    sys.exit(2)

events_path, out_path = sys.argv[1], sys.argv[2]

# robust read (handles optional header "time,event")
df = pd.read_csv(events_path, header=None, names=["t","event"], dtype=str)
df["t_num"] = pd.to_numeric(df["t"], errors="coerce")
df = df.dropna(subset=["t_num"]).reset_index(drop=True)

issue_t = None
delays = []

for _, r in df.iterrows():
    ev = str(r["event"])
    t = float(r["t_num"])
    if "REVOKE_ISSUE" in ev and issue_t is None:
        issue_t = t
    elif "REVOKE_APPLY" in ev and issue_t is not None:
        d = t - issue_t
        if d >= 0:
            delays.append(d)

delays.sort()
out = pd.DataFrame({"delay_s": delays})
if len(out) > 0:
    out["cdf"] = (out.index + 1) / len(out)
else:
    out["cdf"] = []

out.to_csv(out_path, index=False)
print("[OK] wrote", out_path, "n=", len(out))
