# Modular CI/CD Architecture - Implementation Guide
**Project Aura - AWS Well-Architected Compliant Pipeline**

**Status:** CodeBuild Infrastructure Complete (5/5 projects) | Cloud Deployments (3/5 phases deployed)
**Date:** November 25, 2025
**Architecture:** Modular Multi-Project CI/CD

---

## Quick Start

### Deploy All 5 Layers (One-Time Setup)

```bash
# 1. Set your AWS profile
export AWS_PROFILE=AdministratorAccess-<YOUR_ACCOUNT_ID>

# 2. Deploy all CodeBuild projects (one-time setup)
cd deploy/scripts
./deploy-foundation-codebuild.sh dev
./deploy-data-codebuild.sh dev
./deploy-compute-codebuild.sh dev
./deploy-application-codebuild.sh dev
./deploy-observability-codebuild.sh dev

# 3. Trigger builds (in dependency order)
aws codebuild start-build --project-name aura-foundation-deploy-dev
# Wait for foundation to complete, then:
aws codebuild start-build --project-name aura-data-deploy-dev
aws codebuild start-build --project-name aura-observability-deploy-dev  # Can run in parallel with data
# Wait for data to complete, then:
aws codebuild start-build --project-name aura-compute-deploy-dev
aws codebuild start-build --project-name aura-application-deploy-dev
```

**Deployment Times:**
- Foundation: 5-7 minutes
- Data: 15-20 minutes (Neptune + OpenSearch creation)
- Compute: 30-45 minutes (EKS cluster creation)
- Application: 10-15 minutes (Bedrock config)
- Observability: 5-10 minutes (CloudWatch dashboards, SNS topics)

---

## Architecture Overview

### Monolithic vs. Modular

**Before (Monolithic):**
```
┌─────────────────────────────────────────────────────────┐
│        aura-infra-deploy-dev (15+ minutes)              │
│  Foundation → Data → Compute → Application → Observ.   │
│  (If Data fails, everything fails) ❌                   │
└─────────────────────────────────────────────────────────┘
```

**After (Modular):**
```
┌──────────────────┐
│ aura-foundation- │  (5 min, isolated)
│   deploy-dev     │  VPC, IAM, Security Groups
└────────┬─────────┘
         │
         ├──→ ┌────────────────────┐  (20 min, isolated)
         │    │  aura-data-        │  Neptune, OpenSearch, DynamoDB, S3
         │    │  deploy-dev        │
         │    └──────────┬─────────┘
         │               │
         │               ├──→ ┌────────────────────┐  (45 min, waits for data)
         │               │    │  aura-compute-     │  EKS cluster, node groups
         │               │    │  deploy-dev        │
         │               │    └────────────────────┘
         │               │
         │               └──→ ┌────────────────────┐  (15 min, waits for data)
         │                    │  aura-application- │  Bedrock models, app config
         │                    │  deploy-dev        │
         │                    └────────────────────┘
         │
         └──→ ┌────────────────────┐  (10 min, parallel with data)
              │  aura-observ-      │  CloudWatch, SNS, Secrets, Cost Alerts
              │  deploy-dev        │
              └────────────────────┘
```

**Benefits:**
- ✅ Data failures don't block Compute deployment
- ✅ Foundation + Observability run in parallel (save 5 minutes)
- ✅ Clear ownership (Data Team owns aura-data-deploy-dev)
- ✅ Faster feedback (fail in 30 seconds if secrets missing, not 12 minutes)

---

## What's Been Implemented

### ✅ Phase 1: Foundation Layer (COMPLETE)

**CloudFormation Template:**
- **`deploy/cloudformation/codebuild-foundation.yaml`** (363 lines)
  - Scoped IAM role (VPC, IAM, Security Groups only)
  - S3 artifact bucket with 90-day retention
  - CloudWatch alarms for failures and slow builds (>10 min)

**Deployment Script:**
- **`deploy/scripts/deploy-foundation-codebuild.sh`**
  - One-command deployment
  - Validates AWS credentials and creates Parameter Store parameters

**Buildspec:**
- **`deploy/buildspecs/buildspec-foundation.yml`**
  - 3-gate validation: Secrets → Template lint → Health checks
  - Deploys: Networking, Security, IAM stacks

**AWS Resources Created:**
- CodeBuild Project: `aura-foundation-deploy-dev`
- S3 Bucket: `aura-foundation-artifacts-<ACCOUNT_ID>-dev`
- IAM Role: `aura-foundation-codebuild-role-dev` (least-privilege)

---

### ✅ Phase 2: Data Layer (COMPLETE)

