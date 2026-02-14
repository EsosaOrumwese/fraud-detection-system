# DEV_MIN HANDLES REGISTRY — v0 (Single Source of Truth)

## 0. Document Control

### 0.1 Status

* **Status:** v0 (draft-initial; Section 0 complete)
* **As-of:** 2026-02-12 (Europe/London)
* **Purpose:** Pin **all names/paths/IDs** required to provision and operate `dev_min` so that:

  * code and docs do not invent resource names,
  * Codex cannot drift by renaming wiring surfaces,
  * and runs are reproducible and auditable.

### 0.2 Audience

* **Designer / Spec Authority:** GPT-5.2 Thinking (this registry is authoritative)
* **Implementer:** Codex (fills in concrete values and wires infra/code to these keys)
* **Operator:** You (uses these handles via CLI/terraform outputs, but does not edit ad hoc)

### 0.3 Authority Boundaries

**Pinned (MUST follow)**

* **Single source of truth:** No dev_min resource name/path/topic/SSM key may be used in code, Terraform, or docs unless it is defined here.
* **No duplication:** Other docs (runbook twin, Terraform notes) reference these keys; they do not redefine names.
* **No laptop dependency:** All runtime handles correspond to managed compute + managed substrate.
* **Budget posture:** demo→destroy, no NAT, no always-on LB, no always-on fleets (keys reflect this by design).

**Implementer freedom (Codex MAY choose)**

* Concrete values (exact bucket names, cluster names, etc.) as long as they comply with:

  * region pins,
  * uniqueness constraints,
  * and cost/teardown posture.

### 0.4 References (normative)

* `dev_min_spine_green_v0_run_process_flow.md` (phases reference these handles)
* `dev-min_managed-substrate_migration.design-authority.v0.md` (migration constraints, prohibitions, budget posture) 
* Topic set required for Spine Green v0 is pinned by handle keys (Appendix B of runbook; registry is the truth).

### 0.5 Change control rules (pinned)

* Any handle change MUST:

  1. update this registry (with a version bump if needed),
  2. update any dependent Terraform/code references,
  3. be recorded in the PR notes (what changed + why).
* Handles MUST be stable across runs; avoid renaming unless absolutely necessary.

### 0.6 Naming conventions (pinned)

* Handle keys are **UPPER_SNAKE_CASE**.
* Values are opaque strings/paths/IDs.
* All AWS resources MUST carry tags:

  * `project=fraud-platform`
  * `env=dev_min`
  * `owner=esosa`
  * `expires_at=<YYYY-MM-DD>` (demo resources must include this tag)

---

## 1. Global Constants (Pinned)

These constants apply to **all** dev_min infrastructure and runtime wiring. They are intentionally small and high-signal.

### 1.1 Project identity

* `PROJECT_SLUG = "fraud-platform"`
* `ENV_NAME = "dev_min"`

### 1.2 Region pins

* `AWS_REGION = "eu-west-2"` (London)
* `CONFLUENT_CLOUD_PROVIDER = "AWS"`
* `CONFLUENT_REGION = "eu-west-2"` (London)

### 1.3 Cost posture constants

* `MONTHLY_BUDGET_AMOUNT = 30`
* `MONTHLY_BUDGET_UNIT = "USD"` *(AWS Budgets provider/account constraint)*
* `DEMO_DESTROY_DEFAULT = true`
* `FORBID_NAT_GATEWAY = true`
* `FORBID_ALWAYS_ON_LOAD_BALANCER = true`
* `FORBID_ALWAYS_ON_FLEETS = true`

### 1.4 Tagging schema (required on all AWS resources)

* `TAG_PROJECT_KEY = "project"` → value must be `"fraud-platform"`
* `TAG_ENV_KEY = "env"` → value must be `"dev_min"`
* `TAG_OWNER_KEY = "owner"` → value must be `"esosa"`
* `TAG_EXPIRES_AT_KEY = "expires_at"` → value is operator-set date string `YYYY-MM-DD`

### 1.5 Run identity field names (for config/evidence consistency)

These are the canonical field names used in config and evidence payloads:

* `FIELD_PLATFORM_RUN_ID = "platform_run_id"`
* `FIELD_SCENARIO_RUN_ID = "scenario_run_id"`
* `FIELD_PHASE_ID = "phase_id"`
* `FIELD_WRITTEN_AT_UTC = "written_at_utc"`

### 1.6 Run pinning + scenario derivation controls

* `CONFIG_DIGEST_ALGO = "sha256"`
* `CONFIG_DIGEST_FIELD = "config_digest"`
* `SCENARIO_EQUIVALENCE_KEY_INPUT = "sha256(canonical_json_v1)"`
* `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS = "oracle_seed_manifest_uri,oracle_seed_manifest_sha256,oracle_required_output_ids,oracle_sort_key_by_output_id,config_digest"`
* `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE = "json_sorted_keys_v1"`
* `SCENARIO_RUN_ID_DERIVATION_MODE = "deterministic_hash_v1"`

