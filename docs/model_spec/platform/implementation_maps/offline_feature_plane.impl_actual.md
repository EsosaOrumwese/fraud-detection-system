# Offline Feature Plane Implementation Map
_As of 2026-02-10_

---

## Entry: 2026-02-10 11:18AM - Pre-change planning lock for OFS component build plan

### Trigger
User requested planning of the component build plan for Offline Feature Plane after platform Phase `6.0/6.1` closure, with explicit expectation that meta layers are part of the component plan.

### Problem statement
Platform Phase `6.2` is active, but OFS has no component-scoped build plan file yet. Without that plan, implementation sequencing risks drift across:
- replay basis authority (EB vs Archive),
- label leakage boundaries (`observed_time` as-of discipline),
- feature version authority alignment with OFP/MF,
- run/operate and obs/gov onboarding expectations.

### Authorities used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.2` and Phase `6.6/6.7` meta-layer gates)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/offline_feature_plane.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

### Alternatives considered
1. Keep planning only in `platform.build_plan.md`.
   - Rejected: loses component-level execution granularity and violates component map discipline.
2. Create a short OFS plan with only `6.2` DoD copy-paste.
   - Rejected: too coarse; misses internal run/operate and obs/gov closure gates and explicit fail-closed proofs.
3. Create a full OFS component plan with phased progression and explicit closure gates.
   - Selected.

### Decision
Create:
- `docs/model_spec/platform/implementation_maps/offline_feature_plane.build_plan.md`
with explicit phases covering:
1) contract and identity pins,
2) run ledger/idempotency,
3) provenance resolver,
4) replay/completeness corridor,
5) label as-of corridor,
6) deterministic feature reconstruction,
7) manifest publication authority,
8) run/operate onboarding,
9) obs/gov onboarding,
10) integration closure evidence gate.

### Drift sentinel assessment before edit
- Material drift risk if OFS is implemented without explicit replay/label/feature authority locks: high.
- Material drift risk if OFS ships before meta-layer onboarding (run/operate + obs/gov): high.
- Therefore plan must embed these as explicit blocking phases, not optional notes.

### Validation plan for planning change
- Ensure component plan references platform Phase `6.2` and maps to current platform sequencing.
- Ensure meta-layer onboarding is explicit (run/operate and obs/gov sections).
- Ensure non-goals prohibit hot-path and truth-ownership violations.

## Entry: 2026-02-10 11:21AM - Applied OFS component build plan

### What was created
- `docs/model_spec/platform/implementation_maps/offline_feature_plane.build_plan.md`

### Resulting plan posture
- OFS planning now has an explicit, closure-grade component map aligned to platform Phase `6.2`.
- Build plan includes deterministic identity law, replay/label/feature fail-closed rails, manifest authority, and meta-layer onboarding gates.
- Rolling status in component plan set to:
  - Phase 1 planning-active,
  - next action: Phase 1 implementation.

### Why this resolves the planning gap
- Converts high-level platform gate (`6.2`) into concrete component execution sequence and DoD.
- Prevents repeating prior drift pattern where component logic exists but orchestration/observability is deferred.
- Makes OFS readiness auditable before implementation begins.

### Follow-on documentation updates required
- Add platform-level pointer to this OFS build plan in `platform.build_plan.md` Phase `6.2` section.
- Append platform-wide decision note in `platform.impl_actual.md`.
- Record action trail in `docs/logbook/02-2026/2026-02-10.md`.

## Entry: 2026-02-10 11:22AM - Pre-change implementation lock for OFS Phase 1

### Trigger
User directed implementation start for OFS Phase 1 (`BuildIntent + dataset identity + contract lock`).

### Implementation scope (Phase 1 only)
1. Add OFS Phase 1 contract surfaces:
   - BuildIntent contract with explicit `request_id` idempotency key and allowed intent kinds.
   - Explicit rejection taxonomy for inadmissible intents.
2. Add deterministic dataset identity utilities:
   - canonical dataset identity payload normalization,
   - deterministic dataset fingerprint hashing,
   - deterministic manifest id derivation helper.
3. Add schema authority updates for OFS build intent and integrate with existing learning schema registry.
4. Add tests for:
   - contract acceptance/rejection taxonomy,
   - dataset identity determinism and drift behavior.

### Authorities used for this implementation
- `docs/model_spec/platform/implementation_maps/offline_feature_plane.build_plan.md` (Phase 1 DoD)
- `docs/model_spec/platform/component-specific/offline_feature_plane.design-authority.md` (pins: job posture, replay basis, no scanning, manifest authority)
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md` (replay/label/fingerprint defaults)
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`
- `config/platform/learning_registry/ownership_boundaries_v0.yaml`

### Design choices before code
- Keep OFS Phase 1 code in a dedicated package: `src/fraud_detection/offline_feature_plane/`.
- Use explicit schema validation through `LearningRegistrySchemaRegistry` by adding an OFS build-intent schema in learning contracts authority.
- Encode rejection taxonomy as stable reason codes in a dedicated contract error type (`code` + message) so later run/operate/obs layers can consume reasons without parsing free text.
- Preserve fail-closed posture: invalid/missing basis fields, missing label as-of, unresolved feature refs, and ownership contract failures reject before any replay/build behavior.

### Validation plan
- `py_compile` on OFS new modules + updated learning contract modules.
- targeted pytest for OFS Phase 1 tests and learning contract regression.

## Entry: 2026-02-10 11:25AM - Applied OFS Phase 1 implementation and validation

### Implemented files
- New OFS package:
  - `src/fraud_detection/offline_feature_plane/contracts.py`
  - `src/fraud_detection/offline_feature_plane/ids.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py`
- New schema authority:
  - `docs/model_spec/platform/contracts/learning_registry/ofs_build_intent_v0.schema.yaml`
