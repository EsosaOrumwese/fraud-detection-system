###############################################################################
#  Real-time Billing alarm (≈ <2 h latency) at **100 % of budget (40 GBP)**
#
#  • Billing metrics exist ONLY in us-east-1 ⇒ separate provider alias
#  • Uses same SNS topic, so one confirmation step covers all alerts
###############################################################################

# Provider alias in the global billing region
provider "aws" {
  alias  = "us"
  region = "us-east-1"
}

resource "aws_cloudwatch_metric_alarm" "billing_100pct" {
  provider = aws.us # important!

  alarm_name          = "fraud-sbx-billing-40gbp"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  period              = 21600
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  statistic           = "Maximum"
  threshold           = var.monthly_budget_gbp # same 40 GBP
  dimensions = {
    Currency = "GBP"
  }

  alarm_actions = [aws_sns_topic.budget_alerts.arn]
}
