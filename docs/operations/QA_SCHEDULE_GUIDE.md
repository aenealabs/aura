# QA Environment Schedule Guide

This guide documents the QA cost optimization scheduler that automatically scales EKS compute resources outside business hours.

> **Note:** The QA environment may be **fully shut down** via the kill-switch script for significant cost savings by deleting all always-on services (not just scaling nodes to zero). The EventBridge schedules documented below are disabled while QA is shut down. See the [QA Kill-Switch Runbook](../runbooks/QA_KILLSWITCH_RUNBOOK.md) for details on the full shutdown/restore procedure. When QA is restored, these schedules will be re-enabled automatically.

## Overview

The QA environment uses scheduled scaling to reduce costs by ~67% on EKS compute. Nodes are scaled to 0 outside business hours while databases remain available for rapid resumption.

**What Scales Down:**
- EKS General Node Group (t3.large SPOT instances)

**What Stays Running:**
- Neptune (graph database)
- OpenSearch (vector search)
- ElastiCache (Redis)
- dnsmasq (DNS service on ECS Fargate)
- DynamoDB (on-demand, no cost when idle)

## Schedule

| Event | Time (EST) | Time (UTC) | Days |
|-------|------------|------------|------|
| **Scale Down** | 8:00 PM | 01:00 | Daily |
| **Scale Up** | 7:00 AM | 12:00 | Monday-Friday |

**Note:** Schedule uses UTC. Adjust for your local timezone as needed.

## Manual Override

### Check QA Status

```bash
# Check current nodegroup scaling
aws eks describe-nodegroup \
  --cluster-name aura-eks-qa \
  --nodegroup-name aura-general-qa \
  --query 'nodegroup.scalingConfig' \
  --output json

# Invoke Lambda to get status
aws lambda invoke \
  --function-name aura-qa-scaler-qa \
  --payload '{"action": "status"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Start QA Environment (Manual)

```bash
# Invoke Lambda to start QA
aws lambda invoke \
  --function-name aura-qa-scaler-qa \
  --payload '{"action": "start", "trigger": "manual"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Stop QA Environment (Manual)

```bash
# Invoke Lambda to stop QA
aws lambda invoke \
  --function-name aura-qa-scaler-qa \
  --payload '{"action": "stop", "trigger": "manual"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

## Monitoring

### CloudWatch Alarms

| Alarm | Description | Action |
|-------|-------------|--------|
| `aura-qa-scaler-errors-qa` | Lambda execution errors | Check Lambda logs |
| `aura-qa-scale-operation-failures-qa` | Scaling API failures | Verify EKS/IAM permissions |

### CloudWatch Logs

Logs are retained for 90 days (CMMC compliance):

```bash
# View recent Lambda logs
aws logs tail /aws/lambda/aura-qa-scaler-qa --since 1h
```

### Audit Entries

All scaling operations are logged with audit entries:

```json
{
  "timestamp": "2026-01-29T01:00:00Z",
  "event_type": "QA_ENVIRONMENT_CONTROL",
  "action": "stop",
  "trigger": "scheduled",
  "cluster": "aura-eks-qa",
  "nodegroup": "aura-general-qa",
  "request_id": "abc123..."
}
```

## Notifications

SNS notifications are sent to `aura-qa-operations-qa` topic on every scale event.

### Subscribe to Notifications

```bash
# Subscribe email to QA operations
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:aura-qa-operations-qa \
  --protocol email \
  --notification-endpoint your-email@example.com
```

## Troubleshooting

### QA Won't Scale Up

1. **Check EventBridge Schedule:**
   ```bash
   aws scheduler get-schedule --name aura-qa-scale-up
   ```

2. **Check Lambda Permissions:**
   ```bash
   aws lambda get-policy --function-name aura-qa-scaler-qa
   ```

3. **Check EKS Nodegroup Status:**
   ```bash
   aws eks describe-nodegroup \
     --cluster-name aura-eks-qa \
     --nodegroup-name aura-general-qa
   ```

4. **Manual Trigger:**
   ```bash
   aws lambda invoke \
     --function-name aura-qa-scaler-qa \
     --payload '{"action": "start", "trigger": "manual"}' \
     --cli-binary-format raw-in-base64-out \
     /dev/stdout
   ```

### Pods Not Starting After Scale-Up

1. **Wait for Node Registration:**
   Nodes take 3-5 minutes to join the cluster after scale-up.

2. **Check Node Status:**
   ```bash
   kubectl get nodes -l workload-type=general-purpose
   ```

3. **Check Pending Pods:**
   ```bash
   kubectl get pods --all-namespaces | grep Pending
   ```

4. **Check Startup Probe:**
   The QA overlay extends startup probe to 370 seconds for cold starts.

### Cluster Autoscaler Errors

When nodes are scaled to 0, Cluster Autoscaler may log errors attempting to scale. This is expected and harmless since `MaxSize=0` prevents scaling.

## Architecture

```
EventBridge Scheduler
        │
        ▼
   Lambda Function (aura-qa-scaler-qa)
        │
        ├──► EKS UpdateNodegroupConfig API
        │           │
        │           ▼
        │    Node Group Scaling
        │
        ├──► SNS Notification
        │
        └──► CloudWatch Metrics
```

## Cost Savings

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| EKS Nodes (SPOT) | Full | Reduced | ~67% |
| EKS Nodes (On-Demand) | Full | Reduced | ~67% |

**Note:** Neptune, OpenSearch, and ElastiCache continue running 24/7 due to AWS limitations on scheduled scaling.

## Related Resources

- **CloudFormation Template:** `deploy/cloudformation/qa-cost-scheduler.yaml`
- **Lambda Function:** `aura-qa-scaler-qa`
- **SNS Topic:** `aura-qa-operations-qa`
- **Kubernetes Overlay:** `deploy/kubernetes/aura-api/overlays/qa/startup-probe-patch.yaml`
- **Kill-Switch Runbook:** `docs/runbooks/QA_KILLSWITCH_RUNBOOK.md` (full environment shutdown/restore)

## Change History

| Date | Change |
|------|--------|
| 2026-02-15 | Added kill-switch cross-reference; QA fully shut down via kill-switch |
| 2026-01-29 | Initial implementation |
