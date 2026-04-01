# Break/Fix Report: Incident Response CodeBuild IAM Permissions

**Date Identified:** 2025-12-09
**Date Resolved:** 2025-12-09
**Severity:** High
**Affected Component:** `aura-incident-response-deploy-dev` CodeBuild project
**Resolution Build:** Build #10 (SUCCEEDED)
**Commit:** 82085af

---

## Executive Summary

The `aura-incident-response-deploy-dev` CodeBuild project failed repeatedly (builds #1-9) due to insufficient IAM permissions. The IAM role lacked permissions to:
1. Tag/untag CloudWatch Log Groups for Lambda functions
2. Tag/untag KMS keys created by CloudFormation

After comprehensive IAM analysis using the architecture agent, all permission gaps were identified and fixed in a single commit, resulting in a successful Build #10.

---

## Timeline

| Build # | Status | Error | Fix Applied |
|---------|--------|-------|-------------|
| 1-7 | FAILED | Various EventBridge, Step Functions, DynamoDB permission errors | Incremental fixes |
| 8 | FAILED | `kms:TagResource` denied on KMS key | Added basic KMS permissions |
| 9 | FAILED | `logs:UntagResource` denied on `/aws/lambda/aura-deployment-recorder-dev` | Identified missing Lambda log group pattern |
| 10 | **SUCCEEDED** | N/A | Comprehensive fix with architecture review-architect analysis |

---

## Symptoms

### Build #9 Error (Final Failing Build)
```
User: arn:aws:sts::123456789012:assumed-role/aura-incident-response-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: logs:UntagResource on resource:
arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/aura-deployment-recorder-dev
because no identity-based policy allows the logs:UntagResource action
```

### Build #8 Error (KMS Tagging)
```
User: arn:aws:sts::123456789012:assumed-role/aura-incident-response-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: kms:TagResource on resource:
arn:aws:kms:us-east-1:123456789012:key/xxx-xxx-xxx
```

---

## Root Cause Analysis

### Problem 1: Missing Lambda Log Group Pattern

The IAM policy had log group patterns for:
- `/aws/codebuild/${ProjectName}-*`
- `/${ProjectName}/incident-response/*`
- `/aws/states/${ProjectName}-*`
- `/aws/events/${ProjectName}-*`

**Missing:** `/aws/lambda/${ProjectName}-*`

CloudFormation creates Lambda functions that automatically create log groups under `/aws/lambda/`. When CloudFormation updates/deletes these resources, it needs `logs:TagResource` and `logs:UntagResource` permissions.

### Problem 2: KMS Permission Structure

The original KMS permissions were structured incorrectly:

```yaml
# WRONG - kms:CreateKey requires Resource: '*' but was scoped to key ARN
- Effect: Allow
  Action:
    - kms:CreateKey
    - kms:TagResource
    - kms:UntagResource
  Resource:
    - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/*'
```

**Issues:**
1. `kms:CreateKey` requires `Resource: '*'` (you can't specify a key ARN before creation)
2. `kms:TagResource`/`kms:UntagResource` need `kms:CallerAccount` condition for security
3. Alias operations need separate resource ARN patterns

---

## Resolution

### File Changed
`deploy/cloudformation/codebuild-incident-response.yaml`

### Fix 1: Add Lambda Log Group Pattern (Lines 110-111)

```yaml
# CloudWatch Logs - Added Lambda function log groups
- Effect: Allow
  Action:
    - logs:CreateLogGroup
    - logs:CreateLogStream
    - logs:PutLogEvents
    - logs:DeleteLogGroup
    - logs:PutRetentionPolicy
    - logs:TagResource
    - logs:UntagResource
  Resource:
    # ... existing patterns ...
    # NEW: Lambda function log groups (created automatically by Lambda)
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${ProjectName}-*'
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${ProjectName}-*:*'
```

### Fix 2: Restructure KMS Permissions (Lines 267-311)

Split into three separate statements:

```yaml
# KMS - Create key (requires Resource: '*')
- Effect: Allow
  Action:
    - kms:CreateKey
  Resource: '*'
  Condition:
    StringEquals:
      'aws:RequestTag/Project': !Ref ProjectName

# KMS - Key management and tagging operations
- Effect: Allow
  Action:
    - kms:DescribeKey
    - kms:EnableKey
    - kms:DisableKey
    - kms:ScheduleKeyDeletion
    - kms:CancelKeyDeletion
    - kms:PutKeyPolicy
    - kms:GetKeyPolicy
    - kms:GetKeyRotationStatus
    - kms:EnableKeyRotation
    - kms:DisableKeyRotation
    - kms:TagResource
    - kms:UntagResource
    - kms:ListResourceTags
  Resource:
    - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/*'
  Condition:
    StringEquals:
      'kms:CallerAccount': !Ref AWS::AccountId

# KMS - Alias operations (require alias ARN)
- Effect: Allow
  Action:
    - kms:CreateAlias
    - kms:DeleteAlias
    - kms:UpdateAlias
    - kms:ListAliases
  Resource:
    - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:alias/${ProjectName}-incident-*'
    - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/*'
```

---

## Diagnostic Commands Used

### Check CloudFormation Stack Events
```bash
export AWS_PROFILE=aura-admin
aws cloudformation describe-stack-events \
  --stack-name aura-incident-response-dev \
  --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table --region us-east-1
```

### Check CodeBuild Logs for Permission Errors
```bash
aws logs tail /aws/codebuild/aura-incident-response-deploy-dev \
  --filter-pattern "AccessDenied" --region us-east-1
```

### List IAM Role Policies
```bash
aws iam list-role-policies \
  --role-name aura-incident-response-codebuild-role-dev
aws iam get-role-policy \
  --role-name aura-incident-response-codebuild-role-dev \
  --policy-name IncidentResponseDeployPolicy
```

---

## Verification

### Successful Build
```bash
aws codebuild batch-get-builds \
  --ids "aura-incident-response-deploy-dev:00000000-0000-0000-0000-000000000001" \
  --query 'builds[0].{phase:currentPhase,status:buildStatus}' \
  --output table --region us-east-1

# Result:
# phase: COMPLETED
# status: SUCCEEDED
```

### CloudFormation Stack Status
```bash
aws cloudformation describe-stacks \
  --stack-name aura-incident-response-dev \
  --query 'Stacks[0].StackStatus' --output text --region us-east-1
# Result: UPDATE_COMPLETE

aws cloudformation describe-stacks \
  --stack-name aura-incident-investigation-dev \
  --query 'Stacks[0].StackStatus' --output text --region us-east-1
# Result: UPDATE_COMPLETE
```

---

## Prevention Checklist

For future CodeBuild IAM role definitions, ensure permissions cover:

### CloudWatch Logs Patterns
- [ ] `/aws/codebuild/${ProjectName}-*` - CodeBuild logs
- [ ] `/${ProjectName}/${service}/*` - Application logs
- [ ] `/aws/lambda/${ProjectName}-*` - Lambda function logs
- [ ] `/aws/states/${ProjectName}-*` - Step Functions logs
- [ ] `/aws/events/${ProjectName}-*` - EventBridge logs
- [ ] `/aws/ecs/${ProjectName}-*` - ECS task logs

### KMS Permission Structure
- [ ] `kms:CreateKey` with `Resource: '*'` and tag condition
- [ ] Key operations with `kms:CallerAccount` condition
- [ ] Alias operations with separate resource ARNs

### Tagging Actions
- [ ] `TagResource` and `UntagResource` for ALL resources CloudFormation manages
- [ ] DynamoDB, Lambda, Step Functions, EventBridge, KMS, SNS, CloudWatch Logs

---

## Related Documentation

- **Layer Runbook:** `docs/runbooks/LAYER6_SERVERLESS_RUNBOOK.md`
- **Generic Troubleshooting:** `deploy/runbooks/03-troubleshooting.md`
- **IAM Template:** `deploy/cloudformation/codebuild-incident-response.yaml`
- **BuildSpec:** `deploy/buildspecs/buildspec-incident-response.yml`

---

## Lessons Learned

1. **Use architecture review for IAM Analysis:** The architecture agent identified all permission gaps in one analysis, avoiding iterative build failures.

2. **KMS Permissions Are Complex:** `kms:CreateKey` requires `Resource: '*'` while other operations can be scoped. Always split KMS permissions into separate statements.

3. **Lambda Auto-Creates Log Groups:** Any CloudFormation template with Lambda functions needs `/aws/lambda/${ProjectName}-*` log group permissions.

4. **Include `UntagResource`:** CloudFormation updates often untag resources before retagging. Always include both `TagResource` AND `UntagResource`.

5. **Test with CloudFormation Updates:** Initial deployment may succeed, but updates reveal missing permissions when CloudFormation modifies existing resources.
