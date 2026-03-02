# Dev Substrate Deep Plan - M11 (P14 MF_EVAL_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-02-27_

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
3. `m11b_blocker_register.json`
4. `m11b_execution_summary.json`
5. `m11c_input_immutability_snapshot.json`
6. `m11d_train_eval_execution_snapshot.json`
7. `m11e_eval_gate_snapshot.json`
8. `m11f_mlflow_lineage_snapshot.json`
9. `m11g_candidate_bundle_snapshot.json`
10. `m11h_safe_disable_rollback_snapshot.json`
11. `m11i_p14_gate_verdict.json`
12. `m12_handoff_pack.json`
13. `m11_phase_budget_envelope.json`
14. `m11_phase_cost_outcome_receipt.json`
15. `m11_execution_summary.json`
16. `m11_blocker_register.json`
17. `m11_eval_vs_baseline_report.json`
18. `m11_reproducibility_check.json`
19. `m11_model_operability_report.json`

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

Required handles:
1. `ROLE_SAGEMAKER_EXECUTION`
2. `SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH`
3. `SSM_MLFLOW_TRACKING_URI_PATH`
4. `SM_TRAINING_JOB_NAME_PREFIX`
5. `SM_BATCH_TRANSFORM_JOB_NAME_PREFIX`
6. `SM_MODEL_PACKAGE_GROUP_NAME`
7. `SM_ENDPOINT_NAME`
8. `SM_ENDPOINT_COUNT_V0`
9. `SM_SERVING_MODE`

Entry conditions:
1. `M11.A` summary is readable and pass posture:
- `m11a_execution_summary.json` with `overall_pass=true`,
- `next_gate=M11.B_READY`.
2. `M11.A` run-scope is present and single-valued:
- one `platform_run_id`,
- one `scenario_run_id`.
3. Handle registry path is readable and parseable:
- `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.

Execution notes:
1. Validate IAM role existence and trust for `sagemaker.amazonaws.com`.
2. Validate SSM parameter surfaces:
- role ARN path readability and value parity with `ROLE_SAGEMAKER_EXECUTION`,
- MLflow tracking URI path readability.
3. Validate SageMaker control-plane reachability (`list_training_jobs`, `list_model_package_groups`).
4. Ensure package-group readiness:
- `describe_model_package_group` for `SM_MODEL_PACKAGE_GROUP_NAME`,
- create group if absent when permissions allow,
- if package-group describe/create is blocked by access boundary but control-plane probes are green, record advisory and defer package-group materialization to `M11.G` (bundle publication owner lane).
5. Emit artifacts:
- `m11b_sagemaker_readiness_snapshot.json`,
- `m11b_blocker_register.json`,
- `m11b_execution_summary.json`.

Deterministic verification algorithm (M11.B):
1. load `M11.A` summary from durable run-control and fail closed unless pass + next gate matches.
2. resolve required handle set in fixed order (`1..9` above).
3. classify handles (`resolved|missing|placeholder|wildcard`) and map unresolved to `M11-B2`.
4. read SSM role-arn parameter and compare value to `ROLE_SAGEMAKER_EXECUTION`.
5. read SSM MLflow URI parameter and fail closed on empty/placeholder value.
6. verify IAM role exists and trust includes `sagemaker.amazonaws.com`.
7. execute control-plane probes:
- `list_training_jobs(MaxResults=1)`,
- `list_model_package_groups(MaxResults=1)`.
8. describe-or-create model package group for pinned handle name.
9. treat `AccessDenied` on package-group describe/create as non-gating advisory for M11.B and carry the deferred action into M11.G.
10. emit deterministic artifacts and publish local + durable with readback parity.
11. emit deterministic next gate:
- `M11.C_READY` when blocker count is `0`,
- otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. Target <= 8 minutes.

Managed execution binding:
1. Authoritative runner: `.github/workflows/dev_full_m11_b_managed.yml`.
2. Required dispatch inputs:
- `aws_region`
- `aws_role_to_assume`
- `evidence_bucket`
- `upstream_m11a_execution`
3. Optional dispatch input:
- `m11b_execution_id` (fixed execution id override for deterministic rerun).
4. Required upstream evidence key:
- `evidence/dev_full/run_control/{upstream_m11a_execution}/m11a_execution_summary.json`
5. Required M11.B publication keys:
- `evidence/dev_full/run_control/{m11b_execution_id}/m11b_sagemaker_readiness_snapshot.json`
- `evidence/dev_full/run_control/{m11b_execution_id}/m11b_blocker_register.json`
- `evidence/dev_full/run_control/{m11b_execution_id}/m11b_execution_summary.json`

DoD:
- [x] readiness checks pass with no open `M11-B2`.
- [x] snapshot published local + durable.
- [x] `M11.C_READY` asserted.

Closure snapshot (2026-02-26):
1. Authoritative run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22455349242`.
2. Execution id: `m11b_sagemaker_readiness_20260226T182038Z`.
3. Verdict: `ADVANCE_TO_M11_C`.
4. Next gate: `M11.C_READY`.
5. Blockers: `0`.
6. Advisory carried forward (non-blocking): package-group materialization access boundary deferred to `M11.G` owner lane.

