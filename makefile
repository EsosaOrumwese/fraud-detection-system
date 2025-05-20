.PHONY: tf-init tf-plan tf-apply nuke tf-init-remote

# ────────────────────────────────────────────────────────────────────────────
# Variables
# ────────────────────────────────────────────────────────────────────────────
TF_DIR   := infra/terraform
TF_PLAN  := plan.out
ENV      ?= sandbox
TFVARS   := $(ENV).tfvars

# ────────────────────────────────────────────────────────────────────────────
# Terraform targets
# ────────────────────────────────────────────────────────────────────────────
.PHONY: tf-init tf-init-remote tf-plan tf-apply nuke

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-init-remote:
	terraform -chdir=infra/terraform init \
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="dynamodb_table=$(TF_STATE_TABLE)" \
		-backend-config="key=sandbox/terraform.tfstate" \
		-backend-config="region=eu-west-2"
	  	-reconfigure

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
	checkov -d $(TF_DIR)

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
# You can now run:
#   make tf-init
#   make tf-plan
#   make tf-apply
#   make checkov
#   make scan-trivy
#   make infracost
#   etc.
# ────────────────────────────────────────────────────────────────────────────
