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

## iso_legal_tender_2024
- artefact_id: iso_legal_tender_2024
- deprecated_path: reference/iso/iso_legal_tender/2024/deprecated_iso_legal_tender.parquet
- new_path: reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet
- realism_checks:
  - SIX List One XML parsed with deterministic name normalization + alias map; non-tender codes excluded.
  - Primary tender currency selected per ISO2 using minor-unit preference then alpha sort; unmapped entities logged.
  - Provenance recorded at `reference/iso/iso_legal_tender/2024/iso_legal_tender.provenance.json` with is_exact_vintage=false.

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
- deprecated_path: config/models/hurdle/deprecated_hurdle_simulation.priors_2025-12-31.yaml
- new_path: config/models/hurdle/hurdle_simulation.priors.yaml
- realism_checks:
  - Re-authored MCC offsets using the actual top MCCs in `transaction_schema_merchant_ids` (food/retail + auto supply codes) plus negative offsets for digital-only/financial MCCs.
  - Set channel offsets based on observed CP/CNP mix (CP-heavy) and monotone GDP bucket offsets from `gdp_bucket_map_2024`.
  - Updated semver/version to 1.1.0 / 2025-12-31; calibration targets set for realistic multi-site rates and dispersion.

## hurdle_coefficients_2025-12-31
- artefact_id: hurdle_coefficients
- deprecated_path: none (new export run; prior exports remain under version=2025-10-09)
- new_path: config/models/hurdle/exports/version=2025-12-31/20251231T084444Z/hurdle_coefficients.yaml
- realism_checks:
  - Offline simulation + deterministic design + ridge IRLS fit via `scripts/build_hurdle_exports.py`.
  - Dictionary orders: dict_mcc from merchant universe; dict_ch=[CP,CNP]; dict_dev5=[1..5].
  - Belt-and-braces lock PASS recorded in `config/models/hurdle/exports/version=2025-12-31/20251231T084444Z/bundle_selfcheck.json`.
  - Training manifest with input digests stored at `artefacts/training/1A/hurdle_sim/simulation_version=2025-12-31/seed=9248923/20251231T084444Z/manifest.json`.

## nb_dispersion_coefficients_2025-12-31
- artefact_id: nb_dispersion_coefficients
- deprecated_path: none (new export run; prior exports remain under version=2025-10-09)
- new_path: config/models/hurdle/exports/version=2025-12-31/20251231T084444Z/nb_dispersion_coefficients.yaml
- realism_checks:
  - MOM phi targets computed per (mcc, channel, gdp_bucket) with pooling and clamp rules from priors.
  - dict_mcc/dict_ch aligned to paired hurdle export; beta_phi order includes ln_gdp_pc_usd_2015.
  - Belt-and-braces lock PASS recorded alongside hurdle export.

## numeric_policy_profile_2025-12-31
- artefact_id: numeric_policy_profile
- deprecated_path: reference/governance/numeric_policy/2025-12-31/deprecated_numeric_policy_2025-12-31.json
- new_path: reference/governance/numeric_policy/2025-12-31/numeric_policy.json
- realism_checks:
  - Enforces IEEE-754 binary64, RNE rounding, FMA off, FTZ/DAZ off, and serial Neumaier reductions.
  - Removed redundant synonymous keys to avoid drift (single source of truth for rounding/FMA/FTZ fields).

## validation_policy_2024-12-31
- artefact_id: validation_policy
- deprecated_path: config/policy/deprecated_validation_policy_2024-12-31.yaml
- new_path: config/policy/validation_policy.yaml
- realism_checks:
  - CUSUM parameters set to reference_k=0.45, threshold_h=9.0 for a 50k-merchant universe (sustained drift sensitivity without hypersensitivity).
  - File is a sealed governance input; missing policy fails closed by spec.

## residual_quantisation_policy_2024-12-31
- artefact_id: residual_quantisation_policy
- deprecated_path: config/numeric/deprecated_residual_quantisation_2024-12-31.yaml
- new_path: config/numeric/residual_quantisation.yaml
- realism_checks:
  - dp_resid=7 chosen to preserve minimum ccy_country_shares precision while keeping deterministic largest-remainder behaviour.
  - Stable residual sort with deterministic tiebreaks (country_iso, merchant_id).

## policy_s3_rule_ladder_2025-12-31
- artefact_id: policy.s3.rule_ladder.yaml
- deprecated_path: config/policy/deprecated_s3.rule_ladder_2025-12-31.yaml
- new_path: config/policy/s3.rule_ladder.yaml
- realism_checks:
  - Structured predicate DSL with closed vocab, explicit precedence order, and terminal DEFAULT.
  - Authored country sets (GLOBAL_CORE, SANCTIONED) include major economies and a sanctions list with vintage note.
  - Admit-bearing rules target travel/retail MCC ranges and multi-site merchants; high-risk CNP MCCs are denied.