### M11.C - Immutable Input Binding
Goal:
1. Bind M11 execution to immutable M10 output contract.

Handle carry-through surfaces (advisory in M11.C):
1. `S3_EVIDENCE_BUCKET`
2. `S3_RUN_CONTROL_ROOT_PATTERN`

Entry conditions:
1. `M11.B` summary is readable and pass posture:
- `m11b_execution_summary.json` with `overall_pass=true`,
- `next_gate=M11.C_READY`.
2. `M11.B` run-scope is present and single-valued:
- one `platform_run_id`,
- one `scenario_run_id`.
3. Upstream chain surfaces are readable:
- `M11.A` summary using `upstream_refs.m11a_execution_id`,
- `M11.A` handle-closure snapshot using `artifact_keys.m11a_handle_closure_snapshot`,
- `M10.I` handoff pack using `M11.A` upstream refs,
- all required refs inside `m11_handoff_pack.required_refs`.

Execution notes:
1. Resolve upstream chain:
- `M11.B` summary -> `M11.A` execution id,
- `M11.A` summary -> `M10.I` execution id,
- `M10.I` handoff pack -> required immutable input refs.
2. Resolve and validate required immutable input refs in fixed order:
- `m10i_gate_verdict_ref`
- `m10g_manifest_ref`
- `m10g_fingerprint_ref`
- `m10g_time_bound_audit_ref`
- `m10h_rollback_recipe_ref`
- `m10h_rollback_drill_ref`
3. Enforce run-scope parity across all loaded artifacts:
- every artifact carrying run pins must match single-valued `platform_run_id` + `scenario_run_id`.
4. Resolve handle carry-through rows from `M11.A` snapshot for auditability; treat missing rows as advisory (non-gating) in this lane.
5. Recompute fingerprint digest deterministically from `required_fields_order` + `required_field_values` and compare to `fingerprint_sha256`.
6. Validate immutable contract coherence:
- `dataset_manifest.fingerprint_ref` equals resolved fingerprint ref,
- `dataset_manifest.time_bound_audit_ref` equals resolved time-bound ref,
- `dataset_manifest.status=COMMITTED`,
- `dataset_fingerprint.status=COMMITTED`,
- `time_bound_audit.overall_pass=true`,
- `m10i_gate_verdict.verdict=ADVANCE_TO_P14` and `next_gate=M11_READY`.
7. Emit artifacts:
- `m11c_input_immutability_snapshot.json`,
- `m11c_blocker_register.json`,
- `m11c_execution_summary.json`.

Deterministic verification algorithm (M11.C):
1. load `M11.B` summary from durable run-control and fail closed unless pass + next gate matches.
2. resolve upstream `M11.A` summary and validate run-scope parity with `M11.B`.
3. resolve upstream `M10.I` handoff pack and validate `m11_entry_ready=true`.
4. load `required_refs` in fixed order and fail closed on unreadable/invalid JSON.
5. enforce run-scope parity across resolved artifact surfaces.
6. build canonical fingerprint input string using ordered key list from `required_fields_order` and values from `required_field_values` with exact `key=value` + newline join.
7. compute `sha256(canonical_input)` and compare to `fingerprint_sha256`.
8. verify manifest/fingerprint/time-bound and gate-verdict coherence assertions.
9. emit deterministic artifacts and publish local + durable with readback parity.
10. emit deterministic next gate:
- `M11.D_READY` when blocker count is `0`,
- otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. Target <= 8 minutes.

Managed execution binding:
1. Authoritative runner: `.github/workflows/dev_full_m11_c_managed.yml`.
2. Required dispatch inputs:
- `aws_region`
- `aws_role_to_assume`
- `evidence_bucket`
- `upstream_m11b_execution`
3. Optional dispatch input:
- `m11c_execution_id` (fixed execution id override for deterministic rerun).
4. Required upstream evidence key:
- `evidence/dev_full/run_control/{upstream_m11b_execution}/m11b_execution_summary.json`
5. Required M11.C publication keys:
- `evidence/dev_full/run_control/{m11c_execution_id}/m11c_input_immutability_snapshot.json`
- `evidence/dev_full/run_control/{m11c_execution_id}/m11c_blocker_register.json`
- `evidence/dev_full/run_control/{m11c_execution_id}/m11c_execution_summary.json`
6. Dispatch blocker history (resolved):
- `M11C-B0` (workflow not visible on default branch / GitHub HTTP 404) resolved by workflow-only publication to `main` via PR `#62`.
- `M11C-B1` (repo-local handle registry path unreadable on `main`) resolved by sourcing handle carry-through from upstream `M11.A` snapshot via PR `#63`.
- `M11C-B2` (missing carry-through rows treated as blocking) resolved by converting carry-through rows to advisory in this lane via PR `#64`.

DoD:
- [x] immutable binding checks pass with no open `M11-B3`.
- [x] snapshot published local + durable.
- [x] `M11.D_READY` asserted.

