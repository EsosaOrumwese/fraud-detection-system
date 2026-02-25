# Dev Full Track Maps
_As of 2026-02-25_

This folder is reserved for `dev_full` planning and implementation notes.

## Intended contents
- `platform.build_plan.md` (dev_full master phase plan and status owner)
- `platform.impl_actual.md` (dev_full implementation decision trail)
- `platform.M*.build_plan.md` (deep plans per active phase)
- `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md` (dev_full migration authority)
- `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (dev_full phase/gate authority)
- `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (dev_full handle authority)

## Current posture
- Phase progression:
  - `M0..M5` are `DONE`.
  - `M6` is `ACTIVE`.
- Active gate posture:
  - `M6.E` (`P6.A`) is closed green on the EMR-on-EKS runtime path.
  - `M6.F` (`P6.B`) is fail-closed pending blocker clearance.
  - open blockers: `M6P6-B2`, `M6P6-B4`.
  - structurally remediated: `M6P6-B3` (IG idempotency persistence path active).
- Next closure step:
  - clear `M6P6-B2/B4`, rerun `M6.F`, and proceed to `M6.G` only on zero-blocker verdict.
- `dev_min` remains closed and isolated under `../dev_min/`.
