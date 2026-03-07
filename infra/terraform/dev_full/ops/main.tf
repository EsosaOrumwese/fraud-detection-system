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

resource "aws_iam_policy" "github_actions_pr3_runtime" {
  name = "GitHubActionsPR3RuntimeDevFull"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PR3ArtifactsBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::${var.github_actions_artifacts_bucket}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "artifacts/lambda/ig_handler",
              "artifacts/lambda/ig_handler/*"
            ]
          }
        }
      },
      {
        Sid    = "PR3ArtifactsObjectRW"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]
        Resource = "arn:aws:s3:::${var.github_actions_artifacts_bucket}/artifacts/lambda/ig_handler/*"
      },
      {
        Sid    = "PR3TfStateBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::fraud-platform-dev-full-tfstate"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "dev_full/core/terraform.tfstate",
              "dev_full/streaming/terraform.tfstate",
              "dev_full/runtime/terraform.tfstate"
            ]
          }
        }
      },
      {
        Sid    = "PR3TfStateRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "arn:aws:s3:::fraud-platform-dev-full-tfstate/dev_full/core/terraform.tfstate",
          "arn:aws:s3:::fraud-platform-dev-full-tfstate/dev_full/streaming/terraform.tfstate",
          "arn:aws:s3:::fraud-platform-dev-full-tfstate/dev_full/runtime/terraform.tfstate"
        ]
      },
      {
        Sid    = "PR3TfStateWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::fraud-platform-dev-full-tfstate/dev_full/runtime/terraform.tfstate"
      },
      {
        Sid    = "PR3TfLockControl"
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/fraud-platform-dev-full-tf-locks"
      },
      {
        Sid    = "PR3IngressReadRefresh"
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTimeToLive",
          "dynamodb:ListTagsOfResource",
          "sqs:GetQueueAttributes",
          "sqs:ListQueueTags"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/fraud-platform-dev-full-ig-idempotency",
          "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:fraud-platform-dev-full-ig-dlq"
        ]
      },
      {
        Sid    = "PR3IngressLambdaControl"
        Effect = "Allow"
        Action = [
          "lambda:Get*",
          "lambda:ListVersionsByFunction",
          "lambda:CreateFunction",
          "lambda:Update*",
          "lambda:PutFunctionConcurrency",
          "lambda:DeleteFunctionConcurrency",
          "lambda:TagResource",
          "lambda:UntagResource"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:fraud-platform-dev-full-ig-handler"
      },
      {
        Sid    = "PR3IngressLambdaRoleControl"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:PassRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:PutRolePolicy",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies"
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/fraud-platform-dev-full-lambda-ig-execution"
      },
      {
        Sid    = "PR3IngressNetworkControl"
        Effect = "Allow"
        Action = [
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:CreateTags",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets"
        ]
        Resource = "*"
      },
      {
        Sid    = "PR3IngressVerifyRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/fraud-platform/dev_full/ig/api_key",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/fraud-platform/dev_full/msk/bootstrap_brokers"
        ]
      },
      {
        Sid    = "PR3IngressApigwStageControl"
        Effect = "Allow"
        Action = [
          "apigateway:GET",
          "apigateway:PATCH"
        ]
        Resource = [
          "arn:aws:apigateway:${var.aws_region}::/apis/ehwznd2uw7",
          "arn:aws:apigateway:${var.aws_region}::/apis/ehwznd2uw7/*"
        ]
      },
      {
        Sid    = "PR3RuntimeStepFunctionsRead"
        Effect = "Allow"
        Action = [
          "states:DescribeStateMachine"
        ]
        Resource = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:fraud-platform-dev-full-platform-run-v0"
      },
      {
        Sid    = "PR3RuntimeEksOidcRead"
        Effect = "Allow"
        Action = [
          "iam:GetOpenIDConnectProvider"
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/oidc.eks.${var.aws_region}.amazonaws.com/id/6D0DBB7743A87C0ACB0A4645B431D308"
      },
      {
        Sid    = "PR3RuntimeEksNodegroupControl"
        Effect = "Allow"
        Action = [
          "eks:CreateNodegroup",
          "eks:DeleteNodegroup",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:UpdateNodegroupConfig",
          "eks:UpdateNodegroupVersion",
          "eks:DescribeUpdate",
          "eks:ListUpdates",
          "eks:TagResource",
          "eks:UntagResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "PR3RuntimeEksNodegroupPassRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole",
          "iam:GetRole"
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/fraud-platform-dev-full-eks-nodegroup"
      },
      {
        Sid    = "PR3ManagedFlinkRead"
        Effect = "Allow"
        Action = [
          "kinesisanalytics:ListApplications",
          "kinesisanalytics:DescribeApplication"
        ]
        Resource = "*"
      },
      {
        Sid    = "PR3CloudWatchMetricsRead"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "PR3ServiceQuotasRead"
        Effect = "Allow"
        Action = [
          "servicequotas:ListServiceQuotas",
          "servicequotas:GetServiceQuota"
        ]
        Resource = "*"
      },
      {
        Sid    = "PR3ElbRuntimeRead"
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:Describe*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_actions_pr3_runtime" {
  role       = data.aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_pr3_runtime.arn
}
