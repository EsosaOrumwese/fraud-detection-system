# Dev Substrate Deep Plan - M11 (P14 MF_EVAL_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-02-26_

## 0) Purpose
M11 closes `P14 MF_EVAL_COMMITTED` with deterministic, reproducible model-factory train/eval proof. A green M11 means:
1. Inputs are immutable and anchored to M10 closure artifacts.
2. Train/eval execution is managed-only and reproducible.
3. Evaluation gates (performance, stability, leakage) are explicit and fail-closed.
4. MLflow lineage and provenance are complete and auditable.
5. Candidate bundle publication + safe-disable/rollback evidence is complete.
6. Deterministic `P14` verdict and `M12` handoff are emitted.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M10.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Entry Contract
M11 cannot execute unless all are true:
1. `M10` status is `DONE` in `platform.build_plan.md`.
2. `m10j_closure_sync_20260226T164304Z` artifacts are readable from durable evidence.
3. M10 closure verdict is `ADVANCE_TO_M11` and `next_gate=M11_READY`.
4. No active unresolved `M10-B*` blocker remains in master/deep plans.

Entry evidence anchors:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10j_closure_sync_20260226T164304Z/m10_execution_summary.json`
2. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10j_closure_sync_20260226T164304Z/m10j_execution_summary.json`
3. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10i_p13_gate_rollup_20260226T162737Z/m11_handoff_pack.json`

## 3) Global M11 Guardrails
1. No local runtime compute for authoritative M11 closure.
2. Managed-first execution only (GitHub Actions + pinned managed resources).
3. Fail-closed on any unresolved required handle.
4. Fail-closed on any missing or inconsistent upstream artifact.
5. Cost-control law is binding:
- pre-compute budget envelope before heavy run lane,
- closure cost-outcome receipt at M11.J,
- no advance on unattributed spend.
6. Performance-first law is binding:
- explicit runtime budgets per sub-phase,
- no silent long-run acceptance without analysis and remediation trail.

## 3.1) Non-Gate Acceptance Objectives (Mandatory)
M11 is not complete on gate-chain pass alone. All items below are required:
1. Model utility acceptance:
- candidate must outperform or match pinned baseline/champion thresholds from authority handles,
- metric deltas must be explicitly reported, not inferred.
2. Reproducibility acceptance:
- bounded rerun with identical pinned inputs/config must produce stable evaluation posture within pinned tolerance.
3. Operational-readiness acceptance:
- candidate bundle must include runtime-operable metadata (model/package id, feature contract ref, lineage refs, rollback pointers).
4. Auditability acceptance:
- MLflow lineage and provenance must be complete enough for deterministic reconstruction of the train/eval run.
5. Decision quality acceptance:
- promotion-readiness rationale must be explicit (why this candidate is safe/useful), not just `PASS` by chain mechanics.

## 4) Deliverables and Artifact Contract
M11 artifacts (local run folder + durable mirror) must include:
1. `m11a_handle_closure_snapshot.json`
2. `m11b_sagemaker_readiness_snapshot.json`
3. `m11c_input_immutability_snapshot.json`
4. `m11d_train_eval_execution_snapshot.json`
5. `m11e_eval_gate_snapshot.json`
6. `m11f_mlflow_lineage_snapshot.json`
7. `m11g_candidate_bundle_snapshot.json`
8. `m11h_safe_disable_rollback_snapshot.json`
9. `m11i_p14_gate_verdict.json`
10. `m12_handoff_pack.json`
11. `m11_phase_budget_envelope.json`
12. `m11_phase_cost_outcome_receipt.json`
13. `m11_execution_summary.json`
14. `m11_blocker_register.json`
15. `m11_eval_vs_baseline_report.json`
16. `m11_reproducibility_check.json`
17. `m11_model_operability_report.json`

Run folder convention:
1. `runs/dev_substrate/dev_full/m11/<execution_id>/...`
2. Durable mirror: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<execution_id>/...`