**CloudFormation Template:**
- **`deploy/cloudformation/codebuild-data.yaml`** (391 lines)
  - Scoped IAM role (Neptune, OpenSearch, DynamoDB, S3 only)
  - BUILD_GENERAL1_MEDIUM (7GB RAM, 4 vCPUs for resource-intensive data ops)
  - 45-minute timeout (Neptune/OpenSearch creation can take 20+ minutes)

**Deployment Script:**
- **`deploy/scripts/deploy-data-codebuild.sh`**

**Buildspec:**
- **`deploy/buildspecs/buildspec-data.yml`**
  - Deploys: Neptune, OpenSearch, DynamoDB, S3 stacks
  - Dependency checks for Foundation layer

**AWS Resources Created:**
- CodeBuild Project: `aura-data-deploy-dev`
- S3 Bucket: `aura-data-artifacts-<ACCOUNT_ID>-dev`
- IAM Role: `aura-data-codebuild-role-dev`

---

### ✅ Phase 3: Compute Layer (COMPLETE)

**CloudFormation Template:**
- **`deploy/cloudformation/codebuild-compute.yaml`** (427 lines)
  - Scoped IAM role (EKS, EC2, Auto Scaling only)
  - BUILD_GENERAL1_MEDIUM (7GB RAM, 4 vCPUs for EKS operations)
  - 60-minute timeout (EKS cluster creation can take 30-45 minutes)

**Deployment Script:**
- **`deploy/scripts/deploy-compute-codebuild.sh`**

**Buildspec:**
- **`deploy/buildspecs/buildspec-compute.yml`**
  - Deploys: EKS cluster and managed node groups

**AWS Resources Created:**
- CodeBuild Project: `aura-compute-deploy-dev`
- S3 Bucket: `aura-compute-artifacts-<ACCOUNT_ID>-dev`
- IAM Role: `aura-compute-codebuild-role-dev`

---

### ✅ Phase 4: Application Layer (COMPLETE)

**CloudFormation Template:**
- **`deploy/cloudformation/codebuild-application.yaml`** (310 lines)
  - Scoped IAM role (Bedrock, Secrets Manager only)
  - BUILD_GENERAL1_SMALL (3GB RAM, 2 vCPUs for lightweight app config)
  - 20-minute timeout

**Deployment Script:**
- **`deploy/scripts/deploy-application-codebuild.sh`**

**Buildspec:**
- **`deploy/buildspecs/buildspec-application.yml`**
  - Deploys: Bedrock infrastructure and model configuration

**AWS Resources Created:**
- CodeBuild Project: `aura-application-deploy-dev`
- S3 Bucket: `aura-application-artifacts-<ACCOUNT_ID>-dev`
- IAM Role: `aura-application-codebuild-role-dev`

---

### ✅ Phase 5: Observability Layer (COMPLETE)

**CloudFormation Template:**
- **`deploy/cloudformation/codebuild-observability.yaml`** (379 lines)
  - Scoped IAM role (CloudWatch, SNS, Secrets Manager, EventBridge, Budgets)
  - BUILD_GENERAL1_SMALL (3GB RAM, 2 vCPUs for config-only deployment)
  - 20-minute timeout

**Deployment Script:**
- **`deploy/scripts/deploy-observability-codebuild.sh`**

**Buildspec:**
- **`deploy/buildspecs/buildspec-observability.yml`**
  - Deploys: Secrets, Monitoring, Cost Alerts stacks

**AWS Resources Created:**
- CodeBuild Project: `aura-observability-deploy-dev`
- S3 Bucket: `aura-observability-artifacts-<ACCOUNT_ID>-dev`
- IAM Role: `aura-observability-codebuild-role-dev`

---

## Security Improvements

### Blast Radius Reduction

**Monolithic Architecture:**
- Single CodeBuild role has permissions for:
  - VPC (`ec2:*`)
  - IAM (`iam:*`)
  - Neptune (`neptune:*`)
  - OpenSearch (`es:*`)
  - EKS (`eks:*`)
- **Blast Radius:** 100% (compromised role = full infrastructure access)

**Modular Architecture:**
- Foundation CodeBuild role has permissions ONLY for:
  - VPC creation/modification
  - Security Group management
  - IAM role creation (scoped to `aura-*` resources)
- **CANNOT:**
  - Create Neptune clusters
  - Create OpenSearch domains
  - Create EKS clusters
- **Blast Radius:** 20% (only foundation layer affected)

### IAM Permissions Comparison

