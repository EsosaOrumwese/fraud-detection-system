# ────────────────────────────────────────────────────────────────────────────
#  Variables & Defaults
# ────────────────────────────────────────────────────────────────────────────
# Terraform
TF_DIR         := infra/terraform
TF_PLAN        := plan.out
TFVARS         := terraform.tfvars
ALARM_NAME     ?= Test Alarm

# Data generation & ML
ROWS           ?= 1_000_000
OUTDIR         ?= outputs
DATA_DIR	   ?= $(OUTDIR)/payments_$(subst ,,$(ROWS))_*.parquet
SMOKE_ROWS     ?= 1_000
PROFILE_ARGS   ?=
ML_TRAIN_ARGS  ?=					# ML_TRAIN_ARGS="--n-est 200 --learning-rate 0.05"
MLFLOW_PORT    ?= 5000
MLFLOW_LOG     := mlflow.log
MLFLOW_PID     := .mlflow_ui.pid

# Great Expectations
GE_FILE        ?= data/sample.parquet

export PYTHONUTF8=1

# ────────────────────────────────────────────────────────────────────────────
#  Terraform (leave as-is; you can rename tf-apply→infra-apply etc. if you like)
# ────────────────────────────────────────────────────────────────────────────
.PHONY: tf-init tf-init-remote tf-plan tf-apply pull-raw-bucket pull-artifacts-bucket nuke nuke-dry

tf-init:
	@echo "-> terraform init"
	terraform -chdir=$(TF_DIR) init

tf-init-remote:
	@echo "-> terraform init -reconfigure"
	terraform -chdir=$(TF_DIR) init -reconfigure

tf-plan:
	@echo "-> terraform plan"
	terraform -chdir=$(TF_DIR) plan \
	  -var-file=$(TFVARS) \
	  -out=$(TF_PLAN)

tf-apply:
	@echo "-> terraform apply"
	terraform -chdir=$(TF_DIR) apply $(TF_PLAN)

pull-raw-bucket:
	@echo "-> pulling FRAUD_RAW_BUCKET_NAME into .env"
	poetry run python scripts/pull_raw_bucket.py

pull-artifacts-bucket:
	@echo "-> pulling FRAUD_ARTIFACTS_BUCKET_NAME into .env"
	poetry run python scripts/pull_artifacts_bucket.py

# Load RAW_BUCKET and ARTIFACTS_BUCKET from .env (via pull targets), then destroy
nuke: pull-raw-bucket pull-artifacts-bucket
	@echo "-> Running full sandbox teardown"
	bash infra/scripts/nuke.sh

# Dry-run the same teardown (skips confirmation & tag-check)
nuke-dry:
	@echo "-> Preview sandbox teardown (dry-run)"
	@bash infra/scripts/nuke.sh --dry-run --force


# ────────────────────────────────────────────────────────────────────────────
#  Security & Cost Scanning
# ────────────────────────────────────────────────────────────────────────────
.PHONY: checkov scan-trivy tfsec infracost budget-test alarm-test

checkov:
	@echo "-> Running Checkov"
	checkov -d $(TF_DIR) --framework terraform --quiet --soft-fail-on MEDIUM \
	  --skip-path '$(TF_DIR)/lambda' --skip-path '.*\.zip$$'

scan-trivy:
	@echo "-> Running Trivy config scan"
	trivy config $(TF_DIR)

tfsec:
	@echo "-> Running tfsec"
	tfsec $(TF_DIR)

infracost:
	@echo "-> Running Infracost diff"
	infracost diff --path $(TF_DIR) --format diff --show-skipped

budget-test:
	@echo "-> Triggering AWS Budget test alert"
	@echo "  (login to AWS Console -> Budgets -> Send test alert)"

alarm-test:
	@echo "-> Forcing billing alarm into ALARM state"
	aws cloudwatch set-alarm-state \
	  --alarm-name "$(ALARM_NAME)" \
	  --state-value ALARM \
	  --state-reason "manual test via make alarm-test"

# ────────────────────────────────────────────────────────────────────────────
#  Build Lambda ZIP
# ────────────────────────────────────────────────────────────────────────────
.PHONY: build-lambda

build-lambda:
	@echo "-> Packaging Lambda ZIP"
	@mkdir -p $(TF_DIR)/lambda
	@python -m zipfile -c $(TF_DIR)/lambda/cost_kill.zip lambda/index.py

# ────────────────────────────────────────────────────────────────────────────
#  Docs & Schema management
# ────────────────────────────────────────────────────────────────────────────
.PHONY: docs test-schema json-schema bump-schema

docs:
	@echo "-> Generating Markdown data dictionary"
	@mkdir -p docs/data-dictionary
	@poetry run python scripts/schema_to_md.py > \
	  docs/data-dictionary/schema_v$$(yq '.version' config/transaction_schema.yaml).md

test-schema:
	@echo "-> Testing YAML schema syntax"
	poetry run pytest -q tests/unit/test_schema_yaml.py

json-schema:
	@echo "→ Converting YAML → JSON Schema"
	poetry run python scripts/schema_to_json.py

bump-schema:
	@echo "-> Bumping schema version (kind=$(kind))"
	@poetry run python scripts/bump_schema_version.py $(kind)
	@git add config/transaction_schema.yaml
	@git commit -m "chore(schema): bump version" --no-verify
	@git tag "schema-v$$(yq '.version' config/transaction_schema.yaml)"

# ────────────────────────────────────────────────────────────────────────────
#  Great Expectations
# ────────────────────────────────────────────────────────────────────────────
.PHONY: ge-bootstrap ge-validate smoke-schema

