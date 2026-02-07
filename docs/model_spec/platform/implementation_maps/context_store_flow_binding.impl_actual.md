# Context Store + FlowBinding Implementation Notes
_As of 2026-02-07_

## Entry: 2026-02-07 14:02:30 - Component bootstrap and pre-implementation plan

### Problem statement
RTDL integration still needs a shared runtime join plane that DF/DL can query deterministically at decision time. Existing components cover adjacent truth planes but do not provide an explicit runtime JoinFrame + FlowBinding service boundary:
- IEG: projection/world state
- OFP: feature snapshots
- DF/DL: decision core

The missing explicit boundary increases ambiguity on where flow resolution and join-readiness truth are sourced during live decisioning.

### Authorities and references used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `4.3.5`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`

### Decision
Treat the shared join plane as its own component:
- Component id: `context_store_flow_binding`
- Build plan path:
  - `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md`
- Implementation notes path:
  - `docs/model_spec/platform/implementation_maps/context_store_flow_binding.impl_actual.md`

### Alternatives considered
1. Extend IEG to own join-plane runtime reads.
- Rejected: mixes projection authority with decision-time join readiness service concerns.

2. Extend OFP to own FlowBinding and runtime join lookups.
- Rejected: OFP owns snapshot materialization/serve, not authoritative flow-binding updates.

3. Introduce dedicated join-plane component (selected).
- Selected: clean ownership boundary for JoinFrame + FlowBinding runtime duties and explicit DF/DL read contract.

### Planned implementation order
1. Phase 1 contract pinning:
- define JoinFrameKey contract and required pins.
- define FlowBinding contract and conflict semantics.
- define query/read schema for DF/DL.

2. Phase 2 storage:
- add Postgres schema + indexes + checkpoint tables.
- pin commit-point and replay invariants.

3. Phase 3 intake worker:
- EB context intake with idempotent apply and conflict handling.

4. Phase 4+:
- query API
- observability and reconciliation
- parity runs and hardening.

### Invariants to enforce from day 1
- No fabricated joins: missing binding/context is explicit fail-closed response.
- FlowBinding authority is only flow-anchor lineage.
- Replay from identical offset basis must reproduce identical runtime state.
- All rows and artifacts are run-scoped via ContextPins.

### Security and governance posture
- No secrets in runtime artifacts, implementation notes, or logbook.
- Conflict and compatibility failures emit anomaly records; never silently overwrite.

### Validation plan for initial implementation phases
- Unit tests for key normalization, idempotency tuple, and conflict detection.
- Integration tests for context intake -> FlowBinding resolve -> JoinFrame read.
- Replay tests proving same basis -> same state.

---

## Entry: 2026-02-07 14:38:00 - Phase 1 implementation plan (contracts/keys/ownership pins)

### Active-phase objective
Implement Phase 1 from `context_store_flow_binding.build_plan.md` by producing enforceable contract surfaces and policy loaders that downstream runtime code can rely on without ambiguity.

### Decision thread 1: where contracts live
Options considered:
1. Keep Phase 1 contracts as Python-only dataclasses.
2. Create JSON schemas under RTDL contract folder and mirror them in Python validators.

Decision:
- Use Option 2.

Reasoning:
- Existing platform contract authority is schema-first under
  `docs/model_spec/platform/contracts/real_time_decision_loop`.
- Runtime code should consume a typed Python API, but schema artifacts are needed for cross-component and auditable contract review.

Planned schema artifacts:
- `context_store_flow_binding_join_frame_key.schema.yaml`
- `context_store_flow_binding_flow_binding.schema.yaml`
- `context_store_flow_binding_query_request.schema.yaml`
- `context_store_flow_binding_query_response.schema.yaml`

### Decision thread 2: package/module structure
Options considered:
1. Add code into IEG/OFP modules as helpers.
2. New dedicated package `src/fraud_detection/context_store_flow_binding/`.

Decision:
- Option 2 (dedicated package).

Reasoning:
- Prevents ownership blending and keeps the 4.3.5 boundary explicit.
- Enables isolated tests (`tests/services/context_store_flow_binding/`) and phased implementation.

Planned modules:
- `contracts.py`: normalized typed contracts + validation.
- `taxonomy.py`: authoritative event-type compatibility checks for flow-binding source lineage.
- `config.py`: phase policy loader (`required_pins`, source allowlist, compatibility posture, digest).
- `__init__.py`: public exports.

