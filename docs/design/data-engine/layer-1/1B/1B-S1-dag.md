```
          LAYER 1 · SEGMENT 1B — STATE S1 (TILE INDEX: ELIGIBLE CELLS PER COUNTRY)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[Refs] Sealed ingress surfaces (from 1B Dictionary; S1-only)
    - iso3166_canonical_2024
        · FK domain for `country_iso` (ISO-2, uppercase).
    - world_countries
        · Country polygons (multipolygons with holes) in WGS84; point-in-country authority.
    - population_raster_2025
        · Global population raster (COG GeoTIFF); source of **grid geometry** (nrows, ncols, geotransform).
        · Values (population) are **ignored** for S1 decisions; used only to define the grid.

[Schema+Dict] Shape & catalogue anchors
    - schemas.ingress.layer1.yaml
        · anchors for iso3166_canonical_2024, world_countries, population_raster_2025.
    - schemas.1B.yaml
        · anchors for `prep/tile_index` and companion `prep/tile_bounds`.
    - dataset_dictionary.layer1.1B.yaml
        · entries for `tile_index` and `tile_bounds` (ID → path/partition/order/schema).
    - artefact_registry_1B.yaml
        · provenance/licence for ingress; **no gates** for S1 outputs.

Gate posture for S1 (context)
    - S1 does **not** read any 1A egress (`outlet_catalogue`, `s3_candidate_set`).
    - S0’s “No PASS → No read” applies to 1A readers, but **S1 is ingress-only**.
    - `tile_index` / `tile_bounds` have **no `_passed.flag` gate**; consumers rely on schema + Dictionary only.


------------------------------------------------------------- DAG (S1.1–S1.5 · grid → eligibility → tile_index/tile_bounds; no RNG)

[Refs],
[Schema+Dict]
          ->  (S1.1) Raster grid interpretation & tile identity (no RNG)
                 - Read `population_raster_2025` as a COG:
                     * extract `nrows`, `ncols`, geotransform in WGS84.
                 - Define indexing convention:
                     * rows, cols zero-based; grid is row-major (top→bottom, left→right).
                 - Define **tile identity**:
                     * for cell `(r, c)` in grid with `ncols`, `tile_id = r * ncols + c` (u64).
                     * any change to this formula is a **MAJOR** contract break for S1.
                 - Compute centroids:
                     * `centroid_lon, centroid_lat` = cell centre in lon/lat, derived from geotransform.
                     * enforce bounds: lon ∈ [−180,+180], lat ∈ [−90,+90].
                 - Compute pixel area:
                     * `pixel_area_m2` = ellipsoidal area of the cell footprint in metres².
                     * must be strictly > 0; non-positive area is a hard failure.
                 - No RNG: all of this is pure arithmetic off the sealed raster geometry.

[Refs]    ->  (S1.2) Eligibility predicate per country (no RNG)
                 - For each ISO country in `iso3166_canonical_2024`:
                     * read corresponding polygon(s) from `world_countries`.
                     * enforce:
                         · polygons in WGS84,
                         · interior rings are **holes** (subtract area),
                         · antimeridian-aware: polygons crossing ±180° treated as seamless.
                     * if geometry invalid/unrepairable → `E001_GEO_INVALID` → fail S1.
                 - Choose predicate (from config) for this run:
                     * `"center"` (default):
                         · include cell if centroid is inside or on the country boundary,
                           excluding holes (centroid in hole ⇒ exclude).
                     * `"any_overlap"`:
                         · include cell if polygon ∩ cell has strictly **positive area**
                           (edge/point contact alone does **not** qualify).
                 - For each cell `(r,c)`:
                     * evaluate predicate against each country’s polygons → membership decision.
                 - Record which predicate was used (e.g. `"center"` vs `"any_overlap"`) for the run:
                     * stored in `inclusion_rule` column or companion metadata.

(S1.1),
(S1.2)   ->  (S1.3) Materialise `tile_index` (eligible tiles per country; parameter-scoped)
                 - Domain:
                     * one row per `(country_iso, tile_id)` where the cell passes S1.2 for that country.
                 - Columns (shape from `#/prep/tile_index`):
                     * `country_iso` (FK to iso table)
                     * `tile_id` (from S1.1)
                     * `raster_row`, `raster_col`
                     * `centroid_lon_deg`, `centroid_lat_deg`
                     * `pixel_area_m2` (strictly positive)
                     * `inclusion_rule` ("center" / "any_overlap")
                 - Partition & sort discipline:
                     * path: `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/`
                     * partitions: `[parameter_hash]`
                     * writer sort: `[country_iso, tile_id]`
                 - Referential & domain checks:
                     * `country_iso` ∈ iso3166_canonical_2024 (FK).
                     * centroids within WGS84 bounds; `pixel_area_m2 > 0`.
                 - Determinism:
                     * For fixed ingress + `parameter_hash`, the set and order of rows is byte-identical across reruns.
                     * No RNG; results must not depend on degree of parallelism or scheduling.

