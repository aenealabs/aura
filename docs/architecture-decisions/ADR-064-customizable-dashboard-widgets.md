# ADR-064: Customizable Dashboard Widgets

## Status

Deployed

## Date

2026-01-23

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-23 | Approve with modifications |
| Tom | Senior Database Engineer | 2026-01-23 | Approve with schema revisions |
| Design Review | UI/UX Designer | 2026-01-23 | Approve with UX refinements |
| Product Review | Senior AI Product Manager | 2026-01-23 | Approve with scope clarification |

### Review Summary

**Architecture team:**
- Recommended schema redesign using SHARE# records instead of `shared_with` list
- Suggested Widget Data Service for thundering herd prevention
- Identified need for optimistic locking with version attribute

**Tom (Database Engineer):**
- Proposed 3 GSIs: DashboardIdIndex, RoleDefaultIndex, OrgDashboardIndex
- Recommended against list attributes for sharing (query limitations)
- Suggested audit trail via DynamoDB Streams

**Design Review:**
- Provided detailed wireframes for dashboard editor and widget library
- Recommended progressive disclosure for complexity management
- Emphasized role-based onboarding flow

**Product Review:**
- Noted existing implementation is ~80% complete (MetricCard, CustomerHealthDashboard, etc.)
- Recommended adding success metrics and KPIs
- Stressed audit logging as Phase 1 compliance requirement

## Context

The current Aura dashboard provides a one-size-fits-all view that doesn't account for different user personas and their unique priorities. Different roles have fundamentally different needs:

| Persona | Primary Focus |
|---------|---------------|
| Security Engineer | Vulnerabilities, MTTR, CVE trends, approval queue |
| DevOps Lead | Sandbox usage, agent health, deployment velocity |
| Engineering Manager | Team productivity, code quality trends |
| CISO/Executive | Risk posture, compliance %, cost trends |

Rich metrics exist throughout Aura (Trust Center, Agent Registry, Environments, GPU Workloads) but aren't surfaced on the main dashboard in a way that allows users to customize their view.

### Existing Implementation (~80% Complete)

The Aura frontend already has substantial widget infrastructure:

| Component | Location | Status |
|-----------|----------|--------|
| MetricCard | `frontend/src/components/ui/MetricCard.jsx` | Production |
| DashboardMetricCard | `frontend/src/components/dashboard/MetricCard.jsx` | Production |
| MetricCardGrid | Both MetricCard files | Production |
| CustomerHealthDashboard | `frontend/src/components/CustomerHealthDashboard.jsx` | Production |
| Sparkline charts | MetricCard components | Production |
| StatusBadge | MetricCard components | Production |
| TrendIndicator | MetricCard components | Production |
| Loading skeletons | MetricCard components | Production |
| Error states | DashboardMetricCard | Production |

**Gap Analysis:** Missing drag-drop layout, dashboard persistence, widget library UI, and role-based defaults.

### Industry Research

| Platform | Storage | Format | Key Feature |
|----------|---------|--------|-------------|
| Grafana | PostgreSQL/MySQL | JSON | Provisioning via ConfigMaps, API-first |
| Datadog | Server-side (SaaS) | JSON | Template variables, dashboard lists |
| Splunk | KV Store + Files | JSON-in-XML | Dashboard Studio, drilldowns |

## Decision

