# Dev Substrate Deep Plan - M0 (Mobilization + Authority Lock)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail only._
_Last updated: 2026-02-22_

## 0) Purpose
M0 establishes execution governance for `dev_full` before any infra/runtime implementation starts.
This phase is planning and control only.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Baseline continuity source:
- `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`

Decision/action trails:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
- `docs/logbook/02-2026/2026-02-22.md`

## 2) Scope Boundary for M0
In scope:
- authority freeze and precedence validation,
- planning topology lock (status ownership and deep-plan routing),
- authority alignment matrix (stack pins/phase IDs/topic ownership/cost-to-outcome continuity),
- fail-closed `TO_PIN` dependency backlog shaping,
- M1 transition go/no-go protocol.

Out of scope:
- Terraform apply/destroy,
- EKS/MSK/Aurora/Databricks/SageMaker runtime execution,
- any phase status transition beyond M0 unless DoD closes.

## 3) M0 Deliverables
1. M0 prerequisite closure snapshot (`M0.PR0..PR5`).
2. Dev_full authority alignment notes with explicit mismatch classification (`wording_only` vs `execution_risk`) captured in this plan.
3. Dependency-ordered `TO_PIN` backlog with phase-entry impact (`M1`/`M2` blockers).
4. Explicit M1 go/no-go transition contract.
5. M0 closure evidence trail in implementation map and logbook.

## 4) Execution Gate for This Phase
Current posture:
- `M0` is `ACTIVE` for planning closure.

Execution block:
1. No runtime mutation command is allowed during M0.
2. No M1 activation until all M0 checklist items are closed.
3. Any `execution_risk` mismatch discovered in M0 forces `M0-BLOCKED` until resolved/repinned.

## 5) Work Breakdown (Deep)

## M0.A Authority Freeze
Goal:
- lock precedence and prevent reinterpretation drift.

Status:
- `DONE` (authority-freeze pass completed; notes captured in this plan).

Tasks:
1. Verify the precedence chain is consistent between master plan and authority docs.
2. Verify no doc claims contradictory stack baseline (MSK vs other bus, orchestration split, etc.).
3. Verify dev_min remains baseline reference and not active execution authority for dev_full.

DoD:
- [x] precedence chain validated and recorded.
- [x] no unresolved authority contradiction remains.

Evidence target:
- this file (`M0.A closure notes`, below).

M0.A closure notes (in-plan):
1. Precedence chain consistency across master plan, design authority, run-process, and handles registry: PASS.
2. Stack baseline consistency (EKS/MSK/S3/Aurora/Redis/Databricks/SageMaker/MLflow/MWAA/Step Functions): PASS.
3. No-laptop runtime posture continuity: PASS.
4. dev_min baseline usage is reference-only (no active scope mixing with dev_full): PASS.
5. Cost-to-outcome continuity across policy/run/handles/master-plan surfaces: PASS.
6. `execution_risk` mismatches detected in M0.A: none.

## M0.B Planning Topology Lock
Goal:
- keep status control and deep planning separated.

Status:
- `DONE` (topology-lock checks completed).

Tasks:
1. Confirm `platform.build_plan.md` is sole status owner.
2. Confirm `platform.M*.build_plan.md` are deep detail only.
3. Confirm M-phase naming/routing convention is pinned for dev_full.

DoD:
- [x] topology/control rules verified in master plan.
- [x] no competing status surface exists.

Evidence target:
- this file (`M0 prerequisite closure notes` section to be added at M0 closure).

M0.B closure notes (in-plan):
1. Status ownership is pinned to `platform.build_plan.md` only (`Section 6.1`, control rule).
2. Deep-plan role is pinned to `platform.M*.build_plan.md` detail-only (cannot advance phase status).
3. Current dev_full deep-plan inventory confirms only active deep plan is `platform.M0.build_plan.md`; no parallel competing phase-status surface exists.
4. M-phase naming/routing convention is pinned under master-plan deep routing section and references `platform.M0..platform.M13.build_plan.md`.

## M0.C Authority Alignment Matrix
Goal:
- remove hidden ambiguity across policy/run/handle docs.

Status:
- `DONE` (alignment closure pass completed; notes captured in-plan).

