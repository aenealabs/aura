# Layer 6: Serverless Runbook

**Layer:** 6 - Serverless
**CodeBuild Project:** `aura-serverless-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-serverless.yml`
**Estimated Deploy Time:** 10-15 minutes

---

## Overview

The Serverless layer deploys Lambda functions and EventBridge rules for background processing, threat intelligence, and HITL automation.

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-threat-intel-scheduler-{env}` | threat-intel-scheduler.yaml | Lambda (threat intel processor), EventBridge Rule | 3-5 min |
| `aura-hitl-scheduler-{env}` | hitl-scheduler.yaml | Lambda (HITL expiration), EventBridge Rule | 3-5 min |
| `aura-hitl-callback-{env}` | hitl-callback.yaml | Lambda (approval callback handler) | 2-3 min |

### Planned Additions
| Stack Name | Template | Resources |
|------------|----------|-----------|
| `aura-a2a-infrastructure-{env}` | a2a-infrastructure.yaml | DynamoDB, SQS, EventBridge for A2A Protocol |

---

## Dependencies

### Prerequisites
- Layer 1: VPC, Security Groups (Lambda SG)
- Layer 5: SNS topics for alerts
- SSM Parameters for configuration

### Downstream Dependencies
- Sandbox: Uses HITL callback for approvals
- Application: Uses threat intel data

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-serverless-deploy-dev --region us-east-1
```

### Verify Deployment
```bash
for STACK in aura-threat-intel-scheduler-dev aura-hitl-scheduler-dev aura-hitl-callback-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done

# List Lambda functions
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `aura-`)].FunctionName' --output table
```

---

## Troubleshooting

### Issue: Lambda Cold Start Timeout

**Symptoms:**
```
Task timed out after 3.00 seconds
```

**Root Cause:** Lambda in VPC has slow cold starts or timeout too low.

**Resolution:**
```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name aura-threat-intel-processor-dev \
  --timeout 30

# Or use provisioned concurrency
aws lambda put-provisioned-concurrency-config \
  --function-name aura-threat-intel-processor-dev \
  --qualifier '$LATEST' \
  --provisioned-concurrent-executions 1
```

---

### Issue: Lambda VPC Network Timeout

**Symptoms:**
```
Connection timed out connecting to external service
```

**Root Cause:** Lambda in VPC cannot reach internet (missing NAT Gateway route).

**Resolution:**
```bash
# Check Lambda VPC config
aws lambda get-function-configuration \
  --function-name aura-threat-intel-processor-dev \
  --query 'VpcConfig'

# Verify NAT Gateway route exists
aws ec2 describe-route-tables \
  --filters "Name=tag:Name,Values=*private*" \
  --query 'RouteTables[*].Routes[?NatGatewayId]'
```

---

### Issue: EventBridge Rule Not Triggering

**Symptoms:**
- Lambda not invoked on schedule
- No CloudWatch Logs entries

**Root Cause:** Rule disabled or target misconfigured.

**Resolution:**
```bash
# Check rule state
aws events describe-rule \
  --name aura-threat-intel-schedule-dev \
  --query '{State:State,Schedule:ScheduleExpression}'

# Check targets
aws events list-targets-by-rule \
  --rule aura-threat-intel-schedule-dev

# Enable rule if disabled
aws events enable-rule --name aura-threat-intel-schedule-dev
```

---

### Issue: Lambda Permission Denied

**Symptoms:**
```
AccessDeniedException when calling DynamoDB/S3/etc
```

**Root Cause:** Lambda execution role missing permissions.

**Resolution:**
```bash
# Get Lambda role
ROLE=$(aws lambda get-function-configuration \
  --function-name aura-hitl-callback-dev \
  --query 'Role' --output text)

# List attached policies
aws iam list-attached-role-policies --role-name $(basename $ROLE)

# Check inline policies
aws iam list-role-policies --role-name $(basename $ROLE)
```

---

## Recovery Procedures

### Redeploy Single Lambda

```bash
# Force update by touching the stack
aws cloudformation update-stack \
  --stack-name aura-hitl-callback-dev \
  --use-previous-template \
  --parameters ParameterKey=Environment,UsePreviousValue=true \
    ParameterKey=ProjectName,UsePreviousValue=true \
  --capabilities CAPABILITY_IAM

# Or delete and redeploy
aws cloudformation delete-stack --stack-name aura-hitl-callback-dev
aws cloudformation wait stack-delete-complete --stack-name aura-hitl-callback-dev
aws codebuild start-build --project-name aura-serverless-deploy-dev
```

---

## Post-Deployment Verification

### 1. Test Lambda Invocation

```bash
# Invoke threat intel processor
aws lambda invoke \
  --function-name aura-threat-intel-processor-dev \
  --payload '{}' \
  /tmp/response.json

cat /tmp/response.json
```

### 2. Check CloudWatch Logs

```bash
# Get recent log events
aws logs tail /aws/lambda/aura-threat-intel-processor-dev --since 1h
```

### 3. Verify EventBridge Rules

```bash
aws events list-rules \
  --name-prefix aura \
  --query 'Rules[*].[Name,State,ScheduleExpression]' --output table
```

---

## Related Documentation

- [LAYER5_OBSERVABILITY_RUNBOOK.md](./LAYER5_OBSERVABILITY_RUNBOOK.md) - SNS topics
- [LAYER7_SANDBOX_RUNBOOK.md](./LAYER7_SANDBOX_RUNBOOK.md) - HITL workflow integration

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
