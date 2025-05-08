# Fraud Prediction System — Project Charter  
*Baseline v1.0  (5 May 2025)*

---

## 1 · Vision
Build a **real-time, enterprise-grade fraud-prediction platform** that proves I can operate at mid/senior Data-Science + MLOps level in the finance sector.  
The deliverable is a public GitHub repo, fully automated AWS stack, and case-study blog series which shows off my experience

---

## 2 · Scope

| In scope (must-haves)                                                        | Out of scope (won’t build)            |
|------------------------------------------------------------------------------|---------------------------------------|
| • Synthetic payments data generator (open-sourced as a pip package)          | Actual card-network integration       |
| • Offline & online feature stores (Feast → DynamoDB/Redis)                   | 3-D Secure or SCA flows               |
| • Model experimentation, registry, CICD (SageMaker Pipelines + MLflow)       | Mobile SDK / native apps              |
| • Real-time REST/GRPC scoring endpoint (≤150 ms p99)                         | Large-scale batch ETL (Spark, EMR)    |
| • Explainability (SHAP) & “right-to-explanation” API                         | Non-AWS cloud providers               |
| • Drift, performance & cost monitoring → Grafana / CloudWatch dashboards     | On-prem deployment                    |
| • FinOps guardrails: automated budget alerts & teardown scripts              |                                       |

Success is defined by **functional acceptance + performance targets + cost cap** (see §3 & §8).

---

## 3 · Success Metrics

| Dimension        | Target                                                                                             |
|------------------|----------------------------------------------------------------------------------------------------|
| Model quality    | AUC-PR ≥ 0.92 on hold-out set with fraud prevalence ≤ 0.3 %                                        |
| Latency          | End-to-end scoring ≤ 150 ms p99 under 200 TPS synthetic load                                       |
| Availability     | ≥ 99.5 % over 30-day synthetic soak test (blue/green deployment)                                   |
| Cost             | **≤ £50 / month AWS** (alerts at 60 % & 90 % of budget)                                            |
| Compliance       | 100 % feature lineage tracked; GDPR “right to explanation” API returns within 24 h SLA             |
| Documentation    | README, ADRs, architecture diagram, and sprint reports meet “good-first-issue” contributor test    |

---

## 4 · High-Level Architecture
<img src="docs/img/high_level_arch.png" alt="High-Level Architecture" height="400" />

```
Clients ─► API Gateway ─► AWS Lambda/Fargate Service ─►
├─► Online Feature Store (DynamoDB + Redis cache)
├─► Model Endpoint (SageMaker Realtime Endpoint via Nginx container)
└─► Async Kafka / Kinesis stream  ─► Monitoring & Drift
Offline side: S3 Data Lake ─► SageMaker Pipelines (training) ─► MLflow Registry ─► Model Artefacts ─► Endpoint
IaC: Terraform + pre-commit hooks  •  Observability: CloudWatch + Grafana OSS on Fargate
```

*Rationale*: stays in Free/Always-On tier where possible (API Gateway, Lambda), switches to spot instances for training, and keeps heavy infra (EKS) out to respect the £50/month guardrail.

---

## 5 · Data Flow

1. **Synthetic Generator** (Python/Polars) writes daily parquet to S3 “raw/”.
2. **Feature-Build Pipeline** (Prefect) creates:
   * *Offline features* → S3 “feature-store/offline/”.
   * *Online features* → DynamoDB; hot features cached in Redis (Elasticache).
3. **Training Pipeline** (SageMaker Pipelines):
   * Pulls offline features, trains XGBoost & LightGBM; logs to Neptune.ai.
   * Registers champion/challenger in MLflow Registry.
4. **CI/CD** (GitHub Actions):
   * On model-pkg push ⇒ smoke test ⇒ canary deploy (blue/green).
