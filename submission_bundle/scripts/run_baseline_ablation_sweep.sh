#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"

SIM_TIME="${SIM_TIME:-20}"
RSU_RADIUS="${RSU_RADIUS:-300}"

# Inputs: reuse existing SUMO->NS2 traces created in sumo_pipeline
# Path format: sumo/output/grid/veh_${n}_spd_${spd}_seed_${seed}/ns2mobility.tcl

OUT="$REPO/ns3/results/baseline_ablation"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

# Use string lists to avoid bash array "(1)" issue
VEH_LIST_STR="${VEH_LIST_STR:-10 30 50 80}"
SPD_LIST_STR="${SPD_LIST_STR:-8.3 13.9 22.2}"
SEED_LIST_STR="${SEED_LIST_STR:-1 2 3 4 5}"

# Security scenario (fixed)
ATTACK_MODE="${ATTACK_MODE:-2}"
MAL_RATE="${MAL_RATE:-0.2}"
TX_ALL="${TX_ALL:-0}"

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

run_one () {
  local baseline="$1"
  local nveh="$2"
  local spd="$3"
  local seed="$4"
  local ns2="$5"

  local tag="base_${baseline}_n${nveh}_s${spd}_seed${seed}"
  local out_csv="$RUNS/${tag}.csv"
  local out_evt="$RUNS/${tag}_events.csv"

  # Baselines:
  # PKI: no blockchain, no trust engine, no trust gate, no reports
  # BC:  blockchain ON, reports ON, trust engine OFF, trust gate OFF
  # FULL: blockchain ON, reports ON, trust engine ON, trust gate ON
  local enableBC=0 enableReports=0 enableTE=0 enableGate=0 enableRev=0
  case "$baseline" in
    pki)  enableBC=0 enableReports=0 enableTE=0 enableGate=0 enableRev=0 ;;
    bc)   enableBC=1 enableReports=1 enableTE=0 enableGate=0 enableRev=1 ;;
    full) enableBC=1 enableReports=1 enableTE=1 enableGate=1 enableRev=1 ;;
    *) echo "[ERR] unknown baseline: $baseline" >&2; exit 1 ;;
  esac

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$ns2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --rsuCoverageRadius=$RSU_RADIUS \
    --txAllVehicles=$TX_ALL \
    --attackMode=$ATTACK_MODE \
    --maliciousRate=$MAL_RATE \
    --enableReplayCheck=1 \
    --enableSigCheck=1 \
    --enableReports=$enableReports \
    --enableBlockchain=$enableBC \
    --enableTrustEngineFinal=$enableTE \
    --enableTrustGate=$enableGate \
    --enableRevocation=$enableRev \
    --revokeTrustThresh=0.20 \
    --revokeSyncIntervalMs=1000 \
    --csvOut=$out_csv \
    --eventsOut=$out_evt" >/dev/null

  echo "[OK] $tag" >&2
}

echo "[STEP] Baseline ablation sweep..." >&2
for nveh in $VEH_LIST_STR; do
  for spd in $SPD_LIST_STR; do
    for seed in $SEED_LIST_STR; do
      NS2="$REPO/sumo/output/grid/veh_${nveh}_spd_${spd}_seed_${seed}/ns2mobility.tcl"
      if [[ ! -s "$NS2" ]]; then
        echo "[SKIP] missing ns2: $NS2 (run sumo_pipeline first)" >&2
        continue
      fi
      for baseline in pki bc full; do
        run_one "$baseline" "$nveh" "$spd" "$seed" "$NS2"
      done
    done
  done
done

echo "[DONE] CSVs in: $RUNS" >&2
