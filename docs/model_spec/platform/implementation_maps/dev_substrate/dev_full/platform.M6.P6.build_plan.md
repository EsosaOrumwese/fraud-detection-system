# Dev Substrate Deep Plan - M6.P6 (P6 STREAMING_ACTIVE)
_Parent orchestration phase: `platform.M6.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P6 STREAMING_ACTIVE`.

`P6` must prove:
1. Flink stream lanes and ingress admission are actively processing run-scoped traffic.
2. lag remains within threshold.
3. no unresolved publish ambiguity exists.
4. runtime evidence overhead remains within budget and does not degrade hot-path throughput.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P6 STREAMING_ACTIVE`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md` (evidence emission law in guardrails)

## 2) P6 Scope
In scope:
1. streaming entry checks and lane activation.
2. counters/lag posture and publish ambiguity closure.
3. evidence-overhead budget posture (`latency p95`, `bytes/event`, `write-rate`).
4. deterministic `P6` rollup + verdict artifacts.

Out of scope:
1. READY commit authority closure (`P5`).
2. ingest commit evidence closure (`P7`).

## 3) Work Breakdown (Owned by M6.E/M6.F/M6.G)

### P6.A Entry + Activation Precheck (M6.E)
Goal:
1. validate streaming entry preconditions before activation checks.

Tasks:
1. verify `P5` verdict is `ADVANCE_TO_P6`.
2. verify run-scoped source roots and filters:
   - `READY_MESSAGE_FILTER`
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
3. verify required lane handles are pinned:
   - `FLINK_RUNTIME_PATH_ACTIVE`
   - `FLINK_RUNTIME_PATH_ALLOWED`
   - `FLINK_APP_WSP_STREAM_V0` / `FLINK_EKS_WSP_STREAM_REF` (selected by active runtime path)
   - `FLINK_APP_SR_READY_V0` / `FLINK_EKS_SR_READY_REF` (selected by active runtime path)
   - `EMR_EKS_VIRTUAL_CLUSTER_ID` + `EMR_EKS_RELEASE_LABEL` + `EMR_EKS_EXECUTION_ROLE_ARN` (required when active runtime path is `EKS_EMR_ON_EKS`)
   - `FLINK_CHECKPOINT_INTERVAL_MS`
   - `WSP_MAX_INFLIGHT`
   - `WSP_RETRY_MAX_ATTEMPTS`
   - `WSP_RETRY_BACKOFF_MS`
   - `WSP_STOP_ON_NONRETRYABLE`
   - `RTDL_CAUGHT_UP_LAG_MAX` (lag threshold anchor for M6 streaming checks until M6-specific lag handle is pinned)

DoD:
- [x] entry checks pass with no unresolved required handles.
- [x] `m6e_stream_activation_entry_snapshot.json` committed locally and durably.

Execution status (2026-02-25):
1. Historical fail-closed attempts:
   - `m6e_p6a_stream_entry_20260225T044348Z` and `m6e_p6a_stream_entry_20260225T044618Z` stopped on `M6P6-B2` under MSF-only posture.
2. Repin + materialization actions completed:
   - EKS auth mode moved to `API_AND_CONFIG_MAP`,
   - EMR virtual cluster created on runtime EKS namespace:
     - name: `fraud-platform-dev-full-flink-vc`,
     - id: `3cfszbpz28ixf1wmmd2roj571`,
   - handles pinned:
     - `EMR_EKS_VIRTUAL_CLUSTER_ID=3cfszbpz28ixf1wmmd2roj571`,
     - `EMR_EKS_RELEASE_LABEL=emr-6.15.0-latest`.
3. Authoritative M6.E closure rerun:
   - execution: `m6e_p6a_stream_entry_20260225T120522Z`,
   - local: `runs/dev_substrate/dev_full/m6/m6e_p6a_stream_entry_20260225T120522Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6e_p6a_stream_entry_20260225T120522Z/`.
4. Result:
   - `overall_pass=true`,
   - blocker count `0`,
   - `next_gate=M6.F_READY`.