## 5) Execution Order and Gate Chain
| Sub-phase | Phase gate objective | Entry gate | PASS next gate | Primary blockers |
| --- | --- | --- | --- | --- |
| M11.A | authority + handles closure | M10 done + M11 ready | M11.B_READY | M11-B1 |
| M11.B | SageMaker runtime readiness | M11.A pass | M11.C_READY | M11-B2 |
| M11.C | immutable input binding | M11.B pass | M11.D_READY | M11-B3 |
| M11.D | train/eval execution | M11.C pass + budget envelope present | M11.E_READY | M11-B4 |
| M11.E | eval gate adjudication | M11.D pass | M11.F_READY | M11-B5 |
| M11.F | MLflow lineage closure | M11.E pass | M11.G_READY | M11-B6 |
| M11.G | candidate bundle publication | M11.F pass | M11.H_READY | M11-B7 |
| M11.H | safe-disable/rollback closure | M11.G pass | M11.I_READY | M11-B8 |
| M11.I | P14 rollup + verdict + handoff | M11.H pass | M11.J_READY | M11-B9, M11-B10 |
| M11.J | cost-outcome + closure sync | M11.I pass | M12_READY | M11-B11, M11-B12 |

## 6) Sub-Phase Execution Contracts

### M11.A - Authority + Handle Closure
Goal:
1. Resolve all required P14 handles and fail-closed on unresolved items.

Required handles:
1. `SM_TRAINING_JOB_NAME_PREFIX`
2. `SM_BATCH_TRANSFORM_JOB_NAME_PREFIX`
3. `SM_MODEL_PACKAGE_GROUP_NAME`
4. `SM_ENDPOINT_NAME`
5. `MF_EVAL_REPORT_PATH_PATTERN`
6. `MF_CANDIDATE_BUNDLE_PATH_PATTERN`
7. `MF_LEAKAGE_PROVENANCE_CHECK_PATH_PATTERN`
8. `MLFLOW_HOSTING_MODE`
9. `MLFLOW_EXPERIMENT_PATH`
10. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
11. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

