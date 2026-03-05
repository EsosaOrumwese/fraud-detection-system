# Dev Substrate Stress Plan - M6.P7 (P7 INGEST_COMMITTED)
_Parent authority: `platform.M6.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_
_Current posture: `STRICT_RERUN_CLOSED` (fresh strict rerun chain `S1..S5` closed with deterministic `ADVANCE_TO_M7`)._

## 0) Purpose
M6.P7 stress validates ingest commit closure under realistic production stress and prepares deterministic M7 handoff inputs.

M6.P7 stress must prove:
1. receipt, quarantine, and offsets evidence are run-scoped and readable.
2. dedupe/idempotency/anomaly posture remains fail-closed under replay-like pressure.
3. commit evidence stays continuity-consistent with upstream streaming progression.
4. cost/runtime envelope remains controlled during ingest closure windows.
5. P7 rollup emits deterministic verdict (`ADVANCE_TO_M7` only when blocker-free) with valid handoff pack inputs.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P7.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. latest successful M6 parent `S0` and P6 closure verdict.

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) Stage-A Findings (M6.P7)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M6P7-ST-F1` | `PREVENT` | P7 entry is invalid without deterministic upstream P6 verdict (`ADVANCE_TO_P7`). | Gate S0 on latest P6 closure receipt. |
| `M6P7-ST-F2` | `PREVENT` | Offsets evidence can appear present but lack material topic/partition content. | Require materialized offsets validity checks, not file-presence checks only. |
| `M6P7-ST-F3` | `PREVENT` | Receipt/quarantine evidence without dedupe checks can hide replay anomalies. | Keep dedupe/anomaly lane mandatory in S2 and fail-closed on drift. |
| `M6P7-ST-F4` | `PREVENT` | P7 closure feeds M7 handoff; any evidence inconsistency must block handoff publication. | Validate handoff pack refs and run-scope alignment in S5. |
| `M6P7-ST-F5` | `OBSERVE` | Ingest closure costs can rise from repeated broad reruns after single-artifact failures. | Keep targeted rerun policy and stage-local remediation. |
| `M6P7-ST-F6` | `OBSERVE` | Proxy offset modes may be valid but can drift from expected semantics if undocumented. | Record offset evidence mode explicitly in execution summary and decision log. |
| `M6P7-ST-F7` | `ACCEPT` | Build authority already provides deterministic verdict contract and handoff requirement. | Reuse verdict semantics with stronger stress evidence checks. |

## 3) Scope Boundary for M6.P7 Stress
In scope:
1. ingest commit evidence materialization and readability.
2. dedupe/idempotency/anomaly closure under replay-like windows.
3. deterministic P7 rollup and M7-handoff input readiness.

Out of scope:
1. READY and streaming activation closure (`P5/P6`).
2. parent integrated cross-plane stress windows.
3. downstream M7 execution.

## 4) M6.P7 Stress Handle Packet (Pinned)
1. `M6P7_STRESS_PROFILE_ID = "ingest_committed_stress_v0"`.
2. `M6P7_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p7_blocker_register.json"`.
3. `M6P7_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p7_execution_summary.json"`.
4. `M6P7_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6p7_decision_log.json"`.
5. `M6P7_STRESS_REQUIRED_ARTIFACTS = "m6p7_stagea_findings.json,m6p7_lane_matrix.json,m6p7_ingest_commit_snapshot.json,m6p7_receipt_summary_snapshot.json,m6p7_quarantine_summary_snapshot.json,m6p7_offsets_snapshot.json,m6p7_dedupe_anomaly_snapshot.json,m6p7_probe_latency_throughput_snapshot.json,m6p7_control_rail_conformance_snapshot.json,m6p7_secret_safety_snapshot.json,m6p7_cost_outcome_receipt.json,m6p7_blocker_register.json,m6p7_execution_summary.json,m6p7_decision_log.json,m6p7_gate_verdict.json,m7_handoff_pack.json"`.
6. `M6P7_STRESS_MAX_RUNTIME_MINUTES = 140`.
7. `M6P7_STRESS_MAX_SPEND_USD = 25`.
8. `M6P7_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_M7"`.
9. `M6P7_STRESS_REPLAY_WINDOW_MINUTES = 15`.
10. `M6P7_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles for M6.P7:
1. `RECEIPT_SUMMARY_PATH_PATTERN`
2. `QUARANTINE_SUMMARY_PATH_PATTERN`
3. `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
4. `DDB_IG_IDEMPOTENCY_TABLE`
5. `DDB_IG_IDEMPOTENCY_TTL_FIELD`
6. `IG_IDEMPOTENCY_TTL_SECONDS`
7. `M7_HANDOFF_PACK_PATH_PATTERN`
8. `S3_EVIDENCE_BUCKET`
9. `S3_RUN_CONTROL_ROOT_PATTERN`
10. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M6.P7 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry closure | `S0` | required handles + deterministic P6 dependency closure |
| Ingest commit evidence materialization | `S1` | receipt/quarantine/offset evidence present and readable |
| Dedupe/anomaly closure | `S2` | replay-safe dedupe/anomaly checks pass |
| Continuity and replay-window checks | `S3` | count continuity and replay-window behavior pass |
| Remediation + selective rerun | `S4` | blocker-specific rerun closure evidence |
| P7 rollup + verdict + handoff inputs | `S5` | deterministic verdict `ADVANCE_TO_M7` |

