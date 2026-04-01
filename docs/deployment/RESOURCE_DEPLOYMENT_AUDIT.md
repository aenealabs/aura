# Project Aura - Resource Deployment Audit

**Last Updated:** 2026-01-15
**Purpose:** Comprehensive documentation of all AWS resources and their deployment methods for platform support team
**Audit Status:** All templates have deployment coverage (verified 2026-01-15)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Deployment Architecture Overview](#deployment-architecture-overview)
3. [CI/CD Deployed Resources](#cicd-deployed-resources)
4. [Manually Deployed Resources (Prerequisites)](#manually-deployed-resources-prerequisites)
5. [Dependency Graph](#dependency-graph)
6. [Deployment Sequence Guide](#deployment-sequence-guide)
7. [Kubernetes Resources](#kubernetes-resources)
8. [Cross-Stack References](#cross-stack-references)
9. [Recommendations](#recommendations)

---

## Executive Summary

Project Aura uses a **three-phase deployment model**:

| Phase | Method | Purpose | One-Time? |
|-------|--------|---------|-----------|
| **Phase 1: Prerequisites** | Manual CLI/Console | SSM Parameters, GitHub Connection | Yes |
| **Phase 2: Bootstrap** | `deploy-*-codebuild.sh` scripts | Create CodeBuild projects | Yes per env |
| **Phase 3: CI/CD Pipeline** | CodeBuild buildspecs | Deploy infrastructure and applications | Repeatable |

**Key Statistics:**
- **36 Buildspecs** (deployment pipelines including sub-buildspecs)
- **122 CloudFormation Templates** in `deploy/cloudformation/`
- **40+ Kubernetes Manifests** in `deploy/kubernetes/`
- **8 Layers** of infrastructure (Foundation through Security)
- **100% Deployment Coverage** - All templates deployed via CodeBuild

---

## Deployment Architecture Overview

```
                    PHASE 1: MANUAL PREREQUISITES
                    =============================
    ┌─────────────────────────────────────────────────────────────┐
    │ SSM Parameters:                                              │
    │   /aura/global/codeconnections-arn (GitHub Connection)      │
    │   /aura/{env}/admin-role-arn (SSO Admin Role)               │
    │   /aura/{env}/alert-email (Notification Email)              │
    │                                                              │
    │ GitHub CodeConnection:                                       │
    │   Created in AWS Console > Developer Tools > Connections    │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    PHASE 2: BOOTSTRAP (ONE-TIME)
                    =============================
    ┌─────────────────────────────────────────────────────────────┐
    │ deploy-foundation-codebuild.sh → codebuild-foundation.yaml  │
    │ deploy-data-codebuild.sh → codebuild-data.yaml              │
    │ deploy-compute-codebuild.sh → codebuild-compute.yaml        │
    │ deploy-application-codebuild.sh → codebuild-application.yaml│
    │ deploy-observability-codebuild.sh → codebuild-observability │
    │ deploy-serverless-codebuild.sh → codebuild-serverless.yaml  │
    │ deploy-sandbox-codebuild.sh → codebuild-sandbox.yaml        │
    │ deploy-security-codebuild.sh → codebuild-security.yaml      │
    │ deploy-frontend-codebuild.sh → codebuild-frontend.yaml      │
    │ (chat-assistant) → codebuild-chat-assistant.yaml            │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    PHASE 3: CI/CD PIPELINE
                    =======================
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 1: Foundation  → buildspec-foundation.yml             │
    │ Layer 2: Data        → buildspec-data.yml                   │
    │ Layer 3: Compute     → buildspec-compute.yml                │
    │ Layer 4: Application → buildspec-application.yml            │
    │ Layer 5: Observability → buildspec-observability.yml        │
    │ Layer 6: Serverless  → buildspec-serverless.yml             │
    │ Layer 7: Sandbox     → buildspec-sandbox.yml                │
    │ Layer 8: Security    → buildspec-security.yml               │
    │ Frontend Service     → buildspec-service-frontend.yml       │
    │ Chat Assistant       → buildspec-chat-assistant.yml         │
    │ Coordinator          → buildspec-coordinator.yml             │
    └─────────────────────────────────────────────────────────────┘
```

---

## CI/CD Deployed Resources

### Layer 1: Foundation (buildspec-foundation.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-foundation-deploy-{env}` | `aura-networking-{env}` | `networking.yaml` | VPC, Subnets (2 public, 2 private), Route Tables, Internet Gateway, NAT Gateway |
| | `aura-security-{env}` | `security.yaml` | 8 Security Groups (EKS, EKS Nodes, Neptune, OpenSearch, ALB, VPC Endpoints, ECS Workload, Lambda), AWS WAF Web ACL |
| | `aura-iam-{env}` | `iam.yaml` | 7 IAM Roles (EKS Cluster, EKS Node, Service, Neptune Access, CodeBuild, CloudFormation, Lambda Execution) |
| | `aura-vpc-endpoints-{env}` | `vpc-endpoints.yaml` | 9+ VPC Endpoints (ECR, S3, CloudWatch, SSM, STS, etc.) |
| | `aura-ecr-base-images-{env}` | `ecr-base-images.yaml` | 3 ECR Repositories (Alpine, Node.js, Nginx base images) |

**Time to Deploy:** ~5-7 minutes

---

### Layer 2: Data (buildspec-data.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-data-deploy-{env}` | `aura-dynamodb-{env}` | `dynamodb.yaml` | 4 DynamoDB Tables (code-contexts, vulnerability-tracking, agent-state, patch-history) |
| | `aura-s3-{env}` | `s3.yaml` | 2+ S3 Buckets (artifacts, logs) |
| | `aura-neptune-{env}` | `neptune-simplified.yaml` | Neptune Cluster (db.t3.medium), Parameter Group, Subnet Group, KMS Key |
| | `aura-opensearch-{env}` | `opensearch.yaml` | OpenSearch Domain (t3.small.search), Access Policy |

**Time to Deploy:** ~15-20 minutes (Neptune/OpenSearch take 10-15 min each)

---

### Layer 3: Compute (buildspec-compute.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-compute-deploy-{env}` | `aura-eks-{env}` | `eks.yaml` | EKS Cluster (K8s 1.34), OIDC Provider, Managed Node Group (t3.medium, 2-5 nodes), EKS Access Entries |

**Time to Deploy:** ~30-45 minutes (EKS cluster creation)

---

### Layer 4: Application (buildspec-application.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-application-deploy-{env}` | `aura-ecr-dnsmasq-{env}` | `ecr-dnsmasq.yaml` | ECR Repository for dnsmasq |
| | `aura-ecr-api-{env}` | `ecr-api.yaml` | ECR Repository for API |
| | `aura-bedrock-infrastructure-{env}` | `aura-bedrock-infrastructure.yaml` | Bedrock IAM Role, SNS Topic |
| | `aura-irsa-api-{env}` | `irsa-aura-api.yaml` | IRSA Role for aura-api ServiceAccount |

**Kubernetes Resources Deployed (via buildspec-application-k8s.yml):**
- `aura-service-config/*` - Shared service configuration ConfigMap (deployed first)
- `dnsmasq-daemonset.yaml` - DNS caching DaemonSet
- `dnsmasq-networkpolicy.yaml` - Network isolation
- `aura-api/*` - API deployment via Kustomize

**Time to Deploy:** ~10-15 minutes

---

### Layer 5: Observability (buildspec-observability.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-observability-deploy-{env}` | `aura-secrets-{env}` | `secrets.yaml` | Secrets Manager secrets (Bedrock, Neptune, OpenSearch, API keys, JWT) |
| | `aura-monitoring-{env}` | `monitoring.yaml` | CloudWatch Dashboard, Alarms, SNS Topic, Log Groups |
| | `aura-cost-alerts-{env}` | `aura-cost-alerts.yaml` | AWS Budgets (daily $15, monthly $400) |
| | `aura-realtime-monitoring-{env}` | `realtime-monitoring.yaml` | EventBridge Rules, CloudWatch Alarms, SNS Alerts |

**Time to Deploy:** ~5-10 minutes

---

### Layer 6: Serverless (buildspec-serverless.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-serverless-deploy-{env}` | `aura-threat-intel-scheduler-{env}` | `threat-intel-scheduler.yaml` | Lambda (threat intel processor), EventBridge Rule |
| | `aura-hitl-scheduler-{env}` | `hitl-scheduler.yaml` | Lambda (HITL expiration), EventBridge Rule |
| | `aura-hitl-callback-{env}` | `hitl-callback.yaml` | Lambda (approval callback handler) |

**Time to Deploy:** ~8-12 minutes

---

### Layer 7: Sandbox (buildspec-sandbox.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-sandbox-deploy-{env}` | `aura-sandbox-{env}` | `sandbox.yaml` | DynamoDB Tables (approval-requests, sandbox-state, sandbox-results), ECS Cluster, Security Groups, IAM Roles, SNS Topic, S3 Bucket, ECR Repository |
| | `aura-hitl-workflow-{env}` | `hitl-workflow.yaml` | Step Functions State Machine |

**Docker Image Built:** Sandbox Test Runner (pushed to ECR)

**Time to Deploy:** ~10-15 minutes

---

### Layer 8: Security/Compliance (buildspec-security.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-security-deploy-{env}` | `aura-config-compliance-{env}` | `config-compliance.yaml` | AWS Config Recorder, 18 Config Rules (CMMC/NIST), SNS Topic |
| | `aura-guardduty-{env}` | `guardduty.yaml` | GuardDuty Detector, S3/EKS/Malware Protection |

**Time to Deploy:** ~5-10 minutes

---

### Frontend Service (buildspec-service-frontend.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-frontend-deploy-{env}` | `aura-ecr-frontend-{env}` | `ecr-frontend.yaml` | ECR Repository for frontend |

**Kubernetes Resources Deployed:**
- `aura-frontend/*` - Frontend deployment via Kustomize
- Argo Rollouts for canary deployment

**Time to Deploy:** ~5-10 minutes

---

### Chat Assistant (buildspec-chat-assistant.yml)

| CodeBuild Project | Stack Name Pattern | CloudFormation Template | Resources Created |
|-------------------|-------------------|------------------------|-------------------|
| `aura-chat-assistant-deploy-{env}` | `aura-chat-assistant-{env}` | `chat-assistant.yaml` | 4 Lambda Functions (chat-handler, ws-connect, ws-disconnect, ws-message), API Gateway (REST + WebSocket), S3 Bucket |

**Time to Deploy:** ~5-10 minutes

---

## Manually Deployed Resources (Prerequisites)

These resources must be created **BEFORE** running any CI/CD pipeline.

### SSM Parameters (Required)

| Parameter Path | Type | Description | How to Create |
|---------------|------|-------------|---------------|
| `/aura/global/codeconnections-arn` | String | GitHub CodeConnections ARN | `aws ssm put-parameter --name "/aura/global/codeconnections-arn" --type "String" --value "arn:aws:codeconnections:..."` |
| `/aura/{env}/admin-role-arn` | String | SSO Administrator Role ARN | `aws ssm put-parameter --name "/aura/{env}/admin-role-arn" --type "String" --value "arn:aws:iam::..."` |
| `/aura/{env}/alert-email` | String | Email for notifications | `aws ssm put-parameter --name "/aura/{env}/alert-email" --type "String" --value "alerts@example.com"` |

### GitHub CodeConnection (Required)

| Resource | Type | Description | How to Create |
|----------|------|-------------|---------------|
| GitHub Connection | CodeConnections | Connects CodeBuild to GitHub repo | AWS Console > Developer Tools > Settings > Connections > Create connection > GitHub |

### Manual Bootstrap Scripts

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `bootstrap-base-images.sh` | Pull Alpine/Node/Nginx to private ECR | After Foundation layer deploys ECR Base Images stack |
| `configure-argocd-github-app.sh` | Configure ArgoCD GitHub App authentication | After ArgoCD is installed |

### SNS Email Confirmation

| Action | When | How |
|--------|------|-----|
| Confirm SNS subscription | After Observability layer deploys | Click "Confirm subscription" link in email from AWS Notifications |

---

## Dependency Graph

```
                           PREREQUISITES (Manual)
                           ─────────────────────
                    ┌─────────────────────────────────┐
                    │  SSM Parameters                  │
                    │  GitHub CodeConnection           │
                    └──────────────┬──────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │  Layer 1: FOUNDATION            │
                    │  ─────────────────────          │
                    │  networking.yaml                │
                    │  security.yaml                  │
                    │  iam.yaml                       │
                    │  vpc-endpoints.yaml             │
                    │  ecr-base-images.yaml           │
                    └──────────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ Layer 2: DATA       │ │ Layer 5: OBSERV     │ │ bootstrap-base-     │
│ ───────────────     │ │ ─────────────       │ │ images.sh (Manual)  │
│ dynamodb.yaml       │ │ secrets.yaml        │ └─────────────────────┘
│ s3.yaml             │ │ monitoring.yaml     │
│ neptune-simpl.yaml  │ │ cost-alerts.yaml    │
│ opensearch.yaml     │ │ realtime-mon.yaml   │
└─────────┬───────────┘ └─────────────────────┘
          │
          │ (Data layer provides endpoints)
          │
          ├────────────────────┐
          │                    │
          ▼                    ▼
┌─────────────────────┐ ┌─────────────────────┐
│ Layer 3: COMPUTE    │ │ Layer 6: SERVERLESS │
│ ─────────────────   │ │ ─────────────────── │
│ eks.yaml            │ │ threat-intel-sched  │
│                     │ │ hitl-scheduler.yaml │
└─────────┬───────────┘ │ hitl-callback.yaml  │
          │             └─────────────────────┘
          │
          │ (EKS cluster provides K8s API)
          │
          ├────────────────────┬────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ Layer 4: APPLICATION│ │ Layer 7: SANDBOX    │ │ Layer 8: SECURITY   │
│ ─────────────────── │ │ ─────────────────   │ │ ─────────────────   │
│ ecr-dnsmasq.yaml    │ │ sandbox.yaml        │ │ config-compliance   │
│ ecr-api.yaml        │ │ hitl-workflow.yaml  │ │ guardduty.yaml      │
│ bedrock-infra.yaml  │ └─────────────────────┘ └─────────────────────┘
│ irsa-aura-api.yaml  │
│ + K8s manifests     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐ ┌─────────────────────┐
│ FRONTEND SERVICE    │ │ CHAT ASSISTANT      │
│ ─────────────────   │ │ ──────────────      │
│ ecr-frontend.yaml   │ │ chat-assistant.yaml │
│ + K8s manifests     │ │ + Lambda functions  │
└─────────────────────┘ └─────────────────────┘
```

---

## Deployment Sequence Guide

### Fresh Environment Deployment

Execute in this exact order:

```bash
# ============================================
# PHASE 1: Manual Prerequisites (ONE-TIME)
# ============================================

# 1.1 Create GitHub CodeConnection in AWS Console
# Go to: AWS Console > Developer Tools > Settings > Connections
# Create connection, authorize GitHub, copy ARN

# 1.2 Create SSM Parameters
aws ssm put-parameter --name "/aura/global/codeconnections-arn" --type "String" \
  --value "arn:aws:codeconnections:us-east-1:ACCOUNT:connection/XXXXX"

aws ssm put-parameter --name "/aura/dev/admin-role-arn" --type "String" \
  --value "arn:aws:iam::ACCOUNT:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_XXXXX"

aws ssm put-parameter --name "/aura/dev/alert-email" --type "String" \
  --value "alerts@example.com"

# ============================================
# PHASE 2: Bootstrap CodeBuild Projects (ONE-TIME)
# ============================================

./deploy/scripts/deploy-foundation-codebuild.sh dev
./deploy/scripts/deploy-data-codebuild.sh dev
./deploy/scripts/deploy-compute-codebuild.sh dev
./deploy/scripts/deploy-application-codebuild.sh dev
./deploy/scripts/deploy-observability-codebuild.sh dev
./deploy/scripts/deploy-serverless-codebuild.sh dev
./deploy/scripts/deploy-sandbox-codebuild.sh dev
./deploy/scripts/deploy-security-codebuild.sh dev
./deploy/scripts/deploy-frontend-codebuild.sh dev

# ============================================
# PHASE 3: Deploy Infrastructure via CI/CD
# ============================================

# Layer 1: Foundation (5-7 min)
aws codebuild start-build --project-name aura-foundation-deploy-dev
# WAIT FOR COMPLETION

# Bootstrap base images (after Foundation completes)
./deploy/scripts/bootstrap-base-images.sh dev

# Layer 2: Data (15-20 min) - can start after Foundation
aws codebuild start-build --project-name aura-data-deploy-dev

# Layer 5: Observability (5-10 min) - can run PARALLEL with Data
aws codebuild start-build --project-name aura-observability-deploy-dev
# WAIT FOR BOTH TO COMPLETE

# Layer 3: Compute (30-45 min) - needs Foundation
aws codebuild start-build --project-name aura-compute-deploy-dev
# WAIT FOR COMPLETION

# Layer 4: Application (10-15 min) - needs Compute + Data
aws codebuild start-build --project-name aura-application-deploy-dev

# Layer 6: Serverless (8-12 min) - needs Observability
aws codebuild start-build --project-name aura-serverless-deploy-dev

# Layer 7: Sandbox (10-15 min) - needs Foundation + Data
aws codebuild start-build --project-name aura-sandbox-deploy-dev

# Layer 8: Security (5-10 min) - needs Foundation
aws codebuild start-build --project-name aura-security-deploy-dev

# Frontend Service (5-10 min) - needs Compute
aws codebuild start-build --project-name aura-frontend-deploy-dev

# Chat Assistant (5-10 min) - standalone
aws codebuild start-build --project-name aura-chat-assistant-deploy-dev

# ============================================
# POST-DEPLOYMENT: Confirm SNS Subscriptions
# ============================================
# Check email inbox and click "Confirm subscription" links
```

### Recovery Procedures

#### Layer 1: Foundation Failure

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name aura-networking-dev
aws cloudformation describe-stacks --stack-name aura-security-dev
aws cloudformation describe-stacks --stack-name aura-iam-dev

# If ROLLBACK_COMPLETE, delete and recreate
aws cloudformation delete-stack --stack-name aura-networking-dev
aws cloudformation wait stack-delete-complete --stack-name aura-networking-dev

# Re-trigger build
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

#### Layer 2: Data Failure

```bash
# Neptune/OpenSearch failures often need cleanup
aws cloudformation describe-stack-events --stack-name aura-neptune-dev --max-items 20

# If stuck in CREATE_FAILED, delete the stack
aws cloudformation delete-stack --stack-name aura-neptune-dev
aws cloudformation wait stack-delete-complete --stack-name aura-neptune-dev

# Re-trigger
aws codebuild start-build --project-name aura-data-deploy-dev
```

#### Security Groups in Use (Cannot Delete)

```bash
# Check for ENI dependencies
aws ec2 describe-network-interfaces \
  --filters "Name=group-name,Values=aura-*-sg-dev" \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Description,Groups[0].GroupName]'

# Option 1: Import orphaned security groups
./deploy/scripts/import-security-groups.sh

# Option 2: Delete dependent services first (EKS, Neptune, OpenSearch)
aws eks delete-nodegroup --cluster-name aura-cluster-dev --nodegroup-name aura-system-ng-dev
aws eks delete-cluster --name aura-cluster-dev
```

---

## Kubernetes Resources

### Deployed by Application Layer (buildspec-application-k8s.yml)

| Manifest | Namespace | Type | Purpose |
|----------|-----------|------|---------|
| `aura-service-config/*` | default | ConfigMap | Shared service configuration (URLs, emails) |
| `dnsmasq-daemonset.yaml` | aura-network-services | DaemonSet | DNS caching on each node |
| `dnsmasq-networkpolicy.yaml` | aura-network-services | NetworkPolicy | DNS isolation |
| `dnsmasq-prometheus-exporter.yaml` | aura-network-services | DaemonSet | Prometheus metrics |
| `dnsmasq-blocklist-sync.yaml` | aura-network-services | CronJob | Sync blocklist from S3 |
| `aura-api/deployment.yaml` | default | Deployment | API service |
| `aura-api/service.yaml` | default | Service | API service endpoint |
| `aura-api/serviceaccount.yaml` | default | ServiceAccount | IRSA-enabled SA |
| `aura-api/configmap.yaml` | default | ConfigMap | API configuration |
| `aura-api/rollout.yaml` | default | Argo Rollout | Canary deployment |

### Shared Service Configuration (aura-service-config)

Deployed first by `buildspec-application-k8s.yml` to provide environment-specific configuration:

| Variable | Description | Dev Value | Prod Value |
|----------|-------------|-----------|------------|
| `SUPPORT_EMAIL` | Support contact email | `support-dev@aenealabs.com` | `support@aenealabs.com` |
| `PRICING_PAGE_URL` | Pricing page URL | `https://dev.aenealabs.com/pricing` | `https://app.aenealabs.com/pricing` |
| `LICENSE_RENEWAL_URL` | License renewal URL | `https://dev.aenealabs.com/renew` | `https://app.aenealabs.com/renew` |
| `GPU_DASHBOARD_BASE_URL` | GPU dashboard URL | `https://dev.aenealabs.com` | `https://app.aenealabs.com` |

**Deployment:**
```bash
kubectl apply -k deploy/kubernetes/aura-service-config/overlays/${ENVIRONMENT}/
```

### Deployed by Frontend Layer (buildspec-service-frontend.yml)

**Note:** All manifests follow the base/overlay Kustomize pattern. The buildspec deploys via environment-specific overlays (e.g., `overlays/dev/`).

| Manifest | Namespace | Type | Purpose |
|----------|-----------|------|---------|
| `aura-frontend/base/deployment.yaml` | default | Deployment | Frontend service |
| `aura-frontend/base/service.yaml` | default | Service | Frontend endpoint |
| `aura-frontend/base/rollout.yaml` | default | Argo Rollout | Canary deployment |

### ArgoCD Resources (Separate Installation)

| Manifest | Namespace | Type | Purpose |
|----------|-----------|------|---------|
| `argocd/namespace.yaml` | argocd | Namespace | ArgoCD namespace |
| `argocd/applications/aura-api.yaml` | argocd | Application | GitOps for aura-api |
| `argocd/applications/aura-frontend.yaml` | argocd | Application | GitOps for aura-frontend |
| `argocd/projects/aura.yaml` | argocd | AppProject | Aura project definition |
| `argo-rollouts/namespace.yaml` | argo-rollouts | Namespace | Argo Rollouts namespace |
| `argo-rollouts/analysis-templates.yaml` | argo-rollouts | ClusterAnalysisTemplate | Canary analysis |

### ALB Controller Resources

| Manifest | Namespace | Type | Purpose |
|----------|-----------|------|---------|
| `alb-controller/service-account.yaml` | kube-system | ServiceAccount | ALB Controller IRSA |
| `alb-controller/ingress-class.yaml` | kube-system | IngressClass | ALB ingress class |
| `alb-controller/aura-api-ingress.yaml` | default | Ingress | API ingress |
| `alb-controller/aura-frontend-ingress.yaml` | default | Ingress | Frontend ingress |

### OpenTelemetry Collector

| Manifest | Namespace | Type | Purpose |
|----------|-----------|------|---------|
| `otel-collector/namespace.yaml` | observability | Namespace | OTEL namespace |
| `otel-collector/configmap.yaml` | observability | ConfigMap | OTEL config |
| `otel-collector/deployment.yaml` | observability | Deployment | OTEL collector |

---

## Cross-Stack References

### Networking Stack Exports

| Export Name | Value | Consumed By |
|-------------|-------|-------------|
| `aura-networking-{env}-VpcId` | VPC ID | security, vpc-endpoints, eks, neptune, opensearch, sandbox |
| `aura-networking-{env}-PrivateSubnetIds` | Private Subnets | eks, neptune, opensearch, sandbox |
| `aura-networking-{env}-PublicSubnetIds` | Public Subnets | eks (nodes) |
| `aura-networking-{env}-VpcCIDR` | VPC CIDR | security groups |

### Security Stack Exports

| Export Name | Value | Consumed By |
|-------------|-------|-------------|
| `aura-security-{env}-EKSSecurityGroupId` | EKS SG | eks |
| `aura-security-{env}-EKSNodeSecurityGroupId` | EKS Node SG | eks |
| `aura-security-{env}-NeptuneSecurityGroupId` | Neptune SG | neptune |
| `aura-security-{env}-OpenSearchSecurityGroupId` | OpenSearch SG | opensearch |
| `aura-security-{env}-VPCEndpointSecurityGroupId` | VPC Endpoint SG | vpc-endpoints |
| `aura-ecs-workload-sg-{env}` | ECS Workload SG | sandbox, incident-investigation |
| `aura-lambda-sg-{env}` | Lambda SG | serverless functions |
| `aura-security-{env}-WAFWebACLArn` | WAF ACL ARN | alb-controller |

### IAM Stack Exports

| Export Name | Value | Consumed By |
|-------------|-------|-------------|
| `aura-iam-{env}-EKSClusterRoleArn` | EKS Cluster Role | eks |
| `aura-iam-{env}-EKSNodeRoleArn` | EKS Node Role | eks |
| `aura-iam-{env}-ServiceRoleArn` | Service Role | application |
| `aura-iam-{env}-LambdaExecutionRoleArn` | Lambda Role | serverless |

### EKS Stack Exports

| Export Name | Value | Consumed By |
|-------------|-------|-------------|
| `aura-eks-{env}-ClusterName` | Cluster Name | application, frontend |
| `aura-eks-{env}-ClusterEndpoint` | API Endpoint | application, frontend |
| `aura-eks-{env}-OIDCProviderArn` | OIDC Provider | irsa-aura-api, alb-controller |

### Monitoring Stack Exports

| Export Name | Value | Consumed By |
|-------------|-------|-------------|
| `aura-monitoring-{env}-AlertTopicArn` | SNS Topic ARN | serverless, sandbox |

---

## Recommendations

### 1. Deployment Coverage Status (Updated 2026-01-15)

All previously identified gaps have been addressed. Every CloudFormation template now has deployment coverage:

| Previously Identified Gap | Resolution | Buildspec |
|---------------------------|------------|-----------|
| ALB Controller Stack | Now deployed | `buildspec-compute.yml` |
| Cognito Stack | Now deployed | `buildspec-application-bedrock.yml` |
| Bedrock Guardrails | Now deployed | `buildspec-application-bedrock.yml` |
| Disaster Recovery | Now deployed | `buildspec-observability.yml` |
| Red Team Infrastructure | Now deployed | `buildspec-security.yml` |
| A2A Infrastructure | Now deployed | `buildspec-serverless-stacks.yml` |
| Incident Response | Now deployed | `buildspec-bootstrap.yml` |
| Network Services | Now deployed | `buildspec-application-k8s.yml` |
| OTEL Collector | Now deployed | `buildspec-observability.yml` |

### 2. Templates Deployment Summary

All 122 CloudFormation templates are deployed via CodeBuild:

| Category | Count | Deployed By |
|----------|-------|-------------|
| Infrastructure (Layers 1-8) | 83 | Layer-specific buildspecs |
| CodeBuild Projects | 16 | `buildspec-bootstrap.yml` |
| Sub-layer Templates | 23 | Sub-buildspecs (e.g., `buildspec-application-k8s.yml`) |

### 3. Kubernetes Resources Summary

| Resource Type | Count | Deployed By |
|---------------|-------|-------------|
| ConfigMaps | 5 | `buildspec-application-k8s.yml` |
| Deployments/Rollouts | 4 | Application layer buildspecs |
| DaemonSets | 2 | `buildspec-application-k8s.yml` |
| Services | 4 | Application layer buildspecs |
| Ingress | 2 | `buildspec-compute.yml` (ALB Controller) |

### 4. Ongoing Maintenance Recommendations

| Recommendation | Priority | Status |
|----------------|----------|--------|
| Run periodic deployment audits | Medium | Use verification script |
| Keep this document updated | Low | Update after major changes |
| Monitor for manual deployments | High | Use CloudTrail alerts |
| Validate environment variables | Medium | Use env-validator (ADR-062) |

---

## Quick Reference

### Check Build Status

```bash
# List recent builds for a project
aws codebuild list-builds-for-project --project-name aura-foundation-deploy-dev --max-items 5

# Get build details
BUILD_ID=$(aws codebuild list-builds-for-project --project-name aura-foundation-deploy-dev --query 'ids[0]' --output text)
aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].{Status:buildStatus,Phase:currentPhase}'
```

### Check Stack Status

```bash
# List all aura stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].[StackName,StackStatus,CreationTime]" \
  --output table
```

### Verify SSM Parameters

```bash
aws ssm get-parameters-by-path --path "/aura" --recursive --query "Parameters[].Name" --output table
```

---

**Document Version:** 2.0
**Maintainer:** Platform Support Team
**Last Audit:** 2026-01-15 (100% deployment coverage verified)
**Related Documentation:**
- `docs/runbooks/PREREQUISITES_RUNBOOK.md` - Phase 1 setup
- `docs/deployment/CICD_SETUP_GUIDE.md` - CI/CD pipeline details
- `docs/deployment/DEPLOYMENT_GUIDE.md` - Full deployment guide with environment variables
- `MODULAR_CICD_IMPLEMENTATION.md` - Architecture overview
