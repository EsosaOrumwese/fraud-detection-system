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
  public_subnet_ids  = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.public_subnet_ids, []) : []
  vpc_id             = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.vpc_id, "") : ""
  msk_security_group = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.msk_security_group_id, "") : ""
  private_subnet_cidrs = [
    for subnet in data.aws_subnet.private :
    subnet.cidr_block
  ]
  public_subnet_cidrs = [
    for subnet in data.aws_subnet.public :
    subnet.cidr_block
  ]
  runtime_endpoint_client_cidrs = distinct(concat(local.private_subnet_cidrs, local.public_subnet_cidrs))
  private_route_table_ids = distinct([
    for route_table in data.aws_route_table.private_by_subnet :
    route_table.id
  ])

  role_eks_runtime_platform_base_arn = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.role_eks_runtime_platform_base_arn, "") : ""
  role_eks_nodegroup_dev_full_arn    = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.role_eks_nodegroup_dev_full_arn, "") : ""
  core_object_store_bucket           = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.s3_bucket_names.object_store, "fraud-platform-dev-full-object-store") : "fraud-platform-dev-full-object-store"
  core_evidence_bucket               = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.s3_bucket_names.evidence, "fraud-platform-dev-full-evidence") : "fraud-platform-dev-full-evidence"
  core_artifacts_bucket              = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.s3_bucket_names.artifacts, "fraud-platform-dev-full-artifacts") : "fraud-platform-dev-full-artifacts"
  core_kms_key_arn                   = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.kms_key_arn, "") : ""

  msk_cluster_arn              = var.use_streaming_remote_state ? try(data.terraform_remote_state.streaming[0].outputs.msk_cluster_arn, var.msk_cluster_arn_fallback) : var.msk_cluster_arn_fallback
  msk_cluster_suffix           = try(split("cluster/", local.msk_cluster_arn)[1], "")
  msk_cluster_name             = try(split("/", local.msk_cluster_suffix)[0], "")
  msk_cluster_uuid             = try(split("/", local.msk_cluster_suffix)[1], "")
  msk_topic_wildcard_arn       = local.msk_cluster_name != "" && local.msk_cluster_uuid != "" ? "arn:aws:kafka:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/${local.msk_cluster_name}/${local.msk_cluster_uuid}/*" : ""
  msk_group_wildcard_arn       = local.msk_cluster_name != "" && local.msk_cluster_uuid != "" ? "arn:aws:kafka:${var.aws_region}:${data.aws_caller_identity.current.account_id}:group/${local.msk_cluster_name}/${local.msk_cluster_uuid}/*" : ""
  ig_integration_timeout_ms    = min(30000, floor(var.ig_request_timeout_seconds * 1000))
  lambda_ig_use_remote_package = trimspace(var.lambda_ig_package_s3_bucket) != "" && trimspace(var.lambda_ig_package_s3_key) != "" && trimspace(var.lambda_ig_package_sha256_base64) != ""
  lambda_ig_source_code_hash   = local.lambda_ig_use_remote_package ? var.lambda_ig_package_sha256_base64 : data.archive_file.ig_handler_zip.output_base64sha256

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
  irsa_targets_with_msk = local.msk_cluster_arn != "" && local.msk_topic_wildcard_arn != "" && local.msk_group_wildcard_arn != "" ? {
    for key, value in local.irsa_targets :
    key => value if contains(["rtdl", "decision_lane"], key)
  } : {}
}

data "aws_subnet" "private" {
  for_each = toset(local.private_subnet_ids)
  id       = each.value
}

data "aws_subnet" "public" {
  for_each = toset(local.public_subnet_ids)
  id       = each.value
}

data "aws_route_table" "private_by_subnet" {
  for_each  = toset(local.private_subnet_ids)
  subnet_id = each.value
}

