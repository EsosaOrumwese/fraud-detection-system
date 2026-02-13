# Dev Substrate Deep Plan - M4 (P2 Daemons Ready)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M4._
_Last updated: 2026-02-13_

## 0) Purpose
M4 activates the Spine Green v0 daemon packs on managed compute (ECS), enforces run-scope discipline from M3, validates health/stability and dependency reachability, and publishes durable readiness evidence used to enter M5.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P2 section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md`
2. `runs/dev_substrate/m3/20260213T221631Z/m4_handoff_pack.json`
3. `runs/dev_substrate/m3/20260213T221631Z/m3_f_verdict_snapshot.json`
4. `runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M4
In scope:
1. P2 daemon/service bring-up for Spine Green v0 packs only:
   - `control_ingress`
   - `rtdl_core`
   - `rtdl_decision_lane`
   - `case_labels`
   - `obs_gov` (daemonized parts only)
2. Run-scope enforcement (`REQUIRED_PLATFORM_RUN_ID`) for all in-scope daemons.
3. Deterministic singleton policy (1 replica per daemon/service for v0).
4. Dependency readiness checks (Kafka/S3/DB/logging reachability) and crashloop detection.
5. Duplicate-consumer guard and no-parallel once-off consumer discipline.
6. Durable readiness evidence publication and M5 handoff package.

Out of scope:
1. Oracle seed/sort/checker execution (`M5`).
2. P4-P11 domain-phase execution.
3. Any learning/registry lanes (out of Spine Green v0 baseline).

