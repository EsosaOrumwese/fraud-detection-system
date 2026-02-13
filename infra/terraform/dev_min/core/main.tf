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

  object_store_bucket_name = trimspace(var.object_store_bucket_name) != "" ? var.object_store_bucket_name : "${var.name_prefix}-object-store"
  evidence_bucket_name     = trimspace(var.evidence_bucket_name) != "" ? var.evidence_bucket_name : "${var.name_prefix}-evidence"
  quarantine_bucket_name   = trimspace(var.quarantine_bucket_name) != "" ? var.quarantine_bucket_name : "${var.name_prefix}-quarantine"
  archive_bucket_name      = trimspace(var.archive_bucket_name) != "" ? var.archive_bucket_name : "${var.name_prefix}-archive"
  tf_state_bucket_name     = trimspace(var.tf_state_bucket_name) != "" ? var.tf_state_bucket_name : "${var.name_prefix}-tfstate"

  control_table_name          = trimspace(var.control_table_name) != "" ? var.control_table_name : "${var.name_prefix}-control-runs"
  ig_admission_table_name     = trimspace(var.ig_admission_table_name) != "" ? var.ig_admission_table_name : "${var.name_prefix}-ig-admission-state"
  ig_publish_state_table_name = trimspace(var.ig_publish_state_table_name) != "" ? var.ig_publish_state_table_name : "${var.name_prefix}-ig-publish-state"
  tf_lock_table_name          = trimspace(var.tf_lock_table_name) != "" ? var.tf_lock_table_name : "${var.name_prefix}-tf-locks"
}

module "core" {
  source = "../../modules/core"

  name_prefix                      = var.name_prefix
  object_store_bucket              = local.object_store_bucket_name
  evidence_bucket                  = local.evidence_bucket_name
  quarantine_bucket                = local.quarantine_bucket_name
  archive_bucket                   = local.archive_bucket_name
  tf_state_bucket                  = local.tf_state_bucket_name
  control_table_name               = local.control_table_name
  ig_admission_table_name          = local.ig_admission_table_name
  ig_publish_state_table_name      = local.ig_publish_state_table_name
  tf_lock_table_name               = local.tf_lock_table_name
  enable_budget_alert              = var.enable_budget_alert
  budget_alert_email               = var.budget_alert_email
  monthly_budget_usd               = var.monthly_budget_usd
  common_tags                      = local.common_tags
  bucket_versioning_status_by_role = var.bucket_versioning_status_by_role
}