- Contract index updates:
  - `docs/model_spec/platform/contracts/learning_registry/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- New tests:
  - `tests/services/offline_feature_plane/test_phase1_contracts.py`
  - `tests/services/offline_feature_plane/test_phase1_ids.py`

### Functional outcomes
1. BuildIntent contract lock:
   - explicit idempotency key (`request_id`) + intent kinds (`dataset_build`, `parity_rebuild`, `forensic_rebuild`),
   - typed rejection taxonomy via `OfsPhase1ContractError.code`.
2. Dataset identity law:
   - canonicalized replay basis, scenario ids, join/filter scope, and provenance pins,
   - deterministic `dataset_fingerprint` and deterministic `dataset_manifest_id`.
3. Alignment to learning authority:
   - OFS BuildIntent validated through learning schema registry,
   - emitted manifest path uses `DatasetManifestContract` validation against existing authoritative schema.
4. Ownership boundary lock:
   - build-intent admission enforces `owners.ofs` and `outputs.dataset_manifest` in ownership boundaries config.

### Validation results
- Syntax:
  - `python -m py_compile src/fraud_detection/offline_feature_plane/__init__.py src/fraud_detection/offline_feature_plane/contracts.py src/fraud_detection/offline_feature_plane/ids.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py` (`PASS`).
- Tests:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`15 passed`).

### Drift sentinel assessment after implementation
- Intended OFS Phase 1 design preserved: contracts and identity are now explicit and fail-closed.
- No ownership boundary contradiction detected.
- No meta-layer drift introduced in this phase because run/operate and obs/gov concerns remain explicitly queued for Phase 8/9.

### Plan status
- OFS Phase 1 is complete and validated.
- Next active OFS phase is Phase 2 (`run control + idempotent run ledger`).

## Entry: 2026-02-10 11:29AM - Pre-change implementation lock for OFS Phase 2

### Trigger
User requested proceeding to OFS Phase 2 (`run control + idempotent run ledger`).

### Problem statement
OFS currently has Phase 1 contracts and identity pins but no durable run ledger or explicit run-control transitions. Without this, retries/restarts can create semantic drift and publish retry behavior is undefined.

### Authorities used
- `docs/model_spec/platform/implementation_maps/offline_feature_plane.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/component-specific/offline_feature_plane.design-authority.md` (S1 run orchestration and idempotency pins)
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md` (fail-closed and reproducibility posture)
- Existing platform patterns for durable ledgers/checkpoints:
  - `src/fraud_detection/archive_writer/store.py`
  - `src/fraud_detection/case_trigger/checkpoints.py`
  - `src/fraud_detection/scenario_runner/ledger.py`

### Implementation plan
1. Add durable OFS run ledger module with sqlite/postgres support:
   - deterministic `run_key` from `request_id`,
   - request-id uniqueness and payload-hash collision detection,
   - append-only run events + state snapshot table.
2. Encode Phase 2 state machine:
   - `QUEUED -> RUNNING -> DONE|FAILED|PUBLISH_PENDING`
   - `PUBLISH_PENDING -> RUNNING` (publish-only retry path only)
   - terminal idempotency for `DONE` and `FAILED`.
3. Add run-control wrapper:
   - bounded publish-only retry policy (`max_publish_retry_attempts`),
   - enforce that publish-only retries do not increment full-run attempts.
4. Add tests for:
   - duplicate request convergence,
   - request-id payload mismatch fail-closed,
   - valid/invalid transitions,
   - bounded publish-only retry,
   - receipt payload containing pinned input summary and provenance.

### Drift sentinel assessment before code
- No authority conflict detected.
- Material risk noted: if publish-only retry mutates full-run attempt counters, it creates hidden retrain semantics drift.
- Phase 2 implementation must therefore separate `full_run_attempts` and `publish_retry_attempts`.

## Entry: 2026-02-10 11:32AM - Applied OFS Phase 2 implementation and validation

### Implemented files
- `src/fraud_detection/offline_feature_plane/run_ledger.py`
- `src/fraud_detection/offline_feature_plane/run_control.py`
- `src/fraud_detection/offline_feature_plane/__init__.py` (Phase 2 exports)
- `tests/services/offline_feature_plane/test_phase2_run_ledger.py`

### Functional outcomes
1. Durable run ledger:
   - deterministic `run_key` from `request_id`,
   - request-id uniqueness with payload-hash mismatch fail-closed posture,
   - append-only run events table + state snapshot table.
2. State machine enforcement:
   - `QUEUED -> RUNNING -> DONE|FAILED|PUBLISH_PENDING`,
   - `PUBLISH_PENDING -> RUNNING` only via publish-only retry path.
3. Retry posture:
   - bounded publish-only retry via run-control policy,
   - retry budget exhaustion emits explicit fail-closed error (`PUBLISH_RETRY_EXHAUSTED`),
   - publish-only retries do not increment full-run attempts.
4. Receipt posture:
   - run receipts include pinned input summary and provenance summary for auditability.

### Validation results
- Syntax:
  - `python -m py_compile src/fraud_detection/offline_feature_plane/__init__.py src/fraud_detection/offline_feature_plane/run_ledger.py src/fraud_detection/offline_feature_plane/run_control.py tests/services/offline_feature_plane/test_phase2_run_ledger.py` (`PASS`).
- Tests:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`21 passed`).

### Drift sentinel assessment after implementation
- Designed-flow alignment preserved for Phase 2 scope.
- Publish-only retry path is explicit and bounded; no hidden full-run increment drift detected.
- No ownership-boundary contradiction introduced.

### Plan status
- OFS Phase 2 is complete and validated.
- Next active OFS phase is Phase 3 (`pin and provenance resolver`).
