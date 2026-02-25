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
   - `FLINK_APP_WSP_STREAM_V0`
   - `FLINK_CHECKPOINT_INTERVAL_MS`
   - `WSP_MAX_INFLIGHT`
   - `WSP_RETRY_MAX_ATTEMPTS`
   - `WSP_RETRY_BACKOFF_MS`
   - `WSP_STOP_ON_NONRETRYABLE`
   - `RTDL_CAUGHT_UP_LAG_MAX` (lag threshold anchor for M6 streaming checks until M6-specific lag handle is pinned)

DoD:
- [ ] entry checks pass with no unresolved required handles.
- [ ] `m6e_stream_activation_entry_snapshot.json` committed locally and durably.

Execution status (2026-02-25):
1. Executed:
   - `m6e_p6a_stream_entry_20260225T044348Z`
   - local: `runs/dev_substrate/dev_full/m6/m6e_p6a_stream_entry_20260225T044348Z/`
2. Result:
   - `overall_pass=false`, `next_gate=HOLD_REMEDIATE`.
3. Active blockers:
   - `M6P6-B1`: `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` missing in prior handle-closure artifact surface.
   - `M6P6-B2`: required Flink apps absent (`fraud-platform-dev-full-wsp-stream-v0`, `fraud-platform-dev-full-sr-ready-v0`).
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6e_p6a_stream_entry_20260225T044348Z/m6e_stream_activation_entry_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6e_p6a_stream_entry_20260225T044348Z/m6e_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6e_p6a_stream_entry_20260225T044348Z/m6e_execution_summary.json`
5. Superseding rerun:
   - `m6e_p6a_stream_entry_20260225T044618Z` narrowed blocker set to only `M6P6-B2` (missing Flink apps).
   - `M6P6-B1` was cleared using authoritative registry-backed handle resolution.

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
- [ ] `m6f_streaming_active_snapshot.json` and `m6f_evidence_overhead_snapshot.json` committed locally and durably.

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
3. P6 evidence exists locally and durably,
4. verdict is deterministic and blocker-consistent.

Transition:
1. `P7` is blocked until `P6` verdict is `ADVANCE_TO_P7`.
