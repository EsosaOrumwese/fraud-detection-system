# Dev Substrate Deep Plan - M4 (P2 Daemons Ready)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M4._
_Last updated: 2026-02-24_

## 0) Purpose
M4 closes `P2 DAEMONS_READY` for `dev_full` under the managed-first runtime posture.

M4 must prove:
1. required runtime lanes are selected and pinned to one active runtime path per phase run,
2. managed runtime lane health is green (Flink/API Gateway/Lambda/selective EKS),
3. run-scope and correlation conformance hold across runtime lanes,
4. readiness evidence is durable and auditable before M5 entry.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P2` section)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M3.build_plan.md`
2. `runs/dev_substrate/dev_full/m3/m3j_20260223T233827Z/m4_entry_readiness_receipt.json`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M4
In scope:
1. P2 handle closure and runtime-path pinning for spine lanes.
2. Runtime lane manifest freeze (Flink/API edge/selective EKS).
3. Runtime identity/IAM + network/dependency readiness checks.
4. Run-scope and correlation conformance checks at runtime boundary.
5. Readiness evidence publication and fail-closed gate rollup.
6. M5 handoff artifact publication for P3/P4 entry.

Out of scope:
1. Oracle output contract checks (`M5`).
2. Ingress preflight and READY publication (`M5/P4-P5`).
3. Streaming-active closure and downstream functional phases (`M6+`).
4. Learning/evolution lanes (`M11+`).

## 3) M4 Deliverables
1. M4 handle closure matrix + runtime-path selection snapshot.
2. Runtime manifest freeze and lane ownership matrix.
3. IAM/network/runtime conformance snapshots.
4. Runtime readiness publication snapshot (local + durable).
5. M4 blocker rollup and final verdict.
6. M5 handoff pack with deterministic references.

## 4) Entry Gate and Current Posture
Entry gate for M4:
1. M3 is `DONE` with verdict `ADVANCE_TO_M4`.

Current posture:
1. M3 closure is complete (`m3j_20260223T233827Z`).
2. M4 deep plan is now materialized for execution sequencing.

Current pre-execution blockers (fail-closed):
1. `M4-B0`: M4 deep plan file missing or unresolved capability lanes.
2. `M4-B0.1`: required runtime-path/handle closure not yet verified in M4.A.

## 4.1) Anti-Cram Law (Binding for M4)
M4 is not execution-ready unless these capability lanes are explicit:
1. authority and handles,
2. runtime path selection,
3. identity/IAM,
4. network/dependency reachability,
5. runtime health and service posture,
6. observability and correlation continuity,
7. failure/recovery/rollback proof,
8. evidence publication,
9. blocker adjudication and handoff.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M4.A | no unresolved required `P2` handles |
| Runtime-path pinning + manifest freeze | M4.B | single active runtime path + manifest snapshot |
| Identity/IAM conformance | M4.C | role/binding matrix pass |
| Network/dependency reachability | M4.D | dependency probe snapshot pass |
| Runtime health + run-scope conformance | M4.E | lane health + env binding snapshot pass |
| Correlation + telemetry continuity | M4.F | correlation conformance snapshot pass |
| Failure/recovery/rollback proof | M4.G | drill + recovery + rollback artifacts pass |
| Readiness evidence publication | M4.H | durable readiness artifact exists |
| Gate rollup + blocker adjudication | M4.I | blocker-free verdict artifact |
| M5 handoff publication | M4.J | durable `m5_handoff_pack.json` |

## 5) Work Breakdown (Deep)

### M4.A Authority + Handle Closure (P2)
Goal:
1. close required M4/P2 handles before runtime actions.

Tasks:
1. resolve required runtime-path handles:
   - `PHASE_RUNTIME_PATH_MODE`
   - `PHASE_RUNTIME_PATH_PIN_REQUIRED`
   - `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED`
2. resolve required runtime lane handles for P2 surfaces:
   - Flink lane handles
   - ingress edge handles
   - selective EKS runtime handles
3. resolve required evidence handles for M4 snapshots.
4. classify unresolved required handles as blockers.

