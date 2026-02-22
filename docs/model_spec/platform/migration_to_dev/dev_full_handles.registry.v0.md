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

## 5. Runtime Contract Handles (M11.C-M11.F)

| Key | Status | Value |
|---|---|---|
| `DF_PLATFORM_PROFILE_PATH` | PINNED | `config/platform/profiles/dev_full.yaml` |
| `DF_LEARNING_RUN_PACK_REF` | PINNED | `config/platform/run_operate/packs/dev_full_learning_jobs.v0.yaml` |
| `DF_OFS_ENTRYPOINT_CMD` | PINNED | `python -m fraud_detection.offline_feature_plane.worker --profile config/platform/profiles/dev_full.yaml run --once` |
| `DF_MF_ENTRYPOINT_CMD` | PINNED | `python -m fraud_detection.model_factory.worker --profile config/platform/profiles/dev_full.yaml run --once` |
| `DF_MPR_PROMOTION_TRIGGER_CMD` | PINNED | `airflow dags trigger mpr_promotion_approval` |
| `DF_MPR_ROLLBACK_TRIGGER_CMD` | PINNED | `airflow dags trigger mpr_rollback` |

## 6. IAM, Secrets, and KMS Handles (M11.D)

| Key | Status | Value |
|---|---|---|
| `DF_OFS_TASK_ROLE_ARN` | PINNED | `iam://fraud-platform-dev-full-ofs-task-role` |
| `DF_MF_TASK_ROLE_ARN` | PINNED | `iam://fraud-platform-dev-full-mf-task-role` |
| `DF_MPR_CONTROL_ROLE_ARN` | PINNED | `iam://fraud-platform-dev-full-mpr-control-role` |
| `DF_KMS_KEY_ALIAS` | PINNED | `alias/fraud-platform-dev-full` |
| `DF_SSM_OFS_RUN_LEDGER_DSN_PATH` | PINNED | `/fraud-platform/dev_full/ofs/run_ledger_dsn` |
| `DF_SSM_MF_RUN_LEDGER_DSN_PATH` | PINNED | `/fraud-platform/dev_full/mf/run_ledger_dsn` |
| `DF_SSM_RUNTIME_DB_DSN_PATH` | PINNED | `/fraud-platform/dev_full/runtime/db_dsn` |
| `DF_SSM_MLFLOW_TRACKING_URI_PATH` | PINNED | `/fraud-platform/dev_full/mlflow/tracking_uri` |
| `DF_SSM_DATABRICKS_HOST_PATH` | PINNED | `/fraud-platform/dev_full/databricks/host` |
| `DF_SSM_DATABRICKS_TOKEN_PATH` | PINNED | `/fraud-platform/dev_full/databricks/token` |
| `DF_SSM_AIRFLOW_API_TOKEN_PATH` | PINNED | `/fraud-platform/dev_full/airflow/api_token` |

## 7. Data-Store and Retention Contract Handles (M11.E)

| Key | Status | Value |
|---|---|---|
| `DF_SPINE_ARCHIVE_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/archive/` |
| `DF_DATASET_MANIFEST_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/ofs/manifests/{platform_run_id}/` |
| `DF_EVAL_REPORT_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/mf/eval_reports/{platform_run_id}/` |
| `DF_REGISTRY_EVENT_ROOT` | PINNED | `s3://fraud-platform-dev-full-object-store/mpr/registry_events/` |
| `DF_DATASET_RETENTION_DAYS` | PINNED | `180` |
| `DF_EVAL_REPORT_RETENTION_DAYS` | PINNED | `365` |
| `DF_MODEL_ARTIFACT_RETENTION_DAYS` | PINNED | `365` |
| `DF_EVIDENCE_RETENTION_DAYS` | PINNED | `365` |

## 8. Messaging and Governance/Authn Corridor Handles (M11.F)

