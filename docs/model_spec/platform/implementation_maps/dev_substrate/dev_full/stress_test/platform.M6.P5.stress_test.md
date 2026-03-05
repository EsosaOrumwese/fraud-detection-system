# Dev Substrate Stress Plan - M6.P5 (P5 READY_PUBLISHED)
_Parent authority: `platform.M6.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_

## 0) Purpose
M6.P5 stress validates READY publication closure under realistic production posture before streaming activation (`P6`).

M6.P5 stress must prove:
1. READY entry prerequisites are complete and run-scope consistent.
2. READY commit authority is Step Functions with deterministic receipt evidence.
3. duplicate and ambiguous READY outcomes are fail-closed.
4. control-topic publication is stable under sustained and burst commit probes.
5. P5 rollup emits deterministic verdict (`ADVANCE_TO_P6` only when blocker-free).

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P5.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. latest successful M6 parent `S0` receipt.

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) Stage-A Findings (M6.P5)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M6P5-ST-F1` | `PREVENT` | P5 entry must inherit valid M6 parent gate and M5-origin run continuity. | Enforce `S0` dependency chain (`M5 -> M6.S0 -> M6.P5.S0`) before component stress. |
| `M6P5-ST-F2` | `PREVENT` | READY commit authority can silently drift away from Step Functions when fallback logic is introduced. | Require Step Functions authority proof in every commit receipt. |
| `M6P5-ST-F3` | `PREVENT` | Duplicate READY outcomes can appear under retries and create ambiguous control state. | Keep duplicate/ambiguity checks fail-closed at S2/S3. |
| `M6P5-ST-F4` | `OBSERVE` | Control-topic publication may pass single probes but fail under short burst commits. | Add sustained+burst commit windows in S3. |
| `M6P5-ST-F5` | `OBSERVE` | Receipt publication/readback can fail independently of publish success. | Keep durable readback checks mandatory in each state artifact set. |
| `M6P5-ST-F6` | `ACCEPT` | Existing build authority already defines deterministic P5 verdict semantics. | Reuse verdict taxonomy with stress-specific blocker surface checks. |

## 3) Scope Boundary for M6.P5 Stress
In scope:
1. READY entry precheck and run-scope continuity.
2. Step Functions READY commit authority and receipt closure.
3. duplicate/ambiguity closure under retry pressure.
4. deterministic P5 rollup and verdict emission.

Out of scope:
1. streaming activation/lag closure (`P6`).
2. ingest commit evidence closure (`P7`).
3. parent integrated cross-plane stress windows.

## 4) M6.P5 Stress Handle Packet (Pinned)
1. `M6P5_STRESS_PROFILE_ID = "ready_published_stress_v0"`.
2. `M6P5_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p5_blocker_register.json"`.
3. `M6P5_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p5_execution_summary.json"`.
4. `M6P5_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p5_decision_log.json"`.
5. `M6P5_STRESS_REQUIRED_ARTIFACTS = "m6p5_stagea_findings.json,m6p5_lane_matrix.json,m6p5_probe_latency_throughput_snapshot.json,m6p5_control_rail_conformance_snapshot.json,m6p5_secret_safety_snapshot.json,m6p5_cost_outcome_receipt.json,m6p5_blocker_register.json,m6p5_execution_summary.json,m6p5_decision_log.json,m6p5_gate_verdict.json"`.
6. `M6P5_STRESS_MAX_RUNTIME_MINUTES = 120`.
7. `M6P5_STRESS_MAX_SPEND_USD = 20`.
8. `M6P5_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_P6"`.
9. `M6P5_STRESS_READY_REPETITIONS = 25`.
10. `M6P5_STRESS_BURST_FACTOR = 3`.
11. `M6P5_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles for M6.P5:
1. `FP_BUS_CONTROL_V1`
2. `READY_MESSAGE_FILTER`
3. `SR_READY_COMMIT_AUTHORITY`
4. `SR_READY_COMMIT_STATE_MACHINE`
5. `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF`
6. `SR_READY_COMMIT_RECEIPT_PATH_PATTERN`
7. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
8. `M6_HANDOFF_PACK_PATH_PATTERN`
9. `S3_EVIDENCE_BUCKET`
10. `S3_RUN_CONTROL_ROOT_PATTERN`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M6.P5 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry closure | `S0` | required handles + M6 parent dependency closure |
| READY entry precheck | `S1` | run continuity and Step Functions surface pass |
| READY commit authority | `S2` | commit receipt with SFN execution reference |
| READY duplicate/ambiguity + burst checks | `S3` | no unresolved duplicate/ambiguity under stress window |
| Remediation + selective rerun | `S4` | blocker-specific rerun closure evidence |
| P5 rollup + verdict | `S5` | deterministic verdict `ADVANCE_TO_P6` |

## 6) Stress Topology (M6.P5)
1. Component sequence:
   - `P5.A` entry checks,
   - `P5.B` commit authority,
   - `P5.C` duplicate/ambiguity closure,
   - `P5.D` rollup.
2. Plane sequence:
   - `sr_control_plane`,
   - `control_topic_plane`,
   - `p5_rollup_plane`.
3. Integrated windows:
   - `m6p5_s3_sustained_window`,
   - `m6p5_s3_burst_window`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M6P5-ST-S0` - Authority and entry-gate closure
