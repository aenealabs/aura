# Disaster Recovery

**Version:** 1.1
**Last Updated:** May 2026
**Product:** Project Aura by Aenea Labs

---

## Scope

**This document covers Aenea Labs SaaS DR posture only.** Self-hosted Aura customers (ADR-049, deployed via Podman in their own environments) are responsible for their own continuity planning per their deployment model. SaaS multi-region capabilities described here do not extend to self-hosted deployments.

---

## Overview

This document describes Project Aura's disaster recovery (DR) strategy, including backup procedures, recovery objectives, and failover processes. The DR architecture is designed to meet enterprise requirements for business continuity.

> **State of this document (May 2026):** Sections below are split into **Current** (what is deployed and verifiable today) and **Target** (what is committed but not yet implemented). The split was added during a May 2026 honesty pass after a deploy-chain audit found the multi-region orchestration template (`multi-region-global.yaml`) was detection / notification only -- no actual failover capability. The template has been archived. Tier 1 RTO/RPO targets are aspirational pending the implementation tracked under the DR initiative (umbrella issue).

---

## Recovery Objectives

### Service Tier Definitions (Target)

| Tier | RTO | RPO | Description |
|------|-----|-----|-------------|
| **Tier 1** (Critical) | 1 hour | 15 minutes | Core API, authentication |
| **Tier 2** (High) | 4 hours | 1 hour | Agent orchestration, HITL |
| **Tier 3** (Medium) | 8 hours | 4 hours | Scanning, reporting |
| **Tier 4** (Low) | 24 hours | 24 hours | Analytics, historical data |

> The tier definitions are the contractual targets. The component table below distinguishes what is **deployed** to meet them today vs. what remains **target-only**.

### Component Classification

Two columns: **Recovery Strategy (Deployed)** is what is actually in CloudFormation today. **Recovery Strategy (Target)** is the committed end-state from the DR initiative.

| Component | Tier | RTO | RPO | Recovery Strategy (Deployed) | Recovery Strategy (Target) | Gap Tracked As |
|-----------|------|-----|-----|------------------------------|----------------------------|----------------|
| API Gateway | 1 | 1h | N/A | Multi-AZ failover | Multi-AZ + cross-region failover via Route 53 | DR-7 |
| Authentication (Cognito) | 1 | 1h | 15m | Single-region Cognito (no replication) | Cognito user pool replication | DR-2 |
| DynamoDB | 1 | 1h | 15m | PITR + AWS Backup (cross-region copy in prod) | PITR + **Global Tables** for Tier 1 tables | DR-1 |
| Neptune | 2 | 4h | 1h | AWS Backup with cross-region copy (prod) | AWS Backup + cross-region read replica or Global DB | DR-3 |
| OpenSearch | 2 | 4h | 1h | AWS Backup snapshots | AWS Backup + cross-cluster replication (CCR) | DR-4 |
| EKS Control Plane | 2 | 4h | N/A | AWS managed (multi-AZ) | AWS managed + secondary-region warm cluster | DR-7 |
| S3 (Artifacts) | 3 | 8h | 4h | AWS Backup vault (no CRR currently) | Cross-region replication on artifact buckets | DR-5 |
| Secrets Manager | 1 | 1h | N/A | Regional secrets (no replicas) | Native Secrets Manager multi-region replicas | DR-6 |
| CloudWatch Logs | 4 | 24h | 24h | S3 export (verify per log group) | S3 export with cross-region replicated bucket | DR-5 |

### Currently Operational Capabilities

What customers can rely on today:

- **AWS Backup vault** (`disaster-recovery.yaml`, Layer 5.5) is wired into the deploy chain. Production environments enable `EnableCrossRegion: true`, which performs cross-region backup *copies* to a DR region. This is point-in-time recovery, not active failover.
- **DynamoDB PITR** is enabled on Tier 1 tables.
- **Multi-AZ** failover is implicit in the EKS / API Gateway / Neptune / OpenSearch deployments within the primary region.

### Currently NOT Operational

What the original document claimed but is not yet deployed:

- DynamoDB **Global Tables** for cross-region active-active replication (DR-1).
- Cognito user pool replication (DR-2).
- Neptune cross-region read replica or Global Database (DR-3).
- OpenSearch cross-cluster replication (DR-4).
- S3 cross-region replication on artifact buckets (DR-5).
- Secrets Manager multi-region replicas for the Tier 1 secrets the failover path will need (DR-6).
- Multi-region failover orchestration (Route 53 failover records, the actual decision-and-cutover Lambda, drift detection on cross-region resources). The previous orchestration stub (`multi-region-global.yaml`) was detection / notification only and has been archived (DR-7).
- Sally's compliance controls for DR operations: two-person integrity on prod failover deploys, pre-signed change-sets, session recording, evidence-package generation for NIST CP-2/CP-9/CP-10 audit trail (DR-8).
- Drift detection + observability federation across regions (DR-9).

Each gap is tracked as a sub-issue under the umbrella DR initiative. Until the matched sub-issue closes, the corresponding Tier-1 RTO commitment is **aspirational, not contractual**.

### Audit / Compliance Posture

- The **Backup tier** (AWS Backup vault + PITR + cross-region backup copy) is audit-defensible today: deployments are codified, backups are enumerable via the AWS Backup API, restore procedures are documented and tested.
- The **Failover tier** (sub-1h RTO via cross-region active-active or active-passive) is **not** audit-defensible today. Auditors asking "show me the last successful end-to-end failover with measured RTO" cannot be answered until the DR initiative completes. This is captured in `SECURITY.md` under the SaaS DR scope statement.

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
