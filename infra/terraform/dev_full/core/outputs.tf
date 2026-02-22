output "vpc_id" {
  value = aws_vpc.core.id
}

output "public_subnet_ids" {
  value = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  value = [for subnet in aws_subnet.private : subnet.id]
}

output "msk_client_subnet_ids" {
  value = [for subnet in aws_subnet.private : subnet.id]
}

output "msk_security_group_id" {
  value = aws_security_group.msk_clients.id
}

output "kms_key_arn" {
  value = aws_kms_key.platform.arn
}

output "kms_key_alias" {
  value = aws_kms_alias.platform.name
}

output "s3_bucket_names" {
  value = {
    object_store = aws_s3_bucket.core["object_store"].bucket
    evidence     = aws_s3_bucket.core["evidence"].bucket
    artifacts    = aws_s3_bucket.core["artifacts"].bucket
  }
}

output "role_eks_nodegroup_dev_full_arn" {
  value = aws_iam_role.eks_nodegroup_dev_full.arn
}

output "role_eks_runtime_platform_base_arn" {
  value = aws_iam_role.eks_runtime_platform_base.arn
}

output "core_handle_materialization" {
  value = {
    S3_OBJECT_STORE_BUCKET         = aws_s3_bucket.core["object_store"].bucket
    S3_EVIDENCE_BUCKET             = aws_s3_bucket.core["evidence"].bucket
    S3_ARTIFACTS_BUCKET            = aws_s3_bucket.core["artifacts"].bucket
    KMS_KEY_ALIAS_PLATFORM         = aws_kms_alias.platform.name
    ROLE_EKS_NODEGROUP_DEV_FULL    = aws_iam_role.eks_nodegroup_dev_full.arn
    ROLE_EKS_RUNTIME_PLATFORM_BASE = aws_iam_role.eks_runtime_platform_base.arn
    MSK_CLIENT_SUBNET_IDS          = [for subnet in aws_subnet.private : subnet.id]
    MSK_SECURITY_GROUP_ID          = aws_security_group.msk_clients.id
  }
}