resource "aws_security_group" "runtime_endpoints" {
  name        = "${var.name_prefix}-runtime-endpoints-sg"
  description = "Private interface endpoint ingress for runtime worker bootstrap lanes"
  vpc_id      = local.vpc_id

  ingress {
    description = "TLS from runtime worker subnets"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = local.runtime_endpoint_client_cidrs
  }

  egress {
    description = "Permit endpoint egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    precondition {
      condition     = trimspace(local.vpc_id) != ""
      error_message = "VPC id is missing from core outputs. M2.B must be applied before runtime endpoint materialization."
    }
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "Runtime endpoint materialization requires at least two private subnets."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "runtime_endpoints_sg"
  })
}

resource "aws_vpc_endpoint" "runtime_interface" {
  for_each = toset(var.runtime_interface_vpc_endpoint_services)

  vpc_id              = local.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = each.value == "execute-api" ? false : true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.runtime_endpoints.id]

  lifecycle {
    precondition {
      condition     = trimspace(local.vpc_id) != ""
      error_message = "VPC id is missing from core outputs. M2.B must be applied before runtime endpoint materialization."
    }
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "Runtime endpoint materialization requires at least two private subnets."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "runtime_endpoint_${replace(each.value, ".", "_")}"
  })
}

resource "aws_vpc_endpoint" "runtime_s3_gateway" {
  vpc_id            = local.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = local.private_route_table_ids

  lifecycle {
    precondition {
      condition     = trimspace(local.vpc_id) != ""
      error_message = "VPC id is missing from core outputs. M2.B must be applied before runtime endpoint materialization."
    }
    precondition {
      condition     = length(local.private_route_table_ids) > 0
      error_message = "No private route table associations resolved from core private subnets."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "runtime_endpoint_s3_gateway"
  })
}

resource "aws_vpc_endpoint" "runtime_dynamodb_gateway" {
  vpc_id            = local.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = local.private_route_table_ids

  lifecycle {
    precondition {
      condition     = trimspace(local.vpc_id) != ""
      error_message = "VPC id is missing from core outputs. M2.B must be applied before runtime endpoint materialization."
    }
    precondition {
      condition     = length(local.private_route_table_ids) > 0
      error_message = "No private route table associations resolved from core private subnets."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "runtime_endpoint_dynamodb_gateway"
  })
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

data "aws_iam_policy_document" "assume_role_ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
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

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["emr-serverless.amazonaws.com"]
    }
  }

  statement {
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
      test     = "StringLike"
      variable = "${replace(aws_eks_cluster.platform.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values = [
        "system:serviceaccount:${var.eks_namespace_rtdl}:emr-containers-sa-*"
      ]
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
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${local.core_artifacts_bucket}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::${local.core_artifacts_bucket}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${local.core_object_store_bucket}",
          "arn:aws:s3:::${local.core_evidence_bucket}",
          "arn:aws:s3:::${local.core_artifacts_bucket}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:ListBucketMultipartUploads"
        ]
        Resource = [
          "arn:aws:s3:::${local.core_object_store_bucket}/*",
          "arn:aws:s3:::${local.core_evidence_bucket}/*",
          "arn:aws:s3:::${local.core_artifacts_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = local.core_kms_key_arn
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

resource "aws_iam_role_policy_attachment" "lambda_ig_vpc_access" {
  role       = aws_iam_role.lambda_ig_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ig_runtime" {
  name = "${var.role_lambda_ig_execution_name}-runtime-policy"
  role = aws_iam_role.lambda_ig_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
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
          Resource = [
            "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_ig_api_key_path}",
            "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_msk_bootstrap_brokers_path}",
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "sqs:SendMessage"
          ]
          Resource = aws_sqs_queue.ig_dlq.arn
        },
        {
          Effect = "Allow"
          Action = [
            "s3:ListBucket"
          ]
          Resource = "arn:aws:s3:::${local.core_object_store_bucket}"
        },
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject"
          ]
          Resource = "arn:aws:s3:::${local.core_object_store_bucket}/*"
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:Connect",
            "kafka-cluster:DescribeCluster"
          ]
          Resource = local.msk_cluster_arn
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:DescribeTopic",
            "kafka-cluster:ReadData",
            "kafka-cluster:WriteData"
          ]
          Resource = local.msk_topic_wildcard_arn
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:DescribeGroup",
            "kafka-cluster:AlterGroup"
          ]
          Resource = local.msk_group_wildcard_arn
        }
      ],
      local.core_kms_key_arn != "" ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:Encrypt",
            "kms:GenerateDataKey",
            "kms:DescribeKey"
          ]
          Resource = local.core_kms_key_arn
        }
      ] : []
    )
  })
}

