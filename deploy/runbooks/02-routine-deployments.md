# Runbook: Routine Infrastructure Deployments

**Purpose:** Deploy infrastructure changes using the modular CI/CD pipeline

**Audience:** DevOps Engineers, Platform Team, Application Developers

**Estimated Time:** 5-45 minutes (depending on scope)

**Prerequisites:**
- Initial setup completed ([01-initial-setup.md](./01-initial-setup.md))
- Access to GitHub repository
- AWS CLI configured

---

## Overview

This runbook covers day-to-day infrastructure changes using the modular deployment system. The pipeline automatically detects which layers changed and deploys only what's necessary.

## Deployment Workflow

```
1. Make infrastructure changes
   ↓
2. Test change detection locally
   ↓
3. Commit and push to GitHub
   ↓
4. CodeBuild automatically triggers
   ↓
5. Monitor deployment
   ↓
6. Verify changes
```

## Scenario 1: Making Infrastructure Changes

### Example: Increase EKS Node Group Size

**Use Case:** Need more capacity for application workloads

#### Step 1: Identify the Template

```bash
# The EKS configuration is in:
vim deploy/cloudformation/eks.yaml
```

#### Step 2: Make the Change

Find the `NodeGroupMaxSize` parameter and increase it:

```yaml
# Before
ParameterKey=NodeGroupMaxSize,ParameterValue=5

# After
ParameterKey=NodeGroupMaxSize,ParameterValue=10
```

Or modify the default in the template:

```yaml
Parameters:
  NodeGroupMaxSize:
    Type: Number
    Default: 10  # Changed from 5
    MinValue: 1
    MaxValue: 20
```

#### Step 3: Validate Locally

```bash
# Validate template syntax
cfn-lint deploy/cloudformation/eks.yaml

# AWS validation
aws cloudformation validate-template \
  --template-body file://deploy/cloudformation/eks.yaml
```

✅ **Checkpoint:** Validation passes

#### Step 4: Test Change Detection

```bash
# See what will be deployed
python3 deploy/scripts/detect_changes.py
```

**Expected Output:**
```
Layers to deploy (1):
  1. Compute Layer: EKS Cluster and Node Groups [✓ CHANGED]
```

✅ **Checkpoint:** Only Compute layer detected

#### Step 5: Commit and Push

```bash
git add deploy/cloudformation/eks.yaml
git commit -m "feat: Increase EKS node group max size to 10"
git push origin main
```

#### Step 6: Monitor Deployment

```bash
# Get latest build
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' \
  --output text)

# Watch logs
aws logs tail /aws/codebuild/aura-infra-deploy-dev \
  --follow \
  --since 1m
```

⏱️ **Expected Duration:** 15-20 minutes (EKS updates)

#### Step 7: Verify Change

```bash
# Check node group configuration
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-nodegroup-dev \
  --query 'nodegroup.scalingConfig' \
  --output json
```

**Expected Output:**
```json
{
    "minSize": 2,
    "maxSize": 10,
    "desiredSize": 2
}
```

✅ **Checkpoint:** Max size updated to 10

---

## Scenario 2: Adding a New DynamoDB Table

**Use Case:** Application needs a new table for caching

#### Step 1: Edit DynamoDB Template

```bash
vim deploy/cloudformation/dynamodb.yaml
```

#### Step 2: Add New Table Resource

```yaml
  # Add to Resources section
  CacheTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-cache-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: key
          AttributeType: S
      KeySchema:
        - AttributeName: key
          KeyType: HASH
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment
```

#### Step 3: Add Output

```yaml
Outputs:
  CacheTableName:
    Description: Cache table name
    Value: !Ref CacheTable
    Export:
      Name: !Sub '${AWS::StackName}-CacheTableName'
```

#### Step 4: Test Change Detection

```bash
python3 deploy/scripts/detect_changes.py
```

**Expected Output:**
```
Layers to deploy (1):
  1. Data Layer: Databases and Storage [✓ CHANGED]
```

#### Step 5: Deploy

```bash
git add deploy/cloudformation/dynamodb.yaml
git commit -m "feat: Add cache table for application"
git push origin main
```

⏱️ **Expected Duration:** 5-10 minutes

#### Step 6: Verify Table Created

```bash
aws dynamodb describe-table \
  --table-name aura-cache-dev \
  --query 'Table.{Name:TableName,Status:TableStatus,Billing:BillingModeSummary.BillingMode}' \
  --output table
```

✅ **Checkpoint:** Table exists with PAY_PER_REQUEST billing

---

## Scenario 3: Updating Neptune Instance Size

**Use Case:** Database needs more capacity

#### Step 1: Edit Neptune Template

```bash
vim deploy/cloudformation/neptune.yaml
```

#### Step 2: Change Instance Type Parameter

Update the allowed values or default:

```yaml
Parameters:
  InstanceType:
    Type: String
    Default: db.r5.large  # Changed from db.t3.medium
    AllowedValues:
      - db.t3.medium
      - db.r5.large
      - db.r5.xlarge
```

