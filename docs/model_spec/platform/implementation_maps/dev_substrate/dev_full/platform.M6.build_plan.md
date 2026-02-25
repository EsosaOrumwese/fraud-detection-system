# Dev Substrate Deep Plan - M6 (P5 READY_PUBLISHED + P6 STREAMING_ACTIVE + P7 INGEST_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M6._
_Last updated: 2026-02-25_

## 0) Purpose
M6 closes:
1. `P5 READY_PUBLISHED`.
2. `P6 STREAMING_ACTIVE`.
3. `P7 INGEST_COMMITTED`.

M6 must prove:
1. READY is committed with Step Functions authority and duplicate ambiguity is fail-closed.
2. Streaming is active with bounded lag and no unresolved publish ambiguity.
3. Ingest commit evidence (receipt/quarantine/offset + dedupe posture) is complete and deterministic.
4. Runtime evidence policy is honored on hot paths (no per-event sync object-store writes without explicit waiver).
5. `M7` entry handoff is deterministic and auditable.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P5`, `P6`, `P7` sections)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P4.build_plan.md`
3. `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/m6_handoff_pack.json`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M6
In scope:
1. `P5` READY publication closure.
2. `P6` streaming activation closure.
3. `P7` ingest commit closure.
4. M6 phase verdict + `M7` handoff artifact.
5. M6 phase-budget + cost-outcome closure.

Out of scope:
1. `P8+` RTDL/case-label/obs-gov closures (`M7+`).
2. Learning/evolution closures (`M9+`).

## 3) Deliverables
1. `P5` gate verdict artifacts.
2. `P6` gate verdict artifacts.
3. `P7` gate verdict artifacts.
4. `m7_handoff_pack.json`.
5. `m6_execution_summary.json`.
6. `m6_phase_budget_envelope.json` and `m6_phase_cost_outcome_receipt.json`.

## 4) Entry Gate and Current Posture
Entry gate for M6:
1. `M5` is `DONE` with verdict `ADVANCE_TO_M6`.

Current posture:
1. `M5` closure is complete (`m5j_p4e_gate_rollup_20260225T021715Z`).
2. M6 planning is being expanded before execution.

Initial pre-execution blockers (fail-closed, planning stage):
1. `M6-B0`: M6 deep plan/capability-lane incompleteness.
2. `M6-B0.1`: `P5/P6/P7` split planning not explicit.

## 4.1) Anti-Cram Law (Binding for M6)
M6 is not execution-ready unless these capability lanes are explicit:
1. authority and handle closure across `P5..P7`,
2. READY commit authority and duplicate-ambiguity controls,
3. streaming activation/lag posture and publish-ambiguity closure,
4. ingest commit evidence and dedupe/anomaly closure,
5. evidence-overhead conformance on hot paths,
6. durable evidence publication,
7. gate rollups + M6 verdict + `M7` handoff,
8. phase-budget and cost-outcome gating.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure (`P5..P7`) | M6.A | no unresolved required handles |
| READY entry + contract precheck | M6.B | READY entry snapshot pass |
| READY commit authority execution | M6.C | READY commit snapshot + receipt pass |
| `P5` gate rollup + verdict | M6.D | blocker-free `P5` verdict |
| Streaming entry/activation precheck | M6.E | streaming entry snapshot pass |
| Streaming active + lag + ambiguity closure | M6.F | streaming snapshot + lag posture pass |
| `P6` gate rollup + verdict | M6.G | blocker-free `P6` verdict |
| Ingest commit closure | M6.H | receipt/quarantine/offset snapshot pass |
| `P7` rollup + M6 verdict + `M7` handoff | M6.I | blocker-free `P7` verdict + durable `m7_handoff_pack.json` |
| M6 closure sync + cost-outcome | M6.J | `m6_execution_summary.json` + cost artifacts pass |

## 5) Work Breakdown (Orchestration)

### M6.A Authority + Handle Closure (`P5..P7`)
Goal:
1. close required `M6` handles before runtime execution.

