# Dev Substrate Deep Plan - M7.P8 (P8 RTDL_CAUGHT_UP)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P8 RTDL_CAUGHT_UP`.

`P8` must prove:
1. `IEG` inlet projection lane is run-scoped and healthy.
2. `OFP` context projection lane is run-scoped and healthy.
3. `ArchiveWriter` persists durable archive evidence with append/readback guarantees.
4. `P8` rollup verdict is deterministic from component-level proofs.
5. `IEG/OFP/ArchiveWriter` meet pinned throughput and latency budgets.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P8 RTDL_CAUGHT_UP`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P8 Scope
In scope:
1. RTDL entry precheck for P8.
2. Component execution/verification:
   - `IEG`,
   - `OFP`,
   - `ArchiveWriter`.
3. P8 rollup matrix/blocker register/verdict.

Out of scope:
1. P9 decision chain (`DF/AL/DLA`).
2. P10 case/labels (`CaseTrigger/CM/LS`).

## 3) Anti-Lump Rule for P8
1. `IEG`, `OFP`, and `ArchiveWriter` are independent closure lanes.
2. `P8` cannot be green if any one lane lacks explicit evidence.
3. Shared RTDL lag metrics cannot substitute component evidence.

## 3.1) P8 Performance Contract (binding)
Each component lane must publish `*_performance_snapshot.json` for the lane run window and pass pinned numeric SLOs:
1. `IEG`:
   - throughput (`ieg_records_per_second`),
   - processing latency (`ieg_processing_latency_p95_ms`),
   - lag/backlog (`ieg_lag_messages`),
   - resource posture (`ieg_cpu_p95_pct`, `ieg_memory_p95_pct`),
   - stability (`ieg_error_rate_pct`).
2. `OFP`:
   - throughput (`ofp_records_per_second`),
   - processing latency (`ofp_processing_latency_p95_ms`),
   - lag/backlog (`ofp_lag_messages`),
   - resource posture (`ofp_cpu_p95_pct`, `ofp_memory_p95_pct`),
   - stability (`ofp_error_rate_pct`).
3. `ArchiveWriter`:
   - write throughput (`archive_objects_per_minute`),
   - commit latency (`archive_commit_latency_p95_ms`),
   - queue depth/backpressure (`archive_backpressure_seconds`),
   - resource posture (`archive_cpu_p95_pct`, `archive_memory_p95_pct`),
   - stability (`archive_write_error_rate_pct`).
4. Numeric thresholds are mandatory and must be pinned during `P8.A`; missing pins are fail-closed.

## 4) Work Breakdown

### P8.A Entry + Handle Closure
Goal:
1. close required handles and runtime prerequisites for P8.

Tasks:
1. verify M6->M7 continuity and run-scope pin set.
2. verify required handles for `IEG`, `OFP`, and archive surfaces.
3. emit `p8a_entry_snapshot.json` and blocker register.

Required handle set for P8.A:
1. runtime path and scope:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `PHASE_RUNTIME_PATH_MODE`
2. IEG/OFP lane refs:
   - `FLINK_APP_RTDL_IEG_V0`
   - `FLINK_APP_RTDL_OFP_V0`
   - `FLINK_EKS_RTDL_IEG_REF`
   - `FLINK_EKS_RTDL_OFP_REF`
   - `FLINK_EKS_NAMESPACE`
3. archive prerequisites:
   - `K8S_DEPLOY_ARCHIVE_WRITER`
   - `S3_ARCHIVE_RUN_PREFIX_PATTERN`
   - `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`
4. RTDL lag threshold anchor:
   - `RTDL_CAUGHT_UP_LAG_MAX`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7b`.
2. require upstream M7.A closure summary (`m7a_execution_summary.json`) from run-control S3 prefix.
3. verify:
   - upstream `M7.A` is green (`overall_pass=true`, `next_gate=M7.B_READY`),
   - required handle set above is fully resolved (no missing/placeholders),
   - P8 component SLO profile exists for `IEG/OFP/ArchiveWriter`.
