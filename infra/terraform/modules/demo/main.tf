locals {
  tags_demo = merge(var.common_tags, {
    fp_phase = "phase2"
    fp_tier  = "demo"
  })

  manifest_key    = "dev_min/infra/demo/${var.demo_run_id}/manifest.json"
  heartbeat_param = "/fraud-platform/dev_min/demo/${var.demo_run_id}/heartbeat"
}

resource "aws_cloudwatch_log_group" "demo" {
  name              = "/fraud-platform/dev_min/demo/${var.demo_run_id}"
  retention_in_days = var.cloudwatch_retention
  tags              = merge(local.tags_demo, { fp_resource = "demo_log_group" })
}

resource "aws_s3_object" "manifest" {
  bucket       = var.evidence_bucket
  key          = local.manifest_key
  content_type = "application/json"
  content = jsonencode({
    environment = var.environment
    demo_run_id = var.demo_run_id
    created_by  = "terraform"
    fp_phase    = "phase2"
  })

  tags = merge(local.tags_demo, { fp_resource = "demo_manifest" })
}

resource "aws_ssm_parameter" "heartbeat" {
  name      = local.heartbeat_param
  type      = "String"
  overwrite = true
  value = jsonencode({
    demo_run_id = var.demo_run_id
    state       = "active"
  })

  tags = merge(local.tags_demo, { fp_resource = "demo_heartbeat" })
}
