output "log_group_name" {
  value = aws_cloudwatch_log_group.demo.name
}

output "manifest_key" {
  value = aws_s3_object.manifest.key
}

output "heartbeat_parameter_name" {
  value = aws_ssm_parameter.heartbeat.name
}
