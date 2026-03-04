# Dev Substrate Stress Plan - M6.P6 (P6 STREAMING_ACTIVE)
_Parent authority: `platform.M6.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_

## 0) Purpose
M6.P6 stress validates streaming activation and ingress progression under realistic production stress before ingest-commit closure (`P7`).

M6.P6 stress must prove:
1. stream lanes become active on an explicitly pinned runtime path.
2. run-scoped events progress through stream->ingress with non-zero admission continuity.
3. lag stays within threshold and publish ambiguity remains closed.
4. evidence overhead does not materially degrade hot-path throughput.
5. P6 rollup emits deterministic verdict (`ADVANCE_TO_P7` only when blocker-free).

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P6.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. latest successful M6 parent `S0` and P5 closure verdict.

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) Stage-A Findings (M6.P6)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M6P6-ST-F1` | `PREVENT` | P6 entry is invalid without deterministic upstream P5 verdict (`ADVANCE_TO_P6`). | Gate S0 on latest successful P5 closure receipt. |
| `M6P6-ST-F2` | `PREVENT` | Runtime path ambiguity (`MSF_MANAGED` vs `EKS_FLINK_OPERATOR`) can create mismatched probes and false PASS. | Enforce single-active runtime path check in S0 and path-aware probes in S1-S3. |
| `M6P6-ST-F3` | `PREVENT` | Active lane state alone is insufficient; run-window ingress progression must be non-zero. | Require run-window scoped progression checks in S2/S3. |
| `M6P6-ST-F4` | `PREVENT` | Lag claims without active admissions are invalid and can mask failure. | Compute lag only when active run-window admissions exist; fail-closed otherwise. |
| `M6P6-ST-F5` | `OBSERVE` | Managed Flink account/service constraints can block runtime activation in otherwise-correct configs. | Keep explicit fallback remediation lane with measured before/after evidence. |
| `M6P6-ST-F6` | `OBSERVE` | Evidence emission can become hot-path drag during high-rate windows. | Enforce bytes/event and write-rate budgets in S3. |
| `M6P6-ST-F7` | `OBSERVE` | Private-runtime network posture can pass control checks but fail in-pod ingress POST path. | Keep in-runtime bridge probes mandatory for S2 progression validity. |
| `M6P6-ST-F8` | `ACCEPT` | Build authority already defines deterministic `ADVANCE_TO_P7` verdict semantics. | Reuse verdict surface with stress-specific realism gates. |

## 3) Scope Boundary for M6.P6 Stress
In scope:
1. P6 entry and runtime-path closure.
2. stream lane activation and run-window progression checks.
3. lag, ambiguity, and evidence-overhead closure.
4. deterministic P6 rollup and verdict emission.

Out of scope:
1. READY commit authority closure (`P5`).
2. ingest commit evidence closure (`P7`).
3. parent integrated cross-plane closure (`M6` S4/S5).

