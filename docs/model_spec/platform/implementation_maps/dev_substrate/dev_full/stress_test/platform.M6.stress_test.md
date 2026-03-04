# Dev Substrate Stress Plan - M6 (Control and Ingress Orchestration)
_Status source of truth: `platform.stress_test.md`_
_This document provides deep stress-planning detail for M6 orchestration._
_Track: `dev_full` only_
_As of 2026-03-04_

## 0) Purpose
M6 stress validates Control + Ingress production posture under realistic sustained and burst traffic before M7 activation.

M6 stress must prove:
1. READY publication (`P5`) is deterministic, authority-correct, and duplicate-safe.
2. streaming activation (`P6`) is active, lag-bounded, and free from unresolved publish ambiguity.
3. ingest commit closure (`P7`) is evidence-complete, dedupe-safe, and replay-safe.
4. integrated control->stream->ingress plane behavior remains within runtime/cost envelopes.
5. M6 closure emits deterministic M7 handoff recommendation from blocker-consistent evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P5.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P6.build_plan.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P7.build_plan.md`
6. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
7. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s3_20260304T010243Z/stress/m5_execution_summary.json`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) Stage-A Findings (M6)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M6-ST-F1` | `PREVENT` | M6 is a multi-lane coupled phase (`P5/P6/P7`) and cannot be run safely from parent-only summary bullets. | Split into dedicated parent + subphase stress authorities with deterministic gate ownership. |
| `M6-ST-F2` | `PREVENT` | M6 entry must chain from latest M5 parent closure (`GO`, `M6_READY`) without ambiguity. | Enforce strict S0 dependency readback before any M6 stress execution. |
| `M6-ST-F3` | `PREVENT` | M6 throughput acceptance requires explicit production realism budgets (throughput, latency, lag, error, spend) for integrated windows. | Pin M6 integrated S4 profile and fail-closed acceptance thresholds before launch. |
| `M6-ST-F4` | `PREVENT` | P5/P6/P7 verdict progression must remain deterministic (`ADVANCE_TO_P6`, `ADVANCE_TO_P7`, `ADVANCE_TO_M7`). | Gate parent `S1/S2/S3` strictly on subphase verdict contracts and blocker closure. |
| `M6-ST-F5` | `OBSERVE` | Streaming runtime path may need controlled fallback (`MSF_MANAGED` -> `EKS_FLINK_OPERATOR`) when managed service constraints block execution. | Keep fallback lane explicit, measured, and blocker-consistent (no silent repin). |
| `M6-ST-F6` | `OBSERVE` | Plane-level stress can become cost-heavy if broad reruns are used after narrow blocker signals. | Enforce targeted rerun policy and stage-local remediation only. |
| `M6-ST-F7` | `OBSERVE` | Evidence-overhead on hot paths can degrade throughput if unbounded per-event sync writes appear. | Keep evidence-overhead budget checks mandatory in P6 and parent S4 windows. |
| `M6-ST-F8` | `ACCEPT` | M5 closure is already green with explicit M6 entry recommendation. | Use M5 S3 summary as authoritative phase-entry dependency. |

## 3) Scope Boundary for M6 Stress
In scope:
1. parent orchestration gates across `P5`, `P6`, `P7`.
2. subphase execution routing and deterministic verdict progression.
3. integrated control+ingress plane stress windows (sustained, burst, bounded fault).
4. throughput/latency/lag/error and cost envelope enforcement.
5. deterministic M6 closure and M7 handoff recommendation.

Out of scope:
1. RTDL/case-label closures (`M7+`).
2. observability/governance-only phase closure (`M8`).
3. learning/evolution and model-lifecycle phases (`M9+`).

## 4) M6 Parent Stress Handle Packet (Pinned)
1. `M6_STRESS_PROFILE_ID = "control_ingress_orchestration_stress_v0"`.
2. `M6_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6_blocker_register.json"`.
3. `M6_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6_execution_summary.json"`.
4. `M6_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m6_decision_log.json"`.
5. `M6_STRESS_REQUIRED_ARTIFACTS = "m6_stagea_findings.json,m6_lane_matrix.json,m6_probe_latency_throughput_snapshot.json,m6_control_rail_conformance_snapshot.json,m6_secret_safety_snapshot.json,m6_cost_outcome_receipt.json,m6_blocker_register.json,m6_execution_summary.json,m6_decision_log.json,m7_handoff_pack.json"`.
6. `M6_STRESS_MAX_RUNTIME_MINUTES = 300`.
7. `M6_STRESS_MAX_SPEND_USD = 90`.
8. `M6_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M7_READY"`.
9. `M6_STRESS_REQUIRED_SUBPHASES = "M6.P5|M6.P6|M6.P7"`.
10. `M6_STRESS_P5_REQUIRED_VERDICT = "ADVANCE_TO_P6"`.
11. `M6_STRESS_P6_REQUIRED_VERDICT = "ADVANCE_TO_P7"`.
12. `M6_STRESS_P7_REQUIRED_VERDICT = "ADVANCE_TO_M7"`.
13. `M6_STRESS_INTEGRATED_WINDOW_MINUTES = 20`.
14. `M6_STRESS_BURST_WINDOW_MINUTES = 8`.
15. `M6_STRESS_FAILURE_INJECTION_WINDOW_MINUTES = 6`.
16. `M6_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed parent entry/closure handles:
1. `S3_EVIDENCE_BUCKET`
2. `S3_RUN_CONTROL_ROOT_PATTERN`
3. `M6_HANDOFF_PACK_PATH_PATTERN`
4. `M7_HANDOFF_PACK_PATH_PATTERN`
5. `FP_BUS_CONTROL_V1`
6. `READY_MESSAGE_FILTER`
7. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
8. `SR_READY_COMMIT_AUTHORITY`
9. `SR_READY_COMMIT_STATE_MACHINE`
10. `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF`
11. `SR_READY_COMMIT_RECEIPT_PATH_PATTERN`
12. `FLINK_RUNTIME_PATH_ACTIVE`
13. `FLINK_RUNTIME_PATH_ALLOWED`
14. `FLINK_APP_WSP_STREAM_V0`
15. `FLINK_APP_SR_READY_V0`
16. `FLINK_EKS_WSP_STREAM_REF`
17. `FLINK_EKS_SR_READY_REF`
18. `EMR_EKS_VIRTUAL_CLUSTER_ID`
19. `EMR_EKS_RELEASE_LABEL`
20. `EMR_EKS_EXECUTION_ROLE_ARN`
21. `RTDL_CAUGHT_UP_LAG_MAX`
22. `WSP_MAX_INFLIGHT`
23. `WSP_RETRY_MAX_ATTEMPTS`
24. `WSP_RETRY_BACKOFF_MS`
25. `WSP_STOP_ON_NONRETRYABLE`
26. `IG_BASE_URL`
27. `IG_INGEST_PATH`
28. `DDB_IG_IDEMPOTENCY_TABLE`
29. `RECEIPT_SUMMARY_PATH_PATTERN`
30. `QUARANTINE_SUMMARY_PATH_PATTERN`
31. `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M6 parent stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + M5->M6 entry closure | `S0` | valid M5 handoff and required parent handle closure |
| P5 orchestration gate | `S1` | latest successful P5 verdict `ADVANCE_TO_P6` with zero open blockers |
| P6 orchestration gate | `S2` | latest successful P6 verdict `ADVANCE_TO_P7` with zero open blockers |
| P7 orchestration gate | `S3` | latest successful P7 verdict `ADVANCE_TO_M7` with zero open blockers |
| Integrated control+ingress stress window | `S4` | sustained/burst/fault profile pass within runtime and spend envelope |
| M6 closure rollup + M7 recommendation | `S5` | deterministic `GO` recommendation with `next_gate=M7_READY` |

