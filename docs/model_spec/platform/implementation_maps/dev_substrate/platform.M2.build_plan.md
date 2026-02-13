# Dev Substrate Deep Plan - M2 (P0 Substrate Readiness)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M2._
_Last updated: 2026-02-13_

## 0) Purpose
M2 establishes and validates the managed substrate required to run Spine Green v0 in `dev_min` with no laptop runtime dependency.
This phase closes infrastructure and handle readiness before P1 run pinning and P2 daemon bring-up.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P0 section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `infra/terraform/dev_min/core`
2. `infra/terraform/dev_min/demo`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md` (decision trail)

## 2) Scope Boundary for M2
In scope:
1. Terraform core/confluent/demo state and apply/destroy reproducibility contract.
2. Substrate handle closure across S3/SSM/Kafka/ECS/DB/IAM/Budgets.
3. Confluent topic/credential readiness.
4. Network posture checks (no NAT, no forbidden always-on dependency).
5. Runtime DB and migration readiness.
6. Teardown viability and cost guardrail readiness.

Out of scope:
1. P1 run manifest creation (`M3`).
2. P2 daemon deployment/startup execution (`M4`).
3. Oracle lane execution (`M5`) and downstream runtime phases.

## 3) M2 Deliverables
1. M2 capability-lane coverage matrix with no implicit gaps.
2. Pinned M2 execution command surface and preflight checks.
3. Pinned M2 evidence contract with durable output paths.
4. M2 rollback/destroy posture proven and documented.
5. M2 exit-handoff contract ready for M3 activation.
6. Explicit unresolved-blocker register (must be empty before M2 execution starts).

## 4) Execution Gate for This Phase
Current posture:
1. M2 is active for deep planning and closure-hardening.

Execution block:
1. No Terraform mutation command runs until `M2.A` and `M2.B` are complete.
2. No demo apply runs until handle closure (`M2.A`) and backend/state readiness (`M2.B`) are complete.
3. M2 status may transition to `DONE` only after all M2 sub-phases and evidence checks pass in `platform.build_plan.md`.

## 4.1) Anti-Cram Law (Binding for M2)
1. M2 cannot be treated as execution-ready unless all capability lanes are explicit and checklisted:
   - authority/handles
   - identity/IAM
   - network
   - data stores
   - messaging
   - secrets
   - observability/evidence
   - rollback/rerun
   - teardown
   - budget
2. Sub-phase count is not fixed; add sub-phases whenever a new lane appears.
3. If any new blocker reveals missing planning coverage, pause execution and expand this plan first.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles | M2.A | M2.C, M2.D | `handle_resolution_snapshot.json` complete, no unknown required keys |
| Terraform state/backend/locking | M2.B | M2.C, M2.D | backend + lock checks in evidence; distinct core/confluent/demo state keys proven |
| Identity/IAM | M2.E | M2.C, M2.D, M2.F | principal access checks for SSM/ECR/ECS/DB/Kafka control plane |
| Network posture (no NAT/no always-on LB) | M2.G | M2.D | `no_nat_check.json` plus forbidden-infra checks |
| Data stores (S3 + runtime DB) | M2.C | M2.D, M2.H | bucket writable, DB reachable, migration surface pinned |
| Messaging (Confluent topics + access) | M2.F | M2.D | topic existence/auth/ACL checks pass |
| Secrets (SSM) | M2.E | M2.D, M2.H | secret paths exist + readable by intended principals only |
| Observability/evidence | M2.C | M2.D, M2.J | M2 evidence artifacts produced under pinned root, non-secret |
| Rollback/rerun/teardown viability | M2.I | M2.C, M2.D | destroy viability evidence and rollback rules pinned |
| Budget/cost guardrails | M2.I | M2.G | budget handles resolve and alert thresholds validated |

## 5) Work Breakdown (Deep)

## M2.A Substrate Authority + Handle Closure Matrix
Goal:
1. Close all P0 handle references with explicit owner, source, and verification command before execution.

Tasks:
1. Build a closure matrix keyed by handle families and minimum required keys.
2. Minimum required handle keys to close in M2.A:
   - Terraform/backend:
     - `TF_STATE_BUCKET`
     - `TF_STATE_BUCKET_REGION`
     - `TF_STATE_KEY_CORE`
     - `TF_STATE_KEY_CONFLUENT`
     - `TF_STATE_KEY_DEMO`
     - `TF_LOCK_TABLE`
   - S3/evidence:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_ROOT_PREFIX`
     - `RUN_REPORT_PATH_PATTERN`
     - `RECEIPT_SUMMARY_PATH_PATTERN`
   - Confluent + secrets:
     - `CONFLUENT_ENV_NAME`
     - `CONFLUENT_CLUSTER_NAME`
     - `SSM_CONFLUENT_BOOTSTRAP_PATH`
     - `SSM_CONFLUENT_API_KEY_PATH`
     - `SSM_CONFLUENT_API_SECRET_PATH`
   - Kafka topic handles:
     - `FP_BUS_CONTROL_V1`
     - `FP_BUS_TRAFFIC_FRAUD_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
     - `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
     - `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
     - `FP_BUS_RTDL_V1`
     - `FP_BUS_AUDIT_V1`
     - `FP_BUS_CASE_TRIGGERS_V1`
   - ECS/network:
     - `ECS_CLUSTER_NAME`
     - `VPC_ID`
     - `SUBNET_IDS_PUBLIC`
     - `SECURITY_GROUP_ID_APP`
   - Runtime DB:
     - `DB_BACKEND_MODE`
     - `RDS_INSTANCE_ID`
     - `RDS_ENDPOINT`
     - `SSM_DB_USER_PATH`
     - `SSM_DB_PASSWORD_PATH`
   - IAM:
     - `ROLE_TERRAFORM_APPLY`
     - `ROLE_ECS_TASK_EXECUTION`
     - `ROLE_IG_SERVICE`
     - `ROLE_WSP_TASK`
     - `ROLE_SR_TASK`
     - `ROLE_RTDL_CORE`
     - `ROLE_DECISION_LANE`
     - `ROLE_CASE_LABELS`
     - `ROLE_REPORTER_SINGLE_WRITER`
     - `ROLE_DB_MIGRATIONS`
   - Budget:
     - `AWS_BUDGET_NAME`
     - `AWS_BUDGET_LIMIT_GBP`
     - `AWS_BUDGET_ALERT_1_GBP`
     - `AWS_BUDGET_ALERT_2_GBP`
     - `AWS_BUDGET_ALERT_3_GBP`
2. For each handle key, pin:
   - source of value (Terraform output, static pin, runtime lookup)
   - verification method
   - secret/non-secret classification
3. Fail any unresolved handle with explicit blocker status.

DoD:
- [x] Handle closure matrix exists with zero unknown keys required for P0.
- [x] Verification command exists for every required P0 handle family.
- [x] Secret surfaces are separated from non-secret evidence.

### M2.A Closure Summary (Execution Record)
1. Required key count: `47`.
2. Registry presence check result: `ALL_PRESENT` for the minimum M2.A key set.
3. Unknown required keys: `0`.
4. M2.A status: `CLOSED_SPEC` (planning-level closure complete; runtime checks remain in M2.B+).

### M2.A Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `V1_REGISTRY_KEY` | `rg -n "\\b<HANDLE_KEY>\\b" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | confirms handle key exists in authoritative registry |
| `V2_TERRAFORM_BACKEND` | `terraform -chdir=infra/terraform/dev_min/<stack> init -reconfigure "-backend-config=backend.hcl" && terraform -chdir=infra/terraform/dev_min/<stack> validate` | validates Terraform stack command surface for core/confluent/demo |
| `V3_TF_STATE_S3` | `aws s3api get-bucket-versioning --bucket <TF_STATE_BUCKET>` | validates state bucket control surface |
| `V4_TF_LOCK_DDB` | `aws dynamodb describe-table --table-name <TF_LOCK_TABLE>` | validates lock-table surface |
| `V5_SSM_PATH` | `aws ssm get-parameter --name <SSM_PATH> --with-decryption` | validates secret locator handles/readability surface |
| `V6_KAFKA_TOPIC` | `confluent kafka topic describe <TOPIC_NAME>` | validates topic-handle runtime surface |
| `V7_ECS_CLUSTER` | `aws ecs describe-clusters --clusters <ECS_CLUSTER_NAME>` | validates ECS cluster handle runtime surface |
| `V8_NETWORK` | `aws ec2 describe-vpcs --vpc-ids <VPC_ID>` + `aws ec2 describe-subnets --subnet-ids <SUBNET_IDS_PUBLIC>` + `aws ec2 describe-security-groups --group-ids <SECURITY_GROUP_ID_APP>` | validates network handle runtime surface |
| `V9_DB_RDS` | `aws rds describe-db-instances --db-instance-identifier <RDS_INSTANCE_ID>` | validates DB handle runtime surface |
| `V10_IAM_ROLE` | `aws iam get-role --role-name <ROLE_NAME>` | validates IAM role handle runtime surface |
| `V11_BUDGET` | `aws budgets describe-budget --account-id <AWS_ACCOUNT_ID> --budget-name <AWS_BUDGET_NAME>` | validates budget handle runtime surface |