## 4) M6.P6 Stress Handle Packet (Pinned)
1. `M6P6_STRESS_PROFILE_ID = "streaming_active_stress_v0"`.
2. `M6P6_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p6_blocker_register.json"`.
3. `M6P6_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p6_execution_summary.json"`.
4. `M6P6_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p6_decision_log.json"`.
5. `M6P6_STRESS_REQUIRED_ARTIFACTS = "m6p6_stagea_findings.json,m6p6_lane_matrix.json,m6p6_streaming_active_snapshot.json,m6p6_lag_posture_snapshot.json,m6p6_evidence_overhead_snapshot.json,m6p6_probe_latency_throughput_snapshot.json,m6p6_control_rail_conformance_snapshot.json,m6p6_secret_safety_snapshot.json,m6p6_cost_outcome_receipt.json,m6p6_blocker_register.json,m6p6_execution_summary.json,m6p6_decision_log.json,m6p6_gate_verdict.json"`.
6. `M6P6_STRESS_MAX_RUNTIME_MINUTES = 180`.
7. `M6P6_STRESS_MAX_SPEND_USD = 35`.
8. `M6P6_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_P7"`.
9. `M6P6_STRESS_RUNTIME_PATH_PRIORITY = "MSF_MANAGED_PRIMARY|EKS_FLINK_OPERATOR_FALLBACK"`.
10. `M6P6_STRESS_STEADY_WINDOW_MINUTES = 20`.
11. `M6P6_STRESS_BURST_WINDOW_MINUTES = 8`.
12. `M6P6_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles for M6.P6:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `FLINK_APP_WSP_STREAM_V0`
4. `FLINK_APP_SR_READY_V0`
5. `FLINK_EKS_WSP_STREAM_REF`
6. `FLINK_EKS_SR_READY_REF`
7. `EMR_EKS_VIRTUAL_CLUSTER_ID`
8. `EMR_EKS_RELEASE_LABEL`
9. `EMR_EKS_EXECUTION_ROLE_ARN`
10. `READY_MESSAGE_FILTER`
11. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
12. `RTDL_CAUGHT_UP_LAG_MAX`
13. `WSP_MAX_INFLIGHT`
14. `WSP_RETRY_MAX_ATTEMPTS`
15. `WSP_RETRY_BACKOFF_MS`
16. `WSP_STOP_ON_NONRETRYABLE`
17. `IG_BASE_URL`
18. `IG_INGEST_PATH`
19. `DDB_IG_IDEMPOTENCY_TABLE`
20. `S3_EVIDENCE_BUCKET`
21. `S3_RUN_CONTROL_ROOT_PATTERN`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M6.P6 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry closure | `S0` | required handles + deterministic P5 dependency closure |
| Runtime activation precheck | `S1` | active runtime-path lane refs are queryable and aligned |
| Run-window progression closure | `S2` | non-zero run-window ingress progression with active stream refs |
| Lag/ambiguity/overhead stress windows | `S3` | lag threshold pass + ambiguity clear + overhead budget pass |
| Remediation + selective rerun | `S4` | blocker-specific closure evidence |
| P6 rollup + verdict | `S5` | deterministic verdict `ADVANCE_TO_P7` |

## 6) Stress Topology (M6.P6)
1. Component sequence:
   - `P6.A` entry and runtime-path checks,
   - `P6.B` active lane checks,
   - `P6.C` progression and lag closure,
   - `P6.D` rollup.
2. Plane sequence:
   - `stream_runtime_plane`,
   - `ingress_bridge_plane`,
   - `p6_rollup_plane`.
3. Integrated windows:
   - `m6p6_s3_steady_window`,
   - `m6p6_s3_burst_window`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M6P6-ST-S0` - Authority and entry-gate closure
Objective:
1. validate P6 authority, runtime-path pinning, and upstream P5 dependency closure.

Entry criteria:
1. latest successful M6 parent `S0` and P5 `S5` receipts are readable.
2. no unresolved planning decision exists for required handles.

Required inputs:
1. parent `M6-ST-S0` summary/register.
2. latest P5 verdict artifact (`ADVANCE_TO_P6`).
3. required handle packet in section `4`.

Execution steps:
1. enforce parent + P5 dependency continuity.
2. validate required P6 handles and placeholder guards.
3. validate exactly one active runtime path (`FLINK_RUNTIME_PATH_ACTIVE`) and allowed-path compatibility.
4. validate runtime-surface queryability for selected path.
5. emit stage findings, lane matrix, blocker register, summary, and decision log.

Fail-closed blocker mapping:
1. `M6P6-ST-B1`: missing/inconsistent required handle.
2. `M6P6-ST-B2`: invalid P5 dependency contract.
3. `M6P6-ST-B3`: runtime-path ambiguity or inactive path-surface mismatch.
4. `M6P6-ST-B11`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `15` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. rerun only `S0` for dependency/handle/path closure failures.
2. block `S1` until `S0` closes green.

Pass gate:
1. P5 dependency closure is valid.
2. single-active runtime-path checks pass.
3. `next_gate=M6P6_ST_S1_READY`.

### 7.2 `M6P6-ST-S1` - Runtime activation precheck
Objective:
1. verify stream-lane refs activate on pinned runtime path.

Entry criteria:
1. latest successful `S0` summary with `next_gate=M6P6_ST_S1_READY`.

Required inputs:
1. selected runtime path and path-specific lane refs.
2. cluster/virtual-cluster handles where applicable.
3. upstream run scope and message-filter handles.

