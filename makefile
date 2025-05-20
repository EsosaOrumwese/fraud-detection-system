.PHONY: tf-init tf-plan tf-apply nuke tf-init-remote

TF_DIR   := infra/terraform
TF_PLAN  := plan.out
ENV      ?= sandbox
TFVARS   := $(ENV).tfvars

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-plan:
	terraform -chdir=$(TF_DIR) plan \
	  -var-file="$(TFVARS)" \
	  -out=$(TF_PLAN)

tf-apply:
	terraform -chdir=$(TF_DIR) apply $(TF_PLAN)

nuke:
	terraform -chdir=$(TF_DIR) destroy -auto-approve

tf-init-remote:
	terraform -chdir=infra/terraform init \
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="dynamodb_table=$(TF_STATE_TABLE)" \
		-backend-config="key=sandbox/terraform.tfstate" \
		-backend-config="region=eu-west-2"

