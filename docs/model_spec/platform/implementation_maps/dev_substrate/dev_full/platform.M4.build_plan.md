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
- [x] lane manifest is complete for all P2 lanes.
- [x] each lane has one active path with explicit owner.
- [x] fallback paths are explicit but inactive.
- [x] manifest snapshot is committed locally and durably.

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
   - planning expanded; execution closed green.

M4.B execution status (2026-02-24):
1. Authoritative execution id:
   - `m4b_20260224T044454Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4b_20260224T044454Z/`
4. PASS artifacts:
   - `m4b_runtime_path_manifest.json`
   - `m4b_lane_path_selection_matrix.json`
   - `m4b_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M4.B_READY`
   - lane count: `5`
   - single-active-path pass: `true`
   - EKS policy conformance pass: `true`
   - manifest digest: `fa5399d7c5fdee0e17b5f89bfc52958d7c5685cdb099a7eb16b0c21b4cc8f249`
6. Execution note:
   - initial shell wrapper timeout occurred during long publish window; lane rerun completed successfully with increased command timeout and no semantic blockers.

### M4.C Identity/IAM Conformance
Goal:
1. prove runtime identities/roles are aligned to pinned contract.

Tasks:
1. validate role bindings for Flink/API edge/selective EKS lanes.
2. validate secrets/SSM read scopes for runtime principals.
3. detect and fail on role drift vs pinned handles.
4. publish identity conformance snapshot.

DoD:
- [x] all runtime lanes have valid identity bindings.
- [x] no unresolved IAM drift remains.
- [x] identity conformance snapshot is durable.

M4.C planning precheck (decision completeness):
1. Required upstream dependency:
   - latest M4.B execution summary is PASS (`m4b_20260224T044454Z`).
2. Required identity handles are explicit for active M4.B lanes:
   - `ROLE_FLINK_EXECUTION`
   - `ROLE_LAMBDA_IG_EXECUTION`
   - `ROLE_APIGW_IG_INVOKE`
   - `ROLE_DDB_IG_IDEMPOTENCY_RW`
   - `ROLE_EKS_RUNTIME_PLATFORM_BASE`
3. Required EKS runtime identity handles for differentiating-services path:
   - `ROLE_EKS_IRSA_IG`
   - `ROLE_EKS_IRSA_RTDL`
   - `ROLE_EKS_IRSA_DECISION_LANE`
   - `ROLE_EKS_IRSA_CASE_LABELS`
   - `ROLE_EKS_IRSA_OBS_GOV`
4. Secret/identity posture handles are explicit:
   - `SECRETS_BACKEND`
   - `SECRETS_PLAINTEXT_OUTPUT_ALLOWED`
   - `KMS_KEY_ALIAS_PLATFORM`
   - required SSM path handles for runtime dependencies.

M4.C decision pins (closed before execution):
1. Active-lane-only law:
   - identity conformance scope is derived from active paths in M4.B manifest.
2. No-placeholder law:
   - any required role handle unresolved/blank/placeholder is blocker-worthy.
3. Least-privilege law:
   - runtime role permissions must align to lane ownership surfaces; wildcard overreach is drift.
4. Secrets policy law:
   - plaintext secret output is forbidden; secret access must flow through pinned backend.
5. Deterministic binding law:
   - one canonical role-binding map per active lane for this phase execution.

M4.C verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4C-V1-M4B-GATE` | verify `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/m4b_execution_summary.json` has `overall_pass=true` | enforces M4.C entry gate |
| `M4C-V2-ROLE-HANDLE-CLOSURE` | parse required role handles and fail on unresolved placeholders | validates role handle closure |
| `M4C-V3-RUNTIME-ROLE-READBACK` | read IAM role metadata/policies for active-lane role handles | validates materialized role surfaces |
| `M4C-V4-SECRET-PATH-CONFORMANCE` | verify required SSM secret paths are readable by intended runtime principals | validates secret-access posture |
| `M4C-V5-BINDING-MATRIX-PUBLISH` | `aws s3 cp <local_snapshot> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4c_execution_id>/...` | publishes durable M4.C evidence |

M4.C blocker taxonomy (fail-closed):
1. `M4C-B1`: M4.B gate missing/non-pass.
2. `M4C-B2`: required role handle missing/unresolved/malformed.
3. `M4C-B3`: materialized role readback/policy validation failure.
4. `M4C-B4`: required secret-path conformance failure.
5. `M4C-B5`: plaintext/unsafe secrets posture detected.
6. `M4C-B6`: role-binding matrix incomplete or inconsistent with active lane manifest.
7. `M4C-B7`: durable publish/readback failure for M4.C artifacts.

M4.C evidence contract (planned):
1. `m4c_identity_conformance_snapshot.json`
2. `m4c_role_binding_matrix.json`
3. `m4c_secret_path_conformance_snapshot.json`
4. `m4c_execution_summary.json`

M4.C closure rule:
1. M4.C can close only when:
   - all `M4C-B*` blockers are resolved,
   - DoD checks are green,
   - conformance artifacts exist locally and durably,
   - active-lane role-binding matrix is complete and placeholder-free.

M4.C planning status (historical pre-execution snapshot):
1. Prerequisite M4.B is closed green.
2. M4.C is expanded to execution-grade with explicit blocker taxonomy and evidence contract.
3. Known likely pre-execution blocker identified at planning time:
   - `ROLE_EKS_IRSA_*` handles appear unmaterialized and may raise `M4C-B2` until pinned/materialized.
4. Phase posture:
   - planning expanded (execution status recorded below).

M4.C execution status (2026-02-24):
1. Attempt #1 (non-authoritative due checker defect):
   - execution id: `m4c_20260224T050216Z`
   - issue: role-handle parser failed on annotated assignment lines, causing false unresolved-role signal.
   - disposition: retained as audit evidence; not used for closure verdict.
2. Attempt #2 (authoritative, fail-closed):
   - execution id: `m4c_20260224T050409Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4c_20260224T050409Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4c_20260224T050409Z/`
   - result: `overall_pass=false`, `blockers=[M4C-B2,M4C-B4,M4C-B6]`, `next_gate=BLOCKED`.
3. Blocker details from authoritative run:
   - `M4C-B2`: unresolved IRSA role handles for differentiating-services lane:
     - `ROLE_EKS_IRSA_IG`
     - `ROLE_EKS_IRSA_RTDL`
     - `ROLE_EKS_IRSA_DECISION_LANE`
     - `ROLE_EKS_IRSA_CASE_LABELS`
     - `ROLE_EKS_IRSA_OBS_GOV`
   - `M4C-B4`: missing runtime SSM dependency paths:
     - `/fraud-platform/dev_full/aurora/endpoint`
     - `/fraud-platform/dev_full/aurora/reader_endpoint`
     - `/fraud-platform/dev_full/aurora/username`
     - `/fraud-platform/dev_full/aurora/password`
     - `/fraud-platform/dev_full/redis/endpoint`
   - `M4C-B6`: role-binding matrix incomplete because unresolved IRSA handles leave differentiating-services binding partial.
4. M4.C closure posture:
   - DoD remained open until `M4C-B2/B4/B6` remediation.
5. Attempt #3 (authoritative closure run after remediation):
   - execution id: `m4c_20260224T051711Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4c_20260224T051711Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4c_20260224T051711Z/`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.C_READY`.
   - key metrics:
     - `resolved_role_count=11/11`
     - `present_secret_path_count=7/7`
     - `binding_matrix_complete_pass=true`
