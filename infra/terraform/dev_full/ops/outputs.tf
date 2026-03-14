output "role_mwaa_execution_arn" {
  value = aws_iam_role.mwaa_execution.arn
}

output "ssm_mwaa_webserver_url_path" {
  value = aws_ssm_parameter.mwaa_webserver_url.name
}

output "ssm_aurora_endpoint_path" {
  value = var.ssm_aurora_endpoint_path
}

output "ssm_aurora_reader_endpoint_path" {
  value = var.ssm_aurora_reader_endpoint_path
}

output "ssm_aurora_username_path" {
  value = var.ssm_aurora_username_path
}

output "ssm_aurora_password_path" {
  value = var.ssm_aurora_password_path
}

output "ssm_redis_endpoint_path" {
  value = aws_ssm_parameter.redis_endpoint.name
}

output "cloudwatch_runtime_bootstrap_log_group" {
  value = aws_cloudwatch_log_group.runtime_bootstrap.name
}

output "github_actions_m6f_policy_name" {
  value = aws_iam_role_policy.github_actions_m6f_remote.name
}

output "budget_name" {
  value = length(aws_budgets_budget.dev_full_monthly) > 0 ? aws_budgets_budget.dev_full_monthly[0].name : null
}

output "cloudwatch_dashboard_platform_operations" {
  value = aws_cloudwatch_dashboard.platform_operations.dashboard_name
}

output "cloudwatch_dashboard_cost_guardrail" {
  value = aws_cloudwatch_dashboard.cost_guardrail.dashboard_name
}

output "ops_handle_materialization" {
  value = {
    ROLE_MWAA_EXECUTION              = aws_iam_role.mwaa_execution.arn
    SSM_MWAA_WEBSERVER_URL_PATH      = aws_ssm_parameter.mwaa_webserver_url.name
    SSM_AURORA_ENDPOINT_PATH         = var.ssm_aurora_endpoint_path
    SSM_AURORA_READER_ENDPOINT_PATH  = var.ssm_aurora_reader_endpoint_path
    SSM_AURORA_USERNAME_PATH         = var.ssm_aurora_username_path
    SSM_AURORA_PASSWORD_PATH         = var.ssm_aurora_password_path
    SSM_REDIS_ENDPOINT_PATH          = aws_ssm_parameter.redis_endpoint.name
    CLOUDWATCH_LOG_GROUP_PREFIX      = var.cloudwatch_log_group_prefix
    CLOUDWATCH_RUNTIME_BOOTSTRAP_LG  = aws_cloudwatch_log_group.runtime_bootstrap.name
    AWS_BUDGET_NAME                  = length(aws_budgets_budget.dev_full_monthly) > 0 ? aws_budgets_budget.dev_full_monthly[0].name : null
    CW_DASHBOARD_PLATFORM_OPERATIONS = aws_cloudwatch_dashboard.platform_operations.dashboard_name
    CW_DASHBOARD_COST_GUARDRAIL      = aws_cloudwatch_dashboard.cost_guardrail.dashboard_name
    ROLE_GITHUB_ACTIONS_OIDC         = data.aws_iam_role.github_actions.arn
    ROLE_GITHUB_ACTIONS_M6F_POLICY   = aws_iam_role_policy.github_actions_m6f_remote.name
  }
}
