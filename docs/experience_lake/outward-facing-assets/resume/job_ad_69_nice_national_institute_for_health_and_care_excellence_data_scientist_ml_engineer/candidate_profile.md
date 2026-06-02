# Candidate Profile - NICE Data Scientist (ML Engineer)

Since Eric is fictional, this locks the platform truth-set for the NICE ML Engineer statement and interview. It is specific enough to evidence machine learning engineering, deployment, monitoring, governance and responsible AI without sounding like a random cloud-tool dump.

## 1. AWS Services Used

The platform was an **AWS-hosted fraud and transaction decisioning system**.

It used:

| Area | Service used | What it did |
| --- | --- | --- |
| **Ingress** | API Gateway | Exposed controlled endpoints for transaction/event submission. |
| **Validation / publishing** | Lambda | Performed schema checks, basic validation and pushed accepted events onward. |
| **Streaming** | MSK Serverless | Carried validated transaction events between ingestion and decisioning services. |
| **Runtime services** | EKS | Ran containerised services for decisioning, case creation, monitoring and API logic. |
| **Runtime state** | Aurora PostgreSQL | Stored cases, decisions, review status, labels, thresholds and operational state. |
| **Object storage** | S3 | Stored raw events, validated datasets, model artifacts, evaluation outputs and evidence files. |
| **Model work** | SageMaker | Ran training/evaluation jobs and produced model artifacts for candidate models. |
| **Offline analysis** | Databricks | Used for exploratory feature analysis, dataset checks and larger offline review notebooks. |
| **Experiment tracking** | MLflow | Tracked experiments, model versions, metrics, parameters and evaluation runs. |
| **Logs / metrics** | CloudWatch | Captured service logs, errors, latency, event counts and alarms. |
| **Config / secrets** | SSM Parameter Store and Secrets Manager | Held environment configuration, thresholds and credentials outside code. |
| **Access control** | IAM | Controlled service permissions and limited access to data stores and deployment resources. |
| **Scheduling** | EventBridge | Triggered repeatable monitoring and offline evaluation jobs. |
| **Images** | ECR | Stored Docker images used by the EKS services. |

Clean interview sentence:

> I used AWS to run the deployed services, move validated events through the platform, store raw and curated datasets, track logs and metrics, and run repeatable evaluation and monitoring jobs.

## 2. Engineering Tools

Eric used:

- **Git and GitHub** for version control, pull requests, branches and traceable changes.
- **GitHub Actions** for CI checks: linting, unit tests, Docker build and deployment workflow.
- **Docker** to package services consistently.
- **ECR** to store built service images.
- **EKS** to run the containerised services.
- **MLflow** for experiment tracking, model lineage and comparison of model candidates.
- **SageMaker** for training/evaluation jobs and model artifacts.
- **Databricks** for exploratory analysis and feature review, not as the main production runtime.

Suggested wording:

> I used GitHub for version control, Docker for packaging services, GitHub Actions for testing and build workflows, ECR and EKS for container deployment, and MLflow/SageMaker to track and evaluate model candidates.

## 3. Models And Decisioning Methods

The platform used a **hybrid decisioning approach**, not one magic model.

It had:

1. **Rules engine**

   - High-velocity transactions.
   - Unusual transaction amount.
   - Repeated failed attempts.
   - New device or unusual channel.
   - Missing or invalid required fields.
   - Merchant or category risk flags.

2. **Logistic regression baseline**

   - Used as an interpretable benchmark.
   - Helped compare whether more complex models were actually adding value.

3. **Gradient-boosted tree model**

   - Used for the main risk-scoring candidate.
   - Features included transaction amount deviation, recent transaction count, time since last transaction, category rarity, failed-attempt count, account age, channel changes and historical behaviour windows.

4. **Anomaly detection experiment**

   - Used for exploratory review of unusual transaction patterns.
   - Not treated as the main production decision model because explainability and reviewability mattered.

5. **Threshold-based decisioning**

   - Score bands created different outcomes: allow, monitor, review, high-risk review.
   - Thresholds were reviewed against false positives, false negatives and review workload.

Key point:

