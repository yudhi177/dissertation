#!/usr/bin/env bash
set -euo pipefail

RUNS="$HOME/dissertation/ns3/results/publish_pack_baselines/runs"
OUTP="$HOME/dissertation/results_publishable/baselines_pack"
mkdir -p "$OUTP"

EVT=$(ls -1t "$RUNS"/*FULL*_events.csv 2>/dev/null | head -n 1 || true)
if [[ -z "${EVT}" ]]; then
  echo "[ERR] No FULL events file found in $RUNS"
  exit 1
fi

echo "[INFO] Using events: $EVT"

python3 "$HOME/dissertation/ns3/scripts/compute_detection_fp_stats.py" "$EVT" "$OUTP/detect_fp.csv"
ls -lh "$OUTP/detect_fp.csv"
head -n 20 "$OUTP/detect_fp.csv"
