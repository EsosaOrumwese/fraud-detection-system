## Subsegment 1B: Placing outlets on the planet
Below is a comprehensive registry of **all artefacts** in Sub‑segment 1B (“Placing outlets on the planet”), each with a brief note on its role. I’ve cross‑checked both the **assumptions** and **narrative** texts to ensure nothing is omitted.

---

### 1. Manifest & Versioning Artefacts

* **`spatial_manifest.json`** – The fixed‑name JSON manifest listing every spatial prior’s SHA‑256 digest in lexicographic order; its digest is hashed to produce the **`spatial_manifest_digest`** column you embed in each site row for cryptographic provenance.
* **Sibling `.sha256` files** – Plain‑text siblings of each GeoTIFF/shapefile/GeoPackage recording that artefact’s SHA‑256, used by the manifest builder to verify integrity.

### 2. Spatial Prior Artefacts

* **HRSL population raster** (`artefacts/priors/hrsl/2020_v1.2/{ISO2}.tif`) – 100 m GeoTIFF from Meta’s High Resolution Settlement Layer, pinned by ID `hrsl_pop_100m` (vintage `2020_v1.2`); nodata cells→0.
* **WorldPop fallback raster** (`artefacts/priors/worldpop/2023Q4/{ISO2}.tif`) – 1 km GeoTIFF used when primary priors are missing or zero‑support.
* **OSM primary‑road network** (ESRI shapefiles/GeoPackages) – Clipped to country boundary with AADT per segment; used for vehicle‑oriented MCCs.
* **IATA airport polygons** (vector layer) – Commercial‑airport boundaries for travel‑retail MCCs; sampled by area.

### 3. Spatial Blending Artefacts

* **`spatial_blend.yaml`** – Governed YAML mapping each `(MCC, channel)` to either a single prior ID or a convex blend of priors; carries `semver`, `sha256_digest`, and enforces weights summing to 1 within 1 × 10⁻⁹.
* **Blended raster cache** (`cache/blends/{sha256(component_digests+weights)}.tif`) – Content‑addressed GeoTIFF of the blended prior, atomically written & reused.

### 4. Deterministic Sampling Artefacts

* **`fenwick_tie_break.jsonl`** – Captures tie‑break key ordering when two cells share the same cumulative weight, guaranteeing deterministic winner selection.

### 5. Land–Water Filtering Artefacts

* **`natural_earth_land_10m_v5.1.2.geojson`** – Natural Earth 1:10 m land polygon (v5.1.2), used to reject water points or road‑far points (> 50 m).

### 6. Remoteness Proxies Artefacts

* **`capitals_dataset_2024.parquet`** – Parquet of capital coordinates (ISO₂, `role_type`, `primary_flag`, lat, lon) with SHA‑256, used for Haversine distance.
* **OSM planet extract `.osm.pbf`** – Raw OSM snapshot (date‑stamped), SHA‑256‑pinned, source for the road graph.
* **Contraction‑hierarchies graph** – Prebuilt road index with commit hash & build parameters, used for on‑network distance.

### 7. Tagging & Schema Artefacts

Extended Parquet columns added to each site row:

| Column                                                    | Type    | Role                                                           |
| --------------------------------------------------------- | ------- | -------------------------------------------------------------- |
| `lat`, `lon`                                              | float64 | Sampled geographic coordinate                                  |
| `prior_tag`                                               | string  | Prior ID or `"FALLBACK_POP"`                                   |
| `prior_weight_raw`                                        | float64 | Float weight at sampled pixel/feature                          |
| `prior_weight_norm`                                       | float64 | Normalized weight = raw/Σ(raw weights)                         |
| `artefact_digest`                                         | hex64   | SHA‑256 of the specific prior file used                        |
| `spatial_manifest_digest`                                 | hex64   | Manifest hash for end‑to‑end traceability                      |
| `pixel_index` / `feature_index`                           | int32   | Exact sampling index for rasters or vectors                    |
| `segment_index`, `segment_frac` / `triangle_id`, `u`, `v` | various | Barycentric or polyline offsets for replayable vector sampling |
| `cdf_threshold_u`                                         | float64 | Uniform threshold in scaled CDF                                |
| `log_footfall_preclip`                                    | float64 | Pre‑clip log‑footfall value                                    |
| `footfall_clipped`                                        | bool    | Whether a site’s footfall was clipped                          |
|                                                           |         |                                                                |

