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
