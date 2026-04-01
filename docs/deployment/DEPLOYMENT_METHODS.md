# Deployment Methods Guide

This document identifies all Project Aura services and their deployment methods, commands, and dependencies.

## Overview

Project Aura uses three deployment methods:

| Method | Purpose | When to Use |
|--------|---------|-------------|
| **CI/CD (CodeBuild)** | Infrastructure layers | Standard deployments, repeatable |
| **Bootstrap** | One-time setup | Initial environment setup, ECR repos |
| **GitOps (ArgoCD)** | Kubernetes applications | Application code, microservices |

**Golden Rule:** Always use CI/CD (CodeBuild) for infrastructure deployments to maintain audit trail and IAM consistency. Bootstrap scripts are for one-time setup only.

---

## CI/CD Deployments (CodeBuild)

These are the **primary deployment method** for all infrastructure. Each layer has a dedicated CodeBuild project.

### Layer 1: Foundation
**CodeBuild Project:** `aura-foundation-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-foundation.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-networking-dev` | `networking.yaml` | VPC, subnets, route tables |
| `aura-iam-dev` | `iam.yaml` | IAM roles and policies |
| `aura-security-dev` | `security.yaml` | Security groups |
| `aura-vpc-endpoints-dev` | `vpc-endpoints.yaml` | VPC endpoints for AWS services |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1
```

---

### Layer 2: Data
**CodeBuild Project:** `aura-data-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-data.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-s3-dev` | `s3.yaml` | S3 buckets |
| `aura-dynamodb-dev` | `dynamodb.yaml` | DynamoDB tables |
| `aura-neptune-dev` | `neptune.yaml` | Neptune graph database |
| `aura-opensearch-dev` | `opensearch.yaml` | OpenSearch cluster |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-data-deploy-dev --region us-east-1
```

---

### Layer 3: Compute
**CodeBuild Project:** `aura-compute-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-compute.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-eks-dev` | `eks.yaml` | EKS cluster and node groups |
| `aura-ecr-dnsmasq-dev` | `ecr-dnsmasq.yaml` | ECR repo for dnsmasq |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-compute-deploy-dev --region us-east-1
```

---

### Layer 4: Application
**CodeBuild Project:** `aura-application-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-application.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-bedrock-infrastructure-dev` | `bedrock-infrastructure.yaml` | Bedrock LLM configuration |
| `aura-irsa-api-dev` | `irsa-api.yaml` | IRSA for API service |
| `aura-network-services-dev` | `network-services.yaml` | ECS network services (dnsmasq) |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-application-deploy-dev --region us-east-1
```

---

### Layer 5: Observability
**CodeBuild Project:** `aura-observability-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-observability.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-secrets-dev` | `secrets.yaml` | Secrets Manager secrets |
| `aura-monitoring-dev` | `monitoring.yaml` | CloudWatch dashboards, alarms |
| `aura-cost-alerts-dev` | `cost-alerts.yaml` | AWS Budgets alerts |
| `aura-realtime-monitoring-dev` | `realtime-monitoring.yaml` | Real-time anomaly detection |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-observability-deploy-dev --region us-east-1
```

---

### Layer 6: Serverless
**CodeBuild Project:** `aura-serverless-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-serverless.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-dns-blocklist-lambda-dev` | `dns-blocklist-lambda.yaml` | DNS blocklist Lambda |
| `aura-threat-intel-scheduler-dev` | `threat-intel-scheduler.yaml` | Threat intelligence updates |
| `aura-incident-response-dev` | `incident-response.yaml` | Incident response automation |
| `aura-incident-investigation-dev` | `incident-investigation-workflow.yaml` | Incident investigation Step Functions |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-serverless-deploy-dev --region us-east-1
```

---

### Layer 7: Sandbox
**CodeBuild Project:** `aura-sandbox-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-sandbox.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-sandbox-dev` | `sandbox.yaml` | ECS cluster, task definitions, DynamoDB tables |
| `aura-hitl-workflow-dev` | `hitl-workflow.yaml` | Step Functions HITL workflow |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-sandbox-deploy-dev --region us-east-1
```

---

### Layer 8: Security
**CodeBuild Project:** `aura-security-deploy-dev`
**Buildspec:** `deploy/buildspecs/buildspec-security.yml`

**Stacks Deployed:**
| Stack | Template | Purpose |
|-------|----------|---------|
| `aura-config-compliance-dev` | `config-compliance.yaml` | AWS Config rules |
| `aura-guardduty-dev` | `guardduty.yaml` | GuardDuty threat detection |

**Trigger Command:**
```bash
aws codebuild start-build --project-name aura-guardduty-deploy-dev --region us-east-1
```

---

## Bootstrap Deployments (One-Time Setup)

These scripts are for **initial environment setup only**. Run once per environment, then use CI/CD.

### CodeBuild Infrastructure
**Script:** `deploy/scripts/deploy-*-codebuild.sh`
**Purpose:** Create the CodeBuild projects that deploy infrastructure layers

**Commands:**
```bash
# Deploy all CodeBuild projects (run once per environment)
./deploy/scripts/deploy-foundation-codebuild.sh
./deploy/scripts/deploy-data-codebuild.sh
./deploy/scripts/deploy-compute-codebuild.sh
./deploy/scripts/deploy-application-codebuild.sh
./deploy/scripts/deploy-observability-codebuild.sh
./deploy/scripts/deploy-serverless-codebuild.sh
./deploy/scripts/deploy-sandbox-codebuild.sh
./deploy/scripts/deploy-security-codebuild.sh
./deploy/scripts/deploy-frontend-codebuild.sh
```

---

### ECR Base Images
**Script:** `deploy/scripts/bootstrap-base-images.sh`
**Purpose:** Create ECR repos and push base Docker images (alpine, node, nginx)
**Stacks:** `aura-ecr-base-images-dev`

**Command:**
```bash
./deploy/scripts/bootstrap-base-images.sh
```

---

### ECR Frontend
**Script:** (manual via AWS CLI)
**Purpose:** Create ECR repo for frontend application
**Stacks:** `aura-ecr-frontend-dev`

**Command:**
```bash
aws cloudformation deploy \
  --template-file deploy/cloudformation/ecr-frontend.yaml \
  --stack-name aura-ecr-frontend-dev \
  --parameter-overrides Environment=dev ProjectName=aura \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

