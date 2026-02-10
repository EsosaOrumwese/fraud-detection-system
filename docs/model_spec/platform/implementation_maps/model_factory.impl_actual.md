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

## Entry: 2026-02-10 2:06PM - Pre-change implementation lock for MF Phase 4 (train/eval execution corridor)

### Trigger
User directed progression: "Proceed to implementing MF Phase 4."

### Phase objective (DoD-locked)
Implement MF Phase 4 execution mechanics so pinned Phase 3 plans produce reproducible, immutable train/eval evidence:
- enforce explicit split strategy and seed policy recording in execution records,
- produce immutable train artifact and eval evidence artifacts under `mf/...`,
- emit schema-valid `EvalReport` with reproducibility basis and deterministic metrics,
- enforce leakage guardrails fail-closed using manifest as-of/resolution posture (no hidden now).

### Authorities used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 4 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3.C` intent)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/contracts/learning_registry/eval_report_v0.schema.yaml`
- `src/fraud_detection/learning_registry/contracts.py` (`EvalReportContract`)
- Existing immutable-publication patterns:
  - `src/fraud_detection/offline_feature_plane/phase6.py`
  - `src/fraud_detection/offline_feature_plane/phase7.py`

### Problem framing and alternatives considered
1. Stub train/eval with ad-hoc files and skip schema-validated EvalReport until Phase 5.
   - Rejected: Phase 4 DoD explicitly requires eval evidence quality and reproducibility surfaces now.
2. Compute-only in-memory outputs and defer immutable artifact writes to worker integration.
   - Rejected: corridor would be non-auditable and not restart-safe for later phases.
3. Build a deterministic Phase 4 executor with:
   - immutable execution record/model artifact/eval report/evidence pack receipts,
   - typed fail-closed taxonomy for profile/leakage/immutability violations,
   - explicit split/seed policy capture + deterministic metric derivation from pinned inputs.
   - Selected.

### Planned file changes
- New code:
  - `src/fraud_detection/model_factory/phase4.py`
- Update exports:
  - `src/fraud_detection/model_factory/__init__.py`
- New tests:
  - `tests/services/model_factory/test_phase4_execution.py`
- Documentation/status updates after validation:
  - `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/model_factory.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-10.md`

### Validation plan
- Compile new MF Phase 4 module/tests.
- Targeted MF Phase 4 matrix.
- Combined MF regression (Phases 1..4 + learning contracts).
- OFS/MF/learning compatibility sanity matrix.

### Drift sentinel checkpoint
If Phase 4 allows training/eval to proceed without explicit split/seed posture or accepts ambiguous as-of leakage posture, phase closure is blocked as material drift.

## Entry: 2026-02-10 2:10PM - Applied MF Phase 4 implementation (train/eval execution corridor)

### Implemented files and surfaces
- Added MF Phase 4 execution module:
  - `src/fraud_detection/model_factory/phase4.py`
- Updated MF exports for Phase 4 surfaces:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 4 matrix:
  - `tests/services/model_factory/test_phase4_execution.py`

### Phase 4 outcomes
- MF can now execute deterministic train/eval evidence flow from a pinned `ResolvedTrainPlan`.
- Execution corridor explicitly records and enforces:
  - split strategy,
  - seed policy,
  - deterministic stage seed.
- Eval evidence is now schema-validated at emission time (`EvalReportContract`) and written immutably by-ref under run scope.
- Required immutable artifacts are emitted under `mf/train_runs/<run_key>/...`:
  - execution record,
  - train artifact,
  - eval report,
  - evidence pack,
  - train/eval receipt.