Closure snapshot (2026-02-26):
1. Authoritative run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22457735414`.
2. Execution id: `m11c_input_immutability_20260226T192723Z`.
3. Verdict: `ADVANCE_TO_M11_D`.
4. Next gate: `M11.D_READY`.
5. Blockers: `0`.

### M11.D - Train/Eval Execution
Goal:
1. Run managed train/eval jobs with deterministic inputs and pinned config.

Required handles:
1. `SM_TRAINING_JOB_NAME_PREFIX`
2. `SM_BATCH_TRANSFORM_JOB_NAME_PREFIX`
3. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
4. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`
5. `MF_EVAL_REPORT_PATH_PATTERN`
6. `MF_CANDIDATE_BUNDLE_PATH_PATTERN`

Entry conditions:
1. `M11.C` summary is readable and pass posture:
- `m11c_execution_summary.json` with `overall_pass=true`,
- `next_gate=M11.D_READY`.
2. `M11.C` run-scope is present and single-valued:
- one `platform_run_id`,
- one `scenario_run_id`.
3. Upstream runtime readiness is readable and pass posture:
- `M11.B` summary + snapshot (`overall_pass=true`),
- resolved SageMaker execution role ARN is present.
4. Deterministic immutable refs from `M11.C` are readable:
- `m10g_manifest_ref`,
- `m10g_fingerprint_ref`,
- `m10g_time_bound_audit_ref`,
- `m10h_rollback_recipe_ref`.

Execution notes:
1. Emit `m11_phase_budget_envelope.json` before job launch.
2. Build deterministic train/validation/test payloads anchored to `M11.C` fingerprint digest (seeded, repeatable split).
3. Execute managed SageMaker training job.
4. Execute managed SageMaker batch-transform evaluation job.
5. Compute bounded evaluation metrics (accuracy/precision/recall) from transform outputs.
6. Capture job refs/status/runtime and emit:
- `m11d_train_eval_execution_snapshot.json`,
- `m11d_blocker_register.json`,
- `m11d_execution_summary.json`.
7. Mark failures as `M11-B4` with explicit surface details.

Deterministic verification algorithm (M11.D):
1. load `M11.C` summary from durable run-control and fail closed unless pass + next gate matches.
2. resolve upstream `M11.B` and `M11.A` artifacts and enforce run-scope parity.
3. resolve required handles from `M11.A` handle matrix and fail closed if unresolved.
4. derive deterministic dataset seed from `M11.C` fingerprint and generate bounded train/validation/test splits.
5. publish input payload refs under run-scoped evidence surface before training launch.
6. emit and publish `m11_phase_budget_envelope.json` prior to compute launch.
7. launch training job + poll to terminal state; fail closed on non-success.
8. launch batch-transform job + poll to terminal state; fail closed on non-success.
9. parse transform outputs and compute deterministic evaluation metrics.
10. emit deterministic artifacts and publish local + durable with readback parity.
11. emit deterministic next gate:
- `M11.E_READY` when blocker count is `0`,
- otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. Target <= 45 minutes.
2. Hard alert if > 60 minutes without explicit approved waiver.

Managed execution binding:
1. Authoritative runner: `.github/workflows/dev_full_m11_managed.yml` (single-runner lane for M11.D+; subphase input selects lane).
2. Required dispatch inputs:
- `aws_region`
- `aws_role_to_assume`
- `evidence_bucket`
- `m11_subphase=D`
- `upstream_m11c_execution`
3. Optional dispatch inputs:
- `m11d_execution_id` (fixed execution id override for deterministic rerun),
- `poll_timeout_minutes`,
- `poll_interval_seconds`.
4. Required upstream evidence key:
- `evidence/dev_full/run_control/{upstream_m11c_execution}/m11c_execution_summary.json`
5. Required M11.D publication keys:
- `evidence/dev_full/run_control/{m11d_execution_id}/m11_phase_budget_envelope.json`
- `evidence/dev_full/run_control/{m11d_execution_id}/m11d_train_eval_execution_snapshot.json`
- `evidence/dev_full/run_control/{m11d_execution_id}/m11d_blocker_register.json`
- `evidence/dev_full/run_control/{m11d_execution_id}/m11d_execution_summary.json`

DoD:
- [x] train/eval jobs complete successfully.
- [x] execution snapshot published local + durable.
- [x] budget envelope published.
- [x] `M11.E_READY` asserted.

