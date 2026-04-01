# QA/PROD Environment Deployment Sequence

**Project Aura - Fresh Account Deployment Guide**

**Version:** 1.0
**Last Updated:** January 2026
**Target Audience:** Platform Administrators, DevOps Engineers

---

## Executive Summary

This document provides the authoritative deployment sequence for deploying Project Aura infrastructure to a fresh AWS account (QA or PROD). It addresses circular dependency issues discovered during the QA account deployment (234567890123) that prevented successful initial bootstrapping.

**Key Insight:** The DEV environment (123456789012) was built incrementally over months, masking circular dependencies between templates. Fresh account deployments expose these dependencies because resources must be created in a specific order.

---

## Account Reference

| Environment | Account ID | Status | Notes |
|-------------|------------|--------|-------|
| DEV | 123456789012 | Active | Management Account, incrementally built |
| QA | 234567890123 | Active | Mirror of DEV, circular dependencies discovered |
| PROD | TBD | Planned | AWS GovCloud (US), CMMC L3 environment |

---

## Circular Dependencies Discovered

### Problem 1: KMS Key Policy References Non-Existent Roles

**Template:** `deploy/cloudformation/kms.yaml`

**Issue:** The KMS template creates four purpose-specific encryption keys, each with key policies that grant permissions to CodeBuild roles from multiple layers:

```yaml
# kms.yaml grants permissions to these roles (lines 57-64, 109-124, etc.)
- arn:aws:iam::ACCOUNT:role/aura-foundation-codebuild-role-ENV
- arn:aws:iam::ACCOUNT:role/aura-data-codebuild-role-ENV
- arn:aws:iam::ACCOUNT:role/aura-observability-codebuild-role-ENV
- arn:aws:iam::ACCOUNT:role/aura-application-codebuild-role-ENV
- arn:aws:iam::ACCOUNT:role/aura-security-codebuild-role-ENV
- arn:aws:iam::ACCOUNT:role/aura-incident-response-codebuild-role-ENV
```

**Why It Fails:** In a fresh account, these CodeBuild roles do not exist when KMS keys are first created. CloudFormation validates IAM principals in key policies, causing deployment failures.

**Resolution Applied:** The KMS key policies use a pattern that allows non-existent principals by relying on the root account principal with conditional ARN matching:

```yaml
# Pattern used to avoid circular dependency (lines 127-142)
- Sid: AllowProjectBackupRoles
  Effect: Allow
  Principal:
    AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
  Action: [kms:Encrypt, kms:Decrypt, kms:GenerateDataKey*, ...]
  Resource: '*'
  Condition:
    ArnLike:
      aws:PrincipalArn: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-*'
```

This pattern allows any role matching the project naming convention to use the key, avoiding the need to reference specific role ARNs that may not yet exist.

---

### Problem 2: CodeBuild Foundation IAM Policy Size Exceeded 10KB

**Template:** `deploy/cloudformation/codebuild-foundation.yaml`

**Issue:** The Foundation CodeBuild role's inline IAM policy exceeded AWS's hard limit of 10,240 bytes, causing deployment failures with:

```
Maximum policy size of 10240 bytes exceeded
```

**Root Cause:** The policy contained verbose multi-line action arrays and duplicate resource patterns accumulated over development iterations.

**Resolution Applied (by systems architecture review):** Policy optimized using these techniques:

1. **Inline Array Syntax:**
   ```yaml
   # Before (verbose)
   Action:
     - s3:GetObject
     - s3:PutObject
     - s3:DeleteObject

   # After (compact, lines 126-127)
   Action: [s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket]
   ```

2. **Consolidated Wildcards:**
   ```yaml
   # Before (multiple specific patterns)
   Resource:
     - !Sub 'arn:aws:s3:::${ProjectName}-data-*'
     - !Sub 'arn:aws:s3:::${ProjectName}-logs-*'

   # After (single wildcard, line 209)
   Resource: [!Sub 'arn:aws:s3:::${ProjectName}-*-${AWS::AccountId}-${Environment}', ...]
   ```

3. **Single CloudFormation Wildcard:**
   ```yaml
   # Consolidated all stack operations (line 131)
   Resource: !Sub 'arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectName}-*-${Environment}/*'
   ```

**Current Policy Size:** ~8.5KB (within 10KB limit with headroom for future additions)

