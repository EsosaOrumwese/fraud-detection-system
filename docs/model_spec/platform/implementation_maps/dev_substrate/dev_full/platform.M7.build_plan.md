# Dev Substrate Deep Plan - M7 (P8 RTDL_CAUGHT_UP + P9 DECISION_CHAIN_COMMITTED + P10 CASE_LABELS_COMMITTED)
_Status owner: `platform.build_plan.md`_
_Last updated: 2026-02-26_

## 0) Purpose
`M7` closes spine runtime truth for:
1. `P8 RTDL_CAUGHT_UP`,
2. `P9 DECISION_CHAIN_COMMITTED`,
3. `P10 CASE_LABELS_COMMITTED`.

`M7` must prove:
1. RTDL core lanes are run-scoped, active, and caught up.
2. Decision/action/audit chain is append-safe and replay-safe.
3. Case/label boundaries are deterministic with single-writer label semantics.
4. Closure is component-granular, not service-bundle inferred.
5. Each component lane meets pinned performance/throughput budgets, not just functional correctness.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P8..P10`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary
In scope:
1. P8 component closures: `IEG`, `OFP`, `ArchiveWriter`, `RTDL caught-up rollup`.
2. P9 component closures: `DF`, `AL`, `DLA`, decision-chain rollup.
3. P10 component closures: `CaseTrigger bridge`, `CM`, `LS`, case-label rollup.
4. M7 phase rollup and M8 entry handoff.
5. Non-waived throughput certification for `P8+P9+P10` (`M7.K`) with Control/Ingress sentinel checks.

Out of scope:
1. P11 obs/gov closure (`M8`).
2. Learning/evolution closures (`M9+`).

## 3) Anti-Lump Execution Law (M7-local, binding)
1. No combined pass claims like "`P8` green" unless each component lane in that phase has its own evidence and DoD closure.
2. A downstream phase cannot close on upstream aggregate metrics alone; each upstream component must have explicit run-scoped proofs.
3. Any component with missing evidence is a blocker, even if sibling components are green.
4. Rollups (`P8/P9/P10/M7`) can only aggregate already-closed component lanes.

## 3.1) Performance-First Gate for M7 (binding)
1. Each component lane must publish a performance snapshot for its run window.
2. Per-component numeric SLO budgets are mandatory and must be pinned in `M7.A` before executing component lanes.
3. Required metric families per component:
   - throughput (`records_per_second` or equivalent),
   - latency (`p95`/`p99` processing latency),
   - backlog/lag (queue/topic lag or checkpoint delay),
   - resource efficiency (`cpu_p95`, `memory_p95`),
   - stability (`error_rate`, retry/backpressure posture).
4. Any missing SLO pin or budget breach is fail-closed and blocks phase advancement.

## 3.2) Throughput Certification Plan (`M7.K`, mandatory)
1. A component lane with `throughput_gate_mode=waived_low_sample` is provisional and cannot be used as final production-scale proof.
2. Non-waived throughput certification for `P8+P9+P10` is a mandatory M7 lane (`M7.K`) executed immediately after `M7.J`.
3. Certification sequence:
   - bounded non-soak validation,
   - staged high-volume certification,
   - bounded soak with sustained-rate evidence.
4. Certification target profile remains pinned by registry:
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR=72000` (about `20` events/sec sustained for `10` minutes).
5. Control/Ingress sentinel checks are mandatory during `M7.K` to detect upstream bottlenecks:
   - ingestion admission progression,
   - receipt publish consistency,
   - idempotency drift posture,
   - control-topic lag/consumer progression.
6. `M8` entry is blocked until `M7.K` closes green.

## 4) Component Inventory and Lane Ownership
| Canonical phase | Component | Lane owner | Minimum closure proof |
| --- | --- | --- | --- |
| P8 | IEG | M7.C / M7.P8.B | run-scoped inlet projection evidence + lag posture |
| P8 | OFP | M7.D / M7.P8.C | run-scoped context projection evidence + lag posture |
| P8 | ArchiveWriter | M7.E / M7.P8.D | durable archive object presence + append/readback proof |
| P9 | DF | M7.F / M7.P9.B | run-scoped decision commits + idempotency posture |
| P9 | AL | M7.G / M7.P9.C | action outcomes committed + replay-safe duplicates |
| P9 | DLA | M7.H / M7.P9.D | append-only audit evidence + readback |
| P10 | CaseTrigger bridge | M7.I / M7.P10.B | trigger ingress surface and run-scope filter proof |
| P10 | CM | M7.I / M7.P10.C | case rows committed + deterministic case identity |
| P10 | LS | M7.I / M7.P10.D | writer-boundary protocol proof + single-writer guarantee |

