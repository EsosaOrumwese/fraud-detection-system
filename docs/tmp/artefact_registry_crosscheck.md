# Artefact Registry vs Dictionary Cross-Check

## 1A

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`

### Present in dictionary + registry (datasets/logs)
- Ingress/reference: `transaction_schema_merchant_ids`, `world_bank_gdp_per_capita_20250415`, `gdp_bucket_map_2024`, `iso3166_canonical_2024`, `settlement_shares_2024Q4`, `ccy_country_shares_2024Q4`, `iso_legal_tender_2024`
- 1A caches/outputs: `crossborder_eligibility_flags`, `hurdle_pi_probs`, `hurdle_design_matrix`, `ccy_country_weights_cache`, `merchant_currency`, `sparse_flag`, `country_set`, `ranking_residual_cache_1A`, `crossborder_features`, `s3_candidate_set`, `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence`, `s6_membership`, `s6_validation_receipt`, `outlet_catalogue`
- Validation: `validation_bundle_1A`, `validation_passed_flag_1A`
- RNG logs: `rng_audit_log`, `rng_trace_log`, `rng_event_hurdle_bernoulli`, `rng_event_gamma_component`, `rng_event_poisson_component`, `rng_event_nb_final`, `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, `rng_event_ztp_final`, `rng_event_gumbel_key`, `rng_event_dirichlet_gamma_vector`, `rng_event_residual_rank`, `rng_event_sequence_finalize`, `rng_event_site_sequence_overflow`

### Registry-only config/policy artefacts (expected)
- `hurdle_coefficients.yaml` -> registry name `hurdle_coefficients`
- `nb_dispersion_coefficients.yaml` -> registry name `nb_dispersion_coefficients`
- `crossborder_hyperparams.yaml` -> registry name `crossborder_hyperparams`
- `ccy_smoothing_params.yaml` -> registry name `ccy_smoothing_params`
- `s6_selection_policy.yaml` -> registry name `s6_selection_policy`
- `validation_policy.yaml` -> registry name `validation_policy`
- `policy.s3.rule_ladder.yaml`, `policy.s3.base_weight.yaml`, `policy.s3.thresholds.yaml` (all registry policy entries)
- `math_profile_manifest.json` -> registry name `math_profile_manifest`
- `numeric_policy.json` -> registry uses `numeric_policy_profile`
- `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml` -> registry name `transaction_schema_merchant_ids_bootstrap_policy`

### Alias or mismatch vs dictionary/registry ids
- `merchant_ids` -> dictionary/registry use `transaction_schema_merchant_ids`
- `gamma_component`, `poisson_component`, `nb_final` -> dictionary/registry use `rng_event_gamma_component`, `rng_event_poisson_component`, `rng_event_nb_final`
- `rng_event.gumbel_key` -> `rng_event_gumbel_key`
- `rng_event.nb_final` -> `rng_event_nb_final`
- `rng_event.ztp_final` -> `rng_event_ztp_final`
- `rng_event.residual_rank` -> `rng_event_residual_rank`
- `rng_event.dirichlet_gamma_vector` -> `rng_event_dirichlet_gamma_vector`
- `rng_event.sequence_finalize` -> `rng_event_sequence_finalize`
- `rng_event.site_sequence_overflow` -> `rng_event_site_sequence_overflow`
- `_passed.flag` -> dictionary/registry id `validation_passed_flag_1A` (path ends with `_passed.flag`)
- `s3_candidate_set.candidate_rank` -> column in `s3_candidate_set`, not a dataset id
- `static.currency_to_country.map.json` -> not found in 1A dictionary/registry (may live elsewhere)

### Bundle members / sidecars / failure markers (not expected as standalone registry entries)
- `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`
- `DICTIONARY_LINT.txt`, `SCHEMA_LINT.txt`, `index.json`, `schema_checks.json`, `rng_accounting.json`, `metrics.csv`, `diffs`
- `_manifest.json`, `_MANIFEST.json`
- `S5_VALIDATION.json`, `S6_VALIDATION.json`, `S6_VALIDATION_DETAIL.jsonl`, `s8_metrics.json`, `egress_checksums.json`, `s9_summary.json`
- `failure.json`, `_FAILED.SENTINEL.json`, `_FAILED.json`, `merchant_abort_log`

