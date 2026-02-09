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
