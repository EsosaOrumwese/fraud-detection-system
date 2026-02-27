# Dev Substrate Deep Plan - M12 (P15 MPR_PROMOTION_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-02-27_

## 0) Purpose
M12 closes `P15 MPR_PROMOTION_COMMITTED`.

M12 is green only when all of the following are true:
1. Promotion eligibility and compatibility checks are explicit and fail-closed.
2. Promotion commit is append-only, deterministic, and evidenced.
3. Rollback drill is executed and recorded with bounded restore objective evidence.
4. ACTIVE bundle resolution is coherent with runtime compatibility contracts.
5. Governance append trail is complete and audit-reconstructable.
6. Deterministic P15 verdict and M13 handoff are emitted.
7. Phase budget envelope and cost-outcome receipt are emitted and blocker-free.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M11.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Entry Contract (Fail-Closed)
M12 cannot execute unless all are true:
1. `M11` is `DONE` in `platform.build_plan.md`.
2. `M11.J` summary is pass:
   - `overall_pass=true`
   - `blocker_count=0`
   - `verdict=ADVANCE_TO_M12`
   - `next_gate=M12_READY`
3. M11 closure artifacts are readable from durable evidence:
   - `m11j_execution_summary.json`
   - `m11_execution_summary.json`
   - `m11_phase_cost_outcome_receipt.json`
4. M11 handoff basis remains readable:
   - `m12_handoff_pack.json` from `m11i_p14_gate_rollup_20260227T094100Z`.

Entry evidence anchors:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11j_execution_summary.json`
2. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11_execution_summary.json`
3. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11j_closure_sync_20260227T104756Z/m11_phase_cost_outcome_receipt.json`
4. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m11i_p14_gate_rollup_20260227T094100Z/m12_handoff_pack.json`

## 3) Scope Boundary for M12
In scope:
1. MPR authority and handle closure.
2. Candidate eligibility and compatibility prechecks.
3. Promotion event commit and learning-registry event publication checks.
4. Rollback drill execution and bounded restore objective evidence.
5. ACTIVE resolution checks against runtime compatibility contracts.
6. Governance append closure for promotion and rollback evidence.
7. Deterministic P15 verdict and M13 handoff.
8. M12 phase budget + cost-outcome closure.

Out of scope:
1. Full-platform final verdict and teardown (`M13`).
2. Additional retraining loops beyond chosen candidate.

## 4) Global M12 Guardrails
1. No local authoritative compute for M12 closure.
2. Managed-first execution path only (GitHub Actions + managed services).
3. Any unresolved required handle blocks execution.
4. Any unreadable required upstream artifact blocks execution.
5. Promotion cannot close without rollback drill evidence.
6. ACTIVE resolution cannot close with hidden compatibility waivers.
7. Cost-control and performance laws are mandatory for every M12 subphase.

## 4.1) Managed Execution Prerequisite
M12 execution requires an authoritative managed lane.

Prerequisite blocker:
1. `M12-B0` if managed M12 workflow lane is not materialized and dispatchable.

Closure expectation for this prerequisite:
1. single managed workflow lane supports `M12.A..M12.J`,
2. deterministic execution-id routing per subphase,
3. no local fallback marked as authoritative.

Closure evidence (green):
1. Workflow file on default branch:
   - `.github/workflows/dev_full_m12_managed.yml`
