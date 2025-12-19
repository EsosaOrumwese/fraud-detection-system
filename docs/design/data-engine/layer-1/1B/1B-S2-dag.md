```
   LAYER 1 · SEGMENT 1B — STATE S2 (TILE WEIGHTS: DETERMINISTIC FIXED-DP WEIGHTS PER TILE)  [NO RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S1] Upstream S1 universe (required)
    - tile_index
        · path: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · PK: [country_iso, tile_id]
        · shape: schemas.1B.yaml#/prep/tile_index
        · one row per eligible tile (country_iso, tile_id) after clip.

[Ingress refs] Sealed references usable by S2 (S2 is ingress+S1-only)
    - iso3166_canonical_2024        (ISO-2 FK domain for country_iso)
    - world_countries               (country polygons; optional validation use)
    - population_raster_2025        (COG raster; used only when basis="population")

[Schema+Dict] Shape / catalogue anchors
    - schemas.1B.yaml               (shape authority for tile_index and tile_weights)
    - schemas.ingress.layer1.yaml   (shape authority for ingress refs)
    - dataset_dictionary.layer1.1B.yaml
        · ID→path/partition/sort/licence for tile_index, tile_weights
    - artefact_registry_1B.yaml
        · provenance for tile_index/tile_weights; notes on dependencies & write-once posture

[Config] Parameter-scoped config (no RNG)
    - parameter_hash   : hex64 (identity for S2 outputs)
    - basis            : "uniform" | "area_m2" | "population"
    - dp               : ℕ₀; fixed across the entire tile_weights partition
      (basis+dp are governed by parameter_hash and disclosed in the S2 run report.)

Gate posture (context)
    - S2 does NOT read 1A egress or S3 order surfaces (outlet_catalogue, s3_candidate_set).
    - S2 has NO `_passed.flag` of its own; acceptance is via schema + Dictionary + §8 + §11 PAT.


------------------------------------------------------------- DAG (S2.1–S2.5 · tile_index → masses → fixed-dp weights; no RNG)

[S1],
[Schema+Dict],
[Ingress refs]
      ->  (S2.1) Pre-read validation & allowed reads (no RNG)
             - Resolve tile_index via Dictionary:
                 * path family: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
                 * partitioning: [parameter_hash]; writer sort: [country_iso, tile_id]; format: parquet.
             - Enforce:
                 * materialised tile_index conforms to schemas.1B.yaml#/prep/tile_index.
                 * PK uniqueness for (country_iso, tile_id).
                 * country_iso ∈ iso3166_canonical_2024 (FK).
             - If tile_index missing, wrong partitioning/order, or schema-invalid:
                 * abort S2 with E101_TILE_INDEX_MISSING / E108_WRITER_HYGIENE (no outputs).
             - Allowed reads (once tile_index passes):
                 * tile_index
                 * iso3166_canonical_2024 (FK)
                 * world_countries (optional validations only)
                 * population_raster_2025 (only when basis="population")
             - Prohibitions:
                 * must NOT read 1A egress (outlet_catalogue, validation_bundle_1A, etc.).
                 * must NOT read s3_candidate_set or tz_world_2025a.
             - S2 remains RNG-free throughout.

[S1],
[Config],
[Ingress refs]
      ->  (S2.2) Mass assignment per tile (basis → m_i ≥ 0; no RNG)
             - For each tile i = (country_iso, tile_id) from tile_index:
                 * basis = "uniform"   → m_i := 1.
                 * basis = "area_m2"   → m_i := tile_index.pixel_area_m2(i).
                 * basis = "population"→ m_i := population_intensity(i) from population_raster_2025
                                         for the corresponding cell (NODATA ⇒ 0).
             - Constraints:
                 * All m_i must be finite and ≥ 0; any negative / non-finite mass ⇒ E105_NORMALIZATION.
                 * For basis="area_m2", MUST use tile_index.pixel_area_m2 (S1 is area authority).
                 * For basis="population", MUST read ONLY from population_raster_2025 (via Dictionary).
             - Do NOT introduce random noise or smoothing; S2 is strictly deterministic.

(S2.2),
[S1],
[Config]
      ->  (S2.3) Per-country normalisation & fixed-dp quantisation (no RNG)
             - For each ISO country c:
                 * Define U_c = { i ∈ tile_index | country_iso = c }.
                 * If |U_c| = 0 ⇒ abort S2 with E103_ZERO_COUNTRY.
             - Compute total mass:
                 * M_c = Σ_{i∈U_c} m_i.
             - Zero-mass fallback:
                 * If |U_c| > 0 and M_c = 0:
                     · apply deterministic uniform fallback: set m_i := 1 for all i ∈ U_c.
                     · recompute M_c; record zero_mass_fallback=true for c in the run report.
                     · if fallback is not applied in this situation ⇒ E104_ZERO_MASS.
             - Real weights:
                 * For M_c > 0, w_i = m_i / M_c defines a distribution over U_c.
             - Fixed-decimal quantisation:
                 * Single dp ∈ ℕ₀ for the entire run; K = 10^dp.
                 * For each i ∈ U_c:
                     · q_i = w_i * K
                     · z_i = floor(q_i)
                     · r_i = q_i − z_i ∈ [0,1)
                 * Shortfall S = K − Σ z_i (integer in [0, |U_c|)).
                 * Largest remainder rule:
                     · choose exactly S tiles with largest r_i;
                     · ties broken by ascending numeric tile_id;
                     · for selected tiles: weight_fp(i) = z_i + 1; others: weight_fp(i) = z_i.
             - Invariants per country c:
                 * Σ weight_fp(i) over U_c = 10^dp exactly.
                 * All countries share the same dp.
                 * No dependence between countries (each U_c processed independently).
             - No randomness: tie-break is deterministic via tile_id; results must be stable under parallelism.

(S2.3),
[S1],
[Schema+Dict],
[Config]
      ->  (S2.4) Materialise tile_weights (parameter-scoped; write-once; no RNG)
             - Dataset ID: tile_weights
             - Path & partition:
                 * data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/
                 * partitions: [parameter_hash]; writer sort: [country_iso, tile_id]; format: parquet.
             - Domain:
                 * one row per (country_iso, tile_id) in tile_index for this parameter_hash;
                 * no extras; no missing tiles.
             - Required columns (schema-owned semantics):
                 * country_iso        (ISO-2; FK to ingress ISO table)
                 * tile_id            (u64; matches tile_index tile_id)
                 * weight_fp          (fixed-decimal integer weight from S2.3)
                 * dp                 (same value for all rows; matches run-report dp)
                 * optional audit columns (e.g. real-valued weight, basis enum) are non-authoritative.
             - FK & coverage obligations:
                 * every (country_iso, tile_id) in tile_weights MUST appear in tile_index
                   for the same parameter_hash;
                 * per-country row counts MUST match tile_index (no merges/drops).
             - Determinism & immutability:
                 * for fixed inputs + parameter_hash, re-running S2 MUST produce a byte-identical
                   tile_weights partition (file order is non-authoritative).
                 * publishing is atomic (stage → fsync → atomic rename).
                 * any attempt to overwrite a non-empty partition with different bytes is a failure.

(S2.4),
[Config]
      ->  (S2.5) Run report, determinism receipt & acceptance posture (no RNG)
             - Produce S2 run report (JSON, control-plane; not a data-plane dataset):
                 * records parameter_hash, basis, dp, rows_emitted, countries_total,
                   zero_mass_fallback flags, PAT counters (CPU/IO/wall-clock), etc.
             - Per-country normalisation summaries:
                 * for each c: |U_c|, mass_sum, pre/post quant sums, residue allocations S, flags.
             - Determinism receipt:
                 * list all files under tile_weights/parameter_hash={parameter_hash}/ in ASCII-lex
                   relative-path order;
                 * concatenate bytes in that order; compute SHA-256; record {partition_path, sha256_hex}
                   in the run report.
             - Acceptance & gate posture:
                 * there is NO `_passed.flag` for S2; acceptance of tile_weights is via:
                     · schema conformance (#/prep/tile_weights),
                     · Dictionary/path law (path/partition/sort/licence/retention),
                     · §8 validation (FK, coverage, normalisation, exact sums, dp consistency),
                     · §11 PAT thresholds.
                 * consumers MUST NOT invent additional gate semantics around tile_weights.


State boundary (what S2 “owns”)
-------------------------------
- tile_weights   @ data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/
    * parameter-scoped, RNG-free, fixed-dp weights for every eligible tile in tile_index.
    * PK: [country_iso, tile_id]; partitions: [parameter_hash]; writer sort: [country_iso, tile_id].
    * sole persisted **weight surface** over the tile universe; S2 is weight authority.
- Control-plane artefacts (control/, not data-plane):
    * S2 run report (basis, dp, counts, PAT counters, determinism receipt ref).
    * Per-country normalisation summaries, including zero-mass fallback flags.
    * Determinism receipt: SHA-256 over tile_weights/partition contents (evidence, not a gate).


Downstream touchpoints
----------------------
- 1B.S3 (Country requirements):
    * uses tile_weights to sanity-check that every country with outlet_catalogue rows
      has coverage in the spatial prior; may rely on S2 invariants (fixed-dp, dp consistency).
- 1B.S4 (Tile allocation plan):
    * treats tile_weights as the sole authority for per-country tile weights;
      uses weight_fp and dp to integerise S3’s per-(merchant,country) counts into per-tile n_sites_tile.
- Any other consumer (e.g., diagnostics, scenario tuning):
    * may read tile_weights via Dictionary but MUST:
        · treat it as authoritative for spatial weights,
        · not recompute alternative weight surfaces for the same tiles,
        · respect that there is no S2 `_passed.flag` (rely instead on schema+Dictionary+§8+§11).
```