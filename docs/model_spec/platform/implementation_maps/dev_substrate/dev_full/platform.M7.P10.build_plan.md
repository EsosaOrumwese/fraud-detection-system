# Dev Substrate Deep Plan - M7.P10 (P10 CASE_LABELS_COMMITTED)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P10 CASE_LABELS_COMMITTED`.

`P10` must prove:
1. case-trigger bridge admits only run-scoped case-trigger surfaces.
2. `CM` commits case records deterministically.
3. `LS` commits labels via explicit writer-boundary semantics with single-writer posture.
4. P10 rollup verdict is deterministic from component-level proofs.
5. `CaseTrigger/CM/LS` meet pinned throughput and latency budgets.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P10 CASE_LABELS_COMMITTED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P10 Scope
In scope:
1. case-label entry precheck and run continuity checks.
2. component execution/verification:
   - `CaseTrigger bridge`,
   - `CM`,
   - `LS`.
3. writer-boundary and single-writer guarantees for label commits.
4. P10 rollup matrix/blocker register/verdict.

Out of scope:
1. P8 RTDL core closure.
2. P9 decision-chain closure.
3. P11 obs/gov closure.

## 3) Anti-Lump Rule for P10
1. `CaseTrigger bridge`, `CM`, and `LS` are independently adjudicated lanes.
2. `LS` cannot be inferred green from CM results; writer-boundary proof is mandatory.
3. P10 cannot close while any case/label component is unresolved.

## 3.1) P10 Performance Contract (binding)
Each component lane must publish `*_performance_snapshot.json` for the lane run window and pass pinned numeric SLOs:
1. `CaseTrigger bridge`:
   - trigger throughput (`case_trigger_events_per_second`),
   - bridge latency (`case_trigger_bridge_latency_p95_ms`),
   - backlog/queue (`case_trigger_queue_depth`),
   - resource posture (`case_trigger_cpu_p95_pct`, `case_trigger_memory_p95_pct`),
   - stability (`case_trigger_error_rate_pct`).
2. `CM`:
   - case-write throughput (`cm_case_writes_per_second`),
   - case-write latency (`cm_case_write_latency_p95_ms`),
   - queue/backlog (`cm_queue_depth`),
   - resource posture (`cm_cpu_p95_pct`, `cm_memory_p95_pct`),
   - stability (`cm_error_rate_pct`).
3. `LS`:
   - label-write throughput (`ls_label_writes_per_second`),
   - writer-boundary commit latency (`ls_commit_latency_p95_ms`),
   - writer wait/backpressure (`ls_writer_wait_seconds`),
   - resource posture (`ls_cpu_p95_pct`, `ls_memory_p95_pct`),
   - stability (`ls_error_rate_pct`).
4. Numeric thresholds are mandatory and must be pinned during `P10.A`; missing pins are fail-closed.

## 4) Work Breakdown

### P10.A Entry + Handle Closure
Goal:
1. close required handles and entry gates for case/label components.

Entry prerequisites (must already be green):
1. `P9.E` execution summary is green with:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P10`,
   - `next_gate=M7.I_READY`.
2. run scope (`platform_run_id`, `scenario_run_id`) matches upstream `P9.E` execution.

Required handle set for P10.A:
1. runtime path and scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `PHASE_RUNTIME_PATH_MODE`
2. component deployment/runtime handles:
   - `K8S_DEPLOY_CASE_TRIGGER`
   - `K8S_DEPLOY_CM`
   - `K8S_DEPLOY_LS`
   - `EKS_NAMESPACE_CASE_LABELS`
   - `ROLE_EKS_IRSA_CASE_LABELS`
3. data/evidence surfaces:
   - `FP_BUS_CASE_TRIGGERS_V1`
   - `FP_BUS_LABELS_EVENTS_V1`
   - `CASE_LABELS_EVIDENCE_PATH_PATTERN`
4. runtime state backends:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`.

Pinned P10 component SLO continuity check:
1. upstream `m7a_component_slo_profile.json` must contain:
   - `CaseTriggerBridge`,
   - `CM`,
   - `LS`.

Tasks:
1. verify `P9` verdict and run-scope continuity.
2. verify required handles for case-trigger bridge, CM, LS, and label store boundary.
3. verify SLO continuity for `CaseTriggerBridge/CM/LS`.
4. emit:
   - `p10a_entry_snapshot.json`
   - `p10a_blocker_register.json`
   - `p10a_component_slo_profile.json`
   - `p10a_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7l`.
