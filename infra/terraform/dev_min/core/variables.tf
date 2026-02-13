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

variable "monthly_budget_usd" {
  type    = number
  default = 40
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

