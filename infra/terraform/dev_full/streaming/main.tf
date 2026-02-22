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

locals {
  common_tags = merge(
    {
      project = var.project
      env     = var.environment
      owner   = var.owner
    },
    var.additional_tags
  )

  remote_subnets = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.msk_client_subnet_ids, []) : []
  remote_sg      = var.use_core_remote_state ? try(data.terraform_remote_state.core[0].outputs.msk_security_group_id, "") : ""

  msk_client_subnet_ids = length(var.msk_client_subnet_ids_override) > 0 ? var.msk_client_subnet_ids_override : local.remote_subnets
  msk_security_group_id = trimspace(var.msk_security_group_id_override) != "" ? var.msk_security_group_id_override : local.remote_sg
}

resource "aws_msk_serverless_cluster" "streaming" {
  cluster_name = var.msk_cluster_name

  vpc_config {
    subnet_ids         = local.msk_client_subnet_ids
    security_group_ids = [local.msk_security_group_id]
  }

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }

  tags = merge(local.common_tags, {
    Name          = var.msk_cluster_name
    fp_stack      = "streaming"
    fp_msk_mode   = "serverless"
    fp_auth_mode  = "sasl_iam"
    fp_managed_by = "terraform"
  })

  lifecycle {
    precondition {
      condition     = length(local.msk_client_subnet_ids) >= 2
      error_message = "MSK requires at least two client subnets. Materialize M2.B core outputs or provide msk_client_subnet_ids_override."
    }
    precondition {
      condition     = trimspace(local.msk_security_group_id) != ""
      error_message = "MSK security group is missing. Materialize M2.B core output or provide msk_security_group_id_override."
    }
  }
}

data "aws_msk_bootstrap_brokers" "streaming" {
  cluster_arn = aws_msk_serverless_cluster.streaming.arn
}

resource "aws_ssm_parameter" "msk_bootstrap_brokers" {
  name      = var.ssm_msk_bootstrap_brokers_path
  type      = "SecureString"
  overwrite = true
  value     = data.aws_msk_bootstrap_brokers.streaming.bootstrap_brokers_sasl_iam

  tags = merge(local.common_tags, {
    fp_resource = "msk_bootstrap_brokers"
  })
}

resource "aws_glue_registry" "streaming" {
  registry_name = var.glue_schema_registry_name
  description   = "dev_full v0 streaming schema registry baseline"

  tags = merge(local.common_tags, {
    fp_resource = "glue_schema_registry"
  })
}

resource "aws_glue_schema" "anchor_control" {
  registry_arn      = aws_glue_registry.streaming.arn
  schema_name       = var.glue_anchor_schema_name
  data_format       = "JSON"
  compatibility     = var.glue_schema_compatibility_mode
  schema_definition = var.glue_anchor_schema_definition

  tags = merge(local.common_tags, {
    fp_resource = "glue_anchor_schema"
  })
}
