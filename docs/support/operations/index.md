# Operations Guide

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This operations guide provides procedures and best practices for managing Project Aura in production environments. It covers monitoring, logging, backup and restore, and scaling operations.

---

## Operations Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Monitoring Guide](./monitoring.md) | CloudWatch dashboards, metrics, alerts | SRE, DevOps |
| [Logging Guide](./logging.md) | Log formats, retention, analysis | SRE, DevOps, Security |
| [Backup and Restore](./backup-restore.md) | Data protection procedures | SRE, Database Admin |
| [Scaling Guide](./scaling.md) | Auto-scaling, capacity planning | SRE, Platform Engineers |

---

## Daily Operations Checklist

### Morning Check (Start of Business)

```
□ Review overnight alerts in PagerDuty/Slack
□ Check system health dashboard
□ Verify all critical services are healthy
□ Review error rates from last 8 hours
□ Check pending HITL approvals
□ Review any failed scans or deployments
```

### End of Day Check

```
□ Review day's incidents and resolutions
□ Check backup job completion
□ Verify no critical alerts outstanding
□ Review resource utilization trends
□ Update on-call handoff notes
```

---

## Quick Commands Reference

### Health Checks

```bash
# API health
curl -s https://api.aenealabs.com/v1/health | jq '.status'

# Kubernetes cluster health
kubectl get nodes
kubectl get pods -n aura-system --field-selector=status.phase!=Running

# Database health
aws neptune describe-db-clusters \
  --db-cluster-identifier aura-neptune-cluster-${ENV} \
  --query 'DBClusters[0].Status'
```

### Service Management

```bash
# Restart a deployment
kubectl rollout restart deployment/${SERVICE} -n aura-system

# Check rollout status
kubectl rollout status deployment/${SERVICE} -n aura-system

# View recent logs
kubectl logs -n aura-system -l app=${SERVICE} --tail=100 --since=1h

# Scale a service
kubectl scale deployment/${SERVICE} -n aura-system --replicas=${COUNT}
```

### Database Operations

```bash
# Neptune connection test
aws neptune describe-db-cluster-endpoints \
  --db-cluster-identifier aura-neptune-cluster-${ENV}

# DynamoDB table status
aws dynamodb describe-table \
  --table-name aura-approval-requests-${ENV} \
  --query 'Table.TableStatus'

# OpenSearch cluster health
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://opensearch.aura.local:9200/_cluster/health" | jq
```

---

## Service Level Objectives (SLOs)

### Availability SLOs

| Service | Target | Measurement |
|---------|--------|-------------|
| API Gateway | 99.9% | Successful requests / Total requests |
| Agent Orchestrator | 99.5% | Healthy pods / Total pods |
| Scan Service | 99.0% | Successful scans / Total scans |
| HITL Workflow | 99.9% | Approval requests processed |

### Latency SLOs

| Operation | P50 Target | P95 Target | P99 Target |
|-----------|------------|------------|------------|
| API requests | 100ms | 500ms | 1s |
| Context retrieval | 50ms | 200ms | 500ms |
| Patch generation | 30s | 2min | 5min |
| Sandbox validation | 3min | 10min | 15min |

### Error Rate SLOs

| Category | Target | Alert Threshold |
|----------|--------|-----------------|
| API 5xx errors | < 0.1% | > 0.5% |
| Agent failures | < 1% | > 5% |
| Scan failures | < 2% | > 10% |

---

## Incident Management

### Incident Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| SEV1 | Complete outage | 15 minutes | Immediate |
| SEV2 | Major degradation | 30 minutes | Within 1 hour |
| SEV3 | Partial degradation | 4 hours | Next business day |
| SEV4 | Minor issue | 24 hours | Scheduled |

### Incident Response Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INCIDENT RESPONSE WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    DETECTION          TRIAGE           MITIGATION         RESOLUTION
    ┌────────┐        ┌────────┐        ┌────────┐        ┌────────┐
    │ Alert  │───────►│ Assess │───────►│  Fix   │───────►│ Verify │
    │ Fired  │        │ Impact │        │ Issue  │        │& Close │
    └────────┘        └────────┘        └────────┘        └────────┘
         │                │                  │                  │
         ▼                ▼                  ▼                  ▼
    - PagerDuty      - Severity         - Runbook         - Health check
    - Slack          - User impact      - Rollback        - Monitoring
    - CloudWatch     - Scope            - Scale           - Post-mortem
