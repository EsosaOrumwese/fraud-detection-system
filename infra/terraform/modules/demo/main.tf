locals {
  tags_demo = merge(var.common_tags, {
    fp_phase = "phase2"
    fp_tier  = "demo"
  })

  manifest_key             = "dev_min/infra/demo/${var.demo_run_id}/manifest.json"
  topic_catalog_key        = "dev_min/infra/demo/${var.demo_run_id}/confluent/topic_catalog.json"
  heartbeat_param          = "/fraud-platform/dev_min/demo/${var.demo_run_id}/heartbeat"
  ig_event_bus_stream_name = "${var.name_prefix}-ig-bus-v0"
  db_password_value        = trimspace(var.db_password) != "" ? var.db_password : random_password.db_password.result
  lane_role_names = {
    ig_service      = "${var.name_prefix}-ig-service"
    rtdl_core       = "${var.name_prefix}-rtdl-core"
    decision_lane   = "${var.name_prefix}-decision-lane"
    case_labels     = "${var.name_prefix}-case-labels"
    env_conformance = "${var.name_prefix}-env-conformance"
  }

  daemon_container_image_resolved = trimspace(var.ecs_daemon_container_image) != "" ? var.ecs_daemon_container_image : var.ecs_probe_container_image

  daemon_service_specs = {
    "ig" = {
      service_name   = "${var.name_prefix}-ig"
      lane_role_key  = "ig_service"
      pack_id        = "control_ingress"
      runtime_mode   = "service"
      component_mode = "ig"
    }
    "rtdl-core-archive-writer" = {
      service_name   = "${var.name_prefix}-rtdl-core-archive-writer"
      lane_role_key  = "rtdl_core"
      pack_id        = "rtdl_core"
      runtime_mode   = "worker"
      component_mode = "archive_writer"
    }
    "rtdl-core-ieg" = {
      service_name   = "${var.name_prefix}-rtdl-core-ieg"
      lane_role_key  = "rtdl_core"
      pack_id        = "rtdl_core"
      runtime_mode   = "worker"
      component_mode = "ieg"
    }
    "rtdl-core-ofp" = {
      service_name   = "${var.name_prefix}-rtdl-core-ofp"
      lane_role_key  = "rtdl_core"
      pack_id        = "rtdl_core"
      runtime_mode   = "worker"
      component_mode = "ofp"
    }
    "rtdl-core-csfb" = {
      service_name   = "${var.name_prefix}-rtdl-core-csfb"
      lane_role_key  = "rtdl_core"
      pack_id        = "rtdl_core"
      runtime_mode   = "worker"
      component_mode = "csfb"
    }
    "decision-lane-dl" = {
      service_name   = "${var.name_prefix}-decision-lane-dl"
      lane_role_key  = "decision_lane"
      pack_id        = "rtdl_decision_lane"
      runtime_mode   = "worker"
      component_mode = "dl"
    }
    "decision-lane-df" = {
      service_name   = "${var.name_prefix}-decision-lane-df"
      lane_role_key  = "decision_lane"
      pack_id        = "rtdl_decision_lane"
      runtime_mode   = "worker"
      component_mode = "df"
    }
    "decision-lane-al" = {
      service_name   = "${var.name_prefix}-decision-lane-al"
      lane_role_key  = "decision_lane"
      pack_id        = "rtdl_decision_lane"
      runtime_mode   = "worker"
      component_mode = "al"
    }
    "decision-lane-dla" = {
      service_name   = "${var.name_prefix}-decision-lane-dla"
      lane_role_key  = "decision_lane"
      pack_id        = "rtdl_decision_lane"
      runtime_mode   = "worker"
      component_mode = "dla"
    }
    "case-trigger" = {
      service_name   = "${var.name_prefix}-case-trigger"
      lane_role_key  = "case_labels"
      pack_id        = "case_labels"
      runtime_mode   = "worker"
      component_mode = "case_trigger"
    }
    "case-mgmt" = {
      service_name   = "${var.name_prefix}-case-mgmt"
      lane_role_key  = "case_labels"
      pack_id        = "case_labels"
      runtime_mode   = "service"
      component_mode = "cm"
    }
    "label-store" = {
      service_name   = "${var.name_prefix}-label-store"
      lane_role_key  = "case_labels"
      pack_id        = "case_labels"
      runtime_mode   = "service"
      component_mode = "ls"
    }
    "env-conformance" = {
      service_name   = "${var.name_prefix}-env-conformance"
      lane_role_key  = "env_conformance"
      pack_id        = "obs_gov"
      runtime_mode   = "worker"
      component_mode = "env_conformance"
    }
  }

  oracle_job_specs = {
    "oracle-stream-sort" = {
      family_name    = "${var.name_prefix}-oracle-stream-sort"
      component_mode = "oracle_stream_sort"
      command = [
        "sh",
        "-c",
        "echo oracle_stream_sort_task_definition_materialized && exit 0",
      ]
    }
    "oracle-checker" = {
      family_name    = "${var.name_prefix}-oracle-checker"
      component_mode = "oracle_checker"
      command = [
        "sh",
        "-c",
        "echo oracle_checker_task_definition_materialized && exit 0",
      ]
    }
  }

  control_job_specs = {
    "sr" = {
      family_name    = "${var.name_prefix}-sr"
      component_mode = "stream_ready"
      command = [
        "sh",
        "-c",
        "echo sr_task_definition_materialized && exit 0",
      ]
    }
    "wsp" = {
      family_name    = "${var.name_prefix}-wsp"
      component_mode = "world_stream_producer"
      command = [
        "sh",
        "-c",
        "echo wsp_task_definition_materialized && exit 0",
      ]
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_partition" "current" {}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "demo" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-vpc"
    fp_resource = "demo_vpc"
  })
}

resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-igw"
    fp_resource = "demo_igw"
  })
}

resource "aws_subnet" "public" {
  for_each = {
    for idx, cidr in var.public_subnet_cidrs :
    tostring(idx) => {
      cidr = cidr
      az   = data.aws_availability_zones.available.names[idx]
    }
  }

  vpc_id                  = aws_vpc.demo.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-public-${each.key}"
    fp_resource = "demo_public_subnet"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-public-rt"
    fp_resource = "demo_public_route_table"
  })
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.demo.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app-sg"
  description = "Application SG for demo ECS tasks/services"
  vpc_id      = aws_vpc.demo.id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-app-sg"
    fp_resource = "demo_app_sg"
  })
}

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-db-sg"
  description = "DB SG for demo runtime database"
  vpc_id      = aws_vpc.demo.id

  ingress {
    from_port       = var.db_port
    to_port         = var.db_port
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-db-sg"
    fp_resource = "demo_db_sg"
  })
}

resource "aws_cloudwatch_log_group" "demo" {
  name              = "${var.log_group_prefix}/demo/${var.demo_run_id}"
  retention_in_days = var.cloudwatch_retention
  tags              = merge(local.tags_demo, { fp_resource = "demo_log_group" })
}

resource "aws_ecs_cluster" "demo" {
  name = var.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(local.tags_demo, { fp_resource = "demo_ecs_cluster" })
}

resource "aws_kinesis_stream" "ig_event_bus" {
  name             = local.ig_event_bus_stream_name
  shard_count      = 1
  retention_period = 24

  tags = merge(local.tags_demo, {
    fp_resource = "demo_ig_event_bus_stream"
  })
}

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ecs_task_app_secret_read" {
  statement {
    sid = "ReadPinnedSecretParameters"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_confluent_bootstrap_path}",
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_confluent_api_key_path}",
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_confluent_api_secret_path}",
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_db_user_path}",
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_db_password_path}",
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_ig_api_key_path}",
    ]
  }
}

