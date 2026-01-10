SHELL := C:/Progra~1/Git/bin/bash.exe
.SHELLFLAGS := -eu -o pipefail -c

PY ?= python
ENGINE_PYTHONPATH ?= packages/engine/src
PYTHONUNBUFFERED ?= 1

# Python command wrappers (unbuffered to keep console output responsive).
PY_ENGINE = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY)
PY_SCRIPT = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) $(PY)

# ---------------------------------------------------------------------------
# Run defaults
# ---------------------------------------------------------------------------
RUN_ROOT ?= runs/local_full_run-5
SUMMARY_DIR ?= $(RUN_ROOT)/summaries
RESULT_JSON ?= $(SUMMARY_DIR)/segment1a_result.json
SEG1B_RESULT_JSON ?= $(SUMMARY_DIR)/segment1b_result.json
SEG2A_RESULT_JSON ?= $(SUMMARY_DIR)/segment2a_result.json
SEG2B_RESULT_JSON ?= $(SUMMARY_DIR)/segment2b_result.json
SEG3A_RESULT_JSON ?= $(SUMMARY_DIR)/segment3a_result.json
SEG3B_RESULT_JSON ?= $(SUMMARY_DIR)/segment3b_result.json
SEG5A_RESULT_JSON ?= $(SUMMARY_DIR)/segment5a_result.json
SEG5B_RESULT_JSON ?= $(SUMMARY_DIR)/segment5b_result.json
SEG6A_RESULT_JSON ?= $(SUMMARY_DIR)/segment6a_result.json
SEG6B_RESULT_JSON ?= $(SUMMARY_DIR)/segment6b_result.json
RUN_ID ?= 00000000000000000000000000000005
LOG ?= $(RUN_ROOT)/run_log_run-5.log
SEED ?= 2026011001
SKIP_SEG1A ?= 0
SKIP_SEG1B ?= 0
SKIP_SEG2A ?= 0
SKIP_SEG2B ?= 0
SKIP_SEG3A ?= 0
SKIP_SEG3B ?= 0
SKIP_SEG5A ?= 0
SKIP_SEG5B ?= 0
SKIP_SEG6A ?= 0
SKIP_SEG6B ?= 0

GIT_COMMIT ?= $(shell git rev-parse HEAD)

# ---------------------------------------------------------------------------
# Derived run paths
# ---------------------------------------------------------------------------
RUN_DATA_L1 ?= $(RUN_ROOT)/data/layer1
RUN_DATA_L2 ?= $(RUN_ROOT)/data/layer2
RUN_DATA_L3 ?= $(RUN_ROOT)/data/layer3
RUN_LOGS_L1 ?= $(RUN_ROOT)/logs/layer1
RUN_LOGS_L2 ?= $(RUN_ROOT)/logs/layer2
RUN_LOGS_L3 ?= $(RUN_ROOT)/logs/layer3
RUN_ARTEFACTS ?= $(RUN_ROOT)/artefacts
RUN_CONFIG ?= $(RUN_ROOT)/config

define L1_VALIDATION_BUNDLE
$(RUN_DATA_L1)/$(1)/validation/manifest_fingerprint=$(2)
endef

define L2_VALIDATION_BUNDLE
$(RUN_DATA_L2)/$(1)/validation/manifest_fingerprint=$(2)
endef

define L3_VALIDATION_BUNDLE
$(RUN_DATA_L3)/$(1)/validation/manifest_fingerprint=$(2)
endef

# ---------------------------------------------------------------------------
# Preflight helpers
# ---------------------------------------------------------------------------
define REQUIRE_FILE
	@if [ ! -f "$(1)" ]; then \
		echo "Missing required file: $(1)" >&2; \
		exit 1; \
	fi
endef

define REQUIRE_DIR
	@if [ ! -d "$(1)" ]; then \
		echo "Missing required directory: $(1)" >&2; \
		exit 1; \
	fi
endef

# ---------------------------------------------------------------------------
# Contracts pack defaults
# ---------------------------------------------------------------------------
CONTRACTS_PACK_TAG ?= latest

# ---------------------------------------------------------------------------
# External versions (defaults; override as needed)
# ---------------------------------------------------------------------------
MERCHANT_VERSION ?= 2026-01-03
MERCHANT_ISO_VERSION ?= 2024-12-31
MERCHANT_GDP_VERSION ?= 2025-04-15
MERCHANT_BUCKET_VERSION ?= 2024
MERCHANT_MCC_VERSION ?= 2025-12-31

ISO_VERSION ?= 2024-12-31
GDP_VERSION ?= 2025-04-15
BUCKET_VERSION ?= 2024
NUMERIC_POLICY_VERSION ?= 2025-12-31
MATH_PROFILE_VERSION ?= openlibm-v0.8.7

# ---------------------------------------------------------------------------
# External paths (aligned to registries)
# ---------------------------------------------------------------------------
MERCHANT_TABLE ?= reference/layer1/transaction_schema_merchant_ids/$(MERCHANT_VERSION)/transaction_schema_merchant_ids.parquet
ISO_TABLE ?= reference/iso/iso3166_canonical/$(ISO_VERSION)/iso3166.parquet
GDP_TABLE ?= reference/economic/world_bank_gdp_per_capita/$(GDP_VERSION)/gdp.parquet
BUCKET_TABLE ?= reference/economic/gdp_bucket_map/$(BUCKET_VERSION)/gdp_bucket_map.parquet
NUMERIC_POLICY ?= reference/governance/numeric_policy/$(NUMERIC_POLICY_VERSION)/numeric_policy.json
MATH_PROFILE ?= reference/governance/math_profile/$(MATH_PROFILE_VERSION)/math_profile_manifest.json
VALIDATION_POLICY ?= config/layer1/1A/policy/validation_policy.yaml

S3_RULE_LADDER_POLICY ?= config/layer1/1A/policy/s3.rule_ladder.yaml
S3_BASE_WEIGHT_POLICY ?= config/layer1/1A/policy/s3.base_weight.yaml
S3_THRESHOLDS_POLICY ?= config/layer1/1A/policy/s3.thresholds.yaml
S3_BOUNDS_POLICY ?= contracts/_stale/policies/l1/seg_1A/policy.s3.bounds.yaml
CROSSBORDER_HYPERPARAMS ?= config/layer1/1A/policy/crossborder_hyperparams.yaml
CCY_SMOOTHING_PARAMS ?= config/layer1/1A/allocation/ccy_smoothing_params.yaml
S6_SELECTION_POLICY ?= config/layer1/1A/policy.s6.selection.yaml
HURDLE_EXPORT_VERSION ?= 2026-01-03
HURDLE_EXPORT_RUN ?= 20260103T184840Z
HURDLE_COEFFS ?= config/layer1/1A/models/hurdle/exports/version=$(HURDLE_EXPORT_VERSION)/$(HURDLE_EXPORT_RUN)/hurdle_coefficients.yaml
NB_DISPERSION_COEFFS ?= config/layer1/1A/models/hurdle/exports/version=$(HURDLE_EXPORT_VERSION)/$(HURDLE_EXPORT_RUN)/nb_dispersion_coefficients.yaml

# Segment 2B policies
ALIAS_LAYOUT_POLICY_V1 ?= config/layer1/2B/policy/alias_layout_policy_v1.json
DAY_EFFECT_POLICY_V1 ?= config/layer1/2B/policy/day_effect_policy_v1.json
ROUTE_RNG_POLICY_V1 ?= config/layer1/2B/policy/route_rng_policy_v1.json
VIRTUAL_EDGE_POLICY_V1 ?= config/layer1/2B/policy/virtual_edge_policy_v1.json

# Segment 3A policies
ZONE_MIXTURE_POLICY ?= config/layer1/3A/policy/zone_mixture_policy.yaml
COUNTRY_ZONE_ALPHAS ?= config/layer1/3A/allocation/country_zone_alphas.yaml
ZONE_FLOOR_POLICY ?= config/layer1/3A/allocation/zone_floor_policy.yaml

# Segment 3B policies
MCC_CHANNEL_RULES ?= config/layer1/3B/virtual/mcc_channel_rules.yaml
CDN_COUNTRY_WEIGHTS ?= config/layer1/3B/virtual/cdn_country_weights.yaml
VIRTUAL_VALIDATION_POLICY ?= config/layer1/3B/virtual/virtual_validation.yml

