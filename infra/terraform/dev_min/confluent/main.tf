provider "aws" {
  region = var.aws_region
}

provider "confluent" {
  cloud_api_key    = var.confluent_cloud_api_key
  cloud_api_secret = var.confluent_cloud_api_secret
}

locals {
  common_tags = {
    project    = var.project
    env        = var.environment
    owner      = var.owner
    expires_at = var.expires_at
  }

  topic_catalog_key = "dev_min/infra/confluent/${var.confluent_run_id}/topic_catalog.json"
}

module "confluent" {
  source = "../../modules/confluent"

  confluent_env_name                    = var.confluent_env_name
  confluent_cluster_name                = var.confluent_cluster_name
  confluent_cluster_type                = var.confluent_cluster_type
  confluent_cluster_availability        = var.confluent_cluster_availability
  confluent_cluster_cloud               = var.confluent_cluster_cloud
  confluent_cluster_region              = var.confluent_cluster_region
  kafka_topics                          = var.kafka_topics
  high_volume_topic_names               = var.high_volume_topic_names
  high_volume_partitions                = var.high_volume_partitions
  low_volume_partitions                 = var.low_volume_partitions
  high_volume_retention_ms              = var.high_volume_retention_ms
  low_volume_retention_ms               = var.low_volume_retention_ms
  topic_manager_service_account_name    = var.topic_manager_service_account_name
  runtime_service_account_name          = var.runtime_service_account_name
  operator_service_account_display_name = var.operator_service_account_display_name
}

resource "aws_ssm_parameter" "confluent_bootstrap" {
  name      = var.ssm_confluent_bootstrap_path
  type      = "SecureString"
  overwrite = true
  value     = module.confluent.kafka_bootstrap_endpoint

  tags = merge(local.common_tags, { fp_resource = "confluent_bootstrap" })
}

resource "aws_ssm_parameter" "confluent_api_key" {
  name      = var.ssm_confluent_api_key_path
  type      = "SecureString"
  overwrite = true
  value     = module.confluent.runtime_kafka_api_key

  tags = merge(local.common_tags, { fp_resource = "confluent_runtime_api_key" })
}

resource "aws_ssm_parameter" "confluent_api_secret" {
  name      = var.ssm_confluent_api_secret_path
  type      = "SecureString"
  overwrite = true
  value     = module.confluent.runtime_kafka_api_secret

  tags = merge(local.common_tags, { fp_resource = "confluent_runtime_api_secret" })
}

resource "aws_s3_object" "topic_catalog" {
  bucket       = var.evidence_bucket_name
  key          = local.topic_catalog_key
  content_type = "application/json"
  content = jsonencode({
    environment_name = module.confluent.environment_name
    environment_id   = module.confluent.environment_id
    cluster = {
      id           = module.confluent.kafka_cluster_id
      name         = module.confluent.kafka_cluster_name
      type         = var.confluent_cluster_type
      cloud        = var.confluent_cluster_cloud
      region       = var.confluent_cluster_region
      availability = var.confluent_cluster_availability
      bootstrap    = module.confluent.kafka_bootstrap_endpoint
      rest         = module.confluent.kafka_rest_endpoint
    }
    topics = module.confluent.kafka_topics
    ssm_paths = {
      bootstrap  = aws_ssm_parameter.confluent_bootstrap.name
      api_key    = aws_ssm_parameter.confluent_api_key.name
      api_secret = aws_ssm_parameter.confluent_api_secret.name
    }
  })

  tags = merge(local.common_tags, { fp_resource = "confluent_topic_catalog" })
}
