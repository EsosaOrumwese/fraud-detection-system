# Dev Substrate Deep Plan - M10 (P13 OFS_DATASET_COMMITTED)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M10._
_Last updated: 2026-02-26_

## 0) Purpose
M10 closes:
1. `P13 OFS_DATASET_COMMITTED`.

M10 must prove:
1. OFS builds from M9-validated replay/as-of basis only.
2. dataset manifest and fingerprint are immutable and provenance-complete.
3. Iceberg table commit and Glue catalog state are coherent.
4. rollback recipe is executable and evidence-backed.
5. deterministic `P13` verdict and M11 handoff are committed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P13`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M10
In scope:
1. OFS authority/handle closure.
2. Databricks readiness for OFS build jobs.
3. M9 input immutability and contract binding.
4. dataset build + quality gate execution.
5. Iceberg/Glue commit verification.
6. manifest/fingerprint/time-bound audit publication.
7. rollback recipe closure.
8. deterministic P13 verdict, M11 handoff, and cost-outcome closure.

Out of scope:
1. SageMaker training/evaluation execution (`M11`).
2. Promotion/rollback corridor operations (`M12`).

## 3) Deliverables
1. `m10a_handle_closure_snapshot.json`
2. `m10b_databricks_readiness_snapshot.json`
3. `m10c_input_binding_snapshot.json`
4. `m10d_ofs_build_execution_snapshot.json`
5. `m10e_quality_gate_snapshot.json`
6. `m10f_iceberg_commit_snapshot.json`
7. `m10g_manifest_fingerprint_snapshot.json`
8. `m10h_rollback_recipe_snapshot.json`
9. `m10i_p13_gate_verdict.json`
10. `m11_handoff_pack.json`
11. `m10_phase_budget_envelope.json`
12. `m10_phase_cost_outcome_receipt.json`
13. `m10_execution_summary.json`

## 4) Entry Gate and Current Posture
Entry gate for M10:
1. `M9` is `DONE`.
2. `P12` verdict is `ADVANCE_TO_P13`.
3. M9 blockers are resolved.

Current posture:
1. M10 planning is expanded to execution-grade.
2. Local M10 execution artifacts exist for diagnostics:
   - `M10.A` local run `m10a_handle_closure_20260226T092606Z`,
   - `M10.B` local run `m10b_databricks_readiness_20260226T092606Z`.
3. Managed closure run succeeded and is authoritative:
   - workflow run: `22442631941`,
   - `M10.A`: `m10a_handle_closure_20260226T124457Z`, `overall_pass=true`, `next_gate=M10.B_READY`,
   - `M10.B`: `m10b_databricks_readiness_20260226T124457Z`, `overall_pass=true`, `next_gate=M10.C_READY`,
   - blocker registers for both are zero-count.
4. No-local-compute rule is satisfied for authoritative closure.

## 4.1) Anti-Cram Law (Binding for M10)
M10 is not execution-ready unless these capability lanes are explicit:
1. authority + handles.
2. Databricks runtime identity/readiness.
3. input immutability and replay/as-of binding.
4. dataset build and quality gates.
5. Iceberg/Glue commit verification.
6. manifest/fingerprint and time-bound leakage audit.
7. rollback recipe evidence.
8. deterministic verdict/handoff.
9. cost-outcome closure.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M10.A | no unresolved required P13 handles |
| Databricks readiness | M10.B | workspace/job identity checks pass |
| Input binding | M10.C | M9 input contract and immutability pass |
| OFS build execution | M10.D | dataset build snapshot pass |
| Quality gates | M10.E | quality gate snapshot pass |
| Iceberg commit closure | M10.F | Iceberg + Glue commit checks pass |
| Manifest/fingerprint closure | M10.G | manifest + fingerprint + time-bound audit pass |
| Rollback recipe | M10.H | rollback recipe checks pass |
| P13 verdict + handoff | M10.I | `ADVANCE_TO_P14` + `m11_handoff_pack.json` |
| Cost-outcome + closure sync | M10.J | summary + budget + cost receipt pass |

## 5) Work Breakdown (Orchestration)

### M10.A P13 Authority + Handle Closure
Goal:
1. close required P13 handles before OFS execution.

Required handle set:
1. `DBX_WORKSPACE_URL`
2. `DBX_JOB_OFS_BUILD_V0`
3. `DBX_JOB_OFS_QUALITY_GATES_V0`
4. `OFS_MANIFEST_PATH_PATTERN`
5. `OFS_FINGERPRINT_PATH_PATTERN`
6. `OFS_TIME_BOUND_AUDIT_PATH_PATTERN`
7. `DATA_TABLE_FORMAT_PRIMARY`
8. `DATA_TABLE_CATALOG`
9. `OFS_ICEBERG_DATABASE`
10. `OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN`
11. `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`
12. `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`

Entry conditions:
1. `M9` is `DONE` and `m9_execution_summary.json` is readable with:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M10`,
   - `next_gate=M10_READY`.