# Segment 5A policies
BASELINE_INTENSITY_POLICY_5A ?= config/layer2/5A/policy/baseline_intensity_policy_5A.v1.yaml
DEMAND_SCALE_POLICY_5A ?= config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml
MERCHANT_CLASS_POLICY_5A ?= config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml
SHAPE_LIBRARY_5A ?= config/layer2/5A/policy/shape_library_5A.v1.yaml
SCENARIO_HORIZON_CONFIG_5A ?= config/layer2/5A/scenario/scenario_horizon_config_5A.v1.yaml
SCENARIO_OVERLAY_POLICY_5A ?= config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml

# Segment 5B policies
ARRIVAL_COUNT_CONFIG_5B ?= config/layer2/5B/arrival_count_config_5B.yaml
ARRIVAL_LGCP_CONFIG_5B ?= config/layer2/5B/arrival_lgcp_config_5B.yaml
ARRIVAL_RNG_POLICY_5B ?= config/layer2/5B/arrival_rng_policy_5B.yaml
ARRIVAL_ROUTING_POLICY_5B ?= config/layer2/5B/arrival_routing_policy_5B.yaml
ARRIVAL_TIME_PLACEMENT_POLICY_5B ?= config/layer2/5B/arrival_time_placement_policy_5B.yaml
GROUPING_POLICY_5B ?= config/layer2/5B/grouping_policy_5B.yaml
TIME_GRID_POLICY_5B ?= config/layer2/5B/time_grid_policy_5B.yaml
VALIDATION_POLICY_5B ?= config/layer2/5B/validation_policy_5B.yaml

# Segment 6A policies/priors/taxonomies
DEVICE_LINKAGE_RULES_6A ?= config/layer3/6A/policy/device_linkage_rules_6A.v1.yaml
GRAPH_LINKAGE_RULES_6A ?= config/layer3/6A/policy/graph_linkage_rules_6A.v1.yaml
VALIDATION_POLICY_6A ?= config/layer3/6A/policy/validation_policy_6A.v1.yaml
ACCOUNT_TAXONOMY_6A ?= config/layer3/6A/taxonomy/account_taxonomy_6A.v1.yaml
DEVICE_TAXONOMY_6A ?= config/layer3/6A/taxonomy/device_taxonomy_6A.v1.yaml
FRAUD_ROLE_TAXONOMY_6A ?= config/layer3/6A/taxonomy/fraud_role_taxonomy_6A.v1.yaml
INSTRUMENT_TAXONOMY_6A ?= config/layer3/6A/taxonomy/instrument_taxonomy_6A.v1.yaml
IP_TAXONOMY_6A ?= config/layer3/6A/taxonomy/ip_taxonomy_6A.v1.yaml
PARTY_TAXONOMY_6A ?= config/layer3/6A/taxonomy/party_taxonomy_6A.v1.yaml
ACCOUNT_PER_PARTY_PRIORS_6A ?= config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml
ACCOUNT_ROLE_PRIORS_6A ?= config/layer3/6A/priors/account_role_priors_6A.v1.yaml
DEVICE_COUNT_PRIORS_6A ?= config/layer3/6A/priors/device_count_priors_6A.v1.yaml
DEVICE_ROLE_PRIORS_6A ?= config/layer3/6A/priors/device_role_priors_6A.v1.yaml
INSTRUMENT_MIX_PRIORS_6A ?= config/layer3/6A/priors/instrument_mix_priors_6A.v1.yaml
INSTRUMENT_PER_ACCOUNT_PRIORS_6A ?= config/layer3/6A/priors/instrument_per_account_priors_6A.v1.yaml
IP_COUNT_PRIORS_6A ?= config/layer3/6A/priors/ip_count_priors_6A.v1.yaml
IP_ROLE_PRIORS_6A ?= config/layer3/6A/priors/ip_role_priors_6A.v1.yaml
MERCHANT_ROLE_PRIORS_6A ?= config/layer3/6A/priors/merchant_role_priors_6A.v1.yaml
PARTY_ROLE_PRIORS_6A ?= config/layer3/6A/priors/party_role_priors_6A.v1.yaml
POPULATION_PRIORS_6A ?= config/layer3/6A/priors/population_priors_6A.v1.yaml
PRODUCT_MIX_PRIORS_6A ?= config/layer3/6A/priors/product_mix_priors_6A.v1.yaml
SEGMENTATION_PRIORS_6A ?= config/layer3/6A/priors/segmentation_priors_6A.v1.yaml

# Segment 6B policies
AMOUNT_MODEL_6B ?= config/layer3/6B/amount_model_6B.yaml
ATTACHMENT_POLICY_6B ?= config/layer3/6B/attachment_policy_6B.yaml
BANK_VIEW_POLICY_6B ?= config/layer3/6B/bank_view_policy_6B.yaml
BEHAVIOUR_CONFIG_6B ?= config/layer3/6B/behaviour_config_6B.yaml
BEHAVIOUR_PRIOR_PACK_6B ?= config/layer3/6B/behaviour_prior_pack_6B.yaml
CASE_POLICY_6B ?= config/layer3/6B/case_policy_6B.yaml
DELAY_MODELS_6B ?= config/layer3/6B/delay_models_6B.yaml
FLOW_RNG_POLICY_6B ?= config/layer3/6B/flow_rng_policy_6B.yaml
FLOW_SHAPE_POLICY_6B ?= config/layer3/6B/flow_shape_policy_6B.yaml
FRAUD_CAMPAIGN_CATALOGUE_6B ?= config/layer3/6B/fraud_campaign_catalogue_config_6B.yaml
FRAUD_OVERLAY_POLICY_6B ?= config/layer3/6B/fraud_overlay_policy_6B.yaml
FRAUD_RNG_POLICY_6B ?= config/layer3/6B/fraud_rng_policy_6B.yaml
LABEL_RNG_POLICY_6B ?= config/layer3/6B/label_rng_policy_6B.yaml
RNG_POLICY_6B ?= config/layer3/6B/rng_policy_6B.yaml
RNG_PROFILE_LAYER3 ?= config/layer3/6B/rng_profile_layer3.yaml
SEGMENT_VALIDATION_POLICY_6B ?= config/layer3/6B/segment_validation_policy_6B.yaml
SESSIONISATION_POLICY_6B ?= config/layer3/6B/sessionisation_policy_6B.yaml
TIMING_POLICY_6B ?= config/layer3/6B/timing_policy_6B.yaml
TRUTH_LABELLING_POLICY_6B ?= config/layer3/6B/truth_labelling_policy_6B.yaml

SEG1B_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml

# Segment 1A
SEG1A_EXTRA ?=

SEG1A_REQUIRED_REFS = \
	$(MERCHANT_TABLE) \
	$(ISO_TABLE) \
	$(GDP_TABLE) \
	$(BUCKET_TABLE) \
	$(NUMERIC_POLICY) \
	$(MATH_PROFILE) \
	$(VALIDATION_POLICY)