ge-bootstrap:
	@echo "-> Bootstrapping Great Expectations"
	poetry run python scripts/ge_bootstrap.py

ge-validate:
	@echo "-> Validating $(GE_FILE)"
	poetry run python scripts/ge_validate.py $(GE_FILE)

smoke-schema:
	@echo "-> Smoke-testing schema with $(SMOKE_ROWS) rows"
	@rm -rf tmp && mkdir -p tmp
	poetry run python -m fraud_detection.simulator.generate \
	  --rows $(SMOKE_ROWS) --out tmp --s3 no
	poetry run python scripts/ge_validate.py tmp/payments_*_*.parquet
	@rm -rf tmp

# ────────────────────────────────────────────────────────────────────────────
#  Data Generation & Profiling
# ────────────────────────────────────────────────────────────────────────────
.PHONY: gen-data-local gen-data-raw validate-data gen-data profile clean-memory

gen-data-local:
	@echo "-> Generating $(ROWS) rows (local)"
	poetry run python -m fraud_detection.simulator.generate \
	  --rows $(ROWS) --out $(OUTDIR) --s3 no

gen-data-raw:
	@echo "-> Generating $(ROWS) rows & uploading to RAW_BUCKET"
	poetry run python -m fraud_detection.simulator.generate \
	  --rows $(ROWS) --out $(OUTDIR) --s3 yes

validate-data:
	@echo "-> Validating latest Parquet"
	@FILE=$$(ls $(OUTDIR)/payments_$(subst ,,$(ROWS))_*.parquet | tail -n1); \
	if [ -z "$$FILE" ]; then \
	  echo "x No file to validate"; exit 1; \
	else \
	  poetry run python scripts/ge_validate.py $$FILE; \
	fi

# Combined pipeline
gen-data: gen-data-local validate-data

profile:
	@echo "-> Profiling parquet"
	@FILE=$$(ls $(OUTDIR)/payments_$(subst ,,$(ROWS))_*.parquet | tail -n1); \
	if [ -z "$$FILE" ]; then \
	  echo "✗ No parquet to profile"; exit 1; \
	else \
	  poetry run python scripts/profile_parquet.py "$$FILE"; \
	fi

clean-memory:
	@echo "→ Cleaning output directory"
	@rm -rf $(OUTDIR)

# ────────────────────────────────────────────────────────────────────────────
#  Model Training & MLflow UI
# ────────────────────────────────────────────────────────────────────────────
.PHONY: ml-train mlflow-ui-start mlflow-ui-stop

ml-train:
	@echo "-> Training model (rows=$(ROWS))"
	poetry run python -m fraud_detection.modelling.train_baseline \
	  --rows $(ROWS) \
	  --parquet $(DATA_DIR) $(ML_TRAIN_ARGS)

mlflow-ui-start:
	@echo "-> Starting MLflow UI on port $(MLFLOW_PORT)"
	@nohup poetry run mlflow ui -p $(MLFLOW_PORT) \
	  >$(MLFLOW_LOG) 2>&1 & echo $$! >$(MLFLOW_PID)
	@echo "   Logs: $(MLFLOW_LOG), PID: $(MLFLOW_PID)"

mlflow-ui-stop:
	@if [ -f $(MLFLOW_PID) ]; then \
	  PID=$$(cat $(MLFLOW_PID)); \
	  echo "-> Stopping MLflow UI (PID $$PID)"; \
	  kill $$PID && rm $(MLFLOW_PID); \
	else \
	  echo "x No PID file at $(MLFLOW_PID)"; \
	fi

# ────────────────────────────────────────────────────────────────────────────
#  Orchestration: Airflow
# ────────────────────────────────────────────────────────────────────────────
AIRFLOW_DIR := orchestration/airflow
ENV_FILE     = $(AIRFLOW_DIR)/.env
COMPOSE      = docker compose -f $(AIRFLOW_DIR)/docker-compose.yml --env-file $(ENV_FILE)

.PHONY: airflow-bootstrap airflow-build airflow-up airflow-down airflow-reset airflow-logs airflow-test-dag

airflow-bootstrap:
	@echo "Bootstrapping Airflow secrets..."
	@bash -c 'exec "$(AIRFLOW_DIR)/scripts/bootstrap.sh"'

airflow-build:
	@echo "Rebuilding your custom image..."
	@$(COMPOSE) build --pull

airflow-up: #airflow-bootstrap
	@echo "Starting Airflow..."
	@echo "   Initialize DB and Admin User"
	@$(COMPOSE) up airflow-init
	@echo "   Bring up the long running services"
	@$(COMPOSE) up -d --wait

airflow-down:
	@echo "Stopping Airflow..."
	@$(COMPOSE) down -v || true

airflow-reset: airflow-down
	@echo "Resetting state..."
	@rm -rf $(AIRFLOW_DIR)/postgres-db-volume $(AIRFLOW_DIR)/logs/*

airflow-logs:
	@echo "Tailing logs..."
	@$(COMPOSE) logs -f airflow-apiserver

airflow-test-dag: #airflow-up
	@echo "Smoke-test imports"
	@$(COMPOSE) exec airflow-scheduler airflow dags list
	@echo "Runtime test a single task to catch missing deps or runtime errors"
	@$(COMPOSE) exec airflow-scheduler \
      airflow tasks test daily_synthetic run_generator $$(date +%Y-%m-%d)
	@echo "   Successful!"
#	@echo "Tear down services and volumes"
#	@$(COMPOSE) --env-file $(ENV_FILE) down -v #|| true