`SCENARIO_EQUIVALENCE_KEY_INPUT` is computed at P1 execution from the canonical
field set above. It must not include run-unique fields (for example
`platform_run_id` or timestamps) so equivalent reruns resolve to the same
scenario identity surface.

### 1.7 Runtime scope enforcement (no drift)

* `REQUIRED_PLATFORM_RUN_ID_ENV_KEY = "REQUIRED_PLATFORM_RUN_ID"`
* `ACTIVE_RUN_ID_SOURCE = "env_required_platform_run_id"`

(If you later add additional scope keys, they must be pinned here.)

---

## 2. Terraform State Handles

These handles pin how Terraform state is stored and locked for dev_min. This is mandatory to make bring-up/teardown reproducible and safe.

### 2.1 Remote state backend (core)

* `TF_STATE_BUCKET`

  * S3 bucket name for all Terraform state (core + confluent + demo).

* `TF_STATE_BUCKET_REGION`

  * must equal `AWS_REGION`.

* `TF_STATE_VERSIONING_ENABLED = true`

* `TF_STATE_PUBLIC_ACCESS_BLOCKED = true`

* `TF_STATE_ENCRYPTION_ENABLED = true`

### 2.2 State keys (separate core vs confluent vs demo)

* `TF_STATE_KEY_CORE = "dev_min/core/terraform.tfstate"`
* `TF_STATE_KEY_CONFLUENT = "dev_min/confluent/terraform.tfstate"`
* `TF_STATE_KEY_DEMO = "dev_min/demo/terraform.tfstate"`

### 2.3 State lock (DynamoDB)

* `TF_LOCK_TABLE`

  * DynamoDB table name used for Terraform state locking.

### 2.4 Terraform stack roots (repo layout pins)

These are the pinned repo locations (used by operator scripts and Codex automation):

* `TF_STACK_CORE_DIR = "infra/terraform/dev_min/core"`
* `TF_STACK_CONFLUENT_DIR = "infra/terraform/dev_min/confluent"`
* `TF_STACK_DEMO_DIR = "infra/terraform/dev_min/demo"`

### 2.5 Terraform apply identity (operator)

* `AWS_PROFILE_NAME` *(optional)*

  * if used, name of AWS profile operators/CI should use.
* `ROLE_TERRAFORM_APPLY`

  * IAM role assumed by Terraform runner (operator/CI).

---

## 3. AWS S3 Buckets + Prefix Contracts

These handles pin **where data lives** in dev_min. Buckets are provisioned by Terraform **core** (persistent, low-cost). All prefixes are **run-scoped** unless explicitly marked otherwise.

### 3.1 Buckets (names)

* `S3_ORACLE_BUCKET`

  * S3 bucket name that holds oracle inputs + stream_view outputs (dev_min oracle store).
* `S3_ARCHIVE_BUCKET`

  * S3 bucket name that holds bounded archive outputs (dev_min archive store).
* `S3_QUARANTINE_BUCKET`

  * S3 bucket name that holds quarantined payloads + related artifacts.
* `S3_EVIDENCE_BUCKET`

  * S3 bucket name that holds run evidence bundles (proof artifacts).

**Bucket posture (pinned defaults)**

* `S3_BUCKET_VERSIONING_ENABLED = true` *(at minimum for TF state + evidence; may be enabled for all)*
* `S3_BUCKET_PUBLIC_ACCESS_BLOCKED = true`
* `S3_BUCKET_ENCRYPTION_ENABLED = true`

### 3.2 Canonical prefix token conventions (used in patterns)

These are the only allowed template tokens inside prefix patterns:

* `{platform_run_id}`
* `{source_platform_run_id}` *(optional for seed-source selectors)*
* `{scenario_run_id}` *(optional where relevant)*
* `{output_id}`
* `{phase_id}` *(P0..P12)*

### 3.3 Oracle store prefixes (dev_min)

* `S3_ORACLE_RUN_PREFIX_PATTERN = "oracle/{platform_run_id}/"`

  * Root prefix for all oracle artifacts for a run.

* `S3_ORACLE_INPUT_PREFIX_PATTERN = "oracle/{platform_run_id}/inputs/"`

  * Root prefix for sealed oracle inputs copied/written for this run.

* `S3_STREAM_VIEW_PREFIX_PATTERN = "oracle/{platform_run_id}/stream_view/"`

  * Root prefix for all stream_view outputs for this run.

* `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN = "oracle/{platform_run_id}/stream_view/output_id={output_id}/"`

  * Output-specific stream_view prefix.

* `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN = "oracle/{platform_run_id}/stream_view/output_id={output_id}/_stream_view_manifest.json"`