- Leakage guardrails are fail-closed:
  - manifest label rule alignment to `observed_time<=label_asof_utc` (or pinned equivalent),
  - label as-of timestamps cannot exceed execution start,
  - multi-manifest label-as-of mismatch is blocked.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/phase4.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase4_execution.py` (`PASS`).
- Targeted Phase 4:
  - `python -m pytest tests/services/model_factory/test_phase4_execution.py -q --import-mode=importlib` (`5 passed`).
- MF + learning contracts regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`33 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`56 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected for Phase 4 scope.
- MF corridor now has executable, immutable train/eval evidence with explicit leakage policy enforcement before gate/publish phases.
- Residual risk surface moves to MF Phase 5 (`gate receipt + publish eligibility policy`).

### Plan progression
- MF Phase 4 is closed.
- Next MF phase is Phase 5 (`gate receipt + publish eligibility policy`).

## Entry: 2026-02-10 2:13PM - Pre-change implementation lock for MF Phase 5 (gate receipt + publish eligibility policy)

### Trigger
User directed progression: "Proceed to phase 5 implementation of MF."

### Phase objective (DoD-locked)
Implement MF Phase 5 policy layer so publish eligibility is explicit and auditable:
- emit explicit PASS/FAIL gate receipt bound to `run_key` (train run identity),
- evaluate publish eligibility using PASS + required evidence refs,
- enforce fail-closed posture for missing/invalid eval/gate evidence,
- keep FAIL outcomes as forensics-only (explicit ineligible posture, no publish eligibility).

### Authorities used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3.D` intent)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/contracts/learning_registry/eval_report_v0.schema.yaml`
- `src/fraud_detection/learning_registry/contracts.py` (`EvalReportContract`)
- Existing MF phase dependencies:
  - `src/fraud_detection/model_factory/phase3.py`
  - `src/fraud_detection/model_factory/phase4.py`

### Problem framing and alternatives considered
1. Reuse Phase 4 gate_decision as implicit gate receipt and defer explicit eligibility artifacts.
   - Rejected: Phase 5 DoD requires explicit gate and publish-eligibility artifacts.
2. Emit eligibility only for PASS runs and skip FAIL receipts.
   - Rejected: FAIL outcomes must remain explicit for forensics and governance continuity.
3. Implement dedicated Phase 5 evaluator that:
   - validates eval evidence refs and schema,
   - emits immutable gate receipt for both PASS/FAIL,
   - emits immutable publish-eligibility receipt with explicit reason taxonomy,
   - blocks missing/invalid evidence fail-closed.
   - Selected.

### Planned file changes
- New code:
  - `src/fraud_detection/model_factory/phase5.py`
- Update exports:
  - `src/fraud_detection/model_factory/__init__.py`
- New tests:
  - `tests/services/model_factory/test_phase5_gate_policy.py`
- Documentation/status updates after validation:
  - `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/model_factory.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-10.md`

### Validation plan
- Compile MF Phase 5 module/tests.
- Targeted Phase 5 matrix.
- Combined MF regression (Phases 1..5 + learning contracts).
- OFS/MF/learning compatibility sanity matrix.

### Drift sentinel checkpoint
If Phase 5 permits publish eligibility without explicit PASS receipt and validated eval evidence refs, phase closure is blocked as material drift.

## Entry: 2026-02-10 2:15PM - Applied MF Phase 5 implementation (gate receipt + publish eligibility policy)

### Implemented files and surfaces
- Added MF Phase 5 gate/eligibility module:
  - `src/fraud_detection/model_factory/phase5.py`
- Updated MF exports for Phase 5 surfaces:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 5 matrix:
  - `tests/services/model_factory/test_phase5_gate_policy.py`

### Phase 5 outcomes
- MF now emits explicit immutable gate receipt artifacts for both PASS and FAIL outcomes.
- MF now emits explicit immutable publish-eligibility artifacts with clear decision posture:
  - `ELIGIBLE` when PASS and required evidence refs are present/valid,
  - `INELIGIBLE` for FAIL outcomes (forensics-only posture).
- Missing/invalid eval evidence now fails closed before eligibility decisions.
- Gate/eligibility artifacts are run-scoped and idempotent under reruns; immutability drift is detected and blocked.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/phase5.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase5_gate_policy.py` (`PASS`).
- Targeted Phase 5:
  - `python -m pytest tests/services/model_factory/test_phase5_gate_policy.py -q --import-mode=importlib` (`4 passed`).
