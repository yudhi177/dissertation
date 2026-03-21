#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/phase5_fp_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
SIM=20

# BAD CHANNEL knobs (congestion proxy)
PAYLOAD=512
INTERVAL=30

run_one () {
  local tag="$1"
  local seed="$2"
  local conf="$3"
  local fair="$4"

  csv="/tmp/${tag}_seed${seed}.csv"
  evt="/tmp/${tag}_seed${seed}_events.csv"
  log="$RUNS/${tag}_seed${seed}.log"

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${csv} --eventsOut=${evt} \
    --seed=${seed} \
    --baselineName=TRUST_ONLY \
    --enableTrustEngineFinal=1 --enableTrustGate=1 \
    --attackMode=0 --maliciousRate=0.0 \
    --payloadSize=${PAYLOAD} --intervalMs=${INTERVAL} \
    --enableTrustConfidence=${conf} \
    --enableChannelFairness=${fair} \
    --badChannelLossThresh=0.10 \
    --fairnessPenaltyScaleBad=0.25" | tee "$log"

  cp -f "$csv" "$RUNS/${tag}_seed${seed}.csv" || true
  cp -f "$evt" "$RUNS/${tag}_seed${seed}_events.csv" || true
  echo "[OK] ${tag}_seed${seed}"
}

for seed in "${SEEDS[@]}"; do
  run_one "NOATTACK_BADCH_BASE" "$seed" 0 0
  run_one "NOATTACK_BADCH_CONF" "$seed" 1 0
  run_one "NOATTACK_BADCH_CONF_FAIR" "$seed" 1 1
done

echo "[DONE] $RUNS"