Subphase authority routing:
1. `stress_test/platform.M6.P5.stress_test.md`
2. `stress_test/platform.M6.P6.stress_test.md`
3. `stress_test/platform.M6.P7.stress_test.md`

## 6) Stress Topology (M6 Parent)
1. Component sequence:
   - `M6-ST-S0` (entry and handle closure),
   - `M6-ST-S1` (P5 gate),
   - `M6-ST-S2` (P6 gate),
   - `M6-ST-S3` (P7 gate),
   - `M6-ST-S4` (integrated plane window),
   - `M6-ST-S5` (closure rollup).
2. Plane sequence:
   - `control_plane` (`SR`, control topic),
   - `streaming_plane` (`WSP`, stream runtime),
   - `ingress_plane` (`IG`, idempotency/receipt/quarantine),
   - `phase_closure_plane`.
3. Integrated windows:
   - `m6_s4_sustained_window`,
   - `m6_s4_burst_window`,
   - `m6_s4_fault_window`.

## 7) Execution Plan (Parent Orchestration Runbook)
### 7.1 `M6-ST-S0` - Authority and entry-gate closure
Objective:
1. fail-closed validation that M6 can activate with complete authority and valid M5 handoff.

Entry criteria:
1. latest successful M5 parent summary/register are readable.
2. no unresolved planning decision exists for required parent handle packet.

