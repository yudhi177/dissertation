#!/usr/bin/env bash
set -euo pipefail
cd ~/ns-3

OUTD="$HOME/dissertation/ns3/results/revocation_pack"
RUNS="$OUTD/runs"
mkdir -p "$RUNS" "$OUTD/summary" "$OUTD/plots"

SEEDS=(1 2 3 4 5)
SIM=25

for seed in "${SEEDS[@]}"; do
  tag="FULL_revoke_seed${seed}"
  csv="/tmp/${tag}.csv"
  evt="/tmp/${tag}_events.csv"
  log="$RUNS/${tag}.log"

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=${SIM} \
    --csvOut=${csv} --eventsOut=${evt} \
    --baselineName=FULL --seed=${seed} \
    --enableTrustEngineFinal=1 --enableTrustGate=1 \
    --enableBlockchain=1 --enableBCLocalCache=1 \
    --enableBcProbe=1 --bcProbeIntervalMs=200 \
    --enableRevocation=1 --revokeSyncIntervalMs=500 \
    --enablePrivacy=1 \
    --forceRevokeVehicle0=1 --forceRevokeTime=2.0" | tee "$log"

  cp -f "$csv" "$RUNS/${tag}.csv"
  cp -f "$evt" "$RUNS/${tag}_events.csv"

  python3 "$HOME/dissertation/ns3/scripts/compute_revocation_cdf.py" \
    "$RUNS/${tag}_events.csv" "$RUNS/${tag}_cdf.csv"

  python3 "$HOME/dissertation/ns3/scripts/compute_detection_fp_stats.py" \
    "$RUNS/${tag}_events.csv" "$RUNS/${tag}_detect_fp.csv"

  echo "[OK] $tag"
done

echo "[DONE] $RUNS"
