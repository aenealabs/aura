# Dashboard Customization

**Version:** 1.0
**Last Updated:** January 2026
**Time to Complete:** 15-20 minutes

---

## Overview

Project Aura provides customizable dashboards that allow you to focus on metrics most relevant to your role and responsibilities. This guide covers how to personalize your dashboard with widgets, create custom views, and share dashboards with your team.

By the end of this guide, you will be able to:
- Understand and use role-based default dashboards
- Add, remove, and arrange dashboard widgets
- Build custom widgets for specialized metrics
- Share dashboards with team members
- Configure scheduled reports

---

## Prerequisites

Before customizing your dashboard, ensure you have:

- [ ] Active Aura account with Developer role or higher
- [ ] At least one repository connected and scanned
- [ ] Basic familiarity with Aura's core features

> **Note:** Viewers can view dashboards but cannot create or modify them. Contact your administrator to upgrade your role if customization is needed.

---

## Role-Based Default Dashboards

When you first sign in to Aura, you see a default dashboard configured for your role.

### Default Dashboard Layouts

| Role | Default Widgets | Focus Area |
|------|-----------------|------------|
| **Security Engineer** | Open Vulnerabilities, MTTR, Pending Approvals, Agent Health Grid, CVE Trend, Recent Security Alerts | Security posture and remediation |
| **DevOps Lead** | Sandbox Utilization, Deployment Velocity, GPU Jobs Queued, Environment Status, Agent Health Grid, Cost Trend | Operations and infrastructure |
| **Engineering Manager** | Code Quality Score, Deployment Velocity, Open Vulnerabilities, Pending Approvals, Test Coverage Trend, PR Velocity by Team | Team productivity and code health |
| **Executive/CISO** | Risk Posture Score, Compliance Progress, Monthly Cost, Key Incidents | High-level KPI overview |
| **SuperUser** | All 18 widgets available, starts with executive layout | Full platform access |

### Viewing Your Default Dashboard

1. Sign in to Aura

2. Click **Dashboard** in the sidebar (or you land here automatically)

3. Your role's default dashboard is displayed

![Default Dashboard](../images/placeholder-default-dashboard.png)

### Switching to a Different Default

If your role does not match your actual responsibilities:

1. Click **Dashboard Settings** (gear icon) in the top-right

2. Select **Change Default Layout**

3. Choose from available presets:
   - Security Engineer
   - DevOps Lead
   - Engineering Manager
   - Executive
   - Minimal (blank canvas)

4. Click **Apply**

> **Tip:** Changing your default layout does not affect other team members. Each user maintains their own dashboard configuration.

---

## Adding and Arranging Widgets

### Entering Edit Mode

1. Click **Edit Dashboard** button in the top-right corner

2. The dashboard enters edit mode:
   - Widget borders become visible
   - Drag handles appear
   - **+ Add Widget** button displays
   - **Save** and **Cancel** buttons appear

![Dashboard Edit Mode](../images/placeholder-dashboard-edit-mode.png)

### Adding Widgets

1. In edit mode, click **+ Add Widget**

2. The Widget Library drawer opens

3. Browse widgets by category (18 widgets total):

   **Security (4 widgets)**
   - Open Vulnerabilities - Count of currently open security vulnerabilities
   - Mean Time to Remediate (MTTR) - Average time to fix vulnerabilities
   - CVE Trend - 30-day trend of CVE discoveries and patches
   - Recent Security Alerts - Latest security alerts and notifications

   **Operations (6 widgets)**
   - Pending Approvals - Number of items awaiting HITL approval
   - Agent Health Grid - Health status of all active agents
   - Sandbox Utilization - Current sandbox environment utilization percentage
   - Environment Status - Status of dev/qa/prod environments
   - GPU Jobs Queued - Number of GPU jobs waiting in queue
   - Deployment Velocity - Deployments per day (7-day average)

   **Analytics (3 widgets)**
   - Code Quality Score - Overall code quality score (0-100)
   - Test Coverage Trend - Test coverage percentage over time
   - PR Velocity by Team - Pull request velocity grouped by team

   **Compliance (3 widgets)**
   - Compliance Progress - Overall compliance readiness percentage
   - Risk Posture Score - Composite risk posture score (0-100)
   - Key Incidents - Recent key security incidents table

   **Cost (2 widgets)**
   - Monthly Cost - Current month infrastructure cost
   - Cost Trend - 30-day infrastructure cost trend

