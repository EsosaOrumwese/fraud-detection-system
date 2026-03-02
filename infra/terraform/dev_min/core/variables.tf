variable "aws_region" {
  type    = string
  default = "eu-west-2"
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
  default = "esosa"
}

variable "expires_at" {
  type    = string
  default = ""
}

variable "object_store_bucket_name" {
  type    = string
  default = ""
}

variable "evidence_bucket_name" {
  type    = string
  default = ""
}

variable "quarantine_bucket_name" {
  type    = string
  default = ""
}

variable "archive_bucket_name" {
  type    = string
  default = ""
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
  default = true
}

variable "budget_alert_email" {
  type    = string
  default = ""
}

variable "budget_name" {
  type    = string
  default = "fraud-platform-dev-min-budget"
}

variable "budget_limit_amount" {
  type    = number
  default = 30
}

variable "budget_limit_unit" {
  type    = string
  default = "USD"
}

variable "budget_alert_thresholds" {
  type    = list(number)
  default = [10, 20, 28]
}

variable "bucket_versioning_status_by_role" {
  type = map(string)
  default = {
    object_store = "Enabled"
    evidence     = "Enabled"
    quarantine   = "Enabled"
    archive      = "Enabled"
    tf_state     = "Enabled"
  }
}
