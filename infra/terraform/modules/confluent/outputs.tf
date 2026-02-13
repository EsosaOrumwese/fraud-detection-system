output "environment_id" {
  value = confluent_environment.this.id
}

output "environment_name" {
  value = confluent_environment.this.display_name
}

output "kafka_cluster_id" {
  value = confluent_kafka_cluster.this.id
}

output "kafka_cluster_name" {
  value = confluent_kafka_cluster.this.display_name
}

output "kafka_cluster_rbac_crn" {
  value = confluent_kafka_cluster.this.rbac_crn
}

output "kafka_bootstrap_endpoint" {
  value = confluent_kafka_cluster.this.bootstrap_endpoint
}

output "kafka_rest_endpoint" {
  value = confluent_kafka_cluster.this.rest_endpoint
}

output "runtime_service_account_id" {
  value = confluent_service_account.runtime.id
}

output "runtime_kafka_api_key" {
  value = confluent_api_key.runtime_kafka_api_key.id
}

output "runtime_kafka_api_secret" {
  value     = confluent_api_key.runtime_kafka_api_key.secret
  sensitive = true
}

output "kafka_topics" {
  value = [for topic_name in confluent_kafka_topic.topics : topic_name.topic_name]
}
