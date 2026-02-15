output "log_group_name" {
  value = module.demo.log_group_name
}

output "manifest_key" {
  value = module.demo.manifest_key
}

output "topic_catalog_key" {
  value = module.demo.topic_catalog_key
}

output "heartbeat_parameter_name" {
  value = module.demo.heartbeat_parameter_name
}

output "confluent_env_name" {
  value = module.demo.confluent_env_name
}

output "confluent_cluster_name" {
  value = module.demo.confluent_cluster_name
}

output "kafka_topics" {
  value = module.demo.kafka_topics
}

output "ecs_cluster_name" {
  value = module.demo.ecs_cluster_name
}

output "ecs_task_execution_role_name" {
  value = module.demo.ecs_task_execution_role_name
}

output "ecs_task_role_name" {
  value = module.demo.ecs_task_role_name
}

output "role_ig_service_name" {
  value = module.demo.role_ig_service_name
}

output "role_rtdl_core_name" {
  value = module.demo.role_rtdl_core_name
}

output "role_decision_lane_name" {
  value = module.demo.role_decision_lane_name
}

output "role_case_labels_name" {
  value = module.demo.role_case_labels_name
}

output "role_env_conformance_name" {
  value = module.demo.role_env_conformance_name
}

output "ecs_probe_task_definition_arn" {
  value = module.demo.ecs_probe_task_definition_arn
}

output "ecs_db_migrations_task_definition_arn" {
  value = module.demo.ecs_db_migrations_task_definition_arn
}

output "td_db_migrations" {
  value = module.demo.ecs_db_migrations_task_definition_family
}

output "role_db_migrations_name" {
  value = module.demo.role_db_migrations_name
}

output "ecs_probe_service_name" {
  value = module.demo.ecs_probe_service_name
}

output "ecs_daemon_service_names" {
  value = module.demo.ecs_daemon_service_names
}

output "ecs_daemon_task_definition_arns" {
  value = module.demo.ecs_daemon_task_definition_arns
}

output "ecs_oracle_task_definition_arns" {
  value = module.demo.ecs_oracle_task_definition_arns
}

output "ecs_control_task_definition_arns" {
  value = module.demo.ecs_control_task_definition_arns
}

output "ecs_oracle_stream_sort_task_definition_arn" {
  value = module.demo.ecs_oracle_stream_sort_task_definition_arn
}

output "td_oracle_stream_sort" {
  value = module.demo.ecs_oracle_stream_sort_task_definition_family
}

output "ecs_oracle_checker_task_definition_arn" {
  value = module.demo.ecs_oracle_checker_task_definition_arn
}

output "td_oracle_checker" {
  value = module.demo.ecs_oracle_checker_task_definition_family
}

output "ecs_sr_task_definition_arn" {
  value = module.demo.ecs_sr_task_definition_arn
}

output "td_sr" {
  value = module.demo.ecs_sr_task_definition_family
}

output "ecs_wsp_task_definition_arn" {
  value = module.demo.ecs_wsp_task_definition_arn
}

output "td_wsp" {
  value = module.demo.ecs_wsp_task_definition_family
}

output "vpc_id" {
  value = module.demo.vpc_id
}

output "subnet_ids_public" {
  value = module.demo.subnet_ids_public
}

output "security_group_id_app" {
  value = module.demo.security_group_id_app
}

output "security_group_id_db" {
  value = module.demo.security_group_id_db
}

output "rds_instance_id" {
  value = module.demo.rds_instance_id
}

output "rds_endpoint" {
  value = module.demo.rds_endpoint
}

output "ssm_confluent_bootstrap_path" {
  value = module.demo.ssm_confluent_bootstrap_path
}

output "ssm_confluent_api_key_path" {
  value = module.demo.ssm_confluent_api_key_path
}

output "ssm_confluent_api_secret_path" {
  value = module.demo.ssm_confluent_api_secret_path
}

output "ssm_db_user_path" {
  value = module.demo.ssm_db_user_path
}

output "ssm_db_password_path" {
  value = module.demo.ssm_db_password_path
}

output "ssm_db_dsn_path" {
  value = module.demo.ssm_db_dsn_path
}

output "ssm_ig_api_key_path" {
  value = module.demo.ssm_ig_api_key_path
}
