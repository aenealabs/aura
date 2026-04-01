# Modular CI/CD Deployment Guide
**Project Aura - Step-by-Step Deployment Instructions**

**Target Audience:** DevOps Engineers, Platform Team, Data Team
**Prerequisites:** AWS Account, AWS CLI configured, AWS SSO access
**Estimated Time:** 30 minutes total (Foundation: 10 min, Data: 20 min)

---

## Quick Start (TL;DR)

> **Multi-Account Setup:** For QA/PROD environments in separate AWS accounts, see [MULTI_ACCOUNT_SETUP.md](./MULTI_ACCOUNT_SETUP.md) first.

```bash
# Set your AWS profile (use standardized naming: aura-admin-{env})
export AWS_PROFILE=aura-admin  # or: AdministratorAccess-<YOUR_ACCOUNT_ID>
export ENV=dev

# Step 0: Deploy Account Bootstrap (new environments only)
# See "Phase 0: Account Bootstrap" section for full parameters
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-${ENV} \
  --parameter-overrides Environment=${ENV} ... \
  --capabilities CAPABILITY_NAMED_IAM

# Step 1: Deploy Foundation Layer CodeBuild
./deploy-foundation-codebuild.sh ${ENV}

# Step 2: Deploy Data Layer CodeBuild
./deploy-data-codebuild.sh ${ENV}

# Step 3: Trigger builds
./trigger-foundation-build.sh ${ENV}
./trigger-data-build.sh ${ENV}
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 0: Account Bootstrap](#phase-0-account-bootstrap-new-environment-setup)
3. [Architecture Overview](#architecture-overview)
4. [Phase 1: Foundation Layer](#phase-1-foundation-layer)
4. [Phase 2: Data Layer](#phase-2-data-layer)
5. [Phase 3: Compute Layer (EKS)](#phase-3-compute-layer-eks-cluster)
6. [Phase 6: API Deployment](#phase-6-api-deployment-to-eks)
7. [Phase 7: Agent Orchestrator (Warm Pool)](#phase-7-agent-orchestrator-deployment-warm-pool)
8. [Orchestrator Deployment Mode Configuration](#orchestrator-deployment-mode-configuration)
9. [Docker CI/CD Best Practices](#docker-cicd-best-practices)
10. [Verification & Testing](#verification--testing)
11. [Troubleshooting](#troubleshooting)
12. [Rollback Procedures](#rollback-procedures)
13. [Next Steps](#next-steps)

---

## Prerequisites

### Required Tools

```bash
# Verify AWS CLI installed (version 2.x required)
aws --version
# Expected: aws-cli/2.x.x Python/3.x.x

# Verify jq installed (for JSON parsing)
jq --version

# Verify git installed
git --version
```

### AWS Permissions Required

Your AWS user/role must have:
- **IAM:** CreateRole, AttachRolePolicy, PassRole
- **CloudFormation:** CreateStack, UpdateStack, DescribeStacks
- **CodeBuild:** CreateProject, UpdateProject
- **S3:** CreateBucket, PutBucketPolicy
- **CloudWatch:** PutMetricAlarm, CreateLogGroup
- **Secrets Manager:** CreateSecret, DescribeSecret
- **SSM Parameter Store:** PutParameter, GetParameter

**Quick Check:**
```bash
# Verify your AWS identity
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/yourname"
# }
```

### AWS SSO Setup

If using AWS SSO:

```bash
# Configure AWS SSO profile
aws configure sso

# Login to AWS SSO
export AWS_PROFILE=AdministratorAccess-<YOUR_ACCOUNT_ID>
aws sso login --profile $AWS_PROFILE

# Verify access
aws sts get-caller-identity
```

### Container Runtime (Podman-First per ADR-049)

Podman is the primary container runtime for local development, providing rootless execution, no daemon requirement, and no licensing fees. Docker remains available as a CI/CD fallback in CodeBuild.

```bash
# Verify Podman installed (primary)
podman --version

# If not installed, see CONTRIBUTING.md for setup instructions

# Podman compose for docker-compose.yml files
podman compose version
```

**Note:** Podman reads standard `docker-compose.yml` files natively via `podman compose`. HEALTHCHECK warnings in Podman are informational only (Kubernetes/ECS use their own health checks).

---

## Phase 0: Account Bootstrap (New Environment Setup)

For new AWS accounts, deploy the account-bootstrap stack FIRST. This creates foundational SSM parameters, KMS keys, and security resources required by all other stacks.

### Deployment Order (Critical)

The account-bootstrap stack must be deployed BEFORE other infrastructure:

```
1. account-bootstrap          ← Creates SSM params, KMS key, SNS topic
2. realtime-monitoring        ← References bootstrap's SNS topic
3. foundation-codebuild       ← References SSM params
4. All other layers           ← Follow standard deployment order
```

### Account Bootstrap Deployment

```bash
# Set environment
export ENV=dev  # or: qa, prod
export AWS_PROFILE=aura-admin-${ENV}

# Login to AWS
aws sso login --profile $AWS_PROFILE

# Deploy account-bootstrap (adjust parameters based on environment)
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-${ENV} \
  --parameter-overrides \
    Environment=${ENV} \
    AdminRoleArn=$(aws sts get-caller-identity --query 'Arn' --output text | sed 's|assumed-role/\([^/]*\)/.*|role/\1|') \
    AlertEmail=notifications@aenealabs.com \
    CodeConnectionsArn=$(aws codeconnections list-connections --query 'Connections[0].ConnectionArn' --output text) \
    EnableAccountCloudTrail=true \
    EnableGuardDuty=true \
    EnableSecurityAlertsTopic=true \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=aura Environment=${ENV} ManagedBy=CloudFormation
```

### Conditional Parameters

The bootstrap template supports conditional resource creation for environments with existing resources:

| Parameter | Default | Set to `false` when... |
|-----------|---------|------------------------|
| `EnableAccountCloudTrail` | `true` | Org-level CloudTrail already covers this account |
| `EnableGuardDuty` | `true` | GuardDuty is managed by a delegated admin account |
| `EnableSecurityAlertsTopic` | `true` | Another stack (e.g., realtime-monitoring) already owns the SNS topic |

**Example: DEV Environment (Management Account)**

```bash
# DEV has org-level CloudTrail and existing realtime-monitoring SNS topic
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-dev \
  --parameter-overrides \
    Environment=dev \
    AdminRoleArn="arn:aws:iam::123456789012:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_..." \
    AlertEmail=notifications@aenealabs.com \
    CodeConnectionsArn="arn:aws:codeconnections:us-east-1:123456789012:connection/..." \
    EnableAccountCloudTrail=false \
    EnableGuardDuty=true \
    EnableSecurityAlertsTopic=false \
  --capabilities CAPABILITY_NAMED_IAM
```

### Verify Bootstrap Success

```bash
# Check SSM parameters created
aws ssm get-parameters-by-path --path "/aura/${ENV}/" --query 'Parameters[*].Name' --output table

# Check KMS key created
aws kms describe-key --key-id "alias/aura/${ENV}/master" --query 'KeyMetadata.[KeyId,KeyState]' --output table

# Check stack outputs
aws cloudformation describe-stacks --stack-name aura-account-bootstrap-${ENV} --query 'Stacks[0].Outputs' --output table
```

See [ADR-059](../architecture-decisions/ADR-059-aws-organization-account-restructure.md#interim-environment-standardization-devqa-parity) for detailed configuration differences between DEV and QA environments.

### QA Environment Bootstrap: Chicken-and-Egg Fix (Jan 17, 2026)

When bootstrapping a new QA environment, the observability layer deploys managed IAM policies that require `iam:CreatePolicy` permission. However, this permission was not originally present in the bootstrap CodeBuild role.

**Solution:** Added `iam:CreatePolicy` to `codebuild-bootstrap.yaml` (PR #414).

**Deployment Sequence for New QA Environments:**

1. Deploy `codebuild-bootstrap.yaml` with `iam:CreatePolicy` permission first
2. Then deploy observability layer stacks that create managed policies:
   - `aura-observability-cost-explorer-{env}` - Cost Explorer permissions
   - `aura-observability-iam-perms-{env}` - IAM role management permissions

**Why Managed Policies?** AWS enforces a 10KB limit on inline IAM policies. The observability layer was exceeding this limit, so permissions were split into managed policies.

---

## Bootstrap Steps (Base Images - One-Time Setup)

Before the CI/CD pipeline can build container images, you must populate the base images ECR repository. This is a one-time setup step per environment.

### Step 1: Deploy Foundation Layer

The Foundation layer creates the ECR Base Images repository:

```bash
# Trigger Foundation layer deployment
aws codebuild start-build --project-name aura-foundation-deploy-dev

