# Runbook: CloudFormation IAM Permission Errors (AccessDenied)

**Purpose:** Resolve CloudFormation deployment failures caused by insufficient IAM permissions on CodeBuild roles

**Audience:** DevOps Engineers, Platform Team, Security Engineers

**Estimated Time:** 15-45 minutes

**Last Updated:** Dec 11, 2025

---

## Problem Description

CloudFormation stack operations fail with `AccessDenied` when:
- CodeBuild IAM role is missing permissions for specific CloudFormation stacks
- CodeBuild IAM role is missing permissions to manage underlying AWS resources
- New CloudFormation templates require permissions not yet granted

### Symptoms

```
An error occurred (AccessDenied) when calling the CreateStack operation:
User: arn:aws:sts::123456789012:assumed-role/aura-application-codebuild-role-dev/AWSCodeBuild-xxx
is not authorized to perform: cloudformation:CreateStack on resource:
arn:aws:cloudformation:us-east-1:123456789012:stack/aura-ecr-api-dev/*
because no identity-based policy allows the cloudformation:CreateStack action

An error occurred (AccessDenied) when calling the UpdateStack operation:
User: ... is not authorized to perform: cloudformation:UpdateStack on resource:
arn:aws:cloudformation:us-east-1:123456789012:stack/aura-cognito-dev/*
```

### Root Cause

The CodeBuild IAM role (`aura-application-codebuild-role-dev`) has CloudFormation permissions scoped to specific stack ARN patterns. New stacks added to the buildspec may not be included in the IAM policy.

---

## Quick Resolution

### Step 1: Identify Missing Permissions

```bash
# Check the exact error in build logs
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-application-deploy-dev \
  --query 'ids[0]' \
  --output text)

aws logs filter-log-events \
  --log-group-name /aws/codebuild/aura-application-deploy-dev \
  --filter-pattern "AccessDenied" \
  --query 'events[*].message' \
  --output text | head -20
```

### Step 2: Update IAM Policy

Edit `deploy/cloudformation/codebuild-application.yaml` to add the missing stack ARN:

```yaml
# Add to CloudFormation permissions Resource list
Resource:
  - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-NEW-STACK-NAME-${Environment}/*'
```

### Step 3: Deploy Updated IAM

```bash
aws cloudformation update-stack \
  --stack-name aura-codebuild-application-dev \
  --template-body file://deploy/cloudformation/codebuild-application.yaml \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-application-dev
```

### Step 4: Re-run CodeBuild

```bash
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

## Detailed Diagnostic Steps

### Step 1: Identify the Denied Action and Resource

```bash
# Parse the error message for:
# 1. Action (cloudformation:CreateStack, cloudformation:UpdateStack, etc.)
# 2. Resource ARN (the stack that couldn't be accessed)
# 3. Principal (the IAM role attempting the action)

# Example parsing from logs:
aws logs filter-log-events \
  --log-group-name /aws/codebuild/aura-application-deploy-dev \
  --filter-pattern "AccessDenied" \
  --query 'events[-5:].message' \
  --output text
```

### Step 2: Review Current IAM Policy

```bash
# Get the CodeBuild role name
ROLE_NAME="aura-application-codebuild-role-dev"

# List inline policies
aws iam list-role-policies --role-name $ROLE_NAME

# Get the policy document
aws iam get-role-policy \
  --role-name $ROLE_NAME \
  --policy-name ApplicationDeployPolicy \
  --query 'PolicyDocument.Statement[?Effect==`Allow`]' \
  --output yaml
```

### Step 3: Compare with Required Permissions

Check which stacks the buildspec deploys:

```bash
# List all CloudFormation operations in the buildspec
grep -E "cloudformation (create-stack|update-stack|deploy)" \
  deploy/buildspecs/buildspec-application.yml
