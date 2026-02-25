provider "aws" {
  region = var.aws_region
}

data "terraform_remote_state" "core" {
  count   = var.use_core_remote_state ? 1 : 0
  backend = "s3"

  config = {
    bucket = var.core_state_bucket
    key    = var.core_state_key
    region = var.core_state_region
  }
}

data "terraform_remote_state" "streaming" {
  count   = var.use_streaming_remote_state ? 1 : 0
  backend = "s3"

  config = {
    bucket = var.streaming_state_bucket
    key    = var.streaming_state_key
    region = var.streaming_state_region
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "archive_file" "ig_handler_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/ig_handler.py"
  output_path = "${path.module}/.terraform/ig_handler.zip"
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

  private_subnet_ids = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.private_subnet_ids, []) : []
  vpc_id             = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.vpc_id, "") : ""
  msk_security_group = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.msk_security_group_id, "") : ""

  role_eks_runtime_platform_base_arn = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.role_eks_runtime_platform_base_arn, "") : ""
  role_eks_nodegroup_dev_full_arn    = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.role_eks_nodegroup_dev_full_arn, "") : ""

  msk_cluster_arn           = var.use_streaming_remote_state ? try(data.terraform_remote_state.streaming[0].outputs.msk_cluster_arn, var.msk_cluster_arn_fallback) : var.msk_cluster_arn_fallback
  ig_integration_timeout_ms = min(30000, floor(var.ig_request_timeout_seconds * 1000))

  irsa_targets = {
    ig = {
      role_name       = var.role_eks_irsa_ig_name
      namespace       = var.eks_namespace_ingress
      service_account = var.irsa_service_account_ig
    }
    rtdl = {
      role_name       = var.role_eks_irsa_rtdl_name
      namespace       = var.eks_namespace_rtdl
      service_account = var.irsa_service_account_rtdl
    }
    decision_lane = {
      role_name       = var.role_eks_irsa_decision_lane_name
      namespace       = var.eks_namespace_rtdl
      service_account = var.irsa_service_account_decision_lane
    }
    case_labels = {
      role_name       = var.role_eks_irsa_case_labels_name
      namespace       = var.eks_namespace_case_labels
      service_account = var.irsa_service_account_case_labels
    }
    obs_gov = {
      role_name       = var.role_eks_irsa_obs_gov_name
      namespace       = var.eks_namespace_obs_gov
      service_account = var.irsa_service_account_obs_gov
    }
  }
}

data "aws_iam_policy_document" "assume_role_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_role_apigw" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_role_step_functions" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_role_flink" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["kinesisanalytics.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "flink_execution" {
  name               = var.role_flink_execution_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_flink.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "flink_execution" {
  name = "${var.role_flink_execution_name}-policy"
  role = aws_iam_role.flink_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:AlterGroup"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_msk_bootstrap_brokers_path}"
      }
    ]
  })
}

resource "aws_iam_role" "lambda_ig_execution" {
  name               = var.role_lambda_ig_execution_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_lambda.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_ig_basic" {
  role       = aws_iam_role.lambda_ig_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ig_runtime" {
  name = "${var.role_lambda_ig_execution_name}-runtime-policy"
  role = aws_iam_role.lambda_ig_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.ig_idempotency.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_ig_api_key_path}"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.ig_dlq.arn
      }
    ]
  })
}

resource "aws_iam_role" "apigw_ig_invoke" {
  name               = var.role_apigw_ig_invoke_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_apigw.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "apigw_ig_invoke" {
  name = "${var.role_apigw_ig_invoke_name}-policy"
  role = aws_iam_role.apigw_ig_invoke.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.ig_handler.arn
      }
    ]
  })
}

resource "aws_iam_role" "ddb_ig_idempotency_rw" {
  name               = var.role_ddb_ig_idempotency_rw_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_lambda.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "ddb_ig_idempotency_rw" {
  name = "${var.role_ddb_ig_idempotency_rw_name}-policy"
  role = aws_iam_role.ddb_ig_idempotency_rw.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.ig_idempotency.arn
      }
    ]
  })
}

resource "aws_iam_role" "step_functions_orchestrator" {
  name               = var.role_step_functions_orchestrator_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_step_functions.json
  tags               = local.common_tags
}

resource "aws_dynamodb_table" "ig_idempotency" {
  name         = var.ddb_ig_idempotency_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = var.ddb_ig_idempotency_hash_key

  attribute {
    name = var.ddb_ig_idempotency_hash_key
    type = "S"
  }

  ttl {
    attribute_name = var.ddb_ig_idempotency_ttl_attribute
    enabled        = true
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_idempotency_table"
  })
}

resource "aws_ssm_parameter" "ig_api_key" {
  name      = var.ssm_ig_api_key_path
  type      = "SecureString"
  value     = var.ig_api_key_seed_value
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "ig_api_key"
  })
}

resource "aws_sqs_queue" "ig_dlq" {
  name = var.ig_dlq_queue_name

  tags = merge(local.common_tags, {
    fp_resource = "ig_dlq"
  })
}

