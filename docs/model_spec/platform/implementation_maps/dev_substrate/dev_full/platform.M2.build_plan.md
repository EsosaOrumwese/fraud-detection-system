# Dev Substrate Deep Plan - M2 (P0 Substrate Readiness)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M2._
_Last updated: 2026-02-22_

## 0) Purpose
M2 closes `P0 SUBSTRATE_READY` for `dev_full` by proving that managed substrate foundations are materialized, queryable, and fail-closed:
1. Terraform state/lock surfaces are healthy.
2. All five bounded stacks (`core`, `streaming`, `runtime`, `data_ml`, `ops`) are apply-capable.
3. Required IAM and secret path surfaces are present and conformance-checked.
4. Cost guardrail and residual-risk controls are in place before runtime phases.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P0 SUBSTRATE_READY`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.M2.build_plan.md` (structure reference only)

## 2) Scope Boundary for M2
In scope:
1. Terraform substrate readiness and bounded stack sequencing.
2. IAM/identity/secret-path conformance for required handles.
3. Observability + budget surfaces needed for safe phase progression.
4. Destroy/recover rehearsal posture for substrate confidence.

Out of scope:
1. Runtime service behavior and daemon health (`M4+`).
2. Run pinning/orchestration semantics (`M3`).
3. Oracle, ingest, and lane runtime flow checks (`M5+`).

## 3) M2 Deliverables
1. Explicit execution sequence for `core/streaming/runtime/data_ml/ops` stacks.
2. Required-handle conformance proof (`IAM + secret paths + stack outputs`).
3. P0 gate evidence pack with blocker-free rollup.
4. Destroy/recover rehearsal evidence and residual scan posture.

## 4) Execution Gate for This Phase
Current posture:
1. M2 is `IN_PROGRESS` and execution-active.

Execution block:
1. M2 execution begins only after explicit USER go-ahead for M2 run lanes.
2. Any unresolved `TO_PIN` handle required by the active M2 subphase is fail-closed.
3. Any state backend/lock failure blocks all downstream stack application.

## 5) Work Breakdown (Deep)

## M2.A State Backend and Lock Conformance
Goal:
- prove remote state/lock surfaces are healthy before any stack apply.

Tasks:
1. Validate state bucket posture (`exists`, encryption/versioning/public access block).
2. Validate lock table posture (`exists`, key schema, write/read lock semantics).
3. Validate per-stack state key namespace (`core/streaming/runtime/data_ml/ops`).
4. Emit backend conformance evidence and fail-closed diagnostics.

DoD:
- [x] state bucket conformance checks pass.
- [x] lock table conformance checks pass.
- [x] per-stack state key contract is validated.
- [x] M2.A evidence snapshot committed.

M2.A planning precheck (decision completeness):
1. Required handles for this lane are pinned:
   - `TF_STATE_BUCKET`, `TF_STATE_BUCKET_REGION`, `TF_LOCK_TABLE`
   - `TF_STATE_KEY_CORE`, `TF_STATE_KEY_STREAMING`, `TF_STATE_KEY_RUNTIME`, `TF_STATE_KEY_DATA_ML`, `TF_STATE_KEY_OPS`
   - `TF_STACK_CORE_DIR`, `TF_STACK_STREAMING_DIR`, `TF_STACK_RUNTIME_DIR`, `TF_STACK_DATA_ML_DIR`, `TF_STACK_OPS_DIR`
2. Required stack-root filesystem check was failing at planning time:
   - `infra/terraform/dev_full/` was absent during initial planning and was treated as an entry blocker.
3. Backend substrate check was failing at planning time:
   - S3 state bucket `fraud-platform-dev-full-tfstate` and DynamoDB lock table `fraud-platform-dev-full-tf-locks` were initially absent.
4. Planning-time blockers above were executed and resolved during M2.A closure (see execution closure section).

