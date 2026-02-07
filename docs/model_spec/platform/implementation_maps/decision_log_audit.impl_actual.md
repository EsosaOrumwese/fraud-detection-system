# Decision Log & Audit Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:15:05 — Phase 4 planning kickoff (DLA scope + audit record)

### Problem / goal
Pin the DLA v0 audit-record requirements and ingestion posture before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_log_audit.design-authority.md`
- Platform rails (append-only truth, by-ref evidence, no silent corrections).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DLA is the **immutable flight recorder** for decision context + outcomes.
- DLA consumes DecisionResponse + ActionOutcome events from EB (no direct writers).
- Audit records are **append-only** in object storage; Postgres holds lookup index only.
- Audit record must include: decision event ref, outcome refs (when available), bundle ref, snapshot hash + ref, graph_version, eb_offset_basis, degrade_posture, policy_rev, run_config_digest, and explicit context offsets when present.
- If provenance is incomplete, DLA quarantines rather than writing partial truth.

### Planned implementation scope (Phase 4.5)
- Implement EB consumer for decision/outcome events and object-store writer for audit records.
- Implement Postgres audit index with deterministic keys.

---

## Entry: 2026-02-07 18:20:38 - Plan: expand DLA build plan to executable Phase 4.5 component map

### Trigger
Platform `4.5` now has detailed `4.5.A...4.5.J` gates. DLA component plan remains a 3-phase scaffold and is too shallow for deterministic audit closure execution.

### Authorities used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`4.5.A...4.5.J`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (DLA commit-point ordering, audit evidence boundary)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (decision -> action -> outcome -> audit lineage)
- `docs/model_spec/platform/component-specific/decision_log_audit.design-authority.md`

### Design decisions before editing
1. Expand DLA into explicit phases that separate:
   - intake/validation,
   - append-only writer/evidence refs,
   - index/query surfaces,
   - checkpoint/commit ordering,
   - reconciliation and security.
2. Keep ownership strict:
   - DLA is append-only audit truth,
   - no mutation/correction semantics,
   - no direct AL side-effect ownership.
3. Encode commit gate semantics explicitly:
   - v0 ordering requires durable DLA append before relevant checkpoint advancement.
4. Require parity-proof and replay-proof closure gates in the component plan.
5. Keep progressive elaboration + rolling status so implementation can proceed phase by phase.

### Planned file updates
- Update `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md` with expanded phased DoD map.
- Append post-change outcome entry here and logbook entry.

---

## Entry: 2026-02-07 18:21:46 - DLA build plan expansion applied

### Scope completed
Updated:
- `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md`

Replaced prior 3-phase scaffold with an executable 8-phase map:
1. audit contracts + evidence model,
2. storage layout + append-only substrate,
3. intake consumer + fail-closed validation,
4. deterministic lineage assembly (decision->intent->outcome),
5. index + query contract,
6. commit ordering + checkpoint/replay determinism,
7. observability/reconciliation/security,
8. platform integration closure (`4.5` DLA scope).

### Why this is correct
- Aligns DLA component plan to platform `4.5` audit-closure expectations.
- Encodes v0 commit-gate semantics and fail-closed provenance as explicit DoD gates.
- Separates append-only audit ownership from AL execution ownership to avoid boundary drift.

### Residual posture
- Planning expansion only; no DLA runtime implementation started in this entry.
- Current focus is now explicitly Phase 1 in the DLA build plan.

---

## Entry: 2026-02-07 18:31:23 - Phase 1 lockstep implementation applied (contracts first, then storage foundation)

### Scope executed
Implemented DLA Phase 1 contract surfaces and lockstep storage/index foundation.

### Decisions made during implementation
1. Preserve append-only audit contract as strict boundary.
   - Added code validators for `AuditRecord` required provenance fields and fail-closed semantics.
2. Keep evidence model by-ref and deterministic.
   - Enforced event ref/offset structures, context role taxonomy, and run pin requirements.
3. Start storage in lockstep with AL using foundation primitives.
   - Added DLA storage layout resolver + deterministic object-key builder.
   - Added durable index store primitive with deterministic digest-based duplicate/mismatch handling.
4. Avoid premature consumer/writer runtime.
   - Kept this pass at contract + storage foundation level; intake pipelines come in later phases.

### Files added/updated
- Added:
  - `src/fraud_detection/decision_log_audit/__init__.py`
  - `src/fraud_detection/decision_log_audit/contracts.py`
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `tests/services/decision_log_audit/test_dla_phase1_contracts.py`
  - `tests/services/decision_log_audit/test_dla_phase1_storage.py`
- Updated:
  - `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md` (Phase 1 evidence + status)

### Validation evidence
- Command:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`
- Result:
  - `14 passed` (includes DLA Phase 1 tests and lockstep AL tests run together).