6. M4.C closure posture:
   - `M4.C` is closed green.

### M4.D Network + Dependency Reachability
Goal:
1. prove runtime dependencies are reachable before runtime health adjudication.

Tasks:
1. build dependency matrix for each pinned lane.
2. validate required dependencies (MSK/S3/Aurora/Redis/observability endpoints).
3. capture probe evidence and failure classifications.
4. publish dependency conformance snapshot.

DoD:
- [x] dependency matrix covers all pinned runtime lanes.
- [x] required dependency checks pass.
- [x] probe evidence is committed locally and durably.

M4.D planning precheck (decision completeness):
1. Required upstream dependency:
   - latest M4.C execution summary is PASS (`m4c_20260224T051711Z`).
2. Runtime lane/source dependency manifest is fixed:
   - `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/m4b_runtime_path_manifest.json`.
3. Required dependency handles are explicit and pinned:
   - stream/control surfaces:
     - `MSK_CLUSTER_ARN`
     - `SSM_MSK_BOOTSTRAP_BROKERS_PATH`
     - `FP_BUS_CONTROL_V1` + RTDL/case/audit topic handles
   - storage surfaces:
     - `S3_OBJECT_STORE_BUCKET`
     - `S3_EVIDENCE_BUCKET`
     - `S3_ARTIFACTS_BUCKET`
   - ingress/runtime surfaces:
     - `APIGW_IG_API_ID`
     - `LAMBDA_IG_HANDLER_NAME`
     - `EKS_CLUSTER_ARN`
   - datastore dependency surfaces:
     - `SSM_AURORA_ENDPOINT_PATH`
     - `SSM_AURORA_READER_ENDPOINT_PATH`
     - `SSM_AURORA_USERNAME_PATH`
     - `SSM_AURORA_PASSWORD_PATH`
     - `SSM_REDIS_ENDPOINT_PATH`
   - observability surfaces:
     - `CLOUDWATCH_LOG_GROUP_PREFIX`
     - `OTEL_COLLECTOR_SERVICE`
4. Probe output hygiene requirement:
   - secret values are never emitted in cleartext artifacts (metadata-only on secure paths).

M4.D decision pins (closed before execution):
1. Active-lane-only dependency law:
   - probe scope is derived from active paths in M4.B; inactive fallbacks are excluded.
2. Handle-anchored probe law:
   - dependency probes must target registry-pinned handle surfaces only (no inferred endpoints).
3. Bounded probe law:
   - each probe has bounded timeout + deterministic failure classification.
4. Secret-safe evidence law:
   - probe artifacts may include path/key references and status only; secret payload values are forbidden.
5. Deterministic classification law:
   - each failed probe must map to an explicit blocker code/category; no uncategorized failure states.

M4.D verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4D-V1-M4C-GATE` | verify `runs/dev_substrate/dev_full/m4/m4c_20260224T051711Z/m4c_execution_summary.json` has `overall_pass=true` | enforces M4.D entry gate |
| `M4D-V2-DEPENDENCY-MATRIX-BUILD` | derive lane->dependency matrix from M4.B manifest + pinned handles | ensures complete dependency scope before probing |
| `M4D-V3-STREAM-EDGE-STORAGE-PROBES` | `aws kafka describe-cluster-v2 ...`; `aws s3api head-bucket ...`; `aws apigatewayv2 get-api ...`; `aws lambda get-function ...` | validates stream/edge/storage control-plane reachability |
| `M4D-V4-DATASTORE-PROBE` | `aws ssm get-parameter --name <aurora/redis paths> --with-decryption` + endpoint sanity checks | validates datastore dependency path readiness without leaking values |
| `M4D-V5-OBS-PROBE` | `aws logs describe-log-groups --log-group-name-prefix <CLOUDWATCH_LOG_GROUP_PREFIX>` | validates observability dependency surface |
| `M4D-V6-PUBLISH` | `aws s3 cp <local_snapshot> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4d_execution_id>/...` | publishes durable M4.D evidence |

M4.D blocker taxonomy (fail-closed):
1. `M4D-B1`: M4.C gate missing/non-pass.
2. `M4D-B2`: dependency matrix incomplete/inconsistent with active lane manifest.
3. `M4D-B3`: stream/edge/storage dependency probe failure.
4. `M4D-B4`: datastore dependency unresolved/placeholder/non-routable.
5. `M4D-B5`: observability dependency surface missing/unreadable.
6. `M4D-B6`: uncategorized probe failure or invalid failure classification.
7. `M4D-B7`: durable publish/readback failure for M4.D artifacts.
8. `M4D-B8`: secret/credential value leakage detected in probe artifacts.

M4.D evidence contract (planned):
1. `m4d_dependency_matrix.json`
2. `m4d_dependency_probe_snapshot.json`
3. `m4d_probe_failure_classification.json`
4. `m4d_execution_summary.json`

M4.D closure rule:
1. M4.D can close only when:
   - all `M4D-B*` blockers are resolved,
   - DoD checks are green,
   - probe artifacts exist locally and durably,
   - dependency matrix covers all active lanes and mandatory shared dependencies.

M4.D planning status (historical pre-execution snapshot):
1. Prerequisite M4.C is closed green.
2. M4.D is expanded to execution-grade with probe catalog, blocker taxonomy, and evidence contract.
3. Known likely pre-execution blockers to verify at runtime:
   - datastore endpoint seeds may still be placeholder/non-routable and can raise `M4D-B4`.
   - observability surfaces may be partially materialized before runtime-lane start and can raise `M4D-B5`.
4. Phase posture:
   - planning expanded (execution status recorded below).

M4.D execution status (2026-02-24):
1. Attempt #1 (authoritative fail-closed):
   - execution id: `m4d_20260224T054113Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4d_20260224T054113Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4d_20260224T054113Z/`
   - result: `overall_pass=false`, `blockers=[M4D-B3,M4D-B5]`, `next_gate=BLOCKED`.
   - blocker details:
     - `M4D-B3`: stale handle drift (`MSK_CLUSTER_ARN`, `APIGW_IG_API_ID`) resolved to deleted resources.
     - `M4D-B5`: no log groups under `CLOUDWATCH_LOG_GROUP_PREFIX`.
2. Remediation actions executed:
   - repinned streaming/ingress handles in registry from current Terraform outputs:
     - `MSK_CLUSTER_ARN`
     - `MSK_BOOTSTRAP_BROKERS_SASL_IAM`
     - `MSK_CLIENT_SUBNET_IDS`
     - `MSK_SECURITY_GROUP_ID`
     - `APIGW_IG_API_ID`
   - materialized observability bootstrap surface via IaC:
     - added `aws_cloudwatch_log_group.runtime_bootstrap` in `infra/terraform/dev_full/ops/main.tf`
     - applied ops stack to create `/fraud-platform/dev_full/runtime-bootstrap` with retention `14`.
3. Attempt #2 (authoritative closure run):
   - execution id: `m4d_20260224T054449Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4d_20260224T054449Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4d_20260224T054449Z/`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.D_READY`.
   - key metrics:
     - `active_lane_count=5`
     - `matrix_complete_pass=true`
     - `probe_count=16`
     - `failed_probe_count=0`