### M2.A Secret-Surface Separation Rule (Pinned)
1. `secret_locator`: handles that identify where secret values are stored (for example SSM path keys).
2. `non_secret`: handles that are identifiers, names, paths, or numeric thresholds.
3. M2.A evidence is allowed to contain only:
   - handle keys,
   - non-secret literal values already pinned in registry,
   - verification command templates.
4. M2.A evidence must not contain decrypted secret values.

### M2.A Handle Closure Matrix (Per-Key)
| Handle key | Family | Owner (resolution) | Source of value | Verification | Secret class | Status | Blocker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TF_STATE_BUCKET` | Terraform/backend | Terraform core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V3_TF_STATE_S3` | `non_secret` | `CLOSED_SPEC` | `none` |
| `TF_STATE_BUCKET_REGION` | Terraform/backend | Terraform core | registry/stack pin | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `TF_STATE_KEY_CORE` | Terraform/backend | Terraform core | registry literal | `V1_REGISTRY_KEY` + `V2_TERRAFORM_BACKEND` | `non_secret` | `CLOSED_SPEC` | `none` |
| `TF_STATE_KEY_CONFLUENT` | Terraform/backend | Terraform confluent | registry literal | `V1_REGISTRY_KEY` + `V2_TERRAFORM_BACKEND` | `non_secret` | `CLOSED_SPEC` | `none` |
| `TF_STATE_KEY_DEMO` | Terraform/backend | Terraform demo | registry literal | `V1_REGISTRY_KEY` + `V2_TERRAFORM_BACKEND` | `non_secret` | `CLOSED_SPEC` | `none` |
| `TF_LOCK_TABLE` | Terraform/backend | Terraform core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V4_TF_LOCK_DDB` | `non_secret` | `CLOSED_SPEC` | `none` |
| `S3_EVIDENCE_BUCKET` | S3/evidence | Terraform core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V3_TF_STATE_S3` | `non_secret` | `CLOSED_SPEC` | `none` |
| `S3_EVIDENCE_ROOT_PREFIX` | S3/evidence | Registry authority | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `RUN_REPORT_PATH_PATTERN` | S3/evidence | Registry authority | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `RECEIPT_SUMMARY_PATH_PATTERN` | S3/evidence | Registry authority | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `CONFLUENT_ENV_NAME` | Confluent | Terraform confluent | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `CONFLUENT_CLUSTER_NAME` | Confluent | Terraform confluent | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `SSM_CONFLUENT_BOOTSTRAP_PATH` | Confluent/secrets | Terraform confluent | registry literal path | `V1_REGISTRY_KEY` + `V5_SSM_PATH` | `secret_locator` | `CLOSED_SPEC` | `none` |
| `SSM_CONFLUENT_API_KEY_PATH` | Confluent/secrets | Terraform confluent | registry literal path | `V1_REGISTRY_KEY` + `V5_SSM_PATH` | `secret_locator` | `CLOSED_SPEC` | `none` |
| `SSM_CONFLUENT_API_SECRET_PATH` | Confluent/secrets | Terraform confluent | registry literal path | `V1_REGISTRY_KEY` + `V5_SSM_PATH` | `secret_locator` | `CLOSED_SPEC` | `none` |
| `FP_BUS_CONTROL_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_TRAFFIC_FRAUD_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_RTDL_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_AUDIT_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FP_BUS_CASE_TRIGGERS_V1` | Kafka topics | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V6_KAFKA_TOPIC` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ECS_CLUSTER_NAME` | ECS/network | Terraform demo | registry literal (resolved by Terraform resources) | `V1_REGISTRY_KEY` + `V7_ECS_CLUSTER` | `non_secret` | `CLOSED_SPEC` | `none` |
| `VPC_ID` | ECS/network | Terraform demo/core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V8_NETWORK` | `non_secret` | `CLOSED_SPEC` | `none` |
| `SUBNET_IDS_PUBLIC` | ECS/network | Terraform demo/core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V8_NETWORK` | `non_secret` | `CLOSED_SPEC` | `none` |
| `SECURITY_GROUP_ID_APP` | ECS/network | Terraform demo/core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V8_NETWORK` | `non_secret` | `CLOSED_SPEC` | `none` |
| `DB_BACKEND_MODE` | Runtime DB | Registry authority | registry literal | `V1_REGISTRY_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `RDS_INSTANCE_ID` | Runtime DB | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V9_DB_RDS` | `non_secret` | `CLOSED_SPEC` | `none` |
| `RDS_ENDPOINT` | Runtime DB | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V9_DB_RDS` | `non_secret` | `CLOSED_SPEC` | `none` |
| `SSM_DB_USER_PATH` | Runtime DB/secrets | Terraform demo | registry literal path | `V1_REGISTRY_KEY` + `V5_SSM_PATH` | `secret_locator` | `CLOSED_SPEC` | `none` |
| `SSM_DB_PASSWORD_PATH` | Runtime DB/secrets | Terraform demo | registry literal path | `V1_REGISTRY_KEY` + `V5_SSM_PATH` | `secret_locator` | `CLOSED_SPEC` | `none` |
| `ROLE_TERRAFORM_APPLY` | IAM | Terraform core | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_ECS_TASK_EXECUTION` | IAM | Terraform core/demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_IG_SERVICE` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_WSP_TASK` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_SR_TASK` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_RTDL_CORE` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_DECISION_LANE` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_CASE_LABELS` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_REPORTER_SINGLE_WRITER` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ROLE_DB_MIGRATIONS` | IAM | Terraform demo | Terraform output at apply-time | `V1_REGISTRY_KEY` + `V10_IAM_ROLE` | `non_secret` | `CLOSED_SPEC` | `none` |
| `AWS_BUDGET_NAME` | Budget | Terraform core | registry literal/terraform-managed | `V1_REGISTRY_KEY` + `V11_BUDGET` | `non_secret` | `CLOSED_SPEC` | `none` |
| `AWS_BUDGET_LIMIT_GBP` | Budget | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V11_BUDGET` | `non_secret` | `CLOSED_SPEC` | `none` |
| `AWS_BUDGET_ALERT_1_GBP` | Budget | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V11_BUDGET` | `non_secret` | `CLOSED_SPEC` | `none` |
| `AWS_BUDGET_ALERT_2_GBP` | Budget | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V11_BUDGET` | `non_secret` | `CLOSED_SPEC` | `none` |
| `AWS_BUDGET_ALERT_3_GBP` | Budget | Registry authority | registry literal | `V1_REGISTRY_KEY` + `V11_BUDGET` | `non_secret` | `CLOSED_SPEC` | `none` |

