# DEV_FULL HANDLES REGISTRY - v0 (Single Source of Truth)

## 0. Document Control

### 0.1 Status

* **Status:** v0 (draft-initial; execution-grade for naming/path/ID surfaces)
* **As-of:** 2026-02-22 (Europe/London)
* **Purpose:** pin all concrete handles required to provision and run `dev_full` full-platform flow (`P(-1)..P17`) without naming drift.

### 0.2 Audience

* **Design authority:** USER + Codex
* **Implementer:** Codex
* **Operator:** USER

### 0.3 Authority boundaries

**Pinned (MUST follow)**

1. No code/Terraform/workflow/doc may introduce a dev_full runtime handle not declared here.
2. This registry is the concrete naming/path/ID authority paired with:
   * `dev_full_platform_green_v0_run_process_flow.md` (phase semantics/gates)
   * `dev-full_managed-substrate_migration.design-authority.v0.md` (stack/policy pins)
3. Runtime compute remains managed only; no local runtime fallback handles are permitted.
4. Event-bus handles are AWS MSK Serverless only for dev_full v0.

### 0.4 Change control rules

1. Handle changes require registry update first, then downstream implementation updates.
2. Renames are allowed only with explicit compatibility note and migration path.
3. `TO_PIN` fields are fail-closed: execution must stop until materialized.

---

## 1. Global Constants (Pinned)

### 1.1 Project identity

* `PROJECT_SLUG = "fraud-platform"`
* `ENV_NAME = "dev_full"`
* `ENV_LADDER = "local_parity->dev_min->dev_full->prod_target"`

### 1.2 Region pins

* `AWS_REGION = "eu-west-2"`
* `MSK_REGION = "eu-west-2"`
* `AWS_BILLING_REGION = "us-east-1"`

### 1.3 Stack identity pins

* `KAFKA_BACKEND = "AWS_MSK_SERVERLESS"`
* `MSK_CLUSTER_MODE = "Serverless"`
* `MSK_AUTH_MODE = "SASL_IAM"`
* `SCHEMA_REGISTRY_MODE = "AWS_GLUE_SCHEMA_REGISTRY"`

### 1.4 Budget pins

* `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD = 300`
* `DEV_FULL_BUDGET_ALERT_1_USD = 120`
* `DEV_FULL_BUDGET_ALERT_2_USD = 210`
* `DEV_FULL_BUDGET_ALERT_3_USD = 270`
* `BUDGET_CURRENCY = "USD"`

### 1.5 Tagging schema (required)

* `TAG_PROJECT_KEY = "project"` -> `fraud-platform`
* `TAG_ENV_KEY = "env"` -> `dev_full`
* `TAG_OWNER_KEY = "owner"` -> `esosa`
* `TAG_RUN_ID_KEY = "fp_run_id"`
* `TAG_PHASE_KEY = "fp_phase_id"`
* `TAG_EXPIRES_AT_KEY = "expires_at"`

### 1.6 Canonical field names

* `FIELD_PLATFORM_RUN_ID = "platform_run_id"`
* `FIELD_SCENARIO_RUN_ID = "scenario_run_id"`
* `FIELD_PHASE_ID = "phase_id"`
* `FIELD_CONFIG_DIGEST = "config_digest"`
* `FIELD_WRITTEN_AT_UTC = "written_at_utc"`

### 1.7 Run pinning controls

* `CONFIG_DIGEST_ALGO = "sha256"`
* `CONFIG_DIGEST_FIELD = "config_digest"`
* `SCENARIO_EQUIVALENCE_KEY_INPUT = "sha256(canonical_json_v1)"`
* `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS = "oracle_input_manifest_uri,oracle_input_manifest_sha256,oracle_required_output_ids,oracle_sort_key_by_output_id,config_digest"`
* `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE = "json_sorted_keys_v1"`
* `SCENARIO_RUN_ID_DERIVATION_MODE = "deterministic_hash_v1"`

### 1.8 Runtime scope enforcement

* `REQUIRED_PLATFORM_RUN_ID_ENV_KEY = "REQUIRED_PLATFORM_RUN_ID"`
* `ACTIVE_RUN_ID_SOURCE = "env_required_platform_run_id"`

### 1.9 Runtime-path governance (single-path law)

* `PHASE_RUNTIME_PATH_MODE = "single_active_path_per_phase_run"`
* `PHASE_RUNTIME_PATH_PIN_REQUIRED = true`
* `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED = false`
* `RUNTIME_FALLBACK_REQUIRES_NEW_PHASE_EXECUTION_ID = true`
* `PHASE_RUNTIME_PATH_EVIDENCE_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/runtime_path_selection.json"`

---

## 2. Terraform State and Stack Handles

### 2.1 State backend

