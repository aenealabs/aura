# AWS Account Migration Guide

**Project Aura - Org Management Account to Dedicated Workload Account**

**Version:** 1.0
**Last Updated:** January 2026
**Target Audience:** Platform Administrators, DevOps Engineers

---

## Executive Summary

This guide documents the migration of Project Aura dev workloads from the AWS Organization Management Account (123456789012) to a new dedicated workload account.

### Why Migrate?

| Risk | Current State | After Migration |
|------|---------------|-----------------|
| **SCP Bypass** | SCPs don't apply to management account | SCPs fully enforced |
| **Blast Radius** | Dev experiments can affect org controls | Isolated dev account |
| **Audit Trail** | Mixed workload + org management events | Clear separation |
| **CMMC Compliance** | Violates separation of duties | Properly isolated |
| **GovCloud Prep** | Inconsistent with GovCloud best practices | Aligned pattern |

### Migration Scope

| Category | Count | Migration Approach |
|----------|-------|-------------------|
| CloudFormation Stacks | 86 | Redeploy via CodeBuild |
| CodeBuild Projects | 16 | CloudFormation deploy |
| EKS Cluster | 1 (3 node groups) | Fresh cluster + app deploy |
| Neptune Cluster | 1 | Snapshot copy |
| OpenSearch Domain | 1 | Snapshot to S3 |
| DynamoDB Tables | 12+ | Export/Import via S3 |
| S3 Buckets | 8+ | Cross-account sync |
| ECR Repositories | 10+ | Image replication |
| Secrets Manager | 15+ | Recreate with values |
| SSM Parameters | 50+ | Selective migration |
| Lambda Functions | 20+ | Deploy via CloudFormation |
| IAM Roles | 40+ | Deploy via CloudFormation |

---

## Migration Timeline

### Overview (4-6 Weeks)

```
Week 1: Preparation
├── Day 1-2: Create target account, configure SSO
├── Day 3-4: Deploy bootstrap infrastructure
└── Day 5: Test cross-account access

Week 2: Data Layer Migration
├── Day 1-2: Neptune snapshot + copy
├── Day 3: OpenSearch snapshot
├── Day 4-5: DynamoDB export/import
└── Parallel: S3 bucket sync

Week 3: Infrastructure Redeployment
├── Day 1: Foundation layer (VPC, IAM, Security)
├── Day 2: Data layer (Neptune restore, OpenSearch)
├── Day 3: Compute layer (EKS cluster)
└── Day 4-5: Application layer (Bedrock, ECR)

Week 4: Application Migration
├── Day 1-2: Deploy Kubernetes workloads
├── Day 3: Integration testing
├── Day 4: Performance validation
└── Day 5: Cutover preparation

Week 5: Cutover & Validation
├── Day 1: DNS cutover (if applicable)
├── Day 2-3: Validation testing
├── Day 4: Monitoring confirmation
└── Day 5: Source cleanup planning

Week 6: Cleanup (Optional)
├── Day 1-5: Gradual source resource deletion
└── Ongoing: Cost monitoring
```

---

## Phase 0: Pre-Migration Setup

### 0.1 Prerequisites Checklist

- [ ] AWS CLI v2.15+ installed
- [ ] jq installed (`brew install jq` or `apt install jq`)
- [ ] Docker/Podman available for ECR migration
- [ ] AWS SSO configured for Management Account
- [ ] Repository cloned with latest code
- [ ] Sufficient IAM permissions (AdministratorAccess)

### 0.2 Create Migration Artifacts Directory

```bash
mkdir -p migration-artifacts
cd /path/to/aura
```

### 0.3 Export Current State

```bash
# Set source account profile
export AWS_PROFILE=aura-admin
export SOURCE_ACCOUNT_ID=123456789012

# Export inventory
./deploy/scripts/migration/migrate-data-services.sh all prepare
./deploy/scripts/migration/migrate-cicd-pipeline.sh all prepare
```

---

## Phase 1: New Account Setup

### 1.1 Create Workload Account

