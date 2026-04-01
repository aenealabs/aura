# Modular Infrastructure Deployment Guide

## Overview

This document describes Project Aura's modular CI/CD approach for infrastructure deployment using AWS CodeBuild. The system is designed to scale from small teams (1-3 people) to larger organizations with multiple teams owning different infrastructure layers.

## Architecture

### Phase 1: Single Project with Smart Change Detection (Current)

```bash
┌─────────────────────────────────────────────────┐
│  GitHub Repository (main branch)                │
└────────────┬────────────────────────────────────┘
             │ Push event
             ▼
┌─────────────────────────────────────────────────┐
│  CodeBuild: aura-infra-deploy-dev               │
│  BuildSpec: deploy/buildspec-modular.yml        │
├─────────────────────────────────────────────────┤
│  1. detect_changes.py                           │
│     └─> Analyzes git diff                       │
│     └─> Identifies changed layers               │
│                                                 │
│  2. Deploy only changed layers:                 │
│     ├─> Foundation (if changed)                 │
│     ├─> Data (if changed)                       │
│     ├─> Compute (if changed)                    │
│     ├─> Application (if changed)                │
│     └─> Observability (if changed)              │
└─────────────────────────────────────────────────┘
```

**Benefits:**

- Fast deployments (only changed layers)
- Single project to manage
- Simple GitHub webhook
- Easy rollback
- Cost-efficient

### Phase 2: Multiple Projects per Team (Future)

```bash
┌─────────────────────────────────────────────────┐
│  GitHub Repository (main branch)                │
└─────┬────────┬────────┬────────┬────────────────┘
      │        │        │        │        │
      ▼        ▼        ▼        ▼        ▼
   ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐
   │ F  │  │ D  │  │ C  │  │ A  │  │ O  │  Separate CodeBuild
   │ O  │  │ A  │  │ O  │  │ P  │  │ B  │  Projects per Layer
   │ U  │  │ T  │  │ M  │  │ P  │  │ S  │
   │ N  │  │ A  │  │ P  │  │    │  │ E  │
   │ D  │  │    │  │ U  │  │    │  │ R  │
   └────┘  └────┘  └────┘  └────┘  └────┘
 Platform   Data   Compute   App     SRE
   Team     Team     Team    Team    Team
```

**Migration:**

1. Uncomment Phase 2 resources in `deploy/cloudformation/codebuild.yaml`
2. Each team gets their own CodeBuild project
3. Teams can deploy their layer independently
4. Path-based GitHub triggers (optional)

## Infrastructure Layers

### 1. Foundation Layer

**Owners:** Platform/Infrastructure Team
**Stacks:**

- `networking.yaml` - VPC, subnets, NAT gateways, IGW
- `security.yaml` - Security groups, NACLs
- `iam.yaml` - IAM roles and policies

**Deployment Script:** `deploy/scripts/deploy-foundation.sh`
**BuildSpec:** `deploy/buildspecs/buildspec-foundation.yml`

**Dependencies:** None (foundational layer)

### 2. Data Layer

**Owners:** Data Engineering Team
**Stacks:**

- `neptune.yaml` - Graph database
- `opensearch.yaml` - Vector search
- `dynamodb.yaml` - NoSQL tables
- `s3.yaml` - Object storage

**Deployment Script:** `deploy/scripts/deploy-data.sh`
**BuildSpec:** `deploy/buildspecs/buildspec-data.yml`

**Dependencies:** Foundation layer

### 3. Compute Layer

**Owners:** Application/DevOps Team
**Stacks:**

- `eks.yaml` - Kubernetes cluster and node groups

**Deployment Script:** `deploy/scripts/deploy-compute.sh`
**BuildSpec:** `deploy/buildspecs/buildspec-compute.yml`

**Dependencies:** Foundation layer

### 4. Application Layer

**Owners:** Application Team
**Stacks:**

- `aura-bedrock-infrastructure.yaml` - Bedrock LLM infrastructure

**Deployment Script:** `deploy/scripts/deploy-application.sh`
**BuildSpec:** `deploy/buildspecs/buildspec-application.yml`