Required inputs:
1. latest successful `M5-ST-S3` summary + blocker register.
2. required handle set in section `4`.
3. M6 parent + subphase authorities (`M6`, `M6.P5`, `M6.P6`, `M6.P7`).
4. evidence bucket/root handles for durable publish-readback checks.

Execution steps:
1. load latest M5 parent closure evidence and enforce dependency contract:
   - `overall_pass=true`,
   - `recommendation=GO`,
   - `next_gate=M6_READY`,
   - `open_blockers=0`.
2. validate required M6 parent handles for presence, non-placeholder, and non-empty values.
3. validate required M6 stress authority docs are present/readable.
4. run bounded evidence publish/readback probe under M6 control prefix.
5. emit Stage-A findings, lane matrix, blocker register, execution summary, and decision log.

Fail-closed blocker mapping:
1. `M6-ST-B1`: missing/inconsistent required parent handle.
2. `M6-ST-B2`: invalid M5 dependency gate or unreadable closure artifacts.
3. `M6-ST-B3`: missing/unreadable split M6 authority doc.
4. `M6-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `15` minutes.
2. max spend: `$3`.

Targeted rerun policy:
1. rerun only `S0` for authority/handle/evidence-surface failures.
2. do not advance to `S1` until all `S0` blockers are closed.

Pass gate:
1. parent handle set complete and non-placeholder.
2. M5 handoff dependency valid and blocker-free.
3. split M6 authorities readable.
4. `next_gate=M6_ST_S1_READY`.

### 7.2 `M6-ST-S1` - P5 orchestration gate closure
Objective:
1. validate P5 deep stress closure is complete and safe for P6 entry.

Entry criteria:
1. latest successful `S0` summary is readable with `next_gate=M6_ST_S1_READY`.
2. P5 authority is present and advertises deterministic verdict contract.

Required inputs:
1. latest P5 summary/register from `platform.M6.P5.stress_test.md` lane.
2. P5 required verdict contract (`ADVANCE_TO_P6`).
3. parent `S0` summary/register for continuity.

Execution steps:
1. enforce dependency continuity from parent `S0` with zero open blockers.
2. load latest successful P5 closure summary/register.
3. require deterministic P5 verdict contract:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P6`,
   - zero open non-waived `M6P5-ST-B*` blockers.
4. verify P5 required artifacts are complete/readable.
5. emit parent `S1` gate receipt and blocker adjudication.

Fail-closed blocker mapping:
1. `M6-ST-B4`: P5 verdict missing/invalid or blocker-open.
2. `M6-ST-B9`: P5 artifact contract incomplete/unreadable.
3. `M6-ST-B10`: parent `S1` evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$5`.

Targeted rerun policy:
1. rerun `S1` only when failure is P5 evidence/verdict scoped.
2. reopen `S0` only if `S1` reveals parent handle/authority drift.

Pass gate:
1. P5 verdict is deterministic and equals `ADVANCE_TO_P6`.
2. no open non-waived P5 blockers.
3. `next_gate=M6_ST_S2_READY`.

### 7.3 `M6-ST-S2` - P6 orchestration gate closure
Objective:
1. validate P6 deep stress closure is complete and safe for P7 entry.

Entry criteria:
1. latest successful `S1` summary is readable with `next_gate=M6_ST_S2_READY`.
2. P6 authority is present and advertises deterministic verdict contract.

Required inputs:
1. latest P6 summary/register from `platform.M6.P6.stress_test.md` lane.
2. P6 required verdict contract (`ADVANCE_TO_P7`).
3. parent `S1` summary/register for continuity.

Execution steps:
1. enforce dependency continuity from `S1`.
2. load latest successful P6 closure summary/register.
3. require deterministic P6 verdict contract:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P7`,
   - zero open non-waived `M6P6-ST-B*` blockers.