---

### Problem 3: Account Bootstrap KMS Key Missing Service Permissions

**Template:** `deploy/cloudformation/account-bootstrap.yaml`

**Issue:** The Environment KMS Key created by account-bootstrap.yaml initially lacked permissions for CloudWatch Logs and CloudTrail to use the key for encryption.

**Symptoms:**
- CloudTrail trail creation failed with "Access Denied" when encrypting logs
- CloudWatch Log Group creation failed with KMS key access errors

**Resolution Applied:** Added specific service permissions with proper conditions (lines 226-254):

```yaml
# CloudWatch Logs permission (lines 226-239)
- Sid: AllowCloudWatchLogs
  Effect: Allow
  Principal:
    Service: !Sub 'logs.${AWS::Region}.amazonaws.com'
  Action: [kms:Encrypt, kms:Decrypt, kms:ReEncrypt*, kms:GenerateDataKey*, kms:DescribeKey]
  Resource: '*'
  Condition:
    ArnLike:
      kms:EncryptionContext:aws:logs:arn: !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:*'

# CloudTrail permission (lines 241-254)
- Sid: AllowCloudTrail
  Effect: Allow
  Principal:
    Service: cloudtrail.amazonaws.com
  Action: [kms:Encrypt, kms:Decrypt, kms:ReEncrypt*, kms:GenerateDataKey*, kms:DescribeKey]
  Resource: '*'
  Condition:
    StringLike:
      kms:EncryptionContext:aws:cloudtrail:arn: !Sub 'arn:${AWS::Partition}:cloudtrail:*:${AWS::AccountId}:trail/*'
```

---

## Deployment Sequence (Fresh Account)

### Phase 0: Pre-Deployment Prerequisites

These steps MUST be completed before any CloudFormation deployment.

#### 0.1 Enable AWS Organizations (Management Account Only)

```bash
# Only required once in the Management Account (DEV)
export AWS_PROFILE=aura-admin
aws organizations create-organization --feature-set ALL

# Note the Organization ID
ORG_ID=$(aws organizations describe-organization --query 'Organization.Id' --output text)
echo "Organization ID: $ORG_ID"
```

#### 0.2 Create Member Account (Skip if account exists)

```bash
# Create QA or PROD account within organization
aws organizations create-account \
  --email "aura-qa@aenealabs.com" \
  --account-name "aenealabs-qa" \
  --iam-user-access-to-billing ALLOW

# Wait for creation (1-2 minutes)
aws organizations list-create-account-status \
  --query "CreateAccountStatuses[?AccountName=='aenealabs-qa']"
```

#### 0.3 Configure SSO Access to New Account

1. Navigate to IAM Identity Center in AWS Console
2. Assign AdministratorAccess permission set to new account
3. Configure AWS CLI profile:

```bash
# Add to ~/.aws/config
[profile aura-admin]
sso_session = aenealabs
sso_account_id = 234567890123
sso_role_name = AdministratorAccess
region = us-east-1
output = json
```

#### 0.4 Create GitHub CodeConnections (Manual)

CodeConnections require manual OAuth authorization and cannot be created via CloudFormation.

1. Navigate to Developer Tools > Settings > Connections in target account
2. Create connection named `aura-github-{env}` (e.g., `aura-github-qa`)
3. Complete GitHub OAuth authorization
4. Note the connection ARN for SSM parameter creation

---

### Phase 1: Account Bootstrap (Layer 0)

Deploy the account bootstrap stack FIRST. This creates foundational resources required by all other stacks.

```bash
# Switch to target account
export AWS_PROFILE=aura-admin
aws sts get-caller-identity  # Verify account

# Get SSO admin role ARN
ADMIN_ROLE_ARN=$(aws iam list-roles \
  --query "Roles[?contains(RoleName, 'AdministratorAccess')].Arn" \
  --output text | head -1)

# Deploy account-bootstrap.yaml
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-qa \
  --parameter-overrides \
    Environment=qa \
    AdminRoleArn=$ADMIN_ROLE_ARN \
    AlertEmail=alerts-qa@aenealabs.com \
    CodeConnectionsArn="arn:aws:codeconnections:us-east-1:234567890123:connection/YOUR-CONNECTION-ID" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

**Creates:**
- SSM Parameters for account configuration
- S3 bucket for CloudFormation artifacts
- KMS master encryption key with CloudWatch/CloudTrail permissions
- CloudTrail trail for API audit logging
- CloudTrail S3 logs bucket (7-year retention for CMMC)
- GuardDuty detector
- Security alerts SNS topic
- EventBridge rules for security events

**Duration:** ~5 minutes

---

### Phase 2: Organizations (Layer 0.1 - Management Account Only)

Only deploy this in the Management Account to set up SCPs.

```bash
# Switch to Management Account
export AWS_PROFILE=aura-admin