Tasks:
1. resolve `P5` required handles (`FP_BUS_CONTROL_V1`, `SR_READY_COMMIT_*`, `READY_MESSAGE_FILTER`, `WSP_*`).
2. resolve `P6` required handles (Flink runtime-path references, EMR-on-EKS control-plane handles when active path is `EKS_EMR_ON_EKS`, lag threshold handles, publish-ambiguity controls).
3. resolve `P7` required handles (`RECEIPT_SUMMARY_PATH_PATTERN`, `QUARANTINE_SUMMARY_PATH_PATTERN`, `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`, idempotency handles).
4. close missing handoff handle gap by pinning:
   - `M6_HANDOFF_PACK_PATH_PATTERN`,
   - `M7_HANDOFF_PACK_PATH_PATTERN`.

DoD:
- [x] required handle set is explicit and complete.
- [x] unresolved required handles are blocker-marked.
- [x] M6.A closure snapshot exists locally and durably.

M6.A execution closure (2026-02-25):
1. Registry pin remediation applied:
   - added `M6_HANDOFF_PACK_PATH_PATTERN`,
   - added `M7_HANDOFF_PACK_PATH_PATTERN`.
2. Authoritative green run:
   - execution id: `m6a_p5p7_handle_closure_20260225T023522Z`
   - local root: `runs/dev_substrate/dev_full/m6/m6a_p5p7_handle_closure_20260225T023522Z/`
   - summary: `runs/dev_substrate/dev_full/m6/m6a_p5p7_handle_closure_20260225T023522Z/m6a_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, next gate `M6.B_READY`.
3. Handle-closure outcomes:
   - required handles checked: `25`,
   - resolved handles: `25`,
   - unresolved handle blockers: none.
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6a_p5p7_handle_closure_20260225T023522Z/m6a_handle_closure_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6a_p5p7_handle_closure_20260225T023522Z/m6a_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6a_p5p7_handle_closure_20260225T023522Z/m6a_execution_summary.json`
5. Next action:
   - advance to `M6.B` (`P5` entry + contract precheck).

### M6.B `P5` READY Entry + Contract Precheck
Goal:
1. prove `P5` entry is valid before READY commit.

Tasks:
1. verify SR prerequisites and run-scope alignment.
2. verify control topic path and partitioning contracts.
3. verify READY filter and duplicate controls are loaded.

DoD:
- [x] `P5` entry precheck passes.
- [x] blocker set is explicit if any precheck fails.

M6.B execution closure (2026-02-25):
1. Authoritative green run:
   - execution id: `m6b_p5a_ready_entry_20260225T024245Z`
   - local root: `runs/dev_substrate/dev_full/m6/m6b_p5a_ready_entry_20260225T024245Z/`
   - summary: `runs/dev_substrate/dev_full/m6/m6b_p5a_ready_entry_20260225T024245Z/m6b_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, next gate `M6.C_READY`.
2. Entry outcomes:
   - `M6.A` upstream dependency verified,
   - `m6_handoff_pack.json` continuity verified,
   - required P5 handles resolved `13/13`,
   - Step Functions commit authority surface verified (`ACTIVE`).
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6b_p5a_ready_entry_20260225T024245Z/m6b_ready_entry_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6b_p5a_ready_entry_20260225T024245Z/m6b_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6b_p5a_ready_entry_20260225T024245Z/m6b_execution_summary.json`
4. Next action:
   - advance to `M6.C` (`P5.B` READY commit authority execution).

### M6.C `P5` READY Commit Authority Execution
Goal:
1. commit READY with Step Functions authority and deterministic receipt.

Tasks:
1. emit READY signal to `fp.bus.control.v1`.
2. require READY receipt with Step Functions execution reference.
3. fail-closed on duplicate/ambiguous READY outcomes.

DoD:
- [x] READY emitted and observable.
- [x] receipt includes Step Functions commit authority reference.
- [x] no unresolved duplicate/ambiguity remains.

