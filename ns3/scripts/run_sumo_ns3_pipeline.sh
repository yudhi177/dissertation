#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"

# Defaults (full batch)
VEH_LIST=(10 30 50 80)
SPEED_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

SIM_TIME="${SIM_TIME:-20}"
SUMO_STEP="${SUMO_STEP:-0.1}"

NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT_BASE="$REPO/ns3/results/sumo_pipeline"
RUNS_DIR="$OUT_BASE/runs"
mkdir -p "$RUNS_DIR"

PROGRAM="scratch/secure_trust_blockchain_v2x"

# If you run ONLY_ONE=1 NVEH=10 SPD=8.3 SEED=1 ...
if [[ "${ONLY_ONE:-0}" == "1" ]]; then
  VEH_LIST=("${NVEH:-10}")
  SPEED_LIST=("${SPD:-8.3}")
  SEED_LIST=("${SEED:-1}")
fi

echo "Building ns-3..."
cd "$NS3DIR"
./ns3 build >/dev/null

run_one () {
  local nveh="$1"
  local spd="$2"
  local seed="$3"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
  local RUN_DIR="$REPO/sumo/output/grid/${TAG}"
  local TRIPS="$RUN_DIR/trips.xml"
  local ROU="$RUN_DIR/routes.rou.xml"
  local FCD="$RUN_DIR/fcd.xml"
  local NS2="$RUN_DIR/ns2mobility.tcl"
  local LOCAL_CFG="$RUN_DIR/run.sumocfg"

  local OUT_RUN_CSV="$RUNS_DIR/${TAG}.csv"
  local OUT_RUN_EVT="$RUNS_DIR/${TAG}_events.csv"

  echo "=== RUN: $TAG ==="
  rm -rf "$RUN_DIR"
  mkdir -p "$RUN_DIR"

  # Period so we generate >= nveh vehicles within SIM_TIME
  local PERIOD
  PERIOD="$(python3 - <<PY
t=float("$SIM_TIME"); n=int("$nveh")
print(max(0.1, t/max(1,n)))
PY
)"

  # 1) Generate routes/trips
  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" \
    -o "$TRIPS" \
    -r "$ROU" \
    --seed "$seed" \
    --prefix veh \
    --random \
    -b 0 \
    -e "$SIM_TIME" \
    -p "$PERIOD" >/dev/null

  # 2) CLEAN routes.rou.xml:
  #    - remove ALL vType / vTypeDistribution (avoids duplicate veh_passenger)
  #    - add ONE vType: car (maxSpeed=spd)
  #    - set all vehicles type=car
  #    - trim to first nveh vehicles (safe XML)
  python3 - <<PY
import xml.etree.ElementTree as ET

p = r"$ROU"
n = int("$nveh")
spd = str("$spd")

tree = ET.parse(p)
root = tree.getroot()

# remove vType + vTypeDistribution to avoid SUMO "already exists" errors
for tag in ("vType", "vTypeDistribution"):
    for el in list(root.findall(tag)):
        root.remove(el)

# insert ONE vType 'car'
vtype = ET.Element("vType", {
    "id": "car",
    "accel": "2.6",
    "decel": "4.5",
    "sigma": "0.5",
    "length": "5",
    "maxSpeed": spd
})
root.insert(0, vtype)

# collect & trim vehicles
vehicles = root.findall("vehicle")
for v in vehicles[n:]:
    root.remove(v)

vehicles = root.findall("vehicle")
for v in vehicles:
    v.set("type", "car")  # force single known type

tree.write(p, encoding="utf-8", xml_declaration=True)
print("[OK] cleaned vTypes + kept first", len(vehicles), "vehicles")
PY

  # 3) Local sumocfg
  cat > "$LOCAL_CFG" <<CFG
<configuration>
  <input>
    <net-file value="$NET_XML"/>
    <route-files value="$ROU"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="$SIM_TIME"/>
    <step-length value="$SUMO_STEP"/>
  </time>
  <output>
    <fcd-output value="$FCD"/>
  </output>
</configuration>
CFG

  # 4) Run SUMO
  sumo -c "$LOCAL_CFG" --seed "$seed" >/dev/null

  # validate FCD
  grep -q "<timestep" "$FCD" || { echo "[ERR] FCD has no timesteps (SUMO failed)"; return 1; }
  grep -q "<vehicle"  "$FCD" || { echo "[ERR] FCD has no vehicles (depart times/period issue)"; return 1; }

  # 5) Convert FCD -> ns2 mobility (limit = nveh)
  python3 "$REPO/sumo/traci_controller.py" \
    --fcd "$FCD" \
    --out "$NS2" \
    --limit "$nveh" >/dev/null

  test -s "$NS2" || { echo "[ERR] ns2mobility empty"; return 1; }

  # 6) Run ns-3 (NO extra "--" token)
  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$NS2 \
    --simTime=$SIM_TIME \
    --rsuCoverageRadius=300 \
      --nRsu=4 \
    --nVehicles=$nveh \
    --csvOut=$OUT_RUN_CSV \
    --eventsOut=$OUT_RUN_EVT" >/dev/null

  test -s "$OUT_RUN_CSV" || { echo "[ERR] ns-3 CSV not generated"; return 1; }
  echo "[OK] CSV: $OUT_RUN_CSV"
}

for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPEED_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      run_one "$nveh" "$spd" "$seed"
    done
  done
done

echo "DONE. CSVs in: $RUNS_DIR"