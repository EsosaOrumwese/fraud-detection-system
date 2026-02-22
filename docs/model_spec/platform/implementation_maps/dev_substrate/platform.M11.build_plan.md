# Dev Substrate Deep Plan - M11 (F1 Learning/Registry Authority + Runtime Closure)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M11._
_Last updated: 2026-02-22_

## 0) Purpose
M11 closes `F1` by proving Learning/Registry runtime authority is execution-ready on `dev_min` with no local compute dependency and no spine regression risk:
1. Required `OFS/MF/MPR` handles are explicit, concrete, and fail-closed.
2. Managed runtime decomposition (jobs/services/entrypoints) is deterministic and auditable.
3. IAM + secrets + data/messaging ownership boundaries are pinned for safe implementation.
4. Observability/evidence contracts are explicit before runtime build starts.
5. Spine carry-forward non-regression gates (`M8..M10`) are pinned as mandatory.
6. Cost/teardown continuity is preserved for Learning/Registry lanes.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
5. `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
6. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M10.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
3. M10 certification anchors:
   - local: `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
4. `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

## 2) Scope Boundary for M11
In scope:
1. Learning/Registry authority and required-handle closure in `dev_min`.
2. Runtime decomposition and entrypoint closure for:
   - OFS jobs,
   - MF jobs,
   - MPR runtime/control surfaces.
3. IAM/SSM/KMS and identity/authn closure for Learning/Registry lanes.
4. Data store and messaging ownership contracts for F1.
5. Observability/evidence and blocker taxonomy closure for M11 execution.
6. `M8..M10` carry-forward non-regression matrix pin.
7. Cost and teardown continuity posture pin for M11+ runtime lanes.
8. M11 verdict + M12 handoff artifact contract.

Out of scope:
1. OFS dataset build runtime execution (`M12`).
2. MF train/eval/publish runtime execution (`M13`).
3. Integrated full-platform certification runs (`M14`).
4. Production cutover.

## 3) M11 Deliverables
1. `M11.A` authority + M10 handoff closure snapshot.
2. `M11.B` Learning/Registry handle closure matrix snapshot.
3. `M11.C` runtime decomposition + entrypoint matrix snapshot.
4. `M11.D` IAM/secrets/KMS closure snapshot.
5. `M11.E` data-store ownership + path-contract snapshot.
6. `M11.F` messaging + governance/authn corridor closure snapshot.
7. `M11.G` observability/evidence schema + blocker taxonomy snapshot.
8. `M11.H` spine non-regression carry-forward matrix snapshot.
9. `M11.I` cost/teardown continuity snapshot.
10. `M11.J` verdict snapshot (`ADVANCE_TO_M12|HOLD_M11`) + `m12_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. `M10` is closed (`DONE`) with verdict `ADVANCE_CERTIFIED_DEV_MIN`.
2. M10 certification artifacts are readable locally and durably.
3. M11 is activated for planning expansion by explicit user direction.

Execution block:
1. No runtime implementation starts for Learning/Registry lanes until `M11.A..M11.J` planning closure is pass-complete.
2. No `M11` closure is allowed with unresolved handle/IAM/data/messaging ambiguity.
3. No `M11` closure is valid if non-regression matrix for `M8..M10` is missing.

## 4.1) Anti-cram Law (Binding for M11)
1. M11 is not execution-ready unless these lanes are explicit:
   - authority + handoff + required-handle closure,
   - runtime decomposition + entrypoint closure,
   - IAM + secrets + KMS,
   - data stores + ownership boundaries,
   - messaging + governance/authn corridor,
   - observability/evidence + blocker taxonomy,
   - spine non-regression carry-forward,
   - cost + teardown continuity,
   - verdict + handoff contract.
