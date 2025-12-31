SHELL := C:/Progra~1/Git/bin/bash.exe
.SHELLFLAGS := -eu -o pipefail -c

PY ?= python
ENGINE_PYTHONPATH ?= packages/engine/src

# Paths and summaries
RUN_ROOT ?= runs/local_layer1_regen4
SUMMARY_DIR ?= $(RUN_ROOT)/summaries
RESULT_JSON ?= $(SUMMARY_DIR)/segment1a_result.json
SEG1B_RESULT_JSON ?= $(SUMMARY_DIR)/segment1b_result.json
SEG2A_RESULT_JSON ?= $(SUMMARY_DIR)/segment2a_result.json
SEG2B_RESULT_JSON ?= $(SUMMARY_DIR)/segment2b_result.json
SEG3A_RESULT_JSON ?= $(SUMMARY_DIR)/segment3a_result.json
SEG3B_RESULT_JSON ?= $(SUMMARY_DIR)/segment3b_result.json
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
SEG1A_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment1a $(SEG1A_ARGS)

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
SEG1B_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment1b run $(SEG1B_ARGS)

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
SEG2A_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment2a $(SEG2A_ARGS)

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
SEG2B_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment2b $(SEG2B_ARGS)

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
SEG3A_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment3a $(SEG3A_ARGS)

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
SEG3B_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment3b $(SEG3B_ARGS)

# Segment 5A
SEG5A_RESULT_JSON ?= $(SUMMARY_DIR)/segment5a_result.json
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
SEG5A_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m engine.cli.segment5a $(SEG5A_ARGS)

MERCHANT_BUILD_CMD = PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) scripts/build_transaction_schema_merchant_ids.py \
	--version $(MERCHANT_VERSION) \
	--iso-version $(MERCHANT_ISO_VERSION) \
	--gdp-version $(MERCHANT_GDP_VERSION) \
	--bucket-version $(MERCHANT_BUCKET_VERSION)

HURDLE_EXPORT_CMD = $(PY) scripts/build_hurdle_exports.py
CURRENCY_REF_CMD = $(PY) scripts/build_currency_reference_surfaces.py
VIRTUAL_EDGE_POLICY_CMD = $(PY) scripts/build_virtual_edge_policy_v1.py
ZONE_FLOOR_POLICY_CMD = $(PY) scripts/build_zone_floor_policy_3a.py
COUNTRY_ZONE_ALPHAS_CMD = $(PY) scripts/build_country_zone_alphas_3a.py
CROSSBORDER_FEATURES_CMD = $(PY) scripts/build_crossborder_features_1a.py


.PHONY: all segment1a segment1b segment2a segment2b segment3a segment3b segment5a merchant_ids hurdle_exports currency_refs virtual_edge_policy zone_floor_policy country_zone_alphas crossborder_features profile-all profile-seg1b clean-results

all: segment1a segment1b segment2a segment2b segment3a segment3b segment5a

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

segment1a:
	@mkdir -p "$(RUN_ROOT)"
	@mkdir -p "$(SUMMARY_DIR)"
ifeq ($(strip $(LOG)),)
	$(SEG1A_CMD)
else
	@: > "$(LOG)"
	($(SEG1A_CMD)) 2>&1 | tee -a "$(LOG)"
endif

segment1b:
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

profile-all:
	PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m cProfile -o profile.segment1a -m engine.cli.segment1a $(SEG1A_ARGS)
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

profile-seg1b:
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 PYTHONPATH=$(ENGINE_PYTHONPATH) $(PY) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

clean-results:
	rm -rf "$(SUMMARY_DIR)"
	rm -f profile.segment1a profile.segment1b
