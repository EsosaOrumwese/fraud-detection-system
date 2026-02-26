# Dev Substrate Deep Plan - M7.P9 (P9 DECISION_CHAIN_COMMITTED)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P9 DECISION_CHAIN_COMMITTED`.

`P9` must prove:
1. `DF` commits run-scoped decisions deterministically.
2. `AL` commits actions/outcomes with duplicate-safe semantics.
3. `DLA` commits append-only audit truth with durable readback.
4. P9 rollup verdict is deterministic from component-level proofs.
5. `DF/AL/DLA` meet pinned throughput and latency budgets.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P9 DECISION_CHAIN_COMMITTED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P9 Scope
In scope:
1. decision-chain entry precheck and run continuity checks.
2. component execution/verification:
   - `DF`,
   - `AL`,
   - `DLA`.
3. P9 rollup matrix/blocker register/verdict.

Out of scope:
1. P8 RTDL core closure.
2. P10 case/labels closure.

## 3) Anti-Lump Rule for P9
1. `DF`, `AL`, and `DLA` are independently adjudicated lanes.
2. A green decision chain requires all three components to be green.
3. High-level throughput/latency summaries do not replace per-component commit proofs.

## 3.1) P9 Performance Contract (binding)
Each component lane must publish `*_performance_snapshot.json` for the lane run window and pass pinned numeric SLOs:
1. `DF`:
   - decision throughput (`df_decisions_per_second`),
   - decision latency (`df_decision_latency_p95_ms`),
   - backlog/lag (`df_input_lag_messages`),
   - resource posture (`df_cpu_p95_pct`, `df_memory_p95_pct`),
   - stability (`df_error_rate_pct`).
2. `AL`:
   - action throughput (`al_actions_per_second`),
   - action latency (`al_action_latency_p95_ms`),
   - retry/backpressure (`al_retry_ratio_pct`, `al_backpressure_seconds`),
   - resource posture (`al_cpu_p95_pct`, `al_memory_p95_pct`),
   - stability (`al_error_rate_pct`).
3. `DLA`:
   - audit append throughput (`dla_audit_appends_per_second`),
   - append latency (`dla_append_latency_p95_ms`),
   - backlog/queue depth (`dla_queue_depth`),
   - resource posture (`dla_cpu_p95_pct`, `dla_memory_p95_pct`),
   - stability (`dla_error_rate_pct`).
4. Numeric thresholds are mandatory and must be pinned during `P9.A`; missing pins are fail-closed.

## 4) Work Breakdown

### P9.A Entry + Handle Closure
Goal:
1. close required handles and entry gates for decision-chain components.

Entry prerequisites (must already be green):
1. `P8.E` execution summary is green with:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P9`,
   - `next_gate=M7.F_READY`.
2. run scope (`platform_run_id`, `scenario_run_id`) matches upstream `P8.E` execution.

Required handle set for P9.A:
1. runtime path and scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `PHASE_RUNTIME_PATH_MODE`
2. component deployment/runtime handles:
   - `K8S_DEPLOY_DF`
   - `K8S_DEPLOY_AL`
   - `K8S_DEPLOY_DLA`
   - `EKS_NAMESPACE_RTDL`
   - `ROLE_EKS_IRSA_DECISION_LANE`
3. data/evidence surfaces:
   - `FP_BUS_RTDL_V1`
   - `FP_BUS_AUDIT_V1`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
4. runtime state backends:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`.

Pinned P9 component SLO continuity check:
1. upstream `m7a_component_slo_profile.json` must contain:
   - `DF`,
   - `AL`,
   - `DLA`.

Tasks:
1. verify `P8.E` verdict and run-scope continuity.
2. verify required handle set above for `DF/AL/DLA`.
3. verify SLO continuity for `DF/AL/DLA`.
4. emit:
   - `p9a_entry_snapshot.json`
   - `p9a_blocker_register.json`
   - `p9a_component_slo_profile.json`
   - `p9a_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7g`.
2. pass upstream `P8.E` execution id via `upstream_m6d_execution`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M7.F_READY`.

DoD:
- [x] P9 required-handle set is complete.
- [x] unresolved required handles are blocker-marked.
- [x] P9 entry snapshot is committed locally and durably.
- [x] per-component P9 performance SLO targets are pinned.
- [x] managed `P9.A` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.F_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7g`
   - run id: `22423991265`
   - execution id: `m7g_p9a_entry_precheck_20260226T013600Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.F_READY`.
