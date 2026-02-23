# Dev-Full Managed-Substrate Migration (Dev-Min Certified Baseline -> Full Platform Managed Stack) - Design-Authority v0

## 0. Document Control

### 0.1 Status

* **Status:** v0 (ACTIVE AUTHORITY DRAFT; section-by-section pin closure in progress)
* **As-of:** 2026-02-22 (Europe/London)
* **Scope of v0:** define the **dev_full rung** that extends the already-certified `dev_min` spine into a full-platform managed stack (including Learning + Evolution) with explicit operational proof obligations.

### 0.2 Roles and Audience

* **Designer / Spec Authority:** USER + Codex (this document is the active authority for dev_full decisions)
* **Implementer:** Codex (must implement within pinned bounds)
* **Primary reader:** Codex (execution)
* **Secondary readers:** USER, reviewers validating drift vs platform laws and migration intent

### 0.3 Authority Boundaries

**Pinned (Codex MUST follow)**

* **Env ladder semantics remain:** `local_parity -> dev_min -> dev_full -> prod_target`.
* `dev_min` certification remains the baseline truth for Spine Green v0; `dev_full` extends scope and operational posture, it does not rewrite prior semantic laws.
* **No laptop compute** for platform runtime in `dev_full`.
* `dev_full` must cover the full platform: Spine + Learning/Evolution (`OFS`, `MF`, `MPR`).
* Managed stack target for `dev_full` is pinned in Section 5 (AWS MSK + Flink, API Gateway/Lambda/DynamoDB where appropriate, hybrid EKS for differentiating services, S3, Aurora/Redis, Databricks, MLflow, SageMaker, Airflow, Step Functions, OTel, Terraform, GitHub Actions).
* **Decision evidence law:** no section is considered closed without explicit deploy/monitor/fail/recover/rollback/cost-control proof obligations.
* Semantic invariants are unchanged across environments (dedupe identity, payload hash anomaly semantics, append-only truths, origin_offset evidence boundaries, fail-closed posture).

**Implementer Freedom (Codex MAY choose)**

* Exact Terraform module decomposition and internal naming (within pinned naming/ownership rules).
* Exact Kubernetes chart/manifests layout and deployment mechanics.
* Exact Databricks/SageMaker job topology and execution tuning.
* Exact observability backend flavor (CloudWatch-native vs Grafana-backed), provided OTel-first correlation and evidence obligations are met.

### 0.4 Document Conventions

* **MUST / MUST NOT** = pinned requirement.
* **SHOULD** = strong preference; override requires explicit decision note.
* **MAY** = bounded implementer freedom.
* **Drift protocol:** if implementation requires violating a MUST/MUST NOT, implementation stops and a repin is required.

### 0.5 References (Normative)

1. `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
2. `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
3. `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
4. `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
5. `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
6. `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
7. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
8. `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
9. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
10. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
11. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`

**Pinned precedence rule (highest to lowest):**
- Core platform-wide authority docs.
- This document (`dev-full_managed-substrate_migration.design-authority.v0.md`).
- Plane/component pre-design decisions.
- Dev-min migration authority docs (baseline anchor).

### 0.6 References (Working Notes)

* `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md`
* `scratch_files/scratch.md` (job-target signal capture; non-normative)

---

## 1. Problem Statement

### 1.1 The current gap

`dev_min` proved spine migration and managed-substrate operation without laptop runtime, but it intentionally excluded Learning/Evolution and used a minimal cost-first posture. That is insufficient for full-platform closure and insufficient for senior MLOps signaling on its own.

### 1.2 Why `dev_full` now

To claim production-shaped MLOps experience credibly, the platform must demonstrate:

* full lifecycle operation (ingest -> decision -> case/labels -> dataset -> train/eval -> governed activation),
* managed tooling fluency (Kubernetes, MLflow, SageMaker, Airflow, streaming bus, IaC, observability),
* operational reliability under failure drills with deterministic rollback and auditable evidence.

### 1.3 What success must feel like

`dev_full` is successful when:

* full platform is green under managed runtime,
* all major lanes produce deterministic evidence,
* each lane is proven by deploy/monitor/fail/recover/rollback/cost-control checks,
* no hidden local dependency exists,
* non-regression from dev_min spine is continuously enforced.

---

## 2. Goals and Non-Goals

### 2.1 Goals (what v0 dev_full MUST accomplish)

1. **Full platform scope closure**: Spine + Learning/Evolution in one authority and one run posture.
2. **Managed stack execution**: platform runtime and ML lifecycle operate on pinned managed services.
3. **No semantic drift**: all established platform laws remain unchanged.
4. **Operational proof discipline**: every major lane has deploy/monitor/fail/recover/rollback/cost-control evidence.
5. **Deterministic governance**: registry activation remains explicit, auditable, and fail-closed.

