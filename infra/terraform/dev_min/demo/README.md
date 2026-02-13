# dev_min demo stack

Purpose: ephemeral demo substrate for `dev_min`.

This stack is the canonical root pinned by:
- `TF_STACK_DEMO_DIR = "infra/terraform/dev_min/demo"`
- `TF_STATE_KEY_DEMO = "dev_min/demo/terraform.tfstate"`

## Capability lanes in this stack

- Confluent runtime contract surfaces:
  - consumes Confluent metadata/credentials from `dev_min/confluent` remote state by default,
  - writes canonical SSM paths for bootstrap/API key/API secret,
  - topic catalog artifact for pinned topic map visibility.
- ECS runtime scaffolding:
  - VPC/public subnets/security groups,
  - ECS cluster + minimal task definition + desired-count-zero service.
- Runtime DB:
  - demo-scoped Postgres RDS instance + subnet group + DB security group,
  - canonical SSM paths for DB user/password (and optional DSN).
- Observability/evidence:
  - demo log group,
  - demo manifest + Confluent topic catalog objects in evidence bucket.

## Initialize

Create `backend.hcl` from `backend.hcl.example`, then run:

```powershell
terraform -chdir=infra/terraform/dev_min/demo init -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/terraform/dev_min/demo validate
```

## Notes

- Demo resources are destroy-by-default.
- Backend config file is local/operator-managed.
- Apply/destroy is phase-gated by platform M2/M9 process.
- Recommended order: apply `core`, then `confluent`, then `demo`.
- Manual Confluent values are fallback-only (`confluent_credentials_source = "manual"`).
