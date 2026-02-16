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

variable "object_store_bucket_name" {
  type    = string
  default = "fraud-platform-dev-min-object-store"
}

variable "demo_log_retention_days" {
  type    = number
  default = 7
}

variable "cloudwatch_log_group_prefix" {
  type    = string
  default = "/fraud-platform/dev_min"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.0.0/24", "10.42.1.0/24"]
}

variable "ecs_cluster_name" {
  type    = string
  default = "fraud-platform-dev-min"
}

variable "ecs_probe_container_image" {
  type    = string
  default = "public.ecr.aws/docker/library/busybox:1.36"
}

variable "ecs_daemon_container_image" {
  type    = string
  default = ""
}

variable "ecs_daemon_task_cpu" {
  type    = string
  default = "256"
}

variable "ecs_daemon_task_memory" {
  type    = string
  default = "512"
}

variable "required_platform_run_id_env_key" {
  type    = string
  default = "REQUIRED_PLATFORM_RUN_ID"
}

variable "required_platform_run_id" {
  type = string
}

variable "confluent_credentials_source" {
  type    = string
  default = "remote_state"

  validation {
    condition     = contains(["remote_state", "manual"], var.confluent_credentials_source)
    error_message = "confluent_credentials_source must be remote_state or manual."
  }
}

variable "confluent_state_bucket" {
  type    = string
  default = "fraud-platform-dev-min-tfstate"
}

variable "confluent_state_key" {
  type    = string
  default = "dev_min/confluent/terraform.tfstate"
}

variable "confluent_state_region" {
  type    = string
  default = "eu-west-2"
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

variable "confluent_bootstrap" {
  type    = string
  default = "REPLACE_ME_BOOTSTRAP"
}

variable "confluent_api_key" {
  type      = string
  default   = "REPLACE_ME_API_KEY"
  sensitive = true
}

variable "confluent_api_secret" {
  type      = string
  default   = "REPLACE_ME_API_SECRET"
  sensitive = true
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

variable "ig_api_key" {
  type      = string
  default   = "REPLACE_ME_IG_API_KEY"
  sensitive = true
}

variable "ssm_ig_api_key_path" {
  type    = string
  default = "/fraud-platform/dev_min/ig/api_key"
}

variable "rds_instance_id" {
  type    = string
  default = "fraud-platform-dev-min-db"
}

variable "db_name" {
  type    = string
  default = "fraud_platform"
}

variable "db_username" {
  type    = string
  default = "fp_app"
}

variable "db_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "db_engine_version" {
  type    = string
  default = "16.12"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_max_allocated_storage" {
  type    = number
  default = 50
}

variable "db_port" {
  type    = number
  default = 5432
}

variable "db_publicly_accessible" {
  type    = bool
  default = true
}

variable "ssm_db_user_path" {
  type    = string
  default = "/fraud-platform/dev_min/db/user"
}

variable "ssm_db_password_path" {
  type    = string
  default = "/fraud-platform/dev_min/db/password"
}

variable "ssm_db_dsn_path" {
  type    = string
  default = "/fraud-platform/dev_min/db/dsn"
}

variable "write_db_dsn_parameter" {
  type    = bool
  default = true
}