SEG1A_PARAM_PAIRS = \
	policy.s3.rule_ladder.yaml=$(S3_RULE_LADDER_POLICY) \
	policy.s3.base_weight.yaml=$(S3_BASE_WEIGHT_POLICY) \
	policy.s3.thresholds.yaml=$(S3_THRESHOLDS_POLICY) \
	policy.s3.bounds.yaml=$(S3_BOUNDS_POLICY) \
	crossborder_hyperparams.yaml=$(CROSSBORDER_HYPERPARAMS) \
	hurdle_coefficients.yaml=$(HURDLE_COEFFS) \
	nb_dispersion_coefficients.yaml=$(NB_DISPERSION_COEFFS) \
	ccy_smoothing_params.yaml=$(CCY_SMOOTHING_PARAMS) \
	s6_selection_policy.yaml=$(S6_SELECTION_POLICY) \
	alias_layout_policy_v1.json=$(ALIAS_LAYOUT_POLICY_V1) \
	day_effect_policy_v1.json=$(DAY_EFFECT_POLICY_V1) \
	route_rng_policy_v1.json=$(ROUTE_RNG_POLICY_V1) \
	virtual_edge_policy_v1.json=$(VIRTUAL_EDGE_POLICY_V1) \
	zone_mixture_policy.yaml=$(ZONE_MIXTURE_POLICY) \
	country_zone_alphas.yaml=$(COUNTRY_ZONE_ALPHAS) \
	zone_floor_policy.yaml=$(ZONE_FLOOR_POLICY) \
	mcc_channel_rules.yaml=$(MCC_CHANNEL_RULES) \
	cdn_country_weights.yaml=$(CDN_COUNTRY_WEIGHTS) \
	virtual_validation.yml=$(VIRTUAL_VALIDATION_POLICY) \
	baseline_intensity_policy_5A.v1.yaml=$(BASELINE_INTENSITY_POLICY_5A) \
	demand_scale_policy_5A.v1.yaml=$(DEMAND_SCALE_POLICY_5A) \
	merchant_class_policy_5A.v1.yaml=$(MERCHANT_CLASS_POLICY_5A) \
	shape_library_5A.v1.yaml=$(SHAPE_LIBRARY_5A) \
	scenario_horizon_config_5A.v1.yaml=$(SCENARIO_HORIZON_CONFIG_5A) \
	scenario_overlay_policy_5A.v1.yaml=$(SCENARIO_OVERLAY_POLICY_5A) \
	arrival_count_config_5B.yaml=$(ARRIVAL_COUNT_CONFIG_5B) \
	arrival_lgcp_config_5B.yaml=$(ARRIVAL_LGCP_CONFIG_5B) \
	arrival_rng_policy_5B.yaml=$(ARRIVAL_RNG_POLICY_5B) \
	arrival_routing_policy_5B.yaml=$(ARRIVAL_ROUTING_POLICY_5B) \
	arrival_time_placement_policy_5B.yaml=$(ARRIVAL_TIME_PLACEMENT_POLICY_5B) \
	grouping_policy_5B.yaml=$(GROUPING_POLICY_5B) \
	time_grid_policy_5B.yaml=$(TIME_GRID_POLICY_5B) \
	validation_policy_5B.yaml=$(VALIDATION_POLICY_5B) \
	device_linkage_rules_6A.v1.yaml=$(DEVICE_LINKAGE_RULES_6A) \
	graph_linkage_rules_6A.v1.yaml=$(GRAPH_LINKAGE_RULES_6A) \
	validation_policy_6A.v1.yaml=$(VALIDATION_POLICY_6A) \
	account_taxonomy_6A.v1.yaml=$(ACCOUNT_TAXONOMY_6A) \
	device_taxonomy_6A.v1.yaml=$(DEVICE_TAXONOMY_6A) \
	fraud_role_taxonomy_6A.v1.yaml=$(FRAUD_ROLE_TAXONOMY_6A) \
	instrument_taxonomy_6A.v1.yaml=$(INSTRUMENT_TAXONOMY_6A) \
	ip_taxonomy_6A.v1.yaml=$(IP_TAXONOMY_6A) \
	party_taxonomy_6A.v1.yaml=$(PARTY_TAXONOMY_6A) \
	account_per_party_priors_6A.v1.yaml=$(ACCOUNT_PER_PARTY_PRIORS_6A) \
	account_role_priors_6A.v1.yaml=$(ACCOUNT_ROLE_PRIORS_6A) \
	device_count_priors_6A.v1.yaml=$(DEVICE_COUNT_PRIORS_6A) \
	device_role_priors_6A.v1.yaml=$(DEVICE_ROLE_PRIORS_6A) \
	instrument_mix_priors_6A.v1.yaml=$(INSTRUMENT_MIX_PRIORS_6A) \
	instrument_per_account_priors_6A.v1.yaml=$(INSTRUMENT_PER_ACCOUNT_PRIORS_6A) \
	ip_count_priors_6A.v1.yaml=$(IP_COUNT_PRIORS_6A) \
	ip_role_priors_6A.v1.yaml=$(IP_ROLE_PRIORS_6A) \
	merchant_role_priors_6A.v1.yaml=$(MERCHANT_ROLE_PRIORS_6A) \
	party_role_priors_6A.v1.yaml=$(PARTY_ROLE_PRIORS_6A) \
	population_priors_6A.v1.yaml=$(POPULATION_PRIORS_6A) \
	product_mix_priors_6A.v1.yaml=$(PRODUCT_MIX_PRIORS_6A) \
	segmentation_priors_6A.v1.yaml=$(SEGMENTATION_PRIORS_6A) \
	amount_model_6B.yaml=$(AMOUNT_MODEL_6B) \
	attachment_policy_6B.yaml=$(ATTACHMENT_POLICY_6B) \
	bank_view_policy_6B.yaml=$(BANK_VIEW_POLICY_6B) \
	behaviour_config_6B.yaml=$(BEHAVIOUR_CONFIG_6B) \
	behaviour_prior_pack_6B.yaml=$(BEHAVIOUR_PRIOR_PACK_6B) \
	case_policy_6B.yaml=$(CASE_POLICY_6B) \
	delay_models_6B.yaml=$(DELAY_MODELS_6B) \
	flow_rng_policy_6B.yaml=$(FLOW_RNG_POLICY_6B) \
	flow_shape_policy_6B.yaml=$(FLOW_SHAPE_POLICY_6B) \
	fraud_campaign_catalogue_config_6B.yaml=$(FRAUD_CAMPAIGN_CATALOGUE_6B) \
	fraud_overlay_policy_6B.yaml=$(FRAUD_OVERLAY_POLICY_6B) \
	fraud_rng_policy_6B.yaml=$(FRAUD_RNG_POLICY_6B) \
	label_rng_policy_6B.yaml=$(LABEL_RNG_POLICY_6B) \
	rng_policy_6B.yaml=$(RNG_POLICY_6B) \
	rng_profile_layer3.yaml=$(RNG_PROFILE_LAYER3) \
	segment_validation_policy_6B.yaml=$(SEGMENT_VALIDATION_POLICY_6B) \
	sessionisation_policy_6B.yaml=$(SESSIONISATION_POLICY_6B) \
	timing_policy_6B.yaml=$(TIMING_POLICY_6B) \
	truth_labelling_policy_6B.yaml=$(TRUTH_LABELLING_POLICY_6B)

SEG1A_PARAM_ARGS = $(foreach pair,$(SEG1A_PARAM_PAIRS),--param $(pair))

SEG1A_ARGS = \
	--output-dir $(RUN_ROOT) \
	--merchant-table $(MERCHANT_TABLE) \
	--iso-table $(ISO_TABLE) \
	--gdp-table $(GDP_TABLE) \
	--bucket-table $(BUCKET_TABLE) \
	$(SEG1A_PARAM_ARGS) \
	--git-commit $(GIT_COMMIT) \
	--seed $(SEED) \
	--numeric-policy $(NUMERIC_POLICY) \
	--math-profile $(MATH_PROFILE) \
	--validation-policy $(VALIDATION_POLICY) \
	--stage-seg1b-refs \
	--result-json $(RESULT_JSON) \
	$(SEG1A_EXTRA)
SEG1A_CMD = $(PY_ENGINE) -m engine.cli.segment1a $(SEG1A_ARGS)

# Segment 1B
SEG1B_BASIS ?= population
SEG1B_DP ?= 4
SEG1B_S1_WORKERS ?= 8
SEG1B_S4_WORKERS ?= 2
SEG1B_EXTRA ?=

SEG1B_ARGS = \
	--data-root $(RUN_ROOT) \
	--parameter-hash $$PARAM_HASH \
	--manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--seed $(SEED) \
	--dictionary $(SEG1B_DICTIONARY) \
	--basis $(SEG1B_BASIS) \
	--dp $(SEG1B_DP) \
	--s1-workers $(SEG1B_S1_WORKERS) \
	--s4-workers $(SEG1B_S4_WORKERS) \
	--result-json $(SEG1B_RESULT_JSON) \
	--quiet-summary \
	$(SEG1B_EXTRA)
SEG1B_CMD = $(PY_ENGINE) -m engine.cli.segment1b run $(SEG1B_ARGS)

