#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fcd", required=True, help="SUMO fcd.xml path")
    ap.add_argument("--out", required=True, help="Output ns2mobility.tcl path")
    ap.add_argument("--limit", type=int, default=30, help="Max vehicles to export")
    return ap.parse_args()

def main():
    args = parse_args()
    fcd_path = Path(args.fcd)
    out_path = Path(args.out)

    if not fcd_path.exists():
        raise SystemExit(f"[ERR] FCD file not found: {fcd_path}")

    # Parse XML
    try:
        tree = ET.parse(fcd_path)
        root = tree.getroot()
    except Exception as e:
        raise SystemExit(f"[ERR] Failed to parse FCD XML: {e}")

    # FCD has structure: <fcd-export><timestep time=".."><vehicle .../></timestep>...</fcd-export>
    timesteps = root.findall(".//timestep")
    if not timesteps:
        # Some SUMO versions wrap differently; fallback:
        timesteps = root.findall("timestep")

    # Collect vehicle ids encountered (stable mapping to node indices)
    veh_ids = []
    veh_index = {}

    # Prepare output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    total_vehicle_records = 0

    for ts in timesteps:
        t = ts.get("time")
        if t is None:
            continue
        try:
            t = float(t)
        except:
            continue

        for v in ts.findall("vehicle"):
            vid = v.get("id")
            if vid is None:
                continue

            # Map vehicle id to index (0..limit-1)
            if vid not in veh_index:
                if len(veh_ids) >= args.limit:
                    continue
                veh_index[vid] = len(veh_ids)
                veh_ids.append(vid)

            idx = veh_index[vid]

            x = v.get("x")
            y = v.get("y")
            speed = v.get("speed", "0.0")

            if x is None or y is None:
                continue

            try:
                x = float(x); y = float(y); speed = float(speed)
            except:
                continue

            # NS2 mobility format
            # "$ns_ at <time> "$node_(i) setdest x y speed""
            lines.append(f'$ns_ at {t:.2f} "$node_({idx}) setdest {x:.2f} {y:.2f} {speed:.2f}"\n')
            total_vehicle_records += 1

    with open(out_path, "w") as f:
        f.writelines(lines)

    # Print summary
    unique_timesteps = len(timesteps)
    print(f"[OK] wrote ns2 mobility trace: {out_path}")
    print(f"[OK] vehicles: {len(veh_ids)} timesteps: {unique_timesteps} records: {total_vehicle_records}")

if __name__ == "__main__":
    main()#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import argparse
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fcd", required=True, help="SUMO fcd.xml path")
    ap.add_argument("--out", required=True, help="ns-2 mobility trace output path")
    ap.add_argument("--dt", type=float, default=0.1, help="sampling interval (s) expected in FCD")
    ap.add_argument("--limit", type=int, default=0, help="limit number of vehicles (0=all)")
    args = ap.parse_args()

    tree = ET.parse(args.fcd)
    root = tree.getroot()

    # veh_id -> list of (t,x,y)
    tracks = defaultdict(list)

    for ts in root.findall("timestep"):
        t = float(ts.get("time"))
        for v in ts.findall("vehicle"):
            vid = v.get("id")
            x = float(v.get("x"))
            y = float(v.get("y"))
            tracks[vid].append((t, x, y))

    # stable ordering
    vids = sorted(tracks.keys())
    if args.limit and args.limit > 0:
        vids = vids[:args.limit]

    # map SUMO veh IDs -> ns3 node index
    id_map = {vid: i for i, vid in enumerate(vids)}

    with open(args.out, "w") as f:
        # ns2 trace header not required, ns-3 Ns2MobilityHelper reads setdest lines.
        for vid in vids:
            idx = id_map[vid]
            for (t, x, y) in tracks[vid]:
                # speed not needed for RandomWaypoint playback, put 0
                f.write(f'$ns_ at {t:.2f} "$node_({idx}) setdest {x:.2f} {y:.2f} 0.0"\n')

    print(f"[OK] wrote ns2 mobility trace: {args.out}")
    print(f"[OK] vehicles: {len(vids)} timesteps: {len(tracks[vids[0]]) if vids else 0}")

if __name__ == "__main__":
    main()