### 8. Fallback Policy Artefacts

* **`fallback_policy.yml`** – YAML governing when to fallback to population raster, with `global_threshold`, `per_mcc_overrides`, `semver`, `sha256`.
* **`fallback_reason`** values – One of `missing_prior`, `zero_support`, `empty_vector_after_filter`, recorded per site.

### 9. Time‑Zone Consistency Artefacts

* **`tz_world_metadata.json`** – JSON mapping each IANA zone to its valid ISO α‑2 codes, with `semver`, `sha256`.
* **`tz_mismatch`**, **`tz_mismatch_exhausted`** events – Logged on each timezone validation failure or cap exhaustion.
* **`tz_resample.jsonl`** – Logs every coordinate re‑sampling triggered by a TZ/ISO mismatch; feeds nightly mismatch metrics and drift alerts.

### 10. Footfall Calibration Artefacts

* **`footfall_coefficients.yaml`** – YAML storing κ and σ per (MCC, channel) with calibration metadata (Fano target, iterations, seed), `semver`, `sha256`.
* **`calibration_slice_config.yml`** – Config for the 10 million‑row synthetic calibration slice stratified by (MCC, channel).
* **`CALIB_SEED`** – Fixed seed for calibration slice construction.
* **`historic_dist_2024Q4.sha256`** – Digest of the 2024 Q4 merchant distribution used for stratification.
* **`footfall_draw`** event – Audit of the log‑normal residual ε per site.

### 11. Outlier Control Artefacts

* **`winsor.yml`** – Two‑pass clipping policy (`clip_multiple=3`, `min_sites_for_clip=30`), with `semver`, `sha256`.
* **`log_footfall_preclip`**, **`footfall_clipped`** flags – Persisted in the Parquet for audit and debugging.

### 12. RNG Audit Artefacts

* **Master seed** – 128‑bit hex string written into the manifest before sampling. 
* **Shared schema:** all RNG event streams validate against the cross‑layer **`rng_event_schema_catalog`** defined in 1A. 
* **Audit events**:
`fenwick_build`, `fenwick_tie_break`, `pixel_draw`, `feature_draw`, `triangle_draw`, `polyline_offset`,
`footfall_draw`, `tz_resample`, `tz_mismatch`, `tz_mismatch_exhausted`, `placement_failure`
each logging `(pre_counter, post_counter, stride_key, merchant_id, site_id, site_rng_index)` and event‑specific payload. 
 
### 13. Crash‑Tolerance Artefacts

* **Temp file pattern**:
  `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet.tmp` – Written + fsync before atomic rename.
* **Final Parquet files**:
  `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet` – Idempotent output for each site.
* **End‑of‑run manifest JSON** – Records the run seed, composite spatial artefact hash, and wall‑clock time.

## 1B · Governing artefacts — addenda (to include in your doc)

### A) Spatial reference & grid

* **`crs_policy`** — canonical CRS and allowed temporary transforms. Cross‑layer.
* **`global_grid_spec`** — origin, resolution (fixed **1/1200°** grid), indexing; used by blends & sampling. Cross‑layer.
* **`country_boundary_ref`** — Admin‑0 polygons used for clipping/validation. Cross‑layer.
* **`land_water_mask_ref`** — Natural‑Earth **1:10 m v5.1.2** land mask (EPSG:4326). Cross‑layer.
* **`boundary_topology_fix_policy`** — rules/tolerances before clipping (repair self‑intersections/slivers).

### B) Priors & blending provenance

* **`prior_blend_recipe`** — per‑MCC/channel convex weights (must sum to 1 within 1e‑9).
* **`prior_blend_manifest`** — digests of component priors + recipe used.
* **`prior_provenance_map`** — country/category → which prior vintage actually used.

### C) Candidate pools & samplers

* **`country_cell_index`** — grid‑cell membership per country (post‑clip).
* **`candidate_pool_index`** — eligible cells/points with weights after masks & blends.
* **`fenwick_snapshot`** — serialized Fenwick/alias tables per (country, prior).
* **`sampling_method_manifest`** — records sampler (Fenwick vs alias), tolerances, seeds/strides.

### D) Acceptance & fallback governance

* **`acceptance_policy`** — thresholds: land/water, **road proximity**, TZ‑country consistency; Wilson target.
* **`acceptance_metrics`** — nightly acceptance with Wilson intervals (CI gate).
* **`fallback_policy`** — exact fallback rules & global cap.
* **`fallback_metrics`** — realized fallback rates + reasons.
* **`sample_blacklist_areas`** — polygons to exclude (military, glaciers, inland water). Cross‑layer.