```bash
# From Management Account
export AWS_PROFILE=aura-admin

# Create account
aws organizations create-account \
  --email "aura-dev-workload@aenealabs.com" \
  --account-name "aenealabs-dev-workload" \
  --iam-user-access-to-billing DENY

# Wait for creation
sleep 120

# Get new account ID
NEW_ACCOUNT_ID=$(aws organizations list-accounts \
  --query "Accounts[?Name=='aenealabs-dev-workload'].Id" \
  --output text)
echo "New Account ID: $NEW_ACCOUNT_ID"
```

### 1.2 Move to Workloads OU

```bash
# Get Workloads OU ID
WORKLOADS_OU=$(aws ssm get-parameter \
  --name "/aura/global/workloads-ou-id" \
  --query 'Parameter.Value' \
  --output text 2>/dev/null || \
  aws organizations list-organizational-units-for-parent \
    --parent-id $(aws organizations list-roots --query 'Roots[0].Id' --output text) \
    --query "OrganizationalUnits[?Name=='Workloads'].Id" \
    --output text)

# Get account's current parent (root)
ROOT_ID=$(aws organizations list-roots --query 'Roots[0].Id' --output text)

# Move account to Workloads OU
aws organizations move-account \
  --account-id "$NEW_ACCOUNT_ID" \
  --source-parent-id "$ROOT_ID" \
  --destination-parent-id "$WORKLOADS_OU"
```

### 1.3 Configure IAM Identity Center

Via AWS Console (Management Account):
1. Navigate to **IAM Identity Center**
2. Select **AWS accounts** in left nav
3. Check the new `aenealabs-dev-workload` account
4. Click **Assign users or groups**
5. Select your admin user/group
6. Select `AdministratorAccess` permission set
7. Click **Submit**

### 1.4 Configure AWS CLI Profile

```bash
# Add to ~/.aws/config
cat >> ~/.aws/config << EOF

[profile aura-admin-target]
sso_session = aenealabs
sso_account_id = $NEW_ACCOUNT_ID
sso_role_name = AdministratorAccess
region = us-east-1
output = json
EOF

# Login to new account
aws sso login --profile aura-admin-target

# Verify access
aws sts get-caller-identity --profile aura-admin-target
```

### 1.5 Deploy Bootstrap Infrastructure

```bash
export AWS_PROFILE=aura-admin-target

# Get SSO Admin Role ARN
ADMIN_ROLE_ARN=$(aws iam list-roles \
  --query "Roles[?contains(RoleName, 'AWSReservedSSO') && contains(RoleName, 'Admin')].Arn" \
  --output text | head -1)

# Deploy account bootstrap
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-dev \
  --parameter-overrides \
      Environment=dev \
      AdminRoleArn="$ADMIN_ROLE_ARN" \
      AlertEmail="alerts-dev@aenealabs.com" \
      CodeConnectionsArn="arn:aws:codeconnections:us-east-1:${NEW_ACCOUNT_ID}:connection/PLACEHOLDER" \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy migration bootstrap (cross-account access)
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-migration-bootstrap.yaml \
  --stack-name aura-migration-bootstrap \
  --parameter-overrides \
      Environment=dev \
      SourceAccountId=123456789012 \
      AdminRoleArn="$ADMIN_ROLE_ARN" \
      AlertEmail="migration-alerts@aenealabs.com" \
  --capabilities CAPABILITY_NAMED_IAM
```

### 1.6 Create GitHub CodeConnections

Via AWS Console (Target Account):
1. Navigate to **Developer Tools** > **Settings** > **Connections**
2. Click **Create connection**
3. Select **GitHub**
4. Name: `aura-github-dev`
5. Complete GitHub authorization
6. Copy the connection ARN

