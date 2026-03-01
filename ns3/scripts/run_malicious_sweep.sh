#!/usr/bin/env bash
set -euo pipefail

NS3_DIR="$HOME/ns-3"
SCEN="bc_rsu_handover_trust_v2x"

OUT_BASE="$HOME/dissertation/ns3/results/sensitivity/malicious_rate/runs"

# Fixed parameters for this sweep
NVEH=30
SIMTIME=20
CRYPTO_TX=200
CRYPTO_RX=200
BLOCK_INTERVAL=1000
MINE_DELAY=50
REPLAY=1
REPLAY_EVERY=300
TRUST_FAST=0.7
TRUST_MIN=0.3

MAL_LIST=("0.0" "0.1" "0.2" "0.4" "0.6" "0.8")
SEEDS=(1 2 3 4 5)

echo "Linking scenario into ns-3 scratch..."
cd "$NS3_DIR"
ln -sf "$HOME/dissertation/ns3/scenarios/${SCEN}.cc" "scratch/${SCEN}.cc"

echo "Building ns-3..."
./ns3 build

for MAL in "${MAL_LIST[@]}"; do
  for SEED in "${SEEDS[@]}"; do
    TAG="mal_${MAL}_seed_${SEED}"
    CSV_OUT="${OUT_BASE}/${TAG}.csv"
    EVT_OUT="${OUT_BASE}/${TAG}_events.csv"

    echo "Running: maliciousRate=${MAL}, seed=${SEED}"
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
      --trustFastThresh=${TRUST_FAST} \
      --trustMinThresh=${TRUST_MIN} \
      --csvOut=${CSV_OUT} \
      --eventsOut=${EVT_OUT}" >/dev/null

    # quick sanity check
    if [ ! -f "$CSV_OUT" ]; then
      echo "ERROR: Missing output $CSV_OUT"
      exit 1
    fi
  done
done

echo "DONE. Outputs in: ${OUT_BASE}"