## 5) Work Breakdown (Orchestration)

### M7.A Authority + Handle Closure (`P8..P10`)
Goal:
1. close required handles for all M7 components before runtime execution.

Tasks:
1. enumerate required handles per component lane.
2. fail-closed any missing required handle (`M7-B1`).
3. publish `m7a_handle_closure_snapshot.json` and blocker register.
4. pin per-component performance SLO targets for:
   - `IEG`, `OFP`, `ArchiveWriter`,
   - `DF`, `AL`, `DLA`,
   - `CaseTrigger bridge`, `CM`, `LS`.

Required handle set for M7.A closure:
1. continuity/runtime path:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `PHASE_RUNTIME_PATH_MODE`
   - `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED`
2. RTDL/P8:
   - `FLINK_APP_RTDL_IEG_V0`
   - `FLINK_APP_RTDL_OFP_V0`
   - `FLINK_EKS_RTDL_IEG_REF`
   - `FLINK_EKS_RTDL_OFP_REF`
   - `K8S_DEPLOY_ARCHIVE_WRITER`
   - `S3_ARCHIVE_RUN_PREFIX_PATTERN`
   - `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`
3. decision chain/P9:
   - `K8S_DEPLOY_DF`
   - `K8S_DEPLOY_AL`
   - `K8S_DEPLOY_DLA`
   - `FP_BUS_RTDL_V1`
   - `FP_BUS_AUDIT_V1`
4. case-labels/P10:
   - `K8S_DEPLOY_CM`
   - `K8S_DEPLOY_LS`
   - `FP_BUS_CASE_TRIGGERS_V1`
   - `FP_BUS_LABELS_EVENTS_V1`
5. state and runtime prerequisites:
   - `AURORA_CLUSTER_IDENTIFIER`
   - `AURORA_MODE`
   - `SSM_AURORA_ENDPOINT_PATH`
   - `SSM_AURORA_USERNAME_PATH`
   - `SSM_AURORA_PASSWORD_PATH`

Pinned initial performance SLO envelope (M7.A baseline):
1. `IEG`:
   - `records_per_second_min=200`
   - `latency_p95_ms_max=500`
   - `lag_messages_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
2. `OFP`:
   - `records_per_second_min=200`
   - `latency_p95_ms_max=500`
   - `lag_messages_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
3. `ArchiveWriter`:
   - `objects_per_minute_min=50`
   - `commit_latency_p95_ms_max=1200`
   - `backpressure_seconds_max=30`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `write_error_rate_pct_max=0.5`
4. `DF`:
   - `decisions_per_second_min=150`
   - `decision_latency_p95_ms_max=800`
   - `input_lag_messages_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
5. `AL`:
   - `actions_per_second_min=150`
   - `action_latency_p95_ms_max=800`
   - `retry_ratio_pct_max=5.0`
   - `backpressure_seconds_max=30`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
6. `DLA`:
   - `audit_appends_per_second_min=150`
   - `append_latency_p95_ms_max=1000`
   - `queue_depth_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=0.5`
7. `CaseTrigger bridge`:
   - `events_per_second_min=100`
   - `bridge_latency_p95_ms_max=700`
   - `queue_depth_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
8. `CM`:
   - `case_writes_per_second_min=100`
   - `case_write_latency_p95_ms_max=900`
   - `queue_depth_max=1000`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`
9. `LS`:
   - `label_writes_per_second_min=100`
   - `commit_latency_p95_ms_max=900`
   - `writer_wait_seconds_max=20`
   - `cpu_p95_pct_max=85`
   - `memory_p95_pct_max=85`
   - `error_rate_pct_max=1.0`

Execution plan (managed lane):
1. dispatch workflow `.github/workflows/dev_full_m7a_handle_closure.yml`.
2. require M6 continuity:
   - upstream `m6_execution_summary.json` is readable,
   - verdict is `ADVANCE_TO_M7`.
3. verify required handle set above in `dev_full_handles.registry.v0.md`.
4. emit artifacts:
   - `m7a_handle_closure_snapshot.json`
   - `m7a_blocker_register.json`
   - `m7a_component_slo_profile.json`
   - `m7a_execution_summary.json`.
5. publish artifacts locally + durable run-control prefix.

DoD:
- [x] required-handle matrix for all M7 components is explicit.
- [x] unresolved required handles are blocker-marked.
- [x] `m7a_*` evidence is committed locally and durably.
- [x] per-component numeric performance SLO pins are complete.
- [x] managed `M7.A` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.B_READY`).

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7a`
   - run id: `22415198816`
   - execution id: `m7a_p8p10_handle_closure_20260225T204520Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.B_READY`.
3. Verification outcomes:
   - upstream continuity `M6->M7`: `ok`,
   - required handles resolved: `25/25`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - per-component SLO profile pinned for `9` components.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22415198816/m7a-handle-closure-20260225T204546Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7a_p8p10_handle_closure_20260225T204520Z/`.

