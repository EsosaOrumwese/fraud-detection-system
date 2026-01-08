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

### Dictionary-only (missing from registry)
- `s1_run_report_3B`, `s2_run_report_3B`, `s3_run_report_3B`, `s4_run_report_3B`, `s5_run_report_3B`

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
- `virtual_classification`, `virtual_settlement`, `edge_catalogue`, `edge_catalogue_index`, `edge_alias_blob`, `edge_alias_index`, `edge_universe_hash`, `cdn_alias` -> spec uses generic names; dictionary/registry use `_3B` suffixed ids
- `validation_bundle_index_3B/index.json`, `_passed.flag`, `s5_manifest_3B.json` -> file names inside bundle; dataset ids are `validation_bundle_index_3B`, `validation_passed_flag_3B`, `s5_manifest_3B`
- `s5_run_summary_3B` -> optional alias in spec; not in dictionary/registry (use `s5_manifest_3B`)

### Upstream artefacts referenced in state specs but not in 3B dictionary/registry
- `outlet_catalogue`, `site_timezones`, `tz_timetable_cache`, `zone_alloc`, `zone_alloc_universe_hash`, `merchant_ids`

### RNG logs/events referenced but not in 3B dictionary/registry
- `rng_audit_log`, `rng_trace_log`, `rng_event_edge_tile_assign`, `rng_event_edge_jitter`

## 5A

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/dataset_dictionary.layer2.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/artefact_registry_5A.yaml`

### Present in dictionary + registry (datasets/configs)
- 5A policies/configs: `merchant_class_policy_5A`, `demand_scale_policy_5A`, `baseline_intensity_policy_5A`, `shape_library_5A`, `shape_time_grid_policy_5A`, `scenario_horizon_config_5A`, `scenario_metadata`, `scenario_calendar_5A`, `scenario_overlay_policy_5A`, `overlay_ordering_policy_5A`, `scenario_overlay_validation_policy_5A`
- 5A control-plane: `s0_gate_receipt_5A`, `sealed_inputs_5A`, `scenario_manifest_5A`
- 5A outputs: `merchant_zone_profile_5A`, `merchant_class_profile_5A`, `shape_grid_definition_5A`, `class_zone_shape_5A`, `class_shape_catalogue_5A`, `merchant_zone_baseline_local_5A`, `class_zone_baseline_local_5A`, `merchant_zone_baseline_utc_5A`, `merchant_zone_scenario_local_5A`, `merchant_zone_overlay_factors_5A`, `merchant_zone_scenario_utc_5A`
- 5A validation artefacts: `validation_bundle_5A`, `validation_bundle_index_5A`, `validation_report_5A`, `validation_issue_table_5A`, `validation_passed_flag_5A`
- Run reports: `segment_state_runs`, `s1_run_report_5A`, `s2_run_report_5A`, `s3_run_report_5A`, `s4_run_report_5A`, `s5_run_report_5A`
- Upstream bundles/flags: `validation_bundle_1A`, `validation_passed_flag_1A`, `validation_bundle_1B`, `validation_passed_flag_1B`, `validation_bundle_2A`, `validation_passed_flag_2A`, `validation_bundle_2B`, `validation_passed_flag_2B`, `validation_bundle_3A`, `validation_passed_flag_3A`, `validation_bundle_3B`, `validation_passed_flag_3B`
- Upstream data surfaces: `outlet_catalogue`, `site_locations`, `site_timezones`, `tz_timetable_cache`, `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`, `zone_alloc`, `zone_alloc_universe_hash`
- 3B virtual surfaces: `virtual_classification_3B`, `virtual_settlement_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`, `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`

### Dictionary-only (missing from registry)
- None (after alignment)

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> dictionary/registry id `validation_passed_flag_5A`
- `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, `schemas.5A.yaml` -> schema packs, not artefact ids
- `dataset_dictionary.layer1.1A.yaml` .. `dataset_dictionary.layer1.3B.yaml`, `dataset_dictionary.layer2.5A.yaml`, `artefact_registry_1A.yaml` .. `artefact_registry_3B.yaml`, `artefact_registry_5A.yaml` -> doc references, not artefact ids

### Upstream artefacts referenced in state specs but not in 5A dictionary/registry
- None (after alignment)

