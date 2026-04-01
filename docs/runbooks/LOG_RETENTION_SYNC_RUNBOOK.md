# Log Retention Sync Lambda Runbook

**Version:** 1.0
**Last Updated:** December 15, 2025
**Owner:** Platform Engineering Team
**Related ADR:** [ADR-040: Configurable Compliance Settings](../architecture-decisions/ADR-040-configurable-compliance-settings.md)

---

## Overview

The Log Retention Sync Lambda automatically synchronizes CloudWatch log group retention policies when users change the log retention setting in the Aura Settings UI. This ensures compliance with organizational and regulatory requirements (e.g., CMMC L2 requires 90+ days retention).

### Deployment Status

| Environment | Status | Deployed Date |
|-------------|--------|---------------|
| **Dev** | CREATE_COMPLETE | December 15, 2025 |
| QA | Not Deployed | - |
| Prod | Not Deployed | - |

**Dev Environment Resources:**

| Resource | ARN / Identifier |
|----------|-----------------|
| Lambda Function | `arn:aws:lambda:us-east-1:123456789012:function:aura-log-retention-sync-dev` |
| IAM Role | `aura-log-retention-lambda-role-dev` |
| SNS Topic | `aura-log-retention-updates-dev` |
| CloudFormation Stack | `aura-log-retention-sync-dev` |

### Key Features

- **UI-Driven Configuration:** Users configure retention in Settings > Security tab
- **Automatic Sync:** Lambda updates all Aura log groups to match the configured retention
- **Async Invocation:** API responds immediately; sync happens in background
- **Dry-Run Mode:** Test changes without applying them
- **SNS Notifications:** Email alerts on successful sync or failures
- **CMMC Compliance:** UI indicates compliance status based on selected retention

### Validation Test Results (December 15, 2025)

Dry-run test executed against dev environment:

| Metric | Value |
|--------|-------|
| Log Groups Scanned | 38 |
| Already at 90-day Retention | 17 |
| Would Be Updated | 21 |
| Failures | 0 |

**Prefixes Searched:**
- `/aws/lambda/aura`
- `/aws/codebuild/aura`
- `/aura`
- `/aws/eks/aura`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LOG RETENTION SYNC ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────┐
                                    │   Aura UI       │
                                    │ Settings Page   │
                                    │ (Security Tab)  │
                                    └────────┬────────┘
                                             │ PUT /api/v1/settings/security
                                             ▼
                                    ┌─────────────────┐
                                    │  FastAPI        │
                                    │  Settings API   │
                                    │                 │
                                    │ Detects change: │
                                    │ old != new      │
                                    └────────┬────────┘
                                             │ boto3.invoke(
                                             │   InvocationType="Event")
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             AWS LAMBDA                                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  aura-log-retention-sync-{env}                                             │ │
│  │                                                                            │ │
│  │  1. Validate retention_days (normalize to CloudWatch-supported value)      │ │
│  │  2. Query log groups by prefix (paginated)                                 │ │
│  │  3. Deduplicate overlapping prefixes                                       │ │
│  │  4. Update each log group's retention policy                               │ │
│  │  5. Send SNS notification with statistics                                  │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
         │                                                           │
         │  logs:PutRetentionPolicy                                  │ sns:Publish
         ▼                                                           ▼
