# Project Aura - Disaster Recovery Plan

## Document Information

| Attribute | Value |
|-----------|-------|
| Version | 1.0 |
| Created | December 8, 2025 |
| Related Issue | GitHub #14 |
| Compliance | CMMC L2/L3, SOC 2, NIST 800-53 |

---

## 1. Overview

This document defines the disaster recovery (DR) strategy for Project Aura, including:
- Recovery Point Objectives (RPO) and Recovery Time Objectives (RTO)
- Backup configurations for all stateful services
- Recovery procedures for various failure scenarios
- Testing and validation requirements

---

## 2. RTO/RPO Targets

### Service-Level Targets

| Service | RPO | RTO | Tier | Backup Method |
|---------|-----|-----|------|---------------|
| **Neptune** | 24h | 4h | 1 | Automated snapshots + AWS Backup |
| **OpenSearch** | 24h | 4h | 1 | Automated snapshots |
| **DynamoDB** | 1h | 1h | 1 | PITR (continuous) + AWS Backup |
| **S3** | 0 | 1h | 1 | Versioning + CRR (prod) |
| **EKS/Kubernetes** | N/A | 2h | 2 | GitOps redeploy (ArgoCD) |
| **Secrets Manager** | 0 | 15m | 1 | AWS-managed replication |
| **Configuration** | 0 | 30m | 2 | SSM Parameter Store + Git |

### Tier Definitions

- **Tier 1 (Critical)**: Data services with customer/business data
- **Tier 2 (Important)**: Infrastructure components that can be rebuilt

---

## 3. Backup Infrastructure

### 3.1 AWS Backup Configuration

**CloudFormation Template:** `deploy/cloudformation/disaster-recovery.yaml`

Deployed resources:
- AWS Backup Vault (`aura-vault-{env}`) with KMS encryption
- Daily backup plan (3 AM UTC) for Neptune, DynamoDB, EBS
- Hourly backup plan (production) for critical DynamoDB tables
- SNS alerts for backup failures
- Cross-region backup copy (production only to us-west-2)

**Retention Periods:**
| Environment | Daily Backups | Hourly Backups |
|-------------|---------------|----------------|
| dev | 7 days | N/A |
| qa | 14 days | N/A |
| prod | 35 days | 7 days |

### 3.2 Neptune Backups

**Configuration:** `deploy/cloudformation/neptune-simplified.yaml`

```yaml
BackupRetentionPeriod: 7  # prod: 7 days, dev: 1 day
PreferredBackupWindow: '03:00-04:00'
```

**Recovery:**
```bash
# List available snapshots
aws neptune describe-db-cluster-snapshots \
  --db-cluster-identifier aura-dev \
  --query 'DBClusterSnapshots[].DBClusterSnapshotIdentifier'

# Restore from snapshot
aws neptune restore-db-cluster-from-snapshot \
  --db-cluster-identifier aura-dev-restored \
  --snapshot-identifier aura-dev-snapshot-2025-12-08 \
  --engine neptune \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name aura-neptune-subnet-dev
```

### 3.3 OpenSearch Snapshots

**Configuration:** `deploy/cloudformation/opensearch.yaml`

```yaml
SnapshotOptions:
  AutomatedSnapshotStartHour: 2  # 2 AM UTC
```

OpenSearch retains 14 automated snapshots by default. For longer retention, manual snapshots to S3 are recommended.

**Manual Snapshot to S3:**
```bash
# Register S3 repository (one-time)
curl -X PUT "https://opensearch-endpoint/_snapshot/s3-backups" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "s3",
    "settings": {
      "bucket": "aura-backups-{account-id}-prod",
      "region": "us-east-1",
      "role_arn": "arn:aws:iam::{account-id}:role/aura-opensearch-snapshot-role"
    }
  }'

# Create manual snapshot
curl -X PUT "https://opensearch-endpoint/_snapshot/s3-backups/snapshot-$(date +%Y%m%d)"
```

**Recovery:**
```bash
# List snapshots
curl -X GET "https://opensearch-endpoint/_snapshot/s3-backups/_all"

# Restore specific snapshot
curl -X POST "https://opensearch-endpoint/_snapshot/s3-backups/snapshot-20251208/_restore" \
  -H "Content-Type: application/json" \
  -d '{"indices": "code_entities,vulnerabilities"}'
```

### 3.4 DynamoDB Point-in-Time Recovery (PITR)

**Configuration:** `deploy/cloudformation/dynamodb.yaml`

```yaml
PointInTimeRecoverySpecification:
  PointInTimeRecoveryEnabled: true  # All environments
```

PITR provides continuous backups with 35-day retention and 1-second granularity.