* `S3_STREAM_SORT_RECEIPT_KEY_PATTERN = "oracle/{platform_run_id}/stream_view/output_id={output_id}/_stream_sort_receipt.json"`

### 3.4 Archive prefixes (dev_min, bounded)

* `S3_ARCHIVE_RUN_PREFIX_PATTERN = "archive/{platform_run_id}/"`

  * Root prefix for bounded archive outputs for this run.

* `S3_ARCHIVE_EVENTS_PREFIX_PATTERN = "archive/{platform_run_id}/events/"`

  * Where archive writer stores event history artifacts (format pinned elsewhere).

### 3.5 Quarantine prefixes (dev_min)

* `S3_QUARANTINE_RUN_PREFIX_PATTERN = "quarantine/{platform_run_id}/"`

  * Root prefix for all quarantined payloads and metadata for the run.

* `S3_QUARANTINE_PAYLOAD_PREFIX_PATTERN = "quarantine/{platform_run_id}/payloads/"`

* `S3_QUARANTINE_INDEX_PREFIX_PATTERN = "quarantine/{platform_run_id}/index/"`

### 3.6 Evidence bundle prefixes (dev_min)

* `S3_EVIDENCE_ROOT_PREFIX = "evidence/"`
* `S3_EVIDENCE_RUN_ROOT_PATTERN = "evidence/runs/{platform_run_id}/"`

  * **This is the canonical run evidence root used by the dev_min runbook.**

Convenience patterns (must align with Section 6 evidence contract):

* `EVIDENCE_PHASE_PREFIX_PATTERN = "evidence/runs/{platform_run_id}/{phase_id}/"`
* `EVIDENCE_RUN_JSON_KEY = "evidence/runs/{platform_run_id}/run.json"`
* `EVIDENCE_RUN_COMPLETED_KEY = "evidence/runs/{platform_run_id}/run_completed.json"`

### 3.6.1 Evidence path contracts by lane (pinned)

* `RECEIPT_SUMMARY_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/receipt_summary.json"`
* `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/kafka_offsets_snapshot.json"`
* `QUARANTINE_INDEX_PATH_PATTERN = "evidence/runs/{platform_run_id}/ingest/quarantine_summary.json"`
* `OFFSETS_SNAPSHOT_PATH_PATTERN = "evidence/runs/{platform_run_id}/rtdl_core/offsets_snapshot.json"`
* `RTDL_CORE_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/rtdl_core/"`
* `DECISION_LANE_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/decision_lane/"`
* `DLA_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/decision_lane/audit_summary.json"`
* `CASE_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/case_labels/case_summary.json"`
* `LABEL_EVIDENCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/case_labels/label_summary.json"`
* `ENV_CONFORMANCE_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/environment_conformance.json"`
* `RECONCILIATION_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/reconciliation.json"`
* `REPLAY_ANCHORS_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/replay_anchors.json"`
* `RUN_REPORT_PATH_PATTERN = "evidence/runs/{platform_run_id}/obs/run_report.json"`
* `RUN_CLOSURE_MARKER_PATH_PATTERN = "evidence/runs/{platform_run_id}/run_completed.json"`

### 3.7 Lifecycle intent (pinned defaults; exact rules provisioned in core Terraform)

* `S3_ORACLE_RETENTION_DAYS = 14`
* `S3_QUARANTINE_RETENTION_DAYS = 30`
* `S3_ARCHIVE_RETENTION_DAYS = 60`
* `S3_EVIDENCE_RETENTION_DAYS = null` *(no automatic expiry by default)*

### 3.8 Oracle seed source handles (P3 policy lock)

* `ORACLE_SEED_SOURCE_MODE = "s3_to_s3_only"`
* `ORACLE_SEED_SOURCE_BUCKET = "fraud-platform-dev-min-object-store"`
* `ORACLE_SEED_SOURCE_PREFIX_PATTERN = "oracle/{source_platform_run_id}/inputs/"`
* `ORACLE_SEED_SOURCE_PLATFORM_RUN_ID = "platform_20260213T214223Z"`
* `ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED = false`

`ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED` remains explicit so automation cannot
quietly reintroduce local bootstrap behavior. Dev_min v0 policy is managed
object-store-only for P3 seed/sync.

Current-cycle note:
* Seed source uses canonical `oracle/...` style with explicit source-run selector (not legacy `dev_min/...`).
* The active run remains pre-staged under `oracle/{platform_run_id}/inputs/`; the source selector above stays as
  deterministic fallback if `SEED_REQUIRED` is entered.

---

## 4. Confluent Cloud Handles

These handles pin the Confluent Cloud environment, cluster shape, and how runtime credentials are stored and retrieved.

### 4.1 Confluent environment and cluster identity

