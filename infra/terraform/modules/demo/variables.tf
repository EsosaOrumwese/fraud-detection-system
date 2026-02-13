variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "demo_run_id" {
  type = string
}

variable "evidence_bucket" {
  type = string
}

variable "cloudwatch_retention" {
  type    = number
  default = 7
}

variable "common_tags" {
  type = map(string)
}
