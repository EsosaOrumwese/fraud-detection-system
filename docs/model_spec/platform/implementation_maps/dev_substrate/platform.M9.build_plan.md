# Dev Substrate Deep Plan - M9 (P12 Teardown)
_Status source of truth: `platform.build_plan.md`_  
_This document provides deep planning detail for M9._  
_Last updated: 2026-02-19_

## 0) Purpose
M9 closes `P12 TEARDOWN` on managed substrate by proving:
1. Teardown is executed through managed control-plane lanes (no laptop secret-bearing destroy path).
2. Demo-scoped runtime resources are destroyed deterministically.
3. Residual-cost footguns are absent after teardown.
4. Demo-scoped secret surfaces are cleaned up.
5. Teardown proof and M10 handoff artifacts are published.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P12` section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md` (`M2.I` teardown lane contract)
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M8.build_plan.md` (`M8.I` handoff contract)
3. Existing teardown workflow lane:
   - `.github/workflows/dev_min_confluent_destroy.yml`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M9
In scope:
1. P12 authority/handle closure and teardown preserve-set freeze.
2. Confluent teardown using existing managed workflow lane.
3. Demo stack teardown execution on managed lane.
4. Post-destroy residual-resource checks.
5. Demo-scoped SSM secret cleanup verification.
6. Post-teardown budget/cost-guardrail snapshot.
7. Teardown-proof artifact publication and M10 handoff.

Out of scope:
1. Deleting retained S3 evidence/object-store buckets.
2. Learning/Registry rollout.
3. M10 semantic/scale certification runs.

## 3) M9 Deliverables
1. `M9.A` handle + handoff closure snapshot.
2. `M9.B` teardown inventory/preserve-set snapshot.
3. `M9.C` Confluent teardown workflow snapshot.
4. `M9.D` demo stack teardown workflow snapshot.
5. `M9.E` post-destroy residual-resource snapshot.
6. `M9.F` demo-secret cleanup snapshot.
7. `M9.G` cost-guardrail post-teardown snapshot.
8. `M9.H` teardown-proof artifact (`teardown_proof.json`) local + durable.
9. `M9.I` M9 verdict snapshot + M10 handoff pack.

## 4) Execution Gate for This Phase
Current posture:
1. `M8.I` verdict is `ADVANCE_TO_M9`.
2. `m9_handoff_pack.json` exists locally and durably.
3. M9 is active for planning/execution by explicit user direction.

Execution block:
1. No teardown execution starts until `M9.A` and `M9.B` close green.
2. No phase closure is allowed with unresolved residual-resource findings.
3. No M9 closure is allowed if demo-secret cleanup is ambiguous.

## 4.1) Decision Pin: Existing Destroy Workflow Reuse
1. M9 uses one canonical managed teardown workflow:
   - `.github/workflows/dev_min_confluent_destroy.yml`.
2. Teardown target is selected by workflow input:
   - `stack_target=confluent|demo`.
3. Lane split is logical, not file-based:
   - `M9.C` dispatches with `stack_target=confluent`,
   - `M9.D` dispatches with `stack_target=demo`.

## 4.2) Anti-Cram Law (Binding for M9)
1. M9 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - teardown inventory + preserve-set
   - managed teardown workflows
   - residual-resource verification
   - secret cleanup verification
   - post-teardown budget posture
   - teardown evidence + handoff
2. If a missing lane is discovered, execution pauses and plan expansion is mandatory before continuing.

## 4.3) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handoff closure | M9.A | M9.I | zero unresolved required P12 handles |
| Teardown target/preserve-set freeze | M9.B | M9.D/M9.E | explicit destroy-set and preserve-set contract |
| Confluent teardown execution | M9.C | M9.E | workflow result PASS + state/resource summary |
| Demo teardown execution | M9.D | M9.E | workflow result PASS + destroy summary |
| Residual-resource verification | M9.E | M9.I | no demo ECS services/tasks, no NAT/LB footguns |
| Demo-secret cleanup | M9.F | M9.I | demo-scoped SSM cleanup PASS |
| Post-teardown cost posture | M9.G | M9.I | guardrail snapshot PASS |
| Teardown proof publication | M9.H | M9.I | `teardown_proof.json` local + durable |
| Verdict + M10 handoff | M9.I | - | `ADVANCE_TO_M10` + durable handoff pack |

## 5) Work Breakdown (Deep)

### M9.A P12 Authority + Handoff Closure
Goal:
1. Resolve all required P12 handles before any destroy execution.
2. Validate M8->M9 handoff contract and fixed run scope.

Entry conditions:
1. M8 is `DONE` in `platform.build_plan.md`.
2. M8 verdict is `ADVANCE_TO_M9`.
3. M9 handoff pack is readable:
   - local: `runs/dev_substrate/m8/m8_20260219T121603Z/m9_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T121603Z/m9_handoff_pack.json`.

Required inputs:
1. M8 artifacts:
   - `m8_i_verdict_snapshot.json`
   - `m9_handoff_pack.json`.
2. Required P12 handles (runbook `P12.3` closure set):
   - Terraform/state:
     - `TF_STATE_BUCKET`
     - `TF_STATE_KEY_CORE`
     - `TF_STATE_KEY_CONFLUENT`
     - `TF_STATE_KEY_DEMO`
     - `TF_LOCK_TABLE`
   - Tagging:
     - `TAG_PROJECT_KEY`
     - `TAG_ENV_KEY`
     - `TAG_OWNER_KEY`
     - `TAG_EXPIRES_AT_KEY`
   - Demo resources:
     - `CONFLUENT_ENV_NAME`
     - `CONFLUENT_CLUSTER_NAME`
     - `ECS_CLUSTER_NAME`
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
     - `TD_REPORTER`
     - `RDS_INSTANCE_ID`
     - `RDS_ENDPOINT`

Preparation checks:
1. Validate run-scope continuity across:
   - M8 verdict snapshot,
   - M9 handoff pack,
   - active platform run scope.
2. Validate each required handle key exists in registry and resolves to non-empty concrete value.
3. Validate no wildcard/placeholder values in required closure set.
4. Validate handoff indicates blocker-free posture.

Deterministic verification algorithm (M9.A):
1. Load local `m9_handoff_pack.json`; if unreadable, load durable fallback; if both fail -> `M9A-B1`.
2. Validate handoff gate:
   - `m8_verdict=ADVANCE_TO_M9`,
   - `overall_pass=true`,
   - blocker list empty.
   Any mismatch -> `M9A-B1`.
3. Resolve required handle keys from registry into closure matrix:
   - `handle_key`, `resolved`, `value`, `source`.
4. Fail closed on unresolved required handles -> `M9A-B2`.
5. Detect wildcard/placeholder handles in required set -> `M9A-B4`.
6. Validate run-scope continuity between handoff and active execution -> `M9A-B3` on mismatch.
7. Emit local snapshot `m9_a_handle_handoff_snapshot.json` with:
   - run scope,
   - handoff refs,
   - required handle matrix,
   - unresolved/placeholder findings,
   - blockers and `overall_pass`.
8. Publish snapshot durably; publish failure -> `M9A-B5`.

Tasks:
1. Execute handoff-gate validation from M8 closure artifacts.
2. Resolve and verify required P12 handle closure set.
3. Emit and publish `m9_a_handle_handoff_snapshot.json` (local + durable).

Required snapshot fields (`m9_a_handle_handoff_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m8_verdict_local`, `source_m8_verdict_uri`.
3. `source_m9_handoff_local`, `source_m9_handoff_uri`.
4. `required_handle_keys`, `resolved_handle_count`, `unresolved_handle_count`.
5. `unresolved_handle_keys`, `placeholder_handle_keys`, `wildcard_handle_keys`.
6. `handoff_gate_checks`, `run_scope_check`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.A` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] M8 handoff gate checks pass.
- [x] Required P12 handles resolve with zero unresolved required keys.
- [x] Required-handle closure set has zero placeholder/wildcard values.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.A` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. No runtime teardown/destruction was executed during planning expansion.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T123856Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - blockers empty.
4. Gate verification outcome:
   - M8 verdict + handoff gates pass (`ADVANCE_TO_M9`, `overall_pass=true`, blocker-free matrix),
   - run-scope continuity pass (`platform_20260213T214223Z`).
5. Handle closure outcome:
   - `resolved_handle_count=28`,
   - `unresolved_handle_count=0`,
   - no placeholder/wildcard required handles.
6. `M9.A` is closed and `M9.B` is unblocked.

Blockers:
1. `M9A-B1`: M8 handoff invalid/unreadable.
2. `M9A-B2`: required handle unresolved.
3. `M9A-B3`: run-scope mismatch between handoff and active execution.
4. `M9A-B4`: placeholder/wildcard handle in required closure set.
5. `M9A-B5`: snapshot publication failure.

### M9.B Teardown Inventory + Preserve-Set Freeze
Goal:
1. Freeze deterministic destroy-set/preserve-set before destructive operations.

Entry conditions:
1. `M9.A` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`.
2. Required `M9.A` closure facts:
   - `overall_pass=true`
   - blockers empty
   - no unresolved/placeholder/wildcard required handles.