M2.A execution contract (planned):
1. Verify backend resources exist before any `terraform init/plan/apply`:
   - state bucket exists and is reachable,
   - lock table exists and is reachable.
2. Verify bucket posture:
   - encryption enabled,
   - versioning enabled,
   - public access block enabled.
3. Verify lock-table posture:
   - table status is `ACTIVE`,
   - lock key schema supports Terraform lock semantics.
4. Verify stack-root readiness:
   - all five `TF_STACK_*_DIR` paths exist,
   - each stack has backend configuration surface and can run `terraform init` against pinned remote backend.
5. Verify per-stack state-key namespace:
   - key values are unique and non-overlapping,
   - key naming matches bounded stack posture (`core/streaming/runtime/data_ml/ops`).

M2.A command surface (planned, execution-time):
1. Backend existence:
   - `aws s3api head-bucket --bucket <TF_STATE_BUCKET> --region <TF_STATE_BUCKET_REGION>`
   - `aws dynamodb describe-table --table-name <TF_LOCK_TABLE> --region <AWS_REGION>`
2. Bucket posture:
   - `aws s3api get-bucket-encryption --bucket <TF_STATE_BUCKET> --region <TF_STATE_BUCKET_REGION>`
   - `aws s3api get-bucket-versioning --bucket <TF_STATE_BUCKET> --region <TF_STATE_BUCKET_REGION>`
   - `aws s3api get-public-access-block --bucket <TF_STATE_BUCKET> --region <TF_STATE_BUCKET_REGION>`
3. Stack-root/namespace conformance:
   - filesystem existence checks for all `TF_STACK_*_DIR`,
   - uniqueness checks for all `TF_STATE_KEY_*`,
   - `terraform -chdir=<TF_STACK_*_DIR> init -reconfigure -backend-config=...` (readiness check only; no apply in M2.A).

M2.A fail-closed policy (planned):
1. Missing state bucket or missing lock table is a hard blocker (`M2A-B1`).
2. Bucket posture drift (encryption/versioning/public-access-block mismatch) is a hard blocker (`M2A-B2`).
3. Missing stack-root directories or backend surfaces is a hard blocker (`M2A-B3`).
4. Duplicate/invalid per-stack state-key namespace is a hard blocker (`M2A-B4`).
5. Any inability to produce backend conformance evidence is a blocker (`M2A-B5`).

M2.A evidence contract (planned):
1. `m2a_backend_conformance_snapshot.json`
   - backend existence and posture verdicts.
2. `m2a_stack_backend_matrix.json`
   - per-stack directory/backend/key readiness matrix.
3. `m2a_blocker_register.json`
   - active `M2A-B*` blockers with severity and remediation actions.
4. `m2a_execution_summary.json`
   - rollup verdict (`overall_pass`), next-step gate (`M2.B` ready or blocked).

M2.A expected entry blockers (current planning reality):
1. `M2A-B1`: backend resources missing (`TF_STATE_BUCKET` + `TF_LOCK_TABLE` not found).
2. `M2A-B3`: stack-root directories for `infra/terraform/dev_full/*` not yet materialized.

M2.A closure rule:
1. M2.A can close only when:
   - all `M2A-B*` blockers are resolved,
   - all DoD checks are green,
   - evidence artifacts are produced and readable.

M2.A execution closure (2026-02-22):
1. PASS run evidence root:
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/`
2. Required evidence artifacts produced:
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/m2a_backend_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/m2a_stack_backend_matrix.json`
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/m2a_blocker_register.json`
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/m2a_execution_summary.json`
3. Intermediate fail-closed run retained for audit:
   - `runs/dev_substrate/dev_full/m2/m2a_20260222T203851Z/`
   - blocker cause was command-argument binding bug in the local M2.A probe script (not substrate drift); rerun after fix cleared blockers.
4. Final verdict:
   - `overall_pass=true`, blocker count `0`, next gate `M2.B_READY`.