# Wait for completion (5-8 minutes)
aws codebuild batch-get-builds --ids <build-id> --query 'builds[0].buildStatus'
```

### Step 2: Bootstrap Base Images

After the Foundation layer is deployed, run the bootstrap script to populate the Alpine base image:

```bash
# Run bootstrap script (uses Podman locally)
./deploy/scripts/bootstrap-base-images.sh dev

# For production environment
./deploy/scripts/bootstrap-base-images.sh prod
```

The script:
1. Pulls Alpine 3.19 from ECR Public Gallery (no rate limits)
2. Tags and pushes to your private ECR repository
3. Triggers vulnerability scanning
4. Outputs the image URI for use in Dockerfiles

### Step 3: Verify Base Image

```bash
# Check image exists in ECR
aws ecr describe-images \
  --repository-name aura-base-images/alpine \
  --image-ids imageTag=3.19 \
  --query 'imageDetails[0].{pushedAt:imagePushedAt,scanStatus:imageScanStatus.status}'

# Check for vulnerabilities
aws ecr describe-image-scan-findings \
  --repository-name aura-base-images/alpine \
  --image-id imageTag=3.19 \
  --query 'imageScanFindings.findingSeverityCounts'
```

### When to Re-run Bootstrap

Re-run the bootstrap script when:
- **Security patches:** New Alpine version with CVE fixes
- **New environment:** Setting up qa or prod environments
- **Image corruption:** ECR image deleted or corrupted

```bash
# Force re-push (overwrites existing image)
./deploy/scripts/bootstrap-base-images.sh dev --force
```

---

## ⚠️ **IMPORTANT: Pipeline Standards**

### **CodeBuild-Only Deployments**

**🚫 NEVER deploy infrastructure manually via AWS CLI or Console**

**✅ ALL deployments MUST go through CodeBuild projects:**
- Foundation Layer (1): `aura-foundation-deploy-dev`
- Network Services Layer (1.5): `aura-network-services-deploy-dev`
- Data Layer (2): `aura-data-deploy-dev`
- Compute Layer (3): `aura-compute-deploy-dev`
- Application Layer (4): `aura-application-deploy-dev`
- Observability Layer (5): `aura-observability-deploy-dev`
- Serverless Layer (6): `aura-serverless-deploy-dev`
- Incident Response Layer (6.5): `aura-incident-response-deploy-dev`
- Sandbox Layer (7): `aura-sandbox-deploy-dev`
- Security Layer (8): `aura-security-deploy-dev`

###Why CodeBuild-Only?

1. **Audit Trail:** All infrastructure changes are logged in CloudWatch Logs
2. **Validation Gates:** Smoke tests, cfn-lint, and deployment validation run automatically
3. **Consistency:** Same deployment process for dev, qa, and prod environments
4. **Security:** IAM roles are scoped per layer (blast radius reduction)
5. **Rollback:** CloudFormation stacks can be rolled back atomically

### Manual Deployment Exception

Manual deployments are ONLY allowed for:
- **Emergency hotfixes** (with immediate follow-up CodeBuild run)
- **CodeBuild project deployment** (bootstrapping the CI/CD pipeline itself)

After any manual deployment, you MUST:
1. Document the change in a GitHub issue
2. Trigger the corresponding CodeBuild project to reconcile state
3. Verify CloudFormation stacks match expected configuration

### Migration Notice

As of November 25, 2025, the obsolete monolithic CodeBuild project (`aura-infra-deploy-dev`) has been removed. All infrastructure must use the modular layer-specific projects. See `docs/MODULAR_CICD_MIGRATION_GUIDE.md` for migration details.

---

## Architecture Overview

### Modular CI/CD Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Modular Pipeline                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐                                         │
│  │  Foundation    │  (VPC, IAM, Security Groups)            │
│  │  Layer         │  - Duration: 5-7 min                    │
│  └────────┬───────┘  - Compute: SMALL (3 GB RAM)            │
│           │          - Artifact retention: 90 days          │
│           │                                                  │
│           ├──→ ┌──────────────┐                             │
│           │    │  Data Layer  │  (Neptune, OpenSearch)      │
│           │    └──────────────┘  - Duration: 15-20 min      │
│           │                       - Compute: MEDIUM (7 GB)  │
│           │                       - Artifact retention: 30d │
│           │                                                  │
│           ├──→ ┌──────────────┐                             │
│           │    │ Observability│  (CloudWatch, Prometheus)   │
│           │    └──────────────┘  - Can run in parallel!     │
│           │                                                  │
│           └──→ (Compute, Application layers - Phase 3)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Benefits vs. Monolithic

| Aspect | Monolithic | Modular | Benefit |
|--------|-----------|---------|---------|
| **Failure Isolation** | All layers fail | Single layer fails | -80% blast radius |
| **Build Duration** | 15 min (all layers) | 5-7 min (per layer) | Faster feedback |
| **Parallel Execution** | ❌ Sequential | ✅ Parallel (Foundation + Observability) | 50% time savings |
| **Team Ownership** | ❌ Single team | ✅ Layer-specific (Data Team, Platform Team) | Clear accountability |
| **Cost Attribution** | ❌ Unknown | ✅ Per-layer tracking | Chargeback enabled |

---

## Phase 1: Foundation Layer

### Step 1.1: Verify Prerequisites

```bash
# Check if Parameter Store parameter exists
aws ssm get-parameter --name "/aura/dev/alert-email" 2>/dev/null

# If not found, deployment script will prompt you to create it
```

### Step 1.2: Deploy Foundation CodeBuild

```bash
# Set AWS profile (or script will prompt)
export AWS_PROFILE=AdministratorAccess-<YOUR_ACCOUNT_ID>

# Deploy Foundation Layer CodeBuild project
./deploy-foundation-codebuild.sh dev
```

**Expected Output:**
```
==========================================
Foundation Layer CodeBuild Deployment
==========================================
Configuration:
  Environment: dev
  Project: aura
  Stack Name: aura-codebuild-foundation-dev
  Region: us-east-1

✓ Account: 123456789012
✓ Alert email: your-email@example.com
✓ Template is valid
✓ Stack deployment complete!

==========================================
Foundation Layer CodeBuild Ready!
==========================================

CodeBuild Project: aura-foundation-deploy-dev

Next Steps:
1. Trigger a Foundation Layer build:
   ./trigger-foundation-build.sh dev
```

**Duration:** 2-3 minutes

### Step 1.3: Verify Foundation CodeBuild Deployed

```bash
# List CodeBuild projects
aws codebuild list-projects --region us-east-1 | grep foundation

# Expected: "aura-foundation-deploy-dev"

# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-foundation-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# Expected: CREATE_COMPLETE or UPDATE_COMPLETE
```

### Step 1.4: Trigger Foundation Layer Build (Optional - for testing)

```bash
# Trigger a Foundation Layer build
./trigger-foundation-build.sh dev

# Monitor logs in real-time (choose 'y' when prompted)
```

**Expected Build Phases:**
1. **GATE 0:** Secrets Validation (30 seconds)
2. **GATE 1:** Template Validation (1 minute)
3. **GATE 2:** Pre-deployment Health Checks (30 seconds)
4. **BUILD:** Deploy Networking, IAM, Security stacks (3-5 minutes)
5. **GATE 3:** Post-deployment Validation (30 seconds)

**Total Duration:** 5-7 minutes

**Success Indicators:**
```
✓ All secrets present
✓ All templates valid
✓ Health checks passed
✓ aura-networking-dev deployment complete
✓ aura-iam-dev deployment complete
✓ aura-security-dev deployment complete
✓ Metrics published