Required inputs:
1. `M9.A` snapshot (handle closure matrix).
2. Runbook P12 authority:
   - `dev_min_spine_green_v0_run_process_flow.md` (`P12.3..P12.6`).
3. Terraform outputs:
   - `infra/terraform/dev_min/core` (`s3_bucket_names`, `dynamodb_table_names`, `budget_name`)
   - `infra/terraform/dev_min/demo` (ECS service names, task definitions, RDS identifiers, SSM path outputs)
   - `infra/terraform/dev_min/confluent` (Confluent environment/cluster identifiers, SSM path outputs).
4. Handles registry for pinned non-dynamic keys:
   - `TF_STATE_BUCKET`, `TF_STATE_KEY_CORE`, `TF_STATE_KEY_CONFLUENT`, `TF_STATE_KEY_DEMO`, `TF_LOCK_TABLE`.

Preparation checks:
1. Validate `M9.A` snapshot is readable and pass.
2. Validate required inventory inputs from Terraform outputs are readable and non-empty.
3. Validate preserve-set mandatory surfaces are discoverable before inventory freeze.

Deterministic inventory algorithm (M9.B):
1. Load and validate `M9.A` pass snapshot; failure -> `M9B-B5`.
2. Materialize destroy-set categories from authoritative inputs:
   - `terraform_state_targets`:
     - `dev_min/confluent/terraform.tfstate`
     - `dev_min/demo/terraform.tfstate`
   - `confluent_targets`:
     - environment + cluster identifiers from Confluent outputs/handles.
   - `demo_runtime_targets`:
     - ECS daemon service names (`SVC_*`),
     - reporter task definition (`TD_REPORTER`),
     - runtime DB identifiers (`RDS_INSTANCE_ID`, `RDS_ENDPOINT`),
     - demo-scoped SSM paths resolved from demo/confluent outputs.
3. Materialize preserve-set categories from authoritative inputs:
   - core data buckets:
     - evidence, object-store, archive, quarantine,
   - state/control surfaces:
     - tfstate bucket + core key + lock table,
   - budget/control object:
     - budget name (cost guardrail continuity).
4. Validate destroy-set scope:
   - if any core-preserve surface appears in destroy-set -> `M9B-B1`.
5. Validate preserve-set completeness:
   - if required retained surface missing -> `M9B-B2`.
6. Validate overlap is zero:
   - if any resource appears in both destroy-set and preserve-set -> `M9B-B3`.
7. Emit local `m9_b_teardown_inventory_snapshot.json` with explicit include/exclude arrays and category summaries.
8. Publish snapshot durably; upload failure -> `M9B-B4`.

Tasks:
1. Freeze destroy-set from demo + confluent authoritative targets.
2. Freeze preserve-set from core/evidence/state/budget authoritative targets.
3. Run overlap/scope/completeness checks.
4. Emit and publish `m9_b_teardown_inventory_snapshot.json`.