4. verify P6 artifact contract completeness including lag and ambiguity snapshots.
5. emit parent `S2` gate receipt and blocker adjudication.

Fail-closed blocker mapping:
1. `M6-ST-B5`: P6 verdict missing/invalid or blocker-open.
2. `M6-ST-B9`: P6 artifact contract incomplete/unreadable.
3. `M6-ST-B10`: parent `S2` evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$15`.

Targeted rerun policy:
1. rerun `S2` for P6-specific blocker surfaces.
2. reopen `S1` only if verdict chain inconsistency is detected.

Pass gate:
1. P6 verdict is deterministic and equals `ADVANCE_TO_P7`.
2. no open non-waived P6 blockers.
3. `next_gate=M6_ST_S3_READY`.

### 7.4 `M6-ST-S3` - P7 orchestration gate closure
Objective:
1. validate P7 deep stress closure is complete and safe for M6 integrated closure.

Entry criteria:
1. latest successful `S2` summary is readable with `next_gate=M6_ST_S3_READY`.
2. P7 authority is present and advertises deterministic verdict contract.

Required inputs:
1. latest P7 summary/register from `platform.M6.P7.stress_test.md` lane.
2. P7 required verdict contract (`ADVANCE_TO_M7`).
3. parent `S2` summary/register for continuity.

Execution steps:
1. enforce dependency continuity from `S2`.
2. load latest successful P7 closure summary/register.
3. require deterministic P7 verdict contract:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M7`,
   - zero open non-waived `M6P7-ST-B*` blockers.
4. verify `m7_handoff_pack` presence/readability and run-scope consistency.
5. emit parent `S3` gate receipt and blocker adjudication.

Fail-closed blocker mapping:
1. `M6-ST-B6`: P7 verdict missing/invalid or blocker-open.
2. `M6-ST-B7`: M7 handoff pack missing/invalid.
3. `M6-ST-B9`: P7 artifact contract incomplete/unreadable.
4. `M6-ST-B10`: parent `S3` evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$10`.

Targeted rerun policy:
1. rerun `S3` for P7-specific closure defects.
2. reopen `S2` only when upstream verdict continuity is contradicted.

Pass gate:
1. P7 verdict is deterministic and equals `ADVANCE_TO_M7`.
2. handoff pack exists and is valid.
3. `next_gate=M6_ST_S4_READY`.

### 7.5 `M6-ST-S4` - Integrated control+ingress stress window
Objective:
1. validate integrated control->stream->ingress plane behavior under realistic production stress windows.

Entry criteria:
1. latest successful `S3` summary is readable with `next_gate=M6_ST_S4_READY`.
2. active runtime path for P6 is explicit and accepted in current authority (`MSF_MANAGED` or approved fallback).

Required inputs:
1. P5/P6/P7 latest closure artifacts for continuity baseline.
2. integrated profile definition:
   - sustained window (`M6_STRESS_INTEGRATED_WINDOW_MINUTES`),
   - burst window (`M6_STRESS_BURST_WINDOW_MINUTES`),
   - bounded fault window (`M6_STRESS_FAILURE_INJECTION_WINDOW_MINUTES`).
3. acceptance thresholds from active handles or phase overrides:
   - ingress throughput target,
   - end-to-end latency p95 target,
   - lag threshold (`RTDL_CAUGHT_UP_LAG_MAX`),
   - max error-rate threshold,
   - evidence-overhead budget.

Execution steps:
1. run sustained integrated load and capture throughput/latency/error baseline.
2. run bounded burst load and capture saturation/queue growth behavior.
3. run bounded fault injection (for example transient ingress-edge/network jitter) and validate recovery posture.
4. verify count continuity across control topic publish -> stream progression -> ingest commit evidence.
5. verify no unresolved ambiguity and no hidden queue growth during steady recovery.
6. emit integrated snapshots and blocker register.

Fail-closed blocker mapping:
1. `M6-ST-B8`: integrated throughput/latency/lag/error threshold breach.
2. `M6-ST-B11`: count continuity drift across control/stream/ingress boundaries.
3. `M6-ST-B12`: unexplained spend/runtime envelope breach.
4. `M6-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `150` minutes.
2. max spend: `$45`.

Targeted rerun policy:
1. rerun only failed profile windows (`sustained`, `burst`, or `fault`), not full S4 by default.
2. require remediation note mapping each reopened blocker to exact window and owner lane.

