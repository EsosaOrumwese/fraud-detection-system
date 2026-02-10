# Offline Feature Plane Build Plan (v0)
_As of 2026-02-10_

## Purpose
Provide a closure-grade, component-scoped plan for Offline Feature Plane (OFS) aligned to platform Phase 6.2 (`OFS dataset build corridor`) and the pinned learning-loop flow.

## Scope and role
- OFS is an offline, job-driven replay and reconstruction plane.
- Primary flow: `Archive/EB + Label Store + feature definitions + SR run_facts_view -> OFS -> DatasetManifest + by-ref artifacts -> MF`.
- Optional flow: parity rebuild against DLA/DF/OFP provenance anchors.
- OFS does not own event truth, label truth, model training, or ACTIVE bundle lifecycle.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `6.2`, plus `6.6/6.7` meta-layer closure requirements)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/offline_feature_plane.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

## Binding rails
- OFS is a job deployment unit, not an always-on hot-path service.
- Replay basis authority is offset/watermark basis; time selectors must resolve to explicit offsets.
- Label eligibility is explicit and leakage-safe (`observed_time <= label_asof_utc`).
- Dataset identity is deterministic and immutable; no silent overwrite.
- No scanning for "latest"; all input refs are explicit and by-ref.
- Fail closed on unknown compatibility, missing evidence, or replay mismatch.

## Component boundary
- OFS owns:
  - build-intent execution for offline dataset/parity/forensic invocations,
  - replay-basis resolution and deterministic feature reconstruction from pinned inputs,
  - immutable artifact publication and DatasetManifest authority under `ofs/...`,
  - parity/anomaly evidence for replay correctness and optional OFP shadow checks.
- OFS does not own:
  - label truth mutation (Label Store),
  - model training/eval publication intent (Model Factory),
  - bundle activation and ACTIVE lifecycle (MPR/Registry),
  - runtime event admission or decision serving.

## Phase plan (v0)

### Phase 1 - BuildIntent + dataset identity + contract lock
**Intent:** pin OFS run meaning before implementation mechanics.

**DoD checklist:**
- BuildIntent contract is pinned with deterministic idempotency key (`request_id`) and explicit intent kinds (`dataset_build`, `parity_rebuild`, `forensic_rebuild`).
- Dataset identity law is pinned:
  - replay basis offsets,
  - label as-of and resolution rule,
  - feature definition set/version refs,
  - join scope and filters,
  - OFS policy/config revision,
  - `ofs_code_release_id`.
- Rejection taxonomy is explicit for inadmissible intents (`BASIS_UNRESOLVED`, `LABEL_ASOF_MISSING`, `FEATURE_PROFILE_UNRESOLVED`, `RUN_FACTS_UNAVAILABLE`, etc.).
- Contracts align to `dataset_manifest_v0` authority and ownership boundaries from `learning_registry/ownership_boundaries_v0.yaml`.

**Implementation status note (2026-02-10):**
- Phase 1 contract + identity surfaces implemented:
  - `src/fraud_detection/offline_feature_plane/contracts.py`
  - `src/fraud_detection/offline_feature_plane/ids.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py`
  - `docs/model_spec/platform/contracts/learning_registry/ofs_build_intent_v0.schema.yaml`
- Contract indexes updated:
  - `docs/model_spec/platform/contracts/learning_registry/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`15 passed`).

### Phase 2 - Run control + idempotent run ledger (S1)
**Intent:** ensure retries/restarts cannot create semantic drift.

**DoD checklist:**
- OFS run ledger exists with deterministic `run_key` and stable run state machine (`QUEUED -> RUNNING -> DONE/FAILED/PUBLISH_PENDING`).
- Duplicate trigger with same `request_id` converges to same run identity/outcome.
- Retry posture is explicit and bounded; publish-only retry does not retrain/replay.
- Run receipts include pinned input summary and run-level provenance.

**Implementation status note (2026-02-10):**
- Phase 2 run ledger/control implemented:
  - `src/fraud_detection/offline_feature_plane/run_ledger.py`
  - `src/fraud_detection/offline_feature_plane/run_control.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`21 passed`).