- MF + learning contracts regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`37 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`60 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected for Phase 5 scope.
- PASS/FAIL policy boundary is now explicit, immutable, and fail-closed on missing eval evidence.
- Residual risk surface moves to MF Phase 6 (`bundle packaging + MPR publish handshake`).

### Plan progression
- MF Phase 5 is closed.
- Next MF phase is Phase 6 (`bundle packaging + MPR publish handshake`).

## Entry: 2026-02-10 2:19PM - Corrective pre-change lock for MF Phase 6 (documentation-order fix)

### Corrective reason
Implementation work for MF Phase 6 began before this explicit pre-change lock entry was appended. This corrective entry is added immediately to preserve auditable chronology without rewriting prior history.

### Phase objective (DoD-locked)
Implement MF Phase 6 bundle packaging + MPR publish handshake with idempotent append-only semantics:
- immutable bundle publication payload packaging with required compatibility metadata,
- schema-validated publication payloads,
- idempotent publish handshake keyed by `(bundle_id, bundle_version)`,
- fail-closed conflict posture for identity payload drift,
- immutable publish success/evidence artifacts.

### Authorities used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`6.3.E`)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `src/fraud_detection/learning_registry/contracts.py` (`BundlePublicationContract`, `RegistryLifecycleEventContract`)
- Existing MF corridor outputs:
  - `src/fraud_detection/model_factory/phase3.py`
  - `src/fraud_detection/model_factory/phase5.py`

### Planned file changes
- New code:
  - `src/fraud_detection/model_factory/phase6.py`
- Update exports:
  - `src/fraud_detection/model_factory/__init__.py`
- New tests:
  - `tests/services/model_factory/test_phase6_bundle_publish.py`
- Documentation/status updates:
  - build plans + implementation maps + logbook entries.

### Validation plan
- Compile Phase 6 code/tests.
- Run targeted Phase 6 matrix.
- Run combined MF regression and OFS/MF learning compatibility regression.

### Drift sentinel checkpoint
If publish handshake allows identity reuse with divergent payload bytes, Phase 6 must remain blocked as material drift.

## Entry: 2026-02-10 2:23PM - Applied MF Phase 6 implementation (bundle packaging + MPR publish handshake)

### Implemented files and surfaces
- Added MF Phase 6 package/publish module:
  - `src/fraud_detection/model_factory/phase6.py`
- Updated MF exports for Phase 6 surfaces:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 6 matrix:
  - `tests/services/model_factory/test_phase6_bundle_publish.py`
- Minor Phase 3 provenance completion for publish scope carry-forward:
  - `src/fraud_detection/model_factory/phase3.py` now includes `target_scope` in `input_refs`.

### Phase 6 outcomes
- Bundle packaging now emits immutable, schema-valid `BundlePublication` payloads with:
  - artifact/eval/manifest lineage refs,
  - compatibility metadata,
  - release provenance.
- Publish handshake is idempotent and append-only by `(bundle_id, bundle_version)`:
  - same identity + same payload -> converges (already-published posture),
  - same identity + different payload -> fail-closed conflict (`PUBLISH_CONFLICT`).
