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
					- sealing rules (when WARN is acceptable, when FAIL blocks `_passed.flag`).
		- behaviour_config_6B (if used at validation time)
			· may restrict which seeds/scenarios are in scope,
			· may scope particular checks to subsets of flows, campaigns, or cases.
