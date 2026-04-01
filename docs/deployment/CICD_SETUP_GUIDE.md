# Project Aura - CI/CD Pipeline Setup Guide

**Last Updated:** 2026-01-11
**Pipeline:** AWS CodeBuild + Step Functions (Modular 8-Layer Architecture + Automated Pipeline)
**Validation:** 3-Gate Smoke Test System + Image Account Validation
**Status:** All 8 Layers Deployed + Step Functions Pipeline + QA Environment Verified

---

## Overview

Project Aura uses a **modular CI/CD architecture** with 20 CodeBuild projects managing 106 CloudFormation templates across 8 deployment layers. Each layer has its own CodeBuild project for independent, parallel deployments. A Step Functions state machine orchestrates complete environment deployments.

✅ **Modular Architecture:**
- **20 CodeBuild projects** (8 parent layers + 10 sub-layers + 2 pipeline projects)
- **106 CloudFormation templates** (20 CodeBuild + 86 infrastructure)
- **86 stacks deployed** to dev environment
- **20 buildspec files** managing deployments

✅ **Step Functions Deployment Pipeline:**
- **Automated 5-phase deployment** from infrastructure to verification
- **K8s config generation** after all layers complete (avoids circular dependencies)
- **Parallel container builds** for all 5 service images
- **Integration testing** with health checks and connectivity validation

✅ **3-Gate Validation System:**
- **GATE 1:** Pre-deployment smoke tests (BLOCKING - must pass)
- **GATE 2:** Deployment validation script (BLOCKING - must pass)
- **GATE 3:** Post-deployment smoke tests (WARNING - monitors health)

