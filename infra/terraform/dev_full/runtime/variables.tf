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
  default = 200
}

variable "ig_rate_limit_burst" {
  type    = number
  default = 400
}

variable "sfn_platform_run_orchestrator_name" {
  type    = string
  default = "fraud-platform-dev-full-platform-run-v0"
}

variable "eks_cluster_name" {
  type    = string
  default = "fraud-platform-dev-full"
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
