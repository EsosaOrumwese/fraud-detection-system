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
  - `M6.F` (`P6.B`) is now closed green on authoritative remote rerun `m6f_p6b_streaming_active_20260225T152755Z` (GitHub Actions run `22403542013` on `migrate-dev`).
  - cleared blockers: `M6P6-B2`, `M6P6-B3`, `M6P6-B4`.
- Next closure step:
  - execute `M6.G` (`P6` rollup + verdict) with `M6.E/M6.F` green authorities.
- `dev_min` remains closed and isolated under `../dev_min/`.