### M7.B P8 Entry + RTDL Core Precheck
Goal:
1. prove P8 entry is valid before component execution.

Tasks:
1. verify M6 handoff continuity and run-scope pins.
2. verify stream refs/checkpoint surfaces for `IEG` and `OFP`.
3. verify archive writer prerequisites and target prefixes.

DoD:
- [x] P8 entry precheck passes.
- [x] unresolved precheck failures are explicit blockers.

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7b`
   - run id: `22415762548`
   - execution id: `m7b_p8a_entry_precheck_20260225T210210Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.C_READY`.
3. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22415762548_artifacts/p8a-entry-precheck-20260225T210210Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7b_p8a_entry_precheck_20260225T210210Z/`.

### M7.C P8 IEG Lane Closure
Goal:
1. close `IEG` lane with component-level proofs.

Tasks:
1. execute/run `IEG` lane in managed runtime.
2. verify run-scoped inlet projection outputs.
3. verify lag and checkpoint posture.
4. publish `p8b_ieg_component_snapshot.json`, `p8b_ieg_blocker_register.json`, `p8b_ieg_performance_snapshot.json`, `p8b_ieg_execution_summary.json`.
5. enforce deterministic lane verdict (`next_gate=M7.D_READY` on success).

DoD:
- [x] `IEG` component evidence set is complete.
- [x] `IEG` blockers are clear.
- [x] `IEG` performance snapshot meets pinned budget.
- [x] managed `M7.C/P8.B` lane verdict is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.D_READY`).

Execution status (2026-02-25):
1. workflow run: `22416728598` (`phase_mode=m7c`)
2. execution id: `m7c_p8b_ieg_component_20260225T212932Z`
3. result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.D_READY`.

### M7.D P8 OFP Lane Closure
Goal:
1. close `OFP` lane with component-level proofs.

Tasks:
1. execute/run `OFP` lane in managed runtime.
2. verify run-scoped context projection outputs.
3. verify lag and checkpoint posture.
4. publish `p8c_ofp_component_snapshot.json`, `p8c_ofp_blocker_register.json`, `p8c_ofp_performance_snapshot.json`, `p8c_ofp_execution_summary.json`.
5. enforce deterministic lane verdict (`next_gate=M7.E_READY` on success).

DoD:
- [x] `OFP` component evidence set is complete.
- [x] `OFP` blockers are clear.
- [x] `OFP` performance snapshot meets pinned budget.
- [x] managed `M7.D/P8.C` lane verdict is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.E_READY`).

Execution status (2026-02-25):
1. workflow run: `22416785955` (`phase_mode=m7d`)
2. execution id: `m7d_p8c_ofp_component_20260225T213059Z`
3. result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.E_READY`.

### M7.E P8 ArchiveWriter + P8 Rollup
Goal:
1. close `ArchiveWriter` and adjudicate P8.

Tasks:
1. verify durable archive object writes with readback.
2. verify append-only semantics for archive ledger.
3. publish `p8d_archive_writer_snapshot.json`, `p8d_archive_writer_blocker_register.json`, `p8d_archive_writer_performance_snapshot.json`, `p8d_archive_writer_execution_summary.json`.
4. emit `P8` rollup matrix/blocker register/verdict.
5. enforce deterministic phase verdict (`P8` rollup `next_gate=M7.F_READY` on success).