resource "aws_security_group" "lambda_ig" {
  name        = "${var.lambda_ig_handler_name}-sg"
  description = "Private runtime egress for ingress Lambda"
  vpc_id      = local.vpc_id

  egress {
    description = "Allow private runtime egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    precondition {
      condition     = trimspace(local.vpc_id) != ""
      error_message = "Ingress Lambda security group requires a VPC from core outputs."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_lambda_sg"
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
  function_name                  = var.lambda_ig_handler_name
  role                           = aws_iam_role.lambda_ig_execution.arn
  runtime                        = "python3.12"
  handler                        = local.lambda_ig_use_remote_package ? "fraud_detection.ingestion_gate.aws_lambda_handler.lambda_handler" : "ig_handler.lambda_handler"
  filename                       = local.lambda_ig_use_remote_package ? null : data.archive_file.ig_handler_zip.output_path
  s3_bucket                      = local.lambda_ig_use_remote_package ? var.lambda_ig_package_s3_bucket : null
  s3_key                         = local.lambda_ig_use_remote_package ? var.lambda_ig_package_s3_key : null
  source_code_hash               = local.lambda_ig_source_code_hash
  timeout                        = floor(var.lambda_ig_timeout_seconds)
  memory_size                    = floor(var.lambda_ig_memory_size_mb)
  reserved_concurrent_executions = floor(var.lambda_ig_reserved_concurrency)

  vpc_config {
    subnet_ids         = local.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_ig.id]
  }

  environment {
    variables = {
      IG_IDEMPOTENCY_TABLE               = aws_dynamodb_table.ig_idempotency.name
      IG_HASH_KEY                        = var.ddb_ig_idempotency_hash_key
      IG_TTL_ATTRIBUTE                   = var.ddb_ig_idempotency_ttl_attribute
      IG_API_KEY_PATH                    = aws_ssm_parameter.ig_api_key.name
      IG_AUTH_MODE                       = var.ig_auth_mode
      IG_AUTH_HEADER_NAME                = var.ig_auth_header_name
      IG_MAX_REQUEST_BYTES               = tostring(var.ig_max_request_bytes)
      IG_REQUEST_TIMEOUT_SECONDS         = tostring(var.ig_request_timeout_seconds)
      IG_INTERNAL_RETRY_MAX_ATTEMPTS     = tostring(var.ig_internal_retry_max_attempts)
      IG_INTERNAL_RETRY_BACKOFF_MS       = tostring(var.ig_internal_retry_backoff_ms)
      IG_IDEMPOTENCY_TTL_SECONDS         = tostring(var.ig_idempotency_ttl_seconds)
      IG_DLQ_MODE                        = var.ig_dlq_mode
      IG_DLQ_QUEUE_NAME                  = var.ig_dlq_queue_name
      IG_DLQ_URL                         = aws_sqs_queue.ig_dlq.url
      IG_REPLAY_MODE                     = var.ig_replay_mode
      IG_RATE_LIMIT_RPS                  = tostring(var.ig_rate_limit_rps)
      IG_RATE_LIMIT_BURST                = tostring(var.ig_rate_limit_burst)
      PLATFORM_PROFILE_ID                = var.environment
      PLATFORM_CONFIG_REVISION           = "dev-full-v0"
      PLATFORM_STORE_ROOT                = "s3://${local.core_object_store_bucket}"
      OBJECT_STORE_REGION                = var.aws_region
      OBJECT_STORE_PATH_STYLE            = "false"
      KAFKA_AWS_REGION                   = var.aws_region
      KAFKA_SECURITY_PROTOCOL            = "SASL_SSL"
      KAFKA_SASL_MECHANISM               = "OAUTHBEARER"
      KAFKA_REQUEST_TIMEOUT_MS           = tostring(var.lambda_ig_kafka_request_timeout_ms)
      KAFKA_PUBLISH_RETRIES              = "3"
      KAFKA_BOOTSTRAP_BROKERS_PARAM_PATH = var.ssm_msk_bootstrap_brokers_path
      IG_HEALTH_BUS_PROBE_MODE           = "describe"
      IG_POLICY_ACTIVATION_AUDIT_MODE    = var.lambda_ig_policy_activation_audit_mode
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_ig_basic,
    aws_iam_role_policy_attachment.lambda_ig_vpc_access,
    aws_iam_role_policy.lambda_ig_runtime
  ]

  lifecycle {
    precondition {
      condition     = floor(var.lambda_ig_timeout_seconds) >= floor(var.ig_request_timeout_seconds)
      error_message = "Lambda timeout must be >= IG request timeout seconds."
    }
    precondition {
      condition     = floor(var.lambda_ig_memory_size_mb) >= 256
      error_message = "Lambda memory must be at least 256 MB."
    }
    precondition {
      condition     = floor(var.lambda_ig_reserved_concurrency) > 0
      error_message = "Lambda reserved concurrency must be positive for cert-time explicit envelope control."
    }
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "Ingress Lambda requires at least two private subnets from core outputs."
    }
    precondition {
      condition     = trimspace(local.msk_cluster_arn) != ""
      error_message = "Ingress Lambda requires a resolved MSK cluster ARN."
    }
  }

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

resource "aws_ecs_cluster" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  name = var.ig_service_cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_cluster"
  })
}