========================================
Foundation Layer Ready!
========================================
```

---

## Phase 2: Data Layer

### Step 2.1: Verify Foundation Dependencies

```bash
# Check that Foundation stacks exist
for stack in aura-networking-dev aura-security-dev aura-iam-dev; do
  STATUS=$(aws cloudformation describe-stacks \
    --stack-name $stack \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$stack: $STATUS"
done

# Expected output:
# aura-networking-dev: CREATE_COMPLETE
# aura-security-dev: CREATE_COMPLETE
# aura-iam-dev: CREATE_COMPLETE
```

### Step 2.2: Deploy Data Layer CodeBuild

```bash
# Deploy Data Layer CodeBuild project
./deploy-data-codebuild.sh dev
```

**Expected Output:**
```
==========================================
Data Layer CodeBuild Deployment
==========================================
Environment: dev
Stack: aura-codebuild-data-dev

✓ Account: 123456789012
✓ Secret aura/dev/neptune exists
✓ Secret aura/dev/opensearch exists
✓ Stack deployment complete!

==========================================
Data Layer CodeBuild Ready!
==========================================

CodeBuild Project: aura-data-deploy-dev

Trigger a Data Layer build:
  ./trigger-data-build.sh
```

**Duration:** 2-3 minutes

**Note on Secrets:**
- If secrets don't exist, script auto-creates with temporary password: `TempPassword123!ChangeMe`
- **IMPORTANT:** Rotate passwords after first deployment!

```bash
# Rotate Neptune password
aws secretsmanager update-secret \
  --secret-id aura/dev/neptune \
  --secret-string '{"password":"YOUR_SECURE_PASSWORD_HERE"}'

# Rotate OpenSearch password
aws secretsmanager update-secret \
  --secret-id aura/dev/opensearch \
  --secret-string '{"password":"YOUR_SECURE_PASSWORD_HERE"}'
```

### Step 2.3: Verify Data CodeBuild Deployed

```bash
# List CodeBuild projects
aws codebuild list-projects --region us-east-1 | grep data

# Expected: "aura-data-deploy-dev"

# Check stack status
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-data-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# Expected: CREATE_COMPLETE or UPDATE_COMPLETE
```

### Step 2.4: Trigger Data Layer Build (Optional - for testing)

```bash
# Trigger a Data Layer build
./trigger-data-build.sh dev
```

**Expected Build Phases:**
1. **GATE 0:** Secrets Validation (Neptune, OpenSearch) - 30 seconds
2. **GATE 1:** Foundation Dependency Check - 30 seconds
3. **GATE 2:** Template Validation - 1 minute
4. **BUILD:** Deploy DynamoDB, S3, Neptune, OpenSearch - 15-20 minutes
5. **GATE 3:** Post-deployment Validation - 1 minute

**Total Duration:** 15-20 minutes (Neptune cluster creation is slow)

**Success Indicators:**
```
✓ All secrets present
✓ aura-networking-dev is ready (status: CREATE_COMPLETE)
✓ aura-security-dev is ready (status: CREATE_COMPLETE)
✓ All templates valid
✓ aura-dynamodb-dev deployment complete
✓ aura-s3-dev deployment complete
✓ aura-neptune-dev deployment complete
✓ aura-opensearch-dev deployment complete

Data layer deployment completed!
```

---

## Phase 3: Compute Layer (EKS Cluster)

**Status:** ✅ DEPLOYED (November 27, 2025)
**CodeBuild Project:** `aura-compute-deploy-dev`
**Stack Name:** `aura-eks-dev`
**Deployment Time:** ~15-20 minutes (EKS cluster creation)

### Overview

Phase 3 deploys the Amazon EKS (Elastic Kubernetes Service) cluster with EC2 managed node groups. This provides the Kubernetes orchestration platform for running agent workloads, dnsmasq services, and application containers.

**What Gets Deployed:**
- EKS Cluster (control plane) - Version 1.33
- EC2 Managed Node Group - 2 t3.medium nodes (min/max: 2-5)
- Launch Template - Encrypted EBS volumes, security group configuration
- OIDC Provider - For IAM Roles for Service Accounts (IRSA)
- CloudWatch Logging - All 5 log types (api, audit, authenticator, controllerManager, scheduler)

### Prerequisites

Before deploying Phase 3, verify Phase 1 and 2 are complete:

```bash
# Verify Phase 1 (Foundation) stacks
aws cloudformation describe-stacks --stack-name aura-networking-dev --query 'Stacks[0].StackStatus'
aws cloudformation describe-stacks --stack-name aura-security-dev --query 'Stacks[0].StackStatus'
aws cloudformation describe-stacks --stack-name aura-iam-dev --query 'Stacks[0].StackStatus'

# Verify Phase 2 (Data) stacks
aws cloudformation describe-stacks --stack-name aura-neptune-dev --query 'Stacks[0].StackStatus'
aws cloudformation describe-stacks --stack-name aura-opensearch-dev --query 'Stacks[0].StackStatus'
```

All should return `CREATE_COMPLETE` or `UPDATE_COMPLETE`.

### Step 3.1: Deploy Compute Layer CodeBuild Project

```bash
# Deploy the Compute layer CodeBuild project
cd /path/to/project-aura
./deploy/scripts/deploy-compute-codebuild.sh dev

# Expected output:
# Deploying Compute Layer CodeBuild for dev environment...
# Stack: aura-compute-codebuild-dev
# ✓ CodeBuild project created: aura-compute-deploy-dev
# ✓ Deployment script: deploy/scripts/trigger-compute-build.sh
```

### Step 3.2: Trigger Compute Layer Build

The CodeBuild project deploys the actual EKS infrastructure to AWS:

```bash
# Option 1: Use deployment script (recommended)
./deploy/scripts/trigger-compute-build.sh dev

# Option 2: Direct CodeBuild trigger
aws codebuild start-build --project-name aura-compute-deploy-dev
```

**Expected Build Phases:**
```
GATE 0: Pre-validation (cfn-lint validation)
GATE 1: Dependency check (Foundation layer outputs retrieved)
GATE 2: CloudFormation deployment (EKS cluster creation - 15-20 min)
GATE 3: Post-deployment verification (kubectl connectivity test)
```

### Step 3.3: Monitor EKS Deployment

```bash
# Watch CodeBuild progress
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-compute-deploy-dev \
  --query 'ids[0]' --output text)

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].currentPhase' --output text

# Monitor CloudFormation stack creation
aws cloudformation describe-stacks \
  --stack-name aura-eks-dev \
  --query 'Stacks[0].StackStatus' --output text

# Expected progression:
# CREATE_IN_PROGRESS → CREATE_COMPLETE (15-20 minutes)
```

### Step 3.4: Verify EKS Cluster Deployment

After successful deployment, verify the cluster:

```bash
# Get cluster details
aws cloudformation describe-stacks --stack-name aura-eks-dev \
  --query 'Stacks[0].Outputs' --output table

# Expected outputs:
# - ClusterName: aura-cluster-dev
# - ClusterEndpoint: https://XXXXX.gr7.us-east-1.eks.amazonaws.com
# - ClusterArn: arn:aws:eks:us-east-1:ACCOUNT:cluster/aura-cluster-dev
# - OIDCProviderArn: arn:aws:iam::ACCOUNT:oidc-provider/...
# - NodeGroupName: aura-nodegroup-dev

