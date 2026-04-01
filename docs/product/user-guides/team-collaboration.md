# Team Collaboration

**Version:** 1.0
**Last Updated:** January 2026
**Time to Complete:** 10-15 minutes

---

## Overview

Project Aura provides robust team collaboration features that enable security teams to work together effectively. This guide covers how to invite team members, manage role-based permissions, share dashboards and reports, configure notifications, and review team activity through audit logs.

By the end of this guide, you will be able to:
- Invite and manage team members in your organization
- Understand and assign role-based permissions
- Share dashboards, reports, and saved searches
- Configure notification preferences for your team
- Review activity audit logs for compliance

---

## Prerequisites

Before managing team collaboration features, ensure you have:

- [ ] Admin role in your Aura organization
- [ ] Organization setup completed (during initial onboarding)
- [ ] Team member email addresses to invite

> **Note:** Only Admin users can invite team members and manage permissions. Security Engineers can share dashboards but cannot modify organization settings.

---

## Organization Structure

### Understanding Organizations

An organization in Aura represents your company or team:

```
Organization: ACME Corporation
├── Members: 12 users
├── Repositories: 8 connected
├── Teams: 3 (Security, DevOps, Engineering)
└── Policies: enterprise_standard (preset)
```

### Organization Settings

View and manage organization settings:

1. Navigate to **Settings > Organization**

2. View organization details:

| Setting | Description |
|---------|-------------|
| **Name** | Organization display name |
| **Domain** | Email domain for SSO |
| **Member Count** | Total active members |
| **Plan** | Subscription tier |
| **Created** | Organization creation date |

---

## Inviting Team Members

### Single User Invitation

1. Navigate to **Settings > Team**

2. Click **Invite Member**

3. Enter invitation details:

![Invite Member Modal](../images/placeholder-invite-member.png)