3. Verification outcomes:
   - upstream `P8.E` continuity accepted from `m7f_p8e_rollup_20260225T214307Z`,
   - required handles resolved `15/15`,
   - missing handles `0`,
   - placeholder handles `0`,
   - runtime path check passed (`FLINK_RUNTIME_PATH_ACTIVE` in `FLINK_RUNTIME_PATH_ALLOWED`),
   - upstream SLO continuity for `DF/AL/DLA` present.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22423991265_artifacts/p9a-entry-precheck-20260226T013600Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7g_p9a_entry_precheck_20260226T013600Z/`.

### P9.B DF Component Lane Closure
Goal:
1. close `DF` component lane.

Tasks:
1. execute `DF` with run-scoped inputs.
2. verify decision commit evidence and idempotency tuple integrity.
3. verify fail-closed behavior on invalid/missing policy inputs.
4. emit `p9b_df_component_snapshot.json`.

DoD:
- [ ] decision commits are run-scoped and deterministic.
- [ ] DF idempotency and fail-closed checks pass.
- [ ] DF blocker set is empty.
- [ ] `p9b_df_performance_snapshot.json` is committed and within pinned SLO.

### P9.C AL Component Lane Closure
Goal:
1. close `AL` component lane.

Tasks:
1. execute `AL` with run-scoped decision inputs.
2. verify action/outcome commit evidence.
3. verify duplicate-safe side-effect semantics.
4. emit `p9c_al_component_snapshot.json`.

DoD:
- [ ] action/outcome commits are run-scoped and deterministic.
- [ ] duplicate-safe side-effect checks pass.
- [ ] AL blocker set is empty.
- [ ] `p9c_al_performance_snapshot.json` is committed and within pinned SLO.

### P9.D DLA Component Lane Closure
Goal:
1. close `DLA` component lane.

Tasks:
1. execute/verify `DLA` append-only audit writes.
2. verify durable readback for run-scoped audit evidence.
3. verify append-only invariants (no in-place mutation).
4. emit `p9d_dla_component_snapshot.json`.

DoD:
- [ ] append-only audit evidence is committed and readable.
- [ ] append-only invariants pass.
- [ ] DLA blocker set is empty.
- [ ] `p9d_dla_performance_snapshot.json` is committed and within pinned SLO.

### P9.E P9 Rollup + Verdict
Goal:
1. adjudicate P9 from `P9.B/P9.C/P9.D`.

Tasks:
1. build `p9e_decision_chain_rollup_matrix.json`.
2. build `p9e_decision_chain_blocker_register.json`.
3. emit `p9e_decision_chain_verdict.json`.

DoD:
- [ ] rollup matrix and blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_P10` or fail-closed hold).

## 5) P9 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P9-V1-ENTRY` | validate P9 entry gates and required handles |
| `P9-V2-DF` | validate DF decision commits + idempotency/fail-closed posture |
| `P9-V3-AL` | validate AL action/outcome commits + duplicate-safe side effects |
| `P9-V4-DLA` | validate DLA append-only audit evidence + readback |
| `P9-V5-ROLLUP` | validate P9 rollup and deterministic verdict |

## 6) P9 Blocker Taxonomy
1. `M7P9-B1`: P9 entry/handle closure failure.
2. `M7P9-B2`: DF component lane failure.
3. `M7P9-B3`: AL component lane failure.
4. `M7P9-B4`: DLA component lane failure.
5. `M7P9-B5`: P9 rollup/verdict inconsistency.
6. `M7P9-B6`: missing P9 component performance SLO pins.
7. `M7P9-B7`: P9 component performance budget breach.

## 7) P9 Evidence Contract
1. `p9a_entry_snapshot.json`
2. `p9a_blocker_register.json`
3. `p9a_component_slo_profile.json`
4. `p9a_execution_summary.json`
5. `p9b_df_component_snapshot.json`
6. `p9c_al_component_snapshot.json`
7. `p9d_dla_component_snapshot.json`
8. `p9e_decision_chain_rollup_matrix.json`
9. `p9e_decision_chain_blocker_register.json`
10. `p9e_decision_chain_verdict.json`
11. `p9b_df_performance_snapshot.json`
12. `p9c_al_performance_snapshot.json`
13. `p9d_dla_performance_snapshot.json`

## 8) Exit Rule for P9
`P9` can close only when:
1. all `M7P9-B*` blockers are clear,
2. all P9 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. `P10` is blocked until `P9` verdict is `ADVANCE_TO_P10`.
