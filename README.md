
## NS-3 Experiments

### 1. Urban V2X Baseline
- File: ns3/scenarios/urban_v2x.cc
- Outputs: ns3/results/metrics_*.csv

### 2. RSU Handover with Trust
- File: ns3/scenarios/rsu_handover.cc
- Outputs: ns3/results/handover_*.csv
- Aggregated summary: master_summary.csv
- Plot: handover_delay_vs_speed.png

### 3. Secure V2X (Crypto + Replay Attack)
- File: ns3/scenarios/secure_v2x.cc
- Outputs: secure_200us.csv, secure_replay.csv
=======
## Blockchain Trust V2X (ns-3)

### Scenario
- `ns3/scenarios/blockchain_trust_v2x.cc`

### Example run (in your ns-3 workspace)
```bash
./ns3 run "scratch/blockchain_trust_v2x --nVehicles=10 --nRsu=2 --simTime=20 --cryptoDelayUsTx=200 --cryptoDelayUsRx=200 --enableReplayAttack=1 --maliciousRate=0.2 --blockIntervalMs=1000 --mineDelayMs=50 --csvOut=blockchain_runs/bc_metrics_m0.2.csv --eventsOut=blockchain_runs/bc_events_m0.2.csv"
>>>>>>> 8f8b7dc (Complete Secure Trust-Based V2X with Blockchain:)
