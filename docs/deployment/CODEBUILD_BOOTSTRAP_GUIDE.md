# CodeBuild Bootstrap Guide

**Last Updated:** January 2, 2026
**Purpose:** Reference for CodeBuild project deployment paths (bootstrap vs auto-deployed)
**Audience:** Platform development teams, DevOps engineers

---

## Executive Summary

Project Aura uses 16 CodeBuild projects to manage infrastructure deployments across 8 layers. These projects are deployed via two distinct methods:

| Deployment Method | Project Count | When to Use |
|-------------------|---------------|-------------|
| **Bootstrap (Manual)** | 14 projects | Initial environment setup, one-time per environment |
| **Auto-Deployed** | 2 projects | Automatically created by `buildspec-foundation.yml` |

**Key Distinction:**
- **Bootstrap projects** require manual execution of shell scripts to create the CodeBuild project
- **Auto-deployed projects** are created automatically when the Foundation layer runs

The bootstrap scripts are idempotent - they can be re-run safely to update existing CodeBuild projects.

---

## Prerequisites

Before running any bootstrap scripts, ensure:

### AWS Configuration
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Expected output:
# {
#   "UserId": "...",
#   "Account": "123456789012",
#   "Arn": "arn:aws:iam::123456789012:user/admin"
# }
```

### Required SSM Parameters

The CodeBuild projects require these SSM parameters to exist:

| Parameter | Description |
|-----------|-------------|
| `/aura/global/codeconnections-arn` | GitHub CodeConnections ARN for source access |
| `/aura/{env}/admin-role-arn` | SSO Administrator Role ARN for EKS access |
| `/aura/{env}/alert-email` | Email address for SNS notifications |

Verify parameters exist:
```bash
aws ssm get-parameters-by-path \
  --path "/aura" \
  --recursive \
  --query "Parameters[].Name" \
  --output table \
  --region us-east-1
