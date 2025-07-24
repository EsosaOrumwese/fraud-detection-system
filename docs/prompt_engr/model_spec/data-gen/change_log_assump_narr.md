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


## [2A.1.1] – 2025‑07‑24

### Added
* **Deterministic STR-tree index construction and hashing:** Algorithm for STR-tree build, serialization (Python 3.10, pickle 5), and SHA-256 digest (`tz_index_digest`) now formalized in maths appendix and governed as artefact.
* **Nudge/tie-break protocol and output linkage:** Algorithmic formula for vector nudging, YAML-driven epsilon, and output of `(nudge_lat, nudge_lon)` per site.
* **Override precedence algorithm:** Full pseudo-algorithm for specificity/precedence, manifest and CI drift validation now formalized.
* **Audit/event log schema:** Formal field table covering all assignment, nudge, error, and override events, with enforcement.
* **Manifest, provenance, and licensing:** Manifest digest/artefact aggregation, artefact/digest linkage, and explicit licence mapping now governed in both maths and artefact appendix.
* **Output artefacts:** STR-tree digest, override/nudge YAMLs, audit/validation logs, cache byte record, output schema, and output catalogue now fully governed.
* **CI enforcement:** Nightly override drift, audit logs, manifest drift detection and enforcement now governed.
* **Immutability contract:** All catalogue outputs must carry and validate digest lineage; missing field or digest triggers hard abort.

### Changed
* **All previously procedural, narrative, or implicit steps** (STR index build, nudge application, audit logging, error event contracts, manifest enforcement) now formalized as algorithms, tables, or build invariants in appendices.

### Fixed
* **Gaps in registry:** Every referenced log, output, digest, and contract is now explicitly listed and governed.

### Integrity
* No narrative or design changes—*all expansions are formalizations of existing commitments*.

---

## [2B.1.0] – 2025‑07‑22

### Added
* **Catalogue provenance:** `artefacts/catalogue/site_catalogue.parquet` governed under `site_catalogue_digest`.
* **Routing manifest:** `artefacts/routing/routing_manifest.json` with its own semver and `routing_manifest_digest`.
* **Config governance:**
  * `config/routing/routing_day_effect.yml` (`sigma_squared`, semver, `gamma_variance_digest`).
  * `config/routing/cdn_country_weights.yaml` (`q_c`, semver, `cdn_alias_digest`).
  * `config/routing/routing_validation.yml` (`tolerance_share`, `target_correlation`, semver, `validation_config_digest`).
* **Binary I/O formats:**
  * `<merchant_id>_pweights.bin` (little‑endian float64, code in `router/io.py`).
  * `<merchant_id>_alias.npz` (NumPy 1.23 uncompressed, arrays `prob` & `alias`).
* **RNG partitioning:** Philox seed from SHA‑1 of `(global_seed, "router", merchant_id)` documented in `rng_policy.yml`, and counter scheme fixed in `router/prng.py`.
* **Error‑handling:** Introduce `RoutingZeroWeightError` for Σ Fᵢ = 0 in `router/errors.py`.
* **Operational logs:** `logs/routing/routing_audit.log` path, rotation (daily), retention (90 days) governed by `logging.yml` (`audit_log_config_digest`).
* **Performance metrics:** SLA of 200 MB/s and RAM caps monitored via Prometheus in `router/metrics.py`, thresholds in `performance.yml` (`perf_config_digest`).
* **Governed Artefact Registry:** Append registry table listing all 2B artefacts with path patterns, roles, semver and digest fields.

### Changed
* No previous behaviors removed; new validations and exceptions introduced.

## [2B.1.1] – 2025‑07‑22

### Changed

* **Time‑zone grouping:** Added explicit definition of the “time‑zone group” (outlets with matching IANA `tzid`) for re‑normalisation invariants.
* **Alias‑table thresholds:** Clarified that the `prob` array stores fixed‑point thresholds as `round(p_i * N_m)` in `uint32`, ensuring precise comparison against the uniform draw.


