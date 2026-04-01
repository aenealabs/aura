# QA Environment Kill-Switch Runbook

**Last Updated:** March 19, 2026
**Script:** `scripts/qa_killswitch.py`
**Target Environment:** QA only (hardcoded, cannot target dev or prod)
**Owner:** Platform Engineering

---

## Overview

The QA kill-switch is a Python script that safely shuts down and restores the QA environment's always-on AWS services. It was created because the existing `qa-cost-scheduler.yaml` Lambda only scaled EKS node groups to zero, while Neptune, OpenSearch, EKS control plane, VPC Endpoints, ElastiCache, and dnsmasq (ECS Fargate) continued accruing significant costs regardless of usage.

The kill-switch deletes the CloudFormation stacks for these always-on services and can redeploy them when QA is needed again. Foundation stacks (networking, security, IAM, S3, DynamoDB) remain running at minimal cost so that restore only needs to recreate compute and data services.

**Current State:** QA environment is **shut down**. Neptune snapshot is preserved for data recovery if needed.

---

## Cost Breakdown

### Stacks Managed by the Kill-Switch

| Stack | Service | Monthly Cost | Shutdown Order |
|-------|---------|-------------|----------------|
| `aura-network-services-qa` | dnsmasq ECS Fargate | Low | Phase 2 |
| `aura-nodegroup-general-qa` | EKS Nodes (Spot) | Moderate | Phase 3 |
| `aura-nodegroup-memory-qa` | EKS Memory Nodes | included | Phase 3 |
| `aura-nodegroup-gpu-qa` | EKS GPU Nodes | included | Phase 3 |
| `aura-eks-qa` | EKS Control Plane | High | Phase 4 |
| `aura-neptune-qa` | Neptune db.t3.medium | High | Phase 5 |
| `aura-opensearch-qa` | OpenSearch t3.small | Moderate | Phase 5 |
| `aura-elasticache-qa` | ElastiCache t3.micro | Low | Phase 5 |
| `aura-vpc-endpoints-qa` | VPC Endpoints (8 interface) | Moderate | Phase 6 |
| **Total** | | **Significant** | |

### Stacks That Remain Running

| Stack | Service | Monthly Cost | Reason |
|-------|---------|-------------|--------|
| `aura-networking-qa` | VPC, subnets, route tables | ~$0 | No hourly charges |
| `aura-security-qa` | Security groups | ~$0 | No hourly charges |
| `aura-iam-qa` | IAM roles and policies | ~$0 | No charges |
| `aura-s3-qa` | S3 buckets | Minimal | Storage only |
| `aura-dynamodb-*-qa` | DynamoDB tables | Minimal | On-demand, idle |
| **Total** | | **Minimal** | |

---

## Post-Shutdown Cost Cleanup

After the kill-switch shuts down the 9 managed stacks, several cost sources persist in orphaned resources and services outside CloudFormation management. The `cleanup` subcommand targets these residual costs.

### Why Additional Cleanup Is Needed

After the kill-switch runs, the AWS Config recorder and other orphaned resources may continue running undetected outside the managed stacks.

| Source | Impact | Root Cause |
|--------|--------|------------|
| AWS Config recorder + rules | Significant | Config recorder not managed by the 9 kill-switch stacks; persists independently |
| Orphaned ALBs | Moderate | Kubernetes-managed load balancers (AWS LB Controller) are not deleted when EKS is removed via CloudFormation |
| CloudWatch log groups | Low | Log groups from deleted stacks retain stored data indefinitely |
| KMS CMKs | Minor | `aura-kms-qa` stack (DeletionPolicy: Retain) keeps keys alive |
| **Total** | **Varies** | |

### Cleanup Commands

```bash
# Dry-run: show what would be cleaned up
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py cleanup

# Execute cleanup (ELBs, Config, CloudWatch log retention)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py cleanup --execute

# Execute cleanup (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py cleanup --execute --force

# Execute cleanup INCLUDING KMS key deletion (see warning below)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py cleanup --execute --schedule-kms-deletion
```