* `TF_STATE_BUCKET = "fraud-platform-dev-full-tfstate"`
* `TF_STATE_BUCKET_REGION = "eu-west-2"`
* `TF_STATE_ENCRYPTION_ENABLED = true`
* `TF_STATE_VERSIONING_ENABLED = true`
* `TF_STATE_PUBLIC_ACCESS_BLOCKED = true`
* `TF_LOCK_TABLE = "fraud-platform-dev-full-tf-locks"`

### 2.2 State keys (split stack posture)

* `TF_STATE_KEY_CORE = "dev_full/core/terraform.tfstate"`
* `TF_STATE_KEY_STREAMING = "dev_full/streaming/terraform.tfstate"`
* `TF_STATE_KEY_RUNTIME = "dev_full/runtime/terraform.tfstate"`
* `TF_STATE_KEY_DATA_ML = "dev_full/data_ml/terraform.tfstate"`
* `TF_STATE_KEY_OPS = "dev_full/ops/terraform.tfstate"`

### 2.3 Stack roots

* `TF_STACK_CORE_DIR = "infra/terraform/dev_full/core"`
* `TF_STACK_STREAMING_DIR = "infra/terraform/dev_full/streaming"`
* `TF_STACK_RUNTIME_DIR = "infra/terraform/dev_full/runtime"`
* `TF_STACK_DATA_ML_DIR = "infra/terraform/dev_full/data_ml"`
* `TF_STACK_OPS_DIR = "infra/terraform/dev_full/ops"`

### 2.4 Apply identity

* `ROLE_TERRAFORM_APPLY_DEV_FULL = "TO_PIN"`

---

## 3. S3 Buckets and Prefix Contracts

### 3.1 Bucket names

* `S3_OBJECT_STORE_BUCKET = "fraud-platform-dev-full-object-store"`
* `S3_EVIDENCE_BUCKET = "fraud-platform-dev-full-evidence"`
* `S3_ARTIFACTS_BUCKET = "fraud-platform-dev-full-artifacts"`

### 3.2 Bucket posture

* `S3_BUCKET_ENCRYPTION_ENABLED = true`
* `S3_BUCKET_PUBLIC_ACCESS_BLOCKED = true`
* `S3_BUCKET_VERSIONING_ENABLED = true`

### 3.3 Canonical path tokens

Allowed tokens in pattern handles:

* `{platform_run_id}`
* `{scenario_run_id}`
* `{phase_id}`
* `{output_id}`
* `{oracle_source_namespace}`
* `{oracle_engine_run_id}`
* `{dataset_fingerprint}`
* `{bundle_id}`

### 3.4 Oracle store (external input boundary)

* `ORACLE_SOURCE_NAMESPACE = "local_full_run-5"`
* `ORACLE_ENGINE_RUN_ID = "c25a2675fbfbacd952b13bb594880e92"`
* `S3_ORACLE_ROOT_PREFIX = "oracle-store/"`
* `S3_ORACLE_RUN_PREFIX_PATTERN = "oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/"`
* `S3_ORACLE_INPUT_PREFIX_PATTERN = "oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/"`
* `S3_STREAM_VIEW_PREFIX_PATTERN = "oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/stream_view/ts_utc/"`
* `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN = "oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/stream_view/ts_utc/output_id={output_id}/"`
* `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN = "oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/stream_view/ts_utc/output_id={output_id}/_stream_view_manifest.json"`

### 3.5 Oracle inlet policy handles

* `ORACLE_INLET_MODE = "external_pre_staged"`
* `ORACLE_INLET_PLATFORM_OWNERSHIP = "outside_platform_runtime_scope"`
* `ORACLE_INLET_ASSERTION_REQUIRED = true`

### 3.6 Archive and quarantine prefixes

* `S3_ARCHIVE_RUN_PREFIX_PATTERN = "archive/{platform_run_id}/"`
* `S3_ARCHIVE_EVENTS_PREFIX_PATTERN = "archive/{platform_run_id}/events/"`
* `S3_QUARANTINE_RUN_PREFIX_PATTERN = "quarantine/{platform_run_id}/"`
* `S3_QUARANTINE_PAYLOAD_PREFIX_PATTERN = "quarantine/{platform_run_id}/payloads/"`
* `S3_QUARANTINE_INDEX_PREFIX_PATTERN = "quarantine/{platform_run_id}/index/"`

### 3.7 Evidence prefixes (run scoped)

* `S3_EVIDENCE_ROOT_PREFIX = "evidence/"`
* `S3_EVIDENCE_RUN_ROOT_PATTERN = "evidence/runs/{platform_run_id}/"`
* `S3_RUN_CONTROL_ROOT_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/"`
* `EVIDENCE_PHASE_PREFIX_PATTERN = "evidence/runs/{platform_run_id}/{phase_id}/"`
* `EVIDENCE_RUN_JSON_KEY = "evidence/runs/{platform_run_id}/run.json"`
* `EVIDENCE_RUN_COMPLETED_KEY = "evidence/runs/{platform_run_id}/run_completed.json"`