Required snapshot fields (`m9_b_teardown_inventory_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m9a_snapshot_local`, `source_m9a_snapshot_uri`.
3. `destroy_set`:
   - `terraform_state_targets`,
   - `confluent_targets`,
   - `demo_runtime_targets`,
   - `demo_secret_targets`.
4. `preserve_set`:
   - `core_bucket_targets`,
   - `state_control_targets`,
   - `budget_targets`.
5. `overlap_targets`, `destroy_scope_violations`, `preserve_missing_targets`.
6. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.B` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] Destroy-set is explicit and demo-scoped.
- [x] Preserve-set is explicit and excludes evidence-loss paths.
- [x] Destroy-set and preserve-set overlap is empty.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.B` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. No teardown execution/destruction was run during planning expansion.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T125838Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - blockers empty.
4. Inventory validation outcomes:
   - destroy-set is explicit and demo/confluent scoped,
   - preserve-set includes retained core buckets, tfstate-control surfaces, and budget target,
   - overlap target set is empty,
   - destroy-scope violations: none,
   - preserve-missing targets: none.
5. `M9.B` is closed and `M9.C` is unblocked.

Blockers:
1. `M9B-B1`: destroy-set contains non-demo/core-protected surfaces.
2. `M9B-B2`: preserve-set is missing required retained buckets/surfaces.
3. `M9B-B3`: destroy/preserve overlap detected.
4. `M9B-B4`: snapshot publication failure.
5. `M9B-B5`: prerequisite `M9.A` closure invalid/unreadable.

### M9.C Confluent Teardown Execution (Unified Workflow)
Goal:
1. Execute Confluent teardown using existing managed lane.

Entry conditions:
1. `M9.B` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`.
2. `M9.B` preserve controls remain valid:
   - overlap targets empty,
   - destroy-scope violations empty,
   - preserve-missing targets empty.
3. Managed workflow lane exists and is reachable:
   - `.github/workflows/dev_min_confluent_destroy.yml`.

Required inputs:
1. Handles/values for workflow dispatch:
   - `AWS_REGION`
   - `ROLE_TERRAFORM_APPLY` (OIDC role to assume)
   - `TF_STATE_BUCKET`
   - `TF_LOCK_TABLE`
   - `TF_STATE_KEY_CONFLUENT`
   - `S3_EVIDENCE_BUCKET`.
2. Workflow inputs:
   - `stack_target` (`confluent`)
   - `aws_region`
   - `aws_role_to_assume`
   - `tf_state_bucket`
   - `tf_lock_table`
   - `tf_state_key_confluent`
   - `evidence_bucket`
   - `evidence_prefix`
   - `upload_evidence_to_s3`.
3. Access/command surface:
   - GitHub Actions API/CLI access (`gh`),
   - read access to workflow run artifacts/logs.

Preparation checks:
1. Validate required dispatch handles are resolved and non-placeholder.
2. Validate workflow file contains expected `workflow_dispatch` inputs and fail-closed enforcement step.
3. Validate `M9.B` preserve-set snapshot still pass-valid before dispatch.

Deterministic execution algorithm (M9.C):
1. Load `M9.B` pass snapshot; if unreadable or failed -> `M9C-B5`.
2. Resolve dispatch parameters from handles and fixed M9 evidence policy:
   - evidence prefix for M9 capture remains under run-control durability.
3. Dispatch `.github/workflows/dev_min_confluent_destroy.yml` with explicit inputs:
   - `stack_target=confluent`.
   - dispatch failure -> `M9C-B1`.
4. Poll/watch workflow run to terminal state.
   - non-success completion -> `M9C-B2`.
5. Read workflow-produced Confluent destroy snapshot (artifact and/or S3 URI).
   - missing/ambiguous snapshot -> `M9C-B3`.
6. Validate workflow result semantics:
   - `destroy_outcome=success`
   - `post_destroy_state_resource_count=0`
   - `overall_pass=true`.
   Any mismatch -> `M9C-B2`.
7. Emit local `m9_c_confluent_destroy_snapshot.json` with:
   - dispatch inputs (non-secret),
   - workflow run metadata (id/url),
   - source Confluent snapshot ref + parsed outcome,
   - blockers and `overall_pass`.
8. Publish snapshot durably; publish failure -> `M9C-B4`.

Tasks:
1. Dispatch Confluent destroy workflow with explicit M9-scoped inputs.
2. Capture workflow run metadata + source teardown snapshot.
3. Validate destroy outcome and post-destroy state count.
4. Emit and publish `m9_c_confluent_destroy_snapshot.json`.

Required snapshot fields (`m9_c_confluent_destroy_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m9b_snapshot_local`, `source_m9b_snapshot_uri`.
3. `workflow_name`, `workflow_run_id`, `workflow_run_url`, `workflow_conclusion`.
4. `dispatch_inputs` (non-secret only).
5. `source_confluent_destroy_snapshot_uri`, `source_confluent_destroy_snapshot`.
6. `destroy_outcome`, `post_destroy_state_resource_count`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.C` target budget: <= 25 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] Existing Confluent teardown workflow executed successfully.
- [x] Result evidence captures pass/fail + post-destroy state summary.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.C` is now execution-grade (entry/precheck/dispatch/poll/snapshot contract pinned).
2. No teardown execution/destruction was run during planning expansion.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T131353Z`.
2. Workflow run:
   - id: `22183221157`
   - url: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22183221157`
   - conclusion: `success`.
3. Source Confluent snapshot:
   - artifact: `runs/dev_substrate/m9/m9_20260219T131353Z/workflow_artifacts/dev-min-confluent-destroy-20260219T131335Z/confluent_destroy_snapshot.json`
   - durable uri: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m2i_confluent_destroy_20260219T131335Z/confluent_destroy_snapshot.json`.
4. M9.C snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`.
5. Result:
   - `overall_pass=true`,
   - blockers empty.
6. Semantics validation outcome:
   - `destroy_outcome=success`,
   - `post_destroy_state_resource_count=0`,
   - `overall_pass=true` in source Confluent snapshot.
7. `M9.C` is closed and `M9.D` is unblocked.

Blockers:
1. `M9C-B1`: workflow dispatch failure.
2. `M9C-B2`: workflow run failed/non-zero teardown.
3. `M9C-B3`: post-destroy state summary missing/ambiguous.
4. `M9C-B4`: snapshot publication failure.
5. `M9C-B5`: prerequisite `M9.B` closure invalid/unreadable.

### M9.D Demo Stack Teardown Execution
Goal:
1. Execute demo stack teardown in managed control plane.

Entry conditions:
1. `M9.C` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`.
2. `M9.C` workflow semantics are confirmed:
   - `destroy_outcome=success`
   - `post_destroy_state_resource_count=0`
   - `overall_pass=true`.
