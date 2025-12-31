# Evidence - Layer 1 Data Intake

Created: 2025-12-31
Purpose: record deprecated paths, new paths, and realism checks per artefact.

Use one section per artefact:
- artefact_id:
- deprecated_path:
- new_path:
- realism_checks:

## iso3166_canonical_2024
- artefact_id: iso3166_canonical_2024
- deprecated_path: reference/iso/iso3166_canonical/2024-12-31/deprecated_iso3166.parquet
- new_path: reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet
- realism_checks:
  - Source: GeoNames countryInfo.txt snapshot; ISO2-only with XK and UK excluded per guide.
  - Uniqueness enforced: `country_iso` unique and `(alpha3, numeric_code)` unique.
  - Deterministic sort by `country_iso`; row count = 250.
  - Provenance recorded with raw/output sha256 and exclusion list in `reference/iso/iso3166_canonical/2024-12-31/iso3166.provenance.json`.

## world_countries
- artefact_id: world_countries
- deprecated_path: none
- new_path: reference/spatial/world_countries/2024/world_countries.parquet
- realism_checks:
  - Natural Earth Admin 0 Countries 10m (public domain) used; ISO_A2 primary with ISO_A3 fallback via iso3166 canonical.
  - Dissolved to one geometry per ISO2; geometry made valid; CRS preserved as EPSG:4326.
  - Row count = 236; provenance includes raw/output sha256 and unmapped drop count in `reference/spatial/world_countries/2024/world_countries.provenance.json`.

## population_raster_2025
- artefact_id: population_raster_2025
- deprecated_path: none
- new_path: reference/spatial/population/2025/population.tif
- realism_checks:
  - WorldPop Global 2025 constrained 1km raster downloaded and stored as COG with overviews [2,4,8,16].
  - CRS verified as EPSG:4326; resolution ~0.0083333333 degrees; tiled with internal blocks.
  - Provenance with raw/output sha256 and release statement checksum recorded in `reference/spatial/population/2025/population.provenance.json`.

## tz_world_2025a
- artefact_id: tz_world_2025a
- deprecated_path: reference/spatial/tz_world/2025a/deprecated_tz_world.parquet
- new_path: reference/spatial/tz_world/2025a/tz_world.parquet
- realism_checks:
  - timezone-boundary-builder 2025a with oceans shapefile used; tzid validated and polygon parts exploded.
  - Deterministic polygon_id ordering by geodesic area, bbox, centroid, and WKB hash; row count = 1175.
  - Provenance with raw/output sha256 and invalid tzid counts recorded in `reference/spatial/tz_world/2025a/tz_world.provenance.json`.

## mcc_canonical_2025-12-31
- artefact_id: mcc_canonical_2025-12-31
- deprecated_path: none
- new_path: reference/industry/mcc_canonical/2025-12-31/mcc_canonical.parquet
- realism_checks:
  - Alipay+ MCC list (Apr 2024 release) Table A1 parsed; non-ISO tables excluded.
  - MCCs validated in [0..9999] with non-empty descriptions; row count = 290.
  - Provenance recorded at `reference/industry/mcc_canonical/2025-12-31/mcc_canonical.provenance.json` with raw/output sha256.

## world_bank_gdp_per_capita_20250415
- artefact_id: world_bank_gdp_per_capita_20250415
- deprecated_path: reference/economic/world_bank_gdp_per_capita/2025-04-15/deprecated_gdp.parquet
- new_path: reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet
- realism_checks:
  - WDI API used for NY.GDP.PCAP.KD (2024) after archives page returned 403; ISO2 filtered to iso3166 canonical.
  - GDP values constrained to >0; PK uniqueness enforced on (country_iso, observation_year).
  - Provenance recorded at `reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.provenance.json` with raw/output sha256 and is_exact_vintage=false.

## gdp_bucket_map_2024
- artefact_id: gdp_bucket_map_2024
- deprecated_path: none
- new_path: reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet
- realism_checks:
  - Fisher-Jenks (k=5) computed deterministically on 2024 GDP per capita values; all buckets non-empty.
  - Bucket assignments follow [min,b1], (b1,b2], (b2,b3], (b3,b4], (b4,max] intervals.
  - Provenance with breakpoints and input/output sha256 recorded at `reference/economic/gdp_bucket_map/2024/gdp_bucket_map.provenance.json`.

## transaction_schema_merchant_ids_2025-12-31
- artefact_id: transaction_schema_merchant_ids
- deprecated_path: none
- new_path: reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.parquet
- realism_checks:
  - Closed-world authored using bootstrap config `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml` (Philox RNG).
  - Ensured min distinct home countries (>=50) and MCCs (>=200) with channel mix per MCC rules.
  - Provenance recorded at `reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.provenance.json` with config sha256 and counts.

## hurdle_simulation_priors
- artefact_id: hurdle_simulation_priors
- deprecated_path: config/models/hurdle/hurdle_simulation.priors.yaml (overwritten)
- new_path: config/models/hurdle/hurdle_simulation.priors.yaml
- realism_checks:
  - Added calibration/noise/clamp controls and MCC range effects per guide; dispersion MOM parameters pinned.
  - Updated semver/version to 1.0.0 / 2025-12-31 to align with current training inputs.

## numeric_policy_profile_2025-12-31
- artefact_id: numeric_policy_profile
- deprecated_path: none
- new_path: reference/governance/numeric_policy/2025-12-31/numeric_policy.json
- realism_checks:
  - Enforces IEEE-754 binary64, RNE rounding, FMA off, FTZ/DAZ off, and serial Neumaier reductions.
  - Matches v1 policy template for deterministic decision paths.