# Get Organization and Root IDs
ORG_ID=$(aws organizations describe-organization --query 'Organization.Id' --output text)
ROOT_ID=$(aws organizations list-roots --query 'Roots[0].Id' --output text)

# Deploy organizations.yaml
aws cloudformation deploy \
  --template-file deploy/cloudformation/organizations.yaml \
  --stack-name aura-organizations \
  --parameter-overrides \
    OrganizationId=$ORG_ID \
    RootId=$ROOT_ID \
    QAAccountId=234567890123 \
  --capabilities CAPABILITY_NAMED_IAM
```

**Creates:**
- Workloads OU for member accounts
- Security OU for audit accounts
- Baseline Security SCP (IMDSv2, encryption requirements)
- Organization SSM parameters

---

### Phase 3: Bootstrap Layer (Layer 0 - Deploys ALL CodeBuild Projects)

The Bootstrap Layer solves the chicken-and-egg problem by deploying ALL 18 CodeBuild projects in one automated step. This is the **recommended approach** for fresh account deployments.

```bash
# Switch to target account
export AWS_PROFILE=aura-admin

# Store CodeConnections ARN in global SSM parameter first
aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:234567890123:connection/YOUR-CONNECTION-ID" \
  --overwrite

# Option A: Use the automated bootstrap script (RECOMMENDED)
./deploy/scripts/bootstrap-fresh-account.sh qa us-east-1

# Option B: Manual deployment
# Step 1: Deploy Bootstrap CodeBuild project
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-bootstrap.yaml \
  --stack-name aura-codebuild-bootstrap-qa \
  --parameter-overrides \
    Environment=qa \
    ProjectName=aura \
    GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=aura Environment=qa BootstrapExemption=true \
  --region us-east-1

# Step 2: Trigger Bootstrap to deploy all 18 CodeBuild projects
aws codebuild start-build --project-name aura-bootstrap-deploy-qa

# Monitor progress
aws codebuild batch-get-builds \
  --ids $(aws codebuild list-builds-for-project --project-name aura-bootstrap-deploy-qa --query 'ids[0]' --output text) \
  --query 'builds[0].[buildStatus,currentPhase]'
```

**Bootstrap Layer Creates (via `buildspec-bootstrap.yml`):**
- All 8 parent layer CodeBuild projects (foundation, data, compute, application, observability, serverless, sandbox, security)
- All 10 sub-layer CodeBuild projects (network-services, docker, frontend, marketing, chat-assistant, runbook-agent, incident-response, serverless-documentation, application-identity, ssr)

**Duration:** ~10-15 minutes

**CRITICAL:** This approach eliminates manual Phase 4 and Phase 5 - all CodeBuild projects are deployed automatically.

---

### Phase 4: Foundation Layer Infrastructure

After Bootstrap completes, trigger the Foundation CodeBuild project to deploy actual infrastructure.

```bash
# Trigger Foundation layer deployment
aws codebuild start-build \
  --project-name aura-foundation-deploy-qa \
  --region us-east-1

# Monitor progress
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-qa \
  --query 'ids[0]' --output text)

aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --query 'builds[0].[buildStatus,currentPhase]'
```

**Deploys (via `buildspec-foundation.yml`):**
- Networking stack (VPC, subnets, route tables, NAT)
- Security stack (security groups, WAF)
- IAM stack (service roles)
- KMS stack (encryption keys)
- VPC Endpoints stack
- ECR Base Images stack

**Duration:** ~10-15 minutes

---

### Phase 5: Remaining Layer Deployments

Continue with remaining layers in dependency order.

```bash
# Trigger each layer in sequence
for PROJECT in data compute application observability serverless sandbox security; do
  echo "Starting ${PROJECT} layer deployment..."
  aws codebuild start-build \
    --project-name aura-${PROJECT}-deploy-qa \
    --region us-east-1

  # Wait for completion before next layer
  echo "Waiting for ${PROJECT} layer to complete..."
  # Add wait logic or monitor manually