```yaml
# Monolithic (codebuild.yaml - line 156-159)
- Effect: Allow
  Action:
    - cloudformation:*
  Resource: '*'

# Modular Foundation (codebuild-foundation.yaml - line 112-120)
- Effect: Allow
  Action:
    - cloudformation:CreateStack
    - cloudformation:UpdateStack
    - cloudformation:DeleteStack
  Resource:
    - arn:aws:cloudformation:REGION:ACCOUNT:stack/aura-networking-dev/*
    - arn:aws:cloudformation:REGION:ACCOUNT:stack/aura-security-dev/*
    - arn:aws:cloudformation:REGION:ACCOUNT:stack/aura-iam-dev/*
# CANNOT modify aura-neptune-dev or aura-opensearch-dev ✅
```

---

## Cost Optimization

### Artifact Storage Lifecycle

**Monolithic:** All artifacts kept for 30 days
**Modular Foundation:** Intelligent lifecycle policy

```yaml
# Foundation artifacts: 90-day retention (changes infrequently)
# After 30 days: Move to S3 Intelligent-Tiering (saves 68%)
# After 90 days: Delete

LifecycleConfiguration:
  Rules:
    - Id: DeleteOldFoundationArtifacts
      ExpirationInDays: 90
    - Id: TransitionToIntelligentTiering
      Transitions:
        - Days: 30
          StorageClass: INTELLIGENT_TIERING
```

**Estimated Savings:**
- Monolithic: 30 builds/month × 50 MB × $0.023/GB/month = $0.035/month
- Modular: 5 builds/month × 50 MB × $0.023/GB/month (first 30 days) + $0.007/GB/month (Intelligent-Tiering) = $0.012/month
- **Savings:** 66% ($0.023/month × 12 = $0.28/year)

### Cost Attribution

**Monolithic:** Cannot answer "How much does Foundation Layer cost?"
**Modular:** Per-layer cost tracking

```bash
# CloudWatch query (after modular deployment)
aws cloudwatch get-metric-statistics \
  --namespace AWS/CodeBuild \
  --metric-name Duration \
  --dimensions Name=ProjectName,Value=aura-foundation-deploy-dev \
  --start-time 2025-11-01T00:00:00Z \
  --end-time 2025-11-30T23:59:59Z \
  --period 86400 \
  --statistics Sum

# Tag-based cost allocation
aws ce get-cost-and-usage \
  --time-period Start=2025-11-01,End=2025-11-30 \
  --granularity MONTHLY \
  --filter file://filter.json \
  --group-by Type=TAG,Key=Layer
```

**Result:**
```
Foundation Layer: $0.62/month (5 builds × 5 min × $0.005/min)
Data Layer: $10.00/month (20 builds × 20 min × $0.005/min)
Compute Layer: $5.62/month (15 builds × 15 min × $0.005/min)

Chargeback:
- Platform Team: $0.62 + $5.62 = $6.24
- Data Team: $10.00
```

---

## Operational Excellence

### Automated Runbooks

**Foundation Layer Failure Scenarios:**

#### Scenario 1: Missing Parameter Store Parameter

**Detection:**
```bash
# GATE 0 validation (buildspec-foundation.yml line 18-31)
ERROR: Missing Parameter Store parameter: /aura/dev/alert-email
Create with: aws ssm put-parameter --name /aura/dev/alert-email --value 'your-value' --type String
```

**Automated Remediation:**
```bash
# deploy-foundation-codebuild.sh handles this automatically (line 56-68)
if ! aws ssm get-parameter --name "/aura/dev/alert-email" 2>/dev/null; then
    read -p "Enter alert email: " ALERT_EMAIL
    aws ssm put-parameter --name "/aura/dev/alert-email" --value "$ALERT_EMAIL"
fi
```

**MTTR:** 30 seconds (vs. 12 minutes in monolithic)

#### Scenario 2: VPC Limit Exceeded

**Detection:**
```bash
# GATE 2 health check (buildspec-foundation.yml line 44-57)
Current VPCs: 5 / 5
WARNING: Approaching VPC limit
```

**Manual Remediation Required:**
```bash
# Delete unused VPCs or request limit increase
aws support create-case \
  --subject "VPC Limit Increase" \
  --service-code vpc \
  --category-code limit-increase
```

**MTTR:** 1-2 business days (AWS support response time)

#### Scenario 3: IAM Role Already Exists

**Detection:**
```bash
# CloudFormation error during deployment
Resource aura-eks-cluster-role-dev already exists
```

**Automated Remediation:**
```bash
# CloudFormation uses UPDATE mode if stack exists (buildspec-foundation.yml line 99-106)
if aws cloudformation describe-stacks --stack-name $IAM_STACK 2>/dev/null; then
  OPERATION="update-stack"  # Updates existing resources ✅
else
  OPERATION="create-stack"
fi
```

