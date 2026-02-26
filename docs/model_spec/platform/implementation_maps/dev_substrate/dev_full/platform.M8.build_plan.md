# Dev Substrate Deep Plan - M8 (P11 SPINE_OBS_GOV_CLOSED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M8._
_Last updated: 2026-02-26_

## 0) Purpose
M8 closes:
1. `P11 SPINE_OBS_GOV_CLOSED`.

M8 must prove:
1. run report + reconciliation are committed with deterministic run scope.
2. governance append closeout is append-safe and single-writer disciplined.
3. spine non-regression anchors are explicit and pass against certified M6/M7 posture.
4. `P11` verdict is deterministic (`ADVANCE_TO_M9` or fail-closed hold).
5. phase budget envelope + cost-outcome receipt are committed for M8.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P11`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
3. M7 handoff evidence prefix:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7q_m7_rollup_sync_20260226T031710Z/`
4. M7 throughput cert evidence prefix:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7s_m7k_cert_20260226T000002Z/`

## 2) Scope Boundary for M8
In scope:
1. P11 authority and handle closure.
2. reporter runtime identity/lock readiness.
3. closure-input evidence readiness (from P5..P10 outputs).
4. reporter one-shot execution and single-writer contention proof.
5. closure artifact completeness and governance close-marker verification.
6. non-regression pack generation and validation.
7. P11 rollup verdict and M9 handoff publication.
8. M8 phase budget envelope + cost-outcome closure and summary sync.

Out of scope:
1. learning input closure (`M9` / `P12` onward).
2. infra topology changes already closed in M2/M4 unless required by blocker remediation.

## 3) Deliverables
1. `m8a_handle_closure_snapshot.json`
2. `m8b_runtime_lock_readiness_snapshot.json`
3. `m8c_closure_input_readiness_snapshot.json`
4. `m8d_single_writer_probe_snapshot.json`
5. `m8e_reporter_execution_snapshot.json`
6. `m8f_closure_bundle_completeness_snapshot.json`
7. `m8g_non_regression_pack_snapshot.json`
8. `m8h_governance_close_marker_snapshot.json`
9. `m8i_p11_rollup_matrix.json`
10. `m8i_p11_verdict.json`
11. `m9_handoff_pack.json`
12. `m8_phase_budget_envelope.json`
13. `m8_phase_cost_outcome_receipt.json`
14. `m8_execution_summary.json`

## 4) Entry Gate and Current Posture
Entry gate for M8:
1. `M7` is `DONE`.
2. `M7.J` is green with `next_gate=M8_READY`.
3. `M7.K` throughput certification is green (non-waived).
4. run-scope continuity from M7 is unchanged.

Current posture:
1. Entry conditions are met from existing M7 closure evidence.
2. M8 deep-plan expansion is now explicit; execution has not started.

## 4.1) Anti-Cram Law (Binding for M8)
M8 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. identity/IAM + secrets + lock backend.
3. closure input evidence readiness from P5..P10.
4. reporter one-shot runtime + contention guard.
5. closure artifacts publication and non-secret conformance.
6. non-regression validation against certified spine baseline.
7. deterministic P11 rollup/verdict and M9 handoff.
8. phase budget + cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M8.A | no unresolved required P11 handles |
| Runtime identity + lock readiness | M8.B | runtime role + lock probes pass |
| Closure-input readiness | M8.C | required upstream evidence readable |
| Single-writer contention discipline | M8.D | second-writer attempt rejected/blocked |
| Reporter execution | M8.E | one-shot execution succeeds with run scope |
| Closure bundle completeness | M8.F | report + reconciliation + closure artifacts present |
| Non-regression anchors | M8.G | non-regression pack pass verdict |
| Governance append/close marker | M8.H | append log and closure marker verified |
| P11 rollup + M9 handoff | M8.I | `ADVANCE_TO_M9` + durable handoff pack |
| M8 closure sync + cost-outcome | M8.J | summary + budget + cost receipt pass |

## 5) Work Breakdown (Orchestration)

### M8.A P11 Authority + Handle Closure
Goal:
1. close required P11 handles before runtime execution.

Required handle set:
1. `SPINE_RUN_REPORT_PATH_PATTERN`
2. `SPINE_RECONCILIATION_PATH_PATTERN`
3. `SPINE_NON_REGRESSION_PACK_PATTERN`
4. `GOV_APPEND_LOG_PATH_PATTERN`
5. `GOV_RUN_CLOSE_MARKER_PATH_PATTERN`
6. `REPORTER_LOCK_BACKEND`
7. `REPORTER_LOCK_KEY_PATTERN`
8. `ROLE_EKS_IRSA_OBS_GOV`
9. `EKS_NAMESPACE_OBS_GOV`
10. `S3_EVIDENCE_BUCKET`
11. `S3_EVIDENCE_RUN_ROOT_PATTERN`
12. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
13. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`
14. `M7_HANDOFF_PACK_PATH_PATTERN`

Tasks:
1. verify M7->M8 handoff continuity.
2. resolve required handle matrix and fail on unresolved/wildcard entries.
3. emit `m8a_handle_closure_snapshot.json`.

DoD:
- [x] required handle matrix explicit and complete.
- [x] unresolved required handles are blocker-marked.
- [x] `m8a_handle_closure_snapshot.json` committed locally and durably.