Closure evidence:
1. Workflow run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22461137374`.
2. Execution id: `m11d_train_eval_execution_20260226T210509Z`.
3. Summary evidence:
- `evidence/dev_full/run_control/m11d_train_eval_execution_20260226T210509Z/m11d_execution_summary.json`,
- `overall_pass=true`, `blocker_count=0`, `next_gate=M11.E_READY`.
4. Residual advisory:
- `M11D-AD1` retained (transform quota `ml.m5.large` unavailable),
- eval mode stamped as `fallback_local_model_eval` in execution snapshot,
- lane remains green with explicit caveat recorded (no silent pass).

M11D-AD1 clearance contract (mandatory before M11 phase closure):
1. Current quota posture captured from AWS Service Quotas (`eu-west-2`):
- `ml.m5.large for transform job usage = 0` (hard blocker for `CreateTransformJob`).
- `ml.m5.large for endpoint usage = 4` (available).
- `ml.m5.large for training job usage = 0` (current run succeeded under existing lane mechanics; keep explicit watch).
2. Clearance objective:
- rerun `M11.D` with real managed transform path (`CreateTransformJob` succeeds),
- `eval_mode=managed_batch_transform`,
- advisory `M11D-AD1` absent from snapshot/advisories.
3. Primary remediation lane (authoritative):
- request quota increase for `ml.m5.large for transform job usage` (target >=2),
- rerun `M11.D` and require advisory-free evidence.
4. Continuity options while waiting (not advisory-clearance equivalents):
- Option A: pin alternate transform instance type with non-zero transform quota and rerun.
- Option B: temporary managed endpoint inference lane (`CreateEndpoint` + `InvokeEndpoint` + teardown) to avoid local fallback.
5. Hard rule:
- continuity options can keep progression work moving, but `M11D-AD1` remains open until authoritative managed-transform rerun passes.
6. Latest clearance execution state:
- strict rerun executed on workflow run `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22462948967`,
- execution id `m11d_train_eval_execution_20260226T215805Z`,
- `require_managed_transform=true`, `transform_instance_type=ml.c4.xlarge`,
- outcome: `overall_pass=false`, blocker `M11-B4` due `ResourceLimitExceeded` on transform quota still `0`,
- quota request currently `CASE_OPENED`: `be88a3fa50a141a4b67a79538a9cedd4kWCjEenD` (case `177214283200667`).
7. Advisory-clearance success state:
- strict rerun executed on workflow run `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22473966183`,
- execution id `m11d_train_eval_execution_20260227T052312Z`,
- `require_managed_transform=true`, `training_instance_type=ml.c5.xlarge`, `transform_instance_type=ml.c5.xlarge`,
- transform status `Completed`, `eval_mode=managed_batch_transform`,
- advisories `[]`, `overall_pass=true`, `blocker_count=0`, `next_gate=M11.E_READY`,
- `M11D-AD1` is cleared.

### M11.E - Eval Gate Adjudication
Goal:
1. Adjudicate metric/performance/stability/leakage gates deterministically.

Execution lanes (sequential, fail-closed):
1. `M11.E.A` gate-policy closure (decision-completeness precheck):
- verify required evaluation policy handles are pinned and readable from authoritative surfaces.
- required policy handles for this lane:
  - `MF_EVAL_ACCURACY_MIN`
  - `MF_EVAL_PRECISION_MIN`
  - `MF_EVAL_RECALL_MIN`
  - `MF_EVAL_BASELINE_DELTA_ACCURACY_MIN`
  - `MF_EVAL_BASELINE_DELTA_PRECISION_MIN`
  - `MF_EVAL_BASELINE_DELTA_RECALL_MIN`
  - `MF_EVAL_LEAKAGE_HARD_FAIL`
  - `MF_EVAL_STABILITY_MAX_DELTA_PCT`
- if any key is unresolved/missing, stop with `M11-B5` and emit unresolved policy list (no defaults/no assumptions).
2. `M11.E.B` evidence ingestion and integrity precheck:
- load `m11d_train_eval_execution_snapshot.json` and `m11d_execution_summary.json` from authoritative M11.D execution id,
- verify run pins (`platform_run_id`, execution id, code release refs) and artifact checksums,
- verify required artifacts exist: `eval_report`, leakage/provenance check, and baseline reference surface.
3. `M11.E.C` deterministic adjudication:
- compute gate verdicts in fixed order: compatibility -> leakage -> performance -> stability.
- leakage gate is hard fail (no waivers in M11.E).
- performance gate compares candidate metrics vs absolute minima and baseline/champion deltas.
- stability gate checks bounded variance against pinned tolerance.
4. `M11.E.D` publication and handoff:
- publish `m11_eval_vs_baseline_report.json` with explicit metric values, thresholds, deltas, and pass/fail by gate.
- publish `m11e_eval_gate_snapshot.json` with `overall_pass`, blocker list, and `next_gate` contract.
- assert `M11.F_READY` only when `overall_pass=true` and blocker count is `0`.

Blocker semantics (`M11-B5` subcodes):
1. `M11-B5.1`: gate-policy handles unresolved/missing.
2. `M11-B5.2`: authoritative M11.D evidence set incomplete or unreadable.
3. `M11-B5.3`: leakage gate fail.
4. `M11-B5.4`: metric/performance gate fail.
5. `M11-B5.5`: stability gate fail.
6. `M11-B5.6`: snapshot/report publication failure.

Runtime budget:
1. Target <= 10 minutes total.
2. `M11.E.A/B` (policy + evidence precheck) <= 3 minutes.
3. `M11.E.C/D` (adjudication + publication) <= 7 minutes.

DoD:
- [x] policy-handle closure completed with zero unresolved keys (or blocked fail-closed).
- [x] all eval gates pass (`compatibility`, `leakage`, `performance`, `stability`).
- [x] baseline/champion comparison report is published and meets pinned thresholds.
- [x] snapshot + blocker register published local + durable.
- [x] `M11.F_READY` asserted.

Closure evidence:
1. Managed run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22475130190`
2. Execution id: `m11e_eval_gate_20260227T061316Z`
3. Summary: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11e_eval_gate_20260227T061316Z/m11e_execution_summary.json`
4. Snapshot: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11e_eval_gate_20260227T061316Z/m11e_eval_gate_snapshot.json`
5. Blockers: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11e_eval_gate_20260227T061316Z/m11e_blocker_register.json` (`blocker_count=0`)
6. Baseline comparison: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11e_eval_gate_20260227T061316Z/m11_eval_vs_baseline_report.json`
7. Leakage provenance check: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mf/leakage_provenance_check.json`

### M11.F - MLflow Lineage + Provenance Closure
Goal:
1. Prove full lineage from immutable input through evaluation outputs.

Execution lanes (sequential, fail-closed):
1. `M11.F.A` lineage-policy and handle closure:
- verify required handles are pinned/readable:
  - `MLFLOW_HOSTING_MODE`,
  - `MLFLOW_EXPERIMENT_PATH`,
  - `MLFLOW_MODEL_NAME`,
  - `SSM_MLFLOW_TRACKING_URI_PATH`,
  - `SSM_DATABRICKS_WORKSPACE_URL_PATH`,
  - `SSM_DATABRICKS_TOKEN_PATH`.
- fail closed on missing/placeholder values.
- strict conformance rule (no runtime fallback allowed):
  - `MLFLOW_EXPERIMENT_PATH` must resolve as exact canonical path `/Shared/fraud-platform/dev_full/mlflow_exp_v0`.
2. `M11.F.B` upstream evidence integrity gate:
- load authoritative M11.E summary + snapshot and require pass posture (`next_gate=M11.F_READY`),
- load referenced M11.D summary/snapshot and eval/leakage artifacts,
- verify run-scope consistency across M11.D -> M11.E evidence chain.
3. `M11.F.C` managed MLflow lineage commit:
- resolve tracking URI from SSM handle,
- open/create experiment by pinned experiment path,
- create managed run and log:
  - run pins (`platform_run_id`, `scenario_run_id`, execution refs),
  - metric set from M11.D/M11.E surfaces,
  - provenance refs including `m10g_fingerprint_ref` and leakage evidence refs.
4. `M11.F.D` lineage closure publication:
- publish `m11f_mlflow_lineage_snapshot.json` with experiment/run identifiers, source refs, and closure checks,
- publish `m11f_blocker_register.json` + `m11f_execution_summary.json`,
- assert `M11.G_READY` only with `overall_pass=true` and blocker count `0`.

Blocker semantics (`M11-B6` subcodes):
1. `M11-B6.1`: handle closure failure.
2. `M11-B6.2`: upstream evidence unreadable/inconsistent.
3. `M11-B6.3`: tracking URI or secret resolution failure.
4. `M11-B6.4`: managed MLflow API commit failure.
5. `M11-B6.5`: provenance/run-pin mismatch in lineage graph.
6. `M11-B6.6`: snapshot/summary publication failure.

Runtime budget:
1. Target <= 10 minutes total.
2. `M11.F.A/B` prechecks <= 3 minutes.
3. `M11.F.C/D` managed commit + publication <= 7 minutes.

DoD:
- [x] lineage/provenance checks pass with no open `M11-B6`.
- [x] managed MLflow experiment/run identifiers are committed and recorded.
- [x] snapshot + blocker register + execution summary published local + durable.
- [x] `M11.G_READY` asserted.

Closure evidence:
1. Managed run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22475770850`
2. Execution id: `m11f_mlflow_lineage_20260227T063855Z`
3. Summary: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11f_mlflow_lineage_20260227T063855Z/m11f_execution_summary.json`
4. Snapshot: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11f_mlflow_lineage_20260227T063855Z/m11f_mlflow_lineage_snapshot.json`
5. Blockers: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11f_mlflow_lineage_20260227T063855Z/m11f_blocker_register.json` (`blocker_count=0`)
6. MLflow proof:
   - experiment path used: `/Shared/fraud-platform/dev_full/mlflow_exp_v0`,
   - experiment id: `2974219164213255`,
   - run id: `f8f23e9286744e4188992d5d929d477f`,
   - run status: `FINISHED`.

Strict revalidation status (2026-02-27):
1. Strict no-fallback workflow patch applied and dispatched:
   - run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22477445213`,
   - execution id: `m11f_mlflow_lineage_20260227T074421Z`.
