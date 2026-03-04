#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
S="$REPO/ns3/scripts"

RUNS="$REPO/ns3/results/sanity_check/runs"
mkdir -p "$RUNS"
rm -rf "$RUNS"/*

need () { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] missing command: $1"; exit 1; }; }
need python3
need sumo
need grep
need head

echo "=============================="
echo "[SANITY] Starting checks..."
echo "REPO=$REPO"
echo "NS3DIR=$NS3DIR"
echo "=============================="

# -----------------------------
# 0) Build ns-3
# -----------------------------
echo "[0] Building ns-3..."
cd "$NS3DIR"
./ns3 build >/dev/null
echo "[OK] ns-3 build"

# -----------------------------
# 1) NS-3 standalone quick run
# -----------------------------
echo "[1] NS-3 standalone quick run..."
CSV1="/tmp/sanity_ns3_metrics.csv"
EVT1="/tmp/sanity_ns3_events.csv"
rm -f "$CSV1" "$EVT1"

./ns3 run "scratch/secure_trust_blockchain_v2x --simTime=5 --csvOut=$CSV1 --eventsOut=$EVT1" >/dev/null

test -s "$CSV1" || { echo "[ERR] standalone CSV not created: $CSV1"; exit 1; }
test -s "$EVT1" || { echo "[ERR] standalone events not created: $EVT1"; exit 1; }

echo "[OK] standalone outputs exist"
head -n 1 "$CSV1" | grep -q "pdr_norm" || { echo "[ERR] pdr_norm missing in standalone CSV header"; exit 1; }
head -n 1 "$CSV1" | grep -q "handoverCount" || { echo "[ERR] handoverCount missing in standalone CSV header"; exit 1; }
echo "[OK] standalone CSV header contains expected fields"

# -----------------------------
# 2) SUMO pipeline single run
# -----------------------------
echo "[2] SUMO->NS2->NS3 single pipeline run..."
rm -rf "$REPO/ns3/results/sumo_pipeline/runs/"*
ONLY_ONE=1 NVEH=30 SPD=13.9 SEED=1 SIM_TIME=20 \
  "$S/run_sumo_ns3_pipeline.sh" >/dev/null

OUTCSV="$REPO/ns3/results/sumo_pipeline/runs/veh_30_spd_13.9_seed_1.csv"
OUTEVT="$REPO/ns3/results/sumo_pipeline/runs/veh_30_spd_13.9_seed_1_events.csv"

test -s "$OUTCSV" || { echo "[ERR] SUMO pipeline CSV missing: $OUTCSV"; exit 1; }
test -s "$OUTEVT" || { echo "[ERR] SUMO pipeline events missing: $OUTEVT"; exit 1; }

echo "[OK] SUMO pipeline outputs exist"

# Locate SUMO artifacts and validate
RUN_DIR="$REPO/sumo/output/grid/veh_30_spd_13.9_seed_1"
FCD="$RUN_DIR/fcd.xml"
NS2="$RUN_DIR/ns2mobility.tcl"

test -s "$FCD" || { echo "[ERR] missing FCD: $FCD"; exit 1; }
grep -q "<vehicle" "$FCD" || { echo "[ERR] FCD has no <vehicle> entries (SUMO inserted none)"; exit 1; }
echo "[OK] FCD contains vehicles"

test -s "$NS2" || { echo "[ERR] missing ns2mobility trace: $NS2"; exit 1; }
grep -q "set X_" "$NS2" || { echo "[ERR] NS2 trace looks invalid (no positions)"; exit 1; }
echo "[OK] NS2 mobility trace looks valid"

# Required columns in SUMO CSV
hdr="$(head -n 1 "$OUTCSV")"
for col in pdr_norm avgDelay_s throughput_bps avgLedgerTrust handoverCount; do
  echo "$hdr" | grep -q "$col" || { echo "[ERR] missing column '$col' in SUMO pipeline CSV header"; exit 1; }
done
echo "[OK] SUMO pipeline CSV header contains key metrics"

# Handover events presence (not mandatory, but warn if none)
if grep -Eq "HO_START|HO_DONE|HO_REJECT" "$OUTEVT"; then
  echo "[OK] Handover events present in events CSV"
else
  echo "[WARN] No HO_* events found (handoverCount may be 0). Not failing."
fi

# -----------------------------
# 3) Aggregation + plots should run
# -----------------------------
echo "[3] Aggregation + plots (SUMO pipeline)..."
python3 "$S/aggregate_sumo_pipeline.py" >/dev/null
python3 "$S/plot_sumo_pipeline.py" >/dev/null

SUMCSV="$REPO/ns3/results/sumo_pipeline/summary/sumo_pipeline_mean_std.csv"
test -s "$SUMCSV" || { echo "[ERR] summary not created: $SUMCSV"; exit 1; }

PLOTS_DIR="$REPO/ns3/results/sumo_pipeline/plots"
test -d "$PLOTS_DIR" || { echo "[ERR] plots directory missing: $PLOTS_DIR"; exit 1; }

cnt_png="$(ls -1 "$PLOTS_DIR"/*.png 2>/dev/null | wc -l || true)"
if [[ "$cnt_png" -lt 1 ]]; then
  echo "[ERR] no plots generated in $PLOTS_DIR"
  exit 1
fi
echo "[OK] plots generated: $cnt_png PNGs"

echo "=============================="
echo "[SANITY] ALL CHECKS PASSED ✅"
echo "=============================="
