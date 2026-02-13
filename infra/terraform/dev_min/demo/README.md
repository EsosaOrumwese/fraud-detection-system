# dev_min demo stack

Purpose: ephemeral demo substrate for `dev_min`.

This stack is the canonical root pinned by:
- `TF_STACK_DEMO_DIR = "infra/terraform/dev_min/demo"`
- `TF_STATE_KEY_DEMO = "dev_min/demo/terraform.tfstate"`

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

