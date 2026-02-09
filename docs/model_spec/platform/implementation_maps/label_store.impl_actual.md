# Label Store Implementation Map
_As of 2026-02-09_

---

## Entry: 2026-02-09 03:26PM - Phase 5 planning kickoff (LS truth boundary and as-of semantics)

### Objective
Start Label Store planning with explicit phase gates that enforce append-only label truth and leakage-safe as-of reads.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5 sections)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/label_store.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`

### Decisions captured (planning posture)
- LS is the single authoritative writer for label truth timelines.
- Label truth is append-only; corrections are new assertions with explicit provenance.
- Dual-time semantics are mandatory (`effective_time`, `observed_time`) and explicit in read/write contracts.
- v0 primary subject key is `LabelSubjectKey=(platform_run_id,event_id)`; no cross-run leakage.
- Writer boundary idempotency + payload-hash collision detection is fail-closed.
- CM/external/engine truth lanes must enter through the same writer-boundary contract.

### Planned implementation sequencing
1. Contract + vocabulary/subject lock.
2. Writer boundary idempotency corridor.
3. Append-only persistence and correction semantics.
4. As-of and resolved query surfaces.
5. Source adapter lanes (CM + engine/external).
6. Observability/governance and ref-access audit integration.
7. OFS integration and dataset safety checks.
8. Integration closure and parity evidence.

### Invariants to enforce
- No write path bypasses LS truth boundary.
- Label assertions are replay-safe and deterministic under retries.
- As-of reads are explicit and leakage-safe by construction.
- Governance records include actor attribution + evidence refs, without payload leakage.

## Entry: 2026-02-09 03:30PM - Pre-change lock for Phase 1 implementation (LabelAssertion contract + IDs)

### Problem / goal
Close LS Phase 1 by pinning a runtime-validated LabelAssertion contract and deterministic identity/hashing behavior.

### Decisions locked before code
- LabelSubjectKey is execution-scoped: `(platform_run_id, event_id)`.
- Assertion identity is deterministic and derived from a stable anchor (`case_timeline_event_id`) + subject + label_type.
- Dual-time (`effective_time`, `observed_time`) is mandatory at write boundary.
- Payload hash canonicalization sorts evidence refs and excludes transport metadata.
- Human-source assertions require explicit `actor_id`; non-human sources remain provenance stamped but actor optional.

### Planned module set
- `src/fraud_detection/label_store/contracts.py`
- `src/fraud_detection/label_store/ids.py`
- `src/fraud_detection/label_store/__init__.py`
- tests under `tests/services/label_store/` for contracts and identity/hash determinism.

## Entry: 2026-02-09 03:40PM - Phase 1 implemented (LabelAssertion contract + deterministic IDs)

### Changes applied
- Added deterministic identity/hash helpers:
  - `src/fraud_detection/label_store/ids.py`
  - recipes pinned for `label_assertion_id` and canonical assertion payload hash.
- Added Label Store contract validators:
  - `src/fraud_detection/label_store/contracts.py`
  - `LabelSubjectKey`, `LabelAssertion`, `EvidenceRef`, label vocabulary enforcement, source/actor rules, pin checks, deterministic-id and hash checks.
- Added package exports:
  - `src/fraud_detection/label_store/__init__.py`
- Added authoritative schema:
  - `docs/model_spec/platform/contracts/case_and_labels/label_assertion.schema.yaml`
- Added taxonomy pin config:
  - `config/platform/label_store/taxonomy_v0.yaml`
- Added tests:
  - `tests/services/label_store/test_phase1_label_store_contracts.py`
  - `tests/services/label_store/test_phase1_label_store_ids.py`

### Validation
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py` -> `10 passed`.
- `python -m py_compile src/fraud_detection/label_store/__init__.py src/fraud_detection/label_store/contracts.py src/fraud_detection/label_store/ids.py` -> pass.

### Notes
- Canonical payload hash ordering rule (sorted evidence refs) is implemented and tested.
- Human assertions require `actor_id`; non-human sources are provenance-stamped with optional actor.

## Entry: 2026-02-09 06:28PM - Pre-change lock for Phase 2 (LS writer boundary + idempotency corridor)

### Objective
Close LS Phase 2 by implementing a deterministic writer boundary that validates assertions, enforces idempotency + payload-hash collision policy fail-closed, and returns durable acknowledgements only after commit.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/label_store.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.6/5.9 expectations)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (LS boundary semantics)
- `docs/model_spec/platform/component-specific/label_store.design-authority.md`
- Existing LS Phase 1 contracts/ids/tests in:
  - `src/fraud_detection/label_store/contracts.py`
  - `src/fraud_detection/label_store/ids.py`
  - `tests/services/label_store/test_phase1_label_store_contracts.py`
  - `tests/services/label_store/test_phase1_label_store_ids.py`

