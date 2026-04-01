# Disaster Recovery

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document describes Project Aura's disaster recovery (DR) strategy, including backup procedures, recovery objectives, and failover processes. The DR architecture is designed to meet enterprise requirements for business continuity.

---

## Recovery Objectives

### Service Tier Definitions

| Tier | RTO | RPO | Description |
|------|-----|-----|-------------|
| **Tier 1** (Critical) | 1 hour | 15 minutes | Core API, authentication |
| **Tier 2** (High) | 4 hours | 1 hour | Agent orchestration, HITL |
| **Tier 3** (Medium) | 8 hours | 4 hours | Scanning, reporting |
| **Tier 4** (Low) | 24 hours | 24 hours | Analytics, historical data |

### Component Classification

| Component | Tier | RTO | RPO | Recovery Strategy |
|-----------|------|-----|-----|-------------------|
| API Gateway | 1 | 1h | N/A | Multi-AZ failover |
| Authentication | 1 | 1h | 15m | Cognito replication |
| DynamoDB | 1 | 1h | 15m | PITR + Global Tables |
| Neptune | 2 | 4h | 1h | Snapshot restore |
| OpenSearch | 2 | 4h | 1h | Snapshot restore |
| EKS Control Plane | 2 | 4h | N/A | AWS managed |
| S3 (Artifacts) | 3 | 8h | 4h | Cross-region replication |
| CloudWatch Logs | 4 | 24h | 24h | S3 export |

---

## Backup Architecture

### Backup Strategy Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKUP ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    PRIMARY REGION (us-east-1)              DR REGION (us-west-2)
    ┌─────────────────────────┐            ┌─────────────────────────┐
    │                         │            │                         │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │    DynamoDB     │────┼───────────►│  │  DynamoDB       │   │
    │  │  (Global Table) │    │  Sync      │  │  (Global Table) │   │
    │  └─────────────────┘    │            │  └─────────────────┘   │
    │                         │            │                         │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │    Neptune      │────┼───────────►│  │  Neptune        │   │
    │  │   (Primary)     │    │  Snapshot  │  │  (Standby)      │   │
    │  └─────────────────┘    │  Copy      │  └─────────────────┘   │
    │                         │            │                         │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │   OpenSearch    │────┼───────────►│  │  OpenSearch     │   │
    │  │    (Domain)     │    │  Snapshot  │  │  (Standby)      │   │
    │  └─────────────────┘    │  Copy      │  └─────────────────┘   │
    │                         │            │                         │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │      S3         │────┼───────────►│  │      S3         │   │
    │  │   (Buckets)     │    │  CRR       │  │   (Replicas)    │   │
    │  └─────────────────┘    │            │  └─────────────────┘   │
    │                         │            │                         │
    │  ┌─────────────────┐    │            │                         │
    │  │   Secrets       │────┼───────────►│  (Manual restore from  │
    │  │   Manager       │    │            │   CloudFormation)       │
    │  └─────────────────┘    │            │                         │
    │                         │            │                         │
    └─────────────────────────┘            └─────────────────────────┘
```

### DynamoDB Backup

**Continuous Backup (PITR):**

```bash
# Enable PITR on all tables
aws dynamodb update-continuous-backups \
  --table-name aura-approval-requests-${ENV} \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Verify PITR status
aws dynamodb describe-continuous-backups \
  --table-name aura-approval-requests-${ENV}
```

**Global Tables (Cross-Region Replication):**

```bash
# Create global table replica
aws dynamodb update-table \
  --table-name aura-approval-requests-${ENV} \
  --replica-updates \
    Create={RegionName=us-west-2}
```

**Backup Schedule:**

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| PITR | Continuous | 35 days |
| On-demand | Daily | 90 days |
| Global Table | Real-time | N/A |

---

### Neptune Backup

**Automated Snapshots:**

```bash
# Configure automated snapshots
aws neptune modify-db-cluster \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"
```

**Manual Snapshots:**

```bash
# Create manual snapshot
aws neptune create-db-cluster-snapshot \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --db-cluster-snapshot-identifier aura-neptune-${ENV}-$(date +%Y%m%d)

# Copy snapshot to DR region
aws neptune copy-db-cluster-snapshot \
  --source-db-cluster-snapshot-identifier arn:aws:rds:us-east-1:123456789012:cluster-snapshot:aura-neptune-${ENV}-20260119 \
  --target-db-cluster-snapshot-identifier aura-neptune-${ENV}-20260119 \
  --region us-west-2
