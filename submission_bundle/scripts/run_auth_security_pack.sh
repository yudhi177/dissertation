#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/auth_security_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
SIM=20

SCEN_NAMES=(AUTH_OK AUTH_MITM AUTH_REPLAY)
MITM=(0 1 0)
REPLAY=(0 0 1)

common_args=(
  --attackMode=0 --enableReplayAttack=0 --enableReports=0
  --enableTrustGate=0 --enableTrustEngineFinal=0
  --enableBlockchain=0 --enableBcProbe=0
  --enablePrivacy=0 --enableRevocation=0
  --enableAuthBind=1
  --enableAuthProbe=1 --authProbeIntervalMs=200
)

for i in "${!SCEN_NAMES[@]}"; do
  scen="${SCEN_NAMES[$i]}"
  mitm="${MITM[$i]}"
  replay="${REPLAY[$i]}"

  for seed in "${SEEDS[@]}"; do
    tag="${scen}_seed${seed}"
    csv="/tmp/${tag}.csv"
    evt="/tmp/${tag}_events.csv"
    log="$RUNS/${tag}.log"

    ./ns3 run "scratch/secure_trust_blockchain_v2x \
      --simTime=${SIM} \
      --csvOut=${csv} --eventsOut=${evt} \
      --seed=${seed} \
      --enableMitmAttack=${mitm} \
      --enableAuthReplayAttack=${replay} --authReplayEveryN=3 \
      ${common_args[*]}" | tee "$log"

    cp -f "$csv" "$RUNS/${tag}.csv"
    cp -f "$evt" "$RUNS/${tag}_events.csv"
    echo "[OK] $tag"
  done
done

echo "[DONE] $RUNS"
