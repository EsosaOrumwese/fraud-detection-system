# Context Store + FlowBinding Build Plan (v0)
_As of 2026-02-07_

## Purpose
Provide a component-scoped build plan for the shared RTDL join plane that serves decision-time context readiness to DF/DL without duplicating IEG or OFP ownership.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `4.3.5`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md` (join/binding semantics)
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md` (DF context-read contract)

## Planning rules (binding)
- Progressive elaboration: phases are pinned; implementation detail is expanded only when phase is active.
- No half-baked phase transitions: each phase requires explicit evidence before advancing.
- Rails are non-negotiable: ContextPins, fail-closed compatibility, deterministic replay, append-only evidence, no fabricated joins.

## Component boundary
- This component owns:
  - JoinFrame runtime store (run-scoped decision-time context slices)
  - FlowBinding index (`flow_id -> JoinFrameKey`)
  - Read/query API for DF/DL context readiness checks
- This component does not own:
  - Admission decisions (IG)
  - Graph projection truth (IEG)
  - Feature snapshot truth (OFP)
  - Decisioning (DF/DL)

## Phase plan (v0)

### Phase 1 — Contracts, keys, and ownership pins
**Intent:** lock join-plane contracts before storage and workers.

**DoD checklist:**
- JoinFrameKey schema is pinned: `platform_run_id`, `scenario_run_id`, `merchant_id`, `arrival_seq`.
- FlowBinding schema is pinned with authoritative writer rule (`flow_anchor` lineage only).
- Required ContextPins are pinned and validated for write/read surfaces.
- Conflict semantics are pinned:
  - duplicate binding same hash -> idempotent
  - same key, different hash -> anomaly + fail-closed
- API contract for DF/DL reads is versioned and documented.
**Evidence (Phase 1):**
- Schemas:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/context_store_flow_binding_join_frame_key.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/context_store_flow_binding_flow_binding.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/context_store_flow_binding_query_request.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/context_store_flow_binding_query_response.schema.yaml`
- Policy:
  - `config/platform/context_store_flow_binding/policy_v0.yaml`
- Code:
  - `src/fraud_detection/context_store_flow_binding/contracts.py`
  - `src/fraud_detection/context_store_flow_binding/taxonomy.py`
  - `src/fraud_detection/context_store_flow_binding/config.py`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase1_contracts.py`
  - `tests/services/context_store_flow_binding/test_phase1_taxonomy.py`
  - `tests/services/context_store_flow_binding/test_phase1_config.py`

### Phase 2 — Storage schema + durability
**Intent:** implement durable runtime state for join reads and replay safety.

**DoD checklist:**
- Postgres schema exists for:
  - `join_frames`
  - `flow_bindings`
  - `join_apply_failures`
  - `join_checkpoints`
- Constraints prevent cross-run contamination.
- Commit point is pinned: DB transaction commit (WAL flush) before checkpoint advance.
- Retention/TTL posture is pinned for local-parity/dev/prod.
**Evidence (Phase 2):**
- Schema migrations (sqlite + postgres):
  - `src/fraud_detection/context_store_flow_binding/migrations.py`
- Durable store layer:
  - `src/fraud_detection/context_store_flow_binding/store.py`
