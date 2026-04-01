# DEV Environment Kill-Switch Runbook

**Last Updated:** March 19, 2026
**Script:** `scripts/dev_killswitch.py`
**Target Environment:** DEV only (hardcoded, cannot target qa or prod)
**Owner:** Platform Engineering

---

## Overview

The DEV kill-switch is a Python script that safely shuts down and restores the DEV environment's always-on AWS services. Unlike the QA kill-switch (which manages 9 stacks), the DEV kill-switch manages 80 stacks across all deployment layers (Scanning Engine, Security, Sandbox, Serverless, Observability, Application, Network Services, Compute, Data, and Foundation VPC Endpoints).

The kill-switch uses a **hybrid restore approach**: 9 core infrastructure stacks (VPC Endpoints, Neptune, OpenSearch, ElastiCache, EKS, node groups, and dnsmasq) are deployed directly via CloudFormation, while upper-layer stacks (Application, Observability, Serverless, Sandbox, Security, Scanning Engine) are restored by triggering their respective CodeBuild projects to maintain the single source of truth for deployments.

Foundation stacks (VPC, networking, security groups, IAM, KMS, S3, DynamoDB, ECR, Cognito, Secrets, and other stateless/minimal-cost resources) remain running at minimal cost so that restore only needs to recreate compute, data, and application services.

**DEV environment was shut down on March 4, 2026.** All 80 stacks were successfully deleted. QA was previously shut down on February 15, 2026.

---

## Cost Breakdown

### Stacks Managed by the Kill-Switch (80 stacks)

| Phase | Layer | Stack Count | Key Services | Relative Cost |
|-------|-------|-------------|-------------|--------------|
| 2 | Scanning Engine | 8 | Vulnerability scanning monitoring, EventBridge, cleanup, workflow, ECR, networking, IAM, infra | Low |
| 3 | Security | 13 | Runtime security (correlation, baselines, discovery, interceptor), capability governance, semantic guardrails, red team, drift detection, GuardDuty, AWS Config, IAM alerting | Moderate |
| 4 | Sandbox | 13 | Test environment (scheduler, budgets, monitoring, marketplace, namespace, approval, catalog, IAM, state), HITL workflow, SSR training, sandbox | Moderate |
| 5 | Serverless | 18 | Constitutional AI, GPU scheduler, env-drift Lambda, deployment pipeline, scheduling, checkpoint WebSocket, runbook agent, DNS blocklist, orchestrator, agent queues, A2A, HITL callback/scheduler, threat intel, incident investigation, incident response, chat assistant | Moderate |
| 6 | Observability | 8 | DEV cost scheduler, GPU monitoring, alignment alerts, OTel collector, real-time monitoring, org cost monitoring, cost alerts, monitoring | Low |
| 7 | Application | 10 | IRSA (API, memory, GPU, env-validator, cluster-autoscaler), Bedrock infrastructure, Bedrock guardrails, marketing, docs portal, ALB controller | Moderate |
| 8 | Network Services | 1 | dnsmasq ECS Fargate (VPC-wide DNS) | Low |
| 9 | Compute (Nodes) | 4 | EKS general nodes (Spot), memory nodes, GPU nodes, neural memory GPU | Moderate |
| 10 | Compute (Control Plane) | 1 | EKS control plane | High |
| 11 | Data Stores | 3 | Neptune db.t3.medium, OpenSearch t3.small, ElastiCache t3.micro | Highest |
| 12 | Foundation (Endpoints) | 1 | VPC Endpoints (8 interface endpoints) | Moderate |
| | | **80** | | **Significant** |

**Note:** The full estimated savings of significant monthly includes additional cost reductions from idle compute charges, data transfer fees, and associated CloudWatch/logging costs for services not individually tracked in the cost map above. The significant monthly savings figure represents total cost avoidance when the environment is fully shut down.

### Stacks That Remain Running (~58 protected stacks)

