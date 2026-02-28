provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_iam_role" "github_actions" {
  name = var.github_actions_role_name
}

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

resource "aws_cloudwatch_log_group" "runtime_bootstrap" {
  name              = "${var.cloudwatch_log_group_prefix}/runtime-bootstrap"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    fp_resource = "runtime_bootstrap_log_group"
  })
}

resource "aws_iam_role_policy" "github_actions_m6f_remote" {
  name = var.github_actions_policy_m6f_name
  role = data.aws_iam_role.github_actions.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "M6fEKSDescribeNodegroup"
        Effect = "Allow"
        Action = [
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:UpdateNodegroupConfig",
          "eks:DescribeUpdate"
        ]
        Resource = "*"
      },
      {
        Sid    = "M6fEmrContainersControl"
        Effect = "Allow"
        Action = [
          "emr-containers:StartJobRun",
          "emr-containers:CancelJobRun",
          "emr-containers:ListJobRuns",
          "emr-containers:DescribeJobRun"
        ]
        Resource = "*"
      },
      {
        Sid    = "M6fPassEmrExecutionRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = var.github_actions_emr_execution_role_arn
      },
      {
        Sid    = "M6fIgIdempotencyScan"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.github_actions_ig_idempotency_table_name}"
      },
      {
        Sid    = "M6fArtifactsBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::${var.github_actions_artifacts_bucket}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "dev_substrate/m6",
              "dev_substrate/m6/*"
            ]
          }
        }
      },
      {
        Sid    = "M6fArtifactsObjectRW"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]
        Resource = "arn:aws:s3:::${var.github_actions_artifacts_bucket}/dev_substrate/m6/*"
      },
      {
        Sid    = "M6fEvidenceBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::${var.github_actions_evidence_bucket}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "evidence/dev_full/run_control",
              "evidence/dev_full/run_control/*",
              "evidence/runs",
              "evidence/runs/*"
            ]
          }
        }
      },
      {
        Sid    = "M6fEvidenceObjectRW"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]
        Resource = [
          "arn:aws:s3:::${var.github_actions_evidence_bucket}/evidence/dev_full/run_control/*",
          "arn:aws:s3:::${var.github_actions_evidence_bucket}/evidence/runs/*"
        ]
      },
      {
        Sid    = "M10fGlueCatalogReadWrite"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:CreateDatabase",
          "glue:GetTable",
          "glue:CreateTable",
          "glue:UpdateTable"
        ]
        Resource = [
          "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:catalog",
          "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:database/fraud_platform_dev_full_ofs",
          "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/fraud_platform_dev_full_ofs/*"
        ]
      },
      {
        Sid    = "M10fObjectStoreWarehouseList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::fraud-platform-dev-full-object-store"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "learning/ofs/iceberg/warehouse/*"
            ]
          }
        }
      },
      {
        Sid    = "M10fObjectStoreWarehouseObjectRW"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]
        Resource = "arn:aws:s3:::fraud-platform-dev-full-object-store/learning/ofs/iceberg/warehouse/*"
      },
      {
        Sid    = "M11bSageMakerReadinessControl"
        Effect = "Allow"
        Action = [
          "sagemaker:ListTrainingJobs",
          "sagemaker:ListModelPackageGroups",
          "sagemaker:DescribeModelPackageGroup",
          "sagemaker:CreateModelPackageGroup"
        ]
        Resource = "*"
      },
      {
        Sid    = "M11dSageMakerExecutionControl"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:CreateModel",
          "sagemaker:CreateTransformJob",
          "sagemaker:DescribeTransformJob",
          "sagemaker:ListEndpoints",
          "sagemaker:DescribeEndpoint",
          "sagemaker:DeleteEndpoint"
        ]
        Resource = "*"
      },
      {
        Sid    = "M11dPassSageMakerExecutionRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = var.github_actions_sagemaker_execution_role_arn
      },
      {
        Sid    = "M12dEKSDescribeCluster"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster"
        ]
        Resource = "*"
      },
      {
        Sid    = "M12dKafkaDataPlaneProof"
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup",
          "kafka-cluster:CreateTopic"
        ]
        Resource = "*"
      }
    ]
  })
}
