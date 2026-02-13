# dev_min core stack

Purpose: persistent low-cost substrate for `dev_min`.

This stack is the canonical root pinned by:
- `TF_STACK_CORE_DIR = "infra/terraform/dev_min/core"`
- `TF_STATE_KEY_CORE = "dev_min/core/terraform.tfstate"`

## Initialize

Create `backend.hcl` from `backend.hcl.example`, then run:

```powershell
terraform -chdir=infra/terraform/dev_min/core init -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/terraform/dev_min/core validate
```

## Notes

- No secrets in repo.
- Backend config file is local/operator-managed.
- Apply/destroy is phase-gated by platform M2/M9 process.