data "aws_iam_policy_document" "lane_app_object_store_data_plane" {
  statement {
    sid = "ListOraclePrefix"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${var.object_store_bucket}",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "oracle/*",
      ]
    }
  }

  statement {
    sid = "OracleObjectReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${var.object_store_bucket}/oracle/*",
    ]
  }

  statement {
    sid = "ListEvidencePrefix"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${var.evidence_bucket}",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "evidence/runs/*",
      ]
    }
  }

  statement {
    sid = "EvidenceObjectReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${var.evidence_bucket}/evidence/runs/*",
    ]
  }
}

data "aws_iam_policy_document" "lane_app_kinesis_publish" {
  statement {
    sid = "KinesisPublish"
    actions = [
      "kinesis:DescribeStreamSummary",
      "kinesis:ListShards",
      "kinesis:PutRecord",
      "kinesis:PutRecords",
    ]
    resources = [
      aws_kinesis_stream.ig_event_bus.arn,
    ]
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.name_prefix}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
  tags               = merge(local.tags_demo, { fp_resource = "demo_ecs_task_execution_role" })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_app" {
  name               = "${var.name_prefix}-ecs-task-app"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
  tags               = merge(local.tags_demo, { fp_resource = "demo_ecs_task_app_role" })
}

resource "aws_iam_role_policy" "ecs_task_app_secret_read" {
  name   = "${var.name_prefix}-ecs-task-app-secret-read"
  role   = aws_iam_role.ecs_task_app.id
  policy = data.aws_iam_policy_document.ecs_task_app_secret_read.json
}

resource "aws_iam_role" "lane_app_roles" {
  for_each = local.lane_role_names

  name               = each.value
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
  tags = merge(local.tags_demo, {
    fp_resource = "demo_lane_app_role"
    fp_lane     = each.key
  })
}

resource "aws_iam_role_policy" "lane_app_secret_read" {
  for_each = aws_iam_role.lane_app_roles

  name   = "${var.name_prefix}-${each.key}-secret-read"
  role   = each.value.id
  policy = data.aws_iam_policy_document.ecs_task_app_secret_read.json
}

resource "aws_iam_role_policy" "lane_app_object_store_data_plane" {
  for_each = {
    for key, role in aws_iam_role.lane_app_roles : key => role
    if contains(["rtdl_core", "ig_service"], key)
  }

  name   = "${var.name_prefix}-${each.key}-object-store-data-plane"
  role   = each.value.id
  policy = data.aws_iam_policy_document.lane_app_object_store_data_plane.json
}

resource "aws_iam_role_policy" "lane_app_kinesis_publish" {
  for_each = {
    for key, role in aws_iam_role.lane_app_roles : key => role
    if contains(["ig_service"], key)
  }

  name   = "${var.name_prefix}-${each.key}-kinesis-publish"
  role   = each.value.id
  policy = data.aws_iam_policy_document.lane_app_kinesis_publish.json
}

resource "aws_ecs_task_definition" "runtime_probe" {
  family                   = "${var.name_prefix}-runtime-probe"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_app.arn

  container_definitions = jsonencode([
    {
      name      = "runtime-probe"
      image     = var.ecs_probe_container_image
      essential = true
      command   = ["sh", "-c", "sleep 3600"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.demo.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(local.tags_demo, { fp_resource = "demo_ecs_task_definition" })
}

resource "aws_ecs_task_definition" "db_migrations" {
  family                   = "${var.name_prefix}-db-migrations"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_app.arn

  container_definitions = jsonencode([
    {
      name      = "db-migrations"
      image     = var.ecs_probe_container_image
      essential = true
      command   = ["sh", "-c", "echo db_migrations_task_materialized && exit 0"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.demo.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(local.tags_demo, { fp_resource = "demo_ecs_task_definition_db_migrations" })
}

resource "aws_ecs_service" "runtime_probe" {
  name            = "${var.name_prefix}-runtime-probe"
  cluster         = aws_ecs_cluster.demo.id
  task_definition = aws_ecs_task_definition.runtime_probe.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 0

  network_configuration {
    assign_public_ip = true
    subnets          = [for subnet in aws_subnet.public : subnet.id]
    security_groups  = [aws_security_group.app.id]
  }

  tags = merge(local.tags_demo, { fp_resource = "demo_ecs_service" })

  depends_on = [aws_iam_role_policy_attachment.ecs_task_execution]
}

resource "aws_ecs_task_definition" "daemon" {
  for_each = local.daemon_service_specs

  family                   = each.value.service_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_daemon_task_cpu
  memory                   = var.ecs_daemon_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.lane_app_roles[each.value.lane_role_key].arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = local.daemon_container_image_resolved
      essential = true
      command = each.key == "ig" ? [
        "sh",
        "-c",
        "set -e; cp config/platform/profiles/local_parity.yaml /tmp/dev_min_ig_m6c.yaml; python - <<'PY'\nfrom pathlib import Path\nimport yaml\nlayer1_path = Path('/app/docs/model_spec/data-engine/interface_pack/layer-1/specs/contracts/1A/schemas.layer1.yaml')\nif not layer1_path.exists():\n    layer1_path.parent.mkdir(parents=True, exist_ok=True)\n    layer1_stub = {\n        'version': '0.1.0',\n        '$defs': {\n            'hex64': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},\n            'hex32': {'type': 'string', 'pattern': '^[0-9a-f]{32}$'},\n            'uint64': {'type': 'integer', 'minimum': 0, 'maximum': 18446744073709551615},\n            'rfc3339_micros': {'type': 'string', 'pattern': '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\\\.[0-9]{6}Z$'},\n        },\n    }\n    layer1_path.write_text(yaml.safe_dump(layer1_stub, sort_keys=False), encoding='utf-8')\nprofile_path = Path('/tmp/dev_min_ig_m6c.yaml')\ndata = yaml.safe_load(profile_path.read_text(encoding='utf-8'))\nwiring = data.setdefault('wiring', {})\nobj = wiring.setdefault('object_store', {})\nobj['root'] = 's3://${var.evidence_bucket}/evidence/runs'\nobj['region'] = '${var.aws_region}'\nobj['path_style'] = False\nobj.pop('endpoint', None)\nwiring['health_bus_probe_mode'] = 'none'\nwiring['event_bus_kind'] = 'kinesis'\nevent_bus = wiring.setdefault('event_bus', {})\nevent_bus.pop('root', None)\nevent_bus['stream'] = '${local.ig_event_bus_stream_name}'\nevent_bus['region'] = '${var.aws_region}'\nevent_bus.pop('endpoint_url', None)\nprofile_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')\nPY\npython -m fraud_detection.ingestion_gate.service --profile /tmp/dev_min_ig_m6c.yaml --host 0.0.0.0 --port 8080",
        ] : [
        "sh",
        "-c",
        "echo daemon_started service=${each.value.service_name} pack=${each.value.pack_id} mode=${each.value.component_mode} run_scope_env=${var.required_platform_run_id_env_key} run_scope_value=${var.required_platform_run_id}; trap 'exit 0' TERM INT; while true; do sleep 300; done",
      ]
      portMappings = each.key == "ig" ? [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ] : []
      environment = concat([
        {
          name  = var.required_platform_run_id_env_key
          value = var.required_platform_run_id
        },
        {
          name  = "FP_PACK_ID"
          value = each.value.pack_id
        },
        {
          name  = "FP_RUNTIME_MODE"
          value = each.value.runtime_mode
        },
        {
          name  = "FP_COMPONENT_MODE"
          value = each.value.component_mode
        },
        ], each.key == "ig" ? [
        {
          name  = "PLATFORM_RUN_ID"
          value = var.required_platform_run_id
        },
        {
          name  = "OBJECT_STORE_REGION"
          value = var.aws_region
        },
      ] : [])
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.demo.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/${each.key}"
        }
      }
    }
  ])

  tags = merge(local.tags_demo, {
    fp_resource = "demo_ecs_task_definition_daemon"
    fp_pack     = each.value.pack_id
    fp_service  = each.value.service_name
  })
}

resource "aws_ecs_task_definition" "oracle_job" {
  for_each = local.oracle_job_specs

  family                   = each.value.family_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_daemon_task_cpu
  memory                   = var.ecs_daemon_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.lane_app_roles["rtdl_core"].arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = local.daemon_container_image_resolved
      essential = true
      command   = each.value.command
      environment = [
        {
          name  = var.required_platform_run_id_env_key
          value = var.required_platform_run_id
        },
        {
          name  = "FP_PACK_ID"
          value = "oracle_p3"
        },
        {
          name  = "FP_RUNTIME_MODE"
          value = "job"
        },
        {
          name  = "FP_COMPONENT_MODE"
          value = each.value.component_mode
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.demo.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/${each.key}"
        }
      }
    }
  ])

  tags = merge(local.tags_demo, {
    fp_resource = "demo_ecs_task_definition_oracle_job"
    fp_pack     = "oracle_p3"
    fp_service  = each.value.family_name
  })
}

resource "aws_ecs_task_definition" "control_job" {
  for_each = local.control_job_specs

  family                   = each.value.family_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_daemon_task_cpu
  memory                   = var.ecs_daemon_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.lane_app_roles["rtdl_core"].arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = local.daemon_container_image_resolved
      essential = true
      command   = each.value.command
      environment = [
        {
          name  = var.required_platform_run_id_env_key
          value = var.required_platform_run_id
        },
        {
          name  = "FP_PACK_ID"
          value = "control_ingress"
        },
        {
          name  = "FP_RUNTIME_MODE"
          value = "job"
        },
        {
          name  = "FP_COMPONENT_MODE"
          value = each.value.component_mode
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.demo.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/control/${each.key}"
        }
      }
    }
  ])

  tags = merge(local.tags_demo, {
    fp_resource = "demo_ecs_task_definition_control_job"
    fp_pack     = "control_ingress"
    fp_service  = each.value.family_name
  })
}

resource "aws_ecs_service" "daemon" {
  for_each = local.daemon_service_specs

  name            = each.value.service_name
  cluster         = aws_ecs_cluster.demo.id
  task_definition = aws_ecs_task_definition.daemon[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 0

  network_configuration {
    assign_public_ip = true
    subnets          = [for subnet in aws_subnet.public : subnet.id]
    security_groups  = [aws_security_group.app.id]
  }

  tags = merge(local.tags_demo, {
    fp_resource = "demo_ecs_service_daemon"
    fp_pack     = each.value.pack_id
  })

  depends_on = [aws_iam_role_policy_attachment.ecs_task_execution]
}

resource "aws_db_subnet_group" "demo" {
  name       = "${var.name_prefix}-db-subnet-group"
  subnet_ids = [for subnet in aws_subnet.public : subnet.id]

  tags = merge(local.tags_demo, {
    Name        = "${var.name_prefix}-db-subnet-group"
    fp_resource = "demo_db_subnet_group"
  })
}

resource "random_password" "db_password" {
  length  = 24
  special = true
}

resource "aws_db_instance" "runtime" {
  identifier                      = var.rds_instance_id
  engine                          = "postgres"
  engine_version                  = var.db_engine_version
  instance_class                  = var.db_instance_class
  allocated_storage               = var.db_allocated_storage
  max_allocated_storage           = var.db_max_allocated_storage
  db_name                         = var.db_name
  username                        = var.db_username
  password                        = local.db_password_value
  db_subnet_group_name            = aws_db_subnet_group.demo.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  port                            = var.db_port
  publicly_accessible             = var.db_publicly_accessible
  skip_final_snapshot             = true
  deletion_protection             = false
  storage_encrypted               = true
  auto_minor_version_upgrade      = true
  backup_retention_period         = 0
  apply_immediately               = true
  performance_insights_enabled    = false
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = merge(local.tags_demo, { fp_resource = "demo_runtime_db" })
}

resource "aws_s3_object" "manifest" {
  bucket       = var.evidence_bucket
  key          = local.manifest_key
  content_type = "application/json"
  content = jsonencode({
    environment           = var.environment
    demo_run_id           = var.demo_run_id
    created_by            = "terraform"
    fp_phase              = "phase2"
    ecs_cluster_name      = aws_ecs_cluster.demo.name
    vpc_id                = aws_vpc.demo.id
    subnet_ids_public     = [for subnet in aws_subnet.public : subnet.id]
    security_group_id_app = aws_security_group.app.id
    security_group_id_db  = aws_security_group.db.id
    rds_instance_id       = aws_db_instance.runtime.identifier
    rds_endpoint          = aws_db_instance.runtime.address
    td_db_migrations      = aws_ecs_task_definition.db_migrations.arn
    td_sr                 = aws_ecs_task_definition.control_job["sr"].arn
    td_wsp                = aws_ecs_task_definition.control_job["wsp"].arn
    daemon_services       = { for key, svc in aws_ecs_service.daemon : key => svc.name }
    daemon_task_defs      = { for key, td in aws_ecs_task_definition.daemon : key => td.arn }
    control_job_task_defs = { for key, td in aws_ecs_task_definition.control_job : key => td.arn }
    ssm_paths = {
      confluent_bootstrap  = aws_ssm_parameter.confluent_bootstrap.name
      confluent_api_key    = aws_ssm_parameter.confluent_api_key.name
      confluent_api_secret = aws_ssm_parameter.confluent_api_secret.name
      db_user              = aws_ssm_parameter.db_user.name
      db_password          = aws_ssm_parameter.db_password.name
      ig_api_key           = aws_ssm_parameter.ig_api_key.name
    }
  })

  tags = merge(local.tags_demo, { fp_resource = "demo_manifest" })
}

resource "aws_s3_object" "confluent_topic_catalog" {
  bucket       = var.evidence_bucket
  key          = local.topic_catalog_key
  content_type = "application/json"
  content = jsonencode({
    environment        = var.environment
    demo_run_id        = var.demo_run_id
    confluent_env_name = var.confluent_env_name
    cluster = {
      name   = var.confluent_cluster_name
      type   = var.confluent_cluster_type
      cloud  = var.confluent_cluster_cloud
      region = var.confluent_cluster_region
    }
    topics = var.kafka_topics
  })

  tags = merge(local.tags_demo, { fp_resource = "demo_confluent_topic_catalog" })
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

resource "aws_ssm_parameter" "confluent_bootstrap" {
  name      = var.ssm_confluent_bootstrap_path
  type      = "SecureString"
  overwrite = true
  value     = var.confluent_bootstrap

  tags = merge(local.tags_demo, { fp_resource = "demo_confluent_bootstrap" })
}

resource "aws_ssm_parameter" "confluent_api_key" {
  name      = var.ssm_confluent_api_key_path
  type      = "SecureString"
  overwrite = true
  value     = var.confluent_api_key

  tags = merge(local.tags_demo, { fp_resource = "demo_confluent_api_key" })
}

resource "aws_ssm_parameter" "confluent_api_secret" {
  name      = var.ssm_confluent_api_secret_path
  type      = "SecureString"
  overwrite = true
  value     = var.confluent_api_secret

  tags = merge(local.tags_demo, { fp_resource = "demo_confluent_api_secret" })
}

resource "aws_ssm_parameter" "db_user" {
  name      = var.ssm_db_user_path
  type      = "SecureString"
  overwrite = true
  value     = var.db_username

  tags = merge(local.tags_demo, { fp_resource = "demo_db_user" })
}

resource "aws_ssm_parameter" "db_password" {
  name      = var.ssm_db_password_path
  type      = "SecureString"
  overwrite = true
  value     = local.db_password_value

  tags = merge(local.tags_demo, { fp_resource = "demo_db_password" })
}

resource "aws_ssm_parameter" "db_dsn" {
  count     = var.write_db_dsn_parameter ? 1 : 0
  name      = var.ssm_db_dsn_path
  type      = "SecureString"
  overwrite = true
  value     = "postgresql://${var.db_username}:${urlencode(local.db_password_value)}@${aws_db_instance.runtime.address}:${var.db_port}/${var.db_name}"

  tags = merge(local.tags_demo, { fp_resource = "demo_db_dsn" })
}

resource "aws_ssm_parameter" "ig_api_key" {
  name      = var.ssm_ig_api_key_path
  type      = "SecureString"
  overwrite = true
  value     = var.ig_api_key

  tags = merge(local.tags_demo, { fp_resource = "demo_ig_api_key" })
}