## [2B.1.2] – 2025‑07‑24

### Added
* **Manifest construction and governance:** Algorithmic formalization of artefact digest construction, manifest enforcement, and abort triggers.
* **Alias table modulation (O(1) threshold scaling):** Pseudo-algorithm for post-modulation scaling without table rebuild, ensuring invariance.
* **Virtual merchant CDN routing:** Step-by-step process for CDN country alias sampling and output, formalized and governed.
* **Audit/validation/error logs:** Structured schema for all routing/audit/validation/error logs, each governed as output artefacts.
* **Output buffer governance:** Buffer files, all hidden columns (gamma\_id, gamma\_value, ip\_country\_code) now registered with schema enforcement.
* **Validation and CI outputs:** Assertion outputs, batch validation logs, and hard-fail enforcement now governed.
* **Licence enforcement:** All config, YAML, and data files must carry digest-verified licence, referenced in manifest and registry.

### Changed
* **Enforcement contracts:** All procedural/operational requirements for logs, manifests, schema, and audit trails now codified and governed.

### Fixed
* **No design changes:** All expansions are direct formalizations—no mechanism or guarantee altered or omitted.

----


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

## [3A.1.1] – 2025‑07‑24

### Added
* **Cross-linkage to rounding spec and CI test suite:** Maths appendix now formally contracts to `docs/round_ints.md` and requires that all rounding logic and property-based tests (`ci/test_rounding_conservation.py`) must pass and be artefact-logged.
* **Universe hash/manifest enforcement:** Algorithms and error contracts for universe hash construction, manifest propagation, and drift/error (`ZoneAllocDriftError`, `UniverseHashError`) now formalized in maths appendix.
* **Output Parquet schema contract:** Explicit table definition for `<merchant_id>_zone_alloc.parquet` columns, types, sortedness, and nullability now required and governed.
* **Licence provenance/enforcement:** Appendix now requires every governed YAML/CSV/config to have an explicit `LICENSES/` mapping and digest check on every CI run.
* **Replay guarantee:** End-to-end reproducibility and replay contract now stated in appendix; failure to reproduce or replay is a spec violation and aborts the pipeline.
* **Diagnostic/test artefact governance:** All barcode slope validation logs, heatmaps, property-based test logs, and drift/error events are now required as governed outputs and referenced in the manifest.
* **Artefact registry expanded:** Registry now explicitly lists all schema, log, validation, and test outputs as governed, with enforcement and abort contracts.

### Changed
* **All procedural/operational contracts** (test logs, output schemas, licence enforcement, drift/error handling) now formalized in the appendices, with explicit governance rules.

### Fixed
* **Any previously ungoverned artefact, log, or schema referenced in the main text is now fully listed and enforced.**

### Integrity
* **No new requirements or design changes—strict formalization and audit gap-closure only.**


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

## [3B.1.1] – 2025‑07‑24

### Added
* **Output table schema/contract:** Full output column, type, and sortedness contract for `edge_catalogue/<merchant_id>.parquet` formalized and schema-governed.
* **Error and drift log governance:** All error, progress, CI drift, and crash logs (`virtual_error.log`, `edge_progress.log`) now registered as governed artefacts with hard abort on any missing or failed log.
* **Test, validation, and CI contract:** Every referenced test (`test_virtual_rules.py`, `verify_coords_evidence.py`, `test_cdn_key.py`, `test_virtual_universe.py`, `test_cutoff_time.py`, `validate_virtual.py`) now produces a governed log, all tracked and required in the manifest.
* **Manifest/licence contract enforcement:** Every YAML/CSV/NPZ/Parquet artefact is now explicitly mapped to a `LICENSES/` file with SHA-256 digest, enforced on every CI run.
* **Replay/reproducibility contract:** End-to-end reproducibility and replay guarantee now formalized in maths appendix and enforced by CI.
* **Artefact registry expanded:** All schema, log, and validation outputs, plus all CI test logs and licence mappings, now listed as governed with strict enforcement.

