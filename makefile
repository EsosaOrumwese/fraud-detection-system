SHELL := C:/Progra~1/Git/bin/bash.exe
.SHELLFLAGS := -eu -o pipefail -c

-include .env.platform.local
-include .env.local

PY ?= $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,python)
ENGINE_PYTHONPATH ?= packages/engine/src
PYTHONUNBUFFERED ?= 1

# Python command wrappers (unbuffered to keep console output responsive).
PY_ENGINE = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY)
PY_SCRIPT = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) $(PY)
PY_PLATFORM = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) PYTHONPATH=src $(PY)

# ---------------------------------------------------------------------------
# Engine CLI defaults (dev/prod contract switching)
# ---------------------------------------------------------------------------
ENGINE_CONTRACTS_LAYOUT ?= model_spec
ENGINE_CONTRACTS_ROOT ?=
ENGINE_EXTERNAL_ROOTS ?=
ENGINE_RUNS_ROOT ?= $(RUNS_ROOT)
ENGINE_5B_S2_RNG_EVENTS ?= 0
ENGINE_5B_S3_RNG_EVENTS ?= 0
ENGINE_5B_S4_RNG_EVENTS ?= 0
ENGINE_5B_S4_VALIDATE_EVENTS_LIMIT ?= 1000
ENGINE_5B_S4_VALIDATE_EVENTS_FULL ?= 0
ENGINE_5B_S4_EVENT_BUFFER ?= 5000
ENGINE_5B_S4_BATCH_ROWS ?= 200000
ENGINE_5B_S4_MAX_ARRIVALS_CHUNK ?= 250000
ENGINE_5B_S4_VALIDATE_SAMPLE_ROWS ?= 2000
ENGINE_5B_S4_VALIDATE_FULL ?= 0
ENGINE_5B_S4_INCLUDE_LAMBDA ?= 0
ENGINE_5B_S4_REQUIRE_NUMBA ?= 1
ENGINE_5B_S4_STRICT_ORDERING ?= 0
ENGINE_5B_S3_WORKERS ?= 6
ENGINE_5B_S3_INFLIGHT_BATCHES ?= 12
ENGINE_5B_S3_EVENT_BUFFER ?= 10000
ENGINE_5B_S3_VALIDATE_EVENTS_LIMIT ?= 1000
ENGINE_6A_S4_WORKERS ?=
ENGINE_6B_S1_BATCH_ROWS ?= 250000
ENGINE_6B_S1_PARQUET_COMPRESSION ?= zstd
ENGINE_6B_S2_BATCH_ROWS ?= 250000
ENGINE_6B_S2_PARQUET_COMPRESSION ?= zstd
ENGINE_6B_S3_BATCH_ROWS ?= 250000
ENGINE_6B_S3_PARQUET_COMPRESSION ?= zstd
ENGINE_6B_S4_BATCH_ROWS ?= 250000
ENGINE_6B_S4_PARQUET_COMPRESSION ?= zstd
SEG1A_S0_SEED ?=
SEG1A_S0_MERCHANT_VERSION ?= $(MERCHANT_VERSION)
SEG1A_S0_EMIT_VALIDATION ?=
SEG1A_S1_RUN_ID ?= $(RUN_ID)
SEG1A_S2_RUN_ID ?= $(RUN_ID)
SEG1A_S3_RUN_ID ?= $(RUN_ID)
SEG1A_S4_RUN_ID ?= $(RUN_ID)
SEG1A_S9_RUN_ID ?= $(RUN_ID)
SEG1B_S0_RUN_ID ?= $(RUN_ID)
SEG1B_S1_RUN_ID ?= $(RUN_ID)
SEG1B_S2_RUN_ID ?= $(RUN_ID)
SEG1B_S3_RUN_ID ?= $(RUN_ID)
SEG1B_S4_RUN_ID ?= $(RUN_ID)
SEG1B_S5_RUN_ID ?= $(RUN_ID)
SEG1B_S6_RUN_ID ?= $(RUN_ID)
SEG1B_S7_RUN_ID ?= $(RUN_ID)
SEG1B_S8_RUN_ID ?= $(RUN_ID)
SEG1B_S9_RUN_ID ?= $(RUN_ID)
SEG2A_S0_RUN_ID ?= $(RUN_ID)
SEG2A_S1_RUN_ID ?= $(RUN_ID)
SEG2A_S2_RUN_ID ?= $(RUN_ID)
SEG2A_S3_RUN_ID ?= $(RUN_ID)
SEG2A_S4_RUN_ID ?= $(RUN_ID)
SEG2A_S5_RUN_ID ?= $(RUN_ID)
SEG2B_S0_RUN_ID ?= $(RUN_ID)
SEG2B_S1_RUN_ID ?= $(RUN_ID)
SEG2B_S2_RUN_ID ?= $(RUN_ID)
SEG2B_S3_RUN_ID ?= $(RUN_ID)
SEG2B_S4_RUN_ID ?= $(RUN_ID)
SEG2B_S5_RUN_ID ?= $(RUN_ID)
SEG2B_S7_RUN_ID ?= $(RUN_ID)
SEG3A_S0_RUN_ID ?= $(RUN_ID)
SEG3A_S1_RUN_ID ?= $(RUN_ID)
SEG3A_S2_RUN_ID ?= $(RUN_ID)
SEG3A_S3_RUN_ID ?= $(RUN_ID)
SEG3A_S4_RUN_ID ?= $(RUN_ID)
SEG3A_S5_RUN_ID ?= $(RUN_ID)
SEG3A_S6_RUN_ID ?= $(RUN_ID)
SEG3A_S7_RUN_ID ?= $(RUN_ID)
SEG3B_S0_RUN_ID ?= $(RUN_ID)
SEG3B_S1_RUN_ID ?= $(RUN_ID)
SEG3B_S2_RUN_ID ?= $(RUN_ID)
SEG5B_S0_RUN_ID ?= $(RUN_ID)
SEG5B_S1_RUN_ID ?= $(RUN_ID)
SEG5B_S2_RUN_ID ?= $(RUN_ID)
SEG5B_S3_RUN_ID ?= $(RUN_ID)
SEG5B_S4_RUN_ID ?= $(RUN_ID)
SEG5B_S5_RUN_ID ?= $(RUN_ID)
SEG6A_S0_RUN_ID ?= $(RUN_ID)
SEG6A_S1_RUN_ID ?= $(RUN_ID)
SEG6A_S2_RUN_ID ?= $(RUN_ID)
SEG6A_S3_RUN_ID ?= $(RUN_ID)
SEG6A_S4_RUN_ID ?= $(RUN_ID)
SEG6A_S5_RUN_ID ?= $(RUN_ID)
SEG6B_S0_RUN_ID ?= $(RUN_ID)
SEG6B_S1_RUN_ID ?= $(RUN_ID)
SEG6B_S2_RUN_ID ?= $(RUN_ID)
SEG6B_S3_RUN_ID ?= $(RUN_ID)
SEG6B_S4_RUN_ID ?= $(RUN_ID)
SEG6B_S5_RUN_ID ?= $(RUN_ID)
SEG1B_S1_PREDICATE ?= center

# ---------------------------------------------------------------------------
# Run defaults
# ---------------------------------------------------------------------------
RUNS_ROOT ?= runs/local_full_run-5
RUN_ID ?=
RUN_ROOT ?= $(if $(strip $(RUN_ID)),$(RUNS_ROOT)/$(RUN_ID),$(RUNS_ROOT))
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
LOG ?= $(if $(strip $(RUN_ID)),$(RUN_ROOT)/run_log_$(RUN_ID).log,$(RUN_ROOT)/run_log_run-5.log)
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
# Run helpers
# ---------------------------------------------------------------------------
LATEST_RUN_ID = $(shell $(PY_SCRIPT) -c "import json, pathlib; root = pathlib.Path('$(RUNS_ROOT)'); ids = sorted([p.parent.name for p in root.glob('*/run_receipt.json')], key=lambda name: (root / name / 'run_receipt.json').stat().st_mtime); print(ids[-1] if ids else '')")
RUN_ID_OR_LATEST = $(if $(strip $(RUN_ID)),$(RUN_ID),$(LATEST_RUN_ID))

.PHONY: latest-run-id
latest-run-id:
	@latest="$(LATEST_RUN_ID)"; \
	if [ -z "$$latest" ]; then \
		echo "No run_receipt.json files found under $(RUNS_ROOT)." >&2; \
		exit 1; \
	fi; \
	echo "$$latest"

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
# Dev substrate migration defaults (Phase 1 bootstrap/preflight)
# ---------------------------------------------------------------------------
DEV_MIN_AWS_REGION ?= eu-west-2
DEV_MIN_SSM_PREFIX ?= /fraud-platform/dev_min
DEV_MIN_PHASE1_PREFLIGHT_OUTPUT ?=
DEV_MIN_ALLOW_MISSING_CONFLUENT_HANDLES ?=
DEV_MIN_SKIP_CONFLUENT_API_PROBE ?=
DEV_MIN_KAFKA_BOOTSTRAP ?=
DEV_MIN_KAFKA_API_KEY ?=
DEV_MIN_KAFKA_API_SECRET ?=

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
S7_INTEGERISATION_POLICY ?= config/layer1/1A/allocation/s7_integerisation_policy.yaml
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

SEG1A_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S0_SEED)),)
SEG1A_S0_ARGS += --seed $(SEG1A_S0_SEED)
endif
ifneq ($(strip $(SEG1A_S0_MERCHANT_VERSION)),)
SEG1A_S0_ARGS += --merchant-ids-version $(SEG1A_S0_MERCHANT_VERSION)
endif
ifeq ($(strip $(SEG1A_S0_EMIT_VALIDATION)),1)
SEG1A_S0_ARGS += --emit-validation-bundle
endif
ifeq ($(strip $(SEG1A_S0_EMIT_VALIDATION)),0)
SEG1A_S0_ARGS += --no-emit-validation-bundle
endif
SEG1A_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_foundations $(SEG1A_S0_ARGS)

SEG1A_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S1_RUN_ID)),)
SEG1A_S1_ARGS += --run-id $(SEG1A_S1_RUN_ID)
endif
SEG1A_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_hurdle $(SEG1A_S1_ARGS)

SEG1A_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S2_RUN_ID)),)
SEG1A_S2_ARGS += --run-id $(SEG1A_S2_RUN_ID)
endif
SEG1A_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_nb_outlets $(SEG1A_S2_ARGS)

SEG1A_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S3_RUN_ID)),)
SEG1A_S3_ARGS += --run-id $(SEG1A_S3_RUN_ID)
endif
SEG1A_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_crossborder $(SEG1A_S3_ARGS)

SEG1A_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S4_RUN_ID)),)
SEG1A_S4_ARGS += --run-id $(SEG1A_S4_RUN_ID)
endif
SEG1A_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_ztp $(SEG1A_S4_ARGS)

SEG1A_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S5_RUN_ID)),)
SEG1A_S5_ARGS += --run-id $(SEG1A_S5_RUN_ID)
endif
ifneq ($(strip $(SEG1A_S5_EMIT_SPARSE_FLAG)),)
SEG1A_S5_ARGS += --emit-sparse-flag
endif
ifneq ($(strip $(SEG1A_S5_FAIL_ON_DEGRADE)),)
SEG1A_S5_ARGS += --fail-on-degrade
endif
ifneq ($(strip $(SEG1A_S5_VALIDATE_ONLY)),)
SEG1A_S5_ARGS += --validate-only
endif
SEG1A_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_currency_weights $(SEG1A_S5_ARGS)

SEG1A_S6_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S6_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S6_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S6_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S6_RUN_ID)),)
SEG1A_S6_ARGS += --run-id $(SEG1A_S6_RUN_ID)
endif
ifneq ($(strip $(SEG1A_S6_EMIT_MEMBERSHIP)),)
SEG1A_S6_ARGS += --emit-membership-dataset
endif
ifneq ($(strip $(SEG1A_S6_LOG_ALL_CANDIDATES)),)
SEG1A_S6_ARGS += --log-all-candidates
endif
ifneq ($(strip $(SEG1A_S6_FAIL_ON_DEGRADE)),)
SEG1A_S6_ARGS += --fail-on-degrade
endif
ifneq ($(strip $(SEG1A_S6_VALIDATE_ONLY)),)
SEG1A_S6_ARGS += --validate-only
endif
SEG1A_S6_CMD = $(PY_ENGINE) -m engine.cli.s6_foreign_set $(SEG1A_S6_ARGS)

SEG1A_S7_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S7_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S7_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S7_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S7_RUN_ID)),)
SEG1A_S7_ARGS += --run-id $(SEG1A_S7_RUN_ID)
endif
ifneq ($(strip $(SEG1A_S7_VALIDATE_ONLY)),)
SEG1A_S7_ARGS += --validate-only
endif
SEG1A_S7_CMD = $(PY_ENGINE) -m engine.cli.s7_integerisation $(SEG1A_S7_ARGS)

SEG1A_S8_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S8_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S8_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S8_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S8_RUN_ID)),)
SEG1A_S8_ARGS += --run-id $(SEG1A_S8_RUN_ID)
endif
ifneq ($(strip $(SEG1A_S8_VALIDATE_ONLY)),)
SEG1A_S8_ARGS += --validate-only
endif
SEG1A_S8_CMD = $(PY_ENGINE) -m engine.cli.s8_outlet_catalogue $(SEG1A_S8_ARGS)

