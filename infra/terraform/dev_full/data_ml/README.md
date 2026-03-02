# dev_full data_ml stack

This stack materializes M2.G data/ML control surfaces needed for dev_full substrate readiness:

- IAM roles:
  - `ROLE_SAGEMAKER_EXECUTION`
  - `ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS`
- SSM paths:
  - `/fraud-platform/dev_full/databricks/workspace_url`
  - `/fraud-platform/dev_full/databricks/token`
  - `/fraud-platform/dev_full/mlflow/tracking_uri`
  - `/fraud-platform/dev_full/sagemaker/model_exec_role_arn`

Notes:
- Values are seeded via Terraform variables and can be overridden by environment variables (`TF_VAR_*`) in CI/runtime.
- This stack is focused on M2 control-surface materialization and role/secret readability contracts, not full Databricks/SageMaker workload deployment.
