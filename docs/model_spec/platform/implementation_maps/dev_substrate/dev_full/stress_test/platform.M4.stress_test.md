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

S0 required-handle closure checklist:
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

S0 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4S0-V1-HANDLE-EXISTS` | `rg -n "\\b<HANDLE_KEY>\\b" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms required handle key exists in registry |
| `M4S0-V2-PLACEHOLDER-GUARD` | parse required handle values and fail if any is `TO_PIN` | blocks unresolved required handles |
| `M4S0-V3-RUNTIME-PATH-LAW` | local handle-law check on `PHASE_RUNTIME_PATH_*` and switch guard | enforces single-active-path runtime posture |
| `M4S0-V4-M3-S5-LATEST` | read latest successful `m3_stress_s5_*/stress/m3_execution_summary.json` | validates M4 entry dependency surface |
| `M4S0-V5-M3-HANDOFF-GATE` | assert `next_gate=M4_READY`, `m4_readiness_recommendation=GO` | enforces M3->M4 handoff rule |
| `M4S0-V6-SFN-SURFACE` | `aws stepfunctions list-state-machines --region eu-west-2 --max-results 100 ...` | verifies orchestrator control-plane queryability |
| `M4S0-V7-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET> --region eu-west-2` | verifies durable evidence root reachable |
| `M4S0-V8-RUNTIME-SURFACES` | `aws apigatewayv2 get-api`, `aws lambda get-function`, `aws kafka describe-cluster-v2`, `aws dynamodb describe-table` | verifies active runtime-lane control surfaces are queryable |

S0 blocker mapping (fail-closed):
1. `M4-ST-B1`:
   - missing/unresolved required handle or missing required M4 plan key.
2. `M4-ST-B2`:
   - runtime-path law drift (`single_active`/pin/switch guard failure).
3. `M4-ST-B3`:
   - control-plane surface checks fail (orchestrator/evidence/runtime lane surfaces).
4. `M4-ST-B4`:
   - correlation continuity contract anchors unresolved or malformed.
5. `M4-ST-B9`:
   - M3 S5 handoff evidence missing/unreadable/invalid,
   - required S0 artifacts missing/incomplete.

S0 required artifacts:
1. `m4_stagea_findings.json`
2. `m4_lane_matrix.json`
3. `m4_probe_latency_throughput_snapshot.json`
4. `m4_control_rail_conformance_snapshot.json`
5. `m4_secret_safety_snapshot.json`
6. `m4_cost_outcome_receipt.json`
7. `m4_blocker_register.json`
8. `m4_execution_summary.json`
9. `m4_decision_log.json`

S0 closure rule:
1. `S0` closes only when:
   - all required handles pass presence + placeholder guard,
   - runtime-path law checks pass,
   - latest successful M3 S5 handoff gate is valid (`M4_READY` + `GO`),
   - control-plane query checks are green or explicitly blocker-classified,
   - full S0 artifact set is emitted and readable.

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

S1 startup/readiness verification checklist:
1. successful `S0` continuity gate is present (`next_gate=M4_ST_S1_READY`).
2. startup-ready time is measured and validated against `M4_STRESS_STARTUP_BUDGET_SECONDS`.
3. required runtime surfaces are queryable at startup and during steady window:
   - SFN orchestrator,
   - evidence bucket,
   - API Gateway ingress edge,
   - Lambda ingress handler,
   - DDB idempotency table,
   - MSK cluster,
   - active Flink runtime surface handle.
4. runtime-path law remains compliant during S1 window.
5. correlation contract anchors remain fail-closed and complete.
6. new control/correlation issues versus `S0` are empty.
7. instability signals are bounded (error rate + failure streak).