### 3.8 Evidence path contracts by lane

* `RUN_PIN_PATH_PATTERN = "evidence/runs/{platform_run_id}/run_pin/run_header.json"`
* `RECEIPT_SUMMARY_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/receipt_summary.json"`
* `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/kafka_offsets_snapshot.json"`
* `QUARANTINE_SUMMARY_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/quarantine_summary.json"`
* `RTDL_CORE_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/rtdl_core/"`
* `DECISION_LANE_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/decision_lane/"`
* `CASE_LABELS_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/case_labels/"`
* `SPINE_RUN_REPORT_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/run_report.json"`
* `SPINE_RECONCILIATION_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/reconciliation.json"`
* `SPINE_NON_REGRESSION_PACK_PATTERN = "evidence/runs/{platform_run_id}/obs/non_regression_pack.json"`
* `OFS_MANIFEST_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/ofs/dataset_manifest.json"`
* `OFS_FINGERPRINT_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/ofs/dataset_fingerprint.json"`
* `MF_EVAL_REPORT_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/mf/eval_report.json"`
* `MF_CANDIDATE_BUNDLE_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/mf/candidate_bundle.json"`
* `MPR_PROMOTION_RECEIPT_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/mpr/promotion_receipt.json"`
* `MPR_ROLLBACK_DRILL_PATH_PATTERN = "evidence/runs/{platform_run_id}/learning/mpr/rollback_drill_report.json"`
* `FULL_VERDICT_PATH_PATTERN = "evidence/runs/{platform_run_id}/full_platform/final_verdict.json"`
* `TEARDOWN_COST_SNAPSHOT_PATH_PATTERN = "evidence/runs/{platform_run_id}/teardown/cost_guardrail_snapshot.json"`

### 3.9 Retention handles

* `RETENTION_EVIDENCE_DAYS = 365`
* `RETENTION_ARCHIVE_DAYS = 90`
* `RETENTION_QUARANTINE_DAYS = 45`
* `RETENTION_CLOUDWATCH_LOGS_DAYS = 14`
* `RETENTION_TRAINING_ARTIFACTS_DAYS = 180`
* `RETENTION_MLFLOW_METADATA_DAYS = 365`
* `RETENTION_MPR_EVENT_HISTORY_DAYS = 365`

---

## 4. MSK and Schema Registry Handles

### 4.1 MSK cluster identity

* `MSK_CLUSTER_NAME = "fraud-platform-dev-full-msk"`
* `MSK_CLUSTER_ARN = "arn:aws:kafka:eu-west-2:230372904534:cluster/fraud-platform-dev-full-msk/a38adf23-ea5e-4c99-a4cd-109afb1530a8-s3"` (materialized in M2.C)
* `MSK_BOOTSTRAP_BROKERS_SASL_IAM = "boot-6zhso8cu.c3.kafka-serverless.eu-west-2.amazonaws.com:9098"` (materialized in M2.C)
* `MSK_CLIENT_SUBNET_IDS = ["subnet-0f78c51075c563f8b","subnet-02a2247be3765e842"]` (materialized in M2.B)
* `MSK_SECURITY_GROUP_ID = "sg-07b93e3d50bacea7d"` (materialized in M2.B)

### 4.2 Secret path handles (MSK)

* `SSM_MSK_BOOTSTRAP_BROKERS_PATH = "/fraud-platform/dev_full/msk/bootstrap_brokers"`

### 4.3 Schema registry handles

* `GLUE_SCHEMA_REGISTRY_NAME = "fraud-platform-dev-full"`
* `GLUE_SCHEMA_COMPATIBILITY_MODE = "BACKWARD"`

### 4.4 Kafka defaults (v0)

* `KAFKA_PARTITIONS_HIGH_VOLUME_DEFAULT = 6`
* `KAFKA_PARTITIONS_LOW_VOLUME_DEFAULT = 3`
* `KAFKA_RETENTION_HIGH_VOLUME = "7d"`
* `KAFKA_RETENTION_LOW_VOLUME = "30d"`
* `KAFKA_RETENTION_GOVERNANCE = "90d"`
* `KAFKA_CLEANUP_POLICY_DEFAULT = "delete"`

---

## 5. Topic Map (Pinned)

### 5.1 Spine topics