```

### On-Call Responsibilities

1. **Primary On-Call:**
   - First responder for all alerts
   - Acknowledge within SLA
   - Initial triage and mitigation

2. **Secondary On-Call:**
   - Backup for primary
   - Escalation point
   - Expertise in specific areas

3. **On-Call Manager:**
   - Coordination for SEV1/SEV2
   - Stakeholder communication
   - Resource allocation

---

## Maintenance Windows

### Standard Maintenance Schedule

| Day | Time (UTC) | Type | Duration |
|-----|------------|------|----------|
| Tuesday | 02:00-04:00 | Patching | 2 hours |
| Thursday | 02:00-04:00 | Updates | 2 hours |
| Sunday | 02:00-06:00 | Major changes | 4 hours |

### Maintenance Procedures

**Pre-Maintenance:**

```bash
# Notify users (24 hours before)
curl -X POST https://api.aenealabs.com/v1/admin/notifications \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"type": "maintenance", "start": "2026-01-20T02:00:00Z", "duration": "2h"}'

# Update status page
# (Via status page admin interface)

# Verify backup completion
aws dynamodb describe-continuous-backups --table-name aura-approval-requests-${ENV}
```

**During Maintenance:**

```bash
# Enable maintenance mode
kubectl set env deployment/aura-api -n aura-system MAINTENANCE_MODE=true

# Perform maintenance tasks
# ...

# Disable maintenance mode
kubectl set env deployment/aura-api -n aura-system MAINTENANCE_MODE=false
```

**Post-Maintenance:**

```bash
# Verify services
curl -s https://api.aenealabs.com/v1/health | jq

# Clear status page
# (Via status page admin interface)

# Send completion notification
curl -X POST https://api.aenealabs.com/v1/admin/notifications \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"type": "maintenance_complete"}'
```

---

## Change Management

### Change Categories

| Category | Approval | Testing | Rollback Plan |
|----------|----------|---------|---------------|
| Standard | Pre-approved | Automated | Documented |
| Normal | Change board | Staging | Required |
| Emergency | Verbal + post-approval | Minimal | Required |

### Deployment Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT PIPELINE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

    DEV              QA               STAGING           PRODUCTION
    ┌────────┐      ┌────────┐      ┌────────┐        ┌────────┐
    │ Build  │─────►│ Test   │─────►│ Verify │───────►│ Deploy │
    │& Unit  │      │& Integ │      │& Perf  │        │& Monitor│
    └────────┘      └────────┘      └────────┘        └────────┘
         │               │               │                  │
         ▼               ▼               ▼                  ▼
    Automated       Automated       Manual Gate       Canary + Full
```

---

## Capacity Planning

### Current Resource Utilization

| Resource | Current | Threshold | Scaling Action |
|----------|---------|-----------|----------------|
| EKS nodes | 4 | 6 (75%) | Add node group |
| Neptune CPU | 45% | 70% | Upgrade instance |
| OpenSearch | 60% | 80% | Add data node |
| DynamoDB RCU | 500 | 1000 | On-demand |

### Growth Projections

| Metric | Current | 3 Month | 6 Month | 12 Month |
|--------|---------|---------|---------|----------|
| Repositories | 50 | 100 | 200 | 500 |
| Daily scans | 200 | 500 | 1000 | 2500 |
| Patches/day | 50 | 150 | 300 | 750 |
| API calls/min | 500 | 1500 | 3000 | 7500 |

---

## Cost Management

### Monthly Cost Breakdown

| Service | Current | Budget | Alert |
|---------|---------|--------|-------|
| EKS | $2,500 | $3,000 | $2,700 |
| Neptune | $1,200 | $1,500 | $1,350 |
| OpenSearch | $800 | $1,000 | $900 |
| Bedrock | $500 | $750 | $600 |
| S3 | $150 | $200 | $180 |
| Data Transfer | $100 | $150 | $120 |

### Cost Optimization Tips

1. **Reserved Instances:** Consider RI for Neptune and OpenSearch (up to 40% savings)
2. **Spot Instances:** Use for non-critical EKS workloads
3. **Right-sizing:** Review underutilized resources monthly
4. **Data lifecycle:** Implement S3 lifecycle policies

---

## Related Documentation

- [Monitoring Guide](./monitoring.md)
- [Logging Guide](./logging.md)
- [Backup and Restore](./backup-restore.md)
- [Scaling Guide](./scaling.md)
- [Troubleshooting](../troubleshooting/index.md)
- [Architecture Overview](../architecture/index.md)

---

*Last updated: January 2026 | Version 1.0*
