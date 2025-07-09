# Fraud Detection System  
[![codecov](https://codecov.io/gh/EsosaOrumwese/fraud-detection-system/graph/badge.svg?token=9INHHQJDOO)](https://codecov.io/gh/EsosaOrumwese/fraud-detection-system)

> **Enterprise-grade, real-time fraud-prediction platform**  
> Portfolio project — built E2E with Terraform, Polars/Faker, XGBoost 2,  
> MLflow 3, and (future) Airflow 3 + Feast feature store.

---

## 👟 Quick-start

```bash
# 1  Clone & install
git clone https://github.com/EsosaOrumwese/fraud-detection-system.git
cd fraud-detection-system
poetry install --with dev

# 2  Bootstrap Terraform sandbox (≈ 2 min, free-tier)
make tf-init && make tf-plan && make tf-apply

# 3  Generate 1 M synthetic transactions + profile
make pull-raw-bucket           # pulls SSM param into .env
make gen-data      ROWS=1000000
make profile

# 4  Train baseline model & view MLflow UI
make ml-train      ROWS=500000
make mlflow-ui-start    # → http://localhost:5000
````

---
## Data Generator

This repository includes an end-to-end synthetic fraud-data generator under `src/fraud_detection/simulator/`.

### Usage

```bash
python src/fraud_detection/simulator/cli.py \
  --config project_config/generator_config.yaml \
  [--realism v1|v2] \
  [--num-workers N] [--batch-size M] \
  [--s3]
````

* **--config**: YAML config with all generator parameters.
* **--realism**:

  * `v1`: rebuilds customer/merchant/card catalogs per chunk (legacy).
  * `v2`: pre-writes catalogs once to `out_dir/catalog/` and reuses them—faster for large runs.
* **--s3**:

  * Uploads transactions to your “raw” S3 bucket (`/fraud/raw_bucket_name`).
  * When `--realism v2`, also uploads catalog Parquets to your artifacts bucket (`/fraud/artifacts_bucket_name`).

### Outputs

* **Transactions**: partitioned Parquet under `out_dir/payments/year=…/month=…/transactions.parquet`.
* **Catalogs** (v2 only):

  * `out_dir/catalog/customers.parquet`
  * `out_dir/catalog/merchants.parquet`
  * `out_dir/catalog/cards.parquet`

### Schema

See `schema/transaction_schema.yaml` for the transaction column definitions and types.

---

## 📚 Documentation

| Doc                       | Description                                      |
|---------------------------|--------------------------------------------------|
| **PROJECT\_CHARTER.md**   | Scope, sprint cadence, acceptance criteria       |
| **docs/adr/**             | Architecture Decision Records (`ADR-0008`, etc.) |
| **docs/data-dictionary/** | Auto-generated schema dictionary                 |
| **sprints/**              | Sprint plans & velocity tracking                 |

---

## 🛠️ Operations

### Teardown (“nuke”)

Safely destroys **only** sandbox resources: VPC, buckets, IAM roles, and local MLflow artefacts.

```bash
# 1 Pull bucket names from Parameter Store
make pull-raw-bucket && make pull-artifacts-bucket

# 2 Run the nuke script (prompts for token)
make nuke                # type NUKEME to confirm

# GitHub UI (dry-run by default)
Actions → **Nuke Sandbox** → enter NUKEME
```

---

## 📈 Project board

Sprint backlog and done column live on the **GitHub Projects** tab — updated each pull-request.

---

*© 2025 Esosa Orumwese* — MIT Licence
Built with ❤️, caffeine, and lots of `pre-commit` hooks.