```bash
# Store CodeConnections ARN
aws ssm put-parameter \
  --name "/aura/dev/codeconnections-arn" \
  --type "String" \
  --value "arn:aws:codeconnections:us-east-1:${NEW_ACCOUNT_ID}:connection/YOUR_ID" \
  --overwrite

# Update account-bootstrap stack with correct ARN
aws cloudformation update-stack \
  --stack-name aura-account-bootstrap-dev \
  --use-previous-template \
  --parameters \
      ParameterKey=Environment,UsePreviousValue=true \
      ParameterKey=AdminRoleArn,UsePreviousValue=true \
      ParameterKey=AlertEmail,UsePreviousValue=true \
      ParameterKey=CodeConnectionsArn,ParameterValue="arn:aws:codeconnections:..." \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Phase 2: Data Migration

### 2.1 Neptune Migration

```bash
# Set environment variables
export SOURCE_PROFILE=aura-admin
export TARGET_PROFILE=aura-admin-target
export ENVIRONMENT=dev

# Step 1: Create snapshot in source account
./deploy/scripts/migration/migrate-data-services.sh neptune prepare

# Step 2: Copy snapshot to target account (takes 15-30 minutes)
./deploy/scripts/migration/migrate-data-services.sh neptune migrate

# Step 3: Verify snapshot in target account
./deploy/scripts/migration/migrate-data-services.sh neptune verify
```

### 2.2 OpenSearch Migration

OpenSearch requires manual steps due to VPC restrictions:

```bash
# Step 1: Register S3 snapshot repository in SOURCE domain
# Via Kibana Dev Tools or signed HTTP request:

PUT _snapshot/migration-repo
{
  "type": "s3",
  "settings": {
    "bucket": "aura-migration-TARGET_ACCOUNT_ID-dev",
    "region": "us-east-1",
    "role_arn": "arn:aws:iam::SOURCE_ACCOUNT_ID:role/aura-opensearch-snapshot-role-dev"
  }
}

# Step 2: Create snapshot
PUT _snapshot/migration-repo/migration-snapshot-20260110
{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}

# Step 3: After deploying OpenSearch in target account, register same repo
# Then restore:
POST _snapshot/migration-repo/migration-snapshot-20260110/_restore
{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}
```

### 2.3 DynamoDB Migration

```bash
# Prepare (creates backups)
./deploy/scripts/migration/migrate-data-services.sh dynamodb prepare

# Migrate (exports to S3)
./deploy/scripts/migration/migrate-data-services.sh dynamodb migrate

# After infrastructure is deployed, import via CloudFormation or AWS Console
```

**Note:** DynamoDB import requires:
1. Point-in-Time Recovery (PITR) enabled on source tables
2. OR Use AWS Backup for cross-account restore

### 2.4 S3 Bucket Migration

```bash
# Prepare (lists buckets and sizes)
./deploy/scripts/migration/migrate-data-services.sh s3 prepare

# Migrate (syncs data to target buckets)
./deploy/scripts/migration/migrate-data-services.sh s3 migrate

# Verify
./deploy/scripts/migration/migrate-data-services.sh s3 verify
```

---

## Phase 3: Infrastructure Redeployment

### 3.1 Deploy CI/CD Pipeline

```bash
export AWS_PROFILE=aura-admin-target

# Step 1: Migrate ECR images
./deploy/scripts/migration/migrate-cicd-pipeline.sh ecr migrate

# Step 2: Deploy bootstrap CodeBuild project
aws cloudformation deploy \
  --template-file deploy/cloudformation/codebuild-bootstrap.yaml \
  --stack-name aura-codebuild-bootstrap-dev \
  --parameter-overrides Environment=dev \
  --capabilities CAPABILITY_NAMED_IAM

# Step 3: Run bootstrap to deploy all CodeBuild projects
aws codebuild start-build --project-name aura-bootstrap-deploy-dev

# Wait for completion (5-10 minutes)
aws codebuild batch-get-builds \
  --ids $(aws codebuild list-builds-for-project \
    --project-name aura-bootstrap-deploy-dev \
    --max-items 1 --query 'ids[0]' --output text) \
  --query 'builds[0].buildStatus'
```

### 3.2 Deploy Infrastructure Layers

```bash
# Deploy Foundation Layer (VPC, IAM, Security)
aws codebuild start-build --project-name aura-foundation-deploy-dev