* `FP_BUS_CONTROL_V1 = "fp.bus.control.v1"`
* `FP_BUS_TRAFFIC_FRAUD_V1 = "fp.bus.traffic.fraud.v1"`
* `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1 = "fp.bus.context.arrival_events.v1"`
* `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1 = "fp.bus.context.arrival_entities.v1"`
* `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1 = "fp.bus.context.flow_anchor.fraud.v1"`
* `FP_BUS_RTDL_V1 = "fp.bus.rtdl.v1"`
* `FP_BUS_AUDIT_V1 = "fp.bus.audit.v1"`
* `FP_BUS_CASE_TRIGGERS_V1 = "fp.bus.case.triggers.v1"`
* `FP_BUS_LABELS_EVENTS_V1 = "fp.bus.labels.events.v1"`

### 5.2 Learning/control topics

* `FP_BUS_LEARNING_OFS_REQUESTS_V1 = "fp.bus.learning.ofs.requests.v1"`
* `FP_BUS_LEARNING_OFS_EVENTS_V1 = "fp.bus.learning.ofs.events.v1"`
* `FP_BUS_LEARNING_MF_REQUESTS_V1 = "fp.bus.learning.mf.requests.v1"`
* `FP_BUS_LEARNING_MF_EVENTS_V1 = "fp.bus.learning.mf.events.v1"`
* `FP_BUS_LEARNING_REGISTRY_EVENTS_V1 = "fp.bus.learning.registry.events.v1"`

### 5.3 Partition key conventions

* `KAFKA_PARTITION_KEY_CONTROL = "platform_run_id"`
* `KAFKA_PARTITION_KEY_TRAFFIC = "merchant_id"`
* `KAFKA_PARTITION_KEY_CONTEXT = "merchant_id"`
* `KAFKA_PARTITION_KEY_RTDL = "event_id"`
* `KAFKA_PARTITION_KEY_AUDIT = "platform_run_id"`
* `KAFKA_PARTITION_KEY_CASE = "platform_run_id"`
* `KAFKA_PARTITION_KEY_LABELS = "platform_run_id"`
* `KAFKA_PARTITION_KEY_LEARNING = "platform_run_id"`

---

## 6. Container Image and Artifact Handles

### 6.1 ECR repository

* `ECR_REPO_NAME = "fraud-platform-dev-full"`
* `ECR_REPO_URI = "230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full"`

### 6.2 Image identity strategy

* `IMAGE_TAG_GIT_SHA_PATTERN = "git-{git_sha}"`
* `IMAGE_TAG_DEV_FULL_LATEST = "dev-full-latest"`
* `IMAGE_REFERENCE_MODE = "immutable_preferred"`

### 6.3 Build contract

* `IMAGE_BUILD_DRIVER = "github_actions"`
* `IMAGE_BUILD_CONTEXT_PATH = "."`
* `IMAGE_DOCKERFILE_PATH = "Dockerfile"`

### 6.4 Runtime entrypoint contract

* `ENTRYPOINT_ORACLE_STREAM_SORT`
* `ENTRYPOINT_ORACLE_CHECKER`
* `ENTRYPOINT_SR`
* `ENTRYPOINT_WSP`
* `ENTRYPOINT_IG_SERVICE`
* `ENTRYPOINT_RTDL_CORE_WORKER`
* `ENTRYPOINT_DECISION_LANE_WORKER`
* `ENTRYPOINT_CASE_TRIGGER_WORKER`
* `ENTRYPOINT_CM_SERVICE`
* `ENTRYPOINT_LS_SERVICE`
* `ENTRYPOINT_ENV_CONFORMANCE_WORKER`
* `ENTRYPOINT_REPORTER`
* `ENTRYPOINT_OFS_RUNNER`
* `ENTRYPOINT_MF_RUNNER`
* `ENTRYPOINT_MPR_RUNNER`

### 6.5 Oracle lane required output handles

* `ORACLE_REQUIRED_OUTPUT_IDS = ["s3_event_stream_with_fraud_6B","arrival_events_5B","s1_arrival_entities_6B","s3_flow_anchor_with_fraud_6B"]`
* `ORACLE_SORT_KEY_BY_OUTPUT_ID = {"s3_event_stream_with_fraud_6B":"ts_utc","arrival_events_5B":"ts_utc","s1_arrival_entities_6B":"ts_utc","s3_flow_anchor_with_fraud_6B":"ts_utc","s1_session_index_6B":"session_start_utc","s4_event_labels_6B":"flow_id,event_seq","s4_flow_truth_labels_6B":"flow_id","s4_flow_bank_view_6B":"flow_id"}`
* `ORACLE_SORT_KEY_ACTIVE_SCOPE = "use entries where output_id is in ORACLE_REQUIRED_OUTPUT_IDS for the current run"`

---

## 7. Managed Runtime Handles

### 7.1 Runtime strategy pins

* `RUNTIME_STRATEGY = "managed_first_hybrid"`
* `RUNTIME_DEFAULT_STREAM_ENGINE = "msk_flink"`
* `RUNTIME_DEFAULT_INGRESS_EDGE = "apigw_lambda_ddb"`
* `RUNTIME_EKS_USE_POLICY = "differentiating_services_only"`

