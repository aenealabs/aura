# Configuration Guide

This guide provides a comprehensive reference for all configurable settings in the Aura Platform.

---

## Accessing Settings

Navigate to **Settings** in the sidebar to access the configuration interface.

The Settings page is organized into tabs:

| Tab | Purpose |
|-----|---------|
| **Integration Mode** | Defense/Enterprise/Hybrid selection |
| **HITL Settings** | Human-in-the-loop approval configuration |
| **MCP Configuration** | External tool integration settings |
| **Security** | Log retention, isolation, compliance |
| **Compliance** | Compliance profile management |

---

## Integration Mode

### Available Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Defense** | Maximum security, no external dependencies | GovCloud, CMMC L3, classified |
| **Enterprise** | Full integrations enabled | Commercial enterprises |
| **Hybrid** | Selective integrations with controls | Balanced requirements |

### Defense Mode

Features when Defense Mode is enabled:

| Feature | Status |
|---------|--------|
| External network calls | Blocked |
| MCP Gateway | Disabled |
| External tools | Unavailable |
| Air-gap deployment | Supported |
| CMMC L3 compliant | Yes |
| FedRAMP High compatible | Yes |

### Enterprise Mode

Features when Enterprise Mode is enabled:

| Feature | Status |
|---------|--------|
| AgentCore Gateway | Enabled |
| External tools | Available |
| Slack/Jira/GitHub | Supported |
| Automated notifications | Enabled |
| Usage-based MCP costs | Active |

### Hybrid Mode

Features when Hybrid Mode is enabled:

| Feature | Status |
|---------|--------|
| Tool allowlist | Configurable |
| Per-tool HITL approval | Available |
| Budget controls | Per-integration |
| Audit trail | Comprehensive |
| Gradual rollout | Supported |

### Changing Modes

1. Navigate to **Settings > Integration Mode**
2. Select the desired mode card
3. Review the features and restrictions
4. Click **Select [Mode Name]**

**Warning**: Switching to Defense Mode disables MCP Gateway and all external integrations.

---

## HITL Settings

### Approval Requirements

| Setting | Description | Default |
|---------|-------------|---------|
| **Require approval for patches** | All patches need human approval | Yes |
| **Require approval for deployments** | All deployments need approval | Yes |
| **Auto-approve minor patches** | Low-severity auto-approved after testing | No |

### Approval Workflow

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| **Approval timeout (hours)** | Time before request expires | 1-168 | 24 |
| **Minimum approvers** | Required approvals for critical | 1-5 | 1 |

### Notifications

| Setting | Description | Default |
|---------|-------------|---------|
| **Notify on approval request** | Send notification for new approvals | Yes |
| **Notify on approval timeout** | Reminder before expiration | Yes |

### Guardrails (Non-Configurable)

These operations **always** require human approval regardless of settings:

| Operation | Description |
|-----------|-------------|
| `production_deployment` | Deploying to production |
| `credential_modification` | Changing API keys, secrets |
| `access_control_change` | Modifying IAM, RBAC |
| `database_migration` | Schema changes |
| `infrastructure_change` | Cloud resource modifications |

---

## MCP Configuration

### Gateway Settings

| Setting | Description | Required |
|---------|-------------|----------|
| **Enable MCP Gateway** | Turn on/off external integrations | No |
| **Gateway URL** | AgentCore Gateway endpoint | When enabled |
| **API Key** | Authentication key | When enabled |

### Budget Controls

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| **Monthly budget (USD)** | Maximum monthly MCP spend | 0-10,000 | 500 |
| **Daily limit (USD)** | Maximum daily MCP spend | 0-1,000 | 50 |

### External Tools

Available tools (when MCP is enabled):

| Tool | Category | Description |
|------|----------|-------------|
| **Slack** | Communication | Team notifications |
| **Jira** | Project Management | Ticket creation/updates |
| **GitHub** | Version Control | PR integration |
| **PagerDuty** | Incident Management | Alert routing |
| **Datadog** | Monitoring | Metrics integration |
| **ServiceNow** | ITSM | Change management |
| **Splunk** | Logging | Log aggregation |

### Enabling/Disabling Tools

1. Navigate to **Settings > MCP Configuration**
2. Scroll to **External Tool Integrations**
3. Click on a tool card to toggle
4. Changes are saved automatically

---

## Security Settings

### Log Retention

| Option | Days | Compliance Level |
|--------|------|------------------|
| 30 days | 30 | Below CMMC minimum |
| 60 days | 60 | Below CMMC minimum |
| **90 days** | 90 | CMMC L2 compliant |
| 180 days | 180 | Enhanced compliance |
| **365 days** | 365 | GovCloud/FedRAMP |

**Selecting Retention Period**:

1. Navigate to **Settings > Security**
2. Click on the desired retention option
3. Review compliance status indicator
4. Changes trigger log group updates

### Sandbox Isolation Level

| Level | Description | Use Case |
|-------|-------------|----------|
| **Container** | Isolated container | Quick tests |
| **VPC** | Dedicated VPC | Standard testing |
| **Full** | Complete isolation | Compliance testing |

### Security Status Indicators

The Security tab shows status for:

| Indicator | What It Shows |
|-----------|---------------|
| Air-Gap Compatible | External network blocked |
| External Network | Sandbox isolation |
| Audit Logging | All actions logged |
| Log Retention | Days configured |

---

## Compliance Settings

### Compliance Profiles

| Profile | Log Retention | KMS Mode | Integration Mode |
|---------|---------------|----------|------------------|
| **Commercial** | 30 days | AWS Managed | Enterprise |
| **CMMC Level 1** | 30 days | AWS Managed | Hybrid |
| **CMMC Level 2** | 90 days | Customer Managed | Hybrid |
| **GovCloud** | 365 days | Customer Managed | Defense |

