# dev_min Terraform environment

This environment composes Phase 2 infrastructure modules:
- `core` (persistent): S3 stores, control tables, optional budget alert.
- `demo` (ephemeral): demo marker artifacts/logging surfaces.

## Commands

From repo root:

```bash
make platform-dev-min-phase2-plan
make platform-dev-min-phase2-up DEV_MIN_ALLOW_PAID_APPLY=1
make platform-dev-min-phase2-status
make platform-dev-min-phase2-down
make platform-dev-min-phase2-post-destroy-check
make platform-dev-min-phase2-down-all DEV_MIN_ALLOW_PAID_DESTROY_ALL=1
```

All commands source `DEV_MIN_ENV_FILE` (default `.env.dev_min`) and emit local infra evidence under `runs/fraud-platform/dev_substrate/phase2/`.

## State

Current default backend is local state for bootstrap simplicity. The module still provisions TF state bucket + lock table to support remote-backend migration in later phases.