### 2.2 Non-Goals (explicitly out of scope for this v0)

1. Multi-region active-active production resilience.
2. Regulatory certification/compliance audits beyond engineering-grade controls.
3. Mandatory replacement of every component with cloud-native proprietary services.
4. Permanent 24/7 production SLA commitments.

### 2.3 Constraints

* No laptop compute in runtime lanes.
* No unpinned service/tool substitutions.
* No silent defaults when decisions are unresolved.
* Every phase advancement requires blocker-free evidence.

---

## 3. Definitions and Shared Terms

### 3.1 Environment ladder

* `local_parity`: semantic correctness harness.
* `dev_min`: spine managed-substrate certification baseline.
* `dev_full`: full-platform managed stack with production-shaped tooling and operations.
* `prod_target`: later hardening/scale posture.

### 3.2 Identity and correlation

* `platform_run_id`, `scenario_run_id`, `event_id`, `event_class` remain canonical.
* Learning identity must include dataset/bundle fingerprints and code-release IDs.

### 3.3 Evidence and replay

* `origin_offset` remains the online evidence boundary.
* Archive + manifests remain replay truth for offline rebuild.
* Evidence refs are durable, immutable, and run-scoped.

### 3.4 Operational proof terms

For each lane, v0 requires explicit proof artifacts for:

* `DEPLOY_PROOF`
* `MONITOR_PROOF`
* `FAILURE_DRILL_PROOF`
* `RECOVERY_PROOF`
* `ROLLBACK_PROOF`
* `COST_CONTROL_PROOF`

---

## 4. Env Ladder Contract

### 4.1 What local_parity certifies

Semantic correctness and deterministic laws.

### 4.2 What dev_min certifies

Managed-substrate spine closure with strict run/evidence posture and zero laptop runtime for spine services.

### 4.3 What dev_full MUST certify

* Full-platform closure (including OFS/MF/MPR).
* Production-shaped managed toolchain operation.
* Non-regression against dev_min spine gates.
* End-to-end operational proof obligations.

### 4.4 What prod_target adds later

Multi-region resilience, tighter compliance, higher SLO rigor, and enterprise governance scale.

---

## 5. Pinned Decisions (NON-NEGOTIABLE)

### 5.1 Primary dev_full stack selections (fixed)

1. **Runtime strategy:** managed-first and replace-by-default. Custom services are retained only where they carry differentiating business logic or stricter semantic contracts that managed primitives cannot satisfy.
2. **Event bus:** AWS MSK Serverless is the primary managed streaming substrate.
3. **Stream processing lane:** MSK-integrated Flink is the primary runtime for stream-native transformations and joins (WSP/SR stream surfaces and RTDL ingress/context lanes).
4. **Ingress edge:** API Gateway + Lambda + DynamoDB idempotency store is the default IG runtime posture; custom IG service runtime is permitted only if a pinned contract cannot be satisfied otherwise.
5. **Durable object store:** AWS S3 remains durable truth/evidence/archive substrate.
6. **Operational relational store:** Aurora PostgreSQL is the managed primary runtime relational store.
7. **Low-latency join/state cache:** ElastiCache Redis is the managed join-plane cache/state substrate.
8. **Hybrid custom-runtime allowance:** EKS is reserved for differentiating services that remain custom after managed-first adjudication (for example DF policy logic, CM/LS boundary mechanics, selected governance workers).
9. **Data/feature processing lane:** Databricks is the primary OFS-scale data processing substrate.
10. **Training and endpoint lane:** SageMaker is the primary managed ML training/deployment substrate.
11. **Experiment tracking and model lifecycle metadata:** MLflow is the primary experiment/model tracking surface.
12. **Workflow orchestration split:**
   * Step Functions: platform run-state orchestration/gates.
   * Airflow (MWAA): scheduled learning/data DAG orchestration.
13. **Observability baseline:** OpenTelemetry-first telemetry with CloudWatch-backed operational signals and dashboarding.
14. **Delivery and IaC:** Terraform + GitHub Actions are mandatory for reproducible provision/deploy flows.
15. **Secrets and encryption:** IAM + KMS + Secrets Manager/SSM, no plain-text credentials in repo/runtime manifests.
16. **Lakehouse table format:** Apache Iceberg (v2) on S3 with AWS Glue Data Catalog is the default tabular format for OFS/MF learning datasets; Delta is not the v0 default.

#### 5.1.1 Sectional pin closure set (2026-02-22)

The following values are now explicitly pinned for v0 execution:

