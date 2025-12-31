# Evidence - Layer 1 Data Intake

Created: 2025-12-31
Purpose: record new paths and realism checks per artefact.

Use one section per artefact:
- artefact_id:
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

## numeric_policy_profile_2025-12-31
- artefact_id: numeric_policy_profile
- deprecated_path: reference/governance/numeric_policy/2025-12-31/deprecated_numeric_policy_2025-12-31.json
- new_path: reference/governance/numeric_policy/2025-12-31/numeric_policy.json
- realism_checks:
  - Enforces IEEE-754 binary64, RNE rounding, FMA off, FTZ/DAZ off, and serial Neumaier reductions.
  - Removed redundant synonymous keys to avoid drift (single source of truth for rounding/FMA/FTZ fields).

## math_profile_manifest_openlibm-v0.8.7
- artefact_id: math_profile_manifest
- deprecated_path: none
- new_path: reference/governance/math_profile/openlibm-v0.8.7/math_profile_manifest.json
- realism_checks:
  - Built OpenLibm v0.8.7 from the pinned tarball with deterministic flags (no fast-math, no FMA contraction) under WSL Ubuntu 24.04.2 / GCC 13.3.0.
  - Ran `make test` (double/float test suites) and copied the built `libopenlibm.so` into `reference/governance/math_profile/openlibm-v0.8.7/`.
  - Manifest includes sha256 for `openlibm-v0.8.7.tar.gz` and `libopenlibm.so` plus checksum over canonical JSON with required function set.

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

## policy_s3_thresholds_2024-12-31
- artefact_id: policy.s3.thresholds.yaml
- deprecated_path: config/policy/deprecated_s3.thresholds_2024-12-31.yaml
- new_path: config/policy/s3.thresholds.yaml
- realism_checks:
  - Bounded Hamilton thresholds enforce home minimum and at least one foreign when foreigns exist, without forcing one-per-country.
  - Parameters aligned to current N distribution (median 1, q90 5 from hurdle sim).

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
  - Scaled base-share Dirichlet with total_concentration=24 and home_boost_multiplier=1.25 to keep home bias without collapsing foreign mass.
  - Alpha clamps tightened (min 0.03, max 150) to limit extreme draws while keeping randomness.


## license_map_2025-12-31
- artefact_id: license_map
- deprecated_path: licenses/deprecated_license_map_2025-12-31.yaml
- new_path: licenses/license_map.yaml
- realism_checks:
  - Re-authored attribution templates to reflect actual upstream sources (World Bank CC BY, ODbL/OSM, public domain sources).
  - Added SEE-FILES entry for multi-license artefacts with `LICENSES/SEE-FILES.txt` notice file.
  - Normalized layer-1 license keys to match license_map canonical values (CC-BY-4.0, Public-Domain, Proprietary-Internal, SEE-FILES).

## hurdle_simulation_priors_2025-12-31
- artefact_id: hurdle_simulation_priors
- new_path: config/models/hurdle/hurdle_simulation.priors.yaml
- realism_checks:
  - Semver 1.2.0 calibrated to the current 50k merchant universe (mean_pi_target=0.16, mean_mu_target_multi=6.5, median_phi_target=45.0).
  - MCC offsets aligned to the top observed merchant MCCs (54xx grocery, 58xx dining, 55xx auto) with negative offsets for digital/high-risk codes.
  - Channel and GDP-bucket offsets preserve higher multi-site propensity in CP and higher-income buckets while keeping clamps corridor-safe.

## hurdle_coefficients_2025-12-31
- artefact_id: hurdle_coefficients
- new_path: config/models/hurdle/exports/version=2025-12-31/20251231T134200Z/hurdle_coefficients.yaml
- realism_checks:
  - Offline simulation + deterministic design + ridge IRLS fit via `scripts/build_hurdle_exports.py`.
  - Training manifest recorded at `artefacts/training/1A/hurdle_sim/simulation_version=2025-12-31/seed=9248923/20251231T134200Z/manifest.json`.
  - Belt-and-braces selfcheck recorded at `config/models/hurdle/exports/version=2025-12-31/20251231T134200Z/bundle_selfcheck.json`.

## nb_dispersion_coefficients_2025-12-31
- artefact_id: nb_dispersion_coefficients
- new_path: config/models/hurdle/exports/version=2025-12-31/20251231T134200Z/nb_dispersion_coefficients.yaml
- realism_checks:
  - MOM phi targets computed with pooling thresholds from priors; dict_mcc/dict_ch aligned with hurdle export.
  - Selfcheck bundle recorded alongside hurdle export for deterministic validation.

## policy_s3_rule_ladder_2025-12-31
- artefact_id: policy.s3.rule_ladder.yaml
- new_path: config/policy/s3.rule_ladder.yaml
- realism_checks:
  - Channel enums aligned to `card_present`/`card_not_present` to match ingress schema.
  - High-risk CNP deny list expanded to include digital goods MCCs and cash-like categories.
  - GLOBAL_CORE set extended to include major economies and payment hubs observed in the merchant universe; sanctions list pinned to 2025-12-31 vintage.