## 6) Stress Topology (M6.P7)
1. Component sequence:
   - `P7.A` entry and evidence materialization,
   - `P7.B` dedupe/anomaly checks,
   - `P7.C` continuity and replay-window checks,
   - `P7.D` rollup and handoff inputs.
2. Plane sequence:
   - `ingest_commit_plane`,
   - `idempotency_plane`,
   - `p7_rollup_plane`.
3. Integrated windows:
   - `m6p7_s3_replay_window`,
   - `m6p7_s3_continuity_window`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M6P7-ST-S0` - Authority and entry-gate closure
Objective:
1. validate P7 authority, handle completeness, and upstream P6 dependency closure.

Entry criteria:
1. latest successful M6 parent `S0` and P6 `S5` receipts are readable.
2. no unresolved planning decision exists for required handles.

Required inputs:
1. parent `M6-ST-S0` summary/register.
2. latest P6 verdict artifact (`ADVANCE_TO_P7`).
3. required handle packet in section `4`.

Execution steps:
1. enforce parent + P6 dependency continuity.
2. validate required P7 handles for presence and placeholder guard.
3. validate evidence root/write/read surfaces.
4. emit stage findings, lane matrix, blocker register, summary, and decision log.

Fail-closed blocker mapping:
1. `M6P7-ST-B1`: required handle missing/inconsistent.
2. `M6P7-ST-B2`: invalid P6 dependency or entry gate mismatch.
3. `M6P7-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `12` minutes.
2. max spend: `$2`.

Targeted rerun policy:
1. rerun `S0` only for dependency/handle closure defects.
2. block `S1` until `S0` closes green.

Pass gate:
1. P6 dependency closure is valid.
2. required handles complete/non-placeholder.
3. `next_gate=M6P7_ST_S1_READY`.

### 7.2 `M6P7-ST-S1` - Ingest commit evidence materialization
Objective:
1. validate receipt, quarantine, and offsets evidence materialization with run-scope integrity.

Entry criteria:
1. latest successful `S0` summary with `next_gate=M6P7_ST_S1_READY`.

Required inputs:
1. receipt/quarantine/offset path handles.
2. active run scope (`platform_run_id`, scenario scope).
3. upstream progression evidence from P6 summary.

Execution steps:
1. enforce S0 continuity and zero open blockers.
2. retrieve and validate receipt summary artifact.
3. retrieve and validate quarantine summary artifact.
4. retrieve and validate offsets snapshot artifact with material-content checks.
5. emit ingest-commit snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P7-ST-B3`: receipt/quarantine summary missing/unreadable.
2. `M6P7-ST-B4`: offsets snapshot missing/unreadable/non-material.
3. `M6P7-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$5`.

Targeted rerun policy:
1. rerun `S1` for evidence-surface failures only.
2. no progression to `S2` while evidence materialization blockers are open.

Pass gate:
1. commit evidence set is present, readable, and material.
2. `next_gate=M6P7_ST_S2_READY`.

### 7.3 `M6P7-ST-S2` - Dedupe/anomaly closure
Objective:
1. validate replay-safe dedupe/idempotency/anomaly behavior under bounded stress.

Entry criteria:
1. latest successful `S1` summary with `next_gate=M6P7_ST_S2_READY`.

Required inputs:
1. idempotency table handles and TTL handles.
2. receipt/quarantine evidence from `S1`.
3. bounded replay-like event sample for active run scope.

Execution steps:
1. enforce S1 continuity and evidence availability.
2. run dedupe checks against idempotency surface.
3. run anomaly checks against receipt/quarantine consistency.
4. verify TTL and duplicate suppression posture.
5. emit dedupe/anomaly snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P7-ST-B5`: dedupe/idempotency drift.
2. `M6P7-ST-B6`: anomaly inconsistency across ingest evidence surfaces.
3. `M6P7-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$6`.