## M2.B Terraform Backend/State Partition Readiness
Goal:
1. Ensure Terraform state is safe, split (core/confluent/demo), and lock-protected before apply operations.

Tasks:
1. Validate backend configuration for:
   - `TF_STATE_BUCKET`
   - `TF_STATE_KEY_CORE`
   - `TF_STATE_KEY_CONFLUENT`
   - `TF_STATE_KEY_DEMO`
   - `TF_LOCK_TABLE`
2. Verify state bucket security posture:
   - encryption
   - public access block
   - versioning
3. Verify lock table behavior and contention handling posture.
4. Pin canonical non-interactive command surface for backend/state checks (execution to occur only after M2.A/M2.B closure):
   - `terraform -chdir=infra/terraform/dev_min/core init -reconfigure "-backend-config=backend.hcl"`
   - `terraform -chdir=infra/terraform/dev_min/confluent init -reconfigure "-backend-config=backend.hcl"`
   - `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure "-backend-config=backend.hcl"`
   - `terraform -chdir=infra/terraform/dev_min/core validate`
   - `terraform -chdir=infra/terraform/dev_min/confluent validate`
   - `terraform -chdir=infra/terraform/dev_min/demo validate`
   - `aws s3api get-bucket-versioning --bucket <TF_STATE_BUCKET>`
   - `aws s3api get-public-access-block --bucket <TF_STATE_BUCKET>`
   - `aws dynamodb describe-table --table-name <TF_LOCK_TABLE>`

