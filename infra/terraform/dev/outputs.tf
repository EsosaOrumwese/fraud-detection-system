output "vpc_id" { value = module.vpc.vpc_id }
output "public_subnet_ids" { value = module.vpc.public_subnets }
output "raw_bucket" { value = aws_s3_bucket.data["${var.bucket_prefix}-dl-raw"].bucket }
output "artifacts_bucket" { value = aws_s3_bucket.data["${var.bucket_prefix}-model-artifacts"].bucket }
output "pipeline_role_arn" { value = aws_iam_role.pipeline.arn }
