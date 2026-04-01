# Backup and Restore

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide provides procedures for backing up and restoring Project Aura data. For detailed disaster recovery scenarios, see [Disaster Recovery](../architecture/disaster-recovery.md).

---

## Backup Schedule Summary

| Component | Type | Frequency | Retention | RPO |
|-----------|------|-----------|-----------|-----|
| DynamoDB | PITR | Continuous | 35 days | 1 second |
| DynamoDB | On-demand | Daily | 90 days | 24 hours |
| Neptune | Automated | Daily | 7 days | 24 hours |
| Neptune | Manual | Weekly | 90 days | 7 days |
| OpenSearch | Snapshot | Daily | 30 days | 24 hours |
| S3 | Versioning | Continuous | 90 days | Immediate |
| S3 | Cross-region | Continuous | 90 days | 15 minutes |

---

## DynamoDB Backup

### Point-in-Time Recovery (PITR)

PITR provides continuous backup with 1-second granularity.

**Enable PITR:**

```bash
# Enable for all Aura tables
for TABLE in approval-requests agent-state user-sessions scan-results; do
  aws dynamodb update-continuous-backups \
    --table-name aura-${TABLE}-${ENV} \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
done
```

**Verify PITR Status:**

```bash
aws dynamodb describe-continuous-backups \
  --table-name aura-approval-requests-${ENV} \
  --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription'
```

**Restore to Point-in-Time:**

```bash
# Restore to specific time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name aura-approval-requests-${ENV} \
  --target-table-name aura-approval-requests-${ENV}-restored \
  --restore-date-time 2026-01-19T10:00:00Z

# Wait for restore to complete
aws dynamodb wait table-exists \
  --table-name aura-approval-requests-${ENV}-restored

# Verify data
aws dynamodb scan \
  --table-name aura-approval-requests-${ENV}-restored \
  --select COUNT
```

### On-Demand Backup

**Create Backup:**

```bash
# Create named backup
aws dynamodb create-backup \
  --table-name aura-approval-requests-${ENV} \
  --backup-name aura-approval-requests-${ENV}-$(date +%Y%m%d)
```

**List Backups:**

```bash
aws dynamodb list-backups \
  --table-name aura-approval-requests-${ENV} \
  --time-range-lower-bound $(date -d '30 days ago' +%s) \
  --query 'BackupSummaries[*].[BackupName,BackupStatus,BackupCreationDateTime]'
```

**Restore from Backup:**

```bash
# Get backup ARN
BACKUP_ARN=$(aws dynamodb list-backups \
  --table-name aura-approval-requests-${ENV} \
  --query 'BackupSummaries[0].BackupArn' \
  --output text)

# Restore
aws dynamodb restore-table-from-backup \
  --target-table-name aura-approval-requests-${ENV}-restored \
  --backup-arn ${BACKUP_ARN}
```

---

## Neptune Backup

### Automated Snapshots

Automated snapshots are configured during cluster creation.

**Verify Configuration:**

```bash
aws neptune describe-db-clusters \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --query 'DBClusters[0].[BackupRetentionPeriod,PreferredBackupWindow]'
```

**List Automated Snapshots:**

```bash
aws neptune describe-db-cluster-snapshots \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --snapshot-type automated \
  --query 'DBClusterSnapshots[*].[DBClusterSnapshotIdentifier,SnapshotCreateTime,Status]'
```

### Manual Snapshots

**Create Snapshot:**

```bash
aws neptune create-db-cluster-snapshot \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --db-cluster-snapshot-identifier aura-neptune-${ENV}-$(date +%Y%m%d-%H%M)
```

**Copy to Another Region:**

```bash
aws neptune copy-db-cluster-snapshot \
  --source-db-cluster-snapshot-identifier arn:aws:rds:us-east-1:${ACCOUNT_ID}:cluster-snapshot:aura-neptune-${ENV}-20260119 \
  --target-db-cluster-snapshot-identifier aura-neptune-${ENV}-20260119 \
  --region us-west-2
```

### Restore from Snapshot

**Restore Cluster:**

```bash
# Restore to new cluster
aws neptune restore-db-cluster-from-snapshot \
  --db-cluster-identifier aura-neptune-cluster-${ENV}-restored \
  --snapshot-identifier aura-neptune-${ENV}-20260119 \
  --engine neptune \
  --vpc-security-group-ids ${NEPTUNE_SG} \
  --db-subnet-group-name aura-neptune-subnet-group-${ENV}

# Create instance in restored cluster
aws neptune create-db-instance \
  --db-instance-identifier aura-neptune-${ENV}-restored \
  --db-instance-class db.r5.large \
  --engine neptune \
  --db-cluster-identifier aura-neptune-cluster-${ENV}-restored

# Wait for instance
aws neptune wait db-instance-available \
  --db-instance-identifier aura-neptune-${ENV}-restored
```

---

## OpenSearch Backup

### Configure Snapshot Repository

**Register S3 Repository:**

```bash
curl -X PUT "https://opensearch.aura.local:9200/_snapshot/aura-backups" \
  -H "Content-Type: application/json" \
  -u "${OS_USER}:${OS_PASS}" \
  -d '{
    "type": "s3",
    "settings": {
      "bucket": "aura-opensearch-backups-'${ENV}'",
      "region": "'${AWS_REGION}'",
      "role_arn": "arn:aws:iam::'${ACCOUNT_ID}':role/aura-opensearch-snapshot-role",
      "compress": true
    }
  }'
```

### Create Snapshot

**Full Snapshot:**

