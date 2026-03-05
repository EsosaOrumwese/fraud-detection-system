# Dev Substrate Deep Plan - M6.P7 (P7 INGEST_COMMITTED)
_Parent orchestration phase: `platform.M6.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P7 INGEST_COMMITTED`.

`P7` must prove:
1. admit/quarantine summaries are committed and run-scoped.
2. Kafka offsets snapshot is committed and readable.
3. dedupe/anomaly checks pass fail-closed.
4. deterministic `P7` verdict and M6 closure handoff are emitted.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P7 INGEST_COMMITTED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`

## 2) P7 Scope
In scope:
1. ingest commit evidence surface checks.
2. dedupe/anomaly fail-closed checks.
3. deterministic `P7` rollup + verdict artifacts.
4. inputs for M6 final verdict + `M7` handoff.

Out of scope:
1. READY and streaming activation checks (`P5/P6`).
2. RTDL/case-label closures (`P8+`).

## 3) Work Breakdown (Owned by M6.H/M6.I)

### P7.A Ingest Commit Execution (M6.H)
Goal:
1. emit and validate ingest commit evidence set.

Tasks:
1. verify required handles are pinned:
   - `RECEIPT_SUMMARY_PATH_PATTERN`
   - `QUARANTINE_SUMMARY_PATH_PATTERN`
   - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
   - `DDB_IG_IDEMPOTENCY_TABLE`
   - `DDB_IG_IDEMPOTENCY_TTL_FIELD`
   - `IG_IDEMPOTENCY_TTL_SECONDS`
2. verify entry gate condition:
   - non-zero active ingestion counters, or explicit empty-run waiver artifact.
3. emit/verify:
   - receipt summary,
   - quarantine summary,
   - offsets snapshot (`KAFKA_TOPIC_PARTITION_OFFSETS` or `IG_ADMISSION_INDEX_PROXY` for `apigw_lambda_ddb` ingress edge mode).
4. run dedupe/anomaly checks for fail-closed closure.

DoD:
- [x] receipt/quarantine/offset evidence exists and is readable.
- [x] dedupe/anomaly checks pass.
- [x] `m6h_ingest_commit_snapshot.json` committed locally and durably.
- [x] fresh-authority remote execution completed with `overall_pass=true`, `blocker_count=0`, `next_gate=M6.I_READY`.

Execution plan (authoritative lane):
1. Dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with:
   - `phase_mode=m6h`,
   - `platform_run_id=platform_20260223T184232Z`,
   - `scenario_run_id=scenario_38753050f3b70c666e16f7552016b330`,
   - `upstream_m6g_execution=m6g_p6c_gate_rollup_20260225T181523Z`,
   - `ig_idempotency_table=fraud-platform-dev-full-ig-idempotency`.
2. Require artifact set:
   - `receipt_summary.json`,
   - `quarantine_summary.json`,
   - `kafka_offsets_snapshot.json`,
   - `m6h_ingest_commit_snapshot.json`,
   - `m6h_blocker_register.json`,
   - `m6h_execution_summary.json`.
3. Fail-closed gate:
   - any `M6P7-B*` blocker prevents `M6.I` advancement.

Execution status (2026-02-25):
1. Remote authoritative execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m6h`
   - run id: `22410856328`
   - execution id: `m6h_p7a_ingest_commit_20260225T184352Z`
2. Result:
   - `overall_pass=false`
   - `blocker_count=1`
   - `next_gate=HOLD_REMEDIATE`
3. Active blocker:
   - `M6P7-B4` (`kafka_offsets_snapshot` not materially populated with topic/partition offsets).
4. Evidence:
   - workflow artifact set: `m6h-ingest-commit-20260225T184352Z`
   - local artifact root: `runs/dev_substrate/dev_full/m6/_gh_run_22410856328_v2/m6h-ingest-commit-20260225T184352Z/`
   - durable run-control prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6h_p7a_ingest_commit_20260225T184352Z/`
   - durable run-scoped ingest prefix: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/ingest/`
5. Remediation closure execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m6h`
   - run id: `22411945101`
   - execution id: `m6h_p7a_ingest_commit_20260225T191433Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M6.I_READY`
   - local artifact root: `runs/dev_substrate/dev_full/m6/_gh_run_22411945101/m6h-ingest-commit-20260225T191433Z/`
   - durable run-control prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6h_p7a_ingest_commit_20260225T191433Z/`
   - offset evidence mode: `IG_ADMISSION_INDEX_PROXY` (`kafka_offsets_materialized=true`).

### P7.B P7 Gate Rollup + Verdict + M6 Closure Inputs (M6.I)
Goal:
1. adjudicate `P7` and produce closure inputs for M6 verdict/handoff.

Tasks:
1. build `m6i_p7_gate_rollup_matrix.json`.
2. build `m6i_p7_blocker_register.json`.
3. emit `m6i_p7_gate_verdict.json`.
4. build `m7_handoff_pack.json` (non-secret, run-scope consistent, evidence refs explicit).

