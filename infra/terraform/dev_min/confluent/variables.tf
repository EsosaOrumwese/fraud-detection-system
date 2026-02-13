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

variable "confluent_run_id" {
  type    = string
  default = "manual"
}

variable "evidence_bucket_name" {
  type    = string
  default = "fraud-platform-dev-min-evidence"
}

variable "confluent_cloud_api_key" {
  type      = string
  sensitive = true
}

variable "confluent_cloud_api_secret" {
  type      = string
  sensitive = true
}

variable "confluent_env_name" {
  type    = string
  default = "dev_min"
}

variable "confluent_cluster_name" {
  type    = string
  default = "dev-min-kafka"
}

variable "confluent_cluster_type" {
  type    = string
  default = "Basic"

  validation {
    condition     = contains(["Basic", "Standard"], var.confluent_cluster_type)
    error_message = "confluent_cluster_type must be Basic or Standard."
  }
}

variable "confluent_cluster_availability" {
  type    = string
  default = "SINGLE_ZONE"
}

variable "confluent_cluster_cloud" {
  type    = string
  default = "AWS"
}

variable "confluent_cluster_region" {
  type    = string
  default = "eu-west-2"
}

variable "kafka_topics" {
  type = list(string)
  default = [
    "fp.bus.control.v1",
    "fp.bus.traffic.fraud.v1",
    "fp.bus.context.arrival_events.v1",
    "fp.bus.context.arrival_entities.v1",
    "fp.bus.context.flow_anchor.fraud.v1",
    "fp.bus.rtdl.v1",
    "fp.bus.audit.v1",
    "fp.bus.case.triggers.v1",
    "fp.bus.labels.events.v1",
  ]
}

variable "high_volume_topic_names" {
  type = list(string)
  default = [
    "fp.bus.traffic.fraud.v1",
    "fp.bus.context.arrival_events.v1",
    "fp.bus.context.arrival_entities.v1",
    "fp.bus.context.flow_anchor.fraud.v1",
    "fp.bus.rtdl.v1",
  ]
}

variable "high_volume_partitions" {
  type    = number
  default = 3
}

variable "low_volume_partitions" {
  type    = number
  default = 1
}

variable "high_volume_retention_ms" {
  type    = number
  default = 86400000
}

variable "low_volume_retention_ms" {
  type    = number
  default = 259200000
}

variable "topic_manager_service_account_name" {
  type    = string
  default = "fp-dev-min-topic-manager"
}

variable "runtime_service_account_name" {
  type    = string
  default = "fp-dev-min-runtime"
}

variable "ssm_confluent_bootstrap_path" {
  type    = string
  default = "/fraud-platform/dev_min/confluent/bootstrap"
}

variable "ssm_confluent_api_key_path" {
  type    = string
  default = "/fraud-platform/dev_min/confluent/api_key"
}

variable "ssm_confluent_api_secret_path" {
  type    = string
  default = "/fraud-platform/dev_min/confluent/api_secret"
}