DoD:
- [x] Core/confluent/demo state keys are distinct and validated.
- [x] State bucket security controls are explicitly validated.
- [x] Lock-table readiness is evidenced.

### M2.B Closure Summary (Execution Record)
1. Canonical stack roots were materialized and validated:
   - `infra/terraform/dev_min/core`
   - `infra/terraform/dev_min/confluent`
   - `infra/terraform/dev_min/demo`
2. State key separation is explicit and validated from backend configs:
   - core key: `dev_min/core/terraform.tfstate`
   - confluent key: `dev_min/confluent/terraform.tfstate`
   - demo key: `dev_min/demo/terraform.tfstate`
   - distinctness: `true`
3. State bucket control checks (live AWS) for `fraud-platform-dev-min-tfstate`:
   - versioning: `Enabled`
   - public access block: all four flags `true`
   - encryption: `AES256`
4. Lock-table readiness (live AWS) for `fraud-platform-dev-min-tf-locks`:
   - status: `ACTIVE`
   - billing: `PAY_PER_REQUEST`
   - hash key: `LockID`
5. Static Terraform command-surface checks:
   - `terraform -chdir=infra/terraform/dev_min/core init -backend=false` -> `PASS`
   - `terraform -chdir=infra/terraform/dev_min/core validate` -> `PASS`
   - `terraform -chdir=infra/terraform/dev_min/confluent init -backend=false` -> `PASS`
   - `terraform -chdir=infra/terraform/dev_min/confluent validate` -> `PASS`
   - `terraform -chdir=infra/terraform/dev_min/demo init -backend=false` -> `PASS`
   - `terraform -chdir=infra/terraform/dev_min/demo validate` -> `PASS`
   - backend reconfigure checks with `backend.hcl.example` for all three stacks -> `PASS`
6. M2.B status: `CLOSED_EXEC`.
7. Confluent stack lane was added after initial M2.B closure; static `init -backend=false` and `validate` checks were re-run in this pass and passed.

### M2.B Evidence
1. Local snapshot:
   - `runs/dev_substrate/m2_b/20260213T125421Z/m2_b_backend_state_readiness_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T125421Z/m2_b_backend_state_readiness_snapshot.json`

## M2.C Core Apply Closure Contract
Goal:
1. Pin and verify core apply sequence and acceptance outputs without demo mutation drift.

Tasks:
1. Pin exact core command surface.
2. Define expected outputs/resources from core apply.
3. Define core apply evidence payload structure and storage location.
4. Define core rollback behavior (safe correction path).
5. Require core apply evidence to include:
   - backend/state identity used,
   - immutable Terraform plan/apply metadata,
   - resolved output handle set required by demo stack.

DoD:
- [x] Core apply command surface is canonical and non-ambiguous.
- [x] Core output acceptance checks are explicit.
- [x] Core evidence payload schema is pinned.

### M2.C Canonical Core Command Surface (Pinned)
1. Backend and static validation:
   - `terraform -chdir=infra/terraform/dev_min/core init -reconfigure "-backend-config=backend.hcl"`
   - `terraform -chdir=infra/terraform/dev_min/core validate`
2. Pre-apply plan (must run before apply):
   - `terraform -chdir=infra/terraform/dev_min/core plan -input=false -detailed-exitcode -out <core_plan_file>`
3. Core apply (only after plan acceptance and blocker closure):
   - `terraform -chdir=infra/terraform/dev_min/core apply -input=false <core_plan_file>`
4. Post-apply verification:
   - `terraform -chdir=infra/terraform/dev_min/core output -json`
   - `aws s3api get-bucket-versioning --bucket <TF_STATE_BUCKET>`
   - `aws dynamodb describe-table --table-name <TF_LOCK_TABLE>`

### M2.C Acceptance Checks (Pinned)
1. Command-surface acceptance:
   - init/validate commands must return exit `0`.
2. Plan acceptance:
   - a plan artifact must exist and be JSON-renderable via `terraform show -json`.
3. Output acceptance set (required for downstream demo stack):
   - output keys present: `s3_bucket_names`, `dynamodb_table_names`, `budget_name`.
   - output-to-handle coverage includes:
     - `S3_ORACLE_BUCKET`
     - `S3_ARCHIVE_BUCKET`
     - `S3_QUARANTINE_BUCKET`
     - `S3_EVIDENCE_BUCKET`
     - `TF_STATE_BUCKET`
     - `TF_LOCK_TABLE`
4. No-demo-drift guard:
   - M2.C commands run only under `infra/terraform/dev_min/core`.

### M2.C Evidence Schema (Pinned)
Core contract snapshot must include:
1. command receipt (exit codes + command mode),
2. backend/state identity (`bucket`, `key`, `region`, `dynamodb_table`, `encrypt`),
3. plan metadata (`resource_changes_count`, action counts),
4. expected-output contract key set,
5. rollback posture,
6. blocker register status.

