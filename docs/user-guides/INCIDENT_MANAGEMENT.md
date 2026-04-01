# Incident Management User Guide

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

The Incident Investigations view in Project Aura provides a centralized interface for managing and investigating production incidents. This feature combines AI-powered Root Cause Analysis (RCA) with seamless integration to external ticketing systems, enabling teams to track, investigate, and resolve incidents efficiently.

### Key Capabilities

- **Internal Incident Tracking**: Create and manage incident records within Project Aura
- **AI-Powered Root Cause Analysis**: Automated investigation with confidence scoring
- **External Ticketing Integration**: Export incidents to Zendesk, ServiceNow, Linear, or Jira
- **Real-Time Timeline**: Track all investigation activities and decisions
- **Evidence Collection**: Aggregate logs, metrics, and traces in one location

---

## Accessing Incident Investigations

1. Navigate to the main Aura Platform dashboard
2. Select **Incident Investigations** from the sidebar navigation
3. The view displays active incidents, investigation status, and key metrics

### Dashboard Metrics

| Metric | Description |
|--------|-------------|
| **Total Incidents** | Count of all incidents in the system |
| **Open** | Incidents awaiting investigation |
| **Investigating** | Incidents currently being analyzed |
| **RCA Success Rate** | Percentage of incidents with successful root cause identification |

---

## Creating a New Incident

The **+ New Incident** button allows you to manually create an incident record within Project Aura. This is the primary method for logging incidents that require internal tracking and AI-powered investigation.

### When to Use

- You have identified an issue that needs formal tracking
- A user has reported a problem that requires investigation
- You want to leverage Aura's AI agents for root cause analysis
- You need to document an incident for audit or compliance purposes
- You want to coordinate investigation across team members

### How to Create a New Incident

1. Click the **+ New Incident** button in the header section
2. Complete the incident form:

| Field | Required | Description |
|-------|----------|-------------|
| **Title** | Yes | Brief, descriptive summary of the incident (e.g., "Memory leak in Coder Agent") |
| **Description** | No | Detailed explanation of the symptoms, impact, and any initial observations |
| **Severity** | Yes | Select from Critical, High, Medium, or Low based on business impact |
| **Affected Service** | Yes | The service or component experiencing the issue (e.g., "auth-service", "context-retrieval") |
| **Source** | No | How the incident was detected; defaults to "Manual Entry" |

3. Click **Create Incident** to submit

### Source Options

| Source | Use Case |
|--------|----------|
| **Manual Entry** | Incident identified through direct observation |
| **User Report** | Reported by an end user or customer |
| **CloudWatch Alarm** | Triggered by AWS CloudWatch monitoring |
| **Prometheus Alert** | Triggered by Prometheus alerting rules |
| **Security Scanner** | Identified by security scanning tools |

### After Creation

Once created, the incident:
- Appears in the incident list with "Open" status
- Receives a unique incident ID (e.g., INC-001)
- Can be assigned to an AI agent for automated investigation
- Begins accumulating timeline entries

---

## Creating an External Ticket

The **Create Ticket** button exports an existing incident to an external IT Service Management (ITSM) or ticketing system. This enables collaboration with external teams, SLA tracking, and integration with your organization's existing workflows.

### When to Use

- The incident requires involvement from teams outside the Aura Platform
- Your organization mandates ticket creation in a specific ITSM system
- You need to track the incident against SLA commitments
- External vendors or support teams need visibility
- Compliance requirements mandate external documentation

### Prerequisites

- An incident must be selected in the detail panel
- The incident must not be in "Resolved" status
- The **Create Ticket** button appears in the detail panel footer

### How to Create an External Ticket

1. Select an incident from the incident list
2. Click the **Create Ticket** button in the detail panel footer
3. Complete the ticket export form:

| Field | Required | Description |
|-------|----------|-------------|
| **Ticketing System** | Yes | Select from Zendesk, ServiceNow, Linear, or Jira (visual grid selector) |
| **Priority** | Yes | Urgent, High, Normal, or Low; auto-suggested based on incident severity |
| **Assignee** | No | Email address of the person to assign the ticket to |
| **Additional Notes** | No | Context or instructions for the external team |

4. Click **Create Ticket** to submit

### Supported Ticketing Systems

| System | Integration Type |
|--------|------------------|
| **Zendesk** | Customer service and support ticketing |
| **ServiceNow** | Enterprise IT service management |
| **Linear** | Engineering issue tracking and project management |
| **Jira** | Agile project and issue tracking |

### Severity-to-Priority Mapping

The external ticket priority is auto-suggested based on the incident severity:

| Incident Severity | Suggested Priority |
|-------------------|-------------------|
| Critical | Urgent |
| High | High |
| Medium | Normal |
| Low | Low |

You can override this suggestion if your organization uses different priority mappings.

### After Ticket Creation

When an external ticket is created:
- A timeline entry is added to the incident showing the external ticket reference
- The external ticket ID is displayed in the format: `[SYSTEM]-[TICKET-ID]` (e.g., ZENDESK-123456)
- The incident remains in Project Aura for continued internal tracking
- Both systems maintain independent records of the issue

