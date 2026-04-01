# Monitoring and Observability Guide

This guide explains how to monitor Aura Platform health, track agent performance, view security alerts, and understand the observability features available to you.

---

## Monitoring Overview

Aura provides comprehensive observability through dashboards, alerts, and logs.

```
+--------------------------------------------------+
|                   Dashboard                       |
|  +------------+  +------------+  +------------+  |
|  | Health     |  | Agents     |  | Security   |  |
|  | Metrics    |  | Activity   |  | Alerts     |  |
|  +------------+  +------------+  +------------+  |
+--------------------------------------------------+
                        |
         +--------------+--------------+
         |              |              |
         v              v              v
   CloudWatch      Prometheus      SNS Alerts
    Metrics         /Grafana       (Email/Slack)
```

---

## Dashboard Overview

### Main Dashboard

The main dashboard provides a unified view of platform status.

| Widget | Description |
|--------|-------------|
| **System Health** | Overall platform status |
| **Active Agents** | Running agent count |
| **Vulnerabilities** | Open findings by severity |
| **Pending Approvals** | Items awaiting review |
| **Security Alerts** | Recent security events |
| **Activity Feed** | Recent platform activity |

### Customizing Your Dashboard

1. Click **Customize** (grid icon)
2. Drag widgets to reorder
3. Add/remove widgets from the registry
4. Save your layout

---

## Health Monitoring

### Platform Health Status

The system continuously monitors health:

| Status | Meaning | Action |
|--------|---------|--------|
| **Healthy** | All systems operational | None required |
| **Degraded** | Some features impacted | Monitor closely |
| **Unhealthy** | Significant issues | Contact support |

### Health Indicators

| Component | What's Monitored |
|-----------|------------------|
| API Service | Response time, error rate |
| Neptune Graph | Connection, query latency |
| OpenSearch | Cluster status, index health |
| Bedrock LLM | API availability, latency |
| Agent Pool | Active agents, queue depth |

### Viewing Detailed Health

1. Navigate to the Dashboard
2. Click on **System Health** widget
3. View component-level status:
   - Connection status
   - Latency percentiles
   - Error rates
   - Resource usage

---

## Agent Monitoring

### Agent Activity Panel

Track what agents are doing:

| Metric | Description |
|--------|-------------|
| **Active Tasks** | Currently executing |
| **Completed** | Successfully finished |
| **Failed** | Encountered errors |
| **Queued** | Waiting for execution |

### Agent Performance Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Task Completion Rate | > 95% | Successful completions |
| Average Latency | < 30s | Time to complete |
| Error Rate | < 5% | Failed tasks |
| Cache Hit Rate | > 60% | Semantic cache efficiency |

### Viewing Agent Details

1. Navigate to **Agents** in sidebar
2. Click on an agent
3. View:
   - Current status
   - Recent tasks
   - Performance history
   - Configuration

---

## Security Alerts

### Security Alerts Panel

The Security Alerts panel shows threats and incidents.

### Alert Priorities

| Priority | Response Time | Examples |
|----------|---------------|----------|
| **P1 - Critical** | Immediate | Active breach, credential exposure |
| **P2 - High** | < 1 hour | Injection attempt, anomaly detected |
| **P3 - Medium** | < 4 hours | Suspicious pattern |
| **P4 - Low** | < 24 hours | Policy violation |
| **P5 - Info** | Best effort | Informational |

### Alert Workflow

```
Alert Triggered
       |
       v
+------------------+
| Notification     |  <-- Email/Slack/Dashboard
+------------------+
       |
       v
+------------------+
| Acknowledge      |  <-- Claim ownership
+------------------+
       |
       v
+------------------+
| Investigate      |  <-- Review details
+------------------+
       |
       v
+------------------+
| Resolve          |  <-- Document resolution
+------------------+
```

### Managing Alerts

| Action | Description |
|--------|-------------|
| **Acknowledge** | Claim ownership of alert |
| **Assign** | Delegate to team member |
| **Escalate** | Increase priority |
| **Resolve** | Mark as handled |
| **Suppress** | Mute similar alerts |

### Viewing Alert Details

Click on any alert to see:

- Alert description and severity
- Affected resources
- Timeline of events
- Related alerts
- Audit log entries
- Recommended actions

---

## Notifications

### Notification Channels

| Channel | Use Case |
|---------|----------|
| **Dashboard** | Real-time in-app notifications |
| **Email** | HITL approvals, critical alerts |
| **Slack** | Team notifications (Enterprise mode) |
| **SNS** | Integration with other systems |

### Configuring Notifications

1. Navigate to **Settings > Notifications**
2. Configure channels:
   - Enable/disable channels
   - Set notification preferences
   - Configure escalation rules

### Notification Types

| Type | Description | Default Channel |
|------|-------------|-----------------|
| Approval Request | New item needs review | Email + Dashboard |
| Approval Timeout | Request about to expire | Email |
| Security Alert | Security event detected | Based on priority |
| Deployment Complete | Patch deployed | Dashboard |
| Environment Ready | Test env provisioned | Dashboard |

---

## Metrics and Analytics

### Key Performance Indicators

| KPI | Description | Target |
|-----|-------------|--------|
| **Mean Time to Remediate (MTTR)** | Time from detection to fix | < 24 hours |
| **False Positive Rate** | Incorrect vulnerability flags | < 10% |
| **Patch Success Rate** | Patches that pass testing | > 90% |
| **Approval Turnaround** | Time to approve/reject | < 4 hours |

### Viewing Metrics

1. Navigate to **Analytics** or use Chat Assistant
2. Request specific metrics:
   - "Show vulnerability trends for last month"
   - "What's our MTTR this quarter?"
   - "Generate a security report"

