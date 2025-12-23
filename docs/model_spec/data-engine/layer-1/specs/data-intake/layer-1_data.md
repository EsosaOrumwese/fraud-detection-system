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
		- s6_selection_policy @ config/allocation/s6_selection_policy.yaml

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
		- Civil-time manifest for tz provenance:
			· civil_time_manifest (2A-level roll-up of tz polygons / tzdb / overrides / tz_index)
		- Geospatial & tz assets (transitively used by S1–S3):
			· hrsl_raster (HRSL population tiles),
			· pelias_cached_bundle_v1 (Pelias geocoder DB),
			· tz_world_2025a and related tz polygons/index (via 2A’s civil_time_manifest),
			· any tzdata archives / tz_index digests listed in artefact_registry_3B.
		- RNG / routing profile:
			· rng_policy / routing_rng_profile_3B (RNG/routing envelope config used later by 3B + 2B).


* Layer-2 Segment 5A
	[5A policies & configs]
		- merchant_class_policy_5A  (classing policy)
			· deterministic rules mapping features → demand_class (and optional subclass/profile_id).
			· may depend on MCC, channel, size buckets, country, virtual flag, zones_per_merchant, etc.
		- demand_scale_policy_5A    (scale policy)
			· deterministic rules mapping (features, demand_class, scenario_id) → base scale parameters, e.g.:
					- weekly_volume_expected (expected arrivals per local week),
					- or a dimensionless scale factor,
					- plus flags like "high_variability", "low_volume_tail".
			· MUST produce finite, non-negative values.
		- shape_grid_policy_5A
			· defines the **local-week grid**:
					- bucket length (minutes),
					- number of buckets `T_week`,
					- mapping: bucket_index k → (local_day_of_week, local_minutes_since_midnight),
					- constraints (must cover exactly 7×24 hours when composed).
		- class_shape_policy_5A
			· defines base shape templates & modifiers for:
					- each demand_class (office-hours, weekend-heavy, night-heavy, etc.),
					- optional per-zone or per-country variants,
					- optional channel-based variants (if you encode that at S1).
			· shapes are defined as unnormalised “preference curves” over the week grid.
		- scenario metadata/configs
			· scenario_id, scenario_type (e.g. baseline vs stress),
			· “shape profile” selectors if S2 uses scenario to pick different templates.
		- baseline_intensity_policy_5A  (optional)
			· defines:
					- which base scale field to use from S1,
					- unit semantics:
							· “weekly_expected_arrivals” → Σ_k λ_base_local(m,z,k) ≈ weekly_volume_expected(m,z),
							· or “dimensionless_scale”   → alternative weekly constraint,
					- optional clipping rules:
							· min/max λ per bucket,
							· behaviour when base_scale=0 with non-zero shape,
							· any per-class/per-zone overrides.
			· Authority:
					- S3 MUST use this policy to interpret S1’s base scale fields,
					- MUST NOT invent base-scale semantics on the fly.

	[Calendar & horizon configs (S4 control-plane)]
		- horizon_config_5A
			· defines:
					- local horizon start/end (dates & times),
					- local horizon bucket duration,
					- representation of horizon bucket index h,
					- optional UTC horizon config (if S4 outputs UTC intensities).
		- scenario_calendar artefacts
			· list of events with:
					- type (e.g. HOLIDAY, PAYDAY, CAMPAIGN, OUTAGE, STRESS),
					- time range (start_local, end_local),
					- scope (global, region, country, zone, demand_class, merchant, merchant_list, etc.),
					- event metadata (labels, scenario tags).
		- scenario_overlay_policy_5A
			· rules for mapping event surfaces → overlay factors F_overlay:
					- per event type,
					- per scope (global/zone/merchant),
					- combination rules (e.g. multiplicative cascade, caps, shutdown),
					- numeric bounds (min/max factor, special-case behaviour).