Entry conditions:
1. `M10` closure summaries are readable and pass posture:
- `m10_execution_summary.json` with `overall_pass=true`,
- `m10j_execution_summary.json` with `verdict=ADVANCE_TO_M11` and `next_gate=M11_READY`.
2. M10 handoff artifact is readable:
- `m11_handoff_pack.json` from `M10.I`.
3. Active run scope is single-valued from M10 closure:
- one `platform_run_id`,
- one `scenario_run_id`.
4. Handle registry path is readable and parseable:
- `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.

Execution notes:
1. Produce explicit resolved/unresolved matrix.
2. Map unresolved required handles to `M11-B1`.
3. Emit `m11a_handle_closure_snapshot.json` and `m11_blocker_register.json`.
4. Emit `m11a_execution_summary.json` with deterministic next gate.

Deterministic verification algorithm (M11.A):
1. load and validate M10 entry artifacts from durable run-control surface.
2. fail closed unless M10 closure posture is:
- `overall_pass=true`,
- `verdict=ADVANCE_TO_M11`,
- `next_gate=M11_READY`.
3. resolve required handle set in fixed order (`1..11` above).
4. classify each handle deterministically:
- `resolved`,
- `missing`,
- `placeholder`,
- `wildcard`.
5. project blockers:
- any `missing/placeholder/wildcard` required handle -> `M11-B1`.
6. emit deterministic artifacts:
- `m11a_handle_closure_snapshot.json`,
- `m11_blocker_register.json`,
- `m11a_execution_summary.json`.
7. publish local + durable artifacts with readback parity.
8. emit deterministic next gate:
- `M11.B_READY` when blocker count is `0`,
- otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. Target <= 5 minutes.

Managed execution binding:
1. Authoritative runner: `.github/workflows/dev_full_m11_a_managed.yml`.
2. Required dispatch inputs:
- `aws_region`
- `aws_role_to_assume`
- `evidence_bucket`
- `upstream_m10j_execution`
- `upstream_m10i_execution`
3. Optional dispatch input:
- `m11a_execution_id` (fixed execution id override for deterministic rerun).
4. Required upstream evidence keys:
- `evidence/dev_full/run_control/{upstream_m10j_execution}/m10_execution_summary.json`
- `evidence/dev_full/run_control/{upstream_m10j_execution}/m10j_execution_summary.json`
- `evidence/dev_full/run_control/{upstream_m10i_execution}/m11_handoff_pack.json`
5. Required M11.A publication keys:
- `evidence/dev_full/run_control/{m11a_execution_id}/m11a_handle_closure_snapshot.json`
- `evidence/dev_full/run_control/{m11a_execution_id}/m11_blocker_register.json`
- `evidence/dev_full/run_control/{m11a_execution_id}/m11a_execution_summary.json`

DoD:
- [x] all required handles resolved or explicitly blocker-marked.
- [x] `m11a_handle_closure_snapshot.json` published local + durable.
- [x] `m11a_execution_summary.json` published local + durable.
- [x] `M11.B_READY` asserted on blocker-free pass.

Current runtime blocker:
1. `M11A-B0`: managed workflow dispatch prerequisite not met.
- observed condition: GitHub returns `workflow not found on default branch` for `.github/workflows/dev_full_m11_a_managed.yml`,
- clearance action: publish workflow file to default branch, then rerun `M11.A`.
- resolution status (2026-02-26): cleared.
  - workflow-only promotion PR merged: `https://github.com/EsosaOrumwese/fraud-detection-system/pull/58`,
  - authoritative run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22454486097`,
  - execution id: `m11a_handle_closure_20260226T175701Z`,
  - verdict: `ADVANCE_TO_M11_B`,
  - next gate: `M11.B_READY`,
  - blocker count: `0`.

### M11.B - SageMaker Runtime Readiness
Goal:
1. Prove train/eval runtime identity and APIs are ready.

Execution notes:
1. Validate IAM role assumptions and execution permissions.
2. Validate required runtime surfaces for training/evaluation operations.
3. Emit `m11b_sagemaker_readiness_snapshot.json`.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] readiness checks pass with no open `M11-B2`.
- [ ] snapshot published local + durable.
- [ ] `M11.C_READY` asserted.

### M11.C - Immutable Input Binding
Goal:
1. Bind M11 execution to immutable M10 output contract.

Execution notes:
1. Resolve M10 manifest/fingerprint references.
2. Validate immutability contract (fingerprint + run-scoped identity).
3. Emit `m11c_input_immutability_snapshot.json`.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] immutable binding checks pass with no open `M11-B3`.
- [ ] snapshot published local + durable.
- [ ] `M11.D_READY` asserted.

### M11.D - Train/Eval Execution
Goal:
1. Run managed train/eval jobs with deterministic inputs and pinned config.

Execution notes:
1. Emit `m11_phase_budget_envelope.json` before job launch.
2. Execute training and evaluation jobs.
3. Capture job refs/status/runtime and emit `m11d_train_eval_execution_snapshot.json`.
4. Mark failures as `M11-B4` with explicit surface details.

Runtime budget:
1. Target <= 45 minutes.
2. Hard alert if > 60 minutes without explicit approved waiver.

DoD:
- [ ] train/eval jobs complete successfully.
- [ ] execution snapshot published local + durable.
- [ ] budget envelope published.
- [ ] `M11.E_READY` asserted.

### M11.E - Eval Gate Adjudication
Goal:
1. Adjudicate metric/performance/stability/leakage gates deterministically.

Execution notes:
1. Evaluate thresholds from pinned policy surfaces.
2. Fail-closed on any gate miss (`M11-B5`).
3. Emit explicit baseline/champion comparison artifact (`m11_eval_vs_baseline_report.json`).
4. Emit `m11e_eval_gate_snapshot.json`.

Runtime budget:
1. Target <= 10 minutes.

DoD:
- [ ] all eval gates pass.
- [ ] baseline/champion comparison report is published and meets pinned thresholds.
- [ ] snapshot published local + durable.
- [ ] `M11.F_READY` asserted.

### M11.F - MLflow Lineage + Provenance Closure
Goal:
1. Prove full lineage from immutable input through evaluation outputs.

Execution notes:
1. Validate experiment/run identifiers.
2. Validate provenance fields include run pins and dataset fingerprint references.
3. Emit `m11f_mlflow_lineage_snapshot.json`.

Runtime budget:
1. Target <= 10 minutes.

DoD:
- [ ] lineage/provenance checks pass with no open `M11-B6`.
- [ ] snapshot published local + durable.
- [ ] `M11.G_READY` asserted.

### M11.G - Candidate Bundle + Provenance Publication
Goal:
1. Publish candidate bundle package and provenance metadata.

Execution notes:
1. Publish candidate bundle to pinned artifact surface.
2. Validate required provenance keys.
3. Emit model operability report (`m11_model_operability_report.json`) proving the bundle is runnable by downstream promotion/runtime surfaces.
4. Emit `m11g_candidate_bundle_snapshot.json`.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] bundle publish + provenance checks pass.
- [ ] operability report is published and marked pass.
- [ ] snapshot published local + durable.
- [ ] `M11.H_READY` asserted.

### M11.H - Safe-Disable/Rollback Closure
Goal:
1. Prove safe-disable and rollback posture for the candidate bundle.

Execution notes:
1. Emit rollback path references and safe-disable controls.
2. Validate rollback artifact readability.
3. Execute bounded reproducibility check and emit `m11_reproducibility_check.json`.
4. Emit `m11h_safe_disable_rollback_snapshot.json`.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] safe-disable/rollback closure passes with no open `M11-B8`.
- [ ] reproducibility check report is published and pass posture.
- [ ] snapshot published local + durable.
- [ ] `M11.I_READY` asserted.

### M11.I - P14 Gate Rollup + M12 Handoff
Goal:
1. Roll up M11.A..H and emit deterministic P14 verdict.

Execution notes:
1. Construct deterministic gate matrix across M11.A..H.
2. Emit `m11i_p14_gate_verdict.json`.
3. Emit `m12_handoff_pack.json`.
4. Fail-closed with `M11-B9` or `M11-B10` on mismatch/publication failure.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] verdict is `ADVANCE_TO_P15`.
- [ ] `next_gate=M12_READY`.
- [ ] handoff pack published local + durable.
- [ ] `M11.J_READY` asserted.

### M11.J - Cost-Outcome + Closure Sync
Goal:
1. Close M11 with cost/outcome proof and summary parity.

Execution notes:
1. Emit `m11_phase_cost_outcome_receipt.json`.
2. Emit `m11_execution_summary.json` + `m11_blocker_register.json`.
3. Validate artifact parity (required vs published).
4. Fail-closed on `M11-B11` or `M11-B12`.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [ ] cost-outcome receipt published local + durable.
- [ ] summary parity passes (`all_required_available=true`).
- [ ] no active blockers remain.
- [ ] phase closure verdict ready for M12 entry.

## 7) Blocker Taxonomy (Fail-Closed)
1. `M11-B1`: authority/handle closure failure.
2. `M11-B2`: SageMaker readiness failure.
3. `M11-B3`: input immutability failure.
4. `M11-B4`: train/eval execution failure.
5. `M11-B5`: eval gate failure.
6. `M11-B6`: MLflow lineage/provenance failure.
7. `M11-B7`: candidate bundle publication failure.
8. `M11-B8`: safe-disable/rollback failure.
9. `M11-B9`: P14 rollup/verdict inconsistency.
10. `M11-B10`: handoff publication failure.
11. `M11-B11`: cost-outcome closure failure.
12. `M11-B12`: summary/evidence parity failure.
13. `M11-B13`: non-gate acceptance failure (utility/reproducibility/operability/auditability).

## 8) Completion Checklist
- [x] `M11.A` complete
- [ ] `M11.B` complete
- [ ] `M11.C` complete
- [ ] `M11.D` complete
- [ ] `M11.E` complete
- [ ] `M11.F` complete
- [ ] `M11.G` complete
- [ ] `M11.H` complete
- [ ] `M11.I` complete
- [ ] `M11.J` complete
- [ ] no unresolved `M11-B*` blocker remains
- [ ] all M11 artifacts published local + durable
- [ ] non-gate acceptance artifacts (`eval_vs_baseline`, `reproducibility`, `model_operability`) are pass posture

## 9) Planning Status
1. M11 planning is expanded to execution-grade depth.
2. `M11.A` is complete and green on managed lane.
3. Next actionable lane is `M11.B` (SageMaker runtime readiness).
