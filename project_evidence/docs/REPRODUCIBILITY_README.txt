Project Reproducibility Bundle
==============================

Project:
Secure Trust-Based V2X Communication with Blockchain Support

Purpose:
This folder provides organized evidence and documentation for simulation,
integration, and formal verification results.

Folder Meaning
--------------
baseline/   : baseline VANET communication evidence
secure/     : replay-aware secure communication evidence
handover/   : trust-based RSU handover evidence
adaptive/   : adaptive trust / blockchain behavior evidence
integrated/ : integrated end-to-end scenario evidence
formal/     : Scyther formal verification models and results
docs/       : reproducibility and interpretation documents

Canonical Evidence
------------------
Use categorized folders (baseline, secure, handover, adaptive, formal)
as the primary evidence locations.

The integrated/ folder also contains archived mixed copies collected
from the final paper_evidence bundle.

Recommended Review Order
------------------------
1. baseline/urban_default.csv
2. secure/secure_meaningful.csv
3. handover/handover_meaningful.csv
4. handover/handover_meaningful_events.csv
5. adaptive/adaptive_default.csv
6. adaptive/adaptive_default_events.csv
7. integrated/final_valid_comm.csv
8. integrated/final_bc_cache_on.csv
9. integrated/final_bc_cache_on_events.csv
10. integrated/final_privacy_meaningful.csv
11. integrated/final_privacy_meaningful_events.csv
12. formal/v2x_handover_auth.spdl
13. formal/v2x_handover_auth_result.txt
14. formal/v2x_handover_auth_secure.spdl
15. formal/v2x_handover_auth_secure_result.txt
16. formal/v2x_handover_auth_final.spdl
17. formal/v2x_handover_auth_final_result.txt

Formal Verification Interpretation
----------------------------------
- v2x_handover_auth.spdl:
  initial insecure model; multiple claims fail
- v2x_handover_auth_secure.spdl:
  stronger model; most claims pass but initiator-side agreement/sync is incomplete
- v2x_handover_auth_final.spdl:
  final model with additional responder freshness and final acknowledgement;
  all target claims pass within Scyther analysis bounds

Integrity
---------
Use CHECKSUMS.txt to validate file integrity.

Manifest
--------
Use EVIDENCE_MANIFEST.csv to identify category and purpose of each file.