| Key | Status | Value |
|---|---|---|
| `DF_LEARNING_EVENT_BUS_HANDLE` | PINNED | `confluent://fraud-platform-dev-full-learning-bus` |
| `DF_LEARNING_EVENT_TOPIC` | PINNED | `fp.bus.learning.v1` |
| `DF_GOVERNANCE_EVENT_TOPIC` | PINNED | `fp.bus.control.v1` |
| `DF_REGISTRY_EVENT_TOPIC` | PINNED | `fp.bus.registry.v1` |
| `DF_MPR_AUTHN_MODE` | PINNED | `service_token` |
| `DF_MPR_ALLOWED_SYSTEM_ACTORS` | PINNED | `SYSTEM::model_factory,SYSTEM::platform_orchestrator` |
| `DF_MPR_ALLOWED_HUMAN_ACTORS` | PINNED | `HUMAN::platform_governance` |
| `DF_MPR_RESOLUTION_ORDER` | PINNED | `tenant_active>global_active>safe_fallback>fail_closed` |
| `DF_MPR_FAIL_CLOSED_ON_INCOMPATIBLE` | PINNED | `true` |

## 9. Observability and Evidence Taxonomy Handles (M11.G)

| Key | Status | Value |
|---|---|---|
| `DF_M11_EVIDENCE_SCHEMA_VERSION` | PINNED | `m11_snapshot_schema_v1` |
| `DF_M11_REQUIRED_EVIDENCE_FAMILIES` | PINNED | `m11_a_authority_handoff_snapshot,m11_b_handle_closure_snapshot,m11_c_runtime_decomposition_snapshot,m11_d_iam_secret_kms_snapshot,m11_e_data_contract_snapshot,m11_f_messaging_governance_snapshot` |
| `DF_M11_BLOCKER_TAXONOMY_MODE` | PINNED | `fail_closed_union` |
| `DF_M11_NON_SECRET_EVIDENCE_POLICY` | PINNED | `no_secrets_in_snapshots_or_logs` |

## 10. Spine Non-Regression Carry-Forward Handles (M11.H)

| Key | Status | Value |
|---|---|---|
| `DF_M11_NON_REGRESSION_M8_VERDICT_LOCAL` | PINNED | `runs/dev_substrate/m8/m8_20260219T121603Z/m8_i_verdict_snapshot.json` |
| `DF_M11_NON_REGRESSION_M9_VERDICT_LOCAL` | PINNED | `runs/dev_substrate/m9/m9_20260219T191706Z/m9_i_verdict_snapshot.json` |
| `DF_M11_NON_REGRESSION_M10_VERDICT_LOCAL` | PINNED | `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json` |
| `DF_M11_NON_REGRESSION_BLOCKER_MODE` | PINNED | `fail_closed_union` |
| `DF_M11_NON_REGRESSION_RERUN_POLICY` | PINNED | `rerun_non_regression_before_M12_M13_M14_verdicts` |

## 11. Cost and Teardown Continuity Handles (M11.I)

| Key | Status | Value |
|---|---|---|
| `DF_M11_LEARNING_PHASE_PROFILE_POLICY` | PINNED | `on_demand_lanes_with_profiled_start_stop` |
| `DF_M11_LEARNING_DEFAULT_DESIRED_COUNT` | PINNED | `0` |
| `DF_M11_LEARNING_JOB_EXECUTION_MODE` | PINNED | `ephemeral_run_task` |
| `DF_M11_LEARNING_IDLE_TTL_MINUTES` | PINNED | `60` |
| `DF_M11_LEARNING_INCLUDE_IN_TEARDOWN` | PINNED | `true` |
| `DF_M11_LEARNING_INCLUDE_IN_BILLING_GUARDRAIL` | PINNED | `true` |
| `DF_M11_CROSS_PLATFORM_BILLING_REQUIRED` | PINNED | `true` |

## 12. Verdict and Handoff Handles (M11.J)

| Key | Status | Value |
|---|---|---|
| `DF_M11_J_VERDICT_MODE` | PINNED | `fail_closed_union` |
| `DF_M11_J_REQUIRED_SOURCE_SNAPSHOTS` | PINNED | `m11_a_authority_handoff_snapshot,m11_b_handle_closure_snapshot,m11_c_runtime_decomposition_snapshot,m11_d_iam_secret_kms_snapshot,m11_e_data_contract_snapshot,m11_f_messaging_governance_snapshot,m11_g_observability_evidence_snapshot,m11_h_non_regression_matrix_snapshot,m11_i_cost_teardown_continuity_snapshot` |
| `DF_M11_J_ADVANCE_PREDICATES` | PINNED | `all_sources_pass,blocker_union_empty,required_source_count_complete` |
| `DF_M11_J_M12_HANDOFF_REQUIRED_FIELDS` | PINNED | `m11_execution_id,verdict,source_phase_matrix,source_blocker_rollup,target_environment,next_phase_id` |