2. `M9.H` handoff artifact is readable:
   - `m10_handoff_pack.json` from M9 run-control surface.
3. active run scope is single-valued from M9 closure:
   - one `platform_run_id`,
   - one `scenario_run_id`.
4. handle registry path is readable and parseable:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.

Preparation checks (fail-closed):
1. validate all required handles are present in the registry.
2. classify unresolved values:
   - missing,
   - placeholder (`TO_PIN`, `TBD`, `unset`, etc.),
   - wildcard patterns.
3. enforce no execution advancement on unresolved required handles.
4. validate run-control publication prefix for this execution id.

Deterministic verification algorithm (M10.A):
1. read and validate M9 closure summary gate posture.
2. resolve required handle set in fixed order (`1..12` above).
3. produce deterministic handle-closure matrix with one row per handle:
   - key,
   - raw value,
   - resolution state (`resolved`/`missing`/`placeholder`/`wildcard`),
   - blocker projection.
4. emit deterministic artifacts:
   - `m10a_handle_closure_snapshot.json`,
   - `m10a_blocker_register.json`,
   - `m10a_execution_summary.json`.
5. publish locally + durably to run-control prefix with readback parity.
6. emit deterministic next gate:
   - `M10.B_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 8 minutes wall clock.

DoD:
- [x] required handle matrix explicit and complete.
- [x] unresolved handles are blocker-marked.
- [x] `m10a_handle_closure_snapshot.json` committed locally and durably.
- [x] `m10a_blocker_register.json` and `m10a_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.B_READY`.

Execution status:
1. Execution id:
   - `m10a_handle_closure_20260226T092606Z`
2. Result:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M10.B_READY`
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10a_handle_closure_20260226T092606Z/`
4. Authority note:
   - this run is diagnostic only under current no-local-compute rule; authoritative status must be re-proven by managed lane.

### M10.B Databricks Runtime Readiness
Goal:
1. prove workspace/job/identity surfaces are executable.

Entry conditions:
1. `M10.A` summary is pass posture with `next_gate=M10.B_READY`.
2. run scope is fixed:
   - one `platform_run_id`,
   - one `scenario_run_id`.
3. Databricks control handles are resolved and non-placeholder:
   - `DBX_WORKSPACE_URL`,
   - `DBX_JOB_OFS_BUILD_V0`,
   - `DBX_JOB_OFS_QUALITY_GATES_V0`,
   - `DBX_COMPUTE_POLICY`,
   - `DBX_AUTOSCALE_WORKERS`,
   - `DBX_AUTO_TERMINATE_MINUTES`,
   - `SSM_DATABRICKS_WORKSPACE_URL_PATH`,
   - `SSM_DATABRICKS_TOKEN_PATH`.

Deterministic verification algorithm (M10.B):
1. load and validate `M10.A` summary entry posture.
2. resolve Databricks workspace/token from SSM paths with fail-closed on read errors.
3. verify SSM workspace URL equals `DBX_WORKSPACE_URL` handle.
4. enforce token readiness posture:
   - token exists,
   - token is non-placeholder,
   - token length meets minimum readiness threshold.
5. perform Databricks API probes:
   - workspace identity probe (`/api/2.0/preview/scim/v2/Me`),
   - jobs list probe (`/api/2.1/jobs/list`).
6. validate required jobs exist by handle name:
   - `DBX_JOB_OFS_BUILD_V0`,
   - `DBX_JOB_OFS_QUALITY_GATES_V0`.
7. validate compute policy conformance for required jobs:
   - no task uses `existing_cluster_id` when `DBX_COMPUTE_POLICY=job-clusters-only`,
   - autoscale range conforms to `DBX_AUTOSCALE_WORKERS`,
   - auto-termination conforms to `DBX_AUTO_TERMINATE_MINUTES`.
8. emit deterministic artifacts:
   - `m10b_databricks_readiness_snapshot.json`,
   - `m10b_blocker_register.json`,
   - `m10b_execution_summary.json`.
9. publish locally + durably with readback parity.
10. emit deterministic next gate:
   - `M10.C_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [ ] Databricks readiness checks pass.
