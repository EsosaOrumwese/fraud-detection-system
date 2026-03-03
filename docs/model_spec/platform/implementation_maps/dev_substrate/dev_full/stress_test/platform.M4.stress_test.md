# Dev Substrate Stress Plan - M4 (Spine Runtime-Lane Readiness)
_Status source of truth: `platform.stress_test.md`_
_This document provides deep stress-planning detail for M4._
_Track: `dev_full` only_
_As of 2026-03-03_

## 0) Purpose
M4 stress validates that spine runtime lanes can bootstrap and hold stable readiness under realistic production posture before M5 preflight/ingress work begins.

M4 stress must prove:
1. runtime-path pinning and lane ownership remain deterministic for the full phase run,
2. startup and steady-state readiness budgets are met for active managed lanes,
3. runtime identity/network/dependency surfaces remain fail-closed under probe pressure,
4. correlation/telemetry continuity and run-scope bindings remain intact across lane boundaries,
5. closure evidence and M5 handoff recommendation are explicit and blocker-consistent.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M4.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s5_20260303T182701Z/stress/m3_execution_summary.json`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

## 2) Stage-A Findings (M4)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M4-ST-F1` | `PREVENT` | M4 runtime-lane scope is multi-lane and coupled; inline planning is too coarse for fail-closed stress execution. | Use a dedicated M4 stress authority with explicit stage gates and blocker mapping. |
| `M4-ST-F2` | `PREVENT` | Runtime-path and lane-handle closure must be revalidated at stress time even if build-plan history is green. | Enforce S0 handle closure + placeholder guard before any runtime-lane stress window. |
| `M4-ST-F3` | `PREVENT` | M4 entry must be gated on latest M3 stress closure (`M4_READY`, `GO`) from the active stress evidence chain. | Enforce strict S0 dependency check on latest successful M3 S5 summary. |
| `M4-ST-F4` | `OBSERVE` | Runtime-lane readiness can regress after infra churn (teardown/rematerialization), especially at ingress edge and stream dependencies. | Add startup/steady readiness stress windows with explicit dependency probes in S1/S2. |
| `M4-ST-F5` | `OBSERVE` | Correlation/telemetry continuity can drift silently under restarts and temporary lane perturbation. | Add continuity/recovery checks and deterministic failure classification in S3. |
| `M4-ST-F6` | `OBSERVE` | Runtime-lane stress can increase cloud API probe volume and cost surface. | Enforce runtime/spend envelope receipts and fail-closed cost checks in all windows. |
| `M4-ST-F7` | `ACCEPT` | M3 closure is green with explicit `M4_READY` handoff recommendation (`GO`). | Use M3 S5 summary as authoritative entry gate for M4 activation. |

## 3) Scope Boundary for M4 Stress
In scope:
1. runtime-path pinning + required handle closure for active M4 lane surfaces.
2. startup and steady-state readiness stress checks for managed spine lanes.
3. runtime identity/IAM + network/dependency conformance checks under stress windows.
4. run-scope, correlation, and telemetry continuity checks.
5. bounded failure-injection and recovery checks for runtime-lane readiness posture.
6. M5 readiness recommendation publication from M4 closure rollup.

Out of scope:
1. oracle preflight and ingress publication semantics (`M5+`).
2. full control+ingress throughput objective (`M6+`).
3. model training/evolution phases (`M10+`).

## 4) M4 Stress Handle Packet (Pinned)
1. `M4_STRESS_PROFILE_ID = "spine_runtime_lane_readiness_stress_v0"`.
2. `M4_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m4_blocker_register.json"`.
3. `M4_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m4_execution_summary.json"`.
4. `M4_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m4_decision_log.json"`.
5. `M4_STRESS_REQUIRED_ARTIFACTS = "m4_stagea_findings.json,m4_lane_matrix.json,m4_probe_latency_throughput_snapshot.json,m4_control_rail_conformance_snapshot.json,m4_secret_safety_snapshot.json,m4_cost_outcome_receipt.json,m4_blocker_register.json,m4_execution_summary.json,m4_decision_log.json"`.
6. `M4_STRESS_MAX_RUNTIME_MINUTES = 180`.
7. `M4_STRESS_MAX_SPEND_USD = 40`.
8. `M4_STRESS_STARTUP_BUDGET_SECONDS = 900`.
9. `M4_STRESS_STEADY_WINDOW_MINUTES = 10`.
10. `M4_STRESS_BURST_WINDOW_MINUTES = 5`.
11. `M4_STRESS_RECOVERY_BUDGET_SECONDS = 300`.
12. `M4_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M5_READY"`.