**Dependencies:** Foundation, Data, Compute layers

### 5. Observability Layer

**Owners:** SRE/Operations Team
**Stacks:**

- `secrets.yaml` - Secrets Manager
- `monitoring.yaml` - CloudWatch dashboards, alarms
- `aura-cost-alerts.yaml` - Budget alerts

**Deployment Script:** `deploy/scripts/deploy-observability.sh`
**BuildSpec:** `deploy/buildspecs/buildspec-observability.yml`

**Dependencies:** Foundation, Data layers

## How Change Detection Works

The `deploy/scripts/detect_changes.py` script:

1. **Compares git commits** (current vs. previous)
2. **Maps changed files** to infrastructure layers
3. **Calculates dependencies** (e.g., data layer needs foundation)
4. **Outputs deployment plan** in topological order

### Example: Changing Neptune Configuration

```bash
# Edit Neptune template
vim deploy/cloudformation/neptune.yaml

# Commit and push
git add deploy/cloudformation/neptune.yaml
git commit -m "Increase Neptune instance size"
git push
```

**Result:**

```bash
Deployment Plan:
1. Foundation Layer: SKIPPED (no changes)
2. Data Layer: DEPLOYING (neptune.yaml changed)
3. Compute Layer: SKIPPED (no changes)
4. Application Layer: SKIPPED (no changes)
5. Observability Layer: DEPLOYING (dependency on data)
```

## Usage

### Deploy Everything (Force Mode)

```bash
# Locally test change detection
python3 deploy/scripts/detect_changes.py --force-all

# Trigger build via CodeBuild
aws codebuild start-build \
  --project-name aura-infra-deploy-dev \
  --environment-variables-override \
    name=FORCE_DEPLOY,value=true,type=PLAINTEXT
```

### Deploy Specific Layer Locally

```bash
# Set environment variables
export ENVIRONMENT=dev
export PROJECT_NAME=aura
export AWS_DEFAULT_REGION=us-east-1

# Deploy single layer
bash deploy/scripts/deploy-foundation.sh
bash deploy/scripts/deploy-data.sh
bash deploy/scripts/deploy-compute.sh
```

### View Deployment Plan (Without Deploying)

```bash
python3 deploy/scripts/detect_changes.py --base-ref origin/main
```

## Migration to Phase 2 (Multi-Project Setup)

### When to Migrate

Migrate to Phase 2 when:

- Team grows to 3+ people
- Different teams own different infrastructure layers
- You need parallel deployments
- You want layer-specific IAM permissions
- You need separate deployment schedules

### Migration Steps

#### 1. **Update CloudFormation:**

```bash
# Edit deploy/cloudformation/codebuild.yaml
# Uncomment the Phase 2 resources (lines 349-519)
vim deploy/cloudformation/codebuild.yaml
```

#### 2. **Deploy Updated CodeBuild Stack:**

```bash
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=your-email@example.com \
  --capabilities CAPABILITY_NAMED_IAM
```

#### 3. **Configure GitHub Triggers (Optional):**

```yaml
# .github/workflows/infra-deploy.yml
name: Infrastructure Deployment

on:
  push:
    branches: [main]
    paths:
      - 'deploy/cloudformation/networking.yaml'
      - 'deploy/cloudformation/security.yaml'
      - 'deploy/cloudformation/iam.yaml'

jobs:
  deploy-foundation:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Foundation Build
        run: |
          aws codebuild start-build \
            --project-name aura-foundation-deploy-dev
```

#### 4. **Update IAM Permissions (Optional):**

Create team-specific IAM roles with least-privilege access:

```yaml
# Example: Data Team Role
DataTeamRole:
  Type: AWS::IAM::Role
  Properties:
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/AmazonRDSFullAccess
      - arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess
      - arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    # Deny access to networking/security stacks
```

### Rollback Strategy

If Phase 2 doesn't work:

1. Re-comment Phase 2 resources in `codebuild.yaml`
2. Update CodeBuild stack
3. Phase 1 single-project continues to work

## Monitoring and Alerts

### Build Notifications

