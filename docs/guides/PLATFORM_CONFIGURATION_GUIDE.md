# Aura Platform Configuration Guide

**Version:** 1.0
**Last Updated:** December 2025
**Audience:** Platform Administrators, Security Engineers, Team Leads

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Settings Page Overview](#settings-page-overview)
3. [Integration Mode Selection](#integration-mode-selection)
4. [Agent Registry and Management](#agent-registry-and-management)
5. [Autonomy Policies Configuration](#autonomy-policies-configuration)
6. [Orchestrator Mode Settings](#orchestrator-mode-settings)
7. [Agent Configuration](#agent-configuration)
8. [Environment Administration](#environment-administration)
9. [Notification Settings](#notification-settings)
10. [Sandbox Isolation Configuration](#sandbox-isolation-configuration)
11. [Rate Limiting Settings](#rate-limiting-settings)
12. [Security Alert Configuration](#security-alert-configuration)
13. [Best Practices](#best-practices)
14. [Troubleshooting](#troubleshooting)
15. [Glossary](#glossary)

---

## Getting Started

### Who Should Use This Guide

This guide is intended for:

- **Platform Administrators** who configure organization-wide settings
- **Security Engineers** who manage compliance and security policies
- **Team Leads** who configure team-specific settings and quotas

### Prerequisites

Before configuring the platform, ensure you have:

- Administrator or Security Engineer role assigned to your account
- Completed the initial platform setup (see [Getting Started Guide](./getting-started.md))
- Understanding of your organization's compliance requirements

### Accessing the Settings Page

1. Sign in to the Aura Platform using your organization credentials
2. Click **Settings** in the left sidebar navigation
3. You will see the main Settings hub with multiple configuration tabs

**Screenshot Placeholder:** *Main Settings page showing the sidebar navigation with Settings highlighted and the tabbed interface displaying Integration Mode, HITL Settings, MCP Configuration, and other tabs.*

### Configuration Workflow

For new deployments, we recommend configuring settings in this order:

```
1. Integration Mode     -->  Choose Defense, Enterprise, or Hybrid
       |
       v
2. Autonomy Policies    -->  Select policy preset or customize
       |
       v
3. HITL Settings        -->  Configure approval requirements
       |
       v
4. Security Settings    -->  Set log retention and compliance profile
       |
       v
5. Notifications        -->  Configure alert channels
       |
       v
6. Integrations         -->  Connect external tools (if Enterprise mode)
```

---

## Settings Page Overview

The Settings page is your central hub for configuring the Aura Platform. It is organized into logical sections accessible via tabs.

### Main Settings Tabs

| Tab | Purpose | Key Settings |
|-----|---------|--------------|
| **Integration Mode** | Platform connectivity mode | Defense, Enterprise, Hybrid |
| **HITL Settings** | Human approval workflows | Approval requirements, timeouts |
| **MCP Configuration** | External tool gateway | Budget controls, tool connections |
| **Security** | Security and compliance | Log retention, isolation levels |
| **Compliance** | Compliance profiles | CMMC, SOX, FedRAMP presets |

### Additional Configuration Areas

| Area | Purpose | Access Path |
|------|---------|-------------|
| **Agent Registry** | Manage autonomous agents | Sidebar > Agents |
| **Autonomy Policies** | Configure HITL requirements | Settings > Autonomy |
| **Orchestrator Mode** | Agent deployment strategy | Settings > Orchestrator |
| **Environments** | Test environment management | Settings > Environments |
| **Notifications** | Alert routing | Settings > Notifications |
| **Rate Limiting** | API usage controls | Settings > Rate Limits |
| **Security Alerts** | Threat detection thresholds | Settings > Security Alerts |

**Screenshot Placeholder:** *Settings page with all tabs visible, showing the organized layout with clear section headers and status indicators.*

---

## Integration Mode Selection

Integration Mode determines how the Aura Platform connects with external services and tools. This is one of the most important configuration decisions.

### Understanding the Three Modes

#### Defense Mode

**Best for:** Government contractors, classified environments, air-gapped deployments

Defense Mode prioritizes security over convenience. External network access is blocked, and all processing happens within your isolated environment.

| Feature | Status |
|---------|--------|
| External network calls | Blocked |
| MCP Gateway | Disabled |
| External tools (Slack, Jira) | Unavailable |
| Air-gap deployment | Fully supported |
| CMMC Level 3 compliant | Yes |
| FedRAMP High compatible | Yes |

**When to Choose Defense Mode:**

- Your organization handles classified or sensitive government data
- You operate in an air-gapped network environment
- CMMC Level 3 or FedRAMP High compliance is required
- External integrations are prohibited by policy

#### Enterprise Mode

**Best for:** Commercial enterprises, development teams, organizations needing full integrations

Enterprise Mode enables all platform features including external tool integrations and the MCP Gateway for extended capabilities.

| Feature | Status |
|---------|--------|
| MCP Gateway | Enabled |
| External tools | All available |
| Slack/Jira/GitHub | Fully supported |
| Automated notifications | Enabled |
| Usage-based costs | Active |

**When to Choose Enterprise Mode:**

- You need integrations with Slack, Jira, GitHub, or other tools
- Your team benefits from automated notifications
- No regulatory restrictions on external connections
- You want maximum platform capabilities

#### Hybrid Mode

**Best for:** Organizations with mixed requirements, gradual adoption scenarios

Hybrid Mode provides selective control over which integrations are enabled, with per-tool approval options.

| Feature | Status |
|---------|--------|
| Tool allowlist | Configurable |
| Per-tool HITL approval | Available |
| Budget controls | Per-integration |
| Audit trail | Comprehensive |
| Gradual rollout | Supported |

**When to Choose Hybrid Mode:**

- You need some external integrations but not all
- Different teams have different integration requirements
- You want granular control over each tool connection
- You are transitioning from Defense to Enterprise mode

### How to Change Integration Mode

1. Navigate to **Settings > Integration Mode**
2. Review the three mode cards showing features and restrictions
3. Click the mode card you want to select
4. Read the confirmation dialog explaining what will change
5. Click **Select [Mode Name]** to confirm

**Screenshot Placeholder:** *Integration Mode selection screen showing three cards (Defense, Enterprise, Hybrid) with feature lists and a "Current" badge on the active mode.*

**Warning:** Switching to Defense Mode will immediately disable the MCP Gateway and disconnect all external integrations. Ensure your team is prepared for this change.

### Mode Comparison Matrix

| Capability | Defense | Enterprise | Hybrid |
|------------|---------|------------|--------|
| Vulnerability scanning | Yes | Yes | Yes |
| Patch generation | Yes | Yes | Yes |
| Sandbox testing | Yes | Yes | Yes |
| Slack notifications | No | Yes | Configurable |
| Jira ticket creation | No | Yes | Configurable |
| GitHub PR integration | No | Yes | Configurable |
| PagerDuty alerts | No | Yes | Configurable |
| MCP Gateway access | No | Yes | Configurable |
| Air-gap support | Yes | No | Partial |

---

## Agent Registry and Management

The Agent Registry provides visibility into all autonomous agents operating in your environment and allows you to manage their lifecycle.

### Accessing the Agent Registry

1. Click **Agents** in the left sidebar navigation
2. The Agent Registry dashboard displays all registered agents

**Screenshot Placeholder:** *Agent Registry dashboard showing a list of agents with columns for Name, Type, Status, Health, Last Active, and Actions.*

### Understanding Agent Types

| Agent Type | Purpose | Role |
|------------|---------|------|
| **Coder** | Generates code patches | Analyzes vulnerabilities and creates fixes |
| **Reviewer** | Reviews patches | Validates security and quality |
| **Validator** | Tests in sandbox | Executes patches in isolated environments |
| **Orchestrator** | Coordinates workflow | Manages agent collaboration |

### Viewing Agent Details

Click on any agent row to view detailed information:

- **General Information:** Agent ID, type, version, creation date
- **Health Metrics:** CPU usage, memory, response time, error rate
- **Task History:** Recent tasks with status, duration, and outcomes
- **Configuration:** Current settings and capability flags

**Screenshot Placeholder:** *Agent detail view showing health metrics as gauges, a task history timeline, and configuration panels.*

### Agent Health Status

| Status | Indicator | Meaning |
|--------|-----------|---------|
| **Healthy** | Green circle | Operating normally |
| **Degraded** | Yellow circle | Performance issues detected |
| **Unhealthy** | Red circle | Requires attention |
| **Offline** | Gray circle | Not running |

### Managing Agents

#### Starting an Agent

1. Select the agent in the registry
2. Click the **Start** button in the Actions column
3. Wait for the status to change to "Healthy"

#### Pausing an Agent

1. Select the running agent
2. Click **Pause** to temporarily stop processing
3. The agent will finish current tasks before pausing

#### Restarting an Agent

1. Select the agent (any status)
2. Click **Restart** to stop and start the agent
3. Use this to apply configuration changes or recover from errors

#### Deploying a New Agent

1. Click **Deploy New Agent** in the top right corner
2. Select the agent type from the dropdown
3. Configure initial settings (see Agent Configuration section)
4. Click **Deploy** to create the agent

**Screenshot Placeholder:** *Deploy New Agent modal with agent type dropdown, configuration fields, and Deploy/Cancel buttons.*

### Monitoring Agent Performance

The Agent Registry includes real-time metrics:

| Metric | Description | Healthy Range |
|--------|-------------|---------------|
| **Tasks Completed** | Total tasks processed | Increasing over time |
| **Success Rate** | Percentage of successful tasks | Above 95% |
| **Average Duration** | Mean task completion time | Below threshold |
| **Queue Depth** | Pending tasks waiting | Below 10 |
| **Error Count** | Tasks that failed | Below 5% of total |

---

## Autonomy Policies Configuration

Autonomy Policies determine when human approval is required for agent actions. This is a critical security configuration that balances automation speed with human oversight.

### Accessing Autonomy Policies

1. Navigate to **Settings > Autonomy** tab
2. The Autonomy Policies panel displays your current configuration

### Understanding Autonomy Levels

| Level | Description | When HITL Required |
|-------|-------------|-------------------|
| **Full HITL** | All operations require approval | Always |
| **Critical HITL** | High and Critical severity require approval | High, Critical only |
| **Audit Only** | Log all decisions but do not block | Never (logged) |
| **Full Autonomous** | Fully automated operation | Never |

### Policy Presets

The platform includes seven pre-configured policy presets. Select the one that best matches your industry and compliance requirements.

| Preset | Default Level | HITL Enabled | Target Industry |
|--------|---------------|--------------|-----------------|
| **Maximum Security** | Full HITL | Yes | GovCloud, CMMC L3+, classified |
| **Defense Standard** | Full HITL | Yes | Defense contractors |
| **Balanced** | Critical HITL | Yes | Financial services, healthcare |
| **Accelerated** | Critical HITL | Yes | Enterprise standard |
| **Full Autonomous** | Full Autonomous | No | Commercial dev/test |
| **Custom** | Configurable | Configurable | Specific requirements |
| **Audit Only** | Audit Only | No | Logging without blocking |

### Selecting a Policy Preset

1. Navigate to **Settings > Autonomy**
2. Review the preset cards showing their configurations
3. Click on a preset card to see detailed settings
4. Click **Apply Preset** to activate

**Screenshot Placeholder:** *Autonomy Policies tab showing seven preset cards in a grid layout, each with a name, description, and "Current" badge on the active preset.*

### Customizing Your Policy

If the presets do not match your requirements, use the Custom preset to create your own configuration.

#### Enabling/Disabling HITL

Toggle the master HITL switch to enable or disable human approval requirements:

1. Navigate to **Settings > Autonomy**
2. Find the **HITL Enabled** toggle at the top
3. Click to toggle on (approval required) or off (autonomous)

**Warning:** Disabling HITL removes human oversight from agent operations. Only do this if your compliance requirements permit fully autonomous operation.

#### Setting Default Autonomy Level

1. In the Autonomy panel, locate **Default Autonomy Level**
2. Select from the dropdown: Full HITL, Critical HITL, Audit Only, Full Autonomous
3. This applies to all operations unless overridden

#### Configuring Severity Overrides

You can set different autonomy levels based on finding severity:

1. Expand the **Severity Overrides** section
2. For each severity level (Critical, High, Medium, Low, Info), select the autonomy level
3. Click **Save Overrides**

Example configuration for a fintech company:

| Severity | Autonomy Level |
|----------|----------------|
| Critical | Full HITL |
| High | Full HITL |
| Medium | Critical HITL |
| Low | Audit Only |
| Info | Full Autonomous |

#### Adding Repository Overrides

Override policies for specific repositories:

1. Expand the **Repository Overrides** section
2. Click **Add Repository Override**
3. Enter the repository path or pattern
4. Select the autonomy level for that repository
5. Click **Save**

**Screenshot Placeholder:** *Severity Overrides section showing dropdown selectors for each severity level with color-coded labels.*

### Guardrails (Non-Configurable)

Regardless of your policy settings, these operations **always** require human approval:

| Operation | Description | Why It Cannot Be Automated |
|-----------|-------------|---------------------------|
| Production deployment | Deploying to production | Risk of service disruption |
| Credential modification | Changing API keys, secrets | Security-critical operation |
| Access control change | Modifying IAM, RBAC | Permission escalation risk |
| Database migration | Schema changes | Data integrity risk |
| Infrastructure change | Cloud resource modifications | Cost and stability impact |

These guardrails are enforced at the platform level and cannot be disabled.

---

## Orchestrator Mode Settings

The Orchestrator Mode determines how agent jobs are processed. Choose the mode that best balances cost, latency, and your workload patterns.

### Accessing Orchestrator Settings

1. Navigate to **Settings > Orchestrator** tab
2. The Orchestrator Mode panel displays current configuration and cost estimates

### Understanding Deployment Modes

#### On-Demand Mode

**Monthly Cost:** $0 base (pay per job)
**Best For:** Low-volume workloads, development environments

Jobs are created when needed and terminated after completion. You only pay for actual usage.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | $0.00 |
| Per-Job Cost | Approximately $0.15 |
| Cold Start Latency | 30 seconds |
| Best For | Less than 100 jobs/day |

#### Warm Pool Mode

**Monthly Cost:** Approximately $28
**Best For:** High-volume workloads, production environments

Always-on replicas process jobs instantly with no cold start delay.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | Approximately $28.00 |
| Per-Job Cost | Included in base |
| Cold Start Latency | 0 seconds |
| Replicas | 1-10 configurable |
| Best For | More than 500 jobs/day |

#### Hybrid Mode

**Monthly Cost:** Approximately $28 + burst costs
**Best For:** Variable workloads with occasional spikes

Combines warm pool for baseline traffic with burst capacity for peaks.

| Attribute | Value |
|-----------|-------|
| Base Monthly Cost | Approximately $28.00 |
| Burst Cost | Approximately $0.15/job |
| Cold Start Latency | 0 seconds (warm), 30 seconds (burst) |
| Queue Threshold | Configurable |
| Best For | Variable traffic patterns |

### Selecting a Deployment Mode

1. Navigate to **Settings > Orchestrator**
2. Review the three mode cards with cost estimates
3. Click **Select** on your chosen mode
4. Confirm the mode change in the dialog

**Screenshot Placeholder:** *Orchestrator Mode selection showing three cards with On-Demand, Warm Pool, and Hybrid options, each displaying cost estimates and recommended use cases.*

### Configuring Warm Pool Settings

When using Warm Pool or Hybrid mode:

1. **Replica Count (1-10):** Number of always-on processing instances
   - Start with 1 and increase based on queue depth
   - Each replica adds approximately $28/month

2. **Queue Depth Threshold (Hybrid only):** When to spawn burst jobs
   - Default: 5 pending jobs
   - Lower = more responsive, higher = more cost-effective

3. **Scale-Up Cooldown:** Minimum time between scaling events
   - Default: 60 seconds
   - Prevents rapid scaling fluctuations

### Cost Estimation

The Orchestrator panel shows real-time cost estimates based on your settings:

| Your Configuration | Estimated Monthly Cost |
|-------------------|----------------------|
| On-Demand, 50 jobs/day | $225 |
| Warm Pool, 1 replica | $28 |
| Warm Pool, 3 replicas | $84 |
| Hybrid, 1 replica + burst | $28 + burst costs |

**Note:** Warm Pool becomes more cost-effective than On-Demand at approximately 6 jobs per day.

### Mode Change Cooldown

A 5-minute cooldown prevents rapid mode switching that could cause instability:

- After changing modes, wait 5 minutes before changing again
- The **Status** panel shows remaining cooldown time
- Administrators can bypass cooldown in emergencies using the **Force** option

---

## Agent Configuration

The Agent Configuration modal allows you to fine-tune individual agent behavior, resource limits, and capabilities.

### Accessing Agent Configuration

1. Navigate to **Agents** in the sidebar
2. Click on an agent row to open the detail view
3. Click **Configure** to open the configuration modal

**Screenshot Placeholder:** *Agent Configuration modal with tabs for General, Resources, Capabilities, and Rate Limits.*

### General Settings

| Setting | Description | Default | Range |
|---------|-------------|---------|-------|
| **Max Concurrent Tasks** | Maximum tasks this agent can process simultaneously | 5 | 1-20 |
| **Task Timeout (minutes)** | Maximum time for a single task | 30 | 5-120 |
| **Retry Count** | Number of retry attempts on failure | 3 | 0-10 |
| **Retry Delay (seconds)** | Wait time between retries | 30 | 10-300 |

**Recommendations:**

- For Coder agents handling complex patches, increase timeout to 60 minutes
- For Validator agents running extensive tests, set timeout to 90 minutes
- Keep retry count at 3 for transient failures; set to 0 for deterministic failures

### Resource Allocation

| Setting | Description | Default | Range |
|---------|-------------|---------|-------|
| **CPU Allocation** | CPU cores assigned to the agent | 1.0 | 0.5-4.0 |
| **Memory (GB)** | RAM allocated to the agent | 2 | 1-16 |
| **Max Tokens** | LLM token limit per request | 4000 | 1000-32000 |
| **Token Budget (daily)** | Maximum tokens per day | 100000 | 10000-1000000 |

**Recommendations:**

- Coder agents benefit from higher memory (4GB+) for large codebases
- Reviewer agents can use default settings for most workloads
- Increase token limits for agents processing large files

### Capability Toggles

Enable or disable specific agent capabilities:

| Capability | Description | Default |
|------------|-------------|---------|
| **Code Analysis** | Analyze source code for vulnerabilities | Enabled |
| **Patch Generation** | Create code patches | Enabled (Coder only) |
| **Security Review** | Review patches for security issues | Enabled (Reviewer only) |
| **Sandbox Execution** | Execute code in sandbox | Enabled (Validator only) |
| **External API Access** | Call external APIs (requires Enterprise mode) | Disabled |
| **Database Access** | Query connected databases | Disabled |

### Rate Limits

Configure per-agent rate limits to prevent resource exhaustion:

| Setting | Description | Default |
|---------|-------------|---------|
| **Requests per Minute** | Maximum API calls per minute | 60 |
| **Requests per Hour** | Maximum API calls per hour | 1000 |
| **Burst Limit** | Maximum concurrent requests | 10 |

### Saving Configuration

1. Make your changes across the configuration tabs
2. Click **Save Configuration** to apply changes
3. Changes take effect immediately for new tasks
4. In-progress tasks continue with previous configuration

---

## Environment Administration

Environment Administration settings control how test environments (sandboxes) are provisioned and managed.

### Accessing Environment Settings

1. Navigate to **Settings > Environments** tab
2. The Environment Administration panel displays templates and quotas

### Managing Environment Templates

Environment templates define pre-configured sandbox configurations.

#### Viewing Templates

The template list shows all available configurations:

| Column | Description |
|--------|-------------|
| **Name** | Template identifier |
| **Description** | What the template provides |
| **Default TTL** | How long environments last |
| **Cost/Day** | Estimated daily cost |
| **Isolation Level** | Security isolation type |

**Screenshot Placeholder:** *Environment Templates table showing Quick Test, Python FastAPI, React Frontend, Full Stack, and Data Pipeline templates with their configurations.*

#### Creating a Template

1. Click **Create Template** in the templates section
2. Fill in the template details:
   - **Name:** Unique identifier (e.g., "java-microservices")
   - **Description:** What the template provides
   - **Base Image:** Container or VM image to use
   - **Default TTL:** Time-to-live in hours (4-168)
   - **Isolation Level:** Container, VPC, or Account
   - **Resource Limits:** CPU, memory, storage
3. Click **Create** to save the template

#### Editing a Template

1. Click the edit icon on a template row
2. Modify the desired settings
3. Click **Save Changes**

**Note:** Changes to templates do not affect existing environments. Only new environments use the updated configuration.

#### Deleting a Template

1. Click the delete icon on a template row
2. Confirm deletion in the dialog
3. Existing environments using this template continue to operate

### Configuring User Quotas

User quotas prevent any single user from consuming excessive resources.

| Setting | Description | Default |
|---------|-------------|---------|
| **Concurrent Environment Limit** | Max environments per user | 3 |
| **Monthly Budget (USD)** | Maximum spending per user | $500 |
| **Daily Budget (USD)** | Maximum daily spending | $50 |

#### Setting Quotas

1. Navigate to **Settings > Environments > User Quotas**
2. Adjust the slider or enter a value for each quota
3. Click **Save Quotas**

#### Quota Overrides

Administrators can grant quota exceptions for specific users:

1. Click **Manage Overrides** in the quotas section
2. Enter the user's email address
3. Set their custom quota values
4. Click **Add Override**

### Default Environment Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Default TTL (hours)** | Standard environment lifetime | 24 |
| **Default Isolation** | Default isolation level | Container |
| **Auto-Terminate** | Automatically stop idle environments | Enabled |
| **Idle Timeout (minutes)** | Time before auto-termination | 60 |

### Auto-Terminate Configuration

Auto-terminate helps control costs by stopping unused environments:

1. Enable/disable with the **Auto-Terminate** toggle
2. Set **Idle Timeout** to define inactivity period
3. Optionally exclude specific templates from auto-termination

---

## Notification Settings

Configure how and where the platform sends alerts and notifications. Aura supports six notification channels: Email (SES), SNS, Slack, Microsoft Teams, Generic Webhooks, and PagerDuty.

### Accessing Notification Settings

1. Navigate to **Settings > Notifications** tab
2. The Notifications panel shows configured channels and routing rules

**See also:** [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md) for detailed setup instructions for each channel.

### Notification Channels

#### Dashboard Notifications

Always enabled. Notifications appear in the platform's notification center.

- Click the bell icon in the top navigation to view
- Notifications are retained for 30 days

#### Email Notifications

Configure email recipients for notifications:

1. Enable the **Email** toggle
2. Add recipient email addresses
3. Choose whether to use digest mode (batched) or immediate delivery

| Setting | Options |
|---------|---------|
| **Delivery Mode** | Immediate, Hourly Digest, Daily Digest |
| **Recipients** | Add multiple email addresses |
| **Reply-To** | Address for replies |

#### Slack Notifications

**Requires:** Enterprise or Hybrid mode

Aura uses Slack incoming webhooks for reliable notification delivery with rich message formatting.

1. Create a Slack incoming webhook (see [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md#slack-integration))
2. Enable the **Slack** toggle
3. Enter your webhook URL
4. Configure the target channel and bot name
5. Optionally enable threading for related notifications

| Setting | Description |
|---------|-------------|
| **Webhook URL** | Slack incoming webhook endpoint |
| **Channel** | Override channel (optional) |
| **Bot Name** | Display name for notifications |
| **Icon Emoji** | Emoji for bot avatar |

**Message Formatting:**
- Rich attachments with priority-based color coding
- Critical alerts: Red (#DC2626)
- High priority: Orange (#EA580C)
- Normal priority: Blue (#3B82F6)
- Low priority: Gray (#6B7280)

#### Microsoft Teams Notifications

**Requires:** Enterprise or Hybrid mode

Aura uses Teams incoming webhooks to deliver notifications in MessageCard format.

1. Create a Teams incoming webhook connector (see [Notification Integration Guide](./NOTIFICATION_INTEGRATION_GUIDE.md#microsoft-teams-integration))
2. Enable the **Teams** toggle
3. Enter your webhook URL
4. Configure display settings

| Setting | Description |
|---------|-------------|
| **Webhook URL** | Teams incoming webhook endpoint |
| **Channel Name** | Display label for the channel |

**Message Features:**
- MessageCard format with sections and facts
- Theme colors matching notification priority
- "View in Dashboard" action button for quick access
- Source and timestamp metadata

#### SNS Notifications

For AWS-based automation and custom integrations:

1. Enable the **SNS** toggle
2. Enter the SNS Topic ARN
3. Ensure the platform has publish permissions to the topic

#### Webhook Notifications

Send notifications to custom endpoints:

1. Enable the **Webhook** toggle
2. Enter the webhook URL (HTTPS required)
3. Configure authentication (API key, Bearer token, or none)
4. Set retry behavior for failed deliveries

#### PagerDuty Integration

**Requires:** Enterprise or Hybrid mode with PagerDuty integration enabled

1. Enable the **PagerDuty** toggle
2. Enter your PagerDuty Integration Key
3. Map severity levels to PagerDuty urgency

### Event Routing

Configure which events go to which channels:

**Screenshot Placeholder:** *Event Routing matrix showing event types (rows) and channels (columns) with checkboxes for each combination.*

| Event Type | Recommended Channels |
|------------|---------------------|
| Approval Request | Email, Slack, Dashboard |
| Approval Timeout Warning | Email, Dashboard |
| Security Alert (Critical/High) | All channels |
| Security Alert (Medium/Low) | Dashboard only |
| Deployment Complete | Slack, Dashboard |
| Environment Ready | Dashboard |
| Budget Warning | Email, Dashboard |

### Quiet Hours

Suppress non-critical notifications during specified hours:

1. Enable **Quiet Hours**
2. Set start and end times (in your timezone)
3. Select which days to apply (e.g., weekends only)
4. Critical and High severity alerts are never suppressed

**Example:** Enable quiet hours from 10 PM to 7 AM on weekdays to reduce off-hours noise.

---

## Sandbox Isolation Configuration

Sandbox isolation determines the security boundaries for test environments. Choose the level appropriate for your security requirements.

### Accessing Isolation Settings

1. Navigate to **Settings > Security** tab
2. Find the **Sandbox Isolation** section

### Understanding Isolation Levels

#### Namespace Isolation

**Provisioning Time:** 30 seconds
**Monthly Cost Impact:** Minimal
**Security Level:** Basic

Environments share the same cluster but are isolated via Kubernetes namespaces.

| Security Feature | Status |
|-----------------|--------|
| Process isolation | Yes |
| Network policies | Yes |
| Resource quotas | Yes |
| Shared kernel | Yes (same node) |
| Dedicated compute | No |

**Best For:** Quick tests, trusted code, development workflows

#### Container Isolation

**Provisioning Time:** 1-2 minutes
**Monthly Cost Impact:** Low
**Security Level:** Standard

Each environment runs in dedicated containers with enhanced isolation.

| Security Feature | Status |
|-----------------|--------|
| Process isolation | Yes |
| Network policies | Yes |
| Resource quotas | Yes |
| Container sandboxing | Yes |
| Restricted capabilities | Yes |
| Dedicated compute | Optional |

**Best For:** Standard testing, untrusted code review, CI/CD pipelines

#### VPC Isolation

**Provisioning Time:** 5-10 minutes
**Monthly Cost Impact:** Medium
**Security Level:** High

Each environment receives a dedicated Virtual Private Cloud with complete network isolation.

| Security Feature | Status |
|-----------------|--------|
| Dedicated VPC | Yes |
| Private subnets | Yes |
| Security groups | Dedicated |
| No cross-VPC traffic | Yes |
| Internet access | Optional |
| VPC Flow Logs | Yes |

**Best For:** Integration testing, security-sensitive code, compliance requirements

#### Account Isolation

**Provisioning Time:** 15-30 minutes
**Monthly Cost Impact:** High
**Security Level:** Maximum

Each environment runs in a completely separate AWS account.

| Security Feature | Status |
|-----------------|--------|
| Dedicated AWS account | Yes |
| Complete resource isolation | Yes |
| Separate IAM | Yes |
| Independent billing | Yes |
| Cross-account access | None |

**Best For:** Highly sensitive testing, compliance audits, external code review

### Selecting Default Isolation Level

1. Navigate to **Settings > Security > Sandbox Isolation**
2. Review the four isolation level cards
3. Click **Select** on your chosen default level
4. This applies to new environments unless overridden per-template

### Isolation Level Comparison

| Feature | Namespace | Container | VPC | Account |
|---------|-----------|-----------|-----|---------|
| Provisioning Time | 30s | 1-2 min | 5-10 min | 15-30 min |
| Cost Impact | Minimal | Low | Medium | High |
| Network Isolation | Namespace | Container | VPC | Account |
| Compute Isolation | None | Container | Optional | Full |
| Compliance Suitable | Basic | Standard | SOC 2 | CMMC, FedRAMP |

**Screenshot Placeholder:** *Sandbox Isolation selector showing four cards with security icons, provisioning times, and cost indicators.*

---

## Rate Limiting Settings

Rate limiting protects the platform from abuse and ensures fair resource distribution.

### Accessing Rate Limit Settings

1. Navigate to **Settings > Rate Limits** tab
2. The Rate Limiting panel shows tier configurations

### Understanding Rate Limit Tiers

| Tier | Applies To | Purpose |
|------|------------|---------|
| **Public** | Unauthenticated requests | Protection from abuse |
| **Standard** | Regular authenticated users | Fair usage |
| **Admin** | Administrator accounts | Elevated access |
| **Critical** | System-to-system calls | Highest limits |

### Configuring Tier Limits

For each tier, you can configure:

| Setting | Description | Public Default | Standard Default | Admin Default |
|---------|-------------|----------------|------------------|---------------|
| **Requests/Minute** | Short-term burst limit | 10 | 60 | 120 |
| **Requests/Hour** | Sustained rate limit | 100 | 1000 | 5000 |
| **Burst Limit** | Maximum concurrent | 5 | 20 | 50 |

### Adjusting Rate Limits

1. Select the tier to configure
2. Adjust the sliders or enter specific values
3. Click **Save Changes**

**Warning:** Setting limits too low may impact normal operations. Setting limits too high may allow abuse.

### Endpoint Group Visibility

View which endpoints belong to each rate limit category:

1. Click **View Endpoint Groups** in the rate limits panel
2. Expand each category to see included endpoints

| Category | Example Endpoints |
|----------|-------------------|
| **Authentication** | /api/v1/auth/*, /api/v1/login |
| **Read Operations** | GET /api/v1/*, /api/v1/findings |
| **Write Operations** | POST /api/v1/*, PUT /api/v1/* |
| **Agent Operations** | /api/v1/agents/*, /api/v1/orchestrator/* |
| **Admin Operations** | /api/v1/admin/*, /api/v1/settings/* |

### Monitoring Rate Limit Usage

The rate limits dashboard shows current usage:

- **Current Usage:** Real-time request counts per tier
- **Limit Warnings:** Users approaching their limits
- **Blocked Requests:** Requests rejected due to rate limits

---

## Security Alert Configuration

Configure thresholds and escalation rules for security alerts.

### Accessing Security Alert Settings

1. Navigate to **Settings > Security Alerts** tab
2. The Security Alerts panel shows categories and thresholds

### Alert Categories

#### Authentication Alerts

Monitor authentication-related security events.

| Alert Type | Default Threshold | Description |
|------------|------------------|-------------|
| Failed Login Attempts | 5 in 10 minutes | Potential brute force attack |
| Unusual Login Location | Any new location | Access from unexpected geography |
| After-Hours Access | Outside business hours | Access during quiet hours |
| Multiple Session Creation | 3 in 5 minutes | Credential sharing or compromise |

#### Agent Behavior Alerts

Monitor autonomous agent actions for anomalies.

| Alert Type | Default Threshold | Description |
|------------|------------------|-------------|
| Unusual Tool Usage | 50% above baseline | Agent using unexpected tools |
| Excessive API Calls | 200% above baseline | Potential runaway agent |
| Repeated Failures | 5 consecutive failures | Agent malfunction |
| Scope Violation | Any occurrence | Agent exceeding permissions |

#### Data Access Alerts

Monitor access to sensitive data.

| Alert Type | Default Threshold | Description |
|------------|------------------|-------------|
| Bulk Data Export | More than 1000 records | Large data extraction |
| Sensitive Field Access | Any PII/secrets access | Access to protected data |
| Cross-Tenant Access | Any attempt | Multi-tenant boundary violation |
| Unusual Query Patterns | Statistical deviation | Anomalous database queries |

#### Network Alerts

Monitor network activity and connections.

| Alert Type | Default Threshold | Description |
|------------|------------------|-------------|
| Outbound Connection | To unknown destination | Unexpected external access |
| Port Scanning | 10 ports in 1 minute | Reconnaissance activity |
| Sandbox Escape Attempt | Any occurrence | Container/VPC boundary violation |
| DNS Anomaly | Unusual domain queries | Potential exfiltration or C2 |

#### Compliance Alerts

Monitor compliance-related events.

| Alert Type | Default Threshold | Description |
|------------|------------------|-------------|
| Audit Log Gap | More than 5 minutes | Missing audit trail |
| Policy Violation | Any occurrence | Action violating policy |
| Encryption Disabled | Any occurrence | Data protection compromised |
| Retention Violation | Any occurrence | Logs deleted early |

### Adjusting Alert Thresholds

1. Select an alert category
2. Click on the specific alert type
3. Adjust the threshold using the slider or number input
4. Set the time window if applicable
5. Click **Save**

**Screenshot Placeholder:** *Security Alert Configuration showing threshold sliders for Failed Login Attempts with a visualization of current vs threshold values.*

### Severity Escalation

Configure how alerts escalate based on severity:

| Severity | Initial Response | Escalation After | Final Escalation |
|----------|-----------------|------------------|------------------|
| **Critical** | Immediate all-channel alert | 15 minutes | Page on-call |
| **High** | Email + Slack | 1 hour | Escalate to Critical |
| **Medium** | Email | 24 hours | Escalate to High |
| **Low** | Dashboard only | 7 days | Auto-close |

### Configuring Escalation Rules

1. Navigate to **Security Alerts > Escalation Rules**
2. For each severity level, set:
   - Initial notification channels
   - Escalation timeout
   - Escalation action (upgrade severity, notify additional recipients)
3. Click **Save Escalation Rules**

---

## Best Practices

### For Government and Defense Organizations

| Setting | Recommended Value |
|---------|-------------------|
| Integration Mode | Defense |
| Autonomy Policy | Maximum Security or Defense Standard |
| Log Retention | 365 days |
| Sandbox Isolation | VPC or Account |
| HITL Enabled | Yes (all operations) |
| External Tools | Disabled |

### For Commercial Enterprises

| Setting | Recommended Value |
|---------|-------------------|
| Integration Mode | Enterprise |
| Autonomy Policy | Balanced or Accelerated |
| Log Retention | 90 days minimum |
| Sandbox Isolation | Container or VPC |
| HITL Enabled | Yes (Critical/High only) |
| External Tools | Enable as needed |

### For Development Teams

| Setting | Recommended Value |
|---------|-------------------|
| Integration Mode | Enterprise or Hybrid |
| Autonomy Policy | Accelerated or Full Autonomous |
| Log Retention | 30-60 days |
| Sandbox Isolation | Namespace or Container |
| HITL Enabled | Optional (for critical only) |
| External Tools | Full integration |

### Configuration Change Management

1. **Document Changes:** Keep a log of configuration changes with rationale
2. **Test First:** Test configuration changes in a non-production environment
3. **Staged Rollout:** Apply changes to a subset of users before organization-wide
4. **Review Regularly:** Schedule quarterly reviews of configuration settings
5. **Audit Trail:** Review audit logs after significant changes

### Security Configuration Checklist

- [ ] Integration Mode matches compliance requirements
- [ ] Autonomy policy aligns with organizational risk tolerance
- [ ] Log retention meets regulatory requirements
- [ ] Sandbox isolation appropriate for code sensitivity
- [ ] Rate limits protect against abuse without impacting users
- [ ] Security alert thresholds tuned to reduce noise
- [ ] Notification channels configured and tested
- [ ] Guardrails in place for critical operations

---

## Troubleshooting

### Settings Not Saving

**Symptom:** You click Save but settings revert to previous values.

**Possible Causes and Solutions:**

1. **Insufficient Permissions**
   - Verify you have Administrator or Security Engineer role
   - Check with your admin if roles were recently changed

2. **Validation Errors**
   - Look for red error messages near input fields
   - Ensure values are within allowed ranges

3. **Network Issues**
   - Check your internet connection
   - Try refreshing the page and saving again

### Mode Changes Not Taking Effect

**Symptom:** You changed Integration Mode but features remain unchanged.

**Solutions:**

1. Refresh the browser page
2. Sign out and sign back in
3. Wait 5 minutes for changes to propagate
4. Check for active cooldown periods

### Notifications Not Arriving

**Symptom:** You configured notifications but are not receiving them.

**Solutions:**

1. **Email:** Check spam/junk folders; verify email addresses
2. **Slack:** Verify the bot has permission to post in the channel
3. **Webhook:** Test the endpoint with a manual request
4. **Check Event Routing:** Ensure the event type is routed to your channel

### Agent Configuration Not Applied

**Symptom:** Agent behavior does not reflect configuration changes.

**Solutions:**

1. Configuration applies to new tasks only; wait for current tasks to complete
2. Restart the agent to force configuration reload
3. Verify the agent status is "Healthy" after configuration change

### Rate Limit Errors

**Symptom:** You receive "Too Many Requests" (429) errors.

**Solutions:**

1. Check your current tier and limits in Rate Limiting settings
2. Wait for the rate limit window to reset
3. Request an admin to adjust your tier limits if appropriate
4. Implement request queuing in your integration

### Environment Creation Failing

**Symptom:** Test environments fail to provision.

**Solutions:**

1. Check if you have reached your concurrent environment quota
2. Verify your monthly budget has not been exceeded
3. Try a lower isolation level (faster provisioning)
4. Check for any platform-wide capacity issues in the status page

### Security Alerts Too Noisy

**Symptom:** You receive too many alerts for normal activity.

**Solutions:**

1. Review and adjust alert thresholds (increase for noisy alerts)
2. Add exceptions for known benign patterns
3. Use digest mode for non-critical alerts
4. Configure quiet hours for after-hours non-critical alerts

---

## Glossary

| Term | Definition |
|------|------------|
| **Agent** | An autonomous AI component that performs specific tasks (Coder, Reviewer, Validator) |
| **Air-Gap** | A network security measure where a system is isolated from external networks |
| **Autonomy Level** | The degree to which agents can operate without human approval |
| **CMMC** | Cybersecurity Maturity Model Certification - DoD contractor security standard |
| **Cold Start** | Initial delay when creating a new processing resource |
| **FedRAMP** | Federal Risk and Authorization Management Program - government cloud security standard |
| **Guardrail** | A non-configurable safety rule that always requires human approval |
| **HITL** | Human-in-the-Loop - requiring human approval for certain operations |
| **Hybrid Mode** | Platform mode allowing selective external integrations |
| **Isolation Level** | Security boundary for test environments (Namespace, Container, VPC, Account) |
| **MCP Gateway** | Model Context Protocol gateway for external tool integrations |
| **Namespace** | Kubernetes isolation boundary for workloads |
| **On-Demand** | Resources created when needed and terminated after use |
| **Orchestrator** | The component that coordinates agent workflows |
| **Policy Preset** | Pre-configured autonomy settings for common compliance scenarios |
| **Rate Limiting** | Restricting the number of requests a user can make in a time period |
| **Sandbox** | An isolated environment for testing code changes safely |
| **Severity** | Classification of finding importance (Critical, High, Medium, Low, Info) |
| **SNS** | Amazon Simple Notification Service for automated alerts |
| **TTL** | Time-to-Live - how long a resource exists before automatic deletion |
| **VPC** | Virtual Private Cloud - isolated network environment in AWS |
| **Warm Pool** | Pre-provisioned resources ready to process requests immediately |
| **Webhook** | HTTP callback for sending notifications to external systems |

---

## Related Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Platform overview and first steps |
| [Security and Compliance](./security-compliance.md) | HITL workflows and compliance details |
| [Agent System](./agent-system.md) | How agents work and monitoring |
| [Integrations](./integrations.md) | External tool connection details |
| [API Reference](./api-reference.md) | REST API documentation |
| [Troubleshooting](./troubleshooting.md) | Common issues and solutions |

---

**Document Version:** 1.0
**Maintained By:** Aura Platform Team
**Feedback:** Contact your Aura Platform administrator with questions or suggestions.