3. `M9.B` preserve controls remain valid at execution time.

Required inputs:
1. Handles/values for demo destroy dispatch:
   - `AWS_REGION`
   - `ROLE_TERRAFORM_APPLY`
   - `TF_STATE_BUCKET`
   - `TF_LOCK_TABLE`
   - `TF_STATE_KEY_DEMO`
   - `S3_EVIDENCE_BUCKET`.
2. Managed lane contract (pinned for M9.D):
   - expected workflow file: `.github/workflows/dev_min_confluent_destroy.yml`
   - required dispatch selector: `stack_target=demo`
   - expected behavior:
     - terraform init (demo backend)
     - terraform destroy demo stack
     - post-destroy state count capture
     - source snapshot publish (local artifact + durable S3)
     - fail-closed exit on non-success or non-empty state.
3. Source control snapshots:
   - `M9.B` preserve-set inventory snapshot,
   - `M9.C` Confluent teardown snapshot.

Preparation checks:
1. Validate `M9.C` snapshot is readable and pass.
2. Validate required dispatch handles are resolved and non-placeholder.
3. Validate managed demo-destroy workflow exists; if absent -> `M9D-B1`.
4. Validate `M9.B` preserve controls still pass (no overlap/scope/missing findings).

Deterministic execution algorithm (M9.D):
1. Load `M9.C` pass snapshot and verify source semantics; mismatch -> `M9D-B5`.
2. Re-load `M9.B` preserve snapshot and verify controls remain pass; mismatch -> `M9D-B6`.
3. Confirm managed demo-destroy workflow exists; absent -> `M9D-B1`.
4. Dispatch `.github/workflows/dev_min_confluent_destroy.yml` with explicit inputs:
   - `stack_target=demo`.
   - dispatch failure -> `M9D-B1`.
5. Poll/watch workflow run to terminal state.
   - non-success completion -> `M9D-B2`.
6. Read workflow-produced demo-destroy source snapshot.
   - missing/ambiguous snapshot -> `M9D-B3`.
7. Validate source teardown semantics:
   - `destroy_outcome=success`
   - `post_destroy_state_resource_count=0`
   - `overall_pass=true`.
   Any mismatch -> `M9D-B2`.
8. Emit local `m9_d_demo_destroy_snapshot.json` with:
   - dispatch inputs (non-secret),
   - workflow run metadata (id/url),
   - source demo snapshot ref + parsed outcome,
   - blockers and `overall_pass`.
9. Publish snapshot durably; publish failure -> `M9D-B4`.

Tasks:
1. Ensure managed demo-destroy lane is present and dispatchable.
2. Execute demo destroy using the managed lane with explicit inputs.
3. Capture workflow/source snapshot results and verify teardown semantics.
4. Emit and publish `m9_d_demo_destroy_snapshot.json`.

