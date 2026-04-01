# Project Aura - Terraform Infrastructure
# Automated deployment for AWS Bedrock integration

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Aura"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production"
  }
}

variable "alert_email" {
  description = "Email address for budget alerts"
  type        = string
}

variable "daily_budget_usd" {
  description = "Daily LLM budget in USD"
  type        = number
  default     = 10.0
}

variable "monthly_budget_usd" {
  description = "Monthly LLM budget in USD"
  type        = number
  default     = 100.0
}

# Data sources
data "aws_caller_identity" "current" {}

# Outputs
output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "service_role_arn" {
  value = aws_iam_role.aura_service_role.arn
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.llm_costs.name
}

output "sns_topic_arn" {
  value = aws_sns_topic.budget_alerts.arn
}

output "secrets_arns" {
  value = {
    bedrock_config = aws_secretsmanager_secret.bedrock_config.arn
  }
}

# IAM Role for Aura Service
resource "aws_iam_role" "aura_service_role" {
  name               = "AuraBedrockServiceRole-${var.environment}"
  description        = "Service role for Project Aura Bedrock integration"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",
            "ecs-tasks.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# IAM Policy for Bedrock Access
resource "aws_iam_role_policy" "aura_bedrock_policy" {
  name = "AuraBedrockPolicy"
  role = aws_iam_role.aura_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v1:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      },
      {
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:aura/${var.environment}/*"
      },
      {
        Sid    = "DynamoDBCostTracking"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.llm_costs.arn,
          "${aws_dynamodb_table.llm_costs.arn}/index/*"
        ]
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "Aura/LLM"
          }
        }
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/aura/*"
      }
    ]
  })
}

# Instance Profile for EC2
resource "aws_iam_instance_profile" "aura_instance_profile" {
  name = "AuraBedrockInstanceProfile-${var.environment}"
  role = aws_iam_role.aura_service_role.name
}

# DynamoDB Table for Cost Tracking
resource "aws_dynamodb_table" "llm_costs" {
  name         = "aura-llm-costs-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  attribute {
    name = "month"
    type = "S"
  }

  global_secondary_index {
    name            = "date-index"
    hash_key        = "date"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "month-index"
    hash_key        = "month"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "Aura LLM Cost Tracking"
  }
}

# Secrets Manager for Configuration
resource "aws_secretsmanager_secret" "bedrock_config" {
  name        = "aura/${var.environment}/bedrock"
  description = "Bedrock configuration for Project Aura ${var.environment}"

  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "bedrock_config" {
  secret_id = aws_secretsmanager_secret.bedrock_config.id

  secret_string = jsonencode({
    model_id_primary    = var.environment == "development" ? "anthropic.claude-3-haiku-20240307-v1:0" : "anthropic.claude-3-5-sonnet-20241022-v1:0"
    model_id_fallback   = "anthropic.claude-3-haiku-20240307-v1:0"
    max_tokens_default  = 4096
    temperature_default = 0.7
  })
}

# SNS Topic for Budget Alerts
resource "aws_sns_topic" "budget_alerts" {
  name         = "aura-budget-alerts-${var.environment}"
  display_name = "Aura LLM Budget Alerts"
}

resource "aws_sns_topic_subscription" "budget_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "daily_budget_warning" {
  alarm_name          = "aura-daily-budget-warning-${var.environment}"
  alarm_description   = "Daily LLM costs exceeded 70% of budget"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CostUSD"
  namespace           = "Aura/LLM"
  period              = 86400
  statistic           = "Sum"
  threshold           = var.daily_budget_usd * 0.7
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]

  dimensions = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "daily_budget_critical" {
  alarm_name          = "aura-daily-budget-critical-${var.environment}"
  alarm_description   = "Daily LLM costs exceeded 90% of budget"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CostUSD"
  namespace           = "Aura/LLM"
  period              = 86400
  statistic           = "Sum"
  threshold           = var.daily_budget_usd * 0.9
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]

  dimensions = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "monthly_budget_warning" {
  alarm_name          = "aura-monthly-budget-warning-${var.environment}"
  alarm_description   = "Monthly LLM costs exceeded 80% of budget"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CostUSD"
  namespace           = "Aura/LLM"
  period              = 2592000
  statistic           = "Sum"
  threshold           = var.monthly_budget_usd * 0.8
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]

  dimensions = {
    Environment = var.environment
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "aura_logs" {
  name              = "/aws/aura/${var.environment}"
  retention_in_days = var.environment == "production" ? 90 : 7
}
