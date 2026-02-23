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

  databricks_trusted_principal_arn = trimspace(var.databricks_trusted_principal_arn) != "" ? trimspace(var.databricks_trusted_principal_arn) : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
}

data "aws_iam_policy_document" "assume_role_sagemaker" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_role_databricks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [local.databricks_trusted_principal_arn]
    }
  }
}

resource "aws_iam_role" "sagemaker_execution" {
  name               = var.role_sagemaker_execution_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_sagemaker.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "sagemaker_ssm_read" {
  name = "${var.role_sagemaker_execution_name}-ssm-read"
  role = aws_iam_role.sagemaker_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_sagemaker_model_exec_role_arn_path}",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_mlflow_tracking_uri_path}"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "databricks_cross_account_access" {
  name               = var.role_databricks_cross_account_access_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_databricks.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "databricks_ssm_read" {
  name = "${var.role_databricks_cross_account_access_name}-ssm-read"
  role = aws_iam_role.databricks_cross_account_access.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_databricks_workspace_url_path}",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_databricks_token_path}",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_mlflow_tracking_uri_path}"
        ]
      }
    ]
  })
}

resource "aws_ssm_parameter" "databricks_workspace_url" {
  name      = var.ssm_databricks_workspace_url_path
  type      = "String"
  value     = var.databricks_workspace_url_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "databricks_workspace_url"
  })
}

resource "aws_ssm_parameter" "databricks_token" {
  name      = var.ssm_databricks_token_path
  type      = "SecureString"
  value     = var.databricks_token_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "databricks_token"
  })
}

resource "aws_ssm_parameter" "mlflow_tracking_uri" {
  name      = var.ssm_mlflow_tracking_uri_path
  type      = "String"
  value     = var.mlflow_tracking_uri_seed
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "mlflow_tracking_uri"
  })
}

resource "aws_ssm_parameter" "sagemaker_model_exec_role_arn" {
  name      = var.ssm_sagemaker_model_exec_role_arn_path
  type      = "String"
  value     = aws_iam_role.sagemaker_execution.arn
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "sagemaker_model_exec_role_arn"
  })
}