| Category | Stacks | Monthly Cost | Reason |
|----------|--------|-------------|--------|
| Foundation | VPC, networking, security, IAM, KMS, Route 53, build-cache, ECR base-images | ~$0 | No hourly charges |
| Data (State) | S3, DynamoDB (6 tables), repository tables, cloud discovery | ~$2-5 | On-demand, storage only |
| Application (Identity) | Cognito, marketplace, diagram service (IAM + SSM), IdP infrastructure, customer onboarding | ~$0-2 | Minimal cost services |
| Observability (Config) | Secrets, disaster recovery, log-retention-sync, compliance-settings-sync | ~$0-1 | Configuration only |
| Serverless (State) | Checkpoint DynamoDB, serverless permission boundary | ~$0 | On-demand, idle |
| Bootstrap | Organizations, CloudTrail, Route 53 cross-account, account bootstrap/migration | ~$0 | Organizational resources |
| ECR Repos | 7 ECR repositories (agent-orchestrator, API, memory, frontend, meta-orchestrator, runtime-incident, dnsmasq) | ~$0.70 | $0.10/repo storage |
| Certificates | ACM certificate | ~$0 | Free |
| **Total** | | **~$3-9/month** | |

---

## Post-Shutdown Cost Cleanup

After the kill-switch shuts down the 80 managed stacks, several cost sources persist in the protected foundation stacks and orphaned resources. The `cleanup` subcommand targets these residual costs.

### Why Additional Cleanup Is Needed

The kill-switch protects ~58 foundation stacks that provide the base infrastructure for restore. However, some of these protected stacks and orphaned resources continue to incur significant charges:

| Source | Impact | Root Cause |
|--------|--------|------------|
| AWS Config recorder + 18 rules | Significant | `aura-compliance-settings-sync-dev` protected stack keeps Config active |
| CloudWatch log groups | Significant | Log groups from deleted stacks retain stored data indefinitely |
| Orphaned ALBs | Moderate | Kubernetes-managed load balancers (AWS LB Controller) are not deleted when EKS is removed via CloudFormation |
| KMS CMKs (4 keys) | Minor | `aura-kms-dev` protected stack (DeletionPolicy: Retain) keeps keys alive |
| **Total** | **Significant** | |

### Cleanup Commands

```bash
# Dry-run: show what would be cleaned up
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py cleanup

# Execute cleanup (ELBs, Config, CloudWatch log retention)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py cleanup --execute

# Execute cleanup (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py cleanup --execute --force

# Execute cleanup INCLUDING KMS key deletion (see warning below)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py cleanup --execute --schedule-kms-deletion
```

### What Each Step Does

| Step | Action | Savings | Reversible? |
|------|--------|---------|-------------|
| Orphaned ELBs | Finds and deletes load balancers tagged by Kubernetes (AWS LB Controller) | Significant | Yes - ALBs are recreated by the ALB Controller when EKS is restored |
| AWS Config | Stops the recorder, deletes the delivery channel, deletes all Config rules | Significant | Yes - CodeBuild redeploys the compliance stack on restore |
| CloudWatch Logs | Sets all aura log groups to 1-day retention (does NOT delete groups) | Moderate | Yes - retention is updated to standard values when stacks are redeployed |
| KMS CMKs | Schedules 4 customer-managed keys for deletion (7-day pending window) | Minor | Irreversible for old snapshots, but **restore is unaffected** (see below) |

### KMS Key Deletion — Restore Impact