Execution status (2026-02-26):
1. Authoritative execution:
   - execution id: `m8a_p11_handle_closure_20260226T050813Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M8.B_READY`.
3. Verification outcomes:
   - M7->M8 handoff continuity read from:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7q_m7_rollup_sync_20260226T031710Z/m8_handoff_pack.json`,
   - required handles resolved: `14/14`,
   - missing handles: `0`,
   - placeholder handles: `0`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8a_p11_handle_closure_20260226T050813Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8a_p11_handle_closure_20260226T050813Z/`.

### M8.B Reporter Runtime Identity + Lock Readiness
Goal:
1. prove reporter runtime identity and lock posture are executable before closeout run.

Entry conditions:
1. `M8.A` execution summary is green (`overall_pass=true`, `next_gate=M8.B_READY`).
2. run scope is fixed from M7 handoff (`platform_run_id`, `scenario_run_id`).

Required handles:
1. `ROLE_EKS_IRSA_OBS_GOV`
2. `EKS_CLUSTER_NAME`
3. `EKS_NAMESPACE_OBS_GOV`
4. `REPORTER_LOCK_BACKEND`
5. `REPORTER_LOCK_KEY_PATTERN`
6. `SSM_AURORA_ENDPOINT_PATH` (required when backend is aurora)
7. `SSM_AURORA_USERNAME_PATH` (required when backend is aurora)
8. `SSM_AURORA_PASSWORD_PATH` (required when backend is aurora)
9. `AURORA_DB_NAME` (required when backend is aurora)
10. reporter entrypoint declaration (`ENTRYPOINT_REPORTER`) must exist in runtime entrypoint contract.

Tasks:
1. verify runtime identity bindings:
   - IRSA role exists and is readable by IAM.
   - EKS cluster is active for the configured cluster name.
   - Obs/Gov namespace handle is resolved and non-placeholder.
2. validate lock backend readiness:
   - backend handle + key pattern resolved and non-placeholder.
   - run-scoped lock key renders deterministically from `platform_run_id`.
   - aurora backend secret paths are readable from SSM.
3. verify reporter entrypoint declaration exists in handle registry contract.
4. emit:
   - `m8b_runtime_lock_readiness_snapshot.json`
   - `m8b_blocker_register.json`
   - `m8b_execution_summary.json`.

Deterministic verification algorithm:
1. read upstream `M8.A` summary and enforce pass posture.
2. resolve required handles and classify missing/placeholder values.
3. probe identity surfaces (`iam:GetRole`, `eks:DescribeCluster`).
4. probe lock-readiness surfaces (SSM path readability + key rendering).
5. classify blockers (`M8-B2` for readiness failures, `M8-B12` for artifact publication/readback failures).
6. publish local + durable evidence and return deterministic next gate.

Runtime budget:
1. target <= 15 minutes wall clock.

DoD:
- [x] identity bindings are concrete and non-placeholder.
- [x] lock backend readiness probe passes (SSM/backend/key rendering).
- [x] lock acquire/release contention semantics remain mandatory in `M8.D`.
- [x] `m8b_runtime_lock_readiness_snapshot.json` committed locally and durably.

Execution status (2026-02-26):
1. Authoritative execution:
   - execution id: `m8b_p11_runtime_lock_readiness_20260226T052700Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M8.C_READY`.
3. Verification outcomes:
   - upstream continuity from `M8.A` verified.
   - required handles resolved: `9/9`.
   - IRSA role exists and readable.
   - EKS cluster status is `ACTIVE`.
   - aurora lock backend SSM surfaces readable and run-scoped lock key rendering deterministic.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8b_p11_runtime_lock_readiness_20260226T052700Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8b_p11_runtime_lock_readiness_20260226T052700Z/`.
5. Closure note:
   - lock contention/acquire-release proof is explicitly deferred to `M8.D`; M8.B validates readiness surfaces only.

### M8.C Closure-Input Evidence Readiness
Goal:
1. prove all required upstream closure evidence is readable before reporter execution.

Entry conditions:
1. `M8.B` execution summary is green (`overall_pass=true`, `next_gate=M8.C_READY`).
2. run scope is fixed and unchanged from `M8.A/M8.B`.

Required upstream evidence groups:
1. ingest closure (`P7`) artifacts.
2. RTDL closure (`P8`) artifacts.
3. decision chain closure (`P9`) artifacts.
4. case-label closure (`P10`) artifacts.
5. M7 rollup + throughput certification artifacts.

Required source references:
1. M7 handoff pack (`m8_handoff_pack.json`) for authoritative `P8/P9/P10` execution ids.
2. M6 execution summary (`m6_execution_summary.json`) for authoritative `P7` rollup execution id.
3. run-scoped evidence paths rendered from handles:
   - `RECEIPT_SUMMARY_PATH_PATTERN`
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `QUARANTINE_SUMMARY_PATH_PATTERN`
   - `RTDL_CORE_EVIDENCE_PATH_PATTERN`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
   - `CASE_LABELS_EVIDENCE_PATH_PATTERN`.

Tasks:
1. resolve expected paths from handle patterns and active run scope.
2. verify object existence + schema/version markers.
3. emit:
   - `m8c_closure_input_readiness_snapshot.json`
   - `m8c_blocker_register.json`
   - `m8c_execution_summary.json`.

Deterministic verification algorithm:
1. read `M8.B` summary and enforce pass posture.
2. read M7 handoff and M6 summary references.
3. resolve P7/P8/P9/P10/M7 required evidence keys and run-scoped prefixes.
4. verify each required object exists and is parseable (JSON), and required marker fields are present (`phase`, `execution_id`, `overall_pass` for summaries/verdicts).
5. verify run-scoped folders (`rtdl_core`, `decision_lane`, `case_labels`) contain at least one JSON proof object.
6. classify blockers:
   - `M8-B3` for missing/malformed/unreadable upstream evidence,
   - `M8-B12` for artifact publication/readback failures.
7. publish local + durable evidence and return deterministic next gate.

Runtime budget:
1. target <= 20 minutes wall clock.

DoD:
- [x] all required closure-input evidence is readable and in-scope.
- [x] missing or malformed evidence is blocker-marked.
- [x] `m8c_closure_input_readiness_snapshot.json` committed locally and durably.

Execution status (2026-02-26):
1. Authoritative execution:
   - execution id: `m8c_p11_closure_input_readiness_20260226T053157Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M8.D_READY`.
3. Verification outcomes:
   - upstream continuity (`M8.B`, `M7`, `M6`, `M7.K`) verified and readable.
   - run-scoped closure inputs (`ingest`, `rtdl_core`, `decision_lane`, `case_labels`) are readable and non-empty.
   - readiness matrix rows verified: `23/23`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8c_p11_closure_input_readiness_20260226T053157Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8c_p11_closure_input_readiness_20260226T053157Z/`.