### Metric Dashboards

| Dashboard | Focus |
|-----------|-------|
| **Security Overview** | Vulnerabilities, alerts, compliance |
| **Agent Performance** | Task completion, latency, errors |
| **Cost & Usage** | LLM costs, environment usage |
| **Compliance** | Audit logs, retention, coverage |

---

## Logs and Audit Trail

### Log Types

| Log Type | Purpose | Retention |
|----------|---------|-----------|
| **Audit Logs** | Security-relevant actions | Configurable (30-365 days) |
| **Application Logs** | System operations | 90 days |
| **Agent Logs** | Agent execution details | 30 days |
| **Access Logs** | API and UI access | 90 days |

### Viewing Logs

1. Navigate to **Logs** (or use Chat Assistant)
2. Filter by:
   - Time range
   - Log type
   - Severity
   - User
   - Resource

### Audit Log Contents

Every audited action includes:

| Field | Description |
|-------|-------------|
| Timestamp | When it occurred |
| User | Who performed it |
| Action | What was done |
| Resource | What was affected |
| Result | Success/failure |
| IP Address | Where from |
| Context | Additional details |

---

## Cost Monitoring

### LLM Cost Tracking

Monitor AI usage costs:

| Metric | Description |
|--------|-------------|
| **Daily Spend** | Today's LLM costs |
| **Monthly Spend** | Current month total |
| **Budget Used** | Percentage of budget |
| **Trend** | Compared to previous period |

### Environment Cost Tracking

Monitor test environment costs:

| Metric | Description |
|--------|-------------|
| **Active Environments** | Current resource usage |
| **Daily Burn Rate** | Today's environment costs |
| **Monthly Total** | Current month spend |
| **Budget Remaining** | Available budget |

### Cost Alerts

Configure alerts for:

- Daily spend exceeds threshold
- Monthly budget at risk
- Unusual usage patterns

---

## Distributed Tracing

### Understanding Traces

Traces show the full journey of a request:

```
User Request
     |
     v
API Gateway -----> Authentication
     |
     v
Agent Orchestrator
     |
     +---> Coder Agent
     |
     +---> Reviewer Agent
     |
     v
Sandbox Testing
     |
     v
Response
```

### Viewing Traces

1. Navigate to a specific request or operation
2. Click **View Trace**
3. See:
   - Each service/component involved
   - Time spent at each step
   - Any errors or slowdowns

---

## Alerting and Escalation

### Default Alert Rules

| Alert | Condition | Priority |
|-------|-----------|----------|
| High Error Rate | > 10% errors in 5 min | P2 |
| Slow Response | P95 > 10s | P3 |
| Service Down | Health check fails | P1 |
| Budget Exceeded | > 100% budget | P2 |
| Security Event | Injection detected | P1-P3 |

### Custom Alerts

Configure custom alerts:

1. Navigate to **Settings > Alerts**
2. Click **Create Alert**
3. Define:
   - Metric and threshold
   - Evaluation period
   - Notification channel
   - Severity

### Escalation Rules

Configure automatic escalation:

| Condition | Escalation |
|-----------|------------|
| P1 unacknowledged > 15 min | Page on-call |
| P2 unacknowledged > 1 hour | Notify manager |
| P1/P2 open > 4 hours | Executive notification |

---

## Reports

### Available Reports

| Report | Description | Frequency |
|--------|-------------|-----------|
| **Security Summary** | Vulnerabilities, alerts, trends | Weekly/Monthly |
| **Compliance Status** | Audit findings, retention | Monthly |
| **Agent Performance** | Task metrics, costs | Weekly |
| **Cost Analysis** | Usage breakdown, trends | Monthly |

### Generating Reports

Use the Chat Assistant:

| Request | Report Generated |
|---------|------------------|
| "Generate weekly security report" | Security summary |
| "Show compliance status" | Compliance report |
| "What were our costs last month?" | Cost analysis |

### Scheduling Reports

1. Navigate to **Reports > Scheduled**
2. Click **Create Schedule**
3. Configure:
   - Report type
   - Frequency
   - Recipients
   - Format (PDF/CSV)

---

## Integrations for Observability

### Supported Integrations

| Integration | Purpose |
|-------------|---------|
| **Slack** | Alert notifications |
| **PagerDuty** | Incident management |
| **Datadog** | Extended monitoring |
| **Splunk** | Log aggregation |

### Configuring Integrations

1. Navigate to **Settings > Integrations**
2. Select the integration
3. Follow the setup wizard
4. Test the connection

---

## Best Practices

### For Effective Monitoring

1. **Check dashboard daily**: Stay aware of platform status
2. **Configure notifications**: Don't miss critical alerts
3. **Review trends weekly**: Catch issues before they grow
4. **Set appropriate thresholds**: Avoid alert fatigue

### For Security Monitoring

1. **Acknowledge alerts promptly**: Show you're aware
2. **Investigate thoroughly**: Understand root cause
3. **Document resolutions**: Help future investigations
4. **Review audit logs**: Regular security audits

### For Cost Control

1. **Monitor daily spend**: Catch anomalies early
2. **Set budget alerts**: Get notified before overspend
3. **Review usage patterns**: Identify optimization opportunities
4. **Clean up unused resources**: Terminate idle environments

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Security & Compliance](./security-compliance.md) | Security alerts detail |
| [Agent System](./agent-system.md) | Agent metrics |
| [Deployment](./deployment.md) | Environment monitoring |
| [Troubleshooting](./troubleshooting.md) | Diagnosing issues |