## 3) M4 Deliverables
1. M4 handle closure matrix for P2 run-time bring-up.
2. Daemon/service pack map with singleton replica contract.
3. Run-scope launch contract (`REQUIRED_PLATFORM_RUN_ID`) across in-scope services.
4. Daemon readiness snapshot:
   - run-scoped:
     - `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
5. M4 control-plane artifacts:
   - `m4_d_dependency_snapshot.json`
   - `m4_e_launch_contract_snapshot.json`
   - `m4_f_daemon_start_snapshot.json`
   - `m4_g_consumer_uniqueness_snapshot.json`
   - `m4_i_verdict_snapshot.json`
   - `m5_handoff_pack.json`
6. Deterministic M4 verdict:
   - `ADVANCE_TO_M5` or `HOLD_M4`.

## 4) Execution Gate for This Phase
Current posture:
1. M4 is active for deep planning and sequential execution preparation.

Execution block:
1. No M5 execution is allowed before M4 verdict is `ADVANCE_TO_M5`.
2. No daemon start is allowed without run-scope injection from M3 artifacts.
3. No defaulting/improvised service identity values are allowed when required handles are unresolved.

## 4.1) Anti-Cram Law (Binding for M4)
1. M4 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - service/pack mapping
   - identity/IAM
   - network/dependency reachability
   - run-scope launch contract
   - duplicate-consumer guard
   - observability/evidence
   - rollback/retry
2. Sub-phase count is not fixed; this file expands until closure-grade coverage is achieved.
3. Any newly discovered hole blocks progression and must be added to this plan before execution continues.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles closure | M4.A | M4.I | no unresolved required P2 handles |
| Pack/service singleton map | M4.B | M4.F | service map with desired/running singleton expectations |
| Identity/IAM binding | M4.C | M4.F | role/task/service binding snapshot pass |
| Network + dependency reachability | M4.D | M4.F | dependency snapshot pass (Kafka/S3/DB/logs reachable) |
| Run-scope launch contract | M4.E | M4.F | launch contract shows `REQUIRED_PLATFORM_RUN_ID` enforcement |
| Bring-up + stabilization | M4.F | M4.G | daemon start snapshot with health and crashloop checks |
| Duplicate-consumer guard | M4.G | M4.I | uniqueness snapshot pass with no lane conflicts |
| Readiness evidence publication | M4.H | M4.I | durable `operate/daemons_ready.json` exists |
| Verdict + M5 handoff | M4.I / M4.J | - | `ADVANCE_TO_M5` and `m5_handoff_pack.json` durable |

## 5) Work Breakdown (Deep)

## M4 Decision Pins (Closed Before Execution)
1. Managed-compute law:
   - all in-scope daemons/services run on ECS only; no laptop runtime execution.
2. Spine-only law:
   - only in-scope Spine Green v0 packs are started.
3. Run-scope law:
   - all daemons must enforce `REQUIRED_PLATFORM_RUN_ID=<platform_run_id>`.
4. Singleton law:
   - v0 desired/running count target is `1` per in-scope daemon/service.
5. No-duplicate-consumer law:
   - no parallel once-off/manual consumers for a lane with daemon consumers active.
6. Evidence-first law:
   - M4 PASS requires durable daemon readiness evidence and verdict snapshot.
7. Fail-closed law:
   - any blocker at any sub-phase holds M4 (`HOLD_M4`).

## 5.1) Sequential Closure Chain (A->J)
1. `M4.A` closes handle and handoff authority surfaces.
2. `M4.B` converts handles into executable service/pack singleton map.
3. `M4.C` proves mapped services have valid execution identities and access posture.
4. `M4.D` proves substrate reachability for mapped services.
5. `M4.E` builds deterministic launch contract with run-scope injection.
6. `M4.F` executes bring-up and stabilization against the launch contract.
7. `M4.G` validates consumer uniqueness and singleton continuity.
8. `M4.H` publishes canonical run-scoped daemon-readiness evidence.
9. `M4.I` computes deterministic verdict using A-H predicates.
10. `M4.J` publishes handoff artifact for M5 entry.

### M4.A Authority + Handle Closure (P2)
Goal:
1. Close all required P2 handles and M3->M4 handoff anchors before any service action.

Entry conditions:
1. `platform.build_plan.md` keeps M4 as `ACTIVE`.
2. M3 verdict artifact is present and indicates `ADVANCE_TO_M4`.

Inputs:
1. `runs/dev_substrate/m3/20260213T221631Z/m3_f_verdict_snapshot.json`
2. `runs/dev_substrate/m3/20260213T221631Z/m4_handoff_pack.json`
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P2 required surfaces)

Execution sequence:
1. Validate M3 handoff preconditions:
   - `m3_f_verdict_snapshot.json` must be `ADVANCE_TO_M4`.
   - `m4_handoff_pack.json` must exist and be non-secret.
2. Build required-handle matrix by lane:
   - run-scope: `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`, `ACTIVE_RUN_ID_SOURCE`
   - ECS identity surfaces: `ECS_CLUSTER_NAME`, `SVC_*`, `TD_*`
   - dependency handles: S3, Kafka, DB
   - network/logging handles: subnets/SG/log group.
3. Classify each required handle as `resolved` or `blocker`; no implied defaults allowed.
4. Emit closure snapshot and matrix artifacts.

Evidence artifacts:
1. `m4_a_handle_closure_snapshot.json`
2. `m4_a_handle_closure_matrix.json`

DoD:
- [ ] M3 handoff preconditions verified.
- [ ] Required P2 handle set resolved or explicitly blocker-marked.
- [ ] M4.A closure artifacts exist locally and durably.

Blockers:
1. `M4A-B1`: M3 verdict/handoff precondition missing.
2. `M4A-B2`: required P2 handles unresolved for execution.
3. `M4A-B3`: M4.A artifact write/upload failure.

Handoff rule:
1. `M4.B` starts only if `M4A-B*` blockers are empty.

### M4.B Service/Pack Map + Singleton Contract
Goal:
1. Pin executable service/pack map and singleton policy for daemon bring-up.

Entry conditions:
1. M4.A closure snapshot is present with zero unresolved required handles.

Inputs:
1. `m4_a_handle_closure_snapshot.json`
2. P2 in-scope pack definitions from runbook.
3. Handle registry service/task-definition keys.

Execution sequence:
1. Build service map for in-scope packs:
   - `control_ingress`: `SVC_IG`
   - `rtdl_core`: `SVC_RTDL_CORE_ARCHIVE_WRITER`, `SVC_RTDL_CORE_IEG`, `SVC_RTDL_CORE_OFP`, `SVC_RTDL_CORE_CSFB` (if separate)
   - `rtdl_decision_lane`: `SVC_DECISION_LANE_DL`, `SVC_DECISION_LANE_DF`, `SVC_DECISION_LANE_AL`, `SVC_DECISION_LANE_DLA`
   - `case_labels`: `SVC_CASE_TRIGGER`, `SVC_CM`, `SVC_LS`
   - `obs_gov`: `SVC_ENV_CONFORMANCE` (if daemonized for this run).
2. Pin singleton policy:
   - `desired_count=1` for every daemonized service in this phase.
3. Record startup ordering plan per pack to reduce coupled failure blast radius.
4. Publish service-map artifacts.

Evidence artifacts:
1. `m4_b_service_map_snapshot.json`
2. `m4_b_singleton_contract.json`

DoD:
- [ ] M4 pack/service map is explicit and complete for in-scope packs.
- [ ] Singleton `desired_count` policy is pinned for each started service.
- [ ] M4.B artifacts exist locally and durably.

Blockers:
1. `M4B-B1`: service map incomplete for in-scope packs.
2. `M4B-B2`: singleton policy unresolved.
3. `M4B-B3`: M4.B artifact write/upload failure.

Handoff rule:
1. `M4.C` starts only if every in-scope daemon has a mapped ECS service identity.

### M4.C Identity/IAM Binding Validation
Goal:
1. Validate role/task/service execution identities required to start daemons.

Entry conditions:
1. M4.B service map is complete and stable.

Inputs:
1. `m4_b_service_map_snapshot.json`
2. Runtime role and policy handles from registry.

Execution sequence:
1. Verify each mapped service has valid task execution role and app role binding.
2. Validate minimum access posture by daemon class:
   - SSM read for runtime secrets,
   - Kafka credentials retrieval path,
   - S3 read/write to required prefixes,
   - DB connectivity for DB-requiring services.
3. Mark least-privilege drift findings as blockers for this phase.
4. Publish IAM binding snapshot.

Evidence artifacts:
1. `m4_c_iam_binding_snapshot.json`
2. `m4_c_iam_gap_register.json` (empty when pass)

DoD:
- [ ] IAM execution identities for all mapped services are validated.
- [ ] Missing/invalid role bindings are blocker-marked.
- [ ] M4.C artifacts exist locally and durably.

Blockers:
1. `M4C-B1`: required role binding missing/invalid.
2. `M4C-B2`: dependency access policy gap identified.
3. `M4C-B3`: M4.C artifact write/upload failure.

Handoff rule:
1. `M4.D` starts only when IAM gap register is empty.

### M4.D Network + Dependency Reachability Validation
Goal:
1. Validate daemon runtime can reach required substrates before bring-up.

Entry conditions:
1. M4.C passed with no unresolved IAM blockers.

Inputs:
1. `m4_b_service_map_snapshot.json`
2. VPC/subnet/SG handles.
3. Dependency endpoints and identifiers (Kafka/S3/DB/logging).

Execution sequence:
1. Build dependency matrix keyed by service:
   - Kafka bootstrap endpoint
   - S3 buckets/prefixes
   - runtime DB endpoint
   - CloudWatch log-group write surface.
2. Validate runtime network posture aligns with pinned dev-min topology.
3. Execute reachability checks by dependency class and record pass/fail per service.
4. Publish dependency snapshot.

Evidence artifacts:
1. `m4_d_dependency_snapshot.json`
2. `m4_d_dependency_matrix.json`

DoD:
- [ ] Dependency reachability checks pass for mapped services.
- [ ] Any unreachable dependency is blocker-marked.
- [ ] M4.D artifacts exist locally and durably.

Blockers:
1. `M4D-B1`: dependency reachability failure.
2. `M4D-B2`: network posture mismatch vs expected runtime lane.
3. `M4D-B3`: M4.D artifact write/upload failure.

Handoff rule:
1. `M4.E` starts only with zero unresolved reachability blockers.

### M4.E Launch Contract + Run-Scope Injection
Goal:
1. Produce deterministic launch contract enforcing run-scope for all services.

Entry conditions:
1. M4.D dependency checks are green.

Inputs:
1. `platform_run_id` from M3.
2. `m4_b_service_map_snapshot.json`
3. `m4_d_dependency_snapshot.json`
4. image provenance anchors from M1/M3 artifacts.

Execution sequence:
1. Build launch contract for each mapped service with:
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` and M3 run-id value,
   - dependency env/secret references by handle,
   - image provenance references.
