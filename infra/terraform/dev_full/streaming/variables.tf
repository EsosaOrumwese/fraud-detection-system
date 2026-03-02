variable "aws_region" {
  type    = string
  default = "eu-west-2"
}

variable "project" {
  type    = string
  default = "fraud-platform"
}

variable "environment" {
  type    = string
  default = "dev_full"
}

variable "owner" {
  type    = string
  default = "esosa"
}

variable "additional_tags" {
  type    = map(string)
  default = {}
}

variable "use_core_remote_state" {
  type    = bool
  default = true
}

variable "core_state_bucket" {
  type    = string
  default = "fraud-platform-dev-full-tfstate"
}

variable "core_state_key" {
  type    = string
  default = "dev_full/core/terraform.tfstate"
}

variable "core_state_region" {
  type    = string
  default = "eu-west-2"
}

variable "msk_cluster_name" {
  type    = string
  default = "fraud-platform-dev-full-msk"
}

variable "msk_client_subnet_ids_override" {
  type    = list(string)
  default = []
}

variable "msk_security_group_id_override" {
  type    = string
  default = ""
}

variable "ssm_msk_bootstrap_brokers_path" {
  type    = string
  default = "/fraud-platform/dev_full/msk/bootstrap_brokers"
}

variable "glue_schema_registry_name" {
  type    = string
  default = "fraud-platform-dev-full"
}

variable "glue_schema_compatibility_mode" {
  type    = string
  default = "BACKWARD"
}

variable "glue_anchor_schema_name" {
  type    = string
  default = "fp-bus-control-v1-envelope"
}

variable "glue_anchor_schema_definition" {
  type    = string
  default = <<-EOT
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ControlEnvelope",
  "type": "object",
  "properties": {
    "platform_run_id": { "type": "string" },
    "phase_id": { "type": "string" },
    "event_type": { "type": "string" },
    "written_at_utc": { "type": "string" }
  },
  "required": ["platform_run_id", "phase_id", "event_type", "written_at_utc"]
}
EOT
}