* Layer-2 Segment 5B
	[5B policies & configs]
		- time_grid_policy_5B
			· config that describes:
					- how to discretise each scenario’s horizon into buckets:
						· bucket duration,
						· coding of bucket_index,
					- which scenario tags/labels to carry onto grid rows.
		- grouping_policy_5B
			· config that defines:
					- which entities to group:
						· default: (merchant_id, zone_representation[, channel_group]) per scenario,
					- which features (from 5A, 2A, 3A, 3B) may be used in grouping decisions,
					- how to assign group_id deterministically (e.g. by stratifying by class, zone, scenario tag).
		- arrival_lgcp_config_5B   (name illustrative; spec: “arrival-process / LGCP config”)
			· defines:
					- latent field type (e.g. log-Gaussian Cox, OU-on-log-λ, “no latent field”),
					- kernel / covariance structure (variance, length-scale, correlation shape),
					- how groups map to kernel hyper-parameters (per-group overrides),
					- clipping/guardrails for λ_realised (min/max factors).
			· S2 MUST treat this as the only authority on latent-field law.
		- rng_policy_5B
			· defines:
					- event families for S2 (e.g. "s2_latent_field_draw"),
					- stream IDs / substream labels for each (scenario_id, group_id),
					- expected draws/blocks per event,
					- RNG accounting rules (how to update rng_trace_log / rng_audit_log).
			· S2 MUST use only these streams for latent draws and log events accordingly.
		- (optional) s2_validation_config_5B
			· small config providing additional numeric guardrails:
					- allowed ranges for latent values or λ_realised,
					- thresholds for sanity checks (e.g. variance bounds).

	[Counting law & RNG configs]
		- arrival_count_config_5B
			· config object that defines:
					- which arrival law to use (e.g. Poisson, NB, mixed),
					- how to compute law parameters θ from (λ_realised, bucket_duration_seconds, group_id, key traits),
					- any parameter constraints and clipping behaviour,
					- required behaviour when λ_realised=0 or very small.
			· S3 MUST treat this as the **only** source of count-law semantics.

		- arrival_rng_policy_5B
			· RNG policy specific to S3 (or shared arrival RNG policy) defining:
					- event family for counts (e.g. "5B.S3.bucket_count"),
					- mapping from (scenario_id, key, bucket_index) → stream_id / substream_label / counters,
					- expected `draws` and `blocks` per count event,
					- RNG accounting rules for rng_trace_log / rng_audit_log.
			· S3 MUST use only these streams/substreams for count draws; any other RNG consumption is forbidden.

		- (optional) s3_count_guardrail_config_5B
			· optional guardrail config with additional local numeric checks:
					- max/min counts per bucket,
					- rules for “force zero” or “force upper bound” in edge cases.

	[5B S4-specific configs: time placement & routing hooks]
		- s4_time_placement_policy_5B
			· defines how to place N arrivals inside a bucket [start_utc, end_utc):
					- e.g. uniform in time, or optionally modulated using a within-bucket shape,
					- how many u∈(0,1) draws per arrival,
					- how to handle boundaries (open/closed intervals, DST edges).
		- s4_routing_policy_5B
			· defines:
					- when to treat merchant as virtual vs physical (or hybrid),
					- any 5B-specific overrides on top of 2B/3B policies (e.g. exclude certain sites),
					- mapping of entity keys (merchant, zone_representation, channel_group) to routing context
						expected by 2B and 3B policies.
		- s4_rng_policy_5B
			· defines streams/substreams for:
					- micro-time draws,
					- site picks,
					- edge picks,
				and how they sit inside the global RNG envelope:
					- per-event `blocks`, `draws`,
					- mapping from (scenario_id, entity key, bucket_index, arrival_seq) → RNG stream/counter.