resource "aws_security_group" "ig_service_alb" {
  count = var.ig_service_enabled ? 1 : 0

  name        = "${var.ig_service_name}-alb-sg"
  description = "Internal ALB ingress for managed IG service"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTP from private runtime subnets"
    from_port   = floor(var.ig_service_listener_port)
    to_port     = floor(var.ig_service_listener_port)
    protocol    = "tcp"
    cidr_blocks = local.private_subnet_cidrs
  }

  egress {
    description = "ALB egress to managed IG service tasks"
    from_port   = floor(var.ig_service_container_port)
    to_port     = floor(var.ig_service_container_port)
    protocol    = "tcp"
    cidr_blocks = local.private_subnet_cidrs
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_alb_sg"
  })
}

resource "aws_security_group" "ig_service_tasks" {
  count = var.ig_service_enabled ? 1 : 0

  name        = "${var.ig_service_name}-tasks-sg"
  description = "Managed IG service tasks"
  vpc_id      = local.vpc_id

  ingress {
    description     = "HTTP from internal ALB"
    from_port       = floor(var.ig_service_container_port)
    to_port         = floor(var.ig_service_container_port)
    protocol        = "tcp"
    security_groups = [aws_security_group.ig_service_alb[0].id]
  }

  egress {
    description = "Runtime egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_tasks_sg"
  })
}

resource "aws_lb" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  name               = "fp-dev-full-ig-svc"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.ig_service_alb[0].id]
  subnets            = local.private_subnet_ids

  lifecycle {
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "Managed IG service ALB requires at least two private subnets."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_alb"
  })
}

resource "aws_lb_target_group" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  name                 = "fp-dev-full-ig-svc"
  port                 = floor(var.ig_service_container_port)
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = local.vpc_id
  deregistration_delay = 10

  health_check {
    enabled             = true
    path                = "/healthz"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 15
    timeout             = 5
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_tg"
  })
}

