# Model Factory Implementation Map
_As of 2026-02-10_

## Entry: 2026-02-10 1:26PM - Pre-change implementation lock for MF planning bootstrap (Platform Phase 6.3)

### Trigger
User directed planning execution for platform Phase `6.3` and requested creation of the component build plan for MF.

### Scope of this pass
- Planning and decision-trail updates only (no runtime/code-path changes yet).
- Expand platform Phase `6.3` into closure-grade planning detail.
- Create MF component build plan with phased DoD gates aligned to platform Phase `6.3` and the Learning-plane closure sequence.

### Authorities used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3` focus; `6.6/6.7/6.8` dependencies)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/model_policy_registry.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`

### Problem framing and alternatives considered
1. Plan MF as a single bulk phase (`train/eval/publish`) with one closure checklist.
   - Rejected: insufficient control over failure taxonomy, publish gating, and reproducibility boundary.
2. Plan MF deeply but isolated from platform phase sequencing.
   - Rejected: can cause false closure because meta-layer onboarding (`6.6/6.7`) may be skipped.
3. Plan MF as staged corridors tied to platform gates (component closure + meta-layer dependencies + integration gate).
   - Selected: matches doctrine and reduces drift risk across implementation, operation, and governance.

### Decisions pinned for MF planning
- MF consumes only explicit DatasetManifest refs and pinned train/eval config refs.
- MF run identity is deterministic and idempotent under retries/restarts.
- Eval output is contracted, immutable, and required for publish eligibility.
- Bundle publication to MPR is append-only, immutable, and fail-closed on missing compatibility/evidence.
- MF planning includes explicit run/operate and obs/gov phases; these are required for corridor closure, not optional add-ons.

### Planned file changes
- Update `docs/model_spec/platform/implementation_maps/platform.build_plan.md` Phase `6.3`.
- Create `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`.
- Append post-change applied entries in this file, `platform.impl_actual.md`, and `docs/logbook/02-2026/2026-02-10.md`.

### Drift sentinel checkpoint
Any planning statement that permits "latest dataset" scans, mutable bundle rewrites, missing lineage acceptance, or implicit promotion behavior is a fail-closed blocker.

## Entry: 2026-02-10 1:28PM - Applied planning bootstrap for MF component roadmap

### What was applied
- Created MF component build plan:
  - `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`
- Build plan defines phased implementation closure gates for:
  - contract/identity,
  - run ledger/idempotency,
  - input resolution/provenance lock,
  - train/eval evidence,
  - gate receipt/publish eligibility,
  - bundle packaging/MPR handshake,
  - negative-path matrix,
  - run/operate onboarding,
  - obs/gov onboarding,
  - integration closure.

### Why this is the chosen posture
- Preserves progressive elaboration while preventing ambiguous "single-step MF" implementation.
- Keeps MF closure coupled to platform meta-layer obligations and Learning-plane sequencing.
- Makes fail-closed expectations executable before any MF runtime code is introduced.

### Validation evidence
- Planning artifacts created/updated only; no runtime behavior changed in this pass.
- Cross-reference check confirmed:
  - platform Phase `6.3` now points to component execution planning,
  - component plan carries explicit dependency on `6.6/6.7/6.8` gates.

### Drift sentinel assessment
- No mismatch detected between flow narrative, pinned learning decisions, and this MF planning surface.
- Residual risk remains implementation-phase: runtime contracts and failure taxonomy still need code/test enforcement in subsequent phases.

## Entry: 2026-02-10 1:34PM - Pre-change implementation lock for MF Phase 1 (contract + run identity)

### Trigger
User directed execution: "Proceed to Model Factory Phase 1 Implementation."

### Phase objective (DoD-locked)
Implement MF Phase 1 with executable contract and deterministic identity surfaces:
- `TrainBuildRequest` contract validation with typed fail-closed taxonomy.
- Deterministic run identity primitives (`TrainRunKey` canonicalization + `train_run_id` derivation).
- Explicit phase-1 admissibility posture (no implicit dataset discovery; by-ref manifest inputs only).

