# Layer-1 - Segment 1B - State Overview (S0-S9)

Segment 1B makes 1A's outlet stubs real in space. It verifies the 1A gate, tiles the world, assigns sites to tiles with RNG evidence, jitters them to coordinates, and publishes `site_locations`. Inter-country order remains solely on 1A's `s3_candidate_set.candidate_rank` (home=0). Egress is gated by `_passed.flag_1B` under `[seed, fingerprint]`.

## Segment role at a glance
- Enforce "no PASS -> no read" on 1A before any 1B work; seal which inputs are allowed.
- Build the deterministic tile universe (`tile_index`, `tile_bounds`) and fixed-dp tile weights (`tile_weights`).
- Derive per-merchant x country site counts (`s3_requirements`), integerise them over tiles (`s4_alloc_plan`).
- RNG: assign each site to a tile (`site_tile_assign`) and jitter within the tile (`in_cell_jitter`) with full budgets in logs.
- Synthesize per-site rows and publish order-free spatial egress `site_locations` plus the `_passed.flag_1B` gate.

---

## S0 - Gate-in & foundations (RNG-free)
**Purpose & scope**  
Verify 1A's `_passed.flag` for the target `manifest_fingerprint` (hash = SHA-256 over `validation_bundle_1A/index.json` entries in ASCII-lex order) before any 1B read; seal the list of inputs 1B may access.

**Preconditions & gates**  
`validation_bundle_1A` + `_passed.flag` must match for the fingerprint; otherwise abort ("no PASS -> no read").

**Inputs**  
`validation_bundle_1A`, `_passed.flag_1A`; ingress refs listed in `sealed_inputs_1B` (ISO, countries, population raster, TZ polygons); 1A egress `outlet_catalogue` (order-free).

**Outputs & identity**  
`s0_gate_receipt_1B` at `data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_1B` inventory for the same fingerprint.

**RNG**  
None.

**Key invariants**  
Gate must pass before any 1B dataset read; `sealed_inputs_1B` is the whitelist; path tokens equal embedded lineage where present.

**Downstream consumers**  
All 1B states rely on the receipt to read `outlet_catalogue` and refs; S9 replays the gate hash.

---

## S1 - Tile index (eligible cells per country)
**Purpose & scope**  
Enumerate eligible raster tiles per country; RNG-free geometry setup.

**Preconditions & gates**  
S0 receipt present; ingress refs available.

**Inputs**  
`population_raster_2025`, `world_countries`, `iso3166_canonical_2024`.

**Outputs & identity**  
`tile_index` and `tile_bounds` (parameter-scoped) under `parameter_hash={parameter_hash}`; PK `(country_iso, tile_id)`.

**RNG**  
None.

**Key invariants**  
Each tile is within exactly one country polygon; tile IDs stable for a fixed `parameter_hash`.

**Downstream consumers**  
S2 weights, S4 integer plan, S5 assignment, S6 jitter read `tile_index`/`tile_bounds`.

---

## S2 - Tile weights (deterministic)
**Purpose & scope**  
Compute fixed-dp tile weights per country (basis: policy over population/area/etc.); RNG-free.

**Preconditions & gates**  
S1 PASS; weighting policy available.

**Inputs**  
`tile_index`, ingress ISO/polygon surfaces as needed by policy.

**Outputs & identity**  
`tile_weights` at `data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/`, writer sort `[country_iso, tile_id]`; dp and basis recorded in run report.

**RNG**  
None.

**Key invariants**  
Per-country weights sum exactly to `10^dp`; no negative weights; only tiles from `tile_index`.

**Downstream consumers**  
S3 coverage check, S4 integer allocation; S9 re-derives sums.

---

## S3 - Country requirements frame
**Purpose & scope**  
Count sites per `(merchant_id, legal_country_iso)` from 1A `outlet_catalogue`; RNG-free.

**Preconditions & gates**  
S0 gate PASS; `outlet_catalogue` accessible for the fingerprint; `tile_weights` present for coverage check.

**Inputs**  
`outlet_catalogue` `[seed, fingerprint]`, `tile_weights`, `iso3166_canonical_2024`.

**Outputs & identity**  
`s3_requirements` at `data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`, PK `[merchant_id, legal_country_iso]`.

**RNG**  
None.

**Key invariants**  
Counts match `outlet_catalogue`; every `(merchant, country)` exists in `tile_weights` for the parameter hash; inter-country order not encoded.

**Downstream consumers**  
S4 uses counts; S5/S7 parity checks; S9 reconciles counts vs egress.

---

## S4 - Tile allocation plan (integer)
**Purpose & scope**  
Integerise each `(merchant, country)` count over eligible tiles using S2 weights; RNG-free.

**Preconditions & gates**  
S1-S3 PASS; tile universe and weights loaded; gate receipt verified.

**Inputs**  
`s3_requirements`, `tile_weights`, `tile_index`, `iso3166_canonical_2024`.

**Outputs & identity**  
`s4_alloc_plan` at `data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`, writer sort `[merchant_id, legal_country_iso, tile_id]`; run report `s4_run_report`.

**RNG**  
None.

**Key invariants**  
For each `(merchant, country)`, sum `n_sites_tile` = `n_sites`; allocations only to tiles in `tile_index`; drop zero rows.

