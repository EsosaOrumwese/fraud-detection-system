###############################################################################
# 1 ▸ Networking layer – ultra-minimal VPC (no NAT Gateway ≈ £0/day)
###############################################################################

#trivy:ignore:AVD-AWS-0164   # skip error because public subnet is intentional in sandbox
#tfsec:ignore:aws-ec2-require-vpc-flow-logs-for-all-vpcs (no need for logging in this sandbox)
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "fraud-${var.environment}-vpc" } ## e.g. in this sandbox "fraud-sandbox--vpc"
}

# Public subnet in AZ-a so future services (Fargate, Lambda) have outbound
# internet without NAT (cheaper for a sandbox).
#trivy:ignore:AVD-AWS-0164   # skip error because public subnet is intentional in sandbox
#tfsec:ignore:aws-ec2-no-public-ip-subnet    # public-IP on subnet is intentional for sandbox
resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id                ## gets the VPC's id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 0) # 10.10.0.0/24     ###still don't get this section
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = { Name = "fraud-${var.environment}-public-a" }
}

# IGW + route table → make subnet actually public
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "fraud-${var.environment}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = { Name = "fraud-${var.environment}-rt-public" }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

###############################################################################
# 2 ▸ Storage layer – raw data & model-artifact buckets
#
#    Security defaults baked in:
#    • Block public access     – no accidental open buckets
#    • Versioning enabled      – protection against deletes / ransomware
#    • Server-side encryption  – AES-256 at rest (zero extra cost)
###############################################################################

# Helper local to DRY bucket names
locals {
  raw_bucket_name       = "fraud-raw-${var.bucket_suffix}"
  artifacts_bucket_name = "fraud-artifacts-${var.bucket_suffix}"
}

# ---------------- Raw bucket ----------------
#trivy:ignore:AVD-AWS-0089   # skip bucket-logging for now
#tfsec:ignore:aws-s3-enable-bucket-logging   # opting out of logging in sandbox
resource "aws_s3_bucket" "raw" {
  bucket = local.raw_bucket_name
}

# Versioning keeps every object revision (cheap in dev, priceless in prod)
resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

# Default encryption – AWS-managed keys (SSE-S3) cost £0
#-t-f-s-ec:ignore:aws-s3-encryption-customer-key
resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
  }
}

# Block EVERYTHING public, including ACLs
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------- Artifacts bucket (copy-paste w/ different name) -----------
#trivy:ignore:AVD-AWS-0089   # skip bucket-logging for now
#tfsec:ignore:aws-s3-enable-bucket-logging   # opting out of logging in sandbox
resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket_name
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

# Default encryption – AWS-managed keys (SSE-S3) cost £0 [using aws/s3 now]
#-t-f-sec:ignore:aws-s3-encryption-customer-key
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# 3 ▸ IAM – strictly least-privileged role for future SageMaker jobs
###############################################################################

# Trust policy: SageMaker service can *assume* this role
data "aws_iam_policy_document" "sagemaker_trust" {
  statement {
    sid = "SageMakerAssumeRole"
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Permissions: *only* rw access to the two buckets + list
data "aws_iam_policy_document" "bucket_rw" {
  statement {
    sid     = "BucketsRW"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    #tfsec:ignore:aws-iam-no-policy-wildcards   # we accept the wildcard in this sandbox
    resources = [
      aws_s3_bucket.raw.arn,
      "${aws_s3_bucket.raw.arn}/*",
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }
}

resource "aws_iam_role" "sagemaker_rw" {
  name               = "fraud-${var.environment}-sagemaker-rw"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_trust.json
}

resource "aws_iam_role_policy" "sagemaker_rw_inline" {
  role   = aws_iam_role.sagemaker_rw.id
  policy = data.aws_iam_policy_document.bucket_rw.json
}