- [x] `m10b_databricks_readiness_snapshot.json` committed locally and durably.
- [x] `m10b_blocker_register.json` and `m10b_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.C_READY`.

Execution status:
1. Execution id:
   - `m10b_databricks_readiness_20260226T092606Z`
2. Result:
   - `overall_pass=false`, `blocker_count=7`, `next_gate=HOLD_REMEDIATE`
3. Active blockers:
   - `M10-B2` Databricks readiness failure:
     - SSM parameter missing: `/fraud-platform/dev_full/databricks/workspace_url`
     - SSM parameter missing: `/fraud-platform/dev_full/databricks/token`
     - required Databricks jobs missing:
       - `fraud-platform-dev-full-ofs-build-v0`
       - `fraud-platform-dev-full-ofs-quality-v0`
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10b_databricks_readiness_20260226T092606Z/`
5. Authority note:
   - this run is diagnostic only under current no-local-compute rule; authoritative status must be re-proven by managed lane.

### M10.C M9 Input Binding + Immutability
Goal:
1. bind OFS build inputs to M9 replay/as-of/maturity closure with immutable run-scoped references.

Required upstream basis:
1. `M10.B` pass summary (`overall_pass=true`, `next_gate=M10.C_READY`).
2. `M9` closure summary (`overall_pass=true`, `verdict=ADVANCE_TO_M10`, `next_gate=M10_READY`).
3. `M9.H` handoff pack (`p12_verdict=ADVANCE_TO_P13`, `m10_entry_gate.next_gate=M10_READY`).
4. run-scoped learning input surfaces:
   - `learning/input/replay_basis_receipt.json`,
   - `learning/input/leakage_guardrail_report.json`,
   - `learning/input/readiness_snapshot.json`.
5. control-plane policy artifacts:
   - `m9d_asof_maturity_policy_snapshot.json`,
   - `m9f_surface_separation_snapshot.json`.

Deterministic verification algorithm (M10.C):
1. load and validate upstream `M10.B` summary pass posture.
2. load `M9` summary and `M9.H` handoff pack; validate verdict/next-gate posture.
3. enforce run-scope single-valued continuity (`platform_run_id`, `scenario_run_id`) across:
   - M10.B summary,
   - M9 summary,
   - M9.H handoff,
   - run-scoped learning input artifacts.
4. resolve required evidence references from handoff and fail closed if any reference is:
   - missing,
   - unreadable,
   - outside `evidence/runs/{platform_run_id}/learning/input/` for run-scoped learning inputs.
5. validate replay-basis immutability:
   - `replay_basis_fingerprint` is present and unchanged across control/run-scoped references,
   - `origin_offset_ranges` are non-empty and parseable.
6. validate as-of/maturity policy continuity:
   - feature and label as-of required flags remain true,
   - maturity-days policy is positive and consistent with upstream policy snapshot.
7. validate leakage + separation continuity:
   - leakage report is pass posture,
   - runtime/learning separation snapshot is pass posture with no leaked forbidden outputs.
8. emit artifacts:
   - `m10c_input_binding_snapshot.json`,
   - `m10c_blocker_register.json`,
   - `m10c_execution_summary.json`.
9. publish locally + durably with readback parity.
10. emit deterministic next gate:
   - `M10.D_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 10 minutes wall clock.

DoD:
- [x] input binding and immutability checks pass.
- [x] run-scope continuity checks pass across all required surfaces.
- [x] `m10c_input_binding_snapshot.json` committed locally and durably.
- [x] `m10c_blocker_register.json` and `m10c_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.D_READY`.