### M8.D Single-Writer Contention Probe
Goal:
1. prove single-writer governance posture before reporter closeout execution.

Entry conditions:
1. `M8.C` execution summary is green (`overall_pass=true`, `next_gate=M8.D_READY`).
2. run scope is fixed and unchanged from `M8.A/M8.B/M8.C`.
3. lock backend path is executable (not placeholder-only) for the active runtime posture.

Required handles:
1. `REPORTER_LOCK_BACKEND`
2. `REPORTER_LOCK_KEY_PATTERN`
3. `SSM_AURORA_ENDPOINT_PATH` (required when backend is aurora)
4. `SSM_AURORA_USERNAME_PATH` (required when backend is aurora)
5. `SSM_AURORA_PASSWORD_PATH` (required when backend is aurora)
6. `AURORA_DB_NAME` (required when backend is aurora)
7. `S3_EVIDENCE_BUCKET`
8. `S3_EVIDENCE_RUN_ROOT_PATTERN`

Deterministic verification algorithm:
1. read upstream `M8.C` summary and enforce pass posture.
2. resolve run scope + required handles; fail on missing/placeholder values.
3. resolve executable DSN surface for lock backend:
   - prefer explicit `IG_ADMISSION_DSN` if supplied,
   - otherwise derive from aurora SSM surfaces + `AURORA_DB_NAME`.
4. execute controlled contention probe with same `platform_run_id`:
   - writer-1 acquires lock and holds for bounded overlap window,
   - writer-2 attempts acquire on same key during overlap and must be denied fail-closed,
   - writer-1 releases lock,
   - post-release reacquire check must pass to prove no orphan lock state.
5. classify outcomes:
   - `M8-B4` for lock-path non-executable, contention failure, or orphan-lock signal,
   - `M8-B12` for publication/readback failures.
6. emit:
   - `m8d_single_writer_probe_snapshot.json`
   - `m8d_blocker_register.json`
   - `m8d_execution_summary.json`.

Tasks:
1. validate M8.C pass posture and run-scope continuity.
2. resolve lock backend path and prove DSN/secret surfaces are executable.
3. execute deterministic two-writer contention probe on same lock key.
4. verify no orphan-lock state after release.
5. emit local + durable `m8d_*` artifact set.

DoD:
- [x] contention probe proves single-writer behavior.
- [x] no orphan lock remains after probe cleanup.
- [x] `m8d_single_writer_probe_snapshot.json` committed locally and durably.

Runtime budget:
1. target <= 20 minutes wall clock (including remediation rerun if first attempt is fail-closed).

Execution status (2026-02-26):
1. implementation lane script pinned:
   - `scripts/dev_substrate/m8d_single_writer_probe.py`.
2. runtime alias drift patched in reporter worker:
   - `aurora_advisory_lock` now executes the same Postgres advisory-lock path as `db_advisory_lock`.
3. first authoritative execution (fail-closed):
   - execution id: `m8d_p11_single_writer_probe_20260226T054231Z`,
   - result: `overall_pass=false`, `blocker_count=3`,
   - blocker family: `M8-B4`,
   - root cause: seeded/non-routable aurora endpoint surface (`*.cluster.local`) prevented lock acquisition.
4. remediation applied in-lane:
   - concrete Aurora cluster + writer instance were materialized for lock path execution,
   - SSM aurora endpoint paths were repinned to concrete RDS endpoints.
5. authoritative rerun (closure pass):
   - execution id: `m8d_p11_single_writer_probe_20260226T055105Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M8.E_READY`,
   - lock outcomes: writer-1 acquire, writer-2 denied (`REPORTER_LOCK_NOT_ACQUIRED`), post-release reacquire pass (no orphan lock).
6. evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8d_p11_single_writer_probe_20260226T055105Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8d_p11_single_writer_probe_20260226T055105Z/`.
7. closure note:
   - aurora lock-surface remediation was executed directly in AWS control plane; IaC codification follow-up is required to prevent future overwrite/drift on subsequent terraform applies.

### M8.E Reporter One-Shot Execution
Goal:
1. run reporter closeout once under managed runtime with deterministic run scope.

Entry conditions:
1. `M8.D` is pass with blockers empty:
   - local: `runs/dev_substrate/dev_full/m8/m8d_p11_single_writer_probe_20260226T055105Z/m8d_execution_summary.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8d_p11_single_writer_probe_20260226T055105Z/m8d_execution_summary.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260201T224449Z`.
3. Reporter one-shot must execute in managed runtime (`EKS` Job); local reporter compute is not accepted as closure proof.

Required inputs:
1. `M8.D` pass execution summary.
2. Required handles (non-placeholder):
   - `EKS_CLUSTER_NAME`
   - `EKS_NAMESPACE_OBS_GOV`
   - `ROLE_EKS_IRSA_OBS_GOV`
   - `ECR_REPO_URI`
   - `S3_OBJECT_STORE_BUCKET`
   - `S3_EVIDENCE_BUCKET`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`
   - `AURORA_DB_NAME`
   - `REPORTER_LOCK_BACKEND`
   - `REPORTER_LOCK_KEY_PATTERN`
3. Runtime contract handles:
   - `ENTRYPOINT_REPORTER` declaration exists in registry.
4. Execution constants:
   - one-shot k8s job timeout: `<= 900s`
   - one-shot poll interval: `5s`.

Preparation checks:
1. Validate `M8.D` pass posture and run-scope match.
2. Validate no active reporter job exists for same `platform_run_id` in target namespace.
3. Validate EKS namespace/service-account readiness for Obs/Gov runtime.
4. Resolve Aurora lock DSN from SSM surfaces and reject unresolved/placeholder values.
5. Resolve immutable image URI from ECR (`repo@sha256:*` preferred).

Deterministic verification algorithm (M8.E):
1. Load `M8.D` summary; fail on missing/invalid/pass-mismatch -> `M8-B5`.
2. Resolve required handles; unresolved/placeholder/wildcard -> `M8-B5`.
3. Ensure EKS namespace + IRSA service account are materialized and role-annotated.
4. Assert no concurrent run-scoped reporter writer is active.
5. Dispatch one-shot k8s job:
   - command: `python -m fraud_detection.platform_reporter.worker --profile <dev_full_runtime_profile> --once --required-platform-run-id <platform_run_id>`.
6. Wait for terminal lifecycle outcome within budget; timeout/failure -> `M8-B5`.
7. Validate lock lifecycle evidence from pod logs:
   - lock acquired + lock released must both be present for run scope,
   - lock denied pattern must not be present.
   - failure -> `M8-B5`.
8. Validate closure artifacts exist in object-store under run prefix:
   - `<platform_run_id>/obs/platform_run_report.json`
   - `<platform_run_id>/obs/run_report.json`
   - `<platform_run_id>/obs/reconciliation.json`
   - `<platform_run_id>/obs/replay_anchors.json`
   - `<platform_run_id>/obs/environment_conformance.json`
   - `<platform_run_id>/obs/anomaly_summary.json`
   - `<platform_run_id>/run_completed.json`
   - missing/unreadable -> `M8-B5`.
9. Emit `m8e_reporter_execution_snapshot.json` locally and publish durably.
10. Emit `m8e_blocker_register.json` + `m8e_execution_summary.json` with deterministic next gate.

Tasks:
1. Execute managed one-shot reporter job under run scope with lock posture.
2. Validate lifecycle, lock evidence, and closure artifact existence.
3. Emit and publish `m8e_reporter_execution_snapshot.json`, `m8e_blocker_register.json`, `m8e_execution_summary.json` (local + durable).

