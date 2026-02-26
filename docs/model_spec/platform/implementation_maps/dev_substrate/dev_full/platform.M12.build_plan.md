# Dev Substrate Deep Plan - M12 (P15 MPR_PROMOTION_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M12._
_Last updated: 2026-02-26_

## 0) Purpose
M12 closes:
1. `P15 MPR_PROMOTION_COMMITTED`.

M12 must prove:
1. promotion eligibility and compatibility checks are fail-closed.
2. promotion event commit is append-only and deterministic.
3. rollback drill is executed and evidence-backed.
4. ACTIVE bundle resolution remains compatibility-safe for runtime.
5. deterministic `P15` verdict and M13 handoff are committed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P15`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M11.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M12
In scope:
1. MPR authority/handle closure.
2. candidate eligibility and compatibility prechecks.
3. promotion event commit and governance append checks.
4. rollback drill execution and closure.
5. ACTIVE bundle resolution checks against runtime compatibility.
6. deterministic P15 verdict + M13 handoff.
7. phase budget envelope and cost-outcome closure.

Out of scope:
1. full-platform final verdict and teardown (`M13`).
2. additional model retraining cycles beyond the selected candidate.

## 3) Deliverables
1. `m12a_handle_closure_snapshot.json`
2. `m12b_candidate_eligibility_snapshot.json`
3. `m12c_compatibility_precheck_snapshot.json`
4. `m12d_promotion_commit_snapshot.json`
5. `m12e_rollback_drill_snapshot.json`
6. `m12f_active_resolution_snapshot.json`
7. `m12g_governance_append_snapshot.json`
8. `m12h_p15_gate_verdict.json`
9. `m13_handoff_pack.json`
10. `m12_phase_budget_envelope.json`
11. `m12_phase_cost_outcome_receipt.json`
12. `m12_execution_summary.json`
13. `m12_post_promotion_observation_snapshot.json`
14. `m12_operability_acceptance_report.json`

## 4) Entry Gate and Current Posture
Entry gate for M12:
1. `M11` is `DONE`.
2. `P14` verdict is `ADVANCE_TO_P15`.
3. M11 blockers are resolved.

Current posture:
1. M12 planning is expanded and execution-grade.
2. Execution has not started.

## 4.1) Anti-Cram Law (Binding for M12)
M12 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. candidate eligibility and compatibility prechecks.
3. promotion commit and append-only governance checks.
4. rollback drill execution.
5. ACTIVE resolution and runtime compatibility checks.
6. deterministic verdict + M13 handoff.
7. cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M12.A | no unresolved required P15 handles |
| Candidate eligibility | M12.B | eligibility snapshot pass |
| Compatibility prechecks | M12.C | compatibility checks pass |
| Promotion commit | M12.D | promotion commit snapshot pass |
| Rollback drill | M12.E | rollback drill snapshot pass |
| ACTIVE resolution | M12.F | active-resolution snapshot pass |
| Governance append closure | M12.G | append checks pass |
| P15 verdict + M13 handoff | M12.H | `ADVANCE_TO_P16` + `m13_handoff_pack.json` |
| Cost-outcome closure | M12.I | budget + receipt pass |
| Closure sync | M12.J | `m12_execution_summary.json` committed |

## 4.3) Non-Gate Acceptance Objectives (Mandatory)
M12 cannot close on gate-chain pass alone. All items below are required:
1. Promotion safety acceptance:
- promotion includes explicit blast-radius posture and reversible control surface.
2. Operational trust acceptance:
- post-promotion observation window is captured with explicit health/drift/error posture.
3. Rollback realism acceptance:
- rollback drill proves practical operator recoverability with bounded restore objective evidence.
4. Governance completeness acceptance:
- approval, promotion, and rollback rationale is append-only and audit-complete.
5. Runtime continuity acceptance:
- ACTIVE resolution remains coherent with serving/runtime contract without hidden compatibility waivers.

## 5) Work Breakdown (Orchestration)

### M12.A P15 Authority + Handle Closure
Goal:
1. close required P15 handles before promotion corridor execution.

Required handle set:
1. `MPR_PROMOTION_RECEIPT_PATH_PATTERN`
2. `MPR_ROLLBACK_DRILL_PATH_PATTERN`
3. `FP_BUS_LEARNING_REGISTRY_EVENTS_V1`
4. `GOV_APPEND_LOG_PATH_PATTERN`
5. `GOV_RUN_CLOSE_MARKER_PATH_PATTERN`
6. `MF_CANDIDATE_BUNDLE_PATH_PATTERN`
7. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
8. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

DoD:
- [ ] required handle matrix explicit and complete.
- [ ] unresolved handles are blocker-marked.
- [ ] `m12a_handle_closure_snapshot.json` committed locally and durably.

### M12.B Candidate Eligibility Precheck
Goal:
1. prove candidate bundle is eligible for promotion corridor.

Tasks:
1. validate candidate bundle refs and provenance completeness.
2. validate gating prerequisites from M11.
3. emit `m12b_candidate_eligibility_snapshot.json`.

DoD:
- [ ] eligibility checks pass.
- [ ] snapshot committed locally and durably.

### M12.C Compatibility Prechecks
Goal:
1. fail-closed on compatibility mismatch before promotion.

Tasks:
1. validate feature-set and input contract compatibility.
2. validate required capability and degrade-mask compatibility.
3. emit `m12c_compatibility_precheck_snapshot.json`.

DoD:
- [ ] compatibility prechecks pass.
- [ ] snapshot committed locally and durably.

### M12.D Promotion Event Commit
Goal:
1. commit promotion event with append-only semantics.

Tasks:
1. perform promotion commit action.
2. verify append-only event emission and receipt path.
3. emit `m12d_promotion_commit_snapshot.json`.

DoD:
- [ ] promotion event commit passes.
- [ ] snapshot committed locally and durably.

### M12.E Rollback Drill Execution
Goal:
1. execute and verify rollback drill for promoted candidate.

Tasks:
1. run rollback drill scenario.
2. capture drill outputs and outcome state.
3. capture bounded restore objective evidence and operator runbook viability notes.
4. emit `m12e_rollback_drill_snapshot.json`.

DoD:
- [ ] rollback drill passes.
- [ ] rollback drill includes bounded restore objective evidence.
- [ ] snapshot committed locally and durably.

### M12.F ACTIVE Resolution Checks
Goal:
1. verify ACTIVE bundle resolution remains deterministic and safe.

Tasks:
1. validate one-active-per-scope resolution.
2. validate runtime compatibility checks on resolved ACTIVE bundle.
3. emit `m12_post_promotion_observation_snapshot.json`.
4. emit `m12f_active_resolution_snapshot.json`.

DoD:
- [ ] ACTIVE resolution checks pass.
- [ ] post-promotion observation snapshot is pass posture.
- [ ] snapshot committed locally and durably.

### M12.G Governance Append Closure
Goal:
1. prove governance append evidence is complete and coherent.

Tasks:
1. validate append ordering and required event set.
2. validate promotion and rollback evidence refs.
3. emit `m12_operability_acceptance_report.json`.
4. emit `m12g_governance_append_snapshot.json`.

DoD:
- [ ] governance append checks pass.
- [ ] operability/governance acceptance report is published and pass posture.
- [ ] snapshot committed locally and durably.

### M12.H P15 Gate Rollup + M13 Handoff
Goal:
1. produce deterministic P15 verdict and handoff.

Tasks:
1. roll up M12A-G outcomes in fixed order.
2. emit `m12h_p15_gate_verdict.json`.
3. emit `m13_handoff_pack.json`.

DoD:
- [ ] deterministic verdict is emitted.
- [ ] pass posture requires `ADVANCE_TO_P16` + `next_gate=M13_READY`.
- [ ] handoff pack committed locally and durably.

### M12.I M12 Phase Budget + Cost-Outcome Closure
Goal:
1. publish M12 cost-to-outcome artifacts.

Tasks:
1. emit `m12_phase_budget_envelope.json`.
2. emit `m12_phase_cost_outcome_receipt.json`.

DoD:
- [ ] budget + receipt artifacts committed locally and durably.
- [ ] artifacts are coherent with emitted outcomes.

### M12.J M12 Closure Sync
Goal:
1. close M12 and publish authoritative summary.

Tasks:
1. emit `m12_execution_summary.json`.
2. validate local + durable parity of M12 outputs.

DoD:
- [ ] `m12_execution_summary.json` committed locally and durably.
- [ ] M12 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M12-B1`: authority/handle closure failure.
2. `M12-B2`: candidate eligibility failure.
3. `M12-B3`: compatibility precheck failure.
4. `M12-B4`: promotion commit failure.
5. `M12-B5`: rollback drill failure.
6. `M12-B6`: ACTIVE resolution failure.
7. `M12-B7`: governance append failure.
8. `M12-B8`: P15 rollup/verdict inconsistency.
9. `M12-B9`: handoff publication failure.
10. `M12-B10`: phase cost-outcome closure failure.
11. `M12-B11`: summary/evidence publication parity failure.
12. `M12-B12`: non-gate acceptance failure (promotion safety/observation/rollback realism/governance completeness).