2. Validate run-scope key/value equality across all services.
3. Validate contract is non-secret.
4. Publish launch-contract snapshot.

Evidence artifacts:
1. `m4_e_launch_contract_snapshot.json`
2. `m4_e_launch_contract_services.json`

DoD:
- [ ] Launch contract includes run-scope env mapping for all mapped services.
- [ ] Run-scope value equals M3 `platform_run_id` for all services.
- [ ] M4.E artifacts exist locally and durably.

Blockers:
1. `M4E-B1`: run-scope env key/value missing or mismatched.
2. `M4E-B2`: launch contract missing required service entries.
3. `M4E-B3`: secret leakage detected in launch-contract artifacts.
4. `M4E-B4`: M4.E artifact write/upload failure.

Handoff rule:
1. `M4.F` starts only when every mapped daemon has explicit run-scope injection.

### M4.F Daemon Bring-up + Stabilization
Goal:
1. Start mapped ECS services and validate stable singleton running posture.

Entry conditions:
1. M4.E launch contract is complete and non-secret.

Inputs:
1. `m4_e_launch_contract_snapshot.json`
2. `m4_b_singleton_contract.json`

Execution sequence:
1. Execute service start/update choreography by pack order:
   - ingress first,
   - then rtdl core and decision lanes,
   - then case/labels,
   - then obs_gov daemonized parts.