Objective:
1. validate P5 execution authority, dependency continuity, and required handles.

Entry criteria:
1. latest successful M6 parent `S0` summary/register are readable.
2. no unresolved planning decision exists in section `4`.

Required inputs:
1. parent `M6-ST-S0` summary/register.
2. required handle packet in section `4`.
3. P5 authority docs listed in section `1`.

Execution steps:
1. enforce parent dependency continuity (`next_gate=M6_ST_S1_READY` or explicit parent allowance for P5 execution lane).
2. validate all required P5 handles are present and non-placeholder.
3. validate SFN state machine surface queryability.
4. run bounded evidence publish/readback probe.
5. emit stage findings, lane matrix, blocker register, execution summary, and decision log.

Fail-closed blocker mapping:
1. `M6P5-ST-B1`: missing/inconsistent required handle.
2. `M6P5-ST-B2`: invalid parent dependency continuity.
3. `M6P5-ST-B8`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `12` minutes.
2. max spend: `$2`.

Targeted rerun policy:
1. rerun only `S0` for authority and handle defects.
2. no `S1` advancement until all `S0` blockers close.

Pass gate:
1. required handles complete/non-placeholder.
2. parent dependency continuity is valid.
3. `next_gate=M6P5_ST_S1_READY`.

### 7.2 `M6P5-ST-S1` - READY entry precheck
Objective:
1. prove READY entry contract is valid before commit actions.

Entry criteria:
1. latest successful `S0` summary with `next_gate=M6P5_ST_S1_READY`.

Required inputs:
1. run-scope continuity values from M5/M6 handoff chain.
2. control topic + message-filter handles.
3. SFN commit authority handles.

