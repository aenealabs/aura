# Layer 2: Data Runbook

**Layer:** 2 - Data
**CodeBuild Project:** `aura-data-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-data.yml`
**Estimated Deploy Time:** 25-35 minutes

---

## Overview

The Data layer provisions all database and storage infrastructure including Neptune (graph database), OpenSearch (vector search), DynamoDB (NoSQL), and S3 (object storage).

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-dynamodb-{env}` | dynamodb.yaml | 7 DynamoDB Tables with PITR, GSIs | 3-5 min |
| `aura-s3-{env}` | s3.yaml | 2+ S3 Buckets (artifacts, logs) | 1-2 min |
| `aura-neptune-{env}` | neptune-simplified.yaml | Neptune Cluster, Instance, Parameter Groups, KMS Key | 10-15 min |
| `aura-opensearch-{env}` | opensearch.yaml | OpenSearch Domain, Access Policy | 10-15 min |

---

## Dependencies

### Prerequisites (Must exist before deployment)
- Layer 1 (Foundation): VPC, Subnets, Security Groups
- SSM Parameter: `/aura/{env}/alert-email` (for alarms)

### Downstream Dependencies
- Layer 4 (Application): Requires Neptune/OpenSearch endpoints
- Layer 5 (Observability): Requires table ARNs for backup selections
- Layer 7 (Sandbox): Requires DynamoDB tables

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-data-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
# Get latest build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-data-deploy-dev \
  --query 'ids[0]' --output text --region us-east-1)

# Check build status
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}' --output table

# Stream logs
aws logs tail /aws/codebuild/aura-data-deploy-dev --follow --region us-east-1
```

### Verify Deployment
```bash
# Check all Data stacks
for STACK in aura-dynamodb-dev aura-s3-dev aura-neptune-dev aura-opensearch-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done
```

---

## Troubleshooting

### Issue: DynamoDB PITR Enable Fails via CloudFormation

**Symptoms:**
```
UPDATE_FAILED - Cannot update PointInTimeRecoveryEnabled on existing table
```

**Root Cause:** CloudFormation cannot modify PITR on existing tables.

**Resolution:**
See [DYNAMODB_PITR_ENABLE.md](./DYNAMODB_PITR_ENABLE.md) runbook for detailed steps.

Quick fix:
```bash
# Enable PITR via CLI first
for TABLE in aura-cost-tracking-dev aura-user-sessions-dev aura-codegen-jobs-dev \
             aura-ingestion-jobs-dev aura-codebase-metadata-dev aura-platform-settings-dev \
             aura-anomalies-dev; do
  aws dynamodb update-continuous-backups \
    --table-name "$TABLE" \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
    --region us-east-1
done

# Then re-run buildspec
aws codebuild start-build --project-name aura-data-deploy-dev
```

---

### Issue: Neptune Cluster Creation Timeout

**Symptoms:**
- Stack stuck in CREATE_IN_PROGRESS for >20 minutes
- Neptune cluster status: "creating"

**Root Cause:** Neptune cluster creation is slow (10-15 min normal).

**Resolution:**
```bash
# Check Neptune cluster status
aws neptune describe-db-clusters \
  --db-cluster-identifier aura-neptune-dev \
  --query 'DBClusters[0].Status' --output text

# If stuck >30 min, check events
aws neptune describe-events \
  --source-identifier aura-neptune-dev \
  --source-type db-cluster \
  --duration 60
```

If truly stuck:
```bash
# Delete and recreate
aws cloudformation delete-stack --stack-name aura-neptune-dev
aws cloudformation wait stack-delete-complete --stack-name aura-neptune-dev
aws codebuild start-build --project-name aura-data-deploy-dev
```

---

### Issue: Neptune Security Group Rules Missing

**Symptoms:**
```
Connection refused to Neptune endpoint on port 8182
```

**Root Cause:** Security group ingress rules not applied or wrong CIDR.

**Resolution:**
```bash
# Check Neptune security group rules
NEPTUNE_SG=$(aws cloudformation describe-stacks --stack-name aura-security-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`NeptuneSecurityGroupId`].OutputValue' --output text)

aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=$NEPTUNE_SG" \
  --query 'SecurityGroupRules[*].[SecurityGroupRuleId,IpProtocol,FromPort,ToPort,CidrIpv4]' --output table

# Add missing rule if needed
aws ec2 authorize-security-group-ingress \
  --group-id $NEPTUNE_SG \
  --protocol tcp --port 8182 \
  --cidr 10.0.0.0/16
```

---

### Issue: OpenSearch Domain Creation Fails

**Symptoms:**
```
CREATE_FAILED - The requested instance type is not supported in this region
```

**Root Cause:** Instance type not available or quota exceeded.

**Resolution:**
```bash
# Check available instance types
aws opensearch list-instance-type-details \
  --engine-version OpenSearch_2.11 \
  --query 'InstanceTypeDetails[*].InstanceType' --output table

# Update template if needed (deploy/cloudformation/opensearch.yaml)
# Change InstanceType from t3.small.search to available type
```

---

### Issue: OpenSearch Access Denied

**Symptoms:**
```
403 Forbidden - User is not authorized to access this resource
```

**Root Cause:** IAM policy not allowing access or missing IRSA configuration.