Required snapshot fields (`m9_d_demo_destroy_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m9c_snapshot_local`, `source_m9c_snapshot_uri`.
3. `workflow_name`, `workflow_run_id`, `workflow_run_url`, `workflow_conclusion`.
4. `dispatch_inputs` (non-secret only).
5. `source_demo_destroy_snapshot_uri`, `source_demo_destroy_snapshot`.
6. `destroy_outcome`, `post_destroy_state_resource_count`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.D` target budget: <= 30 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] Demo stack teardown lane executes successfully.
- [x] Terraform/state summary confirms demo resource deletion intent/outcome.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.D` is now execution-grade (entry/precheck/dispatch/poll/snapshot contract pinned).
2. Historical preflight hold is retained below for decision traceability; execution is now complete.

Execution preflight hold (historical, resolved 2026-02-19):
1. Attempted `M9.D` execution preflight from local authority posture.
2. Blocker observed:
   - `M9D-B1` (`unified teardown lane missing or not dispatchable for stack_target=demo`).
3. Evidence of drift:
   - remote `origin/migrate-dev` workflow file still lacks `stack_target` input.
4. Resolution required before rerun:
   - materialize updated unified workflow to remote branch used for dispatch.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T150604Z`.
2. Workflow run:
   - id: `22187272766`
   - url: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22187272766`
   - conclusion: `success`.
3. Source demo-destroy snapshot:
   - durable uri: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/teardown_demo_20260219T150604Z/demo_destroy_snapshot.json`.
4. M9.D snapshot artifact:
   - local: `runs/dev_substrate/m9/m9_20260219T150604Z/m9_d_demo_destroy_snapshot.json`
   - durable source carries `overall_pass=true`.
5. Result:
   - `destroy_outcome=success`,
   - `post_destroy_state_resource_count=0`,
   - `overall_pass=true`,
   - blockers empty.
6. Consequence:
   - `M9.D` is closed.
   - `M9.E` is unblocked.

Blockers:
1. `M9D-B1`: unified teardown lane missing or not dispatchable for `stack_target=demo`.
2. `M9D-B2`: destroy execution failed.
3. `M9D-B3`: destroy summary missing/ambiguous.
4. `M9D-B4`: snapshot publication failure.
5. `M9D-B5`: prerequisite `M9.C` closure invalid/unreadable.
6. `M9D-B6`: preserve-control drift from `M9.B` detected.

### M9.E Post-Destroy Residual Verification
Goal:
1. Prove no demo runtime or known cost-footgun resources remain.

Entry conditions:
1. `M9.D` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T150604Z/m9_d_demo_destroy_snapshot.json`
   - durable source: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/teardown_demo_20260219T150604Z/demo_destroy_snapshot.json`.
2. `M9.D` source semantics remain true:
   - `destroy_outcome=success`
   - `post_destroy_state_resource_count=0`
   - `overall_pass=true`.
3. `M9.B` preserve-set contract remains readable and pass-valid.

Required inputs:
1. Source snapshots:
   - `M9.B` teardown inventory/preserve-set snapshot.
   - `M9.D` demo teardown snapshot.
2. Required handles:
   - `AWS_REGION`
   - `ECS_CLUSTER_NAME`
   - `RDS_INSTANCE_ID`
   - `TAG_PROJECT_KEY`
   - `TAG_ENV_KEY`
   - `TAG_OWNER_KEY`
   - `TAG_EXPIRES_AT_KEY`.
3. Residual query surfaces:
   - ECS service/task reads,
   - EC2 NAT gateway reads,
   - ELBv2 load balancer reads,
   - RDS DB instance read.

Preparation checks:
1. Validate `M9.D` snapshot readability and PASS semantics; mismatch -> `M9E-B4`.
2. Validate `M9.B` preserve-set still has zero overlap/scope violations; mismatch -> `M9E-B5`.
3. Validate required residual query handles resolve and are non-placeholder; mismatch/query failure -> `M9E-B6`.

Deterministic execution algorithm (M9.E):
1. Load `M9.D` and `M9.B` authoritative snapshots and enforce entry gates.
2. ECS residual checks:
   - query `ECS_CLUSTER_NAME` services,
   - fail if any demo-scoped service has `desiredCount>0` or `runningCount>0`,
   - query cluster running tasks; fail if any running task remains.
3. NAT residual checks:
   - query NAT gateways in `AWS_REGION`,
   - fail if any non-deleted gateway remains with demo scope (`name_prefix`/tag posture aligned to `dev_min`).
4. LB residual checks:
   - query ALB/NLB in `AWS_REGION`,
   - fail if any active demo-scoped load balancer remains.
5. Runtime DB residual checks:
   - query `RDS_INSTANCE_ID`,
   - fail if DB instance still exists in any non-terminal residual posture.
6. Assemble residual summary object with normalized findings by class:
   - `ecs_services`, `ecs_tasks`, `nat_gateways`, `load_balancers`, `runtime_db`.
7. Compute blocker union and `overall_pass`:
   - any residual finding -> fail closed.
8. Emit local `m9_e_post_destroy_residual_snapshot.json`.
9. Publish snapshot durably; publish failure -> `M9E-B7`.

Tasks:
1. Execute residual scans for ECS/NAT/LB/RDS using pinned handles.
2. Apply fail-closed blocker mapping for any residual finding.
3. Emit and publish `m9_e_post_destroy_residual_snapshot.json`.

Required snapshot fields (`m9_e_post_destroy_residual_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m9b_snapshot_local`, `source_m9b_snapshot_uri`.
3. `source_m9d_snapshot_local`, `source_m9d_snapshot_uri`.
4. `residual_checks`:
   - `ecs_service_counts`
   - `ecs_task_counts`
   - `nat_gateway_counts`
   - `load_balancer_counts`
   - `runtime_db_state`.
5. `residual_findings`:
   - `ecs_services`
   - `ecs_tasks`
   - `nat_gateways`
   - `load_balancers`
   - `runtime_db`.
6. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.E` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] Residual scan passes all required checks.
- [x] Any residual finding is fail-closed and blocker-coded.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.E` is now execution-grade (entry/precheck/residual-query/snapshot contract pinned).
2. Historical planning-only state is superseded by execution closure below.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T153208Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - blockers empty.
4. Residual verification outcomes:
   - ECS services residual: `0` (cluster-level service count `0`),
   - ECS running tasks residual: `0`,
   - NAT residual: `0` (`total_non_deleted=0`),
   - load balancer residual: `0` (`total_scanned=0`, `demo_scoped_residual=0`),
   - runtime DB state: `not_found` (no residual RDS instance).
   - query errors: none.
5. Consequence:
   - `M9.E` is closed.
   - `M9.F` is unblocked.

Blockers:
1. `M9E-B1`: residual ECS service/task remains.
2. `M9E-B2`: NAT/LB footgun detected.
3. `M9E-B3`: runtime DB residual detected.
4. `M9E-B4`: prerequisite `M9.D` closure invalid/unreadable.
5. `M9E-B5`: preserve-control drift from `M9.B` detected.
6. `M9E-B6`: residual query surface unreadable/unauthorized.
7. `M9E-B7`: snapshot publication failure.

### M9.F Demo-Scoped Secret Cleanup Verification
Goal:
1. Prove demo-scoped credentials are removed from SSM after teardown.

Entry conditions:
1. `M9.E` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`.
2. `M9.E` source semantics remain true:
   - `overall_pass=true`,
   - blockers empty.
3. `M9.B` demo secret target set is readable and non-empty.

Required inputs:
1. Source snapshots:
   - `M9.B` teardown inventory/preserve-set snapshot.
   - `M9.E` residual verification snapshot.
2. Required handles/targets:
   - `AWS_REGION`
   - `SSM_CONFLUENT_BOOTSTRAP_PATH`
   - `SSM_CONFLUENT_API_KEY_PATH`
   - `SSM_CONFLUENT_API_SECRET_PATH`
   - `SSM_IG_API_KEY_PATH`
   - `SSM_DB_USER_PATH`
   - `SSM_DB_PASSWORD_PATH`
   - `SSM_DB_DSN_PATH` (if present in `M9.B` demo-secret target set).
3. Query surface:
   - SSM metadata-only reads (`describe-parameters` by exact name); no value reads.

Preparation checks:
1. Validate `M9.E` snapshot readability and PASS semantics; mismatch -> `M9F-B3`.
2. Validate `M9.B` secret target set remains readable and scoped; mismatch -> `M9F-B4`.
3. Validate all required target paths are derivable from handles and `M9.B`; mismatch/query failure -> `M9F-B5`.

Deterministic execution algorithm (M9.F):
1. Load `M9.E` and `M9.B` authoritative snapshots and enforce entry gates.
2. Construct canonical secret target set from `M9.B` `destroy_set.demo_secret_targets` and pinned SSM handles.
3. For each target path, execute metadata-only existence check (exact-name SSM parameter lookup):
   - if parameter metadata exists -> mark `present`,
   - if parameter absent -> mark `absent`,
   - if query unauthorized/unreadable -> fail closed.
4. Compute cleanup verdict:
   - any `present` target -> `M9F-B1` (still active),
   - any query unreadable/unauthorized -> `M9F-B5`.
5. Enforce non-secret evidence posture:
   - snapshot may include path, metadata timestamps/type/tier,
   - snapshot must not include secret values; violation -> `M9F-B2`.
