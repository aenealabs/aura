# EventBridge Schedule Cost Optimization

**Last Updated:** 2026-01-19
**Author:** Platform Engineering Team
**Scope:** Lambda invocation frequency optimization for EventBridge scheduled rules

---

## Executive Summary

This document describes cost optimization changes made to three EventBridge scheduled rules in Project Aura. By reducing Lambda invocation frequency for non-time-critical workloads, we achieved an **80% reduction in daily invocations** (from 2,016 to 408 invocations per day) while maintaining acceptable service levels.

The optimizations target internal operational processes where sub-minute responsiveness is not required. Customer-facing and security-critical schedules remain unchanged.

---

## Changes Summary

| Template | EventBridge Rule | Previous Rate | New Rate | Daily Invocations (Before) | Daily Invocations (After) | Reduction |
|----------|------------------|---------------|----------|---------------------------|--------------------------|-----------|
| `scheduling-infrastructure.yaml` | `aura-scheduler-dispatcher-{env}` | 1 minute | 5 minutes | 1,440 | 288 | 80% |
| `test-env-budgets.yaml` | `aura-test-env-cost-aggregator-{env}` | 5 minutes | 1 hour | 288 | 24 | 92% |
| `test-env-scheduler.yaml` | `aura-test-env-scheduler-trigger-{env}` | 5 minutes | 15 minutes | 288 | 96 | 67% |
| **Total** | | | | **2,016** | **408** | **80%** |

---

## Detailed Change Descriptions

### 1. Scheduler Dispatcher (scheduling-infrastructure.yaml)

**CloudFormation Resource:** `SchedulerDispatcherRule`
**EventBridge Rule Name:** `aura-scheduler-dispatcher-{env}`
**Layer:** 6.11 (Scheduling Infrastructure - ADR-055)

| Attribute | Previous | New |
|-----------|----------|-----|
| Schedule Expression | `rate(1 minute)` | `rate(5 minutes)` |
| Daily Invocations | 1,440 | 288 |
| Description | Triggers scheduler dispatcher every minute | Triggers scheduler dispatcher every 5 minutes |

**Purpose:** Polls DynamoDB for pending scheduled jobs and dispatches them for execution.

**Rationale:** The scheduler dispatcher processes jobs that are typically scheduled hours or days in advance. A 5-minute polling interval provides adequate responsiveness while significantly reducing costs. Jobs scheduled with specific timestamps will execute within a 5-minute window of their scheduled time.

---

### 2. Cost Aggregator (test-env-budgets.yaml)

**CloudFormation Resource:** `CostAggregatorSchedule`
**EventBridge Rule Name:** `aura-test-env-cost-aggregator-{env}`
**Layer:** 7.7 (Test Environment Budgets)

| Attribute | Previous | New |
|-----------|----------|-----|
| Schedule Expression | `rate(5 minutes)` | `rate(1 hour)` |
| Daily Invocations | 288 | 24 |
| Description | Run cost aggregator every 5 minutes | Run cost aggregator hourly |

**Purpose:** Aggregates AWS Cost Explorer data for test environment budget monitoring and alerting.

**Rationale:** AWS Cost Explorer data has inherent latency (typically 8-24 hours for detailed cost data). Aggregating this data every 5 minutes provided no practical benefit. Hourly aggregation aligns with the data availability cadence and provides sufficient granularity for budget monitoring dashboards.

---

### 3. Test Environment Scheduler (test-env-scheduler.yaml)

**CloudFormation Resource:** `SchedulerEventRule`
**EventBridge Rule Name:** `aura-test-env-scheduler-trigger-{env}`
**Layer:** 7.8 (Test Environment Scheduler)

| Attribute | Previous | New |
|-----------|----------|-----|
| Schedule Expression | `rate(5 minutes)` | `rate(15 minutes)` |
| Daily Invocations | 288 | 96 |
| Description | Triggers test environment scheduler processor every 5 minutes | Triggers test environment scheduler processor every 15 minutes |

**Purpose:** Processes scheduled test environment provisioning and teardown requests.

**Rationale:** Test environment provisioning is a planned activity where users schedule environments in advance. A 15-minute polling window provides acceptable latency for environment readiness while reducing operational costs. Users requesting immediate environments use the synchronous API, which is unaffected by this change.

---

## Cost Impact Analysis

### Lambda Invocation Savings

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Daily Invocations | 2,016 | 408 | 1,608 (80%) |
| Monthly Invocations | ~60,480 | ~12,240 | ~48,240 (80%) |
| Annual Invocations | ~735,840 | ~148,920 | ~586,920 (80%) |

### Estimated Cost Savings

AWS Lambda pricing (as of 2026):
- First 1 million requests/month: Free
- Beyond free tier: $0.20 per 1 million requests

**Direct Lambda request costs:** Minimal impact (within free tier for most environments)

**Indirect savings:**
- Reduced CloudWatch Logs ingestion from Lambda execution logs
- Reduced DynamoDB read capacity consumption
- Reduced CloudWatch metrics data points
- Lower baseline compute utilization

**Per-environment estimated monthly savings:** $2-5 (varies by region and usage patterns)

