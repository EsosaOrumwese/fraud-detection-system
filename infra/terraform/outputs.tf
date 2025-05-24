###############################################################################
# Surface key IDs & names so apps / scripts can read them without parsing state
###############################################################################

output "vpc_id" {
  description = "The ID of the main VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "The subnet ID for the public subnet in AZ-a"
  value       = aws_subnet.public_a.id
}

output "raw_bucket_name" {
  description = "Name of the S3 bucket for raw data"
  value       = aws_s3_bucket.raw.id
}

output "artifacts_bucket_name" {
  description = "Name of the S3 bucket for model artifacts"
  value       = aws_s3_bucket.artifacts.id
}

output "sagemaker_role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_rw.arn
}

output "github_cost_role_arn" {
  description = "GitHub cost role arn"
  value       = aws_iam_role.github_cost_reader.arn
}