## [1A.1.0] - 2025-07-20
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

## [1A.1.1] – 2025‑07‑24

### Added
* **Complete manifest construction algorithm**: formalized step‑by‑step procedure for computing parameter and artefact digests, XOR reduction, lineage fingerprint propagation.
* **Audit log schema/table**: explicit field listing and event types for all mandatory stochastic operations, rejection/failure, and sequence indices.
* **Immutability contract**: downstream modules required to verify manifest lineage/fingerprint in all outputs; contract violation now aborts downstream.
* **Formal monitoring and CI/CD guardrails**: CUSUM/threshold logic, corridor constraints, and required diagnostics explicitly mapped.
* **Post‑write and structural validation logic**: algorithm for deterministic replay and validation, ensuring reproducibility and full auditability.
* **Output stub schema (mathematics appendix)**: column‑level type and field specification for all outputs, with explicit encoding, versioning, and read‑only enforcement.
* **Explicit registry of governed input artefacts, logs, manifests, diagnostic outputs, and output catalogues**: all artefacts referenced in the narrative/assumptions now formally listed in Governing Artefacts appendix.

### Changed

* **All previously procedural or implicit narrative/assumption steps** (e.g., lineage propagation, audit events, manifest update triggers, schema versioning, CI validation) are now formalized in appendices as reproducible pseudo‑algorithms or tables.

### Fixed
* **Gaps between narrative/assumptions and appendices**: All referenced artefacts, logs, schemas, and contracts are now explicitly governed and versioned.

### Security / Integrity
* **No design changes or new requirements introduced**: All updates strictly expand and formalize what is already present, ensuring full spec‑appendix alignment and eliminating tacit knowledge.

---

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


## [1B.1.1] – 2025‑07‑24

### Added
* **Manifest digest and whitelist construction (maths appendix)**: stepwise algorithm for composite digest, whitelist enforcement, and timestamp exclusion.
* **Fenwick tree build/reuse logic**: concurrency, lock-guarded idempotent construction, crash handling, and audit event emission now formalized in mathematics appendix.
* **Crash-tolerant write protocol**: temp file, fsync, atomic rename, and recovery invariant detailed and mandated.
* **Audit log and placement event schema**: event fields, types, failure reasons, and site RNG index now formalized.
* **Remoteness/capital row selection algorithm**: fallback/abort logic now explicit for capital dataset usage.
* **Immutability and output contract**: mathematics appendix formalizes lineage verification and downstream enforcement.
* **Output catalogue, schema, log, temp, and diagnostic artefact registry**: all outputs, logs, metrics, schema descriptors, calibration digests, and temp file policies now formally registered in Governing Artefacts appendix.
* **Manifest/whitelist enforcement policy**: build abort and semver bump requirements made explicit in artefacts appendix.

### Changed
* **No narrative/assumption content altered or removed**: All integrations are expansions to fully capture required operational, diagnostic, and reproducibility logic in the appendices.

### Fixed
* **Every artefact, log, contract, and schema referenced in the main text is now governed and explicitly tracked**.

### Security / Integrity
* **Downstream immutability and audit enforcement**: Appendices now require, and mathematically formalize, all lineage, schema, and log contract checks already present in the main text.

---
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


## [4A.1.0] - 2025-07-23
### Added
- `license_map` section details and `validate_licences.py` license‐artifact verification.
- Live manifest path (`/tmp/build.manifest`) and manifest line ordering.
- Parameter‑set hash computation (XOR + SHA256 over ordered digests) and `dataset_root` naming.
- Master seed construction with 64‑bit left‑shift of timestamp and low‑128 bit XOR.
- Philox 2¹²⁸ sub‑stream protocol with SHA1‑derived jump strides and full `rng_trace.log`.
- Structural firewall in `firewall.py` performing five vectorized integrity checks.
- Geospatial conformance audit in `geo_audit.py` using conjugate beta‑posterior intervals.
- Outlet‑count bootstrap (`bootstrap_validator.py`) with 10000 replicates, envelope tests, and PNG diagnostics.
- Footfall–throughput Poisson‑GLM regression in `footfall_glm_validator.py` with dispersion bounds.
- Multivariate indistinguishability test (`xgb_validator.py`) on 6‑D embeddings with deterministic AUROC.
- DST edge‑passer (`dst_validator.py`) minute‑level gap/fold validation around transitions.
- HashGate integration (`upload_to_hashgate.py`) and read‑only NFS export by `parameter_hash`.

### Changed
- YAML schema enforcement extended: all statistical entries require `mean`, `ci_lower`, `ci_upper`.
- Manifest generation revised to include artifact‑registry enumeration and streaming into accumulator.
- CI collision prevention via Postgres unique constraint on `(parameter_hash, seed)`.

### Breaking
- CI jobs now expect new validation scripts and updated `rng_trace.log` event schema.
- Manifest and dataset naming conventions changed; downstream consumers must adapt to `/tmp/build.manifest` and `synthetic_v1_<parameter_hash>` directory names.
- Audit‑log parsers must handle additional fields (`stream_jump`, `hurdle_bernoulli`, `nb_rejection`, etc.).


## [4A.1.1] - 2025-07-23

### Changed
- **Narrative** now references `pipeline_launcher.sh` for manifest creation instead of “orchestration script.”
- **Narrative** now references `artefact_loader.py` for artifact path enumeration.
- **Narrative & Assumptions** updated to place `master_seed_hex` on **line 5** of the manifest.
- **Narrative** now references `upload_to_hashgate.py` for HashGate uploads.
- **Assumptions** now document insertion of `creator_param_hash=<hash>` into Parquet schema comments and its use in the RNG constructor.

### Breaking
- Scripts and line‑number conventions have been formalized; downstream documentation or automation expecting generic “script” names or placeholder line N must be updated to the specific names and line 5.

## [4B.1.0] - 2025-07-23

### Changed
- Structural integrity failure now writes to `structural_failure_<parameter_hash>.parquet` and raises `StructuralValidationError` (was generic `<hash>` placeholder).
- Licence concordance step simplified to `validate_licences.py` comparing against `licence_digests` in the manifest, raising `LicenceMismatchError`.
- HashGate integration clarified: directory `validation/<parameter_hash>/` is SHA-256 hashed, uploaded to `/hashgate/<parameter_hash>/<master_seed>`, with HTTP response logged.
- Footfall regression diagnostic PDF fixed to `glm_theta_violation.pdf` in the `validation/<parameter_hash>/` path.
- AUROC evaluation cadence now configured via `auroc_interval` in `validation_conf.yml` (default 1,000,000 rows) and triggers `AurocThresholdExceeded` on breach.

### Breaking
- File-naming conventions for structural failures and diagnostics changed; downstream scripts and tests must reference the new names.
- Validation configuration (`validation_conf.yml`) must include `auroc_interval`.
- HashGate upload URIs and polling workflows must be updated to use the `/hashgate/<parameter_hash>/<master_seed>` pattern and handle logged HTTP statuses.