Execution steps:
1. enforce S0 continuity and blocker-free dependency.
2. validate run-scope continuity (`platform_run_id`, scenario continuity, handoff refs).
3. validate Step Functions orchestrator is active and authoritative.
4. validate required READY filter semantics are active.
5. emit entry snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P5-ST-B3`: READY entry contract mismatch.
2. `M6P5-ST-B4`: Step Functions authority surface invalid.
3. `M6P5-ST-B8`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `18` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. rerun `S1` after entry-contract remediations.
2. reopen `S0` only when handle/authority drift is detected.

Pass gate:
1. entry precheck is blocker-free.
2. `next_gate=M6P5_ST_S2_READY`.

### 7.3 `M6P5-ST-S2` - READY commit authority execution
Objective:
1. commit READY and validate authoritative receipt behavior.

Entry criteria:
1. latest successful `S1` summary with `next_gate=M6P5_ST_S2_READY`.

Required inputs:
1. SFN commit authority handles and state machine ARN/name.
2. control-topic publication handles.
3. receipt path pattern handles.

Execution steps:
1. execute READY commit under SFN authority.
2. verify READY publication on control topic for active run scope.
3. verify receipt contains SFN execution reference.
4. validate receipt durability and readback.
5. emit commit snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P5-ST-B4`: missing/invalid commit authority evidence.
2. `M6P5-ST-B5`: READY publication failure.
3. `M6P5-ST-B6`: receipt missing/unreadable/invalid.
4. `M6P5-ST-B8`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$6`.

Targeted rerun policy:
1. rerun `S2` only for commit/receipt blockers.
2. keep retries bounded and run-scoped to avoid ambiguous duplicates.

Pass gate:
1. READY publish + receipt authority checks pass.
2. `next_gate=M6P5_ST_S3_READY`.

### 7.4 `M6P5-ST-S3` - Duplicate/ambiguity stress window
Objective:
1. validate duplicate-safe behavior under sustained and burst READY commit attempts.

Entry criteria:
1. latest successful `S2` summary with `next_gate=M6P5_ST_S3_READY`.

Required inputs:
1. baseline commit receipt from `S2`.
2. repetition and burst factors from section `4`.
3. ambiguity and duplicate detection checks.

Execution steps:
1. execute bounded sustained READY attempts under idempotent run scope.
2. execute short burst READY attempts.
3. verify duplicate detection and ambiguity closure remain fail-closed.
4. verify no unresolved multi-receipt ambiguity for same run scope.
5. emit duplicate/ambiguity snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P5-ST-B7`: unresolved duplicate/ambiguity state.
2. `M6P5-ST-B5`: READY publish instability under stress window.
3. `M6P5-ST-B8`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$6`.

Targeted rerun policy:
1. rerun only failed window (`sustained` or `burst`).
2. preserve before/after evidence for each blocker closure.

Pass gate:
1. duplicate/ambiguity checks are green.
2. no unstable publish behavior remains.
3. `next_gate=M6P5_ST_S4_READY`.

### 7.5 `M6P5-ST-S4` - Remediation and selective rerun closure
Objective:
1. close any open P5 blockers with targeted remediation evidence.

Entry criteria:
1. latest `S3` summary/register available.

Required inputs:
1. current blocker register.
2. failing state artifacts from `S1..S3`.
3. remediation decision log.

Execution steps:
1. prioritize open blockers by correctness risk and rerun cost.
2. apply minimal scoped remediation.
3. rerun only affected state windows.
4. verify blocker transitions from `open` to `resolved` with receipts.
5. emit remediation summary and updated blocker register.

Fail-closed blocker mapping:
1. `M6P5-ST-B9`: remediation evidence inconsistent or incomplete.
2. `M6P5-ST-B8`: publish/readback failure during remediation cycle.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$2`.

Targeted rerun policy:
1. no full-phase rerun from `S0` by default.
2. escalate to broader rerun only if root cause spans multiple stages.

Pass gate:
1. all open P5 blockers are resolved or explicitly waived by user.
2. `next_gate=M6P5_ST_S5_READY`.

### 7.6 `M6P5-ST-S5` - P5 rollup and deterministic verdict
Objective:
1. publish deterministic P5 verdict for M6 parent orchestration.

Entry criteria:
1. latest successful `S4` summary with `next_gate=M6P5_ST_S5_READY`.
2. no unresolved non-waived blocker.

Required inputs:
1. latest stage summaries (`S0..S4`).
2. blocker register and decision log.
3. cost-outcome receipt.

Execution steps:
1. aggregate P5 evidence across stages.
2. enforce verdict rule:
   - `ADVANCE_TO_P6` only when blocker-free,
   - else `HOLD_REMEDIATE`.
3. emit rollup matrix, blocker register, verdict artifact, and execution summary.

Fail-closed blocker mapping:
1. `M6P5-ST-B9`: rollup/verdict inconsistency.
2. `M6P5-ST-B10`: artifact contract incompleteness.

Runtime/cost budget:
1. max runtime: `15` minutes.
2. max spend: `$1`.

Targeted rerun policy:
1. rerun `S5` for aggregation defects only.
2. reopen upstream stage only with explicit causal evidence.

Pass gate:
1. deterministic verdict `ADVANCE_TO_P6`.
2. `next_gate=ADVANCE_TO_P6`.

