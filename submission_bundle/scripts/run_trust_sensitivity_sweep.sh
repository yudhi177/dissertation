#!/usr/bin/env bash
set -euo pipefail

cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/trust_sensitivity_sweep"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

MODE="${1:-quick}"   # quick | full
SEEDS=(1 2 3 4 5)
SIM=20
NVEH=60

if [[ "$MODE" == "full" ]]; then
  SEEDS=(1 2 3 4 5 6 7 8 9 10)
  SIM=30
  NVEH=80
fi

common_args=(
  --baselineName=TRUST_ONLY
  --enableTrustEngineFinal=1
  --enableTrustGate=1
  --enableBlockchain=0
  --enableBCLocalCache=0
  --enableBcProbe=0
  --enablePrivacy=0
  --enableRevocation=0
  --attackMode=2
  --maliciousRate=0.2
  --simTime=$SIM
  --nVehicles=$NVEH
)

run_one () {
  local sweep="$1"
  local key="$2"
  local val="$3"
  local seed="$4"

  local tag="${sweep}_${key}_${val}_seed${seed}"
  local csv="/tmp/${tag}.csv"
  local evt="/tmp/${tag}_events.csv"

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --csvOut=${csv} --eventsOut=${evt} --seed=${seed} \
    ${common_args[*]} --${key}=${val}"

  cp -f "$csv" "$RUNS/${tag}.csv"
  cp -f "$evt" "$RUNS/${tag}_events.csv"
  echo "[OK] $tag"
}

# ---- Sweeps ----
# 1) FAST threshold
for s in "${SEEDS[@]}"; do
  for v in 0.60 0.70 0.80; do
    run_one "S1_FAST" "trustFastThresh" "$v" "$s"
  done
done

# 2) MIN threshold
for s in "${SEEDS[@]}"; do
  for v in 0.20 0.30 0.40; do
    run_one "S2_MIN" "trustMinThresh" "$v" "$s"
  done
done

# 3) decay
for s in "${SEEDS[@]}"; do
  for v in 0.001 0.002 0.005; do
    run_one "S3_DECAY" "trustDecayPerSec" "$v" "$s"
  done
done

# 4) recovery
for s in "${SEEDS[@]}"; do
  for v in 0.005 0.010 0.020; do
    run_one "S4_RECOV" "recoveryPerSec" "$v" "$s"
  done
done

# 5) weights (3 fixed combos)
for s in "${SEEDS[@]}"; do
  run_one "S5_W" "w1Base" "0.50" "$s"
  run_one "S5_W" "w2Base" "0.30" "$s"
  run_one "S5_W" "w3Base" "0.20" "$s"
done

# 6) confidence gate
for s in "${SEEDS[@]}"; do
  for v in 0.40 0.60 0.80; do
    run_one "S6_CONF" "confMinForFast" "$v" "$s"
  done
done

echo "[DONE] Runs in $RUNS"