**Resolution:**
```bash
# Check OpenSearch access policy
aws opensearch describe-domain \
  --domain-name aura-opensearch-dev \
  --query 'DomainStatus.AccessPolicies' --output text | jq .

# Verify IRSA role has OpenSearch permissions
aws iam get-role-policy \
  --role-name aura-api-role-dev \
  --policy-name OpenSearchAccess
```

---

### Issue: S3 Bucket Already Exists

**Symptoms:**
```
CREATE_FAILED - aura-artifacts-ACCOUNT-dev already exists
```

**Root Cause:** Bucket was created manually or by previous deployment.

**Resolution:**
```bash
# Check if bucket exists
aws s3 ls s3://aura-artifacts-123456789012-dev

# Option 1: Import into CloudFormation (preferred)
# Option 2: Delete bucket (if empty and not needed)
aws s3 rb s3://aura-artifacts-123456789012-dev --force
```

---

### Issue: DynamoDB Table Throughput Exceeded

**Symptoms:**
```
ProvisionedThroughputExceededException
```

**Root Cause:** Table using provisioned capacity and exceeding limits.

**Resolution:**
```bash
# Check table capacity mode
aws dynamodb describe-table \
  --table-name aura-anomalies-dev \
  --query 'Table.BillingModeSummary.BillingMode'

# If PROVISIONED, switch to PAY_PER_REQUEST (on-demand)
aws dynamodb update-table \
  --table-name aura-anomalies-dev \
  --billing-mode PAY_PER_REQUEST
```

---

## Recovery Procedures

### Full Layer Recovery

**WARNING:** This will delete all data. Backup first if needed.

```bash
# 1. Backup DynamoDB tables (if needed)
for TABLE in aura-anomalies-dev aura-cost-tracking-dev; do
  aws dynamodb create-backup \
    --table-name $TABLE \
    --backup-name "${TABLE}-backup-$(date +%Y%m%d)"
done

# 2. Delete stacks in reverse dependency order
aws cloudformation delete-stack --stack-name aura-opensearch-dev
aws cloudformation delete-stack --stack-name aura-neptune-dev
aws cloudformation delete-stack --stack-name aura-dynamodb-dev
aws cloudformation delete-stack --stack-name aura-s3-dev

# 3. Wait for deletions (Neptune takes 5-10 min)
for STACK in aura-opensearch-dev aura-neptune-dev aura-dynamodb-dev aura-s3-dev; do
  echo "Waiting for $STACK..."
  aws cloudformation wait stack-delete-complete --stack-name $STACK
done

# 4. Redeploy
aws codebuild start-build --project-name aura-data-deploy-dev
```

### Neptune Recovery Only

```bash
# Neptune can take 15-20 min to fully delete
aws cloudformation delete-stack --stack-name aura-neptune-dev
aws cloudformation wait stack-delete-complete --stack-name aura-neptune-dev

# Redeploy entire data layer
aws codebuild start-build --project-name aura-data-deploy-dev
```

---

## Post-Deployment Verification

### 1. Verify Neptune Connectivity

```bash
# Get Neptune endpoint
NEPTUNE_ENDPOINT=$(aws neptune describe-db-clusters \
  --db-cluster-identifier aura-neptune-dev \
  --query 'DBClusters[0].Endpoint' --output text)

echo "Neptune endpoint: $NEPTUNE_ENDPOINT"

# Test from EKS pod
kubectl run neptune-test --rm -it --image=curlimages/curl -- \
  curl -s "https://${NEPTUNE_ENDPOINT}:8182/status"
```

### 2. Verify OpenSearch Connectivity

```bash
# Get OpenSearch endpoint
OPENSEARCH_ENDPOINT=$(aws opensearch describe-domain \
  --domain-name aura-opensearch-dev \
  --query 'DomainStatus.Endpoint' --output text)

echo "OpenSearch endpoint: $OPENSEARCH_ENDPOINT"

# Test cluster health
curl -s "https://${OPENSEARCH_ENDPOINT}/_cluster/health" | jq .
```

### 3. Verify DynamoDB Tables

```bash
aws dynamodb list-tables \
  --query 'TableNames[?starts_with(@, `aura-`)]' --output table
```

### 4. Check PITR Status

```bash
for TABLE in aura-anomalies-dev aura-cost-tracking-dev; do
  STATUS=$(aws dynamodb describe-continuous-backups \
    --table-name "$TABLE" \
    --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
    --output text)
  echo "$TABLE: PITR=$STATUS"
done
```

---

## Stack Outputs Reference

### aura-neptune-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| ClusterEndpoint | Neptune cluster endpoint | Application, API |
| ReaderEndpoint | Neptune reader endpoint | Read replicas |
| Port | Neptune port (8182) | Application |

### aura-opensearch-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| DomainEndpoint | OpenSearch endpoint | Application, API |
| DomainArn | OpenSearch domain ARN | IAM policies |

### aura-dynamodb-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| AnomaliesTableName | Anomalies table name | Application |
| AnomaliesTableArn | Anomalies table ARN | IAM, Backup |

---

## Related Documentation

- [DYNAMODB_PITR_ENABLE.md](./DYNAMODB_PITR_ENABLE.md) - PITR enablement runbook
- [LAYER1_FOUNDATION_RUNBOOK.md](./LAYER1_FOUNDATION_RUNBOOK.md) - Foundation dependencies
- [E2E_TESTING_RUNBOOK.md](../E2E_TESTING_RUNBOOK.md) - Database connectivity tests

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