* Layer-3 Segment 6A
	[6A priors & taxonomies S1 may read (must be in sealed_inputs_6A)]
		- Population priors:
			· world/region-level population priors (expected number of parties per region/type),
			· cell-level mixture priors (fraction of parties in each segment per region/type),
			· demographic distributions if used in the size of the population.
		- Segmentation taxonomies:
			· party_type taxonomy (retail, SME, corporate, organisation, etc.),
			· segment taxonomy (e.g. “mass_market”, “affluent”, “SME_micro”, …),
			· region taxonomy (e.g. country_iso → region_id).
		- Party attribute priors:
			· conditional priors for per-party attributes S1 owns, e.g.:
					- lifecycle_stage priors per (region, party_type, segment),
					- income_band priors per (region, segment, lifecycle_stage),
					- turnover_band, tenure_band, etc.
		- S1 configuration:
			· any S1-specific config/tuning (e.g. total population targets, optional region scaling).

	[6A priors & taxonomies used by S2 (must be in sealed_inputs_6A)]
		- Account/product mix priors:
			· expected number of accounts per party (distribution over counts),
			· mix of account types per party segment & region (e.g. current vs savings vs credit vs loan),
			· product-family priors per account_type (e.g. “standard current”, “premium current”).
		- Account/product taxonomies:
			· canonical account_type codes,
			· product_family/product_id taxonomies,
			· currency/exposure taxonomies (e.g. allowed currencies per region/product).
		- Account eligibility & linkage rules:
			· which (party_type, segment, region) may hold which account_type/product_family,
			· min/max accounts per party per type/family,
			· any mandatory products (e.g. “every business party must have at least one operating account”).
		- S2 configuration:
			· any S2-specific tuning:
					- global caps (“max accounts per world”),
					- per-cell smoothing parameters.

	[6A priors & taxonomies used by S3 (must be in sealed_inputs_6A)]
		- Instrument mix priors:
			· expected number of instruments per account (distribution over counts) by:
					account_type, product_family, segment, region, etc.
			· mix over instrument_type (e.g. `CARD`, `HANDLE`, `WALLET`, `TOKEN`) per account class.
			· optional scheme/network mix priors per instrument_type & region.
		- Instrument taxonomies:
			· instrument_type taxonomy (card vs handle vs wallet vs other),
			· scheme/network/brand taxonomies,
			· token_type taxonomies (if modelling tokenised credentials).
		- Instrument eligibility & linkage rules:
			· which account types can carry which instrument types/schemes,
			· min/max instruments per account per type,
			· any mandatory instruments (e.g. “each primary current account must have at least one card”).
		- Instrument attribute priors:
			· expiry profiles (months/years to expiry) per scheme/network/type,
			· limits and flags (e.g. contactless_enabled, 3DS_enforced),
			· masked identifier formats, BIN/brand mixes (if owned here).
		- S3 configuration:
			· knobs for smoothing, global caps (“max cards per world”), or per-cell guardrails.

	[6A priors & taxonomies used by S4 (must be in sealed_inputs_6A)]
		- Device priors & taxonomies:
			· device_type taxonomy (e.g. MOBILE_PHONE, TABLET, DESKTOP, POS_TERMINAL, ATM),
			· OS, UA-family, device_risk_code taxonomies,
			· device-count priors:
					- expected devices per party/account/merchant per device planning cell,
			· device-sharing priors:
					- how often devices are shared across parties/accounts/merchants,
					- degree distributions (devices per party, parties per device).
		- IP / endpoint priors & taxonomies:
			· ip_type taxonomy (e.g. RESIDENTIAL, CORP, MOBILE_NETWORK, HOSTING_PROVIDER),
			· ip_asn_class taxonomy,
			· IP-count priors:
					- expected IPs per device/party/merchant per IP planning cell,
			· IP-sharing priors & degree distributions:
					- devices per IP, parties per IP, merchants per IP.
		- Graph/linkage rules:
			· which entity types devices/IPs may link to (party/account/instrument/merchant),
			· min/max degrees:
					- min_devices_per_party, max_devices_per_party,
					- min_ips_per_device, max_ips_per_device,
					- similar for parties/merchants.
		- S4 configuration:
			· knobs for smoothing, global caps and performance cutoffs,
			· RNG-family configuration (for counts, allocations, wiring).

	[S5 priors, taxonomies & validation policy]
		- Fraud-role priors per entity type:
			· party-level role priors (per region, segment, party_type, and possibly graph features),
			· account-level role priors (per product family, account_type, owner segment),
			· merchant-level role priors (per mcc/channel/region),
			· device-level role priors (per device_type, risk flags, degree),
			· ip-level role priors (per ip_type/asn_class/risk flags, degree).
		- Fraud-role taxonomies:
			· enumerations of roles per entity type (e.g. PARTY roles, ACCOUNT roles, DEVICE roles, etc.),
			· allowed transitions & compatibility constraints (e.g. certain role combinations forbidden on same entity).
		- S5 validation policy:
			· list of checks to run (coverage, mix vs priors, structure constraints, graph invariants),
			· severity per check (ERROR/WARN/INFO),
			· thresholds and tolerances per metric.


