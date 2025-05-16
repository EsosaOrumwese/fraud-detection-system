###############################################################################
#  Provider config is *profile-based* — avoids hard-coding keys.
#  Developers export AWS_PROFILE=fraud-dev  OR  use LocalStack endpoints.
###############################################################################
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile # set to "default" or "fraud-dev"

  # --- LocalStack toggle (optional) -----------------------------------------
  # Comment-in these lines when running `localstack start -d` and remove asterisk
  # access_k*e*y                  = "test"
  # secret_k*e*y                  = "test"
  # s3_use_path_style           = true
  # endpoints {
  #   s3 = "http://localhost:4566"
  # }
}

locals {
  common_tags = {
    Project     = "fraud-detection-system"
    Environment = "dev"
    Owner       = var.owner
    IaC         = "terraform"
  }
}