Registry-backed required handles for execution:
1. `PHASE_RUNTIME_PATH_MODE`
2. `PHASE_RUNTIME_PATH_PIN_REQUIRED`
3. `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED`
4. `RUNTIME_DEFAULT_STREAM_ENGINE`
5. `RUNTIME_DEFAULT_INGRESS_EDGE`
6. `RUNTIME_EKS_USE_POLICY`
7. `FLINK_RUNTIME_MODE`
8. `FLINK_APP_RTDL_IEG_OFP_V0`
9. `MSK_CLUSTER_ARN`
10. `SSM_MSK_BOOTSTRAP_BROKERS_PATH`
11. `APIGW_IG_API_ID`
12. `LAMBDA_IG_HANDLER_NAME`
13. `DDB_IG_IDEMPOTENCY_TABLE`
14. `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
15. `SR_READY_COMMIT_AUTHORITY`
16. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
17. `S3_EVIDENCE_BUCKET`
18. `CLOUDWATCH_LOG_GROUP_PREFIX`
19. `OTEL_ENABLED`
20. `CORRELATION_REQUIRED_FIELDS`
21. `CORRELATION_HEADERS_REQUIRED`
22. `CORRELATION_ENFORCEMENT_FAIL_CLOSED`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M4 stress stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry gate closure | `S0` | required handle closure + valid M3->M4 handoff gate |
| Lane startup + readiness baseline | `S1` | startup and readiness receipt within pinned budgets |
| Steady-window dependency stress | `S2` | no new dependency/control drift under steady probe window |
| Failure/recovery posture | `S3` | deterministic injection classification + recovery pass |
| Remediation/selective rerun | `S4` | blocker closure adjudication with targeted rerun policy |
| Closure rollup + M5 handoff | `S5` | blocker-free verdict + explicit `M5_READY` recommendation |

## 6) Stress Topology (M4)
1. Component sequence:
   - `M4.A/B` (authority + runtime path pinning),
   - `M4.C/D/E` (identity/network/runtime readiness),
   - `M4.F/G/H/I/J` (continuity, recovery, rollup, handoff).
2. Plane sequence:
   - `runtime_path_plane`,
   - `runtime_health_plane`,
   - `continuity_recovery_plane`.
3. Integrated windows:
   - `S1_startup_baseline`,
   - `S2_steady_dependency`,
   - `S3_failure_recovery`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M4-ST-S0` - Authority and entry-gate closure
Objective:
1. fail-closed validation that M4 runtime-lane stress can run with complete authority and valid M3 entry handoff.

Actions:
1. validate required M4 handles and placeholder guards.
2. validate runtime-path law handles (`single_active`/pin required/no switch).
3. validate latest successful M3 S5 handoff (`next_gate=M4_READY`, `m4_readiness_recommendation=GO`).
4. emit Stage-A findings + lane matrix + blocker register.

Pass gate:
1. required M4 handle set complete and non-placeholder.
2. runtime-path law checks pass.
3. M3 handoff evidence is valid and readable.
4. full S0 artifact set exists and is readable.

### 7.2 `M4-ST-S1` - Startup and readiness baseline window
Objective:
1. validate startup-time and readiness posture for active runtime lanes against pinned budgets.

Window:
1. startup capture until all required probes pass or startup budget expires.
2. steady baseline hold for `M4_STRESS_STEADY_WINDOW_MINUTES`.

Pass gate:
1. startup/readiness budget satisfied.
2. no control/correlation drift versus S0 baseline.
3. no secret leakage or unattributed spend.

### 7.3 `M4-ST-S2` - Steady dependency and contention window
Objective:
1. validate runtime-lane readiness remains stable under repeated dependency/control probing.