## 1B

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`

### Present in dictionary + registry (datasets/logs)
- Upstream 1A surfaces: `validation_bundle_1A`, `outlet_catalogue`, `s3_candidate_set`
- Reference/FK targets: `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a`
- 1B outputs: `s0_gate_receipt_1B`, `tile_index`, `tile_weights`, `s3_requirements`, `s4_alloc_plan`, `s5_site_tile_assignment`, `s6_site_jitter`, `tile_bounds`, `s7_site_synthesis`, `site_locations`
- RNG logs: `rng_audit_log`, `rng_trace_log`, `rng_event_in_cell_jitter`, `rng_event_site_tile_assign`

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> upstream 1A flag is `validation_passed_flag_1A` (bundle member, not a 1B artefact id)
- `site_tile_assign` -> `rng_event_site_tile_assign`
- `numeric_policy.json`, `math_profile_manifest.json` -> not found in 1B dictionary/registry (likely governed cross-layer elsewhere)
- `dataset_dictionary.layer1.1A.yaml`, `dataset_dictionary.layer1.1B.yaml` -> doc references, not artefact ids
- `index.json` -> validation bundle member, not an artefact id

### Run-report metric keys / counters (not standalone artefact ids)
- `s1_run_report.json`, `s2_run_report.json`
- `rows_emitted`, `merchants_total`, `countries_total`, `source_rows_total`, `ingress_versions`, `determinism_receipt`
- `n_sites_total`, `fk_country_violations`, `coverage_missing_countries`, `merchant_id`, `legal_country_iso`
- `pairs_total`, `alloc_sum_equals_requirements`, `tile_not_in_index`
- `rng_events_emitted`, `sites_total`, `tiles_distinct`, `assignments_by_country`
- `expected_events`, `actual_events`, `quota_mismatches`, `dup_sites`
- `identity`, `counts`, `validation_counters`, `by_country`
- `rng.events_total`, `rng.draws_total`, `rng.blocks_total`, `rng.counter_span`
- `fk_tile_index_failures`, `point_outside_pixel`, `point_outside_country`, `path_embed_mismatches`
- `sites`, `rng_events`, `rng_draws`, `outside_pixel`, `outside_country`, `in_cell_jitter`
- `blocks=1`, `draws="2"`, `sigma_lat_deg=0.0`, `sigma_lon_deg=0.0`, `MAX_ATTEMPTS`
- `sizes`, `gates`
- `S3_ERROR`, `S4_ERROR`, `S5_ERROR`

### Bundle members / sidecars (not expected as standalone registry entries)
- `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`
- `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`

## 2A

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/dataset_dictionary.layer1.2A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/artefact_registry_2A.yaml`

### Present in dictionary + registry (datasets/logs)
- Upstream 1B surfaces: `validation_bundle_1B`, `validation_passed_flag_1B`, `site_locations`
- 2A control-plane: `s0_gate_receipt_2A`, `sealed_inputs_v1`
- 2A data-plane: `tz_nudge`, `s1_tz_lookup`, `tz_overrides`, `site_timezones`, `tzdb_release`, `tz_timetable_cache`, `s4_legality_report`
- 2A validation: `validation_bundle_2A`, `validation_passed_flag_2A`

### Dictionary-only (missing from registry)
- `iso3166_canonical_2024` (present in 2A dictionary; not listed in 2A registry)

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> `validation_passed_flag_1B` / `validation_passed_flag_2A` (bundle member, not a dataset id)
- `tz_world_<release>` -> dictionary/registry uses concrete ids (e.g. `tz_world_2025a` in Layer-1; check owning segment)
- `bundle_index_v1` -> bundle index member, not a dataset id

### Run-report or section header tokens (not artefact ids)
- `GATE`, `SEAL`, `HASH`, `EMIT`, `DETERMINISM`, `VALIDATION`, `INPUTS`, `LOOKUP`
- `TZDB_PARSE`, `COMPILE`, `CANONICALISE`, `COVERAGE`, `CHECK`, `DISCOVERY`, `EVIDENCE`, `INDEX`, `DIGEST`
- `nudge_*`, `OVERRIDES`, `created_utc`, `verified_at_utc`, `generated_utc`, `[fingerprint]`

### Bundle members / sidecars (not expected as standalone registry entries)
- `tzdata2025a.tar.gz`, `zoneinfo_version.yml`

## 2B

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`

### Present in dictionary + registry (datasets/logs)
- Upstream surfaces: `validation_bundle_1B`, `site_locations`, `site_timezones`, `tz_timetable_cache`
- 2B control-plane: `s0_gate_receipt_2B`, `sealed_inputs_v1`
- 2B outputs: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`, `s5_selection_log`, `s6_edge_log`, `s7_audit_report`
- 2B policies: `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, `virtual_edge_policy_v1`

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> upstream 1B flag is `validation_passed_flag_1B` (bundle member, not a 2B artefact id)
- `index.json` -> validation bundle member, not a dataset id

### Run-report or field tokens (not artefact ids)
- `created_utc`, `verified_at_utc`, `merchant_id`, `blob_sha256`, `gamma`, `routing_edge`
- `rng_event.alias_pick_group`, `rng_event.alias_pick_site`, `rng_event.cdn_edge_pick`

### Bundle members / sidecars (not expected as standalone registry entries)
- `index.json`

## 3A

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml`

