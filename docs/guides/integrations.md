# Integrations Guide

This guide explains how to connect Aura Platform with external tools and services to enhance your workflow.

---

## Integration Overview

Aura supports integrations with a variety of external tools through the MCP (Model Context Protocol) Gateway.

```
                    +------------------+
                    |  Aura Platform   |
                    +--------|---------+
                             |
                    +--------v---------+
                    |   MCP Gateway    |
                    +--------|---------+
                             |
     +------------+----------+----------+------------+
     |            |          |          |            |
     v            v          v          v            v
  +------+   +------+   +--------+   +------+   +--------+
  | Slack|   | Jira |   | GitHub |   |Pager |   |Datadog |
  |      |   |      |   |        |   | Duty |   |        |
  +------+   +------+   +--------+   +------+   +--------+
```

---

## Prerequisites

### Integration Mode Requirements

| Integration Type | Defense Mode | Enterprise Mode | Hybrid Mode |
|------------------|--------------|-----------------|-------------|
| Communication (Slack) | Not Available | Available | Configurable |
| Project Mgmt (Jira) | Not Available | Available | Configurable |
| Version Control (GitHub) | Not Available | Available | Configurable |
| Monitoring (Datadog) | Not Available | Available | Configurable |
| Security Tools | Not Available | Available | Configurable |

### Enabling Integrations

1. Ensure you are in **Enterprise** or **Hybrid** mode
2. Navigate to **Settings > MCP Configuration**
3. Enable **MCP Gateway**
4. Configure gateway credentials

---

## Communication Integrations

### Slack

Connect Slack for team notifications and alerts using incoming webhooks.

**What You Can Do**:

- Receive approval request notifications with rich formatting
- Get security alert notifications with priority-based color coding
- Receive deployment status updates
- Configure channel routing per event type

**Setup (Webhook Method)**:

1. Create an incoming webhook in your Slack workspace
2. Navigate to **Settings > Notifications**
3. Click **Add Channel** and select **Slack**
4. Enter the webhook URL
5. Configure channel and bot name
6. Save configuration

**Environment Variables**:

| Variable | Description |
|----------|-------------|
| `SLACK_WEBHOOK_URL` | Incoming webhook endpoint |
| `SLACK_CHANNEL` | Target channel (override) |
| `SLACK_BOT_NAME` | Display name for messages |

**Notifications**:

| Event | Default Channel |
|-------|-----------------|
| Approval Request | #aura-approvals |
| Security Alert (P1/P2) | #security-alerts |
| Deployment Complete | #deployments |

**Priority Colors**:

