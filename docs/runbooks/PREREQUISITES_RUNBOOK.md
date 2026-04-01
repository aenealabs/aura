# Prerequisites Runbook

This document describes the one-time setup steps required before running the Project Aura CI/CD pipeline for the first time in a new environment.

## Overview

Project Aura uses a three-phase deployment model:

| Phase | Method | Purpose |
|-------|--------|---------|
| **Phase 1: Prerequisites** | Manual (this runbook) | One-time environment setup |
| **Phase 2: Bootstrap** | `deploy-*-codebuild.sh` scripts | Create CI/CD pipeline (CodeBuild projects) |
| **Phase 3: CI/CD Pipeline** | CodeBuild → buildspec | Deploy infrastructure and applications |

This runbook covers **Phase 1** only. See `docs/deployment/DEPLOYMENT_GUIDE.md` for Phases 2 and 3.

---

## Prerequisites Checklist

### AWS Account Setup

- [ ] AWS Account with appropriate permissions
- [ ] AWS CLI configured with credentials (`aws configure` or SSO)
- [ ] AWS Region set (default: `us-east-1`)

### Required Tools

- [ ] AWS CLI v2.x
- [ ] kubectl (for EKS interaction)
- [ ] Podman or Docker (for local container builds)
- [ ] Python 3.11+ (for cfn-lint)

---

## Step 1: Create SSM Parameters

These parameters store environment-specific configuration that the CI/CD pipeline reads at runtime.

### 1.1 Global Parameters (Shared Across Environments)

```bash
# GitHub CodeConnections ARN (for CodeBuild source)
# Create this in AWS Console: Developer Tools > Settings > Connections
aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:YOUR_ACCOUNT_ID:connection/YOUR_CONNECTION_ID" \
  --description "GitHub CodeConnections ARN for CodeBuild" \
  --region us-east-1
```

### 1.2 Environment-Specific Parameters

Replace `{env}` with `dev`, `qa`, or `prod`.

```bash
# Set environment
ENV=dev

# Admin Role ARN (for EKS access and CloudFormation)
# This is typically your AWS SSO AdministratorAccess role
aws ssm put-parameter \
  --name "/aura/${ENV}/admin-role-arn" \
  --type "String" \
  --value "arn:aws:iam::YOUR_ACCOUNT_ID:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_XXXXXXXX" \
  --description "SSO Administrator Role ARN for EKS access" \
  --region us-east-1

# Alert Email (for SNS notifications)
aws ssm put-parameter \
  --name "/aura/${ENV}/alert-email" \
  --type "String" \
  --value "your-email@example.com" \
  --description "Email address for alert notifications" \
  --region us-east-1
```

### 1.3 Verify Parameters

```bash
aws ssm get-parameters-by-path \
  --path "/aura" \
  --recursive \
  --query "Parameters[].{Name:Name,Value:Value}" \
  --output table \
  --region us-east-1
```

Expected output:
```
---------------------------------------------
|           GetParametersByPath             |
+------------------------------------+------+
|  /aura/global/codeconnections-arn  | ...  |
|  /aura/dev/admin-role-arn          | ...  |
|  /aura/dev/alert-email             | ...  |
+------------------------------------+------+
```

---

## Step 2: Create GitHub CodeConnection

CodeBuild requires a GitHub connection to pull source code.

### 2.1 Create Connection (AWS Console)

1. Go to **AWS Console > Developer Tools > Settings > Connections**
2. Click **Create connection**
3. Select **GitHub** as the provider
4. Name: `aura-github-connection`
5. Click **Connect to GitHub** and authorize AWS
6. Copy the **Connection ARN**

### 2.2 Store Connection ARN

```bash
# Use the ARN from step 2.1
aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:YOUR_ACCOUNT_ID:connection/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" \
  --overwrite \
  --region us-east-1
```

---

## Step 3: Confirm SNS Email Subscription (Post-Deployment)

After the Observability layer is deployed, you'll receive an email to confirm SNS subscriptions.

1. Check your inbox for emails from `AWS Notifications`
2. Click **Confirm subscription** in each email
3. Verify subscriptions:

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:aura-alerts-dev" \
  --query "Subscriptions[].{Endpoint:Endpoint,Status:SubscriptionArn}" \
  --output table \
  --region us-east-1
```

---

## Step 4: Configure kubectl Access (Post-Compute Deployment)

After the EKS cluster is deployed:

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name aura-cluster-dev \
  --region us-east-1 \
  --profile aura-admin

# Verify access
kubectl cluster-info
kubectl get nodes
```

---

## SSM Parameter Reference

| Parameter | Scope | Description | Example Value |
|-----------|-------|-------------|---------------|
| `/aura/global/codeconnections-arn` | Global | GitHub connection for CodeBuild | `arn:aws:codeconnections:...` |
| `/aura/{env}/admin-role-arn` | Per-env | Admin IAM role ARN | `arn:aws:iam::...:role/...` |
| `/aura/{env}/alert-email` | Per-env | SNS notification email | `alerts@example.com` |

### Optional Parameters (Auto-Created)

These parameters are created automatically by CloudFormation stacks:

| Parameter | Created By | Description |
|-----------|-----------|-------------|
| `/aura/{env}/neptune/audit-config` | Neptune stack | Neptune audit log configuration |

---

## Deployment Order

After completing prerequisites, deploy in this order:

```bash
# Phase 2: Bootstrap (one-time per environment)
./deploy/scripts/deploy-foundation-codebuild.sh dev
./deploy/scripts/deploy-data-codebuild.sh dev
./deploy/scripts/deploy-compute-codebuild.sh dev
./deploy/scripts/deploy-application-codebuild.sh dev
./deploy/scripts/deploy-observability-codebuild.sh dev
./deploy/scripts/deploy-serverless-codebuild.sh dev
./deploy/scripts/deploy-sandbox-codebuild.sh dev
./deploy/scripts/deploy-security-codebuild.sh dev

# Phase 3: Trigger CI/CD Pipeline
aws codebuild start-build --project-name aura-foundation-deploy-dev
# Wait for completion, then continue with data, compute, etc.
```

See `docs/deployment/DEPLOYMENT_GUIDE.md` for detailed deployment instructions.

---

## Troubleshooting

### "Parameter not found" Errors

If CodeBuild fails with parameter errors:

```bash
# List all parameters
aws ssm get-parameters-by-path --path "/aura" --recursive --output table

# Create missing parameter
aws ssm put-parameter --name "/aura/dev/missing-param" --type "String" --value "value"
```

### GitHub Connection Not Working

1. Verify connection status in AWS Console
2. Check that the connection is in `AVAILABLE` state
3. Re-authorize if status is `PENDING`

### SNS Subscription Not Confirmed

1. Check spam folder for confirmation email
2. Request new confirmation:

```bash
aws sns subscribe \
  --topic-arn "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:aura-alerts-dev" \
  --protocol email \
  --notification-endpoint "your-email@example.com"
```

---

## Security Notes

1. **SSM Parameter Store** is used for non-secret configuration (FREE tier)
2. **Secrets Manager** is used for actual secrets (API keys, passwords)
3. Never store secrets in SSM Parameter Store Standard tier
4. All parameters should be scoped to the minimum required access

---

## Related Documentation

- `docs/deployment/DEPLOYMENT_GUIDE.md` - Full deployment instructions
- `docs/deployment/CICD_SETUP_GUIDE.md` - CI/CD pipeline architecture
- `CLAUDE.md` - SSM parameter naming conventions
