#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/baseline_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
SIM=20

# Common threat setting (same across baselines for fair ablation)
ATTACK_MODE=2
MAL_RATE=0.2

run_one () {
  local b="$1"
  local seed="$2"

  local csv="/tmp/${b}_seed${seed}.csv"
  local evt="/tmp/${b}_seed${seed}_events.csv"
  local log="$RUNS/${b}_seed${seed}.log"

  local trustFinal=0 trustGate=0 bc=0 cache=0 bcProbe=0 priv=0 rev=0
  local bcProbeInt=200

  case "$b" in
    PKI_ONLY)
      trustFinal=0; trustGate=0; bc=0; cache=0; bcProbe=0; priv=0; rev=0
      ;;
    TRUST_ONLY)
      trustFinal=1; trustGate=1; bc=0; cache=0; bcProbe=0; priv=0; rev=0
      ;;
    BC_TRUST)
      trustFinal=1; trustGate=1; bc=1; cache=1; bcProbe=0; priv=0; rev=0
      ;;
    BC_ALWAYS_QUERY)
      trustFinal=1; trustGate=1; bc=1; cache=0; bcProbe=1; priv=0; rev=0
      ;;
    FULL)
      trustFinal=1; trustGate=1; bc=1; cache=1; bcProbe=1; priv=1; rev=1
      ;;
    *)
      echo "[ERR] unknown baseline: $b" >&2
      exit 1
      ;;
  esac

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${csv} --eventsOut=${evt} \
    --baselineName=${b} --seed=${seed} \
    --enableTrustEngineFinal=${trustFinal} --enableTrustGate=${trustGate} \
    --enableBlockchain=${bc} --enableBCLocalCache=${cache} \
    --enableBcProbe=${bcProbe} --bcProbeIntervalMs=${bcProbeInt} \
    --enablePrivacy=${priv} --enableRevocation=${rev} \
    --attackMode=${ATTACK_MODE} --maliciousRate=${MAL_RATE}" | tee "$log"

  cp -f "$csv" "$RUNS/${b}_seed${seed}.csv"
  cp -f "$evt" "$RUNS/${b}_seed${seed}_events.csv"
  echo "[OK] ${b}_seed${seed}"
}

BASELINES=(PKI_ONLY TRUST_ONLY BC_TRUST BC_ALWAYS_QUERY FULL)

for b in "${BASELINES[@]}"; do
  for seed in "${SEEDS[@]}"; do
    run_one "$b" "$seed"
  done
done

echo "[DONE] $RUNS"