#### Step 3: Deploy

```bash
git add deploy/cloudformation/neptune.yaml
git commit -m "perf: Upgrade Neptune to db.r5.large"
git push origin main
```

⏱️ **Expected Duration:** 15-20 minutes (Neptune update)

**Note:** Neptune updates may cause brief downtime. Consider:
- Notifying application teams
- Scheduling during maintenance window
- Testing in dev/qa first

---

## Scenario 4: Multiple Layer Changes

**Use Case:** Major feature requires changes across multiple layers

#### Example: Adding New Application with Database

**Changes Needed:**
1. New OpenSearch index configuration
2. New S3 bucket for application data
3. New IAM role for application
4. New secrets for API keys

#### Step 1: Make All Changes

```bash
# Update multiple templates
vim deploy/cloudformation/opensearch.yaml
vim deploy/cloudformation/s3.yaml
vim deploy/cloudformation/iam.yaml
vim deploy/cloudformation/secrets.yaml
```

#### Step 2: Test Change Detection

```bash
python3 deploy/scripts/detect_changes.py
```

**Expected Output:**
```
Layers to deploy (3):
  1. Foundation Layer: VPC, Security Groups, IAM Roles [✓ CHANGED]
  2. Data Layer: Databases and Storage [✓ CHANGED]
  3. Observability Layer: Secrets, Monitoring, Alerts [✓ CHANGED]
```

✅ **Checkpoint:** All affected layers detected

#### Step 3: Commit All Changes

```bash
git add deploy/cloudformation/opensearch.yaml \
        deploy/cloudformation/s3.yaml \
        deploy/cloudformation/iam.yaml \
        deploy/cloudformation/secrets.yaml

git commit -m "feat: Add infrastructure for new recommendation service"
git push origin main
```

⏱️ **Expected Duration:** 25-30 minutes (multiple layers)

---

## Scenario 5: Emergency Rollback

**Use Case:** Recent change caused issues, need to revert quickly

#### Option A: Git Revert and Redeploy

```bash
# Find the problematic commit
git log --oneline -10

# Revert the commit
git revert <commit-hash>

# Push revert
git push origin main

# Monitor rollback deployment
aws logs tail /aws/codebuild/aura-infra-deploy-dev --follow
```

⏱️ **Expected Duration:** Same as original deployment

#### Option B: Manual Stack Rollback (Faster)

```bash
# Identify the failed/problematic stack
STACK_NAME=aura-neptune-dev

# Check if rollback is possible
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].StackStatus'

# If status is UPDATE_COMPLETE, you can rollback to previous version
aws cloudformation cancel-update-stack --stack-name $STACK_NAME

# Or continue with rollback
aws cloudformation continue-update-rollback --stack-name $STACK_NAME
```

---

## Scenario 6: Testing Changes Locally Before Push

**Use Case:** Want to validate deployment logic without triggering CI/CD

#### Step 1: Set Environment Variables

```bash
export ENVIRONMENT=dev
export PROJECT_NAME=aura
export AWS_DEFAULT_REGION=us-east-1
```

#### Step 2: Test Single Layer Deployment

```bash
# Test foundation layer
bash deploy/scripts/deploy-foundation.sh

# Test data layer
bash deploy/scripts/deploy-data.sh

# Test compute layer
bash deploy/scripts/deploy-compute.sh
```

**Note:** These scripts directly deploy to AWS. Use with caution!

#### Step 3: Dry Run (Validation Only)

```bash
# Validate without deploying
for template in deploy/cloudformation/*.yaml; do
  echo "Validating $template..."
  aws cloudformation validate-template \
    --template-body file://$template
done
```

---

## Scenario 7: Force Redeploy Everything

**Use Case:** Need to rebuild entire infrastructure (disaster recovery, environment reset)

#### Step 1: Trigger Full Deployment

```bash
aws codebuild start-build \
  --project-name aura-infra-deploy-dev \
  --environment-variables-override \
    name=FORCE_DEPLOY,value=true,type=PLAINTEXT
```

**Or modify change detection:**

```bash
python3 deploy/scripts/detect_changes.py --force-all
```

⏱️ **Expected Duration:** 45-60 minutes

---

## Scenario 8: Deploying to Multiple Environments

**Use Case:** Promote changes from dev → qa → prod

#### Step 1: Deploy to Dev (already done)

```bash
# Changes already tested in dev via main branch
```

#### Step 2: Create QA Environment

```bash
# Create QA CodeBuild stack
aws cloudformation create-stack \
  --stack-name aura-codebuild-qa \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=qa \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=AlertEmail,ParameterValue=team@example.com \
    ParameterKey=GitHubRepository,ParameterValue=https://github.com/org/repo \
    ParameterKey=GitHubBranch,ParameterValue=main \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 3: Trigger QA Deployment

```bash
aws codebuild start-build \
  --project-name aura-infra-deploy-qa