## policy_s3_base_weight_2024-12-31
- artefact_id: policy.s3.base_weight.yaml
- deprecated_path: config/policy/deprecated_s3.base_weight_2024-12-31.yaml
- new_path: config/policy/s3.base_weight.yaml
- realism_checks:
  - Loglinear home/rank prior tuned for ~25-country candidate sets with dp=7 quantisation.
  - Home bias (exp(1.4) ~4x) and rank decay (-0.12 per rank) keep top foreigns competitive without collapsing the tail.

## policy_s3_thresholds_2024-12-31
- artefact_id: policy.s3.thresholds.yaml
- deprecated_path: config/policy/deprecated_s3.thresholds_2024-12-31.yaml
- new_path: config/policy/s3.thresholds.yaml
- realism_checks:
  - Bounded Hamilton thresholds enforce home minimum and at least one foreign when foreigns exist, without forcing one-per-country.
  - Parameters aligned to current N distribution (median 7, q90 13 from hurdle sim).

## crossborder_hyperparams_2025-12-31
- artefact_id: crossborder_hyperparams
- deprecated_path: config/policy/deprecated_crossborder_hyperparams_2025-12-31.yaml
- new_path: config/policy/crossborder_hyperparams.yaml
- realism_checks:
  - Eligibility rules deny sanctioned homes and high-risk CNP MCCs; allow CP retail/travel ranges and selected low-risk CNP MCCs.
  - Eligibility rate ~58% on the current merchant universe (non-degenerate).
  - ZTP parameters calibrated for N~7 median (lambda_extra ~1.8) with clamp01 X and downgrade-domestic fallback.

## ccy_country_shares_2024Q4
- artefact_id: ccy_country_shares_2024Q4
- deprecated_path: none
- new_path: reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet
- realism_checks:
  - Currency membership derived from SIX List One XML; GDP-weighted splits (WDI NY.GDP.MKTP.CD 2024) with floor for missing GDP.
  - BIS D11.3 (2022) used for obs_count mass; largest-remainder allocation with ISO tie-break.
  - Provenance recorded at `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.provenance.json` with is_exact_vintage=false.

## settlement_shares_2024Q4
- artefact_id: settlement_shares_2024Q4
- deprecated_path: none
- new_path: reference/network/settlement_shares/2024Q4/settlement_shares.parquet
- realism_checks:
  - Route B proxy anchored to ccy_country_shares with BIS D11.2 hub weights and D11.3 currency totals.
  - Hub mass tuned by currency concentration; obs_count allocated by largest remainder.
  - Provenance recorded at `reference/network/settlement_shares/2024Q4/settlement_shares.provenance.json`.

## dirichlet_alpha_policy_2024-12-31
- artefact_id: dirichlet_alpha_policy
- deprecated_path: config/models/allocation/deprecated_dirichlet_alpha_policy_2024-12-31.yaml
- new_path: config/models/allocation/dirichlet_alpha_policy.yaml
- realism_checks:
  - Scaled base-share Dirichlet with total_concentration=25 and home_boost_multiplier=1.30 for ~25-country candidate sets.
  - Alpha clamps tightened (min 0.03, max 150) to limit extreme draws while keeping randomness.

## ccy_smoothing_params_2024-12-31
- artefact_id: ccy_smoothing_params
- deprecated_path: config/allocation/deprecated_ccy_smoothing_params_2024-12-31.yaml
- new_path: config/allocation/ccy_smoothing_params.yaml
- realism_checks:
  - Blend+shrink defaults keyed off obs_count floor (5000) with dp=7 output precision aligned to ccy_country_shares min share.
  - Per-currency overrides added for multi-country currencies (EUR, USD, XOF, XAF, XCD, AUD) to avoid uniform artifacts.

## s6_selection_policy_2024-12-31
- artefact_id: s6_selection_policy
- deprecated_path: config/deprecated_policy.s6.selection_2024-12-31.yaml
- new_path: config/policy.s6.selection.yaml
- realism_checks:
  - Selection policy emits membership dataset, logs all candidates, and caps candidate count at 25 by default.
  - Per-currency caps added for multi-country currencies (EUR, USD, XCD, XOF, XAF, AUD).

## license_map_2025-12-31
- artefact_id: license_map
- deprecated_path: licenses/deprecated_license_map_2025-12-31.yaml
- new_path: licenses/license_map.yaml
- realism_checks:
  - Re-authored attribution templates to reflect actual upstream sources (World Bank CC BY, ODbL/OSM, public domain sources).
  - Added SEE-FILES entry for multi-license artefacts with `LICENSES/SEE-FILES.txt` notice file.
  - Normalized layer-1 license keys to match license_map canonical values (CC-BY-4.0, Public-Domain, Proprietary-Internal, SEE-FILES).