### DoD mapping status
- Phase 1 (DLA contract/evidence model): **complete**.
- Storage kickoff delivered in lockstep; full Phase 2 closure continues next.

---

## Entry: 2026-02-07 19:42:10 - Phase 2 pre-implementation plan (storage layout + append-only substrate)

### Trigger
User requested to move to DLA Phase 2 implementation.

### Authorities used
- `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`4.5.D`, `4.5.G`, `4.5.I`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`

### Problem framing
Phase 1 delivered contracts and an index foundation, but Phase 2 still requires:
1. explicit append-only object-record writer semantics,
2. pinned deterministic object-store prefix layout for environment ladder,
3. deterministic index lookup surfaces and schema parity expectations,
4. explicit retention posture for `local/local_parity/dev/prod`.

### Design decisions before coding
1. Add a DLA storage policy file under `config/platform/dla/` with profile-scoped object prefixes and retention windows.
   - Reasoning: this pins env-ladder storage semantics in config rather than implicit code defaults.
2. Add `load_storage_policy(...)` and extend `build_storage_layout(...)` to resolve prefix+retention from profile when requested.
   - Reasoning: layout resolution should be deterministic and testable for parity/dev/prod.
3. Add an append-only object writer in storage module.
   - Reasoning: Phase 2 requires immutable write semantics at object boundary; duplicates are tolerated, hash mismatches are quarantined.
4. Extend index store with deterministic read surfaces (`get_by_audit_id`, run-scope listing, decision-event listing).
   - Reasoning: lookup keys and ordering must be pinned now for later DLA phases.
5. Keep Phase 2 scope bounded.
   - Reasoning: intake consumer/runtime assembly belongs to Phase 3; Phase 2 focuses on substrate only.

### Planned file changes
- Add `config/platform/dla/storage_policy_v0.yaml`
- Update `src/fraud_detection/decision_log_audit/storage.py`
  - policy loader + retention dataclasses,
  - append-only object writer,
  - deterministic index query helpers.
- Update `src/fraud_detection/decision_log_audit/__init__.py` exports.
- Add `tests/services/decision_log_audit/test_dla_phase2_storage.py`
- Update `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md` Phase 2 status/evidence after validation.

### Validation plan
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase2_storage.py -q`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`

---
## Entry: 2026-02-07 20:24:08 - Phase 2 implementation closure (storage layout + append-only substrate)

### What was implemented
1. Added explicit env-ladder storage policy for DLA.
   - Added `config/platform/dla/storage_policy_v0.yaml` with required profiles: `local`, `local_parity`, `dev`, `prod`.
   - Each profile now pins `object_store_prefix` and retention windows (`audit_record_ttl_days`, `index_ttl_days`, `reconciliation_ttl_days`).

2. Extended DLA storage module to resolve deterministic layout from policy.
   - Added dataclasses: `DecisionLogAuditRetentionWindow`, `DecisionLogAuditStorageProfile`, `DecisionLogAuditStoragePolicy`.
   - Added `load_storage_policy(...)` with strict validation (required profiles, non-empty ids, positive TTLs).
   - Extended `build_storage_layout(...)` so `profile_id + storage_policy_path` resolve prefix + retention deterministically.

3. Implemented append-only object substrate.
   - Added `DecisionLogAuditObjectStore.append_audit_record(...)`.
   - Write semantics are explicit and immutable:
     - `NEW` when object key does not exist,
     - `DUPLICATE` when same digest already exists,
     - `HASH_MISMATCH` when same key exists with different digest (no overwrite).
   - Object refs are normalized and path-traversal guarded via `_object_ref_to_relative_path(...)`.

4. Added deterministic index read surfaces to complete Phase 2 lookup substrate.
   - Added `DecisionLogAuditIndexRecord` and readers:
     - `get_by_audit_id(...)`
     - `list_by_run_scope(...)`
     - `list_by_decision_event(...)`
   - Added stable ordering (`recorded_at_utc, audit_id`) and bounded limits for deterministic parity behavior.

5. Updated component exports for new Phase 2 surfaces.
   - Updated `src/fraud_detection/decision_log_audit/__init__.py` to export policy + object/index read/write types.

### Decisions made during implementation (with reasoning)
1. **Policy-as-config instead of hardcoded retention**
   - Decision: keep env retention + prefix policy in YAML, not in code constants.
   - Reasoning: this avoids code edits for environment changes and keeps parity/dev/prod posture auditable.

2. **Append-only object store returns tri-state status instead of throwing on duplicates**
   - Decision: duplicates and mismatches return explicit statuses.
   - Reasoning: downstream commit/checkpoint gates in later phases need deterministic branch outcomes, not ambiguous exceptions.