### 7.2 EKS cluster and namespaces (selective custom-runtime lane)

* `EKS_CLUSTER_NAME = "fraud-platform-dev-full"`
* `EKS_CLUSTER_ARN = "TO_PIN"`
* `EKS_NAMESPACE_PLATFORM = "fraud-platform"`
* `EKS_NAMESPACE_INGRESS = "fraud-platform-ingress"`
* `EKS_NAMESPACE_RTDL = "fraud-platform-rtdl"`
* `EKS_NAMESPACE_CASE_LABELS = "fraud-platform-case-labels"`
* `EKS_NAMESPACE_OBS_GOV = "fraud-platform-obs-gov"`
* `EKS_NAMESPACE_LEARNING = "fraud-platform-learning"`

### 7.3 Flink runtime handles (MSK-integrated stream lanes)

* `FLINK_RUNTIME_MODE = "MSK_MANAGED_FLINK"`
* `FLINK_APP_WSP_STREAM_V0 = "fraud-platform-dev-full-wsp-stream-v0"`
* `FLINK_APP_SR_READY_V0 = "fraud-platform-dev-full-sr-ready-v0"`
* `FLINK_APP_RTDL_IEG_V0 = "fraud-platform-dev-full-rtdl-ieg-v0"`
* `FLINK_APP_RTDL_OFP_V0 = "fraud-platform-dev-full-rtdl-ofp-v0"`
* `FLINK_PARALLELISM_DEFAULT = 2`
* `FLINK_CHECKPOINT_INTERVAL_MS = 60000`
* `FLINK_CHECKPOINT_S3_PREFIX_PATTERN = "state/flink/{application_name}/"`

### 7.4 Ingress edge handles (API Gateway + Lambda + DynamoDB)

* `IG_EDGE_MODE = "apigw_lambda_ddb"`
* `APIGW_IG_API_NAME = "fraud-platform-dev-full-ig-edge"`
* `APIGW_IG_API_ID = "TO_PIN"`
* `APIGW_IG_STAGE = "v1"`
* `LAMBDA_IG_HANDLER_NAME = "fraud-platform-dev-full-ig-handler"`
* `DDB_IG_IDEMPOTENCY_TABLE = "fraud-platform-dev-full-ig-idempotency"`
* `DDB_IG_IDEMPOTENCY_PARTITION_KEY = "dedupe_key"`
* `DDB_IG_IDEMPOTENCY_TTL_FIELD = "ttl_epoch"`
* `IG_MAX_REQUEST_BYTES = 1048576`
* `IG_REQUEST_TIMEOUT_SECONDS = 30`
* `IG_INTERNAL_RETRY_MAX_ATTEMPTS = 3`
* `IG_INTERNAL_RETRY_BACKOFF_MS = 250`
* `IG_IDEMPOTENCY_TTL_SECONDS = 259200`
* `IG_DLQ_MODE = "sqs"`
* `IG_DLQ_QUEUE_NAME = "fraud-platform-dev-full-ig-dlq"`
* `IG_REPLAY_MODE = "dlq_replay_workflow"`
* `IG_RATE_LIMIT_RPS = 200`
* `IG_RATE_LIMIT_BURST = 400`

### 7.5 Runtime service/deployment handles (selective EKS custom lanes only)

* `K8S_DEPLOY_IG = "ig"`
* `K8S_DEPLOY_IEG = "ieg"`
* `K8S_DEPLOY_OFP = "ofp"`
* `K8S_DEPLOY_ARCHIVE_WRITER = "archive-writer"`
* `K8S_DEPLOY_DL = "dl"`
* `K8S_DEPLOY_DF = "df"`
* `K8S_DEPLOY_AL = "al"`
* `K8S_DEPLOY_DLA = "dla"`
* `K8S_DEPLOY_CASE_TRIGGER = "case-trigger"`
* `K8S_DEPLOY_CM = "cm"`
* `K8S_DEPLOY_LS = "ls"`
* `K8S_DEPLOY_ENV_CONFORMANCE = "env-conformance"`

### 7.6 Runtime service/deployment handles (learning)

* `K8S_JOB_OFS_DISPATCHER = "ofs-dispatcher"`
* `K8S_JOB_MF_DISPATCHER = "mf-dispatcher"`
* `K8S_DEPLOY_MPR = "mpr"`

### 7.7 Service discovery and ingress handles

* `IG_BASE_URL = "https://{api_id}.execute-api.eu-west-2.amazonaws.com/v1"`
* `IG_BASE_URL_EKS_FALLBACK = "http://ig.fraud-platform-ingress.svc.cluster.local:8080"`
* `IG_LISTEN_ADDR = "0.0.0.0"`
* `IG_PORT = 8080`
* `IG_INGEST_PATH = "/v1/ingest/push"`
* `IG_HEALTHCHECK_PATH = "/v1/ops/health"`
* `IG_AUTH_MODE = "api_key"`
* `IG_AUTH_HEADER_NAME = "X-IG-Api-Key"`

