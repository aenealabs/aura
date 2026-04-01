# Layer 5: Observability Runbook

**Layer:** 5 - Observability
**CodeBuild Project:** `aura-observability-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-observability.yml`
**Estimated Deploy Time:** 10-15 minutes

---

## Overview

The Observability layer deploys secrets management, monitoring dashboards, cost alerts, and real-time anomaly detection.

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-secrets-{env}` | secrets.yaml | 6 Secrets Manager secrets (Bedrock, Neptune, OpenSearch, API keys, JWT) | 2-3 min |
| `aura-monitoring-{env}` | monitoring.yaml | CloudWatch Dashboard, Alarms, SNS Topic, Log Groups | 3-5 min |
| `aura-cost-alerts-{env}` | aura-cost-alerts.yaml | AWS Budgets (daily $15, monthly $400), SNS Alerts | 2-3 min |
| `aura-realtime-monitoring-{env}` | realtime-monitoring.yaml | EventBridge Rules, CloudWatch Alarms, SNS Alerts | 2-3 min |

### Planned Additions
| Stack Name | Template | Resources |
|------------|----------|-----------|
| `aura-disaster-recovery-{env}` | disaster-recovery.yaml | AWS Backup Vault, Plans, Selections |
| `aura-otel-collector-{env}` | otel-collector.yaml | OpenTelemetry IRSA Role |

---

## Dependencies

### Prerequisites
- Layer 1: VPC (for VPC Flow Logs)
- Layer 2: Neptune ARN, DynamoDB ARNs (for backup selections)
- Layer 3: EKS OIDC (for OTEL IRSA)
- SSM Parameter: `/aura/{env}/alert-email`

### Downstream Dependencies
- Serverless: Uses SNS topics for alerts
- Sandbox: Uses monitoring endpoints

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-observability-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-observability-deploy-dev \
  --query 'ids[0]' --output text)

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}' --output table
```

### Verify Deployment
```bash
for STACK in aura-secrets-dev aura-monitoring-dev aura-cost-alerts-dev aura-realtime-monitoring-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done
```

---

## Troubleshooting

### Issue: SNS Subscription Not Confirmed

**Symptoms:**
- Alerts not received via email
- SNS subscription shows "PendingConfirmation"

**Root Cause:** Email confirmation link not clicked.

**Resolution:**
```bash
# Check subscription status
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-alerts-dev \
  --query 'Subscriptions[*].[Endpoint,SubscriptionArn]' --output table

# If pending, check email inbox for confirmation link
# Subject: "AWS Notification - Subscription Confirmation"

# Alternatively, remove and re-subscribe
aws sns unsubscribe --subscription-arn arn:aws:sns:...:pending
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-alerts-dev \
  --protocol email \
  --notification-endpoint your-email@example.com
```

---

### Issue: CloudWatch Dashboard Empty

**Symptoms:**
- Dashboard shows "No data available"
- Widgets display errors

**Root Cause:** Metrics not being collected or wrong metric names.

**Resolution:**
```bash
# List available metrics
aws cloudwatch list-metrics \
  --namespace "Aura/Anomalies" \
  --query 'Metrics[*].[MetricName,Dimensions]' --output table

# Check if Container Insights is working
aws cloudwatch list-metrics \
  --namespace "ContainerInsights" \
  --query 'Metrics[0:5]'

# Verify EKS addon
aws eks describe-addon \
  --cluster-name aura-cluster-dev \
  --addon-name amazon-cloudwatch-observability
```

---

### Issue: Budget Alert Not Triggering

**Symptoms:**
- Spending exceeded budget but no alert received

**Root Cause:** Budget alert threshold not met or SNS not configured.

**Resolution:**
```bash
# Check budget configuration
aws budgets describe-budgets \
  --account-id 123456789012 \
  --query 'Budgets[*].[BudgetName,BudgetLimit,CalculatedSpend]' --output table

# Check budget notifications
aws budgets describe-notifications-for-budget \
  --account-id 123456789012 \
  --budget-name aura-daily-budget-dev
```

---

### Issue: Secrets Manager Access Denied

**Symptoms:**
```
AccessDeniedException when calling GetSecretValue
```

**Root Cause:** IAM role missing secretsmanager permissions.

**Resolution:**
```bash
# Check secret exists
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `aura/`)].Name' --output table

# Check role permissions
aws iam list-attached-role-policies --role-name aura-api-role-dev

# Test secret access
aws secretsmanager get-secret-value \
  --secret-id aura/dev/bedrock-api-key \
  --query 'SecretString' --output text
```

---

## Recovery Procedures

### Recreate Secrets (After Deletion)

**WARNING:** This will generate new secret values.

```bash
# Delete and recreate secrets stack
aws cloudformation delete-stack --stack-name aura-secrets-dev
aws cloudformation wait stack-delete-complete --stack-name aura-secrets-dev

# Redeploy
aws codebuild start-build --project-name aura-observability-deploy-dev
```

### Reset Budget Alerts

```bash
# Delete and recreate cost alerts stack
aws cloudformation delete-stack --stack-name aura-cost-alerts-dev
aws cloudformation wait stack-delete-complete --stack-name aura-cost-alerts-dev

aws codebuild start-build --project-name aura-observability-deploy-dev
```

---

## Post-Deployment Steps

### 1. Confirm SNS Subscriptions

Check email inbox and click "Confirm subscription" links for:
- `aura-alerts-dev` topic
- `aura-cost-alerts-dev` topic

### 2. Verify Secrets

```bash
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `aura/dev`)].Name' --output table
```

### 3. Check CloudWatch Alarms

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix aura \
  --query 'MetricAlarms[*].[AlarmName,StateValue]' --output table
```

---

## Related Documentation

- [LAYER2_DATA_RUNBOOK.md](./LAYER2_DATA_RUNBOOK.md) - Data layer for backup targets
- [LAYER3_COMPUTE_RUNBOOK.md](./LAYER3_COMPUTE_RUNBOOK.md) - EKS for Container Insights

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
