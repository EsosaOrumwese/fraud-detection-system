terraform {
  required_version = ">= 1.12.0"

  backend "s3" {}
}

locals {
  stack_id = "streaming"
}