Tasks:
1. Compare and lock these alignment surfaces:
   - stack pins,
   - canonical phase IDs,
   - topic ownership and continuity,
   - cost-to-outcome law continuity.
2. For each mismatch, classify:
   - `wording_only` (no execution impact),
   - `execution_risk` (blocks progression).
3. Raise blocker IDs for any `execution_risk` mismatch.

DoD:
- [x] matrix published with classification for all checked surfaces.
- [x] all execution-risk mismatches are resolved or explicitly blocked.

Evidence target:
- this file (`M0.C alignment closure notes` section to be added when M0.C executes).

M0.C alignment closure notes (in-plan):
1. Stack pins alignment:
   - design authority, run-process, handles registry, and master plan all align on
     `EKS + MSK + S3 + Aurora + Redis + Databricks + SageMaker + MLflow + MWAA + Step Functions`.
   - classification: `aligned`.
2. Canonical phase ID alignment:
   - run-process uses `P(-1)..P17`,
   - master roadmap maps `M0..M13` consistently to canonical `P#`.
   - classification: `aligned`.
3. Topic ownership and continuity alignment:
   - run-process appendix topic set and design-authority Appendix C are consistent,
   - handles registry topic map includes all required spine + learning topics.
   - classification: `aligned`.
4. Cost-to-outcome continuity alignment:
   - design authority (`5.2.1`, `15.7`), run-process (`3.4`), handles (`13.4`), and master plan (`Section 9`) are consistent.
   - classification: `aligned`.
5. Mismatch classification summary:
   - `wording_only`: none material.
   - `execution_risk`: none.

## M0.D TO_PIN Dependency Backlog Lock
Goal:
- shape unresolved handles into ordered, fail-closed materialization plan.

Status:
- `DONE` (dependency classification, phase-block mapping, and materialization order pinned).

Current `TO_PIN` set from registry Section 14:
1. `ROLE_TERRAFORM_APPLY_DEV_FULL`
2. `ROLE_EKS_NODEGROUP_DEV_FULL`
3. `ROLE_EKS_RUNTIME_PLATFORM_BASE`
4. `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`
5. `ROLE_MWAA_EXECUTION`
6. `ROLE_SAGEMAKER_EXECUTION`
7. `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS`
8. `MSK_CLUSTER_ARN`
9. `MSK_BOOTSTRAP_BROKERS_SASL_IAM`
10. `ECR_REPO_URI`
11. `EKS_CLUSTER_ARN`
12. `DBX_WORKSPACE_URL`
13. `AWS_BUDGET_NOTIFICATION_EMAIL`

Tasks:
1. Assign each item to dependency class:
   - identity/iam,
   - runtime substrate,
   - data/ml,
   - ops/cost.
2. Map each item to earliest blocked phase (`M1` or `M2`).
3. Pin materialization order for closure (who/where/how checked).

DoD:
- [x] all TO_PIN items dependency-classified.
- [x] phase-entry blockers mapped per item.
- [x] materialization order published.

Evidence target:
- this file (`M0.D TO_PIN dependency backlog` section).

M0.D TO_PIN dependency backlog (in-plan):

