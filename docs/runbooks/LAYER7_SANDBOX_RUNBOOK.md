# Layer 7: Sandbox Runbook

**Layer:** 7 - Sandbox
**CodeBuild Project:** `aura-sandbox-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-sandbox.yml`
**Estimated Deploy Time:** 20-30 minutes (includes Docker build and Phase 4 resources)

---

## Overview

The Sandbox layer deploys HITL (Human-in-the-Loop) approval infrastructure and ephemeral sandbox testing environments.

---

## Resources Deployed

### Phase 1: Core Sandbox Infrastructure

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-sandbox-{env}` | sandbox.yaml | 3 DynamoDB Tables (approval-requests, sandbox-state, sandbox-results), ECS Cluster, Security Groups, IAM Roles, SNS Topic, S3 Bucket, ECR Repository | 8-12 min |
| `aura-hitl-workflow-{env}` | hitl-workflow.yaml | Step Functions State Machine | 3-5 min |

### Phase 2: Self-Service Test Environments (ADR-039)

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-test-env-state-{env}` | test-env-state.yaml | DynamoDB table for environment state | 2-3 min |
| `aura-test-env-iam-{env}` | test-env-iam.yaml | Permission boundary, Lambda roles, Step Functions role, Service Catalog launch role | 3-5 min |
| `aura-test-env-catalog-{env}` | test-environment-catalog.yaml | Service Catalog portfolio, 5 product templates, principal associations, launch constraints | 3-5 min |
| `aura-test-env-approval-{env}` | test-env-approval.yaml | 4 Lambda functions, Step Functions state machine, API Gateway | 5-8 min |
| `aura-test-env-monitoring-{env}` | test-env-monitoring.yaml | CloudWatch dashboard, 5 alarms, SNS topic | 2-3 min |
| `aura-test-env-budgets-{env}` | test-env-budgets.yaml | 3 AWS Budgets, cost tracking DynamoDB table | 2-3 min |

### Phase 4: Advanced Features (ADR-039)

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-test-env-scheduler-{env}` | test-env-scheduler.yaml | DynamoDB schedule table, scheduler Lambda, EventBridge rule (5-min trigger) | 2-3 min |
| `aura-test-env-namespace-{env}` | test-env-namespace.yaml | Namespace controller Lambda, EKS access entry, CloudWatch alarms | 2-3 min |
| `aura-test-env-marketplace-{env}` | test-env-marketplace.yaml | Templates DynamoDB table, submit/approve Lambdas, S3 paths for templates | 2-3 min |

### Phase 5: SSR Training Infrastructure (ADR-050)

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-ssr-training-{env}` | ssr-training.yaml | KMS key (auto-rotation), S3 bucket (TLS enforced, 90-day lifecycle), DynamoDB table (GSIs for repository/status), IAM role | 3-5 min |
| `aura-ssr-training-pipeline-{env}` | ssr-training-pipeline.yaml | ECS Fargate Spot cluster, ECR repos (bug injection/solving), Step Functions workflow, SNS topic, CloudWatch alarms, AWS Budgets | 5-8 min |

### Docker Images Built
- Sandbox Test Runner (pushed to ECR)
- SSR Bug Injector (pushed to ECR) - planned
- SSR Bug Solver (pushed to ECR) - planned

---

## Dependencies

### Prerequisites
- Layer 1: VPC, Subnets, Security Groups
- Layer 2: DynamoDB (for approval state)
- Layer 5: SNS topics for notifications

### Downstream Dependencies
- Frontend: Approval Dashboard uses HITL API
- Agents: Coder/Reviewer use sandbox for testing

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-sandbox-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-sandbox-deploy-dev \
  --query 'ids[0]' --output text)

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}' --output table
```

### Verify Deployment
```bash
# Check CloudFormation stacks (All phases including SSR)
for STACK in aura-sandbox-dev aura-hitl-workflow-dev aura-test-env-state-dev aura-test-env-iam-dev aura-test-env-catalog-dev aura-test-env-approval-dev aura-test-env-monitoring-dev aura-test-env-budgets-dev aura-test-env-scheduler-dev aura-test-env-namespace-dev aura-test-env-marketplace-dev aura-ssr-training-dev aura-ssr-training-pipeline-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done

# Check Step Functions
aws stepfunctions list-state-machines \
  --query 'stateMachines[?contains(name, `aura-`)].name' --output table

# Check Service Catalog (Phase 2)
aws servicecatalog list-portfolios \
  --query "PortfolioDetails[?contains(DisplayName, 'aura')].[DisplayName,Id]" --output table