- Registry-lifecycle publication fact emission is now explicit and schema-validated.
- Publish handshake receipts are immutable and discoverable by ref.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/phase3.py src/fraud_detection/model_factory/phase6.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase6_bundle_publish.py` (`PASS`).
- Targeted Phase 6:
  - `python -m pytest tests/services/model_factory/test_phase6_bundle_publish.py -q --import-mode=importlib` (`5 passed`).
- MF + learning contracts regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`42 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`65 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected for Phase 6 scope.
- Packaging and publish handshake are now explicit, immutable, and conflict-safe.
- Residual risk surface moves to MF Phase 7 (`negative-path matrix + fail-closed taxonomy hardening`).

### Plan progression
- MF Phase 6 is closed.
- Next MF phase is Phase 7 (`negative-path matrix + fail-closed taxonomy hardening`).

## Entry: 2026-02-10 2:30PM - Pre-change implementation lock for MF Phase 7 (negative-path matrix + fail-closed taxonomy hardening)

### Problem framing
MF phases 1..6 are implemented and green, but the closure surface for `6.3.F` is still open: we need explicit executable proof that unsafe states are blocked across the whole corridor and that failure codes remain stable enough for later obs/gov onboarding.

### Authorities and constraints used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 7 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`6.3.F`)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md` (publish retry, idempotency, fail-closed edges)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (append-only + fail-closed rails)
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md` (unknown compatibility/evidence => fail closed)

### Alternatives considered
1. Test-only matrix without new source surfaces.
   - Pros: minimal code.
   - Cons: failure taxonomy remains implicit and can drift silently as more phases are added.
2. New runtime classifier with broad behavior changes.
   - Pros: stronger runtime semantics.
   - Cons: too invasive for Phase 7 scope and risks changing already-green lanes.
3. Minimal new taxonomy authority module + executable negative-path matrix.
   - Pros: explicit stable taxonomy anchor, minimal runtime risk, directly satisfies DoD.
   - Decision: choose option 3.

### Implementation decisions
- Add `src/fraud_detection/model_factory/phase7.py` to pin MF Phase-7 failure taxonomy (class->codes map, stable code set helpers).
- Add `tests/services/model_factory/test_phase7_negative_matrix.py` with executable proofs for required failures:
  - missing manifest/config refs,
  - digest mismatch,
  - incompatible feature/schema,
  - missing EvalReport/gate receipt,
  - partial publish retry behavior,
  - train + publish idempotency checks.
- Export Phase 7 taxonomy helpers from `src/fraud_detection/model_factory/__init__.py`.

### Invariants to enforce
- Unknown or missing evidence remains fail-closed.
- Publish retry never forces retraining and converges deterministically.
- Failure codes used in matrix remain members of the pinned taxonomy set.
- Taxonomy cardinality remains bounded (low-volume posture).

### Validation plan
- Compile Phase 7 module/tests.
- Run targeted Phase 7 matrix.
- Run MF regression (Phase1..7).
- Run MF+OFS+learning compatibility regression.

### Drift sentinel checkpoint
If any negative path executes without typed fail-closed code, or if taxonomy mapping returns unknown for expected failures, Phase 7 remains blocked and must not be marked complete.

## Entry: 2026-02-10 2:33PM - Applied MF Phase 7 implementation (negative-path matrix + fail-closed taxonomy hardening)

### Implemented files and surfaces
- Added MF Phase 7 taxonomy authority module:
  - `src/fraud_detection/model_factory/phase7.py`
- Updated MF exports for Phase 7 helpers:
  - `src/fraud_detection/model_factory/__init__.py`
- Added MF Phase 7 matrix:
  - `tests/services/model_factory/test_phase7_negative_matrix.py`

### Phase 7 outcomes
- MF now has an explicit pinned Phase-7 failure taxonomy surface (category->code map, code classification helpers, known-code set) for stable fail-closed semantics.
- Required negative-path proofs are executable and green for:
  - missing manifest/config refs,
  - manifest digest mismatch,
  - feature/schema incompatibility,
  - missing eval/gate evidence,
  - partial publish retry recovery.
- Train and publish retry idempotency are now validated in one corridor matrix:
  - deterministic train identity remains stable across re-resolve/re-execute,
  - publish retries converge to `ALREADY_PUBLISHED` and recover missing receipt/event artifacts without retrain.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/phase7.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase7_negative_matrix.py` (`PASS`).
- Targeted Phase 7:
  - `python -m pytest tests/services/model_factory/test_phase7_negative_matrix.py -q --import-mode=importlib` (`3 passed`).
