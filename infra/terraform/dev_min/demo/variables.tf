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

variable "demo_run_id" {
  type    = string
  default = "manual"
}

variable "evidence_bucket_name" {
  type    = string
  default = "fraud-platform-dev-min-evidence"
}

variable "demo_log_retention_days" {
  type    = number
  default = 7
}

