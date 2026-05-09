# OpenSearch Cross-Region Failover Runbook

**Last Updated:** 2026-05-09
**Tracked As:** Tier 2 (RTO 4h / RPO 1h) per `docs/support/architecture/disaster-recovery.md`
**Owner:** Platform Engineering
**Sub-issue:** DR-4 (#147) closed via this runbook
**DR umbrella:** #143

---

## Overview

This runbook covers OpenSearch cross-region failover via cross-region backup restore. It is the operational procedure that pairs with the AWS Backup configuration in `deploy/cloudformation/disaster-recovery.yaml` to deliver OpenSearch's Tier 2 commitment (RTO 4h / RPO 1h).

**Why this approach over OpenSearch Cross-Cluster Replication (CCR):**

OpenSearch CCR (active follower cluster) requires (a) a permanently-running follower domain in the secondary region (a minimum 3-node production cluster costs ~$300+/month even when idle), (b) the OpenSearch security plugin's CCR API which is not exposed via CloudFormation, and (c) VPC peering or Transit Gateway between primary and secondary VPCs. AWS Backup with cross-region copy meets the same Tier 2 SLA without those costs or operational surface.

If OpenSearch active replication is required for a Tier 1 commitment in the future (RTO < 1h, near-zero RPO), this runbook is replaced by a CCR setup. Until then, hourly cross-region snapshot copy achieves Tier 2 cleanly.

## What's already in place

`deploy/cloudformation/disaster-recovery.yaml` (Layer 5.5) configures:

- **AWS Backup vault** in the primary region encrypted with the BackupKMSKey from the foundation layer.
- **Hourly Backup Plan** (`HourlyBackupPlan`) with cross-region copy to `aura-dr-vault-{env}` in `us-west-2`. Production-only via the `IsProduction` condition. Recovery points retained 7 days primary / 14 days secondary.
- **`OpenSearchBackupSelection`** (DR-4 / #147) selects the production OpenSearch domain (`${ProjectName}-${Environment}` ARN pattern) into the hourly plan.
- **Cross-region copy action** added to `HourlyBackupPlan` so the same selection covers DynamoDB hot tables and the OpenSearch domain.

Effective targets in production:

- **RPO:** ~1h (hourly snapshots; in-flight indexing between snapshot windows is the data-loss exposure)
- **RTO:** ~4h (snapshot restore + index warmup + traffic redirect)

## Failover decision criteria

Execute this procedure only when one of the following is true:

1. **Primary region declared unavailable** by AWS Health Dashboard or internal incident command.
2. **OpenSearch domain in primary** is in `Red` cluster health for > 30 minutes with no recovery path (data nodes lost, master-node quorum broken, EBS volume corruption).
3. **Disaster recovery drill** scheduled per `docs/support/architecture/disaster-recovery.md` quarterly cadence.

## Pre-failover checklist

- [ ] Incident commander has called the failover decision.
- [ ] Latest cross-region recovery point timestamp known (use `aws backup list-recovery-points-by-backup-vault` -- see Step 1).
- [ ] If recovery point is older than RPO target (1h), confirm the data-loss exposure is acceptable for the incident.
- [ ] Primary-region OpenSearch domain status confirmed via `aws opensearch describe-domain --region us-east-1 --domain-name aura-prod` (or document the timeout / API error).
- [ ] Confirmed which OpenSearch indices are critical (vector embeddings: `aura-vectors-*`; logs: `aura-logs-*`; audit: covered by S3 audit pipeline, separate path).

## Failover procedure

### Step 1: Identify the most recent cross-region recovery point

```bash
SECONDARY_REGION=us-west-2
PROJECT=aura
ENV=prod

aws backup list-recovery-points-by-backup-vault \
    --backup-vault-name "${PROJECT}-dr-vault-${ENV}" \
    --region "${SECONDARY_REGION}" \
    --query 'RecoveryPoints[?contains(ResourceArn, `domain/`)].[RecoveryPointArn, CreationDate, Status]' \
    --output table
```

Pick the most recent `COMPLETED` recovery point. Note its `RecoveryPointArn`.

### Step 2: Pre-staged secondary-region networking

DR-3.0 (#156) provides the VPC; OpenSearch needs a security group + subnet selection. If pre-staged, capture the IDs from CloudFormation exports:

```bash
SECONDARY_SUBNET_IDS=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-secondary-private-subnet-ids-${ENV}'].Value | [0]" \
    --output text)

SECONDARY_VPC_ID=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-secondary-vpc-id-${ENV}'].Value | [0]" \
    --output text)

SECONDARY_VPC_CIDR=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-secondary-vpc-cidr-${ENV}'].Value | [0]" \
    --output text)

# Create security group if not pre-staged
SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT}-opensearch-sg-${ENV}-dr" \
    --description "OpenSearch DR access" \
    --vpc-id "${SECONDARY_VPC_ID}" \
    --region "${SECONDARY_REGION}" \
    --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress \
    --group-id "${SG_ID}" \
    --protocol tcp \
    --port 443 \
    --cidr "${SECONDARY_VPC_CIDR}" \
    --region "${SECONDARY_REGION}"
```

These should be permanently deployed via an `opensearch-secondary-foundation.yaml` template in a future PR; for now they're operator-created at failover time.

### Step 3: Restore OpenSearch domain in secondary region

```bash
RECOVERY_POINT_ARN="<from Step 1>"

# Get a restore role (already provisioned by disaster-recovery.yaml in the primary
# region; AWS Backup uses the same role pattern in the secondary region)
RESTORE_ROLE_ARN=$(aws cloudformation list-exports \
    --region "${SECONDARY_REGION}" \
    --query "Exports[?Name=='${PROJECT}-backup-role-arn-${ENV}'].Value | [0]" \
    --output text)

# Restore metadata: AWS Backup requires the destination domain name + VPC config
SUBNET_ARRAY=$(echo "${SECONDARY_SUBNET_IDS}" | tr ',' '\n' | head -3 | jq -R . | jq -sc .)

aws backup start-restore-job \
    --recovery-point-arn "${RECOVERY_POINT_ARN}" \
    --metadata "{\"DomainName\":\"${PROJECT}-${ENV}-dr\",\"SubnetIds\":${SUBNET_ARRAY},\"SecurityGroupIds\":[\"${SG_ID}\"]}" \
    --iam-role-arn "${RESTORE_ROLE_ARN}" \
    --resource-type OpenSearch \
    --region "${SECONDARY_REGION}"
```

Restore time scales with index size. Expect 30-120 minutes for the typical Aura production embedding index. AWS Backup handles index restoration; cluster boot + warm-up adds ~10-15 minutes.

### Step 4: Verify the restored domain

```bash
aws opensearch describe-domain \
    --domain-name "${PROJECT}-${ENV}-dr" \
    --region "${SECONDARY_REGION}" \
    --query 'DomainStatus.[Created, Processing, EngineVersion, Endpoints]' \
    --output table
```

Wait until `Processing=False` and `Created=True`. Note the VPC endpoint -- application connections target this hostname.

Sanity-check cluster health and index document counts:

```bash
ENDPOINT="<vpc-endpoint-from-above>"

# From a bastion in the secondary VPC
curl -X GET "https://${ENDPOINT}/_cluster/health?pretty"
curl -X GET "https://${ENDPOINT}/_cat/indices?v"
```

Cluster status must be `green` or `yellow`. `red` means restore failed -- abort traffic redirect, file an incident, and try the next-most-recent recovery point.

### Step 5: Redirect application traffic

The application's OpenSearch client config picks the endpoint via `OpenSearchConnectionSecret` in Secrets Manager. DR-6 (#149) configured native multi-region replication for that secret, so the secondary-region replica is already available.

```bash
NEW_ENDPOINT="<from Step 4>"

# Update only the secondary-region replica; the primary will follow when failback runs
aws secretsmanager update-secret \
    --secret-id "aura/${ENV}/opensearch-connection" \
    --secret-string "{\"host\": \"${NEW_ENDPOINT}\", \"port\": 443, \"use_ssl\": true, \"verify_certs\": true}" \
    --region "${SECONDARY_REGION}"
```

Application restart in the secondary region picks up the new endpoint on cold-start.

### Step 6: Validate

- Hit a known-shape vector search against the new endpoint:
  ```bash
  curl -X POST "https://${NEW_ENDPOINT}/aura-vectors-prod/_search" \
      --header "Content-Type: application/json" \
      --data '{"size": 1, "query": {"match_all": {}}}'
  ```
- Application health checks return `200`.
- Latency budget within Tier 2 RTO 4h.
- Document count on critical indices matches expected value for the recovery point timestamp +/- the indexing rate during the snapshot window.

## Post-failover follow-up

- File an incident report capturing actual RTO + RPO measurements.
- Update `docs/support/architecture/disaster-recovery.md` if new operational details emerged.
- Plan primary-region rebuild + reverse-failover when the primary is restored (separate runbook step).
- Re-index any documents written to the primary domain after the snapshot timestamp but before primary failure (only if the source records are still recoverable elsewhere).

## Rollback (failover wasn't needed)

If you started the restore but later determined failover wasn't necessary:

```bash
# Cancel restore (only works if not yet completed)
aws backup stop-backup-job --backup-job-id <id> --region "${SECONDARY_REGION}"

# Or, if the domain was created, delete it:
aws opensearch delete-domain \
    --domain-name "${PROJECT}-${ENV}-dr" \
    --region "${SECONDARY_REGION}"
```

## Drill cadence

Per `docs/support/architecture/disaster-recovery.md`:

- **Quarterly:** regional failover test (next: 2026-07-15).
- **Annual:** full DR exercise (next: 2026-06-15).

Each drill should produce evidence per Sally's controls (DR-8 / #151 when that ships): timestamped logs, measured RTO, signed approval ticket. Until DR-8 lands, capture drill artifacts manually under `s3://aura-compliance-evidence/dr-drills/<quarter>/`.

## Improvement opportunities (out of scope for DR-4)

- **Pre-staged secondary-region OpenSearch foundation** (subnet group + security group via `opensearch-secondary-foundation.yaml`). Removes Step 2 manual work and shaves ~10 minutes off RTO.
- **Pre-warmed standby domain** in secondary region. Cuts RTO from ~4h to ~30 min but adds ~$300+/month idle cost. Track as Tier 1 enhancement if business case appears.
- **OpenSearch CCR** (active follower). Active-active replication via the OpenSearch security plugin's CCR API. Configurable outside CFN. Closes the Tier 1 gap if a future commitment requires sub-hour RPO + sub-hour RTO.

## References

- `deploy/cloudformation/disaster-recovery.yaml` -- the AWS Backup setup (HourlyBackupPlan + OpenSearchBackupSelection)
- `deploy/cloudformation/opensearch.yaml` -- primary-region OpenSearch domain
- `deploy/cloudformation/networking-secondary.yaml` -- DR-3.0 secondary-region VPC foundation
- `docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md` -- companion runbook (DR-3 / #146)
- `docs/support/architecture/disaster-recovery.md` -- service tier definitions and RTO/RPO targets
- DR initiative umbrella: #143
- This runbook closes: DR-4 (#147)