1. **MSK serverless profile and retention envelope**
   * `KAFKA_BACKEND = "AWS_MSK_SERVERLESS"`
   * `MSK_CLUSTER_MODE = "Serverless"`
   * `MSK_REGION = "eu-west-2"`
   * `MSK_AUTH_MODE = "SASL_IAM"`
   * `SCHEMA_REGISTRY_MODE = "AWS_GLUE_SCHEMA_REGISTRY"`
   * `KAFKA_RETENTION_HIGH_VOLUME = 7d`
   * `KAFKA_RETENTION_LOW_VOLUME = 30d`
   * `KAFKA_PARTITIONS_HIGH_VOLUME_DEFAULT = 6`
   * `KAFKA_PARTITIONS_LOW_VOLUME_DEFAULT = 3`
2. **Aurora topology**
   * `AURORA_ENGINE = "Aurora PostgreSQL"`
   * `AURORA_MODE = "Serverless v2"`
   * `AURORA_HA = "Multi-AZ (1 writer + >=1 reader)"`
   * `AURORA_ACU_RANGE = "0.5-8 ACU (v0 default)"`
3. **Databricks workspace/job-compute policy**
   * `DBX_COMPUTE_POLICY = "job-clusters-only (no all-purpose clusters for v0 run lanes)"`
   * `DBX_AUTOSCALE_WORKERS = "1-8"`
   * `DBX_AUTO_TERMINATE_MINUTES = 20`
   * `DBX_COST_GUARD = "fail-closed if monthly spend crosses alert-3 threshold"`
4. **SageMaker serving posture**
   * `SM_SERVING_MODE = "realtime-endpoint for active runtime inference + batch transform for offline eval/backfill"`
   * `SM_ENDPOINT_COUNT_V0 = 1` (primary active model slot)
5. **MLflow hosting mode**
   * `MLFLOW_HOSTING_MODE = "Databricks managed MLflow"`
6. **Airflow deployment mode**
   * `AIRFLOW_MODE = "MWAA (managed Airflow)"`
