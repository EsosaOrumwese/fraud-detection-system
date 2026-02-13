provider "aws" {
  region = var.aws_region
}

locals {
  common_tags = {
    project    = var.project
    env        = var.environment
    owner      = var.owner
    expires_at = var.expires_at
  }
}

module "demo" {
  source = "../../modules/demo"

  name_prefix          = var.name_prefix
  environment          = var.environment
  demo_run_id          = var.demo_run_id
  evidence_bucket      = var.evidence_bucket_name
  cloudwatch_retention = var.demo_log_retention_days
  common_tags          = local.common_tags
}

