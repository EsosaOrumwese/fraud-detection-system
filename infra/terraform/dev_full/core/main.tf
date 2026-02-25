provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  selected_azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  common_tags = merge(
    {
      project = var.project
      env     = var.environment
      owner   = var.owner
    },
    var.additional_tags
  )

  core_buckets = {
    object_store = var.s3_object_store_bucket
    evidence     = var.s3_evidence_bucket
    artifacts    = var.s3_artifacts_bucket
  }

  public_subnet_map = {
    for idx, cidr in var.public_subnet_cidrs :
    format("public_%02d", idx + 1) => {
      cidr = cidr
      az   = local.selected_azs[idx]
    }
  }

  private_subnet_map = {
    for idx, cidr in var.private_subnet_cidrs :
    format("private_%02d", idx + 1) => {
      cidr = cidr
      az   = local.selected_azs[idx]
    }
  }
}

resource "aws_vpc" "core" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name          = "${var.name_prefix}-vpc"
    fp_stack      = "core"
    fp_vpc_role   = "platform_base"
    fp_managed_by = "terraform"
  })
}

resource "aws_internet_gateway" "core" {
  vpc_id = aws_vpc.core.id
  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-igw"
  })
}

resource "aws_subnet" "public" {
  for_each = local.public_subnet_map

  vpc_id                  = aws_vpc.core.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name                     = "${var.name_prefix}-${each.key}"
    "kubernetes.io/role/elb" = "1"
    fp_subnet_tier           = "public"
  })
}

resource "aws_subnet" "private" {
  for_each = local.private_subnet_map

  vpc_id            = aws_vpc.core.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = merge(local.common_tags, {
    Name                              = "${var.name_prefix}-${each.key}"
    "kubernetes.io/role/internal-elb" = "1"
    fp_subnet_tier                    = "private"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.core.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.core.id
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.core.id
  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-private-rt"
  })
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "msk_clients" {
  name        = "${var.name_prefix}-msk-client-sg"
  description = "MSK client baseline security group for dev_full streaming/runtime lanes"
  vpc_id      = aws_vpc.core.id

  ingress {
    description = "Kafka over TLS+IAM"
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Kafka over TLS+IAM (self-reference)"
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Kafka TLS"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Kafka TLS (self-reference)"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Permit egress for bootstrap, metadata, and managed service access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-msk-client-sg"
  })
}

resource "aws_kms_key" "platform" {
  description             = "KMS key for fraud-platform dev_full core encrypted surfaces"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-kms"
  })
}

resource "aws_kms_alias" "platform" {
  name          = var.kms_key_alias_platform
  target_key_id = aws_kms_key.platform.key_id
}

resource "aws_s3_bucket" "core" {
  for_each = local.core_buckets

  bucket        = each.value
  force_destroy = var.s3_force_destroy
  tags = merge(local.common_tags, {
    Name           = each.value
    fp_bucket_role = each.key
  })
}

resource "aws_s3_bucket_public_access_block" "core" {
  for_each = aws_s3_bucket.core

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "core" {
  for_each = aws_s3_bucket.core

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "core" {
  for_each = aws_s3_bucket.core

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.platform.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_ownership_controls" "core" {
  for_each = aws_s3_bucket.core

  bucket = each.value.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "assume_role_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_role_eks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_nodegroup_dev_full" {
  name               = var.role_eks_nodegroup_dev_full
  assume_role_policy = data.aws_iam_policy_document.assume_role_ec2.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_nodegroup_worker" {
  role       = aws_iam_role.eks_nodegroup_dev_full.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_nodegroup_ecr" {
  role       = aws_iam_role.eks_nodegroup_dev_full.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_nodegroup_cni" {
  role       = aws_iam_role.eks_nodegroup_dev_full.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role" "eks_runtime_platform_base" {
  name               = var.role_eks_runtime_platform_base
  assume_role_policy = data.aws_iam_policy_document.assume_role_eks.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_runtime_cluster_policy" {
  role       = aws_iam_role.eks_runtime_platform_base.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
