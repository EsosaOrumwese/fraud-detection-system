# segment_1B.impl_actual.md

Append-only implementation planning log for Segment 1B. Each entry documents the
design element, a short summary of the problem, and the detailed plan to resolve
it. Do not delete prior entries.

---

## S0 - Gate-in & Foundations (S0.*)

### Entry: 2026-01-12 20:01

Design element: Segment 1B readiness (expanded spec + contract review)
Summary: Begin 1B with a full read of S0–S9 expanded specs plus 1B contracts to identify gates, sealed inputs (including population raster/HRSL), and any S0 gate-in constraints that affect downstream states.

Plan (before implementation):
1) **Read all 1B expanded state specs in order (S0–S9).**
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s0.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s1.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s2.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s3.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s4.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s5.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s6.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s7.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s8.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s9.expanded.md`

2) **Review 1B contract authorities and registry.**
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
   - Confirm all `$ref` anchors for 1B tables and validation bundle shapes.

3) **Identify sealed inputs and external data risk.**
   - Pay special attention to population raster / HRSL‑style inputs and world polygons.
   - Verify which S0‑sealed inputs are fingerprint-scoped vs parameter-scoped so parameter_hash changes do not silently invalidate upstream references.

4) **Record a detailed pre‑implementation plan per state.**
   - After reading, add a detailed entry under each state section with the planned data flow, gates, RNG envelope rules, writer sort, and failure posture.

### Entry: 2026-01-12 20:27

Design element: S0 sealed-input availability check (pre-implementation)
Summary: Verified that the sealed reference inputs listed in the 1B dictionary are present locally so S0 can seal them without blocking on missing assets.

Verified paths:
- `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
- `reference/spatial/world_countries/2024/world_countries.parquet`
- `reference/spatial/population/2025/population.tif` (population raster / HRSL‑style prior)
- `reference/spatial/tz_world/2025a/tz_world.parquet`

---

## S1 - Tile Universe (S1.*)

## S2 - Tile Weights (S2.*)

## S3 - Requirements (S3.*)

## S4 - Allocation Plan (S4.*)

## S5 - Site-to-Tile Assignment RNG (S5.*)

## S6 - In-Cell Jitter RNG (S6.*)

## S7 - Site Synthesis (S7.*)

## S8 - Egress Site Locations (S8.*)

## S9 - Validation Bundle & Gate (S9.*)
