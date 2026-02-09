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

## Entry: 2026-02-09 06:34PM - Pre-change lock for Phase 3 (LS append-only timeline persistence)

### Objective
Close LS Phase 3 by persisting authoritative append-only label timeline entries, enforcing deterministic timeline ordering semantics, and adding rebuild-safe timeline recovery support from assertion ledger truth.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/label_store.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.6 expectations)
- `docs/model_spec/platform/component-specific/label_store.design-authority.md` (append-only labels, correction semantics, deterministic timeline reads)
- Existing LS Phase 2 writer corridor in `src/fraud_detection/label_store/writer_boundary.py`

### Problem framing
Phase 2 implemented writer idempotency corridor but current persisted shape is assertion-ledger centric and does not expose an explicit append-only timeline surface nor rebuild utility. Missing gates:
1. no dedicated immutable timeline table optimized for subject-history reads,
2. no deterministic timeline read API with pinned ordering rules,
3. no explicit rebuild path to restore timeline rows from assertion ledger truth.

### Alternatives considered
1. Treat `ls_label_assertions` as both idempotency ledger and timeline read surface.
- Rejected: concerns are conflated; timeline reads and rebuild semantics are less explicit.
2. Add dedicated `ls_label_timeline` append-only table fed only on accepted-new assertions, with deterministic read API and rebuild helper from assertion ledger.
- Selected: clean truth/read separation, auditable append-only lane, explicit restore posture.

### Decisions locked before edits
1. Add `ls_label_timeline` table with one immutable row per accepted assertion id (`label_assertion_id` PK).
2. Insert timeline row only when write outcome is `ASSERTION_COMMITTED_NEW`; duplicate replay/mismatch never appends new timeline truth.
3. Define deterministic timeline ordering as:
- `observed_time ASC`, tie-break `effective_time ASC`, tie-break `label_assertion_id ASC`.
4. Persist provenance/evidence by reference on timeline rows (`source_type`, `actor_id`, `evidence_refs_json`, pins via assertion payload reference fields).
5. Provide `rebuild_timeline_from_assertion_ledger()` utility that repopulates missing timeline rows from `ls_label_assertions.assertion_json` without mutating existing rows.
6. Add dedicated Phase 3 matrix tests for append-only behavior, deterministic ordering, provenance refs persistence, and rebuild safety.

### Planned files
- Update:
  - `src/fraud_detection/label_store/writer_boundary.py`
  - `src/fraud_detection/label_store/__init__.py`
- New:
  - `tests/services/label_store/test_phase3_timeline_persistence.py`
- Documentation updates after validation:
  - `docs/model_spec/platform/implementation_maps/label_store.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/label_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase3_timeline_persistence.py`
- `python -m pytest -q tests/services/label_store/test_phase3_timeline_persistence.py`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`

## Entry: 2026-02-09 06:38PM - Phase 3 implemented and validated (LS append-only timeline persistence)

### Implementation completed
1. Extended LS writer boundary with explicit append-only timeline truth:
- updated `src/fraud_detection/label_store/writer_boundary.py`
- added immutable `ls_label_timeline` table (one row per accepted assertion id), separate from idempotency ledger.
- timeline row insert now occurs only for `ASSERTION_COMMITTED_NEW` outcomes.

2. Added deterministic timeline read surface:
- `list_timeline(platform_run_id, event_id, label_type=None)`
- ordering pinned as:
  - `observed_time ASC`
  - tie-break `effective_time ASC`
  - tie-break `label_assertion_id ASC`

3. Added rebuild-safe restore utility:
- `rebuild_timeline_from_assertion_ledger()`
- repopulates missing timeline rows from `ls_label_assertions.assertion_json` using contract re-validation and idempotent insert semantics.

4. Added Phase 3 data type exports:
- `LabelTimelineEntry` exported via `src/fraud_detection/label_store/__init__.py`.

5. Added Phase 3 validation matrix:
- `tests/services/label_store/test_phase3_timeline_persistence.py`
- coverage includes:
  - append-only correction behavior,
  - deterministic ordering under out-of-order writes,
  - duplicate replay non-append guarantee + evidence-ref persistence,
  - rebuild restore from assertion ledger after timeline wipe.

### Key mechanics delivered
- Label timeline truth is now an explicit append-only surface independent from mutable replay/mismatch counters.
- Corrections are represented as new assertions (new timeline rows) with historical continuity preserved.
- Rebuild utility provides operational safety for timeline recovery without mutating assertion truth.

### Validation evidence
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase3_timeline_persistence.py`
  - result: pass