4. M4.D closure posture:
   - `M4.D` is closed green.

### M4.E Runtime Health + Run-Scope Binding
Goal:
1. prove required runtime lanes are healthy and run-scope aware.

Tasks:
1. capture runtime lane health snapshots for all active M4.B lanes.
2. validate run-scope binding conformance against M3 run identity (`platform_run_id`, `scenario_run_id`).
3. validate runtime stability posture for managed surfaces (no failed-active state at P2).
4. publish runtime health + binding snapshots locally and durably.

DoD:
- [x] required runtime lanes report healthy posture.
- [x] run-scope binding checks pass.
- [x] no crashloop/unbounded restart remains.
- [x] snapshot is durable.

M4.E planning precheck (decision completeness):
1. Required upstream dependencies:
   - latest M4.D execution summary is PASS (`m4d_20260224T054449Z`),
   - M3 handoff pack is readable (`runs/dev_substrate/dev_full/m3/m3f_20260223T224855Z/m4_handoff_pack.json`).
2. Active lane manifest is fixed by M4.B:
   - `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/m4b_runtime_path_manifest.json`.
3. Required runtime health handles are explicit and pinned:
   - stream lane:
     - `MSK_CLUSTER_ARN`
     - `SSM_MSK_BOOTSTRAP_BROKERS_PATH`
     - `ROLE_FLINK_EXECUTION`
   - ingress edge lane:
     - `APIGW_IG_API_ID`
     - `IG_BASE_URL`
     - `IG_HEALTHCHECK_PATH`
     - `IG_INGEST_PATH`
     - `LAMBDA_IG_HANDLER_NAME`
     - `DDB_IG_IDEMPOTENCY_TABLE`
     - `SSM_IG_API_KEY_PATH`
   - differentiating-services lane:
     - `EKS_CLUSTER_ARN`
     - `ROLE_EKS_IRSA_IG`
     - `ROLE_EKS_IRSA_RTDL`
     - `ROLE_EKS_IRSA_DECISION_LANE`
     - `ROLE_EKS_IRSA_CASE_LABELS`
     - `ROLE_EKS_IRSA_OBS_GOV`
   - orchestration and observability:
     - `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
     - `CLOUDWATCH_LOG_GROUP_PREFIX`
4. Required run-scope handles are explicit:
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
   - `FIELD_PLATFORM_RUN_ID`
   - `KAFKA_PARTITION_KEY_CONTROL`
5. Artifact safety requirement:
   - no secret/token plaintext values may appear in M4.E artifacts.

M4.E decision pins (closed before execution):
1. P2 lane-health boundary law:
   - P2 health proof is control-plane/runtime-surface readiness for active lanes; P6 holds streaming-active proof.
2. Active-lane-only scope law:
   - only M4.B active lanes are probed in M4.E.
3. Run-scope identity law:
   - run-scope checks are anchored to M3 handoff identity (`platform_run_id`, `scenario_run_id`) and required env-key handle.
4. Fail-closed drift law:
   - any non-active/unhealthy managed surface or run-scope mismatch yields explicit M4E blocker.
5. Secret-safe evidence law:
   - secure parameters may be checked for existence/use, but values are never emitted.

M4.E verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4E-V1-M4D-GATE` | verify `runs/dev_substrate/dev_full/m4/m4d_20260224T054449Z/m4d_execution_summary.json` has `overall_pass=true` | enforces M4.E entry gate |
| `M4E-V2-LANE-HEALTH-PROBE` | `aws kafka describe-cluster-v2`; `aws apigatewayv2 get-api`; `aws lambda get-function`; `aws dynamodb describe-table`; `aws eks describe-cluster`; `aws stepfunctions describe-state-machine`; `aws logs describe-log-groups` | validates lane health surfaces |
| `M4E-V3-INGRESS-HEALTH-CHECK` | invoke `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` with `X-IG-Api-Key` from `SSM_IG_API_KEY_PATH` | proves ingress edge health endpoint |
| `M4E-V4-RUN-SCOPE-INGEST-BINDING` | invoke `POST <IG_BASE_URL><IG_INGEST_PATH>` with run-scoped payload carrying `platform_run_id` | validates ingress run-scope carriage path |
| `M4E-V5-RUN-SCOPE-ORCHESTRATOR-BINDING` | start/describe Step Functions execution with run-scoped input | validates run-scope carriage at commit authority boundary |
| `M4E-V6-RUNTIME-STABILITY` | evaluate managed surface statuses (`ACTIVE`/`Successful`) and classify failures | enforces no unstable runtime posture |
| `M4E-V7-SNAPSHOT-WRITE` | emit local `m4e_*` artifacts under `runs/dev_substrate/dev_full/m4/<m4e_execution_id>/` | guarantees local audit surfaces |
| `M4E-V8-DURABLE-PUBLISH` | `aws s3 cp <local_artifacts> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4e_execution_id>/...` | publishes durable M4.E evidence |