SEG1A_S9_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1A_S9_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1A_S9_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1A_S9_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1A_S9_RUN_ID)),)
SEG1A_S9_ARGS += --run-id $(SEG1A_S9_RUN_ID)
endif
ifneq ($(strip $(SEG1A_S9_VALIDATE_ONLY)),)
SEG1A_S9_ARGS += --validate-only
endif
SEG1A_S9_CMD = $(PY_ENGINE) -m engine.cli.s9_validation $(SEG1A_S9_ARGS)

SEG1B_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S0_RUN_ID)),)
SEG1B_S0_ARGS += --run-id $(SEG1B_S0_RUN_ID)
endif
SEG1B_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_1b $(SEG1B_S0_ARGS)

SEG1B_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S1_RUN_ID)),)
SEG1B_S1_ARGS += --run-id $(SEG1B_S1_RUN_ID)
endif
ifneq ($(strip $(SEG1B_S1_PREDICATE)),)
SEG1B_S1_ARGS += --predicate $(SEG1B_S1_PREDICATE)
endif
ifneq ($(strip $(SEG1B_S1_WORKERS)),)
SEG1B_S1_ARGS += --workers $(SEG1B_S1_WORKERS)
endif
SEG1B_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_tile_index $(SEG1B_S1_ARGS)

SEG1B_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S2_RUN_ID)),)
SEG1B_S2_ARGS += --run-id $(SEG1B_S2_RUN_ID)
endif
SEG1B_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_tile_weights $(SEG1B_S2_ARGS)

SEG1B_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S3_RUN_ID)),)
SEG1B_S3_ARGS += --run-id $(SEG1B_S3_RUN_ID)
endif
SEG1B_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_requirements $(SEG1B_S3_ARGS)

SEG1B_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S4_RUN_ID)),)
SEG1B_S4_ARGS += --run-id $(SEG1B_S4_RUN_ID)
endif
SEG1B_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_alloc_plan $(SEG1B_S4_ARGS)

SEG1B_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S5_RUN_ID)),)
SEG1B_S5_ARGS += --run-id $(SEG1B_S5_RUN_ID)
endif
SEG1B_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_site_tile_assignment $(SEG1B_S5_ARGS)

SEG1B_S6_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S6_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S6_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S6_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S6_RUN_ID)),)
SEG1B_S6_ARGS += --run-id $(SEG1B_S6_RUN_ID)
endif
SEG1B_S6_CMD = $(PY_ENGINE) -m engine.cli.s6_site_jitter $(SEG1B_S6_ARGS)

SEG1B_S7_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S7_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S7_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S7_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S7_RUN_ID)),)
SEG1B_S7_ARGS += --run-id $(SEG1B_S7_RUN_ID)
endif
SEG1B_S7_CMD = $(PY_ENGINE) -m engine.cli.s7_site_synthesis $(SEG1B_S7_ARGS)

SEG1B_S8_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S8_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S8_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S8_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S8_RUN_ID)),)
SEG1B_S8_ARGS += --run-id $(SEG1B_S8_RUN_ID)
endif
SEG1B_S8_CMD = $(PY_ENGINE) -m engine.cli.s8_site_locations $(SEG1B_S8_ARGS)

SEG1B_S9_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG1B_S9_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG1B_S9_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG1B_S9_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG1B_S9_RUN_ID)),)
SEG1B_S9_ARGS += --run-id $(SEG1B_S9_RUN_ID)
endif
SEG1B_S9_CMD = $(PY_ENGINE) -m engine.cli.s9_validation_bundle $(SEG1B_S9_ARGS)

SEG2A_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S0_RUN_ID)),)
SEG2A_S0_ARGS += --run-id $(SEG2A_S0_RUN_ID)
endif
SEG2A_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_2a $(SEG2A_S0_ARGS)

SEG2A_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S1_RUN_ID)),)
SEG2A_S1_ARGS += --run-id $(SEG2A_S1_RUN_ID)
endif
SEG2A_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_tz_lookup_2a $(SEG2A_S1_ARGS)

SEG2A_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S2_RUN_ID)),)
SEG2A_S2_ARGS += --run-id $(SEG2A_S2_RUN_ID)
endif
SEG2A_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_overrides_2a $(SEG2A_S2_ARGS)

SEG2A_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S3_RUN_ID)),)
SEG2A_S3_ARGS += --run-id $(SEG2A_S3_RUN_ID)
endif
SEG2A_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_timetable_2a $(SEG2A_S3_ARGS)

SEG2A_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S4_RUN_ID)),)
SEG2A_S4_ARGS += --run-id $(SEG2A_S4_RUN_ID)
endif
SEG2A_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_legality_2a $(SEG2A_S4_ARGS)

SEG2A_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2A_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2A_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2A_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2A_S5_RUN_ID)),)
SEG2A_S5_ARGS += --run-id $(SEG2A_S5_RUN_ID)
endif
SEG2A_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_validation_bundle_2a $(SEG2A_S5_ARGS)

SEG2B_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S0_RUN_ID)),)
SEG2B_S0_ARGS += --run-id $(SEG2B_S0_RUN_ID)
endif
SEG2B_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_2b $(SEG2B_S0_ARGS)

SEG2B_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S1_RUN_ID)),)
SEG2B_S1_ARGS += --run-id $(SEG2B_S1_RUN_ID)
endif
SEG2B_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_site_weights_2b $(SEG2B_S1_ARGS)

SEG2B_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S2_RUN_ID)),)
SEG2B_S2_ARGS += --run-id $(SEG2B_S2_RUN_ID)
endif
SEG2B_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_alias_tables_2b $(SEG2B_S2_ARGS)

SEG2B_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S3_RUN_ID)),)
SEG2B_S3_ARGS += --run-id $(SEG2B_S3_RUN_ID)
endif
SEG2B_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_day_effects_2b $(SEG2B_S3_ARGS)

SEG2B_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S4_RUN_ID)),)
SEG2B_S4_ARGS += --run-id $(SEG2B_S4_RUN_ID)
endif
SEG2B_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_group_weights_2b $(SEG2B_S4_ARGS)

SEG2B_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S5_RUN_ID)),)
SEG2B_S5_ARGS += --run-id $(SEG2B_S5_RUN_ID)
endif
SEG2B_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_router_2b $(SEG2B_S5_ARGS)

SEG2B_S6_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S6_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S6_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S6_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S6_RUN_ID)),)
SEG2B_S6_ARGS += --run-id $(SEG2B_S6_RUN_ID)
endif
SEG2B_S6_CMD = $(PY_ENGINE) -m engine.cli.s6_edge_router_2b $(SEG2B_S6_ARGS)

SEG2B_S7_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S7_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S7_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S7_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S7_RUN_ID)),)
SEG2B_S7_ARGS += --run-id $(SEG2B_S7_RUN_ID)
endif
SEG2B_S7_CMD = $(PY_ENGINE) -m engine.cli.s7_audit_2b $(SEG2B_S7_ARGS)

SEG2B_S8_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG2B_S8_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG2B_S8_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG2B_S8_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG2B_S8_RUN_ID)),)
SEG2B_S8_ARGS += --run-id $(SEG2B_S8_RUN_ID)
endif
SEG2B_S8_CMD = $(PY_ENGINE) -m engine.cli.s8_validation_bundle_2b $(SEG2B_S8_ARGS)

SEG3A_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S0_RUN_ID)),)
SEG3A_S0_ARGS += --run-id $(SEG3A_S0_RUN_ID)
endif
SEG3A_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_3a $(SEG3A_S0_ARGS)

SEG3B_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S0_RUN_ID)),)
SEG3B_S0_ARGS += --run-id $(SEG3B_S0_RUN_ID)
endif
SEG3B_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_3b $(SEG3B_S0_ARGS)

SEG5A_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S0_RUN_ID)),)
SEG5A_S0_ARGS += --run-id $(SEG5A_S0_RUN_ID)
endif
SEG5A_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_5a $(SEG5A_S0_ARGS)

SEG5B_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S0_RUN_ID)),)
SEG5B_S0_ARGS += --run-id $(SEG5B_S0_RUN_ID)
endif
SEG5B_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_5b $(SEG5B_S0_ARGS)

SEG6A_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S0_RUN_ID)),)
SEG6A_S0_ARGS += --run-id $(SEG6A_S0_RUN_ID)
endif
SEG6A_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_6a $(SEG6A_S0_ARGS)

SEG6B_S0_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S0_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S0_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S0_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6B_S0_RUN_ID)),)
SEG6B_S0_ARGS += --run-id $(SEG6B_S0_RUN_ID)
endif
SEG6B_S0_CMD = $(PY_ENGINE) -m engine.cli.s0_gate_6b $(SEG6B_S0_ARGS)

SEG6B_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
SEG6B_S1_ARGS += --batch-rows $(ENGINE_6B_S1_BATCH_ROWS)
SEG6B_S1_ARGS += --parquet-compression $(ENGINE_6B_S1_PARQUET_COMPRESSION)
ifneq ($(strip $(SEG6B_S1_RUN_ID)),)
SEG6B_S1_ARGS += --run-id $(SEG6B_S1_RUN_ID)
endif
SEG6B_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_attachment_session_6b $(SEG6B_S1_ARGS)

SEG6B_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
SEG6B_S2_ARGS += --batch-rows $(ENGINE_6B_S2_BATCH_ROWS)
SEG6B_S2_ARGS += --parquet-compression $(ENGINE_6B_S2_PARQUET_COMPRESSION)
ifneq ($(strip $(SEG6B_S2_RUN_ID)),)
SEG6B_S2_ARGS += --run-id $(SEG6B_S2_RUN_ID)
endif
SEG6B_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_baseline_flow_6b $(SEG6B_S2_ARGS)

SEG6B_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
SEG6B_S3_ARGS += --batch-rows $(ENGINE_6B_S3_BATCH_ROWS)
SEG6B_S3_ARGS += --parquet-compression $(ENGINE_6B_S3_PARQUET_COMPRESSION)
ifneq ($(strip $(SEG6B_S3_RUN_ID)),)
SEG6B_S3_ARGS += --run-id $(SEG6B_S3_RUN_ID)
endif
SEG6B_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_fraud_overlay_6b $(SEG6B_S3_ARGS)

SEG6B_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
SEG6B_S4_ARGS += --batch-rows $(ENGINE_6B_S4_BATCH_ROWS)
SEG6B_S4_ARGS += --parquet-compression $(ENGINE_6B_S4_PARQUET_COMPRESSION)
ifneq ($(strip $(SEG6B_S4_RUN_ID)),)
SEG6B_S4_ARGS += --run-id $(SEG6B_S4_RUN_ID)
endif
SEG6B_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_truth_bank_labels_6b $(SEG6B_S4_ARGS)

SEG6B_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6B_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6B_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6B_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6B_S5_RUN_ID)),)
SEG6B_S5_ARGS += --run-id $(SEG6B_S5_RUN_ID)
endif
SEG6B_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_validation_gate_6b $(SEG6B_S5_ARGS)

SEG6A_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S1_RUN_ID)),)
SEG6A_S1_ARGS += --run-id $(SEG6A_S1_RUN_ID)
endif
SEG6A_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_party_base_6a $(SEG6A_S1_ARGS)

SEG6A_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S2_RUN_ID)),)
SEG6A_S2_ARGS += --run-id $(SEG6A_S2_RUN_ID)
endif
SEG6A_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_account_base_6a $(SEG6A_S2_ARGS)

SEG6A_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S3_RUN_ID)),)
SEG6A_S3_ARGS += --run-id $(SEG6A_S3_RUN_ID)
endif
SEG6A_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_instrument_base_6a $(SEG6A_S3_ARGS)

SEG6A_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S4_RUN_ID)),)
SEG6A_S4_ARGS += --run-id $(SEG6A_S4_RUN_ID)
endif
SEG6A_S4_CMD = \
	$(if $(strip $(ENGINE_6A_S4_WORKERS)),ENGINE_6A_S4_WORKERS=$(ENGINE_6A_S4_WORKERS)) \
	$(PY_ENGINE) -m engine.cli.s4_device_graph_6a $(SEG6A_S4_ARGS)
SEG6A_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG6A_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG6A_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG6A_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG6A_S5_RUN_ID)),)
SEG6A_S5_ARGS += --run-id $(SEG6A_S5_RUN_ID)
endif
SEG6A_S5_CMD = \
	$(PY_ENGINE) -m engine.cli.s5_fraud_posture_6a $(SEG6A_S5_ARGS)

SEG5B_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S1_RUN_ID)),)
SEG5B_S1_ARGS += --run-id $(SEG5B_S1_RUN_ID)
endif
SEG5B_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_time_grid_5b $(SEG5B_S1_ARGS)

SEG5B_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S2_RUN_ID)),)
SEG5B_S2_ARGS += --run-id $(SEG5B_S2_RUN_ID)
endif
SEG5B_S2_CMD = \
	ENGINE_5B_S2_RNG_EVENTS=$(ENGINE_5B_S2_RNG_EVENTS) \
	$(PY_ENGINE) -m engine.cli.s2_latent_intensity_5b $(SEG5B_S2_ARGS)

