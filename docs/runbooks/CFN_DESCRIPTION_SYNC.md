# Runbook: CloudFormation Description Synchronization

**Purpose:** Resolve CloudFormation stack description drift where template description changes don't propagate to deployed stacks

**Audience:** DevOps Engineers, Platform Team

**Estimated Time:** 10-20 minutes

**Last Updated:** Dec 12, 2025

---

## Problem Description

CloudFormation stack descriptions only update when **resource changes** occur in the template. If you modify only the `Description` field (or metadata), the stack update reports "No changes to deploy" and the description remains stale.

### Symptoms

**Stack shows old description despite template changes:**

```bash
# Template shows new description
grep -m1 "Description:" deploy/cloudformation/dns-blocklist-lambda.yaml
# Description: 'Project Aura - Layer 6.6 - DNS Blocklist Lambda (Threat Intel)'

# But deployed stack shows old description
aws cloudformation describe-stacks \
  --stack-name aura-dns-blocklist-lambda-dev \
  --query 'Stacks[0].Description' \
  --output text
# Project Aura - Layer 6 - DNS Blocklist Lambda (Threat Intelligence)
```

**CloudFormation deploy reports no changes:**

```bash
aws cloudformation deploy --template-body file://... --stack-name ...
# No changes to deploy. Stack aura-dns-blocklist-lambda-dev is up to date
```

### Root Cause

CloudFormation's change detection only evaluates resource modifications, not metadata or description changes. This is by design to avoid unnecessary stack updates.

---

## Incident: Description Standardization (Dec 12, 2025)

### Background

Project Aura standardized CloudFormation descriptions to use layer-based numbering:
- **CodeBuild projects:** `Layer N` (single integer)
- **Infrastructure templates:** `Layer N.S` (sub-layer decimal)

### Problem

After updating 13 CodeBuild templates and 1 infrastructure template (dns-blocklist-lambda.yaml), descriptions didn't sync to deployed stacks.

### Fix Applied

**Technique:** Force description sync by modifying a resource property that CloudFormation tracks.

**Method 1: Add/Increment DescriptionVersion Tag** (Recommended)

Add a tag to any resource in the template that triggers a change:

```yaml
# In dns-blocklist-lambda.yaml
Resources:
  BlocklistConfigBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-blocklist-config-${Environment}'
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment
        - Key: Component
          Value: dns-blocklist
        - Key: DescriptionVersion    # Add this tag
          Value: '6.6.1'             # Increment to force updates
```

**Method 2: Add Metadata Section**

```yaml
Metadata:
  Version: '1.1'
  LastUpdated: '2025-12-12'
  DescriptionSync: 'Layer-6.6'    # Change this value to force sync
```

### Deployment via CodeBuild

Per CLAUDE.md guidelines, all deployments must use CodeBuild:

```bash
# 1. Commit the template changes
git add deploy/cloudformation/dns-blocklist-lambda.yaml
git commit -m "fix(cfn): Force dns-blocklist-lambda description sync"
git push

# 2. Deploy via CodeBuild (serverless layer handles dns-blocklist-lambda)
aws codebuild start-build \
  --project-name aura-serverless-deploy-dev \
  --region us-east-1

# 3. Monitor build
aws codebuild batch-get-builds \
  --ids <build-id> \
  --query 'builds[0].buildStatus'

# 4. Verify description updated
aws cloudformation describe-stacks \
  --stack-name aura-dns-blocklist-lambda-dev \
  --query 'Stacks[0].Description' \
  --output text
```

---

## Quick Resolution

### Step 1: Identify Stale Descriptions

```bash
# Compare template vs deployed description
STACK_NAME="aura-dns-blocklist-lambda-dev"
TEMPLATE_FILE="deploy/cloudformation/dns-blocklist-lambda.yaml"

echo "Template description:"
grep -m1 "Description:" $TEMPLATE_FILE

echo "Deployed description:"
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Description' \
  --output text
```

### Step 2: Force Description Sync

**Option A: Increment DescriptionVersion tag**

Find a resource with tags and add/increment `DescriptionVersion`:

```yaml
Tags:
  - Key: DescriptionVersion
    Value: '1.0.1'   # Increment from previous value
```

**Option B: Modify any resource property**

Change any benign property that CloudFormation will detect:

```yaml
# Add a harmless tag to any resource
- Key: LastDescriptionSync
  Value: '2025-12-12'
```

### Step 3: Deploy via CodeBuild

```bash
# Identify which CodeBuild project deploys this stack
# See CLAUDE.md "Sub-Layer Reference" table for mapping

# For dns-blocklist-lambda (Layer 6.6), use serverless project:
aws codebuild start-build \
  --project-name aura-serverless-deploy-dev \
  --region us-east-1
```

### Step 4: Verify Sync

```bash
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Description' \
  --output text
```

---

## Layer Numbering Standard

### CodeBuild Templates (Single Integer)

| Layer | CodeBuild Project | Description Format |
|-------|-------------------|-------------------|
| 1 | codebuild-foundation.yaml | `Layer 1: VPC, IAM, WAF, VPC Endpoints` |
| 2 | codebuild-data.yaml | `Layer 2: Neptune, OpenSearch, DynamoDB, S3` |
| 3 | codebuild-compute.yaml | `Layer 3: EKS, Node Groups, ECR, IRSA` |
| 4 | codebuild-application.yaml | `Layer 4: API, Bedrock, Frontend` |
| 5 | codebuild-observability.yaml | `Layer 5: Secrets, Monitoring, Cost Alerts` |
| 6 | codebuild-serverless.yaml | `Layer 6: Lambda, Step Functions, Chat` |
| 7 | codebuild-sandbox.yaml | `Layer 7: Sandbox, HITL Workflow` |
| 8 | codebuild-security.yaml | `Layer 8: Config, GuardDuty, Drift Detection` |

### Sub-Layer CodeBuild Templates (Decimal)

| Sub-Layer | CodeBuild Project | Description Format |
|-----------|-------------------|-------------------|
| 1.7 | codebuild-network-services.yaml | `Layer 1.7: dnsmasq ECS Service` |
| 4.7 | codebuild-frontend.yaml | `Layer 4.7: Frontend Container` |
| 6.7 | codebuild-chat-assistant.yaml | `Layer 6.7: WebSocket API, Bedrock Chat` |
| 6.8 | codebuild-runbook-agent.yaml | `Layer 6.8: Runbook Automation` |
| 6.9 | codebuild-incident-response.yaml | `Layer 6.9: Incident Management` |

### Infrastructure Templates (Decimal Sub-Layers)

See CLAUDE.md "Complete Sub-Layer Reference" for full mapping of 49 infrastructure templates.

---

## Prevention Checklist

When updating CloudFormation template descriptions:

- [ ] Update description in template file
- [ ] Add/increment `DescriptionVersion` tag on any resource
- [ ] Commit changes to git
- [ ] Deploy via CodeBuild (never manual `aws cloudformation deploy` for infrastructure)
- [ ] Verify description synced after deployment
- [ ] Update CLAUDE.md layer reference if new templates added

---

## Related Documentation

- [CLAUDE.md - CloudFormation Description Standards](../../CLAUDE.md#cloudformation-description-standards)
- [Resource Tagging Permissions Runbook](./RESOURCE_TAGGING_PERMISSIONS.md)
- [CI/CD Setup Guide](../CICD_SETUP_GUIDE.md)
- [AWS Knowledge Center: Stack Description Updates](https://repost.aws/knowledge-center/cloudformation-stack-description)