* Layer-3 Segment 6B
	[6B control-plane policies & configuration]
		- Behaviour & attachment policies (resolved via artefact_registry_6B, listed in sealed_inputs_6B):
			· attachment_policy_6B
					- rules for building candidate sets and priors for:
							party attachment, account selection, instrument choice,
							device selection, IP selection, merchant posture usage.
			· sessionisation_policy_6B
					- definitions of session key (which fields form a session),
					- inactivity gap thresholds,
					- whether dwell/session boundaries are deterministic or stochastic.
			· behaviour_config_6B (if present)
					- enables/disables features (e.g. whether to attach instrument at S1),
					- scenario filters and guardrails.
		- RNG policies (Layer-3 shared + 6B-specific):
			· rng_profile_layer3.yaml
					- Philox engine parameters and global invariants.
			· rng_policy_6B.yaml
					- mapping from 6B.S1 decision families → rng_stream_id, budgets:
							rng_event_entity_attach,
							rng_event_session_boundary (if used),
					plus `blocks`/`draws` contracts and envelope semantics.

	[6B configuration & policy inputs for S2]
		- flow_shape_policy_6B       (behaviour_prior / flow_policy)
			· how many flows per session,
			· flow types & structures (auth-only, auth+clear, auth+clear+refund, etc.),
			· arrival→flow assignment rules (one-to-one vs many-to-one).
		- amount_model_6B            (behaviour_prior / amount_policy)
			· per-merchant/segment distributions over amounts & currencies,
			· relationships between auth, clearing, refund amounts.
		- timing_policy_6B           (behaviour_prior / timing_policy)
			· distributions over intra-session & intra-flow time offsets,
			· constraints relative to session windows and arrival timestamps.
		- flow_rng_policy_6B         (RNG policy for S2)
			· mapping from S2 RNG families → rng_stream_id & budgets, e.g.:
					rng_event_flow_shape,
					rng_event_event_timing,
					rng_event_amount_draw.
		- behaviour_config_6B (if present)
			· feature flags, domain filters, and guardrails that may constrain:
					which sessions are eligible for multiple flows,
					which flows may have refunds, etc.

	[6B configuration & policy inputs for S3]
		- fraud_campaign_catalogue_config_6B   (REQUIRED, METADATA or ROW_LEVEL)
			· defines campaign templates:
					campaign_type, segment definitions,
					activation schedules, intended intensities,
					allowable target domains (entities/flows/events).
		- fraud_overlay_policy_6B             (REQUIRED, METADATA or ROW_LEVEL)
			· defines how each campaign type mutates flows & events:
					permitted tactics (amount shifts, routing anomalies, device/IP swaps, etc.),
					what can be inserted vs mutated vs suppressed,
					per-tactic constraints and severity scoring.
		- fraud_rng_policy_6B                 (REQUIRED, METADATA)
			· configuration for S3 RNG families:
					rng_event_campaign_activation,
					rng_event_campaign_targeting,
					rng_event_overlay_mutation,
			plus:
					- per-family budgets (blocks/draws per event),
					- substream keying law (e.g. keyed by (seed,fingerprint,scenario_id,campaign_id,flow_id)).
		- behaviour_config_6B (if present)
			· may limit which campaigns are enabled, which flows/entities are eligible,
			or adjust intensity scaling for particular segments.

	[6B configuration & policy inputs for S4]
		- truth_labelling_policy_6B
			· defines flow-level truth labels (`LEGIT`, `FRAUD_*`, `ABUSE_*`) and event-level truth roles:
					- deterministic rules based on fraud_pattern_type, overlay_flags, posture, baseline vs overlay,
					- optional ambiguous cases where RNG chooses between multiple plausible labels.
		- bank_view_policy_6B
			· defines how the bank reacts:
					- auth decisions (approve/decline/review) given truth & context,
					- detection/no-detection rules and detection channels,
					- dispute/chargeback rules and bank-view labels.
		- delay_models_6B
			· provides distributions for:
					- detection delays,
					- dispute delays,
					- chargeback delays and outcomes,
					- any extra case-event timing needed.
		- case_policy_6B
			· defines:
					- case keys (how flows are grouped into cases),
					- rules for when to open a case,
					- how flows map to one or more cases,
					- canonical case event types and ordering constraints.
		- label_rng_policy_6B
			· declares S4 RNG families and budgets, e.g.:
					- rng_event_truth_label_ambiguity,
					- rng_event_detection_delay,
					- rng_event_dispute_delay,
					- rng_event_chargeback_delay,
					- rng_event_case_timeline;
			and keying scheme:
					- which tuple (mf, parameter_hash, seed, scenario_id, flow_id, case_key, etc.)
					maps to each family’s substream.

	[6B configuration & validation policy for S5]
		- segment_validation_policy_6B
			· defines:
					- which structural, behavioural, and RNG checks S5 must run,
					- severity per check (REQUIRED, WARN, INFO),
					- numeric thresholds / bounds (fraud rate, detection rate, campaign coverage, etc.),
					- sealing rules (when WARN is acceptable, when FAIL blocks `_passed.flag_6B`).
		- behaviour_config_6B (if used at validation time)
			· may restrict which seeds/scenarios are in scope,
			· may scope particular checks to subsets of flows, campaigns, or cases.