* `CONFLUENT_ENV_NAME = "dev_min"`

  * Display name (may be prefixed by project slug if you prefer).

* `CONFLUENT_CLUSTER_NAME = "dev-min-kafka"`

  * Display name.

* `CONFLUENT_CLUSTER_TYPE = "Basic"`

* `CONFLUENT_CLUSTER_CLOUD = "AWS"`

* `CONFLUENT_CLUSTER_REGION = "eu-west-2"`

### 4.2 Confluent bootstrap and API keys (stored in AWS SSM)

These are SSM parameter paths (SecureString where applicable). Values are written by the dedicated Confluent Terraform stack and are managed through that stack lifecycle.

* `SSM_CONFLUENT_BOOTSTRAP_PATH = "/fraud-platform/dev_min/confluent/bootstrap"`
* `SSM_CONFLUENT_API_KEY_PATH = "/fraud-platform/dev_min/confluent/api_key"`
* `SSM_CONFLUENT_API_SECRET_PATH = "/fraud-platform/dev_min/confluent/api_secret"`

### 4.2.1 Confluent Terraform management credential input (operator/CI)

* `TF_VAR_CONFLUENT_CLOUD_API_KEY = "TF_VAR_confluent_cloud_api_key"`
* `TF_VAR_CONFLUENT_CLOUD_API_SECRET = "TF_VAR_confluent_cloud_api_secret"`

These are input variable names for the dedicated Confluent Terraform stack.

### 4.3 Confluent access model (pinned for v0)

* `CONFLUENT_CREDENTIAL_OWNER_MODE = "user_creds_dev"`

  * v0 allows user-owned API keys for learning/dev, but keys must be stored in SSM and rotated/removed on teardown.

* `CONFLUENT_ACL_MODEL = "least_privilege"`

  * Even in dev, enforce least privilege per producer/consumer role.

### 4.4 Kafka client defaults (names only; actual values pinned later if needed)

* `KAFKA_SECURITY_PROTOCOL = "SASL_SSL"`
* `KAFKA_SASL_MECHANISM = "PLAIN"`
* `KAFKA_CLIENT_ID_PREFIX = "fraud-platform-devmin"`

### 4.5 Topic configuration defaults (apply unless overridden)

* `KAFKA_DEFAULT_PARTITIONS_HIGH_VOLUME = 3`
* `KAFKA_DEFAULT_PARTITIONS_LOW_VOLUME = 1`
* `KAFKA_RETENTION_MS_HIGH_VOLUME = 86400000` *(1 day)*
* `KAFKA_RETENTION_MS_LOW_VOLUME = 259200000` *(3 days)*
* `KAFKA_CLEANUP_POLICY_DEFAULT = "delete"`

---

## 5. Kafka Topic Map (Pinned)

These handles are the **only** canonical topic identifiers for Spine Green v0 in dev_min. Code, Terraform, and the runbook must reference these keys.

### 5.1 Control / governance

* `FP_BUS_CONTROL_V1 = "fp.bus.control.v1"`

### 5.2 Traffic (fraud-mode default)

* `FP_BUS_TRAFFIC_FRAUD_V1 = "fp.bus.traffic.fraud.v1"`

*(Optional baseline-mode compatibility — not required for Spine Green v0 unless you explicitly run baseline mode)*

* `FP_BUS_TRAFFIC_BASELINE_V1 = "fp.bus.traffic.baseline.v1"` *(optional)*

### 5.3 Context

* `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1 = "fp.bus.context.arrival_events.v1"`
* `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1 = "fp.bus.context.arrival_entities.v1"`
* `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1 = "fp.bus.context.flow_anchor.fraud.v1"`

*(Optional baseline-mode compatibility)*

* `FP_BUS_CONTEXT_FLOW_ANCHOR_BASELINE_V1 = "fp.bus.context.flow_anchor.baseline.v1"` *(optional)*

### 5.4 RTDL + audit

* `FP_BUS_RTDL_V1 = "fp.bus.rtdl.v1"`
* `FP_BUS_AUDIT_V1 = "fp.bus.audit.v1"`

### 5.5 Case + labels

* `FP_BUS_CASE_TRIGGERS_V1 = "fp.bus.case.triggers.v1"`
* `FP_BUS_LABELS_EVENTS_V1 = "fp.bus.labels.events.v1"` *(optional if you emit derived label events)*

### 5.6 Partition key conventions (pinned)

These are conventions used for deterministic partitioning; they do not change the schema, only the producer key selection.

* `KAFKA_PARTITION_KEY_CONTEXT = "merchant_id"`

  * Applies to all `fp.bus.context.*` topics.

* `KAFKA_PARTITION_KEY_TRAFFIC_DEFAULT = "merchant_id"`

  * v0 default (matches merchant-local routing expectation).

* `KAFKA_PARTITION_KEY_CONTROL = "platform_run_id"`