> **KMS key deletion is irreversible after the 7-day pending window.** Old CMK-encrypted Neptune snapshots become permanently unrecoverable. However:
>
> - **Restore is NOT affected.** The restore templates (`neptune-simplified.yaml`, `opensearch.yaml`) deploy fresh clusters using AWS-managed encryption, not the CMKs. Neptune always starts as an empty cluster on restore — old snapshots are never used.
> - **Old Neptune snapshots should be deleted manually** after the 7-day window expires, since they cannot be restored without their keys.
> - The `aura-kms-dev` CFN stack remains (protected), but the keys inside will be gone. This is harmless since restore templates do not reference those keys.
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
>   --query "DBClusterSnapshots[?contains(DBClusterSnapshotIdentifier, 'aura-neptune-dev')].[DBClusterSnapshotIdentifier,Status]" \
>   --output table
> aws neptune delete-db-cluster-snapshot \
>   --db-cluster-snapshot-identifier <SNAPSHOT_ID>
> ```

### Impact on Restore

After running `cleanup`, the restore process (`dev_killswitch.py restore --execute`) works normally with no additional steps:

- **ELBs:** Recreated automatically by the AWS Load Balancer Controller when EKS and the ALB controller stack are redeployed
- **AWS Config:** The compliance-settings-sync stack is redeployed by the observability CodeBuild project, which recreates the recorder, delivery channel, and rules
- **CloudWatch Logs:** Log groups retain their names; new log data is written with standard retention once stacks are redeployed
- **KMS Keys (if deleted):** Restore deploys Neptune and OpenSearch fresh with AWS-managed encryption — no dependency on the deleted CMKs

---

## Prerequisites

- **AWS CLI v2** configured with DEV account credentials
- **Python 3.11+** with `boto3` installed
- **AWS Profile:** Must have sufficient IAM permissions to delete and create CloudFormation stacks
- **No active CodeBuild builds** targeting DEV (the script checks for this)

---

## Usage

### Check DEV Environment Status

```bash
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py status
```

Displays the CloudFormation stack status for all 80 managed stacks, EventBridge schedule state, estimated monthly cost of running stacks, and kill-switch state file contents.

### Shutdown DEV Environment

```bash
# Dry-run: shows the plan without making changes
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown

# Execute shutdown (interactive confirmation required)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown --execute

# Execute shutdown (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown --execute --force

# Execute shutdown without Neptune snapshot
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown --execute --skip-snapshot
```

**What happens during shutdown:**

1. Pre-flight checks (credentials, account validation via `AURA_DEV_ACCOUNT_ID`, no active CodeBuild builds, stack name validation)
2. Creates a Neptune cluster snapshot (named `aura-neptune-dev-ks-{timestamp}`) unless `--skip-snapshot`
3. Disables EventBridge scale-up/scale-down schedules (`aura-dev-scale-down`, `aura-dev-scale-up`)
4. Deletes stacks in dependency order across 11 phases (Phases 2-12), with parallel deletion within each phase using ThreadPoolExecutor:
   - Phase 2: Scanning Engine (8 stacks)
   - Phase 3: Security Services (13 stacks)
   - Phase 4: Sandbox / Test Environments (13 stacks)
   - Phase 5: Serverless (18 stacks)
   - Phase 6: Observability (8 stacks)
   - Phase 7: Application Services (10 stacks)
   - Phase 8: Network Services (1 stack - dnsmasq)
   - Phase 9: Compute Node Groups (4 stacks)
   - Phase 10: EKS Control Plane (1 stack)
   - Phase 11: Data Stores (3 stacks - Neptune, OpenSearch, ElastiCache)
   - Phase 12: VPC Endpoints (1 stack - last to delete)
5. Cleans up old kill-switch snapshots (keeps only the latest)
6. Saves state to `~/.aura/dev-killswitch-state.json` and S3
7. Sends SNS notification via `aura-operations-dev` topic

**Estimated shutdown time:** ~60-90 minutes (dominated by the large number of parallel stack deletions, ECS Fargate service drain, and OpenSearch deletion)

### Restore DEV Environment

```bash
# Dry-run: shows the restore plan
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py restore

# Execute restore
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py restore --execute

