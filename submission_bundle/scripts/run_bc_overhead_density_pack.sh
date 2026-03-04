#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/bc_overhead_density_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

BASELINES=(BC_TRUST BC_ALWAYS_QUERY FULL)
SEEDS=(1 2 3 4 5)

# Density sweep (no speed flag exists)
NVEHS=(30 60 90)
SIM=20

for b in "${BASELINES[@]}"; do
  for n in "${NVEHS[@]}"; do
    for seed in "${SEEDS[@]}"; do
      tag="${b}_n${n}_seed${seed}"
      csv="/tmp/${tag}.csv"
      evt="/tmp/${tag}_events.csv"
      log="$RUNS/${tag}.log"

      # baseline-specific flags (to satisfy baseline assertions)
      extra=()
      if [[ "$b" == "BC_TRUST" ]]; then
        extra+=(--enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1)
        extra+=(--enablePrivacy=0 --enableRevocation=0)
      elif [[ "$b" == "BC_ALWAYS_QUERY" ]]; then
        extra+=(--enableBlockchain=1 --enableBCLocalCache=0 --enableBcProbe=1)
        extra+=(--enablePrivacy=0 --enableRevocation=0)
      elif [[ "$b" == "FULL" ]]; then
        extra+=(--enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1)
        extra+=(--enablePrivacy=1 --enableRevocation=1)
      fi

      ./ns3 run "scratch/secure_trust_blockchain_v2x \
        --simTime=${SIM} --nVehicles=${n} \
        --csvOut=${csv} --eventsOut=${evt} \
        --baselineName=${b} --seed=${seed} \
        --enableTrustEngineFinal=1 --enableTrustGate=1 \
        --attackMode=2 --maliciousRate=0.2 \
        --bcProbeIntervalMs=200 \
        ${extra[*]}" | tee "$log"

      cp -f "$csv" "$RUNS/${tag}.csv"
      cp -f "$evt" "$RUNS/${tag}_events.csv"
      echo "[OK] $tag"
    done
  done
done

echo "[DONE] $RUNS"