DoD:
- [x] required M4 handle set is explicit and complete.
- [x] every required handle has a verification method.
- [x] unresolved required handles are blocker-marked.
- [x] M4.A closure snapshot exists locally and durably.

M4.A planning precheck (decision completeness):
1. Required handle families for P2 are explicit:
   - runtime-path control (`PHASE_RUNTIME_PATH_*`, `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED`),
   - stream lane (`FLINK_RUNTIME_MODE`, `FLINK_APP_*`, `MSK_*`),
   - ingress edge (`LAMBDA_IG_HANDLER_NAME` + ingress path handles),
   - selective EKS runtime policy + roles,
   - run-scope and observability anchors (`REQUIRED_PLATFORM_RUN_ID_ENV_KEY`, `CLOUDWATCH_LOG_GROUP_PREFIX`, `OTEL_*`).
2. M3 gate dependency is explicit:
   - M3 verdict `ADVANCE_TO_M4` from `m3j_20260223T233827Z`.
3. Handle boundary for M4.A is explicit:
   - only P2 runtime handles are required; non-P2 handles may remain open without blocking M4.A.

M4.A decision pins (closed before execution):
1. Single-active-path law applies at handle-closure stage:
   - path-switch within phase run is prohibited (`RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED=false`).
2. Managed-first law:
   - required lane handles must align to managed-first runtime surfaces (Flink/API edge/selective EKS), no local runtime substitutions.
3. P2-boundary law:
   - M4.A blocks only on unresolved required P2 handles; out-of-scope future-phase handles are tracked but non-blocking.
4. Materialization law:
   - any required handle value set to `TO_PIN` is unresolved and blocker-worthy for M4.A.
5. Evidence law:
   - handle closure result must be emitted locally and durably before M4.B entry.

M4.A verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4A-V1-HANDLE-PRESENCE` | `rg -n \"PHASE_RUNTIME_PATH_MODE|PHASE_RUNTIME_PATH_PIN_REQUIRED|RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED|RUNTIME_DEFAULT_STREAM_ENGINE|FLINK_RUNTIME_MODE|FLINK_APP_|LAMBDA_IG_HANDLER_NAME|RUNTIME_EKS_USE_POLICY|REQUIRED_PLATFORM_RUN_ID_ENV_KEY|CLOUDWATCH_LOG_GROUP_PREFIX|OTEL_ENABLED\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | verifies required handle presence |
| `M4A-V2-TO_PIN-GUARD` | parse required handle values and fail on `TO_PIN` within required set | blocks unresolved required handles |
| `M4A-V3-RUNTIME-PATH-LAW` | assert `PHASE_RUNTIME_PATH_MODE=single_active_path_per_phase_run`, `PHASE_RUNTIME_PATH_PIN_REQUIRED=true`, `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED=false` | enforces runtime-path contract |
| `M4A-V4-M3-GATE` | verify `runs/dev_substrate/dev_full/m3/m3j_20260223T233827Z/m3_execution_summary.json` has `verdict=ADVANCE_TO_M4` | enforces M4 entry dependency |
| `M4A-V5-SNAPSHOT-PUBLISH` | `aws s3 cp <local_snapshot> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4a_execution_id>/...` | publishes durable M4.A closure evidence |

M4.A blocker taxonomy (fail-closed):
1. `M4A-B1`: required P2 handle missing from registry.
2. `M4A-B2`: required P2 handle unresolved (`TO_PIN`) or malformed.
3. `M4A-B3`: runtime-path law drift (`single_active` contract violated).
4. `M4A-B4`: M3 entry dependency missing/non-advance.
5. `M4A-B5`: closure snapshot missing/incomplete.
6. `M4A-B6`: durable publish/readback failure for closure snapshot.

M4.A evidence contract (planned):
1. `m4a_handle_closure_snapshot.json`
2. `m4a_required_handle_matrix.json`
3. `m4a_execution_summary.json`

M4.A closure rule:
1. M4.A can close only when:
   - all `M4A-B*` blockers are resolved,
   - DoD checks are green,
   - closure artifacts exist locally and durably,
   - required P2 handle unresolved set is empty.