# Execute restore (skip confirmation prompt)
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py restore --execute --force
```

**What happens during restore:**

1. Pre-flight checks
2. Loads kill-switch state from S3 (or local fallback)
3. Resolves parameters from foundation stacks (VPC, subnets, security groups, IAM roles, route tables, SSM admin role ARN)
4. Deploys 9 core infrastructure stacks directly in dependency order:
   - Phase 1: VPC Endpoints
   - Phase 2: Neptune, OpenSearch, ElastiCache (parallel)
   - Phase 3: EKS control plane
   - Phase 4: Node groups (general, memory, GPU) + dnsmasq network services (parallel)
5. Triggers 6 CodeBuild projects for upper-layer restoration:
   - `aura-application-deploy-dev`
   - `aura-observability-deploy-dev`
   - `aura-serverless-deploy-dev`
   - `aura-sandbox-deploy-dev`
   - `aura-security-deploy-dev`
   - `aura-vuln-scan-deploy-dev`
6. Re-enables EventBridge schedules
7. Saves updated state

**Estimated restore time:** ~90-120 minutes (core infrastructure deploy ~45-60 minutes + CodeBuild upper-layer deployments running in parallel ~30-60 minutes)

**After restore completes**, the following manual steps may be needed:

1. Update kubeconfig: `aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1`
2. Verify K8s nodes are joining: `kubectl get nodes`
3. Monitor CodeBuild builds for upper-layer deployment completion:
   ```bash
   # Check build status for each project
   aws codebuild list-builds-for-project --project-name aura-application-deploy-dev --max-items 1
   aws codebuild list-builds-for-project --project-name aura-observability-deploy-dev --max-items 1
   aws codebuild list-builds-for-project --project-name aura-serverless-deploy-dev --max-items 1
   aws codebuild list-builds-for-project --project-name aura-sandbox-deploy-dev --max-items 1
   aws codebuild list-builds-for-project --project-name aura-security-deploy-dev --max-items 1
   aws codebuild list-builds-for-project --project-name aura-vuln-scan-deploy-dev --max-items 1
   ```
4. Re-deploy K8s workloads if needed via CodeBuild `aura-k8s-deploy-dev`

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| Environment lock | Hardcoded to `dev` in `ALLOWED_ENVIRONMENTS` frozenset |
| Account validation | Validates AWS account ID via `AURA_DEV_ACCOUNT_ID` env var |
| Protected stacks | ~58 stacks in `PROTECTED_STACKS` frozenset are never deleted |
| Dry-run default | All operations are dry-run unless `--execute` is specified |
| Confirmation prompt | Must type `DESTROY DEV` (shutdown) or `RESTORE DEV` (restore) |
| Stack name validation | Verifies all stack names contain `-dev` substring |
| Cross-list validation | Verifies no stack in `STACK_DEFINITIONS` is also in `PROTECTED_STACKS` |
| Active build check | Refuses to run if DEV CodeBuild projects (8 checked) have builds in progress |
| State persistence | State saved to S3 and local file with 0600 permissions |

---

## State Management

The kill-switch maintains state in two locations:

1. **S3:** `s3://{artifacts-bucket}/killswitch/dev-state.json`
2. **Local:** `~/.aura/dev-killswitch-state.json`

State includes: shutdown/restore timestamps, operator identity, Neptune snapshot ID, deleted stack list, disabled schedules, CodeBuild restore build IDs, and completed phases.

---

## Troubleshooting

### ASG Terminate Process Suspended

**Symptom:** Node group stack deletion hangs or fails.

**Cause:** The DEV cost scheduler Lambda may have suspended ASG Terminate/Launch processes to prevent scaling during off-hours. When CloudFormation tries to delete the node group, it cannot terminate instances because the Terminate process is suspended.

**Fix:**
```bash
# Find the ASG name
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'aura') && contains(AutoScalingGroupName, 'dev')].AutoScalingGroupName" \
  --output text

# Resume all ASG processes
aws autoscaling resume-processes \
  --auto-scaling-group-name <ASG_NAME>

# Retry the kill-switch
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown --execute --force
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

**Symptom:** `status` command shows incorrect state, or restore fails because it thinks DEV is already running.

**Fix:**
```bash
# Remove local state and let S3 be the source of truth
rm ~/.aura/dev-killswitch-state.json

# Or remove S3 state to reset entirely
aws s3 rm s3://<ARTIFACTS_BUCKET>/killswitch/dev-state.json
```

### CodeBuild Restore Build Failure

**Symptom:** One or more CodeBuild projects triggered during restore fail.

**Cause:** Upper-layer CodeBuild projects may fail if core infrastructure is not fully ready (e.g., EKS cluster still initializing, Neptune endpoint not yet resolvable).

**Fix:**
```bash
# Check the failing build logs
aws codebuild batch-get-builds --ids <BUILD_ID> \
  --query "builds[0].{status:buildStatus, phase:currentPhase}"

# View build logs (get log group and stream from build details)
aws codebuild batch-get-builds --ids <BUILD_ID> \
  --query "builds[0].logs.{group:groupName, stream:streamName}"