```

If parameters are missing, see `docs/runbooks/PREREQUISITES_RUNBOOK.md` for setup instructions.

### Environment Variables

Set these before running bootstrap scripts:
```bash
export AWS_DEFAULT_REGION=us-east-1    # Target region
export AWS_PROFILE=your-profile        # (Optional) AWS credentials profile
```

---

## CodeBuild Project Inventory

### Bootstrap Projects (12 Total)

These projects require manual execution of bootstrap scripts to deploy.

| Project Name | Bootstrap Script | Layer | Purpose |
|-------------|------------------|-------|---------|
| `aura-codebuild-foundation-dev` | `./deploy/scripts/deploy-foundation-codebuild.sh` | Layer 1 | VPC, IAM, WAF, VPC Endpoints |
| `aura-codebuild-data-dev` | `./deploy/scripts/deploy-data-codebuild.sh` | Layer 2 | Neptune, OpenSearch, DynamoDB, S3 |
| `aura-codebuild-compute-dev` | `./deploy/scripts/deploy-compute-codebuild.sh` | Layer 3 | EKS, ECR, Node Groups |
| `aura-codebuild-application-dev` | `./deploy/scripts/deploy-application-codebuild.sh` | Layer 4 | Bedrock, IRSA, Frontend Infrastructure |
| `aura-codebuild-observability-dev` | `./deploy/scripts/deploy-observability-codebuild.sh` | Layer 5 | Secrets, Monitoring, Cost Alerts |
| `aura-codebuild-serverless-dev` | `./deploy/scripts/deploy-serverless-codebuild.sh` | Layer 6 | Lambda, EventBridge, Step Functions |
| `aura-codebuild-sandbox-dev` | `./deploy/scripts/deploy-sandbox-codebuild.sh` | Layer 7 | HITL Workflow, ECS Sandbox |
| `aura-codebuild-security-dev` | `./deploy/scripts/deploy-security-codebuild.sh` | Layer 8 | AWS Config, GuardDuty, Drift Detection |
| `aura-codebuild-frontend-dev` | `./deploy/scripts/deploy-frontend-codebuild.sh` | Sub-layer | Frontend application builds |
| `aura-codebuild-network-services-dev` | `./deploy/scripts/deploy-network-services-codebuild.sh` | Sub-layer | dnsmasq, ECS Fargate DNS |
| `aura-codebuild-incident-response-dev` | `./deploy/scripts/deploy-incident-response-codebuild.sh` | Sub-layer | Incident tracking, RCA workflows |
| `aura-codebuild-chat-assistant-dev` | `./deploy/scripts/deploy-chat-assistant-codebuild.sh` | Sub-layer | WebSocket API, Bedrock chat |

### Auto-Deployed Projects (2 Total)

These projects are automatically created by `buildspec-foundation.yml` when the Foundation layer runs. No manual bootstrap required.

| Project Name | Deployed By | ADR | Purpose |
|-------------|-------------|-----|---------|
| `aura-codebuild-docker-dev` | `buildspec-foundation.yml` | ADR-035 | Lightweight Docker image builder for ECR |
| `aura-codebuild-runbook-agent-dev` | `buildspec-foundation.yml` | ADR-033 | Runbook Agent CI/CD automation |

**Why auto-deployed?** These projects have simpler IAM requirements and are tightly coupled to the Foundation layer. Auto-deploying them reduces the bootstrap burden while maintaining the single-source-of-truth principle.

---

## Layer Dependency Architecture

```
                    BOOTSTRAP ENTRY POINT
                            |
                            v
    +-----------------------------------------------+
    |          LAYER 1: FOUNDATION                  |
    |   ./deploy/scripts/deploy-foundation-codebuild.sh   |
    |                                               |
    |   Creates: VPC, IAM, WAF, Security Groups,    |
    |   VPC Endpoints, KMS                          |
    |                                               |
    |   Auto-deploys:                               |
    |   - aura-codebuild-docker-dev                 |
    |   - aura-codebuild-runbook-agent-dev          |
    +-----------------------------------------------+
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
    +-----------+     +-----------+     +-----------+
    | LAYER 2   |     | LAYER 3   |     | LAYER 5   |
    | DATA      |     | COMPUTE   |     | OBSERV.   |
    +-----------+     +-----------+     +-----------+
    | Neptune   |     | EKS       |     | Secrets   |
    | OpenSearch|     | ECR       |     | Monitor   |
    | DynamoDB  |     | Nodes     |     | Cost      |
    | S3        |     |           |     | Alerts    |
    +-----------+     +-----------+     +-----------+
          |                 |                 |
          |                 v                 |
          |           +-----------+           |
          |           | LAYER 4   |           |
          |           | APPLIC.   |           |
          |           +-----------+           |
          |           | Bedrock   |           |
          |           | IRSA      |           |
          |           | Frontend  |           |
          |           +-----------+           |
          |                 |                 |
          +--------+--------+--------+--------+
                   |                 |
                   v                 v
             +-----------+     +-----------+
             | LAYER 6   |     | LAYER 7   |
             | SERVERLESS|     | SANDBOX   |
             +-----------+     +-----------+
             | Lambda    |     | HITL      |
             | Events    |     | ECS       |
             | Chat      |     | Steps     |
             | Incident  |     |           |
             +-----------+     +-----------+
                   |                 |
                   +--------+--------+
                            |
                            v
                    +-----------+
                    | LAYER 8   |
                    | SECURITY  |
                    +-----------+
                    | Config    |
                    | GuardDuty |
                    | Drift     |
                    +-----------+
```

---

## Fresh Environment Setup

For a completely new environment, execute bootstrap scripts in this order:

### Step 1: Bootstrap Layer 1 (Foundation)

```bash
# Bootstrap the Foundation CodeBuild project
./deploy/scripts/deploy-foundation-codebuild.sh dev

# Expected output:
# ==========================================
# Project Aura - Foundation Layer CodeBuild
# ==========================================
# Environment: dev
# Region: us-east-1
# ...
# Stack deployment complete!
```

### Step 2: Run Foundation Build (Creates Auto-Deployed Projects)

```bash
# Trigger Foundation build - this auto-deploys docker and runbook-agent CodeBuild projects
aws codebuild start-build \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1