- `python -m pytest -q tests/services/label_store/test_phase3_timeline_persistence.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py`
  - result: `19 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `10 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `44 passed`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`
  - result: `2 passed`

### Phase closure statement
- LS Phase 3 DoD is satisfied:
  - append-only timeline persistence is implemented,
  - deterministic timeline ordering is enforced,
  - provenance/evidence refs are persisted by reference,
  - rebuild-safe restore path is available and tested.

## Entry: 2026-02-09 06:42PM - Pre-change lock for Phase 4 (LS as-of and resolved-query surfaces)

### Objective
Close LS Phase 4 by implementing leakage-safe `label_as_of` and deterministic resolved-query surfaces over append-only timeline truth.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/label_store.build_plan.md` (Phase 4 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.6 requirements)
- `docs/model_spec/platform/component-specific/label_store.design-authority.md` (as-of semantics, conflict posture)
- Existing LS timeline truth from Phase 3 in `src/fraud_detection/label_store/writer_boundary.py`

### Problem framing
LS now persists append-only timeline rows, but Phase 4 requires explicit read surfaces for learning/governance safety:
1. no dedicated `label_as_of(subject, T)` API yet,
2. no explicit conflict posture surface for resolved view,
3. no stable read contract for consumers (OFS/MF) beyond raw timeline listing.

### Alternatives considered
1. Return only raw timeline rows and leave as-of/resolution to callers.
- Rejected: repeats interpretation logic across consumers and increases leakage risk.
2. Implement explicit as-of/resolved APIs in LS writer boundary with deterministic precedence and conflict signaling.
- Selected: centralizes semantics and satisfies DoD directly.

### Decisions locked before edits
1. Add `label_as_of(...)` method with required `as_of_observed_time` parameter and strict observed-time eligibility (`observed_time <= T_asof`).
2. Add `resolved_labels_as_of(...)` method returning per-label-type resolved snapshots for a subject at `T_asof`.
3. Conflict posture will be explicit:
- if multiple eligible assertions for the same label_type share the highest precedence key (`effective_time`, `observed_time`) but disagree on `label_value`, return `CONFLICT` with candidate refs.
4. Deterministic precedence for non-conflict resolution:
- highest `effective_time`, then highest `observed_time`, then highest `label_assertion_id`.
5. Add Phase 4 test matrix covering:
- observed-time eligibility,
- deterministic resolution,
- explicit conflict surface,
- query contract stability.

### Planned files
- Update:
  - `src/fraud_detection/label_store/writer_boundary.py`
  - `src/fraud_detection/label_store/__init__.py`
- New:
  - `tests/services/label_store/test_phase4_as_of_queries.py`
- Documentation updates after validation:
  - `docs/model_spec/platform/implementation_maps/label_store.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/label_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase4_as_of_queries.py`
