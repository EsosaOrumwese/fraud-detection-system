###############################################################################
# Surface raw bucket name via SSM Parameter Store
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