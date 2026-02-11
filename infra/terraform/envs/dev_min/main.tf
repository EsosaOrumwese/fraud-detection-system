locals {
  common_tags = {
    project    = var.project
    env        = var.environment
    owner      = var.owner
    expires_at = var.expires_at
    fp_env     = var.environment
  }

  tf_state_bucket_name        = trimspace(var.tf_state_bucket_name) != "" ? var.tf_state_bucket_name : "${var.name_prefix}-tfstate"
  control_table_name          = trimspace(var.control_table_name) != "" ? var.control_table_name : "${var.name_prefix}-control-runs"
  ig_admission_table_name     = trimspace(var.ig_admission_table_name) != "" ? var.ig_admission_table_name : "${var.name_prefix}-ig-admission-state"
  ig_publish_state_table_name = trimspace(var.ig_publish_state_table_name) != "" ? var.ig_publish_state_table_name : "${var.name_prefix}-ig-publish-state"
  tf_lock_table_name          = trimspace(var.tf_lock_table_name) != "" ? var.tf_lock_table_name : "${var.name_prefix}-tf-locks"
}

provider "aws" {
  region = var.aws_region
}

module "core" {
  count = var.enable_core ? 1 : 0

  source = "../../modules/core"

  name_prefix                      = var.name_prefix
  object_store_bucket              = var.object_store_bucket_name
  evidence_bucket                  = var.evidence_bucket_name
  quarantine_bucket                = var.quarantine_bucket_name
  archive_bucket                   = var.archive_bucket_name
  tf_state_bucket                  = local.tf_state_bucket_name
  control_table_name               = local.control_table_name
  ig_admission_table_name          = local.ig_admission_table_name
  ig_publish_state_table_name      = local.ig_publish_state_table_name
  tf_lock_table_name               = local.tf_lock_table_name
  enable_budget_alert              = var.enable_budget_alert
  budget_alert_email               = var.budget_alert_email
  monthly_budget_usd               = var.monthly_budget_limit_usd
  bucket_versioning_status_by_role = var.bucket_versioning_status_by_role
  common_tags                      = local.common_tags
}

module "demo" {
  count = var.enable_demo ? 1 : 0

  source = "../../modules/demo"

  name_prefix          = var.name_prefix
  environment          = var.environment
  demo_run_id          = var.demo_run_id
  evidence_bucket      = var.evidence_bucket_name
  cloudwatch_retention = var.demo_log_retention_days
  common_tags          = local.common_tags

  depends_on = [module.core]
}
