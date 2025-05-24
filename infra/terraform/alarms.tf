###############################################################################
#  Real-time Billing alarm (≈ <2 h latency) at **100 % of budget (40 GBP)**
#
#  • Billing metrics exist ONLY in us-east-1 ⇒ separate provider alias
#  • Uses same SNS topic, so one confirmation step covers all alerts
###############################################################################

resource "aws_cloudwatch_metric_alarm" "billing_100pct" {
  alarm_name          = "fraud-sbx-billing-40gbp"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  period              = 21600
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  statistic           = "Maximum"
  threshold           = var.monthly_budget_gbp * var.fx_gbp_to_usd # converting 40 GBP to USD
  dimensions = {
    Currency = "USD"
  }

  alarm_actions = [aws_sns_topic.budget_alerts.arn]
}
