variable "aws_region" {
  description = "AWS region for sandbox"
  type        = string
  default     = "eu-west-2"
}

variable "aws_profile" {
  description = "Named profile in ~/.aws/credentials"
  type        = string
  default     = "fraud-dev"
}

variable "owner" {
  description = "Tag for resource ownership / cost explorer"
  type        = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "bucket_prefix" {
  description = "Prefix for S3 buckets"
  type        = string
  default     = "fraud"
}