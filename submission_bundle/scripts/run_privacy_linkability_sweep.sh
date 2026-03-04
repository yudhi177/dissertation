#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"
NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

OUT="$REPO/ns3/results/privacy_linkability_sweep"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

# --------- IMPORTANT ----------
# Use *_STR variables for lists (space-separated), e.g.
# VEH_LIST_STR="30" SEED_LIST_STR="1"
# -----------------------------
VEH_LIST_STR="${VEH_LIST_STR:-"30 50 80"}"
SPD_LIST_STR="${SPD_LIST_STR:-"13.9"}"
SEED_LIST_STR="${SEED_LIST_STR:-"1 2 3 4 5"}"

ROT_LIST_STR="${ROT_LIST_STR:-"2 5 10"}"       # seconds
RSU_ROT_LIST_STR="${RSU_ROT_LIST_STR:-"0 1"}"  # 0/1

PSEUDO_POOL="${PSEUDO_POOL:-5}"

# Attacks OFF (clean privacy evaluation)
ATTACK_MODE="${ATTACK_MODE:-0}"
MAL_RATE="${MAL_RATE:-0.0}"
ENABLE_REPLAY_ATTACK="${ENABLE_REPLAY_ATTACK:-0}"

RSU_RADIUS="${RSU_RADIUS:-300}"
TX_ALL="${TX_ALL:-0}"

# convert strings -> arrays
IFS=' ' read -r -a VEH_LIST <<< "$VEH_LIST_STR"
IFS=' ' read -r -a SPD_LIST <<< "$SPD_LIST_STR"
IFS=' ' read -r -a SEED_LIST <<< "$SEED_LIST_STR"
IFS=' ' read -r -a ROT_LIST <<< "$ROT_LIST_STR"
IFS=' ' read -r -a RSU_ROT_LIST <<< "$RSU_ROT_LIST_STR"

need () { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] missing command: $1" >&2; exit 1; }; }
need python3
need sumo

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

make_trace () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  # hard validation (prevents '(1)' type bugs)
  [[ "$seed" =~ ^[0-9]+$ ]] || { echo "[ERR] seed must be int, got: $seed" >&2; return 1; }

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/privacy_sweep/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local CFG="$RUN_DIR/run.sumocfg"
  mkdir -p "$RUN_DIR"

  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" -o "$TRIPS" -r "$ROU" \
    --seed "$seed" --prefix veh --min-distance 50 --random >/dev/null

  # Clean vTypes + force first nveh vehicles + set maxSpeed
  python3 - <<PY >/dev/null
import xml.etree.ElementTree as ET
p="${ROU}"
tree=ET.parse(p); root=tree.getroot()

for vt in list(root.findall("vType")):
    if vt.get("id","") in ("veh_passenger","car"):
        root.remove(vt)

root.insert(0, ET.Element("vType", {
    "id":"veh_passenger","accel":"2.6","decel":"4.5","sigma":"0.5","length":"5",
    "maxSpeed":"${spd}"
}))

for v in root.findall("vehicle"):
    v.set("type","veh_passenger")

vehicles = root.findall("vehicle")
for v in vehicles[int(${nveh}):]:
    root.remove(v)

tree.write(p)
PY

  cat > "$CFG" <<CFG
<configuration>
  <input>
    <net-file value="$NET_XML"/>
    <route-files value="$ROU"/>
  </input>
  <time>
    <step-length value="$SUMO_STEP"/>
  </time>
  <output>
    <fcd-output value="$FCD"/>
  </output>
</configuration>
CFG

  sumo -c "$CFG" --seed "$seed" >/dev/null
  grep -q "<vehicle" "$FCD" || { echo "[WARN] no vehicles in FCD for $TAG" >&2; return 1; }

  python3 "$REPO/sumo/traci_controller.py" --fcd "$FCD" --out "$NS2" --limit "$nveh" >/dev/null
  test -s "$NS2" || { echo "[WARN] empty ns2 for $TAG" >&2; return 1; }

  echo "$NS2"
}

run_ns3 () {
  local ns2="$1"
  local nveh="$2"
  local rotSec="$3"
  local rsuRot="$4"
  local out_csv="$5"
  local out_evt="$6"

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$ns2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --rsuCoverageRadius=$RSU_RADIUS \
    --txAllVehicles=$TX_ALL \
    --attackMode=$ATTACK_MODE \
    --maliciousRate=$MAL_RATE \
    --enableReplayAttack=$ENABLE_REPLAY_ATTACK \
    --enableReplayCheck=1 \
    --enableSigCheck=1 \
    --enableReports=1 \
    --enableBlockchain=1 \
    --enableTrustGate=1 \
    --enableTrustEngineFinal=1 \
    --enablePrivacy=1 \
    --pseudoPoolSize=$PSEUDO_POOL \
    --pseudoRotateSec=$rotSec \
    --rotateOnRsuChange=$rsuRot \
    --csvOut=$out_csv \
    --eventsOut=$out_evt" >/dev/null
}

echo "[STEP] Privacy linkability sweep..." >&2

for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPD_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
      for rot in "${ROT_LIST[@]}"; do
        for rsuRot in "${RSU_ROT_LIST[@]}"; do
          TAG="priv_n${nveh}_s${spd}_seed${seed}_rot${rot}_rsu${rsuRot}_pool${PSEUDO_POOL}"
          OUTCSV="$RUNS/${TAG}.csv"
          OUTEVT="$RUNS/${TAG}_events.csv"
          run_ns3 "$NS2" "$nveh" "$rot" "$rsuRot" "$OUTCSV" "$OUTEVT"
          echo "[OK] $TAG" >&2
        done
      done
    done
  done
done

echo "[DONE] CSVs in: $RUNS" >&2