2. Result failed closed:
   - `overall_pass=false`,
   - blocker: `M11-B6.4` (`Managed MLflow lineage commit failed`),
   - `api_error=RuntimeError:experiment_id_missing`,
   - run used stale remote handle value `MLFLOW_EXPERIMENT_PATH=/Shared/fraud-platform/dev_full`.
3. Required remediation before declaring M11.F green:
   - publish canonical handle pin in registry (`MLFLOW_EXPERIMENT_PATH=/Shared/fraud-platform/dev_full/mlflow_exp_v0`) to remote branch,
   - rerun M11.F strict lane and require `next_gate=M11.G_READY`.
4. Remediation executed and closure achieved:
   - canonical handle pin committed/pushed in `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`,
   - strict rerun: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22477775337`,
   - execution id: `m11f_mlflow_lineage_20260227T075634Z`,
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M11.G_READY`, `verdict=ADVANCE_TO_M11_G`,
   - MLflow proof:
     - experiment path: `/Shared/fraud-platform/dev_full/mlflow_exp_v0`,
     - experiment id: `2974219164213255`,
     - run id: `446edf03415548d0944b689e03168795`,
     - run status: `FINISHED`.

### M11.G - Candidate Bundle + Provenance Publication
Goal:
1. Publish candidate bundle package and provenance metadata.