Path contract:
1. local: `runs/dev_substrate/m2_c/<timestamp>/m2_c_core_apply_contract_snapshot.json`
2. durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/substrate/<m2_execution_id>/m2_c_core_apply_contract_snapshot.json`

### M2.C Rollback / Correction Posture (Pinned)
1. If apply fails:
   - fix configuration/state alignment,
   - rerun plan,
   - rerun apply (no manual console patch unless codified in Terraform).
2. If state mismatch is detected:
   - execute controlled state import/migration first,
   - rerun plan until expected create-conflict risk is removed.
3. No demo-stack mutation is allowed from M2.C corrective operations.

### M2.C Closure Summary (Execution Record)
1. Commands executed (read-only/contract validation):
   - core `init -reconfigure` with backend config -> `PASS`,
   - core `validate` -> `PASS`,
   - core `plan -detailed-exitcode` -> exit `2` (24 creates planned),
   - core plan JSON render -> `PASS`.
2. Lock table readiness:
   - `fraud-platform-dev-min-tf-locks` -> `ACTIVE`, hash key `LockID`.
3. State observation:
   - backend key `dev_min/core/terraform.tfstate` currently has no state object.
4. Material blocker discovered and pinned:
   - `M2C-B1` (state mismatch/import required before first core apply).
5. M2.C status:
   - contract closure complete (`CLOSED_CONTRACT`),
   - first core apply unblocked after `M2C-B1` closure.

### M2.C Evidence
1. Local:
   - `runs/dev_substrate/m2_c/20260213T130431Z/m2_c_core_apply_contract_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T130431Z/m2_c_core_apply_contract_snapshot.json`

## M2.D Demo Apply Closure Contract
Goal:
1. Pin and verify demo apply sequence and acceptance outputs for Confluent/ECS/DB/SSM.

Entry precondition:
1. `M2C-B1` must be closed before first core/confluent/demo apply execution in this phase chain (satisfied; see resolved blocker record).

Tasks:
1. Pin exact demo apply command surface.
2. Define required demo resources and outputs:
   - Confluent runtime contract consumption from dedicated Confluent stack (cluster/env/topic map + canonical secret paths)
   - SSM secret writes
   - ECS cluster/scaffolding
   - runtime DB
3. Define demo evidence payload schema and storage path.
4. Define fail-closed stop criteria for partial demo apply.
5. Require demo apply evidence to include:
   - resolved topic map identity,
   - SSM write confirmation for Confluent and DB secret paths (with Confluent values sourced from Confluent stack output contract),
   - ECS + DB endpoint handles produced by Terraform outputs.

DoD:
- [x] Demo apply command surface is canonical and non-ambiguous.
- [x] Required demo resource acceptance checks are explicit.
- [x] Partial apply failure posture is fail-closed.

### M2.D Canonical Demo Command Surface (Pinned)
1. Backend and static validation:
   - `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure "-backend-config=backend.hcl"`
   - `terraform -chdir=infra/terraform/dev_min/demo validate`
2. Pre-apply plan:
   - `aws s3api head-object --bucket <TF_STATE_BUCKET> --key <TF_STATE_KEY_CONFLUENT>` (required when `confluent_credentials_source=remote_state`)
   - `terraform -chdir=infra/terraform/dev_min/demo plan -input=false -detailed-exitcode -out <demo_plan_file>`
3. Demo apply (gated; only when acceptance checks pass):
   - `terraform -chdir=infra/terraform/dev_min/demo apply -input=false <demo_plan_file>`
4. Post-apply verification surface:
   - `terraform -chdir=infra/terraform/dev_min/demo output -json`
   - `aws ssm get-parameter --name <SSM_CONFLUENT_BOOTSTRAP_PATH> --with-decryption`
   - `aws ssm get-parameter --name <SSM_CONFLUENT_API_KEY_PATH> --with-decryption`
   - `aws ssm get-parameter --name <SSM_CONFLUENT_API_SECRET_PATH> --with-decryption`
   - `aws ssm get-parameter --name <SSM_DB_USER_PATH> --with-decryption`
   - `aws ssm get-parameter --name <SSM_DB_PASSWORD_PATH> --with-decryption`

### M2.D Acceptance Checks (Pinned)
1. Command-surface acceptance:
   - init/validate/plan commands must succeed.
2. Required demo categories must be present in plan/resources:
   - Confluent runtime contract consumption via remote state outputs (cluster/env/topic map + canonical secret paths),
   - SSM secret writes for Confluent and DB credentials,
   - ECS cluster/scaffolding,
   - runtime DB.
3. Topic/secret/output acceptance:
   - demo outputs must expose handles required by downstream phases,
   - SSM path writes must align to handle registry paths (not surrogate heartbeat-only paths).
4. No partial-pass allowed:
   - if any required category is missing, M2.D remains open and blocker(s) are registered.

### M2.D Fail-Closed Stop Criteria (Pinned)
1. If required categories are missing from demo plan/resources, stop progression and register blocker.
2. If demo plan writes non-canonical SSM paths without required Confluent/DB secret paths, stop progression.
3. No advancement to M2.E while M2.D blockers remain unresolved.

### M2.D Closure Summary (Execution Record)
1. Executed demo contract checks:
   - demo `init -reconfigure` -> `PASS`,
   - demo `validate` -> `PASS`,
   - demo `plan` -> `PASS` (29 planned creates).
2. Observed resource types in current demo plan:
   - `aws_cloudwatch_log_group`,
   - `aws_vpc`,
   - `aws_subnet`,
   - `aws_internet_gateway`,
   - `aws_route_table`,
   - `aws_route`,
   - `aws_route_table_association`,
   - `aws_security_group`,
   - `aws_ecs_cluster`,
   - `aws_ecs_task_definition`,
   - `aws_ecs_service`,
   - `aws_iam_role`,
   - `aws_iam_role_policy_attachment`,
   - `aws_db_subnet_group`,
   - `aws_db_instance`,
   - `aws_s3_object`,
   - `aws_ssm_parameter`,
   - `random_password`.
3. Required categories status:
   - Confluent lane contract surfaces (cluster/env/topic map + canonical secret paths): `PRESENT`,
   - ECS scaffolding: `PRESENT`,
   - runtime DB: `PRESENT`,
   - required Confluent/DB SSM secret writes: `PRESENT`.
4. M2.D status:
   - contract command surface pinned,
   - required demo capability categories are now explicit in plan/evidence,
   - M2.D is `CLOSED_EXEC` and unblocks `M2.E`.
5. Confluent lane mode for this closure:
   - `contract_materialized_in_confluent_stack_consumed_by_demo`,
   - live topic existence/connectivity/ACL validation remains enforced in `M2.F`.

### M2.D Evidence
1. Local:
   - `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`

## M2.E Secret Materialization and Access Checks (SSM)
Goal:
1. Ensure all required SSM secret paths exist/readable by intended principals and are not leaked to evidence.

Tasks:
1. Validate existence/readability for:
   - Confluent bootstrap/key/secret paths
   - DB user/password paths
   - IG API key path (if in scope for P0 readiness checks)
2. Validate role access boundaries:
   - Terraform role write/read scope
   - runtime task role read scope
3. Pin secret-redaction rules for evidence artifacts and logs.
4. Include command-lane readiness checks (non-secret outputs only):
   - `aws ssm get-parameter --name <path> --with-decryption` (existence/readability by principal)
   - denial checks for non-authorized principal identities (where policy test is safe).

DoD:
- [x] Required SSM paths exist and are readable by intended principals.
- [x] Least-privilege access is validated for runtime identities.
- [x] No secret material is emitted in evidence payloads.

### M2.E Canonical Command Surface (Pinned)
1. Operator readability checks (non-secret output only):
   - `aws ssm get-parameter --name /fraud-platform/dev_min/confluent/bootstrap --with-decryption --query Parameter.Name --output text`
   - `aws ssm get-parameter --name /fraud-platform/dev_min/confluent/api_key --with-decryption --query Parameter.Name --output text`
   - `aws ssm get-parameter --name /fraud-platform/dev_min/confluent/api_secret --with-decryption --query Parameter.Name --output text`
   - `aws ssm get-parameter --name /fraud-platform/dev_min/db/user --with-decryption --query Parameter.Name --output text`
   - `aws ssm get-parameter --name /fraud-platform/dev_min/db/password --with-decryption --query Parameter.Name --output text`
   - `aws ssm get-parameter --name /fraud-platform/dev_min/ig/api_key --with-decryption --query Parameter.Name --output text`
2. Runtime role existence checks:
   - `aws iam get-role --role-name fraud-platform-dev-min-ecs-task-execution --query Role.Arn --output text`
   - `aws iam get-role --role-name fraud-platform-dev-min-ecs-task-app --query Role.Arn --output text`
3. Policy-surface check (Terraform contract hardening):
   - demo plan must include `module.demo.aws_iam_role_policy.ecs_task_app_secret_read`.

### M2.E Closure Summary (Execution Record)
1. Executed M2.E command-lane checks against live account and demo plan.
2. Observed required-path status:
   - Confluent SSM paths: `PRESENT`,
   - DB SSM paths (`/db/user`, `/db/password`): `PRESENT`,
   - IG SSM path (`/ig/api_key`): `PRESENT`.
3. Observed runtime role status:
   - `fraud-platform-dev-min-ecs-task-execution`: `PRESENT`,
   - `fraud-platform-dev-min-ecs-task-app`: `PRESENT`.
4. Policy hardening status:
   - app runtime secret-read policy is codified and applied (`module.demo.aws_iam_role_policy.ecs_task_app_secret_read`),
   - IAM simulation for `ssm:GetParameter` on pinned secret paths:
     - app role allowed count: `6/6`,
     - execution role allowed count: `0/6` (`implicitDeny` for all).
5. M2.E status:
   - `CLOSED_EXEC`.

### M2.E Evidence
1. Local:
   - `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T141419Z/secret_surface_check.json`

## M2.F Kafka/Confluent Topic Readiness
Goal:
1. Validate topic map existence/access posture and producer/consumer readiness for Spine Green v0.

Tasks:
1. Validate all in-scope topic handles exist.
2. Validate connectivity/auth via Confluent bootstrap and API creds.
3. Pin topic verification command set and expected outputs.
4. Pin ACL verification posture (at least minimum producer/consumer rights per lane).
5. Pin one canonical verification lane before execution:
   - `confluent` CLI (if Cloud-compatible command lane is available), or
   - Kafka admin client script executed from managed runner image/local CLI.
6. If verification lane is not pinned, M2.F stays blocked.
7. Canonical command (pinned):
   - `python tools/dev_substrate/verify_m2f_topic_readiness.py --evidence-s3-uri s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_<timestamp>/topic_readiness_snapshot.json`
8. Canonical CI lane (pinned):
   - GitHub Actions workflow: `.github/workflows/dev_min_m2f_topic_readiness.yml`
   - posture: OIDC AWS auth + Confluent Terraform apply + canonical verifier script + artifact upload.

DoD:
- [ ] All required topic handles are resolvable and present.
- [ ] Connectivity/auth verification passes with pinned checks.
- [ ] ACL readiness checks are explicit and repeatable.

### M2.F Canonical Verification Lane (Pinned)
1. Lane selected: `kafka_admin_protocol_python_confluent_kafka` (with `kafka-python` fallback for diagnostics only).
2. Why this lane:
   - Confluent CLI topic commands in current installed version are Confluent Platform REST-proxy commands and reject Confluent Cloud URL usage.
3. Command posture:
   - resolve bootstrap/api key/api secret from pinned SSM paths,
   - run non-interactive Kafka metadata check against required topics,
   - emit non-secret snapshot artifact (`topic_readiness_snapshot.json`) and upload to evidence bucket.
4. Script location:
   - `tools/dev_substrate/verify_m2f_topic_readiness.py`
5. CI execution surface:
   - `.github/workflows/dev_min_m2f_topic_readiness.yml`
   - maps uppercase GitHub secrets to Terraform lowercase runtime vars:
     - `TF_VAR_confluent_cloud_api_key <- TF_VAR_CONFLUENT_CLOUD_API_KEY`
     - `TF_VAR_confluent_cloud_api_secret <- TF_VAR_CONFLUENT_CLOUD_API_SECRET`

### M2.F Execution Summary (Current)
1. Confluent CLI lane was exercised and rejected at runtime for Confluent Cloud URL usage.
2. Selected fallback lane executed with `confluent-kafka` admin client against bootstrap endpoint.
3. Runtime result:
   - authentication/connectivity check failed with SASL auth failure at broker handshake,
   - required topic existence and ACL-readiness checks could not be completed.
4. M2.F status:
   - `OPEN_BLOCKED` (fail-closed).
5. Active blocker:
   - `M2F-B1`: Confluent Kafka credentials in SSM do not authenticate against pinned bootstrap endpoint.
6. Latest rerun (`20260213T154433Z`) using pinned script lane:
   - bootstrap/api_key/api_secret were resolvable from pinned SSM paths,
   - connectivity/auth still failed (`overall_pass=false`),
   - blocker remains unchanged.

### M2.F Evidence
1. Local:
   - `runs/dev_substrate/m2_f/20260213T154433Z/topic_readiness_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T154433Z/topic_readiness_snapshot.json`

## M2.G Network, No-NAT, and Forbidden Infra Checks
Goal:
1. Prove network posture adheres to dev_min constraints and does not introduce hidden cost/risk.

Tasks:
1. Verify no NAT gateways exist.
2. Verify no always-on load balancer dependency for normal operation.
3. Verify ECS and DB security groups and subnet posture align with policy.
4. Pin verification command surfaces and evidence fields.
5. Include explicit forbidden-resource checks:
   - NAT Gateways must be zero,
   - always-on load balancer dependency must be absent,
   - always-on fleets must be absent for dev_min posture.

DoD:
- [ ] No NAT gateways verified.
- [ ] No forbidden always-on infra dependency verified.
- [ ] SG/subnet posture checks are explicit and evidenced.

## M2.H Runtime DB and Migration Readiness
Goal:
1. Verify runtime DB substrate is reachable, scoped correctly, and migration-ready.

Tasks:
1. Validate DB handles and endpoint reachability.
2. Validate DB credentials resolution via SSM.
3. Pin migration task readiness:
   - task definition handle presence
   - migration invocation contract
4. Define DB failure rollback posture (demo destroy/reapply path).
5. Pin migration invocation command surface for `TD_DB_MIGRATIONS` and success/failure evidence fields.

DoD:
- [ ] DB readiness checks are explicit and pass criteria are pinned.
- [ ] Migration readiness contract is pinned.
- [ ] DB rollback/recovery path is explicit.

## M2.I Budget Guardrails and Teardown Viability
Goal:
1. Ensure cost protection and destroyability are proven before advancing to runtime phases.

Tasks:
1. Validate budget object and alert thresholds.
2. Validate demo tag posture for cost attribution.
3. Validate teardown viability (destroy plan safety).
4. Pin teardown-proof artifact contract.
5. Include pre-approved emergency control:
   - if budget threshold breach warning is detected, stop progression to M3+ and initiate early teardown decision.
6. Provision and validate cost-monitoring surfaces:
   - CloudWatch dashboard: `fraud-platform-dev-min-cost-guardrail`,
   - CLI snapshot lane: `python tools/dev_substrate/cost_guardrail_snapshot.py`.
7. Pin live cost-risk command lane (complements delayed Cost Explorer):
   - `aws rds describe-db-instances --db-instance-identifier <RDS_INSTANCE_ID>`,
   - `aws ecs describe-services --cluster <ECS_CLUSTER_NAME> --services <service_name>`,
   - `aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=<VPC_ID>`.

DoD:
- [ ] Budget and alert handles are validated.
- [ ] Demo resource cost-tag posture is explicit.
- [ ] Teardown viability is evidenced and fail-closed.
- [ ] Cost dashboard/snapshot surfaces are operational and documented.

## M2.J Exit Readiness Review and M3 Handoff
Goal:
1. Close M2 with explicit readiness verdict and handoff contract for P1 (`M3`).

Tasks:
1. Verify all M2 sub-phase checklists completed.
2. Verify M2 evidence bundle completeness.
3. Pin M3 entry prerequisites derived from M2 outputs.
4. Publish M2 readiness verdict and hold/advance posture.
5. Publish M3 entry pack with:
   - resolved runtime handles snapshot,
   - substrate evidence index,
   - open-risk register (must be empty for M3 activation).

DoD:
- [ ] M2 deliverables checklist is complete.
- [ ] No unresolved substrate ambiguity remains.
- [ ] M3 handoff prerequisites are explicit and validated.

## 6) M2 Evidence Contract (Pinned for Execution)
Evidence root contract:
1. `evidence/dev_min/substrate/<m2_execution_id>/`
2. `<m2_execution_id>` format: `m2_<YYYYMMDDThhmmssZ>`

Minimum evidence payloads to produce during M2 execution:
1. `evidence/dev_min/substrate/<m2_execution_id>/core_apply_snapshot.json`
2. `evidence/dev_min/substrate/<m2_execution_id>/demo_apply_snapshot.json`
3. `evidence/dev_min/substrate/<m2_execution_id>/handle_resolution_snapshot.json`
4. `evidence/dev_min/substrate/<m2_execution_id>/no_nat_check.json`
5. `evidence/dev_min/substrate/<m2_execution_id>/topic_readiness_snapshot.json`
6. `evidence/dev_min/substrate/<m2_execution_id>/secret_surface_check.json`
7. `evidence/dev_min/substrate/<m2_execution_id>/teardown_viability_snapshot.json`
8. `evidence/dev_min/substrate/<m2_execution_id>/budget_guardrail_snapshot.json`
9. `evidence/dev_min/substrate/<m2_execution_id>/m3_handoff_pack.json`
10. `evidence/dev_min/substrate/<m2_execution_id>/m2_b_backend_state_readiness_snapshot.json`
11. `evidence/dev_min/substrate/<m2_execution_id>/m2_c_core_apply_contract_snapshot.json`
12. `evidence/dev_min/substrate/<m2_execution_id>/m2c_b1_resolution_snapshot.json`
13. `evidence/dev_min/substrate/<m2_execution_id>/m2_d_demo_apply_contract_snapshot.json`

Notes:
1. Evidence must be non-secret.
2. Any command output containing credentials must be redacted before persistence.

## 7) M2 Completion Checklist
- [x] M2.A complete
- [x] M2.B complete
- [x] M2.C complete
- [x] M2.D complete
- [x] M2.E complete
- [ ] M2.F complete
- [ ] M2.G complete
- [ ] M2.H complete
- [ ] M2.I complete
- [ ] M2.J complete

## 8) Risks and Controls
R1: Hidden substrate gap discovered late in P2+  
Control: lane-complete M2 decomposition + fail-closed checklisting.

R2: Manual console drift from Terraform truth  
Control: no manual resource patch accepted without Terraform codification.

R3: Secret leakage in evidence payloads  
Control: secret/non-secret evidence split and redaction rules.

R4: Cost runaway from partial demo lifecycle  
Control: budget + teardown viability gate in M2.I.

R5: Execution lane ambiguity (tooling not pinned before checks)  
Control: explicit command-lane pinning in M2.B/M2.E/M2.F before execution.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M2 Execution)
Current blockers:
1. `M2F-B1` (open)
   - blocker summary:
     - M2.F Kafka admin verification failed at SASL auth handshake for bootstrap `pkc-41wq6.eu-west-2.aws.confluent.cloud:9092`,
     - SSM credential paths exist but current values are not valid for runtime Kafka authentication.
   - closure criteria:
     - export required Confluent Cloud management credentials in execution shell:
       - `TF_VAR_confluent_cloud_api_key`
       - `TF_VAR_confluent_cloud_api_secret`
     - apply `infra/terraform/dev_min/confluent` with valid Confluent Cloud management credentials to regenerate runtime Kafka API key/secret,
     - confirm pinned SSM paths were updated from Confluent stack outputs,
     - rerun M2.F command lane (local or CI workflow) and produce `overall_pass=true` in `topic_readiness_snapshot.json`.
   - evidence:
     - local: `runs/dev_substrate/m2_f/20260213T154433Z/topic_readiness_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T154433Z/topic_readiness_snapshot.json`

Resolved blockers:
1. `M2C-B1` (closed)
   - closure summary:
     - executed controlled state import for core resources,
     - core state now contains 24 managed resources,
     - post-import replan has `CREATE_COUNT=0` for core resources.
   - evidence:
     - local: `runs/dev_substrate/m2_c/20260213T132116Z/m2c_b1_resolution_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T132116Z/m2c_b1_resolution_snapshot.json`
2. `M2D-B1` (closed)
   - closure summary:
     - demo stack now materializes Confluent runtime contract surfaces (cluster/env/topic map + canonical secret paths) and exposes required outputs.
   - evidence:
     - local: `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
