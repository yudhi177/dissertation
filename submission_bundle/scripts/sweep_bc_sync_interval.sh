#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/ns-3"
OUT="${1:-$HOME/dissertation/ns3/results/bc_sync_sweep.csv}"
mkdir -p "$(dirname "$OUT")"
echo "syncIntervalMs,queries,updates,cacheHits,cacheMisses,hitRate,avgQms,avgUms" > "$OUT"

for si in 100 250 500 1000 2000; do
  LOG=$(mktemp)

  ./ns3 run "scratch/secure_trust_blockchain_v2x \
    --simTime=30 \
    --csvOut=/tmp/bc_si_${si}.csv \
    --eventsOut=/tmp/bc_si_${si}_events.csv \
    --enableTrustEngineFinal=1 \
    --attackMode=2 --maliciousRate=0.2 \
    --enableBCLocalCache=1 \
    --cacheTtlMs=2000 \
    --bcSyncIntervalMs=${si} \
    --bcQueryDelayMs=12 \
    --bcUpdateDelayMs=18 \
    --txAllVehicles=1" 2>&1 | tee "$LOG" >/dev/null

  line=$(grep -m1 '^\[BC\]' "$LOG" || true)
  rm -f "$LOG"

  if [[ -z "$line" ]]; then
    echo "[WARN] no [BC] line for sync=$si"
    continue
  fi

  q=$(echo "$line" | awk -F'queries=' '{print $2}' | awk '{print $1}')
  u=$(echo "$line" | awk -F'updates=' '{print $2}' | awk '{print $1}')
  ch=$(echo "$line" | awk -F'cacheHits=' '{print $2}' | awk '{print $1}')
  cm=$(echo "$line" | awk -F'cacheMisses=' '{print $2}' | awk '{print $1}')
  hr=$(echo "$line" | awk -F'hitRate=' '{print $2}' | awk '{print $1}')
  aq=$(echo "$line" | awk -F'avgQms=' '{print $2}' | awk '{print $1}')
  au=$(echo "$line" | awk -F'avgUms=' '{print $2}' | awk '{print $1}')

  echo "${si},${q},${u},${ch},${cm},${hr},${aq},${au}" >> "$OUT"
  echo "[OK] sync=$si -> $line"
done

echo "[DONE] wrote $OUT"