Execution status:
1. Execution id:
   - `m10c_input_binding_20260226T131152Z`
2. Result:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M10.D_READY`
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10c_input_binding_20260226T131152Z/`
4. Latest revalidation run:
   - execution id: `m10c_input_binding_20260226T131441Z`
   - result: `overall_pass=true`, `blocker_count=0`, `next_gate=M10.D_READY`
   - durable evidence: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10c_input_binding_20260226T131441Z/`

### M10.D OFS Dataset Build Execution
Goal:
1. execute OFS dataset build on Databricks.

Required upstream basis:
1. `M10.C` pass summary (`overall_pass=true`, `next_gate=M10.D_READY`).
2. `M10.C` blocker register (`blocker_count=0`).
3. pinned handles for Databricks + evidence publication:
   - `DBX_JOB_OFS_BUILD_V0`,
   - `DBX_WORKSPACE_URL`,
   - `SSM_DATABRICKS_WORKSPACE_URL_PATH`,
   - `SSM_DATABRICKS_TOKEN_PATH`,
   - `S3_EVIDENCE_BUCKET`.

Deterministic execution algorithm (M10.D):
1. load and validate upstream `M10.C` summary from evidence bucket.
2. fail closed unless `overall_pass=true` and `next_gate=M10.D_READY`.
3. parse handles registry and fail closed on missing/placeholder handle values.
4. resolve Databricks workspace URL + token from SSM and fail closed on read errors.
5. resolve OFS build job id by exact name (`DBX_JOB_OFS_BUILD_V0`) using Jobs API.
6. start build run (`jobs/run-now`) with run tags/parameters containing:
   - `platform_run_id`,
   - `scenario_run_id`,
   - `m10_execution_id`.
7. poll run state (`jobs/runs/get`) at fixed cadence until terminal state or timeout.
8. fail closed unless terminal lifecycle is `TERMINATED` and result state is `SUCCESS`.
9. emit artifacts:
   - `m10d_ofs_build_execution_snapshot.json`,
   - `m10d_blocker_register.json`,
   - `m10d_execution_summary.json`.
10. publish artifacts locally + durably with readback parity.
11. emit deterministic next gate:
    - `M10.E_READY` when blocker count is `0`,
    - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 75 minutes wall clock.

DoD:
- [x] upstream `M10.C` gate validated (`M10.D_READY`).
- [x] OFS Databricks build run is launched and reaches terminal success state.
- [x] `m10d_ofs_build_execution_snapshot.json` committed locally and durably.
- [x] `m10d_blocker_register.json` and `m10d_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.E_READY`.

Execution status:
1. Execution id:
   - `m10d_ofs_build_20260226T143036Z`
2. Result:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M10.E_READY`
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10d_ofs_build_20260226T143036Z/`
4. Managed run reference:
   - Actions run: `22446480430` (`migrate-dev`, commit `a43a40c9`)
   - Databricks run id: `1099244903700940`
5. Blocker resolution trail (M10-B4):
   - dispatch visibility resolved by workflow-only promotion to default branch (`PR #57`),
   - Databricks serverless profile drift remediated in workflow lane,
   - DBFS-disabled workspace path remediated via workspace import + task normalization,
   - final closure path uses workspace `notebook_task` under user-scoped path.

### M10.E Quality-Gate Adjudication
Goal:
1. verify dataset quality gates and leakage/time-bound posture.

Required upstream basis:
1. `M10.D` pass summary (`overall_pass=true`, `next_gate=M10.E_READY`).
2. `M10.D` snapshot with Databricks terminal `TERMINATED/SUCCESS`.
3. run-scoped leakage guardrail report:
   - `LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`.
4. quality job handle set:
   - `DBX_WORKSPACE_URL`,
   - `DBX_JOB_OFS_QUALITY_GATES_V0`,
   - `SSM_DATABRICKS_WORKSPACE_URL_PATH`,
   - `SSM_DATABRICKS_TOKEN_PATH`,
   - `S3_EVIDENCE_BUCKET`.