- MF + learning contracts regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`45 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`68 passed`).

### Drift sentinel assessment
- No designed-flow contradiction detected for Phase 7 scope.
- Required `6.3.F` fail-closed proof set is explicit, typed, and replay/retry safe.
- Residual risk surface moves to MF Phase 8 (`run/operate onboarding`).

### Plan progression
- MF Phase 7 is closed.
- Next MF phase is Phase 8 (`run/operate onboarding`).

## Entry: 2026-02-10 2:37PM - Pre-change implementation lock for MF Phase 8 (run/operate onboarding)

### Problem framing
MF phases 1..7 are closed but not yet operating as a run/operate-managed job unit. Without Phase 8 onboarding, MF remains matrix-only and not reachable through the orchestrator packs used for live parity operation.

### Authorities and constraints used
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md` (Phase 8 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`6.6` dependency posture)
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- Existing local-parity patterns from OFS Phase 8:
  - `src/fraud_detection/offline_feature_plane/worker.py`
  - `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
  - `config/platform/profiles/local_parity.yaml`

### Alternatives considered
1. Add only run/operate pack process command for MF and no worker request lane.
   - Pros: quick.
   - Cons: fails DoD requirement for explicit launcher/worker and retry posture checks.
2. Reuse OFS worker schema with MF-specific embedded command shim.
   - Pros: fewer files.
   - Cons: blurs component boundaries and increases drift risk.
3. Add MF-dedicated worker/launcher module mirroring OFS shape, then wire pack/profile/Make targets.
   - Pros: clear ownership, deterministic request schema, explicit retry boundary, easier env-ladder portability.
   - Decision: choose option 3.

### Implementation decisions
- Add `src/fraud_detection/model_factory/worker.py` with:
  - profile-driven config loader,
  - deterministic run-config digest stamping,
  - request queue processing (`train_build`, `publish_retry`),
  - run-control integration (`enqueue/start/mark_*`),
  - immutable run-scoped invocation receipts.
- Add MF launcher policy file and profile wiring:
  - `config/platform/mf/launcher_policy_v0.yaml`
  - extend `config/platform/profiles/local_parity.yaml` with `mf.policy/wiring` block.
- Onboard MF worker into run/operate learning pack:
  - update `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml` env + `mf_job_worker` process.
- Add Makefile env vars and enqueue targets for MF train build and publish retry.
- Update runbook with MF launcher invocation/retry/posture checks.
- Add Phase 8 worker tests:
  - `tests/services/model_factory/test_phase8_run_operate_worker.py`.

### Invariants to enforce
- Active run scope check: request `platform_run_id` must match required active run.
- Run-config digest mismatch fails closed before execution.
- Publish retry path must not retrain and must require `PUBLISH_PENDING` state.
- No hidden filesystem fallback: wiring must use profile-declared object store + ledger locators.

### Validation plan
- Compile MF worker + updated surfaces.
- Run targeted Phase 8 matrix.
- Run MF Phase1..8 regression.
- Run MF+OFS+learning compatibility regression.

### Drift sentinel checkpoint
If MF remains absent from `learning_jobs` pack or lacks active-run guard/digest guard, Phase 8 remains blocked.

## Entry: 2026-02-10 2:49PM - MF Phase 8 continuation lock after interrupted turn

### Continuation context
- Prior turn was interrupted during MF Phase 8 onboarding while `src/fraud_detection/model_factory/worker.py` and `config/platform/mf/launcher_policy_v0.yaml` were being assembled.
- Current workspace confirms `worker.py` exists but run/operate onboarding closure remains partial (pack/Makefile/runbook/tests/status docs still pending).

### Remaining closure decisions (locked before edits)
- Keep MF as a request-driven job worker under `learning_jobs` pack, parallel to OFS (no always-on daemon mode).
- Enforce active-run and run-config digest guards as hard fail-closed gates in worker receipts.
- Add MF enqueue controls to Makefile so operators use the same run/operate-managed invocation surface.
- Add Phase 8 matrix tests focused on run/operate invariants (request success path, digest mismatch fail-closed, publish-retry pending-state gate).
- Update runbook and build-plan statuses only after tests pass.

### Planned validation
- `py_compile` on MF worker + new Phase 8 tests.
- Targeted Phase 8 matrix test module.
- MF regression (`phase1..phase8`).
- MF+OFS+learning compatibility regression.

### Drift sentinel checkpoint
If MF is not present in `learning_jobs` pack or runbook still claims OFS-only learning jobs coverage, Phase 8 remains open.

## Entry: 2026-02-10 2:54PM - Applied MF Phase 8 closure (run/operate onboarding)

### What was implemented
- Completed MF Phase 8 runtime onboarding surfaces:
  - `src/fraud_detection/model_factory/worker.py`
  - `tests/services/model_factory/test_phase8_run_operate_worker.py`
  - `config/platform/mf/launcher_policy_v0.yaml`
  - `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
  - `config/platform/profiles/local_parity.yaml`
  - `Makefile`
  - `docs/runbooks/platform_parity_walkthrough_v0.md`

