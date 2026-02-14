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
   - `obs_gov` (environment conformance daemon only; reporter remains P11 task)
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

### M4.A Authority + Handle Closure (P2)
Goal:
1. Close all required P2 handles and M3->M4 handoff anchors before service actions.

Tasks:
1. Validate M3 verdict and handoff preconditions:
   - `m3_f_verdict_snapshot.json` must be `ADVANCE_TO_M4`.
   - `m4_handoff_pack.json` must exist and be non-secret.
2. Resolve required run-scope and runtime handles (no wildcards allowed in closure result):
   - run-scope:
     - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
     - `ACTIVE_RUN_ID_SOURCE`
   - ECS/network/logging:
     - `ECS_CLUSTER_NAME`
     - `VPC_ID`
     - `SUBNET_IDS_PUBLIC`
     - `SECURITY_GROUP_ID_APP`
     - `CLOUDWATCH_LOG_GROUP_PREFIX`
   - in-scope daemon service identities:
     - `SVC_IG`
     - `SVC_RTDL_CORE_ARCHIVE_WRITER`
     - `SVC_RTDL_CORE_IEG`
     - `SVC_RTDL_CORE_OFP`
     - `SVC_RTDL_CORE_CSFB`
     - `SVC_DECISION_LANE_DL`
     - `SVC_DECISION_LANE_DF`
     - `SVC_DECISION_LANE_AL`
     - `SVC_DECISION_LANE_DLA`
     - `SVC_CASE_TRIGGER`
     - `SVC_CM`
     - `SVC_LS`
     - `SVC_ENV_CONFORMANCE`
   - substrate dependency handles:
     - `S3_ORACLE_BUCKET`
     - `S3_ARCHIVE_BUCKET`
     - `S3_QUARANTINE_BUCKET`
     - `S3_EVIDENCE_BUCKET`
     - `SSM_CONFLUENT_BOOTSTRAP_PATH`
     - `SSM_CONFLUENT_API_KEY_PATH`
     - `SSM_CONFLUENT_API_SECRET_PATH`
     - `FP_BUS_CONTROL_V1`
     - `FP_BUS_TRAFFIC_FRAUD_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
     - `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
     - `FP_BUS_RTDL_V1`
     - `FP_BUS_AUDIT_V1`
     - `FP_BUS_CASE_TRIGGERS_V1`
     - `FP_BUS_LABELS_EVENTS_V1`
     - `RDS_ENDPOINT`
     - `DB_NAME`
3. Verify each required handle resolves to a concrete value with a single source-of-truth origin:
   - handles registry key
   - materialization origin (`terraform_output` or `ssm_parameter`)
   - secret classification (`secret` or `non_secret`)
4. Emit closure snapshot with unresolved handle list (must be empty before M4.B):
   - `m4_execution_id`
   - `platform_run_id`
   - `required_handle_keys`
   - `resolved_handle_count`
   - `unresolved_handle_count`
   - `unresolved_handle_keys`
   - `wildcard_key_present` (must be `false`)
   - `m3_verdict`
   - `m3_handoff_uri`
5. Enforce fail-closed: if unresolved handles exist, stop M4 progression at `M4.A`.

DoD:
- [x] M3 handoff preconditions verified.
- [x] Required P2 handle set resolved with zero wildcard keys.
- [x] `unresolved_handle_count == 0` for execution progression.
- [x] M4.A closure snapshot exists locally and durably.

Blockers:
1. `M4A-B1`: M3 verdict/handoff precondition missing.
2. `M4A-B2`: required P2 handles unresolved for execution.
3. `M4A-B3`: M4.A closure snapshot write/upload failure.
4. `M4A-B4`: wildcard/ambiguous handle references detected in closure set.

### M4.B Service/Pack Map + Singleton Contract
Goal:
1. Pin executable service/pack map and singleton policy for bring-up.

Entry conditions:
1. `M4.A` snapshot exists and is PASS:
   - `runs/dev_substrate/m4/20260214T121004Z/m4_a_handle_closure_snapshot.json`
   - `overall_pass=true`, `unresolved_handle_count=0`, `wildcard_key_present=false`.
