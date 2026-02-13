resource "confluent_environment" "this" {
  display_name = var.confluent_env_name
}

data "confluent_organization" "this" {}

resource "confluent_kafka_cluster" "this" {
  display_name = var.confluent_cluster_name
  availability = var.confluent_cluster_availability
  cloud        = var.confluent_cluster_cloud
  region       = var.confluent_cluster_region

  dynamic "basic" {
    for_each = var.confluent_cluster_type == "Basic" ? [1] : []
    content {}
  }

  dynamic "standard" {
    for_each = var.confluent_cluster_type == "Standard" ? [1] : []
    content {}
  }

  environment {
    id = confluent_environment.this.id
  }
}

locals {
  supports_resource_roles = var.confluent_cluster_type != "Basic"
  environment_crn         = "crn://confluent.cloud/organization=${data.confluent_organization.this.id}/environment=${confluent_environment.this.id}"
  high_volume_topics      = toset(var.high_volume_topic_names)
  topic_profile = {
    for topic_name in var.kafka_topics :
    topic_name => (contains(local.high_volume_topics, topic_name) ? "high" : "low")
  }
}

resource "confluent_service_account" "topic_manager" {
  display_name = var.topic_manager_service_account_name
  description  = "Service account that manages topic lifecycle for dev_min spine."
}

resource "confluent_role_binding" "topic_manager_cluster_admin" {
  count = local.supports_resource_roles ? 1 : 0

  principal   = "User:${confluent_service_account.topic_manager.id}"
  role_name   = "CloudClusterAdmin"
  crn_pattern = confluent_kafka_cluster.this.rbac_crn
}

resource "confluent_role_binding" "topic_manager_environment_admin" {
  count = local.supports_resource_roles ? 0 : 1

  principal   = "User:${confluent_service_account.topic_manager.id}"
  role_name   = "EnvironmentAdmin"
  crn_pattern = local.environment_crn
}

resource "confluent_api_key" "topic_manager_kafka_api_key" {
  display_name = "${var.topic_manager_service_account_name}-kafka-api-key"
  description  = "Kafka API key for topic manager service account."

  owner {
    id          = confluent_service_account.topic_manager.id
    api_version = confluent_service_account.topic_manager.api_version
    kind        = confluent_service_account.topic_manager.kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.this.id
    api_version = confluent_kafka_cluster.this.api_version
    kind        = confluent_kafka_cluster.this.kind
    environment {
      id = confluent_environment.this.id
    }
  }

  depends_on = [
    confluent_role_binding.topic_manager_cluster_admin,
    confluent_role_binding.topic_manager_environment_admin,
  ]
}

resource "confluent_kafka_topic" "topics" {
  for_each = toset(var.kafka_topics)

  kafka_cluster {
    id = confluent_kafka_cluster.this.id
  }

  topic_name       = each.value
  rest_endpoint    = confluent_kafka_cluster.this.rest_endpoint
  partitions_count = local.topic_profile[each.value] == "high" ? var.high_volume_partitions : var.low_volume_partitions
  config = {
    "cleanup.policy" = "delete"
    "retention.ms"   = tostring(local.topic_profile[each.value] == "high" ? var.high_volume_retention_ms : var.low_volume_retention_ms)
  }

  credentials {
    key    = confluent_api_key.topic_manager_kafka_api_key.id
    secret = confluent_api_key.topic_manager_kafka_api_key.secret
  }
}

resource "confluent_service_account" "runtime" {
  display_name = var.runtime_service_account_name
  description  = "Runtime service account for dev_min platform Kafka access."
}

resource "confluent_role_binding" "runtime_read_topic" {
  for_each = local.supports_resource_roles ? toset(var.kafka_topics) : toset([])

  principal   = "User:${confluent_service_account.runtime.id}"
  role_name   = "DeveloperRead"
  crn_pattern = "${confluent_kafka_cluster.this.rbac_crn}/kafka=${confluent_kafka_cluster.this.id}/topic=${each.value}"
}

resource "confluent_role_binding" "runtime_write_topic" {
  for_each = local.supports_resource_roles ? toset(var.kafka_topics) : toset([])

  principal   = "User:${confluent_service_account.runtime.id}"
  role_name   = "DeveloperWrite"
  crn_pattern = "${confluent_kafka_cluster.this.rbac_crn}/kafka=${confluent_kafka_cluster.this.id}/topic=${each.value}"
}

resource "confluent_role_binding" "runtime_environment_admin" {
  count = local.supports_resource_roles ? 0 : 1

  principal   = "User:${confluent_service_account.runtime.id}"
  role_name   = "EnvironmentAdmin"
  crn_pattern = local.environment_crn
}

resource "confluent_api_key" "runtime_kafka_api_key" {
  display_name = "${var.runtime_service_account_name}-kafka-api-key"
  description  = "Kafka API key for runtime service account."

  owner {
    id          = confluent_service_account.runtime.id
    api_version = confluent_service_account.runtime.api_version
    kind        = confluent_service_account.runtime.kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.this.id
    api_version = confluent_kafka_cluster.this.api_version
    kind        = confluent_kafka_cluster.this.kind
    environment {
      id = confluent_environment.this.id
    }
  }

  depends_on = [
    confluent_role_binding.runtime_read_topic,
    confluent_role_binding.runtime_write_topic,
    confluent_role_binding.runtime_environment_admin,
  ]
}
