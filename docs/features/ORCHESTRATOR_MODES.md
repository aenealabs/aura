# Orchestrator Deployment Modes

**Version:** 1.0
**Last Updated:** December 15, 2025
**Status:** Implemented

---

## Table of Contents

1. [Overview](#overview)
2. [Deployment Modes](#deployment-modes)
3. [Architecture](#architecture)
4. [API Reference](#api-reference)
5. [Configuration](#configuration)
6. [Cost Analysis](#cost-analysis)
7. [Mode Transitions](#mode-transitions)
8. [Monitoring and Alarms](#monitoring-and-alarms)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Project Aura's Agent Orchestrator supports three deployment modes, enabling organizations to balance cost, latency, and throughput based on their specific requirements. The deployment mode can be configured at the platform level (affecting all organizations) or with per-organization overrides.

**Key Features:**

- **UI-configurable:** Change modes via REST API or management console
- **Per-organization overrides:** Different orgs can use different modes
- **Anti-thrashing protection:** 5-minute cooldown between mode changes
- **Safe transitions:** State machine ensures graceful mode switching
- **Cost transparency:** Clear monthly cost estimates for each mode

---

## Deployment Modes

### On-Demand Mode

**Cost:** $0/month base cost (pay per job execution)

On-demand mode creates EKS Jobs per orchestration request. Jobs are provisioned when needed and terminated after completion.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | $0.00 |
| Per-Job Cost | ~$0.15 (15 min on m5.large) |
| Cold Start Latency | ~30 seconds |
| Max Concurrency | Limited by EKS Job quotas |

**Recommended For:**

- Low-volume workloads (<100 jobs/day)
- Cost-sensitive environments
- Development and test environments
- Unpredictable traffic patterns

**How It Works:**

```text
Request -> API -> Create EKS Job -> Process -> Job Terminates
                                              |
                                              v
                                    Results in DynamoDB
```

---

### Warm Pool Mode

**Cost:** ~$28/month base cost

Warm pool mode maintains always-on replica(s) that poll SQS for jobs. This eliminates cold start latency at the cost of a fixed monthly fee.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | ~$28.00 |
| Per-Job Marginal Cost | ~$0.00 (included in base) |
| Cold Start Latency | 0 seconds |
| Default Replicas | 1 |
| Max Replicas | 10 |

**Recommended For:**

- High-volume workloads (>500 jobs/day)
- Latency-sensitive applications
- Production environments
- Consistent traffic patterns

**How It Works:**

```text
Request -> API -> SQS Queue -> Warm Pool Pod (always running)
                               |
                               v
                       Process Immediately
                               |
                               v
                     Results in DynamoDB
```

---

### Hybrid Mode

**Cost:** ~$28/month + burst job costs

Hybrid mode combines warm pool with burst capacity. The warm pool handles baseline traffic while additional EKS Jobs are spawned during peak loads.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | ~$28.00 |
| Burst Job Cost | ~$0.15/job |
| Cold Start Latency | 0 seconds (warm pool), ~30s (burst) |
| Queue Depth Threshold | Configurable (default: 5) |
| Max Burst Jobs | Configurable (default: 10) |

**Recommended For:**

- Variable workloads with traffic spikes
- High-value production workloads
- Enterprise deployments
- Latency-sensitive with burst capacity needs

**How It Works:**

```text
Request -> API -> SQS Queue
                    |
                    v
          [Queue Depth < Threshold?]
                /           \
               /             \
              v               v
        Warm Pool Pod    Spawn Burst Job
        (instant)        (30s cold start)
              |               |
              v               v
          Process          Process
              |               |
              +-------+-------+
                      |
                      v
            Results in DynamoDB
```

---

## Architecture

### Component Overview

```text
+------------------+     +------------------------+     +------------------+
|   Frontend UI    | --> | Orchestrator Settings  | --> |  DynamoDB        |
|                  |     |    Endpoints (API)     |     | (Settings Store) |
+------------------+     +------------------------+     +------------------+
                                   |
                                   v
                         +------------------------+
                         | OrchestratorModeService|
                         |  (Mode Transitions)    |
                         +------------------------+
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
            +---------------+            +----------------+
            | K8s Warm Pool |            | CloudWatch     |
            | Deployment    |            | Metrics/Alarms |
            +---------------+            +----------------+
```

### Source Files

| Component | File Path | Description |
|-----------|-----------|-------------|
| REST API | `src/api/orchestrator_settings_endpoints.py` | API endpoints for mode configuration |
| Mode Service | `src/services/orchestrator_mode_service.py` | Mode transition state machine |
| K8s RBAC | `deploy/kubernetes/agent-orchestrator/base/rbac.yaml` | Permissions for warm pool scaling |

### Kubernetes Resources

The warm pool deployment uses the following K8s resources:

- **Deployment:** `agent-orchestrator-warm-pool` - The warm pool pods
- **Service:** `agent-orchestrator` - ClusterIP service for internal access
- **ServiceAccount:** `aura-api` - For K8s API authentication
- **Role/RoleBinding:** `orchestrator-scaler` - Permissions to scale warm pool

---

## API Reference

### Base URL

```
/api/v1/orchestrator/settings
```

### Authentication

All endpoints require authentication. Admin role required for write operations.

---

### GET /api/v1/orchestrator/settings

Get current orchestrator settings.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string (optional) | Get org-specific settings |

**Response:**

```json
{
  "on_demand_jobs_enabled": true,
  "warm_pool_enabled": false,
  "hybrid_mode_enabled": false,
  "warm_pool_replicas": 1,
  "hybrid_threshold_queue_depth": 5,
  "hybrid_scale_up_cooldown_seconds": 60,
  "hybrid_max_burst_jobs": 10,
  "estimated_cost_per_job_usd": 0.15,
  "estimated_warm_pool_monthly_usd": 28.0,
  "mode_change_cooldown_seconds": 300,
  "last_mode_change_at": "2025-12-15T10:30:00Z",
  "last_mode_change_by": "admin@company.com",
  "effective_mode": "on_demand",
  "is_organization_override": false,
  "organization_id": null
}
```

---

### PUT /api/v1/orchestrator/settings

Update orchestrator settings. Requires admin role.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string (optional) | Update org-specific settings |

**Request Body:**

```json
{
  "warm_pool_enabled": true,
  "warm_pool_replicas": 2,
  "hybrid_threshold_queue_depth": 10
}
```

**Notes:**

- Only include fields you want to update
- Enabling hybrid mode auto-enables warm pool
- Changes may not take effect immediately; use `/switch` for explicit mode changes

---

### GET /api/v1/orchestrator/settings/modes

Get information about available deployment modes.

**Response:**

```json
[
  {
    "mode": "on_demand",
    "display_name": "On-Demand Jobs",
    "description": "EKS Jobs created per request. Zero base cost, pay per job execution.",
    "base_monthly_cost_usd": 0.0,
    "cold_start_seconds": 30.0,
    "recommended_for": [
      "Low-volume workloads (<100 jobs/day)",
      "Cost-sensitive environments",
      "Dev/test environments",
      "Unpredictable traffic patterns"
    ]
  },
  {
    "mode": "warm_pool",
    "display_name": "Warm Pool",
    "description": "Always-on replica for instant job processing. Fixed monthly cost.",
    "base_monthly_cost_usd": 28.0,
    "cold_start_seconds": 0.0,
    "recommended_for": [
      "High-volume workloads (>500 jobs/day)",
      "Latency-sensitive applications",
      "Production environments",
      "Consistent traffic patterns"
    ]
  },
  {
    "mode": "hybrid",
    "display_name": "Hybrid Mode",
    "description": "Warm pool + burst jobs. Best of both worlds for variable workloads.",
    "base_monthly_cost_usd": 28.0,
    "cold_start_seconds": 0.0,
    "recommended_for": [
      "Variable workloads with peaks",
      "High-value production workloads",
      "Latency-sensitive with burst capacity",
      "Enterprise deployments"
    ]
  }
]
```

---

### POST /api/v1/orchestrator/settings/switch

Explicitly switch deployment mode. Requires admin role.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string (optional) | Switch mode for specific org |

**Request Body:**

```json
{
  "target_mode": "warm_pool",
  "reason": "Switching to production mode before launch",
  "force": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target_mode` | enum | Yes | `on_demand`, `warm_pool`, or `hybrid` |
| `reason` | string | No | Reason for mode change (max 500 chars) |
| `force` | boolean | No | Bypass cooldown (admin only) |

**Response Codes:**

| Code | Description |
|------|-------------|
| 200 | Mode switched successfully |
| 429 | Cooldown active (try later or use force) |
| 400 | Invalid request |
| 403 | Admin role required |

---

### GET /api/v1/orchestrator/settings/status

Get current operational status.

**Response:**

```json
{
  "current_mode": "warm_pool",
  "warm_pool_replicas_desired": 1,
  "warm_pool_replicas_ready": 1,
  "queue_depth": 0,
  "active_burst_jobs": 0,
  "can_switch_mode": true,
  "cooldown_remaining_seconds": 0,
  "last_mode_change_at": "2025-12-15T10:30:00Z",
  "last_mode_change_by": "admin@company.com"
}
```

---

### GET /api/v1/orchestrator/settings/health

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "service": "orchestrator_settings",
  "mode": "aws"
}
```

---

## Configuration

### Platform Defaults

Platform-wide defaults are stored in DynamoDB under the `platform:orchestrator` settings key.

| Setting | Default | Description |
|---------|---------|-------------|
| `on_demand_jobs_enabled` | `true` | Enable on-demand EKS Jobs |
| `warm_pool_enabled` | `false` | Enable warm pool |
| `hybrid_mode_enabled` | `false` | Enable hybrid mode |
| `warm_pool_replicas` | `1` | Number of warm pool replicas |
| `hybrid_threshold_queue_depth` | `5` | Queue depth to trigger burst |
| `hybrid_max_burst_jobs` | `10` | Maximum burst jobs |
| `mode_change_cooldown_seconds` | `300` | Cooldown between mode changes |

### Per-Organization Overrides

Organizations can override platform defaults with their own settings. Overrides are stored under `organization:{org_id}:orchestrator`.

**Override Behavior:**

- Organization settings are merged with platform defaults
- Organization values override platform values
- Unset organization values fall back to platform defaults

**Example:**

```text
Platform Default: warm_pool_enabled=false, warm_pool_replicas=1
Org Override:     warm_pool_enabled=true

Effective for Org: warm_pool_enabled=true, warm_pool_replicas=1
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_AWS_DYNAMODB` | - | Use AWS DynamoDB for settings persistence |
| `ORCHESTRATOR_NAMESPACE` | `default` | K8s namespace for warm pool |
| `KUBERNETES_SERVICE_HOST` | - | Auto-detect K8s environment |

---

## Cost Analysis

### Monthly Cost Comparison

| Mode | Base Cost | 100 Jobs/Day | 500 Jobs/Day | 1000 Jobs/Day |
|------|-----------|--------------|--------------|---------------|
| **On-Demand** | $0 | $450 | $2,250 | $4,500 |
| **Warm Pool** | $28 | $28 | $28 | $28 |
| **Hybrid** | $28 | $28 + burst | $28 + burst | $28 + burst |

**Break-even Analysis:**

- Warm Pool becomes cost-effective at ~187 jobs/month (~6 jobs/day)
- For >6 jobs/day, warm pool saves money over on-demand
- Hybrid adds burst capacity without significantly increasing baseline costs

### Cost Calculation Formula

```text
On-Demand Monthly Cost = (jobs_per_day * 30 * $0.15)
Warm Pool Monthly Cost = $28 (fixed)
Hybrid Monthly Cost = $28 + (burst_jobs * $0.15)
```

---

## Mode Transitions

### State Machine

Mode transitions follow a state machine to ensure safe, graceful switching:

```text
ACTIVE -> DRAINING -> COMPLETING -> SCALING -> ACTIVE
                                          |
                                          v
                                       FAILED
```

**States:**

| State | Description |
|-------|-------------|
| `ACTIVE` | Normal operation in current mode |
| `DRAINING` | Stop accepting new jobs to current mode |
| `COMPLETING` | Wait for in-flight jobs to finish |
| `SCALING` | Adjust warm pool replicas |
| `FAILED` | Transition failed (manual intervention needed) |

### Cooldown Protection

A 5-minute (300 second) cooldown prevents mode thrashing:

- Cooldown starts after each mode change
- During cooldown, `/switch` returns HTTP 429
- Admins can use `force=true` to bypass (logged for audit)

### Monitoring Transitions

```bash
# Check transition status via API
curl -H "Authorization: Bearer $TOKEN" \
  https://api.aenealabs.com/api/v1/orchestrator/settings/status

# Check K8s deployment status
kubectl get deployment agent-orchestrator-warm-pool -o wide
```

---

## Monitoring and Alarms

### CloudWatch Metrics

| Metric | Description | Dimensions |
|--------|-------------|------------|
| `OrchestratorModeChange` | Count of mode changes | EventType, OrganizationId, User |

### CloudWatch Alarms

| Alarm | Condition | Action |
|-------|-----------|--------|
| Mode Thrashing | >3 mode changes in 1 hour | SNS notification |
| Warm Pool Not Ready | Ready replicas < desired for >5 min | SNS notification |
| Burst Overload | Burst jobs > max_burst_jobs | SNS notification |

### Log Groups

Mode change events are logged to CloudWatch Logs:

- `/aura/{env}/orchestrator-settings` - API access logs
- `/aura/{env}/orchestrator-mode-service` - Transition logs

---

## Best Practices

### Choosing a Mode

1. **Start with On-Demand:** Begin with on-demand for new deployments to understand traffic patterns
2. **Monitor Job Volume:** Track daily job counts for 1-2 weeks
3. **Switch to Warm Pool:** If >6 jobs/day consistently, switch to warm pool
4. **Enable Hybrid:** If experiencing traffic spikes, enable hybrid mode

### Production Recommendations

| Environment | Recommended Mode | Rationale |
|-------------|------------------|-----------|
| Development | On-Demand | Cost savings, low traffic |
| QA/Staging | On-Demand | Cost savings, intermittent use |
| Production (Low Volume) | On-Demand | <100 jobs/day |
| Production (High Volume) | Warm Pool | >500 jobs/day, SLA requirements |
| Production (Variable) | Hybrid | Traffic spikes, enterprise |

### Mode Change Checklist

Before switching modes:

- [ ] Review current job volume and patterns
- [ ] Check for active orchestration jobs
- [ ] Notify stakeholders of potential latency changes
- [ ] Verify K8s cluster has capacity for warm pool
- [ ] Plan change during low-traffic period

---

## Troubleshooting

### Common Issues

**Issue:** Mode switch returns HTTP 429 (Too Many Requests)

**Cause:** Cooldown period active from recent mode change.

**Solution:**
```bash
# Check cooldown status
curl -H "Authorization: Bearer $TOKEN" \
  https://api.aenealabs.com/api/v1/orchestrator/settings/status

# Wait for cooldown to expire, or use force (admin only):
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_mode": "warm_pool", "force": true, "reason": "Emergency switch"}' \
  https://api.aenealabs.com/api/v1/orchestrator/settings/switch
```

---

**Issue:** Warm pool replicas not scaling

**Cause:** K8s RBAC permissions or deployment issues.

**Solution:**
```bash
# Check RBAC
kubectl auth can-i patch deployments/scale --as=system:serviceaccount:default:aura-api

# Check deployment status
kubectl describe deployment agent-orchestrator-warm-pool

# Check events for errors
kubectl get events --sort-by='.lastTimestamp' | grep orchestrator
```

---

**Issue:** Settings not persisting

**Cause:** DynamoDB connection or permissions issue.

**Solution:**
```bash
# Check API health
curl https://api.aenealabs.com/api/v1/orchestrator/settings/health

# Verify DynamoDB table exists
aws dynamodb describe-table --table-name aura-settings-dev

# Check IRSA role permissions
aws iam simulate-principal-policy \
  --policy-source-arn <irsa-role-arn> \
  --action-names dynamodb:GetItem dynamodb:PutItem
```

---

**Issue:** Organization override not applied

**Cause:** Missing organization_id parameter or org settings not saved.

**Solution:**
```bash
# Verify org settings exist
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.aenealabs.com/api/v1/orchestrator/settings?organization_id=org-123"

# Check if is_organization_override is true in response
# If false, org-specific settings haven't been saved

# Save org-specific settings
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"warm_pool_enabled": true}' \
  "https://api.aenealabs.com/api/v1/orchestrator/settings?organization_id=org-123"
```

---

## Related Documentation

- [DEPLOYMENT_GUIDE.md](../deployment/DEPLOYMENT_GUIDE.md) - Phase 7: Agent Orchestrator Deployment
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) - Agent Orchestration Architecture
- [ADR-032: Configurable Autonomy Framework](../architecture-decisions/ADR-032-configurable-autonomy-framework.md) - Related autonomy configuration

---

**Document Version:** 1.0
**Maintained By:** Project Aura Platform Team