```

**Backup Schedule:**

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Automated | Daily | 7 days |
| Manual | Weekly | 90 days |
| Cross-region | Weekly | 30 days |

---

### OpenSearch Backup

**Snapshot Repository:**

```bash
# Register S3 snapshot repository
curl -X PUT "https://opensearch.aura.local:9200/_snapshot/aura-backups" \
  -H "Content-Type: application/json" \
  -u "${OS_USER}:${OS_PASS}" \
  -d '{
    "type": "s3",
    "settings": {
      "bucket": "aura-opensearch-backups-${ENV}",
      "region": "us-east-1",
      "role_arn": "arn:aws:iam::123456789012:role/aura-opensearch-snapshot-role"
    }
  }'
```

**Automated Snapshots:**

```bash
# Create snapshot
curl -X PUT "https://opensearch.aura.local:9200/_snapshot/aura-backups/snapshot-$(date +%Y%m%d)" \
  -H "Content-Type: application/json" \
  -u "${OS_USER}:${OS_PASS}" \
  -d '{
    "indices": "aura-*",
    "ignore_unavailable": true,
    "include_global_state": false
  }'
```

**Backup Schedule:**

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Index snapshot | Daily | 30 days |
| Full snapshot | Weekly | 90 days |
| Cross-region | Weekly | 30 days |

---

### S3 Backup

**Cross-Region Replication:**

```json
{
  "Role": "arn:aws:iam::123456789012:role/aura-s3-replication-role",
  "Rules": [
    {
      "ID": "ReplicateAll",
      "Status": "Enabled",
      "Priority": 1,
      "DeleteMarkerReplication": {"Status": "Enabled"},
      "Filter": {"Prefix": ""},
      "Destination": {
        "Bucket": "arn:aws:s3:::aura-artifacts-dr-${ENV}",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": {"Minutes": 15}
        },
        "Metrics": {
          "Status": "Enabled",
          "EventThreshold": {"Minutes": 15}
        }
      }
    }
  ]
}
```

**Versioning:**

```bash
# Enable versioning
aws s3api put-bucket-versioning \
  --bucket aura-artifacts-${ENV} \
  --versioning-configuration Status=Enabled
```

---

## Recovery Procedures

### Scenario 1: Single AZ Failure

**Impact:** Partial service degradation
**Recovery Time:** Automatic (< 5 minutes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SINGLE AZ FAILURE RECOVERY                               │
└─────────────────────────────────────────────────────────────────────────────┘

    BEFORE FAILURE                         AFTER FAILOVER
    ┌─────────────────────────┐            ┌─────────────────────────┐
    │         AZ-a            │            │         AZ-a            │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │ EKS Nodes (2)   │ ◄──┼────────────┼──│ EKS Nodes (0)   │   │
    │  │ Neptune Primary │    │            │  │ Neptune (down)  │   │
    │  └─────────────────┘    │            │  └─────────────────┘   │
    │                         │            │         ╳              │
    │         AZ-b            │            │         AZ-b            │
    │  ┌─────────────────┐    │            │  ┌─────────────────┐   │
    │  │ EKS Nodes (2)   │    │    ───►    │  │ EKS Nodes (4)   │ ◄─│
    │  │ Neptune Replica │    │            │  │ Neptune Primary │   │
    │  └─────────────────┘    │            │  └─────────────────┘   │
    │                         │            │                         │
    └─────────────────────────┘            └─────────────────────────┘
```

**Automatic Recovery:**

1. ALB health checks detect AZ-a failure
2. Traffic automatically routed to AZ-b
3. EKS cluster autoscaler provisions additional nodes in AZ-b
4. Neptune promotes replica to primary
5. Service restored

---

### Scenario 2: Regional Failure

**Impact:** Complete service outage
**Recovery Time:** 4 hours (Tier 2)

**Recovery Steps:**

```bash
# Step 1: Verify DR region resources
aws cloudformation describe-stacks \
  --region us-west-2 \
  --stack-name aura-foundation-dr

# Step 2: Restore Neptune from snapshot
aws neptune restore-db-cluster-from-snapshot \
  --db-cluster-identifier aura-neptune-cluster-dr \
  --snapshot-identifier aura-neptune-prod-20260119 \
  --region us-west-2

# Step 3: Restore OpenSearch from snapshot
curl -X POST "https://opensearch-dr.aura.local:9200/_snapshot/aura-backups/snapshot-20260119/_restore" \
  -H "Content-Type: application/json" \
  -u "${OS_USER}:${OS_PASS}" \
  -d '{
    "indices": "aura-*",
    "ignore_unavailable": true
  }'

# Step 4: Update DNS to point to DR region
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch file://dr-dns-failover.json

# Step 5: Verify services
curl -s https://api.aenealabs.com/v1/health | jq
```

**DNS Failover Configuration:**

