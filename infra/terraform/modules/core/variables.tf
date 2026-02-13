variable "name_prefix" {
  type = string
}

variable "object_store_bucket" {
  type = string
}

variable "evidence_bucket" {
  type = string
}

variable "quarantine_bucket" {
  type = string
}

variable "archive_bucket" {
  type = string
}

variable "tf_state_bucket" {
  type = string
}

variable "control_table_name" {
  type = string
}

variable "ig_admission_table_name" {
  type = string
}

variable "ig_publish_state_table_name" {
  type = string
}

variable "tf_lock_table_name" {
  type = string
}

variable "enable_budget_alert" {
  type    = bool
  default = false
}

variable "budget_alert_email" {
  type    = string
  default = ""
}

variable "budget_name" {
  type    = string
  default = ""
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

  validation {
    condition     = length(var.budget_alert_thresholds) > 0
    error_message = "budget_alert_thresholds must include at least one threshold value."
  }
}

variable "common_tags" {
  type = map(string)
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