SEG5B_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S3_RUN_ID)),)
SEG5B_S3_ARGS += --run-id $(SEG5B_S3_RUN_ID)
endif
SEG5B_S3_CMD = \
	ENGINE_5B_S3_RNG_EVENTS=$(ENGINE_5B_S3_RNG_EVENTS) \
	ENGINE_5B_S3_WORKERS=$(ENGINE_5B_S3_WORKERS) \
	ENGINE_5B_S3_INFLIGHT_BATCHES=$(ENGINE_5B_S3_INFLIGHT_BATCHES) \
	ENGINE_5B_S3_EVENT_BUFFER=$(ENGINE_5B_S3_EVENT_BUFFER) \
	ENGINE_5B_S3_VALIDATE_EVENTS_LIMIT=$(ENGINE_5B_S3_VALIDATE_EVENTS_LIMIT) \
	$(PY_ENGINE) -m engine.cli.s3_bucket_counts_5b $(SEG5B_S3_ARGS)

SEG5B_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S4_RUN_ID)),)
SEG5B_S4_ARGS += --run-id $(SEG5B_S4_RUN_ID)
endif
SEG5B_S4_CMD = \
	ENGINE_5B_S4_RNG_EVENTS=$(ENGINE_5B_S4_RNG_EVENTS) \
	ENGINE_5B_S4_VALIDATE_EVENTS_LIMIT=$(ENGINE_5B_S4_VALIDATE_EVENTS_LIMIT) \
	ENGINE_5B_S4_VALIDATE_EVENTS_FULL=$(ENGINE_5B_S4_VALIDATE_EVENTS_FULL) \
	ENGINE_5B_S4_EVENT_BUFFER=$(ENGINE_5B_S4_EVENT_BUFFER) \
	ENGINE_5B_S4_BATCH_ROWS=$(ENGINE_5B_S4_BATCH_ROWS) \
	ENGINE_5B_S4_MAX_ARRIVALS_CHUNK=$(ENGINE_5B_S4_MAX_ARRIVALS_CHUNK) \
	ENGINE_5B_S4_VALIDATE_SAMPLE_ROWS=$(ENGINE_5B_S4_VALIDATE_SAMPLE_ROWS) \
	ENGINE_5B_S4_VALIDATE_FULL=$(ENGINE_5B_S4_VALIDATE_FULL) \
	ENGINE_5B_S4_INCLUDE_LAMBDA=$(ENGINE_5B_S4_INCLUDE_LAMBDA) \
	ENGINE_5B_S4_REQUIRE_NUMBA=$(ENGINE_5B_S4_REQUIRE_NUMBA) \
	ENGINE_5B_S4_STRICT_ORDERING=$(ENGINE_5B_S4_STRICT_ORDERING) \
	$(PY_ENGINE) -m engine.cli.s4_arrival_events_5b $(SEG5B_S4_ARGS)

SEG5B_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5B_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5B_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5B_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5B_S5_RUN_ID)),)
SEG5B_S5_ARGS += --run-id $(SEG5B_S5_RUN_ID)
endif
SEG5B_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_validation_bundle_5b $(SEG5B_S5_ARGS)


SEG5A_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S1_RUN_ID)),)
SEG5A_S1_ARGS += --run-id $(SEG5A_S1_RUN_ID)
endif
SEG5A_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_demand_classification_5a $(SEG5A_S1_ARGS)

SEG5A_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S2_RUN_ID)),)
SEG5A_S2_ARGS += --run-id $(SEG5A_S2_RUN_ID)
endif
SEG5A_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_weekly_shape_library_5a $(SEG5A_S2_ARGS)

SEG5A_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S3_RUN_ID)),)
SEG5A_S3_ARGS += --run-id $(SEG5A_S3_RUN_ID)
endif
SEG5A_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_baseline_intensity_5a $(SEG5A_S3_ARGS)

SEG5A_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S4_RUN_ID)),)
SEG5A_S4_ARGS += --run-id $(SEG5A_S4_RUN_ID)
endif
SEG5A_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_calendar_overlays_5a $(SEG5A_S4_ARGS)

SEG5A_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG5A_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG5A_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG5A_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG5A_S5_RUN_ID)),)
SEG5A_S5_ARGS += --run-id $(SEG5A_S5_RUN_ID)
endif
SEG5A_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_validation_bundle_5a $(SEG5A_S5_ARGS)

SEG3B_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S1_RUN_ID)),)
SEG3B_S1_ARGS += --run-id $(SEG3B_S1_RUN_ID)
endif
SEG3B_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_virtual_classification_3b $(SEG3B_S1_ARGS)

SEG3B_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S2_RUN_ID)),)
SEG3B_S2_ARGS += --run-id $(SEG3B_S2_RUN_ID)
endif
SEG3B_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_edge_catalogue_3b $(SEG3B_S2_ARGS)

SEG3B_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S3_RUN_ID)),)
SEG3B_S3_ARGS += --run-id $(SEG3B_S3_RUN_ID)
endif
SEG3B_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_alias_tables_3b $(SEG3B_S3_ARGS)

SEG3B_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S4_RUN_ID)),)
SEG3B_S4_ARGS += --run-id $(SEG3B_S4_RUN_ID)
endif
SEG3B_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_virtual_contracts_3b $(SEG3B_S4_ARGS)

SEG3B_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3B_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3B_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3B_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3B_S5_RUN_ID)),)
SEG3B_S5_ARGS += --run-id $(SEG3B_S5_RUN_ID)
endif
SEG3B_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_validation_bundle_3b $(SEG3B_S5_ARGS)

SEG3A_S1_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S1_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S1_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S1_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S1_RUN_ID)),)
SEG3A_S1_ARGS += --run-id $(SEG3A_S1_RUN_ID)
endif
SEG3A_S1_CMD = $(PY_ENGINE) -m engine.cli.s1_escalation_3a $(SEG3A_S1_ARGS)

SEG3A_S2_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S2_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S2_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S2_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S2_RUN_ID)),)
SEG3A_S2_ARGS += --run-id $(SEG3A_S2_RUN_ID)
endif
SEG3A_S2_CMD = $(PY_ENGINE) -m engine.cli.s2_priors_3a $(SEG3A_S2_ARGS)

SEG3A_S3_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S3_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S3_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S3_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S3_RUN_ID)),)
SEG3A_S3_ARGS += --run-id $(SEG3A_S3_RUN_ID)
endif
SEG3A_S3_CMD = $(PY_ENGINE) -m engine.cli.s3_zone_shares_3a $(SEG3A_S3_ARGS)

SEG3A_S4_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S4_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S4_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S4_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S4_RUN_ID)),)
SEG3A_S4_ARGS += --run-id $(SEG3A_S4_RUN_ID)
endif
SEG3A_S4_CMD = $(PY_ENGINE) -m engine.cli.s4_zone_counts_3a $(SEG3A_S4_ARGS)

SEG3A_S5_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S5_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S5_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S5_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S5_RUN_ID)),)
SEG3A_S5_ARGS += --run-id $(SEG3A_S5_RUN_ID)
endif
SEG3A_S5_CMD = $(PY_ENGINE) -m engine.cli.s5_zone_alloc_3a $(SEG3A_S5_ARGS)

SEG3A_S6_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S6_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S6_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S6_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S6_RUN_ID)),)
SEG3A_S6_ARGS += --run-id $(SEG3A_S6_RUN_ID)
endif
SEG3A_S6_CMD = $(PY_ENGINE) -m engine.cli.s6_validation_3a $(SEG3A_S6_ARGS)

SEG3A_S7_ARGS = --contracts-layout $(ENGINE_CONTRACTS_LAYOUT)
ifneq ($(strip $(ENGINE_CONTRACTS_ROOT)),)
SEG3A_S7_ARGS += --contracts-root $(ENGINE_CONTRACTS_ROOT)
endif
ifneq ($(strip $(ENGINE_EXTERNAL_ROOTS)),)
SEG3A_S7_ARGS += $(foreach root,$(ENGINE_EXTERNAL_ROOTS),--external-root $(root))
endif
ifneq ($(strip $(ENGINE_RUNS_ROOT)),)
SEG3A_S7_ARGS += --runs-root $(ENGINE_RUNS_ROOT)
endif
ifneq ($(strip $(SEG3A_S7_RUN_ID)),)
SEG3A_S7_ARGS += --run-id $(SEG3A_S7_RUN_ID)
endif
SEG3A_S7_CMD = $(PY_ENGINE) -m engine.cli.s7_validation_bundle_3a $(SEG3A_S7_ARGS)

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
	s7_integerisation_policy.yaml=$(S7_INTEGERISATION_POLICY) \
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
SEG2B_S8_RUN_ID ?=

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
	--run-id $(RUN_ID_OR_LATEST) \
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
	--run-id "$(RUN_ID_OR_LATEST)" \
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
	--run-id "$(RUN_ID_OR_LATEST)" \
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
	--run-id "$(RUN_ID_OR_LATEST)" \
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
HRSL_S3_BUCKET ?= s3://dataforgood-fb-data/hrsl-cogs/hrsl_general/
HRSL_LOCAL_ROOT ?= artefacts/rasters/source/hrsl/hrsl_general
HRSL_S3_SYNC_CMD = aws s3 sync --no-sign-request $(HRSL_S3_BUCKET) "$(HRSL_LOCAL_ROOT)"
HRSL_RASTER_CMD = $(PY_SCRIPT) scripts/build_hrsl_raster_3b.py --vintage $(HRSL_VINTAGE) --semver $(HRSL_SEMVER)
PELIAS_VERSION = 2025-12-31
PELIAS_CACHED_CMD = $(PY_SCRIPT) scripts/build_pelias_cached_sqlite_3b.py --pelias-version $(PELIAS_VERSION)
VIRTUAL_SETTLEMENT_CMD = $(PY_SCRIPT) scripts/build_virtual_settlement_coords_3b.py


.PHONY: all preflight-seg1a segment1a segment1a-s0 segment1a-s1 segment1a-s2 segment1a-s3 segment1a-s4 segment1a-s5 segment1a-s6 segment1a-s7 segment1a-s8 segment1a-s9 segment1a-s9-archive segment1b segment1b-s0 segment1b-s1 segment1b-s2 segment1b-s3 segment1b-s4 segment1b-s5 segment1b-s6 segment1b-s7 segment1b-s8 segment1b-s9 segment1b-s9-archive segment2a-s0 segment2a-s1 segment2a-s2 segment2a-s3 segment2a-s4 segment2a-s5 segment2b segment2b-s0 segment2b-s1 segment2b-s2 segment2b-s3 segment2b-s4 segment2b-s5 segment2b-s6 segment2b-s7 segment2b-s8 segment2b-arrival-roster segment3a segment3a-s0 segment3a-s1 segment3a-s2 segment3a-s3 segment3a-s4 segment3a-s5 segment3a-s6 segment3a-s7 segment3b-s0 segment3b-s1 segment3b-s2 segment3b-s3 segment3b-s4 segment3b-s5 segment5a segment5a-s0 segment5a-s1 segment5a-s2 segment5a-s3 segment5a-s4 segment5a-s5 segment5b-s0 segment5b-s1 segment5b-s2 segment5b-s3 segment5b-s4 segment5b-s5 segment6a-s0 segment6a-s1 segment6a-s2 segment6a-s3 segment6a-s4 segment6a-s5 segment6b-s0 segment6b-s1 segment6b-s2 segment6b-s3 segment6b-s4 segment6b-s5 segment6b merchant_ids hurdle_exports refresh_merchant_deps currency_refs virtual_edge_policy zone_floor_policy country_zone_alphas crossborder_features merchant_class_policy_5a demand_scale_policy_5a shape_library_5a scenario_calendar_5a policies_5a cdn_weights_ext mcc_channel_rules cdn_country_weights virtual_validation cdn_key_digest hrsl_raster pelias_cached virtual_settlement_coords profile-all profile-seg1b clean-results
.ONESHELL: segment1a segment1b 

all: segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a

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
	seed="$${SCENARIO_CAL_SEED:-}"; \
	if [ ! -f "$$run_root/run_receipt.json" ] && [ "$$run_root" = "$(RUNS_ROOT)" ] && [ -n "$(LATEST_RUN_ID)" ]; then \
		run_root="$(RUNS_ROOT)/$(LATEST_RUN_ID)"; \
	fi; \
	if [ -z "$$manifest" ]; then \
		if [ ! -f "$(SEG3A_RESULT_JSON)" ]; then \
			if [ -f "$$run_root/run_receipt.json" ]; then \
				manifest=$$($(PY) -c "import json; print(json.load(open('$$run_root/run_receipt.json')).get('manifest_fingerprint',''))"); \
			else \
				echo "Segment 3A summary '$(SEG3A_RESULT_JSON)' not found and run_receipt.json missing under $$run_root. Set SCENARIO_CAL_FINGERPRINT or run segment3a first." >&2; \
				exit 1; \
			fi; \
		else \
			manifest=$$($(PY) -c "import json; print(json.load(open('$(SEG3A_RESULT_JSON)'))['manifest_fingerprint'])"); \
		fi; \
	fi; \
	if [ -z "$$seed" ]; then \
		if [ -f "$$run_root/run_receipt.json" ]; then \
			seed=$$($(PY) -c "import json; print(json.load(open('$$run_root/run_receipt.json')).get('seed',''))"); \
		fi; \
	fi; \
	if [ -z "$$seed" ]; then \
		seed="$(SEED)"; \
	fi; \
	zone_alloc_dir="$$run_root/data/layer1/3A/zone_alloc/seed=$$seed/manifest_fingerprint=$$manifest"; \
	zone_alloc_path=$$(ls "$$zone_alloc_dir"/part-*.parquet 2>/dev/null | head -n 1); \
	if [ -z "$$zone_alloc_path" ]; then \
		echo "zone_alloc parquet not found under $$zone_alloc_dir" >&2; \
		exit 1; \
	fi; \
	echo "Building 5A scenario_calendar_5A (manifest_fingerprint $$manifest)"; \
	$(PY_SCRIPT) scripts/build_scenario_calendar_5a.py --manifest-fingerprint "$$manifest" --zone-alloc-path "$$zone_alloc_path" --output-root "$$run_root"

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
	@command -v aws >/dev/null 2>&1 || { echo "aws CLI not found; install AWS CLI v2 to sync HRSL tiles." >&2; exit 1; }
	@echo "Syncing HRSL tiles from $(HRSL_S3_BUCKET)"
	@$(HRSL_S3_SYNC_CMD)
	$(HRSL_RASTER_CMD) --local-root "$(HRSL_LOCAL_ROOT)" --require-local

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
	@$(PY) tools/preflight_seg1a_contracts.py
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

