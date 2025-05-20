###############################################################################
# Surface key IDs & names so apps / scripts can read them without parsing state
###############################################################################

output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_id" { value = aws_subnet.public_a.id }
output "raw_bucket_name" { value = aws_s3_bucket.raw.id }
output "artifacts_bucket" { value = aws_s3_bucket.artifacts.id }
output "sagemaker_role_arn" { value = aws_iam_role.sagemaker_rw.arn }