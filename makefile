.PHONY: tf-init tf-plan tf-apply nuke tf-init-remote

# ────────────────────────────────────────────────────────────────────────────
# Variables
# ────────────────────────────────────────────────────────────────────────────
TF_DIR   := infra/terraform
TF_PLAN  := plan.out
#ENV      ?= sandbox
TFVARS   := terraform.tfvars
ALARM_NAME    ?= fraud-sbx-billing-40gbp
export PYTHONUTF8 = 1


# ────────────────────────────────────────────────────────────────────────────
# Terraform targets
# ────────────────────────────────────────────────────────────────────────────
.PHONY: tf-init tf-init-remote tf-plan tf-apply nuke

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-init-remote:
	terraform -chdir=infra/terraform init -reconfigure

tf-plan:
	terraform -chdir=$(TF_DIR) plan \
	  -var-file=$(TFVARS) \
	  -out=$(TF_PLAN)

tf-apply:
	terraform -chdir=$(TF_DIR) apply $(TF_PLAN)

nuke:
	terraform -chdir=$(TF_DIR) destroy -auto-approve

# ────────────────────────────────────────────────────────────────────────────
# Security / Scanning targets
# ────────────────────────────────────────────────────────────────────────────
.PHONY: checkov scan-trivy tfsec

checkov:
	@echo "-> Running Checkov with UTF-8 forced"
	checkov -d $(TF_DIR) \
	  --framework terraform \
	  --quiet \
	  --soft-fail-on MEDIUM \
	  --skip-path '$(TF_DIR)/lambda' \
	  --skip-path '.*\.zip$$'

scan-trivy:
	trivy config $(TF_DIR)

tfsec:
	tfsec $(TF_DIR)

# ────────────────────────────────────────────────────────────────────────────
# Infracost
# ────────────────────────────────────────────────────────────────────────────
.PHONY: infracost
infracost:
	infracost diff \
	  --path $(TF_DIR) \
	  --format diff \
	  --show-skipped

# ────────────────────────────────────────────────────────────────────────────
# Budget & Alarms
# ────────────────────────────────────────────────────────────────────────────
.PHONY: budget-test alarm-test

budget-test:   ## Send dummy budget alert from console
	@echo " Go to AWS Budgets -> your budget -> 'Send test alert'"

alarm-test:    ## Force a billing alarm into ALARM state
	@echo "-> Forcing alarm '$(ALARM_NAME)' to ALARM"
	aws cloudwatch set-alarm-state \
	  --alarm-name "$(ALARM_NAME)" \
	  --state-value  ALARM \
	  --state-reason "manual-test via make alarm-test"

# ────────────────────────────────────────────────────────────────────────────
# Build Lambda
# ────────────────────────────────────────────────────────────────────────────
.PHONY: build-lambda

build-lambda:
	mkdir -p infra/terraform/lambda
	python -m zipfile -c infra/terraform/lambda/cost_kill.zip lambda/index.py

# ────────────────────────────────────────────────────────────────────────────
# Generate Markdown data dictionary
# ────────────────────────────────────────────────────────────────────────────
.PHONY: docs test-schema json-schema bump-schema

docs:
	@mkdir -p docs/data-dictionary
	poetry run python scripts/schema_to_md.py > \
	   docs/data-dictionary/schema_v$(shell yq '.version' config/transaction_schema.yaml).md

test-schema:  ## Fast-path test
	poetry run pytest -q tests/unit/test_schema_yaml.py

json-schema:  ## YAML → JSON-Schema
	poetry run python scripts/schema_to_json.py

bump-schema:  ## Args: kind=[patch|minor|major] (default patch)
	poetry run python scripts/bump_schema_version.py $(kind)
	git add config/transaction_schema.yaml
	git commit -m "chore(schema): bump version"
	git tag "schema-v$$(yq '.version' config/transaction_schema.yaml)"

# ────────────────────────────────────────────────────────────────────────────
# Great Expectations Bootstrap and Validate
# ────────────────────────────────────────────────────────────────────────────
FILE ?= data/sample.parquet

.PHONY: ge-bootstrap gen-empty-parquet ge-validate smoke-schema

# ――― Build GE context & suite ―――
ge-bootstrap:
	poetry run python scripts/ge_bootstrap.py

# ――― Generate empty Parquet matching your schema ―――
gen-empty-parquet:
	poetry run python scripts/gen_empty_parquet.py

# ――― Validate a file (override with FILE=…) ―――
ge-validate:
	poetry run python scripts/ge_validate.py $(FILE)

# ――― Smoke‐test: bootstrap → empty parquet → validate ―――

# produce a single valid row
gen-smoke-data:
	@poetry run python scripts/gen_dummy_parquet.py

smoke-schema: ge-bootstrap gen-smoke-data
	@echo "✓ Running GE smoke-test against tmp/dummy.parquet"
	@$(MAKE) ge-validate FILE=tmp/dummy.parquet