## 7) Artifact Contract (M12)
1. `m12a_handle_closure_snapshot.json`
2. `m12b_candidate_eligibility_snapshot.json`
3. `m12c_compatibility_precheck_snapshot.json`
4. `m12d_promotion_commit_snapshot.json`
5. `m12e_rollback_drill_snapshot.json`
6. `m12f_active_resolution_snapshot.json`
7. `m12g_governance_append_snapshot.json`
8. `m12h_p15_gate_verdict.json`
9. `m13_handoff_pack.json`
10. `m12_phase_budget_envelope.json`
11. `m12_phase_cost_outcome_receipt.json`
12. `m12_execution_summary.json`
13. `m12_post_promotion_observation_snapshot.json`
14. `m12_operability_acceptance_report.json`

## 8) Completion Checklist
- [ ] `M12.A` complete
- [ ] `M12.B` complete
- [ ] `M12.C` complete
- [ ] `M12.D` complete
- [ ] `M12.E` complete
- [ ] `M12.F` complete
- [ ] `M12.G` complete
- [ ] `M12.H` complete
- [ ] `M12.I` complete
- [ ] `M12.J` complete
- [ ] all active `M12-B*` blockers resolved
- [ ] non-gate acceptance artifacts (`post_promotion_observation`, `operability_acceptance`) are pass posture

## 9) Planning Status
1. M12 planning is expanded and execution-grade.
2. Execution is blocked until M11 closure is green and handoff is committed.
