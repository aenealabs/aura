# Runbook: Troubleshooting CodeBuild Deployments

**Purpose:** Diagnose and resolve common deployment failures

**Audience:** DevOps Engineers, Platform Team, On-call Engineers

**Estimated Time:** Varies by issue (5-60 minutes)

---

## Quick Diagnostic Commands

```bash
# Get latest build status
aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' \
  --output text | \
  xargs -I {} aws codebuild batch-get-builds --ids {} | \
  jq '.builds[0] | {status: .buildStatus, phase: .currentPhase, reason: .buildStatusReason}'

# Check failed stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_FAILED UPDATE_FAILED ROLLBACK_COMPLETE ROLLBACK_FAILED \
  --query "StackSummaries[?starts_with(StackName, 'aura-')]" \
  --output table

# View recent build logs
aws logs tail /aws/codebuild/aura-infra-deploy-dev \
  --since 30m \
  --format short | grep -i error
```

---

## Issue 1: Build Fails in INSTALL Phase

### Symptoms
```
Phase: INSTALL
Status: FAILED
Error: pip install failed
```

### Diagnostic Steps

#### 1.1 Check Build Logs

```bash
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' \
  --output text)

aws logs filter-log-events \
  --log-group-name /aws/codebuild/aura-infra-deploy-dev \
  --filter-pattern "INSTALL" \
  --query 'events[*].message' \
  --output text
```

#### 1.2 Common Causes

**A. Network/Proxy Issues**
```
Error: Could not find a version that satisfies the requirement
```

**Solution:**
```bash
# Check CodeBuild VPC configuration
aws codebuild batch-get-projects \
  --names aura-infra-deploy-dev \
  --query 'projects[0].vpcConfig'

# If in VPC, ensure NAT gateway allows PyPI access
```

**B. Dependency Version Conflicts**
```
Error: pip's dependency resolver...
```

**Solution:** Pin versions in buildspec:
```yaml
- pip install cfn-lint==0.85.0 boto3==1.34.0 pyyaml==6.0
```

**C. Python Version Mismatch**
```
Error: No matching distribution found
```

**Solution:** Check runtime version in buildspec:
```yaml
install:
  runtime-versions:
    python: 3.11  # Ensure this matches requirements
```

### Resolution

Edit `deploy/buildspec-modular.yml`:
```yaml
install:
  runtime-versions:
    python: 3.11
  commands:
    - pip install --upgrade pip
    - pip install --no-cache-dir cfn-lint==0.85.0 boto3==1.34.0 pyyaml==6.0
```

Commit and redeploy.

---

## Issue 2: Build Fails in PRE_BUILD Phase

### Symptoms
```
Phase: PRE_BUILD
Status: FAILED
Error: cfn-lint validation failed
```

### Diagnostic Steps

#### 2.1 Check CloudFormation Lint Errors

```bash
# Run locally to see exact errors
cfn-lint deploy/cloudformation/*.yaml
```

#### 2.2 Common Validation Errors

**A. W3002 Warning (ignored by default)**
```
deploy/cloudformation/master-stack.yaml:129:9: W3002 Obsolete DependsOn on resource
```

**Solution:** Already ignored. If causing issues, fix the warning:
```yaml
# Remove unnecessary DependsOn
```

**B. E3001 Error - Invalid Property**
```
E3001: Invalid or unsupported Type AWS::Lambda::Function for resource
```

**Solution:** Check CloudFormation docs for correct property names

**C. E1012 Error - Ref Error**
```
E1012: Ref References should be String
```

**Solution:** Fix reference syntax:
```yaml
# Wrong
!Ref: VpcId

# Correct
!Ref VpcId
```

**D. Template Size Limit**
```
WARNING: template.yaml is larger than 51KB (52000 bytes)
```

**Solution:** Upload large templates to S3:
```bash
aws s3 cp deploy/cloudformation/eks.yaml \
  s3://aura-cfn-artifacts-${AWS_ACCOUNT_ID}-dev/cloudformation/
```

### Resolution

#### Fix Template Locally

```bash
# Fix the template
vim deploy/cloudformation/<problem-file>.yaml

# Validate
cfn-lint deploy/cloudformation/<problem-file>.yaml

# Test AWS validation
aws cloudformation validate-template \
  --template-body file://deploy/cloudformation/<problem-file>.yaml
```