### Decision thread 3: pin posture in Phase 1
Decision:
- Required pins remain strict v0 synthetic posture:
  `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed`.
- `run_id` remains optional compatibility alias where present.

Reasoning:
- This matches existing RTDL contract posture and current DF/OFP/IEG pin requirements.

### Decision thread 4: query contract scope
Decision:
- Phase 1 query contract supports two deterministic lookup selectors:
  - by `flow_id` (FlowBinding resolution path),
  - by explicit `join_frame_key`.
- Request must provide exactly one selector to avoid ambiguous read semantics.

Reasoning:
- Matches planned runtime join-plane behavior and avoids hidden precedence rules in reads.

### Decision thread 5: authoritative writer rule encoding
Decision:
- FlowBinding contract and taxonomy will enforce source lineage event types:
  - `s2_flow_anchor_baseline_6B`
  - `s3_flow_anchor_with_fraud_6B`

Reasoning:
- This encodes the "flow-anchor only" authority in Phase 1 so later ingestion/apply code can fail closed by contract, not by ad-hoc branching.

### Phase 1 validation matrix (concrete)
- Contract tests:
  - valid/invalid JoinFrameKey normalization.
  - FlowBinding source-event gate enforcement.
  - query request selector exclusivity.
- Taxonomy tests:
  - allowed flow-anchor families accepted, others rejected.
- Config tests:
  - policy loader deterministic digest and required fields.

---

## Entry: 2026-02-07 14:56:40 - Phase 1 implementation completed (contracts + policy + tests)

### What was implemented
- Contract schemas (RTDL):
  - `context_store_flow_binding_join_frame_key.schema.yaml`
  - `context_store_flow_binding_flow_binding.schema.yaml`
  - `context_store_flow_binding_query_request.schema.yaml`
  - `context_store_flow_binding_query_response.schema.yaml`
- Runtime validation package:
  - `src/fraud_detection/context_store_flow_binding/contracts.py`
  - `src/fraud_detection/context_store_flow_binding/taxonomy.py`
  - `src/fraud_detection/context_store_flow_binding/config.py`
- Policy:
  - `config/platform/context_store_flow_binding/policy_v0.yaml`
- Contract index update:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`

### Decisions made during implementation (with reasoning)
1. **Seed pin enforcement tied to policy flag**
   - Decision: `require_seed=true` must imply `seed` is present in `required_pins`.
   - Reasoning: prevents policies that claim to require seed while omitting it from the pin allowlist, which would create a hidden mismatch between validation and policy posture.

2. **Taxonomy enforcement raises config errors at policy load**
   - Decision: unknown authoritative event types raise `ContextStoreFlowBindingConfigError`, not a raw taxonomy error.
   - Reasoning: policy loading is the authoritative boundary; callers expect a uniform config exception class for policy issues.

3. **Selector exclusivity as hard contract invariant**
   - Decision: Query requests require exactly one selector (`flow_id` xor `join_frame_key`).
   - Reasoning: removes ambiguous precedence during read and keeps join-plane semantics deterministic in Phase 1.

4. **Run identity normalization**
   - Decision: `platform_run_id` uses strict `platform_YYYYMMDDTHHMMSSZ` format; `run_id` stays optional compatibility alias.
   - Reasoning: avoids reintroducing legacy ambiguity while still tolerating legacy `run_id` presence.

### Phase 1 DoD mapping
- JoinFrameKey schema pinned in schema + Python validator.
- FlowBinding schema + authoritative writer rule enforced by taxonomy allowlist.
- ContextPins are validated in both request/response and FlowBinding records.
- Query contract versioned with selector exclusivity.

### Tests executed
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q`
  - Result: `12 passed`

### Notes on constraints and invariants
- All contracts are fail-closed; missing or malformed pins result in explicit contract errors.
- No fabricated joins: queries can only resolve by explicit FlowBinding or explicit JoinFrameKey.
- Phase 1 implements contract/policy boundaries only; storage and intake are deferred to Phase 2+.

---

## Entry: 2026-02-07 15:09:00 - Phase 2 pre-implementation plan (storage schema + durability)

### Active-phase objective
Implement Phase 2 from `context_store_flow_binding.build_plan.md` by delivering durable storage surfaces with explicit run-scoped constraints and checkpoint commit safety.