Execution lanes (sequential, fail-closed):
1. `M11.G.A` handle + entry closure:
- required handles:
  - `MF_CANDIDATE_BUNDLE_PATH_PATTERN`,
  - `MF_EVAL_REPORT_PATH_PATTERN`,
  - `MF_LEAKAGE_PROVENANCE_CHECK_PATH_PATTERN`,
  - `SM_MODEL_PACKAGE_GROUP_NAME`,
  - `SM_ENDPOINT_NAME`,
  - `SM_SERVING_MODE`,
  - `MLFLOW_MODEL_NAME`.
- entry evidence must be strict M11.F pass:
  - `overall_pass=true`,
  - `next_gate=M11.G_READY`,
  - `blocker_count=0`.
2. `M11.G.B` upstream evidence integrity:
- load M11.F summary/snapshot and resolve:
  - `platform_run_id`, `scenario_run_id`, `m11d_execution_id`, `m11e_execution_id`,
  - MLflow lineage refs (`experiment_id`, `run_id`, `run_status`),
  - provenance refs (`m10g_fingerprint_ref`, eval/leakage artifacts).
- load M11.D + M11.E snapshots and require gate continuity:
  - M11.D `next_gate=M11.E_READY`,
  - M11.E `next_gate=M11.F_READY`.
3. `M11.G.C` candidate bundle publication:
- construct deterministic `bundle_id` from run-scope + upstream execution refs,
- build candidate bundle payload with:
  - model artifact pointers,
  - train/transform refs,
  - metrics + gate refs,
  - lineage + rollback pointers,
- publish to `MF_CANDIDATE_BUNDLE_PATH_PATTERN`.
4. `M11.G.D` model operability + package-group closure:
- verify model artifact readability at source URI,
- verify train/transform completion posture,
- materialize/resolve `SM_MODEL_PACKAGE_GROUP_NAME` (describe/create),
- verify serving handles (`SM_ENDPOINT_NAME`, `SM_SERVING_MODE`) are pinned,
- emit `m11_model_operability_report.json`.
5. `M11.G.E` run-control publication:
- emit `m11g_candidate_bundle_snapshot.json`,
- emit `m11g_blocker_register.json`,
- emit `m11g_execution_summary.json`,
- assert `M11.H_READY` only when `overall_pass=true` and blocker count `0`.

Blocker semantics (`M11-B7` subcodes):
1. `M11-B7.1`: handle closure unresolved / unresolved path tokens.
2. `M11-B7.2`: upstream evidence unreadable or gate-chain inconsistent.
3. `M11-B7.3`: candidate bundle publication failure.
4. `M11-B7.4`: operability/package-group checks failed.
5. `M11-B7.5`: run-control artifact publication failure.

Runtime budget:
1. Target <= 8 minutes.
2. `M11.G.A/B` <= 3 minutes.
3. `M11.G.C/D/E` <= 5 minutes.

DoD:
- [x] bundle publish + provenance checks pass.
- [x] operability report is published and marked pass.
- [x] snapshot published local + durable.
- [x] `M11.H_READY` asserted.

Closure evidence:
1. Managed run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22478216340`
2. Execution id: `m11g_candidate_bundle_20260227T081200Z`
3. Summary: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11g_candidate_bundle_20260227T081200Z/m11g_execution_summary.json`
4. Snapshot: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11g_candidate_bundle_20260227T081200Z/m11g_candidate_bundle_snapshot.json`
5. Operability report: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11g_candidate_bundle_20260227T081200Z/m11_model_operability_report.json`
6. Blockers: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11g_candidate_bundle_20260227T081200Z/m11g_blocker_register.json` (`blocker_count=0`)
7. Candidate bundle artifact:
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mf/candidate_bundle.json`
8. Key closure proof:
   - `overall_pass=true`,
   - `next_gate=M11.H_READY`,
   - package group materialized: `fraud-platform-dev-full-models` (`Completed`).