Pass gate:
1. integrated windows are blocker-free against threshold contracts.
2. count continuity and ambiguity checks are green.
3. runtime/spend remain within envelope.
4. `next_gate=M6_ST_S5_READY`.

### 7.6 `M6-ST-S5` - M6 closure rollup and M7 recommendation
Objective:
1. publish deterministic M6 closure verdict and explicit M7 readiness recommendation.

Entry criteria:
1. latest successful `S4` summary is readable with `next_gate=M6_ST_S5_READY`.
2. no unresolved blocker from parent `S0..S4` or subphase `P5..P7`.

Required inputs:
1. latest parent `S0..S4` summaries/registers.
2. latest subphase verdict artifacts.
3. phase runtime/spend receipts.
4. `m7_handoff_pack.json` candidate.

Execution steps:
1. aggregate parent + subphase closure evidence.
2. enforce deterministic recommendation rule:
   - `GO` + `next_gate=M7_READY` only when blocker-free and envelope-safe,
   - otherwise `NO_GO` + `next_gate=BLOCKED`.
3. validate handoff pack run-scope and evidence-ref integrity.
4. emit M6 closure summary, blocker register, decision log, and cost-outcome receipt.

Fail-closed blocker mapping:
1. `M6-ST-B6`: closure-rollup/verdict inconsistency.
2. `M6-ST-B7`: handoff pack missing/invalid.
3. `M6-ST-B12`: envelope inconsistency or unattributed spend.
4. `M6-ST-B9`: artifact contract incomplete.

Runtime/cost budget:
1. max runtime: `60` minutes.
2. max spend: `$12`.

Targeted rerun policy:
1. rerun `S5` only for closure aggregation defects.
2. reopen specific upstream stage only when causal evidence points upstream.

Pass gate:
1. no open non-waived `M6-ST-B*` blockers.
2. deterministic recommendation is `GO` with `next_gate=M7_READY`.
3. handoff pack is readable and evidence-complete.

## 8) Blocker Taxonomy (M6 Parent)
1. `M6-ST-B1`: missing/unresolved required parent handle.
2. `M6-ST-B2`: invalid M5 handoff dependency.
3. `M6-ST-B3`: missing/unreadable split M6 authority file.
4. `M6-ST-B4`: P5 orchestration gate failure.
5. `M6-ST-B5`: P6 orchestration gate failure.
6. `M6-ST-B6`: P7 or M6 closure verdict inconsistency.
7. `M6-ST-B7`: `m7_handoff_pack` missing/invalid.
8. `M6-ST-B8`: integrated throughput/latency/lag/error threshold failure.
9. `M6-ST-B9`: artifact/evidence contract incompleteness.
10. `M6-ST-B10`: durable evidence publish/readback failure.
11. `M6-ST-B11`: cross-boundary count continuity drift.
12. `M6-ST-B12`: runtime/spend envelope breach or unattributed spend.

Any open `M6-ST-B*` blocks M6 closure and M7 transition.

## 9) Evidence Contract (M6 Parent)
Required artifacts for each parent stage:
1. `m6_stagea_findings.json`
2. `m6_lane_matrix.json`
3. `m6_probe_latency_throughput_snapshot.json`
4. `m6_control_rail_conformance_snapshot.json`
5. `m6_secret_safety_snapshot.json`
6. `m6_cost_outcome_receipt.json`
7. `m6_blocker_register.json`
8. `m6_execution_summary.json`
9. `m6_decision_log.json`
10. `m7_handoff_pack.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M6 parent stress authority created.
- [x] M6 split-subphase routing (`P5`, `P6`, `P7`) pinned.
- [x] Parent handle packet and parent blocker taxonomy pinned.
- [x] Parent orchestration runbook (`S0..S5`) pinned.
- [x] `M6-ST-S0` executed with blocker-free entry closure.
- [x] `M6-ST-S1` (P5 orchestration gate) executed and closed.
- [x] `M6-ST-S2..S3` subphase orchestration gates executed and closed.
- [x] `M6-ST-S4` integrated stress windows executed within envelope.
- [x] `M6-ST-S5` closure rollup emitted with deterministic `M7_READY` recommendation.

## 11) Immediate Next Actions
1. Preserve `M6-ST-S5` A4R rerun receipt (`m6_stress_s5_20260304T150852Z`) as active M6 hard-close authority.
2. Keep `M7_READY` handoff anchor at `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s5_20260304T150852Z/stress/m7_handoff_pack.json`.
3. Continue with M7 hard-close addendum lanes (`A1..A4`) before advancing to active M8 execution.

## 12) Execution Progress
1. Planning authority created.
2. Latest upstream dependency is M5 parent `S3` pass (`recommendation=GO`, `next_gate=M6_READY`).
3. `M6-ST-S0` executed and passed:
   - `phase_execution_id=m6_stress_s0_20260304T012128Z`,
   - `overall_pass=true`,
   - `next_gate=M6_ST_S1_READY`,
   - `open_blockers=0`,
   - `probe_count=1`, `error_rate_pct=0.0`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s0_20260304T012128Z/stress/`.