2. pass upstream `P9.E` execution id via `upstream_m6d_execution`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=P10.B_READY`.

DoD:
- [x] P10 required-handle set is complete.
- [x] unresolved required handles are blocker-marked.
- [x] P10 entry snapshot is committed locally and durably.
- [x] per-component P10 performance SLO targets are pinned.
- [x] managed `P10.A` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=P10.B_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7l`
   - run id: `22425458650`
   - execution id: `m7l_p10a_entry_precheck_20260226T023945Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=P10.B_READY`.
3. Verification outcomes:
   - upstream `P9.E` continuity accepted from `m7k_p9e_rollup_20260226T023154Z`,
   - required handles resolved: `15/15`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - upstream SLO continuity for `CaseTriggerBridge/CM/LS` is present.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_tmp_run_22425458650/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7l_p10a_entry_precheck_20260226T023945Z/`.

### P10.B CaseTrigger Bridge Lane Closure
Goal:
1. close case-trigger bridge lane.

Tasks:
1. verify case-trigger input filtering is run-scoped.
2. verify trigger-to-CM bridge contract and delivery receipts.
3. verify duplicate-safe trigger semantics.
4. emit `p10b_case_trigger_snapshot.json`.

DoD:
- [ ] run-scoped case-trigger bridge evidence is present.
- [ ] duplicate-safe trigger semantics pass.
- [ ] CaseTrigger blocker set is empty.
- [ ] `p10b_case_trigger_performance_snapshot.json` is committed and within pinned SLO.

### P10.C CM Component Lane Closure
Goal:
1. close `CM` case-management lane.

Tasks:
1. execute `CM` case writes from run-scoped trigger inputs.
2. verify deterministic case identity and write commits.
3. verify append/readback posture for case evidence.
4. emit `p10c_cm_component_snapshot.json`.

DoD:
- [ ] deterministic case-write evidence is present.
- [ ] case append/readback checks pass.
- [ ] CM blocker set is empty.
- [ ] `p10c_cm_performance_snapshot.json` is committed and within pinned SLO.

### P10.D LS Component Lane Closure
Goal:
1. close `LS` writer-boundary lane.

Tasks:
1. execute `LS` label writes for run-scoped case outcomes.
2. verify writer-boundary protocol:
   - accept/reject outcomes,
   - commit semantics,
   - idempotency key usage.
3. verify single-writer posture for label append surface.
4. emit `p10d_ls_component_snapshot.json`.

DoD:
- [ ] LS writer-boundary protocol evidence is complete.
- [ ] single-writer checks pass.
- [ ] LS blocker set is empty.
- [ ] `p10d_ls_performance_snapshot.json` is committed and within pinned SLO.

### P10.E P10 Rollup + Verdict
Goal:
1. adjudicate P10 from `P10.B/P10.C/P10.D`.

Tasks:
1. build `p10e_case_labels_rollup_matrix.json`.
2. build `p10e_case_labels_blocker_register.json`.
3. emit `p10e_case_labels_verdict.json`.

DoD:
- [ ] rollup matrix and blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_M7`/`ADVANCE_TO_M8` or fail-closed hold as pinned by orchestration gate).

## 5) P10 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P10-V1-ENTRY` | validate P10 entry gates and required handles |
| `P10-V2-CASE-TRIGGER` | validate run-scoped trigger bridge + duplicate-safe semantics |
| `P10-V3-CM` | validate deterministic case writes + readback |
| `P10-V4-LS` | validate LS writer boundary + single-writer posture |
| `P10-V5-ROLLUP` | validate P10 rollup and deterministic verdict |

## 6) P10 Blocker Taxonomy
1. `M7P10-B1`: P10 entry/handle closure failure.
2. `M7P10-B2`: CaseTrigger bridge lane failure.
3. `M7P10-B3`: CM component lane failure.
4. `M7P10-B4`: LS component lane failure.
5. `M7P10-B5`: P10 rollup/verdict inconsistency.
6. `M7P10-B6`: missing P10 component performance SLO pins.
7. `M7P10-B7`: P10 component performance budget breach.

## 7) P10 Evidence Contract
1. `p10a_entry_snapshot.json`
2. `p10a_blocker_register.json`
3. `p10a_component_slo_profile.json`
4. `p10a_execution_summary.json`
5. `p10b_case_trigger_snapshot.json`
6. `p10c_cm_component_snapshot.json`
7. `p10d_ls_component_snapshot.json`
8. `p10e_case_labels_rollup_matrix.json`
9. `p10e_case_labels_blocker_register.json`
10. `p10e_case_labels_verdict.json`
11. `p10b_case_trigger_performance_snapshot.json`
12. `p10c_cm_performance_snapshot.json`
13. `p10d_ls_performance_snapshot.json`

## 8) Exit Rule for P10
`P10` can close only when:
1. all `M7P10-B*` blockers are clear,
2. all P10 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. M7 rollup remains blocked until `P8`, `P9`, and `P10` are all green.
