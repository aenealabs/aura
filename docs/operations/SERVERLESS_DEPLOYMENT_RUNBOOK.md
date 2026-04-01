# Serverless Layer Deployment Runbook

**Last Updated:** 2025-12-12
**Author:** Platform Engineering Team
**Scope:** Troubleshooting and resolving serverless layer (Layer 6) deployment failures

---

## Overview

This runbook documents common deployment failures for the serverless layer and their resolutions. The serverless layer includes:

| Stack | Purpose |
|-------|---------|
| `aura-hitl-callback-dev` | HITL approval callback Lambda with Function URL |
| `aura-orchestrator-dispatcher-dev` | SQS-to-EKS MetaOrchestrator bridge Lambda (VPC-enabled) |
| `aura-hitl-scheduler-dev` | Expiration processor for HITL approval requests |
| `aura-threat-intel-scheduler-dev` | CVE/CISA threat feed processor |

---

## Quick Reference: Deployment Commands

```bash
# Set AWS profile
export AWS_PROFILE=aura-admin

# Check stack status
aws cloudformation describe-stacks --stack-name aura-orchestrator-dispatcher-dev \
  --query 'Stacks[0].StackStatus' --output text --region us-east-1

# View failure reasons
aws cloudformation describe-stack-events --stack-name aura-orchestrator-dispatcher-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table --region us-east-1

# Delete failed stack
aws cloudformation delete-stack --stack-name aura-orchestrator-dispatcher-dev --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name aura-orchestrator-dispatcher-dev --region us-east-1

# Trigger Foundation build (IAM changes)
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1

# Trigger Serverless build
aws codebuild start-build --project-name aura-serverless-deploy-dev --region us-east-1
```

---

## Common Failure Patterns

### 1. IAM Permission Denied Errors

**Symptom:** `AccessDenied` or `is not authorized to perform` in CloudFormation events.

**Diagnosis:**
```bash
aws cloudformation describe-stack-events --stack-name <STACK_NAME> \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].ResourceStatusReason' \
  --output text --region us-east-1 | grep -i "not authorized"
```

**Resolution:**
1. Identify the missing permission from the error message
2. Add to `deploy/cloudformation/codebuild-serverless.yaml`
3. Commit and push
4. Run Foundation build to deploy IAM changes
5. Delete failed stack
6. Run Serverless build

**Common Missing Permissions (Historical):**

| Permission | Resource Type | Error Pattern |
|------------|---------------|---------------|
| `lambda:CreateFunctionUrlConfig` | Lambda Function URL | "not authorized to perform: lambda:CreateFunctionUrlConfig" |
| `lambda:CreateEventSourceMapping` | SQS/DynamoDB triggers | "not authorized to perform: lambda:CreateEventSourceMapping" |
| `lambda:TagResource` | Event source mappings | "not authorized to perform: lambda:TagResource on resource: ...event-source-mapping" |
| `cloudwatch:TagResource` | CloudWatch Alarms | "not authorized to perform: cloudwatch:TagResource on resource: ...alarm:" |
| `ec2:CreateSecurityGroup` | VPC Lambda | "not authorized to perform: ec2:CreateSecurityGroup" |
| `dynamodb:CreateTable` | DynamoDB tables | "not authorized to perform: dynamodb:CreateTable" |
| `sqs:CreateQueue` | SQS queues | "not authorized to perform: sqs:CreateQueue" |
| `events:CreateEventBus` | Custom EventBridge bus | "not authorized to perform: events:CreateEventBus" |
| `iam:CreateRole` | Lambda execution roles | "not authorized to perform: iam:CreateRole on resource: ...role/<role-name>" |

---

### 2. Lambda Reserved Concurrency Quota Error

**Symptom:**
```
The requested reservation for function exceeds account concurrent execution limit.
```

**Cause:** AWS accounts have a default concurrent execution limit (often 10 for new accounts). `ReservedConcurrentExecutions` requires at least 10 unreserved.

**Resolution:** Comment out `ReservedConcurrentExecutions` in Lambda templates:
```yaml
# ReservedConcurrentExecutions: 10  # Disabled - account quota insufficient
```

**Affected Templates:**
- `deploy/cloudformation/hitl-callback.yaml`
- `deploy/cloudformation/orchestrator-dispatcher.yaml`
- `deploy/cloudformation/hitl-scheduler.yaml`

**Permanent Fix:** Request AWS support to increase concurrent execution quota.

---

### 3. Lambda Function URL CORS Invalid Origin

**Symptom:**
```
Invalid origin in Cors configuration: https://*.aenealabs.com
```

**Cause:** Lambda Function URLs do not support wildcard subdomains in CORS origins.

**Resolution:** Use explicit origins or `*` for development:
```yaml
Cors:
  AllowOrigins:
    - '*'  # Development only
    # Production: list specific origins
    # - 'https://app.aenealabs.com'
    # - 'https://api.aenealabs.com'
```

