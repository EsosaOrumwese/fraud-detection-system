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
  - `M8` is `DONE` (`M8.A..M8.J` closed green).
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
  - `M9.A` closed green for `P12` authority/handle closure.
  - `M9.B` closed green for handoff continuity and run-scope lock.
  - `M9.C` closed green for replay-basis receipt closure.
  - `M9.D` closed green for as-of + maturity policy closure.
  - `M9.E` closed green for leakage guardrail evaluation.
  - `M9.F` closed green for runtime-vs-learning surface separation.
  - `M9.G` closed green for learning-input readiness snapshot publication.
  - `M9.H` closed green for deterministic P12 verdict + M10 handoff publication.
  - `M9.I` closed green for phase budget + cost-outcome closure.
  - `M9.J` closed green for full M9 closure sync.
  - next active step is `M10.A` authority + handle closure.
- `dev_min` remains closed and isolated under `../dev_min/`.
