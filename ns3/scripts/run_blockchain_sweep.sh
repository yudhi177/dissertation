#!/usr/bin/env bash
set -euo pipefail

NS3_DIR="$HOME/ns-3"
SCEN="bc_rsu_handover_trust_v2x"
OUT_BASE="$HOME/dissertation/ns3/results/sensitivity/blockchain/runs"

NVEH=30
SIMTIME=20
CRYPTO_TX=200
CRYPTO_RX=200
MAL=0.2
FAST=0.7
MIN=0.3

BLOCK_LIST=("250" "500" "1000" "2000")
MINE_LIST=("10" "50" "120")
SEEDS=(1 2 3 4 5)

cd "$NS3_DIR"
ln -sf "$HOME/dissertation/ns3/scenarios/${SCEN}.cc" "scratch/${SCEN}.cc"
./ns3 build

for BLOCK in "${BLOCK_LIST[@]}"; do
  for MINE in "${MINE_LIST[@]}"; do
    for SEED in "${SEEDS[@]}"; do

      TAG="block_${BLOCK}_mine_${MINE}_seed_${SEED}"
      CSV_OUT="${OUT_BASE}/${TAG}.csv"
      EVT_OUT="${OUT_BASE}/${TAG}_events.csv"

      echo "Running: block=${BLOCK}, mine=${MINE}, seed=${SEED}"

      ./ns3 run "scratch/${SCEN} \
        --RngRun=${SEED} \
        --nVehicles=${NVEH} \
        --simTime=${SIMTIME} \
        --cryptoDelayUsTx=${CRYPTO_TX} \
        --cryptoDelayUsRx=${CRYPTO_RX} \
        --maliciousRate=${MAL} \
        --trustFastThresh=${FAST} \
        --trustMinThresh=${MIN} \
        --blockIntervalMs=${BLOCK} \
        --mineDelayMs=${MINE} \
        --csvOut=${CSV_OUT} \
        --eventsOut=${EVT_OUT}" >/dev/null

    done
  done
done

echo "DONE. Outputs in: ${OUT_BASE}"