| TO_PIN handle | Dependency class | Earliest blocked phase | Owner lane | Verification surface |
| --- | --- | --- | --- | --- |
| `ECR_REPO_URI` | runtime substrate | `M1` | packaging/release lane | ECR repo resolve + immutable tag push succeeds |
| `ROLE_TERRAFORM_APPLY_DEV_FULL` | identity/iam | `M2` | infra apply lane | IAM role exists + assumed by IaC runner |
| `ROLE_EKS_NODEGROUP_DEV_FULL` | identity/iam | `M2` | runtime infra lane | IAM role exists + bound to EKS nodegroup |
| `ROLE_EKS_RUNTIME_PLATFORM_BASE` | identity/iam | `M2` | runtime infra lane | IAM role exists + IRSA/runtime policy binding |
| `ROLE_STEP_FUNCTIONS_ORCHESTRATOR` | identity/iam | `M2` | orchestration lane | IAM role exists + SFN execution policy checks |
| `ROLE_MWAA_EXECUTION` | identity/iam | `M2` | orchestration lane | IAM role exists + MWAA execution binding |
| `ROLE_SAGEMAKER_EXECUTION` | identity/iam | `M2` | data_ml lane | IAM role exists + SageMaker execution binding |
| `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS` | identity/iam | `M2` | data_ml lane | IAM role exists + Databricks trust/policy checks |
| `MSK_CLUSTER_ARN` | runtime substrate | `M2` | streaming lane | MSK cluster exists + ARN resolved |
| `MSK_BOOTSTRAP_BROKERS_SASL_IAM` | runtime substrate | `M2` | streaming lane | bootstrap brokers resolve + auth mode check |
| `EKS_CLUSTER_ARN` | runtime substrate | `M2` | runtime infra lane | EKS cluster exists + ARN resolved |
| `DBX_WORKSPACE_URL` | data/ml | `M2` | data_ml lane | workspace URL resolves + token path validated |
| `AWS_BUDGET_NOTIFICATION_EMAIL` | ops/cost | `M2` | ops lane | budget notification channel configured |

Materialization order (fail-closed):
1. `M0.D-1` identity/iam foundations:
   - `ROLE_TERRAFORM_APPLY_DEV_FULL`, `ROLE_EKS_NODEGROUP_DEV_FULL`, `ROLE_EKS_RUNTIME_PLATFORM_BASE`,
   - `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`, `ROLE_MWAA_EXECUTION`, `ROLE_SAGEMAKER_EXECUTION`, `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS`.
2. `M0.D-2` substrate anchors:
   - `ECR_REPO_URI`, `MSK_CLUSTER_ARN`, `MSK_BOOTSTRAP_BROKERS_SASL_IAM`, `EKS_CLUSTER_ARN`.
3. `M0.D-3` data_ml endpoint:
   - `DBX_WORKSPACE_URL`.
4. `M0.D-4` ops/cost channel:
   - `AWS_BUDGET_NOTIFICATION_EMAIL`.

Block mapping summary:
1. `M1` hard blocker if `ECR_REPO_URI` unresolved.
2. `M2` hard blockers if any remaining TO_PIN handle unresolved.

## M0.E Exit Readiness and M1 Transition Pin
Goal:
- make transition from M0 to M1 deterministic.

Tasks:
1. Define M1 go/no-go checks and required artifacts.
2. Ensure no ambiguous “proceed” path remains.
3. Pin explicit USER confirmation requirement before M1 activation.

DoD:
- [ ] M1 transition protocol is explicit and complete.
- [ ] all M0 blockers either closed or explicitly documented with no-go.

Evidence target:
- transition section in this file + master plan alignment.

## 6) Risks and Controls
R1: Authority drift between docs.
- Control: M0.C matrix with execution-risk blocker classification.

R2: Hidden unresolved handles discovered during execution phases.
- Control: M0.D full TO_PIN dependency lock before M1 entry.

R3: Status confusion between master and deep plans.
- Control: M0.B status-ownership verification.

R4: Premature implementation pressure.
- Control: M0 execution gate prohibits runtime mutation.

## 7) M0 Completion Checklist
- [x] M0.A complete.
- [x] M0.B complete.
- [x] M0.C complete.
- [x] M0.D complete.
- [ ] M0.E complete.
- [ ] M0 prerequisite closure snapshot published.
- [ ] M0 closure note appended in implementation map.
- [ ] M0 action log appended in logbook.

## 8) Exit Criteria and Handoff
M0 is eligible for closure when:
1. all checklist items in Section 7 are complete,
2. no active `execution_risk` mismatch remains,
3. M1 transition protocol is pinned,
4. USER confirms progression to M1 planning/execution.

Handoff posture:
- M1 remains `NOT_STARTED` until explicit USER activation.

## 9) M0 Closure Notes (In-Plan)
Populate this section during M0 closure:
1. `M0 prerequisite closure notes` (`M0.PR0..M0.PR5` status and evidence summary).
2. `M0.C alignment closure notes` (final mismatch classification and blocker verdict): completed in Section `M0.C`.
3. `M0.D TO_PIN dependency backlog` (dependency classes, phase blockers, materialization order): completed in Section `M0.D`.
