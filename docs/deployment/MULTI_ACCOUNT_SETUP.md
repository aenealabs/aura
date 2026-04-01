# Multi-Account Setup Guide

**Project Aura - AWS Organizations & Environment Isolation**

**Version:** 1.0
**Last Updated:** January 2026
**Target Audience:** Platform Administrators, DevOps Engineers

---

## Overview

This guide documents the multi-account strategy for Project Aura, enabling environment isolation for CMMC compliance alignment. Each environment (DEV, QA, PROD) operates in a separate AWS account within an AWS Organization.

### Account Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Organizations                           │
│                    (Management Account)                          │
│                      aenealabs-mgmt                              │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │  Development   │  │     QA         │  │  Production    │    │
│  │  aenealabs-dev │  │  aenealabs-qa  │  │ aenealabs-prod │    │
│  │  123456789012  │  │   (NEW)        │  │  (GovCloud)    │    │
│  │                │  │                │  │                │    │
│  │  - Chaos env   │  │  - Stable ref  │  │  - Customer    │    │
│  │  - Experiment  │  │  - PROD mirror │  │  - FedRAMP     │    │
│  │  - Break things│  │  - Validation  │  │  - CMMC L3     │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Benefits of Multi-Account

| Benefit | Description |
|---------|-------------|
| **Blast Radius Isolation** | DEV mistakes cannot affect QA resources |
| **CMMC Alignment** | Auditors expect environment separation |
| **Cost Visibility** | Native per-account billing without complex tagging |
| **Security Boundaries** | IAM policies cannot cross accounts accidentally |
| **Compliance Scope** | Limit compliance boundary to PROD account only |

---

## Naming Standards

### Account Naming Convention

```
Pattern: aenealabs-{environment}

Environments:
  - aenealabs-dev     Development (existing, becomes Management Account)
  - aenealabs-qa      Quality Assurance (new member account)
  - aenealabs-prod    Production (future, AWS GovCloud)
```

### AWS CLI Profile Naming

```
Pattern: aura-admin-{environment}

Profiles:
  - aura-admin    → Development account access
  - aura-admin     → QA account access
  - aura-admin-prod   → Production account access (GovCloud)

SSO Default Pattern (auto-generated):
  - AdministratorAccess-{account_id}
```

### SSM Parameter Paths

```
Per-Account Parameters:
  /aura/{env}/account-id           Account ID reference
  /aura/{env}/admin-role-arn       SSO Administrator role ARN
  /aura/{env}/alert-email          SNS notification email
  /aura/{env}/codeconnections-arn  GitHub connection (per-account)
  /aura/{env}/vpc-id               VPC identifier

Global Parameters (Management Account only):
  /aura/global/organization-id     AWS Organization ID
  /aura/global/sso-instance-arn    IAM Identity Center instance
```

### IAM Role Naming

```
Pattern: {project}-{purpose}-{type}-{environment}

Examples:
  aura-eks-cluster-role-dev
  aura-foundation-codebuild-role-qa
  aura-lambda-execution-role-prod
  aura-service-role-qa
```

### CloudFormation Stack Naming

```
Pattern: {project}-{service}-{environment}

Examples:
  aura-networking-dev
  aura-eks-qa
  aura-neptune-prod
```

---

## Current State: DEV Account

### Account Identity

| Attribute | Value |
|-----------|-------|
| Account ID | `123456789012` |
| Account Alias | ❌ Not set (should be `aenealabs-dev`) |
| Region | `us-east-1` |
| Organization | ❌ None (standalone) |

### SSO Configuration

| Component | Current State |
|-----------|---------------|
| SSO Instance | Account-local IAM Identity Center |
| Permission Set | `AdministratorAccess` (AWS-managed) |
| SSO Role ARN | `AWSReservedSSO_AdministratorAccess_XXXXXXXX` |
| CLI Profile | `AdministratorAccess-123456789012` |

### SSM Parameters (Existing)

| Parameter | Status | Value |
|-----------|--------|-------|
| `/aura/global/codeconnections-arn` | ✅ Set | GitHub connection ARN |
| `/aura/dev/admin-role-arn` | ✅ Set | SSO Admin role ARN |
| `/aura/dev/alert-email` | ✅ Set | Notification email |

### Bootstrap Resources

| Resource | Status |
|----------|--------|
| S3 Artifact Bucket | ✅ `aura-cfn-artifacts-123456789012-dev` |
| ECR Base Images | ✅ `aura-ecr-base-images-dev` stack |
| GitHub CodeConnections | ✅ Configured |

---

## QA Account Specification

### Target State

| Attribute | Value |
|-----------|-------|
| Account ID | `<TO_BE_ASSIGNED>` |
| Account Alias | `aenealabs-qa` |
| Account Email | `aura-qa@aenealabs.com` |
| Region | `us-east-1` |
| Organization | Member of `aenealabs-dev` Organization |