#### Commit Fix

```bash
git add deploy/cloudformation/<problem-file>.yaml
git commit -m "fix: Correct CloudFormation template validation errors"
git push origin main
```

---

## Issue 3: Change Detection Not Working

### Symptoms
```
No infrastructure changes detected. Skipping deployment.
```

But you know you changed a file.

### Diagnostic Steps

#### 3.1 Test Change Detection Locally

```bash
# Check what files changed
git diff origin/main --name-only

# Run change detection
python3 deploy/scripts/detect_changes.py
```

#### 3.2 Check File Mapping

The file you changed must be in `INFRASTRUCTURE_LAYERS` mapping in `detect_changes.py`:

```python
# Check if your file is mapped
grep -r "your-changed-file.yaml" deploy/scripts/detect_changes.py
```

### Common Causes

**A. File Not in Layer Mapping**

Example: You changed `codebuild.yaml` but it's not in any layer.

**Solution:** Add to appropriate layer in `detect_changes.py`:

```python
"foundation": {
    "files": [
        "deploy/cloudformation/networking.yaml",
        "deploy/cloudformation/security.yaml",
        "deploy/cloudformation/iam.yaml",
        "deploy/cloudformation/codebuild.yaml",  # ADD THIS
    ],
    # ...
}
```

**B. Git Comparison Issue**

```bash
# Check git remote
git remote -v

# Fetch latest
git fetch origin

# Check merge base
git merge-base HEAD origin/main
```

**Solution:** Ensure clean git state:
```bash
git pull origin main
git push origin main
```

**C. Base Ref Not Found**

```bash
# Check if origin/main exists
git show-ref origin/main
```

**Solution:** Update change detection to use correct ref:
```python
# In detect_changes.py, update base_ref logic
base_ref = "HEAD~1"  # Fallback if origin/main missing
```

### Resolution

#### Force Deploy Specific Layer

```bash
# Manually trigger layer deployment
export ENVIRONMENT=dev
export PROJECT_NAME=aura
bash deploy/scripts/deploy-foundation.sh
```

#### Or Force All Layers

```bash
python3 deploy/scripts/detect_changes.py --force-all
```

---

## Issue 4: CloudFormation Stack Update Fails

### Symptoms
```
Phase: BUILD
Stack Status: UPDATE_FAILED
Reason: Resource <X> failed to update
```

### Diagnostic Steps

#### 4.1 Identify Failed Stack

```bash
# List failed stacks
aws cloudformation list-stacks \
  --stack-status-filter UPDATE_FAILED \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].{Name:StackName, Status:StackStatus, Reason:StackStatusReason}" \
  --output table
```

#### 4.2 Get Detailed Error

```bash
STACK_NAME=aura-neptune-dev

# Get failure events
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`CREATE_FAILED`]' \
  --output table
```

#### 4.3 Common CloudFormation Errors

**A. Resource Already Exists**
```
Resource <DBCluster> already exists
```

**Cause:** Trying to create resource that wasn't properly deleted

**Solution:**
```bash
# Delete the orphaned resource
aws neptune delete-db-cluster --db-cluster-identifier aura-neptune-dev

# Or import existing resource into stack
```

**B. Insufficient IAM Permissions**
```
User: arn:aws:iam::123456789012:role/CodeBuildRole is not authorized to perform: eks:CreateCluster
```

**Solution:** Update CodeBuild service role in `codebuild.yaml`:
```yaml
- Effect: Allow
  Action:
    - eks:CreateCluster  # ADD MISSING PERMISSION
    - eks:*
  Resource: '*'
```

**C. Dependency Violation**
```
Resource <VPC> cannot be deleted because it has dependencies
```

**Solution:** Delete in correct order or use `DependsOn`:
```yaml
NeptuneCluster:
  Type: AWS::Neptune::DBCluster
  DependsOn: VPC  # ADD THIS
```

**D. Resource Limit Exceeded**
```
You have reached your limit of 5 VPCs in this region
```

**Solution:**
1. Delete unused VPCs
2. Request limit increase
3. Use different region

**E. Invalid Configuration**
```
The CIDR '10.0.0.0/16' conflicts with existing VPC CIDR
```