### 7.8 Runtime control knobs

* `READY_MESSAGE_FILTER = "platform_run_id=={platform_run_id}"`
* `WSP_MAX_INFLIGHT = 1`
* `WSP_RETRY_MAX_ATTEMPTS = 5`
* `WSP_RETRY_BACKOFF_MS = 500`
* `WSP_STOP_ON_NONRETRYABLE = true`
* `RTDL_CORE_CONSUMER_GROUP_ID = "fraud-platform-dev-full-rtdl-core-v0"`
* `RTDL_CORE_OFFSET_COMMIT_POLICY = "commit_after_durable_write"`
* `RTDL_CAUGHT_UP_LAG_MAX = 10`
* `REPORTER_LOCK_BACKEND = "aurora_advisory_lock"`
* `REPORTER_LOCK_KEY_PATTERN = "reporter:{platform_run_id}"`

---

## 8. Aurora and Redis Handles

### 8.1 Aurora posture

* `AURORA_ENGINE = "aurora-postgresql"`
* `AURORA_MODE = "serverless-v2"`
* `AURORA_HA = "multi_az_writer_reader"`
* `AURORA_ACU_RANGE = "0.5-8"`
* `AURORA_CLUSTER_IDENTIFIER = "fraud-platform-dev-full-aurora"`
* `AURORA_DB_NAME = "fraud_platform"`

### 8.2 Redis posture

* `REDIS_CLUSTER_NAME = "fraud-platform-dev-full-redis"`
* `REDIS_MODE = "elasticache_redis"`

### 8.3 Secret path handles (Aurora/Redis)

* `SSM_AURORA_ENDPOINT_PATH = "/fraud-platform/dev_full/aurora/endpoint"`
* `SSM_AURORA_READER_ENDPOINT_PATH = "/fraud-platform/dev_full/aurora/reader_endpoint"`
* `SSM_AURORA_USERNAME_PATH = "/fraud-platform/dev_full/aurora/username"`
* `SSM_AURORA_PASSWORD_PATH = "/fraud-platform/dev_full/aurora/password"`
* `SSM_REDIS_ENDPOINT_PATH = "/fraud-platform/dev_full/redis/endpoint"`

---

## 9. Data and ML Lane Handles

### 9.1 Databricks handles

* `DBX_WORKSPACE_NAME = "fraud-platform-dev-full"`
* `DBX_WORKSPACE_URL = "TO_PIN"`
* `DBX_COMPUTE_POLICY = "job-clusters-only"`
* `DBX_AUTOSCALE_WORKERS = "1-8"`
* `DBX_AUTO_TERMINATE_MINUTES = 20`
* `DBX_JOB_OFS_BUILD_V0 = "fraud-platform-dev-full-ofs-build-v0"`
* `DBX_JOB_OFS_QUALITY_GATES_V0 = "fraud-platform-dev-full-ofs-quality-v0"`

### 9.2 SageMaker handles

* `SM_TRAINING_JOB_NAME_PREFIX = "fraud-platform-dev-full-mtrain"`
* `SM_BATCH_TRANSFORM_JOB_NAME_PREFIX = "fraud-platform-dev-full-mbatch"`
* `SM_ENDPOINT_NAME = "fraud-platform-dev-full-online-v0"`
* `SM_MODEL_PACKAGE_GROUP_NAME = "fraud-platform-dev-full-models"`
* `SM_ENDPOINT_COUNT_V0 = 1`
* `SM_SERVING_MODE = "realtime_plus_batch"`

### 9.3 MLflow handles

* `MLFLOW_HOSTING_MODE = "databricks_managed"`
* `MLFLOW_EXPERIMENT_PATH = "/Shared/fraud-platform/dev_full"`
* `MLFLOW_MODEL_NAME = "fraud-platform-dev-full"`

### 9.4 Secret path handles (Databricks/MLflow/SageMaker)

* `SSM_DATABRICKS_WORKSPACE_URL_PATH = "/fraud-platform/dev_full/databricks/workspace_url"`
* `SSM_DATABRICKS_TOKEN_PATH = "/fraud-platform/dev_full/databricks/token"`
* `SSM_MLFLOW_TRACKING_URI_PATH = "/fraud-platform/dev_full/mlflow/tracking_uri"`
* `SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH = "/fraud-platform/dev_full/sagemaker/model_exec_role_arn"`

---

## 10. Orchestration Handles (Step Functions + MWAA)

### 10.1 Step Functions state machines

