```
  LAYER 1 · SEGMENT 1B — STATE S4 (TILE ALLOCATION PLAN: n_sites_tile per merchant×country×tile)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S3] Per-merchant×country requirements (run-scoped; counts authority)
    - s3_requirements
        · path: data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · partitions: [seed, fingerprint, parameter_hash]
        · writer sort: [merchant_id, legal_country_iso]
        · PK: [merchant_id, legal_country_iso]
        · schema: schemas.1B.yaml#/plan/s3_requirements
        · semantics:
            * `n_sites` ≥ 1 per (merchant_id, legal_country_iso)
            * derived solely from outlet_catalogue; RNG-free

[S2+S1] Spatial prior & tile universe (parameter-scoped)
    - tile_weights
        · path: data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · schema: schemas.1B.yaml#/prep/tile_weights
        · semantics:
            * per-country fixed-dp integer weights: weight_fp, dp (K = 10^dp)
            * weight_fp ≥ 0; Σ weight_fp = K per country_iso
    - tile_index
        · path: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · schema: schemas.1B.yaml#/prep/tile_index
        · semantics:
            * authoritative list of eligible tiles per country_iso

[ISO] FK / domain authority
    - iso3166_canonical_2024
        · schema: schemas.ingress.layer1.yaml#/iso3166_canonical_2024
        · semantics:
            * canonical uppercase ISO-3166-1 alpha-2 codes

[Schema+Dict+Registry] Shape / path / provenance
    - schemas.1B.yaml
        · shapes for #/plan/s3_requirements, #/plan/s4_alloc_plan, #/prep/tile_weights, #/prep/tile_index
    - dataset_dictionary.layer1.1B.yaml
        · IDs → {path families, partitioning, writer sort} for s3_requirements, tile_weights, tile_index, s4_alloc_plan
    - artefact_registry_1B.yaml
        · dependency & licence metadata; notes that s4_alloc_plan depends on:
            s3_requirements, tile_weights, tile_index, iso3166_canonical_2024

[Context] Identity & posture
    - Identity triple: { seed, manifest_fingerprint, parameter_hash }
        · fixed for the entire S4 publish
    - S4 is strictly **RNG-free**:
        · no RNG events, no RNG logs, no dependence on random state
    - S4 does NOT read:
        · outlet_catalogue, s3_candidate_set, validation_bundle_1A, world_countries,
          population_raster_2025, tz_world_2025a


-------------------------------------------------------------- DAG (S4.1–S4.5 · s3_requirements + tile_weights → s4_alloc_plan; no RNG)

[S3],
[Schema+Dict],
[ISO]
      ->  (S4.1) Resolve s3_requirements & basic sanity (no RNG)
             - Resolve s3_requirements via Dictionary (no literal paths):
                 * path family:
                     data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
                 * partitions: [seed, fingerprint, parameter_hash]; writer sort: [merchant_id, legal_country_iso]
             - Schema + writer-hygiene checks:
                 * dataset conforms to schemas.1B.yaml#/plan/s3_requirements
                 * PK uniqueness on (merchant_id, legal_country_iso)
                 * legal_country_iso ∈ iso3166_canonical_2024 (FK)
                 * n_sites is integer ≥ 1 (no zero/negative counts)
             - Enforce identity discipline:
                 * all rows must embed the same (seed, manifest_fingerprint, parameter_hash) as the path tokens
                   if those columns are present; mismatches ⇒ hard failure.
             - Build domain:
                 * M = set of merchants with at least one row
                 * For each merchant m, C_m = set of legal_country_iso where S3 has n_sites(m,c)

[S2+S1],
[Schema+Dict],
[ISO]
      ->  (S4.2) Resolve tile_weights & tile_index; build per-country tile universes (no RNG)
             - Resolve tile_weights & tile_index via Dictionary:
                 * tile_weights:
                     · path: data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/
                     · partitions: [parameter_hash]; writer sort: [country_iso, tile_id]
                     · schema: #/prep/tile_weights
                 * tile_index:
                     · path: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
                     · partitions: [parameter_hash]; writer sort: [country_iso, tile_id]
                     · schema: #/prep/tile_index
             - Sanity checks:
                 * tile_weights & tile_index both FK country_iso against iso3166_canonical_2024
                 * dp is well-defined and constant per partition (and per country), K = 10^dp
                 * each (country_iso, tile_id) in tile_weights MUST appear in tile_index (FK)
             - Build per-country tile universes:
                 * For each country c:
                     · U_c := { tile_id | (c, tile_id) ∈ tile_index ∧ (c, tile_id) ∈ tile_weights }
                     · if U_c is empty but S3 has requirements in country c:
                         → impossible state ⇒ fail S4; (S3 should have caught country coverage vs tile_weights)
             - Do NOT inspect population_raster_2025 or world_countries here.

(S4.1),
(S4.2)
      ->  (S4.3) Per-merchant×country integer allocation over tiles (no RNG)
             - For each `(merchant_id = m, legal_country_iso = c, n_sites)` in s3_requirements:
                 * assert c ∈ iso3166_canonical_2024 (redundant FK safety)
                 * assert U_c (from S4.2) is non-empty; otherwise ⇒ structural failure.
             - Let K = 10^dp (dp from tile_weights for country c).
             - For each tile i ∈ U_c:
                 * read integer weight_fp[i] from tile_weights
             - Compute base allocations using integer arithmetic (with ≥128-bit intermediates):
                 * base_i = floor( n_sites * weight_fp[i] / K )
                 * B = Σ base_i
                 * if B > n_sites ⇒ overflow / logic error ⇒ fail S4
             - Compute residuals & shortfall:
                 * rnum_i = (n_sites * weight_fp[i]) mod K   (integer remainder)
                 * S = n_sites − B                           (how many +1 bumps remain)
                 * assert 0 ≤ S ≤ |U_c|; otherwise ⇒ failure
             - Largest remainder selection (per (m,c)):
                 * sort tiles in U_c by:
                     1. rnum_i descending
                     2. tile_id ascending (tie-breaker)
                 * let Top_S = first S tiles in this order
             - Final per-tile allocations:
                 * for each i ∈ U_c:
                     · n_sites_tile[i] = base_i + (1 if i ∈ Top_S else 0)
                 * invariants:
                     · Σ_{i∈U_c} n_sites_tile[i] = n_sites exactly
                     · n_sites_tile[i] ≥ 0 for all i
             - Zeros will not be emitted downstream; S4 only materialises rows where n_sites_tile[i] ≥ 1.
             - No RNG:
                 * all ordering (tie-break) is deterministic and based only on (rnum_i, tile_id).

(S4.3),
[Schema+Dict],
[Context]
      ->  (S4.4) Materialise s4_alloc_plan (per-tile quotas; write-once; no RNG)
             - Dataset ID: s4_alloc_plan
             - Path family via Dictionary:
                 * data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
             - Partitions: [seed, fingerprint, parameter_hash]
             - Writer sort: [merchant_id, legal_country_iso, tile_id]
             - Schema: schemas.1B.yaml#/plan/s4_alloc_plan
                 * PK: [merchant_id, legal_country_iso, tile_id]
                 * Columns:
                     · merchant_id      (id64)
                     · legal_country_iso (ISO2; FK)
                     · tile_id          (u64; FK to tile_index & tile_weights for same parameter_hash)
                     · n_sites_tile     (int ≥ 1)
             - Emit rows:
                 * for each (m,c), i ∈ U_c with n_sites_tile[i] ≥ 1:
                     · write row (m, c, i, n_sites_tile[i])
             - FK & coverage obligations:
                 * every (m,c) in s3_requirements:
                     · has at least one emitted row (sum n_sites_tile = n_sites)
                 * every (m,c,i) in s4_alloc_plan:
                     · (c,i) ∈ tile_index and ∈ tile_weights (FK to spatial prior)
             - Identity law:
                 * any embedded {seed, manifest_fingerprint, parameter_hash} fields must match path tokens
             - Immutability & determinism:
                 * partition for given identity is write-once; re-publish with different bytes ⇒ failure
                 * given fixed inputs, s4_alloc_plan is bit-for-bit deterministic (file order is non-authoritative).

(S4.4),
[Context]
      ->  (S4.5) Run report, determinism receipt & acceptance posture (control-plane; no RNG)
             - Produce s4_run_report (JSON; control/s4_alloc_plan/…/s4_run_report.json):
                 * identity: seed, manifest_fingerprint, parameter_hash
                 * counts:
                     · merchants_total
                     · countries_total
                     · tiles_total_distinct (across all (m,c))
                     · requirements_rows_total (from s3_requirements)
                     · alloc_rows_total (rows in s4_alloc_plan)
                 * allocation health:
                     · sum_check_pass = boolean (all Σ n_sites_tile == n_sites)
                     · fk_tile_violations_count (expected 0)
                     · overflow_events_count (expected 0)
                 * PAT counters:
                     · cpu_seconds_total, wall_clock_seconds_total
                     · bytes_read_s3_requirements, bytes_read_tile_weights, bytes_read_tile_index
                     · bytes_written_s4_alloc_plan
             - Determinism receipt:
                 * enumerate all files in the s4_alloc_plan partition as relative paths
                   (ASCII-lex sorted);
                 * concatenate bytes in that order; compute SHA-256; store hex64 digest + partition_path
                   under e.g. `determinism_receipt` in the run report.
             - Acceptance posture (no `_passed.flag` for S4):
                 * s4_alloc_plan is considered valid if:
                     · schema & Dictionary/path rules hold,
                     · all FK & sum invariants pass (per (m,c)),
                     · determinism check passes (identical recompilation),
                     · PAT constraints satisfied.
                 * downstream consumers rely on these rules; they MUST NOT attach extra, hidden gate semantics.


State boundary (what S4 “owns”)
-------------------------------
- s4_alloc_plan  @ data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
    * PK: [merchant_id, legal_country_iso, tile_id]
    * partitions: [seed, fingerprint, parameter_hash]
    * writer sort: [merchant_id, legal_country_iso, tile_id]
    * semantics:
        · per-merchant×country integer allocations over tiles:
            n_sites_tile(m,c,i) ≥ 1 where emitted;
        · for each (m,c), Σ_i n_sites_tile(m,c,i) = n_sites(m,c) from s3_requirements;
        · allocations respect S2 tile_weights (weight_fp, dp) and S1 tile_index universe; no RNG.
- s4_run_report  (control-plane)
    * JSON summary for this identity triple, including determinism receipt and health counters;
    * used by operators/validators, not by data-plane code.


Downstream touchpoints
----------------------
- 1B.S5 (Site→tile assignment; RNG state)
    * treats s4_alloc_plan as **hard quotas**:
         · for each (m,c,i), exactly n_sites_tile(m,c,i) sites must be assigned to tile i;
    * S5 uses RNG to map concrete `(merchant, country, site_order)` to tiles, but MUST respect the
      counts in s4_alloc_plan per (m,c,i).
- 1B.S6 / S7 (jitter & synthesis)
    * indirectly depend on S4 via S5: the spatial spread of outlets is shaped by s4_alloc_plan
      through S5’s random assignment and S6 jitter.
- Any analytics/diagnostics:
    * may use s4_alloc_plan to compare merchant-level outlet distributions against spatial priors,
      but MUST NOT re-invent per-tile integerisation for the same identity; S4 is the allocation authority.
```