# Segment 2A
SEG2A_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml
SEG2A_TZDB_RELEASE ?= 2025a
SEG2A_EXTRA ?=
SEG2A_TZDATA_ROOT ?= artefacts/priors/tzdata
SEG2A_TZ_CONFIG_ROOT ?= config/layer1/2A/timezone
SEG2A_CANONICAL_TZDATA = $(SEG2A_TZDATA_ROOT)/$(SEG2A_TZDB_RELEASE)
SEG2A_RUN_TZDATA = $(RUN_ARTEFACTS)/priors/tzdata/$(SEG2A_TZDB_RELEASE)
SEG2A_RUN_TZCFG = $(RUN_CONFIG)/layer1/2A/timezone
SEG2A_S1_CHUNK_SIZE ?= 250000
SEG2A_S1_RESUME ?= 0

SEG2A_EXTRA += --run-s1 --s1-chunk-size $(SEG2A_S1_CHUNK_SIZE) --run-s2 --run-s3 --run-s4 --run-s5
ifeq ($(strip $(SEG2A_S1_RESUME)),1)
SEG2A_EXTRA += --s1-resume
endif

SEG2A_ARGS = \
	--data-root $(RUN_ROOT) \
	--upstream-manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--tzdb-release-tag $(SEG2A_TZDB_RELEASE) \
	--git-commit-hex $(GIT_COMMIT) \
	--dictionary $(SEG2A_DICTIONARY) \
	--validation-bundle $$VALIDATION_BUNDLE \
	--result-json $(SEG2A_RESULT_JSON) \
	--quiet-summary \
	$(SEG2A_EXTRA)
SEG2A_CMD = $(PY_ENGINE) -m engine.cli.segment2a $(SEG2A_ARGS)

# Segment 2B
SEG2B_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml
SEG2B_EXTRA ?=
SEG2B_PIN_TZ ?= 1
SEG2B_RUN_S1 ?= 1
SEG2B_S1_RESUME ?= 0
SEG2B_S1_QUIET ?= 1
SEG2B_RUN_S2 ?= 1
SEG2B_S2_RESUME ?= 0
SEG2B_S2_QUIET ?= 1
SEG2B_RUN_S3 ?= 1
SEG2B_S3_RESUME ?= 0
SEG2B_S3_QUIET ?= 1
SEG2B_RUN_S4 ?= 1
SEG2B_S4_RESUME ?= 0
SEG2B_S4_QUIET ?= 1
SEG2B_RUN_S5 ?= 1
SEG2B_S5_RESUME ?= 0
SEG2B_S5_RUN_ID ?=
SEG2B_S5_SELECTION_LOG ?= 0
SEG2B_S5_ARRIVALS_JSONL ?=
# Optional cap for profiling/debug runs (limits number of (merchant_id, utc_day) arrivals processed).
SEG2B_S5_MAX_ARRIVALS ?=
SEG2B_S5_QUIET ?= 1
SEG2B_RUN_S6 ?= 1
SEG2B_S6_RESUME ?= 0
SEG2B_S6_RUN_ID ?=
SEG2B_S6_EDGE_LOG ?= 0
SEG2B_S6_QUIET ?= 1
SEG2B_RUN_S7 ?= 1
SEG2B_S7_QUIET ?= 1
SEG2B_RUN_S8 ?= 1
SEG2B_S8_WORKSPACE ?=
SEG2B_S8_QUIET ?= 1

ifeq ($(strip $(SEG2B_PIN_TZ)),1)
SEG2B_EXTRA += --pin-tz-assets
endif
ifeq ($(strip $(SEG2B_RUN_S1)),1)
SEG2B_EXTRA += --run-s1
endif
ifeq ($(strip $(SEG2B_S1_RESUME)),1)
SEG2B_EXTRA += --s1-resume
endif
ifeq ($(strip $(SEG2B_S1_QUIET)),1)
SEG2B_EXTRA += --s1-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S2)),1)
SEG2B_EXTRA += --run-s2
endif
ifeq ($(strip $(SEG2B_S2_RESUME)),1)
SEG2B_EXTRA += --s2-resume
endif
ifeq ($(strip $(SEG2B_S2_QUIET)),1)
SEG2B_EXTRA += --s2-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S3)),1)
SEG2B_EXTRA += --run-s3
endif
ifeq ($(strip $(SEG2B_S3_RESUME)),1)
SEG2B_EXTRA += --s3-resume
endif
ifeq ($(strip $(SEG2B_S3_QUIET)),1)
SEG2B_EXTRA += --s3-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S4)),1)
SEG2B_EXTRA += --run-s4
endif
ifeq ($(strip $(SEG2B_S4_RESUME)),1)
SEG2B_EXTRA += --s4-resume
endif
ifeq ($(strip $(SEG2B_S4_QUIET)),1)
SEG2B_EXTRA += --s4-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S5)),1)
SEG2B_EXTRA += --run-s5
endif
ifeq ($(strip $(SEG2B_S5_RESUME)),1)
SEG2B_EXTRA += --s5-resume
endif
ifneq ($(strip $(SEG2B_S5_RUN_ID)),)
SEG2B_EXTRA += --s5-run-id "$(SEG2B_S5_RUN_ID)"
endif
ifeq ($(strip $(SEG2B_S5_SELECTION_LOG)),1)
SEG2B_EXTRA += --s5-selection-log
endif
ifneq ($(strip $(SEG2B_S5_ARRIVALS_JSONL)),)
SEG2B_EXTRA += --s5-arrivals-jsonl "$(SEG2B_S5_ARRIVALS_JSONL)"
endif
ifneq ($(strip $(SEG2B_S5_MAX_ARRIVALS)),)
SEG2B_EXTRA += --s5-max-arrivals $(SEG2B_S5_MAX_ARRIVALS)
endif
ifeq ($(strip $(SEG2B_S5_QUIET)),1)
SEG2B_EXTRA += --s5-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S6)),1)
SEG2B_EXTRA += --run-s6
endif
ifeq ($(strip $(SEG2B_S6_RESUME)),1)
SEG2B_EXTRA += --s6-resume
endif
ifneq ($(strip $(SEG2B_S6_RUN_ID)),)
SEG2B_EXTRA += --s6-run-id "$(SEG2B_S6_RUN_ID)"
endif
ifeq ($(strip $(SEG2B_S6_EDGE_LOG)),1)
SEG2B_EXTRA += --s6-edge-log
endif
ifeq ($(strip $(SEG2B_S6_QUIET)),1)
SEG2B_EXTRA += --s6-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S7)),1)
SEG2B_EXTRA += --run-s7
endif
ifeq ($(strip $(SEG2B_S7_QUIET)),1)
SEG2B_EXTRA += --s7-quiet-run-report
endif

ifeq ($(strip $(SEG2B_RUN_S8)),1)
SEG2B_EXTRA += --run-s8
endif
ifneq ($(strip $(SEG2B_S8_WORKSPACE)),)
SEG2B_EXTRA += --s8-workspace "$(SEG2B_S8_WORKSPACE)"
endif
ifeq ($(strip $(SEG2B_S8_QUIET)),1)
SEG2B_EXTRA += --s8-quiet-summary
endif

SEG2B_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--seed $(SEED) \
	--manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seg2a-manifest-fingerprint $$SEG2A_MANIFEST_FINGERPRINT \
	--git-commit-hex $(GIT_COMMIT) \
	--dictionary "$(SEG2B_DICTIONARY)" \
	--validation-bundle "$$VALIDATION_BUNDLE" \
	--result-json "$(SEG2B_RESULT_JSON)" \
	--quiet-summary \
	$(SEG2B_EXTRA)
SEG2B_CMD = $(PY_ENGINE) -m engine.cli.segment2b $(SEG2B_ARGS)

# Segment 3A
SEG3A_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml
SEG3A_EXTRA ?=
SEG3A_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--upstream-manifest-fingerprint $$UPSTREAM_MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--git-commit-hex $(GIT_COMMIT) \
	--dictionary "$(SEG3A_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--run-s1 \
	--run-s2 \
	--run-s3 \
	--run-s4 \
	--run-s5 \
	--run-s6 \
	--run-s7 \
	--run-id $(RUN_ID) \
	--result-json "$(SEG3A_RESULT_JSON)" \
	--quiet-summary \
	$(SEG3A_EXTRA)