---

### 4. CloudFormation Export Name Mismatch

**Symptom:**
```
No export named 'aura-private-subnet-1-dev' found
```

**Cause:** Import name doesn't match actual export from networking stack.

**Diagnosis:**
```bash
aws cloudformation list-exports --query 'Exports[?contains(Name, `subnet`) || contains(Name, `Subnet`)].[Name,Value]' --output table --region us-east-1
```

**Resolution:** Update import references to match actual exports:
```yaml
# Wrong
SubnetIds:
  - !ImportValue aura-private-subnet-1-dev

# Correct
SubnetIds:
  - !ImportValue
    Fn::Sub: '${ProjectName}-networking-${Environment}-PrivateSubnet1Id'
```

---

### 5. IAM Role Name Mismatch

**Symptom:**
```
is not authorized to perform: iam:CreateRole on resource: arn:aws:iam::ACCOUNT:role/aura-expiration-processor-role-dev
```

**Cause:** CodeBuild IAM policy expects different role name pattern than template creates.

**Diagnosis:**
```bash
# Check what role name the template creates
grep -r "RoleName:" deploy/cloudformation/hitl-scheduler.yaml

# Check what pattern CodeBuild expects
grep -r "expiration-processor" deploy/cloudformation/codebuild-serverless.yaml
```

**Resolution:** Ensure role names match between:
- CloudFormation template `RoleName` property
- CodeBuild IAM policy `Resource` patterns

---

### 6. Missing Lambda S3 Artifact

**Symptom:**
```
The specified key does not exist. (S3 NoSuchKey)
```

**Cause:** Buildspec doesn't package/upload Lambda code before deployment.

**Resolution:** Ensure buildspec includes:
1. Lambda packaging step
2. S3 key variable definition
3. S3 upload command
4. Parameters passed to CloudFormation

Example fix for hitl-scheduler:
```yaml
# 1. Package
- EXPIRATION_PROCESSOR_PACKAGE="/tmp/lambda-packages/expiration-processor.zip"
- cd src && zip -r $EXPIRATION_PROCESSOR_PACKAGE lambda/expiration_processor.py && cd ..

# 2. Define S3 key
- EXPIRATION_PROCESSOR_S3_KEY="lambda/expiration-processor-${TIMESTAMP}.zip"

# 3. Upload
- aws s3 cp $EXPIRATION_PROCESSOR_PACKAGE s3://$LAMBDA_BUCKET/$EXPIRATION_PROCESSOR_S3_KEY

# 4. Pass to CloudFormation
--parameters \
  ParameterKey=LambdaS3Bucket,ParameterValue=$LAMBDA_BUCKET \
  ParameterKey=LambdaS3Key,ParameterValue=$EXPIRATION_PROCESSOR_S3_KEY
```

---

### 7. VPC Lambda Deletion Takes Forever

**Symptom:** Stack deletion stuck in `DELETE_IN_PROGRESS` for 10-40 minutes.

**Cause:** VPC-enabled Lambda functions create Elastic Network Interfaces (ENIs) that take time to detach.

**Diagnosis:**
```bash
aws ec2 describe-network-interfaces \
  --filters "Name=description,Values=*orchestrator*" \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]' \
  --output table --region us-east-1
```

**Resolution:** Wait. ENI cleanup is handled automatically but can take up to 40 minutes.

**Prevention:** Don't use VPC for Lambdas unless required (e.g., accessing VPC resources like Neptune, OpenSearch).

---

### 8. Stack in UPDATE_ROLLBACK_FAILED State

**Symptom:** Stack stuck in `UPDATE_ROLLBACK_FAILED` and cannot be updated or deleted.

**Diagnosis:**
```bash
aws cloudformation describe-stack-events --stack-name <STACK> \
  --query 'StackEvents[?ResourceStatus==`UPDATE_ROLLBACK_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table --region us-east-1
```

**Resolution Options:**

1. **Continue rollback (skip problematic resources):**
```bash
aws cloudformation continue-update-rollback --stack-name <STACK> \
  --resources-to-skip <RESOURCE_ID> --region us-east-1
```

2. **Delete stack (force):**
```bash
aws cloudformation delete-stack --stack-name <STACK> --region us-east-1
```

If delete fails, use retain option for problematic resources:
```bash
aws cloudformation delete-stack --stack-name <STACK> \
  --retain-resources <RESOURCE_ID> --region us-east-1
```

---

## Deployment Workflow

### Standard Deployment

```
1. Developer commits code
         ↓
2. Push to main branch
         ↓
3. Foundation CodeBuild (IAM changes)
         ↓
4. Serverless CodeBuild (Lambda stacks)
         ↓
5. Verify stack status
```

### Recovery from Failed Deployment

```
1. Identify failure cause (describe-stack-events)
         ↓
2. Fix template or IAM permissions
         ↓