resource "aws_lb_listener" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  load_balancer_arn = aws_lb.ig_service[0].arn
  port              = floor(var.ig_service_listener_port)
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ig_service[0].arn
  }
}

resource "aws_cloudwatch_log_group" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  name              = var.ig_service_log_group_name
  retention_in_days = 14

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_log_group"
  })
}

resource "aws_iam_role" "ecs_ig_task_execution" {
  count = var.ig_service_enabled ? 1 : 0

  name               = var.role_ecs_ig_task_execution_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_ecs_tasks.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_ig_task_execution_managed" {
  count = var.ig_service_enabled ? 1 : 0

  role       = aws_iam_role.ecs_ig_task_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_ig_task_runtime" {
  count = var.ig_service_enabled ? 1 : 0

  name               = var.role_ecs_ig_task_runtime_name
  assume_role_policy = data.aws_iam_policy_document.assume_role_ecs_tasks.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "ecs_ig_task_runtime" {
  count = var.ig_service_enabled ? 1 : 0

  name = "${var.role_ecs_ig_task_runtime_name}-policy"
  role = aws_iam_role.ecs_ig_task_runtime[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
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
            "ssm:GetParameter",
            "ssm:GetParameters"
          ]
          Resource = [
            "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_ig_api_key_path}",
            "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_msk_bootstrap_brokers_path}",
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "sqs:SendMessage"
          ]
          Resource = aws_sqs_queue.ig_dlq.arn
        },
        {
          Effect = "Allow"
          Action = [
            "s3:ListBucket"
          ]
          Resource = "arn:aws:s3:::${local.core_object_store_bucket}"
        },
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject"
          ]
          Resource = "arn:aws:s3:::${local.core_object_store_bucket}/*"
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:Connect",
            "kafka-cluster:DescribeCluster"
          ]
          Resource = local.msk_cluster_arn
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:DescribeTopic",
            "kafka-cluster:ReadData",
            "kafka-cluster:WriteData"
          ]
          Resource = local.msk_topic_wildcard_arn
        },
        {
          Effect = "Allow"
          Action = [
            "kafka-cluster:DescribeGroup",
            "kafka-cluster:AlterGroup"
          ]
          Resource = local.msk_group_wildcard_arn
        }
      ],
      local.core_kms_key_arn != "" ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:Encrypt",
            "kms:GenerateDataKey",
            "kms:DescribeKey"
          ]
          Resource = local.core_kms_key_arn
        }
      ] : []
    )
  })
}