### Changed
* **All procedural/operational requirements** (test outputs, output schemas, error/drift logging, manifest/licence enforcement) are now formally required, not implied.

### Fixed
* **Any missing governance, logging, schema, or contract referenced in main spec is now fully closed.**

### Integrity
* **No design change—every formalization is demanded by your original narrative and assumptions.**

---


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

## [4A.1.2] – 2025‑07‑24

### Added
* **Meta-governance contracts**: All artefacts, configs, logs, scripts, schemas, build/container/source hashes, and validation outputs from 1A–3B must be registered in the artefact registry and referenced in every manifest by hash.
* **Manifest and build artefacts**: `/tmp/build.manifest`, live manifest, and all pipeline orchestration scripts (e.g., `pipeline_launcher.sh`) are now governed artefacts, hash-captured and referenced at row-level.
* **Source and container provenance**: All runs must record the Git source SHA, branch, and container hash (`Dockerfile.lock`) in the manifest and all output rows.
* **Read-only export/immutability contract**: Export directories named by parameter hash are NFS/OS-level read-only; any attempt to overwrite or re-export with the same hash/seed is a fatal error and blocks build/merge.
* **Validation and forensic artefact logging**: All outputs from statistical validation, bootstrap, geospatial conformance, GLM/footfall regression, AUROC, DST, and structural firewall checks are now governed artefacts with unique digests, referenced in the manifest, and blocking for merge.
* **HashGate/Audit linkage**: All manifests and validation outputs must include a HashGate audit URI and require CI approval of this URI prior to merge or release.
* **Licence mapping enforcement**: Every governed artefact, config, or schema is now explicitly mapped to a tracked `LICENSES/` file, with digest checked in every build and merge.

### Changed
* **Row-level provenance and manifest lineage**: All output files/tables must now embed parameter hash, build timestamp, manifest digest, and source/container SHA as schema or metadata.
* **Collision/uniqueness contracts**: Directory and Postgres-level uniqueness constraints on parameter hash and seed are strictly enforced, with collision errors blocking CI and dataset export.

### Breaking
* **CI and audit jobs**: All validation, provenance, and audit artefacts must be present, hashed, and referenced in the manifest for a build to pass or a dataset to be released.
* **Manifest and registry enumeration**: Any missing, mismatched, or omitted artefact, licence, or validation output now blocks pipeline progression, requiring downstream consumers and CI tooling to honor full meta-governance enforcement.


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

## [4B.1.1] – 2025‑07‑24

### Added
* **Full validation artefact and log governance**: Every validator output, error log, AUROC model dump, misclassification index, θ-violation PDF, barcode failure overlay, and HashGate audit URI now governed, hash-tracked, and referenced in the manifest.
* **Merge-blocking and quarantine contracts**: Any structural error, DST/time error, distribution drift, theta/barcode failure, or licence mismatch triggers dataset quarantine and blocks merge until cleared.
* **HashGate audit contract**: All CI jobs must poll and reference the HashGate/Audit URI for immutable approval before merge or release.
* **Licence mapping and enforcement**: All governed artefacts must have explicit licence mapping and digest; any mismatch blocks build and validation.
* **Read-only directory export/collision contract**: Datasets are NFS/OS-level read-only after build, and re-exporting for the same parameter hash/seed triggers a fatal error.

### Changed
* **Validation manifest and pass/fail artefacts**: All validation outputs, pass/fail flags, and error overlays must now be registered in the manifest, referenced in every output row, and block merge on any failure or absence.
* **End-to-end audit trail**: All outputs are now required to be auditable by HashGate and referenced in both manifest and output schema.

### Breaking
* **CI, validation, and audit workflow**: Build, merge, and release are now strictly gated on the successful, complete, and hash-validated presence of all governance artefacts and audit logs listed above. Downstream automation and scripts must enforce these contracts.


