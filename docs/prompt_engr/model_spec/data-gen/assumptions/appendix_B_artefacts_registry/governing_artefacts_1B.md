## Subsegment 1B: Placing outlets on the planet
Below is a comprehensive registry of **all artefacts** in Sub‑segment 1B (“Placing outlets on the planet”), each with a brief note on its role. I’ve cross‑checked both the **assumptions** and **narrative** texts to ensure nothing is omitted.

---

### 1. Manifest & Versioning Artefacts

* **`spatial_manifest.json`** – The fixed‑name JSON manifest listing every spatial prior’s SHA‑256 digest in lexicographic order; its digest is hashed to produce the **`spatial_manifest_digest`** column you embed in each site row for cryptographic provenance.&#x20;
* **Sibling `.sha256` files** – Plain‑text siblings of each GeoTIFF/shapefile/GeoPackage recording that artefact’s SHA‑256, used by the manifest builder to verify integrity.&#x20;

### 2. Spatial Prior Artefacts

* **HRSL population raster** (`artefacts/priors/hrsl/2020_v1.2/{ISO2}.tif`) – 100 m GeoTIFF from Meta’s High Resolution Settlement Layer, pinned by ID `hrsl_pop_100m` (vintage `2020_v1.2`); nodata cells→0.&#x20;
* **WorldPop fallback raster** (`artefacts/priors/worldpop/2023Q4/{ISO2}.tif`) – 1 km GeoTIFF used when primary priors are missing or zero‑support.&#x20;
* **OSM primary‑road network** (ESRI shapefiles/GeoPackages) – Clipped to country boundary with AADT per segment; used for vehicle‑oriented MCCs.&#x20;
* **IATA airport polygons** (vector layer) – Commercial‑airport boundaries for travel‑retail MCCs; sampled by area.&#x20;

### 3. Spatial Blending Artefacts

* **`spatial_blend.yaml`** – Governed YAML mapping each `(MCC, channel)` to either a single prior ID or a convex blend of priors; carries `semver`, `sha256_digest`, and enforces weights summing to 1 within 1 × 10⁻⁹.&#x20;
* **Blended raster cache** (`cache/blends/{sha256(component_digests+weights)}.tif`) – Content‑addressed GeoTIFF of the blended prior, atomically written & reused.&#x20;

### 4. Deterministic Sampling Artefacts

* **Fenwick tree build logs** (`fenwick_build` event) – Records `(country, prior_id, n, total_weight, build_ms, scale_factor)` for each CDF structure, ensuring repeatable importance sampling.&#x20;

### 5. Land–Water Filtering Artefacts

* **`natural_earth_land_10m_v5.1.2.geojson`** – Natural Earth 1:10 m land polygon (v5.1.2), used to reject water points or road‑far points (> 50 m).&#x20;

### 6. Remoteness Proxies Artefacts

* **`capitals_dataset_2024.parquet`** – Parquet of capital coordinates (ISO₂, `role_type`, `primary_flag`, lat, lon) with SHA‑256, used for Haversine distance.&#x20;
* **OSM planet extract `.osm.pbf`** – Raw OSM snapshot (date‑stamped), SHA‑256‑pinned, source for the road graph.&#x20;
* **Contraction‑hierarchies graph** – Prebuilt road index with commit hash & build parameters, used for on‑network distance.&#x20;

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

* **`fallback_policy.yml`** – YAML governing when to fallback to population raster, with `global_threshold`, `per_mcc_overrides`, `semver`, `sha256`.&#x20;
* **`fallback_reason`** values – One of `missing_prior`, `zero_support`, `empty_vector_after_filter`, recorded per site.&#x20;

### 9. Time‑Zone Consistency Artefacts

* **`tz_world_metadata.json`** – JSON mapping each IANA zone to its valid ISO α‑2 codes, with `semver`, `sha256`.&#x20;
* **`tz_mismatch`**, **`tz_mismatch_exhausted`** events – Logged on each timezone validation failure or cap exhaustion.&#x20;

### 10. Footfall Calibration Artefacts

* **`footfall_coefficients.yaml`** – YAML storing κ and σ per (MCC, channel) with calibration metadata (Fano target, iterations, seed), `semver`, `sha256`.&#x20;
* **`calibration_slice_config.yml`** – Config for the 10 million‑row synthetic calibration slice stratified by (MCC, channel).&#x20;
* **`CALIB_SEED`** – Fixed seed for calibration slice construction.&#x20;
* **`historic_dist_2024Q4.sha256`** – Digest of the 2024 Q4 merchant distribution used for stratification.&#x20;
* **`footfall_draw`** event – Audit of the log‑normal residual ε per site.&#x20;

### 11. Outlier Control Artefacts

* **`winsor.yml`** – Two‑pass clipping policy (`clip_multiple=3`, `min_sites_for_clip=30`), with `semver`, `sha256`.&#x20;
* **`log_footfall_preclip`**, **`footfall_clipped`** flags – Persisted in the Parquet for audit and debugging.&#x20;

### 12. RNG Audit Artefacts

* **Master seed** – 128‑bit hex string written into the manifest before sampling.&#x20;
* **Audit events**:
  `fenwick_build`, `pixel_draw`, `feature_draw`, `triangle_draw`, `polyline_offset`,
  `footfall_draw`, `tz_mismatch`, `tz_mismatch_exhausted`, `placement_failure`
  each logging `(pre_counter, post_counter, stride_key, merchant_id, site_id, site_rng_index)` and event‑specific payload.&#x20;

### 13. Crash‑Tolerance Artefacts

* **Temp file pattern**:
  `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet.tmp` – Written + fsync before atomic rename.&#x20;
* **Final Parquet files**:
  `sites/partition_date=YYYYMMDD/merchant_id={id}/site_id={site_id}.parquet` – Idempotent output for each site.&#x20;
* **End‑of‑run manifest JSON** – Records the run seed, composite spatial artefact hash, and wall‑clock time.&#x20;

---