# Configure kubectl
CLUSTER_NAME=$(aws cloudformation describe-stacks --stack-name aura-eks-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' --output text)

aws eks update-kubeconfig --name $CLUSTER_NAME --region us-east-1

# Verify nodes are ready
kubectl get nodes

# Expected output:
# NAME                          STATUS   ROLES    AGE   VERSION
# ip-10-0-1-xxx.ec2.internal   Ready    <none>   5m    v1.28.x
# ip-10-0-2-xxx.ec2.internal   Ready    <none>   5m    v1.28.x
```

### Phase 3 Troubleshooting

**Issue:** EKS cluster creation timeout (>30 minutes)
```bash
# Check stack events for errors
aws cloudformation describe-stack-events --stack-name aura-eks-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' --output table

# Common causes:
# - Insufficient service quotas (EKS clusters per region)
# - Subnet CIDR conflicts
# - Security group rule limits exceeded
```

**Issue:** Nodes not appearing in `kubectl get nodes`
```bash
# Check node group status
aws eks describe-nodegroup --cluster-name aura-cluster-dev \
  --nodegroup-name aura-nodegroup-dev \
  --query 'nodegroup.status' --output text

# Should be: ACTIVE

# Check EC2 instances
aws ec2 describe-instances --filters \
  "Name=tag:eks:cluster-name,Values=aura-cluster-dev" \
  --query 'Reservations[].Instances[].{ID:InstanceId,State:State.Name}' \
  --output table
```

**Issue:** kubectl connection refused
```bash
# Verify cluster endpoint accessibility
ENDPOINT=$(aws cloudformation describe-stacks --stack-name aura-eks-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterEndpoint`].OutputValue' --output text)

curl -k $ENDPOINT/healthz

# Should return: ok

# Re-configure kubectl
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1 --force
```

### Next Steps After Phase 3

Once Phase 3 is deployed, you can proceed with:
1. **Phase 4: Application Layer** - Deploy Bedrock configuration, agent workloads
2. **Phase 5: Observability Layer** - Deploy CloudWatch dashboards, Grafana, monitoring
3. **dnsmasq Deployment** - Deploy 3-tier DNS service to EKS cluster

---

## Application Environment Variables

This section documents environment variables used by Aura services. All variables have sensible defaults for local development using the `*.aura.local` service discovery pattern.

### Required Environment Variables (Production)

These variables **must** be set in production deployments:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `AWS_ACCOUNT_ID` | AWS Account ID for ARN construction | `123456789012` |
| `AWS_REGION` | AWS region for API calls | `us-east-1` |
| `ENVIRONMENT` | Deployment environment | `dev`, `qa`, `prod` |

**Note:** `AWS_ACCOUNT_ID` is automatically retrieved via STS `get_caller_identity()` if not set.

### Service Configuration Variables

These variables configure service endpoints and contact information. Defaults use `*.aura.local` for local development and service discovery.

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `SUPPORT_EMAIL` | Support contact email address | `support@aura.local` |
| `PRICING_PAGE_URL` | Pricing page URL for upgrade prompts | `https://app.aura.local/pricing` |
| `LICENSE_RENEWAL_URL` | License renewal URL | `https://app.aura.local/renew` |
| `GPU_DASHBOARD_BASE_URL` | GPU job monitoring dashboard URL | `https://app.aura.local` |

### Production Configuration Example

For production deployments, override these variables with your actual values:

```bash
# Set via Kubernetes ConfigMap
kubectl create configmap aura-service-config \
  --from-literal=SUPPORT_EMAIL=support@aenealabs.com \
  --from-literal=PRICING_PAGE_URL=https://app.aenealabs.com/pricing \
  --from-literal=LICENSE_RENEWAL_URL=https://app.aenealabs.com/renew \
  --from-literal=GPU_DASHBOARD_BASE_URL=https://app.aenealabs.com

# Or via environment file
cat > .env.prod << 'EOF'
SUPPORT_EMAIL=support@aenealabs.com
PRICING_PAGE_URL=https://app.aenealabs.com/pricing
LICENSE_RENEWAL_URL=https://app.aenealabs.com/renew
GPU_DASHBOARD_BASE_URL=https://app.aenealabs.com
EOF
```

### Kubernetes Deployment Integration

Add to your deployment manifests:

```yaml
# In deployment.yaml
spec:
  containers:
    - name: aura-api
      env:
        - name: AWS_ACCOUNT_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.annotations['eks.amazonaws.com/account-id']
        - name: SUPPORT_EMAIL
          valueFrom:
            configMapKeyRef:
              name: aura-service-config
              key: SUPPORT_EMAIL
        - name: GPU_DASHBOARD_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: aura-service-config
              key: GPU_DASHBOARD_BASE_URL
```

### Service-Specific Variables

#### Licensing Service (`src/services/licensing/`)

| Variable | Description | Default |
|----------|-------------|---------|
| `AURA_LICENSE_PUBLIC_KEY` | Ed25519 public key for offline license validation | Development key |
| `SUPPORT_EMAIL` | Contact for hardware mismatch errors | `support@aura.local` |
| `LICENSE_RENEWAL_URL` | URL for license renewal prompts | `https://app.aura.local/renew` |

#### GPU Scheduler (`src/services/gpu_scheduler/`)

| Variable | Description | Default |
|----------|-------------|---------|
| `GPU_DASHBOARD_BASE_URL` | Base URL for GPU job dashboard links in alerts | `https://app.aura.local` |

#### CLI (`src/cli/`)

| Variable | Description | Default |
|----------|-------------|---------|
| `PRICING_PAGE_URL` | Pricing page for upgrade suggestions | `https://app.aura.local/pricing` |
| `SUPPORT_EMAIL` | Contact for support ticket submission | `support@aura.local` |

#### A2A Gateway (`src/services/a2a_gateway.py`)

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPPORT_EMAIL` | Contact in error responses | `support@aura.local` |

---

## Verification & Testing

### Verify All CodeBuild Projects

```bash
# List all Aura CodeBuild projects
aws codebuild list-projects --region us-east-1 | grep aura

# Expected output:
# aura-foundation-deploy-dev
# aura-data-deploy-dev
# (aura-infra-deploy-dev - monolithic, can coexist)
```

### Verify CloudFormation Stacks

```bash
# List all Aura CloudFormation stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?starts_with(StackName, `aura`)].StackName' \
  --output table

# Expected stacks:
# - aura-codebuild-foundation-dev
# - aura-codebuild-data-dev
# - aura-networking-dev (if foundation build ran)
# - aura-security-dev (if foundation build ran)
# - aura-iam-dev (if foundation build ran)
# - aura-dynamodb-dev (if data build ran)
# - aura-s3-dev (if data build ran)
# - aura-neptune-dev (if data build ran)
# - aura-opensearch-dev (if data build ran)
```

### Test Foundation Layer Build

```bash
# Trigger Foundation build and monitor
BUILD_ID=$(aws codebuild start-build \
  --project-name aura-foundation-deploy-dev \
  --query 'build.id' \
  --output text)

echo "Build ID: $BUILD_ID"

# Check build status
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].[buildStatus,currentPhase]' \
  --output table

# Expected phases:
# SUBMITTED → QUEUED → PROVISIONING → DOWNLOAD_SOURCE → INSTALL → PRE_BUILD → BUILD → POST_BUILD → COMPLETED

# Stream logs (in separate terminal)
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow
```

### Test Data Layer Build

```bash
# Trigger Data build and monitor
BUILD_ID=$(aws codebuild start-build \
  --project-name aura-data-deploy-dev \
  --query 'build.id' \
  --output text)

echo "Build ID: $BUILD_ID"

# Check build status
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].[buildStatus,currentPhase,duration]' \
  --output table

# Stream logs
aws logs tail /aws/codebuild/aura-data-deploy-dev --follow
```

### Verify Cost Tracking

```bash
# Check CodeBuild costs (requires AWS Cost Explorer enabled)
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://<(echo '{
    "Tags": {
      "Key": "Layer",
      "Values": ["foundation", "data"]
    }
  }') \
  --group-by Type=TAG,Key=Layer

# Expected: Separate cost tracking for foundation vs. data layers
```

---

## Troubleshooting

### Issue: "AWS credentials expired"

**Error:**
```
Error: AWS credentials expired
Run: aws sso login --profile <your-aws-profile>
```

**Solution:**
```bash
# Refresh AWS SSO credentials (use your configured profile with AdministratorAccess)
aws sso login --profile <your-aws-profile>

