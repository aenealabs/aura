# Runbook: Initial CodeBuild Setup

**Purpose:** First-time setup of the modular CI/CD pipeline for Project Aura infrastructure

**Audience:** DevOps Engineers, Platform Team

**Estimated Time:** 30-45 minutes

**Prerequisites:**
- AWS CLI installed and configured
- AWS Account with Administrator access
- Git repository with Project Aura code
- Valid email address for alerts

---

## Overview

This runbook walks through setting up the CodeBuild pipeline that will automate deployment of all Project Aura infrastructure using the modular, layer-based approach.

## Pre-Flight Checklist

- [ ] AWS CLI version 2.x or higher installed
- [ ] AWS credentials configured (`aws sts get-caller-identity` works)
- [ ] GitHub repository accessible
- [ ] Email address ready for notifications
- [ ] Region selected (default: us-east-1)

## Step 1: Verify Prerequisites

### 1.1 Check AWS CLI Version

```bash
aws --version
# Expected: aws-cli/2.x.x or higher
```

### 1.2 Verify AWS Credentials

```bash
aws sts get-caller-identity
```

**Expected Output:**
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-user"
}
```

✅ **Checkpoint:** Account ID matches your AWS account

### 1.3 Set Environment Variables

```bash
export AWS_REGION=us-east-1
export PROJECT_NAME=aura
export ENVIRONMENT=dev
export ALERT_EMAIL=your-email@example.com
export GITHUB_REPO=https://github.com/aenealabs/aura
export GITHUB_BRANCH=main
```

**Note:** Save these to `~/.bashrc` or `~/.zshrc` for future use

## Step 2: Validate CloudFormation Templates

### 2.1 Install cfn-lint

```bash
pip install cfn-lint
```

### 2.2 Validate All Templates

```bash
cd /path/to/project-aura
cfn-lint deploy/cloudformation/*.yaml --ignore-checks W3002
```

**Expected Output:**
```
No errors found in templates
```

❌ **If Errors Found:**
1. Review error messages
2. Fix template issues
3. Re-run validation
4. Do not proceed until validation passes

### 2.3 AWS CloudFormation Validation

```bash
aws cloudformation validate-template \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --region $AWS_REGION
```

✅ **Checkpoint:** Template validation succeeds

## Step 3: Create SSM Parameter for Alert Email

This parameter is used by all stacks for notifications.

```bash
aws ssm put-parameter \
  --name "/${PROJECT_NAME}/${ENVIRONMENT}/alert-email" \
  --type String \
  --value "$ALERT_EMAIL" \
  --description "Alert email for infrastructure deployments" \
  --tags "Key=Project,Value=${PROJECT_NAME}" "Key=Environment,Value=${ENVIRONMENT}" \
  --region $AWS_REGION
```

### Verify Parameter

```bash
aws ssm get-parameter \
  --name "/${PROJECT_NAME}/${ENVIRONMENT}/alert-email" \
  --query 'Parameter.Value' \
  --output text \
  --region $AWS_REGION
```

**Expected Output:** Your email address

✅ **Checkpoint:** Email parameter stored correctly

## Step 4: Deploy CodeBuild Stack

### 4.1 Create Stack

```bash
aws cloudformation create-stack \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --template-body file://deploy/cloudformation/codebuild.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
    ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
    ParameterKey=GitHubRepository,ParameterValue=$GITHUB_REPO \
    ParameterKey=GitHubBranch,ParameterValue=$GITHUB_BRANCH \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=Project,Value=$PROJECT_NAME \
    Key=Environment,Value=$ENVIRONMENT \
    Key=ManagedBy,Value=CloudFormation \
  --region $AWS_REGION
```

### 4.2 Monitor Stack Creation

```bash
# Watch stack events in real-time
aws cloudformation describe-stack-events \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --max-items 20 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table \
  --region $AWS_REGION
```

**Or use wait command:**

```bash
aws cloudformation wait stack-create-complete \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --region $AWS_REGION

echo "Stack creation completed!"
```

⏱️ **Expected Duration:** 3-5 minutes

### 4.3 Verify Stack Creation

```bash
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region $AWS_REGION
```

**Expected Output:** `CREATE_COMPLETE`

✅ **Checkpoint:** Stack status is CREATE_COMPLETE

## Step 5: Retrieve Stack Outputs

### 5.1 Get All Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs' \
  --output table \
  --region $AWS_REGION
```

### 5.2 Save Important Values

```bash
# CodeBuild Project Name
export CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`CodeBuildProjectName`].OutputValue' \
  --output text \
  --region $AWS_REGION)

echo "CodeBuild Project: $CODEBUILD_PROJECT"

# Artifacts Bucket
export ARTIFACTS_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`BuildArtifactsBucketName`].OutputValue' \
  --output text \
  --region $AWS_REGION)

echo "Artifacts Bucket: $ARTIFACTS_BUCKET"

# SNS Topic ARN
export SNS_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`BuildNotificationTopicArn`].OutputValue' \
  --output text \
  --region $AWS_REGION)

echo "SNS Topic: $SNS_TOPIC"
```

✅ **Checkpoint:** All outputs retrieved successfully

## Step 6: Confirm SNS Email Subscription

### 6.1 Check Your Email

Look for an email from AWS Notifications with subject:
**"AWS Notification - Subscription Confirmation"**

### 6.2 Click Confirmation Link

Click the **"Confirm subscription"** link in the email.

### 6.3 Verify Subscription

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn $SNS_TOPIC \
  --query 'Subscriptions[*].[Protocol,Endpoint,SubscriptionArn]' \
  --output table \
  --region $AWS_REGION
```

**Expected Output:**
```
-----------------------------------------
|       ListSubscriptionsByTopic        |
+-------+---------------------------+---+
| email | your-email@example.com    | arn:aws:sns:... |
+-------+---------------------------+---+
```

✅ **Checkpoint:** Subscription status is confirmed (not "PendingConfirmation")

## Step 7: Test Change Detection Locally

Before triggering the first build, test the change detection script.

### 7.1 Run Change Detection

```bash
python3 deploy/scripts/detect_changes.py --force-all
```

**Expected Output:**
```
============================================================
Infrastructure Change Detection
============================================================

Force flag set - deploying all layers

============================================================
Deployment Plan
============================================================

Layers to deploy (5):
  1. Foundation Layer: VPC, Security Groups, IAM Roles [✓ CHANGED]
  2. Data Layer: Databases and Storage [✓ CHANGED]
  3. Compute Layer: EKS Cluster and Node Groups [✓ CHANGED]
  4. Application Layer: Application-specific Infrastructure [✓ CHANGED]
  5. Observability Layer: Secrets, Monitoring, Alerts [✓ CHANGED]
============================================================

Deployment plan written to: /tmp/deployment-plan.json
```

✅ **Checkpoint:** Script runs without errors and detects all layers

## Step 8: Trigger First Infrastructure Deployment

### 8.1 Start Build

```bash
aws codebuild start-build \
  --project-name $CODEBUILD_PROJECT \
  --environment-variables-override \
    name=ENVIRONMENT,value=$ENVIRONMENT,type=PLAINTEXT \
    name=PROJECT_NAME,value=$PROJECT_NAME,type=PLAINTEXT \
  --region $AWS_REGION
```

**Save Build ID:**

```bash
BUILD_ID=$(aws codebuild start-build \
  --project-name $CODEBUILD_PROJECT \
  --query 'build.id' \
  --output text \
  --region $AWS_REGION)

echo "Build ID: $BUILD_ID"
```

### 8.2 Monitor Build Progress

**Option 1: Watch CloudWatch Logs (Real-time)**

```bash
aws logs tail /aws/codebuild/${CODEBUILD_PROJECT} \
  --follow \
  --since 1m \
  --region $AWS_REGION
```

**Option 2: Check Build Status**

```bash
watch -n 10 "aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --query 'builds[0].[buildStatus,currentPhase]' \
  --output table \
  --region $AWS_REGION"
```

**Option 3: AWS Console**

Navigate to: https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT/history

⏱️ **Expected Duration:** 45-60 minutes (full infrastructure deployment)

### 8.3 Build Phases

Monitor for these phases:
1. ✅ **SUBMITTED** - Build queued
2. ✅ **PROVISIONING** - Container starting
3. ✅ **DOWNLOAD_SOURCE** - Pulling code
4. ✅ **INSTALL** - Installing dependencies (cfn-lint, boto3)
5. ✅ **PRE_BUILD** - Validating templates, detecting changes
6. ✅ **BUILD** - Deploying infrastructure layers
7. ✅ **POST_BUILD** - Validation, outputs
8. ✅ **COMPLETED** - Success!

### 8.4 Check Build Result

```bash
aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --query 'builds[0].buildStatus' \
  --output text \
  --region $AWS_REGION
```

**Expected Output:** `SUCCEEDED`

✅ **Checkpoint:** Build status is SUCCEEDED

## Step 9: Verify Infrastructure Deployment

### 9.1 List All Created Stacks

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, '${PROJECT_NAME}-')].{Name:StackName, Status:StackStatus, Created:CreationTime}" \
  --output table \
  --region $AWS_REGION
```

**Expected Stacks:**
- `aura-networking-dev`
- `aura-security-dev`
- `aura-iam-dev`
- `aura-dynamodb-dev`
- `aura-s3-dev`
- `aura-neptune-dev`
- `aura-opensearch-dev`
- `aura-eks-dev`
- `aura-secrets-dev`
- `aura-monitoring-dev`
- `aura-cost-alerts-dev`

✅ **Checkpoint:** All expected stacks exist with CREATE_COMPLETE status

### 9.2 Get Key Outputs

```bash
# VPC ID
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-networking-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text \
  --region $AWS_REGION

# EKS Cluster Name
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-eks-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
  --output text \
  --region $AWS_REGION

# Neptune Endpoint
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-neptune-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterEndpoint`].OutputValue' \
  --output text \
  --region $AWS_REGION

# OpenSearch Endpoint
aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-opensearch-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`DomainEndpoint`].OutputValue' \
  --output text \
  --region $AWS_REGION
```

✅ **Checkpoint:** All key resources return valid endpoints

## Step 10: Configure kubectl (Optional)

If you need to interact with the EKS cluster:

```bash
# Get cluster name
CLUSTER_NAME=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-eks-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
  --output text \
  --region $AWS_REGION)

# Update kubeconfig
aws eks update-kubeconfig \
  --name $CLUSTER_NAME \
  --region $AWS_REGION

# Verify connectivity
kubectl get nodes
```

**Expected Output:**
```
NAME                          STATUS   ROLES    AGE   VERSION
ip-10-0-3-xxx.ec2.internal    Ready    <none>   5m    v1.28.x
ip-10-0-4-xxx.ec2.internal    Ready    <none>   5m    v1.28.x
```

✅ **Checkpoint:** kubectl can connect to cluster and shows nodes

## Step 11: Configure GitHub Webhook (Optional)

To enable automatic builds on git push:

### 11.1 Get GitHub Personal Access Token

1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` and `admin:repo_hook` scopes
3. Save token securely

### 11.2 Create Webhook Connection

```bash
# Store GitHub token in Secrets Manager
aws secretsmanager create-secret \
  --name ${PROJECT_NAME}/${ENVIRONMENT}/github-token \
  --secret-string '{"token":"YOUR_GITHUB_TOKEN"}' \
  --region $AWS_REGION

# Update CodeBuild project to use webhook (requires AWS Console or additional CLI commands)
```

**Note:** Full webhook setup requires OAuth connection in AWS Console:
https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT/edit/source

## Step 12: Test Change Detection Workflow

Make a small change to verify the system works:

### 12.1 Create Test Change

```bash
# Edit a CloudFormation template (add a comment)
echo "# Test change $(date)" >> deploy/cloudformation/networking.yaml

# Commit and push
git add deploy/cloudformation/networking.yaml
git commit -m "Test: Verify modular deployment"
git push origin main
```

### 12.2 Watch for Build Trigger

```bash
# List recent builds
aws codebuild list-builds-for-project \
  --project-name $CODEBUILD_PROJECT \
  --max-items 5 \
  --region $AWS_REGION
```

### 12.3 Verify Only Affected Layers Deploy

Check build logs - should show:
```
Foundation: DEPLOYING (networking.yaml changed)
Data: SKIPPED (no changes)
Compute: SKIPPED (no changes)
Application: SKIPPED (no changes)
Observability: SKIPPED (no changes)
```

✅ **Checkpoint:** Only Foundation layer deployed

## Rollback Procedures

### If CodeBuild Stack Creation Fails

```bash
# Check events
aws cloudformation describe-stack-events \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --max-items 20 \
  --region $AWS_REGION

# Delete stack and retry
aws cloudformation delete-stack \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --region $AWS_REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name ${PROJECT_NAME}-codebuild-${ENVIRONMENT} \
  --region $AWS_REGION

# Fix issue and retry Step 4
```

### If Infrastructure Deployment Fails

```bash
# Check which stack failed
aws cloudformation list-stacks \
  --stack-status-filter CREATE_FAILED UPDATE_FAILED ROLLBACK_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, '${PROJECT_NAME}-')]" \
  --output table \
  --region $AWS_REGION

# Get failure reason
aws cloudformation describe-stack-events \
  --stack-name <FAILED_STACK_NAME> \
  --max-items 20 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' \
  --output table \
  --region $AWS_REGION

# Delete failed stack
aws cloudformation delete-stack \
  --stack-name <FAILED_STACK_NAME> \
  --region $AWS_REGION

# Fix issue in template and re-trigger build
```

## Success Criteria

- [x] CodeBuild stack deployed successfully
- [x] SNS email subscription confirmed
- [x] First build completed successfully
- [x] All infrastructure stacks deployed
- [x] Key endpoints accessible
- [x] Change detection works correctly

## Troubleshooting

### Issue: cfn-lint not found

**Solution:**
```bash
pip install --upgrade cfn-lint
```

### Issue: Permission denied errors

**Solution:** Ensure AWS credentials have Administrator or PowerUser access

### Issue: Build times out

**Solution:** Increase timeout in codebuild.yaml:
```yaml
TimeoutInMinutes: 120  # Increase from 60
```

### Issue: Email notifications not received

**Solution:**
1. Check spam folder
2. Verify SNS subscription status
3. Re-confirm subscription

## Next Steps

After successful setup:

1. **Read:** [02-routine-deployments.md](./02-routine-deployments.md)
2. **Configure:** Set up cost alerts and monitoring
3. **Document:** Save environment variables for team
4. **Train:** Share runbooks with team members

## Related Documentation

- [MODULAR_DEPLOYMENT.md](../MODULAR_DEPLOYMENT.md) - Complete deployment guide
- [03-troubleshooting.md](./03-troubleshooting.md) - Troubleshooting guide
- [04-phase2-migration.md](./04-phase2-migration.md) - Team scaling guide

---

**Document Version:** 1.0
**Last Updated:** 2025-11-11
**Maintained By:** Platform Engineering Team