resource "aws_ecs_task_definition" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  family                   = var.ig_service_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(floor(var.ig_service_task_cpu))
  memory                   = tostring(floor(var.ig_service_task_memory))
  execution_role_arn       = aws_iam_role.ecs_ig_task_execution[0].arn
  task_role_arn            = aws_iam_role.ecs_ig_task_runtime[0].arn

  container_definitions = jsonencode([
    {
      name      = "ig"
      image     = var.ig_service_image_uri
      essential = true
      portMappings = [
        {
          containerPort = floor(var.ig_service_container_port)
          hostPort      = floor(var.ig_service_container_port)
          protocol      = "tcp"
        }
      ]
      command = [
        "/bin/sh",
        "-lc",
        "exec gunicorn --bind 0.0.0.0:$${IG_SERVICE_PORT} --workers $${IG_GUNICORN_WORKERS} --threads $${IG_GUNICORN_THREADS} --worker-class gthread --timeout $${IG_GUNICORN_TIMEOUT_SECONDS} --factory 'fraud_detection.ingestion_gate.managed_service:create_app()'"
      ]
      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "IG_SERVICE_PORT"
          value = tostring(floor(var.ig_service_container_port))
        },
        {
          name  = "IG_GUNICORN_WORKERS"
          value = tostring(floor(var.ig_service_gunicorn_workers))
        },
        {
          name  = "IG_GUNICORN_THREADS"
          value = tostring(floor(var.ig_service_gunicorn_threads))
        },
        {
          name  = "IG_GUNICORN_TIMEOUT_SECONDS"
          value = tostring(ceil(var.ig_service_request_timeout_ms / 1000))
        },
        {
          name  = "IG_IDEMPOTENCY_TABLE"
          value = aws_dynamodb_table.ig_idempotency.name
        },
        {
          name  = "IG_HASH_KEY"
          value = var.ddb_ig_idempotency_hash_key
        },
        {
          name  = "IG_TTL_ATTRIBUTE"
          value = var.ddb_ig_idempotency_ttl_attribute
        },
        {
          name  = "IG_API_KEY_PATH"
          value = aws_ssm_parameter.ig_api_key.name
        },
        {
          name  = "IG_AUTH_MODE"
          value = var.ig_auth_mode
        },
        {
          name  = "IG_AUTH_HEADER_NAME"
          value = var.ig_auth_header_name
        },
        {
          name  = "IG_MAX_REQUEST_BYTES"
          value = tostring(var.ig_max_request_bytes)
        },
        {
          name  = "IG_REQUEST_TIMEOUT_SECONDS"
          value = tostring(var.ig_request_timeout_seconds)
        },
        {
          name  = "IG_INTERNAL_RETRY_MAX_ATTEMPTS"
          value = tostring(var.ig_internal_retry_max_attempts)
        },
        {
          name  = "IG_INTERNAL_RETRY_BACKOFF_MS"
          value = tostring(var.ig_internal_retry_backoff_ms)
        },
        {
          name  = "IG_IDEMPOTENCY_TTL_SECONDS"
          value = tostring(var.ig_idempotency_ttl_seconds)
        },
        {
          name  = "IG_DLQ_MODE"
          value = var.ig_dlq_mode
        },
        {
          name  = "IG_DLQ_QUEUE_NAME"
          value = var.ig_dlq_queue_name
        },
        {
          name  = "IG_DLQ_URL"
          value = aws_sqs_queue.ig_dlq.url
        },
        {
          name  = "IG_REPLAY_MODE"
          value = var.ig_replay_mode
        },
        {
          name  = "IG_RATE_LIMIT_RPS"
          value = tostring(var.ig_rate_limit_rps)
        },
        {
          name  = "IG_RATE_LIMIT_BURST"
          value = tostring(var.ig_rate_limit_burst)
        },
        {
          name  = "PLATFORM_PROFILE_ID"
          value = var.environment
        },
        {
          name  = "PLATFORM_CONFIG_REVISION"
          value = "dev-full-v0"
        },
        {
          name  = "PLATFORM_STORE_ROOT"
          value = "s3://${local.core_object_store_bucket}"
        },
        {
          name  = "OBJECT_STORE_REGION"
          value = var.aws_region
        },
        {
          name  = "OBJECT_STORE_PATH_STYLE"
          value = "false"
        },
        {
          name  = "KAFKA_AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "KAFKA_SECURITY_PROTOCOL"
          value = "SASL_SSL"
        },
        {
          name  = "KAFKA_SASL_MECHANISM"
          value = "OAUTHBEARER"
        },
        {
          name  = "KAFKA_REQUEST_TIMEOUT_MS"
          value = tostring(var.lambda_ig_kafka_request_timeout_ms)
        },
        {
          name  = "KAFKA_PUBLISH_RETRIES"
          value = "3"
        },
        {
          name  = "KAFKA_BOOTSTRAP_BROKERS_PARAM_PATH"
          value = var.ssm_msk_bootstrap_brokers_path
        },
        {
          name  = "IG_HEALTH_BUS_PROBE_MODE"
          value = "describe"
        },
        {
          name  = "IG_POLICY_ACTIVATION_AUDIT_MODE"
          value = var.lambda_ig_policy_activation_audit_mode
        }
      ]
      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import sys, urllib.request; urllib.request.urlopen('http://127.0.0.1:$${IG_SERVICE_PORT}/healthz', timeout=2).read(); sys.exit(0)\" || exit 1"
        ]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ig_service[0].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  lifecycle {
    precondition {
      condition     = trimspace(var.ig_service_image_uri) != ""
      error_message = "ig_service_image_uri must be pinned when ig_service_enabled=true."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_task_definition"
  })
}