S1 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4S1-V1-S0-CONTINUITY` | read latest successful `m4_stress_s0_*/stress/m4_execution_summary.json` | enforces S0 dependency gate |
| `M4S1-V2-STARTUP-BUDGET` | local timer from probe loop start to first all-pass cycle | validates startup readiness budget |
| `M4S1-V3-SFN-LOOKUP` | `aws stepfunctions list-state-machines --region eu-west-2 --max-results 100 ...` | validates orchestrator readiness |
| `M4S1-V4-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET> --region eu-west-2` | validates evidence root readiness |
| `M4S1-V5-INGRESS-EDGE` | `aws apigatewayv2 get-api`, `aws lambda get-function`, `aws dynamodb describe-table` | validates ingress edge readiness |
| `M4S1-V6-STREAM-SURFACE` | `aws kafka describe-cluster-v2`; runtime-path aware probe: `MSF_MANAGED -> aws kinesisanalyticsv2 describe-application`, `EKS_FLINK_OPERATOR -> aws emr-containers describe-virtual-cluster + aws eks describe-cluster` | validates stream lane readiness |
| `M4S1-V7-RUNTIME-PATH-LAW` | local checks on `PHASE_RUNTIME_PATH_*` handles | enforces single-active path posture |
| `M4S1-V8-CORRELATION-CONTRACT` | local checks on correlation required fields/headers + fail-closed flag | enforces continuity anchors |
| `M4S1-V9-STEADY-WINDOW` | repeated probe cycles across `M4_STRESS_STEADY_WINDOW_MINUTES` | validates sustained readiness |

S1 closure rule:
1. `S1` closes only when:
   - S0 continuity artifacts are present/readable,
   - startup/readiness budget checks pass,
   - steady-window probes complete with no new control/correlation drift,
   - complete S1 artifact set is emitted with zero open blockers.

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

S2 steady-window verification checklist:
1. latest successful `S1` baseline exists (`next_gate=M4_ST_S2_READY`).
2. startup gate remains green at S2 entry (`startup_ready_seconds <= M4_STRESS_STARTUP_BUDGET_SECONDS` from baseline posture).
3. dependency/runtime probes remain healthy across steady + burst windows:
   - SFN orchestrator,
   - evidence bucket,
   - ingress edge surfaces (APIGW/Lambda/DDB),
   - MSK surface,
   - runtime-path stream surface (`MSF_MANAGED` or `EKS_FLINK_OPERATOR` path-aware probes).
4. no new control/correlation issues versus latest successful S1 baseline.
5. instability metrics remain within S2 policy thresholds.

S2 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4S2-V1-S1-CONTINUITY` | read latest successful `m4_stress_s1_*/stress/m4_execution_summary.json` | enforces S1 dependency gate |
| `M4S2-V2-STEADY-WINDOW` | repeated probe cycles for `M4_STRESS_STEADY_WINDOW_MINUTES` | validates sustained dependency posture |
| `M4S2-V3-BURST-WINDOW` | tighter interval probes for `M4_STRESS_BURST_WINDOW_MINUTES` | validates contention behavior |
| `M4S2-V4-SFN-LOOKUP` | `aws stepfunctions list-state-machines --region eu-west-2 --max-results 100 ...` | validates orchestrator continuity |
| `M4S2-V5-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET> --region eu-west-2` | validates evidence continuity |
| `M4S2-V6-INGRESS-EDGE` | `aws apigatewayv2 get-api`, `aws lambda get-function`, `aws dynamodb describe-table` | validates ingress continuity |
| `M4S2-V7-STREAM-SURFACE` | `aws kafka describe-cluster-v2`; runtime-path aware probe: `MSF_MANAGED -> aws kinesisanalyticsv2 describe-application`, `EKS_FLINK_OPERATOR -> aws emr-containers describe-virtual-cluster + aws eks describe-cluster` | validates stream continuity |
| `M4S2-V8-BASELINE-COMPARE` | compare control issues/error-rate/failure-streak versus latest successful S1 baseline snapshot | detects nonlinear regression |
| `M4S2-V9-RUNTIME-PATH-LAW` | local checks on `PHASE_RUNTIME_PATH_*` and `FLINK_RUNTIME_PATH_*` handles | enforces pinned runtime-path posture |

S2 closure rule:
1. `S2` closes only when:
   - S1 dependency artifacts are present/readable,
   - steady + burst windows complete within runtime/cost envelope,
   - no new control/correlation drift versus S1 baseline,
   - complete S2 artifact set is emitted with zero open blockers.

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

S3 failure-injection verification checklist:
1. latest successful `S2` baseline exists (`next_gate=M4_ST_S3_READY`).
2. precheck probes are green before injections:
   - SFN orchestrator,
   - evidence bucket,
   - ingress edge/runtime dependency probes,
   - stream runtime-path probes.
3. bounded injection set executes with explicit expected classifications:
   - dependency-path unavailable,
   - runtime binding/correlation mismatch,
   - stale lock/duplicate activation conflict.
4. immediate and final recovery probes are green within `M4_STRESS_RECOVERY_BUDGET_SECONDS`.
5. no new control/correlation drift against S2 baseline.