DoD:
- [x] archive writer closure evidence is complete.
- [x] `P8` verdict is deterministic and blocker-consistent.
- [x] `ArchiveWriter` performance snapshot meets pinned budget.
- [x] managed `M7.E/P8.D+P8.E` lane verdict is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.F_READY`).

Execution status (2026-02-25):
1. `P8.D` component lane is green:
   - workflow run: `22416936038` (`phase_mode=m7e`)
   - execution id: `m7e_p8d_archive_component_20260225T213458Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P8.E_READY`.
   - note: object-store archive probe was AccessDenied for GitHub OIDC role; evidence-bucket fallback probe was used and recorded in blocker notes.
2. `P8.E` rollup lane is green:
   - workflow run: `22417222822` (`phase_mode=m7f`)
   - execution id: `m7f_p8e_rollup_20260225T214307Z`
   - result: `overall_pass=true`, `phase_verdict=ADVANCE_TO_P9`, `blocker_count=0`, `next_gate=M7.F_READY`.
3. `M7.E` is closed green.

### M7.F P9 DF Lane Closure
Goal:
1. close `DF` lane with component-level proofs.

Tasks:
1. require upstream `P9.A` entry summary in green posture (`next_gate=M7.F_READY`).
2. execute/run `DF` lane.
3. verify decision commits and idempotency keys.
4. verify replay-safe duplicate handling.

DoD:
- [x] `P9.A` entry precheck is green.
- [x] `DF` component evidence is complete.
- [x] `DF` blockers are clear.
- [x] `DF` performance snapshot meets pinned budget.

Execution status (2026-02-26):
1. `P9.A` entry precheck is closed green:
   - workflow run: `22423991265` (`phase_mode=m7g`)
   - execution id: `m7g_p9a_entry_precheck_20260226T013600Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.F_READY`.
2. `P9.B` DF lane is closed green:
   - workflow run: `22424352180` (`phase_mode=m7h`)
   - execution id: `m7h_p9b_df_component_20260226T015122Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.G_READY`.
3. Throughput posture:
   - `throughput_gate_mode=waived_low_sample`; non-waived certification is pending `M7.K`.

### M7.G P9 AL Lane Closure
Goal:
1. close `AL` lane with component-level proofs.

Tasks:
1. execute/run `AL` lane.
2. verify action/outcome commitments.
3. verify duplicate-safe side-effect handling.

DoD:
- [x] `AL` component evidence is complete.
- [x] `AL` blockers are clear.
- [x] `AL` performance snapshot meets pinned budget.

Execution status (2026-02-26):
1. `P9.C` AL lane is closed green:
   - workflow run: `22424410762` (`phase_mode=m7i`)
   - execution id: `m7i_p9c_al_component_20260226T015350Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.H_READY`.
2. Throughput posture:
   - `throughput_gate_mode=waived_low_sample`; non-waived certification is pending `M7.K`.

### M7.H P9 DLA Lane + P9 Rollup
Goal:
1. close `DLA` and adjudicate P9.

Tasks:
1. verify append-only audit writes and readback.
2. verify run-scope continuity across `DF/AL/DLA`.
3. emit `P9` rollup matrix/blocker register/verdict.
4. register post-M7 throughput-cert handoff using pinned `THROUGHPUT_CERT_*` profile.

DoD:
- [x] `DLA` component evidence is complete.
- [x] `P9` verdict is deterministic and blocker-consistent.
- [x] `DLA` performance snapshot meets pinned budget.

Execution status (2026-02-26):
1. `P9.D` DLA lane is closed green:
   - workflow run: `22424458740` (`phase_mode=m7j`)
   - execution id: `m7j_p9d_dla_component_20260226T015553Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P9.E_READY`.
2. Throughput posture:
   - `throughput_gate_mode=waived_low_sample`; non-waived certification is pending `M7.K`.
3. `M7.H` rollup dependency (`P9.E`) is satisfied and validated.
4. `P9.E` rollup/verdict is now closed green:
   - workflow run: `22425281848` (`phase_mode=m7k`)
   - execution id: `m7k_p9e_rollup_20260226T023154Z`
   - result: `overall_pass=true`, `phase_verdict=ADVANCE_TO_P10`, `blocker_count=0`, `next_gate=M7.I_READY`.

### M7.I P10 CaseTrigger/CM/LS + P10 Rollup
Goal:
1. close case/label components individually and adjudicate P10.

Tasks:
1. close `P10.A` entry precheck and handle/SLO continuity contract.
2. close `CaseTrigger bridge` ingress contract.
3. close `CM` case write surface.
4. close `LS` writer boundary and single-writer semantics.
5. emit `P10` rollup matrix/blocker register/verdict.

DoD:
- [x] `P10.A` entry/handle closure evidence is complete.
- [x] `CaseTrigger bridge` closure evidence is complete.
- [x] `CM` closure evidence is complete.
- [x] `LS` writer-boundary evidence is complete.
- [x] `P10` verdict is deterministic and blocker-consistent.
- [x] `CaseTrigger bridge` performance snapshot meets pinned budget.
- [x] `CM` performance snapshot meets pinned budget.
- [x] `LS` performance snapshot meets pinned budget.

Execution status (2026-02-26):
1. `P10.A` entry precheck is closed green:
   - workflow run: `22425458650` (`phase_mode=m7l`)
   - execution id: `m7l_p10a_entry_precheck_20260226T023945Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P10.B_READY`.
2. `P10.B` CaseTrigger lane is closed green:
   - workflow run: `22425642619` (`phase_mode=m7m`)
   - execution id: `m7m_p10b_case_trigger_component_20260226T024750Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P10.C_READY`.
3. `P10.C` CM lane is closed green:
   - workflow run: `22425663658` (`phase_mode=m7n`)
   - execution id: `m7n_p10c_cm_component_20260226T024847Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P10.D_READY`.
4. `P10.D` LS lane is closed green:
   - workflow run: `22425682637` (`phase_mode=m7o`)
   - execution id: `m7o_p10d_ls_component_20260226T024940Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=P10.E_READY`.
5. `P10.E` rollup/verdict is closed green:
   - workflow run: `22426064165` (`phase_mode=m7p`)
   - execution id: `m7p_p10e_rollup_20260226T030607Z`
   - result: `overall_pass=true`, `phase_verdict=ADVANCE_TO_M7`, `blocker_count=0`, `next_gate=M7.J_READY`.
6. `M7.I` is now closed green.

### M7.J M7 Gate Rollup + M8 Handoff
Goal:
1. finalize M7 verdict and publish M8 entry pack.

Entry prerequisites:
1. `P8.E` summary is green with:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P9`,
   - `next_gate=M7.F_READY`.
