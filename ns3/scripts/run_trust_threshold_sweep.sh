#!/usr/bin/env bash
set -euo pipefail

NS3_DIR="$HOME/ns-3"
SCEN="bc_rsu_handover_trust_v2x"

OUT_BASE="$HOME/dissertation/ns3/results/sensitivity/trust_threshold/runs"

# Fixed parameters
NVEH=30
SIMTIME=20
CRYPTO_TX=200
CRYPTO_RX=200
MAL=0.2
BLOCK_INTERVAL=1000
MINE_DELAY=50
REPLAY=1
REPLAY_EVERY=300

FAST_LIST=("0.6" "0.7" "0.8" "0.9")
MIN_LIST=("0.2" "0.3" "0.4")
SEEDS=(1 2 3 4 5)

cd "$NS3_DIR"
ln -sf "$HOME/dissertation/ns3/scenarios/${SCEN}.cc" "scratch/${SCEN}.cc"
./ns3 build

for FAST in "${FAST_LIST[@]}"; do
  for MIN in "${MIN_LIST[@]}"; do

    # skip invalid combos where MIN >= FAST (causes weird policy behavior)
    python3 - <<PY
fast=float("${FAST}"); mn=float("${MIN}")
import sys
sys.exit(0 if mn < fast else 1)
PY
    if [ $? -ne 0 ]; then
      echo "Skipping invalid combo trustMinThresh=${MIN} >= trustFastThresh=${FAST}"
      continue
    fi

    for SEED in "${SEEDS[@]}"; do
      TAG="fast_${FAST}_min_${MIN}_seed_${SEED}"
      CSV_OUT="${OUT_BASE}/${TAG}.csv"
      EVT_OUT="${OUT_BASE}/${TAG}_events.csv"

      echo "Running: fast=${FAST}, min=${MIN}, seed=${SEED}"
      ./ns3 run "scratch/${SCEN} \
        --RngRun=${SEED} \
        --nVehicles=${NVEH} \
        --simTime=${SIMTIME} \
        --cryptoDelayUsTx=${CRYPTO_TX} \
        --cryptoDelayUsRx=${CRYPTO_RX} \
        --maliciousRate=${MAL} \
        --enableReplayAttack=${REPLAY} \
        --replayEveryMs=${REPLAY_EVERY} \
        --blockIntervalMs=${BLOCK_INTERVAL} \
        --mineDelayMs=${MINE_DELAY} \
        --trustFastThresh=${FAST} \
        --trustMinThresh=${MIN} \
        --csvOut=${CSV_OUT} \
        --eventsOut=${EVT_OUT}" >/dev/null
    done
  done
done

echo "DONE. Outputs in: ${OUT_BASE}"