Execution steps:
1. enforce S0 continuity and zero open blockers.
2. execute runtime-path-aware activation probes for WSP and SR_READY lanes.
3. require active-state contract for lane refs within activation window.
4. capture activation snapshots and control conformance surfaces.
5. emit S1 artifacts.

Fail-closed blocker mapping:
1. `M6P6-ST-B3`: lane refs not active on selected runtime path.
2. `M6P6-ST-B4`: runtime surface queryability failure.
3. `M6P6-ST-B11`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$8`.

Targeted rerun policy:
1. rerun `S1` after runtime activation remediations.
2. no progression to `S2` while refs remain inactive.

Pass gate:
1. required lane refs are active and run-scope aligned.
2. `next_gate=M6P6_ST_S2_READY`.

### 7.3 `M6P6-ST-S2` - Run-window progression closure
Objective:
1. prove active stream consumption produces non-zero run-window ingress progression.

Entry criteria:
1. latest successful `S1` summary with `next_gate=M6P6_ST_S2_READY`.

Required inputs:
1. active lane snapshots from `S1`.
2. IG idempotency table/read model.
3. run-window definition (`platform_run_id`, start timestamp).

Execution steps:
1. capture run-window scoped source emit counters.
2. capture run-window scoped ingress admissions (`IG` idempotency progression).
3. validate cross-surface progression continuity.
4. run in-runtime bridge probe if progression is zero.
5. emit progression snapshot and blocker register.

Fail-closed blocker mapping:
1. `M6P6-ST-B5`: no non-zero run-window ingress progression.
2. `M6P6-ST-B6`: control->stream->ingress continuity mismatch.
3. `M6P6-ST-B11`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$7`.

Targeted rerun policy:
1. rerun `S2` only for progression/continuity failures.
2. reopen `S1` when progression failure is caused by inactive refs.

Pass gate:
1. run-window progression is non-zero and continuity checks pass.
2. `next_gate=M6P6_ST_S3_READY`.

### 7.4 `M6P6-ST-S3` - Lag, ambiguity, and overhead stress windows
Objective:
1. validate lag threshold, ambiguity closure, and evidence-overhead posture under steady and burst windows.

Entry criteria:
1. latest successful `S2` summary with `next_gate=M6P6_ST_S3_READY`.

Required inputs:
1. progression evidence from `S2`.
2. lag threshold handle (`RTDL_CAUGHT_UP_LAG_MAX`).
3. overhead budget definitions (latency p95, bytes/event, write-rate).

Execution steps:
1. run steady window and compute lag from run-window admissions.
2. run burst window and recompute lag/error/latency surfaces.
3. verify unresolved publish ambiguity count is zero.
4. capture evidence-overhead budget metrics.
5. emit lag, ambiguity, overhead, and throughput snapshots.

Fail-closed blocker mapping:
1. `M6P6-ST-B7`: lag threshold breach or lag unavailable with active progression expectation.
2. `M6P6-ST-B8`: unresolved publish ambiguity.
3. `M6P6-ST-B9`: evidence-overhead budget breach.
4. `M6P6-ST-B11`: artifact publish/readback failure.

Runtime/cost budget:
1. max runtime: `55` minutes.
2. max spend: `$10`.

Targeted rerun policy:
1. rerun only failed window (`steady` or `burst`).
2. preserve before/after traces for each remediation decision.

Pass gate:
1. lag within threshold.
2. ambiguity register is clear.
3. overhead budget pass.
4. `next_gate=M6P6_ST_S4_READY`.

### 7.5 `M6P6-ST-S4` - Remediation and selective rerun closure
Objective:
1. remediate open P6 blockers with minimal rerun scope.

Entry criteria:
1. latest `S3` summary/register is readable.

Required inputs:
1. blocker register and failing window artifacts.
2. remediation decision log and owner mapping.
3. runtime path decision evidence if fallback is used.

Execution steps:
1. classify blockers by root cause: path activation, network bridge, lag model, ambiguity, overhead.
2. apply minimal corrective change per blocker class.
3. rerun only impacted stage windows.
4. verify blocker state transitions and emit closure receipts.
5. publish updated execution summary.