**Solution:** Change VPC CIDR in template or parameters

**F. Resource Update Not Supported**
```
Update requires replacement but resource doesn't support it
```

**Solution:** Some resources can't be updated in-place:
```bash
# Must delete and recreate (causes downtime)
aws cloudformation delete-stack --stack-name $STACK_NAME
# Then redeploy
```

### Resolution Process

#### Step 1: Analyze Root Cause

```bash
# Get full event history
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --max-items 50 > /tmp/stack-events.json

# Search for first failure
cat /tmp/stack-events.json | jq '.StackEvents[] | select(.ResourceStatus | contains("FAILED"))'
```

#### Step 2: Fix Template or Resource

**Option A: Fix Template**
```bash
vim deploy/cloudformation/<template>.yaml
git commit -am "fix: Resolve CloudFormation error"
git push origin main
```

**Option B: Delete Failed Stack**
```bash
# Delete stuck stack
aws cloudformation delete-stack --stack-name $STACK_NAME

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME

# Redeploy
aws codebuild start-build --project-name aura-infra-deploy-dev
```

**Option C: Continue Update Rollback**
```bash
# If stack is in UPDATE_ROLLBACK_FAILED
aws cloudformation continue-update-rollback --stack-name $STACK_NAME

# Monitor progress
watch aws cloudformation describe-stacks --stack-name $STACK_NAME
```

---

## Issue 5: Build Times Out

### Symptoms
```
Phase: BUILD
Status: TIMED_OUT
Build exceeded timeout of 60 minutes
```

### Diagnostic Steps

#### 5.1 Check Build Duration

```bash
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' \
  --output text)

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Start:startTime,End:endTime,Duration:duration}'
```

#### 5.2 Identify Slow Phase

```bash
aws logs filter-log-events \
  --log-group-name /aws/codebuild/aura-infra-deploy-dev \
  --filter-pattern "Waiting for" \
  --query 'events[*].message'
```

### Common Causes

**A. EKS Cluster Creation (15-20 min)**
**B. Neptune Cluster Creation (10-15 min)**
**C. OpenSearch Domain Creation (10-15 min)**

All happening sequentially = 45+ minutes

### Resolution

#### Option 1: Increase Timeout

Edit `deploy/cloudformation/codebuild.yaml`:

```yaml
CodeBuildProject:
  Properties:
    TimeoutInMinutes: 120  # Increase from 60
    QueuedTimeoutInMinutes: 480
```

Update CodeBuild stack:
```bash
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Option 2: Deploy Layers Separately

```bash
# Deploy foundation first
bash deploy/scripts/deploy-foundation.sh

# Then data (runs in parallel with compute internally)
bash deploy/scripts/deploy-data.sh &
bash deploy/scripts/deploy-compute.sh &
wait

# Finally observability
bash deploy/scripts/deploy-observability.sh
```

---

## Issue 6: Webhook Not Triggering Builds

### Symptoms
- Push to GitHub
- No build starts automatically
- Must trigger manually

### Diagnostic Steps

#### 6.1 Check Webhook Configuration

```bash
aws codebuild batch-get-projects \
  --names aura-infra-deploy-dev \
  --query 'projects[0].webhook'
```

**Expected:** Should show webhook URL and filterGroups

#### 6.2 Check GitHub Webhooks

1. Go to GitHub repo → Settings → Webhooks
2. Look for AWS CodeBuild webhook
3. Check "Recent Deliveries" for errors

### Resolution

#### Option A: Recreate Webhook (AWS Console)

1. Go to CodeBuild → Projects → aura-infra-deploy-dev
2. Edit → Source
3. Check "Rebuild every time a code change is pushed"
4. Select branch filter: `main`
5. Save

#### Option B: Manual OAuth Connection

Requires AWS Console - cannot be fully automated via CLI.

#### Option C: Use GitHub Actions Trigger

Create `.github/workflows/trigger-codebuild.yml`:

```yaml
name: Trigger CodeBuild

on:
  push:
    branches: [main]
    paths:
      - 'deploy/cloudformation/**'

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Trigger CodeBuild
        run: |
          aws codebuild start-build \
            --project-name aura-infra-deploy-dev
