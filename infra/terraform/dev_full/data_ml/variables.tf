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

variable "role_sagemaker_execution_name" {
  type    = string
  default = "fraud-platform-dev-full-sagemaker-execution"
}

variable "role_databricks_cross_account_access_name" {
  type    = string
  default = "fraud-platform-dev-full-databricks-cross-account-access"
}

variable "databricks_trusted_principal_arn" {
  type    = string
  default = ""
}

variable "ssm_databricks_workspace_url_path" {
  type    = string
  default = "/fraud-platform/dev_full/databricks/workspace_url"
}

variable "ssm_databricks_token_path" {
  type    = string
  default = "/fraud-platform/dev_full/databricks/token"
}

variable "ssm_mlflow_tracking_uri_path" {
  type    = string
  default = "/fraud-platform/dev_full/mlflow/tracking_uri"
}

variable "ssm_sagemaker_model_exec_role_arn_path" {
  type    = string
  default = "/fraud-platform/dev_full/sagemaker/model_exec_role_arn"
}

variable "databricks_workspace_url_seed" {
  type    = string
  default = "https://dbc-placeholder.cloud.databricks.com"
}

variable "databricks_token_seed" {
  type      = string
  default   = "rotate-me-dev-full-databricks-token"
  sensitive = true
}

variable "mlflow_tracking_uri_seed" {
  type    = string
  default = "databricks"
}