4. Click a widget to preview it

5. Click **Add to Dashboard** to place it

![Widget Library](../images/placeholder-widget-library.png)

### Arranging Widgets

**Drag and Drop:**

1. In edit mode, hover over a widget

2. Click and drag the widget header to move it

3. Drop in the desired position

4. Other widgets automatically rearrange

**Resizing Widgets:**

1. Hover over the bottom-right corner of a widget

2. Drag to resize horizontally or vertically

3. Widgets snap to grid positions

**Standard Widget Sizes:**

| Size | Grid Units | Common Use |
|------|------------|------------|
| Small | 1x1 | Single metric |
| Medium | 2x1 | Metric with sparkline |
| Wide | 2x1 | Horizontal chart |
| Tall | 1x2 | Vertical list |
| Large | 2x2 | Detailed chart or table |

### Removing Widgets

1. In edit mode, hover over the widget to remove

2. Click the **X** button in the top-right corner

3. The widget is removed immediately

4. Click **Save** to confirm or **Cancel** to restore

### Saving Changes

1. After arranging widgets, click **Save**

2. Your dashboard configuration is saved to your account

3. The dashboard exits edit mode

> **Note:** Dashboard configurations are saved per user. Changes you make do not affect other team members unless you explicitly share the dashboard.

---

## Widget Configuration

Many widgets support customization options.

### Configuring a Widget

1. In edit mode, click the **gear icon** on any widget

2. The configuration panel opens:

![Widget Configuration](../images/placeholder-widget-config.png)

**Common Configuration Options:**

| Option | Description |
|--------|-------------|
| **Title** | Custom display title |
| **Data Source** | Which metric or data to display |
| **Time Range** | Historical period (24h, 7d, 30d, custom) |
| **Refresh Interval** | How often to update (auto, 1m, 5m, 15m) |
| **Threshold** | Alert threshold for metric widgets |
| **Repository Filter** | Limit to specific repositories |

### Example: Configuring Vulnerability Trend Widget

1. Click gear icon on the vulnerability trend widget

2. Configure options:
   ```
   Title: Critical Vulnerabilities (30 Days)
   Data Source: Vulnerabilities
   Severity Filter: CRITICAL only
   Time Range: 30 days
   Refresh: Every 5 minutes
   Repository: All
   ```

3. Click **Apply**

4. The widget updates with your configuration

---

## Custom Widget Builder

For advanced users, Aura provides a custom widget builder to create specialized visualizations.

### Accessing the Custom Widget Builder

1. In the Widget Library, scroll to **Custom Widgets**

2. Click **Create Custom Widget**

3. The custom widget builder opens

![Custom Widget Builder](../images/placeholder-custom-widget-builder.png)

### Creating a Custom Widget

**Step 1: Select Visualization Type**

| Type | Best For |
|------|----------|
| **Metric Card** | Single value with trend |
| **Line Chart** | Time series data |
| **Bar Chart** | Categorical comparisons |
| **Pie/Donut Chart** | Distribution breakdown |
| **Table** | Detailed data lists |
| **Status Grid** | Multiple status indicators |

**Step 2: Configure Data Source**

1. Select the data category:
   - Vulnerabilities
   - Patches
   - Agents
   - Repositories
   - Users/Activity
   - Custom API endpoint

2. Choose specific metrics:
   ```
   Category: Vulnerabilities
   Metric: Count
   Group By: Severity
   Filter: Status = Open
   ```

3. Set aggregation:
   - Sum, Average, Count, Min, Max
   - Time bucketing (hourly, daily, weekly)

**Step 3: Customize Appearance**

- **Colors:** Select color scheme or custom colors
- **Labels:** Configure axis labels and legends
- **Thresholds:** Set warning/critical thresholds with colors

**Step 4: Preview and Save**

1. Click **Preview** to see your widget

2. Adjust settings as needed

3. Enter a widget name:
   ```
   Name: Critical Vulns by Repository
   Description: Count of critical vulnerabilities grouped by repository
   ```

4. Click **Save Widget**

5. Your custom widget appears in the library

