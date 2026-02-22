# DEV_FULL HANDLES REGISTRY - v0 (Learning/Registry + Full-Platform)

## 0. Document Control

### 0.1 Status
- Status: v0 (draft-initial, fail-closed)
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

All keys below are required surfaces for `M11+`. Any key left as `TBD_M11B` blocks execution.

| Key | Status | Value |
|---|---|---|
| `DF_AWS_REGION` | PINNED | `eu-west-2` |
| `DF_EVIDENCE_BUCKET` | TBD | `TBD_M11B` |
| `DF_EVIDENCE_PREFIX_PATTERN` | TBD | `TBD_M11B` |
| `DF_RUNTIME_CLUSTER_HANDLE` | TBD | `TBD_M11B` |
| `DF_RUNTIME_EXECUTION_ROLE` | TBD | `TBD_M11B` |
| `DF_OFS_DATA_ROOT` | TBD | `TBD_M11B` |
| `DF_LABEL_TIMELINE_ROOT` | TBD | `TBD_M11B` |
| `DF_FEATURE_STORE_HANDLE` | TBD | `TBD_M11B` |
| `DF_TRAINING_JOB_HANDLE` | TBD | `TBD_M11B` |
| `DF_MODEL_ARTIFACT_ROOT` | TBD | `TBD_M11B` |
| `DF_MODEL_REGISTRY_HANDLE` | TBD | `TBD_M11B` |
| `DF_PROMOTION_APPROVAL_CHANNEL` | TBD | `TBD_M11B` |
| `DF_ROLLBACK_CHANNEL` | TBD | `TBD_M11B` |
| `DF_ORCHESTRATION_HANDLE` | TBD | `TBD_M11B` |
| `DF_METRICS_SINK_HANDLE` | TBD | `TBD_M11B` |
| `DF_ALERTING_CHANNEL_HANDLE` | TBD | `TBD_M11B` |
| `DF_COST_GUARDRAIL_HANDLE` | TBD | `TBD_M11B` |
| `DF_TEARDOWN_WORKFLOW_HANDLE` | TBD | `TBD_M11B` |

## 4. Fail-Closed Rule
- `M11` cannot execute with any `TBD_M11B` value in Section 3.
- Placeholder/wildcard values are prohibited for required keys.
- Any new required surface discovered during `M11+` must be added here before use.