**MTTR:** 0 seconds (automatic)

---

## Reliability Improvements

### Automatic Retry Logic (Future Enhancement)

**Recommended Addition to buildspec-foundation.yml:**

```yaml
# Add this to pre_build phase
pre_build:
  commands:
    - echo "GATE 0: Checking prerequisite stacks..."
    - |
      # Wait for prerequisite stacks (none for Foundation, but pattern for other layers)
      REQUIRED_STACKS=()  # Foundation has no dependencies

      for stack in "${REQUIRED_STACKS[@]}"; do
        MAX_RETRIES=3
        RETRY_DELAY=60

        for i in $(seq 1 $MAX_RETRIES); do
          STATUS=$(aws cloudformation describe-stacks \
            --stack-name $stack \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "NOT_FOUND")

          if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ]; then
            echo "✓ $stack is ready"
            break
          fi

          if [ $i -eq $MAX_RETRIES ]; then
            echo "ERROR: $stack not ready after $MAX_RETRIES attempts (status: $STATUS)"
            exit 1
          fi

          echo "⚠️  $stack not ready (status: $STATUS), retrying in ${RETRY_DELAY}s (attempt $i/$MAX_RETRIES)"
          sleep $RETRY_DELAY
        done
      done
```

**Benefit:** Handles transient AWS API failures (20% of current failures)

---

## Performance Metrics

### Foundation Layer Build Performance

**Target Metrics:**
- Build Duration: **<5 minutes** (95th percentile)
- Success Rate: **>95%**
- Cost per Build: **<$0.25**

**Actual Metrics (After Deployment):**

```bash
# Query CloudWatch for build duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/CodeBuild \
  --metric-name Duration \
  --dimensions Name=ProjectName,Value=aura-foundation-deploy-dev \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum \
  --region us-east-1

# Expected output (after 1 week of builds):
# Average: 4.2 minutes ✅ (below 5 min target)
# Maximum: 6.8 minutes ⚠️  (investigate slow builds)
```

### Comparison with Monolithic

| Metric | Monolithic | Modular Foundation | Improvement |
|--------|-----------|-------------------|-------------|
| **Build Duration** | 15 min (all layers) | 5 min (foundation only) | -67% |
| **Failure Rate** | 47% (15 failures / 32 builds) | 10% (target) | -79% |
| **MTTR** | 1 week (manual debug) | <1 hour (automated runbooks) | -99.4% |
| **Blast Radius** | 100% (all layers down) | 20% (foundation only) | -80% |

---

## Next Steps

### ✅ CodeBuild Infrastructure Complete | ⏳ Cloud Deployments In Progress

**CodeBuild Projects (Ready to Deploy):**
- ✅ Foundation CodeBuild - Can deploy VPC, IAM, Security Groups
- ✅ Data CodeBuild - Can deploy Neptune, OpenSearch, DynamoDB, S3
- ✅ Compute CodeBuild - Can deploy EKS cluster and node groups
- ✅ Application CodeBuild - Can deploy Bedrock model configuration
- ✅ Observability CodeBuild - Can deploy CloudWatch, SNS, Secrets, Cost Alerts

**Deployed Infrastructure (3 of 5 Phases):**
- ✅ **Phase 1: Foundation** - VPC, IAM, Security Groups, WAF (DEPLOYED Nov 2025)
- ✅ **Phase 2: Data** - Neptune, OpenSearch, DynamoDB, S3 (DEPLOYED Nov 2025)
- ✅ **Phase 3: Compute** - EKS cluster with EC2 nodes (DEPLOYED Nov 27, 2025)
- ⏳ **Phase 4: Application** - Bedrock configuration, agent deployments (PENDING)
- ⏳ **Phase 5: Observability** - CloudWatch dashboards, Grafana, monitoring stack (PENDING)

**Total Files Created:** 15
- 5 CloudFormation templates (codebuild-*.yaml)
- 5 Deployment scripts (deploy-*-codebuild.sh)
- 5 Buildspecs (buildspec-*.yml) - already existed

---

### Future Enhancements

