# AWS Bedrock Integration - Quick Start Guide

## Overview

Project Aura now includes a production-ready AWS Bedrock integration for Claude API access with comprehensive cost controls, rate limiting, and secure credential management.

**Status:** ✅ Implemented (mock mode runs locally; AWS mode is used when boto3 and AWS credentials are available)

**Components:**

- `src/config/bedrock_config.py` - Environment-based configuration
- `src/services/bedrock_llm_service.py` - Main service with cost controls
- `tests/test_bedrock_service.py` - Comprehensive test suite
- `docs/integrations/BEDROCK_INTEGRATION_PLAN.md` - Original design record

---

## Quick Start (Local Testing)

### 1. Test Configuration

```bash
# Test the configuration module
python3 src/config/bedrock_config.py
```

Expected output:

```bash
Project Aura - Bedrock Configuration
==================================================

Current Environment: development
Configuration:
  Region: us-east-1
  Primary Model: auto
  Daily Budget: $10.00
  Monthly Budget: $100.00
  Rate Limit: 5/min
```

### 2. Test LLM Service (Mock Mode)

```bash
# Test the service with mock responses (no AWS required)
python3 src/services/bedrock_llm_service.py
```

This will demonstrate:

- Service initialization
- Mock LLM invocation
- Token counting
- Cost calculation
- Spend tracking

### 3. Use in Your Code

```python
from src.services.bedrock_llm_service import create_llm_service

# Create service (auto-detects mock/AWS mode)
llm_service = create_llm_service()

# Invoke model
result = llm_service.invoke_model(
    prompt="Analyze this code for security vulnerabilities...",
    agent="ReviewerAgent",
    system_prompt="You are a security expert.",
    max_tokens=2000,
    temperature=0.7
)

# Access results
print(f"Response: {result['response']}")
print(f"Cost: ${result['cost_usd']:.6f}")
print(f"Tokens: {result['input_tokens']} + {result['output_tokens']}")

# Check spending
summary = llm_service.get_spend_summary()
print(f"Daily spend: ${summary['daily_spend']:.2f} / ${summary['daily_budget']:.2f}")
```

---

## Environment Configuration

Set the `AURA_ENV` environment variable to control configuration:

```bash
# Development ($10/day budget)
export AURA_ENV=development

# QA ($25/day budget)
export AURA_ENV=qa

# Staging ($50/day budget)
export AURA_ENV=staging

# Production ($100/day budget)
export AURA_ENV=production
```

### Model Selection

Models are chosen per ADR-015 tier, not per environment: **fast** (Haiku family), **accurate** (Sonnet family), **maximum** (Opus family). Each tier's model resolves in this order:

1. The environment's Secrets Manager secret, `aura/<env>/bedrock-config`
2. The environment's entry in `src/config/bedrock_config.py`
3. The default, `auto`

- **`auto`**: at startup in AWS mode, the service calls `ListFoundationModels` and `ListInferenceProfiles` in the deployment region and picks the newest ACTIVE, priced Claude model for each tier, using an inference profile ID when the model is not available on-demand. In MOCK mode no AWS calls are made and `auto` resolves to labels only.
- **Pinning**: an explicitly configured model ID always wins. Set `model_id_fast`, `model_id_accurate`, `model_id_maximum`, `model_id_primary`, and `model_id_fallback` in the secret, with `model_pricing` for models not in the built-in pricing table and `prompt_cache_models` for models that accept prompt-cache breakpoints. A configured model with no known pricing is refused at startup and the tier keeps its fallback.
- **Upgrades**: follow ADR-088 (Continuous Model Assurance): evaluate, review the shadow report, get human approval, then change the configuration with the previous value stored for rollback.
- **Request adaptation**: newer models (Sonnet 5+, Opus 4.7+, Fable/Mythos) reject a non-default `temperature`, and some reject a forced `tool_choice`. The service omits or adapts these for known models; on a 400 error naming the field it retries without it and remembers that for the model.
- **Prompt caching**: tool-use conversations add cache breakpoints for models in `prompt_cache_models`. Cache writes are priced at 1.25x and cache reads at 0.1x the input price.

---

## Cost Controls

### Budget Limits

| Environment | Daily Budget | Monthly Budget |
|-------------|--------------|----------------|
| Development | $10 | $100 |
| QA | $25 | $250 |
| Staging | $50 | $500 |
| Production | $100 | $2,000 |

### Rate Limits

| Environment | Per Minute | Per Hour | Per Day |
|-------------|------------|----------|---------|
| Development | 5 | 100 | 500 |
| QA | 10 | 200 | 1,000 |
| Staging | 10 | 300 | 2,000 |
| Production | 20 | 500 | 5,000 |

### What Happens When Limits Are Exceeded?

**Budget exceeded:**

```python
BudgetExceededError: Budget exceeded.
Daily: $10.50/$10.00, Monthly: $85.00/$100.00
```

**Rate limit exceeded:**

```python
RateLimitExceededError: Rate limit exceeded.
Please retry later or increase limits in config.
```

---

## AWS Deployment