## 5B

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5B/artefact_registry_5B.yaml`

### Present in dictionary + registry (datasets/configs)
- 5B configs/policies: `time_grid_policy_5B`, `grouping_policy_5B`, `arrival_lgcp_config_5B`, `arrival_count_config_5B`, `arrival_time_placement_policy_5B`, `arrival_routing_policy_5B`, `arrival_rng_policy_5B`, `validation_policy_5B`, `bundle_layout_policy_5B`
- 5B control-plane: `s0_gate_receipt_5B`, `sealed_inputs_5B`
- 5B outputs: `s1_time_grid_5B`, `s1_grouping_5B`, `s2_realised_intensity_5B`, `s2_latent_field_5B`, `s3_bucket_counts_5B`, `arrival_events_5B`, `s4_arrival_summary_5B`, `s4_arrival_anomalies_5B`
- 5B validation artefacts: `validation_bundle_5B`, `validation_bundle_index_5B`, `validation_report_5B`, `validation_issue_table_5B`, `validation_passed_flag_5B`
- 5B RNG logs/events: `rng_audit_log`, `rng_trace_log`, `rng_event_arrival_lgcp_gaussian`, `rng_event_arrival_time_jitter`, `rng_event_arrival_site_pick`, `rng_event_arrival_edge_pick`
- Run-report journal: `segment_state_runs`

### Dictionary-only (missing from registry)
- None (5B dictionary + registry are aligned for the contract surfaces).

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> dictionary/registry id `validation_passed_flag_5B`
- `s4_arrival_events_5B` -> dictionary/registry id `arrival_events_5B`
- `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, `schemas.5A.yaml`, `schemas.5B.yaml` -> schema packs, not artefact ids
- `dataset_dictionary.layer1.1A.yaml` .. `dataset_dictionary.layer1.3B.yaml`, `dataset_dictionary.layer2.5A.yaml`, `dataset_dictionary.layer2.5B.yaml`, `artefact_registry_1A.yaml` .. `artefact_registry_3B.yaml`, `artefact_registry_5A.yaml`, `artefact_registry_5B.yaml` -> doc references, not artefact ids

### Upstream artefacts referenced in state specs but not in 5B dictionary/registry
- None (upstream bundles, routing surfaces, and 5A scenario inputs are registered as cross-layer pointers).

### RNG logs/events referenced but not in 5B dictionary/registry
- None (RNG logs and event tables are now contract entries; substream labels remain `arrival_time_jitter`, `arrival_site_pick`, `arrival_edge_pick`).

## 6A

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`

### Present in dictionary + registry (datasets/configs)
- 6A control-plane: `s0_gate_receipt_6A`, `sealed_inputs_6A`
- 6A priors/taxonomies/policies: `prior_population_6A`, `prior_segmentation_6A`, `taxonomy_party_6A`, `prior_account_per_party_6A`, `prior_product_mix_6A`, `taxonomy_account_types_6A`, `prior_instrument_per_account_6A`, `prior_instrument_mix_6A`, `taxonomy_instrument_types_6A`, `prior_device_counts_6A`, `taxonomy_devices_6A`, `prior_ip_counts_6A`, `taxonomy_ips_6A`, `taxonomy_fraud_roles_6A`, `prior_party_roles_6A`, `prior_account_roles_6A`, `prior_merchant_roles_6A`, `prior_device_roles_6A`, `prior_ip_roles_6A`, `validation_policy_6A`, `graph_linkage_rules_6A`, `device_linkage_rules_6A`, `product_linkage_rules_6A`, `product_eligibility_config_6A`, `instrument_linkage_rules_6A`
- 6A outputs: `s1_party_base_6A`, `s1_party_summary_6A`, `s2_account_base_6A`, `s2_party_product_holdings_6A`, `s2_merchant_account_base_6A`, `s2_account_summary_6A`, `s3_instrument_base_6A`, `s3_account_instrument_links_6A`, `s3_party_instrument_holdings_6A`, `s3_instrument_summary_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A`, `s4_entity_neighbourhoods_6A`, `s4_network_summary_6A`, `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`, `s5_validation_report_6A`, `s5_issue_table_6A`, `validation_bundle_6A`, `validation_bundle_index_6A`, `validation_passed_flag_6A`
- 6A RNG logs/events: `rng_audit_log`, `rng_trace_log`, `rng_event_party_count_realisation`, `rng_event_party_attribute_sampling`, `rng_event_account_count_realisation`, `rng_event_account_allocation_sampling`, `rng_event_account_attribute_sampling`, `rng_event_instrument_count_realisation`, `rng_event_instrument_allocation_sampling`, `rng_event_instrument_attribute_sampling`, `rng_event_device_count_realisation`, `rng_event_device_allocation_sampling`, `rng_event_device_attribute_sampling`, `rng_event_ip_count_realisation`, `rng_event_ip_allocation_sampling`, `rng_event_ip_attribute_sampling`, `rng_event_fraud_role_sampling_party`, `rng_event_fraud_role_sampling_account`, `rng_event_fraud_role_sampling_merchant`, `rng_event_fraud_role_sampling_device`, `rng_event_fraud_role_sampling_ip`

### Dictionary-only (missing from registry)
- None (after alignment).

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> dictionary/registry id `validation_passed_flag_6A`
- `POPULATION_PRIOR` -> `prior_population_6A`
- `SEGMENT_PRIOR` -> `prior_segmentation_6A`
- `PRODUCT_PRIOR` -> `prior_product_mix_6A` (+ `prior_account_per_party_6A` for account counts)
- `INSTRUMENT_PRIOR` -> `prior_instrument_mix_6A` (+ `prior_instrument_per_account_6A`)
- `DEVICE_PRIOR` -> `prior_device_counts_6A`
- `IP_PRIOR` / `ENDPOINT_PRIOR` -> `prior_ip_counts_6A`
- `FRAUD_ROLE_PRIOR` / `FRAUD_PRIOR` -> `prior_party_roles_6A`, `prior_account_roles_6A`, `prior_merchant_roles_6A`, `prior_device_roles_6A`, `prior_ip_roles_6A`
- `TAXONOMY` -> `taxonomy_party_6A`, `taxonomy_account_types_6A`, `taxonomy_instrument_types_6A`, `taxonomy_devices_6A`, `taxonomy_ips_6A`, `taxonomy_fraud_roles_6A`
- `GRAPH_LINKAGE_RULES` -> `graph_linkage_rules_6A`
- `DEVICE_LINKAGE_RULES` -> `device_linkage_rules_6A`
- `VALIDATION_POLICY_6A` / `SEGMENT_CHECKLIST_6A` -> `validation_policy_6A`
- `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`, `schemas.6A.yaml` -> schema packs, not artefact ids
- `dataset_dictionary.layer3.6A.yaml`, `artefact_registry_6A.yaml` -> doc references, not artefact ids

### Upstream artefacts referenced in state specs but not in 6A dictionary/registry
- None (after alignment).

### Run-report / field tokens (not artefact ids)
- `sealed_inputs_digest_6A`, `sealed_inputs_row_count`
- `spec_version_6A`, `upstream_gates_summary`, `prior_packs_summary`

### RNG logs/events referenced but not in 6A dictionary/registry
- None (now listed in 6A contracts).

## 6B

### Sources (docs/model_spec/data-engine)
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`

