# Notification Integration Guide

**Version:** 1.0
**Last Updated:** December 17, 2025
**Audience:** Platform Administrators, DevOps Engineers, Security Teams

---

> **Deployment Status:** Slack and Microsoft Teams notification integrations are **live in the dev environment** as of December 17, 2025. Both `aura-application-deploy-dev` (backend notification_service.py) and `aura-frontend-deploy-dev` (UI components) CodeBuild projects completed successfully.

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Notification Channels](#supported-notification-channels)
3. [Slack Integration](#slack-integration)
4. [Microsoft Teams Integration](#microsoft-teams-integration)
5. [Email (SES) Integration](#email-ses-integration)
6. [SNS Integration](#sns-integration)
7. [Webhook Integration](#webhook-integration)
8. [PagerDuty Integration](#pagerduty-integration)
9. [Event Routing](#event-routing)
10. [Priority Levels](#priority-levels)
11. [Quiet Hours](#quiet-hours)
12. [Environment Variables](#environment-variables)
13. [Testing Integrations](#testing-integrations)
14. [Troubleshooting](#troubleshooting)

---

## Overview

Aura Platform provides multi-channel notification capabilities to keep your team informed about security findings, HITL approval requests, deployment events, and system alerts. This guide explains how to configure each notification channel for your organization.

### Key Features

- **Six Notification Channels:** Email, SNS, Slack, Microsoft Teams, Generic Webhooks, PagerDuty
- **Priority-Based Routing:** Route alerts based on severity (Critical, High, Normal, Low)
- **Rich Message Formatting:** Attachments, colors, and action buttons for supported channels
- **Quiet Hours:** Suppress non-critical notifications during off-hours
- **Event-Based Routing:** Configure which events go to which channels

### Prerequisites

- Platform Administrator or Security Engineer role
- Enterprise or Hybrid integration mode for Slack, Teams, and PagerDuty
- Access to create incoming webhooks in your Slack workspace or Teams channels

---

## Supported Notification Channels

| Channel | Mode Required | Use Case |
|---------|---------------|----------|
| **Email (SES)** | All modes | Primary notification channel for all environments |
| **SNS** | All modes | AWS-based automation and custom integrations |
| **Slack** | Enterprise/Hybrid | Team collaboration and instant alerts |
| **Microsoft Teams** | Enterprise/Hybrid | Enterprise collaboration integration |
| **Webhook** | Enterprise/Hybrid | Custom integrations and automation |
| **PagerDuty** | Enterprise/Hybrid | Incident management and on-call escalation |

### Channel Comparison

| Feature | Email | SNS | Slack | Teams | Webhook | PagerDuty |
|---------|-------|-----|-------|-------|---------|-----------|
| Rich Formatting | Basic | No | Yes | Yes | Custom | Yes |
| Color Coding | No | No | Yes | Yes | Custom | N/A |
| Action Buttons | No | No | No | Yes | Custom | Yes |
| Threading | No | N/A | Yes | No | N/A | N/A |
| Attachments | Yes | No | Yes | No | Custom | N/A |
| Real-time | Varies | Yes | Yes | Yes | Yes | Yes |

---

## Slack Integration

Aura uses Slack incoming webhooks to deliver notifications with rich formatting and priority-based color coding.

### Step 1: Create a Slack Incoming Webhook

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **Create New App** and select **From scratch**
3. Name your app (e.g., "Aura Platform") and select your workspace
4. In the left sidebar, click **Incoming Webhooks**
5. Toggle **Activate Incoming Webhooks** to On
6. Click **Add New Webhook to Workspace**
7. Select the channel where notifications should be posted (e.g., #aura-alerts)
8. Click **Allow**
9. Copy the **Webhook URL** (format: `https://hooks.slack.com/services/T.../B.../...`)

### Step 2: Configure Aura

**Option A: Environment Variables (Recommended for Production)**

Set the following environment variables in your deployment:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
SLACK_CHANNEL=#aura-alerts
SLACK_BOT_NAME=Aura Bot
```

**Option B: UI Configuration**

1. Navigate to **Settings > Notifications**
2. Click **Add Channel** and select **Slack**
3. Enter your webhook URL
4. Configure channel and bot name
5. Click **Save**

### Step 3: Configure Channel Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `SLACK_WEBHOOK_URL` | Incoming webhook endpoint | Required |
| `SLACK_CHANNEL` | Target channel (overrides webhook default) | #aura-notifications |
| `SLACK_BOT_NAME` | Display name for messages | Aura Bot |

### Slack Message Format

Aura sends Slack messages using the attachments format for rich presentation:

```json
{
  "channel": "#aura-alerts",
  "username": "Aura Bot",
  "icon_emoji": ":robot_face:",
  "attachments": [
    {
      "fallback": "Security Alert: Critical vulnerability detected",
      "color": "#DC2626",
      "title": "[AURA] CRITICAL - Security Patch Awaiting Review",
      "text": "A critical vulnerability has been detected...",
      "footer": "Project Aura",
      "ts": 1702828800
    }
  ]
}
```

### Priority Colors (Slack)

| Priority | Color | Hex Code |
|----------|-------|----------|
| Critical | Red | #DC2626 |
| High | Orange | #EA580C |
| Normal | Blue | #3B82F6 |
| Low | Gray | #6B7280 |

### Best Practices for Slack

1. **Create dedicated channels** for different notification types (e.g., #aura-approvals, #aura-security)
2. **Use channel overrides** to route specific events to specific channels
3. **Enable threading** for approval workflows to keep conversations organized
4. **Test webhooks** before enabling for production events

---

## Microsoft Teams Integration

Aura uses Microsoft Teams incoming webhooks with MessageCard format for enterprise notification delivery.

### Step 1: Create a Teams Incoming Webhook

1. Open Microsoft Teams and navigate to the channel where you want notifications
2. Click the **...** (More options) next to the channel name
3. Select **Connectors**
4. Find **Incoming Webhook** and click **Configure**
5. Enter a name for the webhook (e.g., "Aura Platform")
6. Optionally upload an icon
7. Click **Create**
8. Copy the **Webhook URL** (format: `https://outlook.office.com/webhook/...`)
9. Click **Done**

### Step 2: Configure Aura

**Option A: Environment Variables (Recommended for Production)**

```bash
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

**Option B: UI Configuration**

1. Navigate to **Settings > Notifications**
2. Click **Add Channel** and select **Microsoft Teams**
3. Enter your webhook URL
4. Configure display settings
5. Click **Save**

### Teams Message Format

Aura sends Teams messages using the MessageCard format:

```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "DC2626",
  "summary": "[AURA] CRITICAL - Security Alert",
  "sections": [
    {
      "activityTitle": "[AURA] CRITICAL - Security Alert",
      "activitySubtitle": "Priority: CRITICAL",
      "activityImage": "https://aura.local/icon.png",
      "facts": [
        { "name": "Source", "value": "Project Aura" },
        { "name": "Time", "value": "2025-12-17 12:00:00 UTC" }
      ],
      "markdown": true,
      "text": "A critical security vulnerability has been detected..."
    }
  ],
  "potentialAction": [
    {
      "@type": "OpenUri",
      "name": "View in Aura Dashboard",
      "targets": [
        { "os": "default", "uri": "https://aura.example.com/dashboard" }
      ]
    }
  ]
}
```

### Priority Theme Colors (Teams)

| Priority | Theme Color (No #) |
|----------|-------------------|
| Critical | DC2626 |
| High | EA580C |
| Normal | 3B82F6 |
| Low | 6B7280 |

### Best Practices for Teams

1. **Create a dedicated Teams channel** for Aura notifications
2. **Use the "View in Dashboard" action button** to quickly access approval requests
3. **Configure quiet hours** to prevent after-hours notifications for non-critical events
4. **Limit webhook access** to administrators for security

---

## Email (SES) Integration

Email notifications use AWS Simple Email Service (SES) for reliable delivery.

### Configuration

Email configuration is typically set at the infrastructure level:

| Setting | Description | Default |
|---------|-------------|---------|
| `SES_SENDER_EMAIL` | Verified sender address | aura-noreply@{project}.local |
| `SES_REGION` | AWS region for SES | us-east-1 |

### Email Requirements

1. **SES Sender Verification:** The sender email address must be verified in SES
2. **SES Production Access:** For production use, request SES production access to remove sandbox restrictions
3. **IAM Permissions:** The platform role needs `ses:SendEmail` permissions

### Email Format

Aura sends plain-text emails with structured information:

```
Project Aura - Security Patch Approval Request

Approval ID: approval-20251217-abc123
Patch ID: patch-sha256-upgrade
Vulnerability: vuln-sha1-weak-hash
Severity: HIGH
Created: 2025-12-17T12:00:00
Expires: 2025-12-18T12:00:00

--- SANDBOX TEST RESULTS ---
Tests Passed: 42
Tests Failed: 0
Test Coverage: 87.5%

--- ACTION REQUIRED ---
Please review this security patch and approve or reject within 24 hours.

Review URL: https://aura.example.com/approvals/approval-20251217-abc123
```

---

## SNS Integration

AWS SNS (Simple Notification Service) enables integration with AWS infrastructure and custom subscribers.

### Configuration

| Setting | Description |
|---------|-------------|
| `HITL_SNS_TOPIC_ARN` | SNS topic ARN for HITL notifications |
| `AWS_REGION` | AWS region |

### SNS Topic Setup

1. Create an SNS topic in AWS Console
2. Grant publish permissions to the Aura platform role
3. Subscribe endpoints (email, Lambda, SQS, HTTP/S)

### Message Attributes

SNS messages include filterable attributes:

| Attribute | Description |
|-----------|-------------|
| `approval_id` | Unique approval request ID |
| `severity` | Finding severity (CRITICAL, HIGH, MEDIUM, LOW) |
| `priority` | Notification priority |
| `event_type` | Event category (escalation, expiration, etc.) |

---

## Webhook Integration

Generic webhooks allow integration with custom systems and automation platforms.

### Configuration

1. Navigate to **Settings > Notifications**
2. Click **Add Channel** and select **Webhook**
3. Enter the webhook URL (HTTPS required)
4. Configure authentication if needed
5. Save configuration

### Webhook Payload Format

```json
{
  "event": "approval.requested",
  "timestamp": "2025-12-17T12:00:00Z",
  "priority": "high",
  "data": {
    "approval_id": "approval-123",
    "patch_id": "patch-456",
    "severity": "HIGH",
    "vulnerability_id": "vuln-789"
  }
}
```

### Authentication Options

| Method | Description |
|--------|-------------|
| None | No authentication header |
| API Key | `X-API-Key` header |
| Bearer Token | `Authorization: Bearer <token>` |
| Basic Auth | `Authorization: Basic <base64>` |

---

## PagerDuty Integration

PagerDuty integration enables incident management and on-call escalation.

### Configuration

1. Create a PagerDuty integration in your service
2. Copy the Integration Key (routing key)
3. Navigate to **Settings > Notifications**
4. Enable **PagerDuty** and enter the routing key

### Severity Mapping

| Aura Priority | PagerDuty Severity |
|---------------|-------------------|
| Critical | critical |
| High | error |
| Normal | warning |
| Low | info |

---

## Event Routing

Configure which events are sent to which notification channels.

### Supported Events

| Event Type | Description | Recommended Channels |
|------------|-------------|---------------------|
| `approval_required` | New HITL approval request | Email, Slack, Teams |
| `approval_timeout` | Approval request expired | Email |
| `patch_generated` | New security patch created | Dashboard |
| `patch_deployed` | Patch successfully deployed | Slack, Teams |
| `patch_failed` | Patch deployment failed | Email, Slack, Teams, PagerDuty |
| `security_alert` | Critical security event | All channels |
| `system_error` | Platform error occurred | Email, PagerDuty |
| `agent_degraded` | Agent health degraded | Slack, Teams |
| `budget_warning` | Approaching budget limit | Email |
| `environment_expiring` | Test environment expiring | Dashboard |

### Default Event-Channel Matrix

| Event | Email | Slack | Teams | PagerDuty |
|-------|-------|-------|-------|-----------|
| Approval Required | Yes | Yes | Yes | No |
| Approval Timeout | Yes | No | No | No |
| Patch Generated | No | No | No | No |
| Patch Deployed | No | Yes | Yes | No |
| Patch Failed | Yes | Yes | Yes | Yes |
| Security Alert | Yes | Yes | Yes | Yes |
| System Error | Yes | No | No | Yes |
| Agent Degraded | No | Yes | Yes | No |
| Budget Warning | Yes | No | No | No |
| Environment Expiring | No | No | No | No |

### Customizing Event Routing

1. Navigate to **Settings > Notifications > Event Preferences**
2. Toggle events on/off for each channel
3. Save preferences

---

## Priority Levels

Aura uses four priority levels to categorize notifications:

| Priority | Description | UI Color | Slack Color | Teams Color |
|----------|-------------|----------|-------------|-------------|
| **Critical** | Immediate attention required | Red | #DC2626 | DC2626 |
| **High** | Urgent review needed | Orange | #EA580C | EA580C |
| **Normal** | Standard notification | Blue | #3B82F6 | 3B82F6 |
| **Low** | Informational | Gray | #6B7280 | 6B7280 |

### Priority Mapping from Severity

| Finding Severity | Notification Priority |
|------------------|----------------------|
| CRITICAL | Critical |
| HIGH | High |
| MEDIUM | Normal |
| LOW | Low |

---

## Quiet Hours

Suppress non-critical notifications during specified hours.

### Configuration

1. Navigate to **Settings > Notifications > Quiet Hours**
2. Enable **Quiet Hours**
3. Set start and end times
4. Select timezone
5. Configure critical alert bypass

### Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Enabled** | Enable/disable quiet hours | Disabled |
| **Start Time** | When to begin suppression | 22:00 |
| **End Time** | When to end suppression | 08:00 |
| **Timezone** | Timezone for times | UTC |
| **Bypass Critical** | Always send critical alerts | Enabled |

### Bypass Rules

Even during quiet hours, the following notifications are always sent:

- Critical severity security alerts
- High severity security alerts (configurable)
- System emergencies
- PagerDuty escalations

---

## Environment Variables

Complete list of notification-related environment variables:

### Slack

| Variable | Description | Required |
|----------|-------------|----------|
| `SLACK_WEBHOOK_URL` | Incoming webhook URL | For Slack |
| `SLACK_CHANNEL` | Target channel | No |
| `SLACK_BOT_NAME` | Bot display name | No |

### Microsoft Teams

| Variable | Description | Required |
|----------|-------------|----------|
| `TEAMS_WEBHOOK_URL` | Incoming webhook URL | For Teams |

### Email / SES

| Variable | Description | Required |
|----------|-------------|----------|
| `SES_SENDER_EMAIL` | Verified sender address | For email |
| `AWS_REGION` | AWS region | Yes |

### SNS

| Variable | Description | Required |
|----------|-------------|----------|
| `HITL_SNS_TOPIC_ARN` | SNS topic ARN | For SNS |

### Dashboard

| Variable | Description | Required |
|----------|-------------|----------|
| `HITL_DASHBOARD_URL` | Base URL for approval links | Yes |

---

## Testing Integrations

### Using the Test Button

1. Navigate to **Settings > Notifications**
2. Click the **Play** icon next to a configured channel
3. A test notification is sent
4. Verify receipt in the target channel

### Command-Line Testing

For administrators with access to the API:

```bash
# Test Slack notification
curl -X POST https://api.aura.example.com/api/v1/notifications/channels/slack-123/test \
  -H "Authorization: Bearer $TOKEN"
```

### Mock Mode Testing

For development and testing, the notification service supports mock mode:

```python
from src.services.notification_service import create_notification_service

# Create mock service
service = create_notification_service(use_mock=True)

# Notifications are logged but not sent
result = service._send_slack_notification(
    subject="Test",
    message="Test message",
    priority=NotificationPriority.NORMAL
)

# Check delivery log
print(service.get_delivery_log())
```

---

## Troubleshooting

### Slack Notifications Not Arriving

1. **Verify webhook URL:** Ensure the URL is correct and not expired
2. **Check channel permissions:** The webhook app must have access to the target channel
3. **Test webhook manually:**
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message"}' \
     YOUR_WEBHOOK_URL
   ```
4. **Check platform logs:** Look for HTTP errors in notification service logs
5. **Verify integration mode:** Slack requires Enterprise or Hybrid mode

### Teams Notifications Not Arriving

1. **Verify webhook URL:** Teams webhook URLs expire and may need regeneration
2. **Check connector status:** Ensure the connector is still enabled in Teams
3. **Test webhook manually:**
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"@type":"MessageCard","summary":"Test","text":"Test message"}' \
     YOUR_WEBHOOK_URL
   ```
4. **Check for Teams admin restrictions:** Some orgs block incoming webhooks
5. **Verify URL format:** Must start with `https://outlook.office.com/webhook/`

### Webhook Delivery Failures

| Error Code | Cause | Solution |
|------------|-------|----------|
| 400 | Invalid payload | Check webhook endpoint requirements |
| 401/403 | Authentication failed | Verify API key or token |
| 404 | Endpoint not found | Verify webhook URL |
| 429 | Rate limited | Reduce notification frequency |
| 500+ | Server error | Check target system status |

### Email Not Arriving

1. **Check SES status:** Verify SES is not in sandbox mode
2. **Verify sender:** Ensure sender email is verified
3. **Check spam folders:** Emails may be filtered
4. **Review SES metrics:** Check for bounces or complaints

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No notifications | Channel not enabled | Enable in Settings > Notifications |
| Wrong channel | Event routing misconfigured | Review event preferences |
| Missing during quiet hours | Quiet hours enabled | Check quiet hours settings |
| Duplicate notifications | Multiple channels configured | Review channel list |
| Delayed notifications | Rate limiting | Check rate limit settings |

---

## Related Documentation

| Guide | Topic |
|-------|-------|
| [Platform Configuration Guide](./PLATFORM_CONFIGURATION_GUIDE.md) | General settings |
| [Integrations Guide](./integrations.md) | External tool connections |
| [Security & Compliance](./security-compliance.md) | Security settings |
| [Troubleshooting](./troubleshooting.md) | Common issues |

---

**Document Version:** 1.0
**Maintained By:** Aura Platform Team