Targeted rerun policy:
1. rerun only S2 for dedupe/anomaly defects.
2. reopen S1 only when root cause is missing/invalid evidence surface.

Pass gate:
1. dedupe/anomaly checks pass.
2. `next_gate=M6P7_ST_S3_READY`.

### 7.4 `M6P7-ST-S3` - Continuity and replay-window stress
Objective:
1. validate ingest commit continuity under bounded replay-window pressure.

Entry criteria:
1. latest successful `S2` summary with `next_gate=M6P7_ST_S3_READY`.

Required inputs:
1. replay-window duration from section `4`.
2. upstream progression evidence and S1/S2 snapshots.
3. count continuity expectations across receipt/quarantine/offset surfaces.

Execution steps:
1. run bounded replay-window simulation/probe.
2. verify continuity between admitted counts and commit evidence counts.
3. verify no unexplained drift between offsets and ingest summaries.
4. emit continuity/replay snapshot and stage artifacts.

Fail-closed blocker mapping:
1. `M6P7-ST-B6`: continuity drift across ingest evidence surfaces.
2. `M6P7-ST-B7`: replay-window behavior violates idempotent closure expectations.
3. `M6P7-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `35` minutes.
2. max spend: `$6`.

Targeted rerun policy:
1. rerun only failed replay/continuity windows.
2. preserve before/after traces for each closed blocker.

Pass gate:
1. continuity checks are green.
2. replay-window behavior is blocker-free.
3. `next_gate=M6P7_ST_S4_READY`.

### 7.5 `M6P7-ST-S4` - Remediation and selective rerun closure
Objective:
1. close open P7 blockers via minimal-scope remediation and targeted reruns.

Entry criteria:
1. latest `S3` summary/register is readable.

Required inputs:
1. blocker register and failing artifacts.
2. remediation plan and owner mapping.
3. updated evidence refs after fix.

Execution steps:
1. classify blockers by evidence-surface vs idempotency vs continuity root cause.
2. apply minimal remediation.
3. rerun only affected states/windows.
4. confirm blocker transitions and publish closure receipts.

Fail-closed blocker mapping:
1. `M6P7-ST-B8`: remediation evidence inconsistent.
2. `M6P7-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. do not rerun from `S0` unless dependency drift is proven.
2. keep reruns scoped to failing evidence lanes.

Pass gate:
1. all open P7 blockers resolved or explicitly user-waived.
2. `next_gate=M6P7_ST_S5_READY`.

### 7.6 `M6P7-ST-S5` - P7 rollup, verdict, and handoff inputs
Objective:
1. publish deterministic P7 verdict and valid inputs for parent M6 handoff closure.

Entry criteria:
1. latest successful `S4` summary with `next_gate=M6P7_ST_S5_READY`.
2. no unresolved non-waived blockers.

Required inputs:
1. stage summaries `S0..S4`.
2. latest blocker register and cost receipt.
3. handoff-path handle and run-scope context.

Execution steps:
1. aggregate P7 evidence across all states.
2. enforce verdict rule:
   - `ADVANCE_TO_M7` only when blocker-free,
   - else `HOLD_REMEDIATE`.
3. emit rollup matrix, verdict artifact, and summary.
4. emit/validate handoff input artifact references for parent M6 S3/S5 use.

Fail-closed blocker mapping:
1. `M6P7-ST-B8`: rollup/verdict inconsistency.
2. `M6P7-ST-B9`: handoff input artifact missing/invalid.
3. `M6P7-ST-B11`: artifact contract incompleteness.
4. `M6P7-ST-B12`: toy-profile/historical-only closure posture detected.

Runtime/cost budget:
1. max runtime: `18` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. rerun `S5` for aggregation-only defects.
2. reopen upstream states only with explicit causal evidence.

