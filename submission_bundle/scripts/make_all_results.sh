#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
S="$REPO/ns3/scripts"

need () { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] missing command: $1"; exit 1; }; }
need python3
need sumo

MODE="${1:-full}"   # full | quick

echo "[INFO] Repo: $REPO"
echo "[INFO] MODE=$MODE"
echo

# -----------------------------
# 1) SUMO pipeline (core plots)
# -----------------------------
echo "[1/3] SUMO pipeline..."
mkdir -p "$REPO/ns3/results/sumo_pipeline/runs"
rm -rf "$REPO/ns3/results/sumo_pipeline/runs/"*

if [[ "$MODE" == "quick" ]]; then
  ONLY_ONE=1 NVEH=30 SPD=13.9 SEED=1 SIM_TIME=20 \
    "$S/run_sumo_ns3_pipeline.sh"
else
  "$S/run_sumo_ns3_pipeline.sh"
fi

python3 "$S/aggregate_sumo_pipeline.py"
python3 "$S/plot_sumo_pipeline.py"
echo "[OK] SUMO pipeline done."
echo

# --------------------------------
# 2) Adaptive mining compare
# --------------------------------
if [[ -x "$S/run_adaptive_mining_compare.sh" ]]; then
  echo "[2/3] Adaptive mining compare..."
  mkdir -p "$REPO/ns3/results/adaptive_mining_compare/runs"
  rm -rf "$REPO/ns3/results/adaptive_mining_compare/runs/"*

  if [[ "$MODE" == "quick" ]]; then
    ONLY_ONE=1 NVEH=30 SPD=13.9 SEED=1 SIM_TIME=10 \
      "$S/run_adaptive_mining_compare.sh"
  else
    SIM_TIME=20 "$S/run_adaptive_mining_compare.sh"
  fi

  python3 "$S/aggregate_plot_adaptive_mining_compare.py"
  echo "[OK] Adaptive mining compare done."
  echo
else
  echo "[SKIP] run_adaptive_mining_compare.sh not found/executable"
  echo
fi

# --------------------------------
# 3) Sybil burst sweep
# --------------------------------
if [[ -x "$S/run_sybil_burst_sweep.sh" ]]; then
  echo "[3/3] Sybil burst sweep..."
  mkdir -p "$REPO/ns3/results/sybil_burst_sweep/runs"
  rm -rf "$REPO/ns3/results/sybil_burst_sweep/runs/"*

  if [[ "$MODE" == "quick" ]]; then
    ONLY_ONE=1 NVEH=30 SPD=13.9 SEED=1 BURST=2 SIM_TIME=10 \
      "$S/run_sybil_burst_sweep.sh"
  else
    SIM_TIME=20 "$S/run_sybil_burst_sweep.sh"
  fi

  python3 "$S/aggregate_plot_sybil_burst_sweep.py"
  echo "[OK] Sybil burst sweep done."
  echo
else
  echo "[SKIP] run_sybil_burst_sweep.sh not found/executable"
  echo
fi

echo "=============================="
echo "[DONE] All reproducible results generated."
echo "SUMO:      $REPO/ns3/results/sumo_pipeline"
echo "Adaptive:  $REPO/ns3/results/adaptive_mining_compare"
echo "Sybil:     $REPO/ns3/results/sybil_burst_sweep"
echo "=============================="