7. **Step Functions decomposition and failure taxonomy**
   * State machines:
     - `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
     - `SFN_LEARNING_PIPELINE_GATE_V0`
     - `SFN_FINAL_VERDICT_AGGREGATOR_V0`
   * Failure taxonomy (minimum):
     - `DFULL-SFN-B1 = PRECHECK_OR_CONFIG_INVALID`
     - `DFULL-SFN-B2 = RUNTIME_HEALTH_OR_DEPENDENCY_UNAVAILABLE`
     - `DFULL-SFN-B3 = EVIDENCE_MISSING_OR_INVALID`
     - `DFULL-SFN-B4 = ROLLBACK_OR_COMPENSATION_FAILED`
     - `DFULL-SFN-B5 = COST_GUARDRAIL_BREACH`
8. **Managed-first runtime placement policy**
   * `STREAM_ENGINE_MODE = "MSK_FLINK_DEFAULT"`
   * `INGRESS_EDGE_MODE = "APIGW_LAMBDA_DDB_DEFAULT"`
   * `EKS_USE_POLICY = "DIFFERENTIATING_SERVICES_ONLY"`
   * Any EKS placement for non-differentiating lanes requires explicit pin and rationale.
9. **Runtime-path selection policy (single-path law)**
   * `PHASE_RUNTIME_PATH_MODE = "SINGLE_ACTIVE_PATH_PER_PHASE_RUN"`
   * `PHASE_RUNTIME_PATH_PIN_REQUIRED = true`
   * `RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED = false`
   * fallback activation requires explicit blocker adjudication and a new `phase_execution_id`.
10. **SR READY commit authority**
   * `SR_READY_COMPUTE_MODE = "FLINK_ALLOWED"`
   * `SR_READY_COMMIT_AUTHORITY = "STEP_FUNCTIONS_ONLY"`
   * `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF = true`
   * no lane may claim `P5` closure from Flink output alone without Step Functions commit evidence.
11. **Ingress edge operational envelope**
   * `IG_MAX_REQUEST_BYTES = 1048576` (1 MiB)
   * `IG_REQUEST_TIMEOUT_SECONDS = 30`
   * `IG_INTERNAL_RETRY_MAX_ATTEMPTS = 3`
   * `IG_INTERNAL_RETRY_BACKOFF_MS = 250`
   * `IG_IDEMPOTENCY_TTL_SECONDS = 259200` (72h)
   * `IG_DLQ_MODE = "SQS"`
   * `IG_RATE_LIMIT_RPS = 200`
   * `IG_RATE_LIMIT_BURST = 400`
12. **Cross-runtime correlation contract**
   * `CORRELATION_MODE = "W3C_TRACE_CONTEXT_PLUS_RUN_HEADERS"`
   * required correlation fields: `platform_run_id,scenario_run_id,phase_id,event_id,runtime_lane,trace_id`.
   * correlation headers/fields must survive API edge, Flink lanes, Step Functions transitions, EKS services, and evidence artifact emission.
13. **Learning table format and catalog**
   * `DATA_TABLE_FORMAT_PRIMARY = "APACHE_ICEBERG_V2"`
   * `DATA_TABLE_CATALOG = "AWS_GLUE_DATA_CATALOG"`
   * `DATA_TABLE_STORAGE = "S3"`
   * `DATA_TABLE_QUERY_ENGINE = "ATHENA_GLUE_ICEBERG"`
   * `DATA_TABLE_DELTA_MODE = "DISABLED_FOR_V0"`
14. **S3 lifecycle transition posture (cost-safe without losing operator agility)**
   * evidence and archive surfaces remain in S3 Standard during active debugging window, then transition by policy.
   * default v0 transition policy:
     - evidence: `STANDARD` -> `STANDARD_IA` at day 30 -> `GLACIER_IR` at day 180 -> expire day 365.
     - archive: `STANDARD` -> `STANDARD_IA` at day 30 -> `GLACIER_IR` at day 60 -> expire day 90.
     - quarantine: expire day 45 (no Glacier transition requirement).

### 5.2 Cost posture (hard requirements)

1. `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD = 300` (hard cap for v0).
2. `DEV_FULL_BUDGET_ALERT_1_USD = 120`, `DEV_FULL_BUDGET_ALERT_2_USD = 210`, `DEV_FULL_BUDGET_ALERT_3_USD = 270`.
3. Budget alerts MUST exist for AWS total billing (including streaming/runtime/data services) with fail-closed advancement policy when alert-3 is breached.
4. Idle runtime posture MUST be controlled (lane-based start/stop and teardown discipline).
5. `COST_CAPTURE_SCOPE = "aws_plus_external_ml_platform_if_separately_billed"` (no blind spots).

### 5.2.1 Cost-to-outcome operating law (pinned)

1. Every phase execution window MUST declare a pre-run spend envelope:
   * max spend allowance for the phase window,
   * expected duration window,
   * hard stop/kill condition,
   * required proof artifacts expected at phase closure.
2. Every phase closure MUST publish a cost-to-outcome receipt:
   * spend consumed in the window,
   * artifacts produced,
   * decision or risk retired by that spend.
3. Phase advancement is fail-closed if:
   * spend materially breaches the declared phase envelope, or
   * material proof artifacts are missing for the spend consumed.
4. Active implementation windows MUST publish daily cross-platform cost posture (`AWS + external ML platforms where billed separately`).
5. Default runtime posture remains "off when not proving"; idle cost burn without active proof work is disallowed.

### 5.3 Always-on vs Ephemeral policy

* Persistent cores allowed: control-plane services, state stores, registries, evidence stores.
* Batch/training/large compute lanes SHOULD be run-on-demand.
* Non-critical services default to low/zero desired count outside active windows.

### 5.4 Prohibited patterns

* No local laptop runtime fallback.
* No manual-only cloud configuration without IaC representation.
* No model activation outside governed registry events.
* No "latest" implicit dataset reads in OFS/MF run intents.
* No bypass of fail-closed gates for unresolved blockers.

### 5.5 Evidence posture

Every full run MUST emit a durable run bundle containing:

* run config and release digests,
* ingress/decision/case-label summaries,
* OFS manifests,
* MF train/eval evidence,
* MPR promotion/rollback events,
* non-regression matrix against dev_min spine,
* cost and teardown posture snapshot.

---

## 6. Plane-by-Plane Mapping (WHAT moves where)

### 6.0 Cross-plane invariants

* Dedupe identity, payload-hash anomaly law, append-only truths, origin_offset, explicit degrade, and by-ref evidence remain immutable laws.

### 6.1 World Builder Plane

* Oracle truth remains in S3.
* Oracle Store seating is a warm source-of-stream zone under object-store governance (`oracle-store/` boundary), separate from evidence/archive roots.
* Platform access to Oracle Store is read-only; data-engine (or upstream producer) remains write owner.
* SR/WSP stream lanes run on MSK-integrated Flink jobs; orchestration and gate commits remain Step Functions-controlled.
* READY/control remains Kafka-backed, orchestrated via Step Functions run-state controls.
* SR READY closure authority is Step Functions commit evidence (Flink output is compute evidence only).

### 6.2 Control & Ingress Plane

* IG default runtime is API Gateway + Lambda with DynamoDB idempotency boundary.
* EKS-hosted IG remains an explicit fallback option only when a pinned contract requires custom service behavior.
* Kafka topics remain authoritative bus surfaces.
* Quarantine payloads/index and receipt evidence remain in S3 + managed store.
* Authn/authz hardening rises to service identity and policy-bound ingress controls.
* IG edge must enforce pinned envelope limits (payload size, timeout, retry budget, idempotency TTL, DLQ wiring, and rate limits).

### 6.3 RTDL Plane

* Stream-native projections and joins (`IEG`/`OFP` and equivalent inlet/context transforms) run on Flink.
* `DF`/`AL`/`DLA` stay hybrid: managed integrations first, custom runtime only where semantic ownership requires it.
* Redis serves low-latency join/cache lane where required.
* Aurora/Postgres stores durable runtime relational state.
* Audit evidence slices persist to S3.

### 6.4 Label & Case Plane

* Case and label orchestration should prefer managed workflows/events with Aurora state.
* Custom CM/LS service runtime remains allowed where writer-boundary semantics require explicit service control.
* Writer boundary semantics remain fail-closed with durable ack evidence.

### 6.5 Learning & Evolution Plane

* OFS: Databricks jobs build dataset artifacts/manifests against archive + labels truth and publish governed Apache Iceberg tables on S3 via Glue catalog contracts.
* MF: SageMaker training/eval pipeline with MLflow tracking.
* MPR: explicit governed promotion/rollback remains activation authority for runtime bundle resolution.

### 6.6 Meta Layers

* Run/Operate: Step Functions for platform run-state, Airflow for learning schedules, GitHub Actions for CI/CD workflow orchestration.
* Obs/Gov: OTel correlation + run-scoped evidence + governance facts.

---

## 7. Laws that MUST NOT change

### 7.1 Dedupe tuple + payload hash anomalies

Canonical dedupe identity remains `(platform_run_id, event_class, event_id)` with payload hash mismatch as explicit anomaly.

### 7.2 Append-only truths

DLA, LS, receipts, and governance events remain append-only.

### 7.3 Evidence boundary

`origin_offset` and by-ref evidence contracts remain authoritative.

### 7.4 Explicit degrade

No silent defaulting; degrade must be explicit and auditable.

### 7.5 Provenance

Every cross-plane output carries policy/bundle/config/release identifiers required for replay and audit.

### 7.6 Production-pattern adoption law

1. Managed services are default and mandatory where they satisfy the required semantics; custom services are allowed only with explicit differentiating-logic rationale.
2. No local/toy substitute path is allowed for a managed lane once that lane is pinned for `dev_full`.
3. `M0..M2` must explicitly verify production-pattern conformance before advancing to runtime semantics (`M3+`).
4. Any deviation from this law is fail-closed and requires authority repin before execution continues.

---

## 8. Infrastructure-as-Code Plan (Terraform)

### 8.1 Repo/module boundaries (pinned)

`infra/terraform/dev_full/` MUST be split into bounded stacks with independent state:

* `core/` (base networking, KMS, core S3, IAM baselines)
* `streaming/` (MSK cluster/topology/topic configuration/IAM access policy)
* `runtime/` (managed runtime surfaces: Flink apps, ingress edge, and selective EKS custom services)
* `data_ml/` (Databricks, SageMaker, MLflow integration surfaces)
* `ops/` (budgets, alarms, dashboards, workflow role bindings)

### 8.2 State strategy

Each stack MUST use separate remote state keys + lock semantics.

Pinned state handles:

* `TF_STATE_BUCKET = "fraud-platform-dev-full-tfstate"`
* `TF_LOCK_TABLE = "fraud-platform-dev-full-tf-locks"`
* `TF_STATE_KEY_CORE = "dev_full/core/terraform.tfstate"`
* `TF_STATE_KEY_STREAMING = "dev_full/streaming/terraform.tfstate"`
* `TF_STATE_KEY_RUNTIME = "dev_full/runtime/terraform.tfstate"`
* `TF_STATE_KEY_DATA_ML = "dev_full/data_ml/terraform.tfstate"`
* `TF_STATE_KEY_OPS = "dev_full/ops/terraform.tfstate"`

### 8.3 Naming/tagging conventions

All resources MUST include project/env/owner/run-scope tags as applicable.

### 8.4 Providers and versions

Pinned provider families include AWS, Kubernetes/Helm, Databricks.

### 8.5 Outputs and secrets handling

Secret values are never emitted in plain outputs; only refs/ARNs/paths.

### 8.6 Identity and secret-path contracts (pinned)

Required IAM role handles:

* `ROLE_TERRAFORM_APPLY_DEV_FULL`
* `ROLE_EKS_NODEGROUP_DEV_FULL`
* `ROLE_EKS_RUNTIME_PLATFORM_BASE`
* `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`
* `ROLE_MWAA_EXECUTION`
* `ROLE_SAGEMAKER_EXECUTION`
* `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS`

Required secret path handles:

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

---

## 9. Networking and Access Posture

### 9.1 Default stance

Private-by-default networking; explicit ingress only where boundary endpoints require it.

### 9.2 Kubernetes posture

* Namespace segmentation by lane.
* Network policy restrictions.
* Workload identity mapped to least-privilege IAM roles.

### 9.3 External connectivity

* MSK connectivity via secure protocol and managed IAM-authenticated credentials.
* Outbound access constrained to required managed services.

---

## 10. Secrets, Identity, and Config

### 10.1 Secrets storage

* Runtime secrets: Secrets Manager/SSM.
* Encryption: KMS-managed keys.

### 10.2 Workload identity

* IAM role-per-service principle.
* No shared admin role for runtime workloads.

### 10.3 Config pinning

Run config digests must be emitted and validated across runtime and learning lanes.

### 10.4 Drift-safe config changes

No mid-run implicit config mutation; version boundaries must be explicit and auditable.

---

## 11. Observability and Evidence

### 11.1 Telemetry baseline

OpenTelemetry-first instrumentation with run-scoped correlation IDs.

Pinned correlation law:
* single trace/correlation continuity across API edge, stream processors, orchestrators, custom runtimes, and evidence writers is mandatory.
* no phase may close if required correlation fields are missing in lane-level evidence.

### 11.2 Required signals

* Service health, lag, error, latency.
* Model performance and drift indicators.
* Pipeline/job status and failure taxonomy.

### 11.3 Required artifacts

Run evidence bundle must include lane-level proof artifacts, anomaly summaries, and governance events.

### 11.4 SLO posture

Define and track SLOs for core online paths and ML pipeline completion windows.

---

## 12. Run/Operate Workflows

### 12.1 Operator model

Human operator triggers bounded workflows; all actions are traceable and reproducible.

### 12.2 Workflow split

* Step Functions orchestrates full-platform run-state gates.
* Airflow orchestrates recurring OFS/MF schedules.
* GitHub Actions executes CI/CD + infra promotions + policy checks.

### 12.2.1 Runtime-path governance (fail-closed)

* Every phase execution selects exactly one active runtime path and records it in run-control evidence before execution.
* In-phase path switching is prohibited.
* Fallback path activation is allowed only after blocker adjudication, with explicit operator approval and a new `phase_execution_id`.

### 12.3 Failure handling

Every workflow path must explicitly classify and record blockers with deterministic rerun posture.

---

## 13. Demo-Day / Validation Runbook Contract

### 13.1 Preconditions

* All stack handles resolved.
* Required secrets materialized.
* Runtime and learning lanes healthy.

### 13.2 Execution contract

Run must execute end-to-end with explicit phase gates and no hidden manual interventions.

### 13.3 Drill contract

At least one failure drill per major lane class (runtime, data, model, governance) with recovery and rollback proof.

### 13.4 Closure contract

Run closure requires blocker-free rollup and evidence publication.

---

## 14. Teardown, Retention, and Data Lifecycle

### 14.1 What persists

Evidence, audit truths, manifests, model registry metadata, and required state stores.

### 14.2 What is bounded

Expensive transient compute, training clusters/jobs, non-essential workers outside active windows.

### 14.3 Retention policy

Retention tiers are pinned for v0 as follows:

* `RETENTION_EVIDENCE_DAYS = 365`
* `RETENTION_ARCHIVE_DAYS = 90`
* `RETENTION_QUARANTINE_DAYS = 45`
* `RETENTION_CLOUDWATCH_LOGS_DAYS = 14`
* `RETENTION_TRAINING_ARTIFACTS_DAYS = 180`
* `RETENTION_MLFLOW_METADATA_DAYS = 365`
* `RETENTION_MPR_EVENT_HISTORY_DAYS = 365`
* `RETENTION_ORACLE_SOURCE_DAYS = 365`

Lifecycle transition policy (v0 default):

* `EVIDENCE_TRANSITION_TO_STANDARD_IA_DAYS = 30`
* `EVIDENCE_TRANSITION_TO_GLACIER_IR_DAYS = 180`
* `ARCHIVE_TRANSITION_TO_STANDARD_IA_DAYS = 30`
* `ARCHIVE_TRANSITION_TO_GLACIER_IR_DAYS = 60`
* `QUARANTINE_EXPIRY_ONLY = true`
* `ORACLE_TRANSITION_TO_STANDARD_IA_DAYS = 30`
* `ORACLE_TRANSITION_TO_GLACIER_IR_DAYS = 180`

---

## 15. Acceptance Gates (Definition of Done for dev_full v0)

### 15.1 Infrastructure gates

1. `terraform plan` and `apply` succeed for all five stacks (`core`, `streaming`, `runtime`, `data_ml`, `ops`) with no unresolved dependency blockers.
2. `terraform destroy` succeeds for teardown-scoped surfaces with no residual critical resources outside pinned always-on set.
3. IAM/secret path conformance check reports zero missing required handles from Section 8.6.
4. Cost guardrail configuration exists and is queryable before first full run.

### 15.2 Semantic gates

1. All invariant laws in Section 7 pass under managed runtime.
2. Dedupe/payload-hash anomaly checks report zero unresolved anomalies at closure.
3. Evidence boundary checks confirm origin_offset continuity for all required lanes.

### 15.3 Operational gates

Deploy/monitor/fail/recover/rollback/cost-control proof exists for each required lane:

* World Builder
* Control/Ingress
* RTDL
* Case/Labels
* Observability/Governance

### 15.4 Learning gates

1. OFS build succeeds with immutable manifest publication.
2. MF train/eval succeeds with reproducible eval report and metrics.
3. MPR promote and rollback drills both complete with append-only governance evidence.
4. No learning lane closure is valid without explicit rollback proof.

### 15.5 Non-regression gates

Critical dev_min spine behaviors remain green after learning activation:

* P5 ingress admission gates
* P8 RTDL core gates
* P9 decision lane gates
* P10 case/label gates
* P11 run-closeout gates

### 15.6 Portfolio-credibility gate

Operator can demonstrate full lifecycle operation with production-shaped tools and evidence, not just component demos.

### 15.7 Cost-to-outcome gates

1. Every executed phase has a pre-run spend envelope artifact and a post-run cost-to-outcome receipt artifact.
2. Every phase closure explicitly states what proof/decision was gained for spend consumed.
3. Any phase with spend but no material proof/decision outcome is blocked from advancing.
4. Daily cross-platform cost posture snapshots exist for all active build windows.

---

## 16. Drift Watchlist and Change Control

### 16.1 Drift triggers

* Tool substitution without repin.
* Runtime local fallback introduction.
* Untracked schema/contract changes.
* Evidence gaps in required proofs.

### 16.2 Change protocol

All major stack changes require explicit decision note and authority update before execution.

### 16.3 Post-run audit ritual

After every full run, perform semantic drift and ownership-boundary audit before advancing phases.

---

## 17. Decision Registry (v0)

### 17.1 Closed (pinned now)

1. `dev_full` targets full-platform scope (Spine + Learning/Evolution).
2. `dev_full` runtime has zero laptop compute posture.
3. Primary stack is managed-first: AWS MSK + Flink + API Gateway/Lambda/DynamoDB + S3 + Aurora + Redis + Databricks + MLflow + SageMaker + Airflow + Step Functions + OTel + Terraform + GitHub Actions, with EKS reserved for differentiating custom services.
4. Per-lane proof obligations include deploy/monitor/fail/recover/rollback/cost-control evidence.

### 17.2 Sectional closure pins (2026-02-22)

This pass closes the initial open set and repins them as executable defaults:

1. MSK serverless/retention/partition envelope -> closed by Section 5.1.1 item 1.
2. Aurora topology -> closed by Section 5.1.1 item 2.
3. Databricks job-compute policy -> closed by Section 5.1.1 item 3.
4. SageMaker serving posture -> closed by Section 5.1.1 item 4.
5. MLflow hosting mode -> closed by Section 5.1.1 item 5.
6. Airflow deployment mode -> closed by Section 5.1.1 item 6.
7. Step Functions decomposition/failure taxonomy -> closed by Section 5.1.1 item 7.
8. Managed-first runtime placement policy -> closed by Section 5.1.1 item 8.
9. Runtime-path selection policy -> closed by Section 5.1.1 item 9.
10. SR READY commit authority -> closed by Section 5.1.1 item 10.
11. Ingress edge operational envelope -> closed by Section 5.1.1 item 11.
12. Cross-runtime correlation contract -> closed by Section 5.1.1 item 12.
13. Learning table format and catalog -> closed by Section 5.1.1 item 13.
14. S3 lifecycle transition posture -> closed by Section 5.1.1 item 14.

### 17.3 Future upgrades (not pinned)

* Multi-region active-active runtime.
* Real-time feature serving via dedicated feature platform.
* Expanded compliance-grade controls.

---

## 18. Appendices

### Appendix A. Resource Swap Table (local_parity -> dev_min -> dev_full -> prod_target)

| Plane/Layer | Component | local_parity | dev_min | dev_full (pinned target) | prod_target |
| --- | --- | --- | --- | --- | --- |
| World Builder | Oracle store | MinIO | S3 | S3 | S3 + Object Lock/WORM |
| World Builder | SR/WSP | local compose | ECS ephemeral | MSK + Flink jobs (Step Functions-gated) | Flink hardened autoscale + checkpoint governance |
| Control/Ingress | Event bus | Redpanda/LocalStack | Confluent Basic | AWS MSK Serverless | Kafka multi-AZ/tiered |
| Control/Ingress | IG | local service | ECS service | API Gateway + Lambda + DynamoDB idempotency (EKS fallback only if required) | Hardened private ingress + WAF + zero-trust service boundaries |
| RTDL | IEG/OFP (stream transforms) | local workers | ECS workers/services | MSK + Flink stream processing | Flink hardened autoscale + state/checkpoint DR |
| RTDL | DF/AL/DLA (ownership logic) | local workers | ECS workers/services | Hybrid managed integrations + selective EKS custom services | Policy-governed mixed runtime with strict SLO evidence |
| Case/Labels | CM/LS | local services/db | ECS + managed runtime db | Hybrid managed workflows/events + Aurora (selective EKS where boundary semantics require) | Enterprise governance + audited workflow controls |
| Learning/Evolution | OFS | local job | optional | Databricks jobs | Databricks/Snowflake scale |
| Learning/Evolution | MF | scripts/local | optional | SageMaker + MLflow | SageMaker advanced MLOps |
| Learning/Evolution | MPR governance | minimal | minimal | governed promotion/rollback | enterprise policy workflows |
| Meta | Orchestration | scripts/make | CLI run_operate | Step Functions + Airflow | expanded control plane |
| Meta | IaC/CI | compose/manual | Terraform + GH Actions | Terraform + GH Actions (multi-stack) | org-scale policy + drift control |
| Meta | Observability | local logs | minimal CW + S3 evidence | OTel + CW/Grafana + S3 evidence | full SRE-grade stack |

### Appendix B. Cost and Risk Guardrails (dev_full)

1. `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD = 300` (hard cap).
2. Alert thresholds are mandatory:
   * Alert-1: `$120`
   * Alert-2: `$210`
   * Alert-3: `$270`
3. Alert-3 triggers hard-stop on phase advancement until remediation/approval.
4. Non-critical lanes default to low/zero desired count outside active windows.
5. Training/data jobs run on-demand with explicit cutoff/timeout budgets.

### Appendix C. Topic and Data Contract Continuity

1. Existing dev_min topic contracts remain authoritative for shared spine surfaces unless explicitly repinned below.
2. Any new topic/schema surface for learning orchestration must be added to handles registry before use.
3. Schema/version changes require explicit compatibility adjudication and replay impact note.

Pinned dev_full topic set (v0):

| Topic | Class | Partitions | Retention | Producer(s) | Consumer(s) |
| --- | --- | --- | --- | --- | --- |
| `fp.bus.control.v1` | control | 3 | 30d | SR, orchestrators | WSP, reporters |
| `fp.bus.traffic.fraud.v1` | high-volume | 6 | 7d | IG | RTDL ingress |
| `fp.bus.context.arrival_events.v1` | high-volume | 6 | 7d | IG | RTDL context |
| `fp.bus.context.arrival_entities.v1` | high-volume | 6 | 7d | IG | RTDL context |
| `fp.bus.context.flow_anchor.fraud.v1` | high-volume | 6 | 7d | IG | RTDL join plane |
| `fp.bus.rtdl.v1` | high-volume | 6 | 7d | DF/AL | RTDL downstream lanes |
| `fp.bus.audit.v1` | audit | 3 | 30d | DLA | CM, evidence sinks |
| `fp.bus.case.triggers.v1` | case | 3 | 30d | CaseTrigger | CM |
| `fp.bus.labels.events.v1` | labels | 3 | 30d | LS | Learning/reporting |
| `fp.bus.learning.ofs.requests.v1` | learning-control | 3 | 30d | Orchestrator | OFS runner |
| `fp.bus.learning.ofs.events.v1` | learning-control | 3 | 30d | OFS runner | Orchestrator/reporter |
| `fp.bus.learning.mf.requests.v1` | learning-control | 3 | 30d | Orchestrator | MF runner |
| `fp.bus.learning.mf.events.v1` | learning-control | 3 | 30d | MF runner | Orchestrator/reporter |
| `fp.bus.learning.registry.events.v1` | governance | 3 | 90d | MPR | DF/runtime guards |

### Appendix D. Proof Matrix (required for each major lane)

For each lane, publish artifacts proving:

1. Deploy
2. Monitor
3. Failure drill
4. Recovery
5. Rollback
6. Cost-control

No lane may claim closure without this six-part proof set.
