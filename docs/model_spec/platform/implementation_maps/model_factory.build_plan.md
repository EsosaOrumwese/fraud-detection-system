# Model Factory Build Plan (v0)
_As of 2026-02-10_

## Purpose
Provide an executable, component-scoped plan for Model Factory (MF) aligned to platform Phase `6.3` (`train/eval/publish corridor`) with explicit dependency gates for platform Phases `6.6/6.7/6.8`.

## Scope and role
- MF is an offline, job-driven build authority.
- Primary flow:
  - `OFS DatasetManifest refs + pinned training/eval config -> MF train/eval evidence -> candidate bundle publish intent -> MPR`.
- MF does not own:
  - label truth mutation (LS),
  - ACTIVE bundle lifecycle (MPR),
  - runtime serving decisions (DF),
  - replay truth authority (EB/Archive/OFS).

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.3`, dependency posture `6.4/6.6/6.7/6.8`)
- `docs/model_spec/platform/component-specific/model_factory.design-authority.md`
- `docs/model_spec/platform/component-specific/model_policy_registry.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

## Binding rails
- MF consumes only explicit by-ref DatasetManifest inputs and pinned config/profile refs.
- Deterministic run identity and idempotent retry semantics are mandatory.
- Eval evidence and gate receipts are immutable and append-only.
- Bundle publish is append-only and immutable; MF never activates bundles.
- Unknown compatibility or missing lineage/evidence fails closed.
- No scanning for "latest" dataset/config/profile.

## Component boundary
- MF owns:
  - train/eval run identity and run lifecycle records,
  - immutable eval evidence and PASS/FAIL gate receipts,
  - candidate bundle packaging and publish handshake toward MPR.
- MF does not own:
  - registry ACTIVE resolution/promotion/rollback authority,
  - orchestration policy authority (run/operate owns triggers),
  - corridor-level governance policy definitions (obs/gov owns policy; MF emits required facts).

## Phase plan (v0)

### Phase 1 - TrainBuildRequest contract + deterministic run identity
**Intent:** lock input semantics and idempotency before runtime mechanics.

**DoD checklist:**
- `TrainBuildRequest` contract is pinned with required by-ref refs and trigger provenance.
- `TrainRunKey` and deterministic `train_run_id` recipe are pinned and testable.
- Request rejection taxonomy is explicit (`MANIFEST_REF_MISSING`, `CONFIG_REF_MISSING`, `REQUEST_INVALID`, etc.).
- Inputs align with OFS/MF boundary contract and ownership rails.

**Implementation status note (2026-02-10):**
- Phase 1 contract and identity surfaces implemented:
  - `src/fraud_detection/model_factory/contracts.py`
  - `src/fraud_detection/model_factory/ids.py`
  - `src/fraud_detection/model_factory/__init__.py`
  - `docs/model_spec/platform/contracts/learning_registry/mf_train_build_request_v0.schema.yaml`
- Contract indexes updated:
  - `docs/model_spec/platform/contracts/learning_registry/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- Validation evidence:
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`15 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`26 passed`).

### Phase 2 - Run control + idempotent run ledger
**Intent:** ensure retries/restarts cannot fork training meaning.

**DoD checklist:**
- MF run ledger exists with stable states (`QUEUED -> RUNNING -> EVAL_READY -> PASS|FAIL -> PUBLISHED?`).
- Same semantic request converges to the same run identity/outcome under retry.
- Publish-only retry is explicit and cannot retrigger training silently.
- Run records persist deterministic input summary and code/config release IDs.

**Implementation status note (2026-02-10):**
- Phase 2 run ledger/control implemented:
  - `src/fraud_detection/model_factory/run_ledger.py`
  - `src/fraud_detection/model_factory/run_control.py`
  - `src/fraud_detection/model_factory/__init__.py` (Phase 2 exports)
  - `tests/services/model_factory/test_phase2_run_ledger.py`
- Validation evidence:
  - `python -m pytest tests/services/model_factory/test_phase2_run_ledger.py -q --import-mode=importlib` (`7 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`22 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`39 passed`).