# Verify
aws sts get-caller-identity
```

---

### Issue: "Parameter /aura/dev/alert-email not found"

**Error:**
```
Parameter /aura/dev/alert-email not found
```

**Solution:**
```bash
# Create Parameter Store parameter
aws ssm put-parameter \
  --name "/aura/dev/alert-email" \
  --value "your-email@example.com" \
  --type String \
  --region us-east-1

# Or let the deployment script prompt you (recommended)
```

---

### Issue: "Secret aura/dev/neptune not found"

**Error during Data Layer build:**
```
GATE 0: ERROR: Missing secret: aura/dev/neptune
```

**Solution:**
```bash
# Create Neptune secret
aws secretsmanager create-secret \
  --name aura/dev/neptune \
  --secret-string '{"password":"TempPassword123!ChangeMe"}' \
  --region us-east-1

# Create OpenSearch secret
aws secretsmanager create-secret \
  --name aura/dev/opensearch \
  --secret-string '{"password":"TempPassword123!ChangeMe"}' \
  --region us-east-1

# Retry Data Layer build
./trigger-data-build.sh dev
```

---

### Issue: "Prerequisite stack not ready"

**Error during Data Layer build:**
```
GATE 1: ERROR: Prerequisite stack aura-networking-dev not ready (status: NOT_FOUND)
Deploy Foundation Layer first
```

**Solution:**
```bash
# Trigger Foundation Layer build first
./trigger-foundation-build.sh dev

# Wait for completion (5-7 minutes)
# Then trigger Data Layer build
./trigger-data-build.sh dev
```

---

### Issue: "CloudFormation stack already exists in ROLLBACK_COMPLETE"

**Error:**
```
Stack aura-neptune-dev already exists in ROLLBACK_COMPLETE state
```

**Note:** As of Nov 26, 2025, buildspecs automatically handle ROLLBACK_COMPLETE states by deleting and recreating stacks. Manual intervention is only needed if the buildspec itself fails.

**Solution (if manual intervention needed):**
```bash
# Delete the failed stack
aws cloudformation delete-stack \
  --stack-name aura-neptune-dev \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name aura-neptune-dev

# Retry Data Layer build
./trigger-data-build.sh dev
```

---

### Issue: Build fails with "InternalFailure" (Neptune)

**Error:**
```
Resource handler returned message: "null" (InternalFailure)
Resource: NeptuneParameterGroup
```

**Cause:** Transient AWS Neptune API failure (20% of current failures)

**Solution:**
```bash
# Wait 5 minutes and retry
sleep 300

# Delete failed stack
aws cloudformation delete-stack --stack-name aura-neptune-dev

# Retry build (buildspec will auto-retry up to 3 times in future)
./trigger-data-build.sh dev
```

---

### Issue: "logs:TagResource permission denied"

**Error:**
```
User is not authorized to perform: logs:TagResource
```

**Cause:** This was fixed in the recent commit (codebuild.yaml lines 140-144)

**Solution:**
```bash
# Update the CodeBuild stack with fixed permissions
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM

# Or redeploy Foundation/Data CodeBuild (already has fix)
./deploy-foundation-codebuild.sh dev
```

---

### Issue: WAFv2 Logging Permission Denied

**Error:**
```
You don't have the permissions that are required to perform this operation.
(Service: Wafv2, Status Code: 400, Error Code: WAFInvalidOperationException)
Resource: WAFLoggingConfiguration
```

**Cause:** WAFv2 logging requires multiple permission layers:
1. IAM permissions for `wafv2:PutLoggingConfiguration`
2. CloudWatch Logs delivery permissions (`logs:CreateLogDelivery`, etc.)
3. CloudWatch Logs resource policy allowing `delivery.logs.amazonaws.com`
4. Service-linked role for `wafv2.amazonaws.com`

**Note:** As of Nov 26, 2025, these permissions are already configured in:
- `deploy/cloudformation/codebuild-foundation.yaml` (IAM permissions)
- `deploy/cloudformation/security.yaml` (CloudWatch Logs resource policy)

**Solution (if issue recurs):**
1. Ensure CodeBuild IAM role has CloudWatch Logs delivery permissions:
```yaml
# In codebuild-foundation.yaml IAM policy
- Effect: Allow
  Action:
    - logs:CreateLogDelivery
    - logs:GetLogDelivery
    - logs:UpdateLogDelivery
    - logs:DeleteLogDelivery
    - logs:ListLogDeliveries
  Resource: '*'
```

2. Ensure security.yaml has CloudWatch Logs resource policy:
```yaml
WAFLogResourcePolicy:
  Type: AWS::Logs::ResourcePolicy
  Properties:
    PolicyDocument: |
      {
        "Statement": [{
          "Principal": {"Service": "delivery.logs.amazonaws.com"},
          "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
          "Resource": "arn:aws:logs:REGION:ACCOUNT:log-group:aws-waf-logs-*:*"
        }]
      }
```

3. Redeploy Foundation Layer:
```bash
./trigger-foundation-build.sh dev
```

---

## Phase 6: API Deployment to EKS

This section covers deploying the Aura FastAPI application to the EKS cluster. Per [ADR-011](docs/architecture-decisions/ADR-011-vpc-access-via-eks-deployment.md), we use EKS deployment for secure VPC resource access instead of bastion hosts.

### Prerequisites

- Phase 3 (EKS) deployed and accessible
- ECR repository for `aura-api` image
- kubectl configured for EKS cluster

### Step 1: Configure kubectl

```bash
# Update kubeconfig for EKS cluster
aws eks update-kubeconfig \
  --name aura-cluster-dev \
  --region us-east-1 \
  --profile aura-admin

# Verify access
kubectl get nodes
```

### Step 2: Create ECR Repository (if not exists)

```bash
# Create ECR repository for API
aws ecr create-repository \
  --repository-name aura-api \
  --region us-east-1

# Get ECR login (Podman-first per ADR-049)
aws ecr get-login-password --region us-east-1 | \
  podman login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com
```

### Step 3: Build and Push Container Image

Per ADR-049, use Podman for local development. Docker is available as CI/CD fallback.

```bash
# From repository root
cd /path/to/aura

# Login to ECR (works with both Podman and Docker)
aws ecr get-login-password --region us-east-1 | \
  podman login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build the API image (Podman-first, add --platform for Apple Silicon)
podman build --platform linux/amd64 -t aura-api:latest \
  -f deploy/docker/api/Dockerfile.api .

# Tag for ECR
podman tag aura-api:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest

# Push to ECR
podman push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest
```

**CI/CD Note:** CodeBuild uses Docker (not Podman) for container builds. The buildspecs use `docker build` commands which work in the CodeBuild environment.

### Step 4: Deploy to EKS

```bash
# Deploy using environment-specific overlay (dev/qa/prod)
kubectl apply -k deploy/kubernetes/aura-api/overlays/dev/

# Verify deployment
kubectl get pods -l app=aura-api
kubectl get svc aura-api

# Check logs
kubectl logs -f deployment/aura-api
```

**Note:** Always use environment-specific overlays for deployments. The root `kustomization.yaml` references the base directory and does not include environment-specific values (AWS account ID, image tags, etc.).

### Step 5: Access API Locally via Port Forward

```bash
# Port forward to localhost (runs in foreground)
kubectl port-forward svc/aura-api 8080:8080

# In another terminal, test the API
curl http://localhost:8080/health
curl http://localhost:8080/health/detailed

