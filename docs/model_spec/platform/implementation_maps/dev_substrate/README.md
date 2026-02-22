# Dev Substrate Track Maps
_As of 2026-02-22_

**FRESH START RESET:** this folder is now the authoritative planning notebook for a clean `local_parity -> dev` migration run from scratch. Prior dev_substrate implementation attempts are historical context only and must not be adapted forward.

## Track status
- `local_parity -> dev_min` migration track is closed with certification verdict `ADVANCE_CERTIFIED_DEV_MIN`.
- See `platform.migration_wrap_up.md` for closure anchors.

## Active maps
- `platform.build_plan.md`
- `platform.impl_actual.md`
- `platform.migration_wrap_up.md`
- `platform.M0.build_plan.md` (deep-plan detail for closed phase M0)
- `platform.M1.build_plan.md` (deep-plan detail for active phase M1)

## Phase deep-plan pattern
- `platform.M*.build_plan.md` stores deep planning for individual phases.
- Status ownership remains in `platform.build_plan.md` only.
- Create new phase deep-plan files when phase activation is approved.

## Working authority for migration execution
- `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
- `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

## Rule
- Do not recreate legacy dev_substrate wiring from memory or from removed files.
- Phase-entry decisions must follow the migration runbook + handles registry and be logged in `platform.impl_actual.md`.