**Recovery:**
```bash
# Restore table to a point in time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name aura-hitl-approvals-dev \
  --target-table-name aura-hitl-approvals-dev-restored \
  --restore-date-time "2025-12-08T10:00:00Z"

# Or restore to latest restorable time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name aura-anomalies-dev \
  --target-table-name aura-anomalies-dev-restored \
  --use-latest-restorable-time
```

### 3.5 S3 Versioning and Cross-Region Replication

**Configuration:** `deploy/cloudformation/s3.yaml`

All buckets have versioning enabled. Cross-region replication (CRR) is configured for production.

**Recover Deleted Object:**
```bash
# List object versions
aws s3api list-object-versions \
  --bucket aura-artifacts-{account-id}-prod \
  --prefix path/to/file

# Restore specific version
aws s3api copy-object \
  --bucket aura-artifacts-{account-id}-prod \
  --copy-source aura-artifacts-{account-id}-prod/path/to/file?versionId=xxxxx \
  --key path/to/file
```

**Cross-Region Replication Setup (Production):**
```bash
# 1. Create destination bucket in DR region (us-west-2)
aws s3api create-bucket \
  --bucket aura-artifacts-{account-id}-prod-dr \
  --region us-west-2 \
  --create-bucket-configuration LocationConstraint=us-west-2

# 2. Enable versioning on destination
aws s3api put-bucket-versioning \
  --bucket aura-artifacts-{account-id}-prod-dr \
  --versioning-configuration Status=Enabled

# 3. Create replication role and configure CRR
# See: docs/runbooks/s3-crr-setup.md
```

---

## 4. Recovery Procedures

### 4.1 Complete Region Failure

**Scenario:** Primary region (us-east-1) is unavailable.

**RTO:** 4 hours

**Steps:**

1. **Activate DR Region (us-west-2)**
   ```bash
   export AWS_DEFAULT_REGION=us-west-2
   ```

2. **Restore Neptune from Cross-Region Backup**
   ```bash
   aws neptune restore-db-cluster-from-snapshot \
     --db-cluster-identifier aura-prod \
     --snapshot-identifier arn:aws:rds:us-west-2:{account}:cluster-snapshot:aura-prod-xxxxx
   ```

3. **Restore OpenSearch** (manual process - see Section 3.3)

4. **Restore DynamoDB Tables**
   ```bash
   # AWS Backup handles cross-region restore
   aws backup start-restore-job \
     --recovery-point-arn arn:aws:backup:us-west-2:{account}:recovery-point:xxxxx \
     --iam-role-arn arn:aws:iam::{account}:role/aura-backup-role-prod
   ```

5. **Deploy EKS Cluster**
   ```bash
   # Use CloudFormation to deploy EKS in DR region
   aws cloudformation create-stack \
     --stack-name aura-eks-prod \
     --template-body file://deploy/cloudformation/eks.yaml \
     --parameters ParameterKey=Environment,ParameterValue=prod
   ```

6. **Deploy Applications via ArgoCD**
   ```bash
   # ArgoCD will sync from Git - applications auto-deploy
   argocd app sync aura-api
   argocd app sync aura-frontend
   ```

7. **Update DNS**
   ```bash
   # Update Route 53 to point to DR region
   aws route53 change-resource-record-sets \
     --hosted-zone-id ZXXXXX \
     --change-batch file://dr-dns-update.json
   ```

### 4.2 Database Corruption

**Scenario:** Neptune or OpenSearch data is corrupted.

**RTO:** 1-4 hours depending on data size

**Steps:**

1. **Identify Corruption Scope**
   ```bash
   # Check Neptune status
   aws neptune describe-db-clusters --db-cluster-identifier aura-dev

   # Check OpenSearch cluster health
   curl -X GET "https://opensearch-endpoint/_cluster/health"
   ```

2. **Restore from Snapshot** (see Sections 3.2 and 3.3)

3. **Validate Data Integrity**
   ```bash
   # Run validation queries
   python3 scripts/validate_neptune_integrity.py
   python3 scripts/validate_opensearch_integrity.py
   ```

### 4.3 Accidental Data Deletion

**Scenario:** Critical data accidentally deleted from DynamoDB.

**RTO:** 1 hour

**Steps:**

1. **Identify Deletion Time**
   ```bash
   # Check CloudTrail for deletion event
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteItem
   ```

2. **Restore Using PITR**
   ```bash
   # Restore to just before deletion
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name aura-hitl-approvals-dev \
     --target-table-name aura-hitl-approvals-dev-restored \
     --restore-date-time "2025-12-08T09:59:00Z"
   ```

3. **Migrate Data to Original Table**
   ```bash
   # Export from restored table and import to original
   python3 scripts/migrate_dynamodb_data.py \
     --source aura-hitl-approvals-dev-restored \
     --target aura-hitl-approvals-dev
   ```

### 4.4 EKS Cluster Failure

