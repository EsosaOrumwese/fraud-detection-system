### Current **Product Backlog** (everything that did **not** ship in Sprint-01)

Below is the curated list that’s still on the board, grouped by epic.
Use it during the Sprint-01 Review to show stakeholders what “ready” work is queued for Sprint-02 and beyond.

| Epic / Theme                    | Key backlog cards (IDs)                                                                                                                                                                                                                                                                 | Rough size       | Why it matters                                                                            |
|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|-------------------------------------------------------------------------------------------|
| **Synthetic-Data Enhancements** | *SD-01* Entity catalogues (customers, cards, merchants)<br>*SD-02* Zipf-style entity reuse<br>*SD-03* Time-of-day & weekday seasonality<br>*SD-04* Scenario-based fraud injection (velocity, impossible-travel)<br>*SD-05* Great Expectations suite<br>*SD-06* Dockerfile for simulator | L, L, M, L, M, S | Makes data realistic so models can learn behavioural patterns; enables later drift tests. |
| **Orchestration & Pipelines**   | *ORCH-01* Airflow 3 docker-compose stack<br>*ORCH-02* DAG: daily synthetic-data → S3<br>*ORCH-03* DAG: offline feature build Materialise→Feast<br>*ORCH-04* MWAA one-day demo (optional, cost)<br>*ORCH-05* Airflow CI DAG-lint                                                         | M, M, M, S, S    | Moves ad-hoc scripts into production-style scheduling; recruiter-friendly buzzword.       |
| **Feature Store & Serving**     | *FS-01* Feast repo scaffold (entities, feature views)<br>*FS-02* Backfill + point-in-time join test<br>*FS-03* Online store: DynamoDB + Redis cache<br>*FS-04* Airflow operator wiring                                                                                                  | L, M, M, S       | Enables leakage-free training and sub-150 ms online inference.                            |
| **Experiment Tracking Upgrade** | *MLF-01* Stand-alone MLflow tracking server (EC2 t3.micro)<br>*MLF-02* MLflow model registry promotion rules (baseline → staging)                                                                                                                                                       | M, S             | Single, industry-standard tool for runs **and** registry; replaces Neptune stub.          |
| **Model Quality**               | *MODE-01* Hyper-parameter sweep with Optuna (20 trials)<br>*MODE-02* SHAP global & local plots                                                                                                                                                                                          | M, S             | Shows measurable lift over Sprint-01 baseline; adds explainability deliverable.           |
| **Monitoring & FinOps**         | *MON-01* CloudWatch + Grafana latency / AUC dashboard<br>*FIN-01* Infracost PR comments for infra deltas                                                                                                                                                                                | M, S             | Demonstrates production-grade observability and cost discipline.                          |
| **Infra Hardening**             | *INF-01* Tag enforcement (environment=sandbox) in nuke script<br>*INF-02* KMS encryption for SNS topic (budget alerts)<br>*INF-03* S3 remote state backend with DynamoDB lock                                                                                                           | S, S, M          | Security & ops polish; good audit talking points.                                         |

**Total “ready” cards:** 23 (≈ 6–7 sprint-weeks of work for one engineer).
During Sprint-01 Review you’ll propose **Sprint-02** capacity \~70 h and pull in:

* Synthetic-Data Enhancements: **SD-01 → SD-03**
* Orchestration: **ORCH-01, ORCH-02**
* Feature-Store scaffold: **FS-01, FS-02**
* MLflow upgrade: **MLF-01**

That keeps Sprint-02 coherent around **“Realistic data & automated daily pipeline”**.

---

### How to present this in the Review deck

1. **One slide per epic** with bullet list of next cards.
2. Highlight **dependencies** (Airflow must land before Feast backfill).
3. Show budget guard-rail: projected additional AWS spend < £20/month (Airflow local, MLflow t3.micro, Redis cache 750 MB).
4. End with **Sprint-02 draft goal**:

   > “Daily Airflow DAG generates realistic payments, materialises to Feast, trains an updated model, and logs runs to MLflow server.”

That narrative tells reviewers (and future recruiters) exactly what’s coming next and why it matters.