done
```

---

## Deployment Dependency Graph

```
Phase 0: Prerequisites (Manual)
├── Enable Organizations (management account)
├── Create Member Account
├── Configure SSO Access
└── Create GitHub CodeConnections (manual OAuth)
           │
           ▼
Phase 1: Account Bootstrap (account-bootstrap.yaml)
├── SSM Parameters
├── KMS Master Key (with CloudWatch/CloudTrail permissions)
├── CloudTrail (uses KMS key)
├── GuardDuty
└── Security SNS + EventBridge
           │
           ▼
Phase 2: Organizations (organizations.yaml) [Management Account Only]
├── Workloads OU
├── Security OU
└── Baseline Security SCP
           │
           ▼
Phase 3: Bootstrap Layer (codebuild-bootstrap.yaml + buildspec-bootstrap.yml)
├── Deploy Bootstrap CodeBuild project (one-time manual)
├── Trigger Bootstrap build → Deploys ALL 18 CodeBuild projects:
│   ├── Parent Layers: foundation, data, compute, application, observability, serverless, sandbox, security
│   └── Sub-Layers: network-services, docker, frontend, marketing, chat-assistant, runbook-agent,
│                   incident-response, serverless-documentation, application-identity, ssr
└── ~10-15 minutes automated deployment
           │
           ▼
Phase 4: Foundation Layer (via aura-foundation-deploy-{env})
├── networking.yaml (VPC, subnets, NAT)
├── security.yaml (Security Groups, WAF)
├── iam.yaml (Service Roles)
├── kms.yaml (Encryption Keys)
├── vpc-endpoints.yaml
└── ecr-base-images.yaml
           │
           ▼
Phase 5+: Remaining Layers (via CodeBuild - automated cascade)
├── Data Layer (Neptune, OpenSearch, DynamoDB) ~25 min
├── Compute Layer (EKS) ~20 min
├── Application Layer (API, Bedrock)
├── Observability Layer (Monitoring)
├── Serverless Layer (Lambda, Step Functions)
├── Sandbox Layer (HITL Workflow)
└── Security Layer (Config, GuardDuty rules)
```

### Simplified Fresh Account Bootstrap (3 Commands)

```bash
# 1. Deploy Account Bootstrap (one-time security baseline)
aws cloudformation deploy --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-qa --capabilities CAPABILITY_NAMED_IAM ...

# 2. Deploy Bootstrap CodeBuild and run it (deploys ALL 18 CodeBuild projects)
./deploy/scripts/bootstrap-fresh-account.sh qa us-east-1