segment1a: segment1a-s0 segment1a-s1 segment1a-s2 segment1a-s3 segment1a-s4 segment1a-s5 segment1a-s6 segment1a-s7 segment1a-s8 segment1a-s9


segment1a-s0:
	@echo "Running Segment 1A S0 foundations"
	@$(SEG1A_S0_CMD)

engine-s0: segment1a-s0

segment1a-s1:
	@echo "Running Segment 1A S1 hurdle sampler"
	@$(SEG1A_S1_CMD)

engine-s1: segment1a-s1

segment1a-s2:
	@echo "Running Segment 1A S2 NB outlets sampler"
	@$(SEG1A_S2_CMD)

engine-s2: segment1a-s2

segment1a-s3:
	@echo "Running Segment 1A S3 cross-border candidate set"
	@$(SEG1A_S3_CMD)

engine-s3: segment1a-s3

segment1a-s4:
	@echo "Running Segment 1A S4 ZTP sampler"
	@$(SEG1A_S4_CMD)

engine-s4: segment1a-s4

segment1a-s5:
	@echo "Running Segment 1A S5 currency weights"
	@$(SEG1A_S5_CMD)

engine-s5: segment1a-s5

segment1a-s6:
	@echo "Running Segment 1A S6 foreign set selection"
	@$(SEG1A_S6_CMD)

engine-s6: segment1a-s6

segment1a-s7:
	@echo "Running Segment 1A S7 integer allocation"
	@$(SEG1A_S7_CMD)

engine-s7: segment1a-s7

segment1a-s8:
	@echo "Running Segment 1A S8 outlet catalogue"
	@$(SEG1A_S8_CMD)

engine-s8: segment1a-s8

segment1a-s9:
	@echo "Running Segment 1A S9 validation"
	@$(SEG1A_S9_CMD)

engine-s9: segment1a-s9

segment1a-s9-archive:
	@echo "Archiving Segment 1A S9 validation bundle"
	@$(PY_SCRIPT) -c "import json,pathlib,shutil,sys,time; runs_root=pathlib.Path('$(RUNS_ROOT)'); run_id='$(SEG1A_S9_RUN_ID)'.strip(); receipt_path=(runs_root/run_id/'run_receipt.json' if run_id else sorted(runs_root.glob('*/run_receipt.json'), key=lambda p: p.stat().st_mtime)[-1]); receipt=json.loads(receipt_path.read_text(encoding='utf-8')); run_id=receipt['run_id']; fingerprint=receipt['manifest_fingerprint']; bundle_root=runs_root/run_id/'data'/'layer1'/'1A'/'validation'/f'manifest_fingerprint={fingerprint}'; (bundle_root.exists() or sys.exit(f'Validation bundle not found: {bundle_root}')); timestamp=time.strftime('%Y%m%dT%H%M%S'); archive_root=runs_root/run_id/'data'/'layer1'/'1A'/'validation'/'_failed'/f'manifest_fingerprint={fingerprint}'/f'attempt={timestamp}'; archive_root.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(bundle_root), str(archive_root)); print(f'Archived {bundle_root} -> {archive_root}')"

segment1b: segment1b-s0 segment1b-s1 segment1b-s2 segment1b-s3 segment1b-s4 segment1b-s5 segment1b-s6 segment1b-s7 segment1b-s8 segment1b-s9

segment1b-s0:
	@echo "Running Segment 1B S0 gate-in"
	@$(SEG1B_S0_CMD)

segment1b-s1:
	@echo "Running Segment 1B S1 tile index"
	@$(SEG1B_S1_CMD)

segment1b-s2:
	@echo "Running Segment 1B S2 tile weights"
	@$(SEG1B_S2_CMD)

segment1b-s3:
	@echo "Running Segment 1B S3 requirements"
	@$(SEG1B_S3_CMD)

segment1b-s4:
	@echo "Running Segment 1B S4 allocation plan"
	@$(SEG1B_S4_CMD)

segment1b-s5:
	@echo "Running Segment 1B S5 site tile assignment"
	@$(SEG1B_S5_CMD)

segment1b-s6:
	@echo "Running Segment 1B S6 in-cell jitter"
	@$(SEG1B_S6_CMD)

segment1b-s7:
	@echo "Running Segment 1B S7 site synthesis"
	@$(SEG1B_S7_CMD)

segment1b-s8:
	@echo "Running Segment 1B S8 site locations egress"
	@$(SEG1B_S8_CMD)

segment1b-s9:
	@echo "Running Segment 1B S9 validation bundle"
	@$(SEG1B_S9_CMD)

segment1b-s9-archive:
	@echo "Archiving Segment 1B S9 validation bundle"
	@$(PY_SCRIPT) -c "import json,pathlib,shutil,sys,time; runs_root=pathlib.Path('$(RUNS_ROOT)'); run_id='$(SEG1B_S9_RUN_ID)'.strip(); receipt_path=(runs_root/run_id/'run_receipt.json' if run_id else sorted(runs_root.glob('*/run_receipt.json'), key=lambda p: p.stat().st_mtime)[-1]); receipt=json.loads(receipt_path.read_text(encoding='utf-8')); run_id=receipt['run_id']; fingerprint=receipt['manifest_fingerprint']; bundle_root=runs_root/run_id/'data'/'layer1'/'1B'/'validation'/f'manifest_fingerprint={fingerprint}'; (bundle_root.exists() or sys.exit(f'Validation bundle not found: {bundle_root}')); timestamp=time.strftime('%Y%m%dT%H%M%S'); archive_root=runs_root/run_id/'data'/'layer1'/'1B'/'validation'/'_failed'/f'manifest_fingerprint={fingerprint}'/f'attempt={timestamp}'; archive_root.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(bundle_root), str(archive_root)); print(f'Archived {bundle_root} -> {archive_root}')"

segment2a-s0:
	@echo "Running Segment 2A S0 gate-in"
	@$(SEG2A_S0_CMD)

segment2a-s1:
	@echo "Running Segment 2A S1 provisional tz lookup"
	@$(SEG2A_S1_CMD)

segment2a-s2:
	@echo "Running Segment 2A S2 overrides"
	@$(SEG2A_S2_CMD)

segment2a-s3:
	@echo "Running Segment 2A S3 timetable cache"
	@$(SEG2A_S3_CMD)

segment2a-s4:
	@echo "Running Segment 2A S4 legality report"
	@$(SEG2A_S4_CMD)

segment2a-s5:
	@echo "Running Segment 2A S5 validation bundle"
	@$(SEG2A_S5_CMD)

segment2a: segment2a-s0 segment2a-s1 segment2a-s2 segment2a-s3 segment2a-s4 segment2a-s5

segment2b-s0:
	@echo "Running Segment 2B S0 gate-in"
	@$(SEG2B_S0_CMD)

segment2b-s1:
	@echo "Running Segment 2B S1 site weights"
	@$(SEG2B_S1_CMD)

segment2b-s2:
	@echo "Running Segment 2B S2 alias tables"
	@$(SEG2B_S2_CMD)

segment2b-s3:
	@echo "Running Segment 2B S3 day effects"
	@$(SEG2B_S3_CMD)

segment2b-s4:
	@echo "Running Segment 2B S4 group weights"
	@$(SEG2B_S4_CMD)

segment2b-s5:
	@echo "Running Segment 2B S5 router"
	@$(SEG2B_S5_CMD)

segment2b-s6:
	@echo "Running Segment 2B S6 edge router"
	@$(SEG2B_S6_CMD)

segment2b-s7:
	@echo "Running Segment 2B S7 audit/CI gate"
	@$(SEG2B_S7_CMD)

segment2b-s8:
	@echo "Running Segment 2B S8 validation bundle"
	@$(SEG2B_S8_CMD)

segment2b-arrival-roster:
	@echo "Normalizing 2B arrival roster (add is_virtual if missing)"
	@run_id="$(RUN_ID_OR_LATEST)"; \
	if [ -z "$$run_id" ]; then \
		echo "No run_receipt.json files found under $(RUNS_ROOT). Provide RUN_ID." >&2; \
		exit 1; \
	fi; \
	$(PY_SCRIPT) scripts/normalize_arrival_roster.py --run-id "$$run_id" --runs-root "$(RUNS_ROOT)"

segment2b: segment2b-arrival-roster segment2b-s0 segment2b-s1 segment2b-s2 segment2b-s3 segment2b-s4 segment2b-s5 segment2b-s6 segment2b-s7 segment2b-s8

segment3a-s0:
	@echo "Running Segment 3A S0 gate-in"
	@$(SEG3A_S0_CMD)

segment3a-s1:
	@echo "Running Segment 3A S1 escalation queue"
	@$(SEG3A_S1_CMD)

segment3a-s2:
	@echo "Running Segment 3A S2 country-zone priors"
	@$(SEG3A_S2_CMD)

segment3a-s3:
	@echo "Running Segment 3A S3 zone share sampling"
	@$(SEG3A_S3_CMD)

segment3a-s4:
	@echo "Running Segment 3A S4 zone count integerisation"
	@$(SEG3A_S4_CMD)

segment3a-s5:
	@echo "Running Segment 3A S5 zone allocation egress"
	@$(SEG3A_S5_CMD)

segment3a-s6:
	@echo "Running Segment 3A S6 validation"
	@$(SEG3A_S6_CMD)

segment3a-s7:
	@echo "Running Segment 3A S7 validation bundle"
	@$(SEG3A_S7_CMD)

segment3a: segment3a-s0 segment3a-s1 segment3a-s2 segment3a-s3 segment3a-s4 segment3a-s5 segment3a-s6 segment3a-s7

segment3b-s0:
	@echo "Running Segment 3B S0 gate-in"
	@$(SEG3B_S0_CMD)

segment3b-s1:
	@echo "Running Segment 3B S1 virtual classification"
	@$(SEG3B_S1_CMD)

segment3b-s2:
	@echo "Running Segment 3B S2 edge catalogue"
	@$(SEG3B_S2_CMD)

segment3b-s3:
	@echo "Running Segment 3B S3 alias tables"
	@$(SEG3B_S3_CMD)

segment3b-s4:
	@echo "Running Segment 3B S4 virtual contracts"
	@$(SEG3B_S4_CMD)

segment3b-s5:
	@echo "Running Segment 3B S5 validation bundle"
	@$(SEG3B_S5_CMD)

segment3b: segment3b-s0 segment3b-s1 segment3b-s2 segment3b-s3 segment3b-s4 segment3b-s5

segment5a-s0:
	@echo "Running Segment 5A S0 gate-in"
	@run_id="$(if $(strip $(SEG5A_S0_RUN_ID)),$(SEG5A_S0_RUN_ID),$(if $(strip $(RUN_ID)),$(RUN_ID),$(LATEST_RUN_ID)))"; \
	if [ -n "$$run_id" ]; then \
		$(MAKE) scenario_calendar_5a RUN_ID="$$run_id"; \
	else \
		$(MAKE) scenario_calendar_5a; \
	fi
	@$(SEG5A_S0_CMD)

segment5a-s1:
	@echo "Running Segment 5A S1 demand classification"
	@$(SEG5A_S1_CMD)

segment5a-s2:
	@echo "Running Segment 5A S2 weekly shape library"
	@$(SEG5A_S2_CMD)

segment5a-s3:
	@echo "Running Segment 5A S3 baseline intensity"
	@$(SEG5A_S3_CMD)

segment5a-s4:
	@echo "Running Segment 5A S4 calendar overlays"
	@$(SEG5A_S4_CMD)

segment5a-s5:
	@echo "Running Segment 5A S5 validation bundle"
	@$(SEG5A_S5_CMD)

segment5a: segment5a-s0 segment5a-s1 segment5a-s2 segment5a-s3 segment5a-s4 segment5a-s5

segment5b-s0:
	@echo "Running Segment 5B S0 gate-in"
	@$(SEG5B_S0_CMD)

segment5b-s1:
	@echo "Running Segment 5B S1 time grid + grouping"
	@$(SEG5B_S1_CMD)

segment5b-s2:
	@echo "Running Segment 5B S2 latent intensity fields"
	@$(SEG5B_S2_CMD)

segment5b-s3:
	@echo "Running Segment 5B S3 bucket-level arrival counts"
	@$(SEG5B_S3_CMD)

segment5b-s4:
	@echo "Running Segment 5B S4 arrival events"
	@$(SEG5B_S4_CMD)

segment5b-s5:
	@echo "Running Segment 5B S5 validation bundle"
	@$(SEG5B_S5_CMD)