## M2.B Core Stack Materialization
Goal:
- apply and validate `core/` stack surfaces (network base, KMS, base S3, baseline IAM).

Tasks:
1. Run bounded `terraform plan/apply` for `infra/terraform/dev_full/core`.
2. Verify required outputs/handles for downstream stacks.
3. Validate tagging posture and baseline policy attachments.
4. Emit `core` stack apply/verification receipt.

DoD:
- [x] `core` plan/apply succeeds.
- [x] required core outputs are materialized.
- [x] baseline tags/policies pass conformance checks.
- [x] M2.B evidence snapshot committed.

M2.B planning precheck (decision completeness):
1. Required handles for this lane are pinned:
   - `TF_STACK_CORE_DIR`, `TF_STATE_BUCKET`, `TF_STATE_BUCKET_REGION`, `TF_LOCK_TABLE`, `TF_STATE_KEY_CORE`
   - `S3_OBJECT_STORE_BUCKET`, `S3_EVIDENCE_BUCKET`, `S3_ARTIFACTS_BUCKET`
   - `S3_BUCKET_ENCRYPTION_ENABLED`, `S3_BUCKET_PUBLIC_ACCESS_BLOCKED`, `S3_BUCKET_VERSIONING_ENABLED`
   - `KMS_KEY_ALIAS_PLATFORM`
   - downstream-unblock handles expected from core outputs: `MSK_CLIENT_SUBNET_IDS`, `MSK_SECURITY_GROUP_ID`
2. Planning-time execution reality:
   - `infra/terraform/dev_full/core/main.tf` was M2.A skeletal (backend + local only), with no concrete resource/module or output surfaces.
3. That planning blocker was carried as `M2B-B1` and resolved during M2.B execution.

M2.B execution contract (planned):
1. Preconditions:
   - `M2.A` PASS evidence is present,
   - backend/lock is reachable and unchanged from M2.A closure.
2. Core command surface:
   - `terraform -chdir=infra/terraform/dev_full/core init -reconfigure -backend-config=...`
   - `terraform -chdir=infra/terraform/dev_full/core validate`
   - `terraform -chdir=infra/terraform/dev_full/core plan -input=false -detailed-exitcode -out <m2b_core_plan>`
   - `terraform -chdir=infra/terraform/dev_full/core apply -input=false <m2b_core_plan>`
   - `terraform -chdir=infra/terraform/dev_full/core output -json`
3. Acceptance checks:
   - plan/apply commands exit cleanly (`0`) with deterministic artifact capture,
   - core emits required downstream outputs for streaming/runtime entry,
   - bucket posture is confirmed for core-managed buckets (encryption/versioning/public access block),
   - KMS alias/key mapping is queryable and stable.

M2.B fail-closed policy (planned):
1. `M2B-B1`: core stack is non-materialized (no meaningful resources) or apply surface is incomplete.
2. `M2B-B2`: terraform init/validate/plan/apply fails under pinned backend/state posture.
3. `M2B-B3`: required output contract missing (including downstream-unblock handles for later stacks).
4. `M2B-B4`: security/tagging posture drift on core-managed surfaces.
5. `M2B-B5`: evidence artifacts missing/inconsistent with command receipts.

M2.B evidence contract (planned):
1. `m2b_core_plan_snapshot.json`
   - command receipts, plan summary, resource-action rollup.
2. `m2b_core_apply_snapshot.json`
   - apply receipt, terraform output surface, state identity.
3. `m2b_core_output_handle_matrix.json`
   - mapping of core outputs to required registry handles and downstream consumers.
4. `m2b_blocker_register.json`
   - active `M2B-B*` blockers with severity and remediation.
5. `m2b_execution_summary.json`
   - rollup verdict (`overall_pass`), next gate (`M2.C_READY` or `BLOCKED`).

M2.B expected entry blocker (planning-time reality):
1. `M2B-B1`: core stack implementation was skeleton-only and could not satisfy core output/materialization DoD until resource/module/output surfaces were added.

