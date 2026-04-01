# User Guides

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Introduction

Welcome to the Project Aura User Guides. This section provides step-by-step instructions for common tasks and workflows within the Aura platform. Whether you are onboarding your first repository, reviewing AI-generated patches, or customizing your dashboard, these guides will help you work efficiently.

User Guides focus on practical, task-oriented instructions. For conceptual explanations of how Aura works, see [Core Concepts](../core-concepts/index.md). For initial setup, see [Getting Started](../getting-started/index.md).

---

## Available Guides

### [Repository Onboarding](./repository-onboarding.md)

Connect your code repositories to Aura and configure security scanning.

**Topics covered:**
- Connecting GitHub and GitLab accounts via OAuth
- Selecting repositories to analyze
- Configuring branch selection and language filters
- Setting scan frequency and exclusion patterns
- Monitoring initial ingestion progress

**Time to complete:** 10-15 minutes

---

### [Vulnerability Remediation](./vulnerability-remediation.md)

Find, understand, and fix security vulnerabilities in your codebase.

**Topics covered:**
- Navigating the vulnerability dashboard
- Understanding severity levels and prioritization
- Viewing vulnerability details and affected code
- Reviewing AI-generated patch suggestions
- Initiating one-click remediation workflows

**Time to complete:** 15-20 minutes

---

### [Patch Approval Workflows](./patch-approval.md)

Review and approve AI-generated security patches through the Human-in-the-Loop system.

**Topics covered:**
- Understanding autonomy levels (Manual, Supervised, Autonomous, Full Auto)
- Managing the approval queue and notifications
- Reviewing patch diffs with full context
- Sandbox testing results and validation
- Bulk approval for low-risk patches

**Time to complete:** 20-30 minutes

---

### [Dashboard Customization](./dashboard-customization.md)

Personalize your Aura dashboard to focus on metrics that matter most to your role.

**Topics covered:**
- Role-based default dashboards
- Adding, removing, and arranging widgets
- Using the custom widget builder
- Sharing dashboards with team members
- Configuring scheduled reports

**Time to complete:** 15-20 minutes

---

### [Team Collaboration](./team-collaboration.md)

Work effectively with your team using Aura's collaboration features.

**Topics covered:**
- Inviting team members to your organization
- Role-based permissions (Admin, Developer, Viewer)
- Sharing dashboards and reports
- Configuring notification preferences
- Reviewing the activity audit log

**Time to complete:** 10-15 minutes

---

### [Capability Graph](./capability-graph.md)

Visualize and analyze agent capabilities, permissions, and security relationships.

**Topics covered:**
- Understanding the force-directed graph visualization
- Filtering by agent types and tool classifications
- Identifying escalation paths and privilege risks
- Detecting coverage gaps and toxic combinations
- Using the risk threshold slider
- Interactive node exploration and tooltips

**Time to complete:** 15-20 minutes

---

## Quick Reference

| Task | Guide | Estimated Time |
|------|-------|----------------|
| Connect a new repository | [Repository Onboarding](./repository-onboarding.md) | 5-10 minutes |
| Review vulnerability findings | [Vulnerability Remediation](./vulnerability-remediation.md) | 5-15 minutes |
| Approve a security patch | [Patch Approval Workflows](./patch-approval.md) | 2-5 minutes per patch |
| Customize your dashboard | [Dashboard Customization](./dashboard-customization.md) | 5-10 minutes |
| Add a team member | [Team Collaboration](./team-collaboration.md) | 2-3 minutes |
| Analyze agent permissions | [Capability Graph](./capability-graph.md) | 10-15 minutes |

---

## Prerequisites

Before following these guides, ensure you have:

- [ ] Active Aura account with appropriate role permissions
- [ ] Completed the [Quick Start Guide](../getting-started/quick-start.md)
- [ ] Access to repositories you want to analyze (for repository onboarding)
- [ ] Admin or Security Engineer role (for certain features)

---

## Guide Conventions

Throughout these guides, you will encounter the following formatting conventions:

**Navigation paths** are shown in bold with arrows:
- **Settings > Integrations > OAuth Connections**

**Button labels** are shown in bold:
- Click **Generate Patch** to start remediation

**Keyboard shortcuts** are shown in monospace:
- Press `Ctrl+S` to save changes

**Code examples** appear in code blocks:
```python
# Example code snippet
def secure_function(input_data):
    return sanitize(input_data)
```

**Callouts** highlight important information:

> **Note:** General information or tips to improve your workflow.

> **Warning:** Important cautions to avoid errors or data loss.

> **Tip:** Best practices and efficiency suggestions.

---

## Getting Help

If you encounter issues while following these guides:

- **In-App Help:** Click the **?** icon in the navigation bar
- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Email:** support@aenealabs.com

For feature requests or documentation feedback, use the **Feedback** button in the documentation sidebar.

---

## Related Documentation

- [Getting Started](../getting-started/index.md) - Initial setup and configuration
- [Core Concepts](../core-concepts/index.md) - Technical foundations and architecture
- [API Reference](../../support/api-reference/index.md) - REST and GraphQL APIs
- [Troubleshooting](../../support/troubleshooting/index.md) - Common issues and solutions