# Monitor build
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow --region us-east-1
```

### Step 3: Bootstrap Remaining Layers

Execute in order (respects dependencies):

```bash
# Layer 2: Data (depends on Foundation)
./deploy/scripts/deploy-data-codebuild.sh dev

# Layer 3: Compute (depends on Foundation)
./deploy/scripts/deploy-compute-codebuild.sh dev

# Layer 4: Application (depends on Foundation + Compute)
./deploy/scripts/deploy-application-codebuild.sh dev

# Layer 5: Observability (depends on Foundation)
./deploy/scripts/deploy-observability-codebuild.sh dev

# Layer 6: Serverless (depends on Foundation + Observability)
./deploy/scripts/deploy-serverless-codebuild.sh dev

# Layer 7: Sandbox (depends on Foundation + Data)
./deploy/scripts/deploy-sandbox-codebuild.sh dev

# Layer 8: Security (depends on Foundation + Data + Compute)
./deploy/scripts/deploy-security-codebuild.sh dev
```

### Step 4: Bootstrap Sub-Layers

```bash
# Frontend (depends on Application layer)
./deploy/scripts/deploy-frontend-codebuild.sh dev

# Network Services (depends on Foundation)
./deploy/scripts/deploy-network-services-codebuild.sh dev

# Incident Response (depends on Serverless)
./deploy/scripts/deploy-incident-response-codebuild.sh dev

# Chat Assistant (depends on Serverless)
./deploy/scripts/deploy-chat-assistant-codebuild.sh dev
```

### Complete Bootstrap Sequence (Copy-Paste Ready)

For convenience, here is the complete sequence for a new `dev` environment:

```bash
#!/bin/bash
# Complete bootstrap sequence for new dev environment
set -e

echo "=== Phase 1: Bootstrap Foundation ==="
./deploy/scripts/deploy-foundation-codebuild.sh dev

echo "=== Phase 2: Run Foundation Build ==="
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1
echo "Waiting for Foundation build to complete..."
sleep 300  # Wait 5 minutes for Foundation to deploy (includes auto-deployed projects)

echo "=== Phase 3: Bootstrap Core Layers ==="
./deploy/scripts/deploy-data-codebuild.sh dev
./deploy/scripts/deploy-compute-codebuild.sh dev
./deploy/scripts/deploy-application-codebuild.sh dev
./deploy/scripts/deploy-observability-codebuild.sh dev
./deploy/scripts/deploy-serverless-codebuild.sh dev
./deploy/scripts/deploy-sandbox-codebuild.sh dev
./deploy/scripts/deploy-security-codebuild.sh dev

echo "=== Phase 4: Bootstrap Sub-Layers ==="
./deploy/scripts/deploy-frontend-codebuild.sh dev
./deploy/scripts/deploy-network-services-codebuild.sh dev
./deploy/scripts/deploy-incident-response-codebuild.sh dev
./deploy/scripts/deploy-chat-assistant-codebuild.sh dev

echo "=== Bootstrap Complete ==="
echo "All 16 CodeBuild projects are now ready."
echo ""
echo "Next: Trigger layer builds in order:"
echo "  aws codebuild start-build --project-name aura-data-deploy-dev"
echo "  aws codebuild start-build --project-name aura-compute-deploy-dev"
echo "  ... and so on"
```

---

## Troubleshooting

### Common Issues

#### 1. "Stack already exists" Error

**Symptom:** Bootstrap script fails with "Stack already exists" when you expect an update.

**Solution:** The bootstrap scripts handle this automatically. If the error persists:
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-foundation-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# If ROLLBACK_COMPLETE, delete and retry:
aws cloudformation delete-stack --stack-name aura-codebuild-foundation-dev
aws cloudformation wait stack-delete-complete --stack-name aura-codebuild-foundation-dev
./deploy/scripts/deploy-foundation-codebuild.sh dev
```

#### 2. Missing SSM Parameter Error

**Symptom:** Build fails with "Parameter /aura/global/codeconnections-arn does not exist"

