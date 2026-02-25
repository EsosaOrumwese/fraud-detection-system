output "apigw_ig_api_id" {
  value = aws_apigatewayv2_api.ig_edge.id
}

output "apigw_ig_api_endpoint" {
  value = aws_apigatewayv2_api.ig_edge.api_endpoint
}

output "lambda_ig_handler_name" {
  value = aws_lambda_function.ig_handler.function_name
}

output "lambda_ig_handler_arn" {
  value = aws_lambda_function.ig_handler.arn
}

output "ddb_ig_idempotency_table" {
  value = aws_dynamodb_table.ig_idempotency.name
}

output "ddb_ig_idempotency_table_arn" {
  value = aws_dynamodb_table.ig_idempotency.arn
}

output "ssm_ig_api_key_path" {
  value = aws_ssm_parameter.ig_api_key.name
}

output "sfn_platform_run_orchestrator_arn" {
  value = aws_sfn_state_machine.platform_run_orchestrator.arn
}

output "sfn_platform_run_orchestrator_name" {
  value = aws_sfn_state_machine.platform_run_orchestrator.name
}

output "eks_cluster_arn" {
  value = aws_eks_cluster.platform.arn
}

output "role_flink_execution_arn" {
  value = aws_iam_role.flink_execution.arn
}

output "role_lambda_ig_execution_arn" {
  value = aws_iam_role.lambda_ig_execution.arn
}

output "role_apigw_ig_invoke_arn" {
  value = aws_iam_role.apigw_ig_invoke.arn
}

output "role_ddb_ig_idempotency_rw_arn" {
  value = aws_iam_role.ddb_ig_idempotency_rw.arn
}

output "role_step_functions_orchestrator_arn" {
  value = aws_iam_role.step_functions_orchestrator.arn
}

output "role_eks_irsa_ig_arn" {
  value = aws_iam_role.eks_irsa["ig"].arn
}

output "role_eks_irsa_rtdl_arn" {
  value = aws_iam_role.eks_irsa["rtdl"].arn
}

output "role_eks_irsa_decision_lane_arn" {
  value = aws_iam_role.eks_irsa["decision_lane"].arn
}

output "role_eks_irsa_case_labels_arn" {
  value = aws_iam_role.eks_irsa["case_labels"].arn
}

output "role_eks_irsa_obs_gov_arn" {
  value = aws_iam_role.eks_irsa["obs_gov"].arn
}

output "runtime_path_governance_contract" {
  value = {
    PHASE_RUNTIME_PATH_MODE                          = var.phase_runtime_path_mode
    PHASE_RUNTIME_PATH_PIN_REQUIRED                  = var.phase_runtime_path_pin_required
    RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED             = var.runtime_path_switch_in_phase_allowed
    RUNTIME_FALLBACK_REQUIRES_NEW_PHASE_EXECUTION_ID = var.runtime_fallback_requires_new_phase_execution_id
    PHASE_RUNTIME_PATH_EVIDENCE_PATH_PATTERN         = var.phase_runtime_path_evidence_path_pattern
  }
}

output "runtime_handle_materialization" {
  value = {
    APIGW_IG_API_ID                    = aws_apigatewayv2_api.ig_edge.id
    LAMBDA_IG_HANDLER_NAME             = aws_lambda_function.ig_handler.function_name
    DDB_IG_IDEMPOTENCY_TABLE           = aws_dynamodb_table.ig_idempotency.name
    ROLE_FLINK_EXECUTION               = aws_iam_role.flink_execution.arn
    ROLE_LAMBDA_IG_EXECUTION           = aws_iam_role.lambda_ig_execution.arn
    ROLE_APIGW_IG_INVOKE               = aws_iam_role.apigw_ig_invoke.arn
    ROLE_DDB_IG_IDEMPOTENCY_RW         = aws_iam_role.ddb_ig_idempotency_rw.arn
    ROLE_STEP_FUNCTIONS_ORCHESTRATOR   = aws_iam_role.step_functions_orchestrator.arn
    ROLE_EKS_IRSA_IG                   = aws_iam_role.eks_irsa["ig"].arn
    ROLE_EKS_IRSA_RTDL                 = aws_iam_role.eks_irsa["rtdl"].arn
    ROLE_EKS_IRSA_DECISION_LANE        = aws_iam_role.eks_irsa["decision_lane"].arn
    ROLE_EKS_IRSA_CASE_LABELS          = aws_iam_role.eks_irsa["case_labels"].arn
    ROLE_EKS_IRSA_OBS_GOV              = aws_iam_role.eks_irsa["obs_gov"].arn
    EKS_CLUSTER_ARN                    = aws_eks_cluster.platform.arn
    SFN_PLATFORM_RUN_ORCHESTRATOR_V0   = aws_sfn_state_machine.platform_run_orchestrator.name
    SR_READY_COMMIT_AUTHORITY          = "step_functions_only"
    SSM_IG_API_KEY_PATH                = aws_ssm_parameter.ig_api_key.name
    IG_AUTH_MODE                       = var.ig_auth_mode
    IG_AUTH_HEADER_NAME                = var.ig_auth_header_name
    PHASE_RUNTIME_PATH_MODE            = var.phase_runtime_path_mode
    PHASE_RUNTIME_PATH_EVIDENCE_TARGET = var.phase_runtime_path_evidence_path_pattern
  }
}
