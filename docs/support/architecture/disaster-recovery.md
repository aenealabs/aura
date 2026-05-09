# Disaster Recovery

**Version:** 1.2
**Last Updated:** May 9, 2026
**Product:** Project Aura by Aenea Labs

---

## Scope

**This document covers Aenea Labs SaaS DR posture only.** Self-hosted Aura customers (ADR-049, deployed via Podman in their own environments) are responsible for their own continuity planning per their deployment model. SaaS multi-region capabilities described here do not extend to self-hosted deployments.

---

## Overview

This document describes Project Aura's disaster recovery (DR) strategy, including backup procedures, recovery objectives, and failover processes. The DR architecture is designed to meet enterprise requirements for business continuity.

> **State of this document (May 9, 2026):** Sections below are split into **Current** (what is deployed and verifiable today) and **Target** (what is committed but not yet implemented). The Current/Target split was added during a May 2026 honesty pass after a deploy-chain audit found the original multi-region orchestration template (`multi-region-global.yaml`) was detection / notification only -- no actual failover capability. That template has been archived and replaced by `multi-region-failover.yaml` (Layer 5.15) + `multi-region-pipeline.yaml` (Layer 6.22) under DR-7. The DR umbrella initiative (#143) closed all 13 sub-issues by May 9, 2026; the Tier 1 RTO/RPO targets are now backed by deployed infrastructure, not aspirational. Cross-region runbooks, evidence-package generation, and HITL-gated Step Functions failover orchestration are operational. The Current/Target split is preserved below as a historical record of the work delivered.

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
| API Gateway | 1 | 1h | N/A | Multi-AZ failover + Route 53 health-check-driven failover records (DR-7) | Same | DR-7 (closed) |
| Authentication (Cognito) | 1 | 1h | 15m | Lambda-based mirror to DDB Global Table + standby user pool in us-west-2 + hydrator Lambda + force re-auth (ADR-091) | Same (active CCR not feasible: Cognito has no native cross-region replication) | DR-2 (closed) |
| DynamoDB | 1 | 1h | 15m | PITR + AWS Backup + **Global Tables** for 9 Tier 1 tables + **audit pipeline** for 3 audit tables (Streams -> Kinesis -> Firehose -> S3 Object Lock) | Same | DR-1 + DR-1.1 + DR-1.2 (all closed) |
| Neptune | 2 | 4h | 1h | AWS Backup with cross-region copy (prod) + failover runbook | Same; CFN does not support Neptune Global Database (May 2026) | DR-3 (closed) |
| OpenSearch | 2 | 4h | 1h | AWS Backup with hourly snapshots + cross-region copy (prod) + failover runbook | Same; CCR deferred (cost: ~$300+/mo idle follower; not justified for current Tier 2 commitment) | DR-4 (closed) |
| EKS Control Plane | 2 | 4h | N/A | AWS managed (multi-AZ) | AWS managed + secondary-region warm cluster | DR-7 |
| S3 (Artifacts) | 3 | 8h | 4h | CRR on `ArtifactsBucket` + `CodeRepositoryBucket` (prod only); AWS Backup vault for the rest | Same; per-bucket follow-ups for other-template Tier-relevant buckets | DR-5 (closed; follow-ups for non-`s3.yaml` buckets) |
| Secrets Manager | 1 | 1h | N/A | Native multi-region replicas (10 Tier 1 secrets, prod only) | Same | DR-6 (closed) |
| CloudWatch Logs | 4 | 24h | 24h | S3 export (verify per log group) | S3 export with cross-region replicated bucket | DR-5 |

### Currently Operational Capabilities

What customers can rely on today:

- **AWS Backup vault** (`disaster-recovery.yaml`, Layer 5.5) is wired into the deploy chain. Production environments enable `EnableCrossRegion: true`, which performs cross-region backup *copies* to a DR region. This is point-in-time recovery, not active failover.
- **DynamoDB PITR** is enabled on Tier 1 tables.
- **Multi-AZ** failover is implicit in the EKS / API Gateway / Neptune / OpenSearch deployments within the primary region.
- **Secrets Manager native multi-region replicas** for the 10 Tier 1 secrets (Bedrock config in `secrets.yaml` and `aura-bedrock-infrastructure.yaml`, API keys, DB encryption key, JWT signing secret, JWT signing key for IdP, plus the 4 IdP credential templates: LDAP, OIDC, SAML, PingID). Production environments only; gated on `IsProduction` so dev/qa do not pay replica costs. Replicas use the secondary region's AWS-managed default key, consistent with primary-region encryption (per-region customer-managed CMKs are tracked as a separate hardening pass). Closed by DR-6 (#149).
- **S3 Cross-Region Replication** on the two Tier 3 customer-data buckets in `s3.yaml`: `ArtifactsBucket` (analysis outputs, generated reports) and `CodeRepositoryBucket` (uploaded customer code). Production environments only; gated on `IsProduction`. Destination buckets live in `deploy/cloudformation/s3-replica.yaml` deployed manually to the secondary region (default `us-west-2`); orchestration of the cross-region deploy is tracked under DR-7 (#150). Replication uses S3-managed AES256 encryption matching the primary buckets. Closed by DR-5 (#148). Other buckets in the deploy chain (model-assurance, red-team, vuln-scan, calibration-pipeline, sandbox) are tracked as separate per-template follow-ups -- their owners decide whether their data is Tier-relevant.
- **Per-region customer-managed KMS keys** for the auth-credential DynamoDB tables that DR-1 will replicate. `AuthCredentialsKMSKey` in `kms.yaml` (us-east-1) and `AuthCredentialsReplicaKey` in `kms-replica-secondary.yaml` (us-west-2) are **independent keys** -- not multi-region replicas -- per Sally's NIST 800-53 SC-12 guidance ("do not share keys across regions") and Tara's per-region CMK recommendation. Each key's policy allows the DynamoDB service principal only in its own region (`aws:SourceRegion` condition). Production environments only; gated on `IsProduction`. Closed by DR-1.0 (#153).
- **DynamoDB Global Tables for 7 Tier 1 tables** -- main DR-1 scope (#144). Converted from `AWS::DynamoDB::Table` to `AWS::DynamoDB::GlobalTable` across 4 templates. Replicas in `${SecondaryRegion}` (default us-west-2), production only, gated on `IsProduction`. Auth-credential tables (`IdPConfigurationsTable`, `OAuthConnectionsTable`) use per-region customer-managed CMKs from DR-1.0; non-credential tables (`PlatformSettingsTable`, `AutonomyPoliciesTable`, `RepositoriesTable`, `UserOnboardingTable`, `TeamInvitationsTable`) use AWS-managed encryption. Each table has a CloudWatch replication-lag alarm (DR-9 partial / #152) at 5min threshold (1/3 of RPO 15min budget). Region-bound tables (`AuthSessionsTable`, `UserSessionsTable`, `SAMLStateTable`, `OIDCStateTable`) intentionally NOT replicated -- force re-auth on failover per Sally's review.
- **Plus 2 reclassified Tier 1 tables** as Global Tables under DR-1.2 (#155): `AnomaliesTable` (ADR-072 detection ground truth) and `CodebaseMetadataTable` (rebuild = full re-ingestion of every onboarded customer repo).
- **Audit pipeline for 3 audit-shape Tier 1 tables** -- DR-1.1 scope (#154). `IdPAuditTable`, `AutonomyDecisionsTable`, `PolicyAuditTable` keep their regional `AWS::DynamoDB::Table` shape (Global Tables' last-writer-wins replication would violate NIST AU-9(1) -- clock-skewed overwrites of audit records). Each table's `KinesisStreamSpecification` forwards writes through a per-table Kinesis Data Stream into a per-table Firehose Delivery Stream that lands in a shared S3 audit bucket with **Object Lock enabled (governance mode, ~7-year retention)**. The audit bucket has cross-region replication to `${SecondaryRegion}` (audit-pipeline-replica.yaml) where Object Lock also applies. Athena queries against the bucket give compliance teams a queryable interface in either region. Closed by DR-1.1 (#154).
- **Secondary-region VPC foundation** in us-west-2 (`networking-secondary.yaml`, Layer 1.11). Default CIDR 10.1.0.0/16 (non-overlapping with primary 10.0.0.0/16), 3 private subnets across us-west-2a/b/c for HA, VPC Flow Logs to CloudWatch (90-day retention). Production-only via `IsProduction`. Deliberate non-goals: no IGW / public subnets / NAT (deferred to DR-7 orchestration when application-layer failover lands; saves ~$33/mo/AZ on NAT alone). Service-specific subnet groups + security groups land with their respective service templates (Neptune in DR-3, OpenSearch in DR-4). Closed by DR-3.0 (#156).
- **Neptune cross-region failover via AWS Backup** -- DR-3 scope (#146). CloudFormation does not support Neptune Global Database (verified May 2026: `AWS::Neptune::GlobalCluster` does not exist, `AWS::RDS::GlobalCluster` does not accept the `neptune` engine, `AWS::Neptune::DBCluster` lacks `GlobalClusterIdentifier`). Tier 2 commitment (RTO 4h / RPO 1h) is met instead by the existing AWS Backup configuration in `disaster-recovery.yaml` (Layer 5.5): daily Neptune backups with cross-region copy in production. Failover procedure documented in `docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md` -- restore from latest us-west-2 recovery point, redirect application via `NeptuneConnectionSecret` (already replicated cross-region via DR-6). RPO is currently ~24h (daily); upgrading to hourly snapshots is documented as a separate improvement opportunity in the runbook. Closed by DR-3 (#146).
- **OpenSearch cross-region failover via AWS Backup** -- DR-4 scope (#147). Hourly OpenSearch snapshots are now selected into the existing `HourlyBackupPlan` in `disaster-recovery.yaml` (Layer 5.5) via the new `OpenSearchBackupSelection`. The hourly plan now also performs cross-region copy to `aura-dr-vault-{env}` in us-west-2 (production only, retention: 7 days primary / 14 days secondary). This delivers Tier 2 RPO 1h / RTO 4h without the cost of an active OpenSearch follower cluster (~$300+/mo idle). Failover procedure documented in `docs/runbooks/OPENSEARCH_FAILOVER_RUNBOOK.md` -- restore from latest secondary-region recovery point into a `${ProjectName}-${ENV}-dr` domain in the DR-3.0 secondary VPC, redirect application via `OpenSearchConnectionSecret` (already replicated cross-region via DR-6). Active-active OpenSearch CCR is deferred as a Tier 1 enhancement; not justified for the current Tier 2 commitment. Closed by DR-4 (#147).
- **DR compliance controls** -- DR-8 scope (#151). Sally's seven NIST 800-53 (CP-2 / CP-4(1) / CP-9 / CP-10) controls deployed via `dr-compliance-controls.yaml` (Layer 5.16): (1) two-person integrity Lambda gating `states:SendTaskSuccess` on two distinct IAM principals + break-glass single-principal mode with enhanced audit; (2) pre-signed change-set discipline (deploy convention; IAM split tracked separately); (3) SSM Session Manager S3-logged session-recording bucket + custom session preferences document; (4) AWS Signer profile + Lambda code-signing config (infrastructure ready; existing inline-code Lambdas need migration to S3 packages to actually use it); (5) cross-region IAM trust scoping (documented; tighter `aws:RequestedRegion` conditions tracked separately); (6) evidence-package generator Lambda invoked by the failover pipeline at end of every execution (`CaptureEvidenceSuccess` / `CaptureEvidenceRollback` / `CaptureEvidenceFailure` states) -- writes manifest + state-machine history + approval chain into `aura-compliance-evidence-{account}-prod` S3 bucket with Object Lock GOVERNANCE 7-year retention; (7) drill-cadence enforcement via weekly EventBridge-scheduled Lambda + CloudWatch alarm (threshold 90 days from latest evidence package). Operator-facing guide: `docs/runbooks/DR_COMPLIANCE_CONTROLS_GUIDE.md`. The auditor's killer question -- *"show me the last successful end-to-end failover with measured RTO and approval chain"* -- now has an answer: `s3://aura-compliance-evidence-{account}-prod/<quarter>/<execution>/manifest.json`. Closed by DR-8 (#151).
- **Multi-region failover orchestration pipeline** -- DR-7 scope (#150). Two new templates ship the orchestration layer: `multi-region-failover.yaml` (Layer 5.15) provides the global resources -- Route 53 health checks, Route 53 failover records (`app.aenealabs.com` PRIMARY/SECONDARY), SNS notification topic, and three cutover Lambdas (`CognitoHydratorTrigger`, `CognitoSSMCutover`, `DataPlaneSecretCutover`) that codify the manual cutover steps from the per-service failover runbooks. `multi-region-pipeline.yaml` (Layer 6.22) deploys a Step Functions Standard state machine that orchestrates the end-to-end failover with HITL approval gates at every destructive or externally-visible step (data-plane prep approval, Neptune restore prompt, OpenSearch restore prompt, traffic-cutover approval). The pipeline reuses the existing `aura-hitl-approvals` table for approvals via `.waitForTaskToken`. Operator-facing runbook: `docs/runbooks/MULTI_REGION_DR_OPERATIONS.md` (composes the per-service runbooks into a single sequence). Production-only. There is intentionally no automatic failover trigger -- per Sally's NIST CP-2 guidance, regional failover requires human authorization; Route 53 health-check-driven DNS failover handles ALB-layer cutover automatically once enabled. Closed by DR-7 (#150).
- **Cognito cross-region failover via Lambda-based mirror** -- DR-2 scope (#145). Cognito has no native cross-region replication and is not supported by AWS Backup. Per ADR-091, replication is implemented via a `PostConfirmation` + `PostAuthentication` Lambda that mirrors minimal user state (`sub`, `email`, `groups`, `mfa_enabled_flag`, `dr_eligible`, timestamps -- intentionally NOT password hashes or MFA secrets) into a DynamoDB Global Table (`user-mirror-table.yaml`, Layer 2.22) replicated to us-west-2. A standby user pool (`cognito-secondary.yaml`, Layer 4.14) sits empty in us-west-2 and is hydrated at failover time by a hydrator Lambda (`cognito-dr-hydrator.yaml`, Layer 6.21) whose EventBridge schedule is **disabled by default** (CloudWatch alarm fires on any invocation outside an active failover). Per-region customer-managed CMKs for the mirror table (consistent with DR-1.0 SC-12). Failover procedure documented in `docs/runbooks/COGNITO_FAILOVER_RUNBOOK.md`. Tier 1 commitment met (RPO 15m via sub-second GT replication; RTO 1h via batched `AdminCreateUser` + `AdminResetUserPassword`). Compliance bake-ins per Sally's NIST review (IA-2, IA-5, AU-9, SC-12) include forced password reset on first post-failover login (compensating control for IA-5), forced MFA re-enrollment for users with `mfa_enabled_flag=true`, and CloudTrail logging of every privileged hydrator API call. Closed by DR-2 (#145).

### Currently NOT Operational

What the original document claimed but is not yet deployed:

- ~~DynamoDB **Global Tables** for cross-region active-active replication (DR-1).~~ **DONE for the 7 in-scope Tier 1 tables -- closed by DR-1 (#144).** See "Currently Operational Capabilities" above. Audit-shape tables tracked under DR-1.1 (#154); reclassifications tracked under DR-1.2 (#155).
- ~~Cognito user pool replication (DR-2).~~ **Closed via DR-2 (#145), ADR-091** -- Lambda-based mirror to DDB Global Table + standby pool + hydrator Lambda + force re-auth on failover (`docs/runbooks/COGNITO_FAILOVER_RUNBOOK.md`). Native Cognito cross-region replication is not supported by AWS; this is the AWS-recommended pattern.
- ~~Neptune cross-region read replica or Global Database (DR-3).~~ **Closed via DR-3 (#146)** -- CFN does not support Neptune Global Database; Tier 2 commitment met via existing AWS Backup cross-region copy + failover runbook (`docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md`).
- ~~OpenSearch cross-cluster replication (DR-4).~~ **Closed via DR-4 (#147)** -- Tier 2 commitment met via hourly AWS Backup snapshots with cross-region copy + failover runbook (`docs/runbooks/OPENSEARCH_FAILOVER_RUNBOOK.md`). Active-active CCR deferred (Tier 1 enhancement only).
- ~~S3 cross-region replication on artifact buckets (DR-5).~~ **DONE for the two `s3.yaml` Tier 3 buckets -- closed by DR-5 (#148).** Per-template follow-ups for other-template artifact buckets (model-assurance, red-team, vuln-scan, calibration-pipeline) tracked separately.
- ~~Secrets Manager multi-region replicas for the Tier 1 secrets the failover path will need (DR-6).~~ **DONE -- closed by DR-6 (#149).** See "Currently Operational Capabilities" above.
- ~~Multi-region failover orchestration (Route 53 failover records, the actual decision-and-cutover Lambda, drift detection on cross-region resources). The previous orchestration stub (`multi-region-global.yaml`) was detection / notification only and has been archived (DR-7).~~ **Closed via DR-7 (#150)** -- `multi-region-failover.yaml` (Layer 5.15, Route 53 health checks + failover records + cutover Lambdas) and `multi-region-pipeline.yaml` (Layer 6.22, Step Functions orchestrator with HITL approval gates) deployed together with `docs/runbooks/MULTI_REGION_DR_OPERATIONS.md`.
- ~~Sally's compliance controls for DR operations: two-person integrity on prod failover deploys, pre-signed change-sets, session recording, evidence-package generation for NIST CP-2/CP-9/CP-10 audit trail (DR-8).~~ **Closed via DR-8 (#151)** -- 7 controls deployed via `dr-compliance-controls.yaml` (Layer 5.16) + `multi-region-pipeline.yaml` evidence-capture states. Operator guide: `docs/runbooks/DR_COMPLIANCE_CONTROLS_GUIDE.md`.
- ~~Drift detection + observability federation across regions (DR-9).~~ **Closed via DR-9 (#152)** -- `dr-monitoring.yaml` (Layer 5.14) deploys SNS topic, weekly drift-detection Lambda, and cross-region CloudWatch dashboard; nine replication-lag alarms (5min threshold, 1/3 of RPO 15min budget) wired to the DR alert SNS.

**The DR initiative (#143) is closed (May 2026): all 13 sub-issues resolved.** The Tier-1 RTO/RPO commitments are now backed by deployed infrastructure, not just aspirational targets. The "Currently Operational Capabilities" section above describes the deployed posture.

### Audit / Compliance Posture

- The **Backup tier** (AWS Backup vault + PITR + cross-region backup copy) is audit-defensible today: deployments are codified, backups are enumerable via the AWS Backup API, restore procedures are documented and tested.
- The **Failover tier** (sub-1h RTO via cross-region active-passive) is now audit-defensible. The full DR initiative (#143) is closed; auditors asking *"show me the last successful end-to-end failover with measured RTO and approval chain"* are answered with `s3://aura-compliance-evidence-{account}-prod/<quarter>/<execution-name>/manifest.json` produced by DR-8's evidence-package generator. The `SECURITY.md` SaaS DR scope statement was updated in May 2026 to reflect this audit-defensible posture.

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