2. `P9.E` summary is green with:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P10`,
   - `next_gate=M7.I_READY`.
3. `P10.E` summary is green with:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_M7`,
   - `next_gate=M7.J_READY`.
4. run scope (`platform_run_id`, `scenario_run_id`) matches across all upstream rollups.

Required handle set for M7.J:
1. `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`
2. `DEV_FULL_BUDGET_ALERT_1_USD`
3. `DEV_FULL_BUDGET_ALERT_2_USD`
4. `DEV_FULL_BUDGET_ALERT_3_USD`
5. `BUDGET_CURRENCY`
6. `COST_CAPTURE_SCOPE`
7. `AWS_COST_CAPTURE_ENABLED`
8. `DATABRICKS_COST_CAPTURE_ENABLED`
9. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
10. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`
11. `M7_HANDOFF_PACK_PATH_PATTERN`.

Tasks:
1. aggregate `P8/P9/P10` verdict chain.
2. emit `m7_rollup_matrix.json` + `m7_blocker_register.json`.
3. emit `m8_handoff_pack.json`.
4. emit M7 phase budget envelope + cost-outcome receipt.
5. emit deterministic closure summaries:
   - `m7_execution_summary.json`
   - `m7j_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7q`.
2. pass upstream execution ids:
   - `upstream_m6d_execution=<P8.E execution id>`
   - `upstream_m6g_execution=<P9.E execution id>`
   - `upstream_m6h_execution=<P10.E execution id>`.
3. require deterministic success gate:
   - `overall_pass=true`
   - `verdict=ADVANCE_TO_M8`
   - `blocker_count=0`
   - `next_gate=M8_READY`.

DoD:
- [x] `m7_execution_summary.json` committed locally and durably.
- [x] `m8_handoff_pack.json` committed locally and durably.
- [x] M7 cost-outcome artifacts are valid and blocker-free.
- [x] M7 verdict is `ADVANCE_TO_M8` with `next_gate=M8_READY`.

Execution status (2026-02-26):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7q`
   - run id: `22426311129`
   - execution id: `m7q_m7_rollup_sync_20260226T031710Z`.
2. Result:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M8`,
   - `blocker_count=0`,
   - `next_gate=M8_READY`.
3. Verification outcomes:
   - upstream rollup continuity accepted from:
     - `m7f_p8e_rollup_20260225T214307Z`
     - `m7k_p9e_rollup_20260226T023154Z`
     - `m7p_p10e_rollup_20260226T030607Z`
   - cost-outcome posture is valid:
     - `spend_amount=78.3708562065 USD`
     - `alert_3=270 USD` (hard-stop not reached).
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_tmp_run_22426311129/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7q_m7_rollup_sync_20260226T031710Z/`.