Window:
1. steady dependency window for `M4_STRESS_STEADY_WINDOW_MINUTES`.
2. bounded burst sub-window for `M4_STRESS_BURST_WINDOW_MINUTES`.

Pass gate:
1. no new dependency/control drift versus S1 baseline.
2. no sustained instability signals (error-rate/failure-streak within policy).
3. no secret leakage and no unattributed spend.

### 7.4 `M4-ST-S3` - Controlled failure-injection and recovery window
Objective:
1. prove deterministic runtime-lane fault classification and fail-closed recovery behavior.

Injection set (bounded):
1. dependency-path unavailable simulation.
2. runtime binding/correlation contract mismatch simulation.
3. stale lane-health/lock conflict simulation.

Pass gate:
1. all injections classified deterministically.
2. fail-closed behavior is explicit (no silent fallback).
3. recovery probes return green within recovery budget.

### 7.5 `M4-ST-S4` - Remediation and selective rerun
Objective:
1. close blockers with minimal-cost targeted reruns.

Execution rule:
1. rank blockers by severity and closure cost.
2. map blocker -> remediation lane -> rerun scope.
3. rerun only failed windows (`S1/S2/S3`) if blockers exist.
4. emit explicit no-op remediation receipt if blocker set is empty.

Pass gate:
1. all open non-waived `M4-ST-B*` blockers closed.
2. remediation outcome is evidence-backed and scoped.

### 7.6 `M4-ST-S5` - Closure rollup and M5 handoff recommendation
Objective:
1. publish M4 closure verdict and explicit M5 readiness posture.

Actions:
1. aggregate latest successful `S0..S4` summaries + blocker registers.
2. enforce artifact, runtime, and spend envelope checks.
3. emit deterministic `M5` recommendation (`GO`/`NO_GO`) and next gate.

Pass gate:
1. no open non-waived `M4-ST-B*` blockers.
2. required artifacts complete/readable.
3. runtime/spend envelopes within pinned bounds.
4. next gate matches expected pass gate (`M5_READY`).

## 8) Blocker Taxonomy (M4 Stress)
1. `M4-ST-B1`: missing/unresolved required handle or authority contract.
2. `M4-ST-B2`: runtime-path pinning or startup/readiness budget failure.
3. `M4-ST-B3`: identity/IAM/network/dependency readiness failure.
4. `M4-ST-B4`: run-scope/correlation continuity drift.
5. `M4-ST-B5`: runtime-lane health/availability instability.
6. `M4-ST-B6`: secret-path violation or plaintext leakage.
7. `M4-ST-B7`: failure-injection classification or recovery failure.
8. `M4-ST-B8`: unattributed spend or budget envelope breach.
9. `M4-ST-B9`: artifact/evidence contract incomplete or unreadable.

Any open `M4-ST-B*` blocks M4 stress closure.

## 9) Evidence Contract
Required artifacts for each M4 stress window:
1. `m4_stagea_findings.json`.
2. `m4_lane_matrix.json`.
3. `m4_probe_latency_throughput_snapshot.json`.
4. `m4_control_rail_conformance_snapshot.json`.
5. `m4_secret_safety_snapshot.json`.
6. `m4_cost_outcome_receipt.json`.
7. `m4_blocker_register.json`.
8. `m4_execution_summary.json`.
9. `m4_decision_log.json`.

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M4 stress authority file created.
- [x] Stage-A findings (`PREVENT/OBSERVE/ACCEPT`) pinned.
- [x] M4 stress handle packet pinned.
- [x] Capability-lane coverage mapped.
- [x] Stress topology and execution sequence pinned.
- [x] Execution-grade runbook for `S0..S5` pinned.
- [x] Blocker taxonomy and evidence contract pinned.
- [ ] First M4 managed stress window executed.

## 11) Immediate Next Actions
1. Implement `scripts/dev_substrate/m4_stress_runner.py` with `S0` authority/entry-gate stage.
2. Execute `M4-ST-S0` and open fail-closed blockers on any handle or entry-gate drift.
3. Advance to `M4-ST-S1` only if `S0` closes with zero open blockers.

## 12) Execution Progress
1. Planning file created and routed.
2. No M4 stress window executed yet in this authority.