M4.E blocker taxonomy (fail-closed):
1. `M4E-B1`: M4.D gate missing/non-pass.
2. `M4E-B2`: required runtime lane health probe failure.
3. `M4E-B3`: run-scope binding drift/mismatch.
4. `M4E-B4`: managed runtime instability detected.
5. `M4E-B5`: durable publish/readback failure for M4.E artifacts.
6. `M4E-B6`: secret/credential leakage detected in M4.E artifacts.

M4.E evidence contract (planned):
1. `m4e_lane_health_snapshot.json`
2. `m4e_run_scope_binding_matrix.json`
3. `m4e_runtime_health_binding_snapshot.json`
4. `m4e_execution_summary.json`

M4.E closure rule:
1. M4.E can close only when:
   - all `M4E-B*` blockers are resolved,
   - DoD checks are green,
   - lane-health + run-scope artifacts exist locally and durably,
   - active-lane health verdict is deterministic and blocker-free.

M4.E planning status (historical pre-execution snapshot):
1. Prerequisite M4.D is closed green.
2. M4.E has been expanded to execution-grade with explicit pins, verification catalog, blocker taxonomy, and evidence contract.
3. Execution posture:
   - ready to execute fail-closed.

M4.E execution status (2026-02-24):
1. Attempt #1 (authoritative fail-closed):
   - execution id: `m4e_20260224T055735Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4e_20260224T055735Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4e_20260224T055735Z/`
   - result: `overall_pass=false`, `blockers=[M4E-B2,M4E-B3]`, `next_gate=BLOCKED`.
   - blocker detail:
     - ingress probes failed because `IG_BASE_URL` remained templated (`{api_id}`) and produced invalid probe endpoints.
2. Remediation #1 applied:
   - pinned `SSM_IG_API_KEY_PATH` explicitly in handles registry,
   - repinned `IG_BASE_URL` from template to concrete endpoint.
3. Attempt #2 (authoritative fail-closed):
   - execution id: `m4e_20260224T055944Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4e_20260224T055944Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4e_20260224T055944Z/`
   - result: `overall_pass=false`, `blockers=[M4E-B2,M4E-B3]`, `next_gate=BLOCKED`.
   - blocker detail:
     - ingress paths returned `404` because API stage `v1` plus route keys prefixed with `/v1` caused effective `/v1/v1/...` drift.
4. Remediation #2 applied (structural, IaC):
   - runtime route keys changed to stage-safe paths:
     - `GET /ops/health`
     - `POST /ingest/push`
   - IG Lambda route matching aligned to `/ops/health` and `/ingest/push`.
   - handle contract aligned:
     - `IG_BASE_URL = https://<api-id>.execute-api.eu-west-2.amazonaws.com/v1`
     - `IG_HEALTHCHECK_PATH = /ops/health`
     - `IG_INGEST_PATH = /ingest/push`.
5. Attempt #3 (authoritative closure run):
   - execution id: `m4e_20260224T060311Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4e_20260224T060311Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4e_20260224T060311Z/`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.E_READY`.
   - key metrics:
     - `active_lane_count=5`
     - `healthy_lane_count=5`
     - `probe_count=19`
     - `failed_probe_count=0`
     - `run_scope_pass=true`
     - `runtime_stability_pass=true`.
6. M4.E closure posture:
   - `M4.E` is closed green.

### M4.F Correlation + Telemetry Continuity
Goal:
1. prove cross-runtime correlation fields survive runtime boundaries.

Tasks:
1. validate required correlation fields at runtime boundaries:
   - ingress edge boundary (API Gateway -> Lambda),
   - orchestration boundary (Step Functions execution input),
   - evidence emission boundary (M4.F artifact payload).
2. validate telemetry heartbeat and log/metric surfaces for active M4.B lanes.
3. classify propagation/surface drift with explicit fail-closed blockers.
4. publish correlation conformance artifacts locally and durably.

DoD:
- [x] required correlation fields are preserved across runtime boundaries.
- [x] telemetry surfaces for required lanes are present.
- [x] conformance snapshot is durable.

M4.F planning precheck (decision completeness):
1. Required upstream dependency:
   - latest M4.E execution summary is PASS (`m4e_20260224T060311Z`).
2. Active lane manifest is fixed by M4.B:
   - `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/m4b_runtime_path_manifest.json`.
3. Correlation handles are explicit and pinned:
   - `CORRELATION_REQUIRED_FIELDS`
   - `CORRELATION_HEADERS_REQUIRED`
   - `CORRELATION_MODE`
   - `CORRELATION_ENFORCEMENT_FAIL_CLOSED`
   - `CORRELATION_AUDIT_PATH_PATTERN`.
4. Runtime boundary handles are explicit:
   - ingress: `IG_BASE_URL`, `IG_INGEST_PATH`, `IG_AUTH_HEADER_NAME`, `SSM_IG_API_KEY_PATH`
   - orchestration: `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
   - observability: `CLOUDWATCH_LOG_GROUP_PREFIX`, `OTEL_ENABLED`, `OTEL_COLLECTOR_SERVICE`.
5. Security requirement:
   - no secret/token plaintext values may appear in M4.F artifacts.

M4.F decision pins (closed before execution):
1. Fail-closed correlation law:
   - any missing required correlation field at probed boundary is blocker-worthy.
2. Active-lane-only telemetry law:
   - telemetry surface checks are scoped to active M4.B lanes.
3. Ingress-proof sufficiency law:
   - ingress boundary proof requires runtime evidence of correlation carriage (not handle-only assertions).
4. Orchestrator-proof law:
   - Step Functions execution input must carry required correlation fields for probe execution.
5. Evidence-proof law:
   - M4.F artifacts must include correlation audit rows and pass/fail evaluation per boundary.
6. Secret-safe evidence law:
   - artifacts may include path/name metadata but never secret values.