### Inputs/authorities
- `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- Existing parity patterns in:
  - `src/fraud_detection/identity_entity_graph/migrations.py`
  - `src/fraud_detection/degrade_ladder/store.py`
  - `src/fraud_detection/decision_fabric/checkpoints.py`

### Decision thread 1: migration shape
Options considered:
1. Raw `CREATE TABLE IF NOT EXISTS` only in store constructor.
2. Versioned migrations for sqlite/postgres, called by store initialization.

Decision:
- Option 2.

Reasoning:
- Matches mature component posture (IEG) and avoids hidden schema drift when Phase 3+ adds columns.

### Decision thread 2: cross-run contamination guard
Decision:
- Every primary key / unique key for mutable truth tables (`join_frames`, `flow_bindings`) includes run pins axis (`platform_run_id` + `scenario_run_id`) plus stream scope.
- Add explicit composite uniqueness for join-frame key tuple under run scope.

Reasoning:
- Enforces non-overlap between runs by schema shape, not only caller discipline.

### Decision thread 3: conflict semantics in store layer
Decision:
- For both join frames and flow bindings:
  - existing row with same payload hash => `noop` idempotent.
  - existing row with different payload hash => raise conflict error (`*_PAYLOAD_HASH_MISMATCH`).

Reasoning:
- Pushes replay safety into durable layer; Phase 3 worker can remain thinner and fail-closed by exception path.

### Decision thread 4: commit point and checkpoint durability
Decision:
- Provide transactional apply methods that persist row mutation and checkpoint advance in a single DB transaction.
- Checkpoint updates are never performed before mutation write in that transaction body.

Reasoning:
- Directly encodes Phase 2 commit-point rule: durable commit precedes visibility of checkpoint movement.

### Decision thread 5: retention posture pinning
Decision:
- Add versioned retention policy file under `config/platform/context_store_flow_binding/retention_v0.yaml` with explicit env profiles (`local_parity`, `dev`, `prod`).
- Implement strict policy loader now; pruning execution deferred to later phase.

Reasoning:
- Phase 2 requires retention posture to be pinned; loader makes it auditable/testable immediately.

### Planned file paths (Phase 2)
- New:
  - `src/fraud_detection/context_store_flow_binding/migrations.py`
  - `src/fraud_detection/context_store_flow_binding/store.py`
  - `config/platform/context_store_flow_binding/retention_v0.yaml`
  - `tests/services/context_store_flow_binding/test_phase2_store.py`
  - `tests/services/context_store_flow_binding/test_phase2_retention.py`
- Update:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
  - `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md`

### Validation plan
- sqlite-backed tests for table/migration presence and conflict semantics.
- transaction rollback proof: failed apply does not advance checkpoint.
- retention loader contract tests for env profile parsing and fail-closed missing fields.

---

## Entry: 2026-02-07 15:22:00 - Phase 2 implementation completed (storage schema + durability)

### What was implemented
- Added CSFB schema migrations with sqlite/postgres parity:
  - `src/fraud_detection/context_store_flow_binding/migrations.py`
- Added durable store surface with run-scoped write paths and checkpoint commit discipline:
  - `src/fraud_detection/context_store_flow_binding/store.py`
- Added retention posture policy for env ladder:
  - `config/platform/context_store_flow_binding/retention_v0.yaml`
- Added Phase 2 validation tests:
  - `tests/services/context_store_flow_binding/test_phase2_store.py`
  - `tests/services/context_store_flow_binding/test_phase2_retention.py`
- Exported store surfaces from package init:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`

### Decision threads finalized during implementation
1. **Single-transaction apply + checkpoint path**
   - Decision: use `apply_flow_binding_and_checkpoint(...)` with one DB transaction that writes durable state first and only then advances checkpoint row.
   - Reasoning: direct enforcement of the Phase 2 commit-point invariant (no checkpoint movement on failed apply).

2. **Store-level idempotency/conflict enforcement**
   - Decision: keep hash conflict checks inside store methods (`JOIN_FRAME_PAYLOAD_HASH_MISMATCH`, `FLOW_BINDING_PAYLOAD_HASH_MISMATCH`) rather than only in intake worker.
   - Reasoning: puts replay safety at durability boundary and prevents worker regressions from violating invariant.