SEG3A_CMD = $(PY_ENGINE) -m engine.cli.segment3a $(SEG3A_ARGS)

# Segment 3B
SEG3B_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml
SEG3B_EXTRA ?=
SEG3B_RUN_S1 ?= 1
SEG3B_RUN_S2 ?= 1
SEG3B_RUN_S3 ?= 1
SEG3B_RUN_S4 ?= 1
SEG3B_RUN_S5 ?= 1

ifeq ($(strip $(SEG3B_RUN_S1)),0)
SEG3B_EXTRA += --skip-s1
endif
ifeq ($(strip $(SEG3B_RUN_S2)),1)
SEG3B_EXTRA += --run-s2
endif
ifeq ($(strip $(SEG3B_RUN_S3)),1)
SEG3B_EXTRA += --run-s3
endif
ifeq ($(strip $(SEG3B_RUN_S4)),1)
SEG3B_EXTRA += --run-s4
endif
ifeq ($(strip $(SEG3B_RUN_S5)),1)
SEG3B_EXTRA += --run-s5
endif
SEG3B_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--upstream-manifest-fingerprint $$UPSTREAM_MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--git-commit-hex $(GIT_COMMIT) \
	--dictionary "$(SEG3B_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--validation-bundle-2b "$$VALIDATION_BUNDLE_2B" \
	--validation-bundle-3a "$$VALIDATION_BUNDLE_3A" \
	--result-json "$(SEG3B_RESULT_JSON)" \
	$(SEG3B_EXTRA)
SEG3B_CMD = $(PY_ENGINE) -m engine.cli.segment3b $(SEG3B_ARGS)

# Segment 5A
SEG5A_DICTIONARY ?= contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml
SEG5A_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--upstream-manifest-fingerprint $$UPSTREAM_MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--run-id "$(RUN_ID)" \
	--dictionary "$(SEG5A_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--validation-bundle-2b "$$VALIDATION_BUNDLE_2B" \
	--validation-bundle-3a "$$VALIDATION_BUNDLE_3A" \
	--validation-bundle-3b "$$VALIDATION_BUNDLE_3B" \
	--result-json "$(SEG5A_RESULT_JSON)"
SEG5A_CMD = $(PY_ENGINE) -m engine.cli.segment5a $(SEG5A_ARGS)

# Segment 5B
SEG5B_DICTIONARY ?= contracts/dataset_dictionary/l2/seg_5B/layer2.5B.yaml
SEG5B_S1_RESUME ?= 0
SEG5B_S2_RESUME ?= 0
SEG5B_S3_RESUME ?= 0
SEG5B_S4_RESUME ?= 0
SEG5B_EXTRA =
ifeq ($(strip $(SEG5B_S1_RESUME)),1)
SEG5B_EXTRA += --s1-resume
endif
ifeq ($(strip $(SEG5B_S2_RESUME)),1)
SEG5B_EXTRA += --s2-resume
endif
ifeq ($(strip $(SEG5B_S3_RESUME)),1)
SEG5B_EXTRA += --s3-resume
endif
ifeq ($(strip $(SEG5B_S4_RESUME)),1)
SEG5B_EXTRA += --s4-resume
endif
SEG5B_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--run-id "$(RUN_ID)" \
	--dictionary-path "$(SEG5B_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--validation-bundle-2b "$$VALIDATION_BUNDLE_2B" \
	--validation-bundle-3a "$$VALIDATION_BUNDLE_3A" \
	--validation-bundle-3b "$$VALIDATION_BUNDLE_3B" \
	--validation-bundle-5a "$$VALIDATION_BUNDLE_5A" \
	--result-json "$(SEG5B_RESULT_JSON)" \
	$(SEG5B_EXTRA)
SEG5B_CMD = $(PY_ENGINE) -m engine.cli.segment5b $(SEG5B_ARGS)

# Segment 6A
SEG6A_DICTIONARY ?= contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml
SEG6A_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--run-id "$(RUN_ID)" \
	--dictionary-path "$(SEG6A_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--validation-bundle-2b "$$VALIDATION_BUNDLE_2B" \
	--validation-bundle-3a "$$VALIDATION_BUNDLE_3A" \
	--validation-bundle-3b "$$VALIDATION_BUNDLE_3B" \
	--validation-bundle-5a "$$VALIDATION_BUNDLE_5A" \
	--validation-bundle-5b "$$VALIDATION_BUNDLE_5B" \
	--result-json "$(SEG6A_RESULT_JSON)"
SEG6A_CMD = $(PY_ENGINE) -m engine.cli.segment6a $(SEG6A_ARGS)

# Segment 6B
SEG6B_DICTIONARY ?= contracts/dataset_dictionary/l3/seg_6B/layer3.6B.yaml
SEG6B_ARGS = \
	--data-root "$(RUN_ROOT)" \
	--manifest-fingerprint $$MANIFEST_FINGERPRINT \
	--parameter-hash $$PARAM_HASH \
	--seed $(SEED) \
	--run-id "$(RUN_ID)" \
	--dictionary-path "$(SEG6B_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
	--validation-bundle-2b "$$VALIDATION_BUNDLE_2B" \
	--validation-bundle-3a "$$VALIDATION_BUNDLE_3A" \
	--validation-bundle-3b "$$VALIDATION_BUNDLE_3B" \
	--validation-bundle-5a "$$VALIDATION_BUNDLE_5A" \
	--validation-bundle-5b "$$VALIDATION_BUNDLE_5B" \
	--validation-bundle-6a "$$VALIDATION_BUNDLE_6A" \
	--result-json "$(SEG6B_RESULT_JSON)"
SEG6B_CMD = $(PY_ENGINE) -m engine.cli.segment6b $(SEG6B_ARGS)

MERCHANT_BUILD_CMD = $(PY_ENGINE) scripts/build_transaction_schema_merchant_ids.py \
	--version $(MERCHANT_VERSION) \
	--iso-version $(MERCHANT_ISO_VERSION) \
	--gdp-version $(MERCHANT_GDP_VERSION) \
	--bucket-version $(MERCHANT_BUCKET_VERSION) \
	--mcc-version $(MERCHANT_MCC_VERSION) \
	--numeric-policy $(NUMERIC_POLICY)

HURDLE_EXPORT_CMD = $(PY_SCRIPT) scripts/build_hurdle_exports.py
CURRENCY_REF_CMD = $(PY_SCRIPT) scripts/build_currency_reference_surfaces.py
VIRTUAL_EDGE_POLICY_CMD = $(PY_SCRIPT) scripts/build_virtual_edge_policy_v1.py
ZONE_FLOOR_POLICY_CMD = $(PY_SCRIPT) scripts/build_zone_floor_policy_3a.py
COUNTRY_ZONE_ALPHAS_CMD = $(PY_SCRIPT) scripts/build_country_zone_alphas_3a.py
CROSSBORDER_FEATURES_CMD = $(PY_SCRIPT) scripts/build_crossborder_features_1a.py
MERCHANT_CLASS_POLICY_5A_CMD = $(PY_SCRIPT) scripts/build_merchant_class_policy_5a.py
DEMAND_SCALE_POLICY_5A_CMD = $(PY_SCRIPT) scripts/build_demand_scale_policy_5a.py
SHAPE_LIBRARY_5A_CMD = $(PY_SCRIPT) scripts/build_shape_library_5a.py --bucket-minutes 60
SCENARIO_CAL_FINGERPRINT ?=
SCENARIO_CAL_RUN_ROOT ?= $(RUN_ROOT)
CDN_WEIGHTS_EXT_VINTAGE = WDI_ITU_internet_users_share_2024
CDN_WEIGHTS_EXT_YEAR = 2024
CDN_WEIGHTS_EXT_CMD = $(PY_SCRIPT) scripts/build_cdn_weights_ext_yaml.py --vintage $(CDN_WEIGHTS_EXT_VINTAGE) --vintage-year $(CDN_WEIGHTS_EXT_YEAR)
MCC_CHANNEL_RULES_CMD = $(PY_SCRIPT) scripts/build_mcc_channel_rules_3b.py
CDN_COUNTRY_WEIGHTS_CMD = $(PY_SCRIPT) scripts/build_cdn_country_weights_3b.py
VIRTUAL_VALIDATION_CMD = $(PY_SCRIPT) scripts/build_virtual_validation_3b.py
CDN_KEY_DIGEST_CMD = $(PY_SCRIPT) scripts/build_cdn_key_digest_3b.py
HRSL_VINTAGE = HRSL_2025-12-31
HRSL_SEMVER = 1.0.0
HRSL_RASTER_CMD = $(PY_SCRIPT) scripts/build_hrsl_raster_3b.py --vintage $(HRSL_VINTAGE) --semver $(HRSL_SEMVER)
PELIAS_VERSION = 2025-12-31
PELIAS_CACHED_CMD = $(PY_SCRIPT) scripts/build_pelias_cached_sqlite_3b.py --pelias-version $(PELIAS_VERSION)
VIRTUAL_SETTLEMENT_CMD = $(PY_SCRIPT) scripts/build_virtual_settlement_coords_3b.py


