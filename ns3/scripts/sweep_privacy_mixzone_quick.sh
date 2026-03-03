#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/ns-3"

OUT="${1:-$HOME/dissertation/ns3/results/privacy_mixzone_sweep.csv}"
mkdir -p "$(dirname "$OUT")"
echo "mixRadiusM,rotations,linkAttempts,linkSuccess,linkSuccessRate,bcQueries,bcUpdates" > "$OUT"

for R in 20 50 80; do
  LOG=$(mktemp)
  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=40 \
    --csvOut=/tmp/priv_r${R}.csv \
    --eventsOut=/tmp/priv_r${R}_events.csv \
    --enablePrivacy=1 \
    --pseudoRotateIntervalS=5 \
    --linkWindowS=2 \
    --mixRadiusM=${R} \
    --rotateOnHandover=1 \
    --enableTrustEngineFinal=1" 2>&1 | tee "$LOG" >/dev/null

  PRIV=$(grep -m1 '^\[PRIV\]' "$LOG" || true)
  BC=$(grep -m1 '^\[BC\]' "$LOG" || true)
  rm -f "$LOG"

  rot=$(echo "$PRIV" | awk -F'rotations=' '{print $2}' | awk '{print $1}')
  la=$(echo "$PRIV" | awk -F'linkAttempts=' '{print $2}' | awk '{print $1}')
  ls=$(echo "$PRIV" | awk -F'linkSuccess=' '{print $2}' | awk '{print $1}')
  lsr=$(echo "$PRIV" | awk -F'linkSuccessRate=' '{print $2}' | awk '{print $1}')

  q=$(echo "$BC" | awk -F'queries=' '{print $2}' | awk '{print $1}')
  u=$(echo "$BC" | awk -F'updates=' '{print $2}' | awk '{print $1}')

  echo "${R},${rot:-0},${la:-0},${ls:-0},${lsr:-0},${q:-0},${u:-0}" >> "$OUT"
  echo "[OK] R=$R -> $PRIV"
done

echo "[DONE] wrote $OUT"