- `python -m pytest -q tests/services/label_store/test_phase4_as_of_queries.py`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`

## Entry: 2026-02-09 06:47PM - Phase 4 implemented and validated (LS as-of and resolved-query surfaces)

### Implementation completed
1. Finalized leakage-safe as-of read surface in `src/fraud_detection/label_store/writer_boundary.py`:
- `label_as_of(platform_run_id, event_id, label_type, as_of_observed_time)` now enforces explicit observed-time eligibility (`observed_time <= as_of_observed_time`).
- Resolution outputs explicit status posture: `RESOLVED`, `CONFLICT`, `NOT_FOUND`.

2. Finalized deterministic resolved-query surface:
- `resolved_labels_as_of(platform_run_id, event_id, as_of_observed_time)` returns stable per-label-type outputs by delegating to the same `label_as_of(...)` semantics.
- Label types are emitted in deterministic sorted order for caller stability.

3. Finalized deterministic precedence + conflict posture:
- non-conflict precedence key is pinned as highest `(effective_time, observed_time, label_assertion_id)`.
- if top-precedence ties disagree on `label_value`, the surface returns explicit `CONFLICT` with candidate assertion IDs + values.

4. Finalized package exports for Phase 4 consumers:
- `src/fraud_detection/label_store/__init__.py` exports `LabelAsOfResolution` and `LS_AS_OF_*` status constants.

5. Added and validated dedicated Phase 4 matrix tests:
- `tests/services/label_store/test_phase4_as_of_queries.py`
- covers observed-time eligibility, explicit conflict handling, stable per-label-type contract, and `NOT_FOUND` posture.

### Decision trail and rationale
- During Phase 4 execution, the core code/test surfaces were already present in working state from the active implementation thread. I treated this as an in-progress draft, then executed the full Phase 4 validation gate before closure so closure is evidence-backed rather than inferred.
- No additional architectural change was required beyond the pre-change lock decisions at `06:42PM`; behavior matched the pinned Phase 4 decisions.

### Validation evidence
- `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase4_as_of_queries.py`
  - result: pass
- `python -m pytest -q tests/services/label_store/test_phase4_as_of_queries.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py`
  - result: `23 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `10 passed`

### Phase closure statement
- LS Phase 4 DoD is satisfied:
  - timeline-by-subject and as-of read surfaces are implemented,
  - observed-time eligibility is explicit and enforced,
  - resolved conflict posture is explicit and deterministic,
  - query contract is stable for downstream OFS/MF consumers.

## Entry: 2026-02-09 06:50PM - Pre-change lock for Phase 5 (LS ingest adapters for CM + engine/external truth lanes)

### Objective
Close LS Phase 5 by implementing adapter boundaries that admit CM/external/engine truth lanes into LS exclusively through the same writer-boundary contract, with deterministic source identity and fail-closed posture.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/label_store.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.6 + Phase 5.7 alignment)
- `docs/model_spec/platform/component-specific/label_store.design-authority.md`:
  - external adjudication allowed as delayed truth writer,
  - engine truth_products must be translated through explicit writer,
  - idempotency + dual-time + by-ref evidence non-negotiables.
- Existing LS foundations:
  - `src/fraud_detection/label_store/contracts.py`
  - `src/fraud_detection/label_store/writer_boundary.py`
- Existing CM->LS handshake lane in `src/fraud_detection/case_mgmt/label_handshake.py`.

### Problem framing
Phase 1..4 closed contracts, writer corridor, timeline persistence, and as-of reads. Phase 5 still lacks an explicit adapter boundary for non-CM truth lanes. Without this, external/engine writes are ad hoc and can drift from contract/provenance/idempotency expectations.

### Alternatives considered
1. Reuse `write_label_assertion(...)` directly everywhere and leave adaptation to callers.
- Rejected: semantics and provenance discipline would fragment across services.
2. Add a single LS-owned ingest adapter module with source-specific adapter functions that always produce canonical LabelAssertion payloads and call writer boundary.
- Selected: central contract gate, deterministic source identity, and auditable lane behavior.