### Required SSM Parameters

| Parameter | Value |
|-----------|-------|
| `/aura/qa/account-id` | `<QA_ACCOUNT_ID>` |
| `/aura/qa/admin-role-arn` | SSO Admin role ARN |
| `/aura/qa/alert-email` | `alerts-qa@aenealabs.com` |
| `/aura/qa/codeconnections-arn` | QA-specific GitHub connection |
| `/aura/qa/vpc-id` | VPC ID after Foundation deploy |

### Required Bootstrap Resources

| Resource | Naming |
|----------|--------|
| S3 Artifact Bucket | `aura-cfn-artifacts-<QA_ACCOUNT_ID>-qa` |
| CloudTrail Logs Bucket | `aura-cloudtrail-logs-<QA_ACCOUNT_ID>-qa` |
| KMS Master Key | `alias/aura/qa/master` |
| CloudTrail Trail | `aura-account-trail-qa` |
| GuardDuty Detector | Auto-generated ID |
| Security Alerts SNS | `aura-security-alerts-qa` |
| ECR Base Images | `aura-ecr-base-images-qa` stack |
| GitHub CodeConnections | QA-specific connection (not shared) |

---

## Setup Procedures

### Phase 1: Enable AWS Organizations

**Prerequisites:**
- AWS CLI configured with DEV account credentials
- AdministratorAccess permissions

**Steps:**

```bash
# 1. Set profile for DEV account (will become Management Account)
export AWS_PROFILE=aura-admin

# 2. Enable AWS Organizations
aws organizations create-organization --feature-set ALL

# 3. Verify organization created
aws organizations describe-organization

# 4. Note the Organization ID for documentation
aws organizations describe-organization --query "Organization.Id" --output text
```

**Expected Output:**
```json
{
  "Organization": {
    "Id": "o-xxxxxxxxxx",
    "Arn": "arn:aws:organizations::123456789012:organization/o-xxxxxxxxxx",
    "FeatureSet": "ALL",
    "MasterAccountArn": "arn:aws:organizations::123456789012:account/o-xxxxxxxxxx/123456789012",
    "MasterAccountId": "123456789012",
    "MasterAccountEmail": "admin@aenealabs.com"
  }
}
```

### Phase 2: Create QA Account

```bash
# 1. Create QA account within organization
aws organizations create-account \
  --email "aura-qa@aenealabs.com" \
  --account-name "aenealabs-qa" \
  --iam-user-access-to-billing ALLOW

# 2. Check account creation status (takes 1-2 minutes)
aws organizations list-create-account-status \
  --query "CreateAccountStatuses[?AccountName=='aenealabs-qa']"

# 3. Get QA account ID once SUCCEEDED
QA_ACCOUNT_ID=$(aws organizations list-accounts \
  --query "Accounts[?Name=='aenealabs-qa'].Id" \
  --output text)
echo "QA Account ID: $QA_ACCOUNT_ID"

# 4. Store for reference
aws ssm put-parameter \
  --name "/aura/qa/account-id" \
  --type "String" \
  --value "$QA_ACCOUNT_ID" \
  --description "QA AWS Account ID"
```

### Phase 3: Configure IAM Identity Center

**Via AWS Console (recommended for initial setup):**

1. Navigate to **IAM Identity Center** in Management Account
2. If not enabled, click **Enable IAM Identity Center**
3. Go to **AWS accounts** → Select QA account
4. Click **Assign users or groups**
5. Select your user/group → Select `AdministratorAccess` permission set
6. Click **Submit**

**Configure AWS CLI Profile:**

```bash
# Add QA profile to ~/.aws/config
cat >> ~/.aws/config << 'EOF'

[profile aura-admin]
sso_session = aenealabs
sso_account_id = <QA_ACCOUNT_ID>
sso_role_name = AdministratorAccess
region = us-east-1
output = json
EOF

# Login to SSO (will authenticate for all accounts)
aws sso login --profile aura-admin
```

### Phase 4: Bootstrap QA Account

**Switch to QA account context:**

```bash
export AWS_PROFILE=aura-admin

# Verify you're in QA account
aws sts get-caller-identity
```

**Set account alias:**

```bash
aws iam create-account-alias --account-alias aenealabs-qa
```

**Create SSM parameters:**

```bash
# Admin role ARN (get from IAM Identity Center)
ADMIN_ROLE_ARN=$(aws iam list-roles \
  --query "Roles[?contains(RoleName, 'AdministratorAccess')].Arn" \
  --output text | head -1)

aws ssm put-parameter \
  --name "/aura/qa/admin-role-arn" \
  --type "String" \
  --value "$ADMIN_ROLE_ARN" \
  --description "SSO Administrator Role ARN for QA"

aws ssm put-parameter \
  --name "/aura/qa/alert-email" \
  --type "String" \
  --value "alerts-qa@aenealabs.com" \
  --description "Alert notification email for QA"
```