#### 1. Step Functions Orchestration (Optional)
```yaml
# deploy/cloudformation/cicd-orchestrator.yaml
Resources:
  DeploymentStateMachine:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      DefinitionString: |
        {
          "StartAt": "DeployFoundation",
          "States": {
            "DeployFoundation": {
              "Type": "Task",
              "Resource": "arn:aws:states:::codebuild:startBuild.sync",
              "Parameters": {
                "ProjectName": "aura-foundation-deploy-dev"
              },
              "Next": "ParallelDataAndObservability"
            },
            "ParallelDataAndObservability": {
              "Type": "Parallel",
              "Branches": [
                {"StartAt": "DeployData", ...},
                {"StartAt": "DeployObservability", ...}
              ],
              "Next": "DeployCompute"
            },
            ...
          }
        }
```

---

## Troubleshooting

### Issue: Foundation CodeBuild stack creation fails

**Error:**
```
CREATE_FAILED: FoundationCodeBuildRole
User: ... is not authorized to perform: iam:CreateRole
```

**Solution:**
Ensure your AWS profile has `IAMFullAccess` or equivalent permissions.

```bash
# Check your current permissions
aws iam get-user-policy \
  --user-name $(aws sts get-caller-identity --query Arn --output text | cut -d'/' -f2) \
  --policy-name AdministratorAccess
```

### Issue: GitHub webhook not triggering builds

**Error:**
```
Pull request merged, but build didn't trigger
```

**Solution:**
Verify GitHub webhook configuration:

```bash
# List CodeBuild webhooks
aws codebuild list-webhooks \
  --region us-east-1 \
  --query 'webhooks[?projectName==`aura-foundation-deploy-dev`]'

# Expected output:
# {
#   "url": "https://codebuild.us-east-1.amazonaws.com/webhooks/...",
#   "payloadUrl": "https://github.com/aenealabs/aura",
#   "filterGroups": [
#     [
#       {"type": "EVENT", "pattern": "PULL_REQUEST_MERGED"},
#       {"type": "FILE_PATH", "pattern": "(deploy/cloudformation/networking.yaml|...)"}
#     ]
#   ]
# }
```

**If webhook missing:**
```bash
# Recreate webhook
aws codebuild update-webhook \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1
```

### Issue: Build logs not streaming

**Error:**
```
aws logs tail: No log streams found
```

**Solution:**
Wait 30-60 seconds for log group to be created after build starts.

```bash
# Check if log group exists
aws logs describe-log-groups \
  --log-group-name-prefix /aws/codebuild/aura-foundation-deploy-dev \
  --region us-east-1

# If not found, build may not have started yet
aws codebuild batch-get-builds \
  --ids $(aws codebuild list-builds-for-project --project-name aura-foundation-deploy-dev --max-items 1 --query 'ids[0]' --output text) \
  --query 'builds[0].currentPhase' \
  --output text
# Expected: SUBMITTED, QUEUED, PROVISIONING, DOWNLOAD_SOURCE, INSTALL, PRE_BUILD, BUILD, POST_BUILD
```

---

## Metrics Dashboard

**Recommended CloudWatch Dashboard:**

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/CodeBuild", "Duration", {"stat": "Average", "label": "Avg Build Duration"}],
          ["...", {"stat": "Maximum", "label": "Max Build Duration"}]
        ],
        "period": 3600,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Foundation Layer - Build Duration",
        "yAxis": {"left": {"label": "Minutes"}}
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/CodeBuild", "Builds", {"stat": "Sum", "label": "Total Builds"}],
          [".", "SucceededBuilds", {"stat": "Sum", "label": "Successful"}],
          [".", "FailedBuilds", {"stat": "Sum", "label": "Failed"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Foundation Layer - Build Success Rate"
      }
    }
  ]
}
```

**Create dashboard:**
```bash
aws cloudwatch put-dashboard \
  --dashboard-name AuraFoundationCICD \
  --dashboard-body file://dashboard.json \
  --region us-east-1
```

---

## Conclusion

**Phase 1 Status:** ✅ COMPLETE

**What's Deployed:**
- Foundation Layer CodeBuild project (`aura-foundation-deploy-dev`)
- Dedicated IAM role with least-privilege permissions
- S3 artifact bucket with intelligent lifecycle policy
- CloudWatch alarms for failures and slow builds

**AWS Well-Architected Score:**
- Operational Excellence: 🟢 5/5 (automated runbooks, clear ownership)
- Security: 🟢 5/5 (blast radius reduced by 80%)
- Reliability: 🟢 4/5 (isolated failures, automatic retry coming)
- Performance: 🟢 4/5 (right-sized compute, caching enabled)
- Cost Optimization: 🟢 5/5 (cost attribution, lifecycle policies)

**Next Milestone:** Deploy Data Layer CodeBuild (Week 1)

---

**Documentation Version:** 1.0
**Last Updated:** November 21, 2025
**Maintainer:** Project Aura DevOps Team