- Retention policy:
  - `config/platform/context_store_flow_binding/retention_v0.yaml`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase2_store.py`
  - `tests/services/context_store_flow_binding/test_phase2_retention.py`
- Validation command:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`17 passed`)

### Phase 3 — Intake apply worker (context topics -> join plane)
**Intent:** build deterministic intake from admitted EB context topics.

**DoD checklist:**
- Intake consumes only admitted context streams from EB.
- Idempotent apply tuple and payload-hash mismatch semantics are implemented.
- Binding updates are authoritative only from flow-anchor events.
- Late/missing context handling is explicit and machine-readable.
- Apply-failure ledger records reasons and source offsets.
**Evidence (Phase 3):**
- Intake/runtime:
  - `src/fraud_detection/context_store_flow_binding/intake.py`
  - `config/platform/context_store_flow_binding/intake_policy_v0.yaml`
- Durable intake support:
  - `src/fraud_detection/context_store_flow_binding/migrations.py` (v2 `csfb_intake_dedupe`)
  - `src/fraud_detection/context_store_flow_binding/store.py` (`apply_context_event_and_checkpoint` + dedupe registration)
- Package exports:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase3_intake.py`
- Validation commands:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase3_intake.py -q` (`4 passed`)
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`21 passed`)

### Phase 4 — Checkpointing + replay determinism
**Intent:** guarantee restart/replay correctness.

**DoD checklist:**
- Per-partition checkpoints are written only after durable apply.
- Restart resumes from checkpoints with no duplicate state mutation.
- Replay from the same basis yields identical JoinFrames and FlowBindings.
- Backfill/rebuild entrypoint requires explicit offset basis declaration.
**Evidence (Phase 4):**
- Replay/basis surfaces:
  - `src/fraud_detection/context_store_flow_binding/replay.py`
  - `src/fraud_detection/context_store_flow_binding/rebuild.py`
- Intake replay-mode support:
  - `src/fraud_detection/context_store_flow_binding/intake.py` (`run_replay_once`, range-bound consumption, replay pin guard)
- Package exports:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase4_replay.py`
- Validation commands:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase4_replay.py -q` (`4 passed`)
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`25 passed`)

### Phase 5 — Query/read surface for DF/DL
**Intent:** expose deterministic join readiness without hidden fallbacks.

**DoD checklist:**
- Query endpoints support:
  - resolve by `flow_id` via FlowBinding
  - fetch JoinFrame by JoinFrameKey
- Responses include:
  - readiness status
  - reason codes
  - evidence refs (offset lineage)
  - run pins
- Missing state returns explicit fail-closed response contract (no fabricated joins).
**Evidence (Phase 5):**
- Query/read service:
  - `src/fraud_detection/context_store_flow_binding/query.py`
- Store read helpers:
  - `src/fraud_detection/context_store_flow_binding/store.py`
    - `read_flow_binding(...)`
    - `read_flow_binding_for_join_frame(...)`
    - `read_join_frame_record(...)`
- Package exports:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase5_query.py`
- Validation commands:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase5_query.py -q` (`6 passed`)
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`31 passed`)

### Phase 6 — Degrade and observability hooks
**Intent:** make join-plane deficits actionable in DL/DF and Obs/Gov.

**DoD checklist:**
- Metrics exported:
  - join_hits
  - join_misses
  - binding_conflicts
  - apply_failures
  - watermark/lag gauges
- Health surface emits GREEN/AMBER/RED with threshold policy refs.
- Reconciliation artifact exists per run with applied offset basis and unresolved anomalies.
**Evidence (Phase 6):**
- Observability/reporter surface:
  - `src/fraud_detection/context_store_flow_binding/observability.py`
- Threshold policy:
  - `config/platform/context_store_flow_binding/observability_v0.yaml`
- Store observability read helpers:
  - `src/fraud_detection/context_store_flow_binding/store.py`
    - `metrics_snapshot(...)`
    - `checkpoint_summary()`
    - `input_basis()`
    - `unresolved_anomalies(...)`
- Package exports:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
- Tests:
  - `tests/services/context_store_flow_binding/test_phase6_observability.py`
- Validation commands:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase6_observability.py -q` (`3 passed`)
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`34 passed`)

### Phase 7 — Local-parity integration
**Intent:** prove runtime behavior with platform parity stack.

**DoD checklist:**
- Local-parity run wires EB context streams into join-plane worker.
- DF/DL can read join readiness from this component with stable contracts.
- 20-event monitored run evidence is recorded with join hit/miss accounting.
- 200-event monitored run evidence is recorded with lag and determinism checks.
**Evidence (Phase 7):**
- Parity profile wiring + topic map:
  - `config/platform/profiles/local_parity.yaml` (`context_store_flow_binding` section)
  - `config/platform/context_store_flow_binding/topics_v0.yaml`
- Intake profile-root loader + query policy builder:
  - `src/fraud_detection/context_store_flow_binding/intake.py` (profile-root support + env/topic ref resolution)
  - `src/fraud_detection/context_store_flow_binding/query.py` (`build_from_policy(...)`)
- Local-parity execution surfaces:
  - `makefile`
    - `platform-context-store-flow-binding-parity-once`
    - `platform-context-store-flow-binding-parity-live`
  - `docs/runbooks/platform_parity_walkthrough_v0.md` (Section `18`)
- Tests:
  - `tests/services/context_store_flow_binding/test_phase7_parity_integration.py`
    - parity-profile loader + env resolution
    - monitored 20-event pass (`join_hits=20`, `join_misses=0`, query `READY`)
    - monitored 200-event pass (checkpoint-stable re-poll, basis digest stable)
- Validation commands:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase7_parity_integration.py -q` (`3 passed`)
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q` (`37 passed`)

### Phase 8 — Hardening + closure
**Intent:** close component with replay-safe, production-shaped behavior.

**DoD checklist:**
- Migrations are explicit; no runtime schema mutation hacks for prod posture.
- Failure drills (DB outage, offset rollback, conflict storms) are tested.
- Security posture is documented (no secret material in artifacts/logbooks).
- Closure statement is explicit: component green at join-plane boundary; downstream DF/AL/DLA end-to-end closure remains platform-gated.

## Status (rolling)
- Phase 1 (`Contracts, keys, and ownership pins`): completed.
- Phase 2 (`Storage schema + durability`): completed.
- Phase 3 (`Intake apply worker`): completed.
- Phase 4 (`Checkpointing + replay determinism`): completed.
- Phase 5 (`Query/read surface for DF/DL`): completed.
- Phase 6 (`Degrade and observability hooks`): completed.
- Phase 7 (`Local-parity integration`): completed.
- Current focus: Phase 8 (`Hardening + closure`).
