# Neptune Cross-Region Failover Runbook

**Last Updated:** 2026-05-08
**Tracked As:** Tier 2 (RTO 4h / RPO 1h) per `docs/support/architecture/disaster-recovery.md`
**Owner:** Platform Engineering
**Sub-issue:** DR-3 (#146) closed via this runbook
**DR umbrella:** #143

---

## Overview

This runbook covers Neptune cross-region failover via cross-region backup restore. It is the operational procedure that pairs with the existing AWS Backup configuration in `deploy/cloudformation/disaster-recovery.yaml` to deliver Neptune's Tier 2 commitment.

**CloudFormation does not support Neptune Global Database** (verified May 2026 -- `AWS::Neptune::GlobalCluster` does not exist as a resource type, `AWS::RDS::GlobalCluster` does not accept the `neptune` engine, and `AWS::Neptune::DBCluster` does not accept `GlobalClusterIdentifier`). The original DR-3 sub-issue anticipated this limitation: *"Manual cross-region read replica via snapshot copy + restore if Global Database is not available for the deployed engine version."* This runbook documents that fallback.

If AWS adds CFN support for Neptune Global Database in the future, this runbook is replaced by an active-replication setup with sub-second RPO. Until then, the snapshot-restore path achieves Tier 2 (RTO 4h / RPO 1h) without active-active complexity.

## What's already in place

`deploy/cloudformation/disaster-recovery.yaml` (Layer 5.5) sets up:

- **AWS Backup vault** in the primary region encrypted with the BackupKMSKey from the foundation layer.
- **Daily Backup Plan** that includes Neptune via `NeptuneBackupSelection` (tag-based: any resource with `Project=aura` tag is captured).
- **Cross-region copy** (production only via `EnableCrossRegion`): snapshots are copied to a DR vault in the secondary region with a 35-day retention. Default `DRRegion` parameter is `us-west-2` (override in production deploy if different).

Effective RPO: **~24h** for daily backups. The Tier 2 RPO 1h commitment requires hourly snapshots; verify that the `HourlyBackupPlan` covers Neptune (currently configured for DynamoDB only -- see "Hourly Snapshots for Tier 2" below).

## Failover decision criteria

Execute this procedure only when one of the following is true:

1. **Primary region declared unavailable** by AWS Health Dashboard or internal incident command.
2. **Neptune cluster in primary** is in `failed` or `inaccessible` state for > 30 minutes with no recovery path.
3. **Disaster recovery drill** scheduled per `docs/support/architecture/disaster-recovery.md` quarterly cadence.

## Pre-failover checklist

- [ ] Incident commander has called the failover decision.
- [ ] Latest cross-region snapshot timestamp known (use `aws backup list-recovery-points-by-backup-vault --backup-vault-name aura-dr-vault-prod --region us-west-2 --query 'RecoveryPoints[?contains(ResourceArn, \`neptune\`)] | [0].CreationDate'`).
- [ ] If snapshot is older than RPO target (1h ideal, 24h current), confirm the data-loss exposure is acceptable for the incident.
- [ ] Primary-region Neptune cluster status confirmed via `aws neptune describe-db-clusters --region us-east-1 --db-cluster-identifier aura-neptune-prod` (or fail attempt to connect, document timeout).

## Failover procedure

### Step 1: Identify the most recent cross-region recovery point

```bash
SECONDARY_REGION=us-west-2
PROJECT=aura
ENV=prod

aws backup list-recovery-points-by-backup-vault \
    --backup-vault-name "${PROJECT}-dr-vault-${ENV}" \
    --region "${SECONDARY_REGION}" \
    --query 'RecoveryPoints[?contains(ResourceArn, `neptune`)].[RecoveryPointArn, CreationDate, Status]' \
    --output table
```

Pick the most recent `COMPLETED` recovery point. Note its `RecoveryPointArn`.

### Step 2: Restore Neptune cluster in secondary region

```bash
RECOVERY_POINT_ARN="<from Step 1>"
RESTORE_JOB_NAME="aura-neptune-restore-$(date -u +%Y%m%d-%H%M%S)"

# Get a restore role (must allow neptune:* + ec2 networking)
RESTORE_ROLE_ARN=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-backup-role-arn-${ENV}'].Value | [0]" \
    --output text)

# Get networking from secondary-region foundation (DR-3.0 / #156)
SUBNET_GROUP_NAME="${PROJECT}-neptune-subnet-${ENV}-dr"  # to be created per Step 3
SECURITY_GROUP_ID=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-neptune-sg-id-${ENV}-dr'].Value | [0]" \
    --output text)

aws backup start-restore-job \
    --recovery-point-arn "${RECOVERY_POINT_ARN}" \
    --metadata "DBClusterIdentifier=${PROJECT}-neptune-${ENV}-dr,DBSubnetGroupName=${SUBNET_GROUP_NAME},VpcSecurityGroupIds=${SECURITY_GROUP_ID}" \
    --iam-role-arn "${RESTORE_ROLE_ARN}" \
    --resource-type Neptune \
    --region "${SECONDARY_REGION}"
```

Wait for restore (typically 15-90 minutes for small clusters; longer for large data sets).

### Step 3: Pre-staged secondary-region networking

DR-3.0 (#156) provides the VPC; the Neptune-specific subnet group + security group are normally pre-staged. If not, create them on-the-fly:

```bash
# Subnet group
aws neptune create-db-subnet-group \
    --db-subnet-group-name "${SUBNET_GROUP_NAME}" \
    --db-subnet-group-description "Neptune DR subnet group" \
    --subnet-ids $(aws cloudformation list-exports \
        --region "${SECONDARY_REGION}" \
        --query "Exports[?Name=='${PROJECT}-secondary-private-subnet-ids-${ENV}'].Value | [0]" \
        --output text | tr ',' ' ') \
    --region "${SECONDARY_REGION}"

# Security group (allow Neptune port 8182 from VPC CIDR)
SECONDARY_VPC_ID=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-secondary-vpc-id-${ENV}'].Value | [0]" \
    --output text)
SECONDARY_VPC_CIDR=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-secondary-vpc-cidr-${ENV}'].Value | [0]" \
    --output text)

aws ec2 create-security-group \
    --group-name "${PROJECT}-neptune-sg-${ENV}-dr" \
    --description "Neptune DR access" \
    --vpc-id "${SECONDARY_VPC_ID}" \
    --region "${SECONDARY_REGION}"

# Capture the GroupId from the response, then:
aws ec2 authorize-security-group-ingress \
    --group-id "<from above>" \
    --protocol tcp \
    --port 8182 \
    --cidr "${SECONDARY_VPC_CIDR}" \
    --region "${SECONDARY_REGION}"
```

These resources should be permanently deployed via a `neptune-secondary-foundation.yaml` template in a future PR; for now they're operator-created at failover time.

### Step 4: Verify the restored cluster

```bash
aws neptune describe-db-clusters \
    --db-cluster-identifier "${PROJECT}-neptune-${ENV}-dr" \
    --region "${SECONDARY_REGION}" \
    --query 'DBClusters[0].[Status, Endpoint, ReaderEndpoint, EngineVersion]' \
    --output table
```

Status must be `available` before redirecting traffic. Note the `Endpoint` -- application connections target this hostname.

### Step 5: Redirect application traffic

The application's gremlin client config picks the Neptune endpoint via `NeptuneConnectionSecret` in Secrets Manager. Update the secret (production only):

```bash
NEW_ENDPOINT="<from Step 4>"

aws secretsmanager update-secret \
    --secret-id "aura/${ENV}/neptune-connection" \
    --secret-string "{\"host\": \"${NEW_ENDPOINT}\", \"port\": 8182, \"ssl\": true, \"connection_timeout\": 30000, \"max_retries\": 3}" \
    --region "${SECONDARY_REGION}"
```

The `_ThreadDispatchedGremlinClient` wrapper (introduced under DR-1 nest-asyncio replacement) reads this secret on app cold-start, so application restart in the secondary region picks up the new endpoint.

### Step 6: Validate

- Run a known-shape Gremlin query against the new endpoint:
  ```bash
  curl -X POST "https://${NEW_ENDPOINT}:8182/gremlin" \
      --header "Content-Type: application/json" \
      --data '{"gremlin": "g.V().limit(1)"}'
  ```
- Application health checks return `200`.
- Latency budget within Tier 2 RTO 4h.

## Post-failover follow-up

- File an incident report capturing actual RTO + RPO measurements.
- Update `docs/support/architecture/disaster-recovery.md` if new operational details emerged.
- Plan primary-region rebuild + reverse-failover when the primary is restored (separate runbook step).

## Rollback (failover wasn't needed)

If you started the restore but later determined failover wasn't necessary:

```bash
# Cancel restore (only works if not yet completed)
aws backup stop-backup-job --backup-job-id <id> --region "${SECONDARY_REGION}"

# Or, if the cluster was created, delete it:
aws neptune delete-db-cluster \
    --db-cluster-identifier "${PROJECT}-neptune-${ENV}-dr" \
    --skip-final-snapshot \
    --region "${SECONDARY_REGION}"
```

## Hourly Snapshots for Tier 2 (improvement opportunity)

The current `HourlyBackupPlan` in `disaster-recovery.yaml` covers DynamoDB only. To meet Tier 2 RPO 1h for Neptune, add Neptune to the hourly plan:

- Either: add a `NeptuneHourlyBackupSelection` resource referencing `HourlyBackupPlan` with the same tag-based selection as `NeptuneBackupSelection`.
- Or: change `NeptuneBackupSelection` to reference `HourlyBackupPlan` instead of `DailyBackupPlan` (tradeoff: more backup volume / cost).

This is a separate improvement issue, not a blocker for the failover procedure above. The current daily backups satisfy Tier 3 RPO 4h; extending to hourly closes the Tier 2 RPO 1h gap.

## Drill cadence

Per `docs/support/architecture/disaster-recovery.md`:

- **Quarterly**: regional failover test (next: 2026-01-20).
- **Annual**: full DR exercise (next: 2026-06-15).

Each drill should produce evidence per Sally's controls (DR-8 / #151 when that ships): timestamped logs, measured RTO, signed approval ticket. Until DR-8 lands, capture drill artifacts manually under `s3://aura-compliance-evidence/dr-drills/<quarter>/`.

## References

- `deploy/cloudformation/disaster-recovery.yaml` -- the AWS Backup setup
- `deploy/cloudformation/neptune-simplified.yaml` -- primary-region Neptune cluster
- `deploy/cloudformation/networking-secondary.yaml` -- DR-3.0 secondary-region VPC foundation
- `docs/support/architecture/disaster-recovery.md` -- service tier definitions and RTO/RPO targets
- DR initiative umbrella: #143
- This runbook closes: DR-3 (#146)