2. Wait for service stabilization windows and collect:
   - desired/running counts,
   - task ARNs,
   - health/log status.
3. Validate no crashloops and no run-scope mismatch signal in logs/events.
4. Publish daemon-start snapshot.

Evidence artifacts:
1. `m4_f_daemon_start_snapshot.json`
2. `m4_f_service_health_rollup.json`

DoD:
- [ ] All mapped services reach expected singleton running posture.
- [ ] Crashloop-free stabilization checks pass.
- [ ] M4.F artifacts exist locally and durably.

Blockers:
1. `M4F-B1`: service start/update failure.
2. `M4F-B2`: service fails stabilization (desired/running mismatch).
3. `M4F-B3`: crashloop or unhealthy state detected.
4. `M4F-B4`: M4.F artifact write/upload failure.

Handoff rule:
1. `M4.G` starts only when all mapped services stabilize to singleton.

### M4.G Duplicate-Consumer Guard + Singleton Enforcement
Goal:
1. Ensure consumer uniqueness and no conflicting lane consumers.

Entry conditions:
1. M4.F stabilization pass is complete.

Inputs:
1. `m4_f_daemon_start_snapshot.json`
2. lane-to-consumer ownership surfaces from runbook.

Execution sequence:
1. Check for duplicate/manual once-off consumer interference in in-scope lanes.
2. Validate singleton running posture remains stable after guard interval.
3. Record any cross-lane or parallel consumer conflict.
4. Publish consumer-uniqueness snapshot.

Evidence artifacts:
1. `m4_g_consumer_uniqueness_snapshot.json`
2. `m4_g_lane_consumer_map.json`

DoD:
- [ ] No duplicate consumer conflict exists for in-scope lanes.
- [ ] Singleton posture remains stable.
- [ ] M4.G artifacts exist locally and durably.

Blockers:
1. `M4G-B1`: duplicate consumer conflict detected.
2. `M4G-B2`: singleton posture drift after stabilization.
3. `M4G-B3`: M4.G artifact write/upload failure.

Handoff rule:
1. `M4.H` starts only when uniqueness snapshot reports no conflicts.

### M4.H Daemon Readiness Evidence Publication
Goal:
1. Publish canonical run-scoped P2 readiness evidence.

Entry conditions:
1. M4.F and M4.G passed with no unresolved blockers.

Inputs:
1. `m4_f_daemon_start_snapshot.json`
2. `m4_g_consumer_uniqueness_snapshot.json`
3. M3 `platform_run_id`.

