locals {
  default_tags = {
    Environment = local.env
    Owner       = "SRE"
    Terraform   = "true"
  }
}

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.9.0"
    }
  }
}

provider "aws" {
  alias  = "poc"
  region = "cn-northwest-1"

  assume_role {
    duration     = "1h"
    role_arn     = "arn:aws-cn:iam::108301912601:role/terraform"
    session_name = "iam"
  }

  default_tags {
    tags = local.default_tags
  }
}

resource "aws_budgets_budget" "daily_budget" {
  name         = "DailyBudget"
  budget_type  = "COST"
  limit_amount = "300"
  limit_unit   = "CNY"
  time_unit    = "DAILY"

  cost_types {
    include_tax          = true
    include_subscription = true
    use_blended          = false
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "ACTUAL"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = ["qhuang4@partner.jaguarlandrover.com"]
  }
}

resource "aws_cloudwatch_metric_alarm" "high_costs_alarm" {
  alarm_name          = "HighCostsAlarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = "300"
  alarm_description   = "This alarm triggers if the daily estimated charges exceed ¥300."
  actions_enabled     = true
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    Currency = "CNY"
  }
}

resource "aws_sns_topic" "alerts" {
  name = "billing-alerts"
}

resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "qhuang4@partner.jaguarlandrover.com"
}

# 创建IAM角色供Lambda使用
resource "aws_iam_role" "lambda_role" {
  name = "services_cleanup_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_services_full_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws-cn:iam::aws:policy/AdministratorAccess"
}

# Define Lambda function
resource "aws_lambda_function" "services_cleanup" {
  filename      = "lambda_function.zip"  
  function_name = "services_cleanup_function"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.8"
  timeout       = 10

}

# Define CloudWatch Event rule to trigger Lambda func per day
resource "aws_cloudwatch_event_rule" "every_day" {
  name                = "check-services-every-day"
  description         = "Fires every day"
  schedule_expression = "cron(00 11 * * ? *)"
}

resource "aws_cloudwatch_event_target" "check_services_every_day" {
  rule      = aws_cloudwatch_event_rule.every_day.name
  target_id = "lambda"
  arn       = aws_lambda_function.services_cleanup.arn
}

# Enable CloudWatch Events to call Lambda func
resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.services_cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_day.arn
}