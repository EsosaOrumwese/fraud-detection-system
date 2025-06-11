# Sprint-02 — “Realistic Data & Automated Pipelines”  
*11 Jun → 24 Jun 2025*  
Capacity: **40 h / week × 2 weeks = 80 h** (plan ≈ 70 h, 10 h buffer)

---

## 🎯 Sprint Goal  
> **“A daily Airflow 3 pipeline generates realistic payments, materialises features in Feast (offline + online), and logs every model run to a dedicated MLflow tracking server.”**

A successful demo shows:  
1. `docker compose up` → Airflow 3 UI with two green DAGs (Data Gen, Feature Build).  
2. New Parquet file + Feast offline store + DynamoDB online table.  
3. MLflow tracking server (t3.micro) receiving runs from the DAG.  

---

## 1 · Backlog & Estimates (ordered by dependency)

| ID          | Task (DoD = merged PR + CI green)                                      | Est. h |
|-------------|------------------------------------------------------------------------|--------|
| **ORCH-01** | **Airflow 3 stack**: docker-compose, Postgres, web UI on `:8080`       | 6      |
| **ORCH-02** | DAG **daily_synthetic** → runs generator CLI, uploads Parquet to S3    | 10     |
| **SD-01**   | **Entity catalogues** (customers, cards, merchants) with Zipf sampling | 8      |
| **SD-02**   | **Time-of-day & weekday seasonality** in generator                     | 6      |
| **FS-01**   | Feast repo scaffold: repo config, customer & merchant entities         | 8      |
| **FS-02**   | DAG **feature_materialise** → offline parquet, online DynamoDB         | 10     |
| **MLF-01**  | MLflow tracking server (EC2 t3.micro) + SSH tunnel for local UI        | 6      |
| **PIPE-01** | Airflow task → train baseline model nightly, log to MLflow server      | 8      |
| **INF-02**  | KMS-encrypted SNS topic for budget alerts (tfsec MEDIUM fix)           | 3      |
| **DOC-02**  | ADR-0008: “Choose Airflow 3 over Prefect”                              | 2      |
| **MGT-02**  | Sprint-02 Review/Retro templates scaffold                              | 1      |
| **BUFFER**  | Slack for surprises                                                    | **12** |

**Planned hours:** 70

---

## 2 · Timeline & Checkpoints

| Date           | Focus block                | Target output                            |
|----------------|----------------------------|------------------------------------------|
| **Wed 11 Jun** | ORCH-01 compose stack      | Airflow UI up :8080                      |
| Thu 12 Jun     | SD-01 entity tables        | `customers.parquet`, `merchants.parquet` |
| Fri 13 Jun     | SD-02 seasonality          | Generator CLI flag `--realism v2`        |
| Sat 14 Jun     | ORCH-02 DAG draft          | Task success icon in Airflow             |
| Sun off        | —                          | —                                        |
| **Mon 16 Jun** | FS-01 scaffold             | `feature_repo/` with 2 entities          |
| Tue 17 Jun     | FS-02 materialise DAG      | FeatureParquet + DynamoDB table          |
| Wed 18 Jun     | MLF-01 server up           | `mlflow ui -p 5001` tunnel               |
| Thu 19 Jun     | PIPE-01 nightly train task | New run in MLflow server                 |
| Fri 20 Jun     | INF-02 KMS SNS + ADR-0008  | tfsec HIGH→0                             |
| Sat 21 Jun     | MGT-02 docs, buffer        | Review docs drafted                      |
| **Sun 23 Jun** | Demo dry-run               | All tasks green                          |
| **Mon 24 Jun** | *Sprint-02 Review & Retro* | Goal met or carry-over                   |

---

## 3 · Definition of Done (for the sprint)

* Two Airflow DAGs green for three consecutive runs.  
* Feast `first_feature_view` holds ≥ 10 columns; DynamoDB online row count > 0.  
* MLflow tracking server reachable; nightly model run logged with params & AUC-PR metric.  
* tfsec / Checkov: **0 HIGH** severities.  
* `docs/` contains Sprint-02 Review & Retro stubs.  

---

## 4 · Risks & Mitigations

| Risk                               | Likelihood | Impact | Mitigation                                               |
|------------------------------------|------------|--------|----------------------------------------------------------|
| Airflow docker memory leaks        | Med        | Med    | Limit containers to 1 GB; restart nightly                |
| MLflow server cost creep           | Low        | Med    | t3.micro + stop instance outside work hours              |
| Feast point-in-time join confusion | Med        | High   | Reserve half-day spike and pair-review feature view code |
| Data realism slows generator       | Med        | Low    | Keep v1 path; toggle realism with flag                   |

---

## 5 · Sprint-02 GitHub Board Columns

* Backlog (future)  
* **Sprint-02** (active)  
* In Progress  
* In Review  
* Done  
* Blocked (24 h escalation)

---

*(end sprint plan)*