M4.F verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4F-V1-M4E-GATE` | verify `runs/dev_substrate/dev_full/m4/m4e_20260224T060311Z/m4e_execution_summary.json` has `overall_pass=true` | enforces M4.F entry gate |
| `M4F-V2-HANDLE-CORRELATION-CLOSURE` | parse correlation handles and fail on unresolved values | validates contract closure |
| `M4F-V3-INGRESS-CORRELATION-PROBE` | POST probe payload with required fields/headers to IG endpoint and validate runtime response/log evidence | validates ingress boundary correlation carriage |
| `M4F-V4-ORCHESTRATOR-CORRELATION-PROBE` | start/describe Step Functions probe execution with required fields | validates orchestrator boundary carriage |
| `M4F-V5-TELEMETRY-SURFACE-CHECK` | verify log/metric surfaces for active lanes (`logs describe-log-groups`, lane-specific control-plane checks) | validates telemetry surfaces |
| `M4F-V6-SNAPSHOT-WRITE` | emit local M4.F artifacts under `runs/dev_substrate/dev_full/m4/<m4f_execution_id>/` | guarantees local audit surfaces |
| `M4F-V7-DURABLE-PUBLISH` | publish `m4f_*` artifacts to `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4f_execution_id>/` | guarantees durable evidence |

M4.F blocker taxonomy (fail-closed):
1. `M4F-B1`: M4.E gate missing/non-pass.
2. `M4F-B2`: required correlation handle missing/unresolved.
3. `M4F-B3`: ingress boundary correlation propagation failure.
4. `M4F-B4`: orchestrator boundary correlation propagation failure.
5. `M4F-B5`: telemetry heartbeat/surface missing for active lane scope.
6. `M4F-B6`: durable publish/readback failure for M4.F artifacts.
7. `M4F-B7`: secret/credential leakage detected in M4.F artifacts.

M4.F evidence contract (planned):
1. `m4f_correlation_audit_snapshot.json`
2. `m4f_telemetry_surface_snapshot.json`
3. `m4f_correlation_conformance_snapshot.json`
4. `m4f_execution_summary.json`

M4.F closure rule:
1. M4.F can close only when:
   - all `M4F-B*` blockers are resolved,
   - DoD checks are green,
   - conformance artifacts exist locally and durably,
   - correlation boundary checks are explicit and blocker-free.

M4.F planning status (historical pre-execution snapshot):
1. Prerequisite M4.E is closed green.
2. M4.F has been expanded to execution-grade with explicit pins, verification catalog, blocker taxonomy, and evidence contract.
3. Execution posture:
   - ready to execute fail-closed.

M4.F execution status (2026-02-24):
1. Attempt #1 (authoritative fail-closed):
   - execution id: `m4f_20260224T062413Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4f_20260224T062413Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4f_20260224T062413Z/`
   - result: `overall_pass=false`, `blockers=[M4F-B3,M4F-B5]`, `next_gate=BLOCKED`.
   - blocker details:
     - ingress boundary lacked runtime correlation proof surface (`correlation_echo` absent),
     - ingress telemetry heartbeat lacked correlation-bearing Lambda log evidence.
2. Remediation applied (runtime boundary instrumentation):
   - patched `infra/terraform/dev_full/runtime/lambda/ig_handler.py` to:
     - parse request body safely,
     - emit structured correlation-only logs (no raw payload/secret logging),
     - include bounded `correlation_echo` in ingest ACK.
   - applied runtime Terraform to materialize updated Lambda package.
3. Attempt #2 (authoritative closure run):
   - execution id: `m4f_20260224T062653Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4f_20260224T062653Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4f_20260224T062653Z/`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.F_READY`.
   - key metrics:
     - `required_field_count=6`
     - `required_header_count=5`
     - `ingress_boundary_pass=true`
     - `orchestrator_boundary_pass=true`
     - `telemetry_pass=true`
     - `active_lane_count=5`
     - `lane_surface_pass_count=5`.
4. M4.F closure posture:
   - `M4.F` is closed green.

### M4.G Failure/Recovery/Rollback Runtime Drill
Goal:
1. satisfy runtime six-proof obligations for P2 lane class.

Tasks:
1. execute bounded failure drill on selected active lane (`ingress_edge`).
2. execute deterministic recovery and rollback parity checks.
3. validate restored runtime health and run-scope/correlation continuity.
4. publish drill/recovery/rollback proof artifacts locally and durably.

DoD:
- [x] bounded failure drill artifact is committed.
- [x] recovery proof is committed.
- [x] rollback proof is committed.
- [x] post-drill runtime health remains green.

M4.G planning precheck (decision completeness):
1. Required upstream dependency:
   - latest M4.F execution summary is PASS (`m4f_20260224T062653Z`).
2. Active lane manifest is fixed by M4.B:
   - `runs/dev_substrate/dev_full/m4/m4b_20260224T044454Z/m4b_runtime_path_manifest.json`.
3. Drill lane handles are explicit and pinned:
   - `LAMBDA_IG_HANDLER_NAME`
   - `IG_BASE_URL`
   - `IG_HEALTHCHECK_PATH`
   - `IG_INGEST_PATH`
   - `IG_AUTH_HEADER_NAME`
   - `SSM_IG_API_KEY_PATH`.
4. Post-drill conformance anchors are explicit:
   - `CORRELATION_REQUIRED_FIELDS`
   - `CORRELATION_HEADERS_REQUIRED`
   - `CORRELATION_ENFORCEMENT_FAIL_CLOSED`.
5. Drill safety requirement:
   - failure injection must be bounded in time and fully reversible within this phase execution.

M4.G decision pins (closed before execution):
1. Bounded-failure law:
   - failure injection must be narrow and reversible; no destructive route/resource deletion.
2. Lane-selection law:
   - primary drill lane is `ingress_edge`; fallback lane selection requires explicit blocker adjudication.
3. Recovery law:
   - recovery is proven only by restored functional probes (`health + ingest`) and correlation carriage checks.
4. Rollback parity law:
   - post-drill control state must equal pre-drill state for injected control (`ReservedConcurrentExecutions`).
5. Secret-safe evidence law:
   - no secret values (API keys/tokens) in M4.G artifacts.