* `SFN_PLATFORM_RUN_ORCHESTRATOR_V0 = "fraud-platform-dev-full-platform-run-v0"`
* `SFN_LEARNING_PIPELINE_GATE_V0 = "fraud-platform-dev-full-learning-gate-v0"`
* `SFN_FINAL_VERDICT_AGGREGATOR_V0 = "fraud-platform-dev-full-final-verdict-v0"`
* `SR_READY_COMMIT_AUTHORITY = "step_functions_only"`
* `SR_READY_COMMIT_STATE_MACHINE = "SFN_PLATFORM_RUN_ORCHESTRATOR_V0"`
* `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF = true`
* `SR_READY_COMMIT_RECEIPT_PATH_PATTERN = "evidence/runs/{platform_run_id}/sr/ready_commit_receipt.json"`

### 10.2 Failure taxonomy handles

* `DFULL_SFN_B1 = "PRECHECK_OR_CONFIG_INVALID"`
* `DFULL_SFN_B2 = "RUNTIME_HEALTH_OR_DEPENDENCY_UNAVAILABLE"`
* `DFULL_SFN_B3 = "EVIDENCE_MISSING_OR_INVALID"`
* `DFULL_SFN_B4 = "ROLLBACK_OR_COMPENSATION_FAILED"`
* `DFULL_SFN_B5 = "COST_GUARDRAIL_BREACH"`

### 10.3 MWAA handles

* `AIRFLOW_MODE = "MWAA"`
* `MWAA_ENV_NAME = "fraud-platform-dev-full"`
* `MWAA_DAG_PLATFORM_GUARDRAIL = "dev_full_platform_guardrail_v0"`
* `MWAA_DAG_OFS_SCHEDULE = "dev_full_ofs_schedule_v0"`
* `MWAA_DAG_MF_SCHEDULE = "dev_full_mf_schedule_v0"`

### 10.4 Secret path handles (MWAA)

* `SSM_MWAA_WEBSERVER_URL_PATH = "/fraud-platform/dev_full/mwaa/webserver_url"`

---

## 11. IAM and Secret Role Map

### 11.1 Required IAM role handles (design-authority pinned set)

* `ROLE_TERRAFORM_APPLY_DEV_FULL = "TO_PIN"`
* `ROLE_EKS_NODEGROUP_DEV_FULL = "arn:aws:iam::230372904534:role/fraud-platform-dev-full-eks-nodegroup"` (materialized in M2.B)
* `ROLE_EKS_RUNTIME_PLATFORM_BASE = "arn:aws:iam::230372904534:role/fraud-platform-dev-full-runtime-platform-base"` (materialized in M2.B)
* `ROLE_FLINK_EXECUTION = "TO_PIN"`
* `ROLE_LAMBDA_IG_EXECUTION = "TO_PIN"`
* `ROLE_APIGW_IG_INVOKE = "TO_PIN"`
* `ROLE_DDB_IG_IDEMPOTENCY_RW = "TO_PIN"`
* `ROLE_STEP_FUNCTIONS_ORCHESTRATOR = "TO_PIN"`
* `ROLE_MWAA_EXECUTION = "TO_PIN"`
* `ROLE_SAGEMAKER_EXECUTION = "TO_PIN"`
* `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS = "TO_PIN"`

### 11.2 Additional runtime role handles

* `ROLE_EKS_IRSA_IG`
* `ROLE_EKS_IRSA_RTDL`
* `ROLE_EKS_IRSA_DECISION_LANE`
* `ROLE_EKS_IRSA_CASE_LABELS`
* `ROLE_EKS_IRSA_OBS_GOV`
* `ROLE_EKS_IRSA_LEARNING`

### 11.3 Secret path handles (full list)

* `/fraud-platform/dev_full/msk/bootstrap_brokers`
* `/fraud-platform/dev_full/aurora/endpoint`
* `/fraud-platform/dev_full/aurora/reader_endpoint`
* `/fraud-platform/dev_full/aurora/username`
* `/fraud-platform/dev_full/aurora/password`
* `/fraud-platform/dev_full/redis/endpoint`
* `/fraud-platform/dev_full/databricks/workspace_url`
* `/fraud-platform/dev_full/databricks/token`
* `/fraud-platform/dev_full/mlflow/tracking_uri`
* `/fraud-platform/dev_full/sagemaker/model_exec_role_arn`
* `/fraud-platform/dev_full/mwaa/webserver_url`
* `/fraud-platform/dev_full/ig/api_key`

### 11.4 No-plaintext policy handles

* `SECRETS_BACKEND = "ssm_and_secrets_manager"`
* `SECRETS_PLAINTEXT_OUTPUT_ALLOWED = false`
* `KMS_KEY_ALIAS_PLATFORM = "alias/fraud-platform-dev-full"`

---

## 12. Observability and Governance Handles

### 12.1 Logging and metrics handles