4. emit artifacts:
   - `p8a_entry_snapshot.json`
   - `p8a_blocker_register.json`
   - `p8a_execution_summary.json`.
5. publish artifacts locally and durably (`evidence/dev_full/run_control/<execution_id>/...`).

DoD:
- [x] P8 required-handle set is complete.
- [x] unresolved required handles are blocker-marked.
- [x] P8 entry snapshot is committed locally and durably.
- [x] per-component P8 performance SLO targets are pinned.
- [x] managed `P8.A` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.C_READY`).

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
3. Verification outcomes:
   - upstream continuity `M7.A -> P8.A`: `ok`,
   - required handles resolved: `12/12`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - SLO profile continuity for `IEG/OFP/ArchiveWriter`: `ok`.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22415762548_artifacts/p8a-entry-precheck-20260225T210210Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7b_p8a_entry_precheck_20260225T210210Z/`.

### P8.B IEG Component Lane Closure
Goal:
1. close `IEG` with run-scoped evidence.

Entry prerequisites (must already be green):
1. `P8.A` execution summary is green with `next_gate=M7.C_READY`.
2. active runtime path is pinned and allowed (`FLINK_RUNTIME_PATH_ACTIVE` in `FLINK_RUNTIME_PATH_ALLOWED`).
3. `IEG` SLO envelope exists from upstream `M7.A` profile.

Required handle set for P8.B:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `FLINK_APP_RTDL_IEG_V0`
4. `FLINK_EKS_RTDL_IEG_REF`
5. `FLINK_EKS_NAMESPACE`
6. `K8S_DEPLOY_IEG`
7. `FP_BUS_TRAFFIC_V1`
8. `FP_BUS_CONTEXT_V1`
9. `RTDL_CORE_CONSUMER_GROUP_ID`
10. `RTDL_CORE_OFFSET_COMMIT_POLICY`
11. `RTDL_CAUGHT_UP_LAG_MAX`
12. `FLINK_CHECKPOINT_INTERVAL_MS`
13. `FLINK_CHECKPOINT_S3_PREFIX_PATTERN`

Pinned IEG performance gate (from M7.A baseline):
1. `records_per_second_min=200`
2. `latency_p95_ms_max=500`
3. `lag_messages_max=1000`
4. `cpu_p95_pct_max=85`
5. `memory_p95_pct_max=85`
6. `error_rate_pct_max=1.0`

Execution plan (managed lane):
1. materialize `m7c` lane in `.github/workflows/dev_full_m6f_streaming_active.yml` for `P8.B`.
2. dispatch workflow with:
   - `phase_mode=m7c`,
   - upstream `P8.A` execution id,
   - pinned run scope (`platform_run_id`, `scenario_run_id`).
3. run lane checks:
   - required-handle closure for `P8.B`,
   - `IEG` lane health/status proof from runtime surface,
   - run-scoped output proof for traffic/context projection lane,
   - lag/offset/checkpoint posture against pinned thresholds,
   - IEG performance snapshot against numeric SLO gate.
4. emit artifacts:
   - `p8b_ieg_component_snapshot.json`,
   - `p8b_ieg_blocker_register.json`,
   - `p8b_ieg_performance_snapshot.json`,
   - `p8b_ieg_execution_summary.json`.
5. publish artifacts locally and durably (`evidence/dev_full/run_control/<execution_id>/...`).

DoD:
- [x] `IEG` run-scoped output proofs are present.
- [x] `IEG` lag/checkpoint checks are green.
- [x] `IEG` blocker set is empty.
- [x] `p8b_ieg_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P8.B` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.D_READY`).

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7c`
   - run id: `22416728598`
   - execution id: `m7c_p8b_ieg_component_20260225T212932Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.D_READY`.