Fail-closed blocker mapping:
1. `M6P6-ST-B10`: remediation evidence inconsistent or not reproducible.
2. `M6P6-ST-B11`: artifact contract failure during rerun.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$4`.

Targeted rerun policy:
1. no broad rerun from S0 unless dependency drift is proven.
2. use narrowest window that closes each blocker.

Pass gate:
1. all open P6 blockers resolved or explicitly waived by user.
2. `next_gate=M6P6_ST_S5_READY`.

### 7.6 `M6P6-ST-S5` - P6 rollup and deterministic verdict
Objective:
1. publish deterministic P6 verdict for parent M6 orchestration.

Entry criteria:
1. latest successful `S4` summary with `next_gate=M6P6_ST_S5_READY`.
2. no unresolved non-waived blockers.

Required inputs:
1. stage summaries `S0..S4`.
2. latest blocker register and cost receipt.
3. decision log.

Execution steps:
1. aggregate evidence across all P6 states.
2. enforce verdict rule:
   - `ADVANCE_TO_P7` only when blocker-free,
   - else `HOLD_REMEDIATE`.
3. emit rollup matrix, verdict artifact, summary, and decision log.

Fail-closed blocker mapping:
1. `M6P6-ST-B10`: rollup/verdict inconsistency.
2. `M6P6-ST-B12`: artifact contract incompleteness.

Runtime/cost budget:
1. max runtime: `15` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. rerun S5 for aggregation-only defects.
2. reopen upstream states only when justified by causal evidence.

Pass gate:
1. deterministic verdict `ADVANCE_TO_P7`.
2. `next_gate=ADVANCE_TO_P7`.

## 8) Blocker Taxonomy (M6.P6)
1. `M6P6-ST-B1`: required handle missing/inconsistent.
2. `M6P6-ST-B2`: invalid P5 dependency or entry chain.
3. `M6P6-ST-B3`: runtime-path ambiguity/inactive lane refs.
4. `M6P6-ST-B4`: runtime surface queryability failure.
5. `M6P6-ST-B5`: zero run-window ingress progression.
6. `M6P6-ST-B6`: cross-surface continuity mismatch.
7. `M6P6-ST-B7`: lag threshold failure or unresolved lag measurement.
8. `M6P6-ST-B8`: unresolved publish ambiguity.
9. `M6P6-ST-B9`: evidence-overhead budget breach.
10. `M6P6-ST-B10`: remediation/rollup inconsistency.
11. `M6P6-ST-B11`: durable evidence publish/readback failure.
12. `M6P6-ST-B12`: artifact contract incomplete.

Any open `M6P6-ST-B*` blocks P6 closure and parent M6 `S2` progression.

## 9) Evidence Contract (M6.P6)
1. `m6p6_stagea_findings.json`
2. `m6p6_lane_matrix.json`
3. `m6p6_streaming_active_snapshot.json`
4. `m6p6_lag_posture_snapshot.json`
5. `m6p6_evidence_overhead_snapshot.json`
6. `m6p6_probe_latency_throughput_snapshot.json`
7. `m6p6_control_rail_conformance_snapshot.json`
8. `m6p6_secret_safety_snapshot.json`
9. `m6p6_cost_outcome_receipt.json`
10. `m6p6_blocker_register.json`
11. `m6p6_execution_summary.json`
12. `m6p6_decision_log.json`
13. `m6p6_gate_verdict.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M6.P6 stress authority created.
- [x] P6 handle packet and blocker taxonomy pinned.
- [x] Runtime-path and fallback posture explicitly documented.
- [x] P6 execution-grade runbook (`S0..S5`) pinned.
- [x] `M6P6-ST-S0` executed with blocker-free entry closure.
- [x] `M6P6-ST-S1..S3` executed with strict progression/lag semantics.
- [x] `M6P6-ST-S4` remediation lane closed (no-op, blocker-free).
- [x] `M6P6-ST-S5` verdict emitted as `ADVANCE_TO_P7`.

## 11) Immediate Next Actions
1. Preserve `M6.P6` closure receipts as dependency authority for parent `M6-ST-S2`.
2. Execute parent `M6-ST-S2` gate adjudication using P6 verdict `ADVANCE_TO_P7`.
3. After parent `S2` closure, execute `M6.P7` (`S0..S5`) and progress to parent `M6-ST-S3`.