> The platform did not rely only on a model score. It combined rules, model scores, thresholds and reason codes so decisions could be reviewed and explained.

## 4. Model Evaluation Outputs

Evaluation included:

- confusion matrix;
- accuracy;
- precision;
- recall;
- F1-score;
- ROC-AUC;
- PR-AUC for class imbalance;
- false-positive review;
- false-negative review;
- threshold comparison;
- score distribution review;
- review workload by threshold;
- model comparison against logistic regression baseline;
- time-based validation split so future information did not leak into training.

Interview-defensible version:

> I did not judge the model by accuracy alone because fraud-style data is imbalanced. I looked at precision, recall, F1-score, ROC-AUC, PR-AUC, false positives, false negatives and threshold effects. I also reviewed how threshold changes affected review workload, because a technically better model could still create too many cases for users to handle.

## 5. Monitoring

Monitoring covered both **data health** and **model behaviour**.

It tracked:

| Monitoring area | Examples |
| --- | --- |
| **Event flow** | Event volume, rejected events, missing event IDs, duplicate IDs. |
| **Schema/data quality** | Missing fields, invalid categories, null rates, failed joins, rejected records. |
| **Service health** | API errors, Lambda failures, EKS service errors, processing latency. |
| **Model output** | Score distributions, flagged-case volume, reason-code frequency, threshold band movement. |
| **Decision quality** | False positives, false negatives, reviewed cases, label feedback. |
| **Drift indicators** | Feature distribution movement, score distribution movement, unexpected category changes. |
| **Operational alerts** | CloudWatch alarms for failed jobs, high rejection rates, abnormal event volume and service errors. |

Best concise wording:

> I monitored the platform at three levels: whether events were flowing, whether the data was valid, and whether model outputs were behaving as expected. That included rejected events, null rates, failed joins, score distributions, reason-code frequency, false positives, false negatives and CloudWatch alarms for service failures.

## 6. Governance, Ethics And Privacy Controls

The platform had these controls:

- **Least-privilege IAM permissions** for services.
- **No hard-coded credentials**; configuration and secrets were kept in SSM Parameter Store and Secrets Manager.
- **Raw and curated data separation** so users did not work directly from raw events.
- **Reason codes** for every reviewable decision so users could understand why a case was flagged.
- **Validation flags** to separate behavioural risk from data-quality problems.
- **Model cards / evaluation notes** documenting model purpose, features, thresholds, metrics, known limitations and appropriate use.
- **Human review step** for high-risk cases rather than treating the model as a final punitive decision.
- **Bias and fairness checks** across available non-sensitive operational segments, such as channel, transaction type, account age band and merchant/category group.
- **Audit trail** of event ID, model version, threshold version, decision timestamp and reason codes.
- **Data minimisation**: only fields needed for decisioning and evaluation were used in curated outputs.
- **Retention rules** for evidence records and evaluation outputs.

Strongest wording:

> I treated responsible AI as part of the system design. Decisions were supported by reason codes, validation flags, model-version records, threshold records and evaluation notes, so outputs could be reviewed rather than treated as a black box. I avoided hard-coded credentials, separated raw data from curated outputs, used least-privilege access, and documented limitations so users understood where the model should and should not be relied on.

## Canonical One-Paragraph Platform Description

Use this as the settled platform description going forward:

> I built an AWS-hosted fraud and transaction decisioning platform that covered ingestion, validation, feature creation, rule and model decisioning, case creation, monitoring dashboards and offline evaluation. I used Python, SQL, Docker, GitHub, GitHub Actions, EKS, Lambda, MSK Serverless, Aurora PostgreSQL, S3, CloudWatch, SageMaker and MLflow to build repeatable services and evaluation workflows. The decisioning approach combined rules, logistic regression baselines, gradient-boosted models, thresholds and reason codes. I evaluated models using precision, recall, F1-score, ROC-AUC, PR-AUC, confusion matrices, false-positive and false-negative review, and threshold analysis. I also built data-quality checks, score monitoring, reason-code dashboards and governance controls so outputs could be reviewed, explained and improved rather than treated as black-box scores.