2. Workflow promotion PR:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/pull/68`
3. Materialization proof run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22485281434`
   - execution id: `m12a_handle_closure_20260227T115823Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M12.A_READY`, `verdict=ADVANCE_TO_M12_A`
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T115823Z/m12_managed_lane_materialization_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T115823Z/m12_subphase_dispatchability_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T115823Z/m12b0_execution_summary.json`

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary subphase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M12.A | no unresolved required P15 handles |
| Candidate eligibility | M12.B | eligibility snapshot pass |
| Compatibility prechecks | M12.C | compatibility precheck snapshot pass |
| Promotion commit | M12.D | promotion receipt + registry event checks pass |
| Rollback drill | M12.E | rollback drill snapshot + bounded restore evidence pass |
| ACTIVE resolution | M12.F | active-resolution snapshot + compatibility checks pass |
| Governance append closure | M12.G | append snapshot + operability acceptance report pass |
| P15 verdict + M13 handoff | M12.H | `ADVANCE_TO_P16` + `m13_handoff_pack.json` |
| Cost-outcome closure | M12.I | budget envelope + cost-outcome receipt pass |
| M12 closure sync | M12.J | `m12_execution_summary.json` pass and parity-verified |

## 4.3) Non-Gate Acceptance Objectives (Mandatory)
M12 cannot close on gate-chain pass alone. All are mandatory:
1. Promotion safety acceptance:
   - blast radius and disable posture explicitly evidenced.
2. Operational trust acceptance:
   - post-promotion observation captures service health, error posture, and drift posture.
3. Rollback realism acceptance:
   - rollback drill demonstrates practical operator recoverability with bounded objective evidence.
4. Governance completeness acceptance:
   - promotion and rollback rationale is append-only and audit-complete.
5. Runtime continuity acceptance:
   - ACTIVE resolution remains coherent with runtime/serving contract.

## 5) Artifact Contract and Path Conventions
M12 artifacts must be emitted locally and durably.

Local run folder:
1. `runs/dev_substrate/dev_full/m12/<execution_id>/...`

Durable run-control mirror:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<execution_id>/...`

Run-scoped learning governance evidence:
1. `MPR_PROMOTION_RECEIPT_PATH_PATTERN = evidence/runs/{platform_run_id}/learning/mpr/promotion_receipt.json`
2. `MPR_ROLLBACK_DRILL_PATH_PATTERN = evidence/runs/{platform_run_id}/learning/mpr/rollback_drill_report.json`

Expected M12 artifacts:
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
12. `m12_post_promotion_observation_snapshot.json`
13. `m12_operability_acceptance_report.json`
14. `m12_execution_summary.json`
15. `m12_blocker_register.json`

## 6) Subphase Execution Contracts

### M12.A - Authority + Handle Closure
Goal:
1. Close required P15 handles before promotion corridor execution.

Entry conditions:
1. M12 entry contract (Section 2) is satisfied.
2. `platform_run_id` and `scenario_run_id` are available from M11 closure summary.

Required handles:
1. `MPR_PROMOTION_RECEIPT_PATH_PATTERN`
2. `MPR_ROLLBACK_DRILL_PATH_PATTERN`
3. `FP_BUS_LEARNING_REGISTRY_EVENTS_V1`
4. `GOV_APPEND_LOG_PATH_PATTERN`
5. `GOV_RUN_CLOSE_MARKER_PATH_PATTERN`
6. `MF_CANDIDATE_BUNDLE_PATH_PATTERN`
7. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
8. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

Blockers:
1. `M12-B1` if required handles unresolved, malformed, or contradictory.

Runtime budget:
1. Target <= 5 minutes.

DoD:
- [x] required handle matrix explicit and complete.
- [x] unresolved handles are blocker-marked.
- [x] `m12a_handle_closure_snapshot.json` committed locally and durably.

Closure evidence (managed):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22485927170`
2. Execution:
   - `m12a_handle_closure_20260227T121911Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.B_READY`,
   - `verdict=ADVANCE_TO_M12_B`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T121911Z/m12a_handle_closure_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T121911Z/m12a_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12a_handle_closure_20260227T121911Z/m12a_execution_summary.json`

### M12.B - Candidate Eligibility Precheck
Goal:
1. Prove candidate bundle is eligible for promotion.

Entry conditions:
1. `M12.A` pass.
2. candidate bundle ref from M11 is readable and run-scoped.

Execution checks:
1. candidate bundle provenance completeness.
2. required M11 evaluation/gating artifacts are readable.
3. run-scope parity (`platform_run_id`, `scenario_run_id`).

