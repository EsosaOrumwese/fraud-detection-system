## [1A.1] - 2025-07-20
### Added
- Deterministic currency→country expansion artefact with smoothing/fallback.
- Universal RNG audit schema covering all stochastic events and stream jumps.
- Post-write validation replay step with abort semantics.
- Monitoring corridors for NB and ZTP rejection behavior; rounding deviation metrics.
- Explicit statistical metadata: θ₁ significance, stationarity test digest.
- Tie-break rank field, residual 8dp recording, site_id fixed 6-digit width.

### Changed
- NB specification clarified: mean excludes developmental bucket; dispersion includes log(GDPpc).
- Foreign country selection defined via Gumbel-top-k (one uniform per candidate).
- Largest-remainder rounding determinism (residual quantisation + ISO secondary key).

### Fixed
- Contradictions (K=0 under zero-truncation, “exactly same design matrix” wording).
- Schema inconsistencies (missing home/legal country, seed column).
- Ambiguous currency vs country weighting semantics.

### Removed
- Unreachable K=0 logic path.
- Ambiguous blanket statement “No other assumptions are latent.”

### Breaking
- Outlet stub schema expanded; previous builds incompatible.
- RNG log requires updated parser for new event types and fields.


## [1B.1.0] - 2025-07-20
### Added
- `spatial_manifest.json` with composite `spatial_manifest_digest` column.
- Provenance entries for HRSL 100m raster, WorldPop 1km fallback (v2023Q4), Natural Earth land mask v5.1.2, capitals dataset, OSM road graph snapshot.
- Extended per-site tagging fields (indices, barycentric coords, raw & normalized weights, uniform thresholds).
- RNG audit events: fenwick_build, pixel_draw, feature_draw, triangle_draw, polyline_offset, tz_mismatch, tz_mismatch_exhausted, footfall_draw, placement_failure.
- Governed config artefacts: `spatial_blend.yaml`, `winsor.yml`, `fallback_policy.yml`, `calibration_slice_config.yml`, `tz_world_metadata.json`, `footfall_coefficients.yaml`.
- New provenance artefacts for time‑zone boundaries (`tz_world_polygons_v2024a.geojson`), OSM primary‑road snapshot (`osm_primary_roads_{planet_YYYYMMDD}.gpkg`), AADT counts table (`aadt_counts_compiled_v1.parquet`), IATA airport boundaries (`iata_airport_boundaries_v2023Q4.geojson`), suburban population density raster (`suburban_pop_density_2022_v1.tif`), and road traffic density raster (`road_traffic_density_2022_v2.tif`).
- Governed Artefact Registry appendix in Assumptions.txt enumerating every spatial and policy artefact, their path patterns, semver fields, and digest requirements.

### Changed
- Blending: standardized CRS/grid/resampling; deterministic content-addressed output.
- Polygon sampling: triangulation + alias table (replaces bounding-box rejection).
- Polyline sampling: geodesic cumulative length method.
- Fenwick construction: eager, locked, overflow-safe scaling.
- Footfall generation: dedicated RNG sub-stream; calibration methodology formalized.
- Time-zone validation: replaces suffix heuristic with zone→ISO set mapping.
- Termination: hard attempt cap + Wilson interval acceptance monitoring.
- Winsorisation: two-pass deterministic, governed policy file.
- Fallback semantics: explicit zero-support criteria and reason codes.
- Manifest fingerprint: excludes wall-clock timestamp; combined upstream + spatial + governed digests.
- Assumptions.txt now ends with a “Governed Artefact Registry” section listing all spatial/prior and policy files with the exact filename patterns, role descriptions, semver and SHA‑256 columns, and manifest inclusion rules.

### Removed
- Reliance on implicit prior coverage assumption.
- Use of SHA-1 for RNG sub-stream derivation.
- Unspecified polygon rejection sampling.

### Security / Integrity
- All randomness and artefact transformations auditable; undocumented behaviours now explicitly treated as defects.

### Migration
- Consumers must update schema handlers to read new columns and enforce `spatial_manifest_digest`.
- Replay tooling must validate presence of new audit events.


## [2A.1.0] – 2025‑07‑21

### Added