### Prerequisites

1. **Enable AWS Bedrock**

   ```bash
   # Go to AWS Console → Bedrock → Model access
   # Request access to current Anthropic Claude models in each family
   # used by the tiers: Haiku (fast), Sonnet (accurate), Opus (maximum)
   ```

2. **Install boto3**

   ```bash
   pip install boto3
   ```

3. **Create IAM Role**

   ```bash
   # See docs/integrations/BEDROCK_INTEGRATION_PLAN.md section 2.3
   # Create role: AuraBedrockServiceRole
   # Attach policy with bedrock:InvokeModel (on foundation-model and
   # inference-profile resources), bedrock:ListFoundationModels, and
   # bedrock:ListInferenceProfiles
   ```

4. **Create DynamoDB Table**

   ```bash
   # Table name: aura-ddb-<env>-llm-costs (see cost_table_name in src/config/bedrock_config.py)
   # See docs/integrations/BEDROCK_INTEGRATION_PLAN.md section 4.1
   ```

5. **Configure AWS Credentials**

   ```bash
   aws configure
   # Or use IAM role when running on EC2/ECS/Lambda
   ```

### Test AWS Mode

```python
from src.services.bedrock_llm_service import BedrockLLMService, BedrockMode

# Force AWS mode (will fail gracefully if not configured)
service = BedrockLLMService(mode=BedrockMode.AWS, environment="development")

# Test with real API
result = service.invoke_model(
    prompt="Say 'test successful' and nothing else.",
    agent="IntegrationTest",
    max_tokens=20,
    use_fallback=True  # Use the configured fallback model
)

print(f"Response: {result['response']}")
print(f"Real API cost: ${result['cost_usd']:.6f}")
```

---

## Cost Optimization Tips

### 1. Use Model Fallback for Simple Tasks

```python
# Complex task → primary model
result = llm_service.invoke_model(
    prompt="Complex security analysis...",
    agent="ReviewerAgent",
    use_fallback=False
)

# Simple task → fallback model
result = llm_service.invoke_model(
    prompt="Format this string...",
    agent="UtilityAgent",
    use_fallback=True
)
```

The cost difference depends on which models are resolved for the primary and fallback slots; see `MODEL_PRICING` in `src/config/bedrock_config.py` and any `model_pricing` entries in the secret.

### 2. Enable Caching

```python
# Identical requests are cached (24-hour TTL)
result1 = llm_service.invoke_model(
    prompt="What is SQL injection?",
    agent="TrainingAgent",
    cache_enabled=True  # Cost: $0.001
)

result2 = llm_service.invoke_model(
    prompt="What is SQL injection?",  # Identical
    agent="TrainingAgent",
    cache_enabled=True  # Cost: $0.000 (cached!)
)

assert result2['cached'] == True
assert result2['cost_usd'] == 0.0
```

### 3. Set Token Limits

```python
# Prevent runaway costs
result = llm_service.invoke_model(
    prompt="Explain...",
    agent="ExplainerAgent",
    max_tokens=500  # Limit output to 500 tokens
)
```

### 4. Monitor Spending

```python
# Check spend regularly
summary = llm_service.get_spend_summary()

if summary['daily_percent'] > 80:
    print("⚠️  Warning: 80% of daily budget used!")
    # Take action: reduce requests, switch to Haiku, etc.
```

---

## Integration with Orchestrator

> **Already integrated.** `src/agents/agent_orchestrator.py:2782` and the individual agents (for example `src/agents/coder_agent.py:535`) already obtain the service through `create_llm_service()`. The snippet below is an illustrative pattern, not the current code.

To integrate with an orchestrator-style class:

```python
# In src/agents/agent_orchestrator.py

from src.services.bedrock_llm_service import create_llm_service, BudgetExceededError, RateLimitExceededError

class System2Orchestrator:
    def __init__(self):
        # ... existing init code ...

        # Add LLM service
        self.llm_service = create_llm_service()

    def _call_llm(self, prompt: str, agent_name: str, system_prompt: str = None) -> str:
        """Unified LLM call with error handling."""
        try:
            result = self.llm_service.invoke_model(
                prompt=prompt,
                agent=agent_name,
                system_prompt=system_prompt,
                max_tokens=4096,
                temperature=0.7
            )

            # Log to monitor
            if hasattr(self, 'monitor'):
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
            return self._call_llm(prompt, agent_name, system_prompt)  # Retry

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"ERROR: LLM request failed. {e}"
```

Hardcoded LLM responses are replaced with:

```python
# OLD (hardcoded mock)
plan_text = "Mock plan: 1. Fix input validation..."

# NEW (real LLM)
plan_text = self._call_llm(
    prompt=f"Create a security remediation plan for: {issue_description}",
    agent_name="PlannerAgent",
    system_prompt="You are a security expert creating remediation plans."
)
```

---

## Monitoring & Alerts

### View Spending