M2.B closure rule:
1. M2.B can close only when:
   - all `M2B-B*` blockers are resolved,
   - DoD checks are green,
   - evidence artifacts are produced and readable.

M2.B execution closure (2026-02-22):
1. PASS evidence root:
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/`
2. Required artifacts produced:
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_core_plan_snapshot.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_core_apply_snapshot.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_core_output_handle_matrix.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_core_policy_tag_conformance.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_post_apply_stability_check.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_blocker_register.json`
   - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_execution_summary.json`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2b_20260222T210207Z/`
4. Command verdict:
   - `plan_exit=2` (creates present), `apply_exit=0`, `overall_pass=true`, blockers empty.
   - `policy_tag_conformance_pass=true` (IAM attachments + required tags).
   - post-apply stability plan returned no drift (`detailed_exit_code=0`).
5. M2.B blocker adjudication:
   - `M2B-B1` closed by materializing concrete core stack resources/outputs.
   - `M2B-B2..B5` closed by successful command receipts and conformance checks.

## M2.C Streaming Stack Materialization
Goal:
- apply and validate `streaming/` stack (MSK serverless + stream access posture).

Tasks:
1. Run bounded `terraform plan/apply` for `infra/terraform/dev_full/streaming`.
2. Validate `MSK_*` handles and bootstrap-broker secret-path wiring references.
3. Validate auth posture (`MSK_AUTH_MODE=SASL_IAM`).
4. Emit streaming stack receipt with blocker mapping.

DoD:
- [ ] `streaming` plan/apply succeeds.
- [ ] MSK identity handles are materialized or explicit blockers raised.
- [ ] auth mode and secret reference contracts are consistent with authority.
- [ ] M2.C evidence snapshot committed.

## M2.D Topic and Schema Readiness Precheck
Goal:
- prove streaming substrate is ready for lane topic/schema provisioning contracts.

Tasks:
1. Validate topic map handles exist and naming posture is coherent.
2. Validate schema registry handles and compatibility mode.
3. Validate producer/consumer identity bindings for access paths.
4. Emit readiness matrix and fail-closed blockers.

DoD:
- [ ] required topic surfaces are reachable/provisionable.
- [ ] schema registry handles/compatibility contract validated.
- [ ] lane access bindings pass precheck.
- [ ] M2.D readiness snapshot committed.

## M2.E Runtime Stack and IAM Role Posture
Goal:
- apply and validate `runtime/` stack and service identity surfaces.

Tasks:
1. Run bounded `terraform plan/apply` for `infra/terraform/dev_full/runtime`.
2. Validate required IAM role handles from authority Section 8.6/registry Section 11.
3. Validate EKS and workload identity baseline posture.
4. Emit role conformance matrix and runtime stack receipt.

DoD:
- [ ] `runtime` plan/apply succeeds.
- [ ] required role handles are materialized or explicit blockers raised.
- [ ] workload identity baseline checks pass.
- [ ] M2.E evidence snapshot committed.

## M2.F Secret Path Contract and Materialization Checks
Goal:
- verify secret-path contract completeness and materialization posture for required surfaces.

Tasks:
1. Validate required secret path handle set is complete and non-drifting.
2. Validate secret path existence/readability posture via managed identity (value redaction-safe checks).
3. Validate no plaintext secret emission in outputs/evidence.
4. Emit secret conformance report and blocker rollup.

DoD:
- [ ] required secret path set is complete.
- [ ] materialization/readability checks pass or explicit blockers raised.
- [ ] no plaintext leakage in outputs/evidence.
- [ ] M2.F evidence snapshot committed.

## M2.G Data_ML Stack Materialization
Goal:
- apply and validate `data_ml/` stack surfaces (Databricks, SageMaker, MLflow bridge handles).

Tasks:
1. Run bounded `terraform plan/apply` for `infra/terraform/dev_full/data_ml`.
2. Validate required Data_ML handle outputs and role/secret references.
3. Validate minimal cost-safe default posture for non-essential compute.
4. Emit data_ml stack receipt.