2. `platform_run_id` for mapping scope is inherited from `M4.A` (no reminting at M4.B).

Required inputs:
1. `M4.A` closure snapshot (handle/value/source map).
2. P2 in-scope pack contract from runbook and main plan:
   - `control_ingress`, `rtdl_core`, `rtdl_decision_lane`, `case_labels`, `obs_gov`.
3. Handles registry service-key set:
   - `SVC_IG`
   - `SVC_RTDL_CORE_ARCHIVE_WRITER`, `SVC_RTDL_CORE_IEG`, `SVC_RTDL_CORE_OFP`, `SVC_RTDL_CORE_CSFB`
   - `SVC_DECISION_LANE_DL`, `SVC_DECISION_LANE_DF`, `SVC_DECISION_LANE_AL`, `SVC_DECISION_LANE_DLA`
   - `SVC_CASE_TRIGGER`, `SVC_CM`, `SVC_LS`
   - `SVC_ENV_CONFORMANCE`

Tasks:
1. Build canonical `pack -> service-handle -> concrete service-name` mapping for exactly five in-scope packs:
   - `control_ingress`: `SVC_IG`
   - `rtdl_core`: `SVC_RTDL_CORE_ARCHIVE_WRITER`, `SVC_RTDL_CORE_IEG`, `SVC_RTDL_CORE_OFP`, `SVC_RTDL_CORE_CSFB`
   - `rtdl_decision_lane`: `SVC_DECISION_LANE_DL`, `SVC_DECISION_LANE_DF`, `SVC_DECISION_LANE_AL`, `SVC_DECISION_LANE_DLA`
   - `case_labels`: `SVC_CASE_TRIGGER`, `SVC_CM`, `SVC_LS`
   - `obs_gov`: `SVC_ENV_CONFORMANCE`
2. Record concrete-name authority for each mapped service:
   - `service_handle`
   - `service_name`
   - `source` (artifact/registry reference)
   - `materialization_origin`
3. Pin singleton contract for every mapped service:
   - `desired_count=1`
   - `replica_policy=v0_singleton_deterministic`
4. Pin M4.B exclusions explicitly:
   - exclude one-shot task handles (`TD_*`) from daemon service map,
   - exclude reporter daemonization for P2 (`TD_REPORTER` remains P11 one-shot path).
5. Emit `m4_b_service_map_snapshot.json` locally and durably.

DoD:
- [x] M4 pack/service map contains exactly five in-scope packs and no out-of-scope packs.
- [x] All required service handles have concrete service-name bindings and source provenance.
- [x] Singleton desired_count policy (`1`) is pinned for each mapped service.
- [x] Exclusions (`TD_*`, reporter in P2) are explicit in artifact.
- [x] `m4_b_service_map_snapshot.json` exists locally and durably.

Blockers:
1. `M4B-B1`: service map incomplete or contains pack/service drift vs P2 in-scope contract.
2. `M4B-B2`: singleton policy unresolved for any mapped service.
3. `M4B-B3`: service-map artifact write/upload failure.
4. `M4B-B4`: service-handle source ambiguity (multiple concrete names for one handle without pinned precedence).
5. `M4B-B5`: forbidden inclusion detected (`TD_*` daemonization or reporter included in P2 map).

### M4.C Identity/IAM Binding Validation
Goal:
1. Validate role/task/service execution identities required to start daemons.

Tasks:
1. Verify ECS task execution/app roles exist and are attachable for mapped services.
2. Validate minimum access posture for dependencies:
   - SSM read for runtime secrets,
   - Kafka credentials retrieval path,
   - S3 read/write to required prefixes,
   - DB connectivity for DB-requiring services.
3. Publish IAM binding snapshot.

DoD:
- [ ] IAM execution identities for all mapped services are validated.
- [ ] Missing/invalid role bindings are blocker-marked.
- [ ] M4.C IAM snapshot exists locally and durably.