4. `M6.P5` (`S0..S5`) executed and passed end-to-end:
   - final phase execution: `m6p5_stress_s5_20260304T013452Z`,
   - final verdict: `ADVANCE_TO_P6`,
   - `next_gate=ADVANCE_TO_P6`,
   - `open_blockers=0`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p5_stress_s5_20260304T013452Z/stress/`.
5. Parent `M6-ST-S1` gate adjudication executed and passed:
   - `phase_execution_id=m6_stress_s1_20260304T013651Z`,
   - `overall_pass=true`,
   - `next_gate=M6_ST_S2_READY`,
   - `open_blockers=0`,
   - `m6p5_dependency_phase_execution_id=m6p5_stress_s5_20260304T013452Z`,
   - `m6p5_verdict=ADVANCE_TO_P6`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s1_20260304T013651Z/stress/`.
6. `M6.P6` (`S0..S5`) executed and passed end-to-end:
   - final phase execution: `m6p6_stress_s5_20260304T015956Z`,
   - final verdict: `ADVANCE_TO_P7`,
   - `next_gate=ADVANCE_TO_P7`,
   - `open_blockers=0`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p6_stress_s5_20260304T015956Z/stress/`.
7. `M6.P7` `S0` entry-gate executed and passed:
   - `phase_execution_id=m6p7_stress_s0_20260304T021107Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S1_READY`,
   - `open_blockers=0`,
   - `p6_dependency_phase_execution_id=m6p6_stress_s5_20260304T020815Z`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s0_20260304T021107Z/stress/`.
8. `M6.P7` `S1` evidence-materialization gate executed and passed:
   - `phase_execution_id=m6p7_stress_s1_20260304T021901Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S2_READY`,
   - `open_blockers=0`,
   - `s0_dependency_phase_execution_id=m6p7_stress_s0_20260304T021107Z`,
   - `historical_m6h_execution_id=m6h_p7a_ingest_commit_20260225T191433Z`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s1_20260304T021901Z/stress/`.
9. `M6.P7` `S2` dedupe/anomaly gate executed and passed:
   - `phase_execution_id=m6p7_stress_s2_20260304T023114Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S3_READY`,
   - `open_blockers=0`,
   - `s1_dependency_phase_execution_id=m6p7_stress_s1_20260304T021901Z`,
   - `ttl_evidence_mode=HISTORICAL_WITH_LIVE_SAMPLE`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s2_20260304T023114Z/stress/`.
10. `M6.P7` `S3` continuity/replay gate executed and passed:
   - `phase_execution_id=m6p7_stress_s3_20260304T023645Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S4_READY`,
   - `open_blockers=0`,
   - `s2_dependency_phase_execution_id=m6p7_stress_s2_20260304T023114Z`,
   - `historical_m6i_execution_id=m6i_p7b_gate_rollup_20260225T191541Z`,
   - `replay_window_mode=HISTORICAL_CLOSED_WINDOW`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s3_20260304T023645Z/stress/`.
11. `M6.P7` `S4` remediation gate executed and passed:
   - `phase_execution_id=m6p7_stress_s4_20260304T024002Z`,
   - `overall_pass=true`,
   - `next_gate=M6P7_ST_S5_READY`,
   - `open_blockers=0`,
   - `s3_dependency_phase_execution_id=m6p7_stress_s3_20260304T023645Z`,
   - `remediation_mode=NO_OP`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s4_20260304T024002Z/stress/`.
