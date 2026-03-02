#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"
PROGRAM="scratch/secure_trust_blockchain_v2x"

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT="$REPO/ns3/results/sybil_burst_sweep"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

VEH_LIST=(30 50 80)
SPD_LIST=(13.9)
SEED_LIST=(1 2 3 4 5)

BURST_LIST=(1 2 5 10)

# ONLY_ONE mode
if [[ "${ONLY_ONE:-0}" == "1" ]]; then
  VEH_LIST=("${NVEH:-30}")
  SPD_LIST=("${SPD:-13.9}")
  SEED_LIST=("${SEED:-1}")
  BURST_LIST=("${BURST:-2}")
fi

RSU_RADIUS=300
NRSU=4
TX_ALL=0

ATTACK_MODE=3
MAL_RATE=0.2
ATTACK_SEED=1

echo "[OK] Building ns-3..." >&2
cd "$NS3DIR"
./ns3 build >/dev/null

make_trace () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/sybil_burst/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local LOCAL_CFG="$RUN_DIR/run.sumocfg"
  mkdir -p "$RUN_DIR"

  # routes
  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" -o "$TRIPS" -r "$ROU" \
    --seed "$seed" --prefix veh --min-distance 50 --random >/dev/null

  # enforce vType + trim N vehicles
  python3 - <<PY >/dev/null
import xml.etree.ElementTree as ET
p="${ROU}"
tree=ET.parse(p); root=tree.getroot()
for vt in list(root.findall("vType")):
    if vt.get("id","") in ("veh_passenger","car"):
        root.remove(vt)
root.insert(0, ET.Element("vType", {
    "id":"veh_passenger","accel":"2.6","decel":"4.5","sigma":"0.5","length":"5","maxSpeed":"${spd}"
}))
for v in root.findall("vehicle"):
    v.set("type","veh_passenger")
vehicles = root.findall("vehicle")
for v in vehicles[int(${nveh}):]:
    root.remove(v)
tree.write(p)
PY

  # sumocfg
  cat > "$LOCAL_CFG" <<CFG
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

  # run sumo
  sumo -c "$LOCAL_CFG" --seed "$seed" >/dev/null
  grep -q "<vehicle" "$FCD" || { echo "[WARN] no vehicles in FCD for $TAG" >&2; return 1; }

  # fcd -> ns2
  python3 "$REPO/sumo/traci_controller.py" --fcd "$FCD" --out "$NS2" --limit "$nveh" >/dev/null
  test -s "$NS2" || { echo "[WARN] empty ns2 for $TAG" >&2; return 1; }

  echo "$NS2"
}

run_ns3 () {
  local ns2="$1"
  local nveh="$2"
  local burst="$3"
  local out_csv="$4"
  local out_evt="$5"

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$ns2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --nRsu=$NRSU \
    --rsuCoverageRadius=$RSU_RADIUS \
    --txAllVehicles=$TX_ALL \
    --enableReplayCheck=1 \
    --enableSigCheck=1 \
    --enableReports=1 \
    --enableBlockchain=1 \
    --enableTrustGate=1 \
    --attackMode=$ATTACK_MODE \
    --sybilBurst=$burst \
    --maliciousRate=$MAL_RATE \
    --attackSeed=$ATTACK_SEED \
    --csvOut=$out_csv \
    --eventsOut=$out_evt" >/dev/null
}

echo "[STEP] Sybil burst sweep..." >&2
for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPD_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      NS2="$(make_trace "$nveh" "$spd" "$seed")" || continue
      for burst in "${BURST_LIST[@]}"; do
        TAG="sybil_n${nveh}_s${spd}_seed${seed}_b${burst}"
        OUTCSV="$RUNS/${TAG}.csv"
        OUTEVT="$RUNS/${TAG}_events.csv"
        run_ns3 "$NS2" "$nveh" "$burst" "$OUTCSV" "$OUTEVT"
        echo "[OK] $TAG" >&2
      done
    done
  done
done

echo "[DONE] CSVs in: $RUNS" >&2