resource "aws_lambda_function" "ig_handler" {
  function_name    = var.lambda_ig_handler_name
  role             = aws_iam_role.lambda_ig_execution.arn
  runtime          = "python3.12"
  handler          = "ig_handler.lambda_handler"
  filename         = data.archive_file.ig_handler_zip.output_path
  source_code_hash = data.archive_file.ig_handler_zip.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      IG_IDEMPOTENCY_TABLE           = aws_dynamodb_table.ig_idempotency.name
      IG_HASH_KEY                    = var.ddb_ig_idempotency_hash_key
      IG_TTL_ATTRIBUTE               = var.ddb_ig_idempotency_ttl_attribute
      IG_API_KEY_PATH                = aws_ssm_parameter.ig_api_key.name
      IG_AUTH_MODE                   = var.ig_auth_mode
      IG_AUTH_HEADER_NAME            = var.ig_auth_header_name
      IG_MAX_REQUEST_BYTES           = tostring(var.ig_max_request_bytes)
      IG_REQUEST_TIMEOUT_SECONDS     = tostring(var.ig_request_timeout_seconds)
      IG_INTERNAL_RETRY_MAX_ATTEMPTS = tostring(var.ig_internal_retry_max_attempts)
      IG_INTERNAL_RETRY_BACKOFF_MS   = tostring(var.ig_internal_retry_backoff_ms)
      IG_IDEMPOTENCY_TTL_SECONDS     = tostring(var.ig_idempotency_ttl_seconds)
      IG_DLQ_MODE                    = var.ig_dlq_mode
      IG_DLQ_QUEUE_NAME              = var.ig_dlq_queue_name
      IG_DLQ_URL                     = aws_sqs_queue.ig_dlq.url
      IG_REPLAY_MODE                 = var.ig_replay_mode
      IG_RATE_LIMIT_RPS              = tostring(var.ig_rate_limit_rps)
      IG_RATE_LIMIT_BURST            = tostring(var.ig_rate_limit_burst)
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_ig_basic,
    aws_iam_role_policy.lambda_ig_runtime
  ]

  tags = merge(local.common_tags, {
    fp_resource = "ig_lambda_handler"
  })
}

resource "aws_apigatewayv2_api" "ig_edge" {
  name          = var.apigw_ig_api_name
  protocol_type = "HTTP"

  tags = merge(local.common_tags, {
    fp_resource = "ig_api_edge"
  })
}

resource "aws_apigatewayv2_integration" "ig_lambda" {
  api_id                 = aws_apigatewayv2_api.ig_edge.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ig_handler.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = local.ig_integration_timeout_ms
  credentials_arn        = aws_iam_role.apigw_ig_invoke.arn
}

resource "aws_apigatewayv2_route" "ig_ingest_push" {
  api_id    = aws_apigatewayv2_api.ig_edge.id
  route_key = "POST /ingest/push"
  target    = "integrations/${aws_apigatewayv2_integration.ig_lambda.id}"
}

resource "aws_apigatewayv2_route" "ig_health" {
  api_id    = aws_apigatewayv2_api.ig_edge.id
  route_key = "GET /ops/health"
  target    = "integrations/${aws_apigatewayv2_integration.ig_lambda.id}"
}

resource "aws_apigatewayv2_stage" "ig_v1" {
  api_id      = aws_apigatewayv2_api.ig_edge.id
  name        = var.apigw_ig_stage_name
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = floor(var.ig_rate_limit_burst)
    throttling_rate_limit  = var.ig_rate_limit_rps
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_api_stage"
  })
}

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowExecutionFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ig_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ig_edge.execution_arn}/*/*"
}

resource "aws_sfn_state_machine" "platform_run_orchestrator" {
  name     = var.sfn_platform_run_orchestrator_name
  role_arn = aws_iam_role.step_functions_orchestrator.arn

  definition = jsonencode({
    StartAt = "RuntimeReadyCommit"
    States = {
      RuntimeReadyCommit = {
        Type = "Pass"
        Result = {
          commit_authority = "step_functions_only"
          phase            = "P5"
        }
        End = true
      }
    }
  })

  tags = merge(local.common_tags, {
    fp_resource = "platform_run_orchestrator"
  })
}

resource "aws_eks_cluster" "platform" {
  name     = var.eks_cluster_name
  role_arn = local.role_eks_runtime_platform_base_arn

  vpc_config {
    subnet_ids              = local.private_subnet_ids
    security_group_ids      = local.msk_security_group == "" ? [] : [local.msk_security_group]
    endpoint_public_access  = true
    endpoint_private_access = true
  }

  lifecycle {
    precondition {
      condition     = trimspace(local.role_eks_runtime_platform_base_arn) != ""
      error_message = "ROLE_EKS_RUNTIME_PLATFORM_BASE is missing from core outputs. M2.B must be applied before M2.E."
    }
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "EKS cluster requires at least two private subnets from core outputs."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "eks_cluster"
  })
}

data "tls_certificate" "eks_oidc" {
  url = aws_eks_cluster.platform.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.platform.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_oidc.certificates[0].sha1_fingerprint]

  tags = merge(local.common_tags, {
    fp_resource = "eks_oidc_provider"
  })
}

data "aws_iam_policy_document" "assume_role_irsa" {
  for_each = local.irsa_targets

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.platform.identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.platform.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:${each.value.namespace}:${each.value.service_account}"]
    }
  }
}

resource "aws_iam_role" "eks_irsa" {
  for_each = local.irsa_targets

  name               = each.value.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_irsa[each.key].json
  tags = merge(local.common_tags, {
    fp_resource = "eks_irsa_${each.key}"
  })
}

resource "aws_iam_role_policy" "eks_irsa_ssm_read" {
  for_each = local.irsa_targets

  name = "${each.value.role_name}-ssm-read"
  role = aws_iam_role.eks_irsa[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/fraud-platform/dev_full/*"
      }
    ]
  })
}