### Applying a Profile

1. Navigate to **Settings > Compliance**
2. Select the target profile
3. Review settings that will be applied
4. Click **Apply Profile**

### Profile Settings Applied

When you apply a profile, these settings are updated:

| Setting | Where Applied |
|---------|---------------|
| Log retention | CloudWatch log groups |
| KMS mode | Encryption configuration |
| Integration mode | Platform integration settings |
| Audit level | Security audit service |

---

## Autonomy Policy Settings

### Autonomy Levels

| Level | Description | HITL Required |
|-------|-------------|---------------|
| **FULL_HITL** | All operations require approval | Always |
| **CRITICAL_HITL** | Only HIGH/CRITICAL severity | HIGH, CRITICAL |
| **AUDIT_ONLY** | Log decisions, no blocking | Never |
| **FULL_AUTONOMOUS** | Fully automated | Never |

### Policy Presets

| Preset | Default Level | Target Industry |
|--------|---------------|-----------------|
| `defense_contractor` | FULL_HITL | GovCloud, CMMC L3+ |
| `financial_services` | FULL_HITL | SOX, PCI-DSS |
| `healthcare` | FULL_HITL | HIPAA |
| `fintech_startup` | CRITICAL_HITL | Growth-stage |
| `enterprise_standard` | CRITICAL_HITL | Fortune 500 |
| `internal_tools` | FULL_AUTONOMOUS | Internal dev |
| `fully_autonomous` | FULL_AUTONOMOUS | Dev/test |

### Override Hierarchy

Policy resolution priority (highest to lowest):

1. **Guardrails** - Always enforced
2. **Repository Overrides** - Per-repo settings
3. **Operation Overrides** - Per-operation settings
4. **Severity Overrides** - Per-severity settings
5. **Default Level** - Policy default

---

## Orchestrator Settings

### Deployment Modes

| Mode | Cost | Latency | Best For |
|------|------|---------|----------|
| **On-Demand** | $0/mo base | Higher | Low volume |
| **Warm Pool** | ~$28/mo | Low | Consistent use |
| **Hybrid** | ~$28/mo + burst | Low | Variable load |

### Switching Deployment Mode

1. Navigate to **Settings > Orchestrator**
2. Select the desired mode
3. Review cost and latency implications
4. Click **Apply**

**Note**: 5-minute cooldown between mode changes.

---

## Environment Settings

### Default Quotas

| Limit | Default | Configurable |
|-------|---------|--------------|
| Concurrent environments | 3 | By admin |
| Monthly budget | $500 | By admin |
| Daily budget | $50 | By admin |

### Template Configuration

Default templates available:

| Template | TTL | Cost/Day |
|----------|-----|----------|
| Quick Test | 4 hours | $0.10 |
| Python FastAPI | 24 hours | $0.50 |
| React Frontend | 24 hours | $0.30 |
| Full Stack | 24 hours | $1.20 |
| Data Pipeline | 7 days | $0.80 |

---

## Notification Settings

### Channels

| Channel | Configuration |
|---------|---------------|
| **Dashboard** | Always enabled |
| **Email** | Configure recipients |
| **Slack** | Requires Enterprise mode |
| **SNS** | Configure topic ARN |

### Notification Types

| Type | Default Channel |
|------|-----------------|
| Approval Request | Email + Dashboard |
| Approval Timeout Warning | Email |
| Security Alert (P1/P2) | All channels |
| Security Alert (P3+) | Dashboard |
| Deployment Complete | Dashboard |
| Environment Ready | Dashboard |

---

## Configuration Best Practices

### For Defense/Government

```
Integration Mode: Defense
Autonomy Level: FULL_HITL (or defense_contractor preset)
Log Retention: 365 days
Sandbox Isolation: Full
External Network: Blocked
Audit Logging: All actions
```

### For Commercial Enterprise

```
Integration Mode: Enterprise
Autonomy Level: CRITICAL_HITL (or enterprise_standard preset)
Log Retention: 90 days
Sandbox Isolation: VPC
MCP Gateway: Enabled
Budget: Monthly $500, Daily $50
External Tools: Slack, Jira, GitHub
```

### For Development Teams

```
Integration Mode: Hybrid or Enterprise
Autonomy Level: AUDIT_ONLY or FULL_AUTONOMOUS
Log Retention: 30-60 days
Sandbox Isolation: Container
Auto-approve minor patches: Enabled
```

---

## Configuration via API

### Get Current Settings

```bash
curl -X GET https://api.aenealabs.com/api/v1/settings \
  -H "Authorization: Bearer $TOKEN"
```

### Update Integration Mode

```bash
curl -X PUT https://api.aenealabs.com/api/v1/settings/integration-mode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "hybrid"}'
```

### Update HITL Settings

```bash
curl -X PUT https://api.aenealabs.com/api/v1/settings/hitl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requireApprovalForPatches": true,
    "approvalTimeoutHours": 48,
    "minApprovers": 2
  }'
```

---

## Troubleshooting Configuration

### Settings Not Applying

1. Check for validation errors in the response
2. Ensure you have admin permissions
3. Verify no conflicting guardrails

### MCP Connection Failed

1. Verify Gateway URL is correct
2. Check API key is valid
3. Test connection using the **Test Connection** button
4. Ensure not in Defense Mode

### Log Retention Changes Not Visible

- Log retention changes apply to new logs
- Existing logs follow their original policy
- Changes may take up to 24 hours to propagate

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Security & Compliance](./security-compliance.md) | HITL and compliance details |
| [Integrations](./integrations.md) | External tool setup |
| [API Reference](./api-reference.md) | Settings API |
| [Troubleshooting](./troubleshooting.md) | Configuration issues |
