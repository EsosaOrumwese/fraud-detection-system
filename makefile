SHELL := C:/Progra~1/Git/bin/bash.exe
.SHELLFLAGS := -eu -o pipefail -c

PY ?= python
ENGINE_PYTHONPATH ?= packages/engine/src
PYTHONUNBUFFERED ?= 1

# Python command wrappers (unbuffered to keep console output responsive).
PY_ENGINE = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY)
PY_SCRIPT = PYTHONUNBUFFERED=$(PYTHONUNBUFFERED) $(PY)

# Paths and summaries
RUN_ROOT ?= runs/local_layer1_regen4
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
RUN_ID ?= run-0
LOG ?= $(RUN_ROOT)/run_log_regen4.log
SEED ?= 2025121401

GIT_COMMIT ?= $(shell git rev-parse HEAD)

MERCHANT_VERSION ?= 2025-11-28
MERCHANT_TABLE ?= reference/layer1/transaction_schema_merchant_ids/v$(MERCHANT_VERSION)/transaction_schema_merchant_ids.parquet
MERCHANT_ISO_VERSION ?= 2025-10-08
MERCHANT_GDP_VERSION ?= 2025-10-07
MERCHANT_BUCKET_VERSION ?= 2025-10-07
ISO_TABLE ?= reference/layer1/iso_canonical/v2025-10-09/iso_canonical.parquet
GDP_TABLE ?= reference/economic/world_bank_gdp_per_capita/2025-10-07/gdp.parquet
BUCKET_TABLE ?= reference/economic/gdp_bucket_map/2025-10-08/gdp_bucket_map.parquet
NUMERIC_POLICY ?= reference/governance/numeric_policy/2025-10-07/numeric_policy.json
MATH_PROFILE ?= reference/governance/math_profile/2025-10-08/math_profile_manifest.json
VALIDATION_POLICY ?= contracts/policies/l1/seg_1A/s2_validation_policy.yaml
SEG1B_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml

# Segment 1A
SEG1A_EXTRA ?=

SEG1A_ARGS = \
	--output-dir $(RUN_ROOT) \
	--merchant-table $(MERCHANT_TABLE) \
	--iso-table $(ISO_TABLE) \
	--gdp-table $(GDP_TABLE) \
	--bucket-table $(BUCKET_TABLE) \
	--param policy.s3.rule_ladder.yaml=contracts/policies/l1/seg_1A/policy.s3.rule_ladder.yaml \
	--param policy.s3.base_weight.yaml=contracts/policies/l1/seg_1A/policy.s3.base_weight.yaml \
	--param policy.s3.thresholds.yaml=contracts/policies/l1/seg_1A/policy.s3.thresholds.yaml \
	--param policy.s3.bounds.yaml=contracts/policies/l1/seg_1A/policy.s3.bounds.yaml \
	--param crossborder_hyperparams.yaml=config/policy/crossborder_hyperparams.yaml \
	--param hurdle_coefficients.yaml=config/models/hurdle/exports/version=2025-10-09/20251009T120000Z/hurdle_coefficients.yaml \
	--param nb_dispersion_coefficients.yaml=config/models/hurdle/exports/version=2025-10-24/20251024T234923Z/nb_dispersion_coefficients.yaml \
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
SEG2A_TZ_CONFIG_ROOT ?= config/timezone
SEG2A_CANONICAL_TZDATA = $(SEG2A_TZDATA_ROOT)/$(SEG2A_TZDB_RELEASE)
SEG2A_RUN_TZDATA = $(RUN_ROOT)/artefacts/priors/tzdata/$(SEG2A_TZDB_RELEASE)
SEG2A_RUN_TZCFG = $(RUN_ROOT)/config/timezone
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
SEG2B_S5_SELECTION_LOG ?= 0
SEG2B_S5_ARRIVALS_JSONL ?=
SEG2B_S5_QUIET ?= 1
SEG2B_RUN_S6 ?= 1
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
ifeq ($(strip $(SEG2B_S5_SELECTION_LOG)),1)
SEG2B_EXTRA += --s5-selection-log
endif
ifneq ($(strip $(SEG2B_S5_ARRIVALS_JSONL)),)
SEG2B_EXTRA += --s5-arrivals-jsonl "$(SEG2B_S5_ARRIVALS_JSONL)"
endif
ifeq ($(strip $(SEG2B_S5_QUIET)),1)
SEG2B_EXTRA += --s5-quiet-run-report
endif
ifeq ($(strip $(SEG2B_RUN_S6)),1)
SEG2B_EXTRA += --run-s6
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
	--seed $(SEED) \
	--git-commit-hex $(GIT_COMMIT) \
	--dictionary "$(SEG3B_DICTIONARY)" \
	--validation-bundle-1a "$$VALIDATION_BUNDLE_1A" \
	--validation-bundle-1b "$$VALIDATION_BUNDLE_1B" \
	--validation-bundle-2a "$$VALIDATION_BUNDLE_2A" \
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
	--result-json "$(SEG5B_RESULT_JSON)"
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
	--bucket-version $(MERCHANT_BUCKET_VERSION)

