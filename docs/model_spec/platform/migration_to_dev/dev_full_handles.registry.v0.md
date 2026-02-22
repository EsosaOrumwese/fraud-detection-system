# DEV_FULL HANDLES REGISTRY - v0 (Learning/Registry + Full-Platform)

## 0. Document Control

### 0.1 Status
- Status: v0 (M11.B required handles pinned, fail-closed)
- As-of: 2026-02-22 (Europe/London)
- Purpose: hold the authoritative handle namespace for `M11+` (`dev_full` target).

### 0.2 Scope Boundary (Pinned)
- This registry applies to `M11..M14` only.
- `dev_min` handle registry remains authoritative for `M1..M10`.
- No runtime surface may be used in `M11+` unless pinned here.

## 1. Global Constants (Pinned)
- `PROJECT_SLUG = "fraud-platform"`
- `ENV_NAME = "dev_full"`
- `NO_LOCAL_COMPUTE = true`
- `M11_PLUS_TARGET_ENV = "dev_full"`
- `SPINE_BASELINE_SOURCE = "dev_min_m10_certified"`

## 2. Managed Toolchain Intent (Pinned)
- `TOOLCHAIN_ORIENTATION = "managed_first"`
- `TOOLCHAIN_TARGET_SET = "SageMaker,Aurora/Managed-Postgres,Databricks,MLflow,Airflow"`
- `HANDWRITTEN_REPLICA_MODE_ALLOWED = false`

Note:
- This section is intent authority, not a finalized service-selection matrix.
- Exact lane-by-lane selection is pinned in `M11.B` before execution.

## 3. Required Handle Families (M11.B Closure Matrix)

All keys below are required surfaces for `M11+`.

| Key | Status | Value |
|---|---|---|
| `DF_AWS_REGION` | PINNED | `eu-west-2` |
| `DF_EVIDENCE_BUCKET` | PINNED | `fraud-platform-dev-full-evidence` |
| `DF_EVIDENCE_PREFIX_PATTERN` | PINNED | `evidence/dev_full/runs/{platform_run_id}/{phase_id}/` |
| `DF_RUNTIME_CLUSTER_HANDLE` | PINNED | `ecs://fraud-platform-dev-full-runtime-cluster` |
| `DF_RUNTIME_EXECUTION_ROLE` | PINNED | `iam://fraud-platform-dev-full-runtime-role` |
| `DF_OFS_DATA_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/ofs/` |
| `DF_LABEL_TIMELINE_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/labels/timeline/` |
| `DF_FEATURE_STORE_HANDLE` | PINNED | `databricks://fraud-platform-dev-full/feature_store/main` |
| `DF_TRAINING_JOB_HANDLE` | PINNED | `sagemaker://fraud-platform-dev-full/training-jobs/main` |
| `DF_MODEL_ARTIFACT_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/models/` |
| `DF_MODEL_REGISTRY_HANDLE` | PINNED | `mlflow://fraud-platform-dev-full/registry` |
| `DF_PROMOTION_APPROVAL_CHANNEL` | PINNED | `airflow://fraud-platform-dev-full/dags/mpr_promotion_approval` |
| `DF_ROLLBACK_CHANNEL` | PINNED | `airflow://fraud-platform-dev-full/dags/mpr_rollback` |
| `DF_ORCHESTRATION_HANDLE` | PINNED | `stepfunctions://fraud-platform-dev-full/platform-run-operate` |
| `DF_METRICS_SINK_HANDLE` | PINNED | `cloudwatch://fraud-platform-dev-full/metrics` |
| `DF_ALERTING_CHANNEL_HANDLE` | PINNED | `cloudwatch://fraud-platform-dev-full/alerts` |
| `DF_COST_GUARDRAIL_HANDLE` | PINNED | `github-actions://dev_full_m9g_cost_guardrail` |
| `DF_TEARDOWN_WORKFLOW_HANDLE` | PINNED | `github-actions://dev_full_destroy_stack` |

Operational note:
- `DF_ORCHESTRATION_HANDLE` is the spine Run/Operate orchestrator handle (Step Functions posture).
- Airflow handles are pinned for learning-governance control channels (`DF_PROMOTION_APPROVAL_CHANNEL`, `DF_ROLLBACK_CHANNEL`).

## 4. Fail-Closed Rule
- `M11` cannot execute with any unresolved required handle in Section 3.
- Placeholder/wildcard values are prohibited for required keys.
- Any new required surface discovered during `M11+` must be added here before use.
