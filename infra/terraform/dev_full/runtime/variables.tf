variable "aws_region" {
  type    = string
  default = "eu-west-2"
}

variable "project" {
  type    = string
  default = "fraud-platform"
}

variable "environment" {
  type    = string
  default = "dev_full"
}

variable "owner" {
  type    = string
  default = "esosa"
}

variable "name_prefix" {
  type    = string
  default = "fraud-platform-dev-full"
}

variable "additional_tags" {
  type    = map(string)
  default = {}
}

variable "use_core_remote_state" {
  type    = bool
  default = true
}

variable "core_state_bucket" {
  type    = string
  default = "fraud-platform-dev-full-tfstate"
}

variable "core_state_key" {
  type    = string
  default = "dev_full/core/terraform.tfstate"
}

variable "core_state_region" {
  type    = string
  default = "eu-west-2"
}

variable "use_streaming_remote_state" {
  type    = bool
  default = true
}

variable "streaming_state_bucket" {
  type    = string
  default = "fraud-platform-dev-full-tfstate"
}

variable "streaming_state_key" {
  type    = string
  default = "dev_full/streaming/terraform.tfstate"
}

variable "streaming_state_region" {
  type    = string
  default = "eu-west-2"
}

variable "msk_cluster_arn_fallback" {
  type    = string
  default = "arn:aws:kafka:eu-west-2:230372904534:cluster/fraud-platform-dev-full-msk/a38adf23-ea5e-4c99-a4cd-109afb1530a8-s3"
}

variable "ssm_msk_bootstrap_brokers_path" {
  type    = string
  default = "/fraud-platform/dev_full/msk/bootstrap_brokers"
}

variable "role_flink_execution_name" {
  type    = string
  default = "fraud-platform-dev-full-flink-execution"
}

variable "role_lambda_ig_execution_name" {
  type    = string
  default = "fraud-platform-dev-full-lambda-ig-execution"
}

variable "role_apigw_ig_invoke_name" {
  type    = string
  default = "fraud-platform-dev-full-apigw-ig-invoke"
}

variable "role_ddb_ig_idempotency_rw_name" {
  type    = string
  default = "fraud-platform-dev-full-ddb-ig-idempotency-rw"
}

variable "role_step_functions_orchestrator_name" {
  type    = string
  default = "fraud-platform-dev-full-stepfunctions-orchestrator"
}

variable "apigw_ig_api_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-edge"
}

variable "apigw_ig_stage_name" {
  type    = string
  default = "v1"
}

variable "apigw_ig_stage_detailed_metrics_enabled" {
  type    = bool
  default = true
}

variable "apigw_ig_access_log_group_name" {
  type    = string
  default = "/aws/apigateway/fraud-platform-dev-full-ig-edge-v1-access"
}

variable "lambda_ig_handler_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-handler"
}

variable "ddb_ig_idempotency_table_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-idempotency"
}

variable "ddb_ig_idempotency_hash_key" {
  type    = string
  default = "dedupe_key"
}

variable "ddb_ig_idempotency_ttl_attribute" {
  type    = string
  default = "ttl_epoch"
}

variable "ssm_ig_api_key_path" {
  type    = string
  default = "/fraud-platform/dev_full/ig/api_key"
}

variable "ig_api_key_seed_value" {
  type      = string
  default   = "dev-full-ig-api-key-rotate-before-prod"
  sensitive = true
}

variable "ig_auth_mode" {
  type    = string
  default = "api_key"
}

variable "ig_auth_header_name" {
  type    = string
  default = "X-IG-Api-Key"
}

variable "ig_max_request_bytes" {
  type    = number
  default = 1048576
}

variable "ig_request_timeout_seconds" {
  type    = number
  default = 30
}

variable "ig_internal_retry_max_attempts" {
  type    = number
  default = 3
}

variable "ig_internal_retry_backoff_ms" {
  type    = number
  default = 250
}

variable "ig_idempotency_ttl_seconds" {
  type    = number
  default = 259200
}

variable "ig_dlq_mode" {
  type    = string
  default = "sqs"
}

variable "ig_dlq_queue_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-dlq"
}

variable "ig_replay_mode" {
  type    = string
  default = "dlq_replay_workflow"
}

variable "ig_rate_limit_rps" {
  type    = number
  default = 3000
}

variable "ig_rate_limit_burst" {
  type    = number
  default = 6000
}

