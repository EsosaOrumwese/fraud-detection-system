output "bucket_names" {
  value = {
    for role, fallback_name in local.bucket_names :
    role => try(aws_s3_bucket.core[role].bucket, fallback_name)
  }
}

output "control_table_name" {
  value = aws_dynamodb_table.control_runs.name
}

output "ig_admission_table_name" {
  value = aws_dynamodb_table.ig_admission_state.name
}

output "ig_publish_state_table_name" {
  value = aws_dynamodb_table.ig_publish_state.name
}

output "tf_lock_table_name" {
  value = aws_dynamodb_table.tf_lock.name
}

output "budget_name" {
  value = length(aws_budgets_budget.dev_min_monthly) > 0 ? aws_budgets_budget.dev_min_monthly[0].name : ""
}
