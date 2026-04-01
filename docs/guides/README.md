# Aura Platform User Guides

Welcome to the Aura Platform documentation. These guides are designed to help you get the most out of the platform, whether you are a new user getting started or an experienced user looking for specific information.

---

## Quick Start Path

For new users, we recommend following this path:

```
1. Getting Started      -->  Learn the basics
       |
       v
2. Configuration        -->  Set up your environment
       |
       v
3. Security & Compliance -->  Understand HITL and compliance
       |
       v
4. Agent System         -->  Learn how agents work
       |
       v
5. Deployment           -->  Use test environments
```

---

## Guide Index

### Core Guides

| Guide | Description | Audience |
|-------|-------------|----------|
| [Getting Started](./getting-started.md) | Platform overview, first steps, core concepts | New users |
| [Platform Configuration Guide](./PLATFORM_CONFIGURATION_GUIDE.md) | Comprehensive UI configuration walkthrough | Admins, Security |
| [Security & Compliance](./security-compliance.md) | HITL workflows, compliance frameworks, security controls | All users |
| [Agent System](./agent-system.md) | How agents work, orchestration, monitoring | Developers, Admins |
| [Configuration](./configuration.md) | Complete settings reference | Admins |

### Feature Guides

| Guide | Description | Audience |
|-------|-------------|----------|
| [Repository Onboarding](./REPOSITORY_ONBOARDING_GUIDE.md) | Connect GitHub/GitLab repositories via wizard | All users |
| [Data & Context](./data-context.md) | GraphRAG, code indexing, context retrieval | Developers |
| [Deployment](./deployment.md) | Test environments, sandboxes, approval workflows | Developers |
| [Monitoring & Observability](./monitoring-observability.md) | Dashboards, alerts, metrics | Admins, DevOps |

### Reference Guides

| Guide | Description | Audience |
|-------|-------------|----------|
| [API Reference](./api-reference.md) | REST API documentation | Developers |
| [Integrations](./integrations.md) | External tool connections | Admins |
| [Troubleshooting](./troubleshooting.md) | Common issues and solutions | All users |

---

## By Role

### For Developers

| Need | Guide |
|------|-------|
| Understand how code is analyzed | [Data & Context](./data-context.md) |
| Use test environments | [Deployment](./deployment.md) |
| Integrate with API | [API Reference](./api-reference.md) |
| Debug issues | [Troubleshooting](./troubleshooting.md) |

### For Security Engineers

| Need | Guide |
|------|-------|
| Configure HITL workflows | [Security & Compliance](./security-compliance.md) |
| Set up compliance profiles | [Configuration](./configuration.md) |
| Monitor security alerts | [Monitoring & Observability](./monitoring-observability.md) |
| Understand agent security | [Agent System](./agent-system.md) |

### For Administrators

| Need | Guide |
|------|-------|
| Configure platform settings | [Platform Configuration Guide](./PLATFORM_CONFIGURATION_GUIDE.md) |
| Settings quick reference | [Configuration](./configuration.md) |
| Set up integrations | [Integrations](./integrations.md) |
| Monitor platform health | [Monitoring & Observability](./monitoring-observability.md) |
| Troubleshoot issues | [Troubleshooting](./troubleshooting.md) |

---

## By Task

### Getting Started

- [Sign in and navigate the dashboard](./getting-started.md#quick-start)
- [Connect your repositories](./REPOSITORY_ONBOARDING_GUIDE.md)
- [Run your first vulnerability scan](./getting-started.md#your-first-vulnerability-scan)
- [Approve your first patch](./getting-started.md#approving-patches)

### Configuration

- [Choose an integration mode](./configuration.md#integration-mode)
- [Configure HITL settings](./configuration.md#hitl-settings)
- [Set up compliance profiles](./configuration.md#compliance-settings)
- [Configure log retention](./configuration.md#security-settings)

### Security

- [Understand autonomy levels](./security-compliance.md#configurable-autonomy-levels)
- [View security alerts](./monitoring-observability.md#security-alerts)
- [Apply compliance profiles](./security-compliance.md#compliance-profiles)

### Integrations

- [Connect Slack](./integrations.md#slack)
- [Connect Jira](./integrations.md#jira)
- [Connect GitHub](./integrations.md#github)
- [Set up webhooks](./integrations.md#webhook-configuration)

### Environments

- [Create a test environment](./deployment.md#creating-a-test-environment)
- [Understand environment types](./deployment.md#environment-types)
- [Manage quotas](./deployment.md#quotas-and-limits)

### Troubleshooting

- [Authentication issues](./troubleshooting.md#authentication-issues)
- [Agent issues](./troubleshooting.md#agent-issues)
- [Integration issues](./troubleshooting.md#integration-issues)

---

## Key Concepts

### Human-in-the-Loop (HITL)

HITL ensures human oversight for critical operations. Learn more in the [Security & Compliance Guide](./security-compliance.md#human-in-the-loop-hitl-workflows).

### Integration Modes

| Mode | Description |
|------|-------------|
| **Defense** | Maximum security, no external dependencies |
| **Enterprise** | Full external integrations |
| **Hybrid** | Selective integrations with controls |

Learn more in the [Configuration Guide](./configuration.md#integration-mode).

### Autonomy Levels

| Level | HITL Required |
|-------|---------------|
| **Full HITL** | All operations |
| **Critical HITL** | HIGH/CRITICAL only |
| **Audit Only** | None (logged) |
| **Full Autonomous** | None |

Learn more in the [Security & Compliance Guide](./security-compliance.md#configurable-autonomy-levels).

### Agents

Aura uses specialized AI agents:

| Agent | Role |
|-------|------|
| **Coder** | Generates patches |
| **Reviewer** | Reviews for security |
| **Validator** | Tests in sandboxes |

Learn more in the [Agent System Guide](./agent-system.md).

---

## Document Conventions

### Information Boxes

Throughout these guides, you will see:

- **Note**: Additional helpful information
- **Warning**: Important cautions to be aware of
- **Tip**: Helpful suggestions for better results

### Code Examples

```
Code examples are shown in blocks like this
```

### Navigation Paths

Navigation is shown as: **Settings > HITL Settings > Approval Requirements**

---

## Feedback

If you find issues with this documentation or have suggestions for improvement, please contact your Aura administrator.

---

## Version

This documentation is for Aura Platform v1.3.

Last Updated: December 2025