### M11.H - Safe-Disable/Rollback Closure
Goal:
1. Prove safe-disable and rollback posture for the candidate bundle.

Execution lanes (sequential, fail-closed):
1. `M11.H.A` handle + entry closure:
- required handles:
  - `MPR_ROLLBACK_DRILL_PATH_PATTERN`,
  - `MF_CANDIDATE_BUNDLE_PATH_PATTERN`,
  - `SM_ENDPOINT_NAME`,
  - `SM_SERVING_MODE`.
- entry evidence must be M11.G pass:
  - `overall_pass=true`,
  - `next_gate=M11.H_READY`,
  - `blocker_count=0`.
2. `M11.H.B` upstream integrity + rollback refs:
- load M11.G summary/snapshot + operability report and require pass posture,
- resolve candidate bundle key and verify candidate artifact readability,
- verify rollback refs readable:
  - `evidence/runs/{platform_run_id}/learning/ofs/rollback_recipe.json`,
  - `evidence/runs/{platform_run_id}/learning/ofs/rollback_drill_report.json`.
3. `M11.H.C` bounded reproducibility check:
- read candidate bundle twice and compare deterministic SHA256 hash,
- verify run-scope and lineage refs remain stable/non-empty,
- emit `m11_reproducibility_check.json` with explicit pass/fail checks.
4. `M11.H.D` safe-disable/rollback publication:
- publish run-scoped rollback drill artifact to `MPR_ROLLBACK_DRILL_PATH_PATTERN`,
- publish `m11h_safe_disable_rollback_snapshot.json` with safe-disable controls and source refs.
5. `M11.H.E` run-control closure:
- publish `m11h_blocker_register.json` + `m11h_execution_summary.json`,
- assert `M11.I_READY` only with `overall_pass=true` and blocker count `0`.

Blocker semantics (`M11-B8` subcodes):
1. `M11-B8.1`: handle closure unresolved.
2. `M11-B8.2`: M11.G upstream evidence unreadable/inconsistent.
3. `M11-B8.3`: rollback reference/readability failure.
4. `M11-B8.4`: reproducibility check failed.
5. `M11-B8.5`: rollback/run-control artifact publication failure.

Runtime budget:
1. Target <= 8 minutes.
2. `M11.H.A/B` <= 3 minutes.
3. `M11.H.C/D/E` <= 5 minutes.

DoD:
- [x] safe-disable/rollback closure passes with no open `M11-B8`.
- [x] reproducibility check report is published and pass posture.
- [x] snapshot published local + durable.
- [x] `M11.I_READY` asserted.

Closure evidence:
1. Managed run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22479412631`
2. Execution id: `m11h_safe_disable_rollback_20260227T085223Z`
3. Summary: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11h_safe_disable_rollback_20260227T085223Z/m11h_execution_summary.json`
4. Snapshot: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11h_safe_disable_rollback_20260227T085223Z/m11h_safe_disable_rollback_snapshot.json`
5. Blockers: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11h_safe_disable_rollback_20260227T085223Z/m11h_blocker_register.json` (`blocker_count=0`)
6. Reproducibility report:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11h_safe_disable_rollback_20260227T085223Z/m11_reproducibility_check.json` (`overall_pass=true`)
7. Run-scoped rollback publication:
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mpr/rollback_drill_report.json`
8. Key closure proof:
   - `overall_pass=true`,
   - `next_gate=M11.I_READY`,
   - `verdict=ADVANCE_TO_M11_I`.

### M11.I - P14 Gate Rollup + M12 Handoff
Goal:
1. Roll up M11.A..H and emit deterministic P14 verdict.

Execution lanes (sequential, fail-closed):
1. `M11.I.A` entry + chain resolution:
- read `M11.H` summary from durable run-control using authoritative upstream execution id,
- resolve chain ids deterministically from summary refs:
  - `H -> G -> (F,E,D) -> (C,B,A)`,
- reject empty or inconsistent chain refs (`M11-B9`).
2. `M11.I.B` gate matrix rollup:
- load `m11[a-h]_execution_summary.json` for resolved ids,
- require for each row:
  - `overall_pass=true`,
  - `blocker_count=0`,
  - expected `next_gate` exact match:
    - `A:M11.B_READY`, `B:M11.C_READY`, `C:M11.D_READY`,
    - `D:M11.E_READY`, `E:M11.F_READY`, `F:M11.G_READY`,
    - `G:M11.H_READY`, `H:M11.I_READY`,
- require run-scope equality (`platform_run_id`, `scenario_run_id`) across all rows.
3. `M11.I.C` verdict + handoff publication:
- emit `m11i_p14_gate_verdict.json` with deterministic matrix and verdict,
- emit `m12_handoff_pack.json` with entry gate (`ADVANCE_TO_P15`, `M12_READY`) and required refs for M12 entry.
4. `M11.I.D` run-control closure:
- emit `m11i_blocker_register.json` + `m11i_execution_summary.json`,
- assert `M11.J_READY` only when `overall_pass=true` and blocker count `0`.