```

#### Step 4: Repeat for Prod (with approvals)

**Best Practice:** Add manual approval step for production

---

## Monitoring Deployments

### Real-time Build Monitoring

```bash
# Method 1: CloudWatch Logs
aws logs tail /aws/codebuild/aura-infra-deploy-dev \
  --follow \
  --format short

# Method 2: Build Status
watch -n 10 'aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --max-items 1 | jq -r ".ids[0]" | \
  xargs -I {} aws codebuild batch-get-builds --ids {} | \
  jq -r ".builds[0] | {status: .buildStatus, phase: .currentPhase}"'

# Method 3: AWS Console
# https://console.aws.amazon.com/codesuite/codebuild/projects/aura-infra-deploy-dev/history
```

### Post-Deployment Verification

#### Check Stack Status

```bash
# List all stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].{Name:StackName, Status:StackStatus, Updated:LastUpdatedTime}" \
  --output table
```

#### View Recent Changes

```bash
# Get last 10 stack events for a specific stack
STACK_NAME=aura-networking-dev
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --max-items 10 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,ResourceStatusReason]' \
  --output table
```

#### Check Drift Detection

```bash
# Start drift detection
DRIFT_ID=$(aws cloudformation detect-stack-drift \
  --stack-name aura-networking-dev \
  --query 'StackDriftDetectionId' \
  --output text)

# Check drift status
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id $DRIFT_ID
```

---

## Best Practices

### 1. Always Test Change Detection First

```bash
# Before pushing, verify what will deploy
python3 deploy/scripts/detect_changes.py
```

### 2. Use Meaningful Commit Messages

Follow conventional commits:
```bash
feat: Add new cache table for recommendations
fix: Correct Neptune subnet configuration
perf: Increase EKS node capacity
refactor: Reorganize security group rules
docs: Update CloudFormation comments
```

### 3. Small, Incremental Changes

- ✅ One feature/fix per commit
- ✅ Test in dev before qa/prod
- ✅ Deploy during business hours (for visibility)
- ❌ Avoid massive multi-layer changes

### 4. Tag Releases

```bash
git tag -a v1.2.0 -m "Release: Add recommendation service infrastructure"
git push origin v1.2.0
```

### 5. Monitor Costs After Changes

```bash
# Check cost impact
aws ce get-cost-and-usage \
  --time-period Start=2025-11-01,End=2025-11-12 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=TAG,Key=Layer
```

---

## Common Deployment Patterns

### Pattern 1: Database Size Increase

```yaml
# Estimated time: 15-20 min
# Downtime: Possible brief interruption
# Rollback: Difficult (data migration)

Files: neptune.yaml or opensearch.yaml
Changes: InstanceType parameter
Testing: Required in dev first
```

### Pattern 2: Scaling Compute

```yaml
# Estimated time: 10-15 min
# Downtime: None (gradual)
# Rollback: Easy

Files: eks.yaml
Changes: NodeGroup min/max/desired size
Testing: Can test in prod (safe)
```

### Pattern 3: Adding Storage

```yaml
# Estimated time: 3-5 min
# Downtime: None
# Rollback: Easy

Files: s3.yaml or dynamodb.yaml
Changes: New bucket/table resources
Testing: Validate IAM permissions
```

### Pattern 4: Security Changes

```yaml
# Estimated time: 3-5 min
# Downtime: None
# Rollback: Easy (but coordinate with apps)

Files: security.yaml or iam.yaml
Changes: Security group rules, IAM policies
Testing: Critical - test thoroughly
```

---

## Troubleshooting Quick Reference

| Issue | Quick Fix | Detailed Runbook |
|-------|-----------|------------------|
| Build fails validation | Run `cfn-lint` locally | [03-troubleshooting.md](./03-troubleshooting.md#validation-errors) |
| Wrong layer deployed | Check git diff | [03-troubleshooting.md](./03-troubleshooting.md#wrong-layers) |
| Stack update timeout | Check CloudFormation events | [03-troubleshooting.md](./03-troubleshooting.md#timeouts) |
| Build not triggering | Verify webhook or trigger manually | [03-troubleshooting.md](./03-troubleshooting.md#webhook-issues) |

---

## Success Checklist

After each deployment:

- [ ] Build completed successfully
- [ ] All stacks show UPDATE_COMPLETE or CREATE_COMPLETE
- [ ] Application verified to work correctly
- [ ] No unexpected cost increases
- [ ] Team notified of changes
- [ ] Documentation updated if needed

---

## Next Steps

- **Emergency Response:** [03-troubleshooting.md](./03-troubleshooting.md)
- **Team Scaling:** [04-phase2-migration.md](./04-phase2-migration.md)
- **Cost Optimization:** Review AWS Cost Explorer

---

**Document Version:** 1.0
**Last Updated:** 2025-11-11
**Maintained By:** Platform Engineering Team
