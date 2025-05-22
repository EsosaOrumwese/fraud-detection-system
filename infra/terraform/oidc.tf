###############################################################################
#  GitHub Actions OIDC → AWS
#
# 1. federated identity provider: token.actions.githubusercontent.com
# 2. IAM role with trust policy limited to ONE repo (and optionally one branch)
# 3. Inline policy: Cost Explorer read-only (ce:GetCostAndUsage)
###############################################################################

variable "github_owner" {
  description = "GitHub organisation / user that owns the repo"
  type        = string
}

variable "github_repo" {
  description = "Repository name (without owner)"
  type        = string
}

# ─────────────────────────────────────────────────────────────────────────────
# 1 ▸ OIDC identity provider (one per AWS account)
#    Terraform will create it if it doesn’t exist yet.
# ----------------------------------------------------------------------------
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]
  # GitHub’s root cert
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # pragma: allowlist secret
}

# ─────────────────────────────────────────────────────────────────────────────
# 2 ▸ IAM role that GitHub workflows can assume
# ----------------------------------------------------------------------------
data "aws_iam_policy_document" "gh_oidc_trust" {
  statement {
    sid     = "AllowGithubOIDC"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Limit to pushes / workflows that come from this specific repo.
    # Tighten further by branch (e.g., ...:ref:refs/heads/main) if you like.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_owner}/${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "github_cost_reader" {
  name               = "fraud-github-cost-reader"
  assume_role_policy = data.aws_iam_policy_document.gh_oidc_trust.json
}

# ─────────────────────────────────────────────────────────────────────────────
# 3 ▸ Inline permissions – Cost Explorer read-only (and nothing else)
# ----------------------------------------------------------------------------
data "aws_iam_policy_document" "ce_read_only" {
  statement {
    effect    = "Allow"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ce_ro" {
  role   = aws_iam_role.github_cost_reader.id
  policy = data.aws_iam_policy_document.ce_read_only.json
}