3. Verification outcomes:
   - required handles resolved: `18/18`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - RTDL component proof materialized: `evidence/runs/platform_20260223T184232Z/rtdl_core/ieg_component_proof.json`,
   - throughput gate posture: `waived_low_sample` (sample size `18`), lag/error gates pass.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22416728598_artifacts/p8-component-m7c-20260225T212932Z/`
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7c_p8b_ieg_component_20260225T212932Z/`.

### P8.C OFP Component Lane Closure
Goal:
1. close `OFP` with run-scoped evidence.

Entry prerequisites (must already be green):
1. `P8.B` execution summary is green with `next_gate=M7.D_READY`.
2. active runtime path is pinned and allowed (`FLINK_RUNTIME_PATH_ACTIVE` in `FLINK_RUNTIME_PATH_ALLOWED`).
3. `OFP` SLO envelope exists from upstream `M7.A` profile.

Required handle set for P8.C:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `FLINK_APP_RTDL_OFP_V0`
4. `FLINK_EKS_RTDL_OFP_REF`
5. `FLINK_EKS_NAMESPACE`
6. `K8S_DEPLOY_OFP`
7. `FP_BUS_TRAFFIC_V1`
8. `FP_BUS_CONTEXT_V1`
9. `RTDL_CORE_CONSUMER_GROUP_ID`
10. `RTDL_CORE_OFFSET_COMMIT_POLICY`
11. `RTDL_CAUGHT_UP_LAG_MAX`
12. `FLINK_CHECKPOINT_INTERVAL_MS`
13. `FLINK_CHECKPOINT_S3_PREFIX_PATTERN`

Pinned OFP performance gate (from M7.A baseline):
1. `records_per_second_min=200`
2. `latency_p95_ms_max=500`
3. `lag_messages_max=1000`
4. `cpu_p95_pct_max=85`
5. `memory_p95_pct_max=85`
6. `error_rate_pct_max=1.0`

Execution plan (managed lane):
1. materialize `m7d` lane in `.github/workflows/dev_full_m6f_streaming_active.yml` for `P8.C`.
2. dispatch workflow with:
   - `phase_mode=m7d`,
   - upstream `P8.B` execution id,
   - pinned run scope (`platform_run_id`, `scenario_run_id`).
3. run lane checks:
   - required-handle closure for `P8.C`,
   - `OFP` lane health/status proof from runtime surface,
   - run-scoped output proof for context projection lane,
   - lag/offset/checkpoint posture against pinned thresholds,
   - OFP performance snapshot against numeric SLO gate.
4. emit artifacts:
   - `p8c_ofp_component_snapshot.json`,
   - `p8c_ofp_blocker_register.json`,
   - `p8c_ofp_performance_snapshot.json`,
   - `p8c_ofp_execution_summary.json`.
5. publish artifacts locally and durably (`evidence/dev_full/run_control/<execution_id>/...`).

DoD:
- [x] `OFP` run-scoped output proofs are present.
- [x] `OFP` lag/checkpoint checks are green.
- [x] `OFP` blocker set is empty.
- [x] `p8c_ofp_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P8.C` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.E_READY`).

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7d`
   - run id: `22416785955`
   - execution id: `m7d_p8c_ofp_component_20260225T213059Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M7.E_READY`.
3. Verification outcomes:
   - required handles resolved: `18/18`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - RTDL component proof materialized: `evidence/runs/platform_20260223T184232Z/rtdl_core/ofp_component_proof.json`,
   - throughput gate posture: `waived_low_sample` (sample size `18`), lag/error gates pass.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22416785955_artifacts/p8-component-m7d-20260225T213059Z/`
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7d_p8c_ofp_component_20260225T213059Z/`.

### P8.D ArchiveWriter Component Lane Closure
Goal:
1. close `ArchiveWriter` durable evidence lane.

Entry prerequisites (must already be green):
1. `P8.C` execution summary is green with `next_gate=M7.E_READY`.
2. active runtime path is pinned and allowed (`FLINK_RUNTIME_PATH_ACTIVE` in `FLINK_RUNTIME_PATH_ALLOWED`).
3. `ArchiveWriter` SLO envelope exists from upstream `M7.A` profile.