Blocker semantics:
1. `M11-B9`: rollup/verdict inconsistency (entry/chain/gate/run-scope mismatch).
2. `M11-B10`: publication failure (verdict/handoff/run-control artifacts).

Runtime budget:
1. Target <= 8 minutes.
2. `M11.I.A/B` <= 4 minutes.
3. `M11.I.C/D` <= 4 minutes.

DoD:
- [x] verdict is `ADVANCE_TO_P15`.
- [x] `next_gate=M11.J_READY`.
- [x] handoff pack published local + durable.
- [x] `M11.J_READY` asserted.

Closure evidence:
1. Managed run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22480969641`
2. Execution id: `m11i_p14_gate_rollup_20260227T094100Z`
3. Verdict artifact:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11i_p14_gate_rollup_20260227T094100Z/m11i_p14_gate_verdict.json`
4. Handoff artifact:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11i_p14_gate_rollup_20260227T094100Z/m12_handoff_pack.json`
5. Blockers artifact:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11i_p14_gate_rollup_20260227T094100Z/m11i_blocker_register.json` (`blocker_count=0`)
6. Summary artifact:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11i_p14_gate_rollup_20260227T094100Z/m11i_execution_summary.json`
7. Key closure proof:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P15`,
   - `next_gate=M11.J_READY`.

### M11.J - Cost-Outcome + Closure Sync
Goal:
1. Close M11 with cost/outcome proof and summary parity.

Execution lanes (sequential, fail-closed):
1. `M11.J.A` entry + handle closure:
- require M11.I pass posture:
  - `overall_pass=true`,
  - `blocker_count=0`,
  - `verdict=ADVANCE_TO_P15`,
  - `next_gate=M11.J_READY`,
- require cost handles pinned:
  - `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`,
  - `DEV_FULL_BUDGET_ALERT_1_USD`,
  - `DEV_FULL_BUDGET_ALERT_2_USD`,
  - `DEV_FULL_BUDGET_ALERT_3_USD`,
  - `BUDGET_CURRENCY`,
  - `COST_CAPTURE_SCOPE`,
  - `AWS_COST_CAPTURE_ENABLED`,
  - `DATABRICKS_COST_CAPTURE_ENABLED`.
2. `M11.J.B` budget + cost receipt:
- emit `m11_phase_budget_envelope.json`,
- emit `m11_phase_cost_outcome_receipt.json` using AWS CE MTD capture and pinned threshold posture.
3. `M11.J.C` closure summary + blocker register:
- emit `m11j_blocker_register.json`,
- emit `m11j_execution_summary.json`,
- emit `m11_execution_summary.json`.
4. `M11.J.D` contract parity validation:
- require upstream readable count == expected,
- require published output count == expected,
- require `all_required_available=true`,
- PASS only when `overall_pass=true`, blocker count `0`.

Blocker semantics:
1. `M11-B11`: entry/cost/parity failure.
2. `M11-B12`: publication/readback failure.

Runtime budget:
1. Target <= 8 minutes.
2. `M11.J.A/B` <= 4 minutes.
3. `M11.J.C/D` <= 4 minutes.

DoD:
- [x] cost-outcome receipt published local + durable.
- [x] summary parity passes (`all_required_available=true`).
- [x] no active blockers remain.
- [x] phase closure verdict ready for M12 entry.

Closure evidence (managed):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22483128692`
2. Execution:
   - `m11j_closure_sync_20260227T104756Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `verdict=ADVANCE_TO_M12`,
   - `next_gate=M12_READY`,
   - `all_required_available=true`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11_phase_budget_envelope.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11_phase_cost_outcome_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11j_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11j_execution_summary.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11_execution_summary.json`

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
- [x] `M11.B` complete
- [x] `M11.C` complete
- [x] `M11.D` complete
- [x] `M11.E` complete
- [x] `M11.F` complete
- [x] `M11.G` complete
- [x] `M11.H` complete
- [x] `M11.I` complete
- [x] `M11.J` complete
- [x] no unresolved `M11-B*` blocker remains
- [x] all M11 artifacts published local + durable
- [x] non-gate acceptance artifacts (`eval_vs_baseline`, `reproducibility`, `model_operability`) are pass posture
- [x] `M11D-AD1` cleared by advisory-free managed-transform rerun evidence

## 9) Planning Status
1. M11 planning is expanded to execution-grade depth.
2. `M11.A` is complete and green on managed lane.
3. `M11.B` is complete and green on managed lane.
4. `M11.C` is complete and green on managed lane.
5. `M11.D` is complete and green on strict managed lane with advisory-free transform evidence.
6. `M11.G` is complete and green on managed lane with operability pass and candidate bundle publication.
7. `M11.H` is complete and green on managed lane with safe-disable/rollback closure.
8. `M11.I` is complete and green on managed lane with deterministic P14 verdict + M12 handoff publication.
9. `M11.J` is complete and green on managed lane with phase cost-outcome closure and M12 entry verdict.
10. Next actionable lane is `M12.A` (promotion authority + handle closure).