### What Each Step Does

| Step | Action | Savings | Reversible? |
|------|--------|---------|-------------|
| Orphaned ELBs | Finds and deletes load balancers tagged by Kubernetes (AWS LB Controller) | Moderate | Yes - ALBs are recreated by the ALB Controller when EKS is restored |
| AWS Config | Stops the recorder, deletes the delivery channel, deletes all Config rules | Significant | Yes - compliance stack is redeployed on restore |
| CloudWatch Logs | Sets all aura log groups to 1-day retention (does NOT delete groups) | Low | Yes - retention is updated to standard values when stacks are redeployed |
| KMS CMKs | Schedules customer-managed keys for deletion (7-day pending window) | Minor | Irreversible for old snapshots, but **restore is unaffected** (see below) |

### KMS Key Deletion -- Restore Impact

> **KMS key deletion is irreversible after the 7-day pending window.** Old CMK-encrypted Neptune snapshots become permanently unrecoverable. However:
>
> - **Restore is NOT affected.** The restore templates (`neptune-simplified.yaml`, `opensearch.yaml`) deploy fresh clusters using AWS-managed encryption, not the CMKs. Neptune always starts as an empty cluster on restore -- old snapshots are never used.
> - **Old Neptune snapshots should be deleted manually** after the 7-day window expires, since they cannot be restored without their keys.
> - The `aura-kms-qa` CFN stack remains, but the keys inside will be gone. This is harmless since restore templates do not reference those keys.
>
> KMS key deletion is gated behind the `--schedule-kms-deletion` flag and is **not** included in the default `cleanup --execute` command.
>
> To cancel during the 7-day pending window:
> ```bash
> aws kms cancel-key-deletion --key-id <KEY_ID>
> ```
>
> To delete the stale Neptune snapshots after keys expire:
> ```bash
> aws neptune describe-db-cluster-snapshots \
>   --query "DBClusterSnapshots[?contains(DBClusterSnapshotIdentifier, 'aura-neptune-qa')].[DBClusterSnapshotIdentifier,Status]" \
>   --output table
> aws neptune delete-db-cluster-snapshot \
>   --db-cluster-snapshot-identifier <SNAPSHOT_ID>
> ```

### Impact on Restore

After running `cleanup`, the restore process (`qa_killswitch.py restore --execute`) works normally with no additional steps:

- **ELBs:** Recreated automatically by the AWS Load Balancer Controller when EKS and the ALB controller stack are redeployed
- **AWS Config:** The compliance stack is redeployed during restore, which recreates the recorder, delivery channel, and rules
- **CloudWatch Logs:** Log groups retain their names; new log data is written with standard retention once stacks are redeployed
- **KMS Keys (if deleted):** Restore deploys Neptune and OpenSearch fresh with AWS-managed encryption -- no dependency on the deleted CMKs

---

## Prerequisites

- **AWS CLI v2** configured with QA account credentials
- **Python 3.11+** with `boto3` installed
- **AWS Profile:** Must have sufficient IAM permissions to delete and create CloudFormation stacks
- **No active CodeBuild builds** targeting QA (the script checks for this)

---

## Usage

### Check QA Environment Status

```bash
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py status
```

Displays the CloudFormation stack status, EventBridge schedule state, and kill-switch state file contents.

### Shutdown QA Environment

```bash
# Dry-run: shows the plan without making changes
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py shutdown

# Execute shutdown (interactive confirmation required)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py shutdown --execute

# Execute shutdown (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py shutdown --execute --force
```

**What happens during shutdown:**

1. Pre-flight checks (credentials, account validation, no active builds)
2. Creates a Neptune cluster snapshot (named `aura-neptune-qa-ks-{timestamp}`)
3. Disables EventBridge scale-up/scale-down schedules
4. Deletes stacks in dependency order (Phases 2-6, with parallel deletion within each phase)
5. Cleans up old kill-switch snapshots (keeps only the latest)
6. Saves state to `~/.aura/qa-killswitch-state.json` and S3
7. Sends SNS notification

