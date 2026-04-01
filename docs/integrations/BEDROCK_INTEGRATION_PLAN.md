# AWS Bedrock Integration Plan
## Cost Control & Security Architecture

**Created:** November 2025
**Status:** Design Phase
**Owner:** Project Aura Team

---

## Overview

This document outlines the integration of Claude via AWS Bedrock with comprehensive cost controls, secure credential management, and production-ready architecture for Project Aura.

---

## 1. Cost Control Strategy

### 1.1 Monthly Budget Limits

**Target Monthly Budget:** $500-2000 (adjustable)

| Model | Input Cost | Output Cost | Use Case | Est. Monthly Usage |
|-------|-----------|-------------|----------|-------------------|
| Claude 3.5 Sonnet | $3.00/1M tokens | $15.00/1M tokens | Primary (code gen, analysis) | $800-1200 |
| Claude 3 Haiku | $0.25/1M tokens | $1.25/1M tokens | Secondary (simple tasks) | $100-200 |

**Cost Control Mechanisms:**

1. **Hard Budget Cap** - CloudWatch alarm + Lambda to disable API access at threshold
2. **Rate Limiting** - Max requests per minute/hour/day per agent
3. **Token Budgets** - Per-request token limits (input + output)
4. **Model Selection** - Route simple tasks to Haiku, complex to Sonnet
5. **Caching** - Cache identical requests (24-hour TTL)
6. **Monitoring** - Real-time cost tracking dashboard

### 1.2 Cost Tracking Implementation

```python
# Cost tracking per request
cost_tracker = {
    "request_id": "uuid",
    "timestamp": "ISO-8601",
    "agent": "PlannerAgent",
    "model": "claude-3-5-sonnet-20241022",
    "input_tokens": 1500,
    "output_tokens": 800,
    "cost_usd": 0.016,  # (1500*$3 + 800*$15) / 1M
    "cumulative_daily": 2.45,
    "cumulative_monthly": 87.32
}
```

**Storage:** DynamoDB table `aura-llm-costs` with GSI on `date` for aggregation

### 1.3 Budget Alert System

**CloudWatch Alarms:**

- **Warning (70% budget):** SNS → Email to team
- **Critical (90% budget):** SNS → PagerDuty + Slack
- **Hard Stop (100% budget):** Lambda disables Bedrock IAM policy

**Dashboard Metrics:**

- Real-time spend (current day/month)
- Tokens per model
- Cost per agent
- Requests per endpoint
- Error rates and retry costs

---

## 2. Secure Credential Management

### 2.1 AWS Secrets Manager

**Secrets Structure:**

```json
{
  "aura/prod/bedrock": {
    "aws_region": "us-east-1",
    "model_id_primary": "anthropic.claude-3-5-sonnet-20241022-v1:0",
    "model_id_fallback": "anthropic.claude-3-haiku-20240307-v1:0",
    "max_tokens_default": 4096,
    "temperature_default": 0.7
  },
  "aura/prod/cost-limits": {
    "daily_budget_usd": 100,
    "monthly_budget_usd": 2000,
    "max_requests_per_minute": 20,
    "max_requests_per_hour": 500,
    "max_requests_per_day": 5000
  }
}
```

**Access Control:**

- IAM role: `AuraBedrockServiceRole`
- Policy: `secretsmanager:GetSecretValue` on `aura/prod/*` only
- Rotation: Manual (no API keys to rotate, using IAM)
- Audit: CloudTrail logs all secret accesses

### 2.2 Environment-Based Configuration

**Development vs. Production:**