Pass gate:
1. deterministic verdict `ADVANCE_TO_M7`.
2. `next_gate=ADVANCE_TO_M7`.

## 8) Blocker Taxonomy (M6.P7)
1. `M6P7-ST-B1`: required handle missing/inconsistent.
2. `M6P7-ST-B2`: invalid P6 dependency/entry gate.
3. `M6P7-ST-B3`: receipt/quarantine summary missing/unreadable.
4. `M6P7-ST-B4`: offsets snapshot missing/unreadable/non-material.
5. `M6P7-ST-B5`: dedupe/idempotency drift.
6. `M6P7-ST-B6`: ingest evidence continuity drift.
7. `M6P7-ST-B7`: replay-window behavior invalid.
8. `M6P7-ST-B8`: remediation/rollup inconsistency.
9. `M6P7-ST-B9`: handoff input artifact missing/invalid.
10. `M6P7-ST-B10`: durable evidence publish/readback failure.
11. `M6P7-ST-B11`: artifact contract incomplete.
12. `M6P7-ST-B12`: toy-profile or historical/proxy-only closure authority detected.

Any open `M6P7-ST-B*` blocks P7 closure and parent M6 `S3` progression.

## 9) Evidence Contract (M6.P7)
1. `m6p7_stagea_findings.json`
2. `m6p7_lane_matrix.json`
3. `m6p7_ingest_commit_snapshot.json`
4. `m6p7_receipt_summary_snapshot.json`
5. `m6p7_quarantine_summary_snapshot.json`
6. `m6p7_offsets_snapshot.json`
7. `m6p7_dedupe_anomaly_snapshot.json`
8. `m6p7_probe_latency_throughput_snapshot.json`
9. `m6p7_control_rail_conformance_snapshot.json`
10. `m6p7_secret_safety_snapshot.json`
11. `m6p7_cost_outcome_receipt.json`
12. `m6p7_blocker_register.json`
13. `m6p7_execution_summary.json`
14. `m6p7_decision_log.json`
15. `m6p7_gate_verdict.json`
16. `m7_handoff_pack.json` (or parent-consumed handoff-input reference pack)

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M6.P7 stress authority created.
- [x] P7 handle packet and blocker taxonomy pinned.
- [x] P7 execution-grade runbook (`S0..S5`) pinned.
- [x] `M6P7-ST-S0` executed with blocker-free entry closure.
- [x] `M6P7-ST-S1` executed with ingest-evidence materialization closure.
- [x] `M6P7-ST-S2` executed with replay-safe dedupe/anomaly closure.
- [x] `M6P7-ST-S3` executed with continuity/replay-window closure.
- [x] `M6P7-ST-S4` remediation lane closed (`NO_OP`).
- [x] `M6P7-ST-S5` verdict emitted as `ADVANCE_TO_M7`.
- [x] Strict non-toy rerun (`S1..S5`) executed with zero historical/proxy closure authority.

## 11) Immediate Next Actions
1. No open P7 remediation lane; retain strict rerun receipts as closure authority for M6 handoff and audit.
2. Reopen fail-closed only if any future run reintroduces historical-only closure dependence or unresolved blockers.
3. Keep blocker policy (`M6P7-ST-B12`) active for future enforcement.

## 12) Execution Progress
1. Planning authority created.
2. `M6P7-ST-S0` executed and passed:
   - `phase_execution_id=m6p7_stress_s0_20260304T021107Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S1_READY`,
   - `open_blockers=0`,
   - `parent_m6_s0_phase_execution_id=m6_stress_s0_20260304T012128Z`,
   - `p6_dependency_phase_execution_id=m6p6_stress_s5_20260304T020815Z`,
   - `platform_run_id=platform_20260223T184232Z`.
3. Blocker decision for this run:
   - latest prior implementation sweep (`M6.P6` closure and assurance chain) was fully blocker-free,
   - no remediation actions were required before or after `S0` execution.
4. `M6P7-ST-S1` executed and passed:
   - `phase_execution_id=m6p7_stress_s1_20260304T021901Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S2_READY`,
   - `open_blockers=0`,
   - `s0_dependency_phase_execution_id=m6p7_stress_s0_20260304T021107Z`,
   - `historical_m6h_execution_id=m6h_p7a_ingest_commit_20260225T191433Z`,
   - `platform_run_id=platform_20260223T184232Z`,
   - `offset_mode=IG_ADMISSION_INDEX_PROXY`.