```

---

## Issue 7: Layer Deploys in Wrong Order

### Symptoms
```
Error: VPC not found
But networking stack should have created it
```

### Diagnostic Steps

Check dependency resolution in `detect_changes.py`:

```python
# Foundation must be in deployment_order before data
print(deployment_order)
# Expected: ['foundation', 'data', 'compute', ...]
```

### Resolution

#### Fix Dependency Mapping

Edit `deploy/scripts/detect_changes.py`:

```python
INFRASTRUCTURE_LAYERS = {
    "data": {
        "dependencies": ["foundation"],  # ENSURE THIS IS SET
        # ...
    }
}
```

Test locally:
```bash
python3 deploy/scripts/detect_changes.py --force-all
```

---

## Issue 8: IAM Permission Errors

### Symptoms
```
User: CodeBuildServiceRole is not authorized to perform: <action>
```

### Quick Fixes

#### Check Required Permissions

```bash
# Get current role policies
aws iam list-role-policies \
  --role-name aura-codebuild-service-role-dev

# Get attached managed policies
aws iam list-attached-role-policies \
  --role-name aura-codebuild-service-role-dev
```

#### Add Missing Permission

Edit `deploy/cloudformation/codebuild.yaml`:

```yaml
CodeBuildServiceRole:
  Policies:
    - PolicyName: CodeBuildServicePolicy
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action:
              - <missing-action>  # ADD THIS
            Resource: '*'
```

Update stack:
```bash
aws cloudformation update-stack \
  --stack-name aura-codebuild-dev \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Issue 9: Cost Budget Alerts Failing

### Symptoms
```
Stack: aura-cost-alerts-dev
Status: CREATE_FAILED
Reason: Cannot create budget
```

### Diagnostic Steps

```bash
# Check budget status
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --query 'Budgets[*].{Name:BudgetName,Amount:BudgetLimit.Amount,Unit:BudgetLimit.Unit}'
```

### Common Causes

**A. Budget Already Exists**
- Budgets must have unique names
- Can't have duplicate budget

**Solution:** Delete old budget or rename:
```bash
aws budgets delete-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget-name aura-daily-budget-dev
```

**B. Incorrect SNS Topic ARN**

**Solution:** Verify topic exists:
```bash
aws sns list-topics | grep aura
```

---

## Emergency Procedures

### Procedure 1: Halt All Deployments

```bash
# Stop current build
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' \
  --output text)

aws codebuild stop-build --id $BUILD_ID
```

### Procedure 2: Complete Infrastructure Rollback

```bash
# List all stacks
STACKS=$(aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].StackName" \
  --output text)

# Delete in reverse dependency order
# (Manual - respect dependencies!)
```

### Procedure 3: Emergency Contact

1. Check #infrastructure Slack channel
2. Page on-call engineer
3. Create incident ticket

---

## Troubleshooting Checklist

When diagnosing issues:

- [ ] Check build logs in CloudWatch
- [ ] Check CloudFormation events
- [ ] Verify IAM permissions
- [ ] Test change detection locally
- [ ] Validate templates with cfn-lint
- [ ] Check AWS service limits
- [ ] Review recent git commits
- [ ] Check AWS service health dashboard

---

## Common Error Messages Reference

| Error Message | Likely Cause | Quick Fix |
|--------------|--------------|-----------|
| `No changes detected` | File not in layer mapping | Update detect_changes.py |
| `cfn-lint failed` | Template syntax error | Run cfn-lint locally |
| `Resource already exists` | Stack not fully deleted | Delete orphaned resource |
| `User not authorized` | Missing IAM permission | Update CodeBuild role |
| `Timeout exceeded` | Operation too slow | Increase timeout |
| `Webhook not configured` | GitHub connection issue | Recreate webhook |
| `Budget already exists` | Duplicate budget | Delete existing budget |
| `CIDR conflict` | VPC overlap | Change VPC CIDR |

---

## Getting Additional Help

1. **Check logs:** CloudWatch Logs for build details
2. **Check events:** CloudFormation events for stack errors
3. **Run locally:** Test scripts and detection locally
4. **Search docs:** AWS documentation and forums
5. **Contact team:** #infrastructure Slack channel

---

**Document Version:** 1.0
**Last Updated:** 2025-11-11
**Maintained By:** Platform Engineering Team