### Problem framing
Phase 1 pins schema/identity, but no concrete LS writer boundary exists yet. Missing capabilities:
1. no durable assertion write path,
2. no dedupe tuple enforcement against persisted rows,
3. no payload hash mismatch anomaly logging + fail-closed outcome,
4. no deterministic retry semantics for repeated writes.

### Alternatives considered
1. Integrate directly into CM label handshake persistence tables.
- Rejected: violates LS truth ownership boundary and couples CM/LS state.
2. Add dedicated LS writer ledger module with its own storage boundary and deterministic write outcomes.
- Selected: aligns with ownership doctrine and enables later Phase 3/4 expansion.

### Decisions locked before edits
1. Implement a dedicated LS writer ledger module in `label_store` package supporting sqlite/postgres locators.
2. Writer API will accept LabelAssertion payload mapping and return deterministic write result (`ACCEPTED` or `REJECTED`) plus stable assertion reference.
3. Dedupe semantics:
- first insert => `ACCEPTED`,
- same assertion id + same payload hash => `ACCEPTED` (replay-safe duplicate),
- same assertion id + different payload hash => `REJECTED` with mismatch evidence persisted.
4. Provenance enforcement at writer boundary:
- requires non-empty evidence refs,
- otherwise fail-closed rejection (`MISSING_EVIDENCE_REFS`).
5. Add Phase 2 tests covering new write, duplicate replay, mismatch fail-closed, invalid contract rejection, and deterministic retry outcomes.

### Planned files
- New:
  - `src/fraud_detection/label_store/writer_boundary.py`
  - `tests/services/label_store/test_phase2_writer_boundary.py`
- Update:
  - `src/fraud_detection/label_store/__init__.py`
  - `docs/model_spec/platform/implementation_maps/label_store.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/label_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase2_writer_boundary.py`
- `python -m pytest -q tests/services/label_store/test_phase2_writer_boundary.py`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`

## Entry: 2026-02-09 06:30PM - Phase 2 implemented and validated (LS writer boundary + idempotency corridor)

### Implementation completed
1. Added concrete LS writer boundary module:
- `src/fraud_detection/label_store/writer_boundary.py`
- sqlite/postgres locator support with transaction-safe writes.
- writer API: `write_label_assertion(assertion_payload)`.

2. Added deterministic outcome semantics:
- new assertion commit -> `ACCEPTED` / `ASSERTION_COMMITTED_NEW`.
- duplicate replay with same payload hash -> `ACCEPTED` / `ASSERTION_REPLAY_MATCH`.
- same deterministic assertion id with different payload hash -> `REJECTED` / `PAYLOAD_HASH_MISMATCH` (fail-closed).
- invalid contract -> `REJECTED` / `CONTRACT_INVALID:*`.
- missing evidence refs -> `REJECTED` / `MISSING_EVIDENCE_REFS`.

3. Added durable state + anomaly persistence:
- assertion ledger table: `ls_label_assertions`.
- mismatch evidence table: `ls_label_assertion_mismatches`.
- deterministic assertion reference generation:
  - `runs/fraud-platform/<platform_run_id>/label_store/assertions/<label_assertion_id>.json`.

4. Added lookup/testing helper surfaces:
- `lookup_assertion(label_assertion_id=...)`
- `mismatch_count(label_assertion_id=...)`

5. Added Phase 2 test matrix:
- `tests/services/label_store/test_phase2_writer_boundary.py`.
- coverage:
  - new assertion commit,
  - deterministic duplicate replay,
  - payload hash mismatch fail-closed + mismatch log,
  - invalid-contract rejection,
  - missing-evidence-ref rejection.

6. Updated package exports:
- `src/fraud_detection/label_store/__init__.py` now exports Phase 2 writer surfaces/constants.

### Key mechanics delivered
- LS now has its own concrete writer corridor and no longer depends on hypothetical storage behavior.
- Idempotency is deterministic under at-least-once retries.
- Collision policy is explicit and fail-closed with persisted mismatch evidence.
- Writer outcome semantics are stable for CM/adapter integration in subsequent phases.

### Validation evidence
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase2_writer_boundary.py`
  - result: pass
- `python -m pytest -q tests/services/label_store/test_phase2_writer_boundary.py`
  - result: `5 passed`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py`
  - result: `15 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `10 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `44 passed`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`
  - result: `2 passed`

### Phase closure statement
- LS Phase 2 DoD is satisfied:
  - writer boundary validates schema/pins/provenance,
  - dedupe + payload-hash collision policy is enforced fail-closed,
  - write acknowledgement is returned only after transactional commit,
  - retry outcomes are deterministic.