## 12) Execution Progress
1. Planning authority created.
2. `M6P6-ST-S0` executed and passed:
   - `phase_execution_id=m6p6_stress_s0_20260304T015920Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S1_READY`,
   - `open_blockers=0`,
   - `runtime_path_active=EKS_FLINK_OPERATOR`,
   - `p5_dependency_phase_execution_id=m6p5_stress_s5_20260304T013452Z`.
3. `M6P6-ST-S1` executed and passed:
   - `phase_execution_id=m6p6_stress_s1_20260304T015926Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S2_READY`,
   - `open_blockers=0`,
   - `historical_m6e_execution_id=m6e_p6a_stream_entry_20260225T120522Z`,
   - `historical_m6f_execution_id=m6f_p6b_streaming_active_20260225T175655Z`.
4. `M6P6-ST-S2` executed and passed:
   - `phase_execution_id=m6p6_stress_s2_20260304T015936Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S3_READY`,
   - `open_blockers=0`,
   - non-zero progression retained (`platform_run_id=platform_20260223T184232Z`).
5. `M6P6-ST-S3` executed and passed:
   - `phase_execution_id=m6p6_stress_s3_20260304T015942Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S4_READY`,
   - `open_blockers=0`,
   - lag/ambiguity/overhead closure remained green.
6. `M6P6-ST-S4` executed and passed:
   - `phase_execution_id=m6p6_stress_s4_20260304T015951Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S5_READY`,
   - `open_blockers=0`,
   - remediation mode `NO_OP`.
7. `M6P6-ST-S5` executed and passed:
   - `phase_execution_id=m6p6_stress_s5_20260304T015956Z`,
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P7`,
   - `next_gate=ADVANCE_TO_P7`,
   - `open_blockers=0`,
   - `historical_m6g_execution_id=m6g_p6c_gate_rollup_20260225T181523Z`.
8. Authoritative evidence root:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p6_stress_s*_20260304T0159*/stress/`.
9. Targeted assurance rerun of `M6P6-ST-S1` (post-closure stability check):
   - `phase_execution_id=m6p6_stress_s1_20260304T020238Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S2_READY`,
   - `open_blockers=0`,
   - decision: no prior-cycle blockers existed (`S0..S5` all closed), so no remediation was required.
10. Targeted assurance rerun of `M6P6-ST-S2` (progression-lane stability check):
   - `phase_execution_id=m6p6_stress_s2_20260304T020405Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S3_READY`,
   - `open_blockers=0`,
   - `s1_dependency_phase_execution_id=m6p6_stress_s1_20260304T020238Z`,
   - decision: no prior-cycle blockers existed, so rerun was executed as assurance-only with no remediation actions.
11. Targeted assurance rerun of `M6P6-ST-S3` (lag/ambiguity/overhead stability check):
   - `phase_execution_id=m6p6_stress_s3_20260304T020529Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S4_READY`,
   - `open_blockers=0`,
   - `s2_dependency_phase_execution_id=m6p6_stress_s2_20260304T020405Z`,
   - decision: no prior-cycle blockers existed, so rerun was executed as assurance-only with no remediation actions.
12. Targeted assurance rerun of `M6P6-ST-S4` (remediation-lane stability check):
   - `phase_execution_id=m6p6_stress_s4_20260304T020649Z`,
   - `overall_pass=true`,
   - `next_gate=M6P6_ST_S5_READY`,
   - `open_blockers=0`,
   - `remediation_mode=NO_OP`,
   - `s3_dependency_phase_execution_id=m6p6_stress_s3_20260304T020529Z`,
   - decision: no prior-cycle blockers existed, so rerun was executed as assurance-only with no remediation actions.
13. Targeted assurance rerun of `M6P6-ST-S5` (deterministic verdict stability check):
   - `phase_execution_id=m6p6_stress_s5_20260304T020815Z`,
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P7`,
   - `next_gate=ADVANCE_TO_P7`,
   - `open_blockers=0`,
   - `s4_dependency_phase_execution_id=m6p6_stress_s4_20260304T020649Z`,
   - decision: no prior-cycle blockers existed, so rerun was executed as assurance-only with no remediation actions.