12. `M6.P7` `S5` rollup gate executed and passed:
   - `phase_execution_id=m6p7_stress_s5_20260304T024638Z`,
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M7`,
   - `next_gate=ADVANCE_TO_M7`,
   - `open_blockers=0`,
   - `s4_dependency_phase_execution_id=m6p7_stress_s4_20260304T024002Z`,
   - `handoff_path_key=evidence/dev_full/run_control/m6p7_stress_s5_20260304T024638Z/m7_handoff_pack.json`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6p7_stress_s5_20260304T024638Z/stress/`.
13. Parent `M6-ST-S2` executed and passed:
   - `phase_execution_id=m6_stress_s2_20260304T145122Z`,
   - `overall_pass=true`,
   - `next_gate=M6_ST_S3_READY`,
   - `open_blockers=0`,
   - `m6p6_verdict=ADVANCE_TO_P7`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s2_20260304T145122Z/stress/`.
14. Parent `M6-ST-S3` executed and passed:
   - `phase_execution_id=m6_stress_s3_20260304T145156Z`,
   - `overall_pass=true`,
   - `next_gate=M6_ST_S4_READY`,
   - `open_blockers=0`,
   - `m6p7_verdict=ADVANCE_TO_M7`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s3_20260304T145156Z/stress/`.
15. Parent `M6-ST-S4` integrated/addendum execution passed:
   - `phase_execution_id=m6_stress_s4_20260304T145244Z`,
   - `overall_pass=true`,
   - `next_gate=M6_ST_S5_READY`,
   - `open_blockers=0`,
   - integrated checks green (`throughput/latency/lag/error/continuity`),
   - ingest realism checks green (`direct_query_evidence_check=true`, `live_idempotency_sample_check=true`, `proxy_only_check=true`),
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s4_20260304T145244Z/stress/`.
16. Parent `M6-ST-S5` rollup/addendum closure passed:
   - `phase_execution_id=m6_stress_s5_20260304T145252Z`,
   - `overall_pass=true`,
   - `verdict=GO`,
   - `next_gate=M7_READY`,
   - `open_blockers=0`,
   - addendum lane status: `A1=true`, `A2=true`, `A3=true`, `A4=true`,
   - addendum blocker register: `open_blocker_count=0`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s5_20260304T145252Z/stress/`.
17. M6 hard-close addendum artifact contract emitted in parent S5:
   - `m6_addendum_parent_chain_summary.json`,
   - `m6_addendum_integrated_window_summary.json`,
   - `m6_addendum_integrated_window_metrics.json`,
   - `m6_addendum_ingest_live_evidence_summary.json`,
   - `m6_addendum_cost_attribution_receipt.json`,
   - `m6_addendum_blocker_register.json`,
   - `m6_addendum_execution_summary.json`,
   - `m6_addendum_decision_log.json`.
18. Parent `M6-ST-S5` A4R remediation rerun passed with real attributable spend evidence:
   - `phase_execution_id=m6_stress_s5_20260304T150852Z`,
   - `overall_pass=true`,
   - `verdict=GO`,
   - `next_gate=M7_READY`,
   - `open_blockers=0`,
   - addendum lane status `A1=true`, `A2=true`, `A3=true`, `A4=true`,
   - `m6_addendum_cost_attribution_receipt.json`: `mapping_complete=true`, `unattributed_spend_detected=false`, `attributed_spend_usd=5.567148`, `method=aws_ce_daily_unblended_v1`,
   - evidence root: `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m6_stress_s5_20260304T150852Z/stress/`.

## 13) M6 Hard-Close Addendum (Production-Readiness Closure)
Purpose:
1. Promote M6 from subphase-closed posture to strict production-readiness closure by completing parent orchestration (`S2..S5`), proving integrated live-window behavior, and enforcing attributable spend evidence.

Entry prerequisites:
1. latest subphase closure receipts remain green and blocker-free:
   - `M6P5-ST-S5` (`m6p5_stress_s5_20260304T013452Z`),
   - `M6P6-ST-S5` (`m6p6_stress_s5_20260304T020815Z`),
   - `M6P7-ST-S5` (`m6p7_stress_s5_20260304T024638Z`).
2. parent gap was explicit at addendum start and is now resolved in-cycle:
   - parent `M6-ST-S2..S5` executed with closure receipt `m6_stress_s5_20260304T145252Z` and A4R hardening rerun receipt `m6_stress_s5_20260304T150852Z`.
3. run-scope continuity remains pinned to active `platform_run_id`.

