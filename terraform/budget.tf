# AWS Budget for cost monitoring
# This is optional and can be disabled by setting enable_budget = false

data "aws_caller_identity" "current" {}

resource "aws_budgets_budget" "coldvault" {
  count = var.enable_budget && var.budget_email != "" ? 1 : 0

  name              = "coldvault-monthly-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.budget_limit)
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type           = "ACTUAL"
    subscriber_email_addresses  = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type           = "ACTUAL"
    subscriber_email_addresses  = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type           = "ACTUAL"
    subscriber_email_addresses  = [var.budget_email]
  }
}