### P6.B Streaming Active + Lag + Ambiguity Closure (M6.F)
Goal:
1. prove active streaming and bounded lag without unresolved ambiguity.

Tasks:
1. collect streaming counters snapshot (publication + admission progression).
2. collect lag posture snapshot and compare against threshold.
3. verify no unresolved `PUBLISH_UNKNOWN`/publish ambiguity.
4. collect evidence-overhead snapshot:
   - runtime latency p95,
   - emitted evidence bytes/event,
   - evidence write-rate.

DoD:
- [ ] streaming counters show active run-scoped flow.
- [ ] lag is within accepted threshold.
- [ ] ambiguity register is empty.
- [ ] evidence-overhead posture is within budget target.
- [ ] `m6f_streaming_active_snapshot.json` and `m6f_evidence_overhead_snapshot.json` are present in workflow artifacts and durable evidence storage.

Execution status (2026-02-25):
1. Executed authoritative `M6.F` lane:
   - `m6f_p6b_streaming_active_20260225T121536Z`,
   - local: `runs/dev_substrate/dev_full/m6/m6f_p6b_streaming_active_20260225T121536Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T121536Z/`.
2. Result:
   - `overall_pass=false`,
   - blocker count `3`,
   - `next_gate=HOLD_REMEDIATE`.
3. Blockers:
   - `M6P6-B2`: required Flink lane refs not active in EMR VC (`wsp_active=0`, `sr_ready_active=0`),
   - `M6P6-B3`: streaming/admission counters show no active flow (`IG idempotency count=0`),
   - `M6P6-B4`: lag posture unresolved because active stream consumption is absent.
4. Non-blocking checks:
   - `M6P6-B5` clear (`unresolved_publish_ambiguity_count=0`),
   - evidence-overhead budget posture passed (`m6f_evidence_overhead_snapshot.json`).
5. Remediation gate:
   - `M6.G` remains blocked until `M6P6-B2/B3/B4` are cleared with a fresh `M6.F` rerun.

Remediation plan to clear active blockers (`M6P6-B2/B3/B4`):
1. `M6P6-B2` root-cause lock (live-state):
   - EKS worker capacity is absent because nodegroup `fraud-platform-dev-full-m6f-workers` is `CREATE_FAILED` (`NodeCreationFailure`),
   - EMR lane refs fail with scheduler error (`no nodes available to schedule pods`),
   - failed worker console output indicates bootstrap failure (`pluto` timeout retrieving private DNS from EC2),
   - private route table is local-only and lacks required private endpoint surfaces for worker bootstrap/image pull/token exchange.
2. Lane A - network bootstrap connectivity via IaC:
   - add interface VPC endpoints (`ec2`, `ecr.api`, `ecr.dkr`, `sts`) with private DNS enabled in runtime private subnets,
   - add `s3` gateway endpoint to private route table,
   - add endpoint security-group surface permitting `443` from private subnet CIDRs.
3. Lane B - worker capacity via IaC:
   - materialize managed EKS nodegroup resource for `M6.F` workers in Terraform runtime stack,
   - require nodegroup `ACTIVE` and `kubectl get nodes` non-empty before EMR rerun.
4. Lane C - stream-lane semantic validity:
   - replace placeholder EMR job drivers (`SparkPi`) with lane-authentic job specs for refs:
     - `FLINK_EKS_SR_READY_REF`,
     - `FLINK_EKS_WSP_STREAM_REF`,
   - require refs observable as active (`SUBMITTED|PENDING|RUNNING`) during `M6.F` capture window.
5. `M6P6-B3` validation lane (already structurally remediated):
   - maintain IG idempotency persistence check,
   - require non-zero run-scoped admission progression for active `platform_run_id` in rerun artifacts.
6. `M6P6-B4` lag lane:
   - compute lag only after active stream + non-zero admission proof is present,
   - require `measured_lag <= RTDL_CAUGHT_UP_LAG_MAX`.