All builds send notifications to:

- SNS Topic: `aura-build-notifications-{environment}`
- Email: Configured in SSM Parameter Store

### CloudWatch Logs

Each layer has separate log groups:

- `/aws/codebuild/aura-infra-deploy-{env}` (Phase 1)
- `/aws/codebuild/aura-foundation-{env}` (Phase 2)
- `/aws/codebuild/aura-data-{env}` (Phase 2)
- etc.

### Cost Tracking

- All stacks tagged with `Layer=<layer-name>`
- Use AWS Cost Explorer to track layer costs
- Budget alerts configured per environment

## Troubleshooting

### "No changes detected" but I changed a file

**Cause:** File not in the layer mapping
**Solution:** Edit `deploy/scripts/detect_changes.py` and add file to appropriate layer

### Build times out

**Cause:** EKS or Neptune taking too long
**Solution:** Increase timeout in `codebuild.yaml`:

```yaml
TimeoutInMinutes: 120  # Increase from 60
```

### Stack update fails mid-deployment

**Cause:** CloudFormation error in one stack
**Solution:**

1. Check CloudFormation console for error details
2. Fix template issue
3. Re-run deployment (change detection will retry failed layer)

### How to skip a layer deployment

**Option 1:** Temporarily modify change detection script
**Option 2:** Deploy manually via AWS CLI:

```bash
# Skip orchestrator, deploy directly
bash deploy/scripts/deploy-foundation.sh
```

## Performance Optimization

### Parallel Deployments (Future)

Phase 2 allows parallel deployments:

- Foundation → (Data + Compute in parallel) → Application

### Caching

CodeBuild caches:

- Python pip packages: `/root/.cache/pip`
- CloudFormation templates: S3 cache location

### Artifact Reuse

Templates uploaded to S3 once, reused across layers.

## Best Practices

1. **Always test locally first:**

   ```bash
   python3 deploy/scripts/detect_changes.py
   ```

2. **Tag all resources:**
   - `Project=aura`
   - `Environment={env}`
   - `Layer={layer}`
   - `ManagedBy=CodeBuild`

3. **Use SSM Parameter Store** for sensitive values:

   ```bash
   aws ssm put-parameter \
     --name /aura/dev/alert-email \
     --value your-email@example.com \
     --type String
   ```

4. **Version your templates** using S3 versioning (enabled by default)

5. **Monitor costs** per layer using tags

## File Structure Reference

```bash
deploy/
├── buildspec-modular.yml           # Phase 1 orchestrator (main entry)
├── buildspec.yml                   # Legacy monolithic (deprecated)
├── buildspecs/                     # Phase 2 ready buildspecs
│   ├── buildspec-foundation.yml
│   ├── buildspec-data.yml
│   ├── buildspec-compute.yml
│   ├── buildspec-application.yml
│   └── buildspec-observability.yml
├── scripts/                        # Deployment logic
│   ├── detect_changes.py          # Smart change detection
│   ├── execute_buildspec.py       # BuildSpec executor
│   ├── deploy-foundation.sh       # Foundation deployment
│   ├── deploy-data.sh             # Data deployment
│   ├── deploy-compute.sh          # Compute deployment
│   ├── deploy-application.sh      # Application deployment
│   └── deploy-observability.sh    # Observability deployment
└── cloudformation/                 # Infrastructure templates
    ├── codebuild.yaml             # CodeBuild projects (Phase 1 & 2)
    ├── networking.yaml
    ├── security.yaml
    ├── iam.yaml
    ├── neptune.yaml
    ├── opensearch.yaml
    ├── dynamodb.yaml
    ├── s3.yaml
    ├── eks.yaml
    ├── aura-bedrock-infrastructure.yaml
    ├── secrets.yaml
    ├── monitoring.yaml
    └── aura-cost-alerts.yaml
```

## Support

For questions or issues:

1. Check CloudWatch Logs for build errors
2. Review CloudFormation stack events
3. Test change detection locally
4. Contact DevOps team

---

**Version:** 1.0
**Last Updated:** 2025-11-11
**Maintained By:** Platform Engineering Team