2. If a missing lane is discovered, M11 planning pauses and this file must be expanded before execution.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting owners | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + M10 handoff closure | M11.A | M11.J | handoff gate snapshot (`overall_pass=true`) |
| Required handle closure | M11.B | M11.J | zero unresolved required F1 handles |
| Runtime decomposition + entrypoints | M11.C | M11.J | deterministic OFS/MF/MPR runtime matrix |
| IAM + secrets + KMS closure | M11.D | M11.J | role/secret map with least-privilege checks |
| Data-store ownership closure | M11.E | M11.J | explicit owner map + concrete S3/RDS contract |
| Messaging + governance corridor | M11.F | M11.H | producer/consumer/authn matrix closure |
| Observability + evidence schemas | M11.G | M11.J | snapshot schema + evidence contract closure |
| Spine carry-forward non-regression matrix | M11.H | M11.J | pinned `M8..M10` rerun matrix + acceptance gates |
| Cost + teardown continuity | M11.I | M11.J | learning lane phase-profile + teardown invariants |
| Verdict + M12 handoff | M11.J | - | `ADVANCE_TO_M12` with blocker-free rollup |

## 5) Work Breakdown (Deep)

### M11.A Authority + M10 Handoff Closure
Goal:
1. Validate M10 closure posture and freeze M11 authority references.
2. Ensure M11 planning starts from immutable certified baseline.

Entry conditions:
1. `M10` is `DONE` in `platform.build_plan.md`.
2. M10 verdict is `ADVANCE_CERTIFIED_DEV_MIN`.
3. Source artifacts are readable:
   - local + durable `m10_j_certification_verdict_snapshot.json`.
   - local + durable `m10_certification_bundle_index.json`.

Required inputs:
1. M10 closure artifacts:
   - `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - `runs/dev_substrate/m10/m10_20260222T081047Z/m10_certification_bundle_index.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_certification_bundle_index.json`
2. M11 authority set (Section 1 sources in this file).
3. M11 cross-phase pins from main plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` Section `13.1` and `13.2`.

Preparation checks (fail-closed):
1. Validate source artifact readability:
   - local-preferred read, durable-fallback read for both required M10 artifacts.
2. Validate M10 verdict posture:
   - `verdict=ADVANCE_CERTIFIED_DEV_MIN`
   - `overall_pass=true`
   - blockers empty.
3. Validate source consistency:
   - `platform_run_id` parity across local/durable source artifacts.
   - no conflicting verdict across local/durable artifacts.
4. Validate authority set completeness:
   - every Section 1 source exists and is readable.
   - no unresolved "TBD" authority dependency.

Deterministic closure algorithm (M11.A):
1. Load local M10 verdict artifact; if unreadable load durable artifact; if both fail -> `M11A-B1`.
2. Load local M10 bundle index artifact; if unreadable load durable artifact; if both fail -> `M11A-B1`.
3. Verify verdict posture:
   - mismatch from required M10 close state -> `M11A-B2`.
4. Verify source coherence:
   - run-scope or verdict inconsistency between local/durable -> `M11A-B4`.
5. Resolve and verify M11 authority inputs (Section 1):
   - any missing/unreadable authority -> `M11A-B3`.
6. Build deterministic authority matrix in fixed order:
   - primary authority refs,
   - supporting refs,
   - source artifact refs.
7. Emit `m11_a_authority_handoff_snapshot.json` locally.
8. Publish snapshot durably; publish failure -> `M11A-B5`.

Tasks:
1. Validate M10 verdict, blocker posture, and source readability.
2. Validate M11 authority set completeness (Section 1 docs).
3. Emit `m11_a_authority_handoff_snapshot.json` (local + durable contract).