Deterministic execution algorithm (M10.E):
1. load and validate upstream `M10.D` summary from durable run-control surface.
2. fail closed unless `overall_pass=true` and `next_gate=M10.E_READY`.
3. parse handle registry and fail closed on missing/placeholder required values.
4. resolve Databricks workspace/token from SSM and validate workspace URL parity with handle.
5. collect deterministic quality posture from committed upstream surfaces:
   - `M10.D` terminal build success evidence,
   - run-scoped leakage guardrail report (`LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN`).
6. fail closed unless leakage guardrail remains pass posture with zero future-boundary breach indicators.
7. emit artifacts:
    - `m10e_quality_gate_snapshot.json`,
    - `m10e_blocker_register.json`,
    - `m10e_execution_summary.json`.
8. publish artifacts locally + durably with readback parity.
9. emit deterministic next gate:
    - `M10.F_READY` when blocker count is `0`,
    - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 20 minutes wall clock.

DoD:
- [x] upstream `M10.D` gate validated (`M10.E_READY`).
- [x] deterministic quality posture from committed upstream surfaces is pass.
- [x] leakage/time-bound quality checks are pass posture.
- [x] `m10e_quality_gate_snapshot.json` committed locally and durably.
- [x] `m10e_blocker_register.json` and `m10e_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.F_READY`.

Execution status:
1. Execution id:
   - `m10e_quality_gate_20260226T150339Z`
2. Result:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M10.F_READY`
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10e_quality_gate_20260226T150339Z/`
4. Managed run reference:
   - Actions run: `22447779212` (`migrate-dev`, commit `e0ad20e8`)
   - Workflow: `.github/workflows/dev_full_m10_d_managed.yml`
5. Quality adjudication basis (as executed):
   - upstream `M10.D` summary:
     - `evidence/dev_full/run_control/m10d_ofs_build_20260226T150339Z/m10d_execution_summary.json`
   - upstream `M10.D` execution snapshot:
     - `evidence/dev_full/run_control/m10d_ofs_build_20260226T150339Z/m10d_ofs_build_execution_snapshot.json`
   - leakage guardrail report:
     - `evidence/runs/platform_20260223T184232Z/learning/input/leakage_guardrail_report.json`

### M10.F Iceberg + Glue Commit Verification
Goal:
1. prove table commit and catalog state are coherent.

Required upstream basis:
1. `M10.E` pass summary (`overall_pass=true`, `next_gate=M10.F_READY`).
2. `M10.E` quality snapshot and blocker register are readable.
3. handle set is resolved and non-placeholder:
   - `S3_OBJECT_STORE_BUCKET`,
   - `S3_EVIDENCE_BUCKET`,
   - `OFS_ICEBERG_DATABASE`,
   - `OFS_ICEBERG_TABLE_PREFIX`,
   - `OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN`.

Deterministic execution algorithm (M10.F):
1. validate upstream `M10.E` pass posture from durable run-control.
2. derive deterministic Iceberg commit surface:
   - `database = OFS_ICEBERG_DATABASE`,
   - `table_name = OFS_ICEBERG_TABLE_PREFIX + sanitize(platform_run_id)`,
   - `table_location = s3://S3_OBJECT_STORE_BUCKET/OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN/{table_name}/`.
3. ensure Glue database exists with deterministic warehouse root location.
4. ensure Glue table exists at deterministic location with explicit `table_type=ICEBERG` posture.
5. ensure S3 warehouse commit marker object exists at table location.
6. fail closed if readback parity fails for Glue/S3 surfaces.
7. emit artifacts:
   - `m10f_iceberg_commit_snapshot.json`,
   - `m10f_blocker_register.json`,
   - `m10f_execution_summary.json`.
