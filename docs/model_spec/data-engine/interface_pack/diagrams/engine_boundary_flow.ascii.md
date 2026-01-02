```txt
DATA ENGINE BOUNDARY FLOW (BLACK-BOX INTERFACE)
==============================================
Purpose:
  Show the ONLY facts downstream components may assume about the Data Engine:
  identity, addressing, outputs, and HashGates ("no PASS → no read").

Contracts used at the boundary:
  - contracts/engine_invocation.schema.yaml
  - contracts/canonical_event_envelope.schema.yaml
  - contracts/engine_output_locator.schema.yaml
  - contracts/gate_receipt.schema.yaml

Interface pack authorities:
  - engine_outputs.catalogue.yaml    (what exists + where + join keys + required gates)
  - engine_gates.map.yaml            (how to verify gates + what they authorize)
  - data_engine_interface.md         (human-readable boundary rules)

Legend:
  [C] Control plane component
  [E] Data Engine (black box)
  [S] Storage (surfaces, bundles, flags, logs)
  [G] HashGate artifact
  [P] Platform consumer / ingress

-----------------------------------------------------------------------

                 (CONTROL)                                      (DATA)
+----------------------------------+            +----------------------------------+
| [C] Scenario Runner              |            | [S] Storage / Object Store        |
|----------------------------------|            |----------------------------------|
| - chooses run identity:          |            | Surfaces (RO tables/files):       |
|   manifest_fingerprint           |            |   data/<layer>/<seg>/<output>/... |
|   parameter_hash                 |            |     .../fingerprint={mf}/         |
|   seed                           |            |     .../parameter_hash={ph}/      |
|   run_id                          |            |     .../seed={seed}/              |
|   scenario_binding (optional)    |            |                                    |
| - submits engine_invocation      |            | Gates (per segment):              |
| - records run facts (pins)       |            |   data/<layer>/<seg>/validation/   |
+-----------------+----------------+            |     fingerprint={mf}/             |
                  |                             |       index.json (input-set)       |
   engine_invocation.schema.yaml                |       _passed.flag (PASS proof)    |
                  |                             |                                    |
                  v                             | Logs / events (run-scoped):        |
+----------------------------------+            |   logs/.../seed={seed}/            |
| [E] Data Engine Runner (black box)|           |     parameter_hash={ph}/run_id={r}/|
|----------------------------------|            +----------------------------------+
| - reads sealed inputs (params,   |
|   externals) implied by {mf,ph}  |
| - executes segments in order     |
| - materialises outputs by writing|
|   immutable partitions           |
| - publishes per-segment HashGate |
| - may emit canonical events      |
+-----------------+----------------+
                  |
                  | writes surfaces, bundles, flags
                  v

-----------------------------------------------------------------------
SEGMENT PIPELINE WITH HASHGATES (conceptual)
-------------------------------------------
Each segment produces:
  - one or more surfaces/streams (see engine_outputs.catalogue.yaml)
  - one HashGate: validation bundle + _passed.flag (see engine_gates.map.yaml)

Example chain (names illustrative; authoritative list is in the catalogue):
  Layer-1: 1A -> 1B -> 2A -> 2B -> 3A -> 3B
  Layer-2: 5A -> 5B
  Layer-3: 6A -> 6B

For segment <SEG>:
  outputs:   data/<layer>/<SEG>/<output_id>/.../fingerprint={mf}/...
  gate:      data/<layer>/<SEG>/validation/fingerprint={mf}/
             - index.json (authoritative member list / order)
             - _passed.flag (PASS proof; gate-specific hashing law)

-----------------------------------------------------------------------
DOWNSTREAM READ / INGEST RULE ("NO PASS → NO READ")
---------------------------------------------------
+----------------------------------+
| [P] Ingestion Gate / Readers     |
|----------------------------------|
| Input: an output locator (pin)   |
|   { output_id, path, mf, ... }   |
| Behavior:                        |
| 1) Look up output_id in          |
|    engine_outputs.catalogue.yaml |
|    -> required gate_ids          |
| 2) For each gate_id:             |
|    use engine_gates.map.yaml     |
|    -> find gate artifacts paths  |
|    -> run verification steps     |
|    -> FAIL CLOSED if any check   |
| 3) Only on PASS: read/join the   |
|    output and proceed downstream |
+----------------------------------+

Gate verification is gate-specific:
  - do not assume a universal hashing method
  - always follow engine_gates.map.yaml

-----------------------------------------------------------------------
CONTROL-PLANE RUN FACTS (PINS)
------------------------------
Scenario Runner (or control-plane) records:
  - output pins:  engine_output_locator objects
  - gate pins:    gate_receipt objects

This creates a stable "run facts view" without exposing engine internals.

-----------------------------------------------------------------------
NON-NEGOTIABLE INVARIANTS (BOUNDARY)
------------------------------------
- Identity = declared partition tokens for the output_id (catalogue is authority).
- For a fixed identity partition, outputs are immutable / byte-identical.
- run_id may partition logs/events, but MUST NOT change bytes of outputs whose
  identity does not include run_id.
- Where lineage appears in both path and content, values MUST match (path↔embed).
- Physical file order is non-authoritative; use keys + declared fields.
```