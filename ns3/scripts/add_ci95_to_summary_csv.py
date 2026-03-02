import argparse, math
from pathlib import Path
import pandas as pd

def add_ci(df: pd.DataFrame) -> pd.DataFrame:
    n = None
    if "nRuns" in df.columns:
        n = df["nRuns"].astype(float)
    else:
        n = 5.0  # fallback

    mean_cols = [c for c in df.columns if c.endswith("_mean")]
    for mc in mean_cols:
        sc = mc.replace("_mean", "_std")
        if sc not in df.columns:
            continue
        ci = mc.replace("_mean", "_ci95")
        if isinstance(n, pd.Series):
            df[ci] = 1.96 * df[sc].astype(float) / n.apply(lambda x: math.sqrt(x) if x > 0 else 1.0)
        else:
            df[ci] = 1.96 * df[sc].astype(float) / math.sqrt(n)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input summary CSV")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV with CI95 columns")
    args = ap.parse_args()

    inp = Path(args.inp).expanduser()
    out = Path(args.out).expanduser()
    df = pd.read_csv(inp)
    df = add_ci(df)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print("[OK] wrote:", out)

if __name__ == "__main__":
    main()