Required snapshot fields (`m8e_reporter_execution_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `scenario_run_id`, `m8_execution_id`.
2. `source_m8d_summary_uri`, `entry_gate_ok`.
3. `runtime_contract`:
   - `eks_cluster`, `namespace`, `service_account`, `role_arn`,
   - `image_uri`, `entrypoint`.
4. `job_execution`:
   - `job_name`, `pod_name`, `submitted_at_utc`, `completed_at_utc`,
   - `terminal_state`, `container_exit_code`, `elapsed_seconds`.
5. `lock_lifecycle_checks`:
   - `lock_acquired_seen`, `lock_released_seen`, `lock_denied_seen`, `lock_scope_match`.
6. `closure_artifact_checks`:
   - required object-store keys, per-key readability status.
7. `blockers`, `overall_pass`, `next_gate`, `captured_at_utc`.

Blocker codes:
1. `M8-B5`: reporter runtime execution, concurrency, or lock-lifecycle failure.
2. `M8-B12`: summary/evidence publication parity failure.

DoD:
- [x] reporter one-shot execution succeeds and is run-scoped.
- [x] no concurrent reporter writer is active for same run.
- [x] lock acquire/release evidence is present and lock-denied conflict is absent.
- [x] closure artifacts exist in object-store under the run prefix.
- [x] `m8e_reporter_execution_snapshot.json` committed locally and durably.
- [x] `m8e_blocker_register.json` + `m8e_execution_summary.json` committed locally and durably.

Runtime budget:
1. `M8.E` target budget: <= 15 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Execution closure (2026-02-26):
1. fail-first execution chain retained for blocker traceability:
   - `m8e_p11_reporter_one_shot_20260226T060736Z` failed on runtime image/backend mismatch (`REPORTER_LOCK_BACKEND_UNSUPPORTED:aurora_advisory_lock`).
   - `m8e_p11_reporter_one_shot_20260226T060917Z` passed lock path but failed on missing IG Postgres tables (`receipts` absent).
   - `m8e_p11_reporter_one_shot_20260226T061050Z` passed lock + schema bootstrap but failed on IRSA KMS envelope permission (`kms:GenerateDataKey` denied).
2. blocker remediations executed in-lane:
   - runtime compatibility shim in dispatch (`aurora_advisory_lock` handle preserved, pod runtime backend set to `db_advisory_lock` for current image compatibility),
   - one-shot bootstrap DDL for required IG reporter read surfaces (`receipts`, `quarantines`, `admissions`) in Aurora runtime path,
   - IRSA role extension for Obs/Gov reporter path:
     - object-store S3 RW policy,
     - KMS key permissions (`GenerateDataKey/Encrypt/Decrypt/DescribeKey`) for `alias/fraud-platform-dev-full`.
3. closure pass execution:
   - execution id: `m8e_p11_reporter_one_shot_20260226T061150Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M8.F_READY`,
   - reporter pod: `m8e-reporter-061158-vvwbl` exit `0`,
   - lock checks: acquired=true, released=true, denied=false, scope_match=true,
   - closure artifacts: `7/7` required object-store keys readable.
4. evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8e_p11_reporter_one_shot_20260226T061150Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8e_p11_reporter_one_shot_20260226T061150Z/`.

### M8.F Closure-Bundle Completeness Validation
Goal:
1. verify report/reconciliation/obs artifacts are complete and coherent.

Entry conditions:
1. `M8.E` is pass with blockers empty:
   - local: `runs/dev_substrate/dev_full/m8/m8e_p11_reporter_one_shot_20260226T061150Z/m8e_execution_summary.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8e_p11_reporter_one_shot_20260226T061150Z/m8e_execution_summary.json`.
2. Active run scope is fixed:
   - `platform_run_id=platform_20260201T224449Z`.
3. Closure artifacts are expected under implemented object-store prefix:
   - `s3://fraud-platform-dev-full-object-store/<platform_run_id>/...`.

Required inputs:
1. `M8.E` pass snapshot/summary.
2. Required closure bundle object-store keys:
   - `<platform_run_id>/run_completed.json`
   - `<platform_run_id>/obs/platform_run_report.json`
   - `<platform_run_id>/obs/run_report.json`
   - `<platform_run_id>/obs/reconciliation.json`
   - `<platform_run_id>/obs/replay_anchors.json`
   - `<platform_run_id>/obs/environment_conformance.json`
   - `<platform_run_id>/obs/anomaly_summary.json`.
3. Required handle values (concrete, non-placeholder):
   - `S3_OBJECT_STORE_BUCKET`
   - `S3_EVIDENCE_BUCKET`.
4. M8 control-plane evidence root for:
   - `m8f_closure_bundle_completeness_snapshot.json`
   - `m8f_blocker_register.json`
   - `m8f_execution_summary.json`.

Preparation checks:
1. Validate `M8.E` pass posture and run-scope match.
2. Validate object-store/evidence bucket handles resolve concretely.
3. Validate local->durable publication path for `m8f_*` artifacts is writable.
   Failure of any preparation check is fail-closed (`M8-B6`/`M8-B12`).

Deterministic verification algorithm (M8.F):
1. Load `M8.E` summary; fail on missing/invalid/pass-mismatch -> `M8-B6`.
2. Resolve required object-store closure keys from fixed `platform_run_id`.
3. For each required key:
   - validate existence/readability (`HEAD`/`GET`),
   - parse JSON payload,
   - evaluate run-scope conformance (`platform_run_id` field equals active run scope when present).
4. Validate closure-ref coherence from `run_completed.json`:
   - `closure_refs.run_report_ref == <platform_run_id>/obs/run_report.json`
   - `closure_refs.reconciliation_ref == <platform_run_id>/obs/reconciliation.json`
   - `closure_refs.replay_anchors_ref == <platform_run_id>/obs/replay_anchors.json`
   - `closure_refs.environment_conformance_ref == <platform_run_id>/obs/environment_conformance.json`
   - `closure_refs.anomaly_summary_ref == <platform_run_id>/obs/anomaly_summary.json`.
5. Validate reconciliation coherence:
   - `status == PASS`
   - all boolean values in `checks` are `true`
   - `deltas.sent_minus_received`, `deltas.received_minus_admit`, `deltas.decision_minus_outcome` are non-negative integers.
6. Validate report surface coherence:
   - `run_report.platform_run_id == platform_run_id`
   - `platform_run_report.platform_run_id == platform_run_id`
   - `run_report` and `platform_run_report` both parse and have ingress/rtdl basis sections.
7. Emit `m8f_closure_bundle_completeness_snapshot.json`, `m8f_blocker_register.json`, `m8f_execution_summary.json` locally and publish durably.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate required closure artifact existence/readability on object-store path.
2. Validate run-scope and closure-ref coherence across bundle.
3. Validate reconciliation pass/coherence semantics.
4. Emit and publish `m8f_closure_bundle_completeness_snapshot.json`, `m8f_blocker_register.json`, `m8f_execution_summary.json` (local + durable).

Required snapshot fields (`m8f_closure_bundle_completeness_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `scenario_run_id`, `m8_execution_id`.
2. `source_m8e_summary_uri`, `entry_gate_ok`.
3. `bundle_targets` (required object-store keys).
4. `artifact_checks` (per-key existence/readability/json/run-scope/coherence status).
5. `run_completed_ref_checks`.
6. `reconciliation_checks`.
7. `blockers`, `overall_pass`, `next_gate`, `elapsed_seconds`.

Blocker codes:
1. `M8-B6`: closure-bundle completeness/coherence failure.
2. `M8-B12`: summary/evidence publication parity failure.

DoD:
- [x] run report and reconciliation are present, parseable, and run-scoped.
- [x] closure-ref coherence in `run_completed.json` passes.
- [x] closure bundle completeness/coherence checks pass.
- [x] `m8f_closure_bundle_completeness_snapshot.json` committed locally and durably.
- [x] `m8f_blocker_register.json` + `m8f_execution_summary.json` committed locally and durably.

Runtime budget:
1. `M8.F` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Execution closure (2026-02-26):
1. execution id: `m8f_p11_closure_bundle_20260226T061917Z`.
2. result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M8.G_READY`.
3. closure checks passed:
   - all required closure bundle targets readable/parseable (`7/7`),
   - run-scope conformance across bundle surfaces,
   - `run_completed` closure ref coherence,
   - reconciliation pass/check-map/delta coherence.
4. evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8f_p11_closure_bundle_20260226T061917Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8f_p11_closure_bundle_20260226T061917Z/`.

### M8.G Spine Non-Regression Pack
Goal:
1. emit and validate non-regression pack against certified M6/M7 anchors.

Entry conditions:
1. `M8.F` is pass with blockers empty:
   - local: `runs/dev_substrate/dev_full/m8/m8f_p11_closure_bundle_20260226T062814Z/m8f_execution_summary.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8f_p11_closure_bundle_20260226T062814Z/m8f_execution_summary.json`.
2. Certified spine anchors from `M6/M7` are readable:
   - `m6j_m6_closure_sync_20260225T194637Z`,
   - `m7q_m7_rollup_sync_20260226T031710Z`,
   - `m7s_m7k_cert_20260226T000002Z`.
3. No unresolved blockers remain from `M8.F`.

Required inputs:
1. `M8.F` pass summary/snapshot.
2. Certified anchor summaries:
   - `evidence/dev_full/run_control/<m6j_execution>/m6j_execution_summary.json`
   - `evidence/dev_full/run_control/<m7q_execution>/m7_execution_summary.json`
   - `evidence/dev_full/run_control/<m7s_execution>/m7k_throughput_cert_execution_summary.json`.
3. P11 closure artifacts for active run scope:
   - `<platform_run_id>/run_completed.json`
   - `<platform_run_id>/obs/run_report.json`
   - `<platform_run_id>/obs/reconciliation.json`.
4. Handle contracts:
   - `SPINE_NON_REGRESSION_PACK_PATTERN`,
   - `S3_EVIDENCE_BUCKET`,
   - `S3_OBJECT_STORE_BUCKET`.

Preparation checks (fail-closed):
1. Validate `M8.F` pass posture and run-scope.
2. Validate all anchor summaries are readable, parseable, and green with expected next-gate posture.
3. Validate run-scope continuity between M8 closure artifacts and M6/M7 certified run scope.
4. Validate non-regression output destinations are concrete and writable.

Deterministic verification algorithm (M8.G):
1. Load `M8.F` execution summary; fail on missing/invalid/pass-mismatch -> `M8-B7`.
2. Load anchor summaries (`M6.J`, `M7.J`, `M7.K`) and assert:
   - `overall_pass=true` for each,
   - `M6.J.next_gate=M7_READY`,
   - `M7.J.next_gate=M8_READY`,
   - `M7.K.next_gate=M8_READY`.
3. Derive certified run scope from `M7.J` (`platform_run_id` + `scenario_run_id`).
4. Load P11 closure artifacts from object-store (`run_completed`, `run_report`, `reconciliation`) for active `M8.F` run scope.
5. Enforce non-regression checks:
   - run-scope parity (`M8.F` scope equals certified `M7.J` scope),
   - reconciliation closure remains pass (`status=PASS`, checks map all true, non-negative deltas),
   - run report arithmetic identities hold for ingress/rtdl deltas.
6. Emit canonical pack at `SPINE_NON_REGRESSION_PACK_PATTERN`:
   - includes anchor refs, check results, blocker list, and verdict.
7. Emit `m8g_non_regression_pack_snapshot.json`, `m8g_blocker_register.json`, `m8g_execution_summary.json` under M8 run-control root.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Build anchor comparison set (`M6.J`, `M7.J`, `M7.K`, `M8.F`).
2. Evaluate deterministic non-regression checks and classify tolerated vs blocking differences.
3. Emit canonical non-regression pack + M8.G run-control artifacts (local + durable).
4. If run-scope mismatch occurs, remediate by rerunning `M8.D -> M8.E -> M8.F` on certified run scope and rerun `M8.G`.

Required snapshot fields (`m8g_non_regression_pack_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `scenario_run_id`, `m8_execution_id`.
2. `source_m8f_summary_uri`.
3. `anchor_refs` (`m6j`, `m7j`, `m7k` summary keys).
4. `anchor_gate_checks`.
5. `run_scope_parity_checks`.
6. `reconciliation_non_regression_checks`.
7. `non_regression_pack_key`.
8. `blockers`, `overall_pass`, `next_gate`, `elapsed_seconds`.

DoD:
- [x] non-regression pack exists with deterministic pass/fail fields.
- [x] certified M6/M7 anchor parity checks pass or fail-closed with explicit blockers.
- [x] blocking drift is fail-closed and explicit.
- [x] `m8g_non_regression_pack_snapshot.json` + blocker register + summary committed locally and durably.

Runtime budget:
1. `M8.G` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

Execution closure (2026-02-26):
1. fail-first execution:
   - `m8g_p11_non_regression_20260226T062628Z` -> `M8-B7` (run-scope mismatch between M8 closure and certified M7 anchors).
2. remediation chain executed on canonical run scope (`platform_20260223T184232Z`):
   - `M8.D`: `m8d_p11_single_writer_probe_20260226T062710Z` (`overall_pass=true`, `next_gate=M8.E_READY`),
   - `M8.E`: `m8e_p11_reporter_one_shot_20260226T062735Z` (`overall_pass=true`, `next_gate=M8.F_READY`),
   - `M8.F`: `m8f_p11_closure_bundle_20260226T062814Z` (`overall_pass=true`, `next_gate=M8.G_READY`).
3. closure execution:
   - `m8g_p11_non_regression_20260226T062919Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M8.H_READY`.
4. evidence:
   - local: `runs/dev_substrate/dev_full/m8/m8g_p11_non_regression_20260226T062919Z/`,
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8g_p11_non_regression_20260226T062919Z/`,
   - canonical pack: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/obs/non_regression_pack.json`.
5. execution hardening applied:
   - `m8g` now treats upstream `M8.F` run scope as authoritative and fails closed when explicit env run-scope overrides disagree.

### M8.H Governance Append + Closure Marker
Goal:
1. prove governance append log and closure marker are committed correctly.

Entry conditions:
1. `M8.G` is pass with blockers empty:
   - local: `runs/dev_substrate/dev_full/m8/m8g_p11_non_regression_20260226T062919Z/m8g_execution_summary.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m8g_p11_non_regression_20260226T062919Z/m8g_execution_summary.json`.
2. Active run scope is pinned to:
   - `platform_run_id=platform_20260223T184232Z`.
3. No unresolved blockers remain from `M8.G`.

Required inputs:
1. `M8.G` pass summary/snapshot.
2. Source-of-truth closure artifacts from object-store:
   - `<platform_run_id>/run_completed.json`
   - `<platform_run_id>/obs/governance/events.jsonl`
   - `<platform_run_id>/obs/governance/markers/*.json`.
3. Handle contracts:
   - `GOV_APPEND_LOG_PATH_PATTERN`
   - `GOV_RUN_CLOSE_MARKER_PATH_PATTERN`
   - `S3_EVIDENCE_BUCKET`
   - `S3_OBJECT_STORE_BUCKET`.
4. M8 run-control evidence root for:
   - `m8h_governance_close_marker_snapshot.json`
   - `m8h_blocker_register.json`
   - `m8h_execution_summary.json`.

Preparation checks (fail-closed):
1. Validate `M8.G` pass posture and run-scope match.
2. Validate source governance artifacts are readable/parseable from object-store.
3. Validate governance handle targets are concrete (no placeholder/wildcard).
4. Validate run-control and governance evidence output prefixes are writable.

Deterministic verification algorithm (M8.H):
1. Load `M8.G` pass summary; fail on missing/invalid/pass-mismatch -> `M8-B8`.
2. Load and parse source-of-truth governance surfaces:
   - object-store `events.jsonl`,
   - object-store marker objects under `obs/governance/markers/`,
   - object-store `run_completed.json`.
3. Enforce source-truth checks:
   - `run_completed.status == COMPLETED`,
   - `closure_refs.governance_events_ref` is non-empty and run-scoped,
   - governance event rows contain required fields (`event_id`, `event_family`, `ts_utc`, `pins.platform_run_id`),
   - sampled/full governance rows are run-scoped (`pins.platform_run_id == active run`),
   - at least one `RUN_REPORT_GENERATED` event exists,
   - marker file count is >= governance event count for deduped event ids.
4. Enforce append ordering checks:
   - event order in append log is monotonic by `ts_utc` (non-decreasing),
   - marker `event_id` coverage matches append-log event ids.
5. Materialize deterministic governance projection to handle-contract evidence paths:
   - write append log copy to `GOV_APPEND_LOG_PATH_PATTERN`,
   - write closure marker payload to `GOV_RUN_CLOSE_MARKER_PATH_PATTERN` (derived from `run_completed` + governance checks).
6. Validate projected governance artifacts are readable and run-scoped.
7. Emit `m8h_governance_close_marker_snapshot.json`, `m8h_blocker_register.json`, `m8h_execution_summary.json` locally and durably.
8. Return `overall_pass=true` only when blocker list is empty.

Tasks:
1. Validate governance source-of-truth append + marker surfaces on object-store.
2. Validate closure-marker status, run scope, and closure-ref coherence.
3. Validate append ordering and event/marker coverage.
4. Materialize governance evidence projections to handle-contract paths.
5. Emit `m8h_governance_close_marker_snapshot.json` + blocker register + execution summary.

Required snapshot fields (`m8h_governance_close_marker_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `scenario_run_id`, `m8_execution_id`.
2. `source_m8g_summary_uri`.
3. `source_refs` (`run_completed`, `governance_events`, `governance_markers_prefix`).
4. `source_truth_checks` (`run_completed`, `events_schema`, `run_scope`, `event_family`, `marker_coverage`, `ordering`).
5. `projection_targets` (`gov_append_log`, `gov_closure_marker`) and projection write/readback status.
6. `blockers`, `overall_pass`, `next_gate`, `elapsed_seconds`.

DoD:
- [ ] governance append and closure marker are committed and readable.
- [ ] source-truth governance checks pass (schema/run-scope/order/marker coverage).
- [ ] handle-contract governance projection exists and is run-scoped.
- [ ] `m8h_governance_close_marker_snapshot.json` + blocker register + summary committed locally and durably.

Runtime budget:
1. `M8.H` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

### M8.I P11 Rollup Verdict + M9 Handoff
Goal:
1. adjudicate M8 and publish deterministic handoff to M9.

Tasks:
1. aggregate M8.A..M8.H outcomes into rollup matrix.
2. emit `m8i_p11_rollup_matrix.json` + blocker register.
3. emit deterministic verdict artifact `m8i_p11_verdict.json`.
4. emit `m9_handoff_pack.json`.

DoD:
- [ ] verdict is deterministic with explicit next gate.
- [ ] if blocker-free, verdict is `ADVANCE_TO_M9` with `next_gate=M9_READY`.
- [ ] `m9_handoff_pack.json` committed locally and durably.

### M8.J M8 Closure Sync + Cost-Outcome Receipt
Goal:
1. close M8 with required summary and cost-to-outcome artifacts.

Tasks:
1. emit `m8_phase_budget_envelope.json`.
2. emit `m8_phase_cost_outcome_receipt.json`.
3. emit `m8_execution_summary.json`.
4. validate local + durable artifact parity for all M8 outputs.

DoD:
- [ ] budget envelope + cost-outcome receipt committed locally and durably.
- [ ] `m8_execution_summary.json` committed locally and durably.
- [ ] M8 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M8-B1`: authority/handle closure failure.
2. `M8-B2`: runtime identity/lock readiness failure.
3. `M8-B3`: closure-input evidence readiness failure.
4. `M8-B4`: single-writer contention probe failure.
5. `M8-B5`: reporter execution failure.
6. `M8-B6`: closure-bundle completeness failure.
7. `M8-B7`: non-regression pack failure.
8. `M8-B8`: governance append/closure-marker failure.
9. `M8-B9`: P11 rollup verdict inconsistency.
10. `M8-B10`: M9 handoff pack failure.
11. `M8-B11`: phase cost-outcome closure failure.
12. `M8-B12`: summary/evidence publication parity failure.

## 7) Artifact Contract (M8)
1. `m8a_handle_closure_snapshot.json`
2. `m8b_runtime_lock_readiness_snapshot.json`
3. `m8c_closure_input_readiness_snapshot.json`
4. `m8d_single_writer_probe_snapshot.json`
5. `m8e_reporter_execution_snapshot.json`
6. `m8f_closure_bundle_completeness_snapshot.json`
7. `m8g_non_regression_pack_snapshot.json`
8. `m8h_governance_close_marker_snapshot.json`
9. `m8i_p11_rollup_matrix.json`
10. `m8i_p11_verdict.json`
11. `m9_handoff_pack.json`
12. `m8_phase_budget_envelope.json`
13. `m8_phase_cost_outcome_receipt.json`
14. `m8_execution_summary.json`

## 8) Completion Checklist
- [x] `M8.A` complete
- [x] `M8.B` complete
- [x] `M8.C` complete
- [x] `M8.D` complete
- [x] `M8.E` complete
- [x] `M8.F` complete
- [x] `M8.G` complete
- [ ] `M8.H` complete
- [ ] `M8.I` complete
- [ ] `M8.J` complete
- [x] all active `M8-B*` blockers resolved

## 9) Planning Status
1. M8 planning is expanded and execution-grade.
2. `M8.A` handle/authority closure is closed green.
3. `M8.B` runtime identity + lock readiness is closed green.
4. `M8.C` closure-input evidence readiness is closed green.
5. `M8.D` single-writer contention probe is closed green.
6. `M8.E` reporter one-shot execution is closed green.
7. `M8.F` closure-bundle completeness validation is closed green.
8. `M8.G` spine non-regression pack generation + validation is closed green.
9. Next action is `M8.H` governance append + closure-marker verification.