3. **Deterministic read APIs in Phase 2 (not delayed to query phase)**
   - Decision: add read surfaces now to lock key semantics early.
   - Reasoning: later intake/reconciliation phases depend on stable lookup behavior; late introduction would shift risk forward.

4. **Path safety guard at object-ref conversion boundary**
   - Decision: reject absolute paths and `..` path segments.
   - Reasoning: fail-closed storage boundary is mandatory under platform security doctrine.

### Files touched for Phase 2
- Added:
  - `config/platform/dla/storage_policy_v0.yaml`
  - `tests/services/decision_log_audit/test_dla_phase2_storage.py`
- Updated:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase2_storage.py -q`
  - Result: `4 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - Result: `10 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`
  - Result: `55 passed`.

### DoD closure assessment
- Object-store prefix layout pinned per environment ladder: **met**.
- Append-only writer semantics enforced with no overwrite path: **met**.
- Deterministic index schema + lookup keys/read surfaces: **met**.
- Retention posture defined for local/local-parity/dev/prod: **met**.

### Status handoff
- DLA Phase 2 is **green** at component scope.
- Next phase focus in build plan: Phase 3 (`Intake consumer + fail-closed validation`).

---
## Entry: 2026-02-07 20:32:35 - Phase 3 pre-implementation plan (intake consumer + fail-closed validation)

### Trigger
User requested to proceed with DLA Phase 3.

### Authorities used
- `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (fail-closed schema/version policy, quarantine posture, DLA commit-point requirements)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (EB inlet semantics, ContextPins, payload-hash anomaly posture)
- `docs/model_spec/platform/component-specific/decision_log_audit.design-authority.md` (admissibility gate, non-wedging quarantine behavior)

### Problem framing
Phase 2 gave immutable storage primitives, but DLA still lacks the runtime intake boundary that:
1. consumes admitted EB traffic safely,
2. applies strict event-family/schema/pin checks,
3. quarantines malformed/incomplete payloads with explicit reason taxonomy,
4. keeps checkpoint progression coupled to durable write outcomes.

Without this, Phase 3 DoD remains open and Phase 4 lineage assembly would be built on an unstable inlet.

### Alternatives considered
1. **Only add an inlet validator module (no durable processor/store coupling yet).**
   - Pros: fast.
   - Cons: does not satisfy "checkpoint does not advance on failed validation/write"; insufficient for DoD.
2. **Add full DLA runtime with lineage assembly now.**
   - Pros: fewer future rewires.
   - Cons: crosses into Phase 4 scope and mixes concerns.
3. **Add bounded Phase 3 intake stack: policy + inlet + intake store + processor + bus consumer wrapper.**
   - Pros: satisfies all Phase 3 DoD without leaking into Phase 4 lineage semantics.
   - Cons: adds one more internal surface to evolve in Phase 4.

### Decision
Choose **Alternative 3**.

### Concrete design decisions (pre-code)
1. Introduce `config/platform/dla/intake_policy_v0.yaml`.
   - Will pin admitted topics, allowed DLA event families (`decision_response`, `action_intent`, `action_outcome`), allowed schema versions, and required pins.
2. Add DLA intake policy loader module.
   - Mirrors DF policy-loader rigor: strict payload shape, deterministic digest, explicit compatibility checks.
3. Add DLA inlet evaluator module.
   - Validates canonical envelope schema, topic admission, event family/version, required pins, and payload contract compatibility.
   - Payload contract checks use existing contract validators:
     - `DecisionResponse` + `ActionIntent` from DF contracts,
     - `ActionOutcome` from AL contracts.
4. Add explicit quarantine reason taxonomy in inlet results.
   - Keep reasons machine-readable and stable for ops/reconciliation.
5. Extend DLA storage with intake-side durable tables.
   - Intake candidates table (append-only semantics with deterministic dedupe and payload-hash mismatch detection).
   - Intake quarantine table (durable lane for malformed/incomplete records).
   - Intake checkpoints table (per topic/partition progress).
6. Add intake processor service with commit gate semantics.
   - Checkpoint advances only when candidate/quarantine write succeeds (`NEW` or idempotent `DUPLICATE`).
   - Any write failure is fail-closed (`checkpoint_advanced=False`).
7. Add minimal bus consumer wrapper (`run_once`) to process file-bus/Kinesis records through the processor.
   - Enables parity harness and future phase wiring.
8. Add targeted Phase 3 tests for:
   - allowed-family/schema acceptance,
   - malformed/incomplete quarantine reasons,
   - checkpoint gating on write failure.

### Planned file changes
- Add `config/platform/dla/intake_policy_v0.yaml`
- Add `src/fraud_detection/decision_log_audit/config.py`
- Add `src/fraud_detection/decision_log_audit/inlet.py`
- Add `src/fraud_detection/decision_log_audit/intake.py`
- Update `src/fraud_detection/decision_log_audit/storage.py`
- Update `src/fraud_detection/decision_log_audit/__init__.py`
- Add `tests/services/decision_log_audit/test_dla_phase3_intake.py`
- Update DLA build-plan + impl_actual + logbook on closure

### Validation plan
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase3_intake.py -q`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

