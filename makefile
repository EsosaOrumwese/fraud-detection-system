SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PY ?= python

RUN_ROOT ?= runs/local_layer1_regen7
RESULT_JSON ?= $(RUN_ROOT)/segment1a_result.json
LOG ?=
SEED ?= 2025102601

GIT_COMMIT ?= $(shell git rev-parse HEAD)

MERCHANT_TABLE ?= reference/layer1/transaction_schema_merchant_ids/v2025-10-09/transaction_schema_merchant_ids.parquet
ISO_TABLE ?= reference/layer1/iso_canonical/v2025-10-09/iso_canonical.parquet
GDP_TABLE ?= reference/economic/world_bank_gdp_per_capita/2025-10-07/gdp.parquet
BUCKET_TABLE ?= reference/economic/gdp_bucket_map/2025-10-08/gdp_bucket_map.parquet
NUMERIC_POLICY ?= reference/governance/numeric_policy/2025-10-07/numeric_policy.json
MATH_PROFILE ?= reference/governance/math_profile/2025-10-08/math_profile_manifest.json
VALIDATION_POLICY ?= contracts/policies/l1/seg_1A/s2_validation_policy.yaml
SEG1B_DICTIONARY ?= contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml

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
SEG1A_CMD = $(PY) -m engine.cli.segment1a $(SEG1A_ARGS)

SEG1B_BASIS ?= population
SEG1B_DP ?= 4
SEG1B_S1_WORKERS ?= 12
SEG1B_S4_WORKERS ?= 12
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
	$(SEG1B_EXTRA)
SEG1B_CMD = $(PY) -m engine.cli.segment1b run $(SEG1B_ARGS)

.PHONY: all segment1a segment1b profile-all profile-seg1b clean-results

all: segment1b

segment1a:
	@mkdir -p "$(RUN_ROOT)"
ifeq ($(strip $(LOG)),)
	$(SEG1A_CMD)
else
	($(SEG1A_CMD)) 2>&1 | tee "$(LOG)"
endif

segment1b:
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 if [ -n "$(LOG)" ]; then \
		($(SEG1B_CMD)) 2>&1 | tee -a "$(LOG)"; \
	 else \
		$(SEG1B_CMD); \
	 fi

profile-all:
	$(PY) -m cProfile -o profile.segment1a -m engine.cli.segment1a $(SEG1A_ARGS)
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 $(PY) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

profile-seg1b:
	@if [ ! -f "$(RESULT_JSON)" ]; then \
		echo "Segment 1A summary '$(RESULT_JSON)' not found. Run 'make segment1a' first." >&2; \
		exit 1; \
	fi
	@PARAM_HASH=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['parameter_hash'])"); \
	 MANIFEST_FINGERPRINT=$$($(PY) -c "import json; print(json.load(open('$(RESULT_JSON)'))['s0']['manifest_fingerprint'])"); \
	 $(PY) -m cProfile -o profile.segment1b -m engine.cli.segment1b run $(SEG1B_ARGS)

clean-results:
	rm -f "$(RESULT_JSON)" profile.segment1a profile.segment1b