M6.C execution closure (2026-02-25):
1. Authoritative green run:
   - execution id: `m6c_p5b_ready_commit_20260225T041702Z`
   - local root: `runs/dev_substrate/dev_full/m6/m6c_p5b_ready_commit_20260225T041702Z/`
   - summary: `runs/dev_substrate/dev_full/m6/m6c_p5b_ready_commit_20260225T041702Z/m6c_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, next gate `M6.D_READY`.
2. Runtime outcomes:
   - Step Functions execution succeeded under `step_functions_only` commit authority.
   - in-VPC ephemeral publisher emitted READY on `fp.bus.control.v1` (partition `2`, offset `1`, run-scoped key).
   - READY commit receipt written with Step Functions execution reference:
     - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/sr/ready_commit_receipt.json`.
   - duplicate/ambiguity state: `clear`.
3. Durable control evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6c_p5b_ready_commit_20260225T041702Z/m6c_ready_commit_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6c_p5b_ready_commit_20260225T041702Z/m6c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6c_p5b_ready_commit_20260225T041702Z/m6c_execution_summary.json`
4. Remediation closed:
   - prior `M6P5-B2` failures were traced to missing signer package metadata in ephemeral Lambda bundles.
   - closure run packaged `aws_msk_iam_sasl_signer_python-*.dist-info` with runtime modules and retained cleanup-on-exit for temp publisher resources.

### M6.D `P5` Gate Rollup + Verdict
Goal:
1. adjudicate `P5` from M6.B..M6.C evidence.

Tasks:
1. build `P5` rollup matrix and blocker register.
2. emit deterministic `P5` verdict artifact.

DoD:
- [x] `P5` rollup + blocker register committed.
- [x] deterministic `P5` verdict committed.

M6.D execution closure (2026-02-25):
1. Authoritative green run:
   - execution id: `m6d_p5c_gate_rollup_20260225T041801Z`
   - local root: `runs/dev_substrate/dev_full/m6/m6d_p5c_gate_rollup_20260225T041801Z/`
   - summary: `runs/dev_substrate/dev_full/m6/m6d_p5c_gate_rollup_20260225T041801Z/m6d_execution_summary.json`
   - result: `overall_pass=true`, blocker count `0`.
2. P5 verdict:
   - `verdict=ADVANCE_TO_P6`
   - `next_gate=M6.E_READY`.
3. Durable rollup evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6d_p5c_gate_rollup_20260225T041801Z/m6d_p5_gate_rollup_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6d_p5c_gate_rollup_20260225T041801Z/m6d_p5_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6d_p5c_gate_rollup_20260225T041801Z/m6d_p5_gate_verdict.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6d_p5c_gate_rollup_20260225T041801Z/m6d_execution_summary.json`

### M6.E `P6` Entry + Streaming Activation Precheck
Goal:
1. verify streaming activation entry contracts.

Tasks:
1. verify WSP source roots pinned for run.
2. verify required Flink lanes and ingress edge are healthy.
3. verify publish ambiguity controls are active fail-closed.

DoD:
- [x] `P6` entry precheck passes.
- [x] unresolved precheck blockers are explicit.

Execution status (2026-02-25):
1. Historical state:
   - early attempts (`m6e_p6a_stream_entry_20260225T044348Z`, `m6e_p6a_stream_entry_20260225T044618Z`) were fail-closed on `M6P6-B2` under MSF-only posture.
2. Remediation completed:
   - runtime path repinned to `EKS_EMR_ON_EKS`,
   - EMR virtual cluster materialized: `3cfszbpz28ixf1wmmd2roj571`,
   - release label pinned: `emr-6.15.0-latest`.
