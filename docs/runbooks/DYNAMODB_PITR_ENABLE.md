# DynamoDB Point-in-Time Recovery (PITR) Enable Runbook

## Overview

This runbook documents how to enable Point-in-Time Recovery (PITR) on existing DynamoDB tables when CloudFormation stack updates fail.

**Problem:** CloudFormation cannot modify the `PointInTimeRecoveryEnabled` property on existing DynamoDB tables. Attempting to enable PITR via stack update results in:

```
UPDATE_ROLLBACK_IN_PROGRESS
The following resource(s) failed to update: [Table1, Table2, ...]
```

**Solution:** Enable PITR via AWS CLI before redeploying the CloudFormation stack.

---

## Prerequisites

- AWS CLI configured with appropriate credentials
- IAM permissions: `dynamodb:UpdateContinuousBackups`, `dynamodb:DescribeContinuousBackups`
- Access to the AWS account where tables are deployed

---

## Affected Tables (aura-dynamodb-dev stack)

| Table Name | Purpose |
|------------|---------|
| `aura-cost-tracking-dev` | Cost tracking and budget data |
| `aura-user-sessions-dev` | User session management |
| `aura-codegen-jobs-dev` | Code generation job tracking |
| `aura-ingestion-jobs-dev` | Git ingestion pipeline jobs |
| `aura-codebase-metadata-dev` | Repository metadata |
| `aura-platform-settings-dev` | Platform configuration |
| `aura-anomalies-dev` | Anomaly detection records |

---

## Procedure

### Step 1: Verify Current PITR Status

Check the current PITR status for each table:

```bash
export AWS_PROFILE=aura-admin
export AWS_REGION=us-east-1

# Check single table
aws dynamodb describe-continuous-backups \
  --table-name aura-cost-tracking-dev \
  --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
  --output text

# Check all tables
for TABLE in aura-cost-tracking-dev aura-user-sessions-dev aura-codegen-jobs-dev \
             aura-ingestion-jobs-dev aura-codebase-metadata-dev aura-platform-settings-dev \
             aura-anomalies-dev; do
  STATUS=$(aws dynamodb describe-continuous-backups \
    --table-name "$TABLE" \
    --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
    --output text 2>/dev/null || echo "TABLE_NOT_FOUND")
  echo "$TABLE: $STATUS"
done
```

Expected output if PITR is disabled:
```
aura-cost-tracking-dev: DISABLED
aura-user-sessions-dev: DISABLED
...
```

### Step 2: Enable PITR on All Tables

Run the following script to enable PITR:

```bash
export AWS_PROFILE=aura-admin
export AWS_REGION=us-east-1

TABLES=(
  "aura-cost-tracking-dev"
  "aura-user-sessions-dev"
  "aura-codegen-jobs-dev"
  "aura-ingestion-jobs-dev"
  "aura-codebase-metadata-dev"
  "aura-platform-settings-dev"
  "aura-anomalies-dev"
)

echo "Enabling PITR on DynamoDB tables..."
for TABLE in "${TABLES[@]}"; do
  echo "  Enabling PITR for $TABLE..."
  aws dynamodb update-continuous-backups \
    --table-name "$TABLE" \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
    --region $AWS_REGION

  if [ $? -eq 0 ]; then
    echo "    ✓ PITR enabled for $TABLE"
  else
    echo "    ✗ Failed to enable PITR for $TABLE"
  fi
done

echo ""
echo "PITR enablement complete."
```

### Step 3: Verify PITR is Enabled

Re-run the verification from Step 1. Expected output:
```
aura-cost-tracking-dev: ENABLED
aura-user-sessions-dev: ENABLED
...
```

### Step 4: Redeploy CloudFormation Stack

Once PITR is enabled via CLI, the CloudFormation stack update will succeed:

```bash
# Option A: Trigger via CodeBuild (recommended)
aws codebuild start-build \
  --project-name aura-data-deploy-dev \
  --region us-east-1

# Option B: Direct CloudFormation deploy
aws cloudformation deploy \
  --stack-name aura-dynamodb-dev \
  --template-file deploy/cloudformation/dynamodb.yaml \
  --parameter-overrides Environment=dev ProjectName=aura \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --region us-east-1
```

### Step 5: Verify Stack Status

```bash
aws cloudformation describe-stacks \
  --stack-name aura-dynamodb-dev \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region us-east-1
```

Expected: `UPDATE_COMPLETE` or `CREATE_COMPLETE`

---

## Rollback Procedure

If you need to disable PITR (not recommended for production):

```bash
aws dynamodb update-continuous-backups \
  --table-name TABLE_NAME \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=false \
  --region us-east-1
```

---

## Environment-Specific Notes

| Environment | PITR Recommendation |
|-------------|---------------------|
| dev | Optional (enables DR testing) |
| qa | Recommended |
| prod | **Required** (compliance, DR) |

---

## Related Documentation

- [DynamoDB CloudFormation Template](../../deploy/cloudformation/dynamodb.yaml)
- [AWS DynamoDB PITR Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html)
- [CICD Setup Guide](../CICD_SETUP_GUIDE.md)

---

## Troubleshooting

### Error: "Table not found"

The table may not exist yet. Deploy the stack first without PITR enabled, then run this runbook.

### Error: "Access Denied" (CLI)

Ensure your IAM role has `dynamodb:UpdateContinuousBackups` permission.

### Error: "Access Denied" (CloudFormation/CodeBuild)

If CloudFormation stack updates fail with `dynamodb:UpdateContinuousBackups` AccessDenied, the CodeBuild IAM role needs this permission.

**Fix:** Add to `deploy/cloudformation/codebuild-data.yaml`:

```yaml
- dynamodb:UpdateContinuousBackups
- dynamodb:DescribeContinuousBackups
```

Then update the CodeBuild stack:

```bash
aws cloudformation deploy \
  --stack-name aura-codebuild-data-dev \
  --template-file deploy/cloudformation/codebuild-data.yaml \
  --parameter-overrides Environment=dev ProjectName=aura \
    GitHubRepository=https://github.com/aenealabs/aura GitHubBranch=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Error: "PITR already enabled"

This is not an error - the table already has PITR enabled. The CloudFormation update should succeed.

---

## Audit Trail

| Date | Author | Action |
|------|--------|--------|
| 2025-12-08 | Platform Team | Initial runbook creation |