3. **Cross-run contamination guard via composite keys**
   - Decision: primary/unique keys include run scope (`platform_run_id`, `scenario_run_id`) together with stream and business keys.
   - Reasoning: schema-level partitioning avoids accidental inter-run mutation overlap.

4. **Retention posture as versioned policy artifact**
   - Decision: pin environment-specific retention in `retention_v0.yaml` and validate via loader now; actual pruning execution deferred.
   - Reasoning: satisfies Phase 2 posture pinning without introducing premature data lifecycle automation in storage bootstrap phase.

### Phase 2 DoD mapping
- Postgres schema exists for all required tables: satisfied in migrations module.
- Cross-run constraints: satisfied by composite PK/UNIQUE structures.
- Commit-point semantics: satisfied by single-transaction apply+checkpoint method and rollback behavior test.
- Retention/TTL posture pinned: satisfied by env-specific retention policy + parser tests.

### Validation
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q`
  - Result: `17 passed`

### Residual scope boundary (intentional)
- Phase 2 does not implement topic intake worker or replay-backfill orchestration yet; those remain Phase 3/4 scope.

---

## Entry: 2026-02-07 15:35:00 - Phase 3 pre-implementation plan (intake apply worker)

### Active-phase objective
Implement Phase 3 (`Intake apply worker`) so Context Store + FlowBinding consumes admitted EB context topics deterministically and writes replay-safe join state.

### Inputs/authorities
- `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- Existing projector patterns:
  - `src/fraud_detection/identity_entity_graph/projector.py`
  - `src/fraud_detection/online_feature_plane/projector.py`

### Decision thread 1: where idempotency tuple lives
Options considered:
1. Keep dedupe only in worker memory.
2. Persist dedupe tuple in durable store and enforce payload-hash mismatch at DB boundary.

Decision:
- Option 2.

Reasoning:
- At-least-once + restart safety requires durable dedupe, not process-local memory.
- Payload-hash mismatch must survive restarts and be auditable.

Planned tuple:
- `(stream_id, platform_run_id, event_class, event_id)` with persisted `payload_hash`.

### Decision thread 2: join-frame mutation model
Options considered:
1. Strict one-hash-per-join-frame row (conflict on any update).
2. Event-driven frame state updates where different context events can update same join frame while duplicate event hashes remain idempotent.

Decision:
- Option 2.

Reasoning:
- Arrival/arrival_entities/flow_anchor are complementary context updates for the same join key; strict single-hash row would block legitimate progression.

### Decision thread 3: authoritative flow-binding writes
Decision:
- Only flow-anchor event types (`s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`) can create/update FlowBinding records.
- Any other event type attempting binding update is rejected with machine-readable failure reason.

Reasoning:
- Aligns with pre-design and phase invariants; prevents silent authority drift.

### Decision thread 4: missing/late handling semantics
Decision:
- Missing join key or missing required pins is fail-closed with explicit reason codes in `csfb_join_apply_failures`.
- Late context (event_ts older than checkpoint watermark) is treated as explicit machine-readable anomaly (`LATE_CONTEXT_EVENT`) while still applying state when valid.

Reasoning:
- Preserves operational continuity while making late/missing posture inspectable.

### Decision thread 5: intake policy shape
Decision:
- Introduce versioned intake policy file under `config/platform/context_store_flow_binding/intake_policy_v0.yaml` with:
  - context topic allowlist
  - class map reference
  - run-scope gating controls
  - poll settings and event-bus wiring defaults

Reasoning:
- Keeps intake behavior explicit and auditable, consistent with other components.

### Planned file paths (Phase 3)
- Update:
  - `src/fraud_detection/context_store_flow_binding/migrations.py`
  - `src/fraud_detection/context_store_flow_binding/store.py`
  - `src/fraud_detection/context_store_flow_binding/__init__.py`
- New:
  - `src/fraud_detection/context_store_flow_binding/intake.py`
  - `config/platform/context_store_flow_binding/intake_policy_v0.yaml`
  - `tests/services/context_store_flow_binding/test_phase3_intake.py`

### Validation plan
- Targeted tests proving:
  - admitted context intake updates join frames deterministically,
  - flow bindings written only from flow-anchor lineage,
  - payload-hash mismatch for same dedupe tuple is anomaly/fail-closed,
  - apply-failure ledger stores machine-readable reason + source offsets.

---

## Entry: 2026-02-07 15:24:00 - Phase 3 implementation completed (intake apply worker + deterministic failure semantics)