* `CLOUDWATCH_LOG_GROUP_PREFIX = "/fraud-platform/dev_full"`
* `LOG_RETENTION_DAYS = 14`
* `OTEL_ENABLED = true`
* `OTEL_COLLECTOR_SERVICE = "otel-collector"`
* `OTEL_EXPORTER_PRIMARY = "cloudwatch"`
* `OTEL_PROPAGATORS = "tracecontext,baggage"`
* `CORRELATION_MODE = "w3c_trace_context_plus_run_headers"`
* `CORRELATION_REQUIRED_FIELDS = "platform_run_id,scenario_run_id,phase_id,event_id,runtime_lane,trace_id"`
* `CORRELATION_HEADERS_REQUIRED = "traceparent,tracestate,x-fp-platform-run-id,x-fp-phase-id,x-fp-event-id"`
* `CORRELATION_ENFORCEMENT_FAIL_CLOSED = true`
* `CORRELATION_AUDIT_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/correlation_audit.json"`

### 12.2 Dashboard and alert handles

* `CW_DASHBOARD_PLATFORM_OPERATIONS = "fraud-platform-dev-full-operations"`
* `CW_DASHBOARD_COST_GUARDRAIL = "fraud-platform-dev-full-cost-guardrail"`
* `ALARM_PLATFORM_ERROR_RATE = "fraud-platform-dev-full-error-rate"`
* `ALARM_RTDL_LAG = "fraud-platform-dev-full-rtdl-lag"`
* `ALARM_IG_4XX_5XX = "fraud-platform-dev-full-ig-http-anomaly"`

### 12.3 Governance append handles

* `GOV_APPEND_LOG_PATH_PATTERN = "evidence/runs/{platform_run_id}/governance/append_log.jsonl"`
* `GOV_RUN_CLOSE_MARKER_PATH_PATTERN = "evidence/runs/{platform_run_id}/governance/closure_marker.json"`

---

## 13. Cost Guardrail and Teardown Handles

### 13.1 Cost capture scope

* `COST_CAPTURE_SCOPE = "aws_plus_databricks"`
* `AWS_COST_CAPTURE_ENABLED = true`
* `DATABRICKS_COST_CAPTURE_ENABLED = true`

### 13.2 Budget resources

* `AWS_BUDGET_NAME = "fraud-platform-dev-full-monthly"`
* `AWS_BUDGET_NOTIFICATION_EMAIL = "TO_PIN"`
* `COST_GUARDRAIL_SNAPSHOT_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/cost_guardrail_snapshot.json"`

### 13.3 Teardown posture

* `TEARDOWN_NON_ESSENTIAL_DEFAULT = "scale_to_zero_or_destroy"`
* `TEARDOWN_BLOCK_ON_RESIDUAL_RISK = true`
* `TEARDOWN_RESIDUAL_SCAN_PATH_PATTERN = "evidence/runs/{platform_run_id}/teardown/residual_scan.json"`

### 13.4 Cost-to-outcome control handles

* `PHASE_BUDGET_ENVELOPE_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/phase_budget_envelope.json"`
* `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/phase_cost_outcome_receipt.json"`
* `DAILY_COST_POSTURE_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/daily_cost_posture.json"`
* `PHASE_COST_OUTCOME_REQUIRED = true`
* `PHASE_ENVELOPE_REQUIRED = true`
* `PHASE_COST_HARD_STOP_ON_MISSING_OUTCOME = true`
* `COST_POSTURE_REVIEW_CADENCE_HOURS = 24`
* `COST_OUTCOME_RECEIPT_REQUIRED_FIELDS = "phase_id,phase_execution_id,window_start_utc,window_end_utc,spend_amount,spend_currency,artifacts_emitted,decision_or_risk_retired"`

---

## 14. Open Materialization Handles (Fail-Closed)

These are intentionally explicit and must be pinned before first `dev-full-up` execution.

1. `ROLE_TERRAFORM_APPLY_DEV_FULL`
2. `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`
3. `ROLE_MWAA_EXECUTION`
4. `ROLE_SAGEMAKER_EXECUTION`
5. `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS`
6. `EKS_CLUSTER_ARN`
7. `DBX_WORKSPACE_URL`
8. `AWS_BUDGET_NOTIFICATION_EMAIL`
9. `APIGW_IG_API_ID`
10. `ROLE_FLINK_EXECUTION`
11. `ROLE_LAMBDA_IG_EXECUTION`
12. `ROLE_APIGW_IG_INVOKE`
13. `ROLE_DDB_IG_IDEMPOTENCY_RW`

---

## 15. Change Workflow (Registry-First)

1. Update this registry.
2. Update Terraform/workflows/runtime code to consume handle keys.
3. Run handle-conformance checks (`P0` gate).
4. Record decision trail and run-level evidence.

No phase execution is valid if step 1 is skipped.