### Phase 3 - Input resolver + provenance lock
**Intent:** resolve and lock all meaning-shaping refs before train/eval starts.

**DoD checklist:**
- DatasetManifest refs are resolved explicitly and verified for digest/immutability posture.
- Feature/schema compatibility basis is validated before training starts.
- MF records immutable `resolved_train_plan` artifact with all pinned refs/revisions.
- Missing or incompatible refs fail closed with typed taxonomy.

**Implementation status note (2026-02-10):**
- Phase 3 resolver/provenance surfaces implemented:
  - `src/fraud_detection/model_factory/phase3.py`
  - `src/fraud_detection/model_factory/__init__.py` (Phase 3 exports)
  - `tests/services/model_factory/test_phase3_resolver.py`
- Phase 3 resolver now enforces:
  - explicit by-ref DatasetManifest resolution with schema validation via `DatasetManifestContract`,
  - run-scope checks (`manifest.platform_run_id == request.platform_run_id`) fail-closed,
  - feature/schema compatibility checks against pinned training profile,
  - immutable resolved-train-plan artifact emission (`mf/resolved_train_plan/...`) with drift detection.
- Validation evidence:
  - `python -m py_compile src/fraud_detection/model_factory/phase3.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase3_resolver.py` (`PASS`).
  - `python -m pytest tests/services/model_factory/test_phase3_resolver.py -q --import-mode=importlib` (`6 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`28 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`51 passed`).

### Phase 4 - Train/eval execution corridor
**Intent:** produce reproducible model/eval outputs from pinned inputs.

**DoD checklist:**
- Train/eval execution records split strategy and seed policy explicitly.
- EvalReport includes schema/versioned metrics and reproducibility basis.
- Required artifacts are written immutably under `mf/...` with by-ref linkage.
- Leakage guardrails (as-of basis adherence, no hidden "now") are enforced fail-closed.

**Implementation status note (2026-02-10):**
- Phase 4 execution corridor implemented:
  - `src/fraud_detection/model_factory/phase4.py`
  - `src/fraud_detection/model_factory/__init__.py` (Phase 4 exports)
  - `tests/services/model_factory/test_phase4_execution.py`
- Phase 4 executor now enforces:
  - explicit split strategy + seed policy extraction/recording from pinned training profile,
  - deterministic stage seed and deterministic metric derivation from pinned inputs,
  - schema-validated `EvalReport` emission via `EvalReportContract`,
  - immutable execution/evidence artifact writes under `mf/train_runs/<run_key>/...`,
  - leakage guard fail-closed posture (`label_asof_utc` scope + `observed_time<=label_asof_utc` rule alignment).
- Validation evidence:
  - `python -m py_compile src/fraud_detection/model_factory/phase4.py src/fraud_detection/model_factory/__init__.py tests/services/model_factory/test_phase4_execution.py` (`PASS`).
  - `python -m pytest tests/services/model_factory/test_phase4_execution.py -q --import-mode=importlib` (`5 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`33 passed`).
  - `python -m pytest tests/services/model_factory/test_phase1_contracts.py tests/services/model_factory/test_phase1_ids.py tests/services/model_factory/test_phase2_run_ledger.py tests/services/model_factory/test_phase3_resolver.py tests/services/model_factory/test_phase4_execution.py tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`56 passed`).

### Phase 5 - Gate receipt and publish eligibility policy
**Intent:** make publish eligibility explicit and auditable.

**DoD checklist:**
- MF emits explicit PASS/FAIL gate receipt bound to `train_run_id`.
- Publish eligibility requires PASS + required evidence refs.
- FAIL outcomes remain forensics-only and cannot publish.
- Missing gate/eval evidence is a hard fail-closed blocker.

### Phase 6 - Bundle packaging + MPR publish handshake
**Intent:** publish immutable candidate bundles with compatibility metadata.

