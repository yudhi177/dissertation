#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/privacy_ablation_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
SIM=20

ATTACK_MODE=2
MAL_RATE=0.2

run_one () {
  local tag="$1"
  local seed="$2"

  local csv="/tmp/${tag}_seed${seed}.csv"
  local evt="/tmp/${tag}_seed${seed}_events.csv"
  local log="$RUNS/${tag}_seed${seed}.log"

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${csv} --eventsOut=${evt} \
    --seed=${seed} \
    --baselineName=UNSET \
    --enableTrustEngineFinal=1 --enableTrustGate=1 \
    --enableBlockchain=1 --enableBCLocalCache=1 \
    --enableBcProbe=1 --bcProbeIntervalMs=200 \
    --enableRevocation=1 \
    --attackMode=${ATTACK_MODE} --maliciousRate=${MAL_RATE} \
    --enablePrivacy=$3" | tee "$log"

  cp -f "$csv" "$RUNS/${tag}_seed${seed}.csv"
  cp -f "$evt" "$RUNS/${tag}_seed${seed}_events.csv"
  echo "[OK] ${tag}_seed${seed}"
}

for seed in "${SEEDS[@]}"; do
  run_one "FULL_NO_PRIVACY" "$seed" 0
  run_one "FULL_PRIVACY"    "$seed" 1
done

echo "[DONE] $RUNS"
