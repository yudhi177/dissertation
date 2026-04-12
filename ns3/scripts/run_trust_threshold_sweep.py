#!/usr/bin/env python3
from pathlib import Path
import csv
import io
import re
import shutil
import subprocess
import sys

HOME = Path("/home/yudhishthar")
REPO_SCENARIO = HOME / "dissertation/ns3/scenarios/secure_trust_blockchain_v2x.cc"
NS3_DIR = HOME / "ns-3"
NS3_SCENARIO = NS3_DIR / "scratch/secure_trust_blockchain_v2x.cc"
RUN_TARGET = "scratch/secure_trust_blockchain_v2x"

OUTDIR = NS3_DIR / "results/trust_threshold_sweep"
OUTDIR.mkdir(parents=True, exist_ok=True)

# valid (T_low, T_high) pairs
GRID = [
    (0.20, 0.60),
    (0.20, 0.70),
    (0.20, 0.80),
    (0.30, 0.60),
    (0.30, 0.70),
    (0.30, 0.80),
    (0.40, 0.70),
    (0.40, 0.80),
]

if not REPO_SCENARIO.exists():
    print(f"[ERR] Repo scenario not found: {REPO_SCENARIO}")
    sys.exit(1)

source_original = REPO_SCENARIO.read_text()

# backup current ns-3 scratch file if it exists
backup_path = NS3_SCENARIO.with_suffix(".cc.bak_threshold_sweep")
if NS3_SCENARIO.exists():
    shutil.copy2(NS3_SCENARIO, backup_path)

def patch_text(txt: str, t_low: float, t_high: float, csv_name: str, events_name: str) -> str:
    replacements = [
        (r'static bool g_enableTrustEngineFinal = (true|false);',
         'static bool g_enableTrustEngineFinal = true;'),
        (r'static double g_trustFastThresh = [0-9.]+;',
         f'static double g_trustFastThresh = {t_high:.2f};'),
        (r'static double g_trustMinThresh = [0-9.]+;',
         f'static double g_trustMinThresh = {t_low:.2f};'),
        (r'static std::string g_csvOut = ".*?";',
         f'static std::string g_csvOut = "{csv_name}";'),
        (r'static std::string g_eventsOut = ".*?";',
         f'static std::string g_eventsOut = "{events_name}";'),
    ]
    for pat, rep in replacements:
        txt_new = re.sub(pat, rep, txt)
        if txt_new == txt:
            print(f"[WARN] pattern not replaced: {pat}")
        txt = txt_new
    return txt

def parse_csv_first_row(path: Path):
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return {}

    # normal CSV case
    try:
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
        if rows:
            return rows[0]
    except Exception:
        pass

    # fallback for badly newline-packed single-line CSV
    tokens = raw.replace("\r", "\n").splitlines()
    if len(tokens) == 1:
        one = tokens[0]
        # split header/data by double-space if present
        m = re.match(r'^(.*?)(\s{1,})([-0-9].*)$', one)
        if m:
            header = [h.strip() for h in m.group(1).split(",")]
            data = [d.strip() for d in m.group(3).split(",")]
            if len(header) == len(data):
                return dict(zip(header, data))

    return {}

def run_cmd(cmd, cwd):
    print(f"[RUN] {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return res.stdout

summary_rows = []

try:
    # make sure scratch file exists
    NS3_SCENARIO.parent.mkdir(parents=True, exist_ok=True)

    # first configure/build once
    run_cmd(["./ns3", "configure"], NS3_DIR)
    run_cmd(["./ns3", "build"], NS3_DIR)

    for t_low, t_high in GRID:
        tag = f"tl_{int(t_low*100):02d}_th_{int(t_high*100):02d}"
        csv_rel = f"results/trust_threshold_sweep/metrics_{tag}.csv"
        evt_rel = f"results/trust_threshold_sweep/events_{tag}.csv"
        log_path = OUTDIR / f"run_{tag}.log"

        print(f"\n===== RUN {tag} =====")

        patched = patch_text(source_original, t_low, t_high, csv_rel, evt_rel)
        NS3_SCENARIO.write_text(patched, encoding="utf-8")

        run_cmd(["./ns3", "build"], NS3_DIR)
        stdout = run_cmd(["./ns3", "run", RUN_TARGET], NS3_DIR)
        log_path.write_text(stdout, encoding="utf-8")

        metrics_path = NS3_DIR / csv_rel
        row = parse_csv_first_row(metrics_path)

        summary = {
            "T_low": f"{t_low:.2f}",
            "T_high": f"{t_high:.2f}",
            "metrics_file": str(metrics_path),
            "events_file": str(NS3_DIR / evt_rel),
            "handoverCount": row.get("handoverCount", ""),
            "avgHandoverDelay_s": row.get("avgHandoverDelay_s", row.get("avgHandoverDelay", "")),
            "fastAuthCount": row.get("fastAuthCount", ""),
            "fullAuthCount": row.get("fullAuthCount", ""),
            "rejectCount": row.get("rejectCount", ""),
            "avgAdaptiveTrust": row.get("avgAdaptiveTrust", ""),
            "avgBlockLatency": row.get("avgBlockLatency", ""),
            "cacheHits": row.get("cacheHits", ""),
            "cacheHitRate": row.get("cacheHitRate", ""),
            "rxCount": row.get("rxCount", ""),
            "replayDrops": row.get("replayDrops", ""),
            "avgDelay_s": row.get("avgDelay_s", ""),
            "throughput_bps": row.get("throughput_bps", ""),
        }
        summary_rows.append(summary)

    summary_csv = OUTDIR / "threshold_sweep_summary.csv"
    fieldnames = [
        "T_low", "T_high", "metrics_file", "events_file",
        "handoverCount", "avgHandoverDelay_s",
        "fastAuthCount", "fullAuthCount", "rejectCount",
        "avgAdaptiveTrust", "avgBlockLatency",
        "cacheHits", "cacheHitRate",
        "rxCount", "replayDrops", "avgDelay_s", "throughput_bps"
    ]
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\n[OK] Summary written to: {summary_csv}")

finally:
    # restore previous scratch file if backup existed
    if backup_path.exists():
        shutil.move(str(backup_path), str(NS3_SCENARIO))
    else:
        # if there was no original scratch file, leave the patched file in place
        pass
