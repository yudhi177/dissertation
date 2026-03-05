# Secure Trust-Based V2X Communication with Blockchain Support (ns-3)

4th Year Dissertation Implementation (V2X / VANET)  
**Core idea:** Trust-based RSU handover + security attacks + blockchain-backed trust + privacy controls.

---

## Project Highlights
- **Trust-based RSU handover** with FAST vs FULL authentication behavior
- **Security evaluation**: simulated crypto delay + replay/sybil/sig-corruption style attacks
- **Blockchain-backed trust (simulated)** with optional trust cache behavior
- **Privacy controls**: pseudonym rotation + linkability/mix-zone style evaluation
- **Automation**: experiment scripts + CSV aggregation + plots

---

## What this repo contains
- **ns-3 scenarios (C++)** for V2X simulation
- **Python scripts** for experiments, aggregation, plotting
- **Results**: CSV summaries + publishable plots
- **Submission bundle**: final files used for evaluation/submission

---

## Repository Structure (high level)
.
├─ ns3/
│ ├─ scenarios/ # main ns-3 C++ scenario files
│ ├─ scripts/ # run / aggregate / plot scripts
│ ├─ results/ # generated CSV + plots (summaries + publishable outputs)
│ ├─ trust/ crypto/ privacy/ attacks/ model/ session/
├─ sumo/ # mobility traces / helpers (if used)
├─ blockchain/ # blockchain placeholders / scripts (if used)
├─ experiments/ # orchestration scripts (if used)
├─ submission_bundle/ # final submission-ready outputs
├─ docs/ # diagrams / notes / reproducibility
└─ data/ # static input data (if used)


---

## Build ns-3 (recommended workflow)
Run these inside your ns-3 workspace:

```bash
cd ~/ns-3
./ns3 clean
./ns3 configure
./ns3 build