### 5.7 Topic parameters (defaults by class)

These defaults should be applied unless a topic requires different settings.

**High volume (traffic + context + rtdl):**

* `PARTITIONS = KAFKA_DEFAULT_PARTITIONS_HIGH_VOLUME`
* `RETENTION_MS = KAFKA_RETENTION_MS_HIGH_VOLUME`
* `CLEANUP_POLICY = KAFKA_CLEANUP_POLICY_DEFAULT`

**Low volume (control + case + labels):**

* `PARTITIONS = KAFKA_DEFAULT_PARTITIONS_LOW_VOLUME`
* `RETENTION_MS = KAFKA_RETENTION_MS_LOW_VOLUME`
* `CLEANUP_POLICY = KAFKA_CLEANUP_POLICY_DEFAULT`

---

## 6. Container Image + ECR Handles (Pinned)

These handles pin how dev_min runtime images are built, tagged, stored, and referenced by ECS tasks/services. They implement Phase P(-1) in the runbook.

### 6.1 ECR repository

* `ECR_REPO_NAME = "fraud-platform-dev-min"`

  * Single image repo for v0 (one image strategy).

* `ECR_REPO_URI`

  * Fully qualified ECR URI (computed from AWS account + region + repo name).

### 6.2 Image identity strategy (pinned)

* `IMAGE_TAG_GIT_SHA_PATTERN = "git-{git_sha}"`

  * Immutable tag for reproducibility.

* `IMAGE_TAG_DEV_MIN_LATEST = "dev-min-latest"` *(optional convenience)*

* `IMAGE_REFERENCE_MODE = "immutable_preferred"`

  * ECS task/service definitions must be able to pin to the immutable tag.
  * Mutable tag may exist for operator convenience only.

### 6.3 Evidence recording of image provenance

* `IMAGE_DIGEST_EVIDENCE_FIELD = "image_digest"`
* `IMAGE_TAG_EVIDENCE_FIELD = "image_tag"`
* `IMAGE_GIT_SHA_EVIDENCE_FIELD = "git_sha"`

These fields appear in `run.json` in the evidence bundle (Section 6 of the runbook).

### 6.4 Image build mechanism (pinned interface)

Pick at least one (implementer chooses exact mechanics, but the interface is pinned):

* `IMAGE_BUILD_PATH = "."` *(repo root build context, unless you change it)*
* `IMAGE_DOCKERFILE_PATH = "Dockerfile"` *(or pinned path if not root)*

**Allowed build drivers:**

* `IMAGE_BUILD_DRIVER = "github_actions"` *(recommended)*
  or
* `IMAGE_BUILD_DRIVER = "local_cli"` *(allowed)*

### 6.5 Image “entrypoint contract” (names only)

The image must support these logical entrypoint modes (exact commands pinned later by Codex in task defs):

* `ENTRYPOINT_ORACLE_SEED`
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

### 6.6 Oracle lane contract knobs (phase-entry pinning)

* `ORACLE_REQUIRED_OUTPUT_IDS = ["s3_event_stream_with_fraud_6B","arrival_events_5B","s1_arrival_entities_6B","s3_flow_anchor_with_fraud_6B"]`
* `ORACLE_SORT_KEY_BY_OUTPUT_ID = {"s3_event_stream_with_fraud_6B":"ts_utc","arrival_events_5B":"ts_utc","s1_arrival_entities_6B":"ts_utc","s3_flow_anchor_with_fraud_6B":"ts_utc","s1_session_index_6B":"session_start_utc","s4_event_labels_6B":"flow_id,event_seq","s4_flow_truth_labels_6B":"flow_id","s4_flow_bank_view_6B":"flow_id"}`
* `ORACLE_SORT_KEY_ACTIVE_SCOPE = "use entries where output_id is in ORACLE_REQUIRED_OUTPUT_IDS for the current run"`

Pin rationale (Spine Green v0 fraud-mode):

* Required output surfaces: traffic.fraud + context arrival/events/entities + flow_anchor.fraud.
* Primary sort key per output is `ts_utc`; deterministic tie-breakers remain sorter-defined
  (`filename`, `file_row_number`).
* Non-`ts_utc` overrides are pinned from local-parity oracle-store implementation and are retained in
  this registry to prevent drift when future runs expand the required output set.

---

## 7. ECS / Compute Handles

These handles pin the dev_min runtime compute environment: ECS cluster, networking posture, logging, and the mapping from phases to task/service identities.

### 7.1 ECS cluster + logging

* `ECS_CLUSTER_NAME = "fraud-platform-dev-min"`
* `CLOUDWATCH_LOG_GROUP_PREFIX = "/fraud-platform/dev_min"`
* `LOG_RETENTION_DAYS = 7` *(dev_min default)*

### 7.2 Networking posture (no NAT)