HURDLE_EXPORT_CMD = $(PY_SCRIPT) scripts/build_hurdle_exports.py
CURRENCY_REF_CMD = $(PY_SCRIPT) scripts/build_currency_reference_surfaces.py
VIRTUAL_EDGE_POLICY_CMD = $(PY_SCRIPT) scripts/build_virtual_edge_policy_v1.py
ZONE_FLOOR_POLICY_CMD = $(PY_SCRIPT) scripts/build_zone_floor_policy_3a.py
COUNTRY_ZONE_ALPHAS_CMD = $(PY_SCRIPT) scripts/build_country_zone_alphas_3a.py
CROSSBORDER_FEATURES_CMD = $(PY_SCRIPT) scripts/build_crossborder_features_1a.py
MERCHANT_CLASS_POLICY_5A_CMD = $(PY_SCRIPT) scripts/build_merchant_class_policy_5a.py
DEMAND_SCALE_POLICY_5A_CMD = $(PY_SCRIPT) scripts/build_demand_scale_policy_5a.py
SHAPE_LIBRARY_5A_CMD = $(PY_SCRIPT) scripts/build_shape_library_5a.py --bucket-minutes 60
SCENARIO_CAL_FINGERPRINT ?= e22b195ba9fa8ed582f4669a26009c67637760bfe3b51c9ac77af92b6aa572e9
SCENARIO_CAL_ZONE_ALLOC ?= runs/local_layer1_regen4/data/layer1/3A/zone_alloc/seed=2025121401/fingerprint=$(SCENARIO_CAL_FINGERPRINT)/part-0.parquet
SCENARIO_CAL_CMD = $(PY_SCRIPT) scripts/build_scenario_calendar_5a.py --manifest-fingerprint $(SCENARIO_CAL_FINGERPRINT) --zone-alloc-path $(SCENARIO_CAL_ZONE_ALLOC)
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


.PHONY: all segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a segment6b merchant_ids hurdle_exports currency_refs virtual_edge_policy zone_floor_policy country_zone_alphas crossborder_features merchant_class_policy_5a demand_scale_policy_5a shape_library_5a scenario_calendar_5a policies_5a cdn_weights_ext mcc_channel_rules cdn_country_weights virtual_validation cdn_key_digest hrsl_raster pelias_cached virtual_settlement_coords profile-all profile-seg1b clean-results

all: segment1a segment1b segment2a segment2b segment3a segment3b segment5a segment5b segment6a segment6b

merchant_ids:
	@echo "Building transaction_schema_merchant_ids version $(MERCHANT_VERSION)"
	$(MERCHANT_BUILD_CMD)

hurdle_exports:
	@echo "Building hurdle + dispersion export bundles"
	$(HURDLE_EXPORT_CMD)

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
	@echo "Building 5A scenario_calendar_5A (fingerprint $(SCENARIO_CAL_FINGERPRINT))"
	$(SCENARIO_CAL_CMD)

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

