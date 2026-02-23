output "role_mwaa_execution_arn" {
  value = aws_iam_role.mwaa_execution.arn
}

output "ssm_mwaa_webserver_url_path" {
  value = aws_ssm_parameter.mwaa_webserver_url.name
}

output "ssm_aurora_endpoint_path" {
  value = aws_ssm_parameter.aurora_endpoint.name
}

output "ssm_aurora_reader_endpoint_path" {
  value = aws_ssm_parameter.aurora_reader_endpoint.name
}

output "ssm_aurora_username_path" {
  value = aws_ssm_parameter.aurora_username.name
}

output "ssm_aurora_password_path" {
  value = aws_ssm_parameter.aurora_password.name
}

output "ssm_redis_endpoint_path" {
  value = aws_ssm_parameter.redis_endpoint.name
}

output "ops_handle_materialization" {
  value = {
    ROLE_MWAA_EXECUTION             = aws_iam_role.mwaa_execution.arn
    SSM_MWAA_WEBSERVER_URL_PATH     = aws_ssm_parameter.mwaa_webserver_url.name
    SSM_AURORA_ENDPOINT_PATH        = aws_ssm_parameter.aurora_endpoint.name
    SSM_AURORA_READER_ENDPOINT_PATH = aws_ssm_parameter.aurora_reader_endpoint.name
    SSM_AURORA_USERNAME_PATH        = aws_ssm_parameter.aurora_username.name
    SSM_AURORA_PASSWORD_PATH        = aws_ssm_parameter.aurora_password.name
    SSM_REDIS_ENDPOINT_PATH         = aws_ssm_parameter.redis_endpoint.name
  }
}