## 8) Blocker Taxonomy (M6.P5)
1. `M6P5-ST-B1`: required handle missing/inconsistent.
2. `M6P5-ST-B2`: parent entry dependency invalid.
3. `M6P5-ST-B3`: READY entry contract mismatch.
4. `M6P5-ST-B4`: Step Functions commit authority missing/invalid.
5. `M6P5-ST-B5`: READY publication failure/instability.
6. `M6P5-ST-B6`: READY receipt missing/unreadable/invalid.
7. `M6P5-ST-B7`: duplicate/ambiguity unresolved.
8. `M6P5-ST-B8`: durable evidence publish/readback failure.
9. `M6P5-ST-B9`: remediation or rollup inconsistency.
10. `M6P5-ST-B10`: artifact contract incomplete.

Any open `M6P5-ST-B*` blocks P5 closure and parent M6 `S1` progression.

## 9) Evidence Contract (M6.P5)
1. `m6p5_stagea_findings.json`
2. `m6p5_lane_matrix.json`
3. `m6p5_probe_latency_throughput_snapshot.json`
4. `m6p5_control_rail_conformance_snapshot.json`
5. `m6p5_secret_safety_snapshot.json`
6. `m6p5_cost_outcome_receipt.json`
7. `m6p5_blocker_register.json`
8. `m6p5_execution_summary.json`
9. `m6p5_decision_log.json`
10. `m6p5_gate_verdict.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M6.P5 stress authority created.
- [x] P5 handle packet and blocker taxonomy pinned.
- [x] P5 execution-grade runbook (`S0..S5`) pinned.
- [x] `M6P5-ST-S0` executed with blocker-free entry closure.
- [x] `M6P5-ST-S1..S3` executed and validated under stress windows.
- [x] `M6P5-ST-S4` remediation lane closed (no-op, blocker-free).
- [x] `M6P5-ST-S5` verdict emitted as `ADVANCE_TO_P6`.

## 11) Immediate Next Actions
1. Preserve `M6.P5` closure receipts and blocker-free register as dependency authority for parent `M6-ST-S1` and audit replay.
2. Execute `M6.P6` (`S0..S5`) to target deterministic verdict `ADVANCE_TO_P7`.
3. After `M6.P6` closure, run parent `M6-ST-S2` gate adjudication.

## 12) Execution Progress
1. Planning authority created.
2. `M6P5-ST-S0` executed and passed:
   - `phase_execution_id=m6p5_stress_s0_20260304T013405Z`,
   - `overall_pass=true`,
   - `next_gate=M6P5_ST_S1_READY`,
   - `open_blockers=0`,
   - `probe_count=1`, `error_rate_pct=0.0`.
3. `M6P5-ST-S1` executed and passed:
   - `phase_execution_id=m6p5_stress_s1_20260304T013406Z`,
   - `overall_pass=true`,
   - `next_gate=M6P5_ST_S2_READY`,
   - `open_blockers=0`,
   - `historical_m6b_execution_id=m6b_p5a_ready_entry_20260225T024245Z`.
4. `M6P5-ST-S2` executed and passed:
   - `phase_execution_id=m6p5_stress_s2_20260304T013411Z`,
   - `overall_pass=true`,
   - `next_gate=M6P5_ST_S3_READY`,
   - `open_blockers=0`,
   - receipt readback: `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/sr/ready_commit_receipt.json`.
5. `M6P5-ST-S3` executed and passed:
   - `phase_execution_id=m6p5_stress_s3_20260304T013414Z`,
   - `overall_pass=true`,
   - `next_gate=M6P5_ST_S4_READY`,
   - `open_blockers=0`,
   - duplicate/ambiguity stability probes: `25` (`stable_receipt_etag="271a9d7f86b64a60f9b234bf628c50c2"`).
6. `M6P5-ST-S4` executed and passed:
   - `phase_execution_id=m6p5_stress_s4_20260304T013452Z`,
   - `overall_pass=true`,
   - `next_gate=M6P5_ST_S5_READY`,
   - `open_blockers=0`,
   - remediation mode: `NO_OP` (no open blockers).
7. `M6P5-ST-S5` executed and passed:
   - `phase_execution_id=m6p5_stress_s5_20260304T013452Z`,
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P6`,
   - `next_gate=ADVANCE_TO_P6`,
   - `open_blockers=0`.
8. Authoritative evidence root:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p5_stress_s*_20260304T0134*/stress/`.