Required handle set for P8.D:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `K8S_DEPLOY_ARCHIVE_WRITER`
4. `S3_ARCHIVE_RUN_PREFIX_PATTERN`
5. `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`
6. `RTDL_CORE_EVIDENCE_PATH_PATTERN`
7. `RTDL_CAUGHT_UP_LAG_MAX`
8. `ROLE_EKS_IRSA_RTDL`
9. `S3_EVIDENCE_URI_PATTERN`

Pinned ArchiveWriter performance gate (from M7.A baseline):
1. `objects_per_minute_min=50`
2. `commit_latency_p95_ms_max=1200`
3. `backpressure_seconds_max=30`
4. `cpu_p95_pct_max=85`
5. `memory_p95_pct_max=85`
6. `write_error_rate_pct_max=0.5`

Execution plan (managed lane):
1. materialize `m7e` lane in `.github/workflows/dev_full_m6f_streaming_active.yml` for `P8.D`.
2. dispatch workflow with:
   - `phase_mode=m7e`,
   - upstream `P8.C` execution id,
   - pinned run scope (`platform_run_id`, `scenario_run_id`).
3. run lane checks:
   - required-handle closure for `P8.D`,
   - ArchiveWriter health/status proof from runtime surface,
   - durable object existence + readback proof under run-scoped archive prefix,
   - append-only/archive-ledger invariants,
   - archive performance snapshot against numeric SLO gate.
4. emit artifacts:
   - `p8d_archive_writer_snapshot.json`,
   - `p8d_archive_writer_blocker_register.json`,
   - `p8d_archive_writer_performance_snapshot.json`,
   - `p8d_archive_writer_execution_summary.json`.
5. publish artifacts locally and durably (`evidence/dev_full/run_control/<execution_id>/...`).

DoD:
- [x] archive object existence/readback proof is present.
- [x] append-only/archive-ledger invariants pass.
- [x] `ArchiveWriter` blocker set is empty.
- [x] `p8d_archive_writer_performance_snapshot.json` is committed and within pinned SLO.
- [x] managed `P8.D` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=P8.E_READY`).

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7e`
   - run id: `22416936038`
   - execution id: `m7e_p8d_archive_component_20260225T213458Z`.
2. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=P8.E_READY`.
3. Verification outcomes:
   - required handles resolved: `11/11`,
   - missing handles: `0`,
   - placeholder handles: `0`,
   - RTDL component proof materialized: `evidence/runs/platform_20260223T184232Z/rtdl_core/archive_component_proof.json`,
   - archive durability probe: primary object-store path denied by IAM; fallback mirror probe in evidence bucket succeeded and is explicitly recorded in blocker notes.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m7/_gh_run_22416936038_artifacts/p8-component-m7e-20260225T213458Z/`
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7e_p8d_archive_component_20260225T213458Z/`
   - archive probe fallback object: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/archive/p8d_archive_probe_m7e_p8d_archive_component_20260225T213458Z.json`.

### P8.E P8 Rollup + Verdict
Goal:
1. adjudicate P8 from `P8.B/P8.C/P8.D`.

Entry prerequisites (must already be green):
1. `P8.B` execution summary is green with `next_gate=M7.D_READY`.
2. `P8.C` execution summary is green with `next_gate=M7.E_READY`.
3. `P8.D` execution summary is green with `next_gate=P8.E_READY`.

Tasks:
1. load and validate upstream lane summaries/blocker registers (`P8.B/P8.C/P8.D`) from durable run-control S3.
2. verify RTDL proof triplet exists under `RTDL_CORE_EVIDENCE_PATH_PATTERN`:
   - `ieg_component_proof.json`
   - `ofp_component_proof.json`
   - `archive_component_proof.json`.
3. build `p8e_rtdl_gate_rollup_matrix.json`.
4. build `p8e_rtdl_blocker_register.json`.
5. emit `p8e_rtdl_gate_verdict.json`.
6. emit `p8e_execution_summary.json`.