| Priority | Color |
|----------|-------|
| Critical | Red (#DC2626) |
| High | Orange (#EA580C) |
| Normal | Blue (#3B82F6) |
| Low | Gray (#6B7280) |

**Configuration Options**:

| Option | Description |
|--------|-------------|
| Webhook URL | Incoming webhook endpoint |
| Channel | Override channel (optional) |
| Bot Name | Display name for notifications |
| Quiet Hours | Suppress non-critical during off-hours |

**See also:** [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md#slack-integration) for detailed setup instructions.

---

### Microsoft Teams

Connect Microsoft Teams for enterprise communication using incoming webhooks.

**What You Can Do**:

- Receive approval notifications in MessageCard format
- Get security alerts with theme colors
- View deployment status with action buttons
- Quick access to Aura Dashboard via embedded links

**Setup (Webhook Method)**:

1. Create an incoming webhook connector in your Teams channel
2. Navigate to **Settings > Notifications**
3. Click **Add Channel** and select **Microsoft Teams**
4. Enter the webhook URL
5. Configure display settings
6. Save configuration

**Environment Variables**:

| Variable | Description |
|----------|-------------|
| `TEAMS_WEBHOOK_URL` | Incoming webhook endpoint |

**Message Features**:

| Feature | Description |
|---------|-------------|
| MessageCard Format | Rich formatting with sections |
| Theme Colors | Priority-based coloring |
| Facts | Key-value metadata display |
| Action Buttons | "View in Dashboard" quick link |

**See also:** [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md#microsoft-teams-integration) for detailed setup instructions.

---

## Project Management Integrations

### Jira

Connect Jira for ticket management and tracking.

**What You Can Do**:

- Auto-create tickets for vulnerabilities
- Link patches to existing tickets
- Update ticket status on patch deployment
- Track remediation progress

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Jira**
3. Enter your Jira URL (e.g., `https://yourcompany.atlassian.net`)
4. Configure API token authentication
5. Select default project and issue type
6. Save configuration

**Configuration Options**:

| Option | Description |
|--------|-------------|
| Default Project | Where new issues are created |
| Issue Type | Bug, Task, Security, etc. |
| Priority Mapping | How severity maps to Jira priority |
| Custom Fields | Additional fields to populate |

**Automation Rules**:

| Event | Jira Action |
|-------|-------------|
| Critical vulnerability found | Create P1 issue |
| Patch approved | Update linked ticket |
| Patch deployed | Close/resolve ticket |

### Azure DevOps

Connect Azure DevOps for work item tracking.

**What You Can Do**:

- Create work items for vulnerabilities
- Link patches to work items
- Update boards automatically

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Azure DevOps**
3. Enter your organization URL
4. Configure Personal Access Token
5. Select project and area path
6. Save configuration

---

## Version Control Integrations

### GitHub

Connect GitHub for repository integration.

**What You Can Do**:

- Receive webhooks on push/PR events
- Create pull requests for patches
- Add security findings to PRs
- Trigger scans on code changes

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **GitHub**
3. Click **Connect to GitHub**
4. Authorize Aura GitHub App
5. Select repositories to connect
6. Configure webhook settings
7. Save configuration

**Webhook Events**:

| Event | Aura Action |
|-------|-------------|
| Push to main | Trigger incremental scan |
| Pull request opened | Run security checks |
| Pull request merged | Update vulnerability status |

**PR Integration**:

| Feature | Description |
|---------|-------------|
| Security Comments | Add findings to PR discussion |
| Status Checks | Block merge on critical findings |
| Suggested Fixes | Auto-suggest patches in PR |

### GitLab

Connect GitLab for self-hosted or GitLab.com integration.

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **GitLab**
3. Enter your GitLab URL
4. Configure access token
5. Select projects
6. Save configuration

### Bitbucket

Connect Bitbucket for Atlassian ecosystem integration.

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Bitbucket**
3. Configure OAuth credentials
4. Select repositories
5. Save configuration

---

## Incident Management Integrations

### PagerDuty

Connect PagerDuty for incident response.

**What You Can Do**:

- Route security alerts to on-call
- Create incidents for critical findings
- Acknowledge/resolve from Aura

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **PagerDuty**
3. Enter your integration key
4. Configure routing rules
5. Save configuration

**Routing Configuration**:

| Alert Priority | PagerDuty Urgency |
|----------------|-------------------|
| P1 - Critical | High (page) |
| P2 - High | High (page) |
| P3 - Medium | Low (notify) |
| P4/P5 | Low (notify) |

### ServiceNow

Connect ServiceNow for enterprise ITSM.

**What You Can Do**:

- Create incidents for security events
- Create change requests for deployments
- Track remediation in CMDB

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **ServiceNow**
3. Enter your instance URL
4. Configure authentication
5. Map fields and categories
6. Save configuration

---

## Monitoring Integrations

### Datadog

Connect Datadog for enhanced observability.

**What You Can Do**:

- Send custom metrics to Datadog
- Correlate security events with APM
- Create dashboards combining data

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Datadog**
3. Enter your API key
4. Configure metric prefixes
5. Save configuration

**Metrics Sent**:

| Metric | Description |
|--------|-------------|
| `aura.vulnerabilities.count` | Open vulnerabilities by severity |
| `aura.patches.generated` | Patches created |
| `aura.approvals.pending` | Pending approvals |
| `aura.agents.active` | Running agents |

### Splunk

Connect Splunk for log aggregation.

**What You Can Do**:

- Forward audit logs to Splunk
- Correlate security events
- Build custom dashboards

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Splunk**
3. Configure HEC (HTTP Event Collector) endpoint
4. Enter HEC token
5. Configure event types to forward
6. Save configuration

---

## Security Tool Integrations

### Snyk

Connect Snyk for enhanced vulnerability scanning.

**What You Can Do**:

- Import Snyk findings into Aura
- Correlate findings with Aura analysis
- Track remediation across platforms

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Snyk**
3. Enter your Snyk API token
4. Select organization and projects
5. Configure sync settings
6. Save configuration

### CrowdStrike

Connect CrowdStrike for endpoint security correlation.

**What You Can Do**:

- Correlate code vulnerabilities with runtime threats
- Enrich security alerts with endpoint data
- Prioritize based on active exploitation

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **CrowdStrike**
3. Configure API credentials
4. Enable desired integrations
5. Save configuration

### Qualys

Connect Qualys for vulnerability management integration.

**What You Can Do**:

- Import infrastructure vulnerabilities
- Correlate code and infrastructure findings
- Unified vulnerability view

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Qualys**
3. Configure API credentials
4. Select assets to sync
5. Save configuration

---

## Infrastructure Integrations

### Terraform Cloud

Connect Terraform Cloud for IaC integration.

**What You Can Do**:

- Scan Terraform plans for security issues
- Block applies on critical findings
- Track infrastructure changes

**Setup**:

1. Navigate to **Settings > Integrations**
2. Click **Terraform Cloud**
3. Configure API token
4. Select workspaces
5. Enable run task integration
6. Save configuration

---

## Integration Hub

### Accessing the Hub

Navigate to **Settings > Integrations** to see all available integrations.

### Integration Status

| Status | Meaning |
|--------|---------|
| **Connected** | Integration active and working |
| **Disconnected** | Not configured |
| **Error** | Connection issue |
| **Pending** | Setup in progress |

### Testing Connections

1. Click on an integration
2. Click **Test Connection**
3. Review the test results
4. Troubleshoot any errors

---

## Agent-to-Agent (A2A) Protocol

### What is A2A?

A2A allows Aura to communicate with external AI agents using a standard protocol.

**Use Cases**:

- Connect specialized security agents
- Integrate custom analysis tools
- Extend platform capabilities

### Connecting External Agents

1. Navigate to **Agents > Registry**
2. Click **Connect External Agent**
3. Enter the A2A endpoint URL
4. Configure authentication
5. Test the connection
6. Enable the agent

### A2A Security

| Feature | Description |
|---------|-------------|
| Authentication | API key or OAuth |
| Authorization | Cedar policy engine |
| Encryption | TLS required |
| Rate Limiting | Configurable limits |

---

## Webhook Configuration

### Creating Webhooks

Send events from Aura to your systems.

1. Navigate to **Settings > Webhooks**
2. Click **Create Webhook**
3. Configure:
   - URL endpoint
   - Events to send
   - Authentication method
   - Retry policy

### Webhook Events

| Event | Payload |
|-------|---------|
| `vulnerability.created` | Vulnerability details |
| `patch.generated` | Patch information |
| `approval.requested` | Approval request |
| `approval.completed` | Approval decision |
| `deployment.completed` | Deployment result |

### Webhook Payload Example

```json
{
  "event": "vulnerability.created",
  "timestamp": "2025-12-16T12:00:00Z",
  "data": {
    "id": "vuln-123",
    "severity": "HIGH",
    "title": "SQL Injection detected",
    "file_path": "src/auth.py",
    "line_number": 42
  }
}
```

---

## Budget and Cost Control

### MCP Budget Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Monthly Budget | Maximum monthly spend | $500 |
| Daily Limit | Maximum daily spend | $50 |
| Per-Tool Limits | Individual tool limits | Configurable |

### Monitoring Costs

View MCP usage in **Settings > MCP Configuration**:

- Current month spend
- Budget remaining
- Per-tool breakdown
- Usage trends

---

## Best Practices

### For Enterprise Deployments

1. **Start with core integrations**: Slack, Jira, GitHub
2. **Configure notification channels**: Route to appropriate teams
3. **Set budget limits**: Prevent unexpected costs
4. **Test integrations**: Verify before production use
5. **Document configurations**: Maintain integration records

### For Hybrid Mode

1. **Allowlist essential tools only**: Minimize attack surface
2. **Enable per-tool HITL**: Review external calls
3. **Monitor usage**: Track which tools are used
4. **Regular audits**: Review integration permissions

### For Security

1. **Use least privilege**: Minimal permissions for integrations
2. **Rotate credentials**: Regular credential rotation
3. **Monitor access**: Track integration activity
4. **Review webhooks**: Verify webhook endpoints

---

## Troubleshooting

### Connection Failed

1. Verify credentials are correct
2. Check network connectivity
3. Ensure not in Defense Mode
4. Review firewall rules

### Notifications Not Received

1. Check channel configuration
2. Verify webhook is enabled
3. Test connection manually
4. Review integration logs

### Rate Limited

1. Check usage against limits
2. Review budget settings
3. Optimize integration usage
4. Consider upgrading limits

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md) | Slack, Teams, and notification channel setup |
| [Configuration](./configuration.md) | MCP settings |
| [Security & Compliance](./security-compliance.md) | Integration security |
| [Monitoring](./monitoring-observability.md) | Integration metrics |
| [Troubleshooting](./troubleshooting.md) | Integration issues |