3. Authoritative rerun:
   - `m6e_p6a_stream_entry_20260225T120522Z`,
   - local: `runs/dev_substrate/dev_full/m6/m6e_p6a_stream_entry_20260225T120522Z/`,
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6e_p6a_stream_entry_20260225T120522Z/`.
4. Result:
   - `overall_pass=true`,
   - blocker count `0`,
   - `next_gate=M6.F_READY`.

### M6.F `P6` Streaming Active + Lag + Ambiguity Closure
Goal:
1. prove active streaming posture and bounded lag.

Tasks:
1. capture streaming counters and activation proofs.
2. measure lag against pinned threshold.
3. require no unresolved publish ambiguity.
4. capture evidence-overhead posture metrics (`latency p95`, `bytes/event`, `write-rate`).

DoD:
- [x] streaming active proof passes.
- [x] lag within threshold.
- [x] no unresolved publish ambiguity.
- [x] evidence-overhead posture within accepted budget.

Execution status (2026-02-25):
1. Executed as `m6f_p6b_streaming_active_20260225T121536Z`.
2. Result is fail-closed:
   - `overall_pass=false`,
   - blocker count `3`,
   - `next_gate=HOLD_REMEDIATE`.
3. Active blockers:
   - `M6P6-B2`: required Flink lane refs not active in the EMR virtual cluster,
   - `M6P6-B3`: run-scoped streaming/admission counters remain zero,
   - `M6P6-B4`: lag posture unresolved without active stream consumption.
4. Evidence:
   - local: `runs/dev_substrate/dev_full/m6/m6f_p6b_streaming_active_20260225T121536Z/`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T121536Z/`

Bounded remediation lane (approved) before rerun:
1. Patch IG runtime boundary so successful `/ingest/push` admissions persist idempotency records to DynamoDB.
2. Materialize active EMR lane jobs for `sr-ready` and `wsp-stream` refs in the pinned VC.
3. Generate run-scoped ingress admissions from lane execution (no synthetic non-lane shortcut).
4. Rerun `M6.F`; only zero-blocker result unlocks `M6.G`.

Refined blocker-closure plan (2026-02-25 live-state adjudication):
1. Blocker delta:
   - `M6P6-B3` is structurally remediated (`DDB_IG_IDEMPOTENCY_TABLE` non-zero) and remains a rerun validation check.
   - active blockers to clear in rerun remain `M6P6-B2` and `M6P6-B4`.
2. Root-cause findings behind `M6P6-B2`:
   - EKS worker nodegroup `fraud-platform-dev-full-m6f-workers` is `CREATE_FAILED` (`NodeCreationFailure`).
   - EMR lane refs `fraud-platform-dev-full-wsp-stream-v0` and `fraud-platform-dev-full-sr-ready-v0` fail with scheduler error (`no nodes available to schedule pods`).
   - failed Bottlerocket worker console output shows bootstrap failure at `pluto` timeout retrieving private DNS from EC2.
   - private route table is local-only; required private endpoint surfaces for worker bootstrap/image pull/token exchange are not yet materialized.
3. Execution-grade remediation lanes before rerun:
   - Lane A (network bootstrap connectivity via IaC):
     - add private VPC endpoints for `ec2`, `ecr.api`, `ecr.dkr`, `sts` (interface, private DNS enabled),
     - add `s3` gateway endpoint on private route table,
     - attach dedicated endpoint SG (`443`) from private subnet CIDRs.
   - Lane B (worker capacity via IaC):
     - codify `M6.F` worker nodegroup in Terraform runtime stack (managed nodegroup, desired >= 1),
     - replace failed ad-hoc nodegroup path with deterministic apply/destroy lifecycle.
   - Lane C (stream-lane semantic validity):
     - replace placeholder EMR job drivers (`SparkPi`) with lane-authentic job specs for `wsp-stream` and `sr-ready` refs before semantic closure claim.
   - Lane D (gate rerun):
     - rerun `M6.F` with fresh `phase_execution_id`,
     - require `B2` clear (`wsp_active>0` and `sr_ready_active>0`), `B3` validation pass (non-zero admission progression), and `B4` clear (`measured_lag <= RTDL_CAUGHT_UP_LAG_MAX`).
4. Hard stop:
   - do not mark `M6.F` complete or execute `M6.G` until Lanes A-D are green and new `m6f_*` artifacts are committed locally + durably.