# View connection status
curl http://localhost:8080/ | jq
```

### Verification Checklist

- [ ] Pods running: `kubectl get pods -l app=aura-api`
- [ ] Service created: `kubectl get svc aura-api`
- [ ] Health check passing: `curl localhost:8080/health`
- [ ] Database connections: Check `/health/detailed` for mode status

### Multi-Environment Deployment Note (Jan 2026)

For QA/PROD deployments, the k8s-deploy buildspec includes automatic image account validation (PR #275). This prevents cross-account ECR image pull errors by validating that overlay kustomization.yaml files reference the correct AWS account ID before deployment.

If you see "FATAL: Image account validation failed", regenerate configs with:

```bash
./deploy/scripts/generate-k8s-config.sh qa us-east-1  # or prod us-gov-west-1
```

See `docs/deployment/CICD_SETUP_GUIDE.md#k8s-deploy-image-account-validation-pr-275` for details.

### Troubleshooting

**Pod not starting:**
```bash
kubectl describe pod -l app=aura-api
kubectl logs -l app=aura-api --previous
```

**Image pull errors:**
```bash
# Verify ECR authentication (Podman-first per ADR-049)
aws ecr get-login-password --region us-east-1 | \
  podman login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Check image exists
aws ecr describe-images --repository-name aura-api
```

**Restart deployment:**
```bash
kubectl rollout restart deployment/aura-api
kubectl rollout status deployment/aura-api
```

---

## Phase 7: Agent Orchestrator Deployment (Warm Pool)

**Status:** DEPLOYED
**CodeBuild Project:** `aura-application-deploy-dev`
**Deployment Time:** ~5 minutes

### Overview

The Agent Orchestrator uses a hybrid warm pool architecture - an HTTP server with SQS queue consumer that provides zero cold start at ~85% cost savings compared to always-on deployment.

**Architecture:**
1. HTTP server provides health endpoints for K8s probes
2. Background task polls SQS for orchestration jobs
3. System2Orchestrator processes jobs (Coder, Reviewer, Validator agents)
4. Results stored in DynamoDB with optional webhook callback

### Prerequisites

Before deploying the Agent Orchestrator, verify:

```bash
# Verify Phase 3 (Compute/EKS) is deployed
aws cloudformation describe-stacks --stack-name aura-eks-dev --query 'Stacks[0].StackStatus'
# Expected: CREATE_COMPLETE or UPDATE_COMPLETE

# Verify IRSA role with SQS permissions
aws cloudformation describe-stacks --stack-name aura-irsa-aura-api-dev --query 'Stacks[0].StackStatus'
# Expected: CREATE_COMPLETE or UPDATE_COMPLETE

# Verify SQS queue exists
aws sqs get-queue-url --queue-name aura-orchestrator-tasks-dev
# Expected: QueueUrl returned

# Verify DynamoDB table exists
aws dynamodb describe-table --table-name aura-orchestrator-jobs-dev --query 'Table.TableStatus'
# Expected: ACTIVE
```

### Step 7.1: Build and Push Container Image

Per ADR-049, use Podman for local development. Docker is available as CI/CD fallback.

```bash
# From repository root
cd /path/to/project-aura

# Get ECR login (Podman-first per ADR-049)
aws ecr get-login-password --region us-east-1 | \
  podman login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build the orchestrator image (uses HTTP server mode by default)
podman build --platform linux/amd64 \
  -t aura-agent-orchestrator:latest \
  -f deploy/docker/agents/Dockerfile.orchestrator .

# Tag for ECR
podman tag aura-agent-orchestrator:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-agent-orchestrator-dev:latest

# Push to ECR
podman push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-agent-orchestrator-dev:latest
```

**CI/CD Note:** CodeBuild uses Docker for container builds. The buildspecs use `docker build` commands which work in the CodeBuild environment.

### Step 7.2: Deploy to EKS with Kustomize

```bash
# Deploy using environment-specific overlay (dev/qa/prod)
kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/dev/

# Verify deployment
kubectl get pods -l app=agent-orchestrator
kubectl get svc agent-orchestrator
```

### Step 7.3: Verify Deployment

```bash
# Check pod status
kubectl get pods -l app=agent-orchestrator -o wide

# Expected output:
# NAME                                 READY   STATUS    RESTARTS   AGE
# agent-orchestrator-xxx-yyy           1/1     Running   0          2m

# Check health endpoints via port forward
kubectl port-forward svc/agent-orchestrator 8081:8080

# In another terminal:
curl http://localhost:8081/health/live    # Liveness probe
curl http://localhost:8081/health/ready   # Readiness probe (queue consumer active)
curl http://localhost:8081/metrics        # Prometheus metrics
curl http://localhost:8081/status         # Current job processing status
```

### Step 7.4: Test Job Submission

```bash
# Submit a test job via the API (requires authentication)
curl -X POST https://api.aenealabs.com/api/v1/orchestrate \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze the authentication module for security vulnerabilities",
    "priority": "NORMAL",
    "metadata": {"test": true}
  }'

# Expected response:
# {
#   "job_id": "job-xxxxxxxxxxxx",
#   "task_id": "task-xxxxxxxx",
#   "status": "QUEUED",
#   "message": "Job queued for processing...",
#   "poll_url": "/api/v1/orchestrate/job-xxxxxxxxxxxx",
#   "websocket_url": "/api/v1/orchestrate/job-xxxxxxxxxxxx/stream"
# }
```

### Health Endpoints Reference

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health/live` | K8s liveness probe | `{"status": "healthy", ...}` |
| `/health/ready` | K8s readiness probe (queue consumer active) | `{"status": "ready", ...}` |
| `/health/startup` | K8s startup probe | `{"status": "started", ...}` |
| `/status` | Current job processing status | `{"processing": false, ...}` |
| `/metrics` | Prometheus-compatible metrics | Text format metrics |

### ConfigMap Configuration

The orchestrator configuration is managed via ConfigMap (no hardcoded values):

```yaml
# deploy/kubernetes/agent-orchestrator/base/configmap.yaml
data:
  PROJECT_NAME: "aura"
  USE_MOCK_LLM: "false"
  ENABLE_MCP: "false"
  ENABLE_TITAN_MEMORY: "false"
  SQS_POLL_INTERVAL: "5"       # seconds between SQS polls
  SQS_VISIBILITY_TIMEOUT: "1800" # 30 minutes job timeout
  LOG_LEVEL: "INFO"
  PORT: "8080"
```

Environment-specific values (AWS_ACCOUNT_ID, AWS_REGION, SQS_QUEUE_URL) are set via Kustomize overlays in `deploy/kubernetes/agent-orchestrator/overlays/{env}/`.

### Troubleshooting

**Pod not starting:**
```bash
kubectl describe pod -l app=agent-orchestrator
kubectl logs -l app=agent-orchestrator --previous
```

**Queue consumer not active:**
```bash
# Check readiness probe
kubectl port-forward svc/agent-orchestrator 8081:8080
curl http://localhost:8081/health/ready
# If status != "ready", check logs for SQS connection errors
```

**Jobs not being processed:**
```bash
# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/aura-orchestrator-tasks-dev \
  --attribute-names ApproximateNumberOfMessages

# Check DynamoDB for job status
aws dynamodb get-item \
  --table-name aura-orchestrator-jobs-dev \
  --key '{"job_id": {"S": "job-xxxxxxxxxxxx"}}'
```

**Restart deployment:**
```bash
kubectl rollout restart deployment/agent-orchestrator
kubectl rollout status deployment/agent-orchestrator
```

---

## Orchestrator Deployment Mode Configuration

**Status:** Implemented (December 15, 2025)

The Agent Orchestrator supports three configurable deployment modes that can be managed via API or UI. This section covers configuration and operational procedures.

### Available Deployment Modes

| Mode | Monthly Cost | Cold Start | Recommended For |
|------|--------------|------------|-----------------|
| **On-Demand** | Lowest | ~30 seconds | Dev/test, <100 jobs/day |
| **Warm Pool** | Low | 0 seconds | Production, >500 jobs/day |
| **Hybrid** | Low + burst | 0 seconds | Variable workloads |

### Viewing Current Mode

```bash
# Via API
curl -H "Authorization: Bearer $JWT_TOKEN" \
  https://api.aenealabs.com/api/v1/orchestrator/settings

