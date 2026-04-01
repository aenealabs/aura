# QA Deployment Automation Guide

**Last Updated:** 2026-01-11
**Status:** Infrastructure Ready, Kubernetes Automation Complete, Image Validation Enhanced
**Author:** Engineering Team

---

## Overview

This document provides comprehensive guidance for automating QA environment deployments for Project Aura. It addresses critical issues identified during a deployment automation review and provides solutions for seamless multi-environment deployments.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Issues Identified](#issues-identified)
3. [Solutions Implemented](#solutions-implemented)
4. [Deployment Sequence](#deployment-sequence)
5. [Automation Scripts](#automation-scripts)
6. [Troubleshooting](#troubleshooting)
7. [Future Improvements](#future-improvements)

---

## Executive Summary

### What Was Wrong

| Issue | Impact | Status |
|-------|--------|--------|
| Kubernetes overlays used shell variable syntax (`${VAR}`) | Kustomize cannot process environment variables | **FIXED** |
| Hardcoded account IDs in 51 files | Manual editing required for each environment | **PARTIALLY FIXED** |
| Hardcoded Neptune/OpenSearch endpoints | Breaks QA deployment | **FIXED** |
| No SSM parameter population after Data layer | Kubernetes has no source of truth | **FIXED** |
| Integration tests had hardcoded values | Tests fail in non-dev environments | **FIXED** |
| Cross-account ECR image references | k8s-deploy pulls from wrong account | **FIXED (PR #275)** |

### What Works Now

| Component | Status | Notes |
|-----------|--------|-------|
| CloudFormation templates | ✅ Fully parameterized | Uses `!Ref`, `!Sub`, intrinsic functions |
| Buildspecs | ✅ Fully parameterized | Uses environment variables from CodeBuild |
| Account bootstrap | ✅ Automated | Creates SSM parameters for each environment |
| Data layer SSM population | ✅ Automated | Stores Neptune/OpenSearch endpoints in SSM |
| Kubernetes config generation | ✅ Automated | Script generates overlays from CF outputs |
| Integration tests | ✅ Uses ConfigMap | No more hardcoded endpoints |
| Image account validation | ✅ Pre-deployment check | PR #275 validates ECR account IDs before k8s-deploy |

---

## Issues Identified

### Issue 1: Kustomize Variable Substitution (CRITICAL)

**Location:** `deploy/kubernetes/aura-api/overlays/qa/kustomization.yaml`

**Problem:** The QA overlay used shell variable syntax:
```yaml
# THIS DOES NOT WORK - Kustomize ignores ${VAR} syntax
newName: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-api-qa
value: "${NEPTUNE_ENDPOINT}"
```

**Root Cause:** Kustomize is a static YAML transformer. It does not execute shell commands or substitute environment variables. The `${VAR}` syntax is treated as a literal string.

**Impact:** QA Kubernetes deployments fail with invalid image references and endpoint configurations.

---

### Issue 2: Hardcoded Account IDs (51 Files)

**Files Affected:**
```
docs/deployment/QA_PROD_DEPLOYMENT_SEQUENCE.md
docs/deployment/MULTI_ACCOUNT_SETUP.md
docs/deployment/DEPLOYMENT_GUIDE.md
deploy/kubernetes/aura-api/overlays/dev/kustomization.yaml
deploy/kubernetes/agent-orchestrator/overlays/dev/kustomization.yaml
deploy/kubernetes/memory-service/base/deployment.yaml  # Note: root-level deployment.yaml deleted in PR #393
deploy/kubernetes/integration-test-job.yaml
... (44 more files)
```

**Impact:** Every environment change requires manual find-and-replace across dozens of files.

**Resolution:** Hardcoded values were moved to Kustomize overlays, and root-level manifests with unexpanded variables were deleted in PR #393 (Jan 15, 2026).

---

### Issue 3: Missing SSM Parameter Population

**Problem:** After Data layer deployment, endpoints exist in CloudFormation outputs but are not stored anywhere accessible to Kubernetes.

**Gap:** No automation to:
1. Query Neptune endpoint from CloudFormation
2. Store it in SSM Parameter Store
3. Make it available to Kubernetes ConfigMaps

---

### Issue 4: Forward Dependency in buildspec-data.yml

**Location:** `deploy/buildspecs/buildspec-data.yml:120`

```bash
# Data Layer (Layer 2) references Compute Layer (Layer 3) stack
export APP_SG=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-eks-node-groups-${ENVIRONMENT} ...)
```

**Impact:** Creates confusion about deployment order. The fallback handles it, but the pattern is incorrect.

---

## Solutions Implemented

### Solution 1: Kubernetes Config Generator Script

**File:** `deploy/scripts/generate-k8s-config.sh`

**Purpose:** Dynamically generates Kustomize overlays from CloudFormation outputs.

**How It Works:**
1. Queries CloudFormation stacks for Neptune, OpenSearch, ElastiCache endpoints
2. Gets AWS Account ID and region dynamically
3. Stores values in SSM Parameter Store
4. Generates properly configured Kustomize overlays
5. Creates integration test ConfigMaps

**Usage:**
```bash
# Generate configuration for QA environment
./deploy/scripts/generate-k8s-config.sh qa us-east-1

# Generate configuration for production
./deploy/scripts/generate-k8s-config.sh prod us-gov-west-1
```

**Output Files:**
- `deploy/kubernetes/aura-api/overlays/{env}/kustomization.yaml`
- `deploy/kubernetes/agent-orchestrator/overlays/{env}/kustomization.yaml`
- `deploy/kubernetes/test-configs/integration-test-config-{env}.yaml`

---

### Solution 2: SSM Parameter Population in buildspec-data.yml

**Addition to post_build phase:**

```bash
# Store Neptune endpoint
NEPTUNE_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-neptune-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterEndpoint`].OutputValue' \
  --output text)
aws ssm put-parameter \
  --name "/${PROJECT_NAME}/${ENVIRONMENT}/neptune-endpoint" \
  --value "${NEPTUNE_ENDPOINT}" \
  --type String --overwrite

# Store OpenSearch endpoint
OPENSEARCH_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-opensearch-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`DomainEndpoint`].OutputValue' \
  --output text)
aws ssm put-parameter \
  --name "/${PROJECT_NAME}/${ENVIRONMENT}/opensearch-endpoint" \
  --value "${OPENSEARCH_ENDPOINT}" \
  --type String --overwrite
```

**SSM Parameters Created:**
| Parameter | Description |
|-----------|-------------|
| `/{project}/{env}/neptune-endpoint` | Neptune cluster endpoint |
| `/{project}/{env}/opensearch-endpoint` | OpenSearch domain endpoint |
| `/{project}/{env}/redis-endpoint` | ElastiCache Redis endpoint |
| `/{project}/{env}/account-id` | AWS Account ID |
| `/{project}/{env}/region` | AWS Region |

---

### Solution 3: ConfigMap-Based Integration Tests

**File:** `deploy/kubernetes/integration-test-job.yaml`

**Change:** Replaced hardcoded environment variables with ConfigMap references:

```yaml
# Before (broken for non-dev environments)
env:
  - name: NEPTUNE_ENDPOINT
    value: "aura-neptune-dev.cluster-xxx.us-east-1.neptune.amazonaws.com"

# After (works for all environments)
envFrom:
  - configMapRef:
      name: integration-test-config
```

---

### Solution 4: Image Account Validation (PR #275)

**File:** `deploy/buildspecs/buildspec-k8s-deploy.yml`

**Problem:** When `generate-k8s-config.sh` runs in a different account context (e.g., dev account credentials but generating QA config), it can embed the wrong AWS account ID in ECR image references.

**Solution:** Added pre-deployment validation in the k8s-deploy buildspec that checks all overlay kustomization.yaml files for correct account IDs before applying manifests.

```bash
# Pre-deployment validation (buildspec-k8s-deploy.yml)
VALIDATION_FAILED=false
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
if [ "$VALIDATION_FAILED" = "true" ]; then
  echo "FATAL: Image account validation failed - aborting deployment"
  exit 1
fi
```

**Related Files:**

| File | Purpose |
|------|---------|
| `deploy/config/account-mapping.env` | Environment-to-account ID mapping |
| `deploy/scripts/validate-account-id.sh` | Account validation helper script |

**Benefits:**
- Prevents ImagePullBackOff errors due to cross-account ECR references
- Fails fast before attempting deployment
- Clear error messages indicating which files have incorrect account IDs

---

## Deployment Sequence

### Phase 0: Prerequisites (One-Time per Account)

```bash
# 1. Create GitHub CodeConnection in AWS Console
# 2. Store CodeConnection ARN in SSM
aws ssm put-parameter \
  --name /aura/global/codeconnections-arn \
  --value "arn:aws:codeconnections:us-east-1:ACCOUNT:connection/xxx" \
  --type String \
  --region us-east-1
```

### Phase 1: Account Bootstrap (One-Time per Environment)

```bash
# Deploy account bootstrap stack
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-qa \
  --parameter-overrides \
    Environment=qa \
    AdminRoleArn=arn:aws:iam::ACCOUNT:role/AWSAdministratorAccess \
    AlertEmail=alerts-qa@aenealabs.com \
    CodeConnectionsArn=arn:aws:codeconnections:us-east-1:ACCOUNT:connection/xxx \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Phase 2: CodeBuild Bootstrap

```bash
./deploy/scripts/bootstrap-fresh-account.sh qa us-east-1
```

### Phase 3: Infrastructure Layers (1-8)

```bash
# Deploy in sequence
aws codebuild start-build --project-name aura-foundation-deploy-qa
# Wait for completion...
aws codebuild start-build --project-name aura-data-deploy-qa
# Wait for completion...
aws codebuild start-build --project-name aura-compute-deploy-qa
# Continue through all 8 layers...
```

### Phase 4: Kubernetes Configuration (NEW - Required)

```bash
# Generate Kubernetes configs from CloudFormation outputs
./deploy/scripts/generate-k8s-config.sh qa us-east-1

# Apply to cluster
kubectl apply -f deploy/kubernetes/test-configs/integration-test-config-qa.yaml
kubectl apply -k deploy/kubernetes/aura-api/overlays/qa/
kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/qa/
```

---

## Automation Scripts

### generate-k8s-config.sh

| Feature | Description |
|---------|-------------|
| **Location** | `deploy/scripts/generate-k8s-config.sh` |
| **Purpose** | Generate Kustomize overlays from CF outputs |
| **Prerequisites** | AWS CLI, jq, deployed CF stacks |
| **Outputs** | Kustomize overlays, ConfigMaps, SSM parameters |

**Arguments:**
```
Usage: generate-k8s-config.sh <environment> [region]

Arguments:
  environment   Required. One of: dev, qa, prod
  region        Optional. AWS region (default: us-east-1)

Examples:
  ./deploy/scripts/generate-k8s-config.sh dev
  ./deploy/scripts/generate-k8s-config.sh qa us-east-1
  ./deploy/scripts/generate-k8s-config.sh prod us-gov-west-1
```

### bootstrap-fresh-account.sh

| Feature | Description |
|---------|-------------|
| **Location** | `deploy/scripts/bootstrap-fresh-account.sh` |
| **Purpose** | Bootstrap CodeBuild projects for new account |
| **Prerequisites** | SSM parameter for codeconnections-arn |
| **Outputs** | 18 CodeBuild projects |

---

## Troubleshooting

### Problem: Kustomize overlay still has placeholder values

**Symptom:**
```
image: ${AWS_ACCOUNT_ID}.dkr.ecr...
```

**Cause:** The overlay was created before CloudFormation stacks were deployed.

**Solution:**
```bash
# Re-run config generation after all CF stacks are deployed
./deploy/scripts/generate-k8s-config.sh qa us-east-1
```

---

### Problem: Integration tests fail with "NEPTUNE_ENDPOINT not configured"

**Cause:** ConfigMap not created or not applied.

**Solution:**
```bash
# Check if ConfigMap exists
kubectl get configmap integration-test-config -n aura

# If missing, generate and apply
./deploy/scripts/generate-k8s-config.sh qa
kubectl apply -f deploy/kubernetes/test-configs/integration-test-config-qa.yaml
```

---

### Problem: SSM parameters not found

**Cause:** Data layer deployment did not complete successfully.

**Solution:**
```bash
# Check if parameters exist
aws ssm get-parameter --name /aura/qa/neptune-endpoint

# If missing, manually create from CF outputs
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name aura-neptune-qa \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterEndpoint`].OutputValue' \
  --output text)
aws ssm put-parameter \
  --name /aura/qa/neptune-endpoint \
  --value "$ENDPOINT" \
  --type String
```

---

## ALB Controller Configuration (Manual Step)

The ALB Ingress resources contain AWS resource IDs that cannot be auto-generated:

| Resource | Source |
|----------|--------|
| Security Group ID | `aws cloudformation describe-stacks --stack-name aura-security-${ENV} --query 'Stacks[0].Outputs[?OutputKey==\`AlbSecurityGroupId\`].OutputValue'` |
| WAF ACL ARN | `aws cloudformation describe-stacks --stack-name aura-waf-${ENV} --query 'Stacks[0].Outputs[?OutputKey==\`WebAclArn\`].OutputValue'` |
| Subnet IDs | `aws cloudformation describe-stacks --stack-name aura-networking-${ENV} --query 'Stacks[0].Outputs[?OutputKey==\`PublicSubnetIds\`].OutputValue'` |
| ACM Certificate ARN | Create in ACM for the environment domain |

**Files requiring manual update:**
- `deploy/kubernetes/alb-controller/values.yaml`
- `deploy/kubernetes/alb-controller/aura-api-ingress.yaml`
- `deploy/kubernetes/alb-controller/aura-frontend-ingress.yaml`

---

## Services Using Base/Overlay Pattern

The following services use the Kustomize base/overlay pattern for multi-environment support:

| Service | Base Path | Overlay Generated |
|---------|-----------|-------------------|
| aura-api | `deploy/kubernetes/aura-api/base/` | Yes |
| agent-orchestrator | `deploy/kubernetes/agent-orchestrator/base/` | Yes |
| memory-service | `deploy/kubernetes/memory-service/base/` | Yes |
| meta-orchestrator | `deploy/kubernetes/meta-orchestrator/base/` | Yes |
| aura-frontend | `deploy/kubernetes/aura-frontend/base/` | Yes |

Run `./deploy/scripts/generate-k8s-config.sh qa` to generate all overlays.

---

## Future Improvements

### Short-Term (Q1 2026)

1. **External Secrets Operator Integration**
   - Pull SSM parameters directly into Kubernetes at runtime
   - Eliminates need to regenerate overlays when endpoints change

2. **Automated Config Generation in CI/CD**
   - Add `generate-k8s-config.sh` call to buildspec-compute.yml post_build
   - Kubernetes configs auto-update after infrastructure changes

### Medium-Term (Q2 2026)

1. **ArgoCD Integration**
   - GitOps-based Kubernetes deployments
   - Automatic sync when overlays are committed

2. **Helm Migration**
   - Replace Kustomize with Helm charts
   - Better templating with values.yaml per environment

### Long-Term (Q3-Q4 2026)

1. **Terraform Migration**
   - Unified IaC for CloudFormation + Kubernetes
   - Better state management and drift detection

---

## Appendix: Files Modified

| File | Change |
|------|--------|
| `deploy/scripts/generate-k8s-config.sh` | **NEW** - Generates overlays for all 5 services |
| `deploy/buildspecs/buildspec-data.yml` | Added SSM parameter population |
| `deploy/kubernetes/integration-test-job.yaml` | Replaced hardcoded values with ConfigMap |
| `deploy/kubernetes/connectivity-test-pod.yaml` | Replaced hardcoded values with ConfigMap |
| `deploy/kubernetes/test-configs/` | **NEW** - Directory for test ConfigMaps |
| `deploy/kubernetes/*/base/` | **NEW** - Base manifests for 5 services |
| `deploy/kubernetes/alb-controller/*.yaml` | Added placeholder variables |
| `deploy/kubernetes/aura-api/README.md` | Updated with overlay deployment |

---

## References

- [MULTI_ACCOUNT_SETUP.md](./MULTI_ACCOUNT_SETUP.md) - Multi-account AWS setup
- [CICD_SETUP_GUIDE.md](./CICD_SETUP_GUIDE.md) - CI/CD pipeline documentation
- [QA_PROD_DEPLOYMENT_SEQUENCE.md](./QA_PROD_DEPLOYMENT_SEQUENCE.md) - Deployment sequence
- [ADR-041](../architecture-decisions/ADR-041-aws-required-wildcards-defense-in-depth.md) - IAM wildcards policy
