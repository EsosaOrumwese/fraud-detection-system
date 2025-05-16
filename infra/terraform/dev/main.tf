###############################################################################
#  1. VPC  (terraform-aws-modules/vpc) — single public subnet for now
###############################################################################
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name           = "${var.bucket_prefix}-sandbox-vpc"
  cidr           = var.vpc_cidr
  azs            = ["${var.aws_region}a"]
  public_subnets = ["10.42.1.0/24"]

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.common_tags
}

###############################################################################
#  2. S3 buckets — raw data & model artefacts
###############################################################################
locals {
  buckets = [
    "${var.bucket_prefix}-dl-raw",
    "${var.bucket_prefix}-model-artifacts"
  ]
}

resource "aws_s3_bucket" "data" {
  for_each = toset(local.buckets)
  bucket   = each.value

  force_destroy = false # safety net

  tags = merge(local.common_tags, { Name = each.value })
}

# Versioning (cheap insurance) ----------------------------------------------
resource "aws_s3_bucket_versioning" "ver" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}

# Default encryption (KMS or AES256) ----------------------------------------
resource "aws_s3_bucket_server_side_encryption_configuration" "enc" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public ACL/Policy combos ----------------------------------------
resource "aws_s3_bucket_public_access_block" "pab" {
  for_each                = aws_s3_bucket.data
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  restrict_public_buckets = true
  ignore_public_acls      = true
}

###############################################################################
#  3. IAM role  — pipeline code will assume this role via STS
###############################################################################
data "aws_iam_policy_document" "s3_access" {
  statement {
    sid     = "BucketRW"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = concat(
      [for b in aws_s3_bucket.data : b.arn],
      [for b in aws_s3_bucket.data : "${b.arn}/*"]
    )
  }
}

resource "aws_iam_role" "pipeline" {
  name = "${var.bucket_prefix}-pipeline-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_policy" "pipeline" {
  name   = "${var.bucket_prefix}-pipeline-policy"
  policy = data.aws_iam_policy_document.s3_access.json
}

resource "aws_iam_role_policy_attachment" "attach" {
  role       = aws_iam_role.pipeline.name
  policy_arn = aws_iam_policy.pipeline.arn
}
