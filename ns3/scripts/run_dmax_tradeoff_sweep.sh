#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/dmax_tradeoff"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
DMAX=(0 200 500 1000 2000 5000)
SIM=20
NVEH=60

common_args=(
  --baselineName=BC_TRUST
  --enableTrustEngineFinal=1 --enableTrustGate=1
  --enableBlockchain=1 --enableBCLocalCache=1
  --enableBcProbe=0
  --enablePrivacy=0 --enableRevocation=0
  --attackMode=2 --maliciousRate=0.2
  --trustSyncIntervalMs=5000
  --simTime=$SIM
  --nVehicles=$NVEH
)

for seed in "${SEEDS[@]}"; do
  for d in "${DMAX[@]}"; do
    tag="DMAX_${d}_seed${seed}"
    csv="/tmp/${tag}.csv"
    evt="/tmp/${tag}_events.csv"
    log="$RUNS/${tag}.log"

    ./ns3 run "scratch/secure_trust_blockchain_v2x \
      --csvOut=${csv} --eventsOut=${evt} --seed=${seed} \
      --trustMaxAgeMs=${d} \
      ${common_args[*]}" | tee "$log"

    cp -f "$csv" "$RUNS/${tag}.csv"
    cp -f "$evt" "$RUNS/${tag}_events.csv"
    echo "[OK] $tag"
  done
done

echo "[DONE] $RUNS"
