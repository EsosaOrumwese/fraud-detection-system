###############################################################################
# Input variables (+ sane defaults)
###############################################################################

variable "aws_region" {
  type        = string
  description = "AWS region to deploy sandbox into"
  default     = "eu-west-2" # London (cheap & near you)
}

variable "environment" {
  type        = string
  description = "Deployment stage (sandbox, dev, prod, ...)"
  default     = "sandbox"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR range for the sandbox VPC"
  default     = "10.10.0.0/16"
}

#  S3 bucket names must be globally unique, so we let the caller pass any
#  string (GH username, random suffix, etc.) that makes collisions unlikely.
variable "bucket_suffix" {
  type        = string
  description = "Unique suffix to avoid global S3 name clashes"
  default     = "esosaorumz808"
}

## variables for alerts and budgets
variable "alert_email" {
  description = "Primary recipient for budget / billing alerts"
  type        = string
}

variable "monthly_budget_gbp" {
  description = "Cost ceiling for the sandbox environment (GBP)"
  type        = number
  default     = 40 # sprint charter says £40/mo
}