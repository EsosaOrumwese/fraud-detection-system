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