M4.A planning status (current):
1. Prerequisite M3 closure is complete with `ADVANCE_TO_M4`.
2. M4.A is expanded to execution-grade with explicit blocker taxonomy and evidence contract.
3. Pre-execution blockers were not known at planning time.
4. Phase posture:
   - planning expanded; execution closed green.

M4.A execution status (2026-02-24):
1. Authoritative execution id:
   - `m4a_20260224T043334Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m4/m4a_20260224T043334Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4a_20260224T043334Z/`
4. PASS artifacts:
   - `m4a_handle_closure_snapshot.json`
   - `m4a_required_handle_matrix.json`
   - `m4a_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M4.A_READY`
   - required handles: `33/33` resolved
   - runtime-path contract: `PASS`
   - M3 gate dependency (`ADVANCE_TO_M4`): `PASS`
6. Blocker remediation trail retained:
   - attempt `m4a_20260224T043207Z` raised `M4A-B1` due checker naming drift (`RUNTIME_DEFAULT_STREAM_LANE` vs canonical `RUNTIME_DEFAULT_STREAM_ENGINE`),
   - rerun with canonical key closed the blocker without registry semantic duplication.

### M4.B Runtime Path Selection + Lane Manifest Freeze
Goal:
1. pin one active runtime path per lane for this M4 execution.

Tasks:
1. generate runtime lane manifest from pinned handles.
2. freeze selected runtime path per lane (no in-phase switching).
3. record explicit exclusions/fallbacks and justification.
4. publish immutable lane manifest snapshot.

DoD:
- [ ] lane manifest is complete for all P2 lanes.
- [ ] each lane has one active path with explicit owner.
- [ ] fallback paths are explicit but inactive.
- [ ] manifest snapshot is committed locally and durably.

M4.B planning precheck (decision completeness):
1. Required upstream dependency:
   - latest M4.A execution summary is PASS (`m4a_20260224T043334Z`).
2. Runtime-path guardrail handles remain pinned:
   - `PHASE_RUNTIME_PATH_MODE=single_active_path_per_phase_run`
   - `PHASE_RUNTIME_PATH_PIN_REQUIRED=true`
   - `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED=false`
3. Runtime path family handles are present:
   - `RUNTIME_DEFAULT_STREAM_ENGINE`
   - `RUNTIME_DEFAULT_INGRESS_EDGE`
   - `RUNTIME_EKS_USE_POLICY`
4. Lane component handles are present for mapping:
   - Flink apps (`FLINK_APP_*`),
   - ingress edge (`IG_EDGE_MODE`, `APIGW_IG_API_ID`, `LAMBDA_IG_HANDLER_NAME`),
   - selective EKS deployment handles (`K8S_DEPLOY_*`) for differentiating services only.

M4.B decision pins (closed before execution):
1. Single-active-path law:
   - exactly one active runtime path per lane in this phase execution.
2. Managed-first mapping law:
   - stream-native transforms map to `MSK+Flink`.
   - ingress edge maps to `API Gateway + Lambda + DynamoDB`.
3. Selective-EKS law:
   - EKS path may be active only for differentiating/custom lanes consistent with `RUNTIME_EKS_USE_POLICY`.
4. No in-phase switching law:
   - runtime path cannot change after manifest freeze within same `phase_execution_id`.
5. Exclusion explicitness law:
   - inactive paths must be listed with rationale (not implied/omitted).

M4.B verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4B-V1-M4A-GATE` | verify `runs/dev_substrate/dev_full/m4/m4a_20260224T043334Z/m4a_execution_summary.json` has `overall_pass=true` | enforces M4.B entry gate |
| `M4B-V2-HANDLE-PRESENCE` | `rg -n \"RUNTIME_DEFAULT_STREAM_ENGINE|RUNTIME_DEFAULT_INGRESS_EDGE|RUNTIME_EKS_USE_POLICY|FLINK_APP_|IG_EDGE_MODE|K8S_DEPLOY_\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | verifies runtime path mapping handles exist |
| `M4B-V3-SINGLE-ACTIVE-PATH` | evaluate lane manifest and assert one active path per lane | enforces single-path law |
| `M4B-V4-EKS-POLICY-CONFORMANCE` | assert active EKS lanes are subset of differentiating-service set | enforces selective-EKS policy |
| `M4B-V5-MANIFEST-PUBLISH` | `aws s3 cp <local_manifest> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4b_execution_id>/...` | publishes durable M4.B evidence |