---

## Understanding the Difference: New Incident vs. Create Ticket

These two actions serve distinct purposes in the incident management workflow:

| Action | Purpose | Creates Record In | Use Case |
|--------|---------|-------------------|----------|
| **+ New Incident** | Log an issue internally | Project Aura | Initial incident detection and AI-powered investigation |
| **Create Ticket** | Export to external system | External ITSM + reference in Aura | Cross-team coordination and external tracking |

### Typical Workflow

1. **Detection**: An issue is detected (manually, via alert, or user report)
2. **Create Incident**: Use **+ New Incident** to log the issue in Project Aura
3. **Investigation**: Assign an AI agent or manually investigate; review RCA findings
4. **Escalation**: If external teams are needed, use **Create Ticket** to export to ITSM
5. **Resolution**: Mark the incident resolved once the issue is addressed

---

## Incident Investigation Features

### Assigning an AI Agent

For incidents without assigned investigators:

1. Select the incident from the list
2. Click **Assign Agent** in the detail panel
3. The Runtime Incident Agent begins automated investigation
4. Investigation progress appears in the Timeline tab

### Timeline Tab

The timeline displays a chronological record of all incident activities:

| Event Type | Description |
|------------|-------------|
| **Detection** | When and how the incident was identified |
| **Assignment** | Agent or user assigned to investigate |
| **Action** | Investigation steps taken |
| **Finding** | Discoveries and root cause identification |
| **Resolution** | Incident closure details |

### RCA Tab (Root Cause Analysis)

When AI investigation is complete, the RCA tab displays:

- **Confidence Score**: AI confidence in the root cause hypothesis (0-100%)
- **Root Cause Hypothesis**: Detailed explanation of the probable cause
- **Related Code**: Code entities linked to the issue
- **Related Deployments**: Recent deployments that may have contributed
- **Recommended Mitigation**: Suggested steps to resolve the issue

### Evidence Tab

Aggregated evidence supporting the investigation:

- **Logs**: Relevant log entries
- **Metrics**: Performance and health metrics
- **Traces**: Stack traces and execution paths

---

## Resolving an Incident

Once investigation is complete and the issue is addressed:

1. Select the incident from the list
2. Review the RCA findings and verify the fix
3. Click **Mark Resolved** in the detail panel
4. The incident status changes to "Resolved" with timestamp and resolver information

### Resolved Incident Details

Resolved incidents display:
- Resolver identity (email address)
- Resolution timestamp
- Complete timeline of investigation activities

---

## Filtering and Search

### Search

Use the search bar to find incidents by:
- Incident ID (e.g., "INC-001")
- Title keywords
- Affected service name

### Status Filters

| Filter | Shows |
|--------|-------|
| **All** | All incidents regardless of status |
| **Open** | Incidents awaiting investigation |
| **Investigating** | Incidents currently being analyzed |
| **Resolved** | Closed incidents |

---

## Best Practices

### Writing Effective Incident Titles

| Quality | Example |
|---------|---------|
| Good | "Memory leak in Coder Agent causing OOM crashes" |
| Good | "High latency in GraphRAG queries exceeding 5s p99" |
| Poor | "Something is broken" |
| Poor | "Error" |

### Severity Guidelines

| Severity | Criteria |
|----------|----------|
| **Critical** | Complete service outage or data loss risk; immediate action required |
| **High** | Significant degradation affecting multiple users; urgent response needed |
| **Medium** | Partial functionality impaired; normal business hours response acceptable |
| **Low** | Minor issue with workaround available; address during regular maintenance |

### When to Create External Tickets

Consider creating external tickets when:
- Multiple teams need to collaborate on resolution
- SLA tracking is required
- Customer-facing communication is needed
- The issue spans multiple systems or platforms
- Regulatory compliance mandates external documentation

---

## Troubleshooting

### Create Ticket Button Not Visible

**Cause**: The incident is either not selected or already resolved.

**Solution**: Select an active (non-resolved) incident from the list to enable the Create Ticket button.

### RCA Tab Shows "Not Yet Available"

**Cause**: AI investigation is still in progress or no agent has been assigned.

**Solution**: Assign an agent to the incident or wait for ongoing analysis to complete.

### Incident Not Appearing After Creation

**Cause**: Filter settings may be hiding the new incident.

**Solution**: Reset filters to "All" status and clear the search field.

---

## Related Documentation

- [HITL Sandbox Architecture](/docs/design/HITL_SANDBOX_ARCHITECTURE.md) - Patch approval and sandbox environments
- [Security Incident Response](/docs/security/SECURITY_INCIDENT_RESPONSE.md) - Security-specific incident procedures
- [Notification Integration Guide](/docs/guides/NOTIFICATION_INTEGRATION_GUIDE.md) - Alert and notification configuration
- [Platform End-User Guide](/docs/stakeholders/PLATFORM_ENDUSER_GUIDE.md) - General platform usage