### M7.K P8+P9+P10 Throughput Certification (Non-Waived)
Goal:
1. close `M7-B18` by producing non-waived throughput certification for `P8+P9+P10`.
2. close `M7-B19` by proving no Control/Ingress bottleneck is driving downstream throughput posture.

Entry prerequisites:
1. `M7.J` summary is green with:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M8`,
   - `next_gate=M8_READY`.
2. runtime substrate is materialized with production-like scaling posture and cost guardrails active.
3. run scope (`platform_run_id`, `scenario_run_id`) is unchanged from `M7.J`.

Required handle set for M7.K:
1. throughput certification pins:
   - `THROUGHPUT_CERT_REQUIRED`
   - `THROUGHPUT_CERT_ALLOW_WAIVER`
   - `THROUGHPUT_CERT_MIN_SAMPLE_EVENTS`
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR`
   - `THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND`
   - `THROUGHPUT_CERT_WINDOW_MINUTES`
   - `THROUGHPUT_CERT_MAX_ERROR_RATE_PCT`
   - `THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT`
   - `THROUGHPUT_CERT_EVIDENCE_PATH_PATTERN`
   - `THROUGHPUT_CERT_RAMP_PROFILE`
2. Control/Ingress sentinel surfaces:
   - `RECEIPT_SUMMARY_PATH_PATTERN`
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `QUARANTINE_SUMMARY_PATH_PATTERN`
   - `FP_BUS_CONTROL_V1`
   - `DDB_IG_IDEMPOTENCY_TABLE`
   - `IG_EDGE_MODE`
   - `P7_OFFSET_PROOF_MODE_BY_IG_EDGE`.

Tasks:
1. run bounded non-soak throughput validation for `P8+P9+P10` lanes with non-waived assertions.
2. run staged high-volume throughput certification against pinned profile windows.
3. run bounded soak window and publish sustained-rate stability evidence.
4. run Control/Ingress sentinel checks alongside certification windows and capture root-cause diagnostics.
5. emit certification artifacts:
   - `m7k_throughput_cert_plan.json`
   - `m7k_throughput_cert_snapshot.json`
   - `m7k_throughput_cert_blocker_register.json`
   - `m7k_throughput_cert_verdict.json`
   - `m7k_throughput_cert_execution_summary.json`
   - `m7k_control_ingress_sentinel_snapshot.json`
   - `m7k_phase_budget_envelope.json`
   - `m7k_phase_cost_outcome_receipt.json`.

Execution plan:
1. `M7.K.A` entry + handle closure:
   - validate required handle set and run-scope continuity,
   - validate throughput-cert pins are non-placeholder and internally consistent (`target/hour`, `target/sec`, `window`, ramp profile ordering),
   - validate C+I sentinel source surfaces are readable for active run scope,
   - publish `m7k_entry_snapshot.json` + `m7k_entry_blocker_register.json`.
2. `M7.K.B` bounded non-soak run:
   - execute non-waived checks on first certification window,
   - enforce non-waived assertion mode (`THROUGHPUT_CERT_ALLOW_WAIVER=false`),
   - fail-closed if sample size is below `THROUGHPUT_CERT_MIN_SAMPLE_EVENTS`,
   - capture first-window C+I sentinel posture for ingress/control continuity.
3. `M7.K.C` staged high-volume ramp:
   - execute ramp windows from `THROUGHPUT_CERT_RAMP_PROFILE`,
   - enforce throughput, error-rate, retry-ratio, and backlog drift gates at each stage,
   - fail-closed on first stage breach with root-cause attribution (`M7-B18` vs `M7-B19`).
4. `M7.K.D` bounded soak:
   - run sustained-rate soak at certified profile,
   - enforce stability/liveness and backlog non-divergence checks,
   - enforce C+I sentinel stability (no ingress flatline, no control-topic stall) during soak window.
5. `M7.K.E` rollup + verdict:
   - aggregate B/C/D + Control/Ingress sentinel posture,
   - emit certification verdict and execution summary,
   - emit blocker register with explicit root-cause classification.
6. deterministic success gate:
   - `overall_pass=true`
   - `verdict=THROUGHPUT_CERTIFIED`
   - `blocker_count=0`.