| Field | Description |
|-------|-------------|
| **Email** | User's email address |
| **Role** | Permission level (see [Roles](#role-based-permissions)) |
| **Team** | Optional team assignment |
| **Message** | Optional personal message |

4. Click **Send Invitation**

5. The user receives an email invitation:

```
Subject: You're invited to join ACME Corporation on Project Aura

Hi,

[Sender Name] has invited you to join ACME Corporation on Project Aura,
the autonomous AI security platform.

Click below to accept your invitation and set up your account:

[Accept Invitation]

This invitation expires in 7 days.

--
Project Aura by Aenea Labs
```

### Bulk Invitations

For multiple users:

1. Click **Invite Member > Bulk Invite**

2. Enter multiple email addresses (one per line or comma-separated):
   ```
   alice@company.com
   bob@company.com
   carol@company.com
   ```

3. Select a common role for all invitees

4. Click **Send Invitations**

5. Each user receives an individual invitation

### Invitation Status

Track pending invitations:

1. Navigate to **Settings > Team > Pending Invitations**

2. View invitation status:

| Email | Invited By | Date | Status | Actions |
|-------|------------|------|--------|---------|
| alice@company.com | admin@company.com | Jan 20 | Pending | Resend / Cancel |
| bob@company.com | admin@company.com | Jan 18 | Accepted | - |
| carol@company.com | admin@company.com | Jan 15 | Expired | Resend |

### Resending Invitations

If an invitation expires or is lost:

1. Find the user in **Pending Invitations**

2. Click **Resend**

3. A new invitation email is sent

4. Previous invitation link is invalidated

---

## Role-Based Permissions

### Available Roles

| Role | Description | Typical Users |
|------|-------------|---------------|
| **Admin** | Full organization control | Team leads, Security managers |
| **Security Engineer** | Approve patches, manage vulnerabilities | Security analysts, AppSec engineers |
| **Developer** | View vulnerabilities, limited actions | Software developers |
| **Viewer** | Read-only access | Stakeholders, auditors |

### Permission Matrix

| Permission | Admin | Security Engineer | Developer | Viewer |
|------------|-------|-------------------|-----------|--------|
| View dashboards | Yes | Yes | Yes | Yes |
| View vulnerabilities | Yes | Yes | Yes | Yes |
| Generate patches | Yes | Yes | No | No |
| Approve/reject patches | Yes | Yes | No | No |
| Connect repositories | Yes | Yes | No | No |
| Customize dashboard | Yes | Yes | Yes | No |
| Share dashboards | Yes | Yes | Yes | No |
| Invite team members | Yes | No | No | No |
| Manage roles | Yes | No | No | No |
| Modify policies | Yes | No | No | No |
| View audit logs | Yes | Yes | No | No |
| Access billing | Yes | No | No | No |

### Assigning Roles

**During Invitation:**

1. Select role when creating invitation
2. User receives role upon accepting

**Changing Existing Role:**

1. Navigate to **Settings > Team**

2. Find the user in the member list

3. Click the role dropdown

4. Select new role

5. Confirm the change

> **Warning:** Demoting a user removes their access to higher-permission features immediately. Ensure they have saved any work in progress.

### Role Descriptions

**Admin**

Full control over the organization:
- Invite and remove team members
- Modify organization settings
- Configure security policies
- Access billing and usage data
- All Security Engineer permissions

**Security Engineer**

Primary role for security operations:
- Review and approve patches
- Generate remediation for vulnerabilities
- Connect and configure repositories
- Share dashboards and reports
- View audit logs for compliance

**Developer**

Focused on visibility and tracking:
- View vulnerabilities affecting their code
- Track remediation status
- Customize personal dashboard
- Export data for analysis
- Cannot initiate remediation

**Viewer**

Read-only access for stakeholders:
- View dashboards and reports
- See vulnerability summaries
- Access shared content
- Cannot modify any data

---

## Teams (Optional)

Organize members into teams for easier management.

### Creating a Team

1. Navigate to **Settings > Teams**

2. Click **Create Team**

3. Enter team details:

| Field | Description |
|-------|-------------|
| **Name** | Team display name (e.g., "Platform Security") |
| **Description** | Team purpose and responsibilities |
| **Members** | Initial team members |

4. Click **Create**

### Team-Based Features

| Feature | Description |
|---------|-------------|
| **Team Dashboards** | Dashboards visible to all team members |
| **Team Notifications** | Alerts sent to team channel |
| **Team Assignment** | Assign vulnerabilities to a team |
| **Team Reporting** | Activity reports scoped to team |

### Managing Team Membership

1. Click on a team name

2. Add or remove members:
   - Click **Add Member** to add existing org members
   - Click **X** next to a name to remove

3. Changes take effect immediately

---

## Shared Dashboards and Reports

### Sharing Dashboards

Share your custom dashboards with team members:

1. Open the dashboard to share

2. Click the **Share** icon

3. Configure sharing options:

**Share with Specific Users:**
```
alice@company.com - Edit access
bob@company.com - View only
```

**Share with Team:**
```
Platform Security Team - View only
```

**Share with Organization:**
Toggle to make visible to all org members

4. Click **Share**

See [Dashboard Customization](./dashboard-customization.md) for detailed sharing instructions.

### Sharing Saved Searches

Share vulnerability filters and search queries:

1. In the Vulnerabilities view, create your filter

2. Click **Save Search**

3. Name your search: `Critical SQLi - Payment Services`

4. Toggle **Share with Organization**

5. Click **Save**

6. Team members see it in **Saved Searches**

### Sharing Reports

Share scheduled reports:

1. Navigate to **Settings > Scheduled Reports**

2. Find the report to share

3. Click **Edit Recipients**

4. Add team members or distribution lists

5. Click **Save**

---

## Notification Preferences

### Personal Notification Settings

Configure how you receive notifications:

1. Navigate to **Settings > Notifications**

2. Configure by notification type:

| Notification | Email | Slack | In-App | SMS |
|--------------|-------|-------|--------|-----|
| Critical vulnerability | Yes | Yes | Yes | Yes |
| Patch pending approval | Yes | Yes | Yes | No |
| Patch approved/rejected | Yes | No | Yes | No |
| Scan complete | No | No | Yes | No |
| System alerts | Yes | Yes | Yes | Yes |

3. Set quiet hours:
   ```
   Quiet Hours: 10:00 PM - 7:00 AM (local time)
   Override for: Critical vulnerabilities
   ```

4. Click **Save Preferences**

### Team Notification Channels

Admins can configure organization-wide notification channels:

**Slack Integration:**

1. Navigate to **Settings > Integrations > Slack**

2. Click **Connect to Slack**

3. Authorize the Aura app

4. Select default channels:
   ```
   #security-alerts - Critical and High vulnerabilities
   #aura-approvals - Patch approval requests
   #aura-activity - General activity feed
   ```

**Email Distribution Lists:**

1. Navigate to **Settings > Notifications > Distribution Lists**

2. Add lists:
   ```
   security-team@company.com - All security notifications
   ciso-office@company.com - Executive summaries only
   ```

**Webhook Integration:**

1. Navigate to **Settings > Integrations > Webhooks**

2. Add webhook endpoint:
   ```
   URL: https://your-system.com/webhook/aura
   Events: critical_vulnerability, patch_approved
   Secret: ********
   ```

### Notification Routing

Configure how different alert types route to different channels:

```
Routing Rules:

IF severity = CRITICAL
  THEN notify: security-team@company.com, #security-alerts, PagerDuty

IF type = patch_pending AND severity IN (CRITICAL, HIGH)
  THEN notify: approvers@company.com, #aura-approvals

IF repository IN (payment-gateway, auth-service)
  THEN notify: platform-security@company.com
```

---

## Activity Audit Log

### Understanding the Audit Log

The audit log records all significant actions in your organization for compliance and security review.

### Logged Actions

| Category | Actions Logged |
|----------|----------------|
| **Authentication** | Login, logout, MFA events, session timeouts |
| **User Management** | Invitations, role changes, deactivations |
| **Vulnerabilities** | Detection, status changes, assignments |
| **Patches** | Generation, approval, rejection, deployment |
| **Repositories** | Connection, configuration, disconnection |
| **Settings** | Policy changes, notification updates |
| **Dashboards** | Creation, sharing, deletion |

### Viewing the Audit Log

1. Navigate to **Compliance > Audit Log**

2. Browse recent activity:

![Audit Log](../images/placeholder-audit-log.png)

| Timestamp | User | Action | Details |
|-----------|------|--------|---------|
| 2026-01-23 14:32 | alice@company.com | PATCH_APPROVED | Approved patch for VULN-1234 |
| 2026-01-23 14:15 | system | VULN_DETECTED | Critical SQL Injection in repo-a |
| 2026-01-23 13:45 | bob@company.com | LOGIN | Successful login via SSO |
| 2026-01-23 11:20 | admin@company.com | ROLE_CHANGED | bob@company.com: Developer -> Security Engineer |

### Filtering the Audit Log

Filter by:

- **Date Range:** Last 24 hours, 7 days, 30 days, custom
- **User:** Specific user or "System"
- **Action Type:** Category or specific action
- **Resource:** Repository, vulnerability, etc.

**Example Query:**
```
user:alice@company.com AND action:PATCH* AND date:last_7_days
```

### Exporting Audit Data

For compliance reporting:

1. Configure your filter

2. Click **Export**

3. Select format:
   - CSV (spreadsheet analysis)
   - JSON (programmatic processing)
   - PDF (formal reports)

4. Choose date range and fields

5. Click **Download**

### Audit Log Retention

| Environment | Retention | Notes |
|-------------|-----------|-------|
| Cloud (SaaS) | 7 years | Meets SOX, CMMC requirements |
| Self-hosted | Configurable | Default 90 days, extend as needed |
| Data export | Unlimited | Archive exports for compliance |

---

## User Management

### Viewing Team Members

1. Navigate to **Settings > Team**

2. View all organization members:

| Name | Email | Role | Status | Last Active |
|------|-------|------|--------|-------------|
| Alice Chen | alice@company.com | Admin | Active | Today |
| Bob Smith | bob@company.com | Security Engineer | Active | Yesterday |
| Carol Davis | carol@company.com | Developer | Active | 3 days ago |
| Dan Evans | dan@company.com | Viewer | Inactive | 30+ days |

### Modifying User Settings

1. Click on a user's name

2. View/edit user details:
   - Role assignment
   - Team membership
   - Notification preferences (admin override)
   - Activity history

### Deactivating Users

When a team member leaves:

1. Find the user in **Settings > Team**

2. Click **...** menu > **Deactivate**

3. Confirm deactivation:
   ```
   Deactivate bob@company.com?

   This will:
   - Revoke all access immediately
   - Reassign pending approvals
   - Preserve audit history

   [Cancel]  [Deactivate]
   ```

4. User's access is revoked immediately

> **Note:** Deactivation preserves all audit data for compliance. User records are never deleted.

### Reactivating Users

If a user returns:

1. Navigate to **Settings > Team > Inactive Users**

2. Find the user

3. Click **Reactivate**

4. Assign a role

5. User receives reactivation email

---

## Single Sign-On (SSO)

### Supported SSO Providers

| Provider | Protocol | Status |
|----------|----------|--------|
| Okta | SAML 2.0 | Supported |
| Azure AD | SAML 2.0 / OIDC | Supported |
| Google Workspace | SAML 2.0 | Supported |
| OneLogin | SAML 2.0 | Supported |
| Custom SAML | SAML 2.0 | Supported |

### Configuring SSO

1. Navigate to **Settings > Security > Single Sign-On**

2. Click **Configure SSO**

3. Select your identity provider

4. Follow provider-specific instructions:

**Okta Example:**
```
1. In Okta Admin, create a new SAML application
2. Copy these values from Aura:
   - ACS URL: https://app.aenealabs.com/sso/saml/callback
   - Entity ID: https://app.aenealabs.com/sso/saml/metadata
3. Download Okta metadata XML
4. Upload to Aura SSO configuration
5. Test connection
```

### SSO Enforcement

Require SSO for all users:

1. After SSO is configured and tested

2. Navigate to **Settings > Security > Login Policies**

3. Enable **Require SSO for all users**

4. Set grace period for existing password users

5. Users must authenticate via SSO after grace period

---

## Troubleshooting

### Invitation Not Received

**Symptom:** Invited user says they did not receive email.

**Solutions:**
1. Check spam/junk folder
2. Verify email address is correct
3. Ask IT to whitelist aenealabs.com
4. Resend invitation
5. Use manual link share as fallback

### User Cannot Access Features

**Symptom:** User reports permission denied errors.

**Solutions:**
1. Verify user's assigned role
2. Check if feature requires higher role
3. Ensure user accepted invitation (not pending)
4. Verify no IP or SSO restrictions
5. Check for account deactivation

### Audit Log Missing Events

**Symptom:** Expected actions not appearing in audit log.

**Solutions:**
1. Adjust date range filter
2. Check action type filter
3. Verify events occurred (not just attempted)
4. Allow time for log propagation (up to 5 minutes)
5. Contact support for log investigation

### SSO Login Failures

**Symptom:** Users cannot authenticate via SSO.

**Solutions:**
1. Verify SSO configuration is active
2. Check IdP certificate expiration
3. Ensure user exists in IdP directory
4. Review IdP logs for error details
5. Test with SSO debug mode enabled

---

## Related Documentation

- [Dashboard Customization](./dashboard-customization.md) - Sharing dashboards
- [Patch Approval Workflows](./patch-approval.md) - Approval team configuration
- [Getting Started: Quick Start Guide](../getting-started/quick-start.md) - Initial setup
- [API Reference: Users](../../support/api-reference/rest-api.md) - Programmatic user management
- [Security Architecture](../../support/architecture/security-architecture.md) - Access control details
