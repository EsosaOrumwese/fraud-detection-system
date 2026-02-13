output "s3_bucket_names" {
  value = module.core.bucket_names
}

output "dynamodb_table_names" {
  value = {
    control_runs     = module.core.control_table_name
    ig_admission     = module.core.ig_admission_table_name
    ig_publish_state = module.core.ig_publish_state_table_name
    tf_lock          = module.core.tf_lock_table_name
  }
}

output "budget_name" {
  value = module.core.budget_name
}