No-waiver closure rule:
1. M6 cannot be called production-ready while parent `S2..S5` remain unexecuted.
2. Historical/proxy-only ingest evidence is insufficient for hard-close acceptance.
3. Synthetic `window_seconds=1` cost receipts are insufficient for hard-close acceptance.

### 13.1 Addendum Capability Lanes
| Lane | ID | Objective | Hard acceptance posture |
| --- | --- | --- | --- |
| Parent orchestration completion | `A1` | close missing parent adjudication/rollup path | parent `S2` and `S3` execute green with deterministic verdict contracts and zero open blockers |
| Integrated live-window stress | `A2` | prove control->stream->ingress behavior under sustained/burst/fault pressure | parent `S4` windows pass against throughput/latency/lag/error/runtime/spend envelopes |
| Ingest realism hardening | `A3` | remove proxy-only closure weakness in ingest semantics | live-window offsets/replay/idempotency evidence observed directly (no historical-only closure mode) |
| Cost attribution closure | `A4` | map spend to active M6 windows and closure outcomes | attributable spend receipt includes source mapping and `unattributed_spend_detected=false` |

### 13.2 Addendum Execution Packet (Pinned)
1. `M6_ADDENDUM_PROFILE_ID = "m6_production_hard_close_v0"`.
2. `M6_ADDENDUM_EXPECTED_GATE_ON_PASS = "M7_READY_REAFFIRMED"`.
3. `M6_ADDENDUM_REQUIRED_PARENT_STAGES = "S2|S3|S4|S5"`.
4. `M6_ADDENDUM_DISALLOW_PROXY_ONLY_INGEST_CLOSURE = true`.
5. `M6_ADDENDUM_DIRECT_METRICS_REQUIRED = "throughput,latency_p95,lag,error_rate"`.
6. `M6_ADDENDUM_COST_ATTRIBUTION_MIN_WINDOW_SECONDS = 600`.
7. `M6_ADDENDUM_MAX_RUNTIME_MINUTES = 300`.
8. `M6_ADDENDUM_MAX_SPEND_USD = 90`.

### 13.3 Addendum Blocker Mapping
1. `M6-ADD-B1`: parent stage implementation/execution gap (`S2..S5`) remains unresolved.
2. `M6-ADD-B2`: parent adjudication mismatch on required subphase verdicts (`ADVANCE_TO_P7` / `ADVANCE_TO_M7`).
3. `M6-ADD-B3`: integrated live-window threshold breach (throughput/latency/lag/error/runtime/spend).
4. `M6-ADD-B4`: ingest closure still depends on historical/proxy-only evidence.
5. `M6-ADD-B5`: cost attribution incomplete or unexplained spend detected.
6. `M6-ADD-B6`: addendum artifact contract incomplete or unreadable.

### 13.4 Addendum Evidence Contract Extension
1. `m6_addendum_parent_chain_summary.json`
2. `m6_addendum_integrated_window_summary.json`
3. `m6_addendum_integrated_window_metrics.json`
4. `m6_addendum_ingest_live_evidence_summary.json`
5. `m6_addendum_cost_attribution_receipt.json`
6. `m6_addendum_blocker_register.json`
7. `m6_addendum_execution_summary.json`
8. `m6_addendum_decision_log.json`

### 13.5 Addendum DoD
- [x] Lane `A1` executed with parent `M6-ST-S2` and `M6-ST-S3` green and deterministic verdict contracts preserved.
- [x] Lane `A2` executed with parent `M6-ST-S4` sustained/burst/fault windows green within runtime/spend envelope.
- [x] Lane `A3` executed with live-window ingest evidence replacing historical/proxy-only closure mode for offsets/replay/idempotency checks.
- [x] Lane `A4` executed with real CE-backed spend attribution (`window_seconds >= 600`) and `unattributed_spend_detected=false`.
- [x] Addendum blocker register closed (`open_blocker_count=0`) and parent `M6-ST-S5` reaffirms deterministic `M7_READY`.

### 13.6 Addendum Execution Order
1. `A1` -> parent orchestration completion (`S2`, `S3`).
2. `A2` -> integrated live-window stress (`S4` sustained/burst/fault).
3. `A3` -> ingest realism hardening (live offsets/replay/idempotency evidence).
4. `A4` -> cost attribution closure and final parent rollup (`S5`) with `M7_READY` reaffirmation.