---
## Entry: 2026-02-07 20:52:01 - Phase 3 implementation closure (intake consumer + fail-closed validation)

### Implementation summary
Phase 3 is now implemented as a bounded intake layer (policy + inlet + processor + durable intake substrate), without crossing into Phase 4 lineage assembly.

### Decisions made during implementation (with reasoning)

1. **Pinned intake policy in config instead of hardcoded event routing.**
   - Added `config/platform/dla/intake_policy_v0.yaml` and loader `src/fraud_detection/decision_log_audit/config.py`.
   - Decision: explicit allowlist for `decision_response`, `action_intent`, `action_outcome` with schema-version constraints.
   - Reasoning: fail-closed compatibility must be externally auditable and environment-tunable.

2. **Used canonical-envelope + payload-contract dual validation.**
   - Added `src/fraud_detection/decision_log_audit/inlet.py`.
   - Decision: inlet first validates canonical envelope schema, then validates payload contract using existing domain contracts:
     - `DecisionResponse` + `ActionIntent` from DF,
     - `ActionOutcome` from AL.
   - Reasoning: this satisfies "invalid or incomplete events are quarantined" without duplicating contract logic in DLA.

3. **Introduced explicit reason taxonomy for quarantine lanes.**
   - Inlet reason codes now include:
     - `INVALID_ENVELOPE`, `NON_AUDIT_TOPIC`, `UNKNOWN_EVENT_FAMILY`, `SCHEMA_VERSION_REQUIRED`,
     - `SCHEMA_VERSION_NOT_ALLOWED`, `MISSING_REQUIRED_PINS`, `RUN_SCOPE_MISMATCH`, `MISSING_EVENT_ID`, `PAYLOAD_CONTRACT_INVALID`.
   - Processor reason codes add write-path semantics:
     - `WRITE_FAILED`, `PAYLOAD_HASH_MISMATCH`.
   - Reasoning: reason-stable taxonomy is needed for reconciliation and operational triage in later phases.

4. **Checkpoint progression is now explicitly gated by durable writes.**
   - Extended `src/fraud_detection/decision_log_audit/storage.py` with `DecisionLogAuditIntakeStore`:
     - `dla_intake_candidates` (append-only accepted events),
     - `dla_intake_quarantine` (durable reject lane),
     - `dla_intake_checkpoints` (consumer progress).
   - Added `src/fraud_detection/decision_log_audit/intake.py` processor/consumer.
   - Decision: checkpoint advances only after successful `append_candidate` or successful `append_quarantine`.
   - Reasoning: this is the core Phase 3 DoD and aligns with RTDL commit safety posture.

5. **Handled hash-collision anomaly at intake substrate boundary.**
   - Decision: candidate dedupe key is `(platform_run_id, event_type, event_id)` with stored `payload_hash`.
   - If same key arrives with different hash, processor writes quarantine (`PAYLOAD_HASH_MISMATCH`) and only then advances checkpoint.
   - Reasoning: prevents silent overwrite and preserves anomaly evidence deterministically.

6. **Kept bus runtime wrapper minimal but parity-capable.**
   - Added `DecisionLogAuditBusConsumer` with `run_once`/`run_forever`, supporting both file-bus and Kinesis readers.
   - Reasoning: enough runtime surface for parity operations while deferring lineage-specific assembly to Phase 4.

### Files added/updated for Phase 3
- Added:
  - `config/platform/dla/intake_policy_v0.yaml`
  - `src/fraud_detection/decision_log_audit/config.py`
  - `src/fraud_detection/decision_log_audit/inlet.py`
  - `src/fraud_detection/decision_log_audit/intake.py`
  - `tests/services/decision_log_audit/test_dla_phase3_intake.py`
- Updated:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md`

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase3_intake.py -q`
  - Result: `8 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - Result: `18 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`
  - Result: `63 passed`.

### Phase 3 DoD closure mapping
- Consumer accepts only allowed families/schemas: **met** (`intake_policy` + inlet allowlist/version gates).
- Envelope + pins + schema compatibility validated fail-closed: **met**.
- Invalid/incomplete events quarantined with explicit reason taxonomy: **met**.
- Checkpoint does not advance on failed validation/write paths: **met** (processor tests include forced write failures).

### Status handoff
- DLA Phase 3 is **green** at component boundary.
- Next DLA build-plan focus: Phase 4 (`Lineage assembly (decision -> intent -> outcome)`).

---