```

---

## Resolution Procedures

### Procedure 1: Add Missing CloudFormation Stack ARNs

**When:** New CloudFormation stacks added to buildspec

Edit `deploy/cloudformation/codebuild-application.yaml`:

```yaml
# Find the CloudFormation permissions section (~line 126-148)
# CloudFormation - Application stacks
- Effect: Allow
  Action:
    - cloudformation:CreateStack
    - cloudformation:UpdateStack
    - cloudformation:DeleteStack
    # ... other actions
  Resource:
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-bedrock-infrastructure-${Environment}/*'
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-ecr-dnsmasq-${Environment}/*'
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-ecr-api-${Environment}/*'
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-cognito-${Environment}/*'
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-bedrock-guardrails-${Environment}/*'
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-irsa-api-${Environment}/*'
    # ADD NEW STACKS HERE:
    - !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-NEW-STACK-${Environment}/*'
```

### Procedure 2: Add Missing Service Permissions

**When:** CloudFormation needs to create resources the role can't manage

Common services that need explicit permissions:

```yaml
# Cognito User Pools
- Effect: Allow
  Action:
    - cognito-idp:CreateUserPool
    - cognito-idp:DeleteUserPool
    - cognito-idp:DescribeUserPool
    - cognito-idp:UpdateUserPool
    - cognito-idp:CreateUserPoolClient
    - cognito-idp:DeleteUserPoolClient
    - cognito-idp:CreateUserPoolDomain
    - cognito-idp:DeleteUserPoolDomain
    - cognito-idp:CreateGroup
    - cognito-idp:DeleteGroup
    - cognito-idp:TagResource
    - cognito-idp:UntagResource
  Resource:
    - !Sub 'arn:aws:cognito-idp:${AWS::Region}:${AWS::AccountId}:userpool/*'

# Bedrock Guardrails
# NOTE: CloudFormation requires ListTagsForResource to manage tags on Bedrock resources
- Effect: Allow
  Action:
    - bedrock:CreateGuardrail
    - bedrock:DeleteGuardrail
    - bedrock:GetGuardrail
    - bedrock:UpdateGuardrail
    - bedrock:ListGuardrails
    - bedrock:CreateGuardrailVersion
    - bedrock:DeleteGuardrailVersion
    - bedrock:GetGuardrailVersion
    - bedrock:ListGuardrailVersions
    - bedrock:ListTagsForResource
    - bedrock:TagResource
    - bedrock:UntagResource
  Resource:
    - !Sub 'arn:aws:bedrock:${AWS::Region}:${AWS::AccountId}:guardrail/*'

# SSM Parameter Store
- Effect: Allow
  Action:
    - ssm:GetParameter
    - ssm:GetParameters
    - ssm:PutParameter
    - ssm:DeleteParameter
    - ssm:AddTagsToResource
    - ssm:RemoveTagsFromResource
  Resource:
    - !Sub 'arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${ProjectName}/${Environment}/*'
```

### Procedure 3: Deploy the Updated IAM Policy

```bash
# Step 1: Validate the template
cfn-lint deploy/cloudformation/codebuild-application.yaml

# Step 2: Update the stack
aws cloudformation update-stack \
  --stack-name aura-codebuild-application-dev \
  --template-body file://deploy/cloudformation/codebuild-application.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile aura-admin

# Step 3: Wait for completion
aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-application-dev \
  --profile aura-admin

# Step 4: Verify the role policy was updated
aws iam get-role-policy \
  --role-name aura-application-codebuild-role-dev \
  --policy-name ApplicationDeployPolicy \
  --query 'PolicyDocument.Statement | length(@)'

# Step 5: Re-run the failed CodeBuild
aws codebuild start-build \
  --project-name aura-application-deploy-dev \
  --profile aura-admin
```

---

## Common Permission Patterns

### Pattern 1: New CloudFormation Stack

```yaml
# Add to Resource list in CloudFormation permissions
- !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-STACK-NAME-${Environment}/*'
```

### Pattern 2: New AWS Service

```yaml
# Add new policy statement for the service
- Effect: Allow
  Action:
    - servicename:Create*
    - servicename:Delete*
    - servicename:Describe*
    - servicename:Update*
    - servicename:Tag*
    - servicename:Untag*
  Resource:
    - !Sub 'arn:aws:servicename:${AWS::Region}:${AWS::AccountId}:resource/${ProjectName}-*'
```

### Pattern 3: Bedrock Guardrails (CloudFormation Tag Management)

**Important:** CloudFormation requires `ListTagsForResource` to manage tags on Bedrock resources. Without this permission, CloudFormation fails with AccessDenied even if basic CRUD permissions are granted.

```yaml
# Bedrock Guardrails - Include ListTagsForResource for CloudFormation
- Effect: Allow
  Action:
    - bedrock:CreateGuardrail
    - bedrock:DeleteGuardrail
    - bedrock:GetGuardrail
    - bedrock:UpdateGuardrail
    - bedrock:ListGuardrails
    - bedrock:CreateGuardrailVersion
    - bedrock:DeleteGuardrailVersion
    - bedrock:GetGuardrailVersion
    - bedrock:ListGuardrailVersions
    - bedrock:ListTagsForResource    # Required for CloudFormation tag management
    - bedrock:TagResource
    - bedrock:UntagResource
  Resource:
    - !Sub 'arn:aws:bedrock:${AWS::Region}:${AWS::AccountId}:guardrail/*'
```

### Pattern 4: Cross-Account or Cross-Region Access

```yaml
# Be explicit about regions and accounts
- Effect: Allow
  Action:
    - s3:GetObject
  Resource:
    - 'arn:aws:s3:::shared-artifacts-bucket/*'
  Condition:
    StringEquals:
      aws:SourceAccount: !Ref AWS::AccountId
```

---

## Prevention

### 1. Checklist Before Adding New Stacks

Before adding a new CloudFormation stack to a buildspec:

- [ ] Is the stack ARN pattern in the CodeBuild IAM policy?
- [ ] Does the CodeBuild role have permissions for all resource types in the template?
- [ ] Are there any IAM PassRole requirements?
- [ ] Does the template create resources that need KMS encryption?

### 2. Use Least Privilege with Wildcards Carefully

```yaml
# GOOD: Scoped to project resources
Resource:
  - !Sub 'arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*'

# BAD: Too broad
Resource:
  - '*'
```

### 3. Test Permission Changes in Dev First

```bash
# Always update dev environment first
aws cloudformation update-stack \
  --stack-name aura-codebuild-application-dev \
  --template-body file://deploy/cloudformation/codebuild-application.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# Test with a build
aws codebuild start-build --project-name aura-application-deploy-dev

# Only after success, update qa/prod
```

---

## Related Documentation

- [CodeBuild Application IAM Template](../../deploy/cloudformation/codebuild-application.yaml)
- [Application Buildspec](../../deploy/buildspecs/buildspec-application.yml)
- [CLAUDE.md - Security & IAM Section](../../CLAUDE.md#security--code-review)
- [AWS IAM Policy Evaluation Logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)

---

## Appendix: CodeBuild Role Permission Reference

| Service | Required For | Key Actions |
|---------|--------------|-------------|
| CloudFormation | Stack management | Create/Update/DeleteStack, DescribeStacks |
| ECR | Container images | GetAuthorizationToken, PutImage, BatchGetImage |
| EKS | Kubernetes access | DescribeCluster, UpdateKubeconfig |
| Cognito | User authentication | CreateUserPool, CreateUserPoolClient |
| Bedrock | AI guardrails | CreateGuardrail, UpdateGuardrail, **ListTagsForResource** |
| SSM | Parameter storage | GetParameter, PutParameter |
| IAM | Role creation | CreateRole, AttachRolePolicy, PassRole |
| DynamoDB | Table management | CreateTable, UpdateTable |
| SNS | Notifications | CreateTopic, Subscribe |
| CloudWatch | Monitoring | PutMetricAlarm, PutMetricData |