Implement a customizable dashboard system with DynamoDB persistence, role-based defaults, and a drag-drop layout editor. Focus Phase 1 on completing the remaining ~20% gap rather than rebuilding existing functionality.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Aura Frontend                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                 Dashboard Editor                             │    │
│  │  • Widget Library Drawer   • Grid Layout (react-grid-layout) │    │
│  │  • Role Default Selector   • Save/Load Controls              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Dashboard Service (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Dashboard    │  │ Widget Data  │  │ Audit Logger             │   │
│  │ Manager      │  │ Aggregator   │  │                          │   │
│  │              │  │              │  │ • Change tracking        │   │
│  │ • CRUD       │  │ • Data fetch │  │ • Compliance events      │   │
│  │ • Clone      │  │ • Caching    │  │ • User attribution       │   │
│  │ • Share      │  │ • Rate limit │  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
      │  DynamoDB   │      │  DynamoDB   │      │ EventBridge │
      │  Dashboards │      │  Streams    │      │  Audit Bus  │
      └─────────────┘      └─────────────┘      └─────────────┘
```

### Data Model (Revised per Agent Feedback)

**DynamoDB Table:** `aura-dashboard-configs-{env}`

Following DynamoDB single-table design best practices with separate records for sharing relationships:

#### Primary Records

| Record Type | PK | SK | Attributes |
|-------------|----|----|------------|
| Dashboard | `USER#{user_id}` | `DASHBOARD#{dashboard_id}` | name, description, layout_json, widgets_json, is_default, version, created_at, updated_at |
| Role Default | `ROLE#{role}` | `DEFAULT` | dashboard_id, created_by, created_at |
| Share Record | `SHARE#{dashboard_id}` | `USER#{shared_with_user_id}` | permission (view/edit), shared_by, shared_at |
| Org Share | `SHARE#{dashboard_id}` | `ORG#{org_id}` | permission (view), shared_by, shared_at |

#### Global Secondary Indexes

| GSI | PK | SK | Purpose |
|-----|----|----|---------|
| DashboardIdIndex | dashboard_id | user_id | Direct dashboard lookup, clone source validation |
| RoleDefaultIndex | role_default_for | created_at | Fetch role defaults |
| OrgDashboardIndex | org_id | updated_at | List org-shared dashboards |

#### Rationale for Schema Design

1. **SHARE# records vs shared_with list**: DynamoDB doesn't efficiently query list attributes. Separate share records enable querying "who has access to dashboard X" and "what dashboards does user Y have access to" without scanning.

2. **Version attribute**: Enables optimistic locking to prevent concurrent edit conflicts.

3. **DynamoDB Streams**: Enables audit trail without application-level logging overhead. Stream events flow to EventBridge for compliance reporting.

### Widget Types

| Category | Widgets | Data Source |
|----------|---------|-------------|
| **Metrics** | Single value + trend, gauge, progress bar | Existing MetricCard |
| **Charts** | Line/area (time series), bar, donut/pie | New chart components |
| **Tables** | Top N lists, recent activity, paginated data | Existing table patterns |
| **Status** | Agent health, service status, HITL queue | Agent Registry API |
| **Feeds** | Activity stream, alerts, approvals | Security Alerts API |

### Permissions Model

- Widgets respect existing RBAC (users only see data they have access to)
- Dashboard permissions: Owner (full), Editor (modify), Viewer (read-only)
- SuperUser role can view and customize all widgets regardless of data source
- Shared dashboards inherit viewer's permissions (widget shows "No Access" placeholder if unauthorized)

### Role-Based Defaults

| Role | Default Dashboard Layout |
|------|-------------------------|
| security-engineer | 6 widgets: Open Vulns, MTTR, Approval Queue, CVE Trend, Agent Health, Recent Alerts |
| devops | 6 widgets: Sandbox Usage, Deployment Velocity, Agent Health, Environment Status, GPU Jobs, Cost Trend |
| engineering-manager | 5 widgets: Team Activity, Code Quality, PR Velocity, Test Coverage, Sprint Burndown |
| executive | 4 widgets: Risk Posture, Compliance %, Cost Summary, Key Incidents |
| superuser | All widgets available, starts with executive layout |

### UX Design (per Design Wireframes)

#### Dashboard Editor Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Dashboard: My Security View              [Edit Mode Toggle] [Save] [...]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│   │  Widget 1    │ │  Widget 2    │ │  Widget 3    │ │  Widget 4    │      │
│   │  (draggable) │ │  (draggable) │ │  (draggable) │ │  (draggable) │      │
│   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘      │
│                                                                             │
│   ┌───────────────────────────────┐ ┌───────────────────────────────┐      │
│   │        Widget 5 (2x)          │ │        Widget 6 (2x)          │      │
│   │        (draggable)            │ │        (draggable)            │      │
│   └───────────────────────────────┘ └───────────────────────────────┘      │
│                                                                             │
│   [+ Add Widget]                                                            │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

#### Widget Library Slide-Over

```
┌──────────────────────────────────────┐
│  Widget Library                    ✕ │
├──────────────────────────────────────┤
│  [Search widgets...]                 │
│                                      │
│  ▾ Security (4)                      │
│    ○ Open Vulnerabilities            │
│    ○ MTTR Trend                      │
│    ○ CVE Timeline                    │
│    ○ Approval Queue                  │
│                                      │
│  ▾ Operations (5)                    │
│    ○ Agent Health Grid               │
│    ○ Sandbox Utilization             │
│    ○ Deployment History              │
│    ○ GPU Job Queue                   │
│    ○ Environment Status              │
│                                      │
│  ▾ Analytics (3)                     │
│    ○ Code Quality Score              │
│    ○ Test Coverage Trend             │
│    ○ PR Velocity                     │
│                                      │
│  ▸ Compliance (3)                    │
│  ▸ Cost (2)                          │
│                                      │
│  ────────────────────────────────    │
│  [Preview]           [Add to Board]  │
└──────────────────────────────────────┘
```

### Success Metrics (per product recommendation)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dashboard customization rate | >40% of users create custom dashboard | DynamoDB record count vs. active users |
| Widget engagement | >3 widgets per custom dashboard | Average widgets_json array length |
| Role default usage | >60% of new users start with role default | Onboarding funnel analytics |
| Time to first customization | <5 minutes from onboarding | Session timing events |
| Dashboard load time | <2 seconds (P95) | CloudWatch latency metrics |
| Audit compliance | 100% of changes logged | DynamoDB Streams + EventBridge verification |

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

| Task | Description | Owner |
|------|-------------|-------|
| DynamoDB table | Create table with GSIs, enable Streams | Backend |
| Audit logging | EventBridge integration for compliance | Backend |
| REST API | `/api/v1/dashboards` CRUD endpoints | Backend |
| react-grid-layout | Integrate drag-drop library | Frontend |
| Widget registry | Catalog existing widgets, add metadata | Frontend |
| Save/load | Dashboard persistence hooks | Frontend |
| Role defaults | Pre-configured default dashboards | Full stack |

**Compliance Requirement:** Audit logging must be in Phase 1, not deferred. All dashboard changes (create, update, delete, share) must generate audit events for CMMC compliance.

### Phase 2: Sharing & Collaboration (Week 3-4)

| Task | Description | Owner |
|------|-------------|-------|
| Share modal | Share dashboard with user/team/org | Frontend |
| Clone dashboard | Copy dashboard for modification | Full stack |
| Permission checks | Enforce view/edit permissions | Backend |
| Dashboard templates | Pre-built templates for common use cases | Design |

### Phase 3: Advanced Features (Future)

| Task | Description | Priority |
|------|-------------|----------|
| Custom widget builder | Power users create custom queries | Medium |
| Scheduled reports | Email dashboard snapshots | Low |
| Dashboard embedding | iframe/API for external tools | Low |
| Mobile responsive | Auto-reflow for mobile devices | Deferred |

## Technical Considerations

### Frontend

- **react-grid-layout**: Industry standard drag-drop grid (same as Grafana)
- **Widget lazy loading**: Code-split widget components for performance
- **State management**: React Context or Zustand for dashboard editor state
- **Optimistic updates**: Immediate UI feedback with background sync

### Backend

- **REST API**: `/api/v1/dashboards` (CRUD, clone, share)
- **WebSocket**: Optional real-time widget data updates (Phase 2)
- **Widget Data Service**: Aggregate widget data with staggered fetches to prevent thundering herd
- **Caching**: SWR pattern with TTL based on data freshness requirements

### Performance

- **Virtualize widgets**: Large dashboards (>20 widgets) use windowing
- **Stagger fetches**: Initial widget data loads with 50ms delays
- **Client caching**: React Query with stale-while-revalidate
- **CDN**: Dashboard templates cached at CloudFront edge

## API Specification

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dashboards` | GET | List user's dashboards |
| `/api/v1/dashboards` | POST | Create new dashboard |
| `/api/v1/dashboards/{id}` | GET | Get dashboard by ID |
| `/api/v1/dashboards/{id}` | PUT | Update dashboard |
| `/api/v1/dashboards/{id}` | DELETE | Delete dashboard |
| `/api/v1/dashboards/{id}/clone` | POST | Clone dashboard |
| `/api/v1/dashboards/{id}/share` | POST | Share dashboard |
| `/api/v1/dashboards/{id}/share/{user_id}` | DELETE | Revoke share |
| `/api/v1/dashboards/defaults/{role}` | GET | Get role default |
| `/api/v1/widgets/catalog` | GET | List available widgets |

### Request/Response Examples

**Create Dashboard:**
```json
POST /api/v1/dashboards
{
  "name": "My Security Dashboard",
  "description": "Custom view for daily security review",
  "layout_json": {
    "columns": 4,
    "rowHeight": 100,
    "items": [
      {"i": "widget-1", "x": 0, "y": 0, "w": 1, "h": 2},
      {"i": "widget-2", "x": 1, "y": 0, "w": 2, "h": 2}
    ]
  },
  "widgets_json": [
    {"id": "widget-1", "type": "metric", "source": "vulnerabilities/open"},
    {"id": "widget-2", "type": "chart", "source": "vulnerabilities/trend"}
  ]
}
```

**Response:**
```json
{
  "dashboard_id": "01HQ...",
  "name": "My Security Dashboard",
  "version": 1,
  "created_at": "2026-01-23T10:00:00Z",
  "updated_at": "2026-01-23T10:00:00Z"
}
```

## Consequences

### Positive

- Users can focus on metrics relevant to their role
- Increased platform engagement and stickiness
- Leverages existing 80% widget implementation
- Compliance-ready with built-in audit logging
- Industry-standard patterns (Grafana-like experience)

### Negative

- Additional DynamoDB costs (minimal, pay-per-request)
- Frontend bundle size increase (~50KB for react-grid-layout)
- Complexity in permission inheritance for shared dashboards
- Need to maintain role default dashboards as features evolve

### Neutral

- Mobile support deferred to future phase
- Real-time collaboration deferred to Phase 3

## Open Questions

1. ~~Should widget refresh intervals be user-configurable or fixed per widget type?~~ **Decision: Fixed per widget type for Phase 1, user-configurable in Phase 3**
2. ~~Maximum number of dashboards per user?~~ **Decision: 10 dashboards per user (soft limit, configurable)**
3. ~~Dashboard versioning/history?~~ **Decision: Version attribute for optimistic locking; full history in Phase 3**
4. ~~Audit logging for dashboard changes?~~ **Decision: Required in Phase 1 via DynamoDB Streams + EventBridge**

## References

- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/json-model/)
- [Datadog Dashboards API](https://docs.datadoghq.com/api/latest/dashboards/)
- [react-grid-layout](https://github.com/react-grid-layout/react-grid-layout)
- [DynamoDB Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table-design/)
- Original Proposal: `docs/research/proposals/customizable-dashboard-widgets.md`