---

## Trade-offs and Considerations

### Accepted Trade-offs

| Component | Trade-off | Mitigation |
|-----------|-----------|------------|
| Scheduler Dispatcher | Job execution may be delayed up to 5 minutes from scheduled time | Document expected latency; use synchronous APIs for time-critical operations |
| Cost Aggregator | Budget alerts may be delayed up to 1 hour | AWS Budget native alerts provide faster notifications; aggregator is for dashboards |
| Test Environment Scheduler | Environment provisioning may be delayed up to 15 minutes | Document expected latency; synchronous provisioning API available for urgent needs |

### Workloads NOT Affected

The following schedules were evaluated but NOT changed due to their time-sensitive nature:

- Security monitoring and alerting schedules
- Production health check schedules
- Real-time data pipeline triggers
- Customer-facing API schedules

### Monitoring Recommendations

After deployment, monitor the following metrics to validate the changes:

1. **Job Execution Latency:** Track time between scheduled timestamp and actual execution
2. **Queue Depth:** Monitor pending jobs in DynamoDB tables for backlog accumulation
3. **User Feedback:** Collect feedback on perceived responsiveness of scheduled operations

---

## Deployment Notes

### Prerequisites

- AWS CLI configured with appropriate permissions
- Access to deploy CloudFormation stacks in target environment

### Deployment Order

These templates have no inter-dependencies for this change. Deploy in any order:

```bash
# Deploy scheduling infrastructure
aws cloudformation deploy \
  --template-file deploy/cloudformation/scheduling-infrastructure.yaml \
  --stack-name aura-scheduling-infrastructure-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy test environment budgets
aws cloudformation deploy \
  --template-file deploy/cloudformation/test-env-budgets.yaml \
  --stack-name aura-test-env-budgets-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy test environment scheduler
aws cloudformation deploy \
  --template-file deploy/cloudformation/test-env-scheduler.yaml \
  --stack-name aura-test-env-scheduler-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM
```

### Verification

After deployment, verify the schedule expressions:

```bash
# List EventBridge rules and their schedules
aws events list-rules --name-prefix "aura-" --query "Rules[*].[Name,ScheduleExpression]" --output table
```

Expected output:

| Rule Name | Schedule Expression |
|-----------|---------------------|
| `aura-scheduler-dispatcher-{env}` | `rate(5 minutes)` |
| `aura-test-env-cost-aggregator-{env}` | `rate(1 hour)` |
| `aura-test-env-scheduler-trigger-{env}` | `rate(15 minutes)` |

---

## Rollback Procedure

If the optimized schedules cause unacceptable latency or operational issues, revert to the previous configuration.

### Option 1: CloudFormation Rollback

Revert the CloudFormation template changes and redeploy:

```bash
# Revert git changes to templates
git checkout HEAD~1 -- deploy/cloudformation/scheduling-infrastructure.yaml
git checkout HEAD~1 -- deploy/cloudformation/test-env-budgets.yaml
git checkout HEAD~1 -- deploy/cloudformation/test-env-scheduler.yaml

# Redeploy each stack (same commands as Deployment Notes section)
```

### Option 2: Manual AWS Console Override

For immediate rollback without code changes:

1. Navigate to **Amazon EventBridge** > **Rules**
2. Select the rule to modify
3. Click **Edit**
4. Update the **Schedule expression** to the previous value:
   - `aura-scheduler-dispatcher-{env}`: `rate(1 minute)`
   - `aura-test-env-cost-aggregator-{env}`: `rate(5 minutes)`
   - `aura-test-env-scheduler-trigger-{env}`: `rate(5 minutes)`
5. Click **Update**

**Note:** Manual console changes will be overwritten on next CloudFormation deployment. Update templates before redeploying.

### Option 3: AWS CLI Rollback

```bash
# Scheduler Dispatcher - revert to 1 minute
aws events put-rule \
  --name "aura-scheduler-dispatcher-${ENVIRONMENT}" \
  --schedule-expression "rate(1 minute)"

# Cost Aggregator - revert to 5 minutes
aws events put-rule \
  --name "aura-test-env-cost-aggregator-${ENVIRONMENT}" \
  --schedule-expression "rate(5 minutes)"

# Test Environment Scheduler - revert to 5 minutes
aws events put-rule \
  --name "aura-test-env-scheduler-trigger-${ENVIRONMENT}" \
  --schedule-expression "rate(5 minutes)"
```

---

## Related Documentation

- [Lambda Configuration Standards](/docs/operations/LAMBDA_CONFIGURATION_STANDARDS.md)
- [Serverless Deployment Runbook](/docs/operations/SERVERLESS_DEPLOYMENT_RUNBOOK.md)
- [ADR-055: Scheduling Infrastructure](/docs/architecture-decisions/ADR-055-scheduling-infrastructure.md)
- [Test Environment Architecture](/docs/design/TEST_ENVIRONMENT_ARCHITECTURE.md)

---

## Change History

| Date | Author | Description |
|------|--------|-------------|
| 2026-01-19 | Platform Engineering | Initial optimization - 80% invocation reduction |