segment1a:
	@echo "Running Segment 1A (S0-S9)"
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
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@if [ ! -d "$(RUN_ROOT)/data/layer1/1B" ]; then \
		echo "Segment 1B outputs not found under '$(RUN_ROOT)/data/layer1/1B'. Run 'make segment1b' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE="$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=$$MANIFEST_FINGERPRINT/bundle"; \
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
	 VALIDATION_BUNDLE_1A="$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=$$MANIFEST_FINGERPRINT"; \
	 VALIDATION_BUNDLE_1B="$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=$$MANIFEST_FINGERPRINT"; \
	 VALIDATION_BUNDLE_2A="$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=$$SEG2A_MANIFEST_FINGERPRINT"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG3A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG3A_CMD); \
	 fi

segment3b:
	@echo "Running Segment 3B (S0-S5)"
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
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 SEG2A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG2A_RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A="$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=$$MANIFEST_FINGERPRINT"; \
	 VALIDATION_BUNDLE_1B="$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=$$MANIFEST_FINGERPRINT"; \
	 VALIDATION_BUNDLE_2A="$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=$$SEG2A_MANIFEST_FINGERPRINT"; \
	 SEG3A_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG3A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 UPSTREAM_MANIFEST_FINGERPRINT=$$SEG3A_MANIFEST_FINGERPRINT; \
	 VALIDATION_BUNDLE_3A="$(RUN_ROOT)/data/layer1/3A/validation/fingerprint=$$SEG3A_MANIFEST_FINGERPRINT"; \
	 if [ -n "$(LOG)" ]; then \
		($(SEG3B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG3B_CMD); \
	 fi

segment5a:
	@echo "Running Segment 5A (S0-S5)"
	@if [ ! -f "$(SEG3B_RESULT_JSON)" ]; then \
		echo "Segment 3B summary '$(SEG3B_RESULT_JSON)' not found. Run 'make segment3b' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG3B_RESULT_JSON)'))['parameter_hash'])"); \
	 UPSTREAM_MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG3B_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_1B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG5A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG5A_CMD); \
	 fi

segment5b:
	@echo "Running Segment 5B (S0-S5)"
	@if [ ! -f "$(SEG5A_RESULT_JSON)" ]; then \
		echo "Segment 5A summary '$(SEG5A_RESULT_JSON)' not found. Run 'make segment5a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG5A_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG5A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_1B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_5A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer2/5A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG5B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG5B_CMD); \
	 fi

segment6a:
	@echo "Running Segment 6A (S0-S5)"
	@if [ ! -f "$(SEG5B_RESULT_JSON)" ]; then \
		echo "Segment 5B summary '$(SEG5B_RESULT_JSON)' not found. Run 'make segment5b' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG5B_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG5B_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_1B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_5A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer2/5A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_5B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer2/5B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG6A_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG6A_CMD); \
	 fi

segment6b:
	@echo "Running Segment 6B (S0-S5)"
	@if [ ! -f "$(SEG6A_RESULT_JSON)" ]; then \
		echo "Segment 6A summary '$(SEG6A_RESULT_JSON)' not found. Run 'make segment6a' first." >&2; \
		exit 1; \
	fi
	@mkdir -p "$(SUMMARY_DIR)"
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(SEG6A_RESULT_JSON)'))['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(SEG6A_RESULT_JSON)'))['manifest_fingerprint'])"); \
	 VALIDATION_BUNDLE_1A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_1B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/1B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_2B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/2B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_3B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer1/3B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_5A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer2/5A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_5B=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer2/5B/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 VALIDATION_BUNDLE_6A=$$($(PY) -c "import glob; paths=glob.glob('$(RUN_ROOT)/data/layer3/6A/validation/fingerprint=*'); print(paths[0] if paths else '')"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG6B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG6B_CMD); \
	 fi

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