DoD:
- [x] `P7` rollup matrix + blocker register committed.
- [x] deterministic `P7` verdict committed (`ADVANCE_TO_M7`/`HOLD_REMEDIATE`/`NO_GO_RESET_REQUIRED`).
- [x] `m7_handoff_pack.json` committed locally and durably.
- [x] fresh-authority remote execution completed with verdict `ADVANCE_TO_M7` and `next_gate=M6.J_READY`.

Execution plan (authoritative lane):
1. Dispatch `.github/workflows/dev_full_m6f_streaming_active.yml` with:
   - `phase_mode=m6i`,
   - same run scope pins as `P7.A`,
   - `upstream_m6g_execution=m6g_p6c_gate_rollup_20260225T181523Z`,
   - `upstream_m6h_execution=<authoritative M6.H execution id>`.
2. Require artifact set:
   - `m6i_p7_gate_rollup_matrix.json`,
   - `m6i_p7_blocker_register.json`,
   - `m6i_p7_gate_verdict.json`,
   - `m7_handoff_pack.json`,
   - `m6i_execution_summary.json`.
3. Fail-closed gate:
   - any `M6P7-B*` blocker prevents M6 final closure advancement.

Execution status (2026-02-25):
1. Remote authoritative execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m6i`
   - run id: `22410918552`
   - execution id: `m6i_p7b_gate_rollup_20260225T184535Z`
2. Result:
   - `overall_pass=false`
   - `blocker_count=1`
   - `verdict=HOLD_REMEDIATE`
   - `next_gate=HOLD_REMEDIATE`
3. Active blocker:
   - `M6P7-B4` propagated from upstream `M6.H` blocker register.
4. Evidence:
   - workflow artifact set: `m6i-p7-rollup-20260225T184535Z`
   - local artifact root: `runs/dev_substrate/dev_full/m6/_gh_run_22410918552_v1/m6i-p7-rollup-20260225T184535Z/`
   - durable run-control prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6i_p7b_gate_rollup_20260225T184535Z/`
5. Gate posture:
   - initial execution remained fail-closed pending `M6P7-B4` remediation (historical),
   - remediation rerun is green and unblocked.
6. Remediation closure execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m6i`
   - run id: `22411988277`
   - execution id: `m6i_p7b_gate_rollup_20260225T191541Z`
   - result: `overall_pass=true`, `blocker_count=0`, `verdict=ADVANCE_TO_M7`, `next_gate=M6.J_READY`
   - local artifact root: `runs/dev_substrate/dev_full/m6/_gh_run_22411988277/m6i-p7-rollup-20260225T191541Z/`
   - durable run-control prefix: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6i_p7b_gate_rollup_20260225T191541Z/`

## 4) P7 Verification Catalog
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `P7-V1-ENTRY-CHECK` | verify non-zero ingest counters or explicit empty-run waiver | validates entry gate |
| `P7-V2-RECEIPT-SUMMARY` | verify receipt summary artifact by run scope | commit evidence closure |
| `P7-V3-QUARANTINE-SUMMARY` | verify quarantine summary artifact by run scope | commit evidence closure |
| `P7-V4-OFFSET-SNAPSHOT` | verify offsets snapshot artifact and readability | commit evidence closure |
| `P7-V5-DEDUPE-ANOMALY` | execute dedupe/anomaly checks against idempotency/receipt surfaces | fail-closed correctness |
| `P7-V6-ROLLUP-VERDICT` | build rollup + blocker register + verdict + handoff | deterministic closure |

## 5) P7 Blocker Taxonomy
1. `M6P7-B1`: required ingest-commit handles missing/inconsistent.
2. `M6P7-B2`: entry gate unmet (no non-zero flow and no waiver).
3. `M6P7-B3`: receipt/quarantine summary missing/unreadable.
4. `M6P7-B4`: offset snapshot missing/unreadable.
5. `M6P7-B5`: dedupe/anomaly drift.
6. `M6P7-B6`: rollup/verdict inconsistency.
7. `M6P7-B7`: `m7_handoff_pack.json` missing/invalid.
8. `M6P7-B8`: durable publish/readback failure.

## 6) P7 Evidence Contract
1. `m6h_ingest_commit_snapshot.json`
2. `m6i_p7_gate_rollup_matrix.json`
3. `m6i_p7_blocker_register.json`
4. `m6i_p7_gate_verdict.json`
5. `m7_handoff_pack.json`

## 7) Exit Rule for P7
`P7` can close only when:
1. all `M6P7-B*` blockers are resolved,
2. all P7 DoDs are green,
3. P7 evidence exists locally and durably,
4. verdict/handoff are deterministic and blocker-consistent.

Transition:
1. M6 final closure remains blocked until `P7` verdict is available and cost-outcome artifacts are valid.
