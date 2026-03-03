#!/usr/bin/env bash
set -euo pipefail

RUNS_DIR="${1:-$HOME/dissertation/ns3/results/publish_pack_baselines/runs}"
OUT_DIR="${2:-$HOME/dissertation/results_publishable/baselines_pack}"

mkdir -p "$OUT_DIR"

# Pick latest FULL events file (most recent modified)
EVT=$(ls -1t "$RUNS_DIR"/FULL_*_events.csv 2>/dev/null | head -n 1 || true)
if [[ -z "${EVT}" ]]; then
  echo "[ERR] No FULL_*_events.csv found in $RUNS_DIR"
  exit 2
fi

echo "[INFO] Using events: $EVT"

# Revocation CDF
python3 "$HOME/dissertation/ns3/scripts/compute_revocation_cdf_v3.py" "$EVT" "$OUT_DIR/revocation_cdf.csv"
python3 "$HOME/dissertation/ns3/scripts/plot_revocation_cdf_v2.py" "$OUT_DIR/revocation_cdf.csv" "$OUT_DIR/revocation_cdf.png"

# Detection / FP stats
python3 "$HOME/dissertation/ns3/scripts/compute_detection_fp_stats.py" "$EVT" "$OUT_DIR/detect_fp.csv"

echo "[OK] Wrote:"
echo " - $OUT_DIR/revocation_cdf.csv"
echo " - $OUT_DIR/revocation_cdf.png"
echo " - $OUT_DIR/detect_fp.csv"