7. Closure:
   - rerun `M6.F` with fresh `phase_execution_id`,
   - do not proceed to `M6.G` unless blocker count is zero and new `m6f_*` artifacts are published in workflow artifacts + durable evidence storage.

Remediation DoD checklist (`M6P6-B2/B3/B4` closure lane):
- [x] Root-cause proof retained in execution notes (`NodeCreationFailure` + EMR `FailedScheduling` evidence).
- [x] Lane A complete: private endpoint surfaces are materialized and readable (`ec2`, `ecr.api`, `ecr.dkr`, `sts`, `s3` gateway).
- [x] Lane B complete: IaC-managed worker nodegroup is `ACTIVE` and cluster has at least one schedulable `Ready` node.
- [x] Lane C complete: lane refs (`FLINK_EKS_SR_READY_REF`, `FLINK_EKS_WSP_STREAM_REF`) are executed using lane-authentic specs and observed active in capture window.
- [ ] `M6P6-B3` validation passes on rerun with non-zero run-scoped admission progression.
- [ ] `M6P6-B4` validation passes on rerun with `measured_lag <= RTDL_CAUGHT_UP_LAG_MAX`.
- [x] fresh rerun `m6f_*` artifacts are published in workflow artifacts and durable evidence storage.
- [ ] `M6.G` is now unblocked (`rerun blocker_count=0`) and ready for P6 gate rollup.

Rerun closure status (2026-02-25):
1. Provisional local remediator run:
   - `m6f_p6b_streaming_active_20260225T143900Z`,
   - `overall_pass=true`,
   - blocker count `0`.
2. Authoritative no-laptop-compute rerun:
   - workflow run id: `22403542013` (`dev_full_m6f_streaming_active.yml`, ref `migrate-dev`),
   - execution id: `m6f_p6b_streaming_active_20260225T152755Z`,
   - `overall_pass=true`,
   - blocker count `0`,
   - `next_gate=M6.G_READY`.
3. Closure metrics from authoritative rerun artifacts:
   - `wsp_active_count=1`,
   - `sr_ready_active_count=1`,
   - `ig_idempotency_count=5`,
   - `measured_lag=0` with `within_threshold=true`,
   - `unresolved_publish_ambiguity_count=0`.
4. Evidence locations (authoritative rerun):
   - workflow artifact set: `m6f-streaming-active-20260225T152755Z`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T152755Z/`

Strict-semantic rerun status (2026-02-25, supersedes closure claim above):
1. Remote rerun (workflow run `22406210783`, execution `m6f_p6b_streaming_active_20260225T163455Z`) executed with:
   - `RUNNING`-only active-state check,
   - run-window-scoped admission progression (`platform_run_id + admitted_at_epoch window`),
   - measured lag source (`ig_admission_freshness_seconds` or explicit unavailable reason), not legacy proxy.
2. Result:
   - `overall_pass=false`,
   - `blocker_count=3`,
   - `next_gate=HOLD_REMEDIATE`.
3. Active blockers:
   - `M6P6-B2`: refs stayed `SUBMITTED` (`wsp_state=SUBMITTED`, `sr_ready_state=SUBMITTED`),
   - `M6P6-B3`: run-window admission progression `0`,
   - `M6P6-B4`: lag unavailable due no run-window admissions.
4. Evidence:
   - workflow artifact set: `m6f-streaming-active-20260225T163455Z`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T163455Z/`.
5. Gate posture:
   - `P6` is fail-closed and reopened; do not execute/claim `M6.G` as active authority until strict-semantic `M6.F` rerun is blocker-free.

Fallback remediation rerun status (2026-02-25, latest authority):
1. Remote rerun (workflow run `22407876177`, execution `m6f_p6b_streaming_active_20260225T171938Z`) executed on fallback path `EKS_FLINK_OPERATOR`.
2. Result:
   - `overall_pass=false`,
   - `blocker_count=2`,
   - `next_gate=HOLD_REMEDIATE`.
3. Blocker transition:
   - `M6P6-B2` is now cleared (`wsp_state=RUNNING`, `sr_ready_state=RUNNING`),
   - active blockers are `M6P6-B3` and `M6P6-B4`.
