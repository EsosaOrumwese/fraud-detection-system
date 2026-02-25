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
  - `M6` is `DONE`.
  - `M7` is `ACTIVE`.
- Active gate posture:
  - `M6.J` is closed green on authoritative remote run `m6j_m6_closure_sync_20260225T194637Z` (GitHub Actions run `22413131251` on `migrate-dev`).
  - `M7` deep planning is now split into:
    - `platform.M7.build_plan.md`,
    - `platform.M7.P8.build_plan.md`,
    - `platform.M7.P9.build_plan.md`,
    - `platform.M7.P10.build_plan.md`.
- Next closure step:
  - execute `M7.A` handle/entry closure and begin component-level `P8` execution.
- `dev_min` remains closed and isolated under `../dev_min/`.
