# Project Aura - Fresh Account Bootstrap Guide

**Document Version:** 1.0
**Last Updated:** 2026-01-09
**Classification:** Operations / Deployment
**Review Cycle:** Quarterly or upon CI/CD architecture changes

---

## Executive Summary

This guide provides step-by-step instructions for bootstrapping a fresh AWS account (QA, Prod, or GovCloud) with Project Aura's CI/CD infrastructure. The bootstrap process deploys all 18 CodeBuild projects required for automated infrastructure deployment.

**Key Concept:** The Bootstrap layer (Layer 0) solves the chicken-and-egg problem where CodeBuild projects need to exist to deploy infrastructure, but something needs to deploy the CodeBuild projects first.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (5 Minutes)](#quick-start-5-minutes)
4. [Detailed Bootstrap Procedure](#detailed-bootstrap-procedure)
5. [Deployment Sequence](#deployment-sequence)
6. [Troubleshooting](#troubleshooting)
7. [Rollback Procedures](#rollback-procedures)

---

## Architecture Overview

### The Bootstrap Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          THE CHICKEN-AND-EGG PROBLEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CodeBuild projects deploy infrastructure                                   │
│              ↓                                                               │
│   But who deploys the CodeBuild projects?                                   │
│              ↓                                                               │
│   SOLUTION: Bootstrap Layer (one-time manual deployment)                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Bootstrap Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 0: BOOTSTRAP (One-Time Manual)                      │
│                                                                              │
│   deploy/cloudformation/codebuild-bootstrap.yaml                            │
│   deploy/buildspecs/buildspec-bootstrap.yml                                 │
│                                                                              │
│   Creates: aura-bootstrap-deploy-{env}                                      │
│   Deploys: All 18 CodeBuild project CloudFormation stacks                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         18 CodeBuild Projects Deployed                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PARENT LAYERS (8):                    SUB-LAYERS (10):                     │
│  ├── foundation-deploy                 ├── network-services-deploy          │
│  ├── data-deploy                       ├── docker-deploy                    │
│  ├── compute-deploy                    ├── frontend-deploy                  │
│  ├── application-deploy                ├── marketing-deploy                 │
│  ├── observability-deploy              ├── chat-assistant-deploy            │
│  ├── serverless-deploy                 ├── runbook-agent-deploy             │
│  ├── sandbox-deploy                    ├── incident-response-deploy         │
│  └── security-deploy                   ├── serverless-documentation-deploy  │
│                                        ├── application-identity-deploy      │
│                                        └── ssr-deploy                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        8-Layer Infrastructure Cascade                        │
│                                                                              │
│   Layer 1: Foundation → Layer 2: Data → Layer 3: Compute → ...              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. AWS CLI Configuration

```bash
# Verify AWS CLI is installed
aws --version

# Configure credentials for target account
aws configure --profile aura-{env}

# Verify access
aws sts get-caller-identity --profile aura-{env}
```

### 2. GitHub CodeConnection

Create a GitHub CodeConnection in the target account:

1. Navigate to AWS Console > Developer Tools > Settings > Connections
2. Create a new connection for GitHub
3. Authorize the connection to access your repository
4. Copy the Connection ARN

### 3. Store CodeConnection ARN in SSM

```bash
# Store the CodeConnection ARN in SSM Parameter Store
aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --value "arn:aws:codeconnections:us-east-1:123456789012:connection/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --type String \
  --region us-east-1

# For GovCloud
aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --value "arn:aws-us-gov:codeconnections:us-gov-west-1:123456789012:connection/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --type String \
  --region us-gov-west-1
```

---

## Quick Start (5 Minutes)

For experienced operators who want to bootstrap quickly:

```bash
# 1. Clone the repository
git clone https://github.com/aenealabs/aura.git
cd aura

# 2. Run the bootstrap script
./deploy/scripts/bootstrap-fresh-account.sh dev us-east-1

# 3. Deploy Foundation layer (after bootstrap completes)
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1

# 4. Deploy remaining layers (after Foundation completes)
aws codebuild start-build --project-name aura-data-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-compute-deploy-dev --region us-east-1
# ... continue with remaining layers
```

---

## Detailed Bootstrap Procedure

### Step 1: Deploy Bootstrap CodeBuild Stack (Manual, One-Time)

This is the only manual CloudFormation deployment required.

```bash
# Set environment variables
export ENVIRONMENT=dev          # or: qa, prod
export PROJECT_NAME=aura
export REGION=us-east-1         # or: us-gov-west-1 for GovCloud
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Deploy the Bootstrap CodeBuild stack
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-bootstrap.yaml \
  --stack-name ${PROJECT_NAME}-codebuild-bootstrap-${ENVIRONMENT} \
  --parameter-overrides \
    Environment=${ENVIRONMENT} \
    ProjectName=${PROJECT_NAME} \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=${PROJECT_NAME} Environment=${ENVIRONMENT} Layer=bootstrap BootstrapExemption=true \
  --region ${REGION}
```

**What this creates:**
- CodeBuild project: `aura-bootstrap-deploy-{env}`
- S3 bucket: `aura-bootstrap-artifacts-{account-id}-{env}`
- IAM role: `aura-bootstrap-codebuild-role-{env}`
- CloudWatch log group: `/aws/codebuild/aura-bootstrap-deploy-{env}`
- CloudWatch alarm: `aura-bootstrap-build-failures-{env}`

**Time:** ~2-3 minutes

### Step 2: Trigger Bootstrap Build

The Bootstrap CodeBuild project deploys all 18 CodeBuild project stacks.

```bash
# Start the bootstrap build
aws codebuild start-build \
  --project-name ${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT} \
  --region ${REGION}

# Monitor the build
aws codebuild list-builds-for-project \
  --project-name ${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT} \
  --max-items 1 \
  --region ${REGION}
```

**What this deploys (18 CodeBuild stacks):**

| Stack | CodeBuild Project | Layer |
|-------|-------------------|-------|
| aura-codebuild-foundation-{env} | aura-foundation-deploy-{env} | 1 |
| aura-codebuild-data-{env} | aura-data-deploy-{env} | 2 |
| aura-codebuild-compute-{env} | aura-compute-deploy-{env} | 3 |
| aura-codebuild-application-{env} | aura-application-deploy-{env} | 4 |
| aura-codebuild-observability-{env} | aura-observability-deploy-{env} | 5 |
| aura-codebuild-serverless-{env} | aura-serverless-deploy-{env} | 6 |
| aura-codebuild-sandbox-{env} | aura-sandbox-deploy-{env} | 7 |
| aura-codebuild-security-{env} | aura-security-deploy-{env} | 8 |
| aura-codebuild-network-services-{env} | aura-network-services-deploy-{env} | 1.7 |
| aura-codebuild-docker-{env} | aura-docker-deploy-{env} | 1.9 |
| aura-codebuild-frontend-{env} | aura-frontend-deploy-{env} | 4.7 |
| aura-codebuild-marketing-{env} | aura-marketing-deploy-{env} | 4.8 |
| aura-codebuild-chat-assistant-{env} | aura-chat-assistant-deploy-{env} | 6.7 |
| aura-codebuild-runbook-agent-{env} | aura-runbook-agent-deploy-{env} | 6.8 |
| aura-codebuild-incident-response-{env} | aura-incident-response-deploy-{env} | 6.9 |
| aura-codebuild-serverless-documentation-{env} | aura-serverless-documentation-deploy-{env} | 6.12 |
| aura-codebuild-application-identity-{env} | aura-application-identity-deploy-{env} | 4.12 |
| aura-codebuild-ssr-{env} | aura-ssr-deploy-{env} | 7.2-7.3 |

**Time:** ~10-15 minutes

### Step 3: Deploy Infrastructure Layers

After Bootstrap completes, deploy infrastructure layers in sequence:

```bash
# Layer 1: Foundation (VPC, IAM, KMS, Security Groups, VPC Endpoints)
aws codebuild start-build --project-name ${PROJECT_NAME}-foundation-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~5-10 minutes)

# Layer 2: Data (Neptune, OpenSearch, DynamoDB, S3)
aws codebuild start-build --project-name ${PROJECT_NAME}-data-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~15-25 minutes)

# Layer 3: Compute (EKS, ECR)
aws codebuild start-build --project-name ${PROJECT_NAME}-compute-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~15-20 minutes)

# Layer 4: Application (Bedrock, IRSA)
aws codebuild start-build --project-name ${PROJECT_NAME}-application-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~5-10 minutes)

# Layer 5: Observability (Monitoring, Alerts)
aws codebuild start-build --project-name ${PROJECT_NAME}-observability-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~5-10 minutes)

# Layer 6: Serverless (Lambda, Step Functions)
aws codebuild start-build --project-name ${PROJECT_NAME}-serverless-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~10-15 minutes)

# Layer 7: Sandbox (HITL, Ephemeral Environments)
aws codebuild start-build --project-name ${PROJECT_NAME}-sandbox-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~5-10 minutes)

# Layer 8: Security (GuardDuty, Config)
aws codebuild start-build --project-name ${PROJECT_NAME}-security-deploy-${ENVIRONMENT} --region ${REGION}
# Wait for completion (~5-10 minutes)
```

---

## Deployment Sequence

### Dependency Graph

```
                    BOOTSTRAP (Layer 0)
                           │
                           ▼
                    FOUNDATION (Layer 1)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           DATA (2)    COMPUTE (3)   [parallel possible]
              │            │
              └────────────┼────────────┘
                           ▼
                    APPLICATION (Layer 4)
                           │
                           ▼
                    OBSERVABILITY (Layer 5)
                           │
                           ▼
                    SERVERLESS (Layer 6)
                           │
                           ▼
                    SANDBOX (Layer 7)
                           │
                           ▼
                    SECURITY (Layer 8)
```

### Timeline (Fresh Account)

| Step | Layer | Duration | Cumulative |
|------|-------|----------|------------|
| 1 | Bootstrap | 15 min | 15 min |
| 2 | Foundation | 10 min | 25 min |
| 3 | Data | 25 min | 50 min |
| 4 | Compute | 20 min | 70 min |
| 5 | Application | 10 min | 80 min |
| 6 | Observability | 10 min | 90 min |
| 7 | Serverless | 15 min | 105 min |
| 8 | Sandbox | 10 min | 115 min |
| 9 | Security | 10 min | 125 min |

**Total: ~2 hours for complete fresh deployment**

---

## Troubleshooting

### Bootstrap Build Fails

**Symptom:** Bootstrap CodeBuild build fails

**Solution:**
```bash
# Check build logs
aws logs tail /aws/codebuild/${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT} \
  --follow --region ${REGION}

# Common issues:
# 1. CodeConnection not authorized - re-authorize in AWS Console
# 2. SSM parameter missing - verify /aura/global/codeconnections-arn exists
# 3. IAM permissions - verify account has sufficient permissions
```

### Stack in ROLLBACK_COMPLETE State

**Symptom:** CloudFormation stack stuck in ROLLBACK_COMPLETE

**Solution:**
```bash
# Delete the failed stack
aws cloudformation delete-stack \
  --stack-name ${PROJECT_NAME}-codebuild-{layer}-${ENVIRONMENT} \
  --region ${REGION}

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name ${PROJECT_NAME}-codebuild-{layer}-${ENVIRONMENT} \
  --region ${REGION}

# Re-run bootstrap
aws codebuild start-build \
  --project-name ${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT} \
  --region ${REGION}
```

### CodeConnection Authorization Issues

**Symptom:** Build fails with "Connection is not available"

**Solution:**
1. Navigate to AWS Console > Developer Tools > Connections
2. Find the GitHub connection
3. Click "Update pending connection" if shown
4. Re-authorize the connection
5. Retry the build

---

## Rollback Procedures

### Rollback Bootstrap Layer

To completely remove the Bootstrap layer:

```bash
# 1. Delete all CodeBuild stacks deployed by Bootstrap
for stack in $(aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?contains(StackName, '${PROJECT_NAME}-codebuild')].StackName" \
  --output text --region ${REGION}); do
  echo "Deleting: $stack"
  aws cloudformation delete-stack --stack-name $stack --region ${REGION}
done

# 2. Delete the Bootstrap stack itself
aws cloudformation delete-stack \
  --stack-name ${PROJECT_NAME}-codebuild-bootstrap-${ENVIRONMENT} \
  --region ${REGION}

# 3. Delete Bootstrap artifacts bucket (must be empty first)
aws s3 rm s3://${PROJECT_NAME}-bootstrap-artifacts-${ACCOUNT_ID}-${ENVIRONMENT} --recursive
aws s3 rb s3://${PROJECT_NAME}-bootstrap-artifacts-${ACCOUNT_ID}-${ENVIRONMENT}
```

---

## Related Documentation

- **CI/CD Setup Guide:** `docs/deployment/CICD_SETUP_GUIDE.md`
- **Bootstrap Exemptions:** `docs/operations/bootstrap-exemptions.md`
- **Deployment Guide:** `docs/deployment/DEPLOYMENT_GUIDE.md`
- **GovCloud Readiness:** `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md`

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-09 | Platform Team | Initial version - Bootstrap Layer architecture |
