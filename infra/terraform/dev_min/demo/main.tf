provider "aws" {
  region = var.aws_region
}

locals {
  common_tags = {
    project    = var.project
    env        = var.environment
    owner      = var.owner
    expires_at = var.expires_at
  }
}

module "demo" {
  source = "../../modules/demo"

  name_prefix                   = var.name_prefix
  environment                   = var.environment
  aws_region                    = var.aws_region
  demo_run_id                   = var.demo_run_id
  evidence_bucket               = var.evidence_bucket_name
  cloudwatch_retention          = var.demo_log_retention_days
  log_group_prefix              = var.cloudwatch_log_group_prefix
  vpc_cidr                      = var.vpc_cidr
  public_subnet_cidrs           = var.public_subnet_cidrs
  ecs_cluster_name              = var.ecs_cluster_name
  ecs_probe_container_image     = var.ecs_probe_container_image
  confluent_env_name            = var.confluent_env_name
  confluent_cluster_name        = var.confluent_cluster_name
  confluent_cluster_type        = var.confluent_cluster_type
  confluent_cluster_cloud       = var.confluent_cluster_cloud
  confluent_cluster_region      = var.confluent_cluster_region
  kafka_topics                  = var.kafka_topics
  confluent_bootstrap           = var.confluent_bootstrap
  confluent_api_key             = var.confluent_api_key
  confluent_api_secret          = var.confluent_api_secret
  ssm_confluent_bootstrap_path  = var.ssm_confluent_bootstrap_path
  ssm_confluent_api_key_path    = var.ssm_confluent_api_key_path
  ssm_confluent_api_secret_path = var.ssm_confluent_api_secret_path
  ig_api_key                    = var.ig_api_key
  ssm_ig_api_key_path           = var.ssm_ig_api_key_path
  rds_instance_id               = var.rds_instance_id
  db_name                       = var.db_name
  db_username                   = var.db_username
  db_password                   = var.db_password
  db_engine_version             = var.db_engine_version
  db_instance_class             = var.db_instance_class
  db_allocated_storage          = var.db_allocated_storage
  db_max_allocated_storage      = var.db_max_allocated_storage
  db_port                       = var.db_port
  db_publicly_accessible        = var.db_publicly_accessible
  ssm_db_user_path              = var.ssm_db_user_path
  ssm_db_password_path          = var.ssm_db_password_path
  ssm_db_dsn_path               = var.ssm_db_dsn_path
  write_db_dsn_parameter        = var.write_db_dsn_parameter
  common_tags                   = local.common_tags
}
