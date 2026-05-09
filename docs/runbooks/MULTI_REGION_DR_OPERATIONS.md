# Multi-Region DR Operations Runbook

**Last Updated:** 2026-05-09
**Tracked As:** DR-7 (#150), part of DR umbrella #143
**Owner:** Platform Engineering / SRE on-call
**Related ADRs:** ADR-091 (Cognito DR design)
**Related Runbooks:**
- `docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md` (DR-3)
- `docs/runbooks/OPENSEARCH_FAILOVER_RUNBOOK.md` (DR-4)
- `docs/runbooks/COGNITO_FAILOVER_RUNBOOK.md` (DR-2)

---

## What this runbook covers

End-to-end orchestration of a Tier 1 cross-region failover from `us-east-1` to `us-west-2`. Composes the per-service failover runbooks (Neptune, OpenSearch, Cognito) into a single pipeline-driven sequence with HITL approval gates at every destructive or externally-visible step.

The pipeline is deployed by:

- `deploy/cloudformation/multi-region-failover.yaml` (Layer 5.15) -- Route 53 health checks + failover records, SNS topic, cutover Lambdas
- `deploy/cloudformation/multi-region-pipeline.yaml` (Layer 6.22) -- Step Functions Standard state machine with HITL approval gates

This runbook is for the SRE on-call. It is intentionally exec-readable under DR-event time pressure.

## Prerequisites (verify before any failover or drill)

| Check | Command | Expected |
|-------|---------|----------|
| Secondary VPC reachable | `aws cloudformation describe-stacks --stack-name aura-networking-secondary-prod --region us-west-2` | `CREATE_COMPLETE` / `UPDATE_COMPLETE` |
| Secondary KMS keys deployed | `aws cloudformation describe-stacks --stack-name aura-kms-replica-secondary-prod --region us-west-2` | `CREATE_COMPLETE` / `UPDATE_COMPLETE` |
| User-mirror Global Table replicating | CloudWatch alarm `aura-user-mirror-replication-lag-prod` | `OK` (lag < 60s) |
| DDB Tier 1 GlobalTables replicating | CloudWatch alarms `aura-*-replication-lag-prod` | `OK` |
| AWS Backup cross-region copies current | Latest cross-region recovery point < 24h old (Neptune) / 1h old (OpenSearch) | See Step 1 of each service runbook |
| Secrets Manager replicas current | `aws secretsmanager describe-secret --secret-id aura/prod/neptune-connection --region us-west-2` | `ReplicationStatus: SUCCESS` |
| Standby Cognito user pool deployed | `aws cognito-idp describe-user-pool --user-pool-id $(aws ssm get-parameter --name /aura/prod/cognito-dr/standby-pool-id --region us-west-2 --query Parameter.Value --output text) --region us-west-2` | Returns pool details |
| Hydrator schedule disabled | `aws events describe-rule --name aura-cognito-dr-hydrator-schedule-prod --region us-west-2` | `State: DISABLED` |
| Failover pipeline deployed | `aws stepfunctions describe-state-machine --state-machine-arn $(aws cloudformation list-exports --query "Exports[?Name=='aura-multi-region-failover-arn-prod'].Value | [0]" --output text)` | Returns state machine details |

If any check fails, **fix the underlying issue before invoking failover**. The pipeline trusts these prerequisites.

## Failover decision criteria

Execute this procedure only when one of the following is true:

1. **Primary region declared unavailable** by AWS Health Dashboard or internal incident command.
2. **Primary application unhealthy for > 30 minutes** with no recovery path: API success rate < 50%, or sustained 5xx error rate > 10%, or DB connectivity broken across all primary services.
3. **Disaster recovery drill** scheduled per the DR doc's quarterly cadence.

Failover is a Tier 1 incident-command decision. The pipeline pauses for HITL approval at every destructive step; the incident commander approves each gate.

## Phase 1: Initiate failover

### Step 1.1: Start the pipeline execution

```bash
ENV=prod
PROJECT=aura
OPERATOR_NAME="<your-name>"
EXEC_NAME="failover-$(date -u +%Y%m%d-%H%M%S)"

PIPELINE_ARN=$(aws cloudformation list-exports \
    --query "Exports[?Name=='${PROJECT}-multi-region-failover-arn-${ENV}'].Value | [0]" \
    --output text)

aws stepfunctions start-execution \
    --state-machine-arn "${PIPELINE_ARN}" \
    --name "${EXEC_NAME}" \
    --input "{\"mode\": \"failover\", \"operator\": \"${OPERATOR_NAME}\"}"
```

The pipeline emits an SNS notification (subject: *"Aura DR: failover initiated"*) and pauses at the first HITL approval gate.

### Step 1.2: Approve the data-plane gate

The pipeline writes a row to `aura-hitl-approvals-prod` with `kind=DR_FAILOVER_DATA_PLANE`. Approve via the existing HITL UI, or directly via the Step Functions console. To approve via CLI:

```bash
EXECUTION_ARN=$(aws stepfunctions list-executions \
    --state-machine-arn "${PIPELINE_ARN}" \
    --status-filter RUNNING \
    --max-results 1 \
    --query 'executions[0].executionArn' \
    --output text)

# Find the task token for the data-plane gate
TASK_TOKEN=$(aws dynamodb get-item \
    --table-name aura-hitl-approvals-prod \
    --key "{\"approval_id\": {\"S\": \"failover-data-plane-${EXEC_NAME}\"}}" \
    --query 'Item.task_token.S' \
    --output text)

aws stepfunctions send-task-success \
    --task-token "${TASK_TOKEN}" \
    --task-output '{"approved": true}'
```

After this approval, the pipeline enters `ParallelDataPlanePrep` (3 parallel branches). Two of those branches are HITL gates that block on operator action.

## Phase 2: Data-plane preparation

The pipeline now has three things in flight:

### Step 2.1: Cognito hydration (automatic)

Branch 1 invokes `aura-cognito-hydrator-trigger-prod` with `action: enable`. The hydrator schedule starts; users from the user-mirror table populate the standby pool. Monitor:

```bash
aws logs tail /aws/lambda/aura-cognito-dr-hydrator-prod \
    --since 5m \
    --follow \
    --region us-west-2
```

Wait for `hydrator-summary` log lines with `has_more: false` before approving Phase 3.

### Step 2.2: Neptune restore (manual operator step)

Branch 2 writes `kind=DR_FAILOVER_NEPTUNE_RESTORE` to the approvals table and waits. Run `docs/runbooks/NEPTUNE_FAILOVER_RUNBOOK.md` Steps 1-4 (identify recovery point, restore via AWS Backup, pre-stage networking, verify cluster). When the cluster is `available`, capture its endpoint and approve the gate:

```bash
NEPTUNE_TASK_TOKEN=$(aws dynamodb get-item \
    --table-name aura-hitl-approvals-prod \
    --key "{\"approval_id\": {\"S\": \"failover-neptune-${EXEC_NAME}\"}}" \
    --query 'Item.task_token.S' \
    --output text)

# Replace with the endpoint from `aws neptune describe-db-clusters` Step 4 output
NEPTUNE_ENDPOINT="<from-runbook-step-4>"

aws stepfunctions send-task-success \
    --task-token "${NEPTUNE_TASK_TOKEN}" \
    --task-output "{\"neptune_endpoint\": \"${NEPTUNE_ENDPOINT}\"}"
```

### Step 2.3: OpenSearch restore (manual operator step)

Branch 3 mirrors Step 2.2 for OpenSearch. Run `docs/runbooks/OPENSEARCH_FAILOVER_RUNBOOK.md` Steps 1-4, then:

```bash
OS_TASK_TOKEN=$(aws dynamodb get-item \
    --table-name aura-hitl-approvals-prod \
    --key "{\"approval_id\": {\"S\": \"failover-opensearch-${EXEC_NAME}\"}}" \
    --query 'Item.task_token.S' \
    --output text)

OPENSEARCH_ENDPOINT="<from-runbook-step-4>"

aws stepfunctions send-task-success \
    --task-token "${OS_TASK_TOKEN}" \
    --task-output "{\"opensearch_endpoint\": \"${OPENSEARCH_ENDPOINT}\"}"
```

After all three branches complete, the pipeline auto-invokes `DataPlaneSecretCutover` to update the Neptune + OpenSearch connection secrets in `us-west-2`.

## Phase 3: Traffic cutover

### Step 3.1: Approve the traffic-cutover gate

Final HITL gate (`kind=DR_FAILOVER_TRAFFIC_CUTOVER`). Before approving, validate:

- Cognito hydration complete (`has_more=false` in hydrator logs).
- Neptune cluster `available` and reachable on its new endpoint.
- OpenSearch domain `Created=true, Processing=false` and reachable.
- Secrets Manager `aura/prod/neptune-connection` and `aura/prod/opensearch-connection` in `us-west-2` reflect the new endpoints.

Approve:

```bash
TRAFFIC_TASK_TOKEN=$(aws dynamodb get-item \
    --table-name aura-hitl-approvals-prod \
    --key "{\"approval_id\": {\"S\": \"failover-traffic-${EXEC_NAME}\"}}" \
    --query 'Item.task_token.S' \
    --output text)

aws stepfunctions send-task-success \
    --task-token "${TRAFFIC_TASK_TOKEN}" \
    --task-output '{"approved": true}'
```

The pipeline auto-runs `CognitoSSMCutover` (forward direction) -> `DisableCognitoHydrator` -> `NotifyComplete`.

Route 53 failover records (`app.aenealabs.com`) are health-check-driven. As primary's health check fails, DNS automatically points to the secondary ALB. The pipeline does not need to flip records explicitly -- AWS handles that.

### Step 3.2: Send customer comms

Use the failover-comms email template at `s3://aura-compliance-evidence/dr-comms-templates/cognito-failover/`. Key points:
- Password reset is required on next login.
- MFA re-enrollment is required for users who had MFA enabled.

### Step 3.3: Validate

- Browse to `https://app.aenealabs.com` -- confirm Cognito hosted UI loads from the standby pool.
- Run a synthetic test (create a known user, sign in, complete a workflow that hits Neptune + OpenSearch).
- Confirm SNS notification *"Aura DR: failover complete"*.

## Phase 4: Rollback (if failover wasn't needed)

Pre-traffic-cutover rollback: simply reject any open HITL gate. The pipeline transitions to `NotifyFailure`. Manually run cleanup as needed (disable hydrator schedule, clear partial hydration per Cognito runbook rollback section).

Post-traffic-cutover rollback: invoke the pipeline in rollback mode.

```bash
ROLLBACK_EXEC="rollback-$(date -u +%Y%m%d-%H%M%S)"

aws stepfunctions start-execution \
    --state-machine-arn "${PIPELINE_ARN}" \
    --name "${ROLLBACK_EXEC}" \
    --input "{\"mode\": \"rollback\", \"operator\": \"${OPERATOR_NAME}\"}"
```

The rollback mode invokes `CognitoSSMCutover` with `direction: rollback`, which restores the primary pool IDs from the snapshot taken at the start of the original failover. Customer impact: users who authenticated after rollback need to sign in again (refresh tokens issued by the standby pool stop being honoured). Acceptable for a rollback scenario.

Application-layer cleanup after rollback:

- Restart frontend / API workloads in the primary region to pick up the restored SSM values.
- The standby pool retains the hydrated users; treat them as orphan state until the next drill / failover cleans them up.

## Drill cadence

| Drill | Frequency | Scope |
|-------|-----------|-------|
| Synthetic Cognito hydration | Quarterly | Hydrator-only -- enable schedule against a test mirror table, verify, disable. No traffic cutover. |
| Pipeline dry run | Quarterly | Run pipeline through the data-plane gates against the live mirror; **reject** the traffic-cutover gate to skip the SSM flip. |
| End-to-end failover drill | Annually | Full pipeline including SSM cutover. Coordinated with customer comms. Document RTO + RPO. |

Drill artifacts (until DR-8 wires formal evidence-package generation):

```bash
mkdir -p s3://aura-compliance-evidence/dr-drills/$(date -u +%Y-Q%q)/

# State machine execution history
aws stepfunctions get-execution-history \
    --execution-arn "${EXECUTION_ARN}" \
    > drill-execution-history.json

# Hydrator logs
aws logs tail /aws/lambda/aura-cognito-dr-hydrator-prod \
    --since 4h \
    --region us-west-2 \
    > drill-hydrator-logs.txt

# Approval audit trail
aws dynamodb scan \
    --table-name aura-hitl-approvals-prod \
    --filter-expression "begins_with(approval_id, :pfx)" \
    --expression-attribute-values "{\":pfx\": {\"S\": \"failover-\"}}" \
    > drill-approvals.json
```

## Known limitations

- **Neptune + OpenSearch restores are still operator-driven.** Step Functions waits for the operator-supplied endpoint via the HITL gate. Automating the `aws backup start-restore-job` call is feasible but deferred -- the cost of automation outweighs the time savings for a quarterly-or-rarer event.
- **No cross-partition support.** GovCloud failover is `us-gov-west-1` -> `us-gov-east-1`; this template needs a separate deploy with partition-appropriate parameters. Out of scope for DR-7.
- **No cross-account failover.** Single-account-per-environment model assumed. If Aura adopts multi-account in the future, the pipeline and the cutover Lambdas need cross-account roles.
- **HITL gate timeout is 2h per gate.** A long Neptune restore (large data set) may exceed this. Increase `HITLApprovalTimeoutSeconds` parameter at deploy time if needed.
- **No automatic failover trigger.** Per Sally's NIST CP-2 review: regional failover is an explicit human-authorized decision. Route 53 health-check-driven DNS failover handles application-layer (ALB) failover automatically; data-plane / auth-plane cutover is operator-driven.

## GovCloud notes

- Health checks must originate from the same partition. The `us-east-1`, `us-west-1`, `us-west-2` regions in `multi-region-failover.yaml` HealthCheckConfig are commercial regions. For GovCloud, override the `Regions:` list with `us-gov-east-1` and `us-gov-west-1` only.
- KMS Multi-Region Keys (MRKs) work within partition only -- not relevant here since Aura uses independent per-region CMKs (DR-1.0 SC-12 guidance), so this is a non-issue.
- Cross-partition health checks are not supported by Route 53. A commercial-to-GovCloud failover would need a separate hosted zone in each partition.

## References

- DR umbrella: #143
- DR-7: #150 (this runbook)
- ADR-091 (Cognito DR design)
- `multi-region-failover.yaml` (Layer 5.15) -- global resources
- `multi-region-pipeline.yaml` (Layer 6.22) -- Step Functions orchestrator
- `NEPTUNE_FAILOVER_RUNBOOK.md` -- Neptune-specific procedure
- `OPENSEARCH_FAILOVER_RUNBOOK.md` -- OpenSearch-specific procedure
- `COGNITO_FAILOVER_RUNBOOK.md` -- Cognito-specific procedure
- `docs/support/architecture/disaster-recovery.md` -- service tier definitions