Blockers:
1. `M12-B2` on eligibility/provenance/readability failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] eligibility checks pass.
- [x] `m12b_candidate_eligibility_snapshot.json` committed locally and durably.

Closure evidence (managed):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22486311059`
2. Execution:
   - `m12b_candidate_eligibility_20260227T123135Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.C_READY`,
   - `verdict=ADVANCE_TO_M12_C`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12b_candidate_eligibility_20260227T123135Z/m12b_candidate_eligibility_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12b_candidate_eligibility_20260227T123135Z/m12b_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12b_candidate_eligibility_20260227T123135Z/m12b_execution_summary.json`

### M12.C - Compatibility Prechecks
Goal:
1. Fail-closed on compatibility mismatch before promotion.

Entry conditions:
1. `M12.B` pass.

Execution checks:
1. feature/input contract compatibility.
2. policy/degrade compatibility.
3. schema compatibility posture for learning-registry event envelope.

Blockers:
1. `M12-B3` on compatibility failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [x] compatibility prechecks pass.
- [x] `m12c_compatibility_precheck_snapshot.json` committed locally and durably.

Closure evidence (managed):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22487307083`
2. Execution:
   - `m12c_compatibility_precheck_20260227T130306Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.D_READY`,
   - `verdict=ADVANCE_TO_M12_D`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12c_compatibility_precheck_20260227T130306Z/m12c_compatibility_precheck_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12c_compatibility_precheck_20260227T130306Z/m12c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12c_compatibility_precheck_20260227T130306Z/m12c_execution_summary.json`

### M12.D - Promotion Event Commit
Goal:
1. Commit promotion event with append-only semantics.

Entry conditions:
1. `M12.C` pass.

Execution checks:
1. promotion receipt is written to run-scoped MPR path.
2. learning-registry event publication to `FP_BUS_LEARNING_REGISTRY_EVENTS_V1` has broker ACK evidence (`topic`, `partition`, `offset`).
3. consumer-group readback confirms the same event (`registry_event_id` + payload hash match) from broker transport.
4. event payload carries required run/provenance identifiers.

Blockers:
1. `M12-B4` on promotion commit/publish/readback failure.

Runtime budget:
1. Target <= 8 minutes.

DoD:
- [x] promotion receipt exists and is readable.
- [x] broker transport proof is committed and readable (`m12d_broker_transport_proof.json`).
- [x] `m12d_promotion_commit_snapshot.json` committed locally and durably.

Closure evidence (managed, pre-strict-repin run):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22488067476`
2. Execution:
   - `m12d_promotion_commit_20260227T132637Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.E_READY`,
   - `verdict=ADVANCE_TO_M12_E`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T132637Z/m12d_promotion_commit_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T132637Z/m12d_learning_registry_publication_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T132637Z/m12d_execution_summary.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mpr/promotion_receipt.json`
5. Note:
   - this closure run is retained as evidence history, but M12.D is repinned to require broker ACK + consumer readback transport proof before advancing.

Strict closure evidence (managed, post-repin run):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22490894460`
2. Execution:
   - `m12d_promotion_commit_20260227T144832Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.E_READY`,
   - `verdict=ADVANCE_TO_M12_E`.
4. Strict transport proof:
   - `reason=BROKER_ACK_AND_READBACK_PASS`,
   - produced ACK: topic `fp.bus.learning.registry.events.v1`, partition `0`, offset `0`,
   - consumer readback: offset `0`, `payload_hash_match=true`.
5. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T144832Z/m12d_broker_transport_proof.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T144832Z/m12d_learning_registry_publication_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12d_promotion_commit_20260227T144832Z/m12d_execution_summary.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mpr/promotion_receipt.json`

### M12.E - Rollback Drill Execution
Goal:
1. Execute rollback drill for the promoted candidate and prove recoverability.

Entry conditions:
1. `M12.D` pass.

Execution checks:
1. rollback drill completes.
2. rollback drill report is written to run-scoped MPR path.
3. bounded restore objective evidence is emitted.