.PHONY: all preflight-seg1a segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a segment6b merchant_ids hurdle_exports refresh_merchant_deps currency_refs virtual_edge_policy zone_floor_policy country_zone_alphas crossborder_features merchant_class_policy_5a demand_scale_policy_5a shape_library_5a scenario_calendar_5a policies_5a cdn_weights_ext mcc_channel_rules cdn_country_weights virtual_validation cdn_key_digest hrsl_raster pelias_cached virtual_settlement_coords profile-all profile-seg1b clean-results
.ONESHELL: segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a segment6b

all: segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a segment6b

merchant_ids:
	@echo "Building transaction_schema_merchant_ids version $(MERCHANT_VERSION)"
	$(MERCHANT_BUILD_CMD)

hurdle_exports:
	@echo "Building hurdle + dispersion export bundles"
	$(HURDLE_EXPORT_CMD)

refresh_merchant_deps: merchant_ids hurdle_exports crossborder_features mcc_channel_rules virtual_settlement_coords merchant_class_policy_5a demand_scale_policy_5a
	@echo "Refreshed merchant-dependent externals"

currency_refs:
	@echo "Building ISO legal tender + currency share references (2024Q4)"
	$(CURRENCY_REF_CMD)

virtual_edge_policy:
	@echo "Building 2B virtual_edge_policy_v1"
	$(VIRTUAL_EDGE_POLICY_CMD)

zone_floor_policy:
	@echo "Building 3A zone_floor_policy"
	$(ZONE_FLOOR_POLICY_CMD)

country_zone_alphas:
	@echo "Building 3A country_zone_alphas"
	$(COUNTRY_ZONE_ALPHAS_CMD)

crossborder_features:
	@echo "Building 1A crossborder_features"
	$(CROSSBORDER_FEATURES_CMD)

merchant_class_policy_5a:
	@echo "Building 5A merchant_class_policy_5A"
	$(MERCHANT_CLASS_POLICY_5A_CMD)

demand_scale_policy_5a:
	@echo "Building 5A demand_scale_policy_5A"
	$(DEMAND_SCALE_POLICY_5A_CMD)

shape_library_5a:
	@echo "Building 5A shape_library_5A"
	$(SHAPE_LIBRARY_5A_CMD)

scenario_calendar_5a:
	@run_root="$${SCENARIO_CAL_RUN_ROOT:-$(RUN_ROOT)}"; \
	manifest="$${SCENARIO_CAL_FINGERPRINT:-}"; \
	if [ -z "$$manifest" ]; then \
		if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
			echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found. Set SCENARIO_CAL_FINGERPRINT or run segment3a first." >&2; \
			exit 1; \
		fi; \
		manifest=$$($(PY) -c "import json; print(json.load(open('$(SEG3A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	fi; \
	zone_alloc_dir="$$run_root/data/layer1/3A/zone_alloc/seed=$(SEED)/manifest_fingerprint=$$manifest"; \
	zone_alloc_path=$$(ls "$$zone_alloc_dir"/part-*.parquet 2>/dev/null | head -n 1); \
	if [ -z "$$zone_alloc_path" ]; then \
		echo "zone_alloc parquet not found under $$zone_alloc_dir" >&2; \
		exit 1; \
	fi; \
	echo "Building 5A scenario_calendar_5A (manifest_fingerprint $$manifest)"; \
	$(PY_SCRIPT) scripts/build_scenario_calendar_5a.py --manifest-fingerprint "$$manifest" --zone-alloc-path "$$zone_alloc_path"

policies_5a: merchant_class_policy_5a demand_scale_policy_5a shape_library_5a
	@echo "5A policy scripts complete (manual configs: baseline_intensity, scenario_horizon, scenario_overlay)"

cdn_weights_ext:
	@echo "Building 3B cdn_weights_ext_yaml (WDI $(CDN_WEIGHTS_EXT_YEAR))"
	$(CDN_WEIGHTS_EXT_CMD)

mcc_channel_rules:
	@echo "Building 3B mcc_channel_rules"
	$(MCC_CHANNEL_RULES_CMD)

cdn_country_weights:
	@echo "Building 3B cdn_country_weights"
	$(CDN_COUNTRY_WEIGHTS_CMD)

virtual_validation:
	@echo "Building 3B virtual_validation"
	$(VIRTUAL_VALIDATION_CMD)

cdn_key_digest:
	@echo "Building 3B cdn_key_digest"
	$(CDN_KEY_DIGEST_CMD)

hrsl_raster:
	@echo "Building 3B hrsl_raster"
	$(HRSL_RASTER_CMD)

pelias_cached:
	@echo "Building 3B pelias_cached.sqlite"
	$(PELIAS_CACHED_CMD)

virtual_settlement_coords:
	@echo "Building 3B virtual_settlement_coords"
	$(VIRTUAL_SETTLEMENT_CMD)

preflight-seg1a:
	@echo "Preflight Segment 1A inputs"
	$(call REQUIRE_DIR,reference)
	$(call REQUIRE_DIR,config)
	@missing=0; \
	for path in $(SEG1A_REQUIRED_REFS); do \
		if [ ! -f "$$path" ]; then \
			echo "Missing required Segment 1A input: $$path" >&2; \
			missing=1; \
		fi; \
	done; \
	for param in $(SEG1A_PARAM_PAIRS); do \
		path="$${param#*=}"; \
		if [ ! -f "$$path" ]; then \
			echo "Missing SEG1A param file: $$path (from $$param)" >&2; \
			missing=1; \
		fi; \
	done; \
	if [ "$$missing" -ne 0 ]; then \
		echo "Preflight failed: missing inputs detected." >&2; \
		exit 1; \
	fi

segment1a: preflight-seg1a
	@echo "Running Segment 1A (S0-S9)"
	@if [ "$(SKIP_SEG1A)" = "1" ]; then \
		if [ ! -f "$(RESULT_JSON)" ]; then \
			echo "SKIP_SEG1A=1 but summary '$(RESULT_JSON)' is missing. Run 'make segment1a' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 1A (SKIP_SEG1A=1)"; \
		exit 0; \
	fi
	@mkdir -p "$(RUN_ROOT)"
	@mkdir -p "$(SUMMARY_DIR)"
ifeq ($(strip $(LOG)),)
	$(SEG1A_CMD)
else
	@: > "$(LOG)"
	($(SEG1A_CMD)) 2>&1 | tee -a "$(LOG)"
endif

segment1b:
	@echo "Running Segment 1B (S0-S9)"
	@if [ "$(SKIP_SEG1B)" = "1" ]; then \
		if [ ! -f "$(SEG1B_RESULT_JSON)" ]; then \
			echo "SKIP_SEG1B=1 but summary '$(SEG1B_RESULT_JSON)' is missing. Run 'make segment1b' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_DATA_L1)/1B" ]; then \
			echo "SKIP_SEG1B=1 but outputs missing under '$(RUN_DATA_L1)/1B'. Run 'make segment1b' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 1B (SKIP_SEG1B=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG1B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG1B_CMD); \
	 fi

segment2a:
	@echo "Running Segment 2A (S0-S5)"
	@if [ "$(SKIP_SEG2A)" = "1" ]; then \
		if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
			echo "SKIP_SEG2A=1 but summary '$(SEG2A_RESULT_JSON)' is missing. Run 'make segment2a' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer1/2A" ]; then \
			echo "SKIP_SEG2A=1 but outputs missing under '$(RUN_ROOT)/data/layer1/2A'. Run 'make segment2a' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 2A (SKIP_SEG2A=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@if [ ! -d "$(RUN_DATA_L1)/1B" ]; then \
		echo "Segment 1B outputs not found under '$(RUN_DATA_L1)/1B'. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE="$(call L1_VALIDATION_BUNDLE,1B,$$MANIFEST_FINGERPRINT)"; \
	 if [ ! -d "$$VALIDATION_BUNDLE" ]; then \
		echo "Segment 1B validation bundle '$$VALIDATION_BUNDLE' not found. Run 'make segment1b' first." >&2; \
		exit 1; \
	 fi; \
	 if [ ! -d "$(SEG2A_CANONICAL_TZDATA)" ]; then \
		echo "Canonical tzdata release '$(SEG2A_CANONICAL_TZDATA)' not found. Stage artefact before running Segment 2A." >&2; \
		exit 1; \
	 fi; \
	 rm -rf "$(SEG2A_RUN_TZDATA)"; \
	 mkdir -p "$(SEG2A_RUN_TZDATA)"; \
	 cp -a "$(SEG2A_CANONICAL_TZDATA)/." "$(SEG2A_RUN_TZDATA)/"; \
	 if [ ! -d "$(SEG2A_TZ_CONFIG_ROOT)" ]; then \
		echo "Canonical timezone config directory '$(SEG2A_TZ_CONFIG_ROOT)' not found. Stage policy artefacts before running Segment 2A." >&2; \
		exit 1; \
	 fi; \
	 rm -rf "$(SEG2A_RUN_TZCFG)"; \
	 mkdir -p "$(SEG2A_RUN_TZCFG)"; \
	 cp -a "$(SEG2A_TZ_CONFIG_ROOT)/." "$(SEG2A_RUN_TZCFG)/"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG2A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG2A_CMD); \
	 fi