# Retry individual CodeBuild project
aws codebuild start-build --project-name aura-<LAYER>-deploy-dev
```

### CodeBuild Project Not Found

**Symptom:** Restore reports "CodeBuild project not found" for one or more upper-layer projects.

**Cause:** CodeBuild projects are defined by their own CloudFormation stacks (codebuild-*.yaml templates) which are in the protected set. If these were manually deleted or never deployed, the restore trigger will fail for those layers.

**Fix:**
```bash
# Verify CodeBuild project existence
aws codebuild batch-get-projects --names aura-application-deploy-dev \
  aura-observability-deploy-dev aura-serverless-deploy-dev \
  aura-sandbox-deploy-dev aura-security-deploy-dev aura-vuln-scan-deploy-dev

# If projects are missing, deploy the CodeBuild stack first
aws cloudformation deploy \
  --stack-name aura-codebuild-<LAYER>-dev \
  --template-file deploy/cloudformation/codebuild-<LAYER>.yaml \
  --parameter-overrides Environment=dev ProjectName=aura \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

### Partial Shutdown State

**Symptom:** Shutdown completes but state shows `partial` instead of `shutdown`.

**Cause:** One or more stacks failed to delete during the shutdown sequence. The kill-switch counts deleted stacks and only sets status to `shutdown` when all 80 stacks are confirmed deleted.

**Fix:**
```bash
# Check which stacks are still running
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py status

# Manually delete remaining stacks
aws cloudformation delete-stack --stack-name <REMAINING_STACK>

# Re-run shutdown to clean up and update state
AWS_PROFILE=aura-admin python scripts/dev_killswitch.py shutdown --execute --force --skip-snapshot
```

### Missing Foundation Parameters During Restore

**Symptom:** Restore fails with "Missing foundation parameters" error listing VPC_ID, PRIVATE_SUBNET_IDS, or other values.

**Cause:** Foundation stacks (networking, security, IAM) are not running or their outputs are not accessible.

**Fix:**
```bash
# Verify foundation stacks are running
aws cloudformation describe-stacks --stack-name aura-networking-dev --query "Stacks[0].StackStatus"
aws cloudformation describe-stacks --stack-name aura-security-dev --query "Stacks[0].StackStatus"
aws cloudformation describe-stacks --stack-name aura-iam-dev --query "Stacks[0].StackStatus"

# If a foundation stack is missing, it must be deployed first via the foundation CodeBuild project
aws codebuild start-build --project-name aura-foundation-deploy-dev
```

---

## Relationship to DEV Cost Scheduler

The kill-switch **replaces** the DEV cost scheduler (`dev-cost-scheduler.yaml`) for full environment shutdown. The two tools serve different purposes:

| Capability | DEV Cost Scheduler | Kill-Switch |
|------------|-------------------|-------------|
| **Scope** | EKS node groups only (general, memory, GPU) | All always-on services (80 stacks) |
| **Savings** | estimated monthly (node scaling to 0) | significant monthly (full shutdown) |
| **Automation** | EventBridge scheduled (nightly at 1:00 UTC, restore Mon-Fri 12:00 UTC) | Manual execution |
| **Restore time** | 3-5 minutes (nodes rejoin) | 90-120 minutes (core infra + CodeBuild) |
| **Data preservation** | N/A (databases stay running) | Neptune snapshot before deletion |
| **Use case** | Daily on/off schedule (weeknight/weekend savings) | Extended environment hibernation |

When the kill-switch shuts down DEV, it also disables the EventBridge schedules (since there is nothing to scale). On restore, it re-enables them.

**Manual override for DEV cost scheduler (when environment is running):**
```bash
aws lambda invoke --function-name aura-dev-cost-scaler-dev --payload '{"action":"start","trigger":"manual"}' /dev/stdout
```

---

## Comparison with QA Kill-Switch

| Dimension | QA Kill-Switch | DEV Kill-Switch |
|-----------|---------------|-----------------|
| **Stacks managed** | 9 | 80 |
| **Monthly savings** | Significant | Significant (larger environment) |
| **Shutdown time** | ~45 minutes | ~60-90 minutes |
| **Restore time** | ~45-60 minutes | ~90-120 minutes |
| **Restore method** | All stacks deployed directly | Hybrid: 9 core stacks direct + 6 CodeBuild triggers |
| **Shutdown phases** | 5 phases (2-6) | 11 phases (2-12) |
| **Script** | `scripts/qa_killswitch.py` | `scripts/dev_killswitch.py` |
| **Confirmation text** | `DESTROY QA` / `RESTORE QA` | `DESTROY DEV` / `RESTORE DEV` |
| **State file** | `~/.aura/qa-killswitch-state.json` | `~/.aura/dev-killswitch-state.json` |
| **S3 state key** | `killswitch/qa-state.json` | `killswitch/dev-state.json` |
| **Account ID env var** | `AURA_QA_ACCOUNT_ID` | `AURA_DEV_ACCOUNT_ID` |