### Authorities used for this implementation lock
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 1 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3` corridor expectations)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/contracts/learning_registry/*.schema.yaml`
- Existing OFS/learning contract patterns:
  - `src/fraud_detection/offline_feature_plane/contracts.py`
  - `src/fraud_detection/offline_feature_plane/ids.py`
  - `src/fraud_detection/learning_registry/contracts.py`

### Problem framing and alternatives considered
1. Implement Phase 1 with ad-hoc dataclasses and no schema-backed validation.
   - Rejected: inconsistent with existing learning contract posture and weak failure taxonomy control.
2. Reuse existing schemas only and avoid MF-specific request schema/contract type.
   - Rejected: Phase 1 requires explicit MF trigger semantics and deterministic request boundary.
3. Add MF Phase 1 as:
   - a new MF request schema under learning contracts,
   - typed contract parser/validator with taxonomy mapping,
   - deterministic run key/id helpers,
   - focused tests for contract acceptance/rejection and identity determinism.
   - Selected.

### Planned file changes
- New MF package surfaces:
  - `src/fraud_detection/model_factory/contracts.py`
  - `src/fraud_detection/model_factory/ids.py`
  - `src/fraud_detection/model_factory/__init__.py`
- New contract schema:
  - `docs/model_spec/platform/contracts/learning_registry/mf_train_build_request_v0.schema.yaml`
- Contract index updates:
  - `docs/model_spec/platform/contracts/learning_registry/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- New tests:
  - `tests/services/model_factory/test_phase1_contracts.py`
  - `tests/services/model_factory/test_phase1_ids.py`

### Validation plan
- Syntax compile for new MF files/tests.
- Targeted MF phase1 tests.
- Keep existing learning-registry contract tests green to detect schema-registry regressions.

### Drift sentinel checkpoint
If implementation allows non-ref dataset selection, omits deterministic run identity, or treats missing pinned refs as warnings, this is material drift and must fail closed.

## Entry: 2026-02-10 1:38PM - Applied MF Phase 1 implementation (contract + deterministic run identity)

### Implemented files and surfaces
- New MF Phase 1 code:
  - `src/fraud_detection/model_factory/contracts.py`
  - `src/fraud_detection/model_factory/ids.py`
  - `src/fraud_detection/model_factory/__init__.py`
- New learning contract schema:
  - `docs/model_spec/platform/contracts/learning_registry/mf_train_build_request_v0.schema.yaml`
- Contract index updates:
  - `docs/model_spec/platform/contracts/learning_registry/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- New tests:
  - `tests/services/model_factory/test_phase1_contracts.py`
  - `tests/services/model_factory/test_phase1_ids.py`

### Phase 1 outcomes
- MF now has an explicit `TrainBuildRequest` boundary with schema-backed validation and typed fail-closed taxonomy.
- `TargetScope` semantics are explicit at request boundary (`environment/mode/bundle_slot`, optional `tenant_id`).
- Deterministic run identity is executable:
  - canonical TrainRunKey payload,
  - `train_run_key` digest recipe,
  - deterministic `train_run_id` recipe.
- Ownership-boundary assertions are enforced at request admission (`owners.mf` plus expected MF outputs).

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/contracts.py src/fraud_detection/model_factory/ids.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py` (`PASS`).
- Targeted MF + learning contracts:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`15 passed`).
- Cross-check with OFS Phase 1 contract/identity lane:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`26 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected.
- MF Phase 1 preserves by-ref manifest posture and fail-closed semantics.
- Ownership boundaries remain intact: OFS manifest authority, MF train/eval/bundle intent authority, MPR ACTIVE authority.

### Plan progression
- MF Phase 1 is closed.
- Next MF phase is Phase 2 (`run control + idempotent run ledger`).

## Entry: 2026-02-10 1:42PM - Pre-change implementation lock for MF Phase 2 (run control + idempotent run ledger)

### Trigger
User directed progression: "Let's move to implementing MF Phase 2."

### Phase objective (DoD-locked)
Implement durable MF run ledger/control semantics so retries/restarts cannot fork training meaning:
- stable lifecycle states,
- deterministic submission identity behavior,
- explicit publish-only retry path that cannot retrigger full training,
- persisted input/provenance summary in run receipts.