### Phase 3 - Pin and provenance resolver (S2)
**Intent:** resolve all meaning-shaping refs before replay starts.

**DoD checklist:**
- Resolver loads SR `run_facts_view` by explicit run ref and enforces no-PASS-no-read for any gated world refs.
- Feature profile resolution is deterministic and records resolved revision/digest.
- Optional parity anchor resolution from DLA/DF provenance is explicit and typed.
- Resolved BuildPlan artifact is emitted and immutable per run.

**Implementation status note (2026-02-10):**
- Phase 3 pin/provenance resolver implemented:
  - `src/fraud_detection/offline_feature_plane/phase3.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`27 passed`).

### Phase 4 - Replay basis resolver + completeness receipts (S3)
**Intent:** make EB/Archive replay deterministic and auditable.

**DoD checklist:**
- Replay basis is resolved to canonical offset tuples per stream/partition.
- EB/Archive cutover is explicit; Archive is authoritative beyond retention.
- Payload hash mismatch on same offset tuple is emitted as anomaly and fails closed for training-intent builds.
- Completeness receipts are produced and required before publication as `COMPLETE`.

**Implementation status note (2026-02-10):**
- Phase 4 replay/completeness corridor implemented:
  - `src/fraud_detection/offline_feature_plane/phase4.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase4_replay_basis.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`33 passed`).

### Phase 5 - Label as-of resolver and coverage gate (S4)
**Intent:** enforce leakage-safe labels and explicit coverage posture.

**DoD checklist:**
- Label reads are only from Label Store resolved timeline/query surfaces.
- Eligibility rule enforced: `observed_time <= label_asof_utc`.
- Label maturity and coverage diagnostics are emitted and pinned into build evidence.
- Training-intent builds fail closed on coverage policy violations unless explicitly tagged non-training.

**Implementation status note (2026-02-10):**
- Phase 5 label as-of/coverage corridor implemented:
  - `src/fraud_detection/offline_feature_plane/phase5.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase4_replay_basis.py tests/services/offline_feature_plane/test_phase5_label_resolver.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`37 passed`).

### Phase 6 - Deterministic feature reconstruction and dataset drafting (S5)
**Intent:** produce reproducible, version-locked offline feature rows.

**DoD checklist:**
- OFS uses version-locked feature definition refs (shared authority with OFP) and records them in provenance.
- Replay ordering, dedupe, and tie-break rules are deterministic under at-least-once realities.
- Dataset drafts/snapshots include digestable row-order canonicalization rules.
- Optional parity hashes are emitted when parity intent is requested.

**Implementation status note (2026-02-10):**
- Phase 6 deterministic draft corridor implemented:
  - `src/fraud_detection/offline_feature_plane/phase6.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase4_replay_basis.py tests/services/offline_feature_plane/test_phase5_label_resolver.py tests/services/offline_feature_plane/test_phase6_dataset_draft.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`42 passed`).

### Phase 7 - Artifact publication + DatasetManifest authority (S6)
**Intent:** define when a dataset becomes authoritative.

**DoD checklist:**
- Publish is atomic and immutable under `ofs/...`; no silent overwrite.
- DatasetManifest is written only after completeness/evidence gates pass.
- Manifest includes replay basis, label basis, feature refs, digests, provenance refs, and policy/config revision.
- Supersession/backfill linkage is append-only and explicit.

**Implementation status note (2026-02-10):**
- Phase 7 publication corridor implemented:
  - `src/fraud_detection/offline_feature_plane/phase7.py`
  - `src/fraud_detection/offline_feature_plane/__init__.py` (exports)