Refined remediation DoD (M6.F blocker-closure lane):
- [x] Lane A complete: required private endpoint surfaces are materialized in IaC and readable (`ec2`, `ecr.api`, `ecr.dkr`, `sts`, `s3` gateway).
- [x] Lane B complete: worker nodegroup is IaC-managed, reports `ACTIVE`, and at least one node is `Ready`.
- [x] Lane C complete: `wsp-stream` and `sr-ready` refs run with lane-authentic specs (no placeholder-only `SparkPi` closure claim).
- [x] Lane D complete: fresh `M6.F` rerun captures `wsp_active>0`, `sr_ready_active>0`, and non-zero admission progression.
- [x] `M6P6-B2` and `M6P6-B4` are cleared in rerun blocker register.
- [x] `M6P6-B3` remains clear in rerun validation evidence.
- [x] rerun `m6f_*` artifacts are committed locally and durably.

Rerun closure status (2026-02-25):
1. Fresh execution completed:
   - `m6f_p6b_streaming_active_20260225T143900Z`,
   - `overall_pass=true`,
   - blocker count `0`,
   - `next_gate=M6.G_READY`.
2. Key closure evidence:
   - `wsp_active_count=1`,
   - `sr_ready_active_count=1`,
   - `ig_idempotency_count=5`,
   - `measured_lag=0` (`within_threshold=true`),
   - `unresolved_publish_ambiguity_count=0`.
3. Evidence locations:
   - local: `runs/dev_substrate/dev_full/m6/m6f_p6b_streaming_active_20260225T143900Z/`
   - durable: `s3://fraud-platform-dev-full-artifacts/evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T143900Z/`
4. Cost control note:
   - temporary EMR lane jobs used for capture window were explicitly cancelled immediately after artifact capture.

### M6.G `P6` Gate Rollup + Verdict
Goal:
1. adjudicate `P6` from M6.E..M6.F evidence.

Tasks:
1. build `P6` rollup matrix and blocker register.
2. emit deterministic `P6` verdict artifact.

DoD:
- [ ] `P6` rollup + blocker register committed.
- [ ] deterministic `P6` verdict committed.

### M6.H `P7` Ingest Commit Closure
Goal:
1. prove ingest commit evidence is complete.

Tasks:
1. publish/verify receipt summary.
2. publish/verify quarantine summary.
3. publish/verify Kafka offset snapshot.
4. run dedupe/anomaly checks for fail-closed closure.

DoD:
- [ ] receipt/quarantine/offset evidence is committed and readable.
- [ ] dedupe/anomaly checks pass.

### M6.I `P7` Gate Rollup + M6 Verdict + M7 Handoff
Goal:
1. adjudicate `P7` and emit M6 phase verdict/handoff.

Tasks:
1. build `P7` rollup matrix + blocker register.
2. emit deterministic `P7` verdict.
3. emit `m7_handoff_pack.json` with run-scope continuity and evidence refs.

DoD:
- [ ] `P7` rollup + verdict committed.
- [ ] `m7_handoff_pack.json` committed locally and durably.

### M6.J M6 Closure Sync + Cost-Outcome
Goal:
1. finalize M6 closure artifacts and logs.

Tasks:
1. emit `m6_execution_summary.json`.
2. emit `m6_phase_budget_envelope.json` and `m6_phase_cost_outcome_receipt.json`.
3. append closure notes to master plan + impl map + logbook.

DoD:
- [ ] M6 execution summary committed locally and durably.
- [ ] phase-budget/cost-outcome artifacts committed and valid.
- [ ] closure notes appended in required docs.