* Full provenance for `tz_world_2025a.shp` and companion `.shx/.dbf/.prj/.cpg` under `artefacts/priors/tz_world/2025a/` with individual SHA‑256 digests in the manifest.
* SHA‑256 digest of the STR‑tree index (Python 3.10, pickle protocol 5) replacing MD5.
* `tz_nudge.yml` and `tz_overrides.yaml` as governed artefacts with semver and digest fields (`tz_nudge_digest`, `tz_overrides_digest`).
* Declaration of tzdata archive `artefacts/priors/tzdata/tzdata2025a.tar.gz` with semver in `zoneinfo_version.yml` and `tzdata_archive_digest`.
* Simulation horizon config (`simulation_horizon.yml`) with `sim_start`/`sim_end`, RLE truncation and cache‑size gauge enforcement (< 8 MiB).
* Exception table enumerating `TimeZoneLookupError`, `DSTLookupTieError`, and `TimeTableCoverageError` with atomic rollback semantics.
* Appendix A (Mathematical Definitions & Conventions) detailing RLE, Δ computation, nudge, fold‑bit hashing, UTC conversion, horizon truncation, cache metrics, and error‑handling formulas.
* Governed Artefact Registry table listing all 2A artefacts, path patterns, roles, semver and digest fields.

### Changed

* Tie‑break narrative updated to acknowledge `DSTLookupTieError` if a nudge does not resolve overlapping polygons.
* Corrected `event_time_utc` formula to `floor((t_local - 60*o) * 1000)` (ms), aligning with `TIMESTAMP_MILLIS`.

### Removed

* Implicit assumptions about error‑free DST tie resolution; now explicitly handled.

### Migration 
- Consumers must refresh the 2A spec, update CI to ingest new digest fields, and regenerate any downstream manifests before proceeding to 2B.


## [3A.1.0] – 2025‑07‑22

### Added
- `zone_mixture_policy.yml` (`theta_mix`) with `theta_digest` and CI gating  
- `country_zone_alphas.yaml` (ISO→TZID α) with `zone_alpha_digest`  
- `docs/round_ints.md` rounding spec with `rounding_spec_digest` and CI property test  
- `zone_floor.yml` floors for micro‑zones with `zone_floor_digest`  
- `artefacts/allocation/country_major_zone.csv` fallback mapping with `major_zone_digest  
- `artefacts/allocation/<merchant_id>_zone_alloc.parquet` and `zone_alloc_index.csv` drift sentinel with `zone_alloc_index_digest`  
- `config/routing/rng_policy.yml` RNG key policy (`gamma_day`) with `gamma_day_key_digest`  
- `config/validation/cross_zone_validation.yml` validation thresholds with `cross_zone_validation_digest` and CI slope/share tests  
- `docs/rng_proof.md` and `ci/replay_zone_alloc.py` RNG‑stream isolation proof with `rng_proof_digest` 
- `LICENSES/*` licence texts with `licence_digests`  
- Appendix A – Mathematical Definitions & Conventions  
- Governed Artefact Registry table


## [3B.1.0] – 2025‑07‑22

### Added
- `config/virtual/mcc_channel_rules.yaml` policy ledger (`virtual_rules_digest`) and CI `test_virtual_rules.py`
- `artefacts/virtual/virtual_settlement_coords.csv` coordinate registry (`settlement_coord_digest`) and CI `verify_coords_evidence.py`
- `artefacts/geocode/pelias_cached.sqlite` geocoder bundle (`pelias_digest`) and CI `test_geocoder_bundle.py`
- `config/virtual/cdn_country_weights.yaml` edge‑weight policy (`cdn_weights_digest`) and CI `test_cdn_weights.py`
- `artefacts/rasters/hrsl_100m.tif` HRSL population raster (`hrsl_digest`) and CI `test_raster_availability.py`
- `edge_catalogue_index.csv` drift‑sentinel index (`edge_catalogue_index_digest`)
- `config/routing/rng_policy.yml` Philox key policy (`cdn_key_digest`) and CI `test_cdn_key.py`
- `config/virtual/virtual_validation.yml` validation thresholds (`virtual_validation_digest`) and CI `test_virtual_validation.py`
- `logs/edge_progress.log` logging policy (`virtual_logging_digest`) and CI `test_log_config.py`
- `schema/transaction_schema.avsc` virtual‑flow fields (`transaction_schema_digest`) and CI `test_schema_registry.py`
- CI `test_virtual_universe.py` for virtual universe hash
- `manifest_virtual.json` licence digest registry (`licence_digests_virtual`) and CI `test_licences_virtual.py`
- Appendix A with mathematical definitions for all virtual‑merchant algorithms
- Governed Artefact Registry table for the virtual sub‑segment
