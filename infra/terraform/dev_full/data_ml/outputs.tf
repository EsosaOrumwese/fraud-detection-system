output "role_sagemaker_execution_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "role_databricks_cross_account_access_arn" {
  value = aws_iam_role.databricks_cross_account_access.arn
}

output "ssm_databricks_workspace_url_path" {
  value = aws_ssm_parameter.databricks_workspace_url.name
}

output "ssm_databricks_token_path" {
  value = aws_ssm_parameter.databricks_token.name
}

output "ssm_mlflow_tracking_uri_path" {
  value = aws_ssm_parameter.mlflow_tracking_uri.name
}

output "ssm_sagemaker_model_exec_role_arn_path" {
  value = aws_ssm_parameter.sagemaker_model_exec_role_arn.name
}

output "data_ml_handle_materialization" {
  value = {
    ROLE_SAGEMAKER_EXECUTION             = aws_iam_role.sagemaker_execution.arn
    ROLE_DATABRICKS_CROSS_ACCOUNT_ACCESS = aws_iam_role.databricks_cross_account_access.arn
    SSM_DATABRICKS_WORKSPACE_URL_PATH    = aws_ssm_parameter.databricks_workspace_url.name
    SSM_DATABRICKS_TOKEN_PATH            = aws_ssm_parameter.databricks_token.name
    SSM_MLFLOW_TRACKING_URI_PATH         = aws_ssm_parameter.mlflow_tracking_uri.name
    SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN    = aws_ssm_parameter.sagemaker_model_exec_role_arn.name
  }
}