**Solution:** Create the required SSM parameters:
```bash
# Get your CodeConnections ARN from AWS Console:
# Developer Tools > Settings > Connections

aws ssm put-parameter \
  --name "/aura/global/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:ACCOUNT:connection/CONNECTION_ID" \
  --region us-east-1
```

#### 3. IAM Permission Denied

**Symptom:** "AccessDenied" when deploying CodeBuild stacks

**Solution:** Ensure your IAM user/role has:
- `cloudformation:*` on `arn:aws:cloudformation:*:*:stack/aura-*`
- `codebuild:*` on `arn:aws:codebuild:*:*:project/aura-*`
- `iam:*` for creating CodeBuild service roles
- `s3:*` for artifact buckets

#### 4. CodeConnections Authorization Error

**Symptom:** Build fails with "Could not access the GitHub repository"

**Solution:**
1. Verify CodeConnections status in AWS Console (must be "Available")
2. Ensure the GitHub App is authorized for the repository
3. See `docs/runbooks/CODECONNECTIONS_GITHUB_ACCESS.md` for detailed steps

#### 5. Auto-Deployed Project Missing

**Symptom:** `aura-codebuild-docker-dev` or `aura-codebuild-runbook-agent-dev` does not exist

**Solution:** These projects are created by the Foundation build, not bootstrap scripts:
```bash
# Trigger Foundation build to create auto-deployed projects
aws codebuild start-build --project-name aura-foundation-deploy-dev

# Monitor for completion
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow
```

---

## Verification Commands

### Verify All CodeBuild Projects Exist

```bash
# List all Aura CodeBuild projects
aws codebuild list-projects \
  --query "projects[?starts_with(@, 'aura-')]" \
  --output table \
  --region us-east-1

# Expected: 14 projects (12 bootstrap + 2 auto-deployed)
```

### Verify CloudFormation Stacks

```bash
# List all CodeBuild-related stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-codebuild-')]" \
  --output table \
  --region us-east-1

# Expected: 14 stacks
```

### Check Build History

```bash
# Check recent builds for a specific project
aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --max-items 5 \
  --region us-east-1
```

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [PREREQUISITES_RUNBOOK.md](../runbooks/PREREQUISITES_RUNBOOK.md) | One-time SSM parameter and environment setup |
| [CICD_SETUP_GUIDE.md](CICD_SETUP_GUIDE.md) | Complete CI/CD pipeline architecture |
| [DEPLOYMENT_METHODS.md](DEPLOYMENT_METHODS.md) | CI/CD vs Bootstrap vs GitOps comparison |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Full deployment procedures |
| [ADR-035](../architecture-decisions/ADR-035-dedicated-docker-build-project.md) | Docker CodeBuild project rationale |
| [ADR-033](../architecture-decisions/ADR-033-runbook-agent.md) | Runbook Agent architecture |

---

## Quick Reference

### Bootstrap Script Locations

All bootstrap scripts are located in `deploy/scripts/`:

```
deploy/scripts/
  deploy-foundation-codebuild.sh      # Layer 1
  deploy-data-codebuild.sh            # Layer 2
  deploy-compute-codebuild.sh         # Layer 3
  deploy-application-codebuild.sh     # Layer 4
  deploy-observability-codebuild.sh   # Layer 5
  deploy-serverless-codebuild.sh      # Layer 6
  deploy-sandbox-codebuild.sh         # Layer 7
  deploy-security-codebuild.sh        # Layer 8
  deploy-frontend-codebuild.sh        # Sub-layer
  deploy-network-services-codebuild.sh # Sub-layer
  deploy-incident-response-codebuild.sh # Sub-layer
  deploy-chat-assistant-codebuild.sh  # Sub-layer
```

### Script Usage Pattern

All scripts follow the same usage pattern:
```bash
./deploy/scripts/deploy-{layer}-codebuild.sh {environment}

# Examples:
./deploy/scripts/deploy-foundation-codebuild.sh dev
./deploy/scripts/deploy-foundation-codebuild.sh qa
./deploy/scripts/deploy-foundation-codebuild.sh prod
```

### Trigger Build After Bootstrap

```bash
aws codebuild start-build \
  --project-name aura-{layer}-deploy-{env} \
  --region us-east-1
```