3. Commit and push
         ↓
4. Run Foundation build (if IAM changed)
         ↓
5. Delete failed stack
         ↓
6. Wait for deletion complete
         ↓
7. Run Serverless build
         ↓
8. Verify stack status
```

---

## IAM Permission Reference

The serverless CodeBuild role requires these permission categories:

| Category | Actions | Resource Pattern |
|----------|---------|------------------|
| **Lambda Functions** | Create, Update, Delete, Get, Invoke, Tag | `arn:aws:lambda:*:*:function:${ProjectName}-*` |
| **Lambda Function URLs** | CreateFunctionUrlConfig, UpdateFunctionUrlConfig, DeleteFunctionUrlConfig, GetFunctionUrlConfig | `arn:aws:lambda:*:*:function:${ProjectName}-*` |
| **Lambda Event Source Mappings** | CreateEventSourceMapping, DeleteEventSourceMapping, GetEventSourceMapping, UpdateEventSourceMapping, ListEventSourceMappings, TagResource, UntagResource | `*` |
| **Lambda Layers** | GetLayerVersion, PublishLayerVersion | `arn:aws:lambda:*:*:layer:*` |
| **CloudWatch Logs** | CreateLogGroup, DeleteLogGroup, PutRetentionPolicy, TagResource | `arn:aws:logs:*:*:log-group:/aws/lambda/${ProjectName}-*` |
| **CloudWatch Alarms** | PutMetricAlarm, DeleteAlarms, DescribeAlarms, EnableAlarmActions, DisableAlarmActions, TagResource, UntagResource, ListTagsForResource | `arn:aws:cloudwatch:*:*:alarm:${ProjectName}-*` |
| **IAM Roles** | CreateRole, DeleteRole, GetRole, PutRolePolicy, DeleteRolePolicy, AttachRolePolicy, DetachRolePolicy, PassRole, TagRole, UntagRole | Role patterns for Lambda execution roles |
| **EC2 (VPC Lambda)** | CreateSecurityGroup, DeleteSecurityGroup, DescribeSecurityGroups, AuthorizeSecurityGroupIngress/Egress, RevokeSecurityGroupIngress/Egress, CreateTags, DescribeVpcs, DescribeSubnets, DescribeNetworkInterfaces, CreateNetworkInterface, DeleteNetworkInterface | `*` |
| **DynamoDB** | CreateTable, DeleteTable, DescribeTable, UpdateTable, UpdateTimeToLive, DescribeTimeToLive, TagResource, UntagResource | `arn:aws:dynamodb:*:*:table/${ProjectName}-*` |
| **SQS** | CreateQueue, DeleteQueue, GetQueueAttributes, SetQueueAttributes, TagQueue, UntagQueue, GetQueueUrl, AddPermission, RemovePermission | `arn:aws:sqs:*:*:${ProjectName}-*` |
| **EventBridge Rules** | PutRule, DeleteRule, PutTargets, RemoveTargets, DescribeRule, ListRules, ListTargetsByRule, TagResource, UntagResource | `arn:aws:events:*:*:rule/${ProjectName}-*` |
| **EventBridge Event Bus** | CreateEventBus, DeleteEventBus, DescribeEventBus, PutPermission, RemovePermission | `arn:aws:events:*:*:event-bus/${ProjectName}-*` |
| **SNS** | Publish, GetTopicAttributes, ListTopics | `arn:aws:sns:*:*:${ProjectName}-*` |
| **Secrets Manager** | GetSecretValue, DescribeSecret | `arn:aws:secretsmanager:*:*:secret:${ProjectName}/*` |

---

## Monitoring and Alerts

### Build Status Check
```bash
# Recent builds
aws codebuild list-builds-for-project --project-name aura-serverless-deploy-dev \
  --max-items 5 --region us-east-1

# Build details
aws codebuild batch-get-builds --ids <BUILD_ID> \
  --query 'builds[0].{status:buildStatus,phase:currentPhase}' --output json --region us-east-1
```

### Stack Health Check
```bash
for stack in aura-hitl-callback-dev aura-orchestrator-dispatcher-dev aura-hitl-scheduler-dev aura-threat-intel-scheduler-dev; do
  echo -n "$stack: "
  aws cloudformation describe-stacks --stack-name $stack \
    --query 'Stacks[0].StackStatus' --output text --region us-east-1 2>/dev/null || echo "NOT FOUND"
done
```

---

## Related Documentation

- [CI/CD Setup Guide](../CICD_SETUP_GUIDE.md)
- [AWS Naming Standards](../AWS_NAMING_AND_TAGGING_STANDARDS.md)
- [Serverless CodeBuild Template](../../deploy/cloudformation/codebuild-serverless.yaml)
- [Serverless Buildspec](../../deploy/buildspecs/buildspec-serverless.yml)

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-12 | Platform Engineering | Initial creation documenting 11 fix categories |
