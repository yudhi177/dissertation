#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/dissertation"
NS3DIR="$HOME/ns-3"

# Paper matrix
VEH_LIST=(10)
SPEED_LIST=(8.3)
SEED_LIST=(1)

MAL_LIST=(0.0 0.1 0.2 0.4)
FAST_LIST=(0.6 0.7 0.8)
MIN_LIST=(0.2 0.3 0.4)

SIM_TIME=20
SUMO_STEP=0.1
NET_XML="$REPO/sumo/maps/grid/grid.net.xml"

OUT_BASE="$REPO/ns3/results/final_paper_sweep"
RUNS_DIR="$OUT_BASE/runs"
mkdir -p "$RUNS_DIR"

PROGRAM="scratch/secure_trust_blockchain_v2x"
RSU_R=300

cd "$NS3DIR"
./ns3 build >/dev/null

gen_routes_and_fcd () {
  local nveh="$1" spd="$2" seed="$3" run_dir="$4"
  local trips="$run_dir/trips.xml"
  local rou="$run_dir/routes.rou.xml"
  local fcd="$run_dir/fcd.xml"
  local cfg="$run_dir/run.sumocfg"

  local period
  period="$(python3 - <<PY
t=float("$SIM_TIME"); n=int("$nveh")
print(max(0.1, t/max(1,n)))
PY
)"

  python3 /usr/share/sumo/tools/randomTrips.py \
    -n "$NET_XML" -o "$trips" -r "$rou" \
    --seed "$seed" --prefix veh --random \
    -b 0 -e "$SIM_TIME" -p "$period" >/dev/null

  # Clean + force car + trim vehicles
  python3 - <<PY
import xml.etree.ElementTree as ET
p=r"$rou"; n=int("$nveh"); spd=str("$spd")
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
PY

  cat > "$cfg" <<CFG
<configuration>
  <input>
    <net-file value="$NET_XML"/>
    <route-files value="$rou"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="$SIM_TIME"/>
    <step-length value="$SUMO_STEP"/>
  </time>
  <output>
    <fcd-output value="$fcd"/>
  </output>
</configuration>
CFG

  sumo -c "$cfg" --seed "$seed" --quit-on-end --no-step-log true >/dev/null
  grep -q "<vehicle" "$fcd" || { echo "[WARN] No vehicles in FCD"; return 1; }
  return 0
}

for nveh in "${VEH_LIST[@]}"; do
  for spd in "${SPEED_LIST[@]}"; do
    for seed in "${SEED_LIST[@]}"; do

      # Reuse mobility for all sweeps with same (nveh, spd, seed)
      BASE_TAG="veh_${nveh}_spd_${spd}_seed_${seed}"
      BASE_DIR="$REPO/sumo/output/grid_final/$BASE_TAG"
      mkdir -p "$BASE_DIR"

      if ! gen_routes_and_fcd "$nveh" "$spd" "$seed" "$BASE_DIR"; then
        continue
      fi

      NS2="$BASE_DIR/ns2mobility.tcl"
      python3 "$REPO/sumo/traci_controller.py" --fcd "$BASE_DIR/fcd.xml" --out "$NS2" --limit "$nveh" >/dev/null
      test -s "$NS2" || { echo "[WARN] Empty NS2 trace"; continue; }

      for mal in "${MAL_LIST[@]}"; do
        for tf in "${FAST_LIST[@]}"; do
          for tm in "${MIN_LIST[@]}"; do
            TAG="${BASE_TAG}_mal_${mal}_tf_${tf}_tm_${tm}"
            OUT_CSV="$RUNS_DIR/${TAG}.csv"
            OUT_EVT="$RUNS_DIR/${TAG}_events.csv"

            cd "$NS3DIR"
            ./ns3 run "$PROGRAM \
              --useNs2Mobility=1 \
              --ns2Mobility=$NS2 \
              --simTime=$SIM_TIME \
              --nVehicles=$nveh \
              --rsuCoverageRadius=$RSU_R \
              --maliciousRate=$mal \
              --trustFastThresh=$tf \
              --trustMinThresh=$tm \
              --csvOut=$OUT_CSV \
              --eventsOut=$OUT_EVT" >/dev/null

            echo "[OK] $TAG"
          done
        done
      done
    done
  done
done

echo "DONE. CSVs in: $RUNS_DIR"
