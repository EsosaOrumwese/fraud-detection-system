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


* Layer-2 Segment 5B — Externals introduced in 5B (S0-sealed; not engine-generated)

      [Core policies & configs]
      - time_grid_policy_5B
            · defines how to discretise each scenario’s horizon into UTC buckets:
            - bucket duration (seconds)
            - bucket_index coding / ordering
            - which scenario tags/labels are carried onto grid rows

      - grouping_policy_5B
            · defines how entities are grouped for latent/count draws:
            - grouping domain (default: merchant_id × zone_representation [× channel_group])
            - allowed feature inputs (only those available from sealed upstream + 5A outputs)
            - deterministic group_id assignment rule

      [Arrival process (S2) + counting law (S3)]
      - arrival_lgcp_config_5B
            · arrival process / latent field config for S2:
            - latent field family (LGCP / OU-on-log-λ / none)
            - covariance / kernel hyperparameters (+ per-group overrides)
            - factor clipping rules for λ_realised = λ_target × ξ
            - any latent-value guardrails (must be pinned here, not ad hoc)

      - arrival_count_config_5B
            · count-law semantics for S3:
            - count family (Poisson / NB / mixture)
            - parameter mapping from (λ_realised, bucket_duration, group traits) → θ
            - clipping/edge-case behaviour (λ→0, extreme λ)
            - optional count guardrails (max/min per bucket) if used

      [Micro-time placement & routing (S4)]
      - arrival_time_placement_policy_5B
            · place N arrivals inside each bucket [start_utc, end_utc):
            - within-bucket placement law (uniform or pinned alternative)
            - interval boundary semantics (open/closed)
            - draws per arrival (pinned)

      - arrival_routing_policy_5B
            · routing hooks for each arrival:
            - how to decide physical vs virtual (or hybrid) per merchant/zone
            - mapping from (merchant, zone_representation, channel_group, arrival_seq) → routing context
            - any 5B-specific constraints/overrides on top of 2B/3B routing outputs

      [RNG & validation]
      - arrival_rng_policy_5B
            · single RNG policy covering all RNG consumption in 5B (S2/S3/S4):
            - event families + stream IDs/substreams for: latent draws, count draws, micro-time draws, site/edge picks
            - expected blocks/draws per event
            - counter update rules + trace/audit logging requirements
            - forbidden RNG consumption (any RNG not declared here)

      - validation_policy_5B
            · validator thresholds + fail-closed rules for S5:
            - allowable ranges for λ_target/λ_realised and latent values
            - count sanity thresholds (aggregate and per-bucket)
            - routing sanity checks (domain coverage, impossible edges, etc.)
            - pass-flag hashing law references
