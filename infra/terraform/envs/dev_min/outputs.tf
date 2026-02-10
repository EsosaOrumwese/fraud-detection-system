output "core" {
  value = var.enable_core ? {
    buckets = module.core[0].bucket_names
    tables = {
      control = module.core[0].control_table_name
      tf_lock = module.core[0].tf_lock_table_name
    }
    budget_name = module.core[0].budget_name
  } : null
}

output "demo" {
  value = var.enable_demo ? {
    log_group_name = module.demo[0].log_group_name
    manifest_key   = module.demo[0].manifest_key
    heartbeat_key  = module.demo[0].heartbeat_parameter_name
  } : null
}

output "phase2_state" {
  value = {
    environment = var.environment
    enable_core = var.enable_core
    enable_demo = var.enable_demo
    demo_run_id = var.demo_run_id
  }
}