### Decisions locked before edits
1. Introduce `src/fraud_detection/label_store/adapters.py` with explicit source lanes:
- `CM_ASSERTION` (pass-through normalized write),
- `EXTERNAL_ADJUDICATION` (mapped write),
- `ENGINE_TRUTH` (mapped write).
2. Non-CM lanes must derive deterministic `case_timeline_event_id` from `(writer_namespace, source_ref_id, label_subject_key, label_type)` to satisfy LS identity contract under retries.
3. Adapters remain thin and policy-safe:
- no direct table writes,
- all writes must call `LabelStoreWriterBoundary.write_label_assertion(...)`.
4. Evidence is by-ref only and required for all writes; adapters fail closed if minimum references are absent.
5. Source provenance is explicit:
- CM keeps submitted source_type/actor semantics,
- external lane defaults to `source_type=EXTERNAL` and actor namespace `EXTERNAL::<provider>` unless explicit actor provided,
- engine lane uses `source_type=SYSTEM` and actor namespace `SYSTEM::engine_truth_writer`.
6. Add dedicated Phase 5 tests to prove acceptance/replay/fail-closed posture per source lane.

### Planned files
- New:
  - `src/fraud_detection/label_store/adapters.py`
  - `tests/services/label_store/test_phase5_ingest_adapters.py`
- Update:
  - `src/fraud_detection/label_store/__init__.py`
- Documentation updates after validation:
  - `docs/model_spec/platform/implementation_maps/label_store.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/label_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/label_store/adapters.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase5_ingest_adapters.py`