Blockers:
1. `M12-B5` on rollback drill failure or missing restore evidence.

Runtime budget:
1. Target <= 12 minutes.

DoD:
- [x] rollback drill passes.
- [x] bounded restore objective evidence is present.
- [x] `m12e_rollback_drill_snapshot.json` committed locally and durably.

Closure evidence (2026-02-27):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22495589600`
2. Execution:
   - `m12e_rollback_drill_20260227T165747Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.F_READY`,
   - `verdict=ADVANCE_TO_M12_F`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12e_rollback_drill_20260227T165747Z/m12e_rollback_drill_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12e_rollback_drill_20260227T165747Z/m12e_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12e_rollback_drill_20260227T165747Z/m12e_execution_summary.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mpr/rollback_drill_report.json`
5. Bounded restore objective:
   - all checks pass, including strict transport proof continuity, promotion receipt readability, candidate hash stability, run-scope match, and OFS rollback-recipe/drill readability.

### M12.F - ACTIVE Resolution Checks
Goal:
1. Verify ACTIVE resolution remains deterministic and runtime-compatible.

Entry conditions:
1. `M12.E` pass.

Execution checks:
1. one-active-per-scope resolution.
2. runtime compatibility checks on resolved ACTIVE bundle.
3. post-promotion observation snapshot emitted.

Blockers:
1. `M12-B6` on ACTIVE resolution mismatch or runtime compatibility failure.

Runtime budget:
1. Target <= 8 minutes.

Expanded execution contract:
1. `M12.F.A` entry closure:
- enforce upstream `M12.E` pass from durable run-control summary with `next_gate=M12.F_READY`.
2. `M12.F.B` one-active-per-scope determinism:
- resolve promotion receipt, strict promotion snapshot, rollback drill report, and candidate bundle reference;
- require one candidate reference for one tenant scope (`platform_run_id:scenario_run_id`) with no conflicting resolution.
3. `M12.F.C` runtime compatibility checks:
- candidate serving endpoint/mode must align with `SM_ENDPOINT_NAME` and `SM_SERVING_MODE`;
- registry/schema handles (`FP_BUS_LEARNING_REGISTRY_EVENTS_V1`, `GLUE_SCHEMA_REGISTRY_NAME`, `GLUE_SCHEMA_COMPATIBILITY_MODE`) must be non-placeholder and valid;
- candidate package/model artifact posture must be readable and compatible.
4. `M12.F.D` observation evidence:
- emit `m12_post_promotion_observation_snapshot.json` with check-level pass/fail and source refs.
5. `M12.F.E` closure sync:
- emit `m12f_active_resolution_snapshot.json`, `m12f_blocker_register.json`, and `m12f_execution_summary.json`;
- fail-closed on any mismatch as `M12-B6`.

DoD:
- [x] ACTIVE resolution checks pass.
- [x] `m12_post_promotion_observation_snapshot.json` committed and pass posture.
- [x] `m12f_active_resolution_snapshot.json` committed locally and durably.

Closure evidence (2026-02-27):
1. Run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22497074608`
2. Execution:
   - `m12f_active_resolution_20260227T174035Z`
3. Result:
   - `overall_pass=true`,
   - `blocker_count=0`,
   - `next_gate=M12.G_READY`,
   - `verdict=ADVANCE_TO_M12_G`.
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12f_active_resolution_20260227T174035Z/m12f_active_resolution_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12f_active_resolution_20260227T174035Z/m12_post_promotion_observation_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12f_active_resolution_20260227T174035Z/m12f_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m12f_active_resolution_20260227T174035Z/m12f_execution_summary.json`
5. Active-resolution + compatibility posture:
   - one-active-per-scope deterministic checks pass,
   - serving/topic/schema compatibility checks pass,
   - model artifact readability and run-scope parity checks pass.

### M12.G - Governance Append Closure
Goal:
1. Prove governance append trail is complete and coherent.

Entry conditions:
1. `M12.F` pass.