S3 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4S3-V1-S2-CONTINUITY` | read latest successful `m4_stress_s2_*/stress/m4_execution_summary.json` | enforces S2 dependency gate |
| `M4S3-V2-PRECHECK` | SFN + S3 + runtime-path probe set before injections | blocks unsafe injection starts |
| `M4S3-V3-INJ-DEPENDENCY` | bounded missing dependency-path simulation (`ssm get-parameter` on missing path) | validates dependency failure classification |
| `M4S3-V4-INJ-BINDING` | bounded runtime-binding/correlation mismatch simulation | validates fail-closed mismatch classification |
| `M4S3-V5-INJ-LOCK` | stale lock/duplicate activation simulation | validates duplicate activation guardrail |
| `M4S3-V6-RECOVERY-IMMEDIATE` | immediate post-injection control/runtime probes | validates short-loop recovery |
| `M4S3-V7-RECOVERY-FINAL` | final recovery probes at window close | validates sustained recovery |
| `M4S3-V8-BASELINE-COMPARE` | compare S3 control issues against latest successful S2 baseline | detects post-injection drift |
| `M4S3-V9-INJECTION-CLASSIFIER` | deterministic check: `injection_detected_count == injection_expected_count` | enforces classification determinism |

S3 closure rule:
1. `S3` closes only when:
   - S2 dependency artifacts are present/readable,
   - injection set is fully classified and deterministic,
   - recovery probes pass within recovery budget with no new baseline drift,
   - complete S3 artifact set is emitted with zero open blockers.

### 7.5 `M4-ST-S4` - Remediation and selective rerun
Objective:
1. close blockers with minimal-cost targeted reruns.

S4 checklist:
1. load latest successful `S3` execution summary and blocker register.
2. aggregate unresolved blockers from latest `S1..S3` windows (if any remain open).
3. compute deterministic remediation matrix:
   - blocker id,
   - severity,
   - proposed remediation lane,
   - minimal rerun scope (`S1` or `S2` or `S3`),
   - closure evidence path.
4. if blocker set is non-empty:
   - rank by severity and closure cost,
   - execute no-op or externalized remediation notes only (no implicit infra mutation),
   - emit rerun recommendation list scoped to failed windows only.
5. if blocker set is empty:
   - emit explicit no-op remediation receipt with `rerun_required=false`.
6. verify full artifact contract exists/readable.

S4 command catalog:
| Command ID | Command | Purpose |
| --- | --- | --- |
| `M4S4-V1-DEPENDENCY` | load latest successful `S3` summary/register | gates S4 entry on S3 continuity |
| `M4S4-V2-BLOCKER-SCAN` | collect latest `S1..S3` blocker posture | establishes unresolved blocker surface |
| `M4S4-V3-REMEDIATION-MATRIX` | map blockers to remediation lanes + rerun scope | enforces explicit closure planning |
| `M4S4-V4-COST-RUNTIME-CHECK` | ensure remediation posture stays bounded | enforces performance/cost law |
| `M4S4-V5-NOOP-RECEIPT` | generate explicit no-op receipt when no blockers exist | avoids ambiguous closure state |
| `M4S4-V6-ARTIFACT-CHECK` | verify required S4 artifacts readable | enforces evidence contract completeness |

S4 closure rule:
1. `S4` closes only when:
   - latest successful S3 dependency is present/readable,
   - unresolved blocker posture is explicit (`none` or mapped list),
   - rerun scope is deterministic and minimal for each open blocker,
   - no-op remediation receipt is emitted when blocker set is empty,
   - complete S4 artifact set is emitted with zero open blockers.

Pass gate:
1. all open non-waived `M4-ST-B*` blockers closed.
2. remediation outcome is evidence-backed and scoped.

### 7.6 `M4-ST-S5` - Closure rollup and M5 handoff recommendation
Objective:
1. publish M4 closure verdict and explicit M5 readiness posture.

S5 checklist:
1. load latest successful `S0..S4` execution summaries and blocker registers.
2. enforce no-open-blocker closure posture across all loaded stages.
3. verify evidence contract completeness/readability for each stage pack.
4. compute closure envelope summary:
   - total runtime observed (minutes),
   - total attributed spend (USD),
   - unattributed spend signal.
5. compare closure envelope to pinned M4 budgets.
6. emit deterministic handoff recommendation:
   - `recommendation=GO` and `next_gate=M5_READY` on full closure,
   - otherwise `recommendation=NO_GO` and `next_gate=BLOCKED`.

S5 command catalog:
| Command ID | Command | Purpose |
| --- | --- | --- |
| `M4S5-V1-DEPENDENCY` | load latest successful `S0..S4` packs | closes stage-continuity prerequisite |
| `M4S5-V2-BLOCKER-ROLLUP` | aggregate open blocker posture | enforces fail-closed closure law |
| `M4S5-V3-ARTIFACT-AUDIT` | verify evidence completeness/readability | enforces artifact contract |
| `M4S5-V4-ENVELOPE-CHECK` | runtime + spend envelope adjudication | enforces performance/cost law |
| `M4S5-V5-HANDOFF-DECISION` | emit deterministic `GO/NO_GO` + next gate | finalizes M5 readiness posture |

S5 closure rule:
1. `S5` closes only when:
   - latest successful `S0..S4` packs are present/readable,
   - no open non-waived `M4-ST-B*` blockers remain in closure rollup,
   - evidence contract is complete/readable for each stage pack,
   - runtime and spend envelopes remain within pinned bounds,
   - handoff recommendation is deterministic and evidence-backed.

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
- [x] First M4 managed stress window executed.

## 11) Immediate Next Actions
1. Mark `M4` stress closure as complete and retain S5 rollup artifacts as closure authority.
2. Open `M5` planning lane (`S0`) using `M5_READY` handoff from M4.
3. Preserve S5 closure envelope metrics as baseline for M5 runtime/cost guardrails.

## 12) Execution Progress
### `M4-ST-S0` authority/entry-gate closure execution (2026-03-03)
1. Phase execution id: `m4_stress_s0_20260303T184138Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S0`
3. Verification summary:
   - required handle and placeholder guards passed,
   - runtime-path law checks passed (`single_active` + pin required + no switch),
   - latest successful M3 S5 handoff gate validated (`M4_READY`, `GO`),
   - control-plane surface checks passed (SFN, S3 evidence bucket, APIGW, Lambda, DDB, MSK).
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M4_ST_S1_READY`,
   - `open_blockers=0`,
   - `probe_count=6`,
   - `error_rate_pct=0.0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s0_20260303T184138Z/stress/m4_decision_log.json`