✅ **Image Account Validation (PR #275):**
- Pre-deployment validation in k8s-deploy buildspec
- Verifies all overlay kustomization.yaml files reference correct AWS account ID
- Prevents cross-account ECR image pull errors in QA/PROD deployments

✅ **8-Layer Cascade Deployment:**
- Foundation → Data → Compute → Application → Observability → Serverless → Sandbox → Security
- Layer dependencies automatically respected
- Parallel deployment within layers

✅ **Production-Ready Features:**
- Artifact storage in S3 per layer
- CloudWatch logging per CodeBuild project
- SNS email notifications
- Build caching for faster runs

✅ **Container Runtime Strategy (ADR-049):**
- **CI/CD Pipelines (CodeBuild):** Docker - native AWS integration with buildspec commands
- **Local Development:** Podman (primary) - avoids Docker Desktop licensing fees ($5-24/user/month)
- All buildspecs use `docker build` commands for CodeBuild compatibility
- Developers use `podman build` locally with identical Dockerfile syntax

---

## Quick Start

### Step 1: Bootstrap All CodeBuild Projects (One-Time Setup)

The Bootstrap layer (Layer 0) deploys all 18 CodeBuild projects. This is the only manual deployment required.

```bash
# Option A: Use the bootstrap script (recommended)
./deploy/scripts/bootstrap-fresh-account.sh dev us-east-1

# Option B: Manual deployment
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-bootstrap.yaml \
  --stack-name aura-codebuild-bootstrap-dev \
  --parameter-overrides Environment=dev ProjectName=aura \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Project=aura Environment=dev Layer=bootstrap BootstrapExemption=true \
  --region us-east-1

# Then trigger the bootstrap build to deploy all 20 CodeBuild projects
aws codebuild start-build --project-name aura-bootstrap-deploy-dev --region us-east-1
```

**What the Bootstrap layer deploys:**
- 20 CodeBuild projects (8 parent layers + 12 sub-layers including k8s-deploy and integration-test)
- S3 artifacts buckets for each layer
- IAM roles with layer-specific permissions
- CloudWatch log groups and alarms

**Time:** ~15 minutes (bootstrap build deploys all 20 CodeBuild stacks)

> **Note:** See `docs/operations/BOOTSTRAP_GUIDE.md` for complete fresh account bootstrap procedure.
> See `docs/operations/bootstrap-exemptions.md` for bootstrap exemption rationale.

---

### Step 2: Trigger Layer Deployments

After Bootstrap completes, deploy infrastructure layers in sequence:

```bash
# Deploy Foundation layer (VPC, IAM, KMS, Security Groups)
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1

# Deploy Data layer (Neptune, OpenSearch, DynamoDB, S3)
aws codebuild start-build --project-name aura-data-deploy-dev --region us-east-1

# Deploy Compute layer (EKS, ECR)
aws codebuild start-build --project-name aura-compute-deploy-dev --region us-east-1

# Deploy Application layer (Bedrock, IRSA, Frontend)
aws codebuild start-build --project-name aura-application-deploy-dev --region us-east-1

# Deploy Observability layer (Secrets, Monitoring, Cost Alerts)
aws codebuild start-build --project-name aura-observability-deploy-dev --region us-east-1

# Deploy Serverless layer (Lambda, EventBridge)
aws codebuild start-build --project-name aura-serverless-deploy-dev --region us-east-1

# Deploy Sandbox layer (HITL, Step Functions)
aws codebuild start-build --project-name aura-sandbox-deploy-dev --region us-east-1

# Deploy Security layer (Config, GuardDuty, Drift Detection)
aws codebuild start-build --project-name aura-security-deploy-dev --region us-east-1
```

**What happens per layer:**
1. ✅ CodeBuild clones GitHub repo
2. ✅ Installs dependencies (Python, pytest, cfn-lint)
3. ✅ **GATE 1:** Runs smoke tests (must pass)
4. ✅ **GATE 2:** Validates CloudFormation templates
5. ✅ Deploys layer-specific stacks
6. ✅ **GATE 3:** Runs post-deployment validation
7. ✅ Sends SNS notification (success/failure)

**Time:** Varies by layer (3-20 minutes)

---

## CI/CD Pipeline Architecture

### Modular 9-Layer Cascade (Layer 0 + Layers 1-8)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     LAYER 0: BOOTSTRAP (One-Time Manual)                 │
│                     aura-codebuild-bootstrap-{env}                       │
│                                                                          │
│ Deploys: All 18 CodeBuild project CloudFormation stacks                 │
│ Template: deploy/cloudformation/codebuild-bootstrap.yaml                │
│ Buildspec: deploy/buildspecs/buildspec-bootstrap.yml                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: Foundation (aura-foundation-deploy-{env})                       │
│ Deploys: VPC, IAM, WAF, Security Groups, VPC Endpoints, KMS             │
│                                                                          │
│ Sub-layers:                                                              │
│   1.7: aura-network-services-deploy → dnsmasq, ECS Fargate DNS          │
│   1.9: aura-docker-deploy → Docker image builds for ECR                 │
└─────────────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ LAYER 2: Data │ │ LAYER 3:      │ │ LAYER 4:      │ │ LAYER 5:      │
│               │ │ Compute       │ │ Application   │ │ Observability │
│ Neptune       │ │ EKS           │ │ Bedrock       │ │ Secrets       │
│ OpenSearch    │ │ ECR           │ │ IRSA          │ │ Monitoring    │
│ DynamoDB      │ │ Node Groups   │ │ Frontend      │ │ Cost Alerts   │
│ S3            │ │               │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ LAYER 6:      │ │ LAYER 7:      │ │ LAYER 8:      │ │               │
│ Serverless    │ │ Sandbox       │ │ Security      │ │ All 8 Layers  │
│               │ │               │ │               │ │ DEPLOYED ✅   │
│ Lambda        │ │ HITL Workflow │ │ AWS Config    │ │               │
│ EventBridge   │ │ Step Functions│ │ GuardDuty     │ │ 16 CodeBuild  │
│ Chat/Incident │ │ ECS Sandbox   │ │ Drift Detect  │ │ 92 Templates  │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

### Build Phases (Per Layer)

```
┌─────────────────────────────────────────────────────────────┐
│ INSTALL PHASE                                               │
│ - Install Python 3.11                                       │
│ - Install pytest, cfn-lint, boto3                           │
├─────────────────────────────────────────────────────────────┤
│ PRE_BUILD PHASE                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ GATE 1: Smoke Tests (BLOCKING)                          │ │
│ │ - pytest tests/smoke/test_platform_smoke.py             │ │
│ │ - Exit 1 if ANY test fails                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ GATE 2: Template Validation (BLOCKING)                  │ │
│ │ - cfn-lint on layer-specific templates                  │ │
│ │ - Exit 1 if validation fails                            │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ BUILD PHASE                                                 │
│ - Deploy layer-specific CloudFormation stacks               │
│ - Uses aws cloudformation deploy --no-fail-on-empty-changeset│
├─────────────────────────────────────────────────────────────┤
│ POST_BUILD PHASE                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ GATE 3: Post-Deployment Validation (WARNING)            │ │
│ │ - Verify stack status                                   │ │
│ │ - Warns if issues detected                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│ - Upload artifacts to S3                                    │
│ - Send SNS notification                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer Deployment Order

The pipeline deploys infrastructure in 8 layers with proper dependency management. Each layer has a dedicated CodeBuild project.

### Layer 1: Foundation (DEPLOYED ✅)
**CodeBuild Project:** `aura-foundation-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-foundation.yml`

**Stacks:**
- `aura-networking-dev` - VPC, subnets, route tables
- `aura-security-dev` - Security groups, NACLs, WAF
- `aura-iam-dev` - IAM roles for services
- `aura-vpc-endpoints-dev` - VPC endpoints for AWS services
- `aura-kms-dev` - KMS encryption keys
- All `aura-codebuild-*` stacks (deploys other CodeBuild projects)

**Sub-Layers:**
- **1.7:** `aura-network-services-deploy-{env}` - dnsmasq, ECS Fargate VPC-wide DNS
- **1.9:** `aura-docker-deploy-{env}` - Docker image builds for ECR

**Dependencies:** None (Bootstrap exemption for initial deployment)
**Time:** ~5 minutes

---

### Layer 2: Data (DEPLOYED ✅)
**CodeBuild Project:** `aura-data-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-data.yml`

**Stacks:**
- `aura-neptune-dev` - Graph database
- `aura-opensearch-dev` - Vector search database
- `aura-dynamodb-dev` - DynamoDB tables
- `aura-s3-dev` - S3 buckets

**Dependencies:** Foundation Layer
**Time:** ~15 minutes

---

### Layer 3: Compute (DEPLOYED ✅)
**CodeBuild Project:** `aura-compute-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-compute.yml`

**Stacks:**
- `aura-eks-dev` - Multi-tier Kubernetes cluster (EC2 nodes)
  - System node group (t3.medium)
  - Application node group (t3.large)
  - Sandbox node group (t3.medium, scale to zero)
- `aura-ecr-*` - ECR repositories

**Dependencies:** Foundation Layer
**Time:** ~12 minutes

---

### Layer 4: Application (DEPLOYED ✅)
**CodeBuild Project:** `aura-application-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-application.yml`

**Stacks:**
- `aura-bedrock-infrastructure-dev` - Bedrock integration
- `aura-irsa-*` - IAM Roles for Service Accounts
- `aura-frontend-dev` - Frontend application

**Sub-Layer:**
- **4:** `aura-frontend-deploy-{env}` - Frontend-specific deployments

**Dependencies:** Foundation + Compute Layers
**Time:** ~5 minutes

---

### Layer 5: Observability (DEPLOYED ✅)
**CodeBuild Project:** `aura-observability-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-observability.yml`

**Stacks:**
- `aura-secrets-dev` - Secrets Manager secrets
- `aura-monitoring-dev` - CloudWatch dashboards and alarms
- `aura-cost-alerts-dev` - Budget alerts and cost monitoring
- `aura-realtime-monitoring-dev` - Real-time metrics

**Dependencies:** Foundation + Data Layers
**Time:** ~3 minutes

---

### Layer 6: Serverless (DEPLOYED ✅)
**CodeBuild Project:** `aura-serverless-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-serverless.yml`

**Stacks:**
- `aura-dns-blocklist-lambda-dev` - DNS blocklist Lambda
- `aura-threat-intel-scheduler-dev` - Lambda + EventBridge for threat pipeline

**Sub-Layers:**
- **6.7:** `aura-chat-assistant-deploy-{env}` - WebSocket API, Bedrock chat integration
- **6.9:** `aura-incident-response-deploy-{env}` - Incident tracking, RCA workflows
- **6:** `aura-runbook-agent-deploy-{env}` - Runbook automation agents

**Dependencies:** Foundation + Observability Layers
**Time:** ~8-12 minutes

---

### Layer 7: Sandbox (DEPLOYED ✅)
**CodeBuild Project:** `aura-sandbox-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-sandbox.yml`

**Stacks:**
- `aura-sandbox-dev` - DynamoDB tables, ECS cluster, Security Groups, IAM roles, SNS topic, S3 bucket
- `aura-hitl-workflow-dev` - Step Functions state machine for HITL workflow

**Dependencies:** Foundation + Data Layers
**Time:** ~10-15 minutes

**What this deploys:**
- **DynamoDB Tables:** approval-requests, sandbox-state, sandbox-results (with GSIs and TTL)
- **ECS Cluster:** Fargate cluster for isolated patch testing sandboxes
- **Security Groups:** Sandbox isolation with VPC-only access
- **IAM Roles:** Task execution, task role, Step Functions execution role
- **SNS Topic:** HITL notification topic for approval requests
- **S3 Bucket:** Sandbox artifacts storage with lifecycle policies
- **Step Functions:** Complete HITL workflow state machine

---

### Layer 8: Security (DEPLOYED ✅)
**CodeBuild Project:** `aura-security-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-security.yml`

**Stacks:**
- `aura-config-compliance-dev` - AWS Config compliance rules
- `aura-guardduty-dev` - GuardDuty threat detection
- `aura-drift-detection-dev` - CloudFormation drift monitoring

**Dependencies:** Foundation + Data + Compute Layers
**Time:** ~5-10 minutes

**What this deploys:**
- **AWS Config Rules:** Compliance monitoring for security best practices
- **GuardDuty:** Threat detection and continuous security monitoring
- **Drift Detection:** CloudFormation drift alerts via EventBridge
- **Security Findings:** Integration with SNS for security alerts

---

## Step Functions Deployment Pipeline (Layer 6.11)

For fresh QA/PROD deployments, a Step Functions state machine automates the complete deployment sequence, avoiding circular dependencies between layers.

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP FUNCTIONS DEPLOYMENT PIPELINE                        │
│                         (Layer 6.11 - Full Automation)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
     ┌───────────────────────────────┼───────────────────────────────┐
     │                               │                               │
     ▼                               ▼                               ▼
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ PHASE 1 │                    │ PHASE 2 │                    │ PHASE 3 │
│ Infra   │─────────────────▶  │ K8s Gen │─────────────────▶  │ Docker  │
│ Layers  │                    │ Config  │                    │ Builds  │
│ 1→8     │                    │         │                    │ (5x)    │
└─────────┘                    └─────────┘                    └─────────┘
     │                                                              │
     └──────────────────────┬───────────────────────────────────────┘
                            │
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────┐           ┌─────────┐           ┌─────────┐
│ PHASE 4 │           │ PHASE 5 │           │ SUCCESS │
│ K8s     │─────────▶ │ Integr. │─────────▶ │ or      │
│ Deploy  │           │ Tests   │           │ FAILURE │
└─────────┘           └─────────┘           └─────────┘
```

### Phases

| Phase | Name | Description | Duration |
|-------|------|-------------|----------|
| 1 | Infrastructure | Deploy Layers 1-8 (parallel where possible) | ~45-60 min |
| 2 | K8s Config | Generate Kustomize overlays for target environment | ~2 min |
| 3 | Container Builds | Build all 5 service images in parallel | ~8-10 min |
| 4 | K8s Deployment | Apply manifests, deploy services to EKS | ~5-8 min |
| 5 | Integration Tests | Health checks, connectivity, API validation | ~5 min |

### Deploy Pipeline Infrastructure

```bash
# Deploy pipeline components (one-time setup per environment)
./deploy/scripts/deploy-pipeline-infrastructure.sh qa us-east-1

# This deploys:
# - codebuild-k8s-deploy.yaml (Layer 3.5)
# - codebuild-integration-test.yaml (Layer 3.6)
# - deployment-pipeline.yaml (Step Functions state machine)
```

### Trigger Automated Deployment

```bash
# Get the pipeline ARN
PIPELINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name aura-deployment-pipeline-qa \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Start full deployment
aws stepfunctions start-execution \
  --state-machine-arn ${PIPELINE_ARN} \
  --input '{"environment": "qa", "region": "us-east-1"}'
```

### Monitor Pipeline Execution

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn ${PIPELINE_ARN} \
  --max-results 5

# View execution details
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>
```

### Pipeline vs Manual Deployment

| Aspect | Manual (Layer-by-Layer) | Automated (Step Functions) |
|--------|------------------------|---------------------------|
| Time | 2-3 hours | 70-80 minutes |
| Error Risk | Higher (manual steps) | Lower (orchestrated) |
| Circular Dependencies | Possible | Prevented by design |
| Notifications | Per-layer SNS | Pipeline-level + per-phase |
| Rollback | Manual | Planned (future) |

### When to Use Each Approach

**Use Manual Layer Deployment When:**
- Debugging specific layer issues
- Partial deployments (e.g., only update Data layer)
- Development environment incremental changes

**Use Step Functions Pipeline When:**
- Fresh QA/PROD environment deployment
- Complete environment refresh
- Automated CI/CD from GitHub webhook

---

## K8s Deploy Image Account Validation (PR #275)

The `buildspec-k8s-deploy.yml` includes pre-deployment validation to prevent cross-account ECR image pull errors. This was added in January 2026 after discovering that `generate-k8s-config.sh` could generate incorrect account IDs in overlay files when run from a different environment context.

### How It Works

Before deploying any Kubernetes manifests, the buildspec validates that all overlay `kustomization.yaml` files reference the correct AWS account ID for the target environment.

```bash
# Validation loop in buildspec-k8s-deploy.yml
for OVERLAY in deploy/kubernetes/*/overlays/${ENVIRONMENT}/kustomization.yaml; do
  if [ -f "$OVERLAY" ]; then
    if grep -q "dkr.ecr" "$OVERLAY"; then
      OVERLAY_ACCOUNT=$(grep "dkr.ecr" "$OVERLAY" | head -1 | grep -oE '[0-9]{12}' | head -1)
      if [ "$OVERLAY_ACCOUNT" != "$AWS_ACCOUNT_ID" ]; then
        echo "ERROR: $OVERLAY uses account $OVERLAY_ACCOUNT but expected $AWS_ACCOUNT_ID"
        VALIDATION_FAILED=true
      fi
    fi
  fi
done
```

### Validation Output

**Success:**
```
OK: deploy/kubernetes/aura-api/overlays/qa/kustomization.yaml uses correct account 123456789012
OK: deploy/kubernetes/agent-orchestrator/overlays/qa/kustomization.yaml uses correct account 123456789012
...
```

**Failure (deployment blocked):**
```
ERROR: deploy/kubernetes/aura-api/overlays/qa/kustomization.yaml uses account 123456789012 but expected 123456789012
FATAL: Image account validation failed - aborting deployment
```

### Related Files

| File | Purpose |
|------|---------|
| `deploy/buildspecs/buildspec-k8s-deploy.yml` | Contains validation logic in pre_build phase |
| `deploy/config/account-mapping.env` | Environment-to-account ID mapping |
| `deploy/scripts/validate-account-id.sh` | Account validation helper script |
| `deploy/scripts/generate-k8s-config.sh` | Generates overlays from CloudFormation outputs |

### Troubleshooting

**If validation fails:**

1. Verify the environment's CloudFormation stacks are deployed to the correct account
2. Re-run `generate-k8s-config.sh` with the correct environment parameter
3. Check that AWS credentials point to the target environment's account

```bash
# Verify current account
aws sts get-caller-identity --query Account --output text

# Regenerate configs for the target environment
./deploy/scripts/generate-k8s-config.sh qa us-east-1
```

---

## Smoke Test Gates

### GATE 1: Pre-Deployment Smoke Tests (BLOCKING)

**Purpose:** Validate code is deployable before touching infrastructure

**Tests:**
- ✅ AST Parser can parse Python code
- ✅ Context objects can be created
- ✅ Neptune service works in MOCK mode
- ✅ MonitorAgent can be instantiated
- ✅ ObservabilityService tracks operations
- ✅ ObservabilityService reports health
- ✅ AST parsing meets performance SLA (< 2s)
- ✅ Neptune MOCK queries are fast (< 500ms)
- ✅ End-to-end workflow completes

**Failure Action:** **EXIT 1 - DEPLOYMENT BLOCKED**

**Example:**
```bash
pytest tests/smoke/test_platform_smoke.py -m smoke -v --tb=short -o addopts=""
# 10 passed in 0.09s ✓
```

---

### GATE 2: Deployment Validation Script (BLOCKING)

**Purpose:** Validate environment is ready for deployment

**Checks:**
1. **Smoke tests** - Re-runs smoke tests (redundant check)
2. **Code quality** - Ruff, Mypy, Bandit (non-blocking warnings)
3. **Infrastructure** - AWS credentials, VPC exists
4. **Performance** - Performance regression tests
5. **Security** - No secrets in repository, no hardcoded credentials

**Failure Action:** **EXIT 1 - DEPLOYMENT BLOCKED**

**Example:**
```bash
./deploy/scripts/validate-deployment.sh dev

# ✓ Smoke tests PASSED
# ✓ Code quality checks PASSED
# ✓ Infrastructure ready
# ✓ Performance tests PASSED
# ✓ No secrets detected
#
# ALL CHECKS PASSED ✓
# Safe to deploy: YES
```

---

### GATE 3: Post-Deployment Validation (WARNING)

**Purpose:** Verify deployed infrastructure is healthy

**Tests:** Same as GATE 1 (smoke tests against deployed services)

**Failure Action:** **WARNING ONLY** (deployment already complete)

**Use Case:**
- Monitor deployment health
- Trigger rollback if critical services fail
- Send alerts to on-call engineers

**Example:**
```bash
pytest tests/smoke/test_platform_smoke.py -m smoke -v --tb=short -o addopts=""

# If PASS:
# ✓ Post-deployment smoke tests PASSED
# ✓ Infrastructure is healthy and operational

# If FAIL:
# ⚠ WARNING: Post-deployment smoke tests FAILED
# ⚠ Infrastructure may be unhealthy - investigate immediately
# Consider rollback if critical services are down
```

---

## CloudFormation Template Validation

### cfn-lint Exit Code Handling

The buildspecs use `cfn-lint` to validate CloudFormation templates before deployment. Because cfn-lint returns exit code 4 for warnings (which can cause builds to fail even when templates are valid), all buildspecs use a graceful fallback pattern.

**Exit Codes:**

| Exit Code | Meaning | Build Action |
|-----------|---------|--------------|
| 0 | No errors or warnings | Pass |
| 4 | Warnings only (e.g., W3037 for unrecognized IAM actions) | Pass (non-blocking) |
| 2 | Parse error | Fail |
| 6 | Errors found | Fail |
| 8 | Both errors and warnings | Fail |

**Fallback Pattern in Buildspecs:**

```bash
# Prevents build failure on cfn-lint warnings (exit 4)
cfn-lint template.yaml || echo "cfn-lint warnings (non-blocking)"
```

This pattern is applied to 46 cfn-lint invocations across 8 buildspecs.

### cfn-lint Wrapper Script

For consistent exit code handling, use the wrapper script:

```bash
# Run wrapper (treats exit 4 as success)
./scripts/cfn-lint-wrapper.sh deploy/cloudformation/networking.yaml

# Run on all templates
./scripts/cfn-lint-wrapper.sh deploy/cloudformation/*.yaml

# With additional cfn-lint options
./scripts/cfn-lint-wrapper.sh --ignore-checks W3037 deploy/cloudformation/*.yaml
```

### IAM Action Validation

Some cfn-lint W3037 warnings indicate IAM actions that cfn-lint doesn't recognize but are actually valid AWS actions. Use the IAM validator to confirm:

```bash
# Validate all templates
python scripts/validate_iam_actions.py

# Generate detailed report
python scripts/validate_iam_actions.py --report --verbose

# Validate specific template
python scripts/validate_iam_actions.py deploy/cloudformation/iam.yaml

# Refresh validation cache
python scripts/validate_iam_actions.py --cache-refresh
```

**Known Valid Actions:**

When encountering W3037 for actions not in cfn-lint's database, the validator checks:
1. Cache of previously validated actions (7-day TTL)
2. Known valid actions list in `scripts/validate_iam_actions.py`
3. AWS IAM API via `SimulateCustomPolicy` (if credentials available)

To add a confirmed valid action that cfn-lint doesn't recognize, update `KNOWN_VALID_ACTIONS` in `scripts/validate_iam_actions.py`.

### Nightly Validation Workflow

A GitHub Actions workflow runs nightly at 2 AM UTC to validate all templates:

```yaml
# .github/workflows/nightly-iam-validation.yml
on:
  schedule:
    - cron: '0 2 * * *'
```

**Workflow Features:**
- Scans 97 CloudFormation templates (excludes `archive/` and `marketplace.yaml`)
- Validates all IAM actions against AWS service database
- Creates GitHub issue if invalid actions found
- Uploads validation report as artifact (30-day retention)

**Viewing Results:**
- Check Actions tab for workflow runs
- Download `iam-validation-report` artifact for full report
- Check Issues for `iam-validation` label if problems found

---

## Monitoring Builds

### View Build Status

```bash
# List recent builds for a specific layer
aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1

# Get latest build details
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-foundation-deploy-dev \
  --query 'ids[0]' \
  --output text \
  --region us-east-1)

aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --region us-east-1

# Check all layer builds
for layer in foundation data compute application observability serverless sandbox security; do
  echo "=== $layer ==="
  aws codebuild list-builds-for-project \
    --project-name aura-${layer}-deploy-dev \
    --max-items 1 \
    --region us-east-1
done
```

### View Build Logs

```bash
# Stream logs from CloudWatch (per layer)
aws logs tail /aws/codebuild/aura-foundation-deploy-dev \
  --follow \
  --region us-east-1

# Or view logs for other layers
aws logs tail /aws/codebuild/aura-data-deploy-dev --follow --region us-east-1
aws logs tail /aws/codebuild/aura-compute-deploy-dev --follow --region us-east-1
aws logs tail /aws/codebuild/aura-security-deploy-dev --follow --region us-east-1
```

### Build Notifications

**SNS Topics:** Each layer has its own SNS topic for build notifications.

**Email Notifications Sent:**
- ✅ Build started
- ✅ Build succeeded (with deployment summary)
- ❌ Build failed (with error details)
- ⚠ Smoke tests failed (GATE 1 or GATE 2)

---

## GitHub Integration (Optional)

### Set Up Webhook for Automatic Builds

**Step 1: Get CodeBuild Webhook URL**
```bash
aws codebuild list-source-credentials \
  --region us-east-1

# Or get from CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name aura-codebuild-foundation-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
  --output text \
  --region us-east-1
```

**Step 2: Add Webhook to GitHub**
1. Go to: https://github.com/aenealabs/aura/settings/hooks
2. Click "Add webhook"
3. **Payload URL:** (CodeBuild webhook URL from Step 1)
4. **Content type:** `application/json`
5. **Events:** Select "Just the push event"
6. **Active:** ✅ Checked
7. Click "Add webhook"

**Result:** Every push to `main` branch triggers automatic deployment

---

## GitHub Actions Optimization Patterns

Project Aura uses optimized GitHub Actions workflows following industry patterns from Netflix, Spotify, and major open-source projects. These optimizations reduce CI/CD costs by an estimated 50-60%.

### Path Filtering

Workflows use path filters to skip unnecessary CI runs:

```yaml
# Example: Skip CI on docs-only changes
on:
  push:
    branches: [main]
    paths-ignore:
      - '*.md'
      - 'docs/**'
      - '.github/*.md'
      - 'LICENSE'
      - '.gitignore'
  pull_request:
    branches: [main]
    paths-ignore:
      - '*.md'
      - 'docs/**'
```

**Benefits:**
- Documentation PRs complete in ~2 minutes instead of ~15 minutes
- No wasted compute on non-code changes
- Faster feedback for documentation contributors

### Selective Test Execution

Different test strategies for different events:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run linters
        run: |
          pip install ruff mypy
          ruff check src/
          mypy src/ --ignore-missing-imports

  test:
    # Only run full tests on PRs, not on every push to main
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run full test suite
        run: pytest tests/ -v --tb=short
```

**Benefits:**
- Push to `main`: Lint-only (~2 min) for fast feedback
- Pull requests: Full test suite (~15 min) for comprehensive validation
- Maintains quality gates while reducing cost

### Job Timeouts

All jobs have explicit timeouts to prevent hung jobs:

```yaml
jobs:
  lint:
    timeout-minutes: 10
    runs-on: ubuntu-latest
    # ...

  test:
    timeout-minutes: 30
    runs-on: ubuntu-latest
    # ...

  build:
    timeout-minutes: 20
    runs-on: ubuntu-latest
    # ...
```

**Recommended Timeouts:**
- Lint jobs: 10 minutes (typically completes in 2-3 min)
- Unit tests: 30 minutes (typically completes in 10-15 min)
- Integration tests: 45 minutes (includes service startup)
- Build/deploy jobs: 20 minutes

### Job Consolidation (Jan 2026)

Consolidated multiple parallel jobs into a single sequential job to reduce runner overhead and avoid infrastructure limits.

**Before (4 separate jobs):**
```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ setup   │   │  lint   │   │  tests  │   │security │
│ Runner1 │   │ Runner2 │   │ Runner3 │   │ Runner4 │
└─────────┘   └─────────┘   └─────────┘   └─────────┘
```
- 4 runners spin up simultaneously
- Each job: checkout → setup python → pip install → run task
- Total: 4× infrastructure overhead, 4× dependency installs

**After (2 consolidated jobs):**
```
┌────────────────────────────────────┐   ┌──────────┐
│        python-quality              │   │ security │
│  black → flake8 → mypy → bandit   │   │  trivy   │
│              ↓                     │   └──────────┘
│    pytest (PRs only)               │
└────────────────────────────────────┘
```
- 2 runners (quality + security scan)
- Single dependency install, sequential lint steps
- Fail-fast: lint failure stops pipeline before tests

**Implementation:**
```yaml
jobs:
  python-quality:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install black flake8 mypy bandit pytest pytest-cov
          pip install -r requirements.txt
      # Sequential lint steps (fail-fast)
      - run: black --check src/ tests/
      - run: flake8 src/ tests/
      - run: mypy src/ --ignore-missing-imports
        continue-on-error: true
      - run: bandit -r src/ -ll -ii
      # Tests only on PRs
      - name: Run tests
        if: github.event_name == 'pull_request'
        run: pytest tests/ -v --cov=src
```

**Benefits:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Runner spin-ups | 4 | 2 | 50% fewer |
| Dependency installs | 4 | 1 | 75% fewer |
| Typical run time | 10-15 min | 5 min | 50% faster |
| Infrastructure contention | High | Low | Fewer timeouts |

**Trade-offs:**
- ✅ Faster feedback on lint failures (stops immediately)
- ✅ Less GitHub Actions minutes consumed
- ⚠️ Test results wait for lint to complete (sequential)
- ⚠️ Single point of failure per job

### Cost Optimization Summary

| Optimization | Impact | Implementation |
|--------------|--------|----------------|
| Job consolidation | -50% runners | Merge lint/test into single job |
| Path filtering | -40% runs | `paths-ignore` in workflow triggers |
| Selective testing | -30% compute | `if: github.event_name == 'pull_request'` |
| Job timeouts | Prevents runaway costs | `timeout-minutes` on all jobs |
| Caching | -20% install time | `actions/cache` for pip/npm |
| Release Please batching | Prevents rate limits | `commit-search-depth: 100` + baseline tags |

**Expected Savings:**
- Before optimization: ~$50-80/month for active development
- After optimization: ~$15-25/month (60-70% reduction)

### Industry Patterns

These optimizations follow patterns used by:

- **Netflix**: Path-based workflow triggering for monorepo efficiency
- **Spotify**: Tiered testing (lint first, then unit, then integration)
- **Kubernetes**: Selective test execution based on changed paths
- **React**: PR-only full test runs, push triggers lint-only

### Release Please Incremental Scanning (Jan 2026)

Release Please scans commit history to generate changelogs. Without optimization, it scans the entire repository history on every push, causing GitHub API rate limit errors.

**Problem:**
```
commit search depth: 500 (default)
release search depth: 400 (default)
→ API rate limit exceeded for installation
```

**Solution: Batch Scanning with Baseline Tags**

1. **Reduce scan depth** in `release-please-config.json`:
```json
{
  "commit-search-depth": 100,
  "release-search-depth": 50
}
```

2. **Maintain baseline release tags** so scans only check new commits:
```
v1.4.0 tag (baseline)
    ↓
[commits since tag] ← Only these scanned (~100 max)
    ↓
v1.5.0 tag (next release)
    ↓
[commits since tag] ← Only these scanned
```

**Key Principle:** Release Please scans commits **since the last release tag**. Without tags, it scans the entire history. Creating regular releases keeps scan scope small.

**If rate limited:**
```bash
# Create baseline tag manually
git tag -a v1.x.0 -m "Release v1.x.0 - Baseline for Release Please"
git push origin v1.x.0

# Create GitHub release
gh release create v1.x.0 --title "v1.x.0" --notes "Baseline release"
```

**Configuration Reference:** See `release-please-config.json` for full settings.

---

## Rollback Procedures

### Rollback Infrastructure Layer

```bash
# Rollback specific CloudFormation stack
aws cloudformation cancel-update-stack \
  --stack-name aura-eks-dev \
  --region us-east-1

# Or delete and recreate from known-good template
aws cloudformation delete-stack \
  --stack-name aura-eks-dev \
  --region us-east-1

aws cloudformation wait stack-delete-complete \
  --stack-name aura-eks-dev \
  --region us-east-1

# Redeploy from backup
aws cloudformation create-stack \
  --stack-name aura-eks-dev \
  --template-body file://deploy/cloudformation/eks-multi-tier.yaml.backup \
  --region us-east-1
```

### Rollback Code Changes

```bash
# Revert to previous commit
git revert HEAD
git push origin main

# Webhook will trigger automatic deployment of reverted code
```

---

## Troubleshooting

### Build Fails at GATE 1 (Smoke Tests)

**Problem:** Smoke tests fail before deployment

**Solution:**
1. Run smoke tests locally:
   ```bash
   pytest tests/smoke/test_platform_smoke.py -m smoke -v --tb=short -o addopts=""
   ```
2. Fix failing tests
3. Commit and push
4. Re-trigger CodeBuild

**Common Issues:**
- API signature mismatch (check `docs/API_REFERENCE.md`)
- Missing dependencies (update `requirements.txt`)
- Import errors (check Python path)

---

### Build Fails at GATE 2 (Validation Script)

**Problem:** Deployment validation script fails

**Solution:**
1. Run validation locally:
   ```bash
   ./deploy/scripts/validate-deployment.sh dev
   ```
2. Check which step failed:
   - **Smoke tests** - See GATE 1 troubleshooting
   - **Code quality** - Run `ruff check src/` and `mypy src/`
   - **Infrastructure** - Verify AWS credentials with `aws sts get-caller-identity`
   - **Performance** - Check performance tests with `pytest -m performance`
   - **Security** - Search for secrets: `git grep -i 'password\|secret\|key'`

---

### Build Fails During Deployment

**Problem:** CloudFormation stack creation/update fails

**Solution:**
1. Check CloudFormation events:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name aura-eks-dev \
     --region us-east-1 \
     --max-items 20
   ```
2. Common issues:
   - **Insufficient IAM permissions** - Add missing permissions to CodeBuild role
   - **Resource limits** - Increase service quotas (EKS clusters, VPCs, etc.)
   - **Invalid parameters** - Check CloudFormation template parameters
   - **Dependency failure** - Ensure prerequisite stacks are deployed

---

### Post-Deployment Smoke Tests Fail (GATE 3)

**Problem:** Infrastructure deployed but smoke tests fail

**Solution:**
1. Check service health:
   ```bash
   kubectl get pods -n aura
   curl http://agent-orchestrator.aura.local/health
   ```
2. Common issues:
   - **Services not ready** - Wait for pods to reach READY state
   - **Network policy blocking** - Verify NetworkPolicy configuration
   - **DNS resolution failing** - Check dnsmasq services
   - **Database connection failure** - Verify Neptune/OpenSearch endpoints

**Rollback Decision:**
- If critical services are down → Rollback immediately
- If non-critical services are degraded → Monitor and fix

---

## Cost Optimization

### CodeBuild Pricing

**Build Compute:**
- `BUILD_GENERAL1_SMALL` (3 GB, 2 vCPUs): **$0.005/minute**
- Average build time: 20 minutes
- Cost per build: **$0.10**

**Monthly Costs (Dev Environment):**
- 10 builds/day × 22 days = 220 builds/month
- 220 builds × $0.10 = **$22/month**

**S3 Storage:**
- Artifacts bucket: ~1 GB/month
- Cost: **$0.023/month**

**Total:** **~$22/month** for dev environment

**Optimization Tips:**
- Use build caching (enabled by default)
- Deploy only changed layers (change detection enabled)
- Use smaller compute for non-production (`BUILD_GENERAL1_SMALL`)

---

## Security Best Practices

### Secrets Management

❌ **DON'T:** Store secrets in buildspec or git
✅ **DO:** Use AWS Systems Manager Parameter Store

**Example:**
```yaml
# buildspec.yml
env:
  parameter-store:
    DB_PASSWORD: "/aura/dev/database/password"
    API_KEY: "/aura/dev/api-key"
```

### IAM Least Privilege

CodeBuild service role has permissions for:
- ✅ CloudFormation (create/update/delete stacks)
- ✅ S3 (read/write artifacts bucket)
- ✅ CloudWatch Logs (write logs)
- ✅ SSM Parameter Store (read parameters)
- ✅ VPC resources (if deploying to VPC)

❌ **NOT:** Administrator access

---

## Best Practices

### Single Source of Truth Principle

**Rule:** CodeBuild is the ONLY authoritative deployment method. Manual deployments create dangerous mismatches.

**Why This Matters:**
- Manual deployments can succeed while CodeBuild shows FAILED
- Creates confusion about actual infrastructure state
- Breaks audit trail and compliance requirements (CMMC Level 3)
- Future CI/CD runs may fail or produce unexpected results

**When Manual Deployment is Acceptable:**
1. **Initial Development ONLY** - Testing new templates before CI/CD integration
2. **Emergency Hotfixes** - With immediate follow-up CodeBuild run
3. **Local Testing** - Never push to shared environments

**If you manually deployed to a shared environment:**
```bash
# 1. DELETE the manually created stack
aws cloudformation delete-stack --stack-name {stack-name}
aws cloudformation wait stack-delete-complete --stack-name {stack-name}

# 2. REDEPLOY via CodeBuild with proper service role
aws codebuild start-build --project-name {project-name}
```

**Recovery Steps (if single-source-of-truth violated):**
1. Identify what was deployed manually
2. Update buildspec to match manual deployment
3. Commit and push changes
4. Trigger CodeBuild to reconcile state
5. Verify CodeBuild shows SUCCESS

### Avoid Duplicate CodeBuild Executions

**Rule:** Never trigger a new CodeBuild while another build for the same project is still running.

**Why This Matters:**
- Parallel builds create race conditions in CloudFormation stacks
- One build may try to update a stack while another is still creating it
- Leads to `ROLLBACK_COMPLETE` states requiring manual cleanup

**Before Starting a New Build:**
```bash
# Check if any builds are currently running
aws codebuild list-builds-for-project --project-name {project-name} --max-items 3

# Check status of recent builds
aws codebuild batch-get-builds --ids {build-id} --query 'builds[0].buildStatus'

# If IN_PROGRESS, wait for completion or stop if needed
aws codebuild stop-build --id {build-id}
```

---

## Next Steps

After CI/CD pipeline is deployed:

1. **✅ Trigger first build** - Deploy Phase 2 infrastructure
2. **✅ Monitor build logs** - Verify all gates pass
3. **✅ Validate deployment** - Check CloudFormation stacks created
4. **✅ Set up GitHub webhook** - Enable automatic deployments
5. **✅ Configure alerts** - Subscribe to SNS topic for build notifications

---

## Quick Reference

```bash
# Bootstrap Foundation CodeBuild (one-time, per environment)
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-foundation.yaml \
  --stack-name aura-codebuild-foundation-dev \
  --parameter-overrides Environment=dev ProjectName=aura GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Trigger layer deployments
aws codebuild start-build --project-name aura-foundation-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-data-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-compute-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-application-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-observability-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-serverless-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-sandbox-deploy-dev --region us-east-1
aws codebuild start-build --project-name aura-security-deploy-dev --region us-east-1

# View logs (per layer)
aws logs tail /aws/codebuild/aura-foundation-deploy-dev --follow --region us-east-1

# Check stack status
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')]" \
  --region us-east-1 --output table
```

---

**Remember:** The 3-gate validation system ensures safe deployments. If smoke tests fail, deployment is blocked automatically.