# Expected response includes:
# {
#   "effective_mode": "on_demand",
#   "warm_pool_enabled": false,
#   "hybrid_mode_enabled": false,
#   ...
# }
```

### Switching Deployment Modes

**Important:** Mode changes have a 5-minute cooldown to prevent thrashing.

```bash
# Switch to warm pool mode
curl -X POST -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_mode": "warm_pool", "reason": "Enabling for production launch"}' \
  https://api.aenealabs.com/api/v1/orchestrator/settings/switch

# Switch to hybrid mode
curl -X POST -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_mode": "hybrid", "reason": "Need burst capacity for launch"}' \
  https://api.aenealabs.com/api/v1/orchestrator/settings/switch

# Force switch during cooldown (admin only, logged)
curl -X POST -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_mode": "on_demand", "force": true, "reason": "Emergency rollback"}' \
  https://api.aenealabs.com/api/v1/orchestrator/settings/switch
```

### Configuring Per-Organization Overrides

Organizations can have different deployment modes than the platform default:

```bash
# Set org-specific warm pool mode
curl -X PUT -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"warm_pool_enabled": true, "warm_pool_replicas": 2}' \
  "https://api.aenealabs.com/api/v1/orchestrator/settings?organization_id=org-enterprise-123"
```

### Verifying Mode Status

```bash
# Check operational status
curl -H "Authorization: Bearer $JWT_TOKEN" \
  https://api.aenealabs.com/api/v1/orchestrator/settings/status

# Expected response:
# {
#   "current_mode": "warm_pool",
#   "warm_pool_replicas_desired": 1,
#   "warm_pool_replicas_ready": 1,
#   "queue_depth": 0,
#   "can_switch_mode": true,
#   "cooldown_remaining_seconds": 0
# }
```

### Verifying Kubernetes RBAC

The API service needs RBAC permissions to scale the warm pool:

```bash
# Verify RBAC is applied
kubectl get role orchestrator-scaler -o yaml
kubectl get rolebinding orchestrator-scaler-binding -o yaml

# Test permissions
kubectl auth can-i patch deployments/scale \
  --as=system:serviceaccount:default:aura-api

# Expected: yes
```

### Monitoring Mode Changes

Mode changes are logged to CloudWatch and tracked via metrics:

```bash
# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace "Aura/Orchestrator" \
  --metric-name "OrchestratorModeChange" \
  --dimensions Name=EventType,Value=mode_switched \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum
```

### Mode Configuration Best Practices

1. **Start with On-Demand:** New deployments should start with on-demand mode to understand traffic patterns
2. **Monitor Job Volume:** Track daily job counts before switching modes
3. **Use Hybrid for Variable Traffic:** If experiencing traffic spikes, hybrid provides burst capacity
4. **Test Mode Switches in Dev:** Always test mode transitions in dev environment first
5. **Schedule Changes During Low Traffic:** Mode transitions are safest during low-traffic periods

### Troubleshooting Mode Switches

**Issue:** Mode switch returns HTTP 429

```bash
# Check cooldown status
curl -H "Authorization: Bearer $JWT_TOKEN" \
  https://api.aenealabs.com/api/v1/orchestrator/settings/status | jq '.cooldown_remaining_seconds'

# Wait for cooldown or use force (admin only)
```

**Issue:** Warm pool not scaling

```bash
# Check deployment status
kubectl describe deployment agent-orchestrator-warm-pool

# Check RBAC
kubectl auth can-i patch deployments/scale \
  --as=system:serviceaccount:default:aura-api

# Check events
kubectl get events --sort-by='.lastTimestamp' | grep orchestrator
```

**Full Documentation:** See [docs/features/ORCHESTRATOR_MODES.md](../features/ORCHESTRATOR_MODES.md)

---

## Container Build Best Practices

All Debian-based Dockerfiles in Project Aura follow standardized patterns for clean CI/CD builds. These practices apply to both Podman (local development) and Docker (CI/CD in CodeBuild) builds, eliminating noisy log warnings and improving pipeline reliability.

**Container Runtime Strategy (ADR-049):**
- **Local Development:** Podman (primary) - rootless, daemonless, no licensing required
- **CI/CD Pipelines:** Docker (CodeBuild) - native AWS integration

### Key Standards

1. **DEBIAN_FRONTEND=noninteractive** - Suppresses debconf fallback warnings during `apt-get install`
2. **pip --no-warn-script-location** - Suppresses PATH warnings when installing Python packages
3. **PATH configuration** - Ensures pip-installed scripts are executable

### Quick Reference

```dockerfile
# Builder stage pattern
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_ROOT_USER_ACTION=ignore \
    PIP_NO_CACHE_DIR=true \
    PATH=/root/.local/bin:$PATH

RUN pip install --no-cache-dir --user --no-warn-script-location -r requirements.txt
```

### Updated Dockerfiles

| Dockerfile | Service |
|------------|---------|
| `deploy/docker/api/Dockerfile.api` | FastAPI application |
| `deploy/docker/agents/Dockerfile.agent` | Generic agent image |
| `deploy/docker/agents/Dockerfile.orchestrator` | Agent orchestrator |
| `deploy/docker/agents/Dockerfile.runtime-incident` | Runtime incident agent |
| `deploy/docker/memory-service/Dockerfile.memory-service-cpu` | Memory service (CPU) |
| `deploy/docker/sandbox/Dockerfile` | Sandbox environment |
| `deploy/docker/sandbox/Dockerfile.test-runner` | Sandbox test runner |

**Note:** Alpine-based (`Dockerfile.alpine`) and Node.js-based (`Dockerfile.frontend`) images use different package managers and do not require these settings.

**Full Documentation:** See [DOCKER_BEST_PRACTICES.md](DOCKER_BEST_PRACTICES.md) for complete patterns, templates, and verification commands.

---

## Rollback Procedures

### Rollback Foundation Layer CodeBuild

```bash
# Delete Foundation CodeBuild stack
aws cloudformation delete-stack \
  --stack-name aura-codebuild-foundation-dev \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name aura-codebuild-foundation-dev

# Delete S3 artifact bucket (if needed)
BUCKET=$(aws s3 ls | grep aura-foundation-artifacts | awk '{print $3}')
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET
```

### Rollback Data Layer CodeBuild

```bash
# Delete Data CodeBuild stack
aws cloudformation delete-stack \
  --stack-name aura-codebuild-data-dev \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name aura-codebuild-data-dev

# Delete S3 artifact bucket (if needed)
BUCKET=$(aws s3 ls | grep aura-data-artifacts | awk '{print $3}')
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET
```

### Rollback Infrastructure Stacks (Foundation Layer)

```bash
# Delete in reverse dependency order
aws cloudformation delete-stack --stack-name aura-security-dev
aws cloudformation delete-stack --stack-name aura-iam-dev
aws cloudformation delete-stack --stack-name aura-networking-dev

# Wait for deletions
for stack in aura-security-dev aura-iam-dev aura-networking-dev; do
  aws cloudformation wait stack-delete-complete --stack-name $stack
done
```

### Rollback Infrastructure Stacks (Data Layer)

```bash
# Delete in reverse dependency order
aws cloudformation delete-stack --stack-name aura-opensearch-dev
aws cloudformation delete-stack --stack-name aura-neptune-dev
aws cloudformation delete-stack --stack-name aura-s3-dev
aws cloudformation delete-stack --stack-name aura-dynamodb-dev

# Wait for deletions (Neptune takes ~10 minutes)
for stack in aura-opensearch-dev aura-neptune-dev aura-s3-dev aura-dynamodb-dev; do
  aws cloudformation wait stack-delete-complete --stack-name $stack