# Wait for completion, then...

# Deploy Data Layer (Neptune from snapshot, OpenSearch)
aws codebuild start-build \
  --project-name aura-data-deploy-dev \
  --environment-variables-override \
    name=NEPTUNE_SNAPSHOT_ID,value=aura-neptune-dev-migrated

# Wait, then...

# Deploy Compute Layer (EKS)
aws codebuild start-build --project-name aura-compute-deploy-dev

# Deploy Application Layer
aws codebuild start-build --project-name aura-application-deploy-dev

# Deploy Observability Layer
aws codebuild start-build --project-name aura-observability-deploy-dev

# Deploy Serverless Layer
aws codebuild start-build --project-name aura-serverless-deploy-dev

# Deploy Sandbox Layer
aws codebuild start-build --project-name aura-sandbox-deploy-dev

# Deploy Security Layer
aws codebuild start-build --project-name aura-security-deploy-dev
```

### 3.3 Verify Stack Deployment

```bash
# List all deployed stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `aura`)].{Name:StackName,Status:StackStatus}' \
  --output table

# Compare with source
SOURCE_COUNT=$(aws cloudformation list-stacks \
  --profile aura-admin \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'length(StackSummaries[?contains(StackName, `aura`)])' \
  --output text)

TARGET_COUNT=$(aws cloudformation list-stacks \
  --profile aura-admin-target \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'length(StackSummaries[?contains(StackName, `aura`)])' \
  --output text)

echo "Source stacks: $SOURCE_COUNT"
echo "Target stacks: $TARGET_COUNT"
```

---

## Phase 4: Application Migration

### 4.1 Deploy Kubernetes Workloads

```bash
# Update kubeconfig for new cluster
aws eks update-kubeconfig \
  --name aura-cluster-dev \
  --region us-east-1 \
  --profile aura-admin-target

# Generate environment-specific overlays
./deploy/scripts/generate-k8s-config.sh dev us-east-1

# Apply Kubernetes manifests
kubectl apply -k deploy/kubernetes/aura-api/overlays/dev/
kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/dev/
kubectl apply -k deploy/kubernetes/memory-service/overlays/dev/

# Verify pods
kubectl get pods -n aura-dev
```

### 4.2 Run Integration Tests

```bash
# Trigger integration test CodeBuild
aws codebuild start-build --project-name aura-integration-test-dev

# Or run locally
./deploy/scripts/run-integration-tests.sh dev
```

---

## Phase 5: Cutover & Validation

### 5.1 Validation Checklist

#### Infrastructure Validation
- [ ] All 8 infrastructure layers deployed successfully
- [ ] Neptune cluster accessible and responsive
- [ ] OpenSearch domain healthy with restored indices
- [ ] DynamoDB tables with correct item counts
- [ ] S3 buckets with migrated data
- [ ] EKS cluster with healthy node groups
- [ ] ECR repositories with required images

#### Application Validation
- [ ] All Kubernetes pods running
- [ ] API health checks passing
- [ ] Agent orchestrator operational
- [ ] Memory service connected to Neptune
- [ ] Vector search connected to OpenSearch

#### Security Validation
- [ ] CloudTrail logging enabled
- [ ] GuardDuty detector active
- [ ] Security alerts SNS topic configured
- [ ] KMS keys with rotation enabled
- [ ] IAM roles with correct permissions

#### Monitoring Validation
- [ ] CloudWatch alarms in OK state
- [ ] Log groups receiving data
- [ ] Metrics publishing correctly
- [ ] Cost alerts configured

### 5.2 Cutover Steps

1. **Freeze Source Environment**
   ```bash
   # Prevent new deployments
   aws codebuild update-project \
     --name aura-coordinator-deploy-dev \
     --environment-variables name=DEPLOYMENT_FROZEN,value=true \
     --profile aura-admin
   ```

2. **Final Data Sync**
   ```bash
   # Sync any changes since initial migration
   ./deploy/scripts/migration/migrate-data-services.sh s3 migrate
   ```

3. **Update DNS (if applicable)**
   ```bash
   # If using Route 53 for internal DNS
   # Update records to point to new account resources
   ```

4. **Switch Application Access**
   - Update any external integrations to use new endpoints
   - Update GitHub CodeConnections if needed

---

## Phase 6: Cleanup

### 6.1 Source Account Cleanup Plan

**WAIT AT LEAST 2 WEEKS** before deleting source resources to ensure:
- No hidden dependencies
- Rollback capability
- Complete data verification

```bash
# After validation period, delete non-critical resources first
export AWS_PROFILE=aura-admin

