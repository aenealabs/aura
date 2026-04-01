# Customizable Dashboard Widgets Proposal

**Status:** Converted to ADR
**Created:** 2026-01-23
**Author:** Platform Team
**ADR:** [ADR-064](../../architecture-decisions/ADR-064-customizable-dashboard-widgets.md)

> **Note:** This proposal has been reviewed by specialized agents and converted to ADR-064. See the ADR for the finalized design with agent feedback incorporated.

---

## Overview

Enable platform users to customize their dashboard view with configurable widgets, role-based defaults, and personal saved layouts. This increases user engagement and allows different personas to focus on metrics relevant to their role.

---

## Problem Statement

The current dashboard provides a one-size-fits-all view. Different user personas have different priorities:

| Persona | Primary Focus |
|---------|---------------|
| Security Engineer | Vulnerabilities, MTTR, CVE trends, approval queue |
| DevOps Lead | Sandbox usage, agent health, deployment velocity |
| Engineering Manager | Team productivity, code quality trends |
| CISO/Executive | Risk posture, compliance %, cost trends |

Rich metrics exist throughout Aura (Trust Center, Agent Registry, Environments, GPU Workloads) but aren't surfaced on the main dashboard.

---

## Proposed Solution

### Core Capabilities

1. **Widget Library** - Catalog of available widgets with various data sources
2. **Drag-Drop Layout** - Grid-based dashboard editor
3. **Personal Views** - Users can save custom dashboard configurations
4. **Role-Based Defaults** - Pre-configured dashboards per persona
5. **SuperUser Override** - Full access to all widgets and customization

### Data Model

```
DynamoDB Table: aura-dashboard-configs-{env}

PK: USER#{user_id}
SK: DASHBOARD#{dashboard_id}

Attributes:
- dashboard_id (ULID)
- name
- description
- layout_json (widget positions, sizes, grid config)
- widgets_json (widget configs, data sources, refresh intervals)
- is_default (boolean)
- role_default_for (optional: "security_engineer", "devops", "executive", "superuser")
- created_at
- updated_at
- shared_with (list of user_ids or "org")

GSI: RoleDefaultIndex
- PK: ROLE#{role}
- SK: DEFAULT
```

### Widget Types

| Category | Widgets |
|----------|---------|
| **Metrics** | Single value + trend, gauge, progress bar |
| **Charts** | Line/area (time series), bar, donut/pie |
| **Tables** | Top N lists, recent activity, paginated data |
| **Status** | Agent health, service status, HITL queue |
| **Feeds** | Activity stream, alerts, approvals |

### Permissions Model

- Widgets respect existing RBAC
- Users only see widgets for data they have access to
- SuperUser role can view and customize all widgets
- Shared dashboards inherit viewer's permissions (widget shows "No Access" if unauthorized)

---

## Implementation Phases

### Phase 1: Foundation (Current Focus)
- [ ] DynamoDB table and API endpoints
- [ ] Widget component library (10-15 core widgets)
- [ ] Dashboard grid layout with drag-drop
- [ ] Save/load personal dashboards
- [ ] Role-based default dashboards

### Phase 2: Sharing & Collaboration
- [ ] Share dashboard with team/org
- [ ] Clone dashboard functionality
- [ ] Dashboard templates marketplace
- [ ] Export/import dashboard JSON

### Phase 3: Advanced Features
- [ ] Custom metrics/queries (power users)
- [ ] Scheduled reports from dashboards
- [ ] Dashboard embedding (iframe/API)
- [ ] Real-time collaboration (live cursors)

---

## Future Consideration: Mobile Support

**Deferred to future phase.** Two approaches were evaluated:

### Option A: Responsive Layout (Recommended for Future)
- Single layout auto-reflows based on breakpoints
- Grid columns: 4 (desktop) → 2 (tablet) → 1 (mobile)
- Widgets define min/max sizes
- Lower maintenance, faster to ship

### Option B: Separate Mobile Views
- Explicitly designed mobile dashboard
- Different widget selection optimized for mobile
- Better UX but 2x maintenance burden

**Decision:** When mobile becomes a priority, start with responsive layout (Option A) using a library like react-grid-layout. Add optional "mobile override" per dashboard if needed.

---

## Technical Considerations

### Frontend
- Use react-grid-layout for drag-drop grid (same as Grafana)
- Widget components are lazy-loaded
- Dashboard state managed via React Context or Zustand
- Optimistic updates with background sync

### Backend
- REST API: `/api/v1/dashboards` (CRUD operations)
- WebSocket for real-time widget data updates
- Widget data fetched via existing service APIs
- Cache widget responses (TTL based on data freshness needs)

### Performance
- Virtualize widget rendering for large dashboards
- Stagger initial data fetches to avoid thundering herd
- Client-side caching of widget data with SWR/React Query

---

## Industry Reference

| Platform | Storage | Format | Key Feature |
|----------|---------|--------|-------------|
| Grafana | PostgreSQL/MySQL | JSON | Provisioning via ConfigMaps, API-first |
| Datadog | Server-side (SaaS) | JSON | Template variables, dashboard lists |
| Splunk | KV Store + Files | JSON-in-XML | Dashboard Studio, drilldowns |

---

## Open Questions

1. Should widget refresh intervals be user-configurable or fixed per widget type?
2. Maximum number of dashboards per user?
3. Dashboard versioning/history?
4. Audit logging for dashboard changes (compliance requirement)?

---

## References

- [Grafana High Availability Setup](https://grafana.com/docs/grafana/latest/setup-grafana/set-up-for-high-availability/)
- [Datadog Dashboards](https://docs.datadoghq.com/dashboards/)
- [react-grid-layout](https://github.com/react-grid-layout/react-grid-layout)