Execution checks:
1. append ordering and required event set.
2. promotion/rollback evidence refs are present and readable.
3. operability acceptance report is emitted.

Blockers:
1. `M12-B7` on governance append inconsistency or missing mandatory refs.

Runtime budget:
1. Target <= 8 minutes.

Expanded execution contract:
1. `M12.G.A` entry closure:
- enforce upstream `M12.F` pass from durable run-control summary with `next_gate=M12.G_READY`.
2. `M12.G.B` governance append integrity:
- resolve `GOV_APPEND_LOG_PATH_PATTERN` for run scope and validate JSONL readability/parseability;
- enforce append ordering non-decreasing by `ts_utc`, uniqueness by `event_id`, and run-scope consistency.
3. `M12.G.C` required event-set closure:
- ensure governance append includes required M12 event families:
  - promotion committed,
  - rollback drill passed,
  - active resolution confirmed;
- ensure referenced artifacts are readable and stable.
4. `M12.G.D` append-safe publication:
- append required M12 governance events without deleting prior append history;
- verify pre-existing event-id set is preserved after write/readback.
5. `M12.G.E` operability acceptance closure:
- emit `m12_operability_acceptance_report.json` with check-level pass/fail + source refs.
6. `M12.G.F` run-control closure:
- emit `m12g_governance_append_snapshot.json`, `m12g_blocker_register.json`, `m12g_execution_summary.json`;
- fail-closed on any mismatch as `M12-B7`.

DoD:
- [x] governance append checks pass.
- [x] `m12_operability_acceptance_report.json` is published and pass posture.
- [x] `m12g_governance_append_snapshot.json` committed locally and durably.

### M12.H - P15 Gate Rollup + M13 Handoff
Goal:
1. Produce deterministic P15 verdict and M13 handoff.

Entry conditions:
1. `M12.A..M12.G` pass.

Execution checks:
1. fixed-order rollup over subphase outputs A..G.
2. deterministic verdict generation.
3. handoff pack emitted for M13.

Blockers:
1. `M12-B8` on rollup/verdict inconsistency.
2. `M12-B9` on handoff publication failure.

Runtime budget:
1. Target <= 7 minutes.

Expanded execution contract:
1. `M12.H.A` entry closure:
- require `M12.G` pass summary with `next_gate=M12.H_READY`, zero blockers.
2. `M12.H.B` fixed-order rollup:
- load M12 summaries in strict order `A -> B -> C -> D -> E -> F -> G`;
- require each summary to be pass posture with expected `next_gate`:
  - A=`M12.B_READY`,
  - B=`M12.C_READY`,
  - C=`M12.D_READY`,
  - D=`M12.E_READY`,
  - E=`M12.F_READY`,
  - F=`M12.G_READY`,
  - G=`M12.H_READY`.
3. `M12.H.C` deterministic P15 verdict emission:
- emit `m12h_p15_gate_verdict.json` with:
  - `phase_id=P15`,
  - `verdict=ADVANCE_TO_P16` on pass else `HOLD_REMEDIATE`,
  - deterministic fixed-order row set for `A..G`.
4. `M12.H.D` M13 handoff publication:
- emit `m13_handoff_pack.json` with required M13 entry gate contract:
  - required verdict `ADVANCE_TO_P16`,
  - expected next gate `M13_READY`,
  - references to M12.H verdict + M12.G summary.
5. `M12.H.E` run-control closure:
- emit `m12h_blocker_register.json` and `m12h_execution_summary.json`;
- set `next_gate=M12.I_READY` on pass else `HOLD_REMEDIATE`.
6. `M12.H.F` durable publication parity:
- publish all M12.H artifacts to run-control prefix and verify readback/head parity.

DoD:
- [x] `m12h_p15_gate_verdict.json` emitted.
- [x] PASS posture requires `ADVANCE_TO_P16` and `next_gate=M13_READY`.
- [x] `m13_handoff_pack.json` committed locally and durably.

