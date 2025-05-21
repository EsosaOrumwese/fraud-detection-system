###############################################################################
#  Budget guard-rail + two-tier e-mail alerts
#
#  • SNS topic lives in *same* region as stack (eu-west-2) – cheaper, simpler
#  • Topic policy allows ONLY Budgets + CloudWatch services to publish
#  • Two percentage thresholds (60 %, 90 %) give early + late warning
#    [add in 30% if you like]
###############################################################################

# ─────────────────────────────────────────────────────────────────────────────
# 1 ▸  SNS topic + e-mail subscription
# ----------------------------------------------------------------------------

resource "aws_sns_topic" "budget_alerts" {
  name              = "fraud-budget-alerts"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "email_primary" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # **your e-mail** set in terraform.tfvars
}

# ─────────────────────────────────────────────────────────────────────────────
# 2 ▸  Lambda stop action
# Budgets triggers a Lambda that tags live SageMaker endpoints/fleet as
# auto-stop=true and calls stop_* APIs.
# Lambda code lives inline (ZipFile) – tiny handler
# ----------------------------------------------------------------------------
resource "aws_lambda_function" "cost_kill_switch" {
  function_name = "fraud-cost-kill"
  role          = aws_iam_role.lambda_cost.arn
  runtime       = "python3.11"
  handler       = "index.handler"

  timeout = 30

  source_code_hash = filebase64sha256("lambda/cost_kill.zip") # created below
  filename         = "lambda/cost_kill.zip"
}

#  ➤ Subscribe the Lambda to your Budget-topic
resource "aws_sns_topic_subscription" "budget_to_lambda" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.cost_kill_switch.arn
}

#  ➤ Allow SNS to invoke the Lambda
resource "aws_lambda_permission" "allow_sns_invoke" {
  statement_id  = "AllowSNSPublish"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_kill_switch.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.budget_alerts.arn
}


# ─────────────────────────────────────────────────────────────────────────────
# 3 ▸  Strict publish policy – least-privilege even for alerts
# ----------------------------------------------------------------------------
data "aws_iam_policy_document" "budget_topic_policy" {
  statement {
    sid = "AllowBudgetAndCloudWatchPublish"
    principals {
      type = "Service"
      identifiers = [
        "budgets.amazonaws.com",
        "cloudwatch.amazonaws.com"
      ]
    }
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.budget_alerts.arn]
  }
}

resource "aws_sns_topic_policy" "budget_topic_access" {
  arn    = aws_sns_topic.budget_alerts.arn
  policy = data.aws_iam_policy_document.budget_topic_policy.json
}

# IAM role – allow SageMaker stop + logs
resource "aws_iam_role" "lambda_cost" {
  name               = "fraud-lambda-cost"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}
resource "aws_iam_role_policy" "lambda_cost_inline" {
  role = aws_iam_role.lambda_cost.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "sagemaker:ListEndpoints",
        "sagemaker:StopEndpoint",
        "sagemaker:ListNotebookInstances",
        "sagemaker:StopNotebookInstance"
      ],
      Resource = "*"
      }, {
      Effect   = "Allow",
      Action   = ["logs:*"],
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# 4 ▸  Monthly AWS Budget – three notification blocks + 1 that calls Lambda
# ----------------------------------------------------------------------------
resource "aws_budgets_budget" "sandbox_monthly" {
  name        = "fraud-sbx-monthly"
  budget_type = "COST"
  time_unit   = "MONTHLY"

  # Limit is expressed in *display* currency (GBP)
  limit_amount = tostring(var.monthly_budget_gbp) # 40
  limit_unit   = "GBP"

  # 30 % early-warning
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 30
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # 60 % early-warning
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 60
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # 90 % late-warning
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 90
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # A third notification (95 %) that calls Lambda
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 95
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }
}
