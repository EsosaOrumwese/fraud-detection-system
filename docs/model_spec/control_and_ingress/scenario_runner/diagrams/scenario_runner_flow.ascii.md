```txt
SCENARIO RUNNER FLOW (CONTROL-PLANE) — BLACK-BOX ENGINE INTEGRATION
==================================================================
Purpose:
  Show the Scenario Runner’s control-plane flow: run planning, identity anchoring,
  engine invocation (black box), and downstream discovery via run facts pins.
  Scenario Runner MUST NOT depend on engine segment/state internals (1A→6B).

Scenario Runner contracts (this component):
  - contracts/scenario_run_request.schema.yaml
  - contracts/scenario_definition.schema.yaml
  - contracts/run_facts_view.schema.yaml
  - contracts/run_status_event.payload.schema.yaml   (optional; payload-only)

Authoritative dependencies (referenced, not duplicated):
  Platform Rails:
    - run_record.schema.yaml                 (Run Record is Rails-owned)
    - canonical_event_envelope.schema.yaml   (only if emitting status events)
    - id_types.schema.yaml                   (canonical types / IDs)
  Data Engine Interface Pack (black-box boundary):
    - contracts/engine_invocation.schema.yaml
    - contracts/engine_output_locator.schema.yaml
    - contracts/gate_receipt.schema.yaml
    - engine_outputs.catalogue.yaml
    - engine_gates.map.yaml

-----------------------------------------------------------------------
HIGH-LEVEL LANES (WHO DOES WHAT)
--------------------------------

  Caller / Operator               Scenario Runner (control plane)            Data Engine (black box)
  -----------------              ------------------------------            ------------------------
  submits run request            validates + anchors run identity           executes engine run
  (scenario_run_request)         publishes run anchors + discovery          materialises outputs
                                  (Run Record + Run Facts View)            publishes segment gates


+--------------------+          +-----------------------------------+      +---------------------------+
| [C] Caller         |          | [SR] Scenario Runner               |      | [E] Data Engine Runner     |
|--------------------|          |-----------------------------------|      |---------------------------|
| POST run request   |  ----->  | 1) Validate scenario_run_request   |      | Accept engine_invocation  |
|  - mf, ph          |          |    - refuse on missing/invalid IDs |      |  - {mf, ph, seed, run_id} |
|  - scenario_binding|          |    - refuse on conflicting replay  |      |  - scenario_binding       |
|  - seed policy     |          | 2) Assign/confirm run_id (+ seed)  |      |                           |
|  - optional output |          | 3) Publish Run Record (PLANNED)    |      | Writes immutable outputs  |
|    selection       |          |    (Rails run_record schema)       |      | by declared partitions:   |
+--------------------+          | 4) Form engine_invocation (pack)   |      |  data/.../fingerprint={mf}|
                              +->| 5) Invoke engine (idempotent)     |----->|                           |
                              |  | 6) Observe/collect pins:          |      | Publishes per-segment     |
                              |  |    - output locators (preferred)  |      | HashGates (PASS proofs):  |
                              |  |    - or build paths from catalogue|      |  data/.../validation/     |
                              |  |    - gate receipts per gate map   |      |   fingerprint={mf}/       |
                              |  | 7) Publish Run Facts View update  |      |    _passed.flag / index   |
                              |  |    - only list outputs consumable |      |                           |
                              |  |      when required gates PASS     |      +---------------------------+
                              |  | 8) Update Run Record status       |
                              |  |    PLANNED -> STARTED -> ...      |
                              |  +-----------------------------------+
                              |
                              |  Optional: emit status events
                              v
                         +----------------------------------------------+
                         | [EV] run.status.changed (optional)           |
                         |----------------------------------------------|
                         | Envelope: Platform Rails canonical envelope   |
                         | Payload:  run_status_event.payload.schema     |
                         +----------------------------------------------+

-----------------------------------------------------------------------
CONTROL-PLANE OUTPUTS (WHAT DOWNSTREAM READS)
--------------------------------------------

Scenario Runner publishes TWO authority surfaces (pinnable, immutable revisions):

  1) Run Record (Rails-owned shape)
     - anchors {parameter_hash, manifest_fingerprint, scenario_id, run_id, seed?}
     - lifecycle status + timestamps

  2) Run Facts View (Scenario Runner-owned shape)
     - active run entries with:
       * identity tuple
       * run_record_ref (+ optional digest)
       * engine output pins: engine_output_locator objects
       * gate proof pins: gate_receipt objects (PASS/FAIL)
       * optional pending markers (missing gates / not-ready outputs)

-----------------------------------------------------------------------
DOWNSTREAM READ / INGEST RULE ("NO PASS → NO READ")
---------------------------------------------------

+----------------------------------+
| [P] Ingestion Gate / Readers     |
|----------------------------------|
| Input: Run Facts View (pins)     |
|  - output_locators (by output_id)|
|  - gate_receipts (PASS proofs)   |
| Behavior:                        |
| 1) For each output locator:      |
|    look up output_id in          |
|    engine_outputs.catalogue.yaml |
|    -> required gate_ids          |
| 2) For each gate_id:             |
|    follow engine_gates.map.yaml  |
|    -> verify PASS artifacts      |
|    -> FAIL CLOSED if any missing |
| 3) Only on PASS: read/join data  |
+----------------------------------+

Scenario Runner MUST NOT publish an output as “consumable” unless all gates
listed by read_requires_gates (catalogue) are satisfied (PASS proofs pinned),
or the output is explicitly marked pending/not-ready.

-----------------------------------------------------------------------
NON-NEGOTIABLE INVARIANTS (SCENARIO RUNNER)
-------------------------------------------
- Scenario Runner treats the Data Engine as a black box:
  do not assume segment/state ordering or internals.
- Identity tuple is immutable once anchored for a run_id.
- Discovery must be via pins (Run Facts View), not “latest” scanning.
- Output existence is declared by engine_outputs.catalogue.yaml (authority).
- Gate semantics are declared by engine_gates.map.yaml (authority).
- “No PASS → no read” applies to every engine output intended for ingestion.
```