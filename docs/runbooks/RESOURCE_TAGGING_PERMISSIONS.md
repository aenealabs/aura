# Runbook: Resource Tagging Permission Errors (UnauthorizedTaggingOperation)

**Purpose:** Resolve CloudFormation deployment failures caused by missing tag management permissions on CloudWatch Logs, SNS, and other AWS resources

**Audience:** DevOps Engineers, Platform Team

**Estimated Time:** 15-30 minutes

**Last Updated:** Dec 12, 2025

---

## Problem Description

CloudFormation stack operations fail with `UnauthorizedTaggingOperation` when CodeBuild IAM roles lack permissions to manage resource tags. This commonly occurs with:

- **CloudWatch Logs:** `logs:TagResource`, `logs:UntagResource`
- **SNS Topics:** `sns:TagResource`, `sns:UntagResource`
- **DynamoDB Tables:** `dynamodb:TagResource`, `dynamodb:UntagResource`
- **Lambda Functions:** `lambda:TagResource`, `lambda:UntagResource`
- **S3 Buckets:** `s3:PutBucketTagging`, `s3:GetBucketTagging`
- **IAM Roles:** `iam:TagRole`, `iam:UntagRole`, `iam:UpdateAssumeRolePolicy`

### Symptoms

**Stack Status:** `UPDATE_FAILED` or `UPDATE_ROLLBACK_FAILED`

**Error Messages:**

```
Resource handler returned message: "Encountered a permissions error performing a tagging
operation, please add required tag permissions. See
https://repost.aws/knowledge-center/cloudformation-tagging-permission-error for how to resolve.

Resource handler returned message: "User: arn:aws:sts::123456789012:assumed-role/
aura-serverless-codebuild-role-dev/AWSCodeBuild-xxx is not authorized to perform:
logs:TagResource on resource: arn:aws:logs:us-east-1:123456789012:log-group:/aura/runbook-agent/dev
because no identity-based policy allows the logs:TagResource action"
(HandlerErrorCode: UnauthorizedTaggingOperation)

Resource handler returned message: "User: ... is not authorized to perform: SNS:TagResource
on resource: arn:aws:sns:us-east-1:123456789012:aura-runbook-notifications-dev because no
identity-based policy allows the SNS:TagResource action"
(HandlerErrorCode: AccessDenied)
```

### Root Cause

1. **Missing Tag Actions:** IAM policy has CRUD permissions but lacks `TagResource`/`UntagResource`
2. **Resource ARN Pattern Mismatch:** Log group uses custom path (e.g., `/${ProjectName}/*`) but IAM only allows `/aws/codebuild/*` or `/aws/lambda/*`
3. **Rollback Requires UntagResource:** Even if `TagResource` is present, rollbacks need `UntagResource` to revert tag changes

---

## Incident: aura-runbook-agent-dev (Dec 12, 2025)

### Timeline

| Time (UTC) | Event |
|------------|-------|
| 04:54 | First deployment attempt fails - missing `logs:TagResource` |
| 05:02 | Second attempt fails - same error |
| 05:06 | IAM fix committed (added `/${ProjectName}/*` log pattern) |
| 05:12 | Third attempt fails - missing `logs:UntagResource` for rollback |
| 05:12 | Stack enters `UPDATE_ROLLBACK_FAILED` state |
| 05:13 | Manual `continue-update-rollback` with resources skipped |
| 05:15 | IAM fix committed (added `UntagResource` + SNS permissions) |
| 05:17 | Codebuild stack redeployed with new IAM permissions |
| 05:21 | Final deployment succeeds - stack `UPDATE_COMPLETE` |

### Resources Affected

- `RunbookAgentLogGroup` - CloudWatch log group at `/${ProjectName}/runbook-agent/${Environment}`
- `RunbookNotificationTopic` - SNS topic `aura-runbook-notifications-dev`
- `RunbookIndexTable` - DynamoDB table (cascading failure from log group)

### Fix Applied

**File:** `deploy/cloudformation/codebuild-serverless.yaml`

**Commit 1:** `219170b` - Added application log group pattern
```yaml
# Application log groups (runbook-agent, incident-response, etc.)
- !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/${ProjectName}/*'
- !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/${ProjectName}/*:*'
```

**Commit 2:** `85ecd97` - Added `UntagResource` and SNS permissions
```yaml
# CloudWatch Logs
Action:
  - logs:TagResource
  - logs:UntagResource  # Required for rollbacks

# SNS Topics
Action:
  - sns:CreateTopic
  - sns:DeleteTopic
  - sns:TagResource
  - sns:UntagResource
  - sns:ListTagsForResource
```

---

## Quick Resolution

### Step 1: Identify the Failed Resource and Permission