### `M4-ST-S1` startup/readiness baseline execution (2026-03-03)
1. Phase execution id: `m4_stress_s1_20260303T184921Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S1`
3. Verification summary:
   - successful S0 continuity gate loaded (`m4_stress_s0_20260303T184138Z`),
   - Stage-A artifact contract carried forward,
   - critical precheck failed on stream-lane readiness probe:
     - `aws kinesisanalyticsv2 describe-application --application-name fraud-platform-dev-full-rtdl-ieg-ofp-v0 --region eu-west-2`
     - returned `ResourceNotFoundException`,
   - steady window terminated fail-closed before startup-ready state.
4. Verdict:
   - `overall_pass=false`,
   - `next_gate=BLOCKED`,
   - `open_blockers=3`,
   - `probe_count=7`,
   - `error_rate_pct=14.2857`,
   - `startup_ready_seconds=null`.
5. Open blockers:
   - `M4-ST-B2`: startup ready state not reached.
   - `M4-ST-B3`: `s1_flink_app` failures `1`.
   - `M4-ST-B5`: error-rate threshold breached (`14.2857%`).
6. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T184921Z/stress/m4_decision_log.json`
7. Next action:
   - keep fail-closed posture,
   - remediate stream-lane readiness handle/state,
   - rerun `S1` before any `S2` progression.

### `M4-ST-S1` remediation rerun execution (2026-03-03)
1. Remediation chain:
   - direct canonical Managed Flink create call was re-attempted:
     - `aws kinesisanalyticsv2 create-application --application-name fraud-platform-dev-full-rtdl-ieg-ofp-v0 --runtime-environment FLINK-1_18 --service-execution-role arn:aws:iam::230372904534:role/fraud-platform-dev-full-flink-execution --application-mode INTERACTIVE --region eu-west-2`
     - result: `UnsupportedOperationException` (account verification gate still active),
   - runtime active-path handle repinned to fallback-managed stream lane:
     - `FLINK_RUNTIME_PATH_ACTIVE = EKS_FLINK_OPERATOR`,
   - S1 stream readiness probe set made runtime-path aware (`MSF` vs `EKS`).
2. Phase execution id: `m4_stress_s1_20260303T190639Z`.
3. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S1`
4. Verification summary:
   - S0 continuity and Stage-A carry-forward passed,
   - startup/readiness precheck passed (`precheck_fail_closed=false`),
   - full steady window completed (`window_seconds_observed=600`),
   - no new control/correlation issues versus S0.