M4.G verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4G-V1-M4F-GATE` | verify `runs/dev_substrate/dev_full/m4/m4f_20260224T062653Z/m4f_execution_summary.json` has `overall_pass=true` | enforces M4.G entry gate |
| `M4G-V2-PRESTATE-CAPTURE` | `aws lambda get-function-concurrency --function-name <LAMBDA_IG_HANDLER_NAME>` plus baseline ingress probes | captures rollback anchor + baseline |
| `M4G-V3-FAILURE-INJECTION` | `aws lambda put-function-concurrency --reserved-concurrent-executions 0` | injects bounded ingress failure |
| `M4G-V4-FAILURE-OBSERVE` | probe IG health/ingest until bounded failure posture is observed | validates drill effectiveness |
| `M4G-V5-RECOVERY-ACTION` | restore prestate via `delete-function-concurrency` or original value set | performs deterministic recovery |
| `M4G-V6-RECOVERY-VERIFY` | rerun IG health/ingest + correlation checks | validates restored posture |
| `M4G-V7-ROLLBACK-PARITY` | compare post-state concurrency with pre-state anchor | validates rollback parity |
| `M4G-V8-PUBLISH` | publish `m4g_*` artifacts to run-control prefix | guarantees durable evidence |

M4.G blocker taxonomy (fail-closed):
1. `M4G-B1`: M4.F gate missing/non-pass.
2. `M4G-B2`: required drill handle missing/unresolved.
3. `M4G-B3`: bounded failure injection not effective/not observable.
4. `M4G-B4`: recovery action failed or recovery probes still degraded.
5. `M4G-B5`: rollback parity mismatch vs pre-drill state.
6. `M4G-B6`: post-drill run-scope/correlation regression detected.
7. `M4G-B7`: durable publish/readback failure for M4.G artifacts.
8. `M4G-B8`: secret/credential leakage detected in M4.G artifacts.

M4.G evidence contract (planned):
1. `m4g_failure_injection_snapshot.json`
2. `m4g_recovery_rollback_snapshot.json`
3. `m4g_runtime_drill_snapshot.json`
4. `m4g_execution_summary.json`

M4.G closure rule:
1. M4.G can close only when:
   - all `M4G-B*` blockers are resolved,
   - DoD checks are green,
   - drill/recovery/rollback artifacts exist locally and durably,
   - post-drill runtime posture is equivalent to pre-drill baseline.

M4.G planning status (historical pre-execution snapshot):
1. Prerequisite M4.F is closed green.
2. M4.G has been expanded to execution-grade with explicit drill law, blocker taxonomy, and evidence contract.
3. Execution posture:
   - ready to execute fail-closed.

M4.G execution status (2026-02-24):
1. Attempt #1 (authoritative closure run):
   - execution id: `m4g_20260224T063238Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4g_20260224T063238Z/`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4g_20260224T063238Z/`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.G_READY`.
2. Drill details:
   - selected lane: `ingress_edge`,
   - prestate: Lambda reserved concurrency `UNSET`,
   - bounded failure injection: `put-function-concurrency=0`,
   - failure observed within bounded window (`HTTP 503` on ingest probe),
   - recovery action: `delete-function-concurrency`,
   - rollback parity: pre/post state match (`UNSET`).
3. Post-drill conformance:
   - health probe restored (`200`),
   - ingest probe restored (`202`) with valid `correlation_echo`,
   - correlation-bearing Lambda log proof present.
4. M4.G closure posture:
   - `M4.G` is closed green.

### M4.H Runtime Readiness Evidence Publication
Goal:
1. publish canonical M4 readiness evidence for downstream gates.

Tasks:
1. assemble run-scoped P2 readiness payload from M4.A..M4.G authoritative artifacts.
2. validate payload completeness, reference readability, and non-secret policy.
3. publish run-scoped readiness artifact + binding matrix locally and durably.
4. publish M4.H control snapshot and execution summary.

DoD:
- [x] readiness payload is complete and reference-valid.
- [x] durable publication succeeds.
- [x] M4.H publication snapshot is committed.

M4.H planning precheck (decision completeness):
1. Required upstream dependencies:
   - latest M4.F execution summary is PASS (`m4f_20260224T062653Z`),
   - latest M4.G execution summary is PASS (`m4g_20260224T063238Z`).
2. Required source artifacts are explicit and readable:
   - `m4a_20260224T043334Z/m4a_execution_summary.json`
   - `m4b_20260224T044454Z/m4b_runtime_path_manifest.json`
   - `m4c_20260224T051711Z/m4c_execution_summary.json`
   - `m4d_20260224T054449Z/m4d_execution_summary.json`
   - `m4e_20260224T060311Z/m4e_execution_summary.json`
   - `m4e_20260224T060311Z/m4e_run_scope_binding_matrix.json`
   - `m4f_20260224T062653Z/m4f_execution_summary.json`
   - `m4f_20260224T062653Z/m4f_correlation_audit_snapshot.json`
   - `m4g_20260224T063238Z/m4g_execution_summary.json`
   - `m4g_20260224T063238Z/m4g_runtime_drill_snapshot.json`.
3. Run-scoped publication targets are explicit and pinned:
   - `P2_RUNTIME_READINESS_PATH_PATTERN`
   - `P2_RUNTIME_BINDING_MATRIX_PATH_PATTERN`
   - `S3_RUN_CONTROL_ROOT_PATTERN`.
4. Identity anchors are explicit:
   - `platform_run_id` and `scenario_run_id` from M3 handoff.
5. Security requirement:
   - no secret/token plaintext values may appear in readiness artifacts/snapshots.

M4.H decision pins (closed before execution):
1. Authoritative-source law:
   - M4.H uses closure-pass outputs only (blocked attempts remain audit-only references).
2. Run-scoped-first law:
   - canonical readiness publication target is run-scoped evidence path (`evidence/runs/{platform_run_id}/operate/...`).
3. Binding-explicitness law:
   - readiness publication must include explicit runtime binding matrix, not implicit references.
4. Invariant law:
   - publication fails closed if any upstream M4.A..M4.G pass predicate is false or unreadable.
5. Non-secret artifact law:
   - readiness payload may include IDs, ARNs, and references, but never secret values.

M4.H verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4H-V1-M4F-GATE` | verify `runs/dev_substrate/dev_full/m4/m4f_20260224T062653Z/m4f_execution_summary.json` has `overall_pass=true` | enforces M4.H source gate #1 |
| `M4H-V2-M4G-GATE` | verify `runs/dev_substrate/dev_full/m4/m4g_20260224T063238Z/m4g_execution_summary.json` has `overall_pass=true` | enforces M4.H source gate #2 |
| `M4H-V3-READINESS-ASSEMBLY` | assemble `runtime_lanes_ready.json` + `runtime_binding_matrix.json` from authoritative source artifacts | builds canonical run-scoped readiness payload |
| `M4H-V4-REFERENCE-READABILITY` | validate all source anchors and emitted target refs are readable | enforces reference integrity |
| `M4H-V5-NONSECRET-POLICY` | run secret-pattern scan over M4.H artifacts | enforces artifact hygiene |
| `M4H-V6-DURABLE-RUNSCOPED-PUBLISH` | publish run-scoped readiness outputs to `evidence/runs/{platform_run_id}/operate/` | commits canonical readiness evidence |
| `M4H-V7-DURABLE-CONTROL-PUBLISH` | publish `m4h_*` snapshots to `evidence/dev_full/run_control/{phase_execution_id}/` | commits M4 control evidence |

