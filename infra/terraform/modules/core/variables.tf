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

variable "monthly_budget_usd" {
  type    = number
  default = 40
}

variable "common_tags" {
  type = map(string)
}