┌─────────────────────────────────────┐                 ┌─────────────────────────┐
│        CloudWatch Log Groups        │                 │   SNS Topic             │
│                                     │                 │   aura-log-retention-   │
│  /aws/lambda/aura-*                 │                 │   updates-{env}         │
│  /aws/codebuild/aura-*              │                 │                         │
│  /aura/*                            │                 │   -> Email Subscription │
│  /aws/eks/aura-*                    │                 └─────────────────────────┘
│  /aws/ecs/aura-*                    │
└─────────────────────────────────────┘
```

---

## Components

### Lambda Function

| Attribute | Value |
|-----------|-------|
| **Function Name** | `aura-log-retention-sync-{env}` |
| **Runtime** | Python 3.11 |
| **Timeout** | 300 seconds (5 minutes) |
| **Memory** | 256 MB |
| **Handler** | `index.lambda_handler` |
| **CloudFormation Template** | `deploy/cloudformation/log-retention-sync.yaml` (Layer 5.7) |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment (dev, qa, prod) | `dev` |
| `PROJECT_NAME` | Project name for resource naming | `aura` |
| `SNS_TOPIC_ARN` | SNS topic for notifications | Set by CloudFormation |
| `LOG_GROUP_PREFIXES` | Comma-separated prefixes to manage | `/aws/lambda/aura,/aws/codebuild/aura,/aura,/aws/eks/aura` |
| `DEFAULT_RETENTION_DAYS` | Default retention if not specified | `90` |
| `DRY_RUN` | Set to `true` to preview changes | `false` |

### Log Group Prefixes

The Lambda manages log groups matching these prefixes:

| Prefix | Description |
|--------|-------------|
| `/aws/lambda/aura-*` | Lambda function execution logs |
| `/aws/codebuild/aura-*` | CodeBuild project logs |
| `/aura/*` | Application logs (API, agents, services) |
| `/aws/eks/aura-*` | EKS cluster control plane logs |
| `/aws/ecs/aura-*` | ECS task logs |

### IAM Permissions

The Lambda role (`aura-log-retention-lambda-role-{env}`) has these permissions:

```yaml
# Describe all log groups (for discovery)
logs:DescribeLogGroups on arn:${Partition}:logs:${Region}:${Account}:log-group:*

# Update retention on Aura log groups only
logs:PutRetentionPolicy on:
  - arn:${Partition}:logs:${Region}:${Account}:log-group:/aws/lambda/aura-*
  - arn:${Partition}:logs:${Region}:${Account}:log-group:/aws/codebuild/aura-*
  - arn:${Partition}:logs:${Region}:${Account}:log-group:/aura/*
  - arn:${Partition}:logs:${Region}:${Account}:log-group:/aws/eks/aura-*
  - arn:${Partition}:logs:${Region}:${Account}:log-group:/aws/ecs/aura-*

# Publish notifications
sns:Publish on aura-log-retention-updates-{env} topic
```

---

## How It Works

### User Flow

1. User navigates to **Settings > Security** in the Aura UI
2. User selects a new log retention value from the dropdown
3. User clicks **Save**
4. Frontend calls `PUT /api/v1/settings/security` with the new value
5. Backend saves settings to DynamoDB
6. Backend detects retention change and invokes Lambda asynchronously
7. API returns immediately with success
8. Lambda runs in background, updating all log groups
9. User receives email notification when sync completes

### Lambda Execution Flow

```
1. Parse event
   └── Extract retention_days (required)
   └── Extract prefixes (optional, uses defaults)
   └── Extract dry_run flag (optional)

2. Validate retention_days
   └── Check if value is CloudWatch-supported
   └── If not, normalize to next valid value
   └── Log normalization if occurred

3. Discover log groups
   └── For each prefix:
       └── Paginate through describe_log_groups
       └── Collect all matching log groups
   └── Deduplicate (prefixes may overlap)

4. Update log groups
   └── For each unique log group:
       └── Get current retention
       └── Skip if already at target
       └── If dry_run: log what would change
       └── If not dry_run: call put_retention_policy

5. Send notification
   └── If SNS_TOPIC_ARN set and not dry_run:
       └── Publish success/failure message
       └── Include statistics (updated, skipped, failed)

6. Return response
   └── HTTP 200 with statistics
   └── HTTP 400 if retention_days missing
   └── HTTP 500 on unexpected error
```

---

## Deployment

### Prerequisites

- Observability layer CodeBuild project deployed
- SSM parameter `/aura/{env}/alert-email` configured

### Deploy via CI/CD (Recommended)

```bash
# Trigger observability layer deployment
aws codebuild start-build \
  --project-name aura-observability-deploy-dev \
  --region us-east-1
```

### Manual Deployment (Emergency Only)

```bash
# Validate template
cfn-lint deploy/cloudformation/log-retention-sync.yaml

# Deploy stack
aws cloudformation deploy \
  --template-file deploy/cloudformation/log-retention-sync.yaml \
  --stack-name aura-log-retention-sync-dev \
  --parameter-overrides \
    Environment=dev \
    ProjectName=aura \
    AlertEmail=alerts@aenealabs.com \
    DefaultRetentionDays=90 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name aura-log-retention-sync-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# Verify Lambda exists
aws lambda get-function \
  --function-name aura-log-retention-sync-dev \
  --query 'Configuration.FunctionArn' \
  --output text

# Check SNS topic
aws sns list-topics --query "Topics[?contains(TopicArn, 'log-retention')]"
```

---

## Manual Invocation

### Dry-Run (Preview Changes)

```bash
aws lambda invoke \
  --function-name aura-log-retention-sync-dev \
  --payload '{"retention_days": 90, "dry_run": true}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | jq '.body | fromjson'
```

### Production Invocation

```bash
aws lambda invoke \
  --function-name aura-log-retention-sync-dev \
  --payload '{"retention_days": 90, "dry_run": false}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | jq '.body | fromjson'
```

### Custom Prefixes

```bash
aws lambda invoke \
  --function-name aura-log-retention-sync-dev \
  --payload '{
    "retention_days": 90,
    "dry_run": true,
    "prefixes": ["/aws/lambda/aura", "/custom/prefix"]
  }' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

### Expected Response

```json
{
  "statusCode": 200,
  "body": {
    "status": "success",
    "environment": "dev",
    "timestamp": "2025-12-15T10:30:00.000000+00:00",
    "dry_run": false,
    "retention_days": 90,
    "statistics": {
      "total_log_groups": 25,
      "updated": 20,
      "skipped": 4,
      "failed": 1
    },
    "prefixes_searched": [
      "/aws/lambda/aura",
      "/aws/codebuild/aura",
      "/aura",
      "/aws/eks/aura"
    ],
    "details": [...]
  }
}
```

---

## Troubleshooting

### Common Issues

#### Issue: Lambda Not Found

**Symptom:** API logs show `ResourceNotFoundException`

**Cause:** Lambda not deployed or wrong function name

**Resolution:**
```bash
# Check if Lambda exists
aws lambda list-functions --query "Functions[?contains(FunctionName, 'log-retention')]"

# If missing, deploy via CodeBuild
aws codebuild start-build --project-name aura-observability-deploy-dev
```

#### Issue: Permission Denied on Log Group

**Symptom:** Lambda returns `failed` count > 0, logs show `AccessDeniedException`

**Cause:** Log group prefix not in IAM policy

**Resolution:**
1. Check if log group matches managed prefixes
2. If custom prefix needed, update CloudFormation template:
```yaml
# In log-retention-sync.yaml, add to LogRetentionLambdaPolicy
- !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/custom/prefix-*'
```
3. Redeploy stack

#### Issue: Invalid Retention Value

**Symptom:** Lambda logs show "Normalized retention from X to Y days"

**Cause:** Requested retention not in CloudWatch-supported values

**Resolution:** This is expected behavior. CloudWatch only supports specific retention values. The Lambda automatically normalizes to the next valid value.

Valid values: `1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653`

#### Issue: No Log Groups Updated

**Symptom:** `total_log_groups: 0` in response

**Cause:** No log groups match configured prefixes

**Resolution:**
```bash
# List log groups to verify they exist
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/aura

# Check configured prefixes
aws lambda get-function-configuration \
  --function-name aura-log-retention-sync-dev \
  --query 'Environment.Variables.LOG_GROUP_PREFIXES'
```

#### Issue: Timeout

**Symptom:** Lambda times out after 300 seconds

**Cause:** Too many log groups to process

**Resolution:**
1. Invoke with smaller prefix subset
2. Increase Lambda timeout (max 900 seconds)
3. Consider batching by prefix

### View Lambda Logs

```bash
# Recent logs
aws logs tail /aws/lambda/aura-log-retention-sync-dev --follow

# Specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/aura-log-retention-sync-dev \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "ERROR"
```

---

## Monitoring and Alerting

### CloudWatch Metrics

The Lambda automatically publishes these metrics:

| Metric | Description |
|--------|-------------|
| `Invocations` | Number of Lambda invocations |
| `Duration` | Execution time in milliseconds |
| `Errors` | Number of failed invocations |
| `ConcurrentExecutions` | Concurrent execution count |

### SNS Notifications

**Success Notification:**
```
Subject: [Aura] Log Retention Updated to 90 days

Log Retention Sync Completed

Environment: dev
Timestamp: 2025-12-15T10:30:00Z
Dry Run: False

New Retention: 90 days

Statistics:
- Total Log Groups: 25
- Updated: 20
- Skipped (already at target): 4
- Failed: 1

Prefixes Searched: /aws/lambda/aura, /aws/codebuild/aura, /aura, /aws/eks/aura
```

**Error Notification:**
```
Subject: [Aura] Log Retention Sync FAILED

Log Retention Sync Failed

Timestamp: 2025-12-15T10:30:00Z
Error: AccessDeniedException: User is not authorized...

Please investigate and retry manually if needed.
```

### Recommended Alarms

Create these CloudWatch alarms for operational visibility:

```bash
# High failure rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name aura-log-retention-sync-failures \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --dimensions Name=FunctionName,Value=aura-log-retention-sync-dev \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:aura-alerts-dev
```

---

## Security Considerations

### Least Privilege

- Lambda can only modify retention on Aura log groups (prefix-scoped)
- Cannot delete log groups or log streams
- Cannot read log content
- SNS publish limited to specific topic

### Audit Trail

All retention changes are:
1. Logged in Lambda CloudWatch logs
2. Sent via SNS notification
3. Visible in CloudTrail (PutRetentionPolicy events)

### Rate Limiting

- Settings API has admin rate limit (5 requests/minute)
- Lambda uses boto3 default retry with exponential backoff
- No concurrent Lambda executions for same environment

---

## Testing

### Run Unit Tests

```bash
# Run all Lambda tests
pytest tests/test_lambda_log_retention_sync.py -v

# Run with coverage
pytest tests/test_lambda_log_retention_sync.py --cov=src/lambda/log_retention_sync --cov-report=term-missing
```

### Integration Test

```bash
# 1. Create a test log group
aws logs create-log-group --log-group-name /aura/test/integration-test

# 2. Set initial retention
aws logs put-retention-policy \
  --log-group-name /aura/test/integration-test \
  --retention-in-days 30

# 3. Invoke Lambda
aws lambda invoke \
  --function-name aura-log-retention-sync-dev \
  --payload '{"retention_days": 90, "prefixes": ["/aura/test"]}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# 4. Verify retention updated
aws logs describe-log-groups \
  --log-group-name-prefix /aura/test/integration-test \
  --query 'logGroups[0].retentionInDays'

# 5. Clean up
aws logs delete-log-group --log-group-name /aura/test/integration-test
```

---

## CMMC Compliance Reference

| Requirement | Control | How Lambda Supports |
|-------------|---------|---------------------|
| AU.L2-3.3.1 | Create and retain system audit logs | Configurable retention (90+ days default) |
| AU.L2-3.3.2 | Ensure actions are traceable | SNS notifications, CloudTrail logging |
| AU.L2-3.3.4 | Alert on audit log process failure | SNS error notifications |

### Compliance Indicators (UI)

| Retention | Compliance Badge |
|-----------|-----------------|
| < 90 days | "Not CMMC Compliant" (orange warning) |
| >= 90 days | "CMMC L2 Compliant" (green) |
| >= 365 days | "CMMC L2 + GovCloud Compliant" (green) |

---

## Related Documentation

- [ADR-040: Configurable Compliance Settings](../architecture-decisions/ADR-040-configurable-compliance-settings.md)
- [Layer 5 Observability Runbook](./LAYER5_OBSERVABILITY_RUNBOOK.md)
- [Security Settings API](../reference/API_REFERENCE.md#security-settings)
- [CMMC Certification Pathway](../security/CMMC_CERTIFICATION_PATHWAY.md)
