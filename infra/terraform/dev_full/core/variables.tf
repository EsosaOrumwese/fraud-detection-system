variable "aws_region" {
  type    = string
  default = "eu-west-2"
}

variable "project" {
  type    = string
  default = "fraud-platform"
}

variable "environment" {
  type    = string
  default = "dev_full"
}

variable "owner" {
  type    = string
  default = "esosa"
}

variable "name_prefix" {
  type    = string
  default = "fraud-platform-dev-full"
}

variable "additional_tags" {
  type    = map(string)
  default = {}
}

variable "availability_zone_count" {
  type    = number
  default = 2

  validation {
    condition     = var.availability_zone_count >= 2
    error_message = "availability_zone_count must be at least 2 for dev_full core baseline."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.70.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.70.0.0/20", "10.70.16.0/20"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2
    error_message = "public_subnet_cidrs must provide at least two CIDRs."
  }
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.70.128.0/20", "10.70.144.0/20"]

  validation {
    condition     = length(var.private_subnet_cidrs) >= 2
    error_message = "private_subnet_cidrs must provide at least two CIDRs."
  }
}

variable "s3_object_store_bucket" {
  type    = string
  default = "fraud-platform-dev-full-object-store"
}

variable "s3_evidence_bucket" {
  type    = string
  default = "fraud-platform-dev-full-evidence"
}

variable "s3_artifacts_bucket" {
  type    = string
  default = "fraud-platform-dev-full-artifacts"
}

variable "s3_force_destroy" {
  type    = bool
  default = false
}

variable "kms_key_alias_platform" {
  type    = string
  default = "alias/fraud-platform-dev-full"
}

variable "role_eks_nodegroup_dev_full" {
  type    = string
  default = "fraud-platform-dev-full-eks-nodegroup"
}

variable "role_eks_runtime_platform_base" {
  type    = string
  default = "fraud-platform-dev-full-runtime-platform-base"
}