segment5b: segment5b-s0 segment5b-s1 segment5b-s2 segment5b-s3 segment5b-s4 segment5b-s5

segment6a-s0:
	@echo "Running Segment 6A S0 gate-in"
	@$(SEG6A_S0_CMD)

segment6a-s1:
	@echo "Running Segment 6A S1 party base"
	@$(SEG6A_S1_CMD)

segment6a-s2:
	@echo "Running Segment 6A S2 account base"
	@$(SEG6A_S2_CMD)

segment6a-s3:
	@echo "Running Segment 6A S3 instrument base"
	@$(SEG6A_S3_CMD)

segment6a-s4:
	@echo "Running Segment 6A S4 device/IP graph"
	@$(SEG6A_S4_CMD)

segment6a-s5:
	@echo "Running Segment 6A S5 fraud posture"
	@$(SEG6A_S5_CMD)

segment6a: segment6a-s0 segment6a-s1 segment6a-s2 segment6a-s3 segment6a-s4 segment6a-s5

segment6b-s0:
	@echo "Running Segment 6B S0 gate-in"
	@$(SEG6B_S0_CMD)

segment6b-s1:
	@echo "Running Segment 6B S1 attachment + sessionisation"
	@$(SEG6B_S1_CMD)

segment6b-s2:
	@echo "Running Segment 6B S2 baseline flow synthesis"
	@$(SEG6B_S2_CMD)

segment6b-s3:
	@echo "Running Segment 6B S3 fraud overlay"
	@$(SEG6B_S3_CMD)

segment6b-s4:
	@echo "Running Segment 6B S4 truth + bank-view labels"
	@$(SEG6B_S4_CMD)

segment6b-s5:
	@echo "Running Segment 6B S5 validation gate"
	@$(SEG6B_S5_CMD)

segment6b: segment6b-s0 segment6b-s1 segment6b-s2 segment6b-s3 segment6b-s4 segment6b-s5

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

# ---------------------------------------------------------------------------
# Platform (SR/IG) local workflow
# ---------------------------------------------------------------------------
PLATFORM_RUNS_ROOT ?= runs/fraud-platform
SR_WIRING ?= config/platform/sr/wiring_local.yaml
SR_POLICY ?= config/platform/sr/policy_v0.yaml
SR_ENGINE_RUN_ROOT ?= $(ORACLE_ENGINE_RUN_ROOT)
SR_RUN_EQUIVALENCE_KEY ?= local_full_run_5_reuse
SR_REEMIT_RUN_ID ?=
SR_REEMIT_KIND ?= READY_ONLY
SR_MANIFEST_FINGERPRINT ?= c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8
SR_PARAMETER_HASH ?= 56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7
SR_SEED ?= 42
SR_SCENARIO_ID ?= baseline_v1
SR_WINDOW_START ?= 2026-01-01T00:00:00Z
SR_WINDOW_END ?= 2026-01-02T00:00:00Z

IG_PROFILE ?= config/platform/profiles/local.yaml
IG_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
PLATFORM_PROFILE ?= config/platform/profiles/local_parity.yaml
IG_HOST ?= 127.0.0.1
IG_PORT ?= 8081
IG_AUDIT_RUN_ID ?=
PLATFORM_RUN_ID ?=
PLATFORM_RUN_ID_NEW ?=
GOVERNANCE_EVENT_FAMILY ?=
GOVERNANCE_QUERY_LIMIT ?= 200
PLATFORM_CONFORMANCE_OUTPUT_PATH ?=
EVIDENCE_REF_ACTOR_ID ?= SYSTEM::platform_run_reporter
EVIDENCE_REF_SOURCE_TYPE ?= SYSTEM
EVIDENCE_REF_SOURCE_COMPONENT ?= platform_run_reporter
EVIDENCE_REF_PURPOSE ?= platform_run_report
EVIDENCE_REF_TYPE ?=
EVIDENCE_REF_ID ?=
EVIDENCE_REF_STRICT ?= 0
EVIDENCE_REF_ALLOW_ACTOR ?=
WSP_PROFILE ?= config/platform/profiles/local.yaml
WSP_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
IEG_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
OFP_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
OFP_EVENT_BUS_START_POSITION ?= trim_horizon
CONTEXT_STORE_FLOW_BINDING_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
WSP_MAX_EVENTS ?= 1
WSP_VALIDATE_MAX_EVENTS ?= 10
WSP_RESUME_EVENTS ?= 1
WSP_VALIDATE_CHECK_FAILURES ?=
WSP_VALIDATE_SKIP_RESUME ?=
WSP_READY_POLL_SECONDS ?= 2.0
WSP_READY_MAX_MESSAGES ?=
WSP_READY_MAX_EVENTS ?=
PLATFORM_SMOKE_MAX_EVENTS ?= 20
WSP_ENGINE_RUN_ROOT ?=
WSP_SCENARIO_ID ?=
WSP_OUTPUT_IDS ?=
ORACLE_PROFILE ?= config/platform/profiles/local.yaml
ORACLE_PROFILE_PARITY ?= config/platform/profiles/local_parity.yaml
ORACLE_ROOT ?= s3://oracle-store
ORACLE_ENGINE_RUN_ROOT ?=
ORACLE_SCENARIO_ID ?=
ORACLE_ENGINE_RELEASE ?= unknown
ORACLE_PACK_ROOT ?=
ORACLE_OUTPUT_IDS ?=
SR_WIRING_PARITY ?= config/platform/sr/wiring_local_kinesis.yaml
CONTROL_BUS_STREAM ?= $(PARITY_CONTROL_BUS_STREAM)
CONTROL_BUS_REGION ?= $(PARITY_CONTROL_BUS_REGION)
CONTROL_BUS_ENDPOINT_URL ?= $(PARITY_CONTROL_BUS_ENDPOINT_URL)
WSP_CHECKPOINT_DSN ?= $(PARITY_WSP_CHECKPOINT_DSN)
IG_INGEST_URL ?= $(PARITY_IG_INGEST_URL)

PARITY_OBJECT_STORE_ENDPOINT ?= http://localhost:9000
PARITY_OBJECT_STORE_REGION ?= us-east-1
PARITY_ORACLE_ROOT ?= $(ORACLE_ROOT)
PARITY_IG_ADMISSION_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_WSP_CHECKPOINT_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_IEG_PROJECTION_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_OFP_PROJECTION_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_OFP_SNAPSHOT_INDEX_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_CSFB_PROJECTION_DSN ?= postgresql://platform:platform@localhost:5434/platform
PARITY_DL_POSTURE_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_DL_OUTBOX_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_DL_OPS_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_DF_REPLAY_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_DF_CHECKPOINT_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_AL_LEDGER_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_AL_OUTCOMES_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_AL_REPLAY_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_AL_CHECKPOINT_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_DLA_INDEX_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_CASE_TRIGGER_REPLAY_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_CASE_TRIGGER_CHECKPOINT_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_CASE_TRIGGER_PUBLISH_STORE_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_CASE_MGMT_LOCATOR ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_LABEL_STORE_LOCATOR ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_ARCHIVE_WRITER_LEDGER_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_OFS_RUN_LEDGER_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_MF_RUN_LEDGER_DSN ?= $(PARITY_IG_ADMISSION_DSN)
PARITY_EVENT_BUS_STREAM ?= auto
PARITY_EVENT_BUS_REGION ?= $(PARITY_CONTROL_BUS_REGION)
PARITY_EVENT_BUS_ENDPOINT_URL ?= $(PARITY_CONTROL_BUS_ENDPOINT_URL)
PARITY_CONTROL_BUS_STREAM ?= sr-control-bus
PARITY_CONTROL_BUS_REGION ?= us-east-1
PARITY_CONTROL_BUS_ENDPOINT_URL ?= http://localhost:4566
PARITY_IG_INGEST_URL ?= http://localhost:8081
PARITY_AWS_ACCESS_KEY_ID ?= minio
PARITY_AWS_SECRET_ACCESS_KEY ?= minio123
PARITY_MINIO_ACCESS_KEY ?= minio
PARITY_MINIO_SECRET_KEY ?= minio123
PARITY_AWS_EC2_METADATA_DISABLED ?= true
PARITY_CASE_TRIGGER_IG_API_KEY ?= local-parity-case-trigger
RUN_OPERATE_ENV_FILE ?= .env.platform.local
RUN_OPERATE_PACK_CONTROL_INGRESS ?= config/platform/run_operate/packs/local_parity_control_ingress.v0.yaml
RUN_OPERATE_PACK_RTDL_CORE ?= config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml
RUN_OPERATE_PACK_RTDL_DECISION ?= config/platform/run_operate/packs/local_parity_rtdl_decision_lane.v0.yaml
RUN_OPERATE_PACK_CASE_LABELS ?= config/platform/run_operate/packs/local_parity_case_labels.v0.yaml
RUN_OPERATE_PACK_OBS_GOV ?= config/platform/run_operate/packs/local_parity_obs_gov.v0.yaml
RUN_OPERATE_PACK_LEARNING_JOBS ?= config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml

OFS_PROFILE ?= config/platform/profiles/local_parity.yaml
OFS_INTENT_PATH ?=
OFS_REPLAY_EVENTS_PATH ?=
OFS_TARGET_SUBJECTS_PATH ?=
OFS_REPLAY_EVIDENCE_PATH ?=
OFS_REQUEST_ID ?=
OFS_PUBLISH_RETRY_RUN_KEY ?=
OFS_PUBLISH_RETRY_PLATFORM_RUN_ID ?=
OFS_PUBLISH_RETRY_INTENT_PATH ?=
OFS_PUBLISH_RETRY_DRAFT_PATH ?=
OFS_PUBLISH_RETRY_REPLAY_RECEIPT_PATH ?=
OFS_PUBLISH_RETRY_LABEL_RECEIPT_PATH ?=
OFS_SUPERSEDES_MANIFEST_REFS ?=
OFS_BACKFILL_REASON ?=
MF_PROFILE ?= config/platform/profiles/local_parity.yaml
MF_REQUEST_PATH ?=
MF_REQUEST_ID ?=
MF_PUBLISH_RETRY_RUN_KEY ?=
MF_PUBLISH_RETRY_PLATFORM_RUN_ID ?=
MF_PUBLISH_RETRY_RESOLVED_TRAIN_PLAN_REF ?=
MF_PUBLISH_RETRY_GATE_RECEIPT_REF ?=
MF_PUBLISH_RETRY_PUBLISH_ELIGIBILITY_REF ?=

.PHONY: platform-stack-up platform-stack-down platform-stack-status
platform-stack-up:
	docker compose -f infra/local/docker-compose.sr-parity.yaml up -d

platform-stack-down:
	docker compose -f infra/local/docker-compose.sr-parity.yaml down

platform-stack-status:
	docker compose -f infra/local/docker-compose.sr-parity.yaml ps

.PHONY: platform-parity-stack-up platform-parity-stack-down platform-parity-stack-status
platform-parity-stack-up:
	docker compose -f infra/local/docker-compose.platform-parity.yaml up -d

platform-parity-stack-down:
	docker compose -f infra/local/docker-compose.platform-parity.yaml down

platform-parity-stack-status:
	docker compose -f infra/local/docker-compose.platform-parity.yaml ps

.PHONY: platform-parity-bootstrap
platform-parity-bootstrap:
	@AWS_ACCESS_KEY_ID="$(PARITY_AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_AWS_SECRET_ACCESS_KEY)" \
	AWS_DEFAULT_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	AWS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	$(PY_SCRIPT) -c "import boto3, os; endpoint=os.environ.get('AWS_ENDPOINT_URL'); region=os.environ.get('AWS_DEFAULT_REGION','us-east-1'); client=boto3.client('kinesis',region_name=region,endpoint_url=endpoint); names=['sr-control-bus','fp.bus.traffic.baseline.v1','fp.bus.traffic.fraud.v1','fp.bus.context.arrival_events.v1','fp.bus.context.arrival_entities.v1','fp.bus.context.flow_anchor.baseline.v1','fp.bus.context.flow_anchor.fraud.v1','fp.bus.rtdl.v1','fp.bus.case.v1','fp.bus.audit.v1']; existing=set(client.list_streams(Limit=200).get('StreamNames', [])); [client.create_stream(StreamName=n,ShardCount=1) for n in names if n not in existing]" 2> /dev/null || true
	@AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_DEFAULT_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	AWS_ENDPOINT_URL="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	$(PY_SCRIPT) -c "import boto3,os; endpoint=os.environ.get('AWS_ENDPOINT_URL'); region=os.environ.get('AWS_DEFAULT_REGION','us-east-1'); client=boto3.client('s3',region_name=region,endpoint_url=endpoint); existing={item.get('Name') for item in client.list_buckets().get('Buckets', [])}; [client.create_bucket(Bucket=b) for b in ['oracle-store','fraud-platform'] if b not in existing]" 2> /dev/null || true

