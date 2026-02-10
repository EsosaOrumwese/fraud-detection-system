output "bucket_names" {
  value = {
    object_store = aws_s3_bucket.core["object_store"].bucket
    evidence     = aws_s3_bucket.core["evidence"].bucket
    quarantine   = aws_s3_bucket.core["quarantine"].bucket
    archive      = aws_s3_bucket.core["archive"].bucket
    tf_state     = aws_s3_bucket.core["tf_state"].bucket
  }
}

output "control_table_name" {
  value = aws_dynamodb_table.control_runs.name
}

output "tf_lock_table_name" {
  value = aws_dynamodb_table.tf_lock.name
}

output "budget_name" {
  value = length(aws_budgets_budget.dev_min_monthly) > 0 ? aws_budgets_budget.dev_min_monthly[0].name : ""
}