**Pinned rule:** dev_min must not require a NAT gateway.

Handles:

* `VPC_ID` *(demo-scoped if created in demo stack; core if shared)*
* `SUBNET_IDS_PUBLIC` *(list)*
* `SECURITY_GROUP_ID_APP` *(ECS tasks/services SG)*
* `SECURITY_GROUP_ID_DB` *(DB SG)*

Optional (only if you introduce an internal LB — not recommended by default):

* `INTERNAL_LB_ARN` *(demo-scoped)*
* `INTERNAL_LB_DNS_NAME` *(demo-scoped)*

### 7.3 ECS task definitions (one-shot jobs)

These are logical identifiers; the real AWS ARNs/names are bound by Terraform outputs.

* `TD_ORACLE_SEED = "fraud-platform-dev-min-oracle-seed"`
* `TD_ORACLE_STREAM_SORT = "fraud-platform-dev-min-oracle-stream-sort"`
* `TD_ORACLE_CHECKER = "fraud-platform-dev-min-oracle-checker"`
* `TD_SR`
* `TD_WSP`
* `TD_DB_MIGRATIONS` *(if needed)*
* `TD_REPORTER`

### 7.4 ECS services (daemons)

* `SVC_IG`

RTDL core pack (split as you implement):

* `SVC_RTDL_CORE_ARCHIVE_WRITER`
* `SVC_RTDL_CORE_IEG`
* `SVC_RTDL_CORE_OFP`
* `SVC_RTDL_CORE_CSFB` *(if separate)*

Decision lane pack:

* `SVC_DECISION_LANE_DL`
* `SVC_DECISION_LANE_DF`
* `SVC_DECISION_LANE_AL`
* `SVC_DECISION_LANE_DLA`

Case/Labels pack:

* `SVC_CASE_TRIGGER`
* `SVC_CM`
* `SVC_LS`

Obs/Gov pack (daemonized parts):

* `SVC_ENV_CONFORMANCE` *(required daemon in P2; reporter remains the P11 task)*

### 7.5 Runtime service discovery handles

These are how tasks/services locate each other.

* `IG_BASE_URL`

  * Reachable URL for WSP → IG calls (e.g., internal DNS, service discovery, or LB DNS if used).

* `IG_LISTEN_ADDR = "0.0.0.0"`

  * Container bind address for IG service.

* `IG_PORT = 8080`

  * IG service listen port.

* `IG_INGEST_PATH = "/v1/ingest/push"`

  * Writer-boundary ingest endpoint path used by WSP.

* `IG_HEALTHCHECK_PATH = "/v1/ops/health"`

  * Operational health endpoint path for IG readiness checks.

* `IG_AUTH_MODE = "api_key"`

  * v0 writer-boundary auth posture.

* `IG_AUTH_HEADER_NAME = "X-IG-Api-Key"`

  * Required header for IG writer-boundary admission.

* `SSM_IG_API_KEY_PATH = "/fraud-platform/dev_min/ig/api_key"`

  * SSM SecureString path for the IG API key value.

### 7.6 Execution policies (v0 defaults)

* `ECS_SERVICE_DESIRED_COUNT_DEFAULT = 1`
* `ECS_TASK_RETRY_MAX = 1` *(task retries controlled by operator; fail closed by default)*

### 7.7 Runtime control knobs (v0 defaults)

**WSP / READY**

* `READY_MESSAGE_FILTER = "platform_run_id=={platform_run_id}"`
* `WSP_MAX_INFLIGHT = 1`
* `WSP_RETRY_MAX_ATTEMPTS = 5`
* `WSP_RETRY_BACKOFF_MS = 500`
* `WSP_STOP_ON_NONRETRYABLE = true`

**RTDL gate**

* `RTDL_CORE_CONSUMER_GROUP_ID = "fraud-platform-dev-min-rtdl-core-v0"`
* `RTDL_CORE_OFFSET_COMMIT_POLICY = "commit_after_durable_write"`
* `RTDL_CAUGHT_UP_LAG_MAX = 10`

**Case/labels identity + decision idempotency**

* `CASE_SUBJECT_KEY_FIELDS = "<PIN_AT_P10_PHASE_ENTRY>"`
* `LABEL_SUBJECT_KEY_FIELDS = "<PIN_AT_P10_PHASE_ENTRY>"`
* `ACTION_IDEMPOTENCY_KEY_FIELDS = "platform_run_id,event_id,action_type"`
* `ACTION_OUTCOME_WRITE_POLICY = "append_only"`

**Reporter single-writer lock**

* `REPORTER_LOCK_BACKEND = "db_advisory_lock"`
* `REPORTER_LOCK_KEY_PATTERN = "reporter:{platform_run_id}"`

**Optional join-state backing**