# Check Lambda Functions (Phase 4)
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'test-env-scheduler') || contains(FunctionName, 'test-env-namespace') || contains(FunctionName, 'test-env-marketplace')].[FunctionName,Runtime]" --output table

# Check DynamoDB Tables (Phase 4 + SSR)
aws dynamodb list-tables \
  --query "TableNames[?contains(@, 'test-env-schedule') || contains(@, 'test-env-templates') || contains(@, 'ssr-training')]" --output table

# Check SSR Infrastructure (Phase 5)
aws s3 ls | grep ssr-training
aws ecs describe-clusters --clusters aura-ssr-training-dev --query 'clusters[0].status'
```

---

## Troubleshooting

### Issue: Step Functions Execution Fails

**Symptoms:**
```
ExecutionFailed - States.TaskFailed
```

**Root Cause:** ECS task failed or timeout.

**Resolution:**
```bash
# Get execution history
EXECUTION_ARN=$(aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:aura-hitl-workflow-dev \
  --status-filter FAILED \
  --query 'executions[0].executionArn' --output text)

aws stepfunctions get-execution-history \
  --execution-arn $EXECUTION_ARN \
  --query 'events[?type==`TaskFailed`].taskFailedEventDetails'
```

---

### Issue: ECS Task Not Starting

**Symptoms:**
- Task stuck in PROVISIONING
- No containers running

**Root Cause:** Fargate capacity, security group, or image issues.

**Resolution:**
```bash
# Check ECS cluster
aws ecs describe-clusters --clusters aura-sandbox-cluster-dev

# List stopped tasks for errors
aws ecs list-tasks --cluster aura-sandbox-cluster-dev --desired-status STOPPED

# Get task details
TASK_ARN=$(aws ecs list-tasks --cluster aura-sandbox-cluster-dev \
  --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster aura-sandbox-cluster-dev --tasks $TASK_ARN
```

---

### Issue: Sandbox Test Runner Image Pull Fails

**Symptoms:**
```
CannotPullContainerError: pull image failed
```

**Root Cause:** ECR repository doesn't exist or image not pushed.

**Resolution:**
```bash
# Check ECR repository
aws ecr describe-repositories \
  --query 'repositories[?contains(repositoryName, `sandbox`)].repositoryUri'

# Check image exists
aws ecr describe-images \
  --repository-name aura-sandbox-runner-dev \
  --query 'imageDetails[*].[imageTags,imagePushedAt]' --output table

# If missing, rebuild via CodeBuild
aws codebuild start-build --project-name aura-sandbox-deploy-dev
```

---

### Issue: HITL Approval Timeout

**Symptoms:**
- Approval request expires before review
- SNS notification not received

**Root Cause:** Expiration timer too short or SNS not configured.

**Resolution:**
```bash
# Check DynamoDB approval record
aws dynamodb get-item \
  --table-name aura-approval-requests-dev \
  --key '{"approval_id": {"S": "APPROVAL_ID"}}'

# Verify SNS subscription
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:aura-hitl-notifications-dev
```

---

### Issue: Scheduled Provisioning Not Triggering (Phase 4)

**Symptoms:**
- Scheduled environments not created at expected time
- No Lambda invocations in CloudWatch

**Root Cause:** EventBridge rule disabled or Lambda misconfigured.

**Resolution:**
```bash
# Check EventBridge rule status
aws events describe-rule --name aura-test-env-scheduler-rule-dev

# Check recent Lambda invocations
aws logs filter-log-events \
  --log-group-name /aws/lambda/aura-test-env-scheduler-processor-dev \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --limit 10

# Manually trigger scheduler
aws lambda invoke \
  --function-name aura-test-env-scheduler-processor-dev \
  --payload '{}' \
  /tmp/scheduler-output.json && cat /tmp/scheduler-output.json
```

---

### Issue: EKS Namespace Creation Fails (Phase 4)

**Symptoms:**
- Namespace controller returns 500 error
- kubectl errors in Lambda logs

**Root Cause:** EKS access entry missing or kubectl layer not configured.

**Resolution:**
```bash
# Check EKS access entries
aws eks list-access-entries --cluster-name aura-cluster-dev

# Check Lambda has correct role
aws lambda get-function-configuration \
  --function-name aura-test-env-namespace-controller-dev \
  --query 'Role'

# Check Lambda logs for kubectl errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/aura-test-env-namespace-controller-dev \
  --filter-pattern "kubectl" \
  --limit 20
```

---

### Issue: Template Marketplace Submission Fails (Phase 4)

**Symptoms:**
- Template submission returns 400/500 error
- Templates stuck in pending_approval status

**Root Cause:** Validation error, S3 permissions, or HITL misconfiguration.

**Resolution:**
```bash
# Check pending templates
aws dynamodb query \
  --table-name aura-test-env-templates-dev \
  --index-name status-created_at-index \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":status":{"S":"pending_approval"}}'

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/aura-test-env-marketplace-submit-dev \
  --filter-pattern "ERROR" \
  --limit 10

