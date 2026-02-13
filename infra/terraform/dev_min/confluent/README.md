# dev_min confluent stack

Purpose: managed Confluent lifecycle for `dev_min` (environment, cluster, topics, runtime Kafka credentials), with runtime credential materialization to pinned AWS SSM paths.

This stack is the canonical root pinned by:
- `TF_STACK_CONFLUENT_DIR = "infra/terraform/dev_min/confluent"`
- `TF_STATE_KEY_CONFLUENT = "dev_min/confluent/terraform.tfstate"`

## Initialize

Create `backend.hcl` from `backend.hcl.example`, then run:

```powershell
terraform -chdir=infra/terraform/dev_min/confluent init -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/terraform/dev_min/confluent validate
```

## Notes

- Confluent Cloud management credentials are operator/CI-managed inputs (`TF_VAR_confluent_cloud_api_key`, `TF_VAR_confluent_cloud_api_secret`).
- Runtime Kafka bootstrap/key/secret are written to pinned SSM paths for downstream consumption.
- Apply/destroy is phase-gated by platform M2/M9 process.