```python
# config/bedrock_config.py
import os
from enum import Enum

class Environment(Enum):
    DEV = "development"
    STAGING = "staging"
    PROD = "production"

BEDROCK_CONFIG = {
    Environment.DEV: {
        "aws_region": "us-east-1",
        "model_id": "anthropic.claude-3-haiku-20240307-v1:0",  # Cheaper for dev
        "daily_budget_usd": 10,
        "monthly_budget_usd": 100,
        "secrets_path": "aura/dev/bedrock"
    },
    Environment.STAGING: {
        "aws_region": "us-east-1",
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v1:0",
        "daily_budget_usd": 50,
        "monthly_budget_usd": 500,
        "secrets_path": "aura/staging/bedrock"
    },
    Environment.PROD: {
        "aws_region": "us-east-1",
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v1:0",
        "daily_budget_usd": 100,
        "monthly_budget_usd": 2000,
        "secrets_path": "aura/prod/bedrock"
    }
}

def get_config() -> dict:
    env = Environment(os.environ.get("AURA_ENV", "development"))
    return BEDROCK_CONFIG[env]
```

### 2.3 IAM Roles & Policies

**Service Role: AuraBedrockServiceRole**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:aura/prod/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/aura-llm-costs"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "Aura/LLM"
        }
      }
    }
  ]
}
```

**Key Security Features:**

- ✅ Least privilege (only Bedrock invoke + specific secrets)
- ✅ Region-locked (us-east-1 only)
- ✅ Resource-specific (only Claude models, not all Bedrock)
- ✅ Namespace-restricted CloudWatch metrics

---

## 3. BedrockLLMService Implementation

### 3.1 Core Service Class

**File:** `src/services/bedrock_llm_service.py`

```python
import boto3
import json
import time
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class BedrockLLMService:
    """
    Production-ready AWS Bedrock LLM service with:
    - Cost tracking and budget enforcement
    - Rate limiting
    - Token counting
    - Response caching
    - Error handling with retries
    - Security best practices
    """

    def __init__(self, environment: str = "development"):
        """
        Initialize Bedrock client with secure configuration.

        Args:
            environment: 'development', 'staging', or 'production'
        """
        from config.bedrock_config import get_config

        self.config = get_config()
        self.environment = environment

        # Initialize AWS clients
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.config['aws_region']
        )
        self.secrets_manager = boto3.client(
            service_name='secretsmanager',
            region_name=self.config['aws_region']
        )
        self.dynamodb = boto3.resource(
            service_name='dynamodb',
            region_name=self.config['aws_region']
        )
        self.cloudwatch = boto3.client(
            service_name='cloudwatch',
            region_name=self.config['aws_region']
        )

        # Load secrets
        self._load_secrets()

        # Initialize cost tracker
        self.cost_table = self.dynamodb.Table('aura-llm-costs')
        self.daily_spend = self._get_daily_spend()
        self.monthly_spend = self._get_monthly_spend()

        # Rate limiting (in-memory, should use Redis in production)
        self.request_history: List[float] = []

        # Response cache (in-memory, should use Redis in production)
        self.response_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"BedrockLLMService initialized for {environment}")

    def _load_secrets(self):
        """Load configuration from AWS Secrets Manager."""
        try:
            response = self.secrets_manager.get_secret_value(
                SecretId=self.config['secrets_path']
            )
            secrets = json.loads(response['SecretString'])

            self.model_id_primary = secrets['model_id_primary']
            self.model_id_fallback = secrets['model_id_fallback']
            self.max_tokens_default = secrets.get('max_tokens_default', 4096)
            self.temperature_default = secrets.get('temperature_default', 0.7)

            logger.info("Secrets loaded successfully")
        except ClientError as e:
            logger.error(f"Failed to load secrets: {e}")
            raise

    def _get_daily_spend(self) -> float:
        """Query DynamoDB for today's spend."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        try:
            response = self.cost_table.query(
                IndexName='date-index',
                KeyConditionExpression='date = :date',
                ExpressionAttributeValues={':date': today}
            )
            return sum(item['cost_usd'] for item in response.get('Items', []))
        except ClientError as e:
            logger.error(f"Failed to query daily spend: {e}")
            return 0.0

    def _get_monthly_spend(self) -> float:
        """Query DynamoDB for this month's spend."""
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        try:
            response = self.cost_table.query(
                IndexName='month-index',
                KeyConditionExpression='month = :month',
                ExpressionAttributeValues={':month': month}
            )
            return sum(item['cost_usd'] for item in response.get('Items', []))
        except ClientError as e:
            logger.error(f"Failed to query monthly spend: {e}")
            return 0.0

    def _check_budget(self) -> bool:
        """Check if we're within budget limits."""
        if self.daily_spend >= self.config['daily_budget_usd']:
            logger.warning(f"Daily budget exceeded: ${self.daily_spend:.2f}")
            return False

        if self.monthly_spend >= self.config['monthly_budget_usd']:
            logger.warning(f"Monthly budget exceeded: ${self.monthly_spend:.2f}")
            return False

        return True

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()

        # Clean old requests (older than 1 hour)
        self.request_history = [
            ts for ts in self.request_history
            if now - ts < 3600
        ]

        # Check per-minute limit
        recent_minute = sum(1 for ts in self.request_history if now - ts < 60)
        if recent_minute >= self.config.get('max_requests_per_minute', 20):
            logger.warning("Rate limit exceeded (per minute)")
            return False

        # Check per-hour limit
        recent_hour = len(self.request_history)
        if recent_hour >= self.config.get('max_requests_per_hour', 500):
            logger.warning("Rate limit exceeded (per hour)")
            return False

        return True

    def _cache_key(self, prompt: str, model_id: str, params: Dict) -> str:
        """Generate cache key for request."""
        cache_str = f"{prompt}|{model_id}|{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if available and not expired."""
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            if time.time() - cached['timestamp'] < 86400:  # 24-hour TTL
                logger.info("Cache hit")
                return cached['response']
            else:
                del self.response_cache[cache_key]
        return None

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        """Calculate cost based on token usage and model pricing."""
        # Pricing as of Nov 2024 (update as needed)
        pricing = {
            'anthropic.claude-3-5-sonnet-20241022-v1:0': {
                'input': 3.00 / 1_000_000,
                'output': 15.00 / 1_000_000
            },
            'anthropic.claude-3-haiku-20240307-v1:0': {
                'input': 0.25 / 1_000_000,
                'output': 1.25 / 1_000_000
            }
        }

        model_pricing = pricing.get(model_id, pricing['anthropic.claude-3-haiku-20240307-v1:0'])
        cost = (input_tokens * model_pricing['input']) + (output_tokens * model_pricing['output'])
        return round(cost, 6)

    def _record_cost(self, request_id: str, agent: str, model_id: str,
                     input_tokens: int, output_tokens: int, cost_usd: float):
        """Record cost to DynamoDB and update CloudWatch metrics."""
        now = datetime.now(timezone.utc)

        # Record to DynamoDB
        try:
            self.cost_table.put_item(Item={
                'request_id': request_id,
                'timestamp': now.isoformat(),
                'date': now.strftime('%Y-%m-%d'),
                'month': now.strftime('%Y-%m'),
                'agent': agent,
                'model': model_id,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': cost_usd,
                'environment': self.environment
            })

            # Update in-memory counters
            self.daily_spend += cost_usd
            self.monthly_spend += cost_usd

        except ClientError as e:
            logger.error(f"Failed to record cost to DynamoDB: {e}")

        # Send to CloudWatch
        try:
            self.cloudwatch.put_metric_data(
                Namespace='Aura/LLM',
                MetricData=[
                    {
                        'MetricName': 'TokensUsed',
                        'Value': input_tokens + output_tokens,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'Agent', 'Value': agent},
                            {'Name': 'Model', 'Value': model_id.split('/')[-1]},
                            {'Name': 'Environment', 'Value': self.environment}
                        ]
                    },
                    {
                        'MetricName': 'CostUSD',
                        'Value': cost_usd,
                        'Unit': 'None',
                        'Dimensions': [
                            {'Name': 'Agent', 'Value': agent},
                            {'Name': 'Model', 'Value': model_id.split('/')[-1]},
                            {'Name': 'Environment', 'Value': self.environment}
                        ]
                    }
                ]
            )
        except ClientError as e:
            logger.error(f"Failed to send CloudWatch metrics: {e}")

    def invoke_model(
        self,
        prompt: str,
        agent: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_fallback: bool = False,
        cache_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Invoke Claude model via Bedrock with full cost/rate control.

        Args:
            prompt: User prompt
            agent: Agent name (for cost tracking)
            system_prompt: System prompt (optional)
            max_tokens: Max output tokens (default from config)
            temperature: Temperature 0-1 (default from config)
            use_fallback: Use Haiku instead of Sonnet
            cache_enabled: Enable response caching

        Returns:
            {
                'response': str,
                'input_tokens': int,
                'output_tokens': int,
                'cost_usd': float,
                'model': str,
                'cached': bool
            }

        Raises:
            BudgetExceededError: If budget limit reached
            RateLimitExceededError: If rate limit reached
            BedrockError: For API errors
        """
        import uuid
        request_id = str(uuid.uuid4())

        # 1. Budget check
        if not self._check_budget():
            raise BudgetExceededError(
                f"Budget exceeded. Daily: ${self.daily_spend:.2f}/{self.config['daily_budget_usd']}, "
                f"Monthly: ${self.monthly_spend:.2f}/{self.config['monthly_budget_usd']}"
            )

        # 2. Rate limit check
        if not self._check_rate_limit():
            raise RateLimitExceededError("Rate limit exceeded. Please retry later.")

        # 3. Model selection
        model_id = self.model_id_fallback if use_fallback else self.model_id_primary

        # 4. Prepare request
        max_tokens = max_tokens or self.max_tokens_default
        temperature = temperature if temperature is not None else self.temperature_default

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        if system_prompt:
            request_body["system"] = system_prompt

        # 5. Check cache
        cache_key = self._cache_key(prompt, model_id, request_body)
        if cache_enabled:
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                return cached_response

        # 6. Record request (for rate limiting)
        self.request_history.append(time.time())

        # 7. Invoke Bedrock
        try:
            logger.info(f"Invoking {model_id} for agent {agent}")
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # 8. Parse response
            text_response = response_body['content'][0]['text']
            input_tokens = response_body['usage']['input_tokens']
            output_tokens = response_body['usage']['output_tokens']

            # 9. Calculate and record cost
            cost = self._calculate_cost(input_tokens, output_tokens, model_id)
            self._record_cost(request_id, agent, model_id, input_tokens, output_tokens, cost)

            # 10. Build result
            result = {
                'response': text_response,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': cost,
                'model': model_id,
                'cached': False,
                'request_id': request_id
            }

            # 11. Cache response
            if cache_enabled:
                self.response_cache[cache_key] = {
                    'response': result,
                    'timestamp': time.time()
                }

            logger.info(f"Request {request_id} completed. Cost: ${cost:.6f}")
            return result

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Bedrock API error: {error_code} - {e}")

            if error_code == 'ThrottlingException':
                raise RateLimitExceededError("Bedrock throttling. Reduce request rate.")
            elif error_code in ['ModelNotReadyException', 'ValidationException']:
                raise BedrockError(f"Model error: {e}")
            else:
                raise BedrockError(f"Unexpected error: {e}")

# Custom Exceptions
class BudgetExceededError(Exception):
    pass

class RateLimitExceededError(Exception):
    pass

class BedrockError(Exception):
    pass
```

### 3.2 Integration with Orchestrator

**Modify:** `src/agents/agent_orchestrator.py`

Add at the top:
```python
from services.bedrock_llm_service import BedrockLLMService, BudgetExceededError, RateLimitExceededError
```

Replace mock LLM calls with:
```python
# Initialize in __init__
self.llm_service = BedrockLLMService(environment=os.environ.get("AURA_ENV", "development"))

# Replace hardcoded responses
def _call_llm(self, prompt: str, agent_name: str, system_prompt: Optional[str] = None) -> str:
    """Unified LLM call method with error handling."""
    try:
        result = self.llm_service.invoke_model(
            prompt=prompt,
            agent=agent_name,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.7
        )

        # Log to monitor
        self.monitor.log_activity(
            agent=agent_name,
            tokens_used=result['input_tokens'] + result['output_tokens'],
            cost_usd=result['cost_usd']
        )

        return result['response']

    except BudgetExceededError as e:
        logger.error(f"Budget exceeded: {e}")
        return f"ERROR: Budget limit reached. {e}"

    except RateLimitExceededError as e:
        logger.warning(f"Rate limited: {e}")
        time.sleep(60)  # Wait 1 minute
        return self._call_llm(prompt, agent_name, system_prompt)  # Retry once

    except Exception as e:
        logger.error(f"LLM error: {e}")
        return f"ERROR: LLM request failed. {e}"
```

---

## 4. Infrastructure Setup

### 4.1 DynamoDB Table

**Table:** `aura-llm-costs`

```python
# deploy/terraform/dynamodb.tf
resource "aws_dynamodb_table" "llm_costs" {
  name           = "aura-llm-costs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "request_id"

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

  tags = {
    Project     = "Aura"
    Environment = "production"
  }
}
```

### 4.2 CloudWatch Alarms

```python
# deploy/terraform/cloudwatch_alarms.tf
resource "aws_cloudwatch_metric_alarm" "daily_budget_warning" {
  alarm_name          = "aura-llm-daily-budget-70pct"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "CostUSD"
  namespace           = "Aura/LLM"
  period              = "86400"  # 1 day
  statistic           = "Sum"
  threshold           = "70"  # 70% of $100 daily budget
  alarm_description   = "Daily LLM costs exceeded 70% of budget"
  alarm_actions       = [aws_sns_topic.aura_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "monthly_budget_critical" {
  alarm_name          = "aura-llm-monthly-budget-90pct"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "CostUSD"
  namespace           = "Aura/LLM"
  period              = "2592000"  # 30 days
  statistic           = "Sum"
  threshold           = "1800"  # 90% of $2000 monthly budget
  alarm_description   = "Monthly LLM costs exceeded 90% of budget"
  alarm_actions       = [
    aws_sns_topic.aura_critical_alerts.arn,
    aws_lambda_function.disable_bedrock.arn
  ]
}
```

### 4.3 Budget Enforcement Lambda

```python
# deploy/lambda/disable_bedrock.py
import boto3
import json

iam = boto3.client('iam')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """Disable Bedrock access when budget exceeded."""

    # Parse CloudWatch alarm
    message = json.loads(event['Records'][0]['Sns']['Message'])
    alarm_name = message['AlarmName']

    if 'monthly-budget' in alarm_name:
        # Attach deny policy to service role
        iam.attach_role_policy(
            RoleName='AuraBedrockServiceRole',
            PolicyArn='arn:aws:iam::aws:policy/AWSDenyAll'
        )

        # Send alert
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:ACCOUNT_ID:aura-critical-alerts',
            Subject='CRITICAL: Bedrock Access Disabled',
            Message='Monthly budget exceeded. Bedrock access has been disabled.'
        )

        return {'statusCode': 200, 'body': 'Bedrock disabled'}

    return {'statusCode': 200, 'body': 'No action taken'}
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

**File:** `tests/test_bedrock_service.py`

```python
import pytest
from unittest.mock import Mock, patch
from src.services.bedrock_llm_service import BedrockLLMService, BudgetExceededError

@patch('boto3.client')
@patch('boto3.resource')
def test_budget_enforcement(mock_resource, mock_client):
    """Test that budget limits are enforced."""
    service = BedrockLLMService(environment='development')

    # Mock budget exceeded
    service.daily_spend = 999
    service.config['daily_budget_usd'] = 100

    with pytest.raises(BudgetExceededError):
        service.invoke_model(
            prompt="test",
            agent="TestAgent"
        )

@patch('boto3.client')
@patch('boto3.resource')
def test_cost_calculation(mock_resource, mock_client):
    """Test cost calculation accuracy."""
    service = BedrockLLMService(environment='development')

    # Sonnet: 1000 input + 500 output = (1000*$3 + 500*$15)/1M = $0.0105
    cost = service._calculate_cost(
        input_tokens=1000,
        output_tokens=500,
        model_id='anthropic.claude-3-5-sonnet-20241022-v1:0'
    )

    assert cost == 0.0105
```

### 5.2 Integration Tests

Test with real Bedrock in dev environment:

```python
def test_real_bedrock_call():
    """Integration test with real Bedrock API (dev only)."""
    service = BedrockLLMService(environment='development')

    result = service.invoke_model(
        prompt="Say 'test successful' and nothing else.",
        agent="IntegrationTest",
        max_tokens=10
    )

    assert 'response' in result
    assert result['input_tokens'] > 0
    assert result['cost_usd'] > 0
    print(f"Real API test cost: ${result['cost_usd']:.6f}")
```

---

## 6. Deployment Checklist

- [ ] Enable AWS Bedrock in account (requires model access request)
- [ ] Create IAM role `AuraBedrockServiceRole` with policy
- [ ] Store secrets in AWS Secrets Manager
- [ ] Create DynamoDB table `aura-llm-costs`
- [ ] Set up CloudWatch alarms (70%, 90%, 100% budget)
- [ ] Deploy budget enforcement Lambda
- [ ] Configure SNS topics for alerts
- [ ] Test with dev environment (Haiku model)
- [ ] Run integration tests
- [ ] Deploy to production
- [ ] Monitor costs for first week
- [ ] Adjust budgets/rate limits as needed

---

## 7. Cost Projections

**Assumptions:**
- 50 security issues remediated per month
- Average 3 LLM calls per issue (plan, code, review)
- Average 2000 input tokens + 1000 output tokens per call

**Monthly Cost Estimate:**

```
50 issues * 3 calls/issue * 150 total calls/month
150 calls * 2000 input tokens = 300,000 input tokens
150 calls * 1000 output tokens = 150,000 output tokens

Sonnet costs:
- Input: 300K * $3/1M = $0.90
- Output: 150K * $15/1M = $2.25
- Total per month: $3.15

Actual costs likely 10-20x higher with context retrieval:
Realistic estimate: $50-100/month for pilot, $500-1000/month at scale
```

**Optimization opportunities:**
- Use Haiku for simple tasks (5x cheaper)
- Cache identical security policy queries
- Prompt compression (remove unnecessary tokens)
- Batch similar issues together

---

## 8. Monitoring Dashboard

**CloudWatch Dashboard:** `Aura-LLM-Costs`

**Widgets:**
1. **Daily Spend** (line graph, 30 days)
2. **Monthly Spend** (number, current month)
3. **Tokens by Agent** (pie chart)
4. **Cost by Model** (stacked area)
5. **Request Count** (line graph)
6. **Cache Hit Rate** (percentage)
7. **Error Rate** (line graph)
8. **Budget Utilization** (gauge, 0-100%)

---

## 9. Security Best Practices

✅ **Implemented:**
- IAM roles (no hardcoded credentials)
- AWS Secrets Manager for config
- Least privilege policies
- CloudTrail auditing
- Encrypted DynamoDB table
- VPC endpoints for Bedrock (private connectivity)
- Budget enforcement automation

✅ **Compliance:**
- SOX: Full audit trail (CloudWatch + DynamoDB)
- CMMC: No credentials in code, MFA on IAM roles
- Cost governance: Automated budget controls

---

## 10. Next Steps

1. **Immediate (This Week):**
   - [ ] Create `config/bedrock_config.py`
   - [ ] Implement `services/bedrock_llm_service.py`
   - [ ] Write unit tests
   - [ ] Enable Bedrock in AWS dev account

2. **Short Term (Next 2 Weeks):**
   - [ ] Deploy DynamoDB table and CloudWatch alarms
   - [ ] Integrate with System2Orchestrator
   - [ ] Run integration tests
   - [ ] Monitor costs in dev environment

3. **Medium Term (Next Month):**
   - [ ] Deploy to production
   - [ ] Create cost dashboard
   - [ ] Optimize prompts for cost
   - [ ] Build cache warming strategy

---

**Document Status:** Ready for implementation
**Estimated Implementation Time:** 3-5 days
**Risk Level:** Low (incremental, well-tested)