**Estimated shutdown time:** ~45 minutes (dominated by ECS Fargate service drain and OpenSearch deletion)

### Restore QA Environment

```bash
# Dry-run: shows the restore plan
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py restore

# Execute restore
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py restore --execute

# Execute restore (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py restore --execute --force
```

**What happens during restore:**

1. Pre-flight checks
2. Loads kill-switch state from S3 (or local fallback)
3. Resolves parameters from foundation stacks (VPC, subnets, security groups, IAM roles)
4. Deploys stacks in reverse dependency order:
   - Phase 1: VPC Endpoints
   - Phase 2: Neptune, OpenSearch, ElastiCache (parallel)
   - Phase 3: EKS control plane
   - Phase 4: Node groups + dnsmasq network services (parallel)
5. Re-enables EventBridge schedules
6. Saves updated state

**Estimated restore time:** ~45-60 minutes (dominated by Neptune and EKS cluster creation)

**After restore completes**, the following manual steps may be needed:

1. Update kubeconfig: `aws eks update-kubeconfig --name aura-cluster-qa --region us-east-1`
2. Verify K8s nodes are joining: `kubectl get nodes`
3. Re-deploy K8s workloads if needed via CodeBuild `aura-k8s-deploy-qa`

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| Environment lock | Hardcoded to `qa` in `ALLOWED_ENVIRONMENTS` frozenset |
| Account validation | Validates AWS account ID via `AURA_QA_ACCOUNT_ID` env var |
| Dry-run default | All operations are dry-run unless `--execute` is specified |
| Confirmation prompt | Must type `DESTROY QA` (shutdown) or `RESTORE QA` (restore) |
| Stack name validation | Verifies all stack names contain `-qa` substring |
| Active build check | Refuses to run if QA CodeBuild projects have builds in progress |
| State persistence | State saved to S3 and local file with 0600 permissions |

---

## State Management

The kill-switch maintains state in two locations:

1. **S3:** `s3://{artifacts-bucket}/killswitch/qa-state.json`
2. **Local:** `~/.aura/qa-killswitch-state.json`

State includes: shutdown/restore timestamps, operator identity, Neptune snapshot ID, deleted stack list, and disabled schedules.

---

## Troubleshooting

### ASG Terminate Process Suspended

**Symptom:** Node group stack deletion hangs or fails.

**Cause:** The QA cost scheduler Lambda may have suspended ASG Terminate/Launch processes to prevent scaling during off-hours. When CloudFormation tries to delete the node group, it cannot terminate instances because the Terminate process is suspended.

**Fix:**
```bash
# Find the ASG name
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'aura') && contains(AutoScalingGroupName, 'qa')].AutoScalingGroupName" \
  --output text

# Resume all ASG processes
aws autoscaling resume-processes \
  --auto-scaling-group-name <ASG_NAME>

# Retry the kill-switch
AWS_PROFILE=aura-admin python scripts/qa_killswitch.py shutdown --execute --force
```

### Cross-Stack Security Group References

**Symptom:** VPC Endpoint or network services stack deletion fails with "resource sg-xxx has a dependent object."

**Cause:** Security group rules in one stack reference security groups created by another stack. CloudFormation cannot delete a security group that is referenced by another security group's inbound/outbound rules.

**Fix:**
```bash
# Identify the blocking reference
aws ec2 describe-security-group-references \
  --group-id <BLOCKING_SG_ID>

# Remove the referencing rule manually
aws ec2 revoke-security-group-ingress \
  --group-id <REFERENCING_SG_ID> \
  --security-group-rule-ids <RULE_ID>

# Retry stack deletion
aws cloudformation delete-stack --stack-name <STACK_NAME>
```

### ECS Fargate Service Drain Timeout

**Symptom:** Network services stack deletion takes 15-25 minutes.

**Cause:** ECS Fargate tasks have a deregistration delay and must drain active connections before termination. This is normal behavior.