DoD:
- [ ] `data_ml` plan/apply succeeds.
- [ ] required data_ml handles materialized or explicit blockers raised.
- [ ] default cost-safe posture checks pass.
- [ ] M2.G evidence snapshot committed.

## M2.H Ops Stack and Cost Guardrail Surfaces
Goal:
- apply and validate `ops/` stack (budgets, alarms, dashboards, workflow role bindings).

Tasks:
1. Run bounded `terraform plan/apply` for `infra/terraform/dev_full/ops`.
2. Validate budget/alarm/dashboard handles are queryable.
3. Validate cost-to-outcome artifact path handles and operational readiness.
4. Emit ops guardrail receipt.

DoD:
- [ ] `ops` plan/apply succeeds.
- [ ] budget/alarm/dashboard handles queryable.
- [ ] cost guardrail path contracts validated.
- [ ] M2.H evidence snapshot committed.

## M2.I Destroy/Recover Rehearsal and Residual Scan
Goal:
- prove teardown/recovery posture for substrate surfaces before runtime lanes.

Tasks:
1. Execute bounded destroy/recover rehearsal per stack policy.
2. Validate state integrity after recovery and no drift from expected handles.
3. Emit residual-risk scan and teardown cost posture receipt.
4. Classify unresolved residuals with fail-closed severity.

DoD:
- [ ] bounded destroy/recover rehearsal completed.
- [ ] state and handle integrity preserved after recovery.
- [ ] residual scan artifact emitted.
- [ ] M2.I evidence snapshot committed.

## M2.J P0 Gate Rollup and Verdict
Goal:
- adjudicate `P0 SUBSTRATE_READY` closure and handoff to M3.

Tasks:
1. Roll up evidence from M2.A..M2.I into a single P0 verdict matrix.
2. Evaluate blockers severity and no-go conditions.
3. Emit P0 verdict artifact and M3 entry readiness receipt.
4. Mark M2 complete only if blocker-free and fail-closed checks pass.

DoD:
- [ ] P0 rollup matrix complete.
- [ ] blocker register shows no unresolved `S1/S2`.
- [ ] M3 entry readiness is explicit and evidence-backed.
- [ ] M2 closure note appended in implementation map and logbook.

## 6) Blocker Taxonomy (M2)
- `M2-B1`: state backend or lock table failure.
- `M2-B2`: stack apply failure with no deterministic rerun posture.
- `M2-B3`: required IAM role handle missing/unbound.
- `M2-B4`: required secret path missing/unreadable.
- `M2-B5`: streaming identity/auth or schema readiness drift.
- `M2-B6`: ops budget/alarm/dashboard surface not queryable.
- `M2-B7`: destroy/recover rehearsal leaves unresolved residual risk.
- `M2-B8`: P0 rollup evidence incomplete/inconsistent.

Any active `M2-B*` blocker prevents M2 execution closure.

## 7) M2 Completion Checklist
- [x] M2.A complete.
- [x] M2.B complete.
- [ ] M2.C complete.
- [ ] M2.D complete.
- [ ] M2.E complete.
- [ ] M2.F complete.
- [ ] M2.G complete.
- [ ] M2.H complete.
- [ ] M2.I complete.
- [ ] M2.J complete.
- [ ] M2 blockers resolved or explicitly fail-closed.
- [ ] M2 closure note appended in implementation map.
- [ ] M2 action log appended in logbook.

## 8) Exit Criteria and Handoff
M2 is eligible for closure when:
1. all checklist items in Section 7 are complete,
2. `P0 SUBSTRATE_READY` rollup is blocker-free,
3. required evidence artifacts are published and readable,
4. USER confirms progression to M3 activation.

Handoff posture:
- M3 remains `NOT_STARTED` until M2 is marked `DONE` in master plan.
