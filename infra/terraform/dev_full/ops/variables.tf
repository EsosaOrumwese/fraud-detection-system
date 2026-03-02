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

variable "additional_tags" {
  type    = map(string)
  default = {}
}

variable "role_mwaa_execution_name" {
  type    = string
  default = "fraud-platform-dev-full-mwaa-execution"
}

variable "ssm_mwaa_webserver_url_path" {
  type    = string
  default = "/fraud-platform/dev_full/mwaa/webserver_url"
}

variable "ssm_aurora_endpoint_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/endpoint"
}

variable "ssm_aurora_reader_endpoint_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/reader_endpoint"
}

variable "ssm_aurora_username_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/username"
}

variable "ssm_aurora_password_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/password"
}

variable "ssm_redis_endpoint_path" {
  type    = string
  default = "/fraud-platform/dev_full/redis/endpoint"
}

variable "mwaa_webserver_url_seed" {
  type    = string
  default = "https://fraud-platform-dev-full-mwaa.example.amazonaws.com"
}

variable "aurora_endpoint_seed" {
  type    = string
  default = "fraud-platform-dev-full-aurora.cluster.local"
}

variable "aurora_reader_endpoint_seed" {
  type    = string
  default = "fraud-platform-dev-full-aurora-ro.cluster.local"
}

variable "aurora_username_seed" {
  type    = string
  default = "fp_runtime"
}

variable "aurora_password_seed" {
  type      = string
  default   = "rotate-me-dev-full-aurora-password"
  sensitive = true
}

variable "redis_endpoint_seed" {
  type    = string
  default = "fraud-platform-dev-full-redis.cache.amazonaws.com:6379"
}

variable "cloudwatch_log_group_prefix" {
  type    = string
  default = "/fraud-platform/dev_full"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "github_actions_role_name" {
  type    = string
  default = "GitHubAction-AssumeRoleWithAction"
}

variable "github_actions_policy_m6f_name" {
  type    = string
  default = "GitHubActionsM6FRemoteDevFull"
}

variable "github_actions_emr_execution_role_arn" {
  type    = string
  default = "arn:aws:iam::230372904534:role/fraud-platform-dev-full-flink-execution"
}

variable "github_actions_sagemaker_execution_role_arn" {
  type    = string
  default = "arn:aws:iam::230372904534:role/fraud-platform-dev-full-sagemaker-execution"
}

variable "github_actions_ig_idempotency_table_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-idempotency"
}

variable "github_actions_artifacts_bucket" {
  type    = string
  default = "fraud-platform-dev-full-artifacts"
}

variable "github_actions_evidence_bucket" {
  type    = string
  default = "fraud-platform-dev-full-evidence"
}
