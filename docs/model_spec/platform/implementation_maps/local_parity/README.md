# Platform Implementation Maps (local_parity baseline)
_As of 2026-02-10_

This folder preserves the **historical local-parity baseline** implementation maps and decision logs.
Active work for dev substrate promotion now lives under:
`docs/model_spec/platform/implementation_maps/dev_substrate/`.

## File naming
- One file per component: `{COMP}.impl_actual.md`
- One build plan per component: `{COMP}.build_plan.md`
- Examples:
  - `scenario_runner.impl_actual.md`
  - `ingestion_gate.impl_actual.md`
  - `event_bus.impl_actual.md`
  - `decision_fabric.impl_actual.md`
  - `action_layer.impl_actual.md`
  - `context_store_flow_binding.impl_actual.md`
  - `context_store_flow_binding.build_plan.md`

## Required discipline
- Append-only, never rewrite prior entries.
- Add a detailed plan **before** coding and log each decision as it happens.
- Reference the matching entry in `docs/logbook` with local time.
- For this baseline folder, prefer append-only routing continuity notes instead of new active-track design logs.

The data engine keeps its own implementation maps under:
`docs/model_spec/data-engine/implementation_maps/`.
