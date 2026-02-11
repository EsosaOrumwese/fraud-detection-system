variable "aws_region" {
  type = string
}

variable "name_prefix" {
  type    = string
  default = "fraud-platform-dev-min"
}

variable "project" {
  type    = string
  default = "fraud-platform"
}

variable "environment" {
  type    = string
  default = "dev_min"
}

variable "owner" {
  type    = string
  default = "fraud-dev"
}

variable "expires_at" {
  type    = string
  default = ""
}

variable "object_store_bucket_name" {
  type = string
}

variable "evidence_bucket_name" {
  type = string
}

variable "quarantine_bucket_name" {
  type = string
}

variable "archive_bucket_name" {
  type = string
}

variable "tf_state_bucket_name" {
  type    = string
  default = ""
}

variable "control_table_name" {
  type    = string
  default = ""
}

variable "ig_admission_table_name" {
  type    = string
  default = ""
}

variable "ig_publish_state_table_name" {
  type    = string
  default = ""
}

variable "tf_lock_table_name" {
  type    = string
  default = ""
}

variable "enable_budget_alert" {
  type    = bool
  default = false
}

variable "budget_alert_email" {
  type    = string
  default = ""
}

variable "monthly_budget_limit_usd" {
  type    = number
  default = 40
}

variable "enable_core" {
  type    = bool
  default = true
}

variable "enable_demo" {
  type    = bool
  default = true
}

variable "demo_run_id" {
  type    = string
  default = "manual"
}

variable "demo_log_retention_days" {
  type    = number
  default = 7
}

variable "bucket_versioning_status_by_role" {
  type = map(string)
  default = {
    object_store = "Suspended"
    evidence     = "Enabled"
    quarantine   = "Suspended"
    archive      = "Enabled"
    tf_state     = "Enabled"
  }

  validation {
    condition = alltrue([
      for role in ["object_store", "evidence", "quarantine", "archive", "tf_state"] :
      contains(keys(var.bucket_versioning_status_by_role), role)
      ]) && alltrue([
      for status in values(var.bucket_versioning_status_by_role) :
      contains(["Enabled", "Suspended"], status)
    ])
    error_message = "bucket_versioning_status_by_role must include object_store,evidence,quarantine,archive,tf_state with values Enabled or Suspended."
  }
}
