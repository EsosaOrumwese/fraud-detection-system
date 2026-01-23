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
	[S0 externals · control-plane packs sealed before any behaviour runs]
		- rng_profile_layer3
			· Layer-3 RNG invariants (Philox parameters, open-interval u∈(0,1) law, envelope expectations)
			· shared “RNG law” referenced by 6B RNG policies
		- rng_policy_6B
			· S1 RNG families & budgets (entity attachment draws, session-boundary RNG if enabled)
			· stream/substream keying law + blocks/draws contracts
		- behaviour_config_6B (optional)
			· feature flags, scenario filters, domain guardrails
			· may be consulted by S1–S5 if present (otherwise ignored)

	[S1 externals · behaviour attachment + sessionisation]
		- attachment_policy_6B
			· rules for candidate sets / priors used to attach arrivals to:
					party, account, instrument, device, IP, and merchant posture usage
			· deterministic constraints (what’s allowed) + any stochastic knobs (must be via rng_policy_6B)
		- sessionisation_policy_6B
			· session key definition (which fields define a session)
			· inactivity gap thresholds
			· deterministic vs stochastic boundary posture (if stochastic, must route via rng_policy_6B)
		- behaviour_config_6B (optional)
			· may enable/disable attachment features or restrict eligible domains

	[S2 externals · flow synthesis (shape/amount/timing) + RNG]
		- flow_shape_policy_6B
			· flows-per-session distribution
			· flow “structures” (auth-only, auth+clear, refund patterns, etc.)
			· arrival→flow assignment rules (one-to-one vs many-to-one)
		- amount_model_6B
			· amount + currency models (per merchant/segment/type)
			· relationships across auth/clearing/refund amounts
		- timing_policy_6B
			· intra-session and intra-flow time offset distributions
			· constraints relative to session windows and arrival timestamps
		- flow_rng_policy_6B
			· S2 RNG families & budgets (flow shape draws, timing draws, amount draws)
			· keying law for those RNG families
		- behaviour_config_6B (optional)
			· may restrict eligible flows (refund eligibility, multi-flow sessions, etc.)

	[S3 externals · fraud campaigns + overlays + RNG]
		- fraud_campaign_catalogue_config_6B
			· campaign templates: campaign_type, segment targeting definitions
			· activation schedules/windows + intended intensities
			· allowable target domains (entities/flows/events)
		- fraud_overlay_policy_6B
			· permitted tactics (amount shifts, routing anomalies, device/IP swaps, inserts/suppressions)
			· tactic constraints + severity/scoring posture
		- fraud_rng_policy_6B
			· S3 RNG families & budgets (activation, targeting, mutation)
			· keying law (seed/fingerprint/scenario_id/campaign_id/flow_id…)
		- behaviour_config_6B (optional)
			· may enable/disable campaigns or adjust scaling/eligibility

	[S4 externals · truth labels + bank view + delays/cases + RNG]
		- truth_labelling_policy_6B
			· flow-level truth labels (LEGIT, FRAUD_*, ABUSE_*) and event truth roles
			· deterministic rules + optional ambiguity resolved via label_rng_policy_6B
		- bank_view_policy_6B
			· bank reaction rules (approve/decline/review), detection/no-detection
			· dispute/chargeback rules and bank-view labels
		- delay_models_6B
			· distributions for detection delays, dispute delays, chargeback delays/outcomes
		- case_policy_6B
			· case keys and when to open cases
			· flow→case mapping and canonical case event types + ordering constraints
		- label_rng_policy_6B
			· S4 RNG families & budgets (truth ambiguity, delays, case timeline draws)
			· keying law (mf/seed/scenario_id/flow_id/case_key…)
		- behaviour_config_6B (optional)
			· may restrict which seeds/scenarios/flows are in scope for labeling/casing

	[S5 externals · segment validation / HashGate]
		- segment_validation_policy_6B
			· which structural/behavioural/RNG checks must run
			· severity per check (REQUIRED/WARN/INFO) + thresholds (fraud rate, detection rate, coverage, etc.)
			· sealing rules (when WARN still permits _passed.flag vs when FAIL blocks)
		- behaviour_config_6B (optional)
			· may scope validation to subsets of scenarios/campaigns/cases

	[Optional future externals (not required by current contracts; consider if you want to split enums out of policies)]
		- taxonomy.behaviour_vocab_6B (optional)
			· canonical flow types + event types used across S2/S4
		- taxonomy.campaign_vocab_6B (optional)
			· canonical campaign_type + tactic enums used across S3
		- taxonomy.labels_bank_case_vocab_6B (optional)
			· canonical truth label enums, bank label/action enums, case event type enums used across S4/S5