### E) Roads & distance

* **`roads_ref`** — road network vintage & license (OSM). Cross‑layer.
* **`road_spatial_index`** — tiled index (R‑tree/H3) for proximity queries.
* **`road_proximity_config`** — category‑specific thresholds (default **50 m**).
* **`network_distance_graph`** *(optional)* — OSRM/CH snapshot for on‑network distance. Cross‑layer.
* **`road_distance_method`** — “nearest‑segment” vs “shortest‑path”, tie‑breaks.

### F) Remoteness proxies

* **`capital_points_ref`** — authoritative capital coordinates (Parquet). Cross‑layer.
* **`remoteness_method`** — Haversine/Vincenty, ellipsoid constants, rounding.
* **`remoteness_metrics`** — GC/network distance summaries; winsor stats.

### G) Timezone consistency

* **`tz_polygons_ref`** — TZ polygons to assign TZID. Cross‑layer.
* **`tz_override_table`** — manual fixes (enclaves/quirks). Cross‑layer.
* **`tz_mismatch_events`** — events when TZ country ≠ ISO country.

### H) Footfall & winsorization

* **`footfall_coefficients`** — transform from prior intensity → per‑site scalar.
* **`winsor_policy`** — caps by category/country bucket.
* **`footfall_scalar_table`** — per‑site scalar + provenance tag.

### I) Output governance & reproducibility

* **`site_catalogue`** + **`site_catalogue_schema`** — final rows; single authoritative schema file; written atomically; validated by spatial manifest.
* **`spatial_write_manifest`** — per‑run list of parts, bbox, CRS, digests.
* **`temp_write_policy`** + **`write_ahead_log`** — rename‑only commits + idempotent WAL. Cross‑layer.
* **`geospatial_lib_versions`** — exact GDAL/GEOS/PROJ used (pins topology behaviour). Cross‑layer.

### J) RNG & event logging

* **`rng_event_types_sampling`** — schema/catalog for sampling events. Cross‑layer.
* **`sample_candidate_events`**, **`accept_reject_events`**, **`fallback_invoked_events`** — runtime event streams (data).

---

## Policy constants & QA gates (record these verbatim in the doc)

* **Road proximity:** reject if candidate point is **> 50 m** from the sampled road segment.
* **Land mask:** Natural‑Earth **1:10 m v5.1.2** (EPSG:4326), **no simplification**.
* **Acceptance SLO:** nightly CI draws **10 000** per prior; **Wilson 95% lower bound ≥ 0.90** or build fails; trend alert if p̂ drops > 5 pp week‑over‑week. 
* **Termination cap:** `max_attempts_per_site = min(500, 10 × 1/max(0.10, a_L))`; exceeding logs `placement_failure` and aborts.
* **Grid alignment:** all blends resampled to **1/1200°** global grid (origin −180°, −90°); bilinear for continuous rasters.
* **AADT floor:** **500 vehicles/day** when constructing road weights.
* **Deterministic sampling:** floats scaled to **uint64**; CDF via **Fenwick tree**; no intra‑pixel jitter in governed builds.

---

## Site‑catalogue: schema deltas to surface in the doc

Add these **column families** (your schema file remains the source of truth):

* **Core:** `lat`, `lon`, `prior_tag`, `prior_weight_raw`, `prior_weight_norm`, `spatial_manifest_digest`, `artefact_digest`. 
* **Replay fields:** raster → `pixel_index`; vector‑polyline → `feature_index`, `segment_index`, `segment_frac`; vector‑polygon → `feature_index`, `triangle_id`, `u`, `v`; always log `cdf_threshold_u`.
* **Remoteness:** `gc_km_to_capital` and, if network enabled, `road_km_to_capital`.

---

## Cross‑layer flags (mark clearly in the doc)

`crs_policy`, `global_grid_spec`, `country_boundary_ref`, `land_water_mask_ref`, `roads_ref`, `network_distance_graph`, `tz_polygons_ref`, `tz_override_table`, `geospatial_lib_versions`, **`rng_event_schema_catalog`**, **`storage_path_pattern`**, **`manifest_fingerprint`** — these artefacts live in 1A (or higher) and are referenced here; they must stay version‑locked layer‑wide.

