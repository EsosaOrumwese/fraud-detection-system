# IaC environments

## Status
Phase 2 implementation unlocked for `dev_min`.

## Environments
- `dev_min/`: composes `core` + `demo` modules for managed-substrate migration.

## Notes
- State backend is local during bootstrap.
- Core module provisions tf-state bucket + lock table for remote-backend migration in later phases.