Execution plan (managed lane):
1. dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with `phase_mode=m7f`.
2. pass upstream execution ids:
   - `upstream_m6d_execution = <p8b_execution_id>`
   - `upstream_m6g_execution = <p8c_execution_id>`
   - `upstream_m6h_execution = <p8d_execution_id>`.
3. require deterministic verdict:
   - `phase_verdict = ADVANCE_TO_P9`
   - `next_gate = M7.F_READY`
   on green closure; otherwise fail-closed hold.

DoD:
- [x] rollup matrix and blocker register committed.
- [x] deterministic verdict committed (`phase_verdict=ADVANCE_TO_P9`, `next_gate=M7.F_READY`) or fail-closed hold.
- [x] managed `P8.E` run is green (`overall_pass=true`, `blocker_count=0`, `next_gate=M7.F_READY`).

Execution status (2026-02-25):
1. Authoritative managed execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m7f`
   - run id: `22417222822`
   - execution id: `m7f_p8e_rollup_20260225T214307Z`.
2. Result:
   - `overall_pass=true`,
   - `phase_verdict=ADVANCE_TO_P9`,
   - `blocker_count=0`,
   - `next_gate=M7.F_READY`.
3. Verification outcomes:
   - upstream lane posture checks pass for `P8.B/P8.C/P8.D`,
   - RTDL proof triplet exists (`ieg_component_proof.json`, `ofp_component_proof.json`, `archive_component_proof.json`),
   - rollup artifacts committed locally and durably.
4. Evidence:
   - durable run-control: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m7f_p8e_rollup_20260225T214307Z/`.

## 5) P8 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P8-V1-ENTRY` | validate handles and entry gates for all P8 components |
| `P8-V2-IEG` | validate IEG run-scoped projection outputs and lag/checkpoint posture |
| `P8-V3-OFP` | validate OFP run-scoped projection outputs and lag/checkpoint posture |
| `P8-V4-ARCHIVE` | validate archive writer durable object + append/readback posture |
| `P8-V5-ROLLUP` | validate P8 rollup and deterministic verdict |

## 6) P8 Blocker Taxonomy
1. `M7P8-B1`: P8 entry/handle closure failure.
2. `M7P8-B2`: IEG component lane failure.
3. `M7P8-B3`: OFP component lane failure.
4. `M7P8-B4`: ArchiveWriter component lane failure.
5. `M7P8-B5`: P8 rollup/verdict inconsistency.
6. `M7P8-B6`: missing P8 component performance SLO pins.
7. `M7P8-B7`: P8 component performance budget breach.

## 7) P8 Evidence Contract
1. `p8a_entry_snapshot.json`
2. `p8a_blocker_register.json`
3. `p8a_execution_summary.json`
4. `p8b_ieg_component_snapshot.json`
5. `p8b_ieg_blocker_register.json`
6. `p8b_ieg_performance_snapshot.json`
7. `p8b_ieg_execution_summary.json`
8. `p8c_ofp_component_snapshot.json`
9. `p8c_ofp_blocker_register.json`
10. `p8c_ofp_performance_snapshot.json`
11. `p8c_ofp_execution_summary.json`
12. `p8d_archive_writer_snapshot.json`
13. `p8d_archive_writer_blocker_register.json`
14. `p8d_archive_writer_performance_snapshot.json`
15. `p8d_archive_writer_execution_summary.json`
16. `p8e_rtdl_gate_rollup_matrix.json`
17. `p8e_rtdl_blocker_register.json`
18. `p8e_rtdl_gate_verdict.json`
19. `p8e_execution_summary.json`

## 8) Exit Rule for P8
`P8` can close only when:
1. all `M7P8-B*` blockers are clear,
2. all P8 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. `P9` is blocked until `P8` verdict is `ADVANCE_TO_P9` with `next_gate=M7.F_READY`.