6. Emit local `m9_f_secret_cleanup_snapshot.json` with full target matrix.
7. Publish snapshot durably; publish failure -> `M9F-B6`.

Tasks:
1. Execute metadata-only SSM cleanup verification for all demo-secret target paths.
2. Apply fail-closed blocker mapping for present/unknown targets.
3. Enforce non-secret output policy in the emitted evidence.
4. Emit and publish `m9_f_secret_cleanup_snapshot.json`.

Required snapshot fields (`m9_f_secret_cleanup_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m9b_snapshot_local`, `source_m9b_snapshot_uri`.
3. `source_m9e_snapshot_local`, `source_m9e_snapshot_uri`.
4. `secret_target_matrix`:
   - `parameter_name`
   - `expected_scope` (`demo_secret_target`)
   - `exists` (`true|false|unknown`)
   - `metadata` (non-secret only).
5. `present_targets`, `absent_targets`, `unknown_targets`.
6. `non_secret_policy_pass`.
7. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.F` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] Demo-scoped secret cleanup checks pass.
- [x] No secret values are emitted in evidence.
- [x] Snapshot exists locally and durably.

Planning status:
1. `M9.F` is now execution-grade (entry/precheck/metadata-only secret-check/snapshot contract pinned).
2. Historical planning-only state is superseded by execution closure below.

Execution closure (2026-02-19):
1. Execution id:
   - `m9_20260219T155120Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`.
3. Result:
   - `overall_pass=true`,
   - blockers empty.
4. Secret-cleanup outcomes:
   - all canonical demo-secret targets are `absent`,
   - `present_targets=[]`,
   - `unknown_targets=[]`,
   - `query_errors=[]`,
   - `non_secret_policy_pass=true`.
5. Consequence:
   - `M9.F` is closed.
   - `M9.G` is unblocked.

Blockers:
1. `M9F-B1`: demo-scoped secret path still active.
2. `M9F-B2`: cleanup check emits secret-bearing payload.
3. `M9F-B3`: prerequisite `M9.E` closure invalid/unreadable.
4. `M9F-B4`: secret target-set drift from `M9.B` detected.
5. `M9F-B5`: secret-query surface unreadable/unauthorized.
6. `M9F-B6`: snapshot publication failure.

### M9.G Post-Teardown Cost-Guardrail Snapshot
Goal:
1. Confirm cost posture is within dev_min guardrails after teardown.

Entry conditions:
1. `M9.F` is closed PASS:
   - local: `runs/dev_substrate/m9/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`.
2. `M9.F` source semantics remain true:
   - `overall_pass=true`,
   - blockers empty.
3. Budget guardrail baseline from `M2.I` remains readable:
   - local: `runs/dev_substrate/m2_i/20260213T201427Z/budget_guardrail_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T201427Z/budget_guardrail_snapshot.json`.
4. Required handles are resolvable from registry authority:
   - `AWS_REGION`
   - `AWS_BUDGET_NAME`
   - `AWS_BUDGET_LIMIT_AMOUNT`
   - `AWS_BUDGET_LIMIT_UNIT`
   - `AWS_BUDGET_ALERT_1_AMOUNT`
   - `AWS_BUDGET_ALERT_2_AMOUNT`
   - `AWS_BUDGET_ALERT_3_AMOUNT`
   - `ECS_CLUSTER_NAME`
   - `RDS_INSTANCE_ID`
   - `CLOUDWATCH_LOG_GROUP_PREFIX`
   - `LOG_RETENTION_DAYS`
   - `COST_CAPTURE_SCOPE`
   - `CONFLUENT_BILLING_SOURCE_MODE`
   - `TOTAL_MONTHLY_BUDGET_LIMIT_AMOUNT`
   - `TOTAL_MONTHLY_BUDGET_LIMIT_UNIT`
   - `TOTAL_BUDGET_ALERT_1_AMOUNT`
   - `TOTAL_BUDGET_ALERT_2_AMOUNT`
   - `TOTAL_BUDGET_ALERT_3_AMOUNT`.

Required inputs:
1. Source snapshots:
   - `M2.I` `budget_guardrail_snapshot.json`.
   - `M9.B` teardown inventory/preserve-set snapshot.
   - `M9.E` residual-resource snapshot.
   - `M9.F` secret-cleanup snapshot.
2. Query surfaces (metadata/cost only; no secrets):
   - `aws sts get-caller-identity` for `account_id`.
   - `aws budgets describe-budget` and `aws budgets describe-notifications-for-budget`.
   - `aws ce get-cost-and-usage` (month-to-date cost posture).
   - Confluent Cloud billing API snapshot (managed control-plane lane, non-secret output only):
     - workflow: `.github/workflows/dev_min_m9g_confluent_billing.yml`
     - durable artifact key: `evidence/dev_min/run_control/<m9_execution_id>/confluent_billing_snapshot.json`.
   - `aws ec2 describe-nat-gateways` (non-deleted NAT residuals).
   - `aws elbv2 describe-load-balancers` (+ tag/name scope check).
   - `aws ecs list-services` + `aws ecs describe-services`.
   - `aws rds describe-db-instances --db-instance-identifier <RDS_INSTANCE_ID>`.
   - `aws logs describe-log-groups --log-group-name-prefix <CLOUDWATCH_LOG_GROUP_PREFIX>`.

Preparation checks:
1. Validate `M9.F` snapshot readability and PASS semantics; mismatch -> `M9G-B6`.
2. Validate `M2.I` budget baseline snapshot readability; mismatch -> `M9G-B6`.
3. Validate all budget/cost handles resolve with no placeholder/wildcard drift; failure -> `M9G-B1`.
4. Validate `COST_CAPTURE_SCOPE=aws_plus_confluent_cloud`; mismatch -> `M9G-B8`.
5. Validate managed Confluent billing snapshot exists for this `m9_execution_id`; missing/unreadable -> `M9G-B8`.

Deterministic execution algorithm (M9.G):
1. Load authoritative source snapshots (`M2.I`, `M9.B`, `M9.E`, `M9.F`) and enforce entry gates.
2. Resolve runtime `account_id` via STS for budget/CE reads.
3. Read live budget object and notifications; validate:
   - name, limit amount, limit unit match pinned handles,
   - threshold notifications include `10/20/28` set (`AWS_BUDGET_ALERT_1/2/3_AMOUNT`).
4. Read month-to-date cost from CE and compute:
   - `aws_mtd_cost_amount`,
   - `budget_limit_amount`,
   - `budget_utilization_pct`.
5. Read Confluent month-to-date billing snapshot and compute:
   - `confluent_mtd_cost_amount`,
   - `confluent_billing_currency`,
   - `confluent_billing_period_start/end`.
6. Compute combined cost posture:
   - `combined_mtd_cost_amount = aws_mtd_cost_amount + confluent_mtd_cost_amount`,
   - `combined_budget_utilization_pct = combined_mtd_cost_amount / TOTAL_MONTHLY_BUDGET_LIMIT_AMOUNT`.
7. Recompute post-teardown cost-footgun indicators:
   - NAT non-deleted count,
   - demo-scoped load balancer residual count,
   - ECS service desired count > 0,
   - runtime DB existence state,
   - log groups under prefix with retention > `LOG_RETENTION_DAYS` or null retention.
8. Apply blocker mapping:
   - budget unreadable/misaligned -> `M9G-B1`,
   - notification threshold drift -> `M9G-B2`,
   - critical budget posture (utilization at/above alert_3) -> `M9G-B3`,
   - any cost-footgun residual indicator -> `M9G-B4`,
   - log-retention drift -> `M9G-B5`,
   - source snapshot/entry gate invalid -> `M9G-B6`,
   - Confluent billing unreadable/unavailable -> `M9G-B8`,
   - combined cross-platform critical posture (at/above `TOTAL_BUDGET_ALERT_3_AMOUNT`) -> `M9G-B9`.
9. Emit local `m9_g_cost_guardrail_snapshot.json` with non-secret posture only.
10. Publish snapshot durably; publish failure -> `M9G-B7`.

Tasks:
1. Capture AWS budget object + notification threshold posture against pinned handles.
2. Capture AWS MTD cost posture.
3. Capture Confluent Cloud MTD billing posture from managed API snapshot.
   - dispatch managed lane (`dev_min_m9g_confluent_billing.yml`) with current `m9_execution_id`,
   - require workflow verdict PASS before rollup.
4. Compute combined cross-platform MTD rollup and utilization.
5. Recompute post-teardown cost-footgun indicators.
6. Apply fail-closed blocker mapping and emit `m9_g_cost_guardrail_snapshot.json`.
7. Publish snapshot to durable evidence path.

Required snapshot fields (`m9_g_cost_guardrail_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m9_execution_id`.
2. `source_m2i_budget_snapshot_local`, `source_m2i_budget_snapshot_uri`.
3. `source_m9b_snapshot_local`, `source_m9b_snapshot_uri`.
4. `source_m9e_snapshot_local`, `source_m9e_snapshot_uri`.
5. `source_m9f_snapshot_local`, `source_m9f_snapshot_uri`.
6. `budget_posture`:
   - `budget_name`, `limit_amount`, `limit_unit`,
   - `notification_thresholds`,
   - `threshold_match_pass`.
7. `mtd_cost_posture`:
   - `aws_mtd_cost_amount`, `budget_utilization_pct`, `critical_threshold_amount`.
8. `confluent_mtd_cost_posture`:
   - `confluent_mtd_cost_amount`, `billing_currency`, `billing_period_start`, `billing_period_end`.
   - `source_workflow_file`, `source_workflow_run_id`, `source_snapshot_uri`.
9. `combined_mtd_cost_posture`:
   - `scope`, `combined_mtd_cost_amount`, `combined_budget_limit_amount`, `combined_budget_utilization_pct`, `combined_critical_threshold_amount`.
10. `post_teardown_cost_footguns`:
   - `nat_non_deleted_count`,
   - `lb_demo_scoped_residual_count`,
   - `ecs_desired_gt_zero_count`,
   - `runtime_db_state`,
   - `log_retention_drift_count`.
11. `non_secret_policy_pass`.
12. `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M9.G` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless explicit user waiver is recorded.

DoD:
- [x] AWS budget posture is readable and in-policy.
- [x] Post-teardown AWS-resource cost-footgun indicators are clear.
- [ ] Confluent Cloud MTD billing is captured in the lane.
- [ ] Combined AWS+Confluent MTD posture is computed and in-policy.
- [ ] Cross-platform snapshot exists locally and durably.

Pinned cost-optimization posture for dev substrate (execution navigation anchor):
1. Default all ECS services to `desired_count=0`; only start lane-specific services for the current phase.
2. Convert non-daemon components to ECS `RunTask` jobs instead of always-on services.
3. Enforce idle auto-teardown TTL so forgotten-up runtime windows do not burn cost.
4. Right-size ECS CPU/memory from measured p95 usage; avoid static generous defaults.
5. Keep cross-platform cost gates (`AWS + Confluent Cloud`) mandatory before phase advance, with hard stop near alert-3.
6. Keep dev log retention short (`LOG_RETENTION_DAYS=7`) and debug verbosity off by default.
7. Keep Confluent dev footprint minimal and teardown quickly after run closure.
8. Require per-run cost attribution (`run_id` + tags + durable evidence receipt).

Recommended implementation order:
1. Phase-aware ECS start/stop profile.
2. Idle auto-teardown guard.
3. ECS task-definition right-sizing.
4. Keep `M9.G` cross-platform billing gate mandatory.

Planning status:
1. `M9.G` is now execution-grade (entry/precheck/live-budget-live-cost/footgun-check/snapshot contract pinned).
2. Historical planning-only state is superseded by execution closure below.

Execution closure (2026-02-19):
1. Attempt-1 fail-closed:
   - execution id: `m9_20260219T160439Z`
   - result: `overall_pass=false`, blocker: `M9G-B1`
   - blocker cause: CE `get-cost-and-usage` request used unquoted `--time-period` composite and returned `ValidationException` (`Start time is invalid`).
2. Remediation:
   - quoted the CE argument as one value:
     - `--time-period "Start=<yyyy-mm-dd>,End=<yyyy-mm-dd>"`.
   - reran full deterministic lane with the same entry gates and blocker model.
3. Authoritative PASS run:
   - execution id: `m9_20260219T160549Z`.
4. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T160549Z/m9_g_cost_guardrail_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T160549Z/m9_g_cost_guardrail_snapshot.json`.
5. Result:
   - `overall_pass=true`,
   - blockers empty.
6. Cost posture outcomes:
   - budget surface aligned to pinned handles (`fraud-platform-dev-min-budget`, `30 USD`),
   - threshold set present (`10/20/28`), `threshold_match_pass=true`,
   - MTD cost: `17.8956072585 USD`,
   - budget utilization: `59.6520%`,
   - critical threshold (`28 USD`) not breached.
7. Post-teardown footgun outcomes:
   - `nat_non_deleted_count=0`
   - `lb_demo_scoped_residual_count=0`
   - `ecs_desired_gt_zero_count=0`
   - `runtime_db_state=not_found`
   - `log_retention_drift_count=0`.
8. Consequence:
   - `M9.G` is closed.
   - `M9.H` is unblocked.

Policy uplift (2026-02-19, cross-platform cost scope):
1. Cost capture scope is now pinned as `aws_plus_confluent_cloud`.
2. The above execution closure is AWS-only and does not satisfy cross-platform cost capture.
3. `M9.G` is reopened under the updated scope and must be rerun with Confluent billing included before `M9.H`.

Cross-platform rerun attempt (2026-02-19):
1. Execution id:
   - `m9_20260219T162445Z`.
2. Snapshot artifacts:
   - local: `runs/dev_substrate/m9/m9_20260219T162445Z/m9_g_cost_guardrail_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T162445Z/m9_g_cost_guardrail_snapshot.json`.
3. Result:
   - `overall_pass=false`.
4. Blocker outcome:
   - `M9G-B8` raised:
     - Confluent billing surface unreadable/unavailable because Confluent CLI is not authenticated for billing reads.
   - AWS side remained readable (`aws_mtd_cost_amount=17.8956072585`, thresholds match, footguns clear), but cross-platform closure is fail-closed.
5. Consequence:
   - `M9.G` remains open.
   - `M9.H` remains blocked.

Managed-lane implementation (2026-02-19):
1. Added workflow:
   - `.github/workflows/dev_min_m9g_confluent_billing.yml`.
2. Workflow contract:
   - source auth: GitHub Actions secrets `TF_VAR_CONFLUENT_CLOUD_API_KEY/SECRET`,
   - source API: `GET https://api.confluent.cloud/billing/v1/costs`,
   - output: non-secret `confluent_billing_snapshot.json` to:
     - local workflow artifact,
     - durable key `evidence/dev_min/run_control/<m9_execution_id>/confluent_billing_snapshot.json`.
3. Implication:
   - `M9.G` rerun must now consume this managed snapshot path; local `confluent` CLI auth is not the closure path.

Blockers:
1. `M9G-B1`: budget surface unreadable/misaligned.
2. `M9G-B2`: budget notification threshold drift/missing alerts.
3. `M9G-B3`: critical budget posture after teardown.
4. `M9G-B4`: post-teardown cost-footgun residual detected.
5. `M9G-B5`: log-retention drift above pinned dev_min cap.
6. `M9G-B6`: prerequisite source snapshot invalid/unreadable.
7. `M9G-B7`: snapshot publication failure.
8. `M9G-B8`: Confluent billing surface unreadable/unavailable.
9. `M9G-B9`: combined AWS+Confluent critical cost posture.

### M9.H Teardown-Proof Artifact Publication
Goal:
1. Publish the canonical P12 teardown proof object.

Tasks:
1. Assemble `teardown_proof.json` using `M9.B..M9.G` outputs.
2. Publish local + durable:
   - `evidence/runs/<platform_run_id>/teardown/teardown_proof.json` (durable canonical form).

DoD:
- [ ] Teardown-proof schema is complete and run-scoped.
- [ ] Artifact exists locally and durably.

Blockers:
1. `M9H-B1`: proof assembly missing required fields/refs.
2. `M9H-B2`: durable publish failed.

### M9.I M9 Verdict + M10 Handoff
Goal:
1. Compute deterministic M9 verdict and publish M10 handoff.

Tasks:
1. Roll up `M9.A..M9.H` pass posture.
2. Set verdict:
   - `ADVANCE_TO_M10` only if all required predicates are true and blocker union is empty,
   - else `HOLD_M9`.
3. Emit:
   - `m9_i_verdict_snapshot.json`
   - `m10_handoff_pack.json` (non-secret only).

DoD:
- [ ] Verdict rule applied deterministically.
- [ ] `m10_handoff_pack.json` passes non-secret policy.
- [ ] Both artifacts exist locally and durably.

Blockers:
1. `M9I-B1`: source snapshot missing/invalid.
2. `M9I-B2`: blocker union non-empty.
3. `M9I-B3`: handoff non-secret policy violation.
4. `M9I-B4`: artifact publication failure.

## 6) M9 Runtime Budget Targets
1. `M9.A` <= 10 minutes.
2. `M9.B` <= 10 minutes.
3. `M9.C` <= 25 minutes.
4. `M9.D` <= 30 minutes.
5. `M9.E` <= 10 minutes.
6. `M9.F` <= 10 minutes.
7. `M9.G` <= 10 minutes.
8. `M9.H` <= 10 minutes.
9. `M9.I` <= 10 minutes.

Budget rule:
1. Over-budget lanes require explicit blocker notation and remediation/retry posture before progression.

## 7) Current Planning Status
1. M9 is planning-open with `M9.A`, `M9.B`, `M9.C`, `M9.D`, `M9.E`, and `M9.F` execution closed green.
2. `M9.G` is reopened under cross-platform cost scope (`aws_plus_confluent_cloud`).
3. Latest rerun (`m9_20260219T162445Z`) is fail-closed on `M9G-B8` (Confluent billing unreadable).
4. Managed billing lane is implemented at `.github/workflows/dev_min_m9g_confluent_billing.yml`.
5. `M9.H` remains blocked until `M9.G` cross-platform rerun is blocker-free.
6. Unified teardown workflow decision is pinned:
   - `dev_min_confluent_destroy.yml` is stack-aware (`stack_target=confluent|demo`).
