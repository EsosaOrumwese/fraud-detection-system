locals {
  bucket_names = {
    object_store = var.object_store_bucket
    evidence     = var.evidence_bucket
    quarantine   = var.quarantine_bucket
    archive      = var.archive_bucket
    tf_state     = var.tf_state_bucket
  }

  bucket_versioning_defaults = {
    object_store = "Enabled"
    evidence     = "Enabled"
    quarantine   = "Enabled"
    archive      = "Enabled"
    tf_state     = "Enabled"
  }
  bucket_versioning_status_by_role = merge(
    local.bucket_versioning_defaults,
    var.bucket_versioning_status_by_role,
  )

  tags_core = merge(var.common_tags, {
    fp_phase = "phase2"
    fp_tier  = "core"
  })
}

resource "aws_s3_bucket" "core" {
  for_each = local.bucket_names

  bucket = each.value
  tags   = merge(local.tags_core, { fp_bucket_role = each.key })
}

resource "aws_s3_bucket_public_access_block" "core" {
  for_each = local.bucket_names

  bucket                  = aws_s3_bucket.core[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "core" {
  for_each = local.bucket_names

  bucket = aws_s3_bucket.core[each.key].id
  versioning_configuration {
    status = lookup(local.bucket_versioning_status_by_role, each.key, "Enabled")
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "core" {
  for_each = local.bucket_names

  bucket = aws_s3_bucket.core[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "control_runs" {
  name         = var.control_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "platform_run_id"

  attribute {
    name = "platform_run_id"
    type = "S"
  }

  tags = merge(local.tags_core, { fp_table_role = "control_runs" })
}

resource "aws_dynamodb_table" "ig_admission_state" {
  name         = var.ig_admission_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = merge(local.tags_core, { fp_table_role = "ig_admission_state" })
}

resource "aws_dynamodb_table" "ig_publish_state" {
  name         = var.ig_publish_state_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = merge(local.tags_core, { fp_table_role = "ig_publish_state" })
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = var.tf_lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = merge(local.tags_core, { fp_table_role = "tf_lock" })
}

resource "aws_budgets_budget" "dev_min_monthly" {
  count = var.enable_budget_alert && trimspace(var.budget_alert_email) != "" ? 1 : 0

  name         = "${var.name_prefix}-monthly-cost"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["project$${var.common_tags[\"project\"]}"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