### Key mechanics now enforced
- MF is a request-driven worker unit under run/operate (`mf_job_worker`), co-located with OFS in the `learning_jobs` pack.
- Active-run scoping is fail-closed via `required_platform_run_id` checks.
- Run-config digest mismatch is fail-closed before any train/retry execution.
- Operator invoke surface is explicit:
  - `make platform-mf-enqueue-train-build`
  - `make platform-mf-enqueue-publish-retry`
- Publish retry remains publish-only and requires `PUBLISH_PENDING` state from MF run-control/ledger.

### Validation evidence
- Syntax:
  - `python -m py_compile src/fraud_detection/model_factory/worker.py tests/services/model_factory/test_phase8_run_operate_worker.py` (`PASS`).
- Targeted Phase 8 matrix:
  - `python -m pytest tests/services/model_factory/test_phase8_run_operate_worker.py -q --import-mode=importlib` (`3 passed`).
- MF + learning regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/model_factory/test_phase8_run_operate_worker.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`48 passed`).
- MF + OFS + learning compatibility regression:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/model_factory/test_phase8_run_operate_worker.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`71 passed`).

### Plan/status updates applied
- `docs/model_spec/platform/implementation_maps/model_factory.build_plan.md`
  - Phase 8 marked complete with implementation note + validation evidence.
  - Next action moved to Phase 9.
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - Phase 6 status updated to MF phases `1..8` complete.
  - Added MF Phase 8 completion line and shifted next active step to `6.3` Phase 9.

### Drift sentinel assessment
- No designed-flow/runtime drift remains for MF Phase 8 scope.
- `learning_jobs` run/operate lane now matches plane-agnostic orchestration law for both OFS and MF job units.

## Entry: 2026-02-10 2:57PM - Post-closure correction: MF launcher policy path resolution

### Issue found during closure review
- MF Phase 8 worker initially resolved `mf.policy.launcher_policy_ref` relative to `profile_path.parent` unconditionally.
- In local parity (`config/platform/profiles/local_parity.yaml`), this would incorrectly rewrite `config/platform/mf/launcher_policy_v0.yaml` into `config/platform/profiles/config/platform/mf/...`.

### Applied fix
- Updated `load_worker_config(...)` in `src/fraud_detection/model_factory/worker.py`:
  - keep configured relative path as-is (repo/CWD resolution first, matching OFS posture),
  - only fallback to profile-relative path when the configured relative path does not exist.

### Validation rerun (post-fix)
- `python -m py_compile src/fraud_detection/model_factory/worker.py tests/services/model_factory/test_phase8_run_operate_worker.py` (`PASS`).
- `python -m pytest tests/services/model_factory/test_phase8_run_operate_worker.py -q --import-mode=importlib` (`3 passed`).
- `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/model_factory/test_phase8_run_operate_worker.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`48 passed`).
- `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/model_factory/test_phase5_gate_policy.py tests/services/model_factory/test_phase6_bundle_publish.py tests/services/model_factory/test_phase7_negative_matrix.py tests/services/model_factory/test_phase8_run_operate_worker.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`71 passed`).

### Drift sentinel assessment
- This correction removes a latent local parity launch-time drift and aligns MF with existing OFS path-resolution semantics.
