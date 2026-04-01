# ADR-008: Comprehensive Cost Controls for AWS Bedrock LLM Integration

**Status:** Deployed
**Date:** 2025-11-28
**Decision Makers:** Project Aura Team

## Context

Project Aura uses Claude via AWS Bedrock for AI-powered code generation and security analysis. LLM costs can scale unpredictably:
- Claude 3.5 Sonnet: $3.00/1M input tokens, $15.00/1M output tokens
- A single complex task can consume thousands of tokens
- Runaway agents could incur significant unexpected costs

We needed a strategy to:
1. Prevent budget overruns
2. Track costs by agent and use case
3. Maintain service availability within budget
4. Optimize cost/quality tradeoffs

This decision impacts:
- Monthly infrastructure costs ($500-2000 target)
- Service availability (budget exhaustion = service down)
- Agent behavior (rate limiting affects responsiveness)
- Operational visibility (cost attribution)

## Decision

We chose a **Multi-Layer Cost Control System** with hard budget enforcement:

**Cost Control Mechanisms:**
1. **Hard Budget Cap** - CloudWatch alarm + Lambda disables API access at threshold
2. **Rate Limiting** - Max requests per minute/hour/day per agent
3. **Token Budgets** - Per-request token limits (input + output)
4. **Model Selection** - Route simple tasks to Haiku, complex to Sonnet
5. **Response Caching** - Cache identical requests (24-hour TTL)
6. **Real-Time Monitoring** - CloudWatch dashboard with cost metrics

**Budget Thresholds:**

| Level | Threshold | Action |
|-------|-----------|--------|
| Warning | 70% budget | Email notification |
| Critical | 90% budget | PagerDuty + Slack alert |
| Hard Stop | 100% budget | Lambda attaches DenyAll policy |

**Model Routing Strategy:**

| Task Type | Model | Cost/1M tokens | Use Case |
|-----------|-------|----------------|----------|
| Complex code generation | Claude 3.5 Sonnet | $18.00 (in+out avg) | Patch generation, analysis |
| Simple validation | Claude 3 Haiku | $1.50 (in+out avg) | Syntax checks, formatting |

## Alternatives Considered

### Alternative 1: No Cost Controls (Trust Users)

Rely on engineers to be cost-conscious with LLM usage.

**Pros:**
- No implementation effort
- Maximum flexibility

**Cons:**
- Single runaway agent can exhaust monthly budget
- No visibility into cost attribution
- No automatic protection
- Budget overruns likely

### Alternative 2: Fixed Token Quotas Only

Set hard token limits per request, no budget tracking.

**Pros:**
- Simple to implement
- Predictable per-request cost

**Cons:**
- Doesn't prevent many cheap requests adding up
- No aggregate budget enforcement
- Agents can still exhaust budget via volume
- No cost attribution

### Alternative 3: External Cost Management Tool

Use AWS Cost Explorer or third-party tool (Kubecost, CloudHealth).

**Pros:**
- Rich visualization
- Multi-service cost tracking

**Cons:**
- Reactive, not preventive
- Delays in cost data (hours/days)
- Cannot stop spending in real-time
- No integration with agent system

### Alternative 4: Pre-Approved Request Budget

Each request requires budget approval before execution.

**Pros:**
- Maximum control
- No unexpected costs

**Cons:**
- High latency (approval required per request)
- Operational overhead
- Not suitable for autonomous agents
- Poor user experience

## Consequences

### Positive

1. **Budget Protection**
   - Cannot exceed monthly budget (hard stop)
   - Early warning at 70% and 90%
   - Automatic enforcement (no manual intervention)

2. **Cost Visibility**
   - Per-agent cost attribution
   - Per-model cost breakdown
   - Real-time dashboard
   - Historical trends

3. **Optimization Opportunities**
   - Caching reduces redundant API calls
   - Model routing saves 5-10x on simple tasks
   - Usage patterns inform prompt optimization

4. **Audit Compliance**
   - DynamoDB table logs all LLM requests
   - CloudTrail captures cost-related actions
   - 7-year retention for SOX compliance

5. **Graceful Degradation**
   - Rate limiting smooths traffic spikes
   - Fallback to Haiku if Sonnet unavailable
   - Cache provides results during outages

### Negative

1. **Service Disruption**
   - Hard stop at 100% budget halts all LLM calls
   - Must wait for budget reset or manual override

2. **Implementation Complexity**
   - Multiple AWS services (Lambda, DynamoDB, CloudWatch, SNS)
   - Cost tracking code in service layer
   - Testing budget enforcement is tricky

3. **Latency Overhead**
   - Budget/rate checks add ~5-10ms per request
   - DynamoDB writes add ~20ms (async)
   - Cache lookup adds ~2ms (hit) or 0ms (miss)

### Mitigation

- CISO override capability for emergencies
- Budget increase process documented
- Alerts with clear escalation path
- Cache warming for common queries

## Cost Tracking Schema

```json
{
  "request_id": "uuid",
  "timestamp": "ISO-8601",
  "agent": "PlannerAgent",
  "model": "claude-3-5-sonnet-20241022",
  "input_tokens": 1500,
  "output_tokens": 800,
  "cost_usd": 0.016,
  "cumulative_daily": 2.45,
  "cumulative_monthly": 87.32,
  "cached": false
}
```

## Budget Estimates

**Conservative Scenario (50 issues/month):**
- 150 LLM calls × 3,000 avg tokens = 450,000 tokens
- Sonnet: (300K × $3 + 150K × $15) / 1M = $3.15/month

**Realistic Scenario (with context retrieval):**
- 10-20x higher due to RAG context
- Estimate: $50-100/month for pilot
- Scale: $500-1,000/month at full capacity

**Budget Allocation:**

| Environment | Daily | Monthly |
|-------------|-------|---------|
| Development | $10 | $100 |
| Staging | $50 | $500 |
| Production | $100 | $2,000 |

## CloudWatch Dashboard Widgets

1. **Daily Spend** - Line graph (30 days)
2. **Monthly Spend** - Current month total
3. **Tokens by Agent** - Pie chart
4. **Cost by Model** - Stacked area
5. **Request Count** - Line graph
6. **Cache Hit Rate** - Percentage gauge
7. **Error Rate** - Line graph
8. **Budget Utilization** - 0-100% gauge

## References

- `docs/BEDROCK_INTEGRATION_PLAN.md` - Full implementation specification
- `src/services/bedrock_llm_service.py` - Cost-controlled LLM service
- `deploy/cloudformation/aura-cost-alerts.yaml` - Budget alert configuration
- `deploy/cloudformation/secrets.yaml` - Bedrock configuration secrets