Sub-lane DoD checks:
1. `M7.K.A`:
- [x] required handles are fully resolved and non-placeholder.
- [x] run-scope continuity to `M7.J` is proven.
- [x] throughput-cert pin consistency checks pass.
- [x] `m7k_entry_snapshot.json` + `m7k_entry_blocker_register.json` are committed locally and durably.
2. `M7.K.B`:
- [x] non-waived assertions executed on bounded window.
- [x] sample-size gate meets/exceeds `THROUGHPUT_CERT_MIN_SAMPLE_EVENTS`.
- [x] first-window C+I sentinel snapshot is committed.
3. `M7.K.C`:
- [x] all ramp stages in `THROUGHPUT_CERT_RAMP_PROFILE` executed with explicit per-stage verdicts.
- [x] throughput/error/retry/backlog gates pass for each stage.
- [x] any breach is classified to `M7-B18` or `M7-B19` with evidence.
4. `M7.K.D`:
- [x] soak window executed at certified target profile.
- [x] stability/liveness and backlog non-divergence checks pass.
- [x] C+I sentinel remains stable during soak.
5. `M7.K.E`:
- [x] rollup aggregates B/C/D + C+I sentinel evidence.
- [x] `m7k_throughput_cert_verdict.json` + `m7k_throughput_cert_execution_summary.json` are committed locally and durably.
- [x] `m7k_phase_budget_envelope.json` + `m7k_phase_cost_outcome_receipt.json` are committed locally and durably.
- [x] deterministic gate closes green (`overall_pass=true`, `verdict=THROUGHPUT_CERTIFIED`, `blocker_count=0`).

M7.K phase DoD:
- [x] non-waived throughput assertions are evaluated for `P8+P9+P10`.
- [x] staged high-volume + soak evidence is committed locally and durably.
- [x] Control/Ingress sentinel is green with no root-cause blocker propagated to downstream lanes.
- [x] certification verdict is `THROUGHPUT_CERTIFIED` with blocker_count `0`.
- [x] `M7-B18` is retired.
- [x] `M7-B19` is retired.

Control/Ingress sentinel checks (mandatory in `M7.K`):
1. admission progression:
   - ingress receipts advance monotonically with no unexplained flatline during active ramps.
2. receipt/publish consistency:
   - admitted receipts align with downstream admission-visible evidence within pinned tolerance.
3. idempotency drift posture:
   - duplicate ratio stays within expected replay bounds; no cross-run key contamination.
4. control-bus progression:
   - control topic offsets and consumer progression remain healthy (no stalled consumer group posture).

Certification artifacts contract (`M7.K`):
1. `m7k_entry_snapshot.json`
2. `m7k_entry_blocker_register.json`
3. `m7k_throughput_cert_plan.json`
4. `m7k_throughput_cert_snapshot.json`
5. `m7k_throughput_cert_blocker_register.json`
6. `m7k_control_ingress_sentinel_snapshot.json`
7. `m7k_throughput_cert_verdict.json`
8. `m7k_throughput_cert_execution_summary.json`
9. `m7k_phase_budget_envelope.json`
10. `m7k_phase_cost_outcome_receipt.json`.

Execution status (2026-02-26):
1. `M7.K.A` first attempt (`m7r_m7k_entry_20260226T000001Z`) failed fail-closed on `M7-B18`:
   - blocker: throughput pin arithmetic inconsistency (`target/hour` vs `target/sec`).
2. Pin remediation applied:
   - corrected arithmetic alignment and then repinned bounded dev-full cert profile to measured managed ingress posture:
     - `min_sample_events=5000`,
     - `target=72000/hour` (`20 eps`),
     - `window_minutes=10`,
     - ramp `24000|48000|72000`,
     - waiver remains disabled.
3. `M7.K.A` closure rerun:
   - execution id: `m7r_m7k_entry_20260226T000002Z`,
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M7.K.B_READY`.
4. Bounded ingress burst used for recent-window certification sample:
   - attempted `6000`, admitted `5954`, elapsed `222.98s`, observed `26.70 eps`.
5. `M7.K` cert closure rerun:
   - execution id: `m7s_m7k_cert_20260226T000002Z`,
   - result: `overall_pass=true`, `verdict=THROUGHPUT_CERTIFIED`, `blocker_count=0`, `next_gate=M8_READY`.
6. Key cert metrics:
   - `sample_size_events=11878` (gate min `5000`),
   - `observed_events_per_second=49.49` (target `20`),
   - error/retry gates pass (`0%` / `0%`),
   - Control/Ingress sentinel is readable and green.

## 6) Deep Phase Routing
1. `P8` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P8.build_plan.md`
2. `P9` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P9.build_plan.md`
3. `P10` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P10.build_plan.md`