### Present in dictionary + registry (datasets/configs)
- 6B control-plane: `s0_gate_receipt_6B`, `sealed_inputs_6B`
- 6B policies/configs: `attachment_policy_6B`, `sessionisation_policy_6B`, `behaviour_config_6B`, `behaviour_prior_pack_6B`, `rng_profile_layer3`, `rng_policy_6B`, `flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B`, `flow_rng_policy_6B`, `fraud_campaign_catalogue_config_6B`, `fraud_overlay_policy_6B`, `fraud_rng_policy_6B`, `truth_labelling_policy_6B`, `bank_view_policy_6B`, `delay_models_6B`, `case_policy_6B`, `label_rng_policy_6B`, `segment_validation_policy_6B`
- 6B outputs: `s1_arrival_entities_6B`, `s1_session_index_6B`, `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`, `s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_event_labels_6B`, `s4_case_timeline_6B`
- 6B validation artefacts: `s5_validation_report_6B`, `s5_issue_table_6B`, `validation_bundle_6B`, `validation_passed_flag_6B`
- 6B RNG logs/events: `rng_audit_log`, `rng_trace_log`, `rng_event_flow_anchor_baseline`, `rng_event_event_stream_baseline`, `rng_event_fraud_campaign_pick`, `rng_event_fraud_overlay_apply`, `rng_event_truth_label`, `rng_event_bank_view_label`

### Alias or mismatch vs dictionary/registry ids
- `_passed.flag` -> dictionary/registry id `validation_passed_flag_6B`
- `validation_bundle_index_6B` -> not found in dictionary/registry (bundle is `validation_bundle_6B`)
- `validation_policy_6B` -> dictionary/registry use `segment_validation_policy_6B`
- `campaign_catalogue_config_6B` -> dictionary id is `fraud_campaign_catalogue_config_6B`
- `labelling_policy_6B` -> dictionary uses `truth_labelling_policy_6B`
- `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`, `schemas.6B.yaml` -> schema packs, not artefact ids
- `dataset_dictionary.layer3.6B.yaml`, `artefact_registry_6B.yaml` -> doc references, not artefact ids

### Upstream artefacts referenced in state specs but not in 6B dictionary/registry
- Upstream validation bundles/flags: `validation_bundle_*`, `_passed.flag` for segments 1A-6A
- Upstream sealed inputs: `sealed_inputs_5A`, `sealed_inputs_5B`, `sealed_inputs_6A`
- Upstream arrivals/entities: `arrival_events_5B`, `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s3_account_instrument_links_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`
- 6A fraud posture: `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`

### RNG logs/events referenced but not in 6B dictionary/registry
- None (now listed in 6B contracts).