M4.B blocker taxonomy (fail-closed):
1. `M4B-B1`: M4.A gate missing/non-pass.
2. `M4B-B2`: required mapping handles missing/unresolved.
3. `M4B-B3`: lane manifest incomplete or malformed.
4. `M4B-B4`: multiple active paths detected for a lane.
5. `M4B-B5`: EKS active path violates differentiating-services policy.
6. `M4B-B6`: inactive/fallback paths not explicitly declared with rationale.
7. `M4B-B7`: durable publish/readback failure for manifest artifacts.

M4.B evidence contract (planned):
1. `m4b_runtime_path_manifest.json`
2. `m4b_lane_path_selection_matrix.json`
3. `m4b_execution_summary.json`

M4.B closure rule:
1. M4.B can close only when:
   - all `M4B-B*` blockers are resolved,
   - DoD checks are green,
   - manifest artifacts exist locally and durably,
   - each lane has one and only one active runtime path.

M4.B planning status (current):
1. Prerequisite M4.A is closed green.
2. M4.B is expanded to execution-grade with explicit blocker taxonomy and evidence contract.
3. No pre-execution blockers are known at planning time.
4. Phase posture:
   - planning expanded; execution not started.

### M4.C Identity/IAM Conformance
Goal:
1. prove runtime identities/roles are aligned to pinned contract.

Tasks:
1. validate role bindings for Flink/API edge/selective EKS lanes.
2. validate secrets/SSM read scopes for runtime principals.
3. detect and fail on role drift vs pinned handles.
4. publish identity conformance snapshot.

DoD:
- [ ] all runtime lanes have valid identity bindings.
- [ ] no unresolved IAM drift remains.
- [ ] identity conformance snapshot is durable.

### M4.D Network + Dependency Reachability
Goal:
1. prove runtime dependencies are reachable before runtime health adjudication.

Tasks:
1. build dependency matrix for each pinned lane.
2. validate required dependencies (MSK/S3/Aurora/Redis/observability endpoints).
3. capture probe evidence and failure classifications.
4. publish dependency conformance snapshot.

DoD:
- [ ] dependency matrix covers all pinned runtime lanes.
- [ ] required dependency checks pass.
- [ ] probe evidence is committed locally and durably.

### M4.E Runtime Health + Run-Scope Binding
Goal:
1. prove required runtime lanes are healthy and run-scope aware.

Tasks:
1. capture runtime lane health snapshots.
2. validate run-scope env conformance (`REQUIRED_PLATFORM_RUN_ID` and related fields).
3. validate singleton/desired-count posture as pinned for M4.
4. publish runtime health + binding snapshot.

DoD:
- [ ] required runtime lanes report healthy posture.
- [ ] run-scope binding checks pass.
- [ ] no crashloop/unbounded restart remains.
- [ ] snapshot is durable.

### M4.F Correlation + Telemetry Continuity
Goal:
1. prove cross-runtime correlation fields survive runtime boundaries.

Tasks:
1. validate required correlation fields:
   - `platform_run_id,scenario_run_id,phase_id,event_id,runtime_lane,trace_id`
2. validate telemetry heartbeat and log/metric surfaces for pinned lanes.
3. detect missing field propagation and fail closed.
4. publish correlation conformance snapshot.

DoD:
- [ ] required correlation fields are preserved across runtime boundaries.
- [ ] telemetry surfaces for required lanes are present.
- [ ] conformance snapshot is durable.

### M4.G Failure/Recovery/Rollback Runtime Drill
Goal:
1. satisfy runtime six-proof obligations for P2 lane class.

Tasks:
1. execute bounded failure drill on selected runtime lane.
2. execute recovery and rollback path checks.
3. validate restored healthy posture and binding continuity.
4. publish drill/recovery/rollback proof artifacts.