segment2b:
	@echo "Running Segment 2B (S0-S8)"
	@if [ "$(SKIP_SEG2B)" = "1" ]; then \
		if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
			echo "SKIP_SEG2B=1 but summary '$(SEG2B_RESULT_JSON)' is missing. Run 'make segment2b' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer1/2B" ]; then \
			echo "SKIP_SEG2B=1 but outputs missing under '$(RUN_ROOT)/data/layer1/2B'. Run 'make segment2b' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 2B (SKIP_SEG2B=1)"; \
		exit 0; \
	fi
	@if [ ! -d "$(RUN_ROOT)/data/layer1/2A" ]; then \
		echo "Segment 2A outputs not found under '$(RUN_ROOT)/data/layer1/2A'. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@TMP_ENV_FILE="$(RUN_ROOT)/.seg2b_env.$$$$"; \
	trap 'rm -f "$$TMP_ENV_FILE"' EXIT; \
	$(PY) scripts/make_helpers/resolve_seg2b_env.py \
		--seg1a-summary "$(RESULT_JSON)" \
		--seg2a-summary "$(SEG2A_RESULT_JSON)" \
		--run-root "$(RUN_ROOT)" \
		--seed "$(SEED)" \
		> "$$TMP_ENV_FILE"; \
	. "$$TMP_ENV_FILE"; \
	rm -f "$$TMP_ENV_FILE"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG2B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG2B_CMD); \
	 fi

segment3a:
	@echo "Running Segment 3A (S0-S7)"
	@if [ "$(SKIP_SEG3A)" = "1" ]; then \
		if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
			echo "SKIP_SEG3A=1 but summary '$(SEG3A_RESULT_JSON)' is missing. Run 'make segment3a' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer1/3A" ]; then \
			echo "SKIP_SEG3A=1 but outputs missing under '$(RUN_ROOT)/data/layer1/3A'. Run 'make segment3a' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 3A (SKIP_SEG3A=1)"; \
		exit 0; \
	fi
	@if [ ! -d "$(RUN_ROOT)/data/layer1/2A" ]; then \
		echo "Segment 2A outputs not found under '$(RUN_ROOT)/data/layer1/2A'. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG2A_RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 UPSTREAM_MANIFEST_FINGERPRINT=$$SEG2A_MANIFEST_FINGERPRINT; \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG3A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG3A_CMD); \
	 fi

segment3b:
	@echo "Running Segment 3B (S0-S5)"
	@if [ "$(SKIP_SEG3B)" = "1" ]; then \
		if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
			echo "SKIP_SEG3B=1 but summary '$(SEG3B_RESULT_JSON)' is missing. Run 'make segment3b' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer1/3B" ]; then \
			echo "SKIP_SEG3B=1 but outputs missing under '$(RUN_ROOT)/data/layer1/3B'. Run 'make segment3b' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 3B (SKIP_SEG3B=1)"; \
		exit 0; \
	fi
	@if [ ! -d "$(RUN_ROOT)/data/layer1/3A" ]; then \
		echo "Segment 3A outputs not found under '$(RUN_ROOT)/data/layer1/3A'. Run 'make segment3a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
		echo "Segment 2B summary '$(SEG2B_RESULT_JSON)' not found. Run 'make segment2b' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG2A_RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 SEG2B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG2B_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2B="$(call L1_VALIDATION_BUNDLE,2B,$$SEG2B_MANIFEST_FINGERPRINT)"; \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG3A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 UPSTREAM_MANIFEST_FINGERPRINT=$$SEG3A_MANIFEST_FINGERPRINT; \
	 VALIDATION_BUNDLE_3A="$(call L1_VALIDATION_BUNDLE,3A,$$SEG3A_MANIFEST_FINGERPRINT)"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG3B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG3B_CMD); \
	 fi

segment5a:
	@echo "Running Segment 5A (S0-S5)"
	@if [ "$(SKIP_SEG5A)" = "1" ]; then \
		if [ ! -f "$(SEG5A_RESULT_JSON)" ]; then \
			echo "SKIP_SEG5A=1 but summary '$(SEG5A_RESULT_JSON)' is missing. Run 'make segment5a' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer2/5A" ]; then \
			echo "SKIP_SEG5A=1 but outputs missing under '$(RUN_ROOT)/data/layer2/5A'. Run 'make segment5a' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 5A (SKIP_SEG5A=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG1B_RESULT_JSON)" ]; then \
		echo "Segment 1B summary '$(SEG1B_RESULT_JSON)' not found. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
		echo "Segment 2B summary '$(SEG2B_RESULT_JSON)' not found. Run 'make segment2b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
		echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found. Run 'make segment3a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
		echo "Segment 3B summary '$(SEG3B_RESULT_JSON)' not found. Run 'make segment3b' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG3B_RESULT_JSON)'))['parameter_hash'])"); \
	 UPSTREAM_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG3B_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 SEG1A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG1B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json, re; data=json.load(open('$(SEG1B_RESULT_JSON)')); mf=data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or ''; \
