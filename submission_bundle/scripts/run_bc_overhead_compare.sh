#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/bc_overhead_compare"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

BASELINES=(BC_TRUST BC_ALWAYS_QUERY FULL)
SEEDS=(1 2 3 4 5)
SPEEDS=(10 20)
SIM=20
NVEH=60

for b in "${BASELINES[@]}"; do
  for spd in "${SPEEDS[@]}"; do
    for seed in "${SEEDS[@]}"; do
      tag="${b}_spd${spd}_seed${seed}"
      csv="/tmp/${tag}.csv"
      evt="/tmp/${tag}_events.csv"
      log="$RUNS/${tag}.log"

      ./ns3 run "scratch/secure_trust_blockchain_v2x \
        --simTime=${SIM} --nVehicles=${NVEH} \
        --csvOut=${csv} --eventsOut=${evt} \
        --baselineName=${b} --seed=${seed} \
        --speed=${spd} \
        --enableTrustEngineFinal=1 --enableTrustGate=1 \
        --attackMode=2 --maliciousRate=0.2" | tee "$log"

      cp -f "$csv" "$RUNS/${tag}.csv"
      cp -f "$evt" "$RUNS/${tag}_events.csv"
      echo "[OK] $tag"
    done
  done
done

echo "[DONE] $RUNS"