### M12.I - Phase Budget + Cost-Outcome Closure
Goal:
1. Publish M12 cost-to-outcome artifacts.

Entry conditions:
1. `M12.H` pass.

Execution checks:
1. emit `m12_phase_budget_envelope.json`.
2. emit `m12_phase_cost_outcome_receipt.json`.
3. cost artifacts map spend to concrete M12 closure outcomes.

Blockers:
1. `M12-B10` on cost-outcome closure failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] budget and receipt committed locally and durably.
- [ ] artifacts are coherent with emitted outcomes.

### M12.J - M12 Closure Sync
Goal:
1. Close M12 and publish authoritative summary.

Entry conditions:
1. `M12.I` pass.

Execution checks:
1. emit `m12_execution_summary.json`.
2. emit `m12_blocker_register.json`.
3. validate local and durable parity for required M12 outputs.

Blockers:
1. `M12-B11` on summary/evidence publication parity failure.
2. `M12-B12` on non-gate acceptance failure.

Runtime budget:
1. Target <= 6 minutes.

DoD:
- [ ] `m12_execution_summary.json` committed locally and durably.
- [ ] `m12_blocker_register.json` committed locally and durably.
- [ ] M12 closure sync passes with no unresolved blocker.

## 7) Blocker Taxonomy (Fail-Closed)
1. `M12-B0`: managed M12 execution lane not materialized.
2. `M12-B1`: authority/handle closure failure.
3. `M12-B2`: candidate eligibility failure.
4. `M12-B3`: compatibility precheck failure.
5. `M12-B4`: promotion commit failure.
6. `M12-B5`: rollback drill or bounded-restore evidence failure.
7. `M12-B6`: ACTIVE resolution failure.
8. `M12-B7`: governance append closure failure.
9. `M12-B8`: P15 rollup/verdict inconsistency.
10. `M12-B9`: M13 handoff publication failure.
11. `M12-B10`: phase cost-outcome closure failure.
12. `M12-B11`: summary/evidence publication parity failure.
13. `M12-B12`: non-gate acceptance failure.

## 8) Completion Checklist
- [x] `M12.A` complete
- [x] `M12.B` complete
- [x] `M12.C` complete
- [x] `M12.D` complete
- [x] `M12.E` complete
- [x] `M12.F` complete
- [x] `M12.G` complete
- [x] `M12.H` complete
- [ ] `M12.I` complete
- [ ] `M12.J` complete
- [ ] all active `M12-B*` blockers resolved
- [x] non-gate acceptance artifacts (`post_promotion_observation`, `operability_acceptance`) are pass posture

## 9) Planning Status
1. M12 planning is execution-grade and aligned to P15 authority.
2. M11 closure entry requirements are already satisfied.
3. `M12-B0` is closed green (managed lane materialized + dispatchability proven).
4. `M12.A` is complete and green on managed lane with `M12-B1` cleared.
5. `M12.B` is complete and green on managed lane with `M12-B2` cleared.
6. `M12.C` is complete and green on managed lane with `M12-B3` cleared.
7. `M12.D` strict transport-proof rerun is complete and green (`22490894460`, execution `m12d_promotion_commit_20260227T144832Z`) with `M12-B4` cleared.
8. `M12.E` rollback drill execution is complete and green (`22495589600`, execution `m12e_rollback_drill_20260227T165747Z`) with `M12-B5` cleared.
9. `M12.F` ACTIVE resolution checks are complete and green (`22497074608`, execution `m12f_active_resolution_20260227T174035Z`) with `M12-B6` cleared.
10. `M12.G` governance append closure is complete and green (`22497579073`, execution `m12g_governance_append_20260227T175530Z`) with `M12-B7` cleared.
11. `M12.H` P15 gate rollup + M13 handoff is complete and green (`22498398890`, execution `m12h_p15_gate_rollup_20260227T181932Z`) with `M12-B8`/`M12-B9` cleared.
12. Next action: proceed to `M12.I` phase budget + cost-outcome closure.
