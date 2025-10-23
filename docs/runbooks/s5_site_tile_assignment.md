# Segment 1B - S5 Site→Tile Assignment Runbook

_Updated: 2025-10-23 (scaffolding)_

---

## 1. Scope
State 5 randomly assigns each site `(merchant_id, legal_country_iso, site_order)` to an eligible tile, respecting the integer quotas emitted by S4.

---

## 2. Status
- **Implementation:** In progress (Phase 1 scaffolding complete; logic to follow).
- **Outputs:** Planned dataset `s5_site_tile_assignment` and run report `s5_run_report` (see dictionary).
- **RNG envelope:** `site_tile_assign` (one draw per site).

---

## 3. Next Steps
- Implement loaders, RNG kernel, and validator per `docs/model_spec/data-engine/specs/state-flow/1B/state.1B.s5.expanded.md`.
- Update this runbook with execution/validation commands once the state is functional.
