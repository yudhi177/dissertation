#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/baseline_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS"

SEEDS=(1 2 3 4 5)
SIM=20
NVEH=60

common_no_attack=(
  --simTime=$SIM
  --nVehicles=$NVEH
  --attackMode=0
  --maliciousRate=0.0
  --enableReplayAttack=0
)

run_one () {
  local b="$1"
  local seed="$2"
  local tag="${b}_seed${seed}"
  local csv="/tmp/${tag}.csv"
  local evt="/tmp/${tag}_events.csv"
  local log="$RUNS/${tag}.log"

  # baseline-specific switches (MUST match baseline asserts)
  local extra=()
  case "$b" in
    PKI_ONLY)
      extra+=( --enableTrustEngineFinal=0 --enableTrustGate=0 )
      extra+=( --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 )
      extra+=( --enablePrivacy=0 --enableRevocation=0 )
      ;;
    TRUST_ONLY)
      extra+=( --enableTrustEngineFinal=1 --enableTrustGate=1 )
      extra+=( --enableBlockchain=0 --enableBCLocalCache=0 --enableBcProbe=0 )
      extra+=( --enablePrivacy=0 --enableRevocation=0 )
      ;;
    BC_TRUST)
      extra+=( --enableTrustEngineFinal=1 --enableTrustGate=1 )
      extra+=( --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=0 )
      extra+=( --enablePrivacy=0 --enableRevocation=0 )
      ;;
    BC_ALWAYS_QUERY)
      extra+=( --enableTrustEngineFinal=1 --enableTrustGate=1 )
      extra+=( --enableBlockchain=1 --enableBCLocalCache=0 --enableBcProbe=1 --bcProbeIntervalMs=200 )
      extra+=( --enablePrivacy=0 --enableRevocation=0 )
      ;;
    FULL)
      extra+=( --enableTrustEngineFinal=1 --enableTrustGate=1 )
      extra+=( --enableBlockchain=1 --enableBCLocalCache=1 --enableBcProbe=1 --bcProbeIntervalMs=200 )
      extra+=( --enablePrivacy=1 --enableRevocation=1 )
      ;;
    *)
      echo "[ERR] unknown baseline: $b" >&2
      exit 1
      ;;
  esac

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --baselineName=${b} --seed=${seed} \
    --csvOut=${csv} --eventsOut=${evt} \
    ${common_no_attack[*]} \
    ${extra[*]}" | tee "$log"

  cp -f "$csv" "$RUNS/${tag}.csv"
  cp -f "$evt" "$RUNS/${tag}_events.csv"
  echo "[OK] $tag"
}

BASELINES=(PKI_ONLY TRUST_ONLY BC_TRUST BC_ALWAYS_QUERY FULL)

for b in "${BASELINES[@]}"; do
  for seed in "${SEEDS[@]}"; do
    run_one "$b" "$seed"
  done
done

echo "[DONE] $RUNS"
