#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/bc_probe_intensity_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

BASELINES=(BC_TRUST BC_ALWAYS_QUERY)
SEEDS=(1 2 3 4 5)

NVEH=60
SIM=20
PROBES=(100 200 500 1000)

for b in "${BASELINES[@]}"; do
  for p in "${PROBES[@]}"; do
    for seed in "${SEEDS[@]}"; do
      tag="${b}_probe${p}_seed${seed}"
      csv="/tmp/${tag}.csv"
      evt="/tmp/${tag}_events.csv"
      log="$RUNS/${tag}.log"

      extra=()
      if [[ "$b" == "BC_TRUST" ]]; then
        extra+=(--enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1)
      else
        extra+=(--enableBlockchain=1 --enableBCLocalCache=0 --enableBcProbe=1)
      fi

      ./ns3 run "scratch/secure_trust_blockchain_v2x \
        --simTime=${SIM} --nVehicles=${NVEH} \
        --csvOut=${csv} --eventsOut=${evt} \
        --baselineName=${b} --seed=${seed} \
        --enableTrustEngineFinal=1 --enableTrustGate=1 \
        --attackMode=2 --maliciousRate=0.2 \
        --bcProbeIntervalMs=${p} \
        ${extra[*]}" | tee "$log"

      cp -f "$csv" "$RUNS/${tag}.csv"
      cp -f "$evt" "$RUNS/${tag}_events.csv"
      echo "[OK] $tag"
    done
  done
done

echo "[DONE] $RUNS"