4. Root-cause evidence for remaining blockers:
   - pod-level IG POST attempts from EKS runtime timed out (`URLError timed out`),
   - diagnostic pod showed no run-window admission progression while lane refs remained active,
   - this indicates private-runtime egress/path to IG managed edge is not yet materialized for lane workers.
5. Evidence:
   - workflow artifact set: `m6f-streaming-active-20260225T171938Z`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T171938Z/`.
6. Gate posture:
   - `P6` remains fail-closed; `M6.G` stays blocked until non-zero run-window admissions and measured lag evidence are restored.

### P6.C P6 Gate Rollup + Verdict (M6.G)
Goal:
1. adjudicate `P6` from P6.A/P6.B evidence.

Tasks:
1. build `m6g_p6_gate_rollup_matrix.json`.
2. build `m6g_p6_blocker_register.json`.
3. emit `m6g_p6_gate_verdict.json`.

DoD:
- [ ] rollup matrix + blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_P7`/`HOLD_REMEDIATE`/`NO_GO_RESET_REQUIRED`).

Execution status (2026-02-25):
1. Remote authoritative execution:
   - workflow: `.github/workflows/dev_full_m6f_streaming_active.yml`
   - mode: `phase_mode=m6g`
   - run id: `22404445249`
   - execution id: `m6g_p6c_gate_rollup_20260225T155035Z`
2. Adjudication result:
   - `overall_pass=true`
   - `blocker_count=0`
   - `verdict=ADVANCE_TO_P7`
   - `next_gate=M6.H_READY`
3. Evidence:
   - workflow artifact set: `m6g-p6-gate-rollup-20260225T155035Z`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6g_p6c_gate_rollup_20260225T155035Z/`
4. Gate note:
   - this rollup remains historical only after strict-semantic `M6.F` reopened fail-closed on run `22406210783`.

## 4) P6 Verification Catalog
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `P6-V1-ENTRY-CHECK` | verify `P5` verdict and required streaming handles | prevents invalid activation |
| `P6-V2-STREAM-COUNTERS` | collect run-scoped stream/admission counters | proves active streaming |
| `P6-V3-LAG-POSTURE` | compare measured lag with threshold handle | bounded-lag conformance |
| `P6-V4-AMBIGUITY-CHECK` | verify no unresolved publish ambiguity | fail-closed ambiguity control |
| `P6-V5-EVIDENCE-OVERHEAD` | compute `latency p95`, `bytes/event`, `write-rate` | enforces hot-path evidence policy |
| `P6-V6-ROLLUP-VERDICT` | build rollup + blocker register + verdict | deterministic gate closure |

## 5) P6 Blocker Taxonomy
1. `M6P6-B1`: required streaming handles missing/inconsistent.
2. `M6P6-B2`: streaming lane activation failure.
3. `M6P6-B3`: streaming counters do not show active flow.
4. `M6P6-B4`: lag threshold breach.
5. `M6P6-B5`: unresolved publish ambiguity.
6. `M6P6-B6`: rollup/verdict inconsistency.
7. `M6P6-B7`: evidence-overhead budget breach.
8. `M6P6-B8`: durable publish/readback failure.

## 6) P6 Evidence Contract
1. `m6e_stream_activation_entry_snapshot.json`
2. `m6f_streaming_active_snapshot.json`
3. `m6f_streaming_lag_posture.json`
4. `m6f_publish_ambiguity_register.json`
5. `m6f_evidence_overhead_snapshot.json`
6. `m6g_p6_gate_rollup_matrix.json`
7. `m6g_p6_blocker_register.json`
8. `m6g_p6_gate_verdict.json`

## 7) Exit Rule for P6
`P6` can close only when:
1. all `M6P6-B*` blockers are resolved,
2. all P6 DoDs are green,
3. P6 evidence exists in workflow artifacts and durably,
4. verdict is deterministic and blocker-consistent.

Transition:
1. `P7` is blocked until `P6` verdict is `ADVANCE_TO_P7`.
