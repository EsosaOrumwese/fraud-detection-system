###############################################################################
# Terraform core & AWS provider versions
#
# • Pin Terraform to the latest minor that’s still widely supported (1.12.x)
#   so “terraform init” on GitHub Actions uses the same binary as locally.
# • Pin AWS provider to a caret-range so you get patch updates but not
#   accidental breaking changes (>=5.36,<6).
###############################################################################

terraform {
  required_version = "~> 1.12"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.98"
    }
  }
}

###############################################################################
# Provider configuration
#
# • Region is parameterised so you can deploy to another region with a single
#   `-var="aws_region=us-east-1"` flag.
# • `default_tags` guarantee cost-allocation and security teams always see
#   who owns a resource, even if an engineer forgets to tag one manually.
###############################################################################

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project     = "fraud-detection"
      environment = var.environment
    }
  }
}