receipt=data.get('s0_receipt',''); m=re.search(r'(?:manifest_fingerprint|fingerprint)=([a-f0-9]{64})', receipt); mf=mf or (m.group(1) if m else ''); print(mf)"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG2B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$SEG1A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$SEG1B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2B="$(call L1_VALIDATION_BUNDLE,2B,$$SEG2B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3A="$(call L1_VALIDATION_BUNDLE,3A,$$SEG3A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3B="$(call L1_VALIDATION_BUNDLE,3B,$$SEG3B_MANIFEST_FINGERPRINT)"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG5A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG5A_CMD); \
	 fi

segment5b:
	@echo "Running Segment 5B (S0-S5)"
	@if [ "$(SKIP_SEG5B)" = "1" ]; then \
		if [ ! -f "$(SEG5B_RESULT_JSON)" ]; then \
			echo "SKIP_SEG5B=1 but summary '$(SEG5B_RESULT_JSON)' is missing. Run 'make segment5b' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer2/5B" ]; then \
			echo "SKIP_SEG5B=1 but outputs missing under '$(RUN_ROOT)/data/layer2/5B'. Run 'make segment5b' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 5B (SKIP_SEG5B=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG1B_RESULT_JSON)" ]; then \
		echo "Segment 1B summary '$(SEG1B_RESULT_JSON)' not found. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
		echo "Segment 2B summary '$(SEG2B_RESULT_JSON)' not found. Run 'make segment2b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
		echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found. Run 'make segment3a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
		echo "Segment 3B summary '$(SEG3B_RESULT_JSON)' not found. Run 'make segment3b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG5A_RESULT_JSON)" ]; then \
		echo "Segment 5A summary '$(SEG5A_RESULT_JSON)' not found. Run 'make segment5a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG5A_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG5A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 SEG1A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG1B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json, re; data=json.load(open('$(SEG1B_RESULT_JSON)')); mf=data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or ''; \
receipt=data.get('s0_receipt',''); m=re.search(r'(?:manifest_fingerprint|fingerprint)=([a-f0-9]{64})', receipt); mf=mf or (m.group(1) if m else ''); print(mf)"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG2B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG5A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG5A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$SEG1A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$SEG1B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2B="$(call L1_VALIDATION_BUNDLE,2B,$$SEG2B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3A="$(call L1_VALIDATION_BUNDLE,3A,$$SEG3A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3B="$(call L1_VALIDATION_BUNDLE,3B,$$SEG3B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_5A="$(call L2_VALIDATION_BUNDLE,5A,$$SEG5A_MANIFEST_FINGERPRINT)"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG5B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG5B_CMD); \
	 fi

segment6a:
	@echo "Running Segment 6A (S0-S5)"
	@if [ "$(SKIP_SEG6A)" = "1" ]; then \
		if [ ! -f "$(SEG6A_RESULT_JSON)" ]; then \
			echo "SKIP_SEG6A=1 but summary '$(SEG6A_RESULT_JSON)' is missing. Run 'make segment6a' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer3/6A" ]; then \
			echo "SKIP_SEG6A=1 but outputs missing under '$(RUN_ROOT)/data/layer3/6A'. Run 'make segment6a' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 6A (SKIP_SEG6A=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG1B_RESULT_JSON)" ]; then \
		echo "Segment 1B summary '$(SEG1B_RESULT_JSON)' not found. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
		echo "Segment 2B summary '$(SEG2B_RESULT_JSON)' not found. Run 'make segment2b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
		echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found. Run 'make segment3a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
		echo "Segment 3B summary '$(SEG3B_RESULT_JSON)' not found. Run 'make segment3b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG5A_RESULT_JSON)" ]; then \
		echo "Segment 5A summary '$(SEG5A_RESULT_JSON)' not found. Run 'make segment5a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG5B_RESULT_JSON)" ]; then \
		echo "Segment 5B summary '$(SEG5B_RESULT_JSON)' not found. Run 'make segment5b' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG5B_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG5B_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 SEG1A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG1B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json, re; data=json.load(open('$(SEG1B_RESULT_JSON)')); mf=data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or ''; \
receipt=data.get('s0_receipt',''); m=re.search(r'(?:manifest_fingerprint|fingerprint)=([a-f0-9]{64})', receipt); mf=mf or (m.group(1) if m else ''); print(mf)"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG2B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG5A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG5A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG5B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG5B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$SEG1A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$SEG1B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2B="$(call L1_VALIDATION_BUNDLE,2B,$$SEG2B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3A="$(call L1_VALIDATION_BUNDLE,3A,$$SEG3A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3B="$(call L1_VALIDATION_BUNDLE,3B,$$SEG3B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_5A="$(call L2_VALIDATION_BUNDLE,5A,$$SEG5A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_5B="$(call L2_VALIDATION_BUNDLE,5B,$$SEG5B_MANIFEST_FINGERPRINT)"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG6A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG6A_CMD); \
	 fi

segment6b:
	@echo "Running Segment 6B (S0-S5)"
	@if [ "$(SKIP_SEG6B)" = "1" ]; then \
		if [ ! -f "$(SEG6B_RESULT_JSON)" ]; then \
			echo "SKIP_SEG6B=1 but summary '$(SEG6B_RESULT_JSON)' is missing. Run 'make segment6b' first." >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$(RUN_ROOT)/data/layer3/6B" ]; then \
			echo "SKIP_SEG6B=1 but outputs missing under '$(RUN_ROOT)/data/layer3/6B'. Run 'make segment6b' first." >&2; \
			exit 1; \
		fi; \
		echo "Skipping Segment 6B (SKIP_SEG6B=1)"; \
		exit 0; \
	fi
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG1B_RESULT_JSON)" ]; then \
		echo "Segment 1B summary '$(SEG1B_RESULT_JSON)' not found. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2A_RESULT_JSON)" ]; then \
		echo "Segment 2A summary '$(SEG2A_RESULT_JSON)' not found. Run 'make segment2a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG2B_RESULT_JSON)" ]; then \
		echo "Segment 2B summary '$(SEG2B_RESULT_JSON)' not found. Run 'make segment2b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
		echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found. Run 'make segment3a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
		echo "Segment 3B summary '$(SEG3B_RESULT_JSON)' not found. Run 'make segment3b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG5A_RESULT_JSON)" ]; then \
		echo "Segment 5A summary '$(SEG5A_RESULT_JSON)' not found. Run 'make segment5a' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG5B_RESULT_JSON)" ]; then \
		echo "Segment 5B summary '$(SEG5B_RESULT_JSON)' not found. Run 'make segment5b' first." >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(SEG6A_RESULT_JSON)" ]; then \
		echo "Segment 6A summary '$(SEG6A_RESULT_JSON)' not found. Run 'make segment6a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG6A_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG6A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 SEG1A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG1B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json, re; data=json.load(open('$(SEG1B_RESULT_JSON)')); mf=data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or ''; \
receipt=data.get('s0_receipt',''); m=re.search(r'(?:manifest_fingerprint|fingerprint)=([a-f0-9]{64})', receipt); mf=mf or (m.group(1) if m else ''); print(mf)"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG2B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG2B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG3B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG3B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG5A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG5A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG5B_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG5B_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 SEG6A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; data=json.load(open('$(SEG6A_RESULT_JSON)')); print(data.get('manifest_fingerprint') or data.get('s0',{}).get('manifest_fingerprint') or '')"); \
	 VALIDATION_BUNDLE_1A="$(call L1_VALIDATION_BUNDLE,1A,$$SEG1A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_1B="$(call L1_VALIDATION_BUNDLE,1B,$$SEG1B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2A="$(call L1_VALIDATION_BUNDLE,2A,$$SEG2A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_2B="$(call L1_VALIDATION_BUNDLE,2B,$$SEG2B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3A="$(call L1_VALIDATION_BUNDLE,3A,$$SEG3A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_3B="$(call L1_VALIDATION_BUNDLE,3B,$$SEG3B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_5A="$(call L2_VALIDATION_BUNDLE,5A,$$SEG5A_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_5B="$(call L2_VALIDATION_BUNDLE,5B,$$SEG5B_MANIFEST_FINGERPRINT)"; \
	 VALIDATION_BUNDLE_6A="$(call L3_VALIDATION_BUNDLE,6A,$$SEG6A_MANIFEST_FINGERPRINT)"; \
	if [ -n "$(LOG)" ]; then \
		($(SEG6B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	else \
		$(SEG6B_CMD); \
	fi

paths-tree:
	@$(PY_SCRIPT) scripts/build_paths_tree.py

contracts-sync:
	@$(PY_SCRIPT) tools/sync_contracts_from_model_spec.py --force

contracts-pack: contracts-sync
	@$(PY_SCRIPT) tools/build_contracts_pack.py --tag "$(CONTRACTS_PACK_TAG)" --force

profile-all:
	$(PY_ENGINE) -m cProfile -o profile.segment1a -m engine.cli.segment1a $(SEG1A_ARGS)
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 $(PY_ENGINE) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

profile-seg1b:
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 $(PY_ENGINE) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

clean-results:
	rm -rf "$(SUMMARY_DIR)"
	rm -f profile.segment1a profile.segment1b
