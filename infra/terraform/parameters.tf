###############################################################################
# Surface bucket names via SSM Parameter Store
###############################################################################
resource "aws_ssm_parameter" "raw_bucket_name" {
  name        = "/fraud/raw_bucket_name"
  description = "S3 bucket for raw synthetic transactions"
  type        = "SecureString"
  value       = aws_s3_bucket.raw.id
  tags = {
    anc = "infra"
  }
}

resource "aws_ssm_parameter" "artifacts_bucket_name" {
  name        = "/fraud/artifacts_bucket_name"
  description = "S3 bucket for model artifacts"
  type        = "SecureString"
  value       = aws_s3_bucket.artifacts.id
  tags = {
    anc = "infra"
  }
}