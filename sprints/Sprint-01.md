# Sprint 01 — Scaffold & Sandbox  
*12 May → 25 May 2025*  
Capacity: **40 h/week × 2 weeks = 80 h** (plan for 70 h work, 10 h buffer)

---

## Sprint Goal  
> **“Repo scaffolded, AWS sandbox cost-capped, first synthetic dataset generated, and a baseline fraud model trained & logged — demo end-to-end data → metric.”**

Demo criteria  
* Browser-share showing:  
  1. GitHub repo with CI green check.  
  2. AWS console: S3 bucket with `raw/` parquet files and budget alarm in place.  
  3. Neptune.ai run with baseline AUC-PR metric.  

---

## Work Breakdown

| ID         | Task                                                                                                 | Owner | Est. hrs | Acceptance Criteria                                                                             |
|------------|------------------------------------------------------------------------------------------------------|-------|----------|-------------------------------------------------------------------------------------------------|
| **REP-01** | Initialise mono-repo (`main`, `dev`), add `PROJECT_CHARTER.md`, tag `baseline-v1.0`.                 | Esosa | 3        | `git tag` visible on GitHub; charter rendered.                                                  |
| **REP-02** | Configure **pre-commit** (`ruff`, `black`, `pytest`, `terraform fmt`).                               | Esosa | 4        | Running `pre-commit run --all-files` returns 0 errors locally & in CI.                          |
| **OPS-01** | GitHub Action — lint + unit-test on every PR.                                                        | Esosa | 3        | PR shows green check; failing test blocks merge.                                                |
| **IAC-01** | Terraform bootstrap: VPC, S3 (`fraud-dl-raw`, `fraud-model-artifacts`), IAM roles (least-privilege). | Esosa | 10       | `terraform apply` succeeds; state in `infra/terraform.tfstate`; security scan (Checkov) passes. |
| **CST-01** | AWS Budget: £50/mo; CloudWatch alarm SNS → your email.                                               | Esosa | 4        | Alarm email received after manual threshold test; budget visible in console.                    |
| **DAT-01** | Design synthetic payments schema (YAML spec, 20+ fields inc. location, MCC, device).                 | Esosa | 6        | Spec committed; peer-review (me) approved; ADR-0002 documents design choice.                    |
| **DAT-02** | Generator spike: create 1 M rows with Polars, profile with `pandas-profiling`, upload to S3.         | Esosa | 10       | `data/sample_1M.parquet` in S3; profiling HTML artefact saved.                                  |
| **ML-01**  | Baseline model: XGBoost on local box; log run to Neptune (free).                                     | Esosa | 8        | Neptune run shows AUC-PR metric ≥0.70 (placeholder target).                                     |
| **DOC-01** | ADR-0001: Choose Feast for feature store (template in `/docs/ADRs`).                                 | Esosa | 2        | ADR committed & linked from README.                                                             |
| **OPS-02** | Cost-teardown script `make nuke`: destroys non-prod resources.                                       | Esosa | 4        | Running script removes sandbox stack; verified by empty AWS console.                            |
| **MGT-01** | Sprint Review & Retro templates (Markdown).                                                          | Esosa | 2        | `/docs/sprint-review.md` & `/docs/retro.md` committed.                                          |
| **BUFFER** | Contingency / spill-over                                                                             | —     | 14       | —                                                                                               |

**Total planned**: 70 h

---

## Timeline & Checkpoints

| Date                  | Focus                        | Target output                            |
|-----------------------|------------------------------|------------------------------------------|
| **Mon 12 May**        | Kick-off, tasks REP-01/02    | Repo pushed, pre-commit hooks installed  |
| Tue 13 May            | OPS-01 CI pipeline           | First PR shows green check               |
| Wed-Thu 14-15 May     | IAC-01 Terraform             | Sandbox infra live                       |
| Fri 16 May            | CST-01 Budget alarm          | Test email received                      |
| Sat 17 May (flex)     | DAT-01 schema design         | ADR-0002 merged                          |
| Sun Off / Rest        | —                            | —                                        |
| **Mon-Tue 19-20 May** | DAT-02 generator spike       | 1 M parquet + profiling                  |
| Wed-Thu 21-22 May     | ML-01 baseline model         | Neptune run logged                       |
| Fri 23 May            | OPS-02 teardown script       | Demo destroy/re-apply                    |
| Sat 24 May            | MGT-01 templates, buffer     | Docs ready                               |
| **Sun 25 May**        | *Sprint Review* demo & Retro | Goal met or move spill-over to Sprint 02 |

*(You can shuffle days around your Five Guys rota; checkpoints keep us honest.)*

---

## Definition of Done

* Code merged to `main` via reviewed PR.  
* All pre-commit hooks pass.  
* GitHub Actions green.  
* Relevant artefacts (data sample, profiling report, screen-shots) stored in repo or S3.  
* Task card moved to “Done” on GitHub Projects.

---

## Risks this sprint

| Risk                         | Trigger                                   | Mitigation                                                  |
|------------------------------|-------------------------------------------|-------------------------------------------------------------|
| Terraform permissions error  | First `apply` fails due to IAM mis-config | Pair-debug in chat; use AWS CloudShell if needed.           |
| 1 M-row gen too slow locally | Laptop limits                             | Use Polars + pyarrow; fall back to 100 k rows for baseline. |
| Neptune free-tier throttling | Exceeds 200 runs/mo.                      | We log **1** run this sprint; fine.                         |

---

## Sprint Review Agenda (Fri 23 / Sun 25 May)

1. Live demo: local CLI → synthetic data → baseline model in Neptune.  
2. Show AWS Budget alarm & teardown script.  
3. Discuss any scope spill-over to Sprint 02.  

---

## Retro Prompt

*What went well?* • *What could be improved?* • *What will we try next sprint?*

---

*(End Sprint-01 Plan)*