variable "lambda_ig_memory_size_mb" {
  type    = number
  default = 2048
}

variable "lambda_ig_reserved_concurrency" {
  type    = number
  default = 600
}

variable "lambda_ig_timeout_seconds" {
  type    = number
  default = 30
}

variable "lambda_ig_kafka_request_timeout_ms" {
  type    = number
  default = 5000
}

variable "lambda_ig_receipt_storage_mode" {
  type    = string
  default = "ddb_hot"
}

variable "ig_kafka_publish_retries" {
  type    = number
  default = 5
}

variable "lambda_ig_policy_activation_audit_mode" {
  type    = string
  default = "store_only"
}

variable "lambda_ig_health_bus_probe_mode" {
  type    = string
  default = "none"
}

variable "lambda_ig_package_s3_bucket" {
  type    = string
  default = ""
}

variable "lambda_ig_package_s3_key" {
  type    = string
  default = ""
}

variable "lambda_ig_package_sha256_base64" {
  type    = string
  default = ""
}

variable "ig_service_enabled" {
  type    = bool
  default = false
}

variable "ig_service_cluster_name" {
  type    = string
  default = "fraud-platform-dev-full-ingress"
}

variable "ig_service_name" {
  type    = string
  default = "fraud-platform-dev-full-ig-service"
}

variable "ig_service_image_uri" {
  type    = string
  default = ""
}

variable "ig_service_container_port" {
  type    = number
  default = 8080
}

variable "ig_service_listener_port" {
  type    = number
  default = 80
}

variable "ig_service_task_cpu" {
  type    = number
  default = 4096
}

variable "ig_service_task_memory" {
  type    = number
  default = 8192
}

variable "ig_service_desired_count" {
  type    = number
  default = 32
}

variable "ig_service_gunicorn_workers" {
  type    = number
  default = 8
}

variable "ig_service_gunicorn_threads" {
  type    = number
  default = 8
}

variable "ig_service_request_timeout_ms" {
  type    = number
  default = 30000
}

variable "ig_service_gunicorn_keepalive_seconds" {
  type    = number
  default = 75
}

variable "ig_service_kafka_request_timeout_ms" {
  type    = number
  default = 15000
}

variable "ig_service_receipt_storage_mode" {
  type    = string
  default = "ddb_hot"
}

variable "ig_service_health_check_interval_seconds" {
  type    = number
  default = 30
}

variable "ig_service_health_check_timeout_seconds" {
  type    = number
  default = 10
}

variable "ig_service_health_check_healthy_threshold" {
  type    = number
  default = 2
}

variable "ig_service_health_check_unhealthy_threshold" {
  type    = number
  default = 5
}

variable "ig_service_health_check_start_period_seconds" {
  type    = number
  default = 60
}

variable "ig_service_health_check_grace_period_seconds" {
  type    = number
  default = 180
}

variable "ig_service_deployment_minimum_healthy_percent" {
  type    = number
  default = 50
}

variable "ig_service_deployment_maximum_percent" {
  type    = number
  default = 109
}

variable "ig_service_health_bus_probe_mode" {
  type    = string
  default = "none"
}

variable "ig_service_log_group_name" {
  type    = string
  default = "/ecs/fraud-platform-dev-full-ig-service"
}

variable "role_ecs_ig_task_execution_name" {
  type    = string
  default = "fraud-platform-dev-full-ecs-ig-task-execution"
}

variable "role_ecs_ig_task_runtime_name" {
  type    = string
  default = "fraud-platform-dev-full-ecs-ig-task-runtime"
}

variable "ssm_ig_service_url_path" {
  type    = string
  default = "/fraud-platform/dev_full/ig/service_url"
}

variable "sfn_platform_run_orchestrator_name" {
  type    = string
  default = "fraud-platform-dev-full-platform-run-v0"
}

variable "eks_cluster_name" {
  type    = string
  default = "fraud-platform-dev-full"
}

variable "eks_nodegroup_m6f_name" {
  type    = string
  default = "fraud-platform-dev-full-m6f-workers"
}

variable "eks_nodegroup_instance_types" {
  type    = list(string)
  default = ["m6i.xlarge"]
}

variable "eks_nodegroup_ami_type" {
  type    = string
  default = "BOTTLEROCKET_x86_64"
}

variable "eks_nodegroup_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "eks_nodegroup_disk_size" {
  type    = number
  default = 80
}