```json
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.aenealabs.com",
        "Type": "A",
        "SetIdentifier": "primary",
        "Failover": "SECONDARY",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "alb-dr.us-west-2.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
```

---

### Scenario 3: Data Corruption

**Impact:** Data integrity compromised
**Recovery Time:** 1-4 hours depending on scope

**DynamoDB Point-in-Time Recovery:**

```bash
# Identify last known good time
aws dynamodb describe-continuous-backups \
  --table-name aura-approval-requests-${ENV}

# Restore to point in time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name aura-approval-requests-${ENV} \
  --target-table-name aura-approval-requests-${ENV}-restored \
  --restore-date-time 2026-01-19T10:00:00Z

# Verify restored data
aws dynamodb scan \
  --table-name aura-approval-requests-${ENV}-restored \
  --select COUNT

# Rename tables to swap
aws dynamodb update-table \
  --table-name aura-approval-requests-${ENV} \
  --new-table-name aura-approval-requests-${ENV}-corrupted

aws dynamodb update-table \
  --table-name aura-approval-requests-${ENV}-restored \
  --new-table-name aura-approval-requests-${ENV}
```

**Neptune Snapshot Restore:**

```bash
# Restore from snapshot
aws neptune restore-db-cluster-from-snapshot \
  --db-cluster-identifier aura-neptune-cluster-restored \
  --snapshot-identifier aura-neptune-${ENV}-20260119

# Create new instance
aws neptune create-db-instance \
  --db-instance-identifier aura-neptune-restored \
  --db-instance-class db.r5.large \
  --engine neptune \
  --db-cluster-identifier aura-neptune-cluster-restored

# Update application configuration
kubectl set env deployment/orchestrator -n aura-system \
  NEPTUNE_ENDPOINT=aura-neptune-cluster-restored.cluster-xxx.us-east-1.neptune.amazonaws.com
```

---

### Scenario 4: Ransomware/Security Incident

**Impact:** System compromised
**Recovery Time:** Variable (depends on scope)

**Immediate Actions:**

```bash
# Step 1: Isolate affected systems
aws ec2 modify-instance-attribute \
  --instance-id ${INSTANCE_ID} \
  --groups sg-isolation

# Step 2: Preserve evidence
aws ec2 create-snapshot \
  --volume-id ${VOLUME_ID} \
  --description "Forensic snapshot - incident $(date +%Y%m%d)"

# Step 3: Rotate all credentials
aws secretsmanager rotate-secret \
  --secret-id aura/prod/database-credentials

# Step 4: Restore from pre-compromise backup
# (Follow regional failure procedure with clean backups)
```

---

## Recovery Runbooks

### Runbook: Database Recovery

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATABASE RECOVERY RUNBOOK                               │
└─────────────────────────────────────────────────────────────────────────────┘

1. ASSESS IMPACT
   □ Identify affected database(s)
   □ Determine scope of data loss/corruption
   □ Identify last known good backup

2. NOTIFY STAKEHOLDERS
   □ Alert on-call engineer
   □ Notify security team (if security incident)
   □ Update status page

3. EXECUTE RECOVERY
   □ Select recovery method (PITR vs snapshot)
   □ Restore to new instance/table
   □ Verify data integrity
   □ Update application configuration

4. VALIDATE
   □ Run health checks
   □ Verify recent transactions
   □ Test critical workflows

5. COMMUNICATE
   □ Update status page
   □ Send all-clear notification
   □ Schedule post-mortem

6. POST-RECOVERY
   □ Document timeline
   □ Update runbook if needed
   □ Review backup strategy
```

---

## Testing Schedule

| Test Type | Frequency | Last Test | Next Test |
|-----------|-----------|-----------|-----------|
| Backup verification | Weekly | 2026-01-12 | 2026-01-19 |
| Single AZ failover | Monthly | 2025-12-15 | 2026-01-15 |
| Regional failover | Quarterly | 2025-10-20 | 2026-01-20 |
| Full DR exercise | Annually | 2025-06-15 | 2026-06-15 |

### DR Test Checklist

```
□ Pre-test communication sent
□ Monitoring dashboards reviewed
□ Backup integrity verified
□ Recovery procedures executed
□ RTO/RPO measured and documented
□ Issues identified and logged
□ Post-test report generated
□ Runbooks updated as needed
```

---

## Related Documentation

- [Architecture Index](./index.md)
- [System Overview](./system-overview.md)
- [Security Architecture](./security-architecture.md)
- [Backup and Restore Operations](../operations/backup-restore.md)
- [Monitoring Guide](../operations/monitoring.md)

---

*Last updated: January 2026 | Version 1.0*
