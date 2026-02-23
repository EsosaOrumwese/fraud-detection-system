provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  common_tags = merge(
    {
      project = var.project
      env     = var.environment
      owner   = var.owner
    },
    var.additional_tags
  )
}

data "aws_iam_policy_document" "assume_role_mwaa" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = [
        "airflow.amazonaws.com",
        "airflow-env.amazonaws.com"
      ]
    }
  }
}

resource "aws_iam_role" "mwaa_execution" {
  name               = var.role_mwaa_execution_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_mwaa.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "mwaa_ssm_read" {
  name = "${var.role_mwaa_execution_name}-ssm-read"
  role = aws_iam_role.mwaa_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_mwaa_webserver_url_path}"
        ]
      }
    ]
  })
}

resource "aws_ssm_parameter" "mwaa_webserver_url" {
  name      = var.ssm_mwaa_webserver_url_path
  type      = "String"
  value     = var.mwaa_webserver_url_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "mwaa_webserver_url"
  })
}

resource "aws_ssm_parameter" "aurora_endpoint" {
  name      = var.ssm_aurora_endpoint_path
  type      = "String"
  value     = var.aurora_endpoint_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "aurora_endpoint"
  })
}

resource "aws_ssm_parameter" "aurora_reader_endpoint" {
  name      = var.ssm_aurora_reader_endpoint_path
  type      = "String"
  value     = var.aurora_reader_endpoint_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "aurora_reader_endpoint"
  })
}

resource "aws_ssm_parameter" "aurora_username" {
  name      = var.ssm_aurora_username_path
  type      = "String"
  value     = var.aurora_username_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "aurora_username"
  })
}

resource "aws_ssm_parameter" "aurora_password" {
  name      = var.ssm_aurora_password_path
  type      = "SecureString"
  value     = var.aurora_password_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "aurora_password"
  })
}

resource "aws_ssm_parameter" "redis_endpoint" {
  name      = var.ssm_redis_endpoint_path
  type      = "String"
  value     = var.redis_endpoint_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "redis_endpoint"
  })
}