---

### ArgoCD GitHub App Configuration
**Script:** `deploy/scripts/configure-argocd-github-app.sh`
**Purpose:** Configure ArgoCD with GitHub App authentication

**Command:**
```bash
./deploy/scripts/configure-argocd-github-app.sh
```

---

## GitOps Deployments (ArgoCD)

Application-level deployments to Kubernetes are managed by ArgoCD.

### ArgoCD Applications
| Application | Path | Purpose |
|-------------|------|---------|
| `aura-api` | `deploy/kubernetes/argocd/applications/aura-api.yaml` | API service deployment |
| `aura-frontend` | `deploy/kubernetes/argocd/applications/aura-frontend.yaml` | Frontend deployment |

### How It Works
1. Commit changes to `deploy/kubernetes/` manifests
2. ArgoCD detects drift and syncs automatically
3. Argo Rollouts handles canary/blue-green deployments

### Manual Sync (if needed)
```bash
# Check sync status
kubectl get applications -n argocd

# Force sync
argocd app sync aura-api
argocd app sync aura-frontend
```

---

## Manual/Utility Scripts

These scripts are for specific operational tasks, not regular deployments.

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate-deployment.sh` | Validate stack deployments | After CodeBuild runs |
| `harden-eks-nodes.sh` | Apply STIG hardening | GovCloud prep |
| `update-eks-node-ami.sh` | Update node AMI | Security patches |
| `update-dnsmasq-blocklist.sh` | Update DNS blocklist | Threat intel updates |
| `delete-nat-gateways.sh` | Remove NAT gateways | Cost optimization |
| `migrate-to-vpc-endpoints.sh` | Set up VPC endpoints | After NAT removal |
| `trigger-hitl-test.sh` | Trigger HITL test workflow | E2E testing |
| `stage-code-for-sandbox.py` | Stage code to S3 for HITL | Before HITL tests |

---

## Quick Reference: Deployment Decision Tree

```
Is this a new environment?
├── YES → Run bootstrap scripts first, then CI/CD
└── NO → Is this Kubernetes application code?
    ├── YES → Commit to repo, ArgoCD syncs automatically
    └── NO → Is this infrastructure (CloudFormation)?
        ├── YES → Use CodeBuild (trigger via AWS Console or CLI)
        └── NO → Use appropriate utility script
```

---

## Environment Variables

All deployments expect these environment variables:

```bash
export AWS_PROFILE=aura-admin      # AWS credentials profile
export AWS_REGION=us-east-1        # Target region
export ENVIRONMENT=dev             # Environment (dev/qa/prod)
export PROJECT_NAME=aura           # Project name prefix
```

---

## Checking Build Status

### Check if a build is running (before triggering)
```bash
aws codebuild list-builds-for-project \
  --project-name aura-{layer}-deploy-dev \
  --max-items 1 \
  --query 'ids[0]' \
  --output text | xargs -I {} aws codebuild batch-get-builds --ids {} \
  --query 'builds[0].buildStatus' --output text
```

### Watch build logs
```bash
BUILD_ID=$(aws codebuild start-build --project-name aura-{layer}-deploy-dev --query 'build.id' --output text)
aws logs tail /aws/codebuild/aura-{layer}-deploy-dev --follow
```

---

## Summary Table

| Layer | Stacks | CodeBuild Project | Bootstrap Script |
|-------|--------|-------------------|------------------|
| 1 - Foundation | 4 | `aura-foundation-deploy-dev` | `deploy-foundation-codebuild.sh` |
| 2 - Data | 4 | `aura-data-deploy-dev` | `deploy-data-codebuild.sh` |
| 3 - Compute | 2 | `aura-compute-deploy-dev` | `deploy-compute-codebuild.sh` |
| 4 - Application | 3 | `aura-application-deploy-dev` | `deploy-application-codebuild.sh` |
| 5 - Observability | 4 | `aura-observability-deploy-dev` | `deploy-observability-codebuild.sh` |
| 6 - Serverless | 4 | `aura-serverless-deploy-dev` | `deploy-serverless-codebuild.sh` |
| 7 - Sandbox | 2 | `aura-sandbox-deploy-dev` | `deploy-sandbox-codebuild.sh` |
| 8 - Security | 2 | `aura-security-deploy-dev` | `deploy-security-codebuild.sh` |
| Frontend | - | `aura-frontend-deploy-dev` | `deploy-frontend-codebuild.sh` |

**Total: 36 stacks across 8 layers + frontend**
