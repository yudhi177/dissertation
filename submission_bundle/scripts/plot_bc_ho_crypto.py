import os
import pandas as pd
import matplotlib.pyplot as plt

INP = "bc_ho_crypto/master_summary.csv"
OUT_DIR = "bc_ho_crypto"

def save_plot(x, y, xlabel, ylabel, title, outname):
    plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    outpath = os.path.join(OUT_DIR, outname)
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    print("Saved:", outpath)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(INP)
    if "cryptoDelayUs" not in df.columns:
        # fallback: use tx delay if present
        if "cryptoDelayUsTx" in df.columns:
            df["cryptoDelayUs"] = df["cryptoDelayUsTx"]
        else:
            raise SystemExit("No cryptoDelayUs/cryptoDelayUsTx column found in master_summary.csv")

    df = df.sort_values("cryptoDelayUs")

    x = df["cryptoDelayUs"]

    # Core graphs
    if "pdr" in df.columns:
        save_plot(x, df["pdr"], "Crypto delay (us)", "PDR",
                  "PDR vs Crypto Delay", "pdr_vs_crypto.png")

    if "avgDelay_s" in df.columns:
        save_plot(x, df["avgDelay_s"], "Crypto delay (us)", "Avg data delay (s)",
                  "Data Delay vs Crypto Delay", "data_delay_vs_crypto.png")

    if "throughput_bps" in df.columns:
        save_plot(x, df["throughput_bps"], "Crypto delay (us)", "Throughput (bps)",
                  "Throughput vs Crypto Delay", "throughput_vs_crypto.png")

    if "avgHandoverDelay_s" in df.columns:
        save_plot(x, df["avgHandoverDelay_s"], "Crypto delay (us)", "Avg HO delay (s)",
                  "Handover Delay vs Crypto Delay", "handover_delay_vs_crypto.png")

    if "avgLedgerTrust" in df.columns:
        save_plot(x, df["avgLedgerTrust"], "Crypto delay (us)", "Avg ledger trust",
                  "Ledger Trust vs Crypto Delay", "ledger_trust_vs_crypto.png")

    if "replayDrops" in df.columns:
        save_plot(x, df["replayDrops"], "Crypto delay (us)", "Replay drops",
                  "Replay Drops vs Crypto Delay", "replayDrops_vs_crypto.png")

    if "sigDrops" in df.columns:
        save_plot(x, df["sigDrops"], "Crypto delay (us)", "Signature drops",
                  "Signature Drops vs Crypto Delay", "sigDrops_vs_crypto.png")

if __name__ == "__main__":
    main()
