* Layer-1 Segment 1A — externals to acquire/author

      [M] Ingress (dataset)
      - transaction_schema_merchant_ids
            · cols: merchant_id, mcc, channel, home_country_iso
            · (optional but necessary if using closed-world Route B)
            - config/ingress/transaction_schema_merchant_ids.bootstrap.yaml  (binding bootstrap policy)

      [R] Reference artefacts
      - iso3166_canonical_2024
      - world_bank_gdp_per_capita_20250415
      - gdp_bucket_map_2024  (Jenks K=5; deterministic)

      [I] Share surfaces & ISO enumerations
      - settlement_shares_2024Q4
      - ccy_country_shares_2024Q4
      - (optional; only if producing merchant_currency)
            - iso_legal_tender_2024

      [C] Model coeff bundles (offline-trained)
      - hurdle_coefficients.yaml
      - nb_dispersion_coefficients.yaml

      [P] Policy / hyperparams / allocation
      - crossborder_hyperparams.yaml
      - policy.s3.rule_ladder.yaml
      - (opt) policy.s3.base_weight.yaml
      - (opt) policy.s3.thresholds.yaml
      - config/allocation/ccy_smoothing_params.yaml  (id: ccy_smoothing_params)
      - s6_selection_policy @ config/policy.s6.selection.yaml

      - (recommended / present in 1A contracts; include to stay “complete”)
            - config/models/allocation/dirichlet_alpha_policy.yaml     (used if Dirichlet lane enabled)
            - config/numeric/residual_quantisation.yaml                (pins residual rounding before rank)

      - (optional; only if any policy references it)
            - static.currency_to_country.map.json

      [N] Numeric / math governance
      - numeric_policy.json
      - math_profile_manifest.json

      [Compliance] Licence governance (required)
      - licenses/license_map.yaml (+ LICENSES/ folder if that’s your convention)

      [Validation knobs] (required)
      - validation_policy.yaml  (CUSUM corridor parameters used by 1A validation)


* Layer-1 Segment 1B — what it needs (v1)

      [Upstream gated inputs from 1A]  (not “shopped”, but required to exist)
      - outlet_catalogue  (seed + fingerprint-scoped)
      - validation_bundle_1A + _passed.flag  (S0 gate)

      - (optional / not consumed by 1B v1 states)
            - s3_candidate_set  (order authority for downstream joins, if needed elsewhere)

      [Refs / spatial priors]  (externals to acquire/author)
      - iso3166_canonical_2024
      - world_countries
      - population_raster_2025
      - (optional / reserved for later 2A/2B; not consumed by 1B v1)
            - tz_world_2025a

      [Policies · 1B]
      - (none for v1; jitter_policy intentionally excluded / reserved)

	
* Layer-1 Segment 2A
	[Policy] Inputs S0 will seal for 2A:
		- tzdb_release                        (IANA tzdata archive + tag/version)
		- tz_overrides                        (governed override registry: per-site / per-MCC / per-country rules)
		- tz_nudge                            (border-nudge epsilon + policy)

	[Optional] Merchant → MCC mapping
		- merchant_mcc_map (only if sealed in S0)
			· schema: schemas.ingress.layer1.yaml#/merchant_mcc_map_…
			· role: map merchant_id → mcc for MCC-scope overrides
			· if not sealed: MCC-scope overrides are unusable; using them MUST fail'


* Layer-1 Segment 2B
	[Policy] Inputs S0 will seal for 2B (minimum required set):
		- route_rng_policy_v1                (RNG sub-stream + budget policy for 2B routing states)
		- alias_layout_policy_v1             (alias-table byte layout, endianness, alignment)
		- day_effect_policy_v1               (daily gamma / effect policy for S3/S4)
		- virtual_edge_policy_v1             (defines canonical edge ordering and per-merchant edge distributions)


* Layer-1 Segment 3A
	[Policies & Priors · part of the parameter set]
		- zone_mixture_policy_3A       (mixture / escalation policy for S1; theta thresholds/buckets)
		- country_zone_alphas_3A      (Dirichlet α-pack per country×tzid for S2)
		- zone_floor_policy_3A        (floor/bump rules for S2/S4 integerisation)


* Layer-1 Segment 3B
	[Ingress / external artefacts S0 must seal for 3B]
		- Virtual classification rules:
			· mcc_channel_rules @ config/virtual/mcc_channel_rules.yaml
				(logical_id ≈ "virtual_rules" / manifest_key mlr.3B.config.virtual_rules)
		- Virtual settlement coordinate sources:
			· virtual_settlement_coords @ artefacts/virtual/virtual_settlement_coords.csv (or parquet)
		- CDN country mix policy:
			· cdn_country_weights @ config/virtual/cdn_country_weights.yaml
				+ external base weights cdn_weights_ext_yaml
		- Validation policy packs:
			· virtual_validation_config @ config/virtual/virtual_validation.yaml
				(tolerances for virtual/CDN behaviour)
		- Geospatial & tz assets (transitively used by S1–S3):
			· hrsl_raster (HRSL population tiles),
			· pelias_cached_bundle_v1 (Pelias geocoder DB),
			· tz_world_2025a and related tz polygons/index (via 2A’s civil_time_manifest),
			· any tzdata archives / tz_index digests listed in artefact_registry_3B.
		- RNG / routing profile:
			· rng_policy / routing_rng_profile_3B (RNG/routing envelope config used later by 3B + 2B).