### What was implemented
- Implemented intake runtime worker:
  - `src/fraud_detection/context_store_flow_binding/intake.py`
  - Supports file-bus and kinesis-bus read loops (`run_once`, `run_forever`) with per-topic/per-partition checkpoint resume.
- Implemented intake policy surface:
  - `config/platform/context_store_flow_binding/intake_policy_v0.yaml`
  - Pins context topic allowlist, class allowlist, run-scope gate, poll controls, and bus wiring defaults.
- Extended durable layer for Phase 3 intake invariants:
  - `src/fraud_detection/context_store_flow_binding/migrations.py`
    - migration `v2` with `csfb_intake_dedupe`.
  - `src/fraud_detection/context_store_flow_binding/store.py`
    - `CsfbIntakeApplyResult`
    - `apply_context_event_and_checkpoint(...)`
    - durable dedupe registration and payload-hash mismatch fail-closed path.
- Exported intake and intake result surfaces:
  - `src/fraud_detection/context_store_flow_binding/__init__.py`

### Decisions made during implementation (with reasoning)
1. **Deduplication is enforced in the same transaction as apply/checkpoint**
   - Decision: perform dedupe registration, join-frame mutation, optional flow-binding mutation, and checkpoint advance in one transaction.
   - Reasoning: this is the narrowest way to keep at-least-once safety and prevent checkpoint drift under duplicate/restart conditions.

2. **Duplicate replay semantics are checkpoint-advancing but state-stable**
   - Decision: if dedupe tuple is already known with the same payload hash, mark intake as `duplicate`, skip mutations, still advance checkpoint.
   - Reasoning: avoids hot-loop reprocessing on restart while preserving deterministic state.

3. **Payload-hash mismatch is fail-closed and machine-readable**
   - Decision: same dedupe tuple + different payload hash raises `INTAKE_PAYLOAD_HASH_MISMATCH`, records failure row, then advances checkpoint.
   - Reasoning: protects replay integrity and surfaces anomalies explicitly for operations/reconciliation.

4. **Flow-binding writer authority remains event-type gated**
   - Decision: only authoritative flow-anchor events produce `FlowBindingRecord`; non-authoritative events never mutate binding.
   - Reasoning: preserves ownership boundary and avoids accidental binding drift from non-anchor context events.

5. **Late context is explicit anomaly, not silent drop**
   - Decision: valid late events are applied but ledgered as `LATE_CONTEXT_EVENT` with watermark evidence.
   - Reasoning: keeps projection continuity while making out-of-order posture auditable.

6. **Missing join keys are hard failures**
   - Decision: events without required join-key fields (`merchant_id`, `arrival_seq`, scoped run pins) are recorded as `JOIN_KEY_MISSING` and checkpointed forward.
   - Reasoning: fail-closed posture without blocking partition progress.

7. **Implementation correction discovered by runtime tests**
   - Decision: corrected `_extract_join_key` callsite to pass keyword-only args (`payload=...`).
   - Reasoning: this was a real runtime bug in intake path (TypeError) that Phase 3 tests surfaced; fixed immediately before closure.

### Tests added for Phase 3
- `tests/services/context_store_flow_binding/test_phase3_intake.py`
  - `test_phase3_context_apply_and_authoritative_binding`
  - `test_phase3_dedupe_duplicate_advances_checkpoint_no_extra_mutation`
  - `test_phase3_payload_hash_mismatch_records_failure_and_advances_checkpoint`
  - `test_phase3_missing_and_late_context_are_machine_readable`

### Validation executed
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding/test_phase3_intake.py -q`
  - Result: `4 passed`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q`
  - Result: `21 passed`

### Phase 3 DoD mapping
- Intake consumes admitted context streams from EB: satisfied via topic/class allowlists and bus readers.
- Idempotent tuple and payload-hash mismatch semantics: satisfied via durable `csfb_intake_dedupe` + conflict handling.
- Authoritative binding updates from flow-anchor only: satisfied in intake binding builder and taxonomy gate.
- Late/missing context handling explicit and machine-readable: satisfied via `LATE_CONTEXT_EVENT` and `JOIN_KEY_MISSING` failure ledger entries.
- Apply-failure ledger with reasons and offsets: satisfied via `record_apply_failure(...)` paths across intake gate failures and conflicts.