### Example: Custom Vulnerability Heatmap

Create a heatmap showing vulnerability distribution by repository and severity:

```
Visualization: Heatmap
Data Source: Vulnerabilities
X-Axis: Repository Name
Y-Axis: Severity (Critical, High, Medium, Low)
Cell Value: Count
Color Scale: Red (high) to Green (low)
Time Range: Current state
```

---

## Sharing Dashboards

Share your custom dashboards with team members.

### Sharing Options

| Share Type | Access Level | Audience |
|------------|--------------|----------|
| **View Only** | Read-only access | Anyone with link |
| **Edit** | Can modify dashboard | Specific users |
| **Organization** | View access for all org members | Organization-wide |

### Sharing a Dashboard

1. Navigate to the dashboard you want to share

2. Click **Share** (share icon) in the top-right

3. The Share Dashboard modal opens

![Share Dashboard Modal](../images/placeholder-share-dashboard.png)

**Share with Specific Users:**

1. Enter email addresses or select from team members:
   ```
   security-lead@company.com - Edit
   analyst@company.com - View
   ```

2. Set permission level for each:
   - **View** - Can see but not modify
   - **Edit** - Can modify the shared copy

3. Click **Share**

4. Recipients receive an email notification

**Share with Organization:**

1. Toggle **Share with Organization**

2. All organization members can view the dashboard

3. Dashboard appears in their **Shared Dashboards** list

**Get Shareable Link:**

1. Click **Copy Link**

2. Anyone with the link can view (if org sharing enabled)

3. Link respects existing permission settings

### Managing Shared Dashboards

**View Shared Dashboards:**

1. In the Dashboard section, click **Shared with Me**

2. See dashboards shared by team members

3. Click to view or fork

**Fork a Shared Dashboard:**

1. Open a shared dashboard

2. Click **Fork** to create your own copy

3. Modify the forked version independently

**Revoke Sharing:**

1. Open your dashboard

2. Click **Share > Manage Access**

3. Remove users or disable organization sharing

4. Changes take effect immediately

---

## Scheduled Reports

Generate automated dashboard reports delivered via email.

### Creating a Scheduled Report

1. Open the dashboard you want to report

2. Click **...** menu > **Schedule Report**

3. Configure the schedule:

![Schedule Report Modal](../images/placeholder-schedule-report.png)

**Schedule Options:**

| Option | Values |
|--------|--------|
| **Frequency** | Daily, Weekly, Monthly |
| **Day** | Specific day (for weekly/monthly) |
| **Time** | Report generation time (UTC) |
| **Recipients** | Email addresses |
| **Format** | PDF, PNG, CSV data |

**Example Configuration:**

```
Report Name: Weekly Security Summary
Dashboard: Security Overview
Frequency: Weekly
Day: Monday
Time: 8:00 AM UTC
Recipients: security-team@company.com, ciso@company.com
Format: PDF with CSV data attachment
```

4. Click **Create Schedule**

### Managing Scheduled Reports

1. Navigate to **Settings > Scheduled Reports**

2. View all active schedules:

| Report | Dashboard | Frequency | Next Run | Status |
|--------|-----------|-----------|----------|--------|
| Weekly Security | Security Overview | Weekly | Mon 8:00 | Active |
| Daily Metrics | Operations | Daily | 6:00 | Active |
| Monthly Executive | Executive Summary | Monthly | 1st 9:00 | Active |

3. Click a report to edit or delete

### Report Contents

Scheduled reports include:

- Dashboard screenshot (current state)
- Metric summaries as text
- Data tables in attachment (CSV format)
- Time range noted in report header
- Link back to live dashboard

---

## Dashboard Templates

Use pre-built templates for common use cases.

### Available Templates

| Template | Description | Widgets |
|----------|-------------|---------|
| **Security Operations** | SOC team daily view | 8 security widgets |
| **Compliance Dashboard** | Audit-ready overview | 6 compliance widgets |
| **DevSecOps Pipeline** | CI/CD security integration | 7 pipeline widgets |
| **Executive Summary** | High-level KPIs | 4 summary widgets |
| **Incident Response** | Active incident tracking | 6 IR widgets |

### Using a Template

1. Click **Dashboard Settings > Create from Template**

2. Browse available templates

