#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"

# Base grid
VEH_LIST=(10 30 50 80)
SPEED_LIST=(8.3 13.9 22.2)
SEED_LIST=(1 2 3 4 5)

# Sweeps (paper set)
MAL_LIST=(0.0 0.1 0.2 0.4)
FAST_LIST=(0.6 0.7 0.8)
MIN_LIST=(0.2 0.3 0.4)

SIM_TIME=20
SUMO_STEP=0.1
NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT_BASE="$REPO/ns3/results/sumo_pipeline_sweep"
RUNS_DIR="$OUT_BASE/runs"
mkdir -p "$RUNS_DIR"

PROGRAM="scratch/secure_trust_blockchain_v2x"

cd "$NS3DIR"
./ns3 build >/dev/null

run_one () {
  local nveh="$1"; local spd="$2"; local seed="$3"
  local mal="$4"; local tf="$5"; local tm="$6"

  local TAG="veh_${nveh}_spd_${spd}_seed_${seed}_mal_${mal}_tf_${tf}_tm_${tm}"
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

  # Generate routes
  local PERIOD
  PERIOD="$(python3 - <<PY
t=float("$SIM_TIME"); n=int("$nveh")
print(max(0.1, t/max(1,n)))
PY
)"

  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" -o "$TRIPS" -r "$ROU" \
    --seed "$seed" --prefix veh --random \
    -b 0 -e "$SIM_TIME" -p "$PERIOD" >/dev/null

  # Clean vTypes + force car + trim vehicles safely
  python3 - <<PY
import xml.etree.ElementTree as ET
p=r"$ROU"; n=int("$nveh"); spd=str("$spd")
tree=ET.parse(p); root=tree.getroot()
for tag in ("vType","vTypeDistribution"):
  for el in list(root.findall(tag)):
    root.remove(el)
vtype=ET.Element("vType", {"id":"car","accel":"2.6","decel":"4.5","sigma":"0.5","length":"5","maxSpeed":spd})
root.insert(0, vtype)
vehicles=root.findall("vehicle")
for v in vehicles[n:]:
  root.remove(v)
for v in root.findall("vehicle"):
  v.set("type","car")
tree.write(p, encoding="utf-8", xml_declaration=True)
print("[OK] routes cleaned + kept", min(len(vehicles), n))
PY

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

  sumo -c "$LOCAL_CFG" --seed "$seed" >/dev/null
  grep -q "<vehicle" "$FCD" || { echo "[WARN] No vehicles in FCD"; return 0; }

  python3 "$REPO/sumo/traci_controller.py" --fcd "$FCD" --out "$NS2" --limit "$nveh" >/dev/null
  test -s "$NS2" || { echo "[WARN] Empty ns2mobility"; return 0; }

  cd "$NS3DIR"
  ./ns3 run "$PROGRAM \
    --useNs2Mobility=1 \
    --ns2Mobility=$NS2 \
    --simTime=$SIM_TIME \
    --nVehicles=$nveh \
    --rsuCoverageRadius=300 \
    --maliciousRate=$mal \
    --trustFastThresh=$tf \
    --trustMinThresh=$tm \
    --csvOut=$OUT_RUN_CSV \
    --eventsOut=$OUT_RUN_EVT" >/dev/null

  echo "[OK] CSV: $OUT_RUN_CSV"
}

for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPEED_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do
      for mal in "${MAL_LIST[@]}"; do
        for tf in "${FAST_LIST[@]}"; do
          for tm in "${MIN_LIST[@]}"; do
            run_one "$nveh" "$spd" "$seed" "$mal" "$tf" "$tm"
          done
        done
      done
    done
  done
done

echo "DONE. CSVs in: $RUNS_DIR"