```bash
# Check stack events for failed resources
aws cloudformation describe-stack-events \
  --stack-name aura-runbook-agent-dev \
  --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED`].{Resource:LogicalResourceId,Reason:ResourceStatusReason}' \
  --output table
```

Look for:
- `logs:TagResource` or `logs:UntagResource` - CloudWatch Logs permission
- `sns:TagResource` or `SNS:TagResource` - SNS permission
- Resource ARN pattern (e.g., `/aura/runbook-agent/dev` vs `/aws/lambda/*`)

### Step 2: If Stack is in UPDATE_ROLLBACK_FAILED State

```bash
# Continue rollback by skipping the problematic resources
aws cloudformation continue-update-rollback \
  --stack-name aura-runbook-agent-dev \
  --resources-to-skip RunbookAgentLogGroup RunbookIndexTable \
  --region us-east-1

# Wait for rollback to complete
aws cloudformation wait stack-rollback-complete \
  --stack-name aura-runbook-agent-dev
```

### Step 3: Update IAM Policy

Edit the appropriate CodeBuild template (e.g., `codebuild-serverless.yaml`):

**For CloudWatch Logs:**
```yaml
- Effect: Allow
  Action:
    - logs:CreateLogGroup
    - logs:DeleteLogGroup
    - logs:PutRetentionPolicy
    - logs:TagResource      # Add if missing
    - logs:UntagResource    # Add if missing - required for rollbacks!
  Resource:
    # Standard AWS service log groups
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/codebuild/${ProjectName}-*'
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${ProjectName}-*'
    # Application log groups (custom paths like /aura/*)
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/${ProjectName}/*'
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/${ProjectName}/*:*'
```

**For SNS Topics:**
```yaml
- Effect: Allow
  Action:
    - sns:CreateTopic
    - sns:DeleteTopic
    - sns:Publish
    - sns:Subscribe
    - sns:Unsubscribe
    - sns:GetTopicAttributes
    - sns:SetTopicAttributes
    - sns:TagResource        # Add if missing
    - sns:UntagResource      # Add if missing
    - sns:ListTagsForResource
  Resource:
    - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-*'
```

### Step 4: Deploy Updated IAM

```bash
# Redeploy the CodeBuild stack (bootstrap stack)
export AWS_PROFILE=aura-admin
./deploy/scripts/deploy-serverless-codebuild.sh

# Or manually:
aws cloudformation update-stack \
  --stack-name aura-codebuild-serverless-dev \
  --template-body file://deploy/cloudformation/codebuild-serverless.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters ParameterKey=ProjectName,ParameterValue=aura \
               ParameterKey=Environment,ParameterValue=dev \
               ParameterKey=GitHubRepository,ParameterValue=https://github.com/aenealabs/aura \
               ParameterKey=GitHubBranch,ParameterValue=main

aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-serverless-dev
```

### Step 5: Re-run CodeBuild Deployment

```bash
aws codebuild start-build \
  --project-name aura-serverless-deploy-dev \
  --region us-east-1
```

---

## Incident: aura-dns-blocklist-lambda-dev (Dec 12, 2025)

### Timeline

| Time (UTC) | Event |
|------------|-------|
| 05:30 | First deployment attempt fails - missing CloudFormation stack permission |
| 05:35 | IAM fix committed (added dns-blocklist-lambda stack ARN) |
| 05:40 | Second attempt fails - missing `s3:PutBucketTagging` on blocklist-config |
| 05:42 | Stack enters `UPDATE_ROLLBACK_FAILED` state |
| 05:43 | Manual `continue-update-rollback` with resources skipped |
| 05:45 | IAM fix committed (added S3 bucket permissions) |
| 05:50 | Third attempt fails - missing `iam:TagRole`, `iam:UntagRole` |
| 05:52 | Stack enters `UPDATE_ROLLBACK_FAILED` state again |
| 05:53 | Manual `continue-update-rollback` with roles skipped |
| 05:55 | IAM fix committed (added IAM role permissions) |
| 06:00 | Fourth attempt fails - missing `iam:UpdateAssumeRolePolicy` |
| 06:02 | Stack enters `UPDATE_ROLLBACK_FAILED` state |
| 06:03 | Manual `continue-update-rollback` with IRSA role skipped |
| 06:05 | IAM fix committed (added UpdateAssumeRolePolicy action) |
| 06:10 | CodeBuild serverless stack redeployed |
| 06:15 | Final deployment succeeds - stack `UPDATE_COMPLETE` |

### Resources Affected

- `BlocklistConfigBucket` - S3 bucket `aura-blocklist-config-dev`
- `BlocklistLambdaRole` - IAM role `aura-blocklist-lambda-role-dev`
- `BlocklistSyncIRSARole` - IAM role `aura-blocklist-sync-role-dev` (IRSA for K8s)

### Fix Applied

**File:** `deploy/cloudformation/codebuild-serverless.yaml`

**Commit 1:** Added CloudFormation stack permission
```yaml
# DNS Blocklist Lambda (Layer 6.6: Threat Intelligence)
- !Sub 'arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-dns-blocklist-lambda-${Environment}/*'
```

**Commit 2:** Added S3 bucket permissions
```yaml
# S3 - DNS Blocklist bucket (Layer 6.6)
- Effect: Allow
  Action:
    - s3:CreateBucket
    - s3:DeleteBucket
    - s3:PutEncryptionConfiguration
    - s3:PutBucketVersioning
    - s3:PutBucketPublicAccessBlock
    - s3:PutLifecycleConfiguration
    - s3:PutBucketTagging       # Required for tagging
    - s3:GetBucketTagging       # Required for tag reads
    - s3:GetBucketPolicy
    - s3:PutBucketPolicy
    - s3:DeleteBucketPolicy
    - s3:GetBucketLocation
    - s3:ListBucket
    - s3:PutObject
    - s3:GetObject
    - s3:DeleteObject
  Resource:
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-blocklist-config-${Environment}'
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-blocklist-config-${Environment}/*'
```

**Commit 3:** Added IAM role permissions
```yaml
# DNS Blocklist Lambda roles (Layer 6.6)
- !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-blocklist-lambda-role-${Environment}'
- !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-blocklist-sync-role-${Environment}'
```

**Commit 4:** Added UpdateAssumeRolePolicy action
```yaml
Action:
  - iam:CreateRole
  - iam:DeleteRole
  - iam:GetRole
  - iam:PutRolePolicy
  - iam:DeleteRolePolicy
  - iam:GetRolePolicy
  - iam:AttachRolePolicy
  - iam:DetachRolePolicy
  - iam:TagRole
  - iam:UntagRole
  - iam:UpdateAssumeRolePolicy  # Required for IRSA role updates
  - iam:ListAttachedRolePolicies
  - iam:ListRolePolicies
  - iam:PassRole
```

### Key Learnings

1. **IRSA Roles Require UpdateAssumeRolePolicy:** Roles with OIDC trust relationships (like `BlocklistSyncIRSARole`) need `iam:UpdateAssumeRolePolicy` to modify the trust policy during updates.

2. **S3 Buckets Need Explicit Tag Permissions:** Unlike some services, S3 buckets require explicit `s3:PutBucketTagging` and `s3:GetBucketTagging` permissions (not `s3:TagResource`).

3. **Multiple Rollback Cycles Common:** Complex stacks with multiple new resource types often require iterative permission fixes, with `continue-update-rollback` to recover between attempts.

---

## Common Resource ARN Patterns

| Resource Type | Standard Path | Custom Path | IAM Pattern Needed |
|--------------|---------------|-------------|-------------------|
| CodeBuild Logs | `/aws/codebuild/aura-*` | - | `/aws/codebuild/${ProjectName}-*` |
| Lambda Logs | `/aws/lambda/aura-*` | - | `/aws/lambda/${ProjectName}-*` |
| Application Logs | - | `/aura/runbook-agent/dev` | `/${ProjectName}/*` |
| SNS Topics | - | `aura-runbook-notifications-dev` | `${ProjectName}-*` |
| S3 Buckets | - | `aura-blocklist-config-dev` | `${ProjectName}-*-${Environment}` |
| IAM Roles | - | `aura-blocklist-lambda-role-dev` | `${ProjectName}-*-role-${Environment}` |

---

## Prevention Checklist

When adding new CloudFormation resources with Tags:

- [ ] Check if resource type requires `TagResource`/`UntagResource` permissions
- [ ] Verify resource ARN matches IAM policy patterns
- [ ] Include BOTH `TagResource` AND `UntagResource` (rollbacks need untag)
- [ ] For S3 buckets: Use `s3:PutBucketTagging`/`s3:GetBucketTagging` (not TagResource)
- [ ] For IAM roles: Add `iam:TagRole`, `iam:UntagRole`
- [ ] For IRSA roles: Add `iam:UpdateAssumeRolePolicy` for trust policy updates
- [ ] Test in dev environment before promoting to prod
- [ ] Update this runbook if new patterns discovered

---

## Related Documentation

- [AWS Knowledge Center: Tagging Permission Errors](https://repost.aws/knowledge-center/cloudformation-tagging-permission-error)
- [CloudFormation IAM Permissions Runbook](./CLOUDFORMATION_IAM_PERMISSIONS.md)
- [Serverless Deployment Runbook](../operations/SERVERLESS_DEPLOYMENT_RUNBOOK.md)
- [CI/CD Setup Guide](../CICD_SETUP_GUIDE.md)