5. **Realtime Scoring**: request → API Gateway → Lambda router → feature fetch → model inference → response.
6. **Monitoring**:
   * Latency, throughput (CloudWatch).
   * Prediction distribution vs. baseline (drift) → Grafana dashboard.
   * Cost Explorer API polled nightly; alert SNS at thresholds.

---

## 6 · User Personas & Key Stories

| Persona                    | “As a … I want …”                                                            | Sprint ID |
|----------------------------|------------------------------------------------------------------------------|-----------|
| Fraud-Ops Analyst          | to review each flagged txn with feature-attribution so I can decide quickly. | FS-01     |
| Compliance Officer         | to query why a txn was blocked within 24 h to satisfy GDPR regulators.       | CO-01     |
| MLOps Engineer             | automated blue/green rollback if p99 latency > 150 ms after deploy.          | MO-02     |
| Data Science Lead          | visibility into weekly model/drift metrics via a Grafana link in Slack.      | DS-03     |
| End Customer (Card Holder) | near-instant approval for legitimate txns (≤150 ms p99).                     | CU-01     |

---

## 7 · Tech Stack

| Layer               | Primary Tools/Services                                   | Notes / Cost Tactics                             |
|---------------------|----------------------------------------------------------|--------------------------------------------------|
| Language            | **Python 3.12**                                          | Standard in DS; supports `polars` & `pydantic`.  |
| Core ML             | scikit-learn, XGBoost, LightGBM                          | Free, GPU optional via spot.                     |
| Experiment Tracking | **Neptune.ai (free tier)**; MLflow Registry              | Neptune for rich UI; MLflow for infra-as-code.   |
| Feature Store       | **Feast** (offline S3, online DynamoDB + Redis)          | DynamoDB on-demand; Redis cache small (1 GB).    |
| Serving Infra       | API Gateway + Lambda (router) → SageMaker Endpoint       | Endpoint on ml.t3.medium, auto-pauses overnight. |
| Data Pipelines      | Prefect OSS                                              | Runs on EC2 spot; no SaaS fee.                   |
| IaC & CICD          | Terraform, GitHub Actions, pre-commit (`ruff`, `pytest`) | GH Actions 2k free minutes/mo.                   |
| Observability       | CloudWatch, Grafana OSS on Fargate                       | Minimal t4g.small task; free CloudWatch tier.    |
| Security            | IAM least-privilege, Checkov/TFSec in pipeline           | **Automated unit tests for IAM**                 |
| Cost Management     | AWS Budgets, Cost Explorer API                           | SNS → email/Slack at 60 % & 90 % thresholds.     |

---

## 8 · Constraints & Guardrails

### Time  
*Available effort*: **≈40 h/wk** outside Five Guys shifts.  
*Total project window*: 5 months ⇒ **~20 weeks ≈ 800 hrs** personal effort.

### Cost  
*Monthly AWS cap*: **£50**  
*Controls*:  
1. All training on spot or local Docker.  
2. Endpoint auto-pause overnight.  
3. `terraform destroy` for non-prod stacks after demos.  
4. Weekly cost-report job; SNS alerts.

---

## 9 · Milestones & Timeline (Gantt-ish)

| Phase                                   | Calendar Weeks       | Key Deliverables                                                      |
|-----------------------------------------|----------------------|-----------------------------------------------------------------------|
| **Sprint 01 – Scaffold + Sandbox**      | 12 May → 25 May 2025 | Repo skeleton, AWS bootstrap, first synthetic dataset, baseline model |
| Sprint 02 – Feature Store MVP           | 26 May → 8 Jun       | Feast offline/online wired; E2E local scoring demo                    |
| Sprint 03 – Training Pipelines          | 9 Jun → 22 Jun       | SageMaker Pipelines, Neptune logging, MLflow registry                 |
| Sprint 04 – Realtime Serving            | 23 Jun → 6 Jul       | API Gateway + Lambda router → endpoint, latency SLA hit               |
| Sprint 05 – Explainability + Compliance | 7 Jul → 20 Jul       | SHAP API, GDPR data-retention tests, audit logs                       |
| Sprint 06–07 – Monitoring & FinOps      | 21 Jul → 17 Aug      | Grafana dashboards, cost controls, drift alerts                       |
| Sprint 08 – Hardening & Soak Test       | 18 Aug → 31 Aug      | 30-day synthetic soak, incident playbook                              |
| Sprint 09 – Content & Case Study        | 1 Sep → 14 Sep       | Blog series, demo video, LinkedIn posts                               |
| **Sprint 10 – Polish & Release v1**     | 15 Sep → 28 Sep      | v1.0 tagged, résumé & cover-letter updates                            |