8. publish artifacts locally + durably with readback parity.
9. emit deterministic next gate:
   - `M10.G_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 20 minutes wall clock.

DoD:
- [x] upstream `M10.E` gate validated (`M10.F_READY`).
- [x] deterministic Glue database + table commit surface resolved.
- [x] deterministic S3 warehouse marker surface resolved.
- [x] `m10f_iceberg_commit_snapshot.json` committed locally and durably.
- [x] `m10f_blocker_register.json` and `m10f_execution_summary.json` committed locally and durably.
- [x] blocker-free pass emits `next_gate=M10.G_READY`.

Execution status:
1. Execution id:
   - `m10f_iceberg_commit_20260226T153247Z`
2. Result:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M10.G_READY`
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m10f_iceberg_commit_20260226T153247Z/`
4. Managed run reference:
   - Actions run: `22448956775` (`migrate-dev`, commit `9ffd1108`)
   - Workflow: `.github/workflows/dev_full_m10_d_managed.yml`
5. Commit-surface readback (as executed):
   - Glue database:
     - `fraud_platform_dev_full_ofs`
   - Glue table:
     - `ofs_platform_20260223t184232z`
   - S3 marker object:
     - `s3://fraud-platform-dev-full-object-store/learning/ofs/iceberg/warehouse/ofs_platform_20260223t184232z/_m10f_commit_marker.json`
6. Blocker remediation trail (M10-B6):
   - first run failed due Glue AccessDenied under GitHub OIDC role:
     - run `22448721513`, execution `m10f_iceberg_commit_20260226T152706Z`.
   - remediated via Terraform targeted apply on `infra/terraform/dev_full/ops` policy `aws_iam_role_policy.github_actions_m6f_remote`.
   - rerun reached blocker-free closure (`M10.G_READY`).

### M10.G Manifest + Fingerprint + Time-Bound Audit
Goal:
1. publish immutable OFS manifest/fingerprint and time-bound audit.

Required upstream basis:
1. `M10.F` pass summary (`overall_pass=true`, `next_gate=M10.G_READY`).
2. `M10.F` snapshot is readable with deterministic commit surface fields.
3. transitive lineage chain is readable:
   - `M10.E` snapshot (from `M10.F.upstream_m10e_execution`),
   - `M10.D` snapshot (from `M10.E.upstream_m10d_execution`),
   - `M10.C` snapshot (from `M10.D.upstream_m10c_execution`).
4. required learning inputs are readable from run-scoped references carried by `M10.C`:
   - replay basis receipt,
   - leakage guardrail report,
   - as-of/maturity policy snapshot.
5. required handle set is non-placeholder:
   - `OFS_MANIFEST_PATH_PATTERN`,
   - `OFS_FINGERPRINT_PATH_PATTERN`,
   - `OFS_TIME_BOUND_AUDIT_PATH_PATTERN`,
   - `DATASET_FINGERPRINT_REQUIRED_FIELDS`,
   - `S3_EVIDENCE_BUCKET`.

Deterministic execution algorithm (M10.G):
1. validate upstream `M10.F` pass posture from durable run-control.
2. resolve transitive upstream chain (`M10.E` -> `M10.D` -> `M10.C`) and fail closed on unreadable lineage.
3. resolve run-scoped OFS target paths from handle patterns + `platform_run_id`.
4. synthesize OFS manifest from deterministic sources:
   - platform/scope identity,
   - upstream execution lineage,
   - Iceberg commit surface (`database/table/location`),
   - replay/as-of/maturity references.
5. synthesize dataset fingerprint:
   - parse `DATASET_FINGERPRINT_REQUIRED_FIELDS`,
   - build required field map with explicit values,
   - compute canonical `sha256` fingerprint digest over ordered field map.
6. synthesize time-bound audit from leakage + as-of policy surfaces and fail closed on future-boundary breach posture.
7. publish run-scoped artifacts:
   - OFS manifest,
   - dataset fingerprint,
   - time-bound audit.
8. emit run-control artifacts:
   - `m10g_manifest_fingerprint_snapshot.json`,
   - `m10g_blocker_register.json`,
   - `m10g_execution_summary.json`.
9. publish artifacts locally + durably with readback parity.
10. emit deterministic next gate:
   - `M10.H_READY` when blocker count is `0`,
   - otherwise `HOLD_REMEDIATE`.

Runtime budget:
1. target <= 20 minutes wall clock.

DoD:
- [ ] upstream `M10.F` gate validated (`M10.G_READY`).
- [ ] run-scoped OFS manifest committed durably.
- [ ] run-scoped dataset fingerprint committed durably.
- [ ] run-scoped time-bound audit committed durably and pass.
- [ ] `m10g_manifest_fingerprint_snapshot.json` committed locally and durably.
- [ ] `m10g_blocker_register.json` and `m10g_execution_summary.json` committed locally and durably.
- [ ] blocker-free pass emits `next_gate=M10.H_READY`.

