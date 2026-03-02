output "confluent_environment_id" {
  value = module.confluent.environment_id
}

output "confluent_environment_name" {
  value = module.confluent.environment_name
}

output "confluent_cluster_id" {
  value = module.confluent.kafka_cluster_id
}

output "confluent_cluster_name" {
  value = module.confluent.kafka_cluster_name
}

output "confluent_cluster_type" {
  value = var.confluent_cluster_type
}

output "confluent_cluster_cloud" {
  value = var.confluent_cluster_cloud
}

output "confluent_cluster_region" {
  value = var.confluent_cluster_region
}

output "kafka_bootstrap_endpoint" {
  value = module.confluent.kafka_bootstrap_endpoint
}

output "kafka_rest_endpoint" {
  value = module.confluent.kafka_rest_endpoint
}

output "runtime_service_account_id" {
  value = module.confluent.runtime_service_account_id
}

output "runtime_kafka_api_key" {
  value = module.confluent.runtime_kafka_api_key
}

output "runtime_kafka_api_secret" {
  value     = module.confluent.runtime_kafka_api_secret
  sensitive = true
}

output "kafka_topics" {
  value = module.confluent.kafka_topics
}

output "ssm_confluent_bootstrap_path" {
  value = aws_ssm_parameter.confluent_bootstrap.name
}

output "ssm_confluent_api_key_path" {
  value = aws_ssm_parameter.confluent_api_key.name
}

output "ssm_confluent_api_secret_path" {
  value = aws_ssm_parameter.confluent_api_secret.name
}

output "topic_catalog_key" {
  value = aws_s3_object.topic_catalog.key
}
