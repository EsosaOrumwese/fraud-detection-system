###############################################################################
# Remote-state backend
# A shared, versioned state is expected not local .tfstate files
#
# NOTE: this file is *not* read during `terraform init` until you let Terraform
#       know via the init command (see make tf-init-remote).
###############################################################################

terraform {
  backend "s3" {
    bucket       = "tfstate-esosaorumwese808-fraud" # create once, keep private+encrypted
    key          = "sandbox/terraform.tfstate"
    region       = "eu-west-2"
    use_lockfile = true
    encrypt      = true
  }
}

