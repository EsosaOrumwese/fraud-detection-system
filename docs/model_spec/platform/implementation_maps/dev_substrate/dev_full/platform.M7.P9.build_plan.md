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

## 3.2) P9 Throughput Certification Plan (deferred post-M7)
1. `throughput_gate_mode=waived_low_sample` is provisional evidence, not final throughput proof.
2. `P9` functional closure is allowed with waived-low-sample posture when all non-throughput gates are green.
3. Non-waived throughput certification remains mandatory as a post-`M7` non-soak lane before any production-scale throughput claim.
4. Certification profile follows registry pins:
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR=134000000`,
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND=37223`,
   - `THROUGHPUT_CERT_WINDOW_MINUTES=60`.
5. Deferred tracking key for this phase: `M7P9-D8` (deferred certification item, not a functional-closure blocker).

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

Entry prerequisites:
1. `P9.A` execution summary is green with:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.F_READY`.
2. run scope (`platform_run_id`, `scenario_run_id`) matches upstream `P9.A` execution.

Required handle set for P9.B:
1. runtime scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
2. component/runtime identity:
   - `K8S_DEPLOY_DF`
   - `EKS_NAMESPACE_RTDL`
   - `ROLE_EKS_IRSA_DECISION_LANE`
3. data/evidence surfaces:
   - `FP_BUS_RTDL_V1`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
4. state backends:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`.

Tasks:
1. verify upstream `P9.A` continuity and run-scope match.
2. verify required handle set above for `DF`.
3. verify run-scoped ingest basis evidence is readable.
4. emit decision-lane component proof:
   - `df_component_proof.json`.
5. emit:
   - `p9b_df_component_snapshot.json`
   - `p9b_df_blocker_register.json`
   - `p9b_df_performance_snapshot.json`
   - `p9b_df_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7h`.
2. pass upstream `P9.A` execution id via `upstream_m6d_execution`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M7.G_READY`.

DoD:
- [x] decision commits are run-scoped and deterministic.
- [x] DF idempotency and fail-closed checks pass.
- [x] DF blocker set is empty.
- [x] `p9b_df_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P9.B` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.G_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7h`
   - run id: `22424352180`
   - execution id: `m7h_p9b_df_component_20260226T015122Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.G_READY`.
3. Verification outcomes:
   - upstream `P9.A` continuity accepted from `m7g_p9a_entry_precheck_20260226T013600Z`,
   - required handles resolved with no missing/placeholder values,
   - run-scoped ingest basis evidence readable,
   - decision-lane component proof published:
     - `evidence/runs/platform_20260223T184232Z/decision_lane/df_component_proof.json`.
4. Performance posture:
   - low-sample guarded mode applied (`total_receipts=18`),
   - throughput assertion waived (`<200` sample),
   - lag/error gate posture passed.
5. Certification posture:
   - status is provisional for throughput; post-`M7` non-waived certification remains required (`M7P9-D8`).
6. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22424352180_artifacts/p9-component-m7h-20260226T015122Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7h_p9b_df_component_20260226T015122Z/`.

### P9.C AL Component Lane Closure
Goal:
1. close `AL` component lane.

Entry prerequisites:
1. `P9.B` execution summary is green with:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.G_READY`.
2. run scope (`platform_run_id`, `scenario_run_id`) matches upstream `P9.B` execution.
3. upstream proof continuity:
   - `df_component_proof.json` exists under decision-lane run prefix.

Required handle set for P9.C:
1. runtime scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
2. component/runtime identity:
   - `K8S_DEPLOY_AL`
   - `EKS_NAMESPACE_RTDL`
   - `ROLE_EKS_IRSA_DECISION_LANE`
3. data/evidence surfaces:
   - `FP_BUS_RTDL_V1`
   - `FP_BUS_AUDIT_V1`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
4. state backends:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`.

Tasks:
1. verify upstream `P9.B` continuity and run-scope match.
2. verify required handle set above for `AL`.
3. verify `df_component_proof.json` dependency is present.
4. emit decision-lane component proof:
   - `al_component_proof.json`.
5. emit:
   - `p9c_al_component_snapshot.json`
   - `p9c_al_blocker_register.json`
   - `p9c_al_performance_snapshot.json`
   - `p9c_al_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7i`.
2. pass upstream `P9.B` execution id via `upstream_m6g_execution`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M7.H_READY`.