* `CSFB_BACKEND_MODE = "postgres_table"`
* `CSFB_STATE_TABLE_NAME = "rtdl.csfb_state"`

---

## 8. Managed DB Handles (Pinned for “no laptop dependency”)

These handles pin the **runtime operational database** used by components that cannot rely on laptop-local state (CM/LS, and any IG/RTDL state that requires a DB). In dev_min, the DB is **demo-scoped** (created/destroyed with demo stack) unless explicitly repinned.

### 8.1 DB engine and scope

* `DB_ENGINE = "postgres"`
* `DB_SCOPE = "demo"`

  * created during `terraform apply demo`, destroyed during `terraform destroy demo`.

### 8.2 DB resource identifiers

Pinned for dev_min v0:

* `DB_BACKEND_MODE = "rds_instance"`

* `RDS_INSTANCE_ID`
* `RDS_ENDPOINT`

Aurora is intentionally out-of-scope for this baseline and is not an active handle surface in v0.

### 8.3 Database name and schema namespaces

* `DB_NAME = "fraud_platform"`
* `DB_SCHEMA_IG = "ig"`
* `DB_SCHEMA_RTDL = "rtdl"`
* `DB_SCHEMA_CASES = "cases"`
* `DB_SCHEMA_LABELS = "labels"`

(If you use a different schema layout, pin it here.)

### 8.4 DB credentials (stored in SSM)

* `SSM_DB_USER_PATH = "/fraud-platform/dev_min/db/user"`
* `SSM_DB_PASSWORD_PATH = "/fraud-platform/dev_min/db/password"`

Optional:

* `SSM_DB_DSN_PATH = "/fraud-platform/dev_min/db/dsn"` *(only if you choose to store DSN as a single secret)*

### 8.5 DB connectivity / access

* `DB_SECURITY_GROUP_ID = SECURITY_GROUP_ID_DB`
* `DB_PORT = 5432`

### 8.6 DB migrations / bootstrap (if required)

* `DB_MIGRATIONS_REQUIRED = true` *(default until proven otherwise)*
* `TD_DB_MIGRATIONS`

  * ECS one-shot task definition used to apply migrations for dev_min DB.
  * Materialized via demo Terraform outputs:
    - `td_db_migrations` (family handle)
    - `ecs_db_migrations_task_definition_arn` (concrete ARN)

### 8.7 DB cleanup policy (demo posture)

* `DB_DESTROY_ON_TEARDOWN = true`
* `DB_PII_PRESENT = false` *(synthetic only; still treat creds as sensitive)*

---

## 9. AWS Batch Handles (ONLY if used for P3)

Dev_min v0 prefers ECS run-tasks for P3 (oracle jobs). If (and only if) you choose AWS Batch for stream-sort/seed/checker, pin the required handles here. If not used, leave these unset and do not reference them elsewhere.

### 9.1 Batch usage flag

* `USE_AWS_BATCH_FOR_ORACLE_JOBS = false` *(default v0)*

If set to `true`, then all handles in 9.2–9.4 become required.

### 9.2 Batch queue and job definition

* `BATCH_JOB_QUEUE`
* `BATCH_JOB_DEFINITION`

### 9.3 Batch roles

* `BATCH_JOB_ROLE_ARN`
* `BATCH_EXECUTION_ROLE_ARN` *(if separate from ECS execution role)*

### 9.4 Batch logs

* `BATCH_LOG_GROUP = "/fraud-platform/dev_min/batch"` *(example; must align with log prefix policy)*

### 9.5 Teardown rule (pinned if Batch used)

* Batch resources must be demo-scoped and destroyed in `terraform destroy demo`.
* No Batch compute environment must persist outside demo windows.

---

## 10. IAM Role Map (Who can do what)

These handles pin the IAM roles used by Terraform and every ECS task/service. The exact IAM policy JSON is implementation detail, but it must obey least privilege and match the IAM boundary summary in the runbook appendix.

### 10.1 Terraform runner role

* `ROLE_TERRAFORM_APPLY`

### 10.2 ECS execution role (pull images + logs only)

* `ROLE_ECS_TASK_EXECUTION = "fraud-platform-dev-min-ecs-task-execution"`

### 10.3 Task/service roles (application data access)

* `ROLE_ORACLE_JOB = "fraud-platform-dev-min-rtdl-core"`

  * for `TD_ORACLE_SEED`, `TD_ORACLE_STREAM_SORT`, `TD_ORACLE_CHECKER`
  * v0 posture: reuse existing materialized lane role for M5 bring-up; split to a dedicated oracle role if/when least-privilege policy divergence is required.

* `ROLE_SR_TASK`

  * for `TD_SR`

* `ROLE_WSP_TASK`

  * for `TD_WSP`

* `ROLE_IG_SERVICE = "fraud-platform-dev-min-ig-service"`

  * for `SVC_IG`