## policy_s3_base_weight_2025-12-31
- artefact_id: policy.s3.base_weight.yaml
- new_path: config/policy/s3.base_weight.yaml
- realism_checks:
  - Semver 1.2.0 with beta_home=1.25 and beta_rank=-0.10 to keep home competitive while preserving foreign tail mass.
  - Quantisation dp=7 with w_min=1e-7 to avoid zeroing weights after rounding.

## crossborder_hyperparams_2025-12-31
- artefact_id: crossborder_hyperparams
- new_path: config/policy/crossborder_hyperparams.yaml
- realism_checks:
  - Eligibility rules deny sanctioned homes and high-risk CNP MCCs, allow travel/transport and CNP retail, and whitelist major hub home countries.
  - ZTP link uses ordered coefficients with clamp01 feature transform and deterministic exhaustion policy.

## ccy_smoothing_params_2025-12-31
- artefact_id: ccy_smoothing_params
- new_path: config/allocation/ccy_smoothing_params.yaml
- realism_checks:
  - Defaults blend ccy-country and settlement shares with light alpha smoothing and dp=7 output precision.
  - Per-currency overrides tuned for EUR/USD and currency unions (XOF/XAF/XCD/XPF) to prevent uniform artifacts.

## s6_selection_policy_2025-12-31
- artefact_id: s6_selection_policy
- new_path: config/policy.s6.selection.yaml
- realism_checks:
  - Default cap 25 preserves non-trivial candidate sets; EUR override allows the full union candidate set.
  - Membership emission and full logging enabled for deterministic replay.

## tzdb_release_2025a
- artefact_id: tzdb_release
- new_path: artefacts/priors/tzdata/2025a/
- realism_checks:
  - Pinned release_tag to 2025a to align with tz_world_2025a coverage.
  - archive_sha256 computed from tzdata2025a.tar.gz bytes and recorded in tzdb_release.json.
  - Provenance recorded with file size and sha256 in tzdb_release.provenance.json.

## tz_nudge_2025-12-31
- artefact_id: tz_nudge
- new_path: config/timezone/tz_nudge.yml
- realism_checks:
  - epsilon_degrees set to 0.000005 (~0.55m) to break border ties without relocating sites materially.
  - sha256_digest computed from the semver+epsilon payload per the guide and recorded in the policy file.

## tz_overrides_2025-12-31
- artefact_id: tz_overrides
- new_path: config/timezone/tz_overrides.yaml
- realism_checks:
  - Empty override list to avoid unverified tzid pins; no MCC-scope overrides enabled without a sealed merchant_mcc_map.

## route_rng_policy_v1
- artefact_id: route_rng_policy_v1
- new_path: contracts/policy/2B/route_rng_policy_v1.json
- realism_checks:
  - Philox2x64-10 with `routing_selection` and `routing_edge` streams; event budgets are single-uniform per arrival (2 for S5, 1 for S6).
  - Stream IDs are namespaced (`2B.routing`, `2B.routing_edge`) and key_basis is `[seed, parameter_hash, run_id]`.

## alias_layout_policy_v1
- artefact_id: alias_layout_policy_v1
- new_path: contracts/policy/2B/alias_layout_policy_v1.json
- realism_checks:
  - Quantised_bits=24, prob_qbits=32, and `walker_vose_q0_32` decode law pinned; deterministic residual adjustment rules included.
  - Floor_spec uses absolute floor 1e-12 with uniform fallback and normalisation_epsilon=1e-9 to keep alias weights stable.

## day_effect_policy_v1
- artefact_id: day_effect_policy_v1
- new_path: contracts/policy/2B/day_effect_policy_v1.json
- realism_checks:
  - Day range is 2024-01-01 through 2025-12-31 (inclusive), meeting the multi-year volume floor.
  - Sigma_gamma=0.32 with Philox2x64-10 and deterministic key/counter derivation; sha256_hex computed per canonical JSON rules.

## virtual_edge_policy_v1
- artefact_id: virtual_edge_policy_v1
- new_path: contracts/policy/2B/virtual_edge_policy_v1.json
- realism_checks:
  - 2000 edges with deterministic ip_country/edge_id ordering and weights normalized to sum=1; heavy-tail check passes via top-5% mass ≥30%.
  - Edge catalogue derived from iso3166_canonical_2024 + world_countries + population_raster_2025 with POP fallback for raster gaps and synthetic candidate grids for countries with insufficient raster cells (e.g., Antarctica).
  - Allocation uses k_alloc=Q^0.30 to avoid flat weights under current inputs; missing world_countries ISO2 polygons (15/250) excluded with notes in the policy file.