done
```

---

## Next Steps

### Short-Term (This Week)

1. **Monitor Build Success Rates**
   ```bash
   # Check build history
   aws codebuild list-builds-for-project \
     --project-name aura-foundation-deploy-dev \
     --max-items 10

   # Target: >90% success rate
   ```

2. **Rotate Secrets**
   ```bash
   # Change temporary passwords to secure ones
   aws secretsmanager update-secret \
     --secret-id aura/dev/neptune \
     --secret-string '{"password":"YOUR_SECURE_PASSWORD"}'

   aws secretsmanager update-secret \
     --secret-id aura/dev/opensearch \
     --secret-string '{"password":"YOUR_SECURE_PASSWORD"}'
   ```

3. **Set Up CloudWatch Dashboards**
   - Review `MODULAR_CICD_IMPLEMENTATION.md` → "Metrics Dashboard" section
   - Create dashboard for Foundation and Data layer metrics

### Medium-Term (Next 2 Weeks)

4. **Implement Remaining Layers**
   - Compute Layer (EKS, EC2 Node Groups)
   - Application Layer (Agent pods, services)
   - Observability Layer (CloudWatch, Prometheus)

5. **Step Functions Orchestration**
   - Automate dependency management
   - Enable parallel builds (Foundation + Observability)
   - Add automatic rollback logic

6. **Team Onboarding**
   - Data Team: Owns `aura-data-deploy-dev`
   - Platform Team: Owns `aura-foundation-deploy-dev` + `aura-compute-deploy-dev`
   - SRE Team: Owns `aura-observability-deploy-dev`

### Long-Term (Next Month)

7. **Migrate from Monolithic**
   - Run modular + monolithic in parallel for 1 week
   - Compare success rates, duration, costs
   - Deprecate monolithic pipeline once modular is stable

8. **Advanced Features**
   - Blue/Green deployments per layer
   - Canary deployments (1 region → all regions)
   - Carbon-aware scheduling (deploy during renewable energy peaks)

---

## Cost Estimates

### CodeBuild Costs (Dev Environment)

| Layer | Compute Size | Avg Duration | Builds/Month | Cost/Month |
|-------|-------------|--------------|--------------|------------|
| **Foundation** | SMALL (3 GB) | 5 min | 5 | $0.62 |
| **Data** | MEDIUM (7 GB) | 20 min | 20 | $10.00 |
| **Total** | - | - | 25 | **$10.62** |

**Comparison with Monolithic:**
- Monolithic: 32 builds/month × 15 min × $0.005/min = $2.40 (but 47% fail)
- Modular: 25 builds/month × avg 12 min × $0.005/min = $1.50 (target: 90% success)
- **Savings:** Reduced wasted compute from failures

### Infrastructure Costs (After Deployment)

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| **VPC** | $0 | No NAT Gateway (using VPC endpoints) |
| **Neptune (db.t3.medium)** | $81.76 | Always-on graph database |
| **OpenSearch (t3.small.search)** | $25.92 | Vector search |
| **DynamoDB (on-demand)** | ~$5 | Pay per request |
| **S3** | ~$2 | Artifacts + data |
| **Total Infrastructure** | **~$115/month** | Dev environment |

---

## Support & Resources

### Documentation

- **Architecture Assessment:** `AWS_WELL_ARCHITECTED_CICD_ASSESSMENT.md` (1,000+ lines)
- **Security Audit:** `SECURITY_CICD_ANALYSIS.md` (350+ lines)
- **Implementation Guide:** `MODULAR_CICD_IMPLEMENTATION.md` (500+ lines)
- **This Guide:** `DEPLOYMENT_GUIDE.md`

### Monitoring

- **CloudWatch Logs:**
  - Foundation: `/aws/codebuild/aura-foundation-deploy-dev`
  - Data: `/aws/codebuild/aura-data-deploy-dev`

- **CloudWatch Alarms:**
  - `aura-foundation-build-failures-dev`
  - `aura-foundation-build-slow-dev`
  - `aura-data-build-failures-dev`
  - `aura-data-build-slow-dev`
  - `aura-data-layer-cost-exceeded-dev`

### Git Repository

```bash
# View recent commits
git log --oneline -5

# Expected:
# fa97df0 feat: implement Data Layer modular CodeBuild (Phase 2)
# e4347b9 feat: implement modular CI/CD architecture and security hardening (Phase 1)
```

---

## Phase 7.2-7.3: SSR Training Infrastructure

**Status:** DEPLOYED (January 2, 2026)
**CodeBuild Project:** `aura-ssr-deploy-dev`
**Deployment Time:** ~10-15 minutes

### Overview

SSR (Self-Play SWE-RL) training infrastructure enables continuous self-improvement of Aura's autonomous agents through self-play reinforcement learning, based on Meta FAIR research (arXiv:2512.18552).

**What Gets Deployed:**

**Layer 7.2 - SSR Training (ssr-training.yaml):**
- KMS Key with automatic rotation
- S3 Bucket for training artifacts (TLS enforced, 90-day lifecycle)
- DynamoDB Table for training state (with GSIs for repository and status queries)
- IAM Role for SSR service

**Layer 7.3 - SSR Training Pipeline (ssr-training-pipeline.yaml):**
- ECS Fargate Spot Cluster (4:1 Spot weight for cost savings)
- ECR Repositories for bug injection and solving containers
- Step Functions Workflow for training orchestration
- SNS Topic for training notifications
- CloudWatch Alarms for monitoring
- AWS Budgets for cost control

### Prerequisites

Before deploying SSR infrastructure, verify Phase 7 (Sandbox) is deployed:

```bash
# Verify Sandbox stacks exist
aws cloudformation describe-stacks --stack-name aura-sandbox-dev --query 'Stacks[0].StackStatus'
aws cloudformation describe-stacks --stack-name aura-hitl-workflow-dev --query 'Stacks[0].StackStatus'
# Both should return: CREATE_COMPLETE or UPDATE_COMPLETE
```

### Trigger SSR Deployment

```bash
# Deploy SSR infrastructure via CodeBuild
aws codebuild start-build --project-name aura-ssr-deploy-dev --region us-east-1
```

### Verify SSR Deployment

```bash
# Check CloudFormation stacks
for STACK in aura-ssr-training-dev aura-ssr-training-pipeline-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done

# Verify S3 bucket
aws s3 ls | grep ssr-training

# Verify DynamoDB table
aws dynamodb describe-table --table-name aura-ssr-training-state-dev \
  --query 'Table.TableStatus'

# Verify ECS cluster
aws ecs describe-clusters --clusters aura-ssr-training-dev \
  --query 'clusters[0].status'

# Verify Step Functions workflow
aws stepfunctions list-state-machines \
  --query 'stateMachines[?contains(name, `ssr-training`)].name'
```

### Integration Tests

The SSR infrastructure includes integration tests that validate:

1. **Health Check** - S3 + DynamoDB connectivity
2. **Artifact CRUD** - Create, retrieve, update, delete operations
3. **KMS Encryption** - S3 uploads require KMS encryption
4. **DynamoDB Decimal Conversion** - Float to Decimal handling for validation scores
5. **Validation Pipeline** - 7-stage validation flow

Run integration tests:

```bash
# From repository root
pytest tests/integration/test_ssr_integration.py -v
```

### Troubleshooting

**Issue: S3 Upload AccessDenied**

The SSR S3 bucket enforces KMS encryption. Ensure uploads include the correct KMS key:

```python
s3_client.put_object(
    Bucket='aura-ssr-training-ACCOUNT-dev',
    Key='artifacts/...',
    Body=data,
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId='alias/aura-ssr-training-dev'
)
```

**Issue: DynamoDB ValidationException for Float values**

DynamoDB does not accept Python floats. Use the `_convert_floats_to_decimal()` helper in `artifact_storage_service.py`:

```python
from decimal import Decimal

def _convert_floats_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj
```

### Related Documentation

- [ADR-050: Self-Play SWE-RL Integration](../architecture-decisions/ADR-050-self-play-swe-rl-integration.md)
- [LAYER7_SANDBOX_RUNBOOK.md](../runbooks/LAYER7_SANDBOX_RUNBOOK.md)

---

**Deployment Guide Version:** 1.9
**Last Updated:** January 17, 2026
**Maintainer:** Project Aura DevOps Team

**Questions or Issues?** Reference the troubleshooting section above or review the comprehensive documentation in the repository.