Execution sequence:
1. Build readiness artifact `evidence/runs/<platform_run_id>/operate/daemons_ready.json` with:
   - pack IDs,
   - service names and task ARNs,
   - desired/running counts,
   - run-scope key/value used,
   - publication timestamp.
2. Publish local mirror and durable run-scoped object.
3. Publish publication snapshot.

Evidence artifacts:
1. `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
2. `m4_h_readiness_publication_snapshot.json`

DoD:
- [ ] `operate/daemons_ready.json` exists and is complete.
- [ ] Run-scoped durable evidence publication passes.
- [ ] M4.H artifacts exist locally and durably.

Blockers:
1. `M4H-B1`: readiness artifact missing required fields.
2. `M4H-B2`: durable run-scoped publication failure.
3. `M4H-B3`: M4.H artifact write/upload failure.

Handoff rule:
1. `M4.I` starts only after durable run-scoped readiness evidence is confirmed.

### M4.I Pass Gates + Blocker Rollup + Verdict
Goal:
1. Compute deterministic M4 verdict from explicit gate predicates.

Entry conditions:
1. Sub-phases M4.A through M4.H have published snapshots.

Inputs:
1. `m4_a_handle_closure_snapshot.json`
2. `m4_b_service_map_snapshot.json`
3. `m4_c_iam_binding_snapshot.json`
4. `m4_d_dependency_snapshot.json`
5. `m4_e_launch_contract_snapshot.json`
6. `m4_f_daemon_start_snapshot.json`
7. `m4_g_consumer_uniqueness_snapshot.json`
8. `m4_h_readiness_publication_snapshot.json`

Execution sequence:
1. Evaluate gate predicates:
   - `handles_closed`
   - `service_map_complete`
   - `iam_binding_valid`
   - `dependencies_reachable`
   - `run_scope_enforced`
   - `services_stable`
   - `no_duplicate_consumers`
   - `readiness_evidence_durable`.
2. Roll up blockers from M4.A..M4.H.
3. Compute verdict:
   - all predicates true and blockers empty => `ADVANCE_TO_M5`
   - otherwise => `HOLD_M4`.
4. Publish verdict snapshot.

Evidence artifacts:
1. `m4_i_verdict_snapshot.json`
2. `m4_i_gate_predicates_snapshot.json`

DoD:
- [ ] M4 gate predicates are explicit and reproducible.
- [ ] Blocker rollup is complete and fail-closed.
- [ ] M4.I artifacts exist locally and durably.

Blockers:
1. `M4I-B1`: missing/unreadable prerequisite snapshot from A-H lanes.
2. `M4I-B2`: predicate evaluation incomplete/invalid.
3. `M4I-B3`: blocker rollup non-empty.
4. `M4I-B4`: M4.I artifact write/upload failure.

Handoff rule:
1. `M4.J` starts only when verdict is `ADVANCE_TO_M5`.

### M4.J M5 Handoff Artifact Publication
Goal:
1. Publish canonical handoff surface for M5 entry.

Entry conditions:
1. M4.I verdict is `ADVANCE_TO_M5`.

Inputs:
1. `m4_i_verdict_snapshot.json`
2. `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
3. service map and launch contract snapshots.

Execution sequence:
1. Build `m5_handoff_pack.json` with:
   - `platform_run_id`
   - M4 verdict
   - readiness evidence URI
   - runtime service map snapshot URI
   - source execution IDs (`m3*`, `m4*`).
2. Validate non-secret contract.
3. Publish local + durable handoff artifact.

Evidence artifacts:
1. `m5_handoff_pack.json`
2. `m4_j_handoff_publication_snapshot.json`

DoD:
- [ ] `m5_handoff_pack.json` is complete and non-secret.
- [ ] Durable handoff publication passes.
- [ ] URI references are captured for M5 entry.

Blockers:
1. `M4J-B1`: M4 verdict is not `ADVANCE_TO_M5`.
2. `M4J-B2`: handoff pack missing required fields/URIs.
3. `M4J-B3`: non-secret policy violation in handoff artifact.
4. `M4J-B4`: M4.J artifact write/upload failure.