3. `M2D-B2` (closed)
   - closure summary:
     - demo stack now includes ECS cluster, IAM execution/app roles, task definition, and desired-count-zero service scaffolding.
   - evidence:
     - local: `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
4. `M2D-B3` (closed)
   - closure summary:
     - demo stack now includes managed Postgres runtime DB resources and endpoint outputs.
   - evidence:
     - local: `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
5. `M2D-B4` (closed)
   - closure summary:
     - demo stack now writes canonical SSM parameter paths for Confluent and DB credentials.
   - evidence:
     - local: `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
6. `M2E-B1` (closed)
   - closure summary:
     - demo apply materialized required secret paths (`/db/user`, `/db/password`, `/ig/api_key`), and M2.E checks confirmed operator readability.
   - evidence:
     - local: `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T141419Z/secret_surface_check.json`
7. `M2E-B2` (closed)
   - closure summary:
     - demo apply materialized runtime roles and IAM simulation confirmed least-privilege boundary for pinned secret paths.
   - evidence:
     - local: `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T141419Z/secret_surface_check.json`

Rule:
1. Any newly discovered blocker is appended here with owner, impacted sub-phase, and closure criteria.
2. If this register is non-empty, no M2 execution command may run.

## 9) Exit Criteria
M2 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M2 evidence contract artifacts are produced and verified.
3. Main plan M2 DoD checklist is complete.
4. USER confirms progression to M3 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