Blockers:
1. `M4C-B1`: required role binding missing/invalid.
2. `M4C-B2`: dependency access policy gap identified.
3. `M4C-B3`: IAM snapshot write/upload failure.

### M4.D Network + Dependency Reachability Validation
Goal:
1. Validate daemon runtime can reach required substrates before bring-up.

Tasks:
1. Check runtime network posture aligns with demo constraints (no NAT expectations preserved).
2. Validate reachability surface for:
   - Kafka bootstrap endpoint,
   - S3 buckets/prefixes,
   - runtime DB endpoint,
   - CloudWatch log-group write surface.
3. Publish dependency snapshot.

DoD:
- [ ] Dependency reachability checks pass for mapped services.
- [ ] Any unreachable dependency is blocker-marked.
- [ ] M4.D dependency snapshot exists locally and durably.

Blockers:
1. `M4D-B1`: dependency reachability failure.
2. `M4D-B2`: network posture mismatch vs expected runtime lane.
3. `M4D-B3`: dependency snapshot write/upload failure.

### M4.E Launch Contract + Run-Scope Injection
Goal:
1. Produce deterministic launch contract enforcing run-scope for all services.

Tasks:
1. Build launch contract for each mapped service with:
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` and value from M3,
   - dependency env/secret references by handle,
   - image provenance references from M3/M1 anchors.
2. Validate that launch contract is non-secret.
3. Publish launch-contract snapshot.

DoD:
- [ ] Launch contract includes run-scope env mapping for all mapped services.
- [ ] Run-scope value equals M3 `platform_run_id` for all services.
- [ ] M4.E launch-contract snapshot exists locally and durably.

Blockers:
1. `M4E-B1`: run-scope env key/value missing or mismatched.
2. `M4E-B2`: launch contract missing required service entries.
3. `M4E-B3`: secret leakage detected in launch-contract artifacts.
4. `M4E-B4`: launch-contract snapshot write/upload failure.

### M4.F Daemon Bring-up + Stabilization
Goal:
1. Start mapped ECS services and validate stable running posture.

Tasks:
1. Execute service start/update choreography by pack order:
   - ingress first, then rtdl core/decision lanes, then case/labels, then obs_gov environment conformance daemon.
2. Wait for service stabilization and collect:
   - desired/running counts,
   - task ARNs,
   - health endpoint/log status.
3. Validate no crashloops and run-scope mismatch logs.
4. Publish daemon-start snapshot.

DoD:
- [ ] All mapped services reach expected singleton running posture.
- [ ] Crashloop-free stabilization checks pass.
- [ ] M4.F daemon-start snapshot exists locally and durably.

Blockers:
1. `M4F-B1`: service start/update failure.
2. `M4F-B2`: service fails stabilization (desired/running mismatch).
3. `M4F-B3`: crashloop or unhealthy state detected.
4. `M4F-B4`: daemon-start snapshot write/upload failure.

### M4.G Duplicate-Consumer Guard + Singleton Enforcement
Goal:
1. Ensure consumer uniqueness and no conflicting lane consumers.

Tasks:
1. Check for duplicate/manual once-off consumer interference in mapped lanes.
2. Validate singleton running posture is preserved after stabilization interval.
3. Publish consumer-uniqueness snapshot.

DoD:
- [ ] No duplicate consumer conflict exists for in-scope lanes.
- [ ] Singleton posture remains stable.
- [ ] M4.G uniqueness snapshot exists locally and durably.

Blockers:
1. `M4G-B1`: duplicate consumer conflict detected.
2. `M4G-B2`: singleton posture drift after stabilization.
3. `M4G-B3`: uniqueness snapshot write/upload failure.

### M4.H Daemon Readiness Evidence Publication
Goal:
1. Publish canonical run-scoped P2 readiness evidence.

Tasks:
1. Build readiness artifact:
   - `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
   containing:
   - pack IDs,
   - service names/task ARNs,
   - desired/running counts,
   - run-scope key/value used,
   - timestamp.