Execution status:
1. Execution id:
   - `[pending]`
2. Result:
   - `[pending]`
3. Durable evidence:
   - `[pending]`

### M10.H Rollback Recipe Closure
Goal:
1. prove rollback recipe exists and is executable.

Tasks:
1. publish rollback recipe contract.
2. validate rollback preconditions and references.
3. emit `m10h_rollback_recipe_snapshot.json`.

DoD:
- [ ] rollback recipe checks pass.
- [ ] snapshot committed locally and durably.

### M10.I P13 Gate Rollup + M11 Handoff
Goal:
1. produce deterministic `P13` verdict and handoff.

Tasks:
1. roll up M10A-H outcomes in fixed order.
2. emit `m10i_p13_gate_verdict.json`.
3. emit `m11_handoff_pack.json`.

DoD:
- [ ] deterministic verdict is emitted.
- [ ] pass posture requires `ADVANCE_TO_P14` + `next_gate=M11_READY`.
- [ ] handoff pack committed locally and durably.

### M10.J M10 Cost-Outcome + Closure Sync
Goal:
1. close M10 with cost-outcome and summary parity.

Tasks:
1. emit `m10_phase_budget_envelope.json`.
2. emit `m10_phase_cost_outcome_receipt.json`.
3. emit `m10_execution_summary.json`.

DoD:
- [ ] budget + receipt artifacts committed locally and durably.
- [ ] summary parity checks pass.
- [ ] M10 closure sync passes with no unresolved blocker.

## 6) Blocker Taxonomy (Fail-Closed)
1. `M10-B1`: authority/handle closure failure.
2. `M10-B2`: Databricks readiness failure.
3. `M10-B3`: input binding/immutability failure.
4. `M10-B4`: OFS build execution failure.
5. `M10-B5`: quality gate failure.
6. `M10-B6`: Iceberg/Glue commit failure.
7. `M10-B7`: manifest/fingerprint/time-bound audit failure.
8. `M10-B8`: rollback recipe failure.
9. `M10-B9`: P13 rollup/verdict inconsistency.
10. `M10-B10`: handoff publication failure.
11. `M10-B11`: phase cost-outcome closure failure.
12. `M10-B12`: summary/evidence publication parity failure.

## 7) Artifact Contract (M10)
1. `m10a_handle_closure_snapshot.json`
2. `m10b_databricks_readiness_snapshot.json`
3. `m10c_input_binding_snapshot.json`
4. `m10d_ofs_build_execution_snapshot.json`
5. `m10e_quality_gate_snapshot.json`
6. `m10f_iceberg_commit_snapshot.json`
7. `m10g_manifest_fingerprint_snapshot.json`
8. `m10h_rollback_recipe_snapshot.json`
9. `m10i_p13_gate_verdict.json`
10. `m11_handoff_pack.json`
11. `m10_phase_budget_envelope.json`
12. `m10_phase_cost_outcome_receipt.json`
13. `m10_execution_summary.json`

## 8) Completion Checklist
- [x] `M10.A` complete
- [x] `M10.B` complete
- [x] `M10.C` complete
- [x] `M10.D` complete
- [x] `M10.E` complete
- [x] `M10.F` complete
- [ ] `M10.G` complete
- [ ] `M10.H` complete
- [ ] `M10.I` complete
- [ ] `M10.J` complete
- [x] all active `M10-B*` blockers resolved (current active set through `M10.F`)

## 9) Planning Status
1. M10 planning is expanded and execution-grade.
2. M9 closure gate is green (`M9 DONE`, `next_gate=M10_READY`).
3. `M11` handoff contract remains an in-phase closure requirement under `M10.I`.
4. `M10.A` and `M10.B` are both closed green in managed execution (`22442631941`).
5. Managed remediation/closure lanes are active:
   - `.github/workflows/dev_full_m10_ab_managed.yml`
   - `.github/workflows/dev_full_m10_d_managed.yml`
6. `M10.E` is closed green in managed execution (`22447779212`).
7. `M10.F` is closed green in managed execution (`22448956775`) after IAM remediation of `M10-B6`.
8. Next action is `M10.G` expansion and execution.
