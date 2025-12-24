* Layer-1 Segment 1A
	[M] merchant_ids (ingress):
		- merchant_id, mcc, channel, home_country_iso

	[R] Reference artefacts:
		- iso3166_canonical_2024
		- world_bank_gdp_per_capita_20250415
		- gdp_bucket_map_2024 (Jenks K=5 buckets, precomputed)

	[C] Model coeffs:
		- hurdle_coefficients.yaml
		- nb_dispersion_coefficients.yaml

	[P] Policy / hyperparams:
		- crossborder_hyperparams.yaml
		- policy.s3.rule_ladder.yaml  (eligibility rules)
		- (opt) policy.s3.base_weight.yaml
			· deterministic base-weight prior formula, coeffs, fixed dp
		- (opt) policy.s3.thresholds.yaml
			· deterministic integerisation bounds / feasibility thresholds (L_i, U_i, etc.)
		- config/allocation/ccy_smoothing_params.yaml  (id: ccy_smoothing_params)
		- s6_selection_policy @ config/policy.s6.selection.yaml

	[N] Numeric / math policy artefacts:
		- numeric_policy.json
		- math_profile_manifest.json

	[I] Share surfaces & ISO enumerations:
		- settlement_shares_2024Q4
			· path: reference/network/settlement_shares/2024Q4/settlement_shares.parquet
			· schema: schemas.ingress.layer1.yaml#/settlement_shares
			· PK: (currency, country_iso), columns: share∈[0,1], obs_count≥0
		- ccy_country_shares_2024Q4
			· path: reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet
			· schema: schemas.ingress.layer1.yaml#/ccy_country_shares
			· PK: (currency, country_iso), columns: share∈[0,1], obs_count≥0
		- iso3166_canonical_2024
			· canonical ISO-2 set; PK: (country_iso)
		- (optional, only if producing merchant_currency)
			iso_legal_tender_2024
			· ISO2 → primary legal tender; schema: schemas.ingress.layer1.yaml#/iso_legal_tender_2024


* Layer-1 Segment 1B
	[Refs] Reference / FK surfaces S0 pins for 1B:
		- world_countries                     (country polygons)
		- population_raster_2025              (population raster)
		- tz_world_2025a                      (TZ polygons; used later by 2A/2B)

	[Policies · 1B]
		- jitter_policy
			· path: config/policy/1B.jitter.yaml
			· schema: schemas.1B.yaml#/policy/jitter_policy
			· role: Jitter σ (deg) policy by latitude band / merchant class (deterministic)

	
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
