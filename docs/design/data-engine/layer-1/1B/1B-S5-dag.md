```
   LAYER 1 · SEGMENT 1B — STATE S5 (SITE→TILE ASSIGNMENT FROM S4 QUOTAS)  [RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S4] Per-tile quotas (run-scoped, RNG-free counts authority)
    - s4_alloc_plan
        · path: data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · partitions: [seed, fingerprint, parameter_hash]
        · writer sort: [merchant_id, legal_country_iso, tile_id]
        · schema: schemas.1B.yaml#/plan/s4_alloc_plan
        · semantics:
            * n_sites_tile ≥ 1 per (merchant_id, legal_country_iso, tile_id)
            * Σ_tile n_sites_tile(m,c,·) = S3 n_sites(m,c)         (per identity triple)
            * per-tile allocations respect S2 tile_weights and S1 tile_index universe 

[S1] Tile universe (parameter-scoped)
    - tile_index
        · path: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · schema: schemas.1B.yaml#/prep/tile_index
        · semantics:
            * authoritative list of eligible tiles per country_iso
            * FK target for (legal_country_iso, tile_id) in downstream datasets 

[ISO] FK / domain authority
    - iso3166_canonical_2024
        · schema: schemas.ingress.layer1.yaml#/iso3166_canonical_2024
        · semantics:
            * canonical uppercase ISO-3166-1 alpha-2 codes; FK target for legal_country_iso 

[Gate] 1B gate receipt (context; no direct I/O)
    - s0_gate_receipt_1B
        · proves 1A PASS for manifest_fingerprint and enumerates sealed inputs 1B may use
        · S5 relies on this gate; it does NOT re-hash the 1A bundle. 

[Schema+Dict+Registry] Shape / paths / provenance / RNG envelope
    - schemas.1B.yaml
        · shape for #/plan/s4_alloc_plan, #/prep/tile_index, #/plan/s5_site_tile_assignment
    - schemas.layer1.yaml
        · RNG envelope anchor: #/rng/events/site_tile_assign
    - dataset_dictionary.layer1.1B.yaml
        · IDs → {path families, partitioning, writer sort} for s4_alloc_plan, tile_index, s5_site_tile_assignment, s5_run_report
    - artefact_registry_1B.yaml
        · dependencies and roles for s5_site_tile_assignment and rng_event_site_tile_assign
        · notes on partitioning, write-once posture, and RNG roles 

[Context] Identity & RNG posture
    - Dataset identity triple: { seed, manifest_fingerprint, parameter_hash }
        · fixed for entire S5 publish; mixing identities is forbidden.
    - RNG logs identity: { seed, parameter_hash, run_id }
        · single run_id per S5 publish; shared across all site_tile_assign events.
    - RNG substream:
        · site_tile_assign events; exactly ONE event per output row (per site). 

Prohibited surfaces for S5 (fail-closed for assignment logic)
    - MUST NOT read: world_countries, population_raster_2025, tz_world_2025a, outlet_catalogue,
      s3_requirements, s3_candidate_set, tile_weights, validation_bundle_1A, or any surface not listed in §3.1. 


------------------------------------------------------------------ DAG (S5.1–S5.6 · quotas → RNG permute → assignment; RNG-bound)

[S4],
[Schema+Dict],
[ISO]
      ->  (S5.1) Resolve s4_alloc_plan & sanity checks (no RNG yet)
             - Resolve s4_alloc_plan path via Dictionary (no literal paths):
                 * data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
                 * partitions: [seed, fingerprint, parameter_hash]; writer sort: [merchant_id, legal_country_iso, tile_id]
             - Validate against schemas.1B.yaml#/plan/s4_alloc_plan:
                 * PK uniqueness on (merchant_id, legal_country_iso, tile_id)
                 * n_sites_tile integer ≥ 1
                 * legal_country_iso ∈ iso3166_canonical_2024 (FK)
             - Identity discipline:
                 * all rows must share the same {seed, manifest_fingerprint, parameter_hash} as path tokens
                   (where embedded); mismatches ⇒ hard failure.
             - Build S4 frame:
                 * For each pair (m,c) = (merchant_id, legal_country_iso):
                     · collect rows (tile_id, n_sites_tile)
                     · compute N(m,c) = Σ_tile n_sites_tile(m,c,tile)
                     · assert N(m,c) ≥ 1
             - S4 remains sole authority for `n_sites_tile`; S5 MUST NOT alter these counts. 

[S1],
[Schema+Dict],
[ISO]
      ->  (S5.2) Resolve tile_index & per-country tile universe (no RNG)
             - Resolve tile_index via Dictionary:
                 * data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
                 * partitions: [parameter_hash]; writer sort: [country_iso, tile_id]
             - Validate against schemas.1B.yaml#/prep/tile_index:
                 * PK uniqueness on (country_iso, tile_id)
                 * country_iso ∈ iso3166_canonical_2024 (FK)
             - Build per-country tile sets:
                 * U_c = { tile_id | (country_iso=c, tile_id) exists in tile_index }
             - FK check vs S4:
                 * for each row (m,c,tile_id) in s4_alloc_plan, assert (c,tile_id) ∈ U_c; otherwise fail.
             - Note: S5 does not inspect geometry; it only checks tile membership.

(S5.1),
(S5.2),
[Context]
      ->  (S5.3) Per-merchant×country setup: site list & tile multiset (no RNG)
             - For each pair (m,c) with N(m,c) from S4:
                 * Site list S(m,c) := [1,2,…,N(m,c)]  (site_order domain for this pair)
                 * Tile multiset T(m,c):
                     · for each tile_id in ascending numeric order:
                           repeat tile_id exactly n_sites_tile(m,c,tile_id) times
                     · concatenating these runs yields:
                           T(m,c) = [tile₁, …, tile₁, tile₂, …, tile₂, …]   (each repeated count times)
             - Invariants:
                 * |S(m,c)| = N(m,c) = Σ n_sites_tile(m,c,·)
                 * |T(m,c)| = N(m,c)
             - No RNG used yet; this is pure deterministic expansion of S4 quotas.

(S5.3),
[Context]
      ->  (S5.4) RNG draws & permutation of sites (RNG-bound: site_tile_assign)
             - For each pair (m,c), for each site_order s ∈ S(m,c):
                 * draw one uniform u_s ∈ (0,1) from the `site_tile_assign` substream:
                     · RNG event logged under:
                           logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
                     · event MUST validate against schemas.layer1.yaml#/rng/events/site_tile_assign
                     · envelope: exactly 1 draw per event; exactly 1 event per site. 
             - Define permutation S_perm(m,c):
                 * sort S(m,c) by key (u_s ascending, site_order ascending)
                 * tie-break deterministic via site_order; no further randomness.
             - RNG budget law (binding):
                 * total number of site_tile_assign events MUST equal total number of output rows
                   in s5_site_tile_assignment (one event per site).
             - Determinism posture:
                 * for fixed {seed, manifest_fingerprint, parameter_hash, run_id} and same S4 inputs,
                   replaying S5 MUST produce the same u_s sequence, S_perm(m,c), and thus same assignments.

(S5.3),
(S5.4),
[Context]
      ->  (S5.5) Quota-exact pairing of sites to tiles (assignment; RNG already sampled)
             - For each pair (m,c):
                 * Let S_perm(m,c) = [s₁, s₂, …, s_N] (permuted site_orders)
                 * Let T(m,c) = [t₁, t₂, …, t_N] (tile multiset from S4; ordered by tile_id)
             - Pair them positionally:
                 * for j = 1..N(m,c):
                       assign site_order = sⱼ → tile_id = tⱼ
             - Invariants (per (m,c)):
                 * each site_order ∈ [1..N(m,c)] appears in exactly one assignment row
                 * for each tile_id:
                       # { assignments with tile_id } = n_sites_tile(m,c,tile_id) from S4
                 * Σ_tile assignments = N(m,c) (no loss, no duplication)
             - No additional RNG is used here; behaviour is deterministic given S4 quotas + u_s.

(S5.5),
[Schema+Dict],
[ISO],
[Context]
      ->  (S5.6) Materialise s5_site_tile_assignment & run report (dataset + control-plane)
             - Dataset ID: s5_site_tile_assignment
             - Path (via Dictionary):
                 * data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
             - Partitions: [seed, fingerprint, parameter_hash]
             - Writer sort: [merchant_id, legal_country_iso, site_order]
             - Schema: schemas.1B.yaml#/plan/s5_site_tile_assignment
                 * PK: [merchant_id, legal_country_iso, site_order]
                 * Columns: merchant_id, legal_country_iso, site_order, tile_id
                 * FK:
                     · legal_country_iso → iso3166_canonical_2024
                     · (legal_country_iso, tile_id) → tile_index (same parameter_hash) 
             - Emit rows:
                 * for each assignment (m,c, site_order, tile_id_assigned) from S5.5:
                       write one row; no extra/placeholder rows.
             - PK & coverage checks:
                 * each (m,c, site_order) appears exactly once; no gaps/duplicates (site_order domain 1..N(m,c))
                 * per (m,c, tile_id), the count of rows equals S4 n_sites_tile(m,c,tile_id)
             - Identity & immutability:
                 * this partition is write-once for the identity; re-publish must be byte-identical
                 * where lineage fields exist, they MUST match {seed, manifest_fingerprint, parameter_hash}
             - Control-plane: s5_run_report
                 * path: control/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_run_report.json
                 * schema: schemas.1B.yaml#/control/s5_run_report
                 * contains:
                     · identity triple, run_id
                     · rows_total, merchants_total, pairs_total
                     · quotas_satisfied (boolean), fk_tile_violations_count, pk_violations_count
                     · rng_event_count (must equal rows_total)
                     · PAT counters (IO/CPU/wall-clock)
                     · determinism_receipt: SHA-256 over partition files (ASCII-lex path order) 


State boundary (what S5 “owns”)
-------------------------------
- s5_site_tile_assignment
    * One row per site (merchant_id, legal_country_iso, site_order) under {seed, fingerprint, parameter_hash}.
    * PK: [merchant_id, legal_country_iso, site_order]
    * Partition keys: [seed, fingerprint, parameter_hash]
    * Sort keys: [merchant_id, legal_country_iso, site_order]
    * Semantics:
        · site→tile assignment consistent with S4 quotas:
            for each (m,c,tile_id), count(rows) == n_sites_tile from s4_alloc_plan;
        · every assigned (legal_country_iso, tile_id) exists in tile_index for this parameter_hash;
        · RNG used only to randomise which sites take which tile slots, not the counts themselves.

- rng_event_site_tile_assign
    * Path: logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
    * Exactly one RNG event per row in s5_site_tile_assignment for this publish.
    * Schema: schemas.layer1.yaml#/rng/events/site_tile_assign
    * Identity: {seed, parameter_hash, run_id} shared across all S5 events.

- s5_run_report (control-plane)
    * JSON summary & determinism receipt for this S5 publish;
    * non-data-plane, but binding for presence and for RNG budget / health checks.


Downstream touchpoints
----------------------
- 1B.S6 (Site jitter; RNG state)
    * Consumes s5_site_tile_assignment and tile_index (plus world_countries, ISO):
        · per site, S6 uses the assigned tile_id as the base cell for in-pixel jitter;
        · S6 MUST NOT change which tile a site belongs to; it only produces deltas. 
- 1B.S7 (Site synthesis; RNG-free)
    * Consumes s5_site_tile_assignment + s6_site_jitter + tile_bounds:
        · reconstructs absolute coordinates per site;
        · enforces 1:1 coverage with 1A outlet_catalogue via S0 gate. 
- 1B validation bundle (S9)
    * Uses s5_site_tile_assignment and rng_event_site_tile_assign to:
        · verify per-site PK coverage,
        · confirm S4 quotas are honoured,
        · reconcile RNG budgets (rows vs events) for the `site_tile_assign` substream. 
```