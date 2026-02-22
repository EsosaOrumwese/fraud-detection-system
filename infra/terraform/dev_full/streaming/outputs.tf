output "msk_cluster_arn" {
  value = aws_msk_serverless_cluster.streaming.arn
}

output "msk_cluster_name" {
  value = aws_msk_serverless_cluster.streaming.cluster_name
}

output "msk_bootstrap_brokers_sasl_iam" {
  value = data.aws_msk_bootstrap_brokers.streaming.bootstrap_brokers_sasl_iam
}

output "msk_client_subnet_ids" {
  value = local.msk_client_subnet_ids
}

output "msk_security_group_id" {
  value = local.msk_security_group_id
}

output "ssm_msk_bootstrap_brokers_path" {
  value = aws_ssm_parameter.msk_bootstrap_brokers.name
}

output "glue_schema_registry_name" {
  value = aws_glue_registry.streaming.registry_name
}

output "glue_schema_registry_arn" {
  value = aws_glue_registry.streaming.arn
}

output "glue_schema_compatibility_mode" {
  value = aws_glue_schema.anchor_control.compatibility
}

output "streaming_handle_materialization" {
  value = {
    MSK_CLUSTER_ARN                = aws_msk_serverless_cluster.streaming.arn
    MSK_BOOTSTRAP_BROKERS_SASL_IAM = data.aws_msk_bootstrap_brokers.streaming.bootstrap_brokers_sasl_iam
    MSK_CLIENT_SUBNET_IDS          = local.msk_client_subnet_ids
    MSK_SECURITY_GROUP_ID          = local.msk_security_group_id
    SSM_MSK_BOOTSTRAP_BROKERS_PATH = aws_ssm_parameter.msk_bootstrap_brokers.name
    GLUE_SCHEMA_REGISTRY_NAME      = aws_glue_registry.streaming.registry_name
    GLUE_SCHEMA_COMPATIBILITY_MODE = aws_glue_schema.anchor_control.compatibility
  }
}