.PHONY: platform-bus-clean
platform-bus-clean:
	rm -f runs/fraud-platform/control_bus/fp.bus.control.v1/*.json

.PHONY: platform-run-new
platform-run-new:
	rm -f runs/fraud-platform/ACTIVE_RUN_ID
	@PLATFORM_RUN_ID="$(PLATFORM_RUN_ID_NEW)" $(PY_PLATFORM) -c "from fraud_detection.platform_runtime import resolve_platform_run_id; print(resolve_platform_run_id(create_if_missing=True))"

.PHONY: platform-oracle-sync
platform-oracle-sync:
	@if [ -z "$(ORACLE_SYNC_SOURCE)" ]; then \
		echo "ORACLE_SYNC_SOURCE is required for platform-oracle-sync." >&2; \
		exit 1; \
	fi
	@if [ -z "$(ORACLE_ENGINE_RUN_ROOT)" ]; then \
		echo "ORACLE_ENGINE_RUN_ROOT is required for platform-oracle-sync." >&2; \
		exit 1; \
	fi
	@AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_DEFAULT_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	aws --endpoint-url "$(PARITY_OBJECT_STORE_ENDPOINT)" s3 sync \
		"$(ORACLE_SYNC_SOURCE)" "$(ORACLE_ENGINE_RUN_ROOT)"

.PHONY: platform-sr-run-reuse
platform-sr-run-reuse:
	@if [ -z "$(SR_ENGINE_RUN_ROOT)" ]; then \
		echo "SR_ENGINE_RUN_ROOT (or ORACLE_ENGINE_RUN_ROOT) is required." >&2; \
		exit 1; \
	fi
	@if [ -z "$(SR_MANIFEST_FINGERPRINT)" ] || [ -z "$(SR_PARAMETER_HASH)" ]; then \
		echo "SR_MANIFEST_FINGERPRINT and SR_PARAMETER_HASH are required." >&2; \
		exit 1; \
	fi
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_STORE_ROOT)" \
	PLATFORM_COMPONENT="sr" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.scenario_runner.cli run \
		--wiring "$(SR_WIRING)" \
		--policy "$(SR_POLICY)" \
		--run-equivalence-key "$(SR_RUN_EQUIVALENCE_KEY)" \
		--manifest-fingerprint "$(SR_MANIFEST_FINGERPRINT)" \
		--parameter-hash "$(SR_PARAMETER_HASH)" \
		--seed "$(SR_SEED)" \
		--scenario-id "$(SR_SCENARIO_ID)" \
		--window-start "$(SR_WINDOW_START)" \
		--window-end "$(SR_WINDOW_END)" \
		--engine-run-root "$(SR_ENGINE_RUN_ROOT)"

.PHONY: platform-sr-reemit
platform-sr-reemit:
	@if [ -z "$(SR_REEMIT_RUN_ID)" ]; then \
		echo "SR_REEMIT_RUN_ID is required for platform-sr-reemit." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.scenario_runner.cli reemit \
		--wiring "$(SR_WIRING)" \
		--policy "$(SR_POLICY)" \
		--run-id "$(SR_REEMIT_RUN_ID)" \
		--kind "$(SR_REEMIT_KIND)"

.PHONY: platform-ig-service
platform-ig-service:
	@PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_STORE_ROOT)" \
	PLATFORM_COMPONENT="ig" \
	$(PY_PLATFORM) -m fraud_detection.ingestion_gate.service \
		--profile "$(IG_PROFILE)" \
		--host "$(IG_HOST)" \
		--port "$(IG_PORT)"

.PHONY: platform-ig-service-parity
platform-ig-service-parity:
	@OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	EVENT_BUS_REGION="$(PARITY_EVENT_BUS_REGION)" \
	EVENT_BUS_ENDPOINT_URL="$(PARITY_EVENT_BUS_ENDPOINT_URL)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	IG_INGEST_URL="$(PARITY_IG_INGEST_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_DEFAULT_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	AWS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_STORE_ROOT)" \
	PLATFORM_COMPONENT="ig" \
	$(PY_PLATFORM) -m fraud_detection.ingestion_gate.service \
		--profile "$(IG_PROFILE_PARITY)" \
		--host "$(IG_HOST)" \
		--port "$(IG_PORT)"


.PHONY: platform-wsp-ready-once
platform-wsp-ready-once:
	@if [ -z "$(WSP_ENGINE_RUN_ROOT)" ]; then \
		echo "WSP_ENGINE_RUN_ROOT is required for platform-wsp-ready-once." >&2; \
		exit 1; \
	fi
	@if [ -z "$(WSP_SCENARIO_ID)" ]; then \
		echo "WSP_SCENARIO_ID is required for platform-wsp-ready-once." >&2; \
		exit 1; \
	fi
	@ORACLE_STREAM_VIEW_ROOT="$(ORACLE_STREAM_VIEW_ROOT)" \
	$(PY_PLATFORM) -m fraud_detection.world_streamer_producer.cli --profile "$(WSP_PROFILE)" \
		--engine-run-root "$(WSP_ENGINE_RUN_ROOT)" \
		--scenario-id "$(WSP_SCENARIO_ID)" \
		$(if $(WSP_OUTPUT_IDS),--output-ids "$(WSP_OUTPUT_IDS)",) \
		$(if $(WSP_MAX_EVENTS),--max-events "$(WSP_MAX_EVENTS)",)

.PHONY: platform-wsp-ready-consumer
platform-wsp-ready-consumer:
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_STORE_ROOT)" \
	PLATFORM_COMPONENT="wsp" \
	ORACLE_ROOT="$(ORACLE_ROOT)" \
	ORACLE_ENGINE_RUN_ROOT="$(ORACLE_ENGINE_RUN_ROOT)" \
	ORACLE_SCENARIO_ID="$(ORACLE_SCENARIO_ID)" \
	ORACLE_STREAM_VIEW_ROOT="$(ORACLE_STREAM_VIEW_ROOT)" \
	CONTROL_BUS_STREAM="$(CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(CONTROL_BUS_ENDPOINT_URL)" \
	WSP_CHECKPOINT_DSN="$(WSP_CHECKPOINT_DSN)" \
	IG_INGEST_URL="$(IG_INGEST_URL)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.world_streamer_producer.ready_consumer --profile "$(WSP_PROFILE)" \
		--poll-seconds "$(WSP_READY_POLL_SECONDS)" \
		$(if $(WSP_READY_MAX_MESSAGES),--max-messages "$(WSP_READY_MAX_MESSAGES)",) \
		$(if $(WSP_READY_MAX_EVENTS),--max-events "$(WSP_READY_MAX_EVENTS)",) \
		$(if $(WSP_MAX_EVENTS_PER_OUTPUT),--max-events-per-output "$(WSP_MAX_EVENTS_PER_OUTPUT)",)

.PHONY: platform-wsp-ready-consumer-once
platform-wsp-ready-consumer-once:
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_STORE_ROOT)" \
	PLATFORM_COMPONENT="wsp" \
	ORACLE_ROOT="$(ORACLE_ROOT)" \
	ORACLE_ENGINE_RUN_ROOT="$(ORACLE_ENGINE_RUN_ROOT)" \
	ORACLE_SCENARIO_ID="$(ORACLE_SCENARIO_ID)" \
	ORACLE_STREAM_VIEW_ROOT="$(ORACLE_STREAM_VIEW_ROOT)" \
	CONTROL_BUS_STREAM="$(CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(CONTROL_BUS_ENDPOINT_URL)" \
	WSP_CHECKPOINT_DSN="$(WSP_CHECKPOINT_DSN)" \
	IG_INGEST_URL="$(IG_INGEST_URL)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.world_streamer_producer.ready_consumer --profile "$(WSP_PROFILE)" --once \
		$(if $(WSP_READY_MAX_MESSAGES),--max-messages "$(WSP_READY_MAX_MESSAGES)",) \
		$(if $(WSP_READY_MAX_EVENTS),--max-events "$(WSP_READY_MAX_EVENTS)",) \
		$(if $(WSP_MAX_EVENTS_PER_OUTPUT),--max-events-per-output "$(WSP_MAX_EVENTS_PER_OUTPUT)",)

.PHONY: platform-smoke
platform-smoke:
	@echo "Ensure IG service is running (in another terminal): make platform-ig-service"
	@$(MAKE) platform-run-new
	@$(MAKE) platform-bus-clean
	@SR_RUN_EQUIVALENCE_KEY="local_smoke_$$(date +%Y%m%dT%H%M%SZ)" \
		$(MAKE) platform-sr-run-reuse
	@WSP_READY_MAX_EVENTS="$(PLATFORM_SMOKE_MAX_EVENTS)" $(MAKE) platform-wsp-ready-consumer-once

.PHONY: platform-parity-smoke
platform-parity-smoke:
	@echo "Ensure parity stack is up: make platform-parity-stack-up"
	@$(MAKE) platform-parity-bootstrap
	@echo "Ensure IG service is running (in another terminal): make platform-ig-service-parity"
	@$(MAKE) platform-run-new
	@OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	IG_INGEST_URL="$(PARITY_IG_INGEST_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	SR_WIRING="$(SR_WIRING_PARITY)" WSP_PROFILE="$(WSP_PROFILE_PARITY)" IG_PROFILE="$(IG_PROFILE_PARITY)" \
	ORACLE_PROFILE="$(ORACLE_PROFILE_PARITY)" \
	SR_RUN_EQUIVALENCE_KEY="parity_smoke_$$(date +%Y%m%dT%H%M%SZ)" \
	$(MAKE) platform-sr-run-reuse
	@OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	IG_INGEST_URL="$(PARITY_IG_INGEST_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	WSP_PROFILE="$(WSP_PROFILE_PARITY)" WSP_READY_MAX_EVENTS="$(PLATFORM_SMOKE_MAX_EVENTS)" \
	$(MAKE) platform-wsp-ready-consumer-once

.PHONY: platform-ofp-projector-parity-live
platform-ofp-projector-parity-live:
	@echo "Ensure parity stack is up: make platform-parity-stack-up"
	@echo "Ensure run id is set: make platform-run-new"
	@PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	OFP_REQUIRED_PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	OFP_PROJECTION_DSN="$(PARITY_OFP_PROJECTION_DSN)" \
	OFP_SNAPSHOT_INDEX_DSN="$(PARITY_OFP_SNAPSHOT_INDEX_DSN)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_RUNS_ROOT)" \
	OFP_EVENT_BUS_START_POSITION="$(OFP_EVENT_BUS_START_POSITION)" \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	EVENT_BUS_REGION="$(PARITY_EVENT_BUS_REGION)" \
	EVENT_BUS_ENDPOINT_URL="$(PARITY_EVENT_BUS_ENDPOINT_URL)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.online_feature_plane.projector \
		--profile "$(OFP_PROFILE_PARITY)"

.PHONY: platform-ieg-projector-parity-live
platform-ieg-projector-parity-live:
	@echo "Ensure parity stack is up: make platform-parity-stack-up"
	@echo "Ensure run id is set: make platform-run-new"
	@PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	IEG_REQUIRED_PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	IEG_PROJECTION_DSN="$(PARITY_IEG_PROJECTION_DSN)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_RUNS_ROOT)" \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	EVENT_BUS_REGION="$(PARITY_EVENT_BUS_REGION)" \
	EVENT_BUS_ENDPOINT_URL="$(PARITY_EVENT_BUS_ENDPOINT_URL)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.identity_entity_graph.projector \
		--profile "$(IEG_PROFILE_PARITY)"

.PHONY: platform-context-store-flow-binding-parity-once
platform-context-store-flow-binding-parity-once:
	@echo "Ensure parity stack is up: make platform-parity-stack-up"
	@echo "Ensure run id is set: make platform-run-new"
	@PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	CSFB_REQUIRED_PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	CSFB_PROJECTION_DSN="$(PARITY_CSFB_PROJECTION_DSN)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_RUNS_ROOT)" \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	EVENT_BUS_REGION="$(PARITY_EVENT_BUS_REGION)" \
	EVENT_BUS_ENDPOINT_URL="$(PARITY_EVENT_BUS_ENDPOINT_URL)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.context_store_flow_binding.intake \
		--policy "$(CONTEXT_STORE_FLOW_BINDING_PROFILE_PARITY)" \
		--once

.PHONY: platform-context-store-flow-binding-parity-live
platform-context-store-flow-binding-parity-live:
	@echo "Ensure parity stack is up: make platform-parity-stack-up"
	@echo "Ensure run id is set: make platform-run-new"
	@PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	CSFB_REQUIRED_PLATFORM_RUN_ID="$(shell cat runs/fraud-platform/ACTIVE_RUN_ID 2>/dev/null)" \
	CSFB_PROJECTION_DSN="$(PARITY_CSFB_PROJECTION_DSN)" \
	PLATFORM_STORE_ROOT="$(PLATFORM_RUNS_ROOT)" \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	ORACLE_ROOT="$(PARITY_ORACLE_ROOT)" \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	WSP_CHECKPOINT_DSN="$(PARITY_WSP_CHECKPOINT_DSN)" \
	EVENT_BUS_STREAM="$(PARITY_EVENT_BUS_STREAM)" \
	EVENT_BUS_REGION="$(PARITY_EVENT_BUS_REGION)" \
	EVENT_BUS_ENDPOINT_URL="$(PARITY_EVENT_BUS_ENDPOINT_URL)" \
	CONTROL_BUS_STREAM="$(PARITY_CONTROL_BUS_STREAM)" \
	CONTROL_BUS_REGION="$(PARITY_CONTROL_BUS_REGION)" \
	CONTROL_BUS_ENDPOINT_URL="$(PARITY_CONTROL_BUS_ENDPOINT_URL)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.context_store_flow_binding.intake \
		--policy "$(CONTEXT_STORE_FLOW_BINDING_PROFILE_PARITY)"

.PHONY: platform-rtdl-core-parity-live
platform-rtdl-core-parity-live:
	@echo "RTDL live core (open these in separate terminals, same ACTIVE_RUN_ID):"
	@echo "  1) make platform-ieg-projector-parity-live"
	@echo "  2) make platform-ofp-projector-parity-live"
	@echo "  3) make platform-context-store-flow-binding-parity-live"
	@echo "Scope: live-capable RTDL core consumers in v0 parity (IEG/OFP/CSFB)."
	@echo "Decision lane (DL/DF/AL/DLA) is orchestrated via run/operate:"
	@echo "  make platform-operate-rtdl-decision-up"

.PHONY: platform-operate-control-ingress-up platform-operate-control-ingress-down platform-operate-control-ingress-restart platform-operate-control-ingress-status
platform-operate-control-ingress-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CONTROL_INGRESS)" up

platform-operate-control-ingress-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CONTROL_INGRESS)" down

platform-operate-control-ingress-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CONTROL_INGRESS)" restart

platform-operate-control-ingress-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CONTROL_INGRESS)" status

.PHONY: platform-operate-rtdl-core-up platform-operate-rtdl-core-down platform-operate-rtdl-core-restart platform-operate-rtdl-core-status
platform-operate-rtdl-core-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_CORE)" up

platform-operate-rtdl-core-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_CORE)" down

platform-operate-rtdl-core-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_CORE)" restart

platform-operate-rtdl-core-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_CORE)" status

.PHONY: platform-operate-rtdl-decision-up platform-operate-rtdl-decision-down platform-operate-rtdl-decision-restart platform-operate-rtdl-decision-status
platform-operate-rtdl-decision-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_DECISION)" up

platform-operate-rtdl-decision-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_DECISION)" down

platform-operate-rtdl-decision-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_DECISION)" restart

platform-operate-rtdl-decision-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_RTDL_DECISION)" status

.PHONY: platform-operate-case-labels-up platform-operate-case-labels-down platform-operate-case-labels-restart platform-operate-case-labels-status
platform-operate-case-labels-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CASE_LABELS)" up

platform-operate-case-labels-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CASE_LABELS)" down

platform-operate-case-labels-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CASE_LABELS)" restart

platform-operate-case-labels-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_CASE_LABELS)" status

.PHONY: platform-operate-obs-gov-up platform-operate-obs-gov-down platform-operate-obs-gov-restart platform-operate-obs-gov-status
platform-operate-obs-gov-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_OBS_GOV)" up

platform-operate-obs-gov-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_OBS_GOV)" down

platform-operate-obs-gov-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_OBS_GOV)" restart

platform-operate-obs-gov-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_OBS_GOV)" status

.PHONY: platform-operate-learning-jobs-up platform-operate-learning-jobs-down platform-operate-learning-jobs-restart platform-operate-learning-jobs-status
platform-operate-learning-jobs-up:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_LEARNING_JOBS)" up

platform-operate-learning-jobs-down:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_LEARNING_JOBS)" down

platform-operate-learning-jobs-restart:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_LEARNING_JOBS)" restart

platform-operate-learning-jobs-status:
	@$(PY_PLATFORM) -m fraud_detection.run_operate.orchestrator \
		--env-file "$(RUN_OPERATE_ENV_FILE)" \
		--pack "$(RUN_OPERATE_PACK_LEARNING_JOBS)" status

.PHONY: platform-operate-parity-up platform-operate-parity-down platform-operate-parity-restart platform-operate-parity-status
platform-operate-parity-up:
	@echo "Ensure parity stack is up and bootstrap complete before orchestration start."
	@echo "Recommended preflight: make platform-parity-stack-up && make platform-parity-bootstrap && make platform-run-new"
	@$(MAKE) platform-operate-rtdl-core-up
	@$(MAKE) platform-operate-rtdl-decision-up
	@$(MAKE) platform-operate-case-labels-up
	@$(MAKE) platform-operate-learning-jobs-up
	@$(MAKE) platform-operate-obs-gov-up
	@$(MAKE) platform-operate-control-ingress-up

platform-operate-parity-down:
	@$(MAKE) platform-operate-control-ingress-down
	@$(MAKE) platform-operate-obs-gov-down
	@$(MAKE) platform-operate-learning-jobs-down
	@$(MAKE) platform-operate-case-labels-down
	@$(MAKE) platform-operate-rtdl-decision-down
	@$(MAKE) platform-operate-rtdl-core-down

platform-operate-parity-restart:
	@$(MAKE) platform-operate-parity-down
	@$(MAKE) platform-operate-parity-up

platform-operate-parity-status:
	@$(MAKE) platform-operate-control-ingress-status
	@$(MAKE) platform-operate-rtdl-core-status
	@$(MAKE) platform-operate-rtdl-decision-status
	@$(MAKE) platform-operate-case-labels-status
	@$(MAKE) platform-operate-learning-jobs-status
	@$(MAKE) platform-operate-obs-gov-status

.PHONY: platform-ofs-enqueue-build
platform-ofs-enqueue-build:
	@if [ -z "$(OFS_INTENT_PATH)" ]; then \
		echo "OFS_INTENT_PATH is required for platform-ofs-enqueue-build." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.offline_feature_plane.worker \
		--profile "$(OFS_PROFILE)" \
		enqueue-build \
		--intent-path "$(OFS_INTENT_PATH)" \
		$(if $(OFS_REPLAY_EVENTS_PATH),--replay-events-path "$(OFS_REPLAY_EVENTS_PATH)",) \
		$(if $(OFS_TARGET_SUBJECTS_PATH),--target-subjects-path "$(OFS_TARGET_SUBJECTS_PATH)",) \
		$(if $(OFS_REPLAY_EVIDENCE_PATH),--replay-evidence-path "$(OFS_REPLAY_EVIDENCE_PATH)",) \
		$(if $(OFS_REQUEST_ID),--request-id "$(OFS_REQUEST_ID)",) \
		$(foreach ref,$(OFS_SUPERSEDES_MANIFEST_REFS),--supersedes-manifest-ref "$(ref)") \
		$(if $(OFS_BACKFILL_REASON),--backfill-reason "$(OFS_BACKFILL_REASON)",)

.PHONY: platform-ofs-enqueue-publish-retry
platform-ofs-enqueue-publish-retry:
	@if [ -z "$(OFS_PUBLISH_RETRY_RUN_KEY)" ] || [ -z "$(OFS_PUBLISH_RETRY_PLATFORM_RUN_ID)" ] || [ -z "$(OFS_PUBLISH_RETRY_INTENT_PATH)" ] || [ -z "$(OFS_PUBLISH_RETRY_DRAFT_PATH)" ] || [ -z "$(OFS_PUBLISH_RETRY_REPLAY_RECEIPT_PATH)" ]; then \
		echo "platform-ofs-enqueue-publish-retry requires OFS_PUBLISH_RETRY_RUN_KEY, OFS_PUBLISH_RETRY_PLATFORM_RUN_ID, OFS_PUBLISH_RETRY_INTENT_PATH, OFS_PUBLISH_RETRY_DRAFT_PATH, and OFS_PUBLISH_RETRY_REPLAY_RECEIPT_PATH." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.offline_feature_plane.worker \
		--profile "$(OFS_PROFILE)" \
		enqueue-publish-retry \
		--run-key "$(OFS_PUBLISH_RETRY_RUN_KEY)" \
		--platform-run-id "$(OFS_PUBLISH_RETRY_PLATFORM_RUN_ID)" \
		--intent-path "$(OFS_PUBLISH_RETRY_INTENT_PATH)" \
		--draft-path "$(OFS_PUBLISH_RETRY_DRAFT_PATH)" \
		--replay-receipt-path "$(OFS_PUBLISH_RETRY_REPLAY_RECEIPT_PATH)" \
		$(if $(OFS_PUBLISH_RETRY_LABEL_RECEIPT_PATH),--label-receipt-path "$(OFS_PUBLISH_RETRY_LABEL_RECEIPT_PATH)",) \
		$(if $(OFS_REQUEST_ID),--request-id "$(OFS_REQUEST_ID)",) \
		$(foreach ref,$(OFS_SUPERSEDES_MANIFEST_REFS),--supersedes-manifest-ref "$(ref)") \
		$(if $(OFS_BACKFILL_REASON),--backfill-reason "$(OFS_BACKFILL_REASON)",)

.PHONY: platform-mf-enqueue-train-build
platform-mf-enqueue-train-build:
	@if [ -z "$(MF_REQUEST_PATH)" ]; then \
		echo "MF_REQUEST_PATH is required for platform-mf-enqueue-train-build." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.model_factory.worker \
		--profile "$(MF_PROFILE)" \
		enqueue-train-build \
		--request-path "$(MF_REQUEST_PATH)" \
		$(if $(MF_REQUEST_ID),--request-id "$(MF_REQUEST_ID)",)

.PHONY: platform-mf-enqueue-publish-retry
platform-mf-enqueue-publish-retry:
	@if [ -z "$(MF_PUBLISH_RETRY_RUN_KEY)" ] || [ -z "$(MF_PUBLISH_RETRY_PLATFORM_RUN_ID)" ]; then \
		echo "platform-mf-enqueue-publish-retry requires MF_PUBLISH_RETRY_RUN_KEY and MF_PUBLISH_RETRY_PLATFORM_RUN_ID." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.model_factory.worker \
		--profile "$(MF_PROFILE)" \
		enqueue-publish-retry \
		--run-key "$(MF_PUBLISH_RETRY_RUN_KEY)" \
		--platform-run-id "$(MF_PUBLISH_RETRY_PLATFORM_RUN_ID)" \
		$(if $(MF_REQUEST_ID),--request-id "$(MF_REQUEST_ID)",) \
		$(if $(MF_PUBLISH_RETRY_RESOLVED_TRAIN_PLAN_REF),--resolved-train-plan-ref "$(MF_PUBLISH_RETRY_RESOLVED_TRAIN_PLAN_REF)",) \
		$(if $(MF_PUBLISH_RETRY_GATE_RECEIPT_REF),--gate-receipt-ref "$(MF_PUBLISH_RETRY_GATE_RECEIPT_REF)",) \
		$(if $(MF_PUBLISH_RETRY_PUBLISH_ELIGIBILITY_REF),--publish-eligibility-ref "$(MF_PUBLISH_RETRY_PUBLISH_ELIGIBILITY_REF)",)

.PHONY: platform-run-report
platform-run-report:
	@run_id=""; \
	if [ -f runs/fraud-platform/ACTIVE_RUN_ID ]; then \
		run_id=$$(tr -d '\r\n' < runs/fraud-platform/ACTIVE_RUN_ID); \
	fi; \
	if [ -z "$$run_id" ]; then \
		run_id="$(PLATFORM_RUN_ID)"; \
	fi; \
	if [ -z "$$run_id" ]; then \
		echo "platform-run-report requires PLATFORM_RUN_ID or runs/fraud-platform/ACTIVE_RUN_ID" >&2; \
		exit 1; \
	fi; \
	IG_ADMISSION_DSN="$(PARITY_IG_ADMISSION_DSN)" \
	IEG_PROJECTION_DSN="$(PARITY_IEG_PROJECTION_DSN)" \
	OFP_PROJECTION_DSN="$(PARITY_OFP_PROJECTION_DSN)" \
	OFP_SNAPSHOT_INDEX_DSN="$(PARITY_OFP_SNAPSHOT_INDEX_DSN)" \
	CSFB_PROJECTION_DSN="$(PARITY_CSFB_PROJECTION_DSN)" \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.platform_reporter.cli \
		--profile "$(PLATFORM_PROFILE)" \
		--platform-run-id "$$run_id"

.PHONY: platform-dev-min-phase1-preflight
platform-dev-min-phase1-preflight:
	@MSYS_NO_PATHCONV=1 pwsh -NoProfile -File scripts/dev_substrate/phase1_preflight.ps1 \
		-RequiredRegion "$(DEV_MIN_AWS_REGION)" \
		-SsmPrefix "$(DEV_MIN_SSM_PREFIX)" \
		$(if $(DEV_MIN_ALLOW_MISSING_CONFLUENT_HANDLES),-AllowMissingConfluentHandles,) \
		$(if $(DEV_MIN_SKIP_CONFLUENT_API_PROBE),-SkipConfluentApiProbe,) \
		$(if $(DEV_MIN_PHASE1_PREFLIGHT_OUTPUT),-OutputPath "$(DEV_MIN_PHASE1_PREFLIGHT_OUTPUT)",)

.PHONY: platform-dev-min-phase1-seed-ssm
platform-dev-min-phase1-seed-ssm:
	@MSYS_NO_PATHCONV=1 pwsh -NoProfile -File scripts/dev_substrate/phase1_seed_ssm.ps1 \
		-SsmPrefix "$(DEV_MIN_SSM_PREFIX)" \
		-FromEnv \
		$(if $(DEV_MIN_KAFKA_BOOTSTRAP),-Bootstrap "$(DEV_MIN_KAFKA_BOOTSTRAP)",) \
		$(if $(DEV_MIN_KAFKA_API_KEY),-ApiKey "$(DEV_MIN_KAFKA_API_KEY)",) \
		$(if $(DEV_MIN_KAFKA_API_SECRET),-ApiSecret "$(DEV_MIN_KAFKA_API_SECRET)",)

.PHONY: platform-governance-query
platform-governance-query:
	@run_id=""; \
	if [ -f runs/fraud-platform/ACTIVE_RUN_ID ]; then \
		run_id=$$(tr -d '\r\n' < runs/fraud-platform/ACTIVE_RUN_ID); \
	fi; \
	if [ -z "$$run_id" ]; then \
		run_id="$(PLATFORM_RUN_ID)"; \
	fi; \
	if [ -z "$$run_id" ]; then \
		echo "platform-governance-query requires PLATFORM_RUN_ID or runs/fraud-platform/ACTIVE_RUN_ID" >&2; \
		exit 1; \
	fi; \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.platform_governance.cli \
		$(if $(PLATFORM_STORE_ROOT),--object-store-root "$(PLATFORM_STORE_ROOT)",) \
		query --platform-run-id "$$run_id" \
		$(if $(GOVERNANCE_EVENT_FAMILY),--event-family "$(GOVERNANCE_EVENT_FAMILY)",) \
		--limit "$(GOVERNANCE_QUERY_LIMIT)"

.PHONY: platform-env-conformance
platform-env-conformance:
	@run_id=""; \
	if [ -f runs/fraud-platform/ACTIVE_RUN_ID ]; then \
		run_id=$$(tr -d '\r\n' < runs/fraud-platform/ACTIVE_RUN_ID); \
	fi; \
	if [ -z "$$run_id" ]; then \
		run_id="$(PLATFORM_RUN_ID)"; \
	fi; \
	if [ -z "$$run_id" ]; then \
		echo "platform-env-conformance requires PLATFORM_RUN_ID or runs/fraud-platform/ACTIVE_RUN_ID" >&2; \
		exit 1; \
	fi; \
	$(PY_PLATFORM) -m fraud_detection.platform_conformance.cli \
		--platform-run-id "$$run_id" \
		--local-parity-profile config/platform/profiles/local_parity.yaml \
		--dev-profile config/platform/profiles/dev.yaml \
		--prod-profile config/platform/profiles/prod.yaml \
		$(if $(PLATFORM_CONFORMANCE_OUTPUT_PATH),--output-path "$(PLATFORM_CONFORMANCE_OUTPUT_PATH)",)

.PHONY: platform-evidence-ref-resolve
platform-evidence-ref-resolve:
	@if [ -z "$(EVIDENCE_REF_TYPE)" ] || [ -z "$(EVIDENCE_REF_ID)" ]; then \
		echo "platform-evidence-ref-resolve requires EVIDENCE_REF_TYPE and EVIDENCE_REF_ID" >&2; \
		exit 1; \
	fi
	@run_id=""; \
	if [ -f runs/fraud-platform/ACTIVE_RUN_ID ]; then \
		run_id=$$(tr -d '\r\n' < runs/fraud-platform/ACTIVE_RUN_ID); \
	fi; \
	if [ -z "$$run_id" ]; then \
		run_id="$(PLATFORM_RUN_ID)"; \
	fi; \
	if [ -z "$$run_id" ]; then \
		echo "platform-evidence-ref-resolve requires PLATFORM_RUN_ID or runs/fraud-platform/ACTIVE_RUN_ID" >&2; \
		exit 1; \
	fi; \
	OBJECT_STORE_ENDPOINT="$(PARITY_OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(PARITY_OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(PARITY_MINIO_ACCESS_KEY)" \
	AWS_SECRET_ACCESS_KEY="$(PARITY_MINIO_SECRET_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(PARITY_AWS_EC2_METADATA_DISABLED)" \
	$(PY_PLATFORM) -m fraud_detection.platform_governance.cli \
		$(if $(PLATFORM_STORE_ROOT),--object-store-root "$(PLATFORM_STORE_ROOT)",) \
		resolve-ref \
		--actor-id "$(EVIDENCE_REF_ACTOR_ID)" \
		--source-type "$(EVIDENCE_REF_SOURCE_TYPE)" \
		--source-component "$(EVIDENCE_REF_SOURCE_COMPONENT)" \
		--purpose "$(EVIDENCE_REF_PURPOSE)" \
		--platform-run-id "$$run_id" \
		--ref-type "$(EVIDENCE_REF_TYPE)" \
		--ref-id "$(EVIDENCE_REF_ID)" \
		$(if $(EVIDENCE_REF_ALLOW_ACTOR),--allow-actor "$(EVIDENCE_REF_ALLOW_ACTOR)",) \
		$(if $(filter 1 true yes,$(EVIDENCE_REF_STRICT)),--strict,)

.PHONY: platform-wsp-validate-local
platform-wsp-validate-local:
	@if [ -z "$(WSP_ENGINE_RUN_ROOT)" ]; then \
		echo "WSP_ENGINE_RUN_ROOT is required for platform-wsp-validate-local." >&2; \
		exit 1; \
	fi
	@if [ -z "$(WSP_SCENARIO_ID)" ]; then \
		echo "WSP_SCENARIO_ID is required for platform-wsp-validate-local." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.world_streamer_producer.validate_cli --profile "$(WSP_PROFILE)" \
		--engine-run-root "$(WSP_ENGINE_RUN_ROOT)" \
		--scenario-id "$(WSP_SCENARIO_ID)" \
		--mode local \
		$(if $(WSP_OUTPUT_IDS),--output-ids "$(WSP_OUTPUT_IDS)",) \
		$(if $(WSP_VALIDATE_MAX_EVENTS),--max-events "$(WSP_VALIDATE_MAX_EVENTS)",) \
		$(if $(WSP_RESUME_EVENTS),--resume-events "$(WSP_RESUME_EVENTS)",) \
		$(if $(filter 1 true yes,$(WSP_VALIDATE_SKIP_RESUME)),--skip-resume,) \
		$(if $(filter 1 true yes,$(WSP_VALIDATE_CHECK_FAILURES)),--check-failures,)

.PHONY: platform-wsp-validate-dev
platform-wsp-validate-dev:
	@if [ -z "$(WSP_ENGINE_RUN_ROOT)" ]; then \
		echo "WSP_ENGINE_RUN_ROOT is required for platform-wsp-validate-dev." >&2; \
		exit 1; \
	fi
	@if [ -z "$(WSP_SCENARIO_ID)" ]; then \
		echo "WSP_SCENARIO_ID is required for platform-wsp-validate-dev." >&2; \
		exit 1; \
	fi
	@$(PY_PLATFORM) -m fraud_detection.world_streamer_producer.validate_cli --profile "$(WSP_PROFILE)" \
		--engine-run-root "$(WSP_ENGINE_RUN_ROOT)" \
		--scenario-id "$(WSP_SCENARIO_ID)" \
		--mode dev \
		$(if $(WSP_OUTPUT_IDS),--output-ids "$(WSP_OUTPUT_IDS)",)

.PHONY: platform-oracle-pack
platform-oracle-pack:
	@if [ -z "$(ORACLE_ENGINE_RUN_ROOT)" ]; then \
		echo "ORACLE_ENGINE_RUN_ROOT is required for platform-oracle-pack." >&2; \
		exit 1; \
	fi
	@if [ -z "$(ORACLE_SCENARIO_ID)" ]; then \
		echo "ORACLE_SCENARIO_ID is required for platform-oracle-pack." >&2; \
		exit 1; \
	fi
	@if [ -z "$(ORACLE_ENGINE_RELEASE)" ]; then \
		echo "ORACLE_ENGINE_RELEASE is required for platform-oracle-pack." >&2; \
		exit 1; \
	fi
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.oracle_store.pack_cli --profile "$(ORACLE_PROFILE)" \
		--engine-run-root "$(ORACLE_ENGINE_RUN_ROOT)" \
		--scenario-id "$(ORACLE_SCENARIO_ID)" \
		$(if $(ORACLE_PACK_ROOT),--pack-root "$(ORACLE_PACK_ROOT)",) \
		--engine-release "$(ORACLE_ENGINE_RELEASE)"

.PHONY: platform-oracle-stream-sort
platform-oracle-stream-sort:
	@if [ -z "$(ORACLE_ENGINE_RUN_ROOT)" ]; then \
		echo "ORACLE_ENGINE_RUN_ROOT is required for platform-oracle-stream-sort." >&2; \
		exit 1; \
	fi
	@if [ -z "$(ORACLE_SCENARIO_ID)" ]; then \
		echo "ORACLE_SCENARIO_ID is required for platform-oracle-stream-sort." >&2; \
		exit 1; \
	fi
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.oracle_store.stream_sort_cli --profile "$(ORACLE_PROFILE)" \
		--engine-run-root "$(ORACLE_ENGINE_RUN_ROOT)" \
		--scenario-id "$(ORACLE_SCENARIO_ID)" \
		$(if $(ORACLE_STREAM_VIEW_ROOT),--stream-view-root "$(ORACLE_STREAM_VIEW_ROOT)",) \
		$(if $(ORACLE_STREAM_OUTPUT_IDS_REF),--output-ids-ref "$(ORACLE_STREAM_OUTPUT_IDS_REF)",) \
		$(if $(ORACLE_STREAM_OUTPUT_ID),--output-id "$(ORACLE_STREAM_OUTPUT_ID)",)

.PHONY: platform-oracle-stream-sort-context-truth
platform-oracle-stream-sort-context-truth:
	@ORACLE_STREAM_OUTPUT_IDS_REF="config/platform/wsp/context_truth_outputs_v0.yaml" \
	$(MAKE) platform-oracle-stream-sort

.PHONY: platform-oracle-stream-sort-context-fraud
platform-oracle-stream-sort-context-fraud:
	@ORACLE_STREAM_OUTPUT_IDS_REF="config/platform/wsp/context_fraud_outputs_v0.yaml" \
	$(MAKE) platform-oracle-stream-sort

.PHONY: platform-oracle-stream-sort-context-baseline
platform-oracle-stream-sort-context-baseline:
	@ORACLE_STREAM_OUTPUT_IDS_REF="config/platform/wsp/context_baseline_outputs_v0.yaml" \
	$(MAKE) platform-oracle-stream-sort

.PHONY: platform-oracle-stream-sort-traffic-both
platform-oracle-stream-sort-traffic-both:
	@ORACLE_STREAM_OUTPUT_IDS_REF="config/platform/wsp/traffic_outputs_dual_v0.yaml" \
	$(MAKE) platform-oracle-stream-sort

.PHONY: platform-oracle-check
platform-oracle-check:
	@if [ -z "$(ORACLE_ENGINE_RUN_ROOT)" ]; then \
		echo "ORACLE_ENGINE_RUN_ROOT is required for platform-oracle-check." >&2; \
		exit 1; \
	fi
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.oracle_store.cli --profile "$(ORACLE_PROFILE)" \
		--engine-run-root "$(ORACLE_ENGINE_RUN_ROOT)" \
		$(if $(ORACLE_SCENARIO_ID),--scenario-id "$(ORACLE_SCENARIO_ID)",) \
		$(if $(ORACLE_OUTPUT_IDS),--output-ids "$(ORACLE_OUTPUT_IDS)",)

.PHONY: platform-oracle-check-strict
platform-oracle-check-strict:
	@if [ -z "$(ORACLE_ENGINE_RUN_ROOT)" ]; then \
		echo "ORACLE_ENGINE_RUN_ROOT is required for platform-oracle-check-strict." >&2; \
		exit 1; \
	fi
	@OBJECT_STORE_ENDPOINT="$(OBJECT_STORE_ENDPOINT)" \
	OBJECT_STORE_REGION="$(OBJECT_STORE_REGION)" \
	AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
	AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
	AWS_EC2_METADATA_DISABLED="$(AWS_EC2_METADATA_DISABLED)" \
	AWS_DEFAULT_REGION="$(OBJECT_STORE_REGION)" \
	$(PY_PLATFORM) -m fraud_detection.oracle_store.cli --profile "$(ORACLE_PROFILE)" \
		--engine-run-root "$(ORACLE_ENGINE_RUN_ROOT)" \
		$(if $(ORACLE_SCENARIO_ID),--scenario-id "$(ORACLE_SCENARIO_ID)",) \
		$(if $(ORACLE_OUTPUT_IDS),--output-ids "$(ORACLE_OUTPUT_IDS)",) \
		--strict-seal

# ---------------------------------------------------------------------------
# Scenario Runner test tiers (Makefile-based, no PowerShell)
# ---------------------------------------------------------------------------
.PHONY: sr-tests-tier0 sr-tests-parity sr-tests-localstack sr-tests-engine-fixture sr-tests-all
sr-tests-tier0:
	@$(PY_SCRIPT) -m pytest tests/services/scenario_runner -m "not parity and not localstack and not engine_fixture" -q

sr-tests-parity:
	@$(PY_SCRIPT) -m pytest tests/services/scenario_runner -m "parity" -q

sr-tests-localstack:
	@$(PY_SCRIPT) -m pytest tests/services/scenario_runner -m "localstack" -q

sr-tests-engine-fixture:
	@$(PY_SCRIPT) -m pytest tests/services/scenario_runner -m "engine_fixture" -q

sr-tests-all:
	@$(PY_SCRIPT) -m pytest tests/services/scenario_runner -q

# ---------------------------------------------------------------------------
# LocalStack helpers (Makefile-based)
# ---------------------------------------------------------------------------
.PHONY: localstack-up localstack-down localstack-logs
localstack-up:
	@docker rm -f localstack >/dev/null 2>&1 || true
	@docker run -d --name localstack -p 4566:4566 -e SERVICES=kinesis localstack/localstack:latest

localstack-down:
	@docker rm -f localstack >/dev/null 2>&1 || true

localstack-logs:
	@docker logs -f localstack