### Authorities used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3` corridor)
- `src/fraud_detection/offline_feature_plane/run_ledger.py` (reference pattern)
- `src/fraud_detection/offline_feature_plane/run_control.py` (reference pattern)
- `tests/services/offline_feature_plane/test_phase2_run_ledger.py` (reference matrix)
- `src/fraud_detection/model_factory/contracts.py` and `ids.py` (Phase 1 identity boundary)

### Problem framing and alternatives considered
1. Keep MF Phase 2 in-memory only and defer durable ledger semantics.
   - Rejected: violates at-least-once/idempotency doctrine and restart safety.
2. Copy OFS ledger semantics without MF-specific state model.
   - Rejected: MF requires explicit `EVAL_READY`, `PASS/FAIL`, and publication outcome states.
3. Reuse OFS ledger architecture but adapt MF-specific state machine and payload summaries.
   - Selected: high implementation reliability with low drift risk.

### Planned MF Phase 2 state model
- Core states:
  - `QUEUED`
  - `RUNNING`
  - `EVAL_READY`
  - `PASS`
  - `FAIL`
  - `PUBLISH_PENDING`
  - `PUBLISHED`
- Execution modes:
  - `FULL`
  - `PUBLISH_ONLY`
- Retry policy:
  - bounded publish-only retries from `PUBLISH_PENDING`,
  - no full-run counter increase on publish-only retry.

### Planned file changes
- New:
  - `src/fraud_detection/model_factory/run_ledger.py`
  - `src/fraud_detection/model_factory/run_control.py`
  - `tests/services/model_factory/test_phase2_run_ledger.py`
- Update:
  - `src/fraud_detection/model_factory/__init__.py` exports
  - build-plan/status docs and implementation/logbook trails.

### Validation plan
- Compile new MF phase2 files/tests.
- Run targeted matrix:
  - `tests/services/model_factory/test_phase2_run_ledger.py`
- Run combined MF regression:
  - Phase1 + Phase2 + learning contracts (and OFS phase1 compatibility sanity).

### Drift sentinel checkpoint
If publish-only retry can increment full-run attempts or if run submission accepts payload mismatch under same idempotency identity, this phase must remain blocked.

## Entry: 2026-02-10 1:51PM - Applied MF Phase 2 implementation (run control + idempotent run ledger)

### Implemented files and surfaces
- Added MF Phase 2 runtime modules:
  - `src/fraud_detection/model_factory/run_ledger.py`
  - `src/fraud_detection/model_factory/run_control.py`
- Updated MF exports:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 2 matrix:
  - `tests/services/model_factory/test_phase2_run_ledger.py`

### Phase 2 outcomes
- Durable MF run ledger is now available with explicit lifecycle states:
  - `QUEUED`, `RUNNING`, `EVAL_READY`, `PASS`, `FAIL`, `PUBLISH_PENDING`, `PUBLISHED`.
- Idempotent submission and fail-closed mismatch posture are enforced:
  - same request returns duplicate outcome with same run identity,
  - request payload drift under same request id fails closed (`REQUEST_ID_PAYLOAD_MISMATCH`),
  - semantic duplicates converge by deterministic run key.
- Publish-only retry is explicit, bounded, and does not increment full-train attempts.
- Run receipts persist deterministic input summary and provenance summaries for audit/reconciliation surfaces.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/run_ledger.py src/fraud_detection/model_factory/run_control.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase2_run_ledger.py` (`PASS`).
- Targeted Phase 2:
  - `python -m pytest tests/services/model_factory/test_phase2_run_ledger.py -q --import-mode=importlib` (`7 passed`).
- MF + learning contracts:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`22 passed`).
- MF + OFS + learning regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`39 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected for Phase 2 scope.
- Ownership boundaries remain intact and explicit.
- Retry and idempotency semantics are now durable and bounded, reducing hidden restart/replay drift risk before Phase 3 resolver work.

### Plan progression
- MF Phase 2 is closed.
- Next MF phase is Phase 3 (`input resolver + provenance lock`).

## Entry: 2026-02-10 2:00PM - Pre-change implementation lock for MF Phase 3 (input resolver + provenance lock)