- `python -m pytest -q tests/services/label_store/test_phase5_ingest_adapters.py`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`

## Entry: 2026-02-09 06:53PM - Phase 5 implemented and validated (LS ingest adapters)

### Implementation completed
1. Added dedicated LS ingest adapter module:
- `src/fraud_detection/label_store/adapters.py`
- Introduced explicit source lanes:
  - `CM_ASSERTION`
  - `EXTERNAL_ADJUDICATION`
  - `ENGINE_TRUTH`
- Added `ingest_label_from_source(...)` as the single adapter entrypoint.

2. Enforced fail-closed adaptation discipline:
- unsupported source classes are rejected.
- required source identity fields are mandatory per lane (`external_ref_id`, `provider_id`, `truth_record_id`, `engine_bundle_id`, etc.).
- source-type constraints are lane-specific and fail-closed (`EXTERNAL` for external lane, `SYSTEM` for engine lane).

3. Implemented deterministic identity input for non-CM writes:
- added recipe constant `ls.adapter.case_timeline_event_id.v1`.
- non-CM lanes derive deterministic `case_timeline_event_id` from:
  - writer namespace,
  - source ref id,
  - label subject key,
  - label type.
- This keeps retries stable without introducing mutable caller-side IDs.

4. Preserved writer-boundary ownership:
- adapters do not write tables directly.
- all adapted payloads are validated through `LabelAssertion.from_payload(...)` then committed only via `LabelStoreWriterBoundary.write_label_assertion(...)`.

5. Added Phase 5 exports for consumers:
- updated `src/fraud_detection/label_store/__init__.py` with adapter surfaces/constants.

6. Added dedicated Phase 5 matrix tests:
- `tests/services/label_store/test_phase5_ingest_adapters.py`
- coverage includes:
  - CM assertion pass-through + replay determinism,
  - external adjudication mapping + provenance + deterministic replay,
  - engine truth mapping + provenance + deterministic replay,
  - fail-closed unsupported source,
  - fail-closed missing required external identity.

### Decision trail and rationale
- We considered leaving source adaptation to callers and exposing only writer boundary APIs.
- Rejected because it would duplicate mapping/provenance semantics across components and increase drift risk.
- We centralized lane mapping in LS to keep one canonical adaptation behavior while still preserving LS as a simple truth writer (adapters map + validate; writer enforces commit discipline).

### Validation evidence
- `python -m py_compile src/fraud_detection/label_store/adapters.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase5_ingest_adapters.py`
  - result: pass
- `python -m pytest -q tests/services/label_store/test_phase5_ingest_adapters.py`
  - result: `5 passed`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py`
  - result: `28 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `10 passed`

### Phase closure statement
- LS Phase 5 DoD is satisfied:
  - CM assertion lane remains accepted through writer boundary,
  - engine/external truth lanes now have explicit adapters with provenance + dual-time semantics,
  - all lanes converge on the same idempotent writer checks,
  - no bypass path writes label truth outside LS writer boundary.

## Entry: 2026-02-09 06:57PM - Pre-change lock for Phase 6 (LS observability, governance, access audit)

### Objective
Close LS Phase 6 by adding run-scoped metrics/anomaly reporting, lifecycle-governance emission with actor/evidence attribution, and explicit evidence-access audit hook surfaces.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/label_store.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.8 alignment)
- `docs/model_spec/platform/component-specific/label_store.design-authority.md` (truth ownership, by-ref evidence, idempotency, non-leaky governance posture)
- Existing implementation context:
  - `src/fraud_detection/label_store/writer_boundary.py` (assertion/mismatch/timeline truth)
  - `src/fraud_detection/case_mgmt/observability.py` (component observability/governance emission pattern)
  - `src/fraud_detection/platform_governance/evidence_corridor.py` (access-audit posture reference)

### Problem framing
LS currently has write/read correctness (Phases 1..5) but lacks component-level operate/audit surfaces:
1. no run-scoped metrics export artifact for accepted/rejected/duplicates/pending/anomaly classes,
2. no LS lifecycle governance emission artifact with actor/evidence attribution,
3. no explicit access-audit hook for LS evidence reference resolution/use,
4. no explicit redaction posture in LS governance artifacts.

### Alternatives considered
1. Add ad-hoc counters to writer-boundary write path and emit inline artifacts.
- Rejected: mixes control path with observability concerns and misses historical/backfill export from existing ledgers.
2. Add dedicated LS observability module that derives run-scoped posture from append-only ledgers and writes artifacts idempotently.
- Selected: keeps write control path clean and aligns with component reporter patterns already used in CM/OFP/CSFB.

### Decisions locked before edits
1. Introduce `src/fraud_detection/label_store/observability.py` with:
- `LabelStoreRunReporter.collect()` and `.export()` over existing LS tables.
2. Metrics will be run-scoped by parsing assertion pins (`platform_run_id`, `scenario_run_id`) from assertion JSON and include DoD lanes:
- `accepted`, `rejected`, `duplicate`, `pending`, and anomaly classes.
- `pending` is emitted explicitly; v0 default is `0` until asynchronous LS pending lanes are introduced.
3. Lifecycle governance events are emitted to component-local `label_store/governance/events.jsonl` using marker-based idempotency and include:
- actor attribution (`actor_id`, `source_type`, `source_component`),
- evidence refs by-ref only,
- pins and subject identifiers,
- explicit exclusion of sensitive `label_payload` and full assertion JSON.
4. Add explicit evidence access-audit hooks in LS module:
- append-only audit event writer for access attempts (`ALLOWED`/`DENIED`) with by-ref metadata,
- reusable request/result dataclasses so caller components can integrate where required.
5. Export artifacts under run root:
- `label_store/metrics/last_metrics.json`
- `label_store/health/last_health.json`
- `label_store/reconciliation/last_reconciliation.json`
- `label_store/governance/events.jsonl`
- `label_store/access_audit/events.jsonl`
- plus `case_labels/reconciliation/label_store_reconciliation.json` and dated file contribution.
6. Add Phase 6 matrix tests for metrics/anomalies, governance idempotency/redaction, and access-audit hooks.

### Planned files
- New:
  - `src/fraud_detection/label_store/observability.py`
  - `tests/services/label_store/test_phase6_observability.py`
- Update:
  - `src/fraud_detection/label_store/__init__.py`
  - `src/fraud_detection/platform_reporter/run_reporter.py` (reconciliation ref discovery for LS contribution)
- Documentation updates after validation:
  - `docs/model_spec/platform/implementation_maps/label_store.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/label_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/label_store/observability.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase6_observability.py`
- `python -m pytest -q tests/services/label_store/test_phase6_observability.py`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py tests/services/label_store/test_phase6_observability.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`