## 6) M4 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M4 control-plane evidence root:
   - `evidence/dev_min/run_control/<m4_execution_id>/`
3. `<m4_execution_id>` format:
   - `m4_<YYYYMMDDTHHmmssZ>`

Minimum M4 evidence payloads:
1. `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
2. `evidence/dev_min/run_control/<m4_execution_id>/m4_a_handle_closure_snapshot.json`
3. `evidence/dev_min/run_control/<m4_execution_id>/m4_a_handle_closure_matrix.json`
4. `evidence/dev_min/run_control/<m4_execution_id>/m4_b_service_map_snapshot.json`
5. `evidence/dev_min/run_control/<m4_execution_id>/m4_b_singleton_contract.json`
6. `evidence/dev_min/run_control/<m4_execution_id>/m4_c_iam_binding_snapshot.json`
7. `evidence/dev_min/run_control/<m4_execution_id>/m4_c_iam_gap_register.json`
8. `evidence/dev_min/run_control/<m4_execution_id>/m4_d_dependency_snapshot.json`
9. `evidence/dev_min/run_control/<m4_execution_id>/m4_d_dependency_matrix.json`
10. `evidence/dev_min/run_control/<m4_execution_id>/m4_e_launch_contract_snapshot.json`
11. `evidence/dev_min/run_control/<m4_execution_id>/m4_e_launch_contract_services.json`
12. `evidence/dev_min/run_control/<m4_execution_id>/m4_f_daemon_start_snapshot.json`
13. `evidence/dev_min/run_control/<m4_execution_id>/m4_f_service_health_rollup.json`
14. `evidence/dev_min/run_control/<m4_execution_id>/m4_g_consumer_uniqueness_snapshot.json`
15. `evidence/dev_min/run_control/<m4_execution_id>/m4_g_lane_consumer_map.json`
16. `evidence/dev_min/run_control/<m4_execution_id>/m4_h_readiness_publication_snapshot.json`
17. `evidence/dev_min/run_control/<m4_execution_id>/m4_i_verdict_snapshot.json`
18. `evidence/dev_min/run_control/<m4_execution_id>/m4_i_gate_predicates_snapshot.json`
19. `evidence/dev_min/run_control/<m4_execution_id>/m5_handoff_pack.json`
20. `evidence/dev_min/run_control/<m4_execution_id>/m4_j_handoff_publication_snapshot.json`
21. local mirrors under:
   - `runs/dev_substrate/m4/<timestamp>/...`

Notes:
1. M4 artifacts must be non-secret.
2. Any secret-bearing payload in M4 artifacts is a hard blocker.
3. M4 readiness evidence must preserve P2 semantics from runbook (packs running, run-scope enforcement, no duplicate consumers).

## 7) M4 Completion Checklist
- [ ] M4.A complete
- [ ] M4.B complete
- [ ] M4.C complete
- [ ] M4.D complete
- [ ] M4.E complete
- [ ] M4.F complete
- [ ] M4.G complete
- [ ] M4.H complete
- [ ] M4.I complete
- [ ] M4.J complete

## 8) Risks and Controls
R1: Services start with wrong run scope.  
Control: launch-contract run-scope validation + fail-closed mismatch block.

R2: Duplicate consumers introduce offset drift or duplicate effects.  
Control: explicit uniqueness guard and singleton enforcement.

R3: Hidden dependency failure causes late-phase crashes.  
Control: pre-bring-up dependency snapshot + crashloop stabilization gate.

R4: Readiness claimed without durable evidence.  
Control: mandatory run-scoped `operate/daemons_ready.json` and control-plane snapshots.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M4 Execution)
Current blockers:
1. None.

Resolved blockers:
1. None yet.

Rule:
1. Any newly discovered blocker is appended here with closure criteria.
2. If this register is non-empty, M4 execution remains blocked.

## 9) Exit Criteria
M4 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M4 evidence contract artifacts are produced and verified.
3. Main plan M4 DoD checklist is complete.
4. M4 verdict is `ADVANCE_TO_M5`.
5. USER confirms progression to M5 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