(Timeline is adjustable; change requests will update §9.)

---

## 10 · Governance & Process

* **Methodology** – Scrum-lite, 2-week sprints.  
* **Boards** – GitHub Projects → one column per sprint.  
* **Ceremonies** – Sprint Planning, async daily stand-up (Yesterday / Today / Blockers), Sprint Review + Retro.  
* **Change Control** – Any scope/stack/timeline change must be noted in `CHANGELOG.md` and approved in chat.  
* **Documentation** – README, `/docs/` folder, ADRs, and diagram source (`draw.io`) stored in repo.

---

## 11 · Risks & Mitigations

| Risk                               | Likelihood | Impact | Mitigation                                            |
|------------------------------------|------------|--------|-------------------------------------------------------|
| AWS bill blows past £50/mo         | Medium     | High   | Budget alerts, shutdown script in CI                  |
| Work shifts reduce available hours | Medium     | Medium | Re-plan sprint; move non-critical tasks               |
| Model quality target not met       | Low-Med    | High   | Hyperparameter search, synthetic data tuning          |
| Service latency exceeds 150 ms p99 | Med        | High   | Profiling, Redis caching, endpoint auto-scaling       |
| Burn-out                           | Medium     | High   | Built-in slack (70 h target per sprint), weekly retro |

---

## 12 · References

* AWS Well-Architected – Serverless Lens  
* Feast docs, v0.43  
* SageMaker Pipelines best-practices (re:Spot training)  
* GDPR Article 15 (“Right of access”) & Article 22 (Automated decision-making)

---

# Sprint 01 Backlog  —  12 May → 25 May 2025  (Capacity ≈ 80 hrs; plan = 70 hrs)

| 🗂 Issue ID | Task (Definition of Done = merged ± CI green)                                     | Est. hrs |
|-------------|-----------------------------------------------------------------------------------|----------|
| **REP-01**  | Initialise mono-repo (`main` & `dev`), commit this charter, tag **baseline-v1.0** | 3        |
| **REP-02**  | Pre-commit: `ruff`, `black`, `pytest`, `terraform fmt`                            | 4        |
| **IAC-01**  | Terraform bootstrap: VPC, S3 buckets, IAM least-privilege roles                   | 10       |
| **CST-01**  | AWS Budget & CloudWatch alarm + SNS email integration                             | 4        |
| **DAT-01**  | Design synthetic schema & YAML config                                             | 6        |
| **DAT-02**  | Spike script: generate 1 M txns (Polars), profile, export to S3                   | 10       |
| **ML-01**   | Baseline XGBoost notebook → metrics logged to Neptune (free tier)                 | 8        |
| **DOC-01**  | First Architecture Decision Record (ADR-0001: Choose Feast)                       | 2        |
| **OPS-01**  | GitHub Action: lint + unit-test on PR                                             | 3        |
| **OPS-02**  | Cost-teardown script (`make nuke`)                                                | 4        |
| **MGT-01**  | Sprint Review & Retrospective docs template                                       | 2        |
| **BUFFER**  | Contingency / spill-over                                                          | 14       |

**Sprint Goal**: *“Repo scaffolded, AWS sandbox cost-capped, first synthetic dataset and baseline model produced; demo E2E flow data → metric.”*

---

*End of Charter — tag `baseline-v1.0`*
