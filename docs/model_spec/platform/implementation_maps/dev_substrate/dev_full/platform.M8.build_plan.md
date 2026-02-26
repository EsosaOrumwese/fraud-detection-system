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

Tasks:
1. attempt writer-1 lock acquire for run scope.
2. attempt writer-2 lock acquire on same key and require deterministic failure/deferral.
3. release writer-1 lock and verify no orphan lock state.
4. emit `m8d_single_writer_probe_snapshot.json`.

DoD:
- [ ] contention probe proves single-writer behavior.
- [ ] no orphan lock remains after probe cleanup.
- [ ] `m8d_single_writer_probe_snapshot.json` committed locally and durably.

### M8.E Reporter One-Shot Execution
Goal:
1. run reporter closeout once under managed runtime with deterministic run scope.

Tasks:
1. dispatch reporter one-shot execution.
2. verify execution lifecycle + exit status.
3. capture runtime evidence refs and emitted closure artifact paths.
4. emit `m8e_reporter_execution_snapshot.json`.

DoD:
- [ ] reporter one-shot execution succeeds and is run-scoped.
- [ ] no concurrent reporter writer is active for same run.
- [ ] `m8e_reporter_execution_snapshot.json` committed locally and durably.

### M8.F Closure-Bundle Completeness Validation
Goal:
1. verify report/reconciliation/obs artifacts are complete and coherent.

Tasks:
1. verify run report exists and has required fields.
2. verify reconciliation exists and matches run scope + closure totals.
3. verify required obs outputs are present.
4. emit `m8f_closure_bundle_completeness_snapshot.json`.

DoD:
- [ ] run report and reconciliation are present, parseable, and run-scoped.
- [ ] closure bundle completeness check passes.
- [ ] `m8f_closure_bundle_completeness_snapshot.json` committed locally and durably.

### M8.G Spine Non-Regression Pack
Goal:
1. emit and validate non-regression pack against certified M6/M7 anchors.

Tasks:
1. build anchor comparison set (P5/P6/P7/P8/P9/P10 closure invariants).
2. evaluate non-regression checks and classify tolerated vs blocking differences.
3. emit `m8g_non_regression_pack_snapshot.json` and `non_regression_pack.json`.

DoD:
- [ ] non-regression pack exists with deterministic pass/fail fields.
- [ ] blocking drift is fail-closed and explicit.
- [ ] `m8g_non_regression_pack_snapshot.json` committed locally and durably.

### M8.H Governance Append + Closure Marker
Goal:
1. prove governance append log and closure marker are committed correctly.

Tasks:
1. verify append log writes to `GOV_APPEND_LOG_PATH_PATTERN`.
2. verify closure marker writes to `GOV_RUN_CLOSE_MARKER_PATH_PATTERN`.
3. verify append ordering and run-scope correlation fields.
4. emit `m8h_governance_close_marker_snapshot.json`.

DoD:
- [ ] governance append and closure marker are committed and readable.
- [ ] append ordering/correlation checks pass.
- [ ] `m8h_governance_close_marker_snapshot.json` committed locally and durably.

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
- [ ] `M8.D` complete
- [ ] `M8.E` complete
- [ ] `M8.F` complete
- [ ] `M8.G` complete
- [ ] `M8.H` complete
- [ ] `M8.I` complete
- [ ] `M8.J` complete
- [ ] all active `M8-B*` blockers resolved

## 9) Planning Status
1. M8 planning is expanded and execution-grade.
2. `M8.A` handle/authority closure is closed green.
3. `M8.B` runtime identity + lock readiness is closed green.
4. `M8.C` closure-input evidence readiness is closed green.
5. Next action is `M8.D` single-writer contention probe.