2. Publish local mirror and durable run-scoped object.

DoD:
- [ ] `operate/daemons_ready.json` exists and is complete.
- [ ] Run-scoped durable evidence publication passes.
- [ ] M4.H publication snapshot exists locally and durably.

Blockers:
1. `M4H-B1`: readiness artifact missing required fields.
2. `M4H-B2`: durable run-scoped publication failure.
3. `M4H-B3`: publication snapshot write/upload failure.

### M4.I Pass Gates + Blocker Rollup + Verdict
Goal:
1. Compute deterministic M4 verdict from explicit gate predicates.

Tasks:
1. Evaluate predicates:
   - `handles_closed`
   - `service_map_complete`
   - `iam_binding_valid`
   - `dependencies_reachable`
   - `run_scope_enforced`
   - `services_stable`
   - `no_duplicate_consumers`
   - `readiness_evidence_durable`
2. Roll up blockers from M4.A..M4.H.
3. Compute verdict:
   - all predicates true and blockers empty => `ADVANCE_TO_M5`
   - otherwise => `HOLD_M4`.
4. Publish verdict snapshot.

DoD:
- [ ] M4 gate predicates are explicit and reproducible.
- [ ] Blocker rollup is complete and fail-closed.
- [ ] Verdict snapshot exists locally and durably.

Blockers:
1. `M4I-B1`: missing/unreadable prerequisite snapshot from A-H lanes.
2. `M4I-B2`: predicate evaluation incomplete/invalid.
3. `M4I-B3`: blocker rollup non-empty.
4. `M4I-B4`: verdict snapshot write/upload failure.

### M4.J M5 Handoff Artifact Publication
Goal:
1. Publish canonical handoff surface for M5 entry.

Tasks:
1. Build `m5_handoff_pack.json` with:
   - `platform_run_id`
   - M4 verdict
   - readiness evidence URI
   - runtime service map snapshot URI
   - source execution IDs (`m3*`, `m4*`)
2. Ensure non-secret payload.
3. Publish local + durable handoff artifact.

DoD:
- [ ] `m5_handoff_pack.json` is complete and non-secret.
- [ ] Durable handoff publication passes.
- [ ] URI references are captured for M5 entry.

Blockers:
1. `M4J-B1`: M4 verdict is not `ADVANCE_TO_M5`.
2. `M4J-B2`: handoff pack missing required fields/URIs.
3. `M4J-B3`: non-secret policy violation in handoff artifact.
4. `M4J-B4`: handoff artifact write/upload failure.

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
3. `evidence/dev_min/run_control/<m4_execution_id>/m4_b_service_map_snapshot.json`
4. `evidence/dev_min/run_control/<m4_execution_id>/m4_c_iam_binding_snapshot.json`
5. `evidence/dev_min/run_control/<m4_execution_id>/m4_d_dependency_snapshot.json`
6. `evidence/dev_min/run_control/<m4_execution_id>/m4_e_launch_contract_snapshot.json`
7. `evidence/dev_min/run_control/<m4_execution_id>/m4_f_daemon_start_snapshot.json`
8. `evidence/dev_min/run_control/<m4_execution_id>/m4_g_consumer_uniqueness_snapshot.json`
9. `evidence/dev_min/run_control/<m4_execution_id>/m4_h_readiness_publication_snapshot.json`
10. `evidence/dev_min/run_control/<m4_execution_id>/m4_i_verdict_snapshot.json`
11. `evidence/dev_min/run_control/<m4_execution_id>/m5_handoff_pack.json`
12. local mirrors under:
   - `runs/dev_substrate/m4/<timestamp>/...`

Notes:
1. M4 artifacts must be non-secret.
2. Any secret-bearing payload in M4 artifacts is a hard blocker.
3. M4 readiness evidence must preserve P2 semantics from runbook (packs running, run-scope enforcement, no duplicate consumers).

## 7) M4 Completion Checklist
- [x] M4.A complete
- [x] M4.B complete
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
