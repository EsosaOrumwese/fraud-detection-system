# Segment 1B - S5 Site→Tile Assignment Runbook

_Updated: 2025-10-23 (materialisation & validation)_

---

## 1. Scope
State 5 randomly assigns each site `(merchant_id, legal_country_iso, site_order)` to an eligible tile, respecting the integer quotas emitted by S4.

---

## 2. Status
- **Implementation:** Runner now materialises dataset + RNG logs + run report with determinism receipt; validator enforces quota/RNG/identity checks.
- **Outputs:** Dataset `s5_site_tile_assignment`, run report `s5_run_report`, RNG log stream `rng_event_site_tile_assign`.
- **RNG envelope:** `site_tile_assign` (one draw per site).

---

## 3. Next Steps
- Wire S5 into the segment orchestrator/CLI (run + validate) and refresh nightly automation to include the validator.
- Capture evidence bundle (dataset, RNG logs, run report) for governance review and update release notes accordingly.
- Extend regression coverage with end-to-end S0→S5 smoke once downstream S6 is available.