## Entry: 2026-02-09 07:02PM - Phase 6 implemented and validated (LS observability, governance, access audit)

### Implementation completed
1. Added dedicated LS observability module:
- `src/fraud_detection/label_store/observability.py`
- Introduced `LabelStoreRunReporter.collect()/export()` over LS append-only ledgers.

2. Implemented run-scoped metrics and anomaly posture:
- run-scope gate uses assertion pins (`platform_run_id`, `scenario_run_id`) from canonical assertion JSON.
- emitted DoD counters:
  - `accepted`, `rejected`, `duplicate`, `pending`,
  - plus anomaly counters (`payload_hash_mismatch`, `dedupe_tuple_collision`, `mismatch_rows`).
- explicit `pending` lane is emitted as `0` for current synchronous LS posture.

3. Implemented lifecycle governance emission with idempotent markers:
- governance events emitted to `label_store/governance/events.jsonl` with marker dedupe.
- lifecycle event posture: `LABEL_ACCEPTED` from LS timeline truth.
- actor attribution is preserved (`actor_id`, `source_type`, `source_component=label_store`).
- evidence refs are preserved by-ref only.

4. Enforced sensitive-payload exclusion in governance/audit outputs:
- governance details intentionally exclude `label_payload` and full assertion payloads.
- emitted details are minimal/auditable (`label_assertion_id`, subject refs, label_type, evidence refs).

5. Added explicit evidence access-audit hook surfaces:
- `LabelStoreEvidenceAccessAuditor`
- `LabelStoreEvidenceAccessAuditRequest/Result`
- append-only audit emission to `label_store/access_audit/events.jsonl` with marker dedupe.
- allow/deny status (`ALLOWED`/`DENIED`) and reason-code carriage for fail-closed caller integration.

6. Added reconciliation contribution export for Case+Labels plane:
- `case_labels/reconciliation/label_store_reconciliation.json`
- dated contribution `case_labels/reconciliation/YYYY-MM-DD.json`.

7. Exported Phase 6 surfaces:
- updated `src/fraud_detection/label_store/__init__.py`.

8. Updated platform reporter reconciliation discovery for LS:
- `src/fraud_detection/platform_reporter/run_reporter.py` now includes:
  - `label_store/reconciliation/last_reconciliation.json`
  - `case_labels/reconciliation/label_store_reconciliation.json`.

9. Added dedicated Phase 6 test matrix:
- `tests/services/label_store/test_phase6_observability.py`
- coverage includes:
  - run-scoped metrics/anomalies,
  - lifecycle governance emission + redaction,
  - governance idempotency,
  - evidence access-audit hook allow/deny + idempotency + status validation.

### Decision trail and rationale
- We chose a dedicated reporter module instead of inlining metrics into writer control-path to preserve control-path determinism and avoid coupling write commits to artifact export mechanics.
- We intentionally modeled access-audit as hook surfaces (not forced side-effects inside read APIs) so callers can integrate according to corridor/policy context while still producing append-only audit evidence when required.

### Validation evidence
- `python -m py_compile src/fraud_detection/label_store/observability.py src/fraud_detection/label_store/__init__.py src/fraud_detection/platform_reporter/run_reporter.py tests/services/label_store/test_phase6_observability.py`
  - result: pass
- `python -m pytest -q tests/services/label_store/test_phase6_observability.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py tests/services/label_store/test_phase6_observability.py`
  - result: `32 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `10 passed`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`
  - result: `2 passed`

### Phase closure statement
- LS Phase 6 DoD is satisfied:
  - run-scoped LS counters are emitted,
  - lifecycle governance events include actor attribution + evidence refs,
  - evidence access-audit hook surfaces are available for caller integration,
  - sensitive payload details are excluded from governance/audit artifacts.