# Verify S3 pending path
aws s3 ls s3://aura-artifacts-ACCOUNT-dev/marketplace/pending/
```

---

## Recovery Procedures

### Reset Step Functions Workflow

```bash
# Delete stuck executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:aura-hitl-workflow-dev \
  --status-filter RUNNING \
  --query 'executions[*].executionArn' --output text | \
  xargs -I {} aws stepfunctions stop-execution --execution-arn {}
```

### Rebuild Sandbox Stack

```bash
aws cloudformation delete-stack --stack-name aura-sandbox-dev
aws cloudformation wait stack-delete-complete --stack-name aura-sandbox-dev
aws codebuild start-build --project-name aura-sandbox-deploy-dev
```

---

## Post-Deployment Verification

### 1. Test HITL Workflow

```bash
# Start a test execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:aura-hitl-workflow-dev \
  --input '{"approval_id": "test-123", "patch_id": "patch-456"}'
```

### 2. Verify DynamoDB Tables

```bash
aws dynamodb list-tables \
  --query 'TableNames[?contains(@, `approval`) || contains(@, `sandbox`)]' --output table
```

### 3. Check ECS Cluster

```bash
aws ecs describe-clusters --clusters aura-sandbox-cluster-dev \
  --query 'clusters[0].{Status:status,ActiveServices:activeServicesCount}'
```

---

### Issue: SSR S3 Upload AccessDenied (Phase 5)

**Symptoms:**
- `AccessDenied` error when uploading artifacts to SSR S3 bucket
- Error mentions missing encryption

**Root Cause:** SSR S3 bucket policy enforces KMS encryption.

**Resolution:**
```bash
# Uploads must include KMS encryption
aws s3 cp artifact.tar.gz s3://aura-ssr-training-ACCOUNT-dev/artifacts/ \
  --sse aws:kms \
  --sse-kms-key-id alias/aura-ssr-training-dev
```

In Python:
```python
s3_client.put_object(
    Bucket='aura-ssr-training-ACCOUNT-dev',
    Key='artifacts/...',
    Body=data,
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId='alias/aura-ssr-training-dev'
)
```

---

### Issue: SSR DynamoDB ValidationException for Float (Phase 5)

**Symptoms:**
- `ValidationException: Type mismatch` when storing validation results
- Error on float values like `0.95`

**Root Cause:** DynamoDB does not accept Python float type; requires Decimal.

**Resolution:**
Use the `_convert_floats_to_decimal()` helper:
```python
from decimal import Decimal

def _convert_floats_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj

# Apply before DynamoDB operations
item = _convert_floats_to_decimal(validation_results)
dynamodb.put_item(TableName='aura-ssr-training-state-dev', Item=item)
```

---

### Issue: SSR Step Functions Execution Failed (Phase 5)

**Symptoms:**
- Step Functions workflow stuck or failed
- ECS task not completing

**Resolution:**
```bash
# Get failed execution details
EXECUTION_ARN=$(aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT:stateMachine:aura-ssr-training-dev \
  --status-filter FAILED \
  --query 'executions[0].executionArn' --output text)

aws stepfunctions get-execution-history \
  --execution-arn $EXECUTION_ARN \
  --query 'events[?type==`TaskFailed`].taskFailedEventDetails'

# Check ECS task logs
aws logs filter-log-events \
  --log-group-name /ecs/aura-ssr-injector-dev \
  --filter-pattern "ERROR" \
  --limit 20
```

---

## Related Documentation

- [ADR039_SERVICE_CATALOG_DEPLOYMENT.md](./ADR039_SERVICE_CATALOG_DEPLOYMENT.md) - Phase 2 IAM troubleshooting guide
- [ADR-050: Self-Play SWE-RL Integration](../architecture-decisions/ADR-050-self-play-swe-rl-integration.md) - SSR architecture
- [LAYER6_SERVERLESS_RUNBOOK.md](./LAYER6_SERVERLESS_RUNBOOK.md) - HITL callbacks
- [CLOUDFORMATION_IAM_PERMISSIONS.md](./CLOUDFORMATION_IAM_PERMISSIONS.md) - General IAM permission patterns
- [HITL_SANDBOX_ARCHITECTURE.md](../design/HITL_SANDBOX_ARCHITECTURE.md) - Architecture design

---

**Document Version:** 1.3
**Last Updated:** 2026-01-02 (Added Phase 5: SSR Training Infrastructure)