resource "aws_ecs_service" "ig_service" {
  count = var.ig_service_enabled ? 1 : 0

  name            = var.ig_service_name
  cluster         = aws_ecs_cluster.ig_service[0].id
  task_definition = aws_ecs_task_definition.ig_service[0].arn
  desired_count   = floor(var.ig_service_desired_count)
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ig_service_tasks[0].id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ig_service[0].arn
    container_name   = "ig"
    container_port   = floor(var.ig_service_container_port)
  }

  depends_on = [
    aws_lb_listener.ig_service,
    aws_iam_role_policy_attachment.ecs_ig_task_execution_managed,
    aws_iam_role_policy.ecs_ig_task_runtime,
  ]

  lifecycle {
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "Managed IG service requires at least two private subnets."
    }
    precondition {
      condition     = floor(var.ig_service_desired_count) > 0
      error_message = "Managed IG service desired count must be positive."
    }
  }

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_ecs_service"
  })
}

resource "aws_ssm_parameter" "ig_service_url" {
  count = var.ig_service_enabled ? 1 : 0

  name      = var.ssm_ig_service_url_path
  type      = "String"
  value     = "http://${aws_lb.ig_service[0].dns_name}/v1/ingest/push"
  overwrite = true

  tags = merge(local.common_tags, {
    fp_resource = "ig_service_url"
  })
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

resource "aws_eks_node_group" "m6f_workers" {
  cluster_name    = aws_eks_cluster.platform.name
  node_group_name = var.eks_nodegroup_m6f_name
  node_role_arn   = local.role_eks_nodegroup_dev_full_arn
  subnet_ids      = local.private_subnet_ids
  ami_type        = var.eks_nodegroup_ami_type
  capacity_type   = var.eks_nodegroup_capacity_type
  instance_types  = var.eks_nodegroup_instance_types
  disk_size       = var.eks_nodegroup_disk_size

  scaling_config {
    desired_size = var.eks_nodegroup_desired_size
    min_size     = var.eks_nodegroup_min_size
    max_size     = var.eks_nodegroup_max_size
  }

  update_config {
    max_unavailable = 1
  }

  lifecycle {
    precondition {
      condition     = trimspace(local.role_eks_nodegroup_dev_full_arn) != ""
      error_message = "ROLE_EKS_NODEGROUP_DEV_FULL is missing from core outputs. M2.B must be applied before M6 worker lane."
    }
    precondition {
      condition     = length(local.private_subnet_ids) >= 2
      error_message = "M6 worker nodegroup requires at least two private subnets."
    }
  }

  depends_on = [
    aws_vpc_endpoint.runtime_interface,
    aws_vpc_endpoint.runtime_s3_gateway,
  ]

  tags = merge(local.common_tags, {
    fp_resource = "eks_nodegroup_m6f_workers"
    fp_phase    = "M6.F"
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

resource "aws_iam_role_policy" "eks_irsa_msk_data_plane" {
  for_each = local.irsa_targets_with_msk

  name = "${each.value.role_name}-msk-data-plane"
  role = aws_iam_role.eks_irsa[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = local.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData"
        ]
        Resource = local.msk_topic_wildcard_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:DescribeGroup",
          "kafka-cluster:AlterGroup"
        ]
        Resource = local.msk_group_wildcard_arn
      }
    ]
  })
}