---

## Related Resources

- **Script:** `scripts/dev_killswitch.py`
- **QA Kill-Switch Runbook:** `docs/runbooks/QA_KILLSWITCH_RUNBOOK.md`
- **QA Kill-Switch Script:** `scripts/qa_killswitch.py`
- **DEV Cost Scheduler Template:** `deploy/cloudformation/dev-cost-scheduler.yaml`
- **Dev Environment Cost Analysis:** `docs/assessments/COST_ANALYSIS_DEV_ENVIRONMENT.md`
- **Deployment Guide:** `docs/deployment/DEPLOYMENT_GUIDE.md`
- **CI/CD Setup Guide:** `docs/deployment/CICD_SETUP_GUIDE.md`

---

## Dependency-Safe Deletion (`delete_order`)

Within each shutdown phase, stacks may have cross-stack CloudFormation export dependencies that prevent parallel deletion. The `delete_order` field in `STACK_DEFINITIONS` enforces sequential sub-groups within a phase:

- Stacks with the **same** `delete_order` value run in **parallel**
- Sub-groups run **sequentially** (lowest `delete_order` first)
- Stacks without a `delete_order` field default to `delete_order: 1` (all run in parallel)

**Phases with `delete_order` sub-groups:**

| Phase | Layer | Sub-Groups | Rationale |
|-------|-------|------------|-----------|
| 2 | Scanning Engine | 4 waves: monitoring/eventbridge/cleanup/ecr -> workflow -> iam/networking -> infra | Cross-stack exports between scanning infrastructure stacks |
| 4 | Sandbox | 2 waves: all test-env/ssr/hitl stacks -> sandbox | Sandbox stack exports referenced by test environment stacks |
| 5 | Serverless | 2 waves: all stacks including incident-investigation -> incident-response | `incident-response` imports exports from `incident-investigation` |

**Cross-Stack Export Dependency Chain (Scanning Engine):**
```
vuln-scan-monitoring, vuln-scan-eventbridge, vuln-scan-cleanup, vuln-scan-ecr  (delete_order: 1)
  -> vuln-scan-workflow                                                         (delete_order: 2)
    -> vuln-scan-iam, vuln-scan-networking                                      (delete_order: 3)
      -> vuln-scan-infra                                                        (delete_order: 4)
```

---

## Canceled-Delete Detection

The `_wait_for_delete` method includes detection for CloudFormation delete cancellations. When a stack transitions from `DELETE_IN_PROGRESS` back to a prior state (e.g., `CREATE_COMPLETE`, `UPDATE_COMPLETE`), this indicates CloudFormation canceled the deletion due to a dependency or resource issue.

**Behavior:** The kill-switch immediately returns an error for that stack instead of polling indefinitely. This prevents infinite loops that could occur when a stack's deletion is silently canceled.

**Common causes of canceled deletes:**
- Cross-stack export dependencies (another stack imports a value from the stack being deleted)
- Resource-level dependencies (e.g., security group referenced by another security group)
- AWS service-level retention policies preventing resource deletion

---

## Change History

| Date | Change |
|------|--------|
| 2026-03-19 | Added `cleanup` subcommand for post-shutdown cost reduction (estimated monthly). Targets orphaned ELBs, AWS Config, CloudWatch log retention, and KMS CMKs. 14 new tests (100 total DEV tests). |
| 2026-03-04 | DEV shutdown executed (80 stacks deleted). Added `delete_order` mechanism, canceled-delete detection, `aura-incident-investigation-dev` stack. Kill-switch fixes applied to both dev and qa scripts. 133 tests passing (86 DEV + 47 QA). |
| 2026-03-03 | Initial runbook. Documents DEV kill-switch with hybrid restore approach. |