* `ROLE_RTDL_CORE = "fraud-platform-dev-min-rtdl-core"`

  * for all `SVC_RTDL_CORE_*`

* `ROLE_DECISION_LANE = "fraud-platform-dev-min-decision-lane"`

  * for all `SVC_DECISION_LANE_*`

* `ROLE_CASE_LABELS = "fraud-platform-dev-min-case-labels"`

  * for `SVC_CASE_TRIGGER`, `SVC_CM`, `SVC_LS`

* `ROLE_ENV_CONFORMANCE = "fraud-platform-dev-min-env-conformance"`

  * for `SVC_ENV_CONFORMANCE`

* `ROLE_REPORTER_SINGLE_WRITER`

  * for `TD_REPORTER`

* `ROLE_DB_MIGRATIONS`

  * for `TD_DB_MIGRATIONS`

### 10.4 Role binding rule (pinned)

* Every ECS task/service must declare **exactly one** task role from this map.
* No runtime task/service may run under the Terraform role.
* No “shared admin” runtime role is permitted.

---

## 11. Budgets / Alerts Handles

These handles pin the AWS budget guardrails required for dev_min.

### 11.1 Budget identity

* `AWS_BUDGET_NAME = "fraud-platform-dev-min-budget"`
* `AWS_BUDGET_LIMIT_AMOUNT = 30`
* `AWS_BUDGET_LIMIT_UNIT = "USD"`

### 11.2 Alert thresholds (pinned)

* `AWS_BUDGET_ALERT_1_AMOUNT = 10`
* `AWS_BUDGET_ALERT_2_AMOUNT = 20`
* `AWS_BUDGET_ALERT_3_AMOUNT = 28`

Note:
* Authority cost posture remains "~£30/month" at policy level; AWS Budgets enforcement in this account/provider is pinned in `USD`.

### 11.3 Alert delivery

One of these must be pinned and implemented:

* `ALERT_CHANNEL_MODE = "email"` *(simplest)*

  * `ALERT_EMAIL_ADDRESS` *(operator-controlled; not committed in repo)*

or

* `ALERT_CHANNEL_MODE = "sns"`

  * `SNS_TOPIC_ARN`
  * `SNS_SUBSCRIPTION_EMAIL`

### 11.4 Cost anomaly detection (optional v0)

* `ENABLE_COST_ANOMALY_DETECTION = true` *(recommended)*

### 11.5 Tag-based cost visibility (pinned)

* All demo resources must be taggable and tagged with:

  * `project=fraud-platform`
  * `env=dev_min`
  * `owner=esosa`
  * `expires_at=YYYY-MM-DD`

---

## 12. Observability Handles (Minimal v0)

These handles pin minimal observability wiring for dev_min. v0 does not require a heavy observability stack; it requires durable evidence in S3 and basic logs.

### 12.1 Logging

* `LOG_BACKEND = "cloudwatch"`
* Logging group/retention handles are defined in Section 7.1:
  * `CLOUDWATCH_LOG_GROUP_PREFIX`
  * `LOG_RETENTION_DAYS`

### 12.2 Metrics (minimal)

* `METRICS_BACKEND = "cloudwatch_basic"`
* `METRIC_NAMESPACE = "fraud-platform/dev_min"`

### 12.3 Tracing (optional v0)

* `TRACING_ENABLED = false` *(default v0)*
  If enabled later:
* `TRACE_BACKEND = "xray_or_otlp"`
* `TRACE_SAMPLING_RATE = 0.1`

### 12.4 Evidence-first posture (pinned)

* Any metric/log used as proof must be materialized into the S3 evidence bundle (Section 6 of runbook).
* Logs can supplement, but “proof only in logs” is drift.

---

## 13. Change Control

This section pins how the handles registry evolves without drift.

### 13.1 No undeclared handles rule (pinned)

* Code, Terraform, and docs MUST NOT introduce any new resource name/path/topic/SSM key unless:

  1. it is added to this registry,
  2. it is referenced by key name,
  3. and it is included in the PR decision notes.

### 13.2 Versioning

* Minor edits (typos, clarifications) may remain within v0.
* Any handle rename or semantic change requires a version bump:

  * v0 → v0.1 (or v1) depending on impact.

### 13.3 “Registry-first” workflow (pinned)

When adding a new runtime dependency:

1. Add handle keys to registry
2. Wire Terraform to output or provision those values
3. Wire runtime code to read those handles
4. Update runbook references

### 13.4 Drift prevention

* If a handle is removed or renamed, Codex must:

  * search repo references
  * update all call sites
  * update runbook + appendices
  * ensure teardown still works

### 13.5 Teardown safety

* Any demo-scoped handle must be associated with resources that are destroyed by `terraform destroy demo`.
* If a handle corresponds to a resource that cannot be destroyed, it is not allowed in demo scope.

---