# 1. Delete test/temporary stacks
aws cloudformation delete-stack --stack-name aura-test-env-state-dev

# 2. Delete application stacks (data preserved in target)
aws cloudformation delete-stack --stack-name aura-application-dev

# 3. LAST: Delete data layer (only after confirming target data)
# aws cloudformation delete-stack --stack-name aura-neptune-dev
# aws cloudformation delete-stack --stack-name aura-opensearch-dev
```

### 6.2 Retain in Management Account

Keep these resources in the Management Account:
- AWS Organizations configuration
- SCPs and organization policies
- IAM Identity Center configuration
- CloudTrail organization trail (if configured)

---

## Rollback Procedures

### Full Rollback (Pre-Cutover)

If issues occur before cutover:

```bash
# Source environment is still active
# Simply stop using target account and delete stacks

export AWS_PROFILE=aura-admin-target

# Delete all stacks in reverse order
for stack in security sandbox serverless observability application compute data foundation; do
  aws cloudformation delete-stack --stack-name "aura-${stack}-dev" || true
done
```

### Partial Rollback (Post-Cutover)

If issues occur after cutover:

1. **Revert DNS** to source endpoints
2. **Unfreeze source deployments**
3. **Investigate target issues** before retrying

---

## Troubleshooting

### Common Issues

#### Cross-Account Access Denied

```bash
# Verify cross-account role exists
aws iam get-role \
  --role-name aura-cross-account-migration-dev \
  --profile aura-admin-target

# Test assume role from source
aws sts assume-role \
  --role-arn "arn:aws:iam::${TARGET_ACCOUNT_ID}:role/aura-cross-account-migration-dev" \
  --role-session-name migration-test \
  --external-id "aura-migration-dev" \
  --profile aura-admin
```

#### Neptune Snapshot Copy Fails

```bash
# Check if snapshot is shared correctly
aws neptune describe-db-cluster-snapshot-attributes \
  --db-cluster-snapshot-identifier "your-snapshot-id" \
  --profile aura-admin
```

#### KMS Key Access Denied

```bash
# Verify key policy allows cross-account access
aws kms get-key-policy \
  --key-id "alias/aura/dev/migration" \
  --policy-name default \
  --profile aura-admin-target
```

#### CodeBuild GitHub Connection Failed

1. Verify CodeConnections is in "Available" status
2. Reauthorize GitHub if pending
3. Ensure SSM parameter `/aura/dev/codeconnections-arn` is correct

---

## Appendix

### Resource Naming Changes

| Resource Type | Source Account | Target Account |
|---------------|----------------|----------------|
| S3 Buckets | `aura-*-123456789012-dev` | `aura-*-{NEW_ID}-dev` |
| Neptune | `aura-neptune-dev` | `aura-neptune-dev` (same) |
| OpenSearch | `aura-dev` | `aura-dev` (same) |
| EKS Cluster | `aura-cluster-dev` | `aura-cluster-dev` (same) |
| IAM Roles | Account-specific ARNs | New account ARNs |

### Migration Scripts Reference

| Script | Purpose |
|--------|---------|
| `migrate-data-services.sh` | Neptune, OpenSearch, DynamoDB, S3 migration |
| `migrate-cicd-pipeline.sh` | ECR, Secrets, SSM, CodeBuild migration |

### Support Contacts

- **Platform Team:** platform@aenealabs.com
- **Security Team:** security@aenealabs.com

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | January 2026 | Initial migration guide |