M4.H blocker taxonomy (fail-closed):
1. `M4H-B1`: source gate drift (`M4.F` or `M4.G` missing/non-pass).
2. `M4H-B2`: readiness payload missing required fields or source anchors.
3. `M4H-B3`: readiness/binding reference readability failure.
4. `M4H-B4`: run-scoped durable publication failure.
5. `M4H-B5`: control snapshot durable publication failure.
6. `M4H-B6`: non-secret policy violation in M4.H artifacts.

M4.H evidence contract (planned):
1. `runtime_lanes_ready.json` (run-scoped)
2. `runtime_binding_matrix.json` (run-scoped)
3. `m4h_readiness_publication_snapshot.json`
4. `m4h_execution_summary.json`

M4.H closure rule:
1. M4.H can close only when:
   - all `M4H-B*` blockers are resolved,
   - DoD checks are green,
   - run-scoped readiness artifacts and control snapshots exist locally and durably,
   - readiness payload is reference-valid and non-secret.

M4.H planning status (current):
1. Prerequisite M4.F and M4.G are closed green.
2. M4.H has been expanded to execution-grade with explicit publication targets, blocker taxonomy, and evidence contract.
3. Execution posture:
   - ready to execute fail-closed.

M4.H execution status (2026-02-24):
1. Attempt #1 (authoritative closure run):
   - execution id: `m4h_20260224T063724Z`
   - local evidence: `runs/dev_substrate/dev_full/m4/m4h_20260224T063724Z/`
   - durable run-scoped evidence:
     - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/operate/runtime_lanes_ready.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/operate/runtime_binding_matrix.json`
   - durable control evidence:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4h_20260224T063724Z/m4h_readiness_publication_snapshot.json`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4h_20260224T063724Z/m4h_execution_summary.json`
   - result: `overall_pass=true`, `blockers=[]`, `next_gate=M4.H_READY`.
2. Closure metrics:
   - `source_artifact_count=10`
   - `active_lane_count=5`
   - `invariants_pass_count=4/4`.
3. M4.H closure posture:
   - `M4.H` is closed green.

### M4.I Pass Gates + Blocker Rollup + Verdict
Goal:
1. adjudicate M4 closure using M4.A..M4.H evidence.

Tasks:
1. evaluate pass predicates for each M4 lane.
2. aggregate unresolved blockers with severity.
3. produce deterministic M4 verdict.
4. publish M4.I rollup + verdict artifact.

DoD:
- [x] pass predicate matrix is complete.
- [x] unresolved blocker set is explicit.
- [x] deterministic verdict artifact is committed.

M4.I planning precheck (decision completeness):
1. Upstream evidence must be present and readable:
   - M4.A..M4.H `m4*_execution_summary.json` artifacts.
2. Rollup policy source must be explicit:
   - M4 blocker taxonomy in Section 6 is authoritative for phase-level adjudication.
3. Verdict vocabulary must be pinned before execution:
   - `ADVANCE_TO_M4J`, `HOLD_REMEDIATE`, `NO_GO_RESET_REQUIRED`.
4. Fail-closed posture:
   - missing evidence, inconsistent blocker state, or ambiguous severity produces non-advance verdict.

M4.I decision pins (closed before execution):
1. Completeness-first law:
   - no adjudication if any required M4.A..M4.H summary/evidence artifact is missing.
2. Blocker severity law:
   - `S1` blockers are hard no-go for M4 closure.
   - `S2` blockers allow only hold/remediate posture, never direct advance.
3. Chain integrity law:
   - each subphase must report `overall_pass=true` for advance path.
4. Deterministic verdict law:
   - given identical input artifacts, verdict output is byte-deterministic.
5. Explicit unresolved-set law:
   - unresolved blockers are enumerated explicitly (no implicit/empty inference).
6. Durable publish law:
   - rollup artifacts must exist locally and in run-control durable mirror before closure.

M4.I verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4I-V1-UPSTREAM-SUMMARIES` | verify presence/readability of M4.A..M4.H execution summaries under `runs/dev_substrate/dev_full/m4/<execution_id>/` | proves required source evidence exists |
| `M4I-V2-UPSTREAM-GREEN` | parse summaries and assert `overall_pass=true` for all required subphases | validates green chain integrity |
| `M4I-V3-BLOCKER-ROLLUP` | aggregate blockers from subphase summaries and classify by severity | produces adjudication input set |
| `M4I-V4-MATRIX-BUILD` | build `m4i_gate_rollup_matrix.json` with phase/DoD/blocker status | creates canonical rollup matrix |
| `M4I-V5-REGISTER-BUILD` | build `m4i_blocker_register.json` with unresolved/closed sets and rationale | creates explicit blocker ledger |
| `M4I-V6-VERDICT-BUILD` | build `m4i_phase_verdict.json` from matrix + blocker register | emits deterministic rollup verdict |
| `M4I-V7-DURABLE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4i_execution_id>/...` | publishes durable M4.I evidence |

M4.I blocker taxonomy (fail-closed):
1. `M4I-B1`: one or more required upstream artifacts missing/unreadable.
2. `M4I-B2`: one or more upstream phases not green.
3. `M4I-B3`: blocker severity classification ambiguous/incomplete.
4. `M4I-B4`: rollup matrix missing required sections or inconsistent with source summaries.
5. `M4I-B5`: blocker register unresolved set missing/implicit.
6. `M4I-B6`: deterministic verdict build failed or non-repeatable.
7. `M4I-B7`: durable publish/readback failed for M4.I artifacts.
8. `M4I-B8`: verdict indicates unresolved blockers but advance path still emitted.

M4.I evidence contract (planned):
1. `m4i_gate_rollup_matrix.json`
2. `m4i_blocker_register.json`
3. `m4i_phase_verdict.json`
4. `m4i_execution_summary.json`

M4.I closure rule:
1. M4.I can close only when:
   - all `M4I-B*` blockers are resolved,
   - DoD checks are green,
   - rollup matrix + blocker register + verdict artifacts are present locally and durably,
   - verdict is deterministic and consistent with blocker register.

M4.I planning status (current):
1. Prerequisite lanes `M4.A`..`M4.H` are closed green.
2. M4.I is expanded to execution-grade with explicit blocker taxonomy and evidence contract.
3. Execution posture:
   - planning expanded; execution closed green.

M4.I execution status (2026-02-24):
1. Authoritative execution id:
   - `m4i_20260224T064331Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m4/m4i_20260224T064331Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4i_20260224T064331Z/`
4. PASS artifacts:
   - `m4i_gate_rollup_matrix.json`
   - `m4i_blocker_register.json`
   - `m4i_phase_verdict.json`
   - `m4i_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M4.I_READY`
   - verdict: `ADVANCE_TO_M4J`
   - upstream chain rollup: `8/8` green (`M4.A..M4.H`).