### Present in dictionary + registry (datasets/logs)
- 3A control-plane: `s0_gate_receipt_3A`, `sealed_inputs_3A`
- 3A policies/data: `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`
- 3A plan outputs: `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, `zone_alloc_universe_hash`
- 3A validation artefacts: `s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`, `validation_bundle_3A`, `validation_passed_flag_3A`

### Dictionary-only (missing from registry)
- Upstream/context pins: `outlet_catalogue`, `site_timezones`, `tz_timetable_cache`, `iso3166_canonical_2024`, `tz_world_2025a`, `day_effect_policy_v1`

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> upstream validation flag ids are `validation_passed_flag_*` (bundle member, not a dataset id)
- `validation_bundle_1A`, `validation_bundle_1B`, `validation_bundle_2A` -> upstream bundle ids (may not be listed in 3A registry)
- `zone_mixture_policy_3A`, `country_zone_alphas_3A`, `zone_floor_policy_3A` -> spec references include suffix; dictionary/registry use `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`
- `zone_mixture_policy.yml`, `country_zone_alphas.yaml`, `zone_floor.yml` -> example filenames; dictionary/registry ids are `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`
- `day_effect_policy_v1.json` -> policy id `day_effect_policy_v1` (governed in 2B; referenced by 3A)
- `tz_world` -> placeholder in spec; dictionary pins `tz_world_2025a`
- `sealed_inputs_v1` -> schema alias mentioned in spec; dataset id is `sealed_inputs_3A`
- `s4_legality_report` -> 2A output referenced as optional diagnostics; not in 3A registry/dictionary
- `dataset_dictionary.layer1.1A.yaml` .. `dataset_dictionary.layer1.3A.yaml`, `artefact_registry_1A.yaml` .. `artefact_registry_3A.yaml` -> doc references, not artefact ids

### Run-report or field tokens (not artefact ids)
- `created_utc`, `country_tz_universe`, `site_count`
- `status="PASS"`, `s6_receipt_3A.overall_status="PASS"`

### Bundle members / sidecars (not expected as standalone registry entries)
- `index.json`
- `tz_index_manifest` (not in 3A dictionary/registry; referenced in spec)

## 3B

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/dataset_dictionary.layer1.3B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/artefact_registry_3B.yaml`

### Present in dictionary + registry (datasets/logs)
- Upstream input: `site_locations`
- 3B governed inputs: `mcc_channel_rules`, `virtual_settlement_coords`, `cdn_country_weights`, `virtual_validation_policy`, `hrsl_raster`, `cdn_weights_ext_yaml`, `pelias_cached_sqlite`
- 3B outputs: `s0_gate_receipt_3B`, `sealed_inputs_3B`, `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_catalogue_index_3B`, `edge_alias_blob_3B`, `edge_alias_index_3B`, `edge_universe_hash_3B`, `gamma_draw_log_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`, `s4_run_summary_3B`, `validation_bundle_3B`, `validation_bundle_index_3B`, `validation_passed_flag_3B`, `s5_manifest_3B`

### Registry-only policy/config artefacts referenced by state specs
- `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, `cdn_key_digest` (present in registry; not listed in 3B dictionary)

### Alias or mismatch vs dictionary/registry ids
- `mcc_channel_rules.yaml` -> registry/dictionary id `mcc_channel_rules`
- `cdn_country_weights.yaml` -> `cdn_country_weights`
- `virtual_validation.yml` -> `virtual_validation_policy`
- `virtual_settlement_coords.csv` -> `virtual_settlement_coords`
- `virtual_settlement_coords.parquet` -> not in dictionary/registry (dictionary uses CSV)
- `edge_alias_layout_policy_v1` -> registry policy id `alias_layout_policy_v1`
- `cdn_rng_policy_v1` -> not found in dictionary/registry (spec example; closest is `route_rng_policy_v1` + `cdn_key_digest`)
- `virtual_classification`, `virtual_settlement`, `edge_catalogue`, `edge_alias_blob`, `edge_alias_index`, `edge_universe_hash` -> spec uses generic names; dictionary/registry use `_3B` suffixed ids
- `validation_bundle_index_3B/index.json`, `_passed.flag`, `s5_manifest_3B.json` -> file names inside bundle; dataset ids are `validation_bundle_index_3B`, `validation_passed_flag_3B`, `s5_manifest_3B`

### Upstream artefacts referenced in state specs but not in 3B dictionary/registry
- `outlet_catalogue`, `site_timezones`, `tz_timetable_cache`, `zone_alloc`, `zone_alloc_universe_hash`, `merchant_ids`

### RNG logs/events referenced but not in 3B dictionary/registry
- `rng_audit_log`, `rng_trace_log`, `rng_event_edge_tile_assign`, `rng_event_edge_jitter`