- Validation evidence:
  - `python -m pytest tests/services/offline_feature_plane/test_phase1_contracts.py tests/services/offline_feature_plane/test_phase1_ids.py tests/services/offline_feature_plane/test_phase2_run_ledger.py tests/services/offline_feature_plane/test_phase3_resolver.py tests/services/offline_feature_plane/test_phase4_replay_basis.py tests/services/offline_feature_plane/test_phase5_label_resolver.py tests/services/offline_feature_plane/test_phase6_dataset_draft.py tests/services/offline_feature_plane/test_phase7_manifest_publication.py tests/services/learning_registry/test_phase61_contracts.py -q --import-mode=importlib` (`47 passed`).

### Phase 8 - Run/Operate onboarding (meta-layer gate)
**Intent:** make OFS first-class in orchestration from day one.

**DoD checklist:**
- OFS job unit is onboarded into run/operate packs with explicit command entrypoints and bounded retry policy.
- Local parity wiring is aligned to environment map stack classes (MinIO/S3, Postgres, Kinesis/local event substrate as configured) with no hidden filesystem-only fallback.
- Active-run scoping and run-config digest stamping are enforced in launcher surfaces.
- Runbook steps for OFS invocation and rerun/publish-only retry are documented.

### Phase 9 - Obs/Gov onboarding (meta-layer gate)
**Intent:** keep OFS auditable without hot-path overhead.

**DoD checklist:**
- Run-scoped OFS counters exist (`build_requested/completed/failed`, `datasets_built`, anomaly classes).
- Governance lifecycle facts are emitted for dataset build completion/failure and parity outcomes.
- Reconciliation artifact includes OFS contribution refs and compact run summary.
- Evidence-ref resolution audit is enforced for protected refs consumed by OFS.

### Phase 10 - Integration closure gate (platform Phase 6.2 closure evidence)
**Intent:** prove OFS corridor is complete and safe before deeper Phase 6 work advances.

**DoD checklist:**
- Positive-path proof exists:
  - build intent -> replay/label resolution -> DatasetManifest commit -> OFS reconciliation artifact.
- MF handoff readiness proof exists:
  - MF-admissible DatasetManifest refs are produced and validate against learning contract authority.
- Negative-path proof exists:
  - replay mismatch fail-closed,
  - missing label basis fail-closed,
  - unresolved feature profile fail-closed,
  - PASS-gated world ref denial (`no PASS -> no read`).
- Platform report/reconciliation surfaces include OFS outputs with run-scoped evidence refs.

## Validation gate (required before phase advancement)
- Contract tests:
  - BuildIntent validation,
  - DatasetFingerprint determinism,
  - DatasetManifest schema conformance.
- Replay tests:
  - deterministic rebuild from same offset basis,
  - duplicate/out-of-order tolerance under canonical result invariants,
  - EB/Archive mismatch anomaly fail-closed.
- Label leakage tests:
  - observed-time cutoff enforcement,
  - maturity/coverage gates.
- Integration tests:
  - OFS output admissibility for MF intake.
- Evidence logging in:
  - `docs/model_spec/platform/implementation_maps/offline_feature_plane.impl_actual.md`
  - `docs/logbook/<month>/<date>.md`

## Non-goals for v0
- No OFS participation in real-time decision serving.
- No direct writes to Label Store, Registry ACTIVE state, or Event Bus truth streams.
- No implicit "latest dataset/profile" discovery by scanning.

## Status (rolling)
- Phase 1 (`BuildIntent + dataset identity + contract lock`): complete (implemented and validated on `2026-02-10`).
- Phase 2 (`run control + idempotent run ledger`): complete (implemented and validated on `2026-02-10`).
- Phase 3 (`pin and provenance resolver`): complete (implemented and validated on `2026-02-10`).
- Phase 4 (`replay basis resolver + completeness receipts`): complete (implemented and validated on `2026-02-10`).
- Phase 5 (`label as-of resolver and coverage gate`): complete (implemented and validated on `2026-02-10`).
- Phase 6 (`deterministic feature reconstruction and dataset drafting`): complete (implemented and validated on `2026-02-10`).
- Phase 7 (`artifact publication + DatasetManifest authority`): complete (implemented and validated on `2026-02-10`).
- Next action: begin Phase 8 implementation (`run/operate onboarding`).