```bash
curl -X PUT "https://opensearch.aura.local:9200/_snapshot/aura-backups/snapshot-$(date +%Y%m%d)" \
  -H "Content-Type: application/json" \
  -u "${OS_USER}:${OS_PASS}" \
  -d '{
    "indices": "aura-*",
    "ignore_unavailable": true,
    "include_global_state": true
  }'
```

**Check Snapshot Status:**

```bash
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_snapshot/aura-backups/snapshot-20260119/_status" | jq
```

**List Snapshots:**

```bash
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_snapshot/aura-backups/_all" | jq '.snapshots[] | {name: .snapshot, status: .state, indices: .indices | length}'
```

### Restore from Snapshot

**Restore All Indices:**

```bash
# Close existing indices first
curl -X POST -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/aura-*/_close"

# Restore snapshot
curl -X POST -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_snapshot/aura-backups/snapshot-20260119/_restore" \
  -H "Content-Type: application/json" \
  -d '{
    "indices": "aura-*",
    "ignore_unavailable": true,
    "include_global_state": false
  }'
```

**Restore to Different Index:**

```bash
curl -X POST -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_snapshot/aura-backups/snapshot-20260119/_restore" \
  -H "Content-Type: application/json" \
  -d '{
    "indices": "aura-code-embeddings",
    "rename_pattern": "aura-(.+)",
    "rename_replacement": "restored-aura-$1"
  }'
```

---

## S3 Backup

### Versioning

Versioning is enabled by default for all Aura buckets.

**Check Versioning Status:**

```bash
aws s3api get-bucket-versioning \
  --bucket aura-artifacts-${ENV}
```

**List Object Versions:**

```bash
aws s3api list-object-versions \
  --bucket aura-artifacts-${ENV} \
  --prefix patches/ \
  --max-keys 10
```

**Restore Previous Version:**

```bash
# Get previous version ID
VERSION_ID=$(aws s3api list-object-versions \
  --bucket aura-artifacts-${ENV} \
  --prefix patches/patch-12345.json \
  --query 'Versions[1].VersionId' \
  --output text)

# Copy previous version as current
aws s3api copy-object \
  --bucket aura-artifacts-${ENV} \
  --copy-source aura-artifacts-${ENV}/patches/patch-12345.json?versionId=${VERSION_ID} \
  --key patches/patch-12345.json
```

### Cross-Region Replication

**Verify Replication:**

```bash
# Check replication status
aws s3api get-bucket-replication \
  --bucket aura-artifacts-${ENV}

# Check replication metrics
aws s3api get-bucket-metrics-configuration \
  --bucket aura-artifacts-${ENV} \
  --id ReplicationMetrics
```

---

## Backup Verification

### Automated Verification Script

```bash
#!/bin/bash
# backup-verify.sh

ENV=${1:-dev}
DATE=$(date +%Y%m%d)

echo "=== Backup Verification Report - ${DATE} ==="

# DynamoDB PITR
echo -e "\n--- DynamoDB PITR Status ---"
for TABLE in approval-requests agent-state user-sessions; do
  STATUS=$(aws dynamodb describe-continuous-backups \
    --table-name aura-${TABLE}-${ENV} \
    --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
    --output text)
  echo "${TABLE}: ${STATUS}"
done

# Neptune Snapshots
echo -e "\n--- Neptune Snapshots (Last 7 Days) ---"
aws neptune describe-db-cluster-snapshots \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --query 'DBClusterSnapshots[?SnapshotCreateTime>=`'"$(date -d '7 days ago' -Iseconds)"'`].[DBClusterSnapshotIdentifier,Status]' \
  --output table

# OpenSearch Snapshots
echo -e "\n--- OpenSearch Snapshots ---"
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_snapshot/aura-backups/_all" | \
  jq -r '.snapshots[-5:] | .[] | "\(.snapshot): \(.state)"'

# S3 Replication
echo -e "\n--- S3 Replication Status ---"
aws s3api head-bucket --bucket aura-artifacts-dr-${ENV} 2>/dev/null && \
  echo "DR bucket accessible" || echo "DR bucket NOT accessible"

echo -e "\n=== Verification Complete ==="
```

### Restore Testing Schedule

| Component | Test Type | Frequency | Last Test | Next Test |
|-----------|-----------|-----------|-----------|-----------|
| DynamoDB PITR | Restore single table | Monthly | 2025-12-15 | 2026-01-15 |
| Neptune | Full cluster restore | Quarterly | 2025-10-20 | 2026-01-20 |
| OpenSearch | Index restore | Monthly | 2025-12-20 | 2026-01-20 |
| S3 | Version restore | Weekly | 2026-01-12 | 2026-01-19 |

---

## Emergency Restore Procedures

### Critical Data Loss

If critical data is lost or corrupted:

1. **Assess Impact**
   - Identify affected tables/indices
   - Determine time of corruption
   - Identify last known good state

2. **Notify Stakeholders**
   - Alert on-call team
   - Update status page

3. **Execute Restore**
   - Follow component-specific procedures above
   - Restore to new resource (do not overwrite)

4. **Verify Data**
   - Run integrity checks
   - Compare record counts
   - Spot-check critical records

5. **Switch Traffic**
   - Update application configuration
   - Monitor for errors

6. **Document and Review**
   - Create incident report
   - Update procedures if needed

---

## Related Documentation

- [Operations Index](./index.md)
- [Disaster Recovery](../architecture/disaster-recovery.md)
- [Monitoring Guide](./monitoring.md)

---

*Last updated: January 2026 | Version 1.0*
