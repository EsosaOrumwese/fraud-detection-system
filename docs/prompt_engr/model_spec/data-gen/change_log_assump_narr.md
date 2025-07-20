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

### Removed
- Reliance on implicit prior coverage assumption.
- Use of SHA-1 for RNG sub-stream derivation.
- Unspecified polygon rejection sampling.

### Security / Integrity
- All randomness and artefact transformations auditable; undocumented behaviours now explicitly treated as defects.

### Migration
- Consumers must update schema handlers to read new columns and enforce `spatial_manifest_digest`.
- Replay tooling must validate presence of new audit events.
