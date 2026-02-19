provider "aws" {
  region = var.aws_region
}

data "terraform_remote_state" "confluent" {
  count   = var.confluent_credentials_source == "remote_state" ? 1 : 0
  backend = "s3"

  config = {
    bucket = var.confluent_state_bucket
    key    = var.confluent_state_key
    region = var.confluent_state_region
  }
}

locals {
  common_tags = {
    project    = var.project
    env        = var.environment
    owner      = var.owner
    expires_at = var.expires_at
  }

  confluent_env_name_resolved       = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.confluent_environment_name : var.confluent_env_name
  confluent_cluster_name_resolved   = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.confluent_cluster_name : var.confluent_cluster_name
  confluent_cluster_type_resolved   = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.confluent_cluster_type : var.confluent_cluster_type
  confluent_cluster_cloud_resolved  = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.confluent_cluster_cloud : var.confluent_cluster_cloud
  confluent_cluster_region_resolved = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.confluent_cluster_region : var.confluent_cluster_region
  kafka_topics_resolved             = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.kafka_topics : var.kafka_topics
  confluent_bootstrap_resolved      = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.kafka_bootstrap_endpoint : var.confluent_bootstrap
  confluent_api_key_resolved        = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.runtime_kafka_api_key : var.confluent_api_key
  confluent_api_secret_resolved     = var.confluent_credentials_source == "remote_state" ? data.terraform_remote_state.confluent[0].outputs.runtime_kafka_api_secret : var.confluent_api_secret
}

module "demo" {
  source = "../../modules/demo"

  name_prefix                              = var.name_prefix
  environment                              = var.environment
  aws_region                               = var.aws_region
  demo_run_id                              = var.demo_run_id
  evidence_bucket                          = var.evidence_bucket_name
  object_store_bucket                      = var.object_store_bucket_name
  archive_bucket                           = var.archive_bucket_name
  cloudwatch_retention                     = var.demo_log_retention_days
  log_group_prefix                         = var.cloudwatch_log_group_prefix
  vpc_cidr                                 = var.vpc_cidr
  public_subnet_cidrs                      = var.public_subnet_cidrs
  ecs_cluster_name                         = var.ecs_cluster_name
  ecs_probe_container_image                = var.ecs_probe_container_image
  ecs_daemon_container_image               = var.ecs_daemon_container_image
  ecs_daemon_task_cpu                      = var.ecs_daemon_task_cpu
  ecs_daemon_task_memory                   = var.ecs_daemon_task_memory
  ecs_daemon_service_desired_count_default = var.ecs_daemon_service_desired_count_default
  required_platform_run_id_env_key         = var.required_platform_run_id_env_key
  required_platform_run_id                 = var.required_platform_run_id
  ig_ingest_url                            = var.ig_ingest_url
  rtdl_core_consumer_group_id              = var.rtdl_core_consumer_group_id
  rtdl_core_offset_commit_policy           = var.rtdl_core_offset_commit_policy
  confluent_env_name                       = local.confluent_env_name_resolved
  confluent_cluster_name                   = local.confluent_cluster_name_resolved
  confluent_cluster_type                   = local.confluent_cluster_type_resolved
  confluent_cluster_cloud                  = local.confluent_cluster_cloud_resolved
  confluent_cluster_region                 = local.confluent_cluster_region_resolved
  kafka_topics                             = local.kafka_topics_resolved
  confluent_bootstrap                      = local.confluent_bootstrap_resolved
  confluent_api_key                        = local.confluent_api_key_resolved
  confluent_api_secret                     = local.confluent_api_secret_resolved
  ssm_confluent_bootstrap_path             = var.ssm_confluent_bootstrap_path
  ssm_confluent_api_key_path               = var.ssm_confluent_api_key_path
  ssm_confluent_api_secret_path            = var.ssm_confluent_api_secret_path
  ig_api_key                               = var.ig_api_key
  ssm_ig_api_key_path                      = var.ssm_ig_api_key_path
  rds_instance_id                          = var.rds_instance_id
  db_name                                  = var.db_name
  db_username                              = var.db_username
  db_password                              = var.db_password
  db_engine_version                        = var.db_engine_version
  db_instance_class                        = var.db_instance_class
  db_allocated_storage                     = var.db_allocated_storage
  db_max_allocated_storage                 = var.db_max_allocated_storage
  db_port                                  = var.db_port
  db_publicly_accessible                   = var.db_publicly_accessible
  ssm_db_user_path                         = var.ssm_db_user_path
  ssm_db_password_path                     = var.ssm_db_password_path
  ssm_db_dsn_path                          = var.ssm_db_dsn_path
  write_db_dsn_parameter                   = var.write_db_dsn_parameter
  common_tags                              = local.common_tags
}