**DoD checklist:**
- Bundle payload includes artifact digests, eval refs, manifest lineage, compatibility metadata, and release IDs.
- Publish to MPR is idempotent by `(bundle_id, version)` and append-only.
- Packaging or publish drift (digest mismatch, missing compatibility metadata) is fail-closed.
- MF publish success/failure artifacts are immutable and discoverable by ref.

### Phase 7 - Negative-path matrix and fail-closed taxonomy hardening
**Intent:** prove the corridor blocks unsafe states under real failure modes.

**DoD checklist:**
- Executable failures include:
  - missing manifest/config refs,
  - digest mismatch,
  - incompatible feature/schema contract,
  - missing EvalReport/gate receipt,
  - partial publish retry behavior.
- Typed anomaly/failure taxonomy is stable and low-volume.
- Idempotency under retries is validated for train and publish paths.

### Phase 8 - Run/Operate onboarding (meta-layer gate)
**Intent:** onboard MF into orchestrated operation under environment-ladder semantics.

**DoD checklist:**
- MF job unit is onboarded into run/operate packs with explicit launcher/worker entrypoints.
- Active-run scoping and run-config digest stamping are enforced.
- Local parity profile wiring uses pinned substrate classes from environment map (no hidden filesystem fallback).
- Runbook includes MF invoke/retry/posture checks.

### Phase 9 - Obs/Gov onboarding (meta-layer gate)
**Intent:** make MF lifecycle auditable without hot-path drag.

**DoD checklist:**
- Run-scoped MF counters are emitted (`train_requested`, `train_completed`, `eval_pass`, `eval_fail`, `bundle_published`, anomalies).
- Governance lifecycle facts are emitted with actor attribution and evidence refs.
- Evidence-ref resolution audits are emitted for protected ref consumption where applicable.
- MF reconciliation contribution refs are discoverable by platform reporter surfaces.

### Phase 10 - Integration closure gate (platform 6.3 closure evidence)
**Intent:** prove MF corridor is complete and safe before `6.4/6.8` progression.

**DoD checklist:**
- Positive continuity proof exists:
  - `DatasetManifest ref -> MF train/eval -> gate receipt -> bundle publish artifact`.
- Handoff readiness for MPR lifecycle exists with immutable bundle/evidence package.
- Negative-path fail-closed proof exists for missing evidence, incompatibility, and publish idempotency conflicts.
- Meta-layer coverage proofs (`8` and `9`) are present before closure declaration.

## Validation gate (required before phase advancement)
- Contract tests:
  - request contract validation,
  - run-identity determinism/idempotency.
- Corridor tests:
  - input resolution and provenance lock,
  - train/eval evidence emission,
  - publish eligibility and bundle packaging.
- Failure tests:
  - fail-closed matrix for required negative paths.
- Integration tests:
  - OFS-to-MF manifest handoff compatibility,
  - MF-to-MPR publish payload admissibility.
- Evidence logging in:
  - `docs/model_spec/platform/implementation_maps/model_factory.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/<month>/<date>.md`

## Non-goals for v0
- No ACTIVE lifecycle ownership or promotion decisions inside MF.
- No implicit dataset/config discovery by scanning object store.
- No always-on training daemon mode.

## Status (rolling)
- Phase 1 (`TrainBuildRequest contract + deterministic run identity`): complete (implemented and validated on `2026-02-10`).
- Phase 2 (`run control + idempotent run ledger`): complete (implemented and validated on `2026-02-10`).
- Phase 3 (`input resolver + provenance lock`): complete (implemented and validated on `2026-02-10`).
- Phase 4 (`train/eval execution corridor`): complete (implemented and validated on `2026-02-10`).
- Phase 5 (`gate receipt + publish eligibility policy`): pending.
- Phase 6 (`bundle packaging + MPR publish handshake`): pending.
- Phase 7 (`negative-path matrix + fail-closed taxonomy`): pending.
- Phase 8 (`run/operate onboarding`): pending.
- Phase 9 (`obs/gov onboarding`): pending.
- Phase 10 (`integration closure gate`): pending.
- Next action: implement Phase 5 (`gate receipt + publish eligibility policy`).