## 6) Split Deep Plan Routing
1. `P5` detailed lane plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P5.build_plan.md`
2. `P6` detailed lane plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P6.build_plan.md`
3. `P7` detailed lane plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P7.build_plan.md`

Rule:
1. M6 execution follows:
   - `M6.A -> M6.B -> M6.C -> M6.D -> M6.E -> M6.F -> M6.G -> M6.H -> M6.I -> M6.J`.
2. `P6` execution cannot start until `P5` verdict is `ADVANCE_TO_P6`.
3. `P7` execution cannot start until `P6` verdict is `ADVANCE_TO_P7`.

## 7) M6 Blocker Taxonomy (Fail-Closed)
1. `M6-B0`: deep plan/capability-lane incompleteness.
2. `M6-B0.1`: `P5/P6/P7` split plan incompleteness.
3. `M6-B1`: required handle missing/inconsistent.
4. `M6-B2`: READY commit authority failure.
5. `M6-B3`: duplicate/ambiguous READY unresolved.
6. `M6-B4`: streaming activation failure/stall.
7. `M6-B5`: lag threshold breach.
8. `M6-B6`: unresolved publish ambiguity.
9. `M6-B7`: ingest evidence surface missing/unreadable.
10. `M6-B8`: dedupe/anomaly drift.
11. `M6-B9`: evidence-overhead budget breach.
12. `M6-B10`: rollup/verdict inconsistency.
13. `M6-B11`: `m7_handoff_pack.json` missing/invalid/unreadable.
14. `M6-B12`: phase-budget/cost-outcome artifact missing/invalid.
15. `M6-B13`: cost-outcome hard-stop violated.

Any active `M6-B*` blocker prevents M6 closure.

## 8) M6 Evidence Contract (Pinned for Planning)
1. `m6a_handle_closure_snapshot.json`
2. `m6b_ready_entry_snapshot.json`
3. `m6c_ready_commit_snapshot.json`
4. `m6d_p5_gate_verdict.json`
5. `m6e_stream_activation_entry_snapshot.json`
6. `m6f_streaming_active_snapshot.json`
7. `m6f_evidence_overhead_snapshot.json`
8. `m6g_p6_gate_verdict.json`
9. `m6h_ingest_commit_snapshot.json`
10. `m6i_p7_gate_verdict.json`
11. `m7_handoff_pack.json`
12. `m6_phase_budget_envelope.json`
13. `m6_phase_cost_outcome_receipt.json`
14. `m6_execution_summary.json`

## 9) M6 Completion Checklist
- [x] M6.A complete
- [x] M6.B complete
- [x] M6.C complete
- [x] M6.D complete
- [x] M6.E complete
- [x] M6.F complete
- [ ] M6.G complete
- [ ] M6.H complete
- [ ] M6.I complete
- [ ] M6.J complete
- [ ] M6 blockers resolved or explicitly fail-closed
- [ ] M6 phase-budget and cost-outcome artifacts are valid and accepted
- [ ] M6 closure note appended in implementation map
- [ ] M6 action log appended in logbook

## 10) Exit Criteria
M6 can close only when:
1. all checklist items in Section 9 are complete,
2. `P5`, `P6`, and `P7` verdicts are blocker-free and deterministic,
3. M6 evidence is locally and durably readable,
4. `m7_handoff_pack.json` is committed and reference-valid,
5. phase-budget and cost-outcome artifacts are valid and blocker-free.

Handoff posture:
1. M7 remains blocked until M6 verdict is `ADVANCE_TO_M7`.

## 11) Planning Status (Current)
1. M5 dependency is closed green (`ADVANCE_TO_M6`).
2. M6 orchestration plan is expanded to execution-grade with split `P5/P6/P7` ownership.
3. Initial planning blockers resolved:
   - `M6-B0` resolved,
   - `M6-B0.1` resolved.
4. `M6.A` is closed green (`m6a_p5p7_handle_closure_20260225T023522Z`) after handoff-handle pin remediation.
5. `M6.B` is closed green (`m6b_p5a_ready_entry_20260225T024245Z`) with `M6.C_READY`.
6. `M6.C` is closed green (`m6c_p5b_ready_commit_20260225T041702Z`) with `M6.D_READY`.
7. `M6.D` is closed green (`m6d_p5c_gate_rollup_20260225T041801Z`) with verdict `ADVANCE_TO_P6` and `M6.E_READY`.
8. `M6.E` is closed green (`m6e_p6a_stream_entry_20260225T120522Z`) with `M6.F_READY`.
9. `M6.F` fail-closed attempt (`m6f_p6b_streaming_active_20260225T121536Z`) was remediated and rerun closed green as `m6f_p6b_streaming_active_20260225T143900Z` (`blocker_count=0`, `M6.G_READY`).