**Downstream consumers**  
S5 uses per-tile quotas; S9 replays integerisation (floors + residual bumps).

---

## S5 - Site->tile assignment (RNG)
**Purpose & scope**  
Assign each site stub to exactly one tile, satisfying S4 quotas; RNG evidences the selection.

**Preconditions & gates**  
S0-S4 PASS; identities `{seed, manifest_fingerprint, parameter_hash}` fixed.

**Inputs**  
`s4_alloc_plan`, `tile_index`, `iso3166_canonical_2024` (optional `s3_requirements` for diagnostics).

**Outputs & identity**  
`s5_site_tile_assignment` at `data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`, writer sort `[merchant_id, legal_country_iso, site_order]`; `s5_run_report`.  
RNG events: `rng_event_site_tile_assign` under `logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

**RNG posture**  
Exactly one U(0,1) draw per site; single `run_id` for the publish; envelope counters reconciled in trace.

**Key invariants**  
Each site appears once; per-tile counts match `s4_alloc_plan`; one RNG event per site with budgets logged.

**Downstream consumers**  
S6 jitter reads assignments; S7 synthesis joins assignments; S9 checks quotas vs events.

---

## S6 - In-cell jitter (RNG)
**Purpose & scope**  
Jitter each assigned site to a `(lat, lon)` inside its tile and country; bounded resampling.

**Preconditions & gates**  
S1, S5 PASS; geometry refs available.

**Inputs**  
`s5_site_tile_assignment`, `tile_bounds`/`tile_index`, `world_countries`, `iso3166_canonical_2024`.

**Outputs & identity**  
`s6_site_jitter` at `data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`; `s6_run_report`.  
RNG events: `rng_event_in_cell_jitter` under `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

**RNG posture**  
Per attempt: one event with `draws="2"`, `blocks=1`; >=1 event per site; capped attempts.

**Key invariants**  
Final point lies in the tile pixel and country polygon; attempts within cap; budgets match trace; no change to tile membership.

**Downstream consumers**  
S7 synthesis; S9 replays jitter envelopes and point-in-country checks.

---

## S7 - Site synthesis (deterministic)
**Purpose & scope**  
Combine assignments, jitter, tile geometry, and outlet identity into per-site rows with coordinates; RNG-free.

**Preconditions & gates**  
S5, S6 PASS; `outlet_catalogue` available; geometry from S1.

**Inputs**  
`s5_site_tile_assignment`, `s6_site_jitter`, `tile_index`/`tile_bounds`, `outlet_catalogue`.

**Outputs & identity**  
`s7_site_synthesis` at `data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`, writer sort `[merchant_id, legal_country_iso, site_order]`; `s7_run_summary`.

**RNG posture**  
None (all randomness already captured in S5/S6 events).

**Key invariants**  
1:1 with `outlet_catalogue`; FK to assignments and tile universe; coordinates match jitter results; no duplicates or gaps.

**Downstream consumers**  
S8 egress; S9 structural and cross-state parity checks.

---

## S8 - Egress `site_locations` (deterministic publish)
**Purpose & scope**  
Publish final spatial egress; order-free, partitioned by `[seed, fingerprint]`.

**Preconditions & gates**  
S7 PASS; schema/dictionary anchors fixed; gate law continues ("no PASS -> no read").

**Inputs**  
`s7_site_synthesis` (and summaries).

**Outputs & identity**  
`site_locations` at `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/`, PK `(merchant_id, legal_country_iso, site_order)`; `s8_run_summary`.

**RNG posture**  
None.

**Key invariants**  
Order-free; lineage columns equal path tokens; `parameter_hash` implied via provenance, not a partition; immutable after publish.

**Downstream consumers**  
Later layers read only after `_passed.flag_1B`; S9 hashes egress for the bundle.

---

## S9 - Validation bundle & PASS gate
**Purpose & scope**  
Validate S1-S8 outputs and RNG evidence; publish `validation_bundle_1B/` and `_passed.flag_1B` (SHA-256 over bundle files in ASCII-lex order, flag excluded).

**Preconditions & gates**  
All prior states complete; RNG logs/events available: `rng_audit_log`, `rng_trace_log`, `rng_event_site_tile_assign`, `rng_event_in_cell_jitter`.

**Inputs**  
All 1B datasets (`tile_index`, `tile_bounds`, `tile_weights`, `s3_requirements`, `s4_alloc_plan`, `s5_site_tile_assignment`, `s6_site_jitter`, `s7_site_synthesis`, `site_locations`) and RNG evidence.

**Outputs & identity**  
`validation_bundle_1B` at `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/`; `_passed.flag_1B` alongside it; gate text mirrors 1A ("no PASS -> no read").

**RNG posture**  
None; validator replays and reconciles budgets from events and trace.

**Key invariants**  
Schema and partition conformance for all datasets; RNG budgets close (S5 one event/site, S6 >=1 event/site with `draws="2"` and `blocks=1` per event); counts and coverage match across states; bundle digest equals `_passed.flag_1B`.

**Downstream consumers**  
All downstream segments must verify `_passed.flag_1B` before reading `site_locations` or any 1B artefact.