5. Blocker decision for this run:
   - latest prior implementation sweep (`M6P7-ST-S0` + `M6.P6` assurance chain) remained blocker-free,
   - no remediation actions were required before or after `S1` execution.
6. `M6P7-ST-S2` executed and passed:
   - `phase_execution_id=m6p7_stress_s2_20260304T023114Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S3_READY`,
   - `open_blockers=0`,
   - `s1_dependency_phase_execution_id=m6p7_stress_s1_20260304T021901Z`,
   - `historical_m6h_execution_id=m6h_p7a_ingest_commit_20260225T191433Z`,
   - `platform_run_id=platform_20260223T184232Z`,
   - `offset_mode=IG_ADMISSION_INDEX_PROXY`,
   - `ttl_evidence_mode=HISTORICAL_WITH_LIVE_SAMPLE`.
7. Blocker decision for this run:
   - latest prior implementation sweep (`M6P7-ST-S1`) remained blocker-free,
   - no remediation actions were required,
   - TTL-window check determined run-scoped live idempotency rows are expectedly expired for the historical run; S2 therefore used historical run-scoped evidence plus bounded live-table posture sampling.
8. `M6P7-ST-S3` executed and passed:
   - `phase_execution_id=m6p7_stress_s3_20260304T023645Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S4_READY`,
   - `open_blockers=0`,
   - `s2_dependency_phase_execution_id=m6p7_stress_s2_20260304T023114Z`,
   - `historical_m6i_execution_id=m6i_p7b_gate_rollup_20260225T191541Z`,
   - `replay_window_mode=HISTORICAL_CLOSED_WINDOW`.
9. Blocker decision for this run:
   - latest prior implementation sweep (`M6P7-ST-S2`) remained blocker-free,
   - no remediation actions were required,
   - replay-window continuity was evaluated in historical-closed mode because run age exceeded the replay window and TTL-expired posture was expected.
10. `M6P7-ST-S4` executed and passed:
   - `phase_execution_id=m6p7_stress_s4_20260304T024002Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S5_READY`,
   - `open_blockers=0`,
   - `s3_dependency_phase_execution_id=m6p7_stress_s3_20260304T023645Z`,
   - `remediation_mode=NO_OP`,
   - `replay_window_mode=HISTORICAL_CLOSED_WINDOW`.
11. Blocker decision for this run:
   - latest prior implementation sweep (`M6P7-ST-S3`) remained blocker-free,
   - no remediation actions were required,
   - S4 remediation lane was intentionally closed as `NO_OP` with targeted-rerun policy preserved.
12. `M6P7-ST-S5` executed and passed:
   - `phase_execution_id=m6p7_stress_s5_20260304T024638Z`,
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M7`,
   - `next_gate=ADVANCE_TO_M7`,
   - `open_blockers=0`,
   - `s4_dependency_phase_execution_id=m6p7_stress_s4_20260304T024002Z`,
   - `historical_m6i_execution_id=m6i_p7b_gate_rollup_20260225T191541Z`,
   - `handoff_path_key=evidence/dev_full/run_control/m6p7_stress_s5_20260304T024638Z/m7_handoff_pack.json`.
13. Blocker decision for this run:
   - latest prior implementation sweep (`M6P7-ST-S4`) remained blocker-free,
   - no remediation actions were required,
   - deterministic rollup verdict and handoff-pack emission both closed green under targeted-rerun policy.

## 13) Reopen Notice - Non-Toy Enforcement (2026-03-04, Resolved)
1. Legacy `M6P7-ST-S2..S5` receipts are retained for traceability only; they are not valid closure authority.
2. `M6P7-ST-B12` is opened whenever closure depends on:
   - `historical_*` execution ids as primary proof,
   - replay/idempotency checks in historical-closed mode,
   - advisory-only throughput posture.
3. Strict rerun path for re-closure has been completed:
   - `S1..S5` rerun closed with run-scoped evidence (`phase_execution_id=m6p7_stress_s5_20260304T203739Z`),
   - blocker register is closed (`open_blocker_count=0`),
   - deterministic verdict is `ADVANCE_TO_M7`.
4. Future closure remains fail-closed: any reintroduction of historical-only proof reopens `M6P7-ST-B12`.