**Create GitHub CodeConnections (Console only):**

1. Navigate to **Developer Tools** → **Settings** → **Connections**
2. Click **Create connection**
3. Select **GitHub** provider
4. Name: `aura-github-qa`
5. Complete GitHub authorization
6. Copy connection ARN

```bash
# Store CodeConnections ARN
aws ssm put-parameter \
  --name "/aura/qa/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:<QA_ACCOUNT_ID>:connection/<CONNECTION_ID>" \
  --description "GitHub CodeConnections ARN for QA"
```

### Phase 5: Deploy Infrastructure to QA

```bash
# Ensure QA profile is active
export AWS_PROFILE=aura-admin

# Bootstrap base images
./deploy/scripts/bootstrap-base-images.sh qa

# Deploy Foundation layer (creates VPC, IAM, WAF)
# First, deploy the CodeBuild project for Foundation
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --stack-name aura-codebuild-foundation-qa \
  --parameter-overrides Environment=qa \
  --capabilities CAPABILITY_NAMED_IAM

# Trigger Foundation build
aws codebuild start-build --project-name aura-foundation-deploy-qa

# Continue with remaining layers...
```

---

## Verification Checklist

### Organization Setup

- [ ] AWS Organizations enabled on DEV account
- [ ] Organization ID documented
- [ ] DEV account is Management Account

### QA Account Creation

- [ ] QA account created successfully
- [ ] Account ID: `_______________`
- [ ] Account alias set to `aenealabs-qa`
- [ ] Account email: `aura-qa@aenealabs.com`

### IAM Identity Center

- [ ] SSO access configured for QA account
- [ ] AdministratorAccess permission set assigned
- [ ] CLI profile `aura-admin` configured
- [ ] SSO login tested successfully

### SSM Parameters (QA Account)

- [ ] `/aura/qa/account-id` created
- [ ] `/aura/qa/admin-role-arn` created
- [ ] `/aura/qa/alert-email` created
- [ ] `/aura/qa/codeconnections-arn` created

### Bootstrap Resources (QA Account)

- [ ] GitHub CodeConnections created (QA-specific)
- [ ] S3 artifact bucket created
- [ ] ECR base images populated

### Security Resources (QA Account)

- [ ] KMS master key created (`alias/aura/qa/master`)
- [ ] CloudTrail trail enabled (multi-region)
- [ ] CloudTrail logs bucket created (with 7-year retention)
- [ ] GuardDuty detector enabled
- [ ] Security alerts SNS topic created
- [ ] Alert email subscription confirmed
- [ ] EventBridge rules active (GuardDuty, Root User, IAM Changes)

---

## Troubleshooting

### Account Creation Failed

**Symptom:** `create-account` returns `FAILED` status

**Possible Causes:**
- Email address already used by another AWS account
- Organization has reached account limit (default: 10)
- Email validation failed

**Resolution:**
```bash
# Check failure reason
aws organizations describe-create-account-status \
  --create-account-request-id <REQUEST_ID>
```

### SSO Access Not Working

**Symptom:** Cannot assume role in QA account

**Resolution:**
1. Verify permission set is assigned in IAM Identity Center
2. Check that SSO session is active: `aws sso login`
3. Verify profile configuration in `~/.aws/config`

### CodeConnections Authorization Failed

**Symptom:** GitHub connection shows "Pending" status

**Resolution:**
1. Click "Update pending connection" in AWS Console
2. Complete GitHub OAuth authorization
3. Verify connection shows "Available" status

---

## Security Considerations

### Organization SCPs (Future)

For production readiness, consider implementing Service Control Policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyLeaveOrganization",
      "Effect": "Deny",
      "Action": "organizations:LeaveOrganization",
      "Resource": "*"
    },
    {
      "Sid": "RequireIMDSv2",
      "Effect": "Deny",
      "Action": "ec2:RunInstances",
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "StringNotEquals": {
          "ec2:MetadataHttpTokens": "required"
        }
      }
    }
  ]
}
```

### Cross-Account Access

This setup uses **per-account CodeConnections** (not cross-account) for:
- Simpler security model
- No cross-account IAM trust relationships
- Independent GitHub authorization per environment
- Easier revocation if needed

---

## Related Documentation

- [Deployment Guide](./DEPLOYMENT_GUIDE.md) - Infrastructure deployment procedures
- [Prerequisites Runbook](../runbooks/PREREQUISITES_RUNBOOK.md) - One-time setup steps
- [GovCloud Readiness Tracker](../cloud-strategy/GOVCLOUD_READINESS_TRACKER.md) - Production planning
- [CI/CD Setup Guide](./CICD_SETUP_GUIDE.md) - CodeBuild configuration

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Platform Team | Initial multi-account setup guide |