variable "eks_nodegroup_desired_size" {
  type    = number
  default = 4
}

variable "eks_nodegroup_min_size" {
  type    = number
  default = 2
}

variable "eks_nodegroup_max_size" {
  type    = number
  default = 8
}

variable "runtime_interface_vpc_endpoint_services" {
  type    = list(string)
  default = ["ec2", "ecr.api", "ecr.dkr", "execute-api", "logs", "sqs", "ssm", "sts"]
}

variable "eks_namespace_ingress" {
  type    = string
  default = "fraud-platform-ingress"
}

variable "eks_namespace_rtdl" {
  type    = string
  default = "fraud-platform-rtdl"
}

variable "eks_namespace_case_labels" {
  type    = string
  default = "fraud-platform-case-labels"
}

variable "eks_namespace_obs_gov" {
  type    = string
  default = "fraud-platform-obs-gov"
}

variable "irsa_service_account_ig" {
  type    = string
  default = "ig"
}

variable "irsa_service_account_rtdl" {
  type    = string
  default = "rtdl"
}

variable "irsa_service_account_decision_lane" {
  type    = string
  default = "decision-lane"
}

variable "irsa_service_account_case_labels" {
  type    = string
  default = "case-labels"
}

variable "irsa_service_account_obs_gov" {
  type    = string
  default = "obs-gov"
}

variable "role_eks_irsa_ig_name" {
  type    = string
  default = "fraud-platform-dev-full-irsa-ig"
}

variable "role_eks_irsa_rtdl_name" {
  type    = string
  default = "fraud-platform-dev-full-irsa-rtdl"
}

variable "role_eks_irsa_decision_lane_name" {
  type    = string
  default = "fraud-platform-dev-full-irsa-decision-lane"
}

variable "role_eks_irsa_case_labels_name" {
  type    = string
  default = "fraud-platform-dev-full-irsa-case-labels"
}

variable "role_eks_irsa_obs_gov_name" {
  type    = string
  default = "fraud-platform-dev-full-irsa-obs-gov"
}

variable "phase_runtime_path_mode" {
  type    = string
  default = "single_active_path_per_phase_run"
}

variable "phase_runtime_path_pin_required" {
  type    = bool
  default = true
}

variable "runtime_path_switch_in_phase_allowed" {
  type    = bool
  default = false
}

variable "runtime_fallback_requires_new_phase_execution_id" {
  type    = bool
  default = true
}

variable "phase_runtime_path_evidence_path_pattern" {
  type    = string
  default = "evidence/dev_full/run_control/{phase_execution_id}/runtime_path_selection.json"
}

variable "aurora_cluster_identifier" {
  type    = string
  default = "fraud-platform-dev-full-aurora"
}

variable "aurora_engine" {
  type    = string
  default = "aurora-postgresql"
}

variable "aurora_engine_version" {
  type    = string
  default = "16.6"
}

variable "aurora_database_name" {
  type    = string
  default = "fraud_platform"
}

variable "aurora_master_username" {
  type    = string
  default = "fp_runtime"
}

variable "aurora_port" {
  type    = number
  default = 5432
}

variable "aurora_serverless_min_capacity" {
  type    = number
  default = 0.5
}

variable "aurora_serverless_max_capacity" {
  type    = number
  default = 4
}

variable "aurora_backup_retention_period" {
  type    = number
  default = 7
}

variable "aurora_preferred_backup_window" {
  type    = string
  default = "03:00-04:00"
}

variable "aurora_preferred_maintenance_window" {
  type    = string
  default = "sun:04:00-sun:05:00"
}

variable "aurora_skip_final_snapshot" {
  type    = bool
  default = true
}

variable "aurora_deletion_protection" {
  type    = bool
  default = false
}

variable "aurora_apply_immediately" {
  type    = bool
  default = true
}

variable "aurora_writer_instance_identifier" {
  type    = string
  default = "fraud-platform-dev-full-aurora-writer-1"
}

variable "ssm_aurora_endpoint_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/endpoint"
}

variable "ssm_aurora_reader_endpoint_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/reader_endpoint"
}

variable "ssm_aurora_username_path" {
  type    = string
  default = "/fraud-platform/dev_full/aurora/username"
}

variable "ssm_aurora_password_path" {
  type      = string
  default   = "/fraud-platform/dev_full/aurora/password"
  sensitive = true
}
