Algorithm Pack README
=====================

Purpose
-------
This folder is used to hold the algorithm-oriented material that will later
support the paper's method / implementation explanation.

Planned Core Algorithms
-----------------------
1. Receive-and-Validate Packet Path
   - replay check
   - invalid/tampered packet filtering
   - accept/drop logic

2. Handover Decision Logic
   - trust score evaluation
   - freshness check
   - FAST / FULL / REJECT selection

3. Blockchain-Assisted Trust Lookup
   - cache check
   - continuity query path
   - returned trust-context handling

Why This Pack Exists
--------------------
The paper should explain the framework in a reviewer-friendly way without
depending only on source code screenshots.

These algorithm notes will provide:
- clear stepwise logic
- implementation-backed explanation
- a direct bridge between code and paper description

Relationship to Code
--------------------
The algorithms are conceptual summaries of the implemented logic and should
be aligned with:
- packet receive path
- trust-guided handover logic
- blockchain/cache continuity support

They are not intended to claim a full formal proof.
They are implementation-oriented explanatory artifacts.

Expected Output Files
---------------------
This folder is expected to later include:

- RECEIVE_VALIDATE_ALGORITHM.txt
- HANDOVER_DECISION_ALGORITHM.txt
- BLOCKCHAIN_LOOKUP_ALGORITHM.txt

Safe Paper Positioning
----------------------
The paper may present these algorithms as implementation-guided procedural
descriptions of the framework's core control flow.

They should not be presented as standalone security proofs.
