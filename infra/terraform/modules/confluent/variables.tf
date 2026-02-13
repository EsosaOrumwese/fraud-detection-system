variable "confluent_env_name" {
  type = string
}

variable "confluent_cluster_name" {
  type = string
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
  type = string
}

variable "kafka_topics" {
  type = list(string)
}

variable "high_volume_topic_names" {
  type = list(string)
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

variable "operator_service_account_display_name" {
  type    = string
  default = "fraud_detection_dev"
}