**Resolution:** Wait for completion. The kill-switch polls every 15 seconds and has a 30-minute timeout per stack.

### Stack in DELETE_FAILED State

**Symptom:** A stack enters `DELETE_FAILED` and the kill-switch reports failure.

**Fix:**
```bash
# Check which resources failed to delete
aws cloudformation describe-stack-events \
  --stack-name <STACK_NAME> \
  --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId, ResourceStatusReason]" \
  --output table

# Retry deletion, skipping the problematic resource
aws cloudformation delete-stack \
  --stack-name <STACK_NAME> \
  --retain-resources <LOGICAL_RESOURCE_ID>
```

### State File Mismatch

**Symptom:** `status` command shows incorrect state, or restore fails because it thinks QA is already running.

**Fix:**
```bash
# Remove local state and let S3 be the source of truth
rm ~/.aura/qa-killswitch-state.json

# Or remove S3 state to reset entirely
aws s3 rm s3://<ARTIFACTS_BUCKET>/killswitch/qa-state.json
```

---

## Lessons Learned (First Execution, Feb 15, 2026)

1. **ASG process suspension blocks node group deletion.** The QA cost scheduler Lambda suspends ASG Terminate/Launch processes. Resume ASG processes before retrying node group stack deletion.

2. **Cross-stack security group references block deletion.** VPC Endpoint security groups can reference network-services security groups (and vice versa). Manual SG rule cleanup may be required before stack deletion succeeds.

3. **ECS Fargate services take 15-25 minutes to drain.** This is the dominant time contributor during shutdown. The overall shutdown took ~45 minutes.

4. **OpenSearch deletion is slow.** OpenSearch domain deletion takes 10-15 minutes after the CloudFormation delete is initiated.

5. **Parallel deletion within phases works well.** The script deletes stacks at the same phase level in parallel using ThreadPoolExecutor, which reduces total shutdown time.

---

## Relationship to QA Cost Scheduler

The kill-switch **replaces** the QA cost scheduler (`qa-cost-scheduler.yaml`) for full environment shutdown. The two tools serve different purposes:

| Capability | QA Cost Scheduler | Kill-Switch |
|------------|-------------------|-------------|
| **Scope** | EKS nodes only | All always-on services |
| **Savings** | Partial (nodes only) | Significant (all always-on services) |
| **Automation** | EventBridge scheduled (daily) | Manual execution |
| **Restore time** | 3-5 minutes (nodes rejoin) | 45-60 minutes (full stack deploy) |
| **Data preservation** | N/A (databases stay running) | Neptune snapshot before deletion |
| **Use case** | Daily on/off schedule | Extended environment hibernation |

When the kill-switch shuts down QA, it also disables the EventBridge schedules (since there is nothing to scale). On restore, it re-enables them.

See [QA_SCHEDULE_GUIDE.md](../operations/QA_SCHEDULE_GUIDE.md) for the daily scheduler documentation.

---

## Related Resources

- **Script:** `scripts/qa_killswitch.py`
- **QA Cost Scheduler Template:** `deploy/cloudformation/qa-cost-scheduler.yaml`
- **QA Schedule Guide:** `docs/operations/QA_SCHEDULE_GUIDE.md`
- **QA Deployment Checklist:** `docs/deployment/QA_DEPLOYMENT_CHECKLIST.md`
- **QA/Prod Deployment Sequence:** `docs/deployment/QA_PROD_DEPLOYMENT_SEQUENCE.md`
- **Dev Cost Analysis:** `docs/assessments/COST_ANALYSIS_DEV_ENVIRONMENT.md`
- **GitHub Issue:** #639 (QA environment inactive for cost savings)

---

## Change History

| Date | Change |
|------|--------|
| 2026-03-19 | Added `cleanup` subcommand and Post-Shutdown Cost Cleanup section. AWS Config recorder found running post-shutdown. |
| 2026-02-15 | Initial runbook. QA environment shut down. |
