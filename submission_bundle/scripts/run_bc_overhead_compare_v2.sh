#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/bc_overhead_compare_v2"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

BASELINES=(BC_TRUST BC_ALWAYS_QUERY FULL)
SEEDS=(1 2 3 4 5)
PROBE_MS=(100 200 500)
SIM=20
NVEH=60

# common safety defaults
COMMON=(
  --simTime=${SIM}
  --nVehicles=${NVEH}
  --enableTrustEngineFinal=1
  --enableTrustGate=1
  --attackMode=2
  --maliciousRate=0.2
  --enableBlockchain=1
  --enableBcProbe=1
)

for b in "${BASELINES[@]}"; do
  for pi in "${PROBE_MS[@]}"; do
    for seed in "${SEEDS[@]}"; do
      tag="${b}_probe${pi}_seed${seed}"
      csv="/tmp/${tag}.csv"
      evt="/tmp/${tag}_events.csv"
      log="$RUNS/${tag}.log"

      extra=()

      if [[ "$b" == "BC_TRUST" ]]; then
        extra+=( --baselineName=BC_TRUST --enableBCLocalCache=1 --enablePrivacy=0 --enableRevocation=0 )
      elif [[ "$b" == "BC_ALWAYS_QUERY" ]]; then
        extra+=( --baselineName=BC_ALWAYS_QUERY --enableBCLocalCache=0 --enablePrivacy=0 --enableRevocation=0 )
      elif [[ "$b" == "FULL" ]]; then
        # FULL baseline assertions require BOTH privacy + revocation ON
        extra+=( --baselineName=FULL --enableBCLocalCache=1 --enablePrivacy=1 --enableRevocation=1 )
      fi

      ./ns3 run "scratch/secure_trust_blockchain_v2x \
        --csvOut=${csv} --eventsOut=${evt} \
        --seed=${seed} \
        --bcProbeIntervalMs=${pi} \
        ${COMMON[*]} ${extra[*]}" | tee "$log"

      cp -f "$csv" "$RUNS/${tag}.csv"
      cp -f "$evt" "$RUNS/${tag}_events.csv"
      echo "[OK] $tag"
    done
  done
done

echo "[DONE] $RUNS"
