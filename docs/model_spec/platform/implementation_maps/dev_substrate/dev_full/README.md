# Dev Full Track Maps
_As of 2026-02-26_

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
  - `M7` is `DONE`.
  - `M8` is `ACTIVE` (`M8.A` closed green).
- Active gate posture:
  - `M7.J` is closed green on authoritative managed run `m7q_m7_rollup_sync_20260226T031710Z` with `next_gate=M8_READY`.
  - `M7.K` throughput certification is closed green on `m7s_m7k_cert_20260226T000002Z`.
  - `M7` deep planning is split into:
    - `platform.M7.build_plan.md`,
    - `platform.M7.P8.build_plan.md`,
    - `platform.M7.P9.build_plan.md`,
    - `platform.M7.P10.build_plan.md`.
  - `M8` deep planning now exists in:
    - `platform.M8.build_plan.md`.
- Next closure step:
  - execute `M8.B` reporter runtime identity + lock readiness for `P11`.
- `dev_min` remains closed and isolated under `../dev_min/`.