Required snapshot fields (`m11_a_authority_handoff_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.A"`.
2. `source_m10_verdict_local`, `source_m10_verdict_uri`.
3. `source_m10_bundle_index_local`, `source_m10_bundle_index_uri`.
4. `entry_gate_checks`.
5. `source_consistency_checks`.
6. `authority_refs` (primary + supporting).
7. `authority_readability_matrix`.
8. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.A` planning/closure target budget: <= 10 minutes wall clock.
2. Over-budget without user waiver is blocker state (`M11A-B6`).

DoD:
- [ ] M10 handoff gate is pass-closed and blocker-free.
- [ ] M11 authority list is complete and concrete.
- [ ] M10 local/durable artifact coherence is verified.
- [ ] Snapshot schema for M11.A is pinned.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M11A-B1`: M10 handoff unreadable/invalid.
2. `M11A-B2`: M10 verdict mismatch or blocker residue.
3. `M11A-B3`: M11 authority set incomplete.
4. `M11A-B4`: local/durable source inconsistency.
5. `M11A-B5`: snapshot publication failure.
6. `M11A-B6`: runtime budget breach without waiver.

### M11.B Learning/Registry Handle Closure Matrix
Goal:
1. Close all required F1 handle surfaces before build execution.
2. Eliminate wildcard/placeholder handle usage.

Tasks:
1. Build required-handle set for OFS/MF/MPR lanes from authorities.
2. Resolve each handle from `dev_min_handles.registry.v0.md`.
3. Fail closed on unresolved/wildcard/placeholder required handles.
4. Emit `m11_b_handle_closure_snapshot.json`.

Required closure categories:
1. Runtime identities:
   - learning task/service handles (logical + concrete mapping contract).
2. Data surfaces:
   - archive/features/models/evidence S3 prefixes/patterns.
3. Messaging/authn surfaces:
   - topics/events and auth path/secret references where applicable.
4. Governance surfaces:
   - promotion/rollback actor/audit references.

DoD:
- [ ] Required F1 handle set is explicit and versioned.
- [ ] Required-handle unresolved count is zero.
- [ ] Placeholder/wildcard required-handle count is zero.
- [ ] Snapshot exists with deterministic closure matrix.

Blockers:
1. `M11B-B1`: unresolved required handle.
2. `M11B-B2`: wildcard/placeholder required handle.
3. `M11B-B3`: handle ownership ambiguity across components.

### M11.C Runtime Decomposition + Entrypoint Closure
Goal:
1. Pin exact managed runtime topology for OFS/MF/MPR.
2. Ensure no lane depends on local/laptop execution.

Tasks:
1. Define runtime mode per lane:
   - OFS: ECS run-task.
   - MF: ECS run-task.
   - MPR: ECS service or run-task (explicitly pinned).
2. Map each lane to concrete entrypoint command and container runtime assumptions.
3. Pin desired-count/start-stop posture for any service lane.
4. Emit `m11_c_runtime_decomposition_snapshot.json`.

DoD:
- [ ] Runtime mode is pinned for OFS/MF/MPR with no ambiguity.
- [ ] Entrypoint matrix is complete and runnable in managed substrate.
- [ ] No local runtime path remains in authoritative flow.
- [ ] Snapshot includes deterministic lane-to-entrypoint map.

Blockers:
1. `M11C-B1`: missing/invalid entrypoint for required lane.
2. `M11C-B2`: runtime mode ambiguity (job vs service unresolved).
3. `M11C-B3`: local-runtime dependency detected.

### M11.D IAM + Secrets + KMS Closure
Goal:
1. Pin least-privilege role map and secret materialization for Learning/Registry lanes.
2. Ensure fail-closed secret posture before execution.

Tasks:
1. Pin task-role mapping for OFS/MF/MPR lanes.
2. Pin required SSM paths and secret materialization policy.
3. Validate KMS/encryption posture for secret-bearing surfaces.
4. Emit `m11_d_iam_secret_kms_snapshot.json`.

DoD:
- [ ] Each required lane has exactly one runtime task role.
- [ ] Secret sources/paths are explicit and non-duplicated.
- [ ] Missing required secrets are explicit blockers (fail-closed).
- [ ] Snapshot documents role->surface least-privilege mapping.

Blockers:
1. `M11D-B1`: unresolved runtime role.
2. `M11D-B2`: missing required SSM secret path/materialization rule.
3. `M11D-B3`: privilege overreach or role/surface mismatch.

### M11.E Data-Store Ownership + Path Contracts
Goal:
1. Pin deterministic ownership and path contracts for archive/features/models/registry/evidence.
2. Prevent cross-plane truth collisions.

Tasks:
1. Build owner matrix (`OFS`, `MF`, `MPR`, existing spine components).
2. Pin concrete path patterns and run-scope semantics where required.
3. Pin retention/lifecycle posture references for learning artifacts.
4. Emit `m11_e_data_contract_snapshot.json`.

DoD:
- [ ] Data-store owner matrix has zero overlaps on truth ownership.
- [ ] Path patterns are concrete and non-conflicting.
- [ ] Required run-scope semantics are explicit (`platform_run_id` vs global registry events where applicable).
- [ ] Snapshot captures owner + path + retention contract.

Blockers:
1. `M11E-B1`: ownership overlap/ambiguity.
2. `M11E-B2`: path conflict or unresolved prefix contract.
3. `M11E-B3`: run-scope semantics mismatch.

### M11.F Messaging + Governance/Authn Corridor Closure
Goal:
1. Pin learning-plane messaging interfaces and governance writer-boundary authn requirements.
2. Ensure MPR corridor semantics are explicit and fail-closed.

Tasks:
1. Pin producer/consumer responsibilities for learning/registry events.
2. Pin governance actor and authn requirements for MPR actions.
3. Pin deterministic resolution/promotion/rollback corridor references.
4. Emit `m11_f_messaging_governance_snapshot.json`.

DoD:
- [ ] Messaging ownership matrix is explicit and non-overlapping.
- [ ] Governance action authn/actor requirements are explicit.
- [ ] MPR fail-closed compatibility/resolution expectations are pinned.
- [ ] Snapshot captures corridor contract and acceptance checks.

Blockers:
1. `M11F-B1`: messaging ownership ambiguity.
2. `M11F-B2`: missing governance/authn requirement for MPR actions.
3. `M11F-B3`: unresolved promotion/rollback corridor semantics.

### M11.G Observability/Evidence + Blocker Taxonomy Closure
Goal:
1. Pin required evidence artifacts and schemas for M11 and downstream M12/M13 entry.
2. Pin blocker taxonomy families for deterministic fail-closed adjudication.

Tasks:
1. Define required evidence objects for each M11 sub-phase.
2. Pin minimum snapshot field schema contract.
3. Pin blocker taxonomy (`M11A-B*` .. `M11J-B*`) and rollup rule.
4. Emit `m11_g_observability_evidence_snapshot.json`.

DoD:
- [ ] Required evidence family list is complete and scoped.
- [ ] Snapshot schema contract is explicit and reusable.
- [ ] Blocker taxonomy and rollup contract are pinned.
- [ ] Non-secret evidence policy is explicit.

Blockers:
1. `M11G-B1`: missing required evidence family.
2. `M11G-B2`: snapshot schema incomplete/ambiguous.
3. `M11G-B3`: blocker taxonomy/rollup contract missing.

### M11.H Spine Carry-Forward Non-Regression Matrix
Goal:
1. Convert `M8..M10` carry-forward law into executable acceptance matrix for `M11+`.
2. Prevent false green claims that break certified spine behavior.

Tasks:
1. Pin critical non-regression probes from:
   - `M8` (Obs/Gov closure integrity),
   - `M9` (teardown/cost guardrail enforceability),
   - `M10` (semantic + scale surfaces required for integrated posture).
2. Pin acceptance thresholds and blocker mapping for each probe.
3. Pin rerun policy for non-regression probes during M11+ execution.
4. Emit `m11_h_non_regression_matrix_snapshot.json`.

DoD:
- [ ] Non-regression matrix has explicit probes, thresholds, and owners.
- [ ] Each probe has deterministic evidence source paths.
- [ ] Failure mapping to blockers is explicit and fail-closed.
- [ ] Matrix is approved as mandatory for `M11..M14`.

Blockers:
1. `M11H-B1`: missing critical probe for M8/M9/M10 carry-forward.
2. `M11H-B2`: threshold/acceptance ambiguity.
3. `M11H-B3`: probe evidence source undefined/unreadable.

### M11.I Cost + Teardown Continuity for Learning Lanes
Goal:
1. Keep post-M10 cost discipline intact while adding learning runtime lanes.
2. Ensure learning lanes integrate into existing destroy/guardrail posture.

Tasks:
1. Pin phase-profile start/stop policy for learning services/tasks.
2. Pin teardown scope inclusion for learning demo resources.
3. Pin cost guardrail inclusion requirements for learning lanes.
4. Emit `m11_i_cost_teardown_continuity_snapshot.json`.

DoD:
- [ ] Learning lanes are included in phase-profile control policy.
- [ ] Teardown preserve/destroy matrix includes learning resources.
- [ ] Cross-platform billing guardrail posture remains mandatory.
- [ ] Snapshot captures continuity policy and blocker mapping.

Blockers:
1. `M11I-B1`: learning lane omitted from phase profile controls.
2. `M11I-B2`: teardown inclusion ambiguity for learning resources.
3. `M11I-B3`: cost guardrail continuity gap.

### M11.J Verdict + M12 Handoff
Goal:
1. Aggregate M11 closure outcomes and publish deterministic verdict.
2. Publish M12 handoff pack only when M11 passes fail-closed gates.

Tasks:
1. Build source matrix from `M11.A..M11.I` snapshots.
2. Compute blocker union and verdict:
   - `ADVANCE_TO_M12` when blocker union empty and required predicates true.
   - `HOLD_M11` otherwise.
3. Emit:
   - `m11_j_verdict_snapshot.json`,
   - `m12_handoff_pack.json`.
4. Publish both locally + durably.

DoD:
- [ ] Source matrix includes all M11 sub-phase snapshots.
- [ ] Blocker rollup is deterministic and reproducible.
- [ ] Verdict and handoff artifacts are published locally + durably.
- [ ] `ADVANCE_TO_M12` only when all required predicates are true.

Blockers:
1. `M11J-B1`: missing required source snapshot.
2. `M11J-B2`: source snapshot unreadable/schema-invalid.
3. `M11J-B3`: publication failure for verdict/handoff artifacts.
4. `M11J-B4`: predicate mismatch with attempted advance verdict.

## 6) M11 Runtime Budget Posture (Planning)
Planning target budgets:
1. `M11.A`: <= 10 minutes.
2. `M11.B`: <= 20 minutes.
3. `M11.C`: <= 20 minutes.
4. `M11.D`: <= 20 minutes.
5. `M11.E`: <= 20 minutes.
6. `M11.F`: <= 20 minutes.
7. `M11.G`: <= 15 minutes.
8. `M11.H`: <= 20 minutes.
9. `M11.I`: <= 15 minutes.
10. `M11.J`: <= 10 minutes.

Rule:
1. Over-budget planning execution is blocker state unless explicit user waiver is recorded.

## 7) Required Snapshot Contracts (M11)
Minimum common fields for each M11 sub-phase snapshot:
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id`.
2. `authority_refs`.
3. `entry_gate_checks`.
4. `predicate_checks`.
5. `blockers`.
6. `overall_pass`.
7. `elapsed_seconds`.
8. `created_utc`.

M11 verdict snapshot (`m11_j_verdict_snapshot.json`) additional required fields:
1. `source_phase_matrix` (`M11.A..M11.I` -> pass/blockers refs).
2. `source_blocker_rollup`.
3. `verdict`.
4. `m12_handoff_ref_local`.
5. `m12_handoff_ref_uri`.

## 8) M11 DoD (Phase-Level)
- [ ] `M11.A..M11.I` are planned and executed with blocker-free closure snapshots.
- [ ] Required handles for Learning/Registry are fully closed and concrete.
- [ ] Runtime/IAM/data/messaging/evidence/cost lanes are explicit and non-ambiguous.
- [ ] `M8..M10` non-regression matrix is pinned with executable acceptance rules.
- [ ] `M11.J` publishes `ADVANCE_TO_M12` verdict and `m12_handoff_pack.json` locally + durably.

## 9) Planning Status
1. This file is now expanded to execution-grade planning depth.
2. No runtime infrastructure change or execution is performed by this planning update.
3. Status transitions remain governed only by `platform.build_plan.md`.