### Trigger
User directed progression: "Let's move to Phase 3 implementation of the MF plan."

### Phase objective (DoD-locked)
Implement MF Phase 3 as the strict input-admissibility and provenance-lock boundary before any train/eval logic:
- resolve all `dataset_manifest_refs` explicitly by reference (no scanning/latest),
- validate manifest schema and run-scope compatibility fail-closed,
- validate manifest feature/schema compatibility against pinned training profile requirements,
- resolve training/governance profile refs and capture immutable provenance digests,
- emit immutable `resolved_train_plan` artifact under run scope.

### Authorities used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3.B`)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`
- Existing reference implementation pattern:
  - `src/fraud_detection/offline_feature_plane/phase3.py`
  - `tests/services/offline_feature_plane/test_phase3_resolver.py`

### Problem framing and alternatives considered
1. Resolve manifests as raw JSON without contract validation.
   - Rejected: violates fail-closed compatibility posture and weakens OFS->MF boundary.
2. Add only shallow path-existence checks and defer feature/schema compatibility to later phases.
   - Rejected: Phase 3 explicitly owns pre-train meaning lock; deferral risks hidden drift.
3. Implement typed MF resolver boundary with:
   - contract validation (`DatasetManifestContract`),
   - run-scope checks (`platform_run_id` match),
   - training-profile compatibility checks for feature-definition set + expected manifest schema,
   - immutable resolved-plan emission with drift detection.
   - Selected.

### Planned file changes
- New code:
  - `src/fraud_detection/model_factory/phase3.py`
- Update exports:
  - `src/fraud_detection/model_factory/__init__.py`
- New tests:
  - `tests/services/model_factory/test_phase3_resolver.py`
- Documentation/status updates after validation:
  - `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/model_factory.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-10.md`

### Validation plan
- Syntax compile of new MF Phase 3 module and tests.
- Targeted Phase 3 resolver matrix.
- Combined MF regression (Phases 1..3 + learning contracts).
- OFS/MF learning-lane compatibility sanity matrix (existing OFS Phase 1..3 + MF Phase 1..3 + learning contracts).

### Drift sentinel checkpoint
If Phase 3 allows unresolved refs, run-scope mismatch, or feature/schema incompatibility to proceed into train/eval, that is material drift and Phase 3 remains blocked.

## Entry: 2026-02-10 2:03PM - Applied MF Phase 3 implementation (input resolver + provenance lock)

### Implemented files and surfaces
- Added MF Phase 3 resolver module:
  - `src/fraud_detection/model_factory/phase3.py`
- Updated MF public exports for Phase 3 surfaces:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 3 validation matrix:
  - `tests/services/model_factory/test_phase3_resolver.py`

### Phase 3 outcomes
- MF now resolves DatasetManifest refs explicitly via by-ref reads and schema validation (`DatasetManifestContract`).
- Fail-closed run-scope enforcement is now explicit:
  - manifest `platform_run_id` must equal request `platform_run_id`.
- Feature/schema compatibility guard is now enforced before train/eval:
  - manifest `feature_definition_set` must match training profile feature requirements,
  - manifest schema version must match expected training-profile schema basis.
- Resolver records immutable `resolved_train_plan` artifacts under run scope:
  - `<platform_run_id>/mf/resolved_train_plan/<run_key>.json`.
- Re-emission drift is blocked with typed immutability violation (`RESOLVED_TRAIN_PLAN_IMMUTABILITY_VIOLATION`).

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/phase3.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase3_resolver.py` (`PASS`).
- Targeted Phase 3:
  - `python -m pytest tests/services/model_factory/test_phase3_resolver.py -q --import-mode=importlib` (`6 passed`).
- MF + learning contracts regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`28 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`51 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected in Phase 3 scope.
- J15 intake boundary is now stricter and explicit (by-ref manifests, fail-closed compatibility, immutable provenance lock).
- Residual risk surface moves to MF Phase 4 (`train/eval execution corridor`) for evidence production and leakage-policy execution mechanics.

### Plan progression
- MF Phase 3 is closed.
- Next MF phase is Phase 4 (`train/eval execution corridor`).