**Scenario:** EKS cluster is unresponsive or corrupted.

**RTO:** 2 hours

**Steps:**

1. **Check Cluster Status**
   ```bash
   aws eks describe-cluster --name aura-cluster-dev
   kubectl cluster-info
   ```

2. **If Recoverable:** Restart nodes
   ```bash
   # Terminate unhealthy nodes (ASG will replace)
   aws autoscaling terminate-instance-in-auto-scaling-group \
     --instance-id i-xxxxx \
     --should-decrement-desired-capacity false
   ```

3. **If Unrecoverable:** Redeploy cluster
   ```bash
   # Delete and recreate via CloudFormation
   aws cloudformation delete-stack --stack-name aura-eks-dev
   aws cloudformation wait stack-delete-complete --stack-name aura-eks-dev
   aws cloudformation create-stack --stack-name aura-eks-dev \
     --template-body file://deploy/cloudformation/eks.yaml
   ```

4. **Restore Applications via ArgoCD**
   ```bash
   # ArgoCD will auto-sync from Git
   kubectl apply -f deploy/kubernetes/argocd/applications/
   ```

---

## 5. Monitoring and Alerting

### 5.1 Backup Monitoring

**CloudWatch Alarms:**
- `aura-backup-failed-{env}` - Alerts on any backup job failure
- `aura-backup-success-{env}` - Alerts if no backups complete in 24 hours

**SNS Topic:** `aura-backup-alerts-{env}`

**EventBridge Rule:** `aura-backup-events-{env}` captures FAILED, ABORTED, EXPIRED states

### 5.2 Verification Commands

```bash
# Check backup vault status
aws backup list-backup-jobs \
  --by-backup-vault-name aura-vault-dev \
  --by-state COMPLETED \
  --max-results 10

# List recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name aura-vault-dev

# Check Neptune snapshot status
aws neptune describe-db-cluster-snapshots \
  --db-cluster-identifier aura-dev

# Check DynamoDB PITR status
aws dynamodb describe-continuous-backups \
  --table-name aura-hitl-approvals-dev
```

---

## 6. DR Testing Schedule

### Quarterly Tests

| Test Type | Frequency | Duration | Scope |
|-----------|-----------|----------|-------|
| Backup Verification | Weekly | 1 hour | Automated |
| Table-Level Restore | Monthly | 2 hours | DynamoDB PITR |
| Cluster Restore | Quarterly | 4 hours | Neptune/OpenSearch |
| Full DR Drill | Annually | 8 hours | Complete failover |

### Test Checklist

- [ ] Verify all automated backups completed successfully
- [ ] Restore a DynamoDB table using PITR
- [ ] Restore Neptune cluster from snapshot
- [ ] Restore OpenSearch index from snapshot
- [ ] Deploy EKS cluster from scratch
- [ ] Validate application functionality after restore
- [ ] Measure actual RTO against targets
- [ ] Document any issues and remediation

---

## 7. Contacts and Escalation

### On-Call Rotation

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| Primary On-Call | PagerDuty | Immediate |
| Secondary On-Call | PagerDuty | 15 minutes |
| Engineering Lead | Slack #aura-incidents | 30 minutes |
| Management | Email | 1 hour |

### External Contacts

| Service | Support Level | Contact |
|---------|---------------|---------|
| AWS Support | Enterprise | support.console.aws.amazon.com |
| GitHub | Enterprise | enterprise-support@github.com |

---

## 8. Related Documentation

- [HITL Sandbox Architecture](./HITL_SANDBOX_ARCHITECTURE.md)
- [GovCloud Migration Summary](./GOVCLOUD_MIGRATION_SUMMARY.md)
- [System Architecture](../SYSTEM_ARCHITECTURE.md)
- [ADR-026: Bootstrap Once, Update Forever](./architecture-decisions/ADR-026-BOOTSTRAP-ONCE-UPDATE-FOREVER.md)

---

## Appendix A: CloudFormation Stacks for DR

| Stack | Purpose | DR Impact |
|-------|---------|-----------|
| `disaster-recovery.yaml` | AWS Backup infrastructure | Core DR |
| `neptune-simplified.yaml` | Neptune with backup config | Tier 1 |
| `opensearch.yaml` | OpenSearch with snapshots | Tier 1 |
| `dynamodb.yaml` | DynamoDB with PITR | Tier 1 |
| `s3.yaml` | S3 with versioning | Tier 1 |
| `eks.yaml` | EKS cluster (stateless) | Tier 2 |

## Appendix B: Recovery Scripts

Located in `scripts/dr/`:
- `validate_neptune_integrity.py`
- `validate_opensearch_integrity.py`
- `migrate_dynamodb_data.py`
- `restore_from_backup.sh`
- `dr_failover.sh`