### M4.J M5 Handoff Artifact Publication
Goal:
1. publish M5 entry handoff only when M4 verdict allows progression.

Tasks:
1. build `m5_handoff_pack.json` with run-scope and evidence refs.
2. validate referenced artifacts are readable.
3. publish handoff locally and durably.
4. append closure note to master plan + impl map + logbook.

DoD:
- [x] `m5_handoff_pack.json` committed locally and durably.
- [x] M4 closure notes appended to required docs.
- [x] M5 entry marker is explicit and deterministic.

M4.J planning precheck (decision completeness):
1. Required upstream closure artifacts must exist and be readable:
   - `m4i_phase_verdict.json` with verdict outcome from M4.I.
   - `m4i_execution_summary.json` (`overall_pass=true`).
   - M4.A..M4.I execution summaries.
2. M5 handoff dependencies must remain valid:
   - M3 run-scope handoff anchor: `m4_handoff_pack.json`.
   - M4.H run-scoped readiness artifacts:
     - `runtime_lanes_ready.json`
     - `runtime_binding_matrix.json`.
3. Verdict vocabulary and transition law must be explicit:
   - `ADVANCE_TO_M5`, `HOLD_REMEDIATE`, `NO_GO_RESET_REQUIRED`.
4. Publication targets must be explicit and pinned:
   - `M4_EXECUTION_SUMMARY_PATH_PATTERN`
   - `M5_HANDOFF_PACK_PATH_PATTERN`
   - `S3_RUN_CONTROL_ROOT_PATTERN`.
5. Fail-closed posture:
   - if any unresolved M4 blocker remains, M4.J must not emit `ADVANCE_TO_M5`.

M4.J decision pins (closed before execution):
1. Adjudication inheritance law:
   - M4.J must inherit M4.I adjudication (`ADVANCE_TO_M4J`) as the primary gate input.
2. Closure consistency law:
   - `m4_execution_summary.json` verdict must be consistent with unresolved blocker register.
3. Transition law:
   - `ADVANCE_TO_M5` only when M4.A..M4.I are green and unresolved blockers are empty.
4. Handoff readiness law:
   - `m5_handoff_pack.json` must include references to M4.I verdict and M4.H readiness artifacts.
5. Determinism law:
   - M4 verdict payload built from explicit source set only (no ambient state inference).
6. Durable closure law:
   - closure artifacts must exist locally and durably before phase close.

M4.J verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M4J-V1-M4I-VERDICT` | verify `m4i_phase_verdict.json` exists and verdict is in allowed vocabulary | ensures adjudication input is valid |
| `M4J-V2-UPSTREAM-CHAIN` | verify M4.A..M4.I summaries are readable and green where required | validates closure chain integrity |
| `M4J-V3-HANDOFF-REFS` | verify `m4_handoff_pack.json` + M4.H readiness refs are readable and run-scope consistent | validates M5 dependency integrity |
| `M4J-V4-M4-SUMMARY-BUILD` | build `m4_execution_summary.json` from source summaries + adjudication result | emits canonical M4 closure summary |
| `M4J-V5-M5-HANDOFF-BUILD` | build `m5_handoff_pack.json` with refs to M4.I verdict + M4.H readiness | emits M5 transition marker |
| `M4J-V6-DURABLE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m4j_execution_id>/...` | publishes durable M4.J evidence |
| `M4J-V7-CONSISTENCY-CHECK` | verify `m4_execution_summary.verdict` and `m5_handoff_pack.m5_entry_ready` are blocker-consistent | prevents false advance |

M4.J blocker taxonomy (fail-closed):
1. `M4J-B1`: M4.I verdict artifact missing/unreadable/invalid.
2. `M4J-B2`: upstream M4 chain incomplete or non-green.
3. `M4J-B3`: unresolved M4 blocker set non-empty at closure attempt.
4. `M4J-B4`: M5 handoff dependencies missing/inconsistent.
5. `M4J-B5`: `m4_execution_summary.json` missing/invalid/inconsistent with source adjudication.
6. `M4J-B6`: `m5_handoff_pack.json` missing required references/fields.
7. `M4J-B7`: durable publish/readback failure for closure artifacts.
8. `M4J-B8`: transition verdict emitted as `ADVANCE_TO_M5` despite unresolved blockers.

M4.J evidence contract (planned):
1. `m4_execution_summary.json`
2. `m5_handoff_pack.json`
3. `m4j_execution_summary.json`

M4.J closure rule:
1. M4.J can close only when:
   - all `M4J-B*` blockers are resolved,
   - DoD checks are green,
   - closure artifacts exist locally and durably,
   - transition verdict is deterministic and blocker-consistent.

M4.J planning status (current):
1. Prerequisite lane `M4.I` is closed green with verdict `ADVANCE_TO_M4J`.
2. M4.J is expanded to execution-grade with explicit transition/blocker controls.
3. Execution posture:
   - planning expanded; execution closed green.

M4.J execution status (2026-02-24):
1. Authoritative execution id:
   - `m4j_20260224T064802Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m4/m4j_20260224T064802Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m4j_20260224T064802Z/`
4. PASS artifacts:
   - `m4_execution_summary.json`
   - `m5_handoff_pack.json`
   - `m4j_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M4.J_READY`
   - M4 verdict: `ADVANCE_TO_M5`
   - M5 entry readiness: `true`
   - upstream chain closure: `9/9` green (`M4.A..M4.I`).

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
9. `m4i_phase_verdict.json`
10. `m5_handoff_pack.json`

## 8) M4 Completion Checklist
- [x] M4.A complete
- [x] M4.B complete
- [x] M4.C complete
- [x] M4.D complete
- [x] M4.E complete
- [x] M4.F complete
- [x] M4.G complete
- [x] M4.H complete
- [x] M4.I complete
- [x] M4.J complete
- [x] M4 blockers resolved or explicitly fail-closed
- [x] M4 closure note appended in implementation map
- [x] M4 action log appended in logbook

## 9) Exit Criteria
M4 can close only when:
1. all checklist items in Section 8 are complete,
2. verdict is blocker-free and deterministic,
3. runtime readiness evidence is locally and durably readable,
4. `m5_handoff_pack.json` is committed and reference-valid.

Handoff posture:
1. M5 remains blocked until M4 verdict is `ADVANCE_TO_M5`.
2. Authoritative closure achieved at `m4j_20260224T064802Z` with verdict `ADVANCE_TO_M5`; M5 entry is now unblocked.
