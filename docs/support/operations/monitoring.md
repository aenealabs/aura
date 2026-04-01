# Monitoring Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This guide covers monitoring strategies, dashboards, metrics, and alerting for Project Aura. Effective monitoring ensures service reliability and enables rapid incident response.

---

## Monitoring Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        DATA SOURCES                                  │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
    │  │  API    │  │ Agents  │  │ Neptune │  │OpenSearch│ │  EKS    │  │
    │  │ Metrics │  │ Metrics │  │ Metrics │  │ Metrics │  │ Metrics │  │
    │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  │
    └───────┼────────────┼────────────┼────────────┼────────────┼────────┘
            │            │            │            │            │
            └────────────┴────────────┼────────────┴────────────┘
                                      │
                                      ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     CloudWatch / Prometheus                          │
    │                                                                      │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │                    Metrics Aggregation                       │   │
    │  │  - Namespace: Aura/*                                         │   │
    │  │  - Dimensions: Environment, Service, Agent                   │   │
    │  │  - Resolution: 1 minute (standard), 1 second (high-res)      │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
    ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
    │  Dashboards  │          │    Alarms    │          │   Insights   │
    │              │          │              │          │              │
    │ - CloudWatch │          │ - SNS        │          │ - Logs       │
    │ - Grafana    │          │ - PagerDuty  │          │ - Traces     │
    │              │          │ - Slack      │          │              │
    └──────────────┘          └──────────────┘          └──────────────┘
```

---

## Key Metrics

### API Metrics

| Metric | Namespace | Description | Alert Threshold |
|--------|-----------|-------------|-----------------|
| `RequestCount` | Aura/API | Total API requests | N/A |
| `ErrorCount` | Aura/API | 4xx and 5xx errors | > 1% of requests |
| `Latency` | Aura/API | Response time (ms) | p99 > 2000ms |
| `ActiveConnections` | Aura/API | Concurrent connections | > 80% capacity |
| `ThrottledRequests` | Aura/API | Rate-limited requests | > 10/min |

### Agent Metrics

| Metric | Namespace | Description | Alert Threshold |
|--------|-----------|-------------|-----------------|
| `ExecutionCount` | Aura/Agents | Agent task executions | N/A |
| `ExecutionDuration` | Aura/Agents | Task duration (ms) | p95 > 5min (coder) |
| `ExecutionErrors` | Aura/Agents | Failed executions | > 5% |
| `QueueDepth` | Aura/Agents | Pending tasks | > 100 |
| `LLMTokens` | Aura/Agents | Bedrock tokens used | > 80% quota |

### Database Metrics

| Metric | Namespace | Description | Alert Threshold |
|--------|-----------|-------------|-----------------|
| `CPUUtilization` | AWS/Neptune | CPU usage % | > 80% |
| `FreeableMemory` | AWS/Neptune | Available memory | < 1GB |
| `VolumeReadIOPs` | AWS/Neptune | Read operations/sec | > 10,000 |
| `ClusterStatus` | AWS/OpenSearch | Cluster health | != green |
| `ConsumedReadCapacity` | AWS/DynamoDB | RCU consumed | > 80% provisioned |

### Kubernetes Metrics

| Metric | Namespace | Description | Alert Threshold |
|--------|-----------|-------------|-----------------|
| `pod_cpu_usage` | k8s | Pod CPU usage | > 80% limit |
| `pod_memory_usage` | k8s | Pod memory usage | > 85% limit |
| `pod_restart_count` | k8s | Container restarts | > 3 in 10min |
| `node_ready` | k8s | Node health status | != True |
| `pvc_usage_percent` | k8s | PVC disk usage | > 80% |

---

## Dashboards

### Executive Dashboard

Overview of platform health and key business metrics.

**Widgets:**

| Widget | Type | Metrics |
|--------|------|---------|
| System Health | Status indicator | Health check results |
| Vulnerabilities | Counter | Open by severity |
| Patches | Counter | Generated, approved, deployed |
| MTTR | Gauge | Mean time to remediate |
| Error Rate | Line chart | 5xx errors over time |

### API Performance Dashboard

Detailed API performance metrics.

**CloudWatch Dashboard JSON:**

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "Request Rate",
        "metrics": [
          ["Aura/API", "RequestCount", "Environment", "${ENV}"]
        ],
        "period": 60,
        "stat": "Sum"
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Latency Percentiles",
        "metrics": [
          ["Aura/API", "Latency", "Environment", "${ENV}", {"stat": "p50"}],
          ["...", {"stat": "p95"}],
          ["...", {"stat": "p99"}]
        ],
        "period": 60
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Error Rate",
        "metrics": [
          [{"expression": "errors/requests*100", "label": "Error %"}]
        ],
        "period": 300
      }
    }
  ]
}
```

### Agent Performance Dashboard

Agent-specific performance tracking.

**Widgets:**

| Widget | Description |
|--------|-------------|
| Execution Timeline | Agent executions over time |
| Latency Heatmap | Execution duration distribution |
| Queue Depth | Pending tasks by agent type |
| Token Usage | LLM token consumption |
| Error Breakdown | Errors by agent and type |

### Infrastructure Dashboard

EKS and AWS resource monitoring.

**Widgets:**

| Widget | Description |
|--------|-------------|
| Node Health | EKS node status and capacity |
| Pod Status | Pod health by namespace |
| Resource Usage | CPU/memory utilization |
| Network | Traffic in/out |
| Storage | PVC usage and IOPS |

---

## Alerting

### Alert Configuration

**CloudWatch Alarm Example:**

```yaml
# High API Error Rate Alarm
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  HighErrorRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: aura-api-high-error-rate-${Environment}
      AlarmDescription: API error rate exceeds 1%
      MetricName: ErrorCount
      Namespace: Aura/API
      Dimensions:
        - Name: Environment
          Value: !Ref Environment
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 2
      Threshold: 100
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Ref AlertSNSTopic
      OKActions:
        - !Ref AlertSNSTopic
```

### Alert Routing

| Alert | Severity | Routing |
|-------|----------|---------|
| System Down | P1 | PagerDuty + Slack #incidents |
| High Error Rate | P2 | PagerDuty + Slack #alerts |
| Resource Warning | P3 | Slack #alerts |
| Informational | P4 | Slack #monitoring |

### Alert Runbooks

Each alert should have an associated runbook:

**Example: High API Error Rate**

```
ALERT: aura-api-high-error-rate
SEVERITY: P2
DESCRIPTION: API error rate exceeds 1% for 10 minutes

TRIAGE STEPS:
1. Check CloudWatch Logs for error patterns:
   - Log Group: /aura/api
   - Filter: "ERROR" or status >= 500

2. Identify error type:
   - 500: Internal error (check application logs)
   - 502: Upstream failure (check dependencies)
   - 503: Overloaded (check resource utilization)
   - 504: Timeout (check database/external calls)

3. Check dependencies:
   - Neptune: aws neptune describe-db-clusters
   - OpenSearch: curl opensearch.aura.local:9200/_cluster/health
   - Bedrock: Check quota usage

MITIGATION:
- If overloaded: Scale API pods
- If dependency failure: Check specific service
- If application bug: Consider rollback

ESCALATION:
- After 30 minutes: Escalate to secondary on-call
- After 1 hour: Escalate to on-call manager
```

---

## Health Checks

### Application Health Endpoints

| Endpoint | Check | Frequency |
|----------|-------|-----------|
| `/health` | Basic liveness | 10s |
| `/health/ready` | Full readiness | 30s |
| `/health/deep` | All dependencies | 60s |

**Health Check Response:**

```json
{
  "status": "healthy",
  "version": "1.6.0",
  "checks": {
    "api": {
      "status": "healthy",
      "latency_ms": 5
    },
    "neptune": {
      "status": "healthy",
      "latency_ms": 15
    },
    "opensearch": {
      "status": "healthy",
      "latency_ms": 20
    },
    "bedrock": {
      "status": "healthy",
      "latency_ms": 100
    },
    "dynamodb": {
      "status": "healthy",
      "latency_ms": 10
    }
  },
  "timestamp": "2026-01-19T12:00:00Z"
}
```

### Synthetic Monitoring

Synthetic tests that run continuously:

```bash
# Synthetic test script (runs every 5 minutes)
#!/bin/bash

# Test API health
HEALTH=$(curl -s -w "%{http_code}" -o /dev/null https://api.aenealabs.com/v1/health)
if [ "$HEALTH" != "200" ]; then
  echo "Health check failed: $HEALTH"
  # Send alert
fi

# Test authentication
TOKEN=$(curl -s -X POST https://api.aenealabs.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"synthetic@test.com","password":"***"}' | jq -r '.data.access_token')

if [ -z "$TOKEN" ]; then
  echo "Auth test failed"
  # Send alert
fi

# Test API operation
REPOS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.aenealabs.com/v1/repositories | jq '.data | length')

echo "Synthetic test passed: $REPOS repositories found"
```

---

## Observability Best Practices

### Metric Naming Conventions

```
{namespace}/{service}/{metric_name}

Examples:
- Aura/API/RequestCount
- Aura/Agents/ExecutionDuration
- Aura/HITL/ApprovalLatency
```

### Tagging Strategy

| Tag | Description | Example |
|-----|-------------|---------|
| Environment | Deployment environment | prod, qa, dev |
| Service | Service name | api, orchestrator |
| Team | Owning team | platform, security |
| CostCenter | Billing allocation | eng-platform |

### Retention Policies

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| High-resolution metrics | 3 hours | CloudWatch |
| Standard metrics | 15 months | CloudWatch |
| Logs | 90 days (prod), 30 days (dev) | CloudWatch Logs |
| Traces | 30 days | X-Ray |

---

## Related Documentation

- [Operations Index](./index.md)
- [Logging Guide](./logging.md)
- [Troubleshooting](../troubleshooting/index.md)
- [Performance Issues](../troubleshooting/performance-issues.md)

---

*Last updated: January 2026 | Version 1.0*