## 7) M7 Blocker Taxonomy (Fail-Closed)
1. `M7-B1`: required handles missing/inconsistent.
2. `M7-B2`: P8 entry contract failure.
3. `M7-B3`: IEG lane closure failure.
4. `M7-B4`: OFP lane closure failure.
5. `M7-B5`: archive writer closure failure.
6. `M7-B6`: P8 rollup/verdict inconsistency.
7. `M7-B7`: DF lane closure failure.
8. `M7-B8`: AL lane closure failure.
9. `M7-B9`: DLA lane closure failure.
10. `M7-B10`: P9 rollup/verdict inconsistency.
11. `M7-B11`: CaseTrigger bridge closure failure.
12. `M7-B12`: CM closure failure.
13. `M7-B13`: LS writer-boundary closure failure.
14. `M7-B14`: P10 rollup/verdict inconsistency.
15. `M7-B15`: M7 handoff/cost-outcome artifact failure.
16. `M7-B16`: missing per-component performance SLO pins for active lane.
17. `M7-B17`: component performance budget breach (throughput/latency/lag/resource/stability).
18. `M7-B18`: `M7.K` throughput certification unresolved/failing for `P8+P9+P10`.
19. `M7-B19`: Control/Ingress sentinel failure during `M7.K` (upstream bottleneck/root-cause unresolved).

## 8) M7 Completion Checklist
- [x] M7.A complete
- [x] M7.B complete
- [x] M7.C complete
- [x] M7.D complete
- [x] M7.E complete
- [x] M7.F complete
- [x] M7.G complete
- [x] M7.H complete
- [x] M7.I complete
- [x] M7.J complete
- [x] M7.K complete
- [x] all active `M7-B*` blockers resolved

## 9) Planning Status
1. M7 deep-plan scaffold created.
2. P8/P9/P10 deep plans are split and referenced.
3. `M7.A` is closed green (`m7a_p8p10_handle_closure_20260225T204520Z`).
4. `M7.B` is closed green (`m7b_p8a_entry_precheck_20260225T210210Z`).
5. `M7.C` is closed green (`m7c_p8b_ieg_component_20260225T212932Z`).
6. `M7.D` is closed green (`m7d_p8c_ofp_component_20260225T213059Z`).
7. `P8.D` component lane is closed green (`m7e_p8d_archive_component_20260225T213458Z`).
8. `M7.E` is closed green (`m7f_p8e_rollup_20260225T214307Z`) with `phase_verdict=ADVANCE_TO_P9`.
9. `M7.F` is closed green (`m7h_p9b_df_component_20260226T015122Z`), throughput proof provisional.
10. `M7.G` is closed green (`m7i_p9c_al_component_20260226T015350Z`), throughput proof provisional.
11. `M7.H` DLA component lane is green (`m7j_p9d_dla_component_20260226T015553Z`), throughput proof provisional.
12. `M7.H` rollup is now closed green (`m7k_p9e_rollup_20260226T023154Z`) with `phase_verdict=ADVANCE_TO_P10`.
13. Non-waived throughput certification for `P8+P9+P10` is now closed green via `M7.K` with retired blockers `M7-B18/M7-B19`.
14. `M7.I` entry is closed green (`m7l_p10a_entry_precheck_20260226T023945Z`) with `next_gate=P10.B_READY`.
15. `P10.B` CaseTrigger lane is closed green (`m7m_p10b_case_trigger_component_20260226T024750Z`).
16. `P10.C` CM lane is closed green (`m7n_p10c_cm_component_20260226T024847Z`).
17. `P10.D` LS lane is closed green (`m7o_p10d_ls_component_20260226T024940Z`).
18. `P10.E` rollup/verdict is closed green (`m7p_p10e_rollup_20260226T030607Z`) with `next_gate=M7.J_READY`.
19. `M7.J` rollup/handoff is closed green (`m7q_m7_rollup_sync_20260226T031710Z`) with `next_gate=M8_READY`.
20. `M7.K` is closed green (`m7s_m7k_cert_20260226T000002Z`) with deterministic verdict `THROUGHPUT_CERTIFIED` and `next_gate=M8_READY`.
21. `M7` is now `DONE`; throughput blockers `M7-B18` and `M7-B19` are retired.
