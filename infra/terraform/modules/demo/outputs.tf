output "log_group_name" {
  value = aws_cloudwatch_log_group.demo.name
}

output "manifest_key" {
  value = aws_s3_object.manifest.key
}

output "topic_catalog_key" {
  value = aws_s3_object.confluent_topic_catalog.key
}

output "heartbeat_parameter_name" {
  value = aws_ssm_parameter.heartbeat.name
}

output "confluent_env_name" {
  value = var.confluent_env_name
}

output "confluent_cluster_name" {
  value = var.confluent_cluster_name
}

output "kafka_topics" {
  value = var.kafka_topics
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.demo.name
}

output "ecs_task_execution_role_name" {
  value = aws_iam_role.ecs_task_execution.name
}

output "ecs_task_role_name" {
  value = aws_iam_role.ecs_task_app.name
}

output "role_ig_service_name" {
  value = aws_iam_role.lane_app_roles["ig_service"].name
}

output "role_rtdl_core_name" {
  value = aws_iam_role.lane_app_roles["rtdl_core"].name
}

output "role_decision_lane_name" {
  value = aws_iam_role.lane_app_roles["decision_lane"].name
}

output "role_case_labels_name" {
  value = aws_iam_role.lane_app_roles["case_labels"].name
}

output "role_env_conformance_name" {
  value = aws_iam_role.lane_app_roles["env_conformance"].name
}

output "ecs_probe_task_definition_arn" {
  value = aws_ecs_task_definition.runtime_probe.arn
}

output "ecs_db_migrations_task_definition_arn" {
  value = aws_ecs_task_definition.db_migrations.arn
}

output "ecs_db_migrations_task_definition_family" {
  value = aws_ecs_task_definition.db_migrations.family
}

output "ecs_probe_service_name" {
  value = aws_ecs_service.runtime_probe.name
}

output "ecs_daemon_service_names" {
  value = { for key, svc in aws_ecs_service.daemon : key => svc.name }
}

output "ecs_daemon_task_definition_arns" {
  value = { for key, td in aws_ecs_task_definition.daemon : key => td.arn }
}

output "ecs_oracle_task_definition_arns" {
  value = { for key, td in aws_ecs_task_definition.oracle_job : key => td.arn }
}

output "ecs_control_task_definition_arns" {
  value = { for key, td in aws_ecs_task_definition.control_job : key => td.arn }
}

output "ecs_oracle_stream_sort_task_definition_arn" {
  value = aws_ecs_task_definition.oracle_job["oracle-stream-sort"].arn
}

output "ecs_oracle_stream_sort_task_definition_family" {
  value = aws_ecs_task_definition.oracle_job["oracle-stream-sort"].family
}

output "ecs_oracle_checker_task_definition_arn" {
  value = aws_ecs_task_definition.oracle_job["oracle-checker"].arn
}

output "ecs_oracle_checker_task_definition_family" {
  value = aws_ecs_task_definition.oracle_job["oracle-checker"].family
}

output "ecs_sr_task_definition_arn" {
  value = aws_ecs_task_definition.control_job["sr"].arn
}

output "ecs_sr_task_definition_family" {
  value = aws_ecs_task_definition.control_job["sr"].family
}

output "ecs_wsp_task_definition_arn" {
  value = aws_ecs_task_definition.control_job["wsp"].arn
}

output "ecs_wsp_task_definition_family" {
  value = aws_ecs_task_definition.control_job["wsp"].family
}

output "vpc_id" {
  value = aws_vpc.demo.id
}

output "subnet_ids_public" {
  value = [for subnet in aws_subnet.public : subnet.id]
}

output "security_group_id_app" {
  value = aws_security_group.app.id
}

output "security_group_id_db" {
  value = aws_security_group.db.id
}

output "rds_instance_id" {
  value = aws_db_instance.runtime.identifier
}

output "rds_endpoint" {
  value = aws_db_instance.runtime.address
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

output "ssm_db_user_path" {
  value = aws_ssm_parameter.db_user.name
}

output "ssm_db_password_path" {
  value = aws_ssm_parameter.db_password.name
}

output "ssm_db_dsn_path" {
  value = try(aws_ssm_parameter.db_dsn.name, null)
}

output "ssm_ig_api_key_path" {
  value = aws_ssm_parameter.ig_api_key.name
}

output "role_db_migrations_name" {
  value = aws_iam_role.ecs_task_app.name
}