DoD:
- [x] action/outcome commits are run-scoped and deterministic.
- [x] duplicate-safe side-effect checks pass.
- [x] AL blocker set is empty.
- [x] `p9c_al_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P9.C` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.H_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7i`
   - run id: `22424410762`
   - execution id: `m7i_p9c_al_component_20260226T015350Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.H_READY`.
3. Verification outcomes:
   - upstream `P9.B` continuity accepted from `m7h_p9b_df_component_20260226T015122Z`,
   - required handles resolved with no missing/placeholder values,
   - upstream `df_component_proof.json` dependency present,
   - decision-lane AL proof published:
     - `evidence/runs/platform_20260223T184232Z/decision_lane/al_component_proof.json`.
4. Performance posture:
   - low-sample guarded mode applied (`total_receipts=18`),
   - throughput assertion waived (`<200` sample),
   - lag/error/retry gate posture passed.
5. Certification posture:
   - status is provisional for throughput; post-`M7` non-waived certification remains required (`M7P9-D8`).
6. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22424410762_artifacts/p9-component-m7i-20260226T015350Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7i_p9c_al_component_20260226T015350Z/`.

### P9.D DLA Component Lane Closure
Goal:
1. close `DLA` component lane.

Entry prerequisites:
1. `P9.C` execution summary is green with:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.H_READY`.
2. run scope (`platform_run_id`, `scenario_run_id`) matches upstream `P9.C` execution.
3. upstream proof continuity:
   - `df_component_proof.json` and `al_component_proof.json` exist under decision-lane run prefix.

Required handle set for P9.D:
1. runtime scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
2. component/runtime identity:
   - `K8S_DEPLOY_DLA`
   - `EKS_NAMESPACE_RTDL`
   - `ROLE_EKS_IRSA_DECISION_LANE`
3. data/evidence surfaces:
   - `FP_BUS_AUDIT_V1`
   - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
4. state backends:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`.

Tasks:
1. verify upstream `P9.C` continuity and run-scope match.
2. verify required handle set above for `DLA`.
3. verify `df_component_proof.json` + `al_component_proof.json` dependencies are present.
4. execute append-only audit probe write/readback:
   - `audit_append_probe_<execution_id>.json` under decision-lane run prefix.
5. emit decision-lane component proof:
   - `dla_component_proof.json`.
6. emit:
   - `p9d_dla_component_snapshot.json`
   - `p9d_dla_blocker_register.json`
   - `p9d_dla_performance_snapshot.json`
   - `p9d_dla_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7j`.
2. pass upstream `P9.C` execution id via `upstream_m6h_execution`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=P9.E_READY`.

DoD:
- [x] append-only audit evidence is committed and readable.
- [x] append-only invariants pass.
- [x] DLA blocker set is empty.
- [x] `p9d_dla_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P9.D` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=P9.E_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7j`
   - run id: `22424458740`
   - execution id: `m7j_p9d_dla_component_20260226T015553Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=P9.E_READY`.
3. Verification outcomes:
   - upstream `P9.C` continuity accepted from `m7i_p9c_al_component_20260226T015350Z`,
   - required handles resolved with no missing/placeholder values,
   - upstream proof chain dependencies present:
     - `df_component_proof.json`
     - `al_component_proof.json`
   - append-only audit probe write/readback passed:
     - `audit_append_probe_m7j_p9d_dla_component_20260226T015553Z.json`
   - decision-lane DLA proof published:
     - `evidence/runs/platform_20260223T184232Z/decision_lane/dla_component_proof.json`.
4. Performance posture:
   - low-sample guarded mode applied (`total_receipts=18`),
   - throughput assertion waived (`<200` sample),
   - lag/error gate posture passed.
5. Certification posture:
   - status is provisional for throughput; post-`M7` non-waived certification remains required (`M7P9-D8`).
6. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22424458740_artifacts/p9-component-m7j-20260226T015553Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7j_p9d_dla_component_20260226T015553Z/`.

### P9.E P9 Rollup + Verdict
Goal:
1. adjudicate P9 from `P9.B/P9.C/P9.D`.

Entry prerequisites:
1. `P9.B` execution summary is green with `next_gate=M7.G_READY`.
2. `P9.C` execution summary is green with `next_gate=M7.H_READY`.
3. `P9.D` execution summary is green with `next_gate=P9.E_READY`.
4. run scope (`platform_run_id`, `scenario_run_id`) matches across all upstream P9 component lanes.

Required handle set for P9.E:
1. `DECISION_LANE_EVIDENCE_PATH_PATTERN`
2. `S3_EVIDENCE_URI_PATTERN`

Tasks:
1. validate upstream summaries and blocker registers for:
   - `P9.B` (`p9b_df_execution_summary.json`, `p9b_df_blocker_register.json`),
   - `P9.C` (`p9c_al_execution_summary.json`, `p9c_al_blocker_register.json`),
   - `P9.D` (`p9d_dla_execution_summary.json`, `p9d_dla_blocker_register.json`).
2. verify proof triplet exists under `DECISION_LANE_EVIDENCE_PATH_PATTERN`:
   - `df_component_proof.json`,
   - `al_component_proof.json`,
   - `dla_component_proof.json`.
3. build `p9e_decision_chain_rollup_matrix.json`.
4. build `p9e_decision_chain_blocker_register.json`.
5. emit `p9e_decision_chain_verdict.json`.
6. emit `p9e_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7k`.
2. pass upstream execution ids:
   - `upstream_m6d_execution = <p9b_execution_id>`,
   - `upstream_m6g_execution = <p9c_execution_id>`,
   - `upstream_m6h_execution = <p9d_execution_id>`.
3. require deterministic success gate:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P10`,
   - `next_gate=M7.I_READY`.

DoD:
- [x] rollup matrix and blocker register committed.
- [x] deterministic verdict committed (`ADVANCE_TO_P10` or fail-closed hold).
- [x] managed `P9.E` run is green (`overall_pass=true`, `phase_verdict=ADVANCE_TO_P10`, `next_gate=M7.I_READY`).

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7k`
   - run id: `22425281848`
   - execution id: `m7k_p9e_rollup_20260226T023154Z`.
2. Result:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P10`,
   - `blocker_count=0`,
   - `next_gate=M7.I_READY`.
3. Verification outcomes:
   - upstream posture checks pass for `P9.B/P9.C/P9.D`,
   - decision-lane proof triplet exists (`df_component_proof.json`, `al_component_proof.json`, `dla_component_proof.json`),
   - rollup artifacts committed locally and durably.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_tmp_run_22425281848/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7k_p9e_rollup_20260226T023154Z/`.

## 5) P9 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P9-V1-ENTRY` | validate P9 entry gates and required handles |
| `P9-V2-DF` | validate DF decision commits + idempotency/fail-closed posture |
| `P9-V3-AL` | validate AL action/outcome commits + duplicate-safe side effects |
| `P9-V4-DLA` | validate DLA append-only audit evidence + readback |
| `P9-V5-ROLLUP` | validate P9 rollup and deterministic verdict |

## 6) P9 Blocker and Deferred Taxonomy
1. `M7P9-B1`: P9 entry/handle closure failure.
2. `M7P9-B2`: DF component lane failure.
3. `M7P9-B3`: AL component lane failure.
4. `M7P9-B4`: DLA component lane failure.
5. `M7P9-B5`: P9 rollup/verdict inconsistency.
6. `M7P9-B6`: missing P9 component performance SLO pins.
7. `M7P9-B7`: P9 component performance budget breach.
8. `M7P9-D8`: post-M7 throughput certification pending (deferred item; non-blocking for P9 functional closure).

## 7) P9 Evidence Contract
1. `p9a_entry_snapshot.json`
2. `p9a_blocker_register.json`
3. `p9a_component_slo_profile.json`
4. `p9a_execution_summary.json`
5. `p9b_df_component_snapshot.json`
6. `p9b_df_blocker_register.json`
7. `p9b_df_execution_summary.json`
8. `p9b_df_performance_snapshot.json`
9. `df_component_proof.json`
10. `p9c_al_component_snapshot.json`
11. `p9c_al_blocker_register.json`
12. `p9c_al_execution_summary.json`
13. `p9c_al_performance_snapshot.json`
14. `al_component_proof.json`
15. `p9d_dla_component_snapshot.json`
16. `p9d_dla_blocker_register.json`
17. `p9d_dla_execution_summary.json`
18. `p9d_dla_performance_snapshot.json`
19. `audit_append_probe_<execution_id>.json`
20. `dla_component_proof.json`
21. `p9e_decision_chain_rollup_matrix.json`
22. `p9e_decision_chain_blocker_register.json`
23. `p9e_decision_chain_verdict.json`

## 8) Exit Rule for P9
`P9` can close only when:
1. all `M7P9-B*` blockers are clear,
2. all P9 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent,
5. if throughput posture is `waived_low_sample`, deferred item `M7P9-D8` is recorded for post-M7 non-soak certification.

Transition:
1. `P10` is blocked until `P9` verdict is `ADVANCE_TO_P10`.