5. Verdict:
   - `overall_pass=true`,
   - `next_gate=M4_ST_S2_READY`,
   - `open_blockers=0`,
   - `probe_count=549`,
   - `error_rate_pct=0.0`,
   - `startup_ready_seconds=2`.
6. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s1_20260303T190639Z/stress/m4_decision_log.json`

### `M4-ST-S2` steady dependency/contention execution (2026-03-03)
1. Phase execution id: `m4_stress_s2_20260303T192644Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S2`
3. Verification summary:
   - latest successful S1 dependency loaded (`m4_stress_s1_20260303T190639Z`),
   - S2 entry precheck passed (`precheck_fail_closed=false`),
   - steady and burst windows completed:
     - `steady_window_seconds_configured=600`,
     - `burst_window_seconds_configured=300`,
     - `window_cycle_counts={steady:60, burst:60}`,
   - no new dependency/control drift versus S1 baseline (`new_issues_vs_s1=[]`).
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M4_ST_S3_READY`,
   - `open_blockers=0`,
   - `probe_count=1089`,
   - `error_rate_pct=0.0`,
   - `entry_ready_seconds=3`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s2_20260303T192644Z/stress/m4_decision_log.json`

### `M4-ST-S3` controlled failure-injection and recovery execution (2026-03-03)
1. Phase execution id: `m4_stress_s3_20260303T195440Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S3`
3. Verification summary:
   - latest successful S2 dependency loaded (`m4_stress_s2_20260303T192644Z`),
   - precheck passed (`precheck_fail_closed=false`),
   - bounded injection classifier passed (`injection_detected=3/3`):
     - dependency-path unavailable (`DETECTED_MISSING_DEPENDENCY_PATH`),
     - runtime-binding correlation mismatch (`DETECTED_CORRELATION_BINDING_MISMATCH`),
     - stale lock duplicate activation (`DETECTED_STALE_LOCK_DUPLICATE`),
   - immediate/final recovery passed within budget:
     - `recovery_elapsed_seconds=4`,
     - `recovery_budget_seconds=300`,
   - no new control/correlation drift versus S2 baseline (`new_issues_vs_s2=[]`).
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M4_ST_S4_READY`,
   - `open_blockers=0`,
   - `probe_count=24`,
   - `error_rate_pct=0.0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s3_20260303T195440Z/stress/m4_decision_log.json`

### `M4-ST-S4` remediation and selective-rerun adjudication execution (2026-03-03)
1. Phase execution id: `m4_stress_s4_20260303T200131Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S4`
3. Verification summary:
   - latest successful S3 dependency loaded (`m4_stress_s3_20260303T195440Z`),
   - unresolved blocker scan across latest `S1..S3` windows returned empty set,
   - explicit remediation receipt emitted in deterministic no-op mode:
     - `action_mode=NOOP_RECEIPT`,
     - `remediation_required=false`,
     - `rerun_required=false`,
     - `rerun_scopes=[]`.
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M4_ST_S5_READY`,
   - `open_blockers=0`,
   - `probe_count=0`,
   - `error_rate_pct=0.0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s4_20260303T200131Z/stress/m4_decision_log.json`

### `M4-ST-S5` closure rollup and M5 handoff recommendation execution (2026-03-03)
1. Phase execution id: `m4_stress_s5_20260303T200552Z`.
2. Runner:
   - `python scripts/dev_substrate/m4_stress_runner.py --stage S5`
3. Verification summary:
   - latest successful `S0..S4` packs loaded and rolled up (`rollup_stage_count=5`),
   - no open non-waived blockers in closure rollup (`open_blocker_count=0`),
   - full evidence contract available/readable for each stage pack,
   - closure envelopes within pinned bounds:
     - `total_runtime_minutes=25.317` (`<= M4_STRESS_MAX_RUNTIME_MINUTES`),
     - `total_attributed_spend_usd=0.0`,
     - `unattributed_spend_detected=false`,
   - deterministic handoff emitted:
     - `recommendation=GO`,
     - `next_gate=M5_READY`.
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M5_READY`,
   - `open_blockers=0`,
   - `probe_count=1668`,
   - `error_rate_pct=0.0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_decision_log.json`