3. Preview the template layout

4. Click **Use Template**

5. The template creates a new dashboard you can customize

---

## Best Practices

### Dashboard Design Tips

**Focus on Actionable Metrics:**
- Include metrics that drive decisions
- Avoid vanity metrics without context
- Ensure each widget serves a purpose

**Limit Widget Count:**
- 6-10 widgets per dashboard is optimal
- Too many widgets reduce focus
- Create multiple dashboards for different contexts

**Use Consistent Time Ranges:**
- Align time ranges across related widgets
- 30 days is good for trends
- 24 hours for operational monitoring

**Group Related Widgets:**
- Place related metrics together
- Use layout to show relationships
- Severity metrics should flow left-to-right

### Performance Considerations

- Widgets with real-time data refresh more frequently
- Large time ranges (90+ days) may load slower
- Custom widgets with complex queries impact performance
- Dashboard load time target: < 2 seconds

---

## Troubleshooting

### Dashboard Not Loading

**Symptom:** Dashboard shows loading spinner indefinitely.

**Solutions:**
1. Refresh the page
2. Check network connectivity
3. Verify API endpoints are reachable
4. Clear browser cache
5. Try a different browser

### Widget Shows "No Data"

**Symptom:** Widget displays "No Data Available."

**Common causes:**

| Cause | Solution |
|-------|----------|
| No repositories connected | Connect repositories first |
| Time range has no data | Adjust to a different time range |
| Filter too restrictive | Remove or adjust filters |
| Permission issue | Verify access to underlying data |

### Changes Not Saving

**Symptom:** Dashboard reverts to previous state.

**Solutions:**
1. Ensure you clicked **Save** before leaving edit mode
2. Check for error messages in the console
3. Verify your session is active (not timed out)
4. Try saving smaller changes incrementally

### Shared Dashboard Not Visible

**Symptom:** Cannot see dashboard shared by team member.

**Solutions:**
1. Check **Shared with Me** section (not main dashboard list)
2. Verify the share was sent to correct email
3. Ask sharer to re-send invitation
4. Check spam folder for sharing notification

---

## Technical Details

### Architecture

The dashboard customization system is built on the following components:

| Component | Technology | Purpose |
|-----------|------------|---------|
| Layout Engine | react-grid-layout | Drag-and-drop widget positioning |
| State Persistence | DynamoDB | Dashboard configurations and sharing |
| Local Cache | localStorage | Fast layout restoration on page load |
| Widget Data | REST API | Real-time data fetching per widget |
| Audit Logging | DynamoDB Streams + EventBridge | Compliance event tracking |

### Widget Types

| Type | Display | Use Case |
|------|---------|----------|
| **Metric** | Single value with trend indicator | KPIs, counts, scores |
| **Chart (Line)** | Time series visualization | Trends over time |
| **Chart (Bar)** | Categorical comparison | Team/project comparisons |
| **Gauge** | Circular percentage indicator | Utilization, capacity |
| **Progress** | Linear progress bar | Completion percentages |
| **Table** | Tabular data display | Lists, recent items |
| **Status Grid** | Multi-item status indicators | Health checks, environments |
| **Activity Feed** | Chronological event stream | Alerts, notifications |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dashboards` | GET | List user dashboards |
| `/api/v1/dashboards` | POST | Create new dashboard |
| `/api/v1/dashboards/{id}` | PUT | Update dashboard |
| `/api/v1/dashboards/{id}/clone` | POST | Clone dashboard |
| `/api/v1/dashboards/{id}/share` | POST | Share with users/teams |
| `/api/v1/widgets/catalog` | GET | List available widgets |

For complete API documentation, see [REST API Reference](../../support/api-reference/rest-api.md).

---

## Related Documentation

- [Vulnerability Remediation](./vulnerability-remediation.md) - Metrics shown in security widgets
- [Team Collaboration](./team-collaboration.md) - Sharing with team members
- [API Reference: Dashboard Endpoints](../../support/api-reference/rest-api.md) - Programmatic dashboard access
- [Architecture: Dashboard Design](../../support/architecture/system-overview.md) - Technical implementation
- [ADR-064: Customizable Dashboard Widgets](../../architecture-decisions/ADR-064-customizable-dashboard-widgets.md) - Architecture decision record