DoD:
- [ ] bounded failure drill artifact is committed.
- [ ] recovery proof is committed.
- [ ] rollback proof is committed.
- [ ] post-drill runtime health remains green.

### M4.H Runtime Readiness Evidence Publication
Goal:
1. publish canonical M4 readiness evidence for downstream gates.

Tasks:
1. assemble readiness payload from M4.A..M4.G artifacts.
2. validate payload completeness and reference readability.
3. publish readiness artifact locally and durably.
4. publish M4.H control snapshot.

DoD:
- [ ] readiness payload is complete and reference-valid.
- [ ] durable publication succeeds.
- [ ] M4.H publication snapshot is committed.

### M4.I Pass Gates + Blocker Rollup + Verdict
Goal:
1. adjudicate M4 closure using M4.A..M4.H evidence.

Tasks:
1. evaluate pass predicates for each M4 lane.
2. aggregate unresolved blockers with severity.
3. produce deterministic M4 verdict.
4. publish M4.I rollup + verdict artifact.

DoD:
- [ ] pass predicate matrix is complete.
- [ ] unresolved blocker set is explicit.
- [ ] deterministic verdict artifact is committed.

### M4.J M5 Handoff Artifact Publication
Goal:
1. publish M5 entry handoff only when M4 verdict allows progression.

Tasks:
1. build `m5_handoff_pack.json` with run-scope and evidence refs.
2. validate referenced artifacts are readable.
3. publish handoff locally and durably.
4. append closure note to master plan + impl map + logbook.

DoD:
- [ ] `m5_handoff_pack.json` committed locally and durably.
- [ ] M4 closure notes appended to required docs.
- [ ] M5 entry marker is explicit and deterministic.

## 6) M4 Blocker Taxonomy (Fail-Closed)
1. `M4-B0`: deep plan/capability-lane incompleteness.
2. `M4-B1`: required handle missing/inconsistent.
3. `M4-B2`: runtime-path ambiguity or in-phase switching drift.
4. `M4-B3`: identity/IAM conformance failure.
5. `M4-B4`: dependency reachability failure.
6. `M4-B5`: runtime lane health or run-scope binding failure.
7. `M4-B6`: correlation/telemetry conformance failure.
8. `M4-B7`: failure/recovery/rollback proof missing or failed.
9. `M4-B8`: readiness publication failure.
10. `M4-B9`: rollup/verdict inconsistency or unresolved blocker set.
11. `M4-B10`: M5 handoff artifact missing/invalid/unreadable.

Any active `M4-B*` blocker prevents M4 closure.

## 7) M4 Evidence Contract (Pinned for Execution)
1. `m4a_handle_closure_snapshot.json`
2. `m4b_runtime_path_manifest.json`
3. `m4c_identity_conformance_snapshot.json`
4. `m4d_dependency_probe_snapshot.json`
5. `m4e_runtime_health_binding_snapshot.json`
6. `m4f_correlation_conformance_snapshot.json`
7. `m4g_runtime_drill_snapshot.json`
8. `m4h_readiness_publication_snapshot.json`
9. `m4i_gate_rollup_verdict.json`
10. `m5_handoff_pack.json`

## 8) M4 Completion Checklist
- [x] M4.A complete
- [ ] M4.B complete
- [ ] M4.C complete
- [ ] M4.D complete
- [ ] M4.E complete
- [ ] M4.F complete
- [ ] M4.G complete
- [ ] M4.H complete
- [ ] M4.I complete
- [ ] M4.J complete
- [ ] M4 blockers resolved or explicitly fail-closed
- [ ] M4 closure note appended in implementation map
- [ ] M4 action log appended in logbook

## 9) Exit Criteria
M4 can close only when:
1. all checklist items in Section 8 are complete,
2. verdict is blocker-free and deterministic,
3. runtime readiness evidence is locally and durably readable,
4. `m5_handoff_pack.json` is committed and reference-valid.

Handoff posture:
1. M5 remains blocked until M4 verdict is `ADVANCE_TO_M5`.