(S1.1),
(S1.2)   ->  (S1.4) Materialise `tile_bounds` (rectangle bounds per eligible tile; parameter-scoped)
                 - Domain:
                     * same PK domain as `tile_index`: every `(country_iso, tile_id)` in `tile_index`
                       appears exactly once in `tile_bounds`.
                 - Columns (shape from `#/prep/tile_bounds`):
                     * `country_iso`, `tile_id`
                     * `min_lon_deg`, `max_lon_deg`
                     * `min_lat_deg`, `max_lat_deg`
                     * `centroid_lon_deg`, `centroid_lat_deg` (copy of S1.1 centroids)
                 - Bounds semantics:
                     * rectangle corresponds exactly to cell footprint from the raster grid.
                     * must be consistent with centroids and area semantics used in S1.1/S1.3.
                 - Partition & sort discipline:
                     * path: `data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/`
                     * partitions: `[parameter_hash]`
                     * writer sort: `[country_iso, tile_id]`
                 - No RNG; same determinism guarantees as `tile_index`.

(S1.3),
(S1.4)   ->  (S1.5) Integrity, acceptance & gate posture
                 - Acceptance checks (S1 succeeds only if all hold):
                     * both datasets conform to their schema anchors:
                         · `schemas.1B.yaml#/prep/tile_index`
                         · `schemas.1B.yaml#/prep/tile_bounds`
                     * Dictionary/path law respected:
                         · written only under declared `parameter_hash={parameter_hash}` paths,
                           with `format: parquet`, `partitioning: [parameter_hash]`, `ordering: [country_iso, tile_id]`.
                     * PK uniqueness: no duplicate `(country_iso, tile_id)` for a given `parameter_hash`.
                     * FK & geometry:
                         · `country_iso` in ISO domain,
                         · centroids in bounds, `pixel_area_m2 > 0`,
                         · rectangle bounds consistent with grid + country geometry.
                     * Determinism: repeated runs for same ingress + `parameter_hash`
                       produce byte-identical outputs.
                 - Gate posture for outputs:
                     * `tile_index` / `tile_bounds` have **no** `_passed.flag` gate.
                     * consumers must:
                         · resolve via Dictionary,
                         · apply these schema/path/FK/geometry checks,
                         · there is **no validation_bundle_1B** for S1 alone.
                 - Prohibitions:
                     * no reads of 1A egress or S3 order surfaces,
                     * no use of `tz_world_2025a` (belongs to later TZ states),
                     * no RNG, no order authority.


State boundary (authoritative outputs of S1)
-------------------------------------------
- tile_index   @ data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
    * parameter-scoped, RNG-free universe of **eligible raster cells per country**.
    * PK: [country_iso, tile_id]; partitions: [parameter_hash]; writer sort: [country_iso, tile_id].
    * sole authority for “which tiles exist for this parameter set” across 1B.
- tile_bounds  @ data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/
    * parameter-scoped companion to `tile_index` with rectangle bounds per eligible tile.
    * PK, partitions, writer sort mirror `tile_index`.
    * sole authority for per-tile rectangle geometry used later for jitter and synthesis.
- No RNG events or validation bundles are produced by S1.


Downstream touchpoints (from S1 outputs)
----------------------------------------
- 1B.S2 (Tile weights):
    * reads `tile_index` to know which `(country_iso, tile_id)` exist for this `parameter_hash`,
      then assigns fixed-dp weights per tile into `tile_weights`.
- 1B.S4 (Tile allocation plan):
    * relies on `tile_weights` being consistent with `tile_index` (coverage checks),
      so S1’s PK/FK/geometry guarantees are a precondition.
- 1B.S7 (Site synthesis) and 1B.S6 (jitter geometry checks):
    * use `tile_bounds` as the authoritative rectangle geometry for each tile_id when reconstructing
      absolute site coordinates and verifying jitter stays inside the cell.
- Any cross-layer consumer (e.g., diagnostics, 2A/2B planning):
    * may read `tile_index` / `tile_bounds` for geometry analysis,
      but **must not** invent competing grids or weight surfaces; S1 is the grid authority in 1B.
```