# 3. Trigger Foundation to start infrastructure cascade
aws codebuild start-build --project-name aura-foundation-deploy-qa
```

---

## PROD Deployment Checklist

Use this checklist when deploying to the GovCloud PROD account.

### Pre-Deployment

- [ ] GovCloud account provisioned and verified
- [ ] GovCloud SSO access configured
- [ ] GovCloud CodeConnections created (separate from commercial)
- [ ] `${AWS::Partition}` verified in all templates (aws-us-gov partition)
- [ ] All templates pass `cfn-lint` validation
- [ ] IAM policies reviewed for GovCloud service availability

### Phase 0: Prerequisites

- [ ] Organizations enabled (if using multi-account in GovCloud)
- [ ] CodeConnections OAuth completed for GovCloud GitHub
- [ ] SSM parameters created:
  - [ ] `/aura/global/codeconnections-arn`
  - [ ] `/aura/prod/admin-role-arn`
  - [ ] `/aura/prod/alert-email`

### Phase 1: Account Bootstrap

- [ ] `aura-account-bootstrap-prod` stack deployed
- [ ] CloudTrail logging verified
- [ ] GuardDuty enabled
- [ ] Security alerts SNS subscription confirmed

### Phase 2: Organizations (if applicable)

- [ ] SCPs applied to PROD account
- [ ] Organization SSM parameters set

### Phase 3: CodeBuild Foundation

- [ ] `aura-codebuild-foundation-prod` deployed
- [ ] Foundation CodeBuild role created successfully
- [ ] CodeConnections access verified

### Phase 4: KMS Keys

- [ ] `aura-kms-prod` deployed
- [ ] All 4 KMS keys created with rotation enabled
- [ ] Key aliases verified:
  - [ ] `alias/aura-backup-prod`
  - [ ] `alias/aura-data-prod`
  - [ ] `alias/aura-security-prod`
  - [ ] `alias/aura-app-prod`

### Phase 5: Remaining CodeBuild Projects

- [ ] All CodeBuild stacks deployed
- [ ] CodeBuild projects can access GitHub via CodeConnections

### Phase 6: Foundation Layer

- [ ] Foundation CodeBuild triggered and succeeded
- [ ] VPC created with correct CIDR
- [ ] Security groups created
- [ ] VPC endpoints operational

### Phase 7+: Remaining Layers

- [ ] Data layer deployed (Neptune ~20 min, OpenSearch ~15 min)
- [ ] Compute layer deployed (EKS ~20 min)
- [ ] Application layer deployed
- [ ] Observability layer deployed
- [ ] Serverless layer deployed
- [ ] Sandbox layer deployed
- [ ] Security layer deployed

### Post-Deployment Verification

- [ ] All CloudFormation stacks in `*_COMPLETE` state
- [ ] No ROLLBACK or FAILED stacks
- [ ] Health endpoints responding
- [ ] CloudWatch alarms configured
- [ ] Cost alerts and budgets active

---

## Template Optimization Reference

### IAM Policy Size Optimization Techniques

| Technique | Before | After | Savings |
|-----------|--------|-------|---------|
| Inline arrays | Multi-line actions | `[action1, action2]` | ~30% |
| Consolidated wildcards | Multiple specific ARNs | Single `*` pattern | ~40% |
| Remove duplicate resources | Repeated ARNs in statements | Single merged statement | ~20% |
| Remove verbose comments | Inline explanations | External documentation | ~10% |

### Template Files Modified

| Template | Modification | Reason |
|----------|--------------|--------|
| `codebuild-foundation.yaml` | IAM policy optimization | 10KB limit exceeded |
| `kms.yaml` | Root principal + ArnLike condition | Circular role references |
| `account-bootstrap.yaml` | CloudWatch/CloudTrail KMS permissions | Service encryption access |

---

## Troubleshooting

### KMS Key Policy Validation Failure

**Error:** `Policy contains a statement with one or more invalid principals`

**Cause:** Key policy references an IAM role that doesn't exist yet.

**Solution:** Ensure Foundation CodeBuild stack is deployed BEFORE KMS stack.

```bash
# Verify Foundation CodeBuild role exists
aws iam get-role --role-name aura-foundation-codebuild-role-qa
```

### IAM Policy Size Exceeded

**Error:** `Maximum policy size of 10240 bytes exceeded`

**Cause:** Inline policy in CloudFormation template is too large.

**Solution:** Apply optimization techniques:

1. Use inline array syntax for actions
2. Consolidate resource ARN patterns with wildcards
3. Remove duplicate statements
4. Split into multiple policies if necessary

```bash
# Check current policy size
aws cloudformation get-template --stack-name STACK_NAME \
  | jq '.TemplateBody' | wc -c
```

### CodeConnections Authorization Pending

**Error:** CodeBuild fails with GitHub source access error

**Cause:** CodeConnections OAuth flow not completed.

**Solution:**
1. Navigate to Developer Tools > Settings > Connections
2. Find connection with "Pending" status
3. Click "Update pending connection"
4. Complete GitHub OAuth

### CloudTrail Encryption Failed

**Error:** `Access Denied` when CloudTrail attempts to encrypt logs

**Cause:** KMS key missing CloudTrail service permissions.

**Solution:** Verify account-bootstrap.yaml includes CloudTrail KMS statement with proper conditions (see Problem 3 resolution above).

---

## Related Documentation

- [MULTI_ACCOUNT_SETUP.md](./MULTI_ACCOUNT_SETUP.md) - Initial account setup procedures
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Layer-by-layer deployment instructions
- [CICD_SETUP_GUIDE.md](./CICD_SETUP_GUIDE.md) - CodeBuild configuration details
- [GOVCLOUD_READINESS_TRACKER.md](../cloud-strategy/GOVCLOUD_READINESS_TRACKER.md) - GovCloud compatibility status

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Platform Team | Initial QA/PROD deployment sequence documentation |