```python
from src.services.bedrock_llm_service import create_llm_service

service = create_llm_service()
summary = service.get_spend_summary()

print(f"Daily: ${summary['daily_spend']:.2f} / ${summary['daily_budget']:.2f} ({summary['daily_percent']:.1f}%)")
print(f"Monthly: ${summary['monthly_spend']:.2f} / ${summary['monthly_budget']:.2f} ({summary['monthly_percent']:.1f}%)")
print(f"Requests today: {summary['total_requests']}")
```

### CloudWatch Metrics (AWS Mode Only)

When running in AWS mode, metrics are automatically sent to CloudWatch:

**Namespace:** `Aura/LLM`

**Metrics:**

- `TokensUsed` (by Agent, Model, Environment)
- `CostUSD` (by Agent, Model, Environment)

**Create Dashboard:**

```bash
# Go to CloudWatch → Dashboards → Create Dashboard
# Add widgets for TokensUsed and CostUSD
```

### DynamoDB Cost Logs (AWS Mode Only)

Query cost history:

```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('aura-ddb-dev-llm-costs')  # aura-ddb-<env>-llm-costs

# Get today's costs
today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
response = table.query(
    IndexName='date-index',
    KeyConditionExpression='#date = :date',
    ExpressionAttributeNames={'#date': 'date'},
    ExpressionAttributeValues={':date': today}
)

total = sum(float(item['cost_usd']) for item in response['Items'])
print(f"Total spend today: ${total:.2f}")
```

---

## Troubleshooting

### "boto3 not found"

**Problem:** Service falls back to mock mode

**Solution:**

```bash
pip install boto3
```

### "Access Denied" when calling Bedrock

**Problem:** IAM permissions not configured

**Solution:**

1. Create IAM role with `bedrock:InvokeModel` (including inference-profile resources), `bedrock:ListFoundationModels`, and `bedrock:ListInferenceProfiles` permissions
2. Attach role to EC2/ECS/Lambda instance
3. OR configure AWS credentials: `aws configure`

### "Model not found"

**Problem:** Bedrock model access not granted

**Solution:**

1. Go to AWS Console → Bedrock → Model access
2. Request access to Claude models (can take a few minutes)

### "Budget exceeded" immediately

**Problem:** DynamoDB has stale data from previous day

**Solution:**

```python
# Clear in-memory cache
service.daily_spend = 0.0

# Or wait for daily rollover (midnight UTC)
```

### "Rate limit exceeded" too quickly

**Problem:** Rate limits too low for your use case

**Solution:**
Edit `src/config/bedrock_config.py`:

```python
BEDROCK_CONFIG[Environment.DEV] = {
    # ...
    'max_requests_per_minute': 10,  # Increase from 5
    'max_requests_per_hour': 200,   # Increase from 100
}
```

---

## Testing

### Run Unit Tests

```bash
# Install pytest
pip install pytest

# Run tests
python -m pytest tests/test_bedrock_service.py -v
```

### Run Integration Tests (Requires AWS)

```bash
# Set flag to enable integration tests
export RUN_INTEGRATION_TESTS=1

# Run with AWS credentials configured
python -m pytest tests/test_bedrock_service.py::TestIntegration -v
```

---

## Security Best Practices

✅ **Implemented:**

- IAM roles (no hardcoded API keys)
- AWS Secrets Manager integration
- Least privilege policies
- Budget enforcement (prevents runaway costs)
- Rate limiting (prevents abuse)
- CloudTrail auditing (all API calls logged)
- Encrypted DynamoDB storage

✅ **Compliant with:**

- SOX (full audit trail)
- CMMC (secure credential management)
- Cost governance (automated controls)

---

## Next Steps

1. **Test locally** - Run mock mode tests
2. **Enable Bedrock** - Request model access in AWS Console
3. **Deploy infrastructure** - Create DynamoDB table, IAM roles
4. **Test AWS mode** - Run integration test with real API
5. **Integrate with orchestrator** - Done (agents call `create_llm_service()`)
6. **Set up monitoring** - Configure CloudWatch dashboards
7. **Tune budgets** - Adjust limits based on actual usage

---

## Cost Estimates

**Development testing (1 week):**

- ~50 requests/day
- Avg 2000 input + 1000 output tokens
- Haiku model: $0.000875 per request
- **Total: ~$0.30/week**

**Production (full deployment):**

- ~150 requests/day (50 security issues × 3 agents)
- Avg 2000 input + 1000 output tokens
- Sonnet model: $0.0105 per request
- **Total: ~$47/month**

With caching and optimization: **$30-50/month**

---

## Support

**Documentation:**

- Design record: `docs/integrations/BEDROCK_INTEGRATION_PLAN.md`
- AWS Bedrock: <https://docs.aws.amazon.com/bedrock/>
- Claude API: <https://docs.anthropic.com/>

**Issues:**

- Check logs for detailed error messages
- Review `src/config/bedrock_config.py` for environment settings
- Verify AWS credentials: `aws sts get-caller-identity`

---

**Created:** November 2025
**Status:** Implemented
**Tested:** ✅ Mock mode (local). AWS-mode integration tests require AWS credentials (`RUN_INTEGRATION_TESTS=1`)
