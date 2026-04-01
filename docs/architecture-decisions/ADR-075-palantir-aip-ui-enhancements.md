# ADR-075: Palantir AIP Integration UI Enhancements

## Status

Deployed

## Date

2026-01-29

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-29 | Approved |
| Design Review | UI/UX Designer | 2026-01-29 | Approved |
| Pending | Senior Systems Architect | - | - |
| Pending | Test Architect | - | - |

### Review Summary

**Agent Architecture Review** - Approved with comprehensive recommendations:
- 8 new dashboard widgets with role-based defaults
- Configuration UI following existing MCP settings pattern
- Admin panel for circuit breaker and observability metrics
- GovCloud compatibility considerations
- Estimated ~1,650 lines across 7 new files

**Agent Design Review** - Approved with detailed design specifications:
- Apple-inspired widget designs with semantic color coding
- D3.js force-directed graph for attack surface visualization
- 5-step configuration wizard
- Detailed mockups for all 5 use cases
- Accessibility compliance (WCAG 2.1 AA)
- 3-phase implementation timeline

## Context

### Parent ADR

This ADR extends **ADR-074: Palantir AIP Integration** by defining the frontend UI components required to surface the bidirectional data integration in the Aura dashboard.

### Current State

ADR-074 defines the backend architecture for Palantir integration:
- Ontology Bridge Service for bidirectional data sync
- Event stream for real-time updates
- Circuit breaker pattern for resilience
- 5 use cases (threat-informed remediation, DIB supply chain, healthcare compliance, insider threat, compliance drift)

However, ADR-074 does not specify:
- Dashboard widgets for threat intelligence visualization
- Configuration UI for integration setup
- Admin panels for operational monitoring
- User workflows for the 5 use cases

### Gap Analysis

| Capability | ADR-074 | UI Gap |
|------------|---------|--------|
| Threat context retrieval | API defined | No widget to display threat campaigns |
| CVE prioritization | Scoring algorithm defined | No prioritized vulnerability table |
| Asset criticality | CMDB integration defined | No criticality visualization |
| Circuit breaker | Pattern implemented | No status indicator for operators |
| Compliance mapping | Data flow defined | No drift detection dashboard |
| Event stream | Kinesis/SQS architecture | No sync health monitoring |

### Design System Context

Project Aura follows an Apple-inspired design philosophy:

| Element | Specification |
|---------|---------------|
| Primary Brand | `#3B82F6` (Blue) |
| Critical/Error | `#DC2626` (Red) |
| High Priority | `#EA580C` (Orange) |
| Medium Priority | `#F59E0B` (Amber) |
| Success | `#10B981` (Green) |
| Typography | Inter font family |
| Spacing | 8px base unit |
| Accessibility | WCAG 2.1 AA required |

### Existing Widget Infrastructure

ADR-064 established the dashboard widget system:
- Widget registry at `frontend/src/components/dashboard/widgetRegistry.js`
- 18 existing widgets across 5 categories
- Role-based default layouts
- Drag-drop editor with sharing capabilities
- ~16.3K lines, 83 tests

## Decision

Implement comprehensive UI enhancements for ADR-074 Palantir AIP Integration, including:

1. **8 new dashboard widgets** for threat intelligence and integration health
2. **Configuration wizard** for guided integration setup
3. **Admin panel** for circuit breaker and observability monitoring
4. **Data visualizations** for attack surface and compliance drift
5. **User workflow pages** for all 5 use cases

## Architecture

### Component Hierarchy

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PALANTIR UI COMPONENT ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DASHBOARD LAYER                                                             │
│  ───────────────                                                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Dashboard (ADR-064)                               │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │    │
│  │  │ ThreatIntel     │  │ AssetCriticality│  │ PrioritizedVuln │     │    │
│  │  │ Widget          │  │ Widget          │  │ Widget          │     │    │
│  │  │ [NEW]           │  │ [NEW]           │  │ [NEW]           │     │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │    │
│  │  │ EPSSTrend       │  │ SyncStatus      │  │ ComplianceDrift │     │    │
│  │  │ Widget          │  │ Widget          │  │ Widget          │     │    │
│  │  │ [NEW]           │  │ [NEW]           │  │ [NEW]           │     │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │    │
│  │  ┌─────────────────┐  ┌─────────────────┐                          │    │
│  │  │ InsiderRisk     │  │ MTTR            │                          │    │
│  │  │ Widget          │  │ Widget          │                          │    │
│  │  │ [NEW]           │  │ [NEW]           │                          │    │
│  │  └─────────────────┘  └─────────────────┘                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  CONFIGURATION LAYER                                                         │
│  ───────────────────                                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Settings Page                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │ PalantirIntegrationSettings                                  │   │    │
│  │  │ ├── ConnectionStep (URL, auth method)                        │   │    │
│  │  │ ├── AuthenticationStep (credentials, mTLS)                   │   │    │
│  │  │ ├── DataMappingStep (object types, sync frequency)           │   │    │
│  │  │ ├── EventStreamStep (Kafka topics, event types)              │   │    │
│  │  │ └── ReviewStep (summary, consent)                            │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ADMIN LAYER                                                                 │
│  ───────────                                                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Admin Panel                                       │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │    │
│  │  │ CircuitBreaker  │  │ Integration     │  │ EventQueue      │     │    │
│  │  │ Status          │  │ Health          │  │ Monitor         │     │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  VISUALIZATION LAYER                                                         │
│  ───────────────────                                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │    │
│  │  │ AttackSurfaceMap (D3.js)    │  │ ComplianceDriftTimeline     │  │    │
│  │  │ ├── ThreatActorNode         │  │ ├── ControlStatusDot        │  │    │
│  │  │ ├── CVENode                 │  │ ├── RemediationEvent        │  │    │
│  │  │ ├── RepositoryNode          │  │ └── TimelineAxis            │  │    │
│  │  │ └── ExploitEdge             │  │                             │  │    │
│  │  └─────────────────────────────┘  └─────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  SERVICE LAYER                                                               │
│  ─────────────                                                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  palantirApi.js              │  usePalantirSync.js                  │    │
│  │  ├── getActiveThreats()      │  ├── syncStatus                      │    │
│  │  ├── getPrioritizedCVEs()    │  ├── lastSyncTime                    │    │
│  │  ├── getAssetCriticality()   │  ├── circuitBreakerState             │    │
│  │  ├── getComplianceDrift()    │  └── refetch()                       │    │
│  │  └── testConnection()        │                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Widget Specifications

#### 1. Threat Intelligence Widget

**Purpose:** Display real-time threat campaigns from Palantir alongside affected Aura repositories.

```text
┌──────────────────────────────────────────────────────────────────┐
│  Threat Intelligence                                   [Palantir]│
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Active Campaigns                                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐       │
│  │  APT29                  │  │  CVE-2024-5678          │       │
│  │  [Critical] 4 repos     │  │  [High] EPSS: 94.2%     │       │
│  │  Healthcare targeting   │  │  2 repos affected       │       │
│  └─────────────────────────┘  └─────────────────────────┘       │
│                                                                  │
│  Threat-to-Vulnerability Correlation                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  [████████████████████████████████░░░] 97% correlated    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Last sync: 2 min ago   [Refresh]                                │
└──────────────────────────────────────────────────────────────────┘
```

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-active-threats` |
| Category | `THREAT_INTELLIGENCE` (new) |
| Default Size | 2x2 grid units |
| Refresh Interval | 60 seconds |
| Data Source | `GET /api/v1/palantir/threats/active` |
| Role Defaults | security-engineer, executive |

**Component Props:**

```typescript
interface ThreatIntelWidgetProps {
  refreshInterval?: number;  // Default: 60000ms
  maxCampaigns?: number;     // Default: 4
  showCorrelation?: boolean; // Default: true
  onCampaignClick?: (campaignId: string) => void;
}
```

#### 2. CVE Prioritization Widget

**Purpose:** Display vulnerabilities ranked by composite score (EPSS + asset criticality + active threat).

```text
┌──────────────────────────────────────────────────────────────────┐
│  Prioritized Vulnerabilities                     [Full Queue →]  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Priority  CVE              Score    Reason                      │
│  ────────────────────────────────────────────────────────────── │
│  [1]       CVE-2024-1234    98.5     Active campaign + Critical  │
│            [Critical] Log4j  ◉───    asset + 94% EPSS            │
│                                                                  │
│  [2]       CVE-2024-5678    87.2     High EPSS + Healthcare      │
│            [High] XSS        ◉──     targeting                   │
│                                                                  │
│  [3]       CVE-2024-9012    72.1     Business-critical repo +    │
│            [Medium] SSRF     ◉─      known TTP                   │
│                                                                  │
│  Prioritization: EPSS + Asset Criticality + Active Threat        │
└──────────────────────────────────────────────────────────────────┘
```

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-cve-prioritization` |
| Category | `SECURITY` |
| Default Size | 2x3 grid units |
| Refresh Interval | 300 seconds |
| Data Source | `GET /api/v1/palantir/cve/prioritized` |
| Role Defaults | security-engineer, developer |

**Score Visualization:**

```javascript
const scoreThresholds = {
  critical: { min: 90, color: '#DC2626' },  // Red
  high:     { min: 70, color: '#EA580C' },  // Orange
  medium:   { min: 40, color: '#F59E0B' },  // Amber
  low:      { min: 0,  color: '#10B981' }   // Green
};
```

#### 3. Asset Criticality Widget

**Purpose:** Show repository criticality scores from Palantir CMDB.

```text
┌──────────────────────────────────────────────────────────────────┐
│  Asset Criticality                              [View All Assets]│
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Business-Critical Assets         4 repos                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  [████████████████████████████████████] 4/12 repos       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Repository              Criticality    Data Class   Owner       │
│  ────────────────────────────────────────────────────────────── │
│  payment-service         10/10 [████]   Restricted   @jsmith     │
│  auth-gateway            9/10  [███░]   Confidential @mchen      │
│  user-api                8/10  [███░]   Internal     @alee       │
│  analytics-pipeline      6/10  [██░░]   Internal     @bwilson    │
│                                                                  │
│  Source: Palantir CMDB   Updated: 4h ago                         │
└──────────────────────────────────────────────────────────────────┘
```

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-asset-criticality` |
| Category | `OPERATIONS` |
| Default Size | 2x2 grid units |
| Refresh Interval | 3600 seconds |
| Data Source | `GET /api/v1/palantir/assets/criticality` |
| Role Defaults | executive, platform-engineer |

**Data Classification Colors:**

| Classification | Color | Badge Style |
|----------------|-------|-------------|
| Restricted | `#DC2626` | Solid red |
| Confidential | `#EA580C` | Solid orange |
| Internal | `#3B82F6` | Solid blue |
| Public | `#10B981` | Solid green |

#### 4. EPSS Trend Widget

**Purpose:** Display 30-day EPSS score trends for monitored CVEs.

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-epss-trend` |
| Category | `ANALYTICS` |
| Default Size | 2x2 grid units |
| Chart Type | Line chart (p50, p95, p99) |
| Data Source | `GET /api/v1/palantir/epss/trend` |

#### 5. Sync Status Widget

**Purpose:** Real-time status of Ontology object synchronization.

```text
┌──────────────────────────────────────────────────────────────────┐
│  Ontology Sync Health                                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Object Type        Status    Count     Last Sync                │
│  ────────────────────────────────────────────────────────────── │
│  ThreatActor        [●]       247       2 min ago                │
│  Vulnerability      [●]       1,892     2 min ago                │
│  Asset              [●]       156       2 min ago                │
│  Compliance         [◐]       892       12 min ago               │
│                                                                  │
│  Circuit Breaker: [CLOSED]   Queue: 0 events                     │
└──────────────────────────────────────────────────────────────────┘
```

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-sync-status` |
| Category | `OPERATIONS` |
| Default Size | 2x2 grid units |
| Refresh Interval | 30 seconds |
| Data Source | `GET /api/v1/palantir/sync/status` |

#### 6. Compliance Drift Widget

**Purpose:** Display compliance control failures requiring remediation.

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-compliance-drift` |
| Category | `COMPLIANCE` |
| Default Size | 2x2 grid units |
| Data Source | `GET /api/v1/palantir/compliance/drift` |
| Role Defaults | compliance-officer, security-engineer |

#### 7. Insider Risk Widget

**Purpose:** Count of users with elevated risk scores requiring scrutiny.

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-insider-risk` |
| Category | `SECURITY` |
| Default Size | 1x1 grid units |
| Data Source | `GET /api/v1/palantir/insider/count` |
| Role Defaults | security-engineer (RBAC restricted) |

#### 8. Threat-Informed MTTR Widget

**Purpose:** Compare MTTR for threat-prioritized vs. standard vulnerabilities.

**Specifications:**

| Property | Value |
|----------|-------|
| Widget ID | `palantir-remediation-mttr` |
| Category | `METRICS` |
| Default Size | 1x1 grid units |
| Data Source | `GET /api/v1/palantir/metrics/mttr` |
| Role Defaults | executive, security-engineer |

### Widget Registry Update

Add to `frontend/src/components/dashboard/widgetRegistry.js`:

```javascript
// New category for Palantir integration
export const WidgetCategory = {
  ...existingCategories,
  THREAT_INTELLIGENCE: 'threat_intelligence',
};

// Palantir widgets
export const palantirWidgets = {
  'palantir-active-threats': {
    id: 'palantir-active-threats',
    name: 'Active Threat Campaigns',
    description: 'Real-time threat campaigns from Palantir AIP',
    category: WidgetCategory.THREAT_INTELLIGENCE,
    component: 'ThreatIntelWidget',
    defaultSize: { w: 2, h: 2 },
    minSize: { w: 2, h: 2 },
    maxSize: { w: 4, h: 3 },
    defaultRefreshSeconds: 60,
    requiredIntegration: 'palantir_aip',
    requiredRoles: ['security-engineer', 'admin'],
  },
  'palantir-cve-prioritization': {
    id: 'palantir-cve-prioritization',
    name: 'Threat-Prioritized CVEs',
    description: 'CVEs ranked by EPSS + criticality + active threat',
    category: WidgetCategory.SECURITY,
    component: 'PrioritizedVulnsWidget',
    defaultSize: { w: 2, h: 3 },
    minSize: { w: 2, h: 2 },
    maxSize: { w: 4, h: 4 },
    defaultRefreshSeconds: 300,
    requiredIntegration: 'palantir_aip',
  },
  // ... additional widgets
};
```

### Configuration Wizard

#### 5-Step Wizard Flow

```text
┌─────────────────────────────────────────────────────────────────┐
│  Connect to Palantir AIP                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1     Step 2     Step 3     Step 4     Step 5            │
│  [●]────────[○]────────[○]────────[○]────────[○]               │
│  Connection  Auth      Data       Events     Review             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Step 1: Connection Details**

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| Instance URL | URL | Yes | HTTPS, valid domain |
| Authentication Method | Radio | Yes | Service Account / SAML |

**Step 2: Authentication**

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| Client ID | Text | Yes | Non-empty |
| Client Secret | Password | Yes | Min 32 chars |
| mTLS Certificate | Textarea | Conditional | Valid PEM format |
| Test Connection | Button | - | Returns success/failure |

**Step 3: Data Mapping**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| ThreatActor sync | Checkbox | No | Checked |
| Vulnerability sync | Checkbox | No | Checked |
| Asset sync | Checkbox | No | Checked |
| Compliance sync | Checkbox | No | Unchecked |
| Sync Frequency | Select | Yes | Hourly |
| Retention Period | Select | Yes | 7 days |

**Step 4: Event Stream**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| VulnerabilityDetected | Checkbox | No | Checked |
| PatchGenerated | Checkbox | No | Checked |
| RemediationComplete | Checkbox | No | Checked |
| HITLApproval | Checkbox | No | Checked |
| Stream Target | Select | Yes | Kafka |
| Topic Prefix | Text | Yes | `aura.{tenant_id}.` |

**Step 5: Review & Confirm**

- Summary of all configuration
- Data sharing consent checkbox
- Enable Integration button

### Circuit Breaker Status Component

```text
┌──────────────────────────────────────────────────────────────────┐
│  Circuit Breaker Status                                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  State: [CLOSED] Operational                                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Failure Count: 0 / 5 threshold                          │   │
│  │  [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Timeout: 60s    Half-Open Requests: 3                           │
│                                                                  │
│  [Force Open]  [Reset Failures]                                  │
└──────────────────────────────────────────────────────────────────┘
```

**State Visual Treatments:**

| State | Color | Icon | Animation |
|-------|-------|------|-----------|
| CLOSED | `#10B981` (Green) | CheckCircle | None |
| HALF_OPEN | `#F59E0B` (Amber) | ArrowPath | Rotate 2s |
| OPEN | `#DC2626` (Red) | ExclamationTriangle | Pulse 1s |

### Attack Surface Map (D3.js)

**Node Types:**

| Node Type | Shape | Size | Color | Stroke |
|-----------|-------|------|-------|--------|
| ThreatActor | Hexagon | 48px | `#DC2626` | 2px white |
| CVE (Critical) | Circle | 36px | `#DC2626` | None |
| CVE (High) | Circle | 32px | `#EA580C` | None |
| CVE (Medium) | Circle | 28px | `#F59E0B` | None |
| Repository | Rounded Rect | 40px | `#3B82F6` | None |
| File | Diamond | 24px | `#6B7280` | None |
| Remediated | Any | Same | 30% opacity | 2px `#10B981` |

**Edge Types:**

| Edge Type | Style | Color | Width |
|-----------|-------|-------|-------|
| Exploits (Threat→CVE) | Solid | `#DC2626` | 2px |
| Affects (CVE→Repo) | Dashed | `#EA580C` | 1.5px |
| Contains (Repo→File) | Dotted | `#94A3B8` | 1px |
| Remediation Path | Solid | `#10B981` | 2px, animated |

**Interactions:**

| Action | Behavior |
|--------|----------|
| Click node | Highlight connected paths, show detail sidebar |
| Hover | Tooltip with node details (200ms delay) |
| Drag | Reposition nodes |
| Double-click | Focus and zoom to neighborhood |
| Right-click | Context menu (Navigate to Code, View in Palantir, Start Remediation) |

### Data Freshness Indicator

```javascript
const freshnessThresholds = {
  fresh:   { max: 5,   color: '#10B981', label: 'Just now' },
  stale:   { max: 30,  color: '#F59E0B', label: 'X min ago' },
  expired: { max: 60,  color: '#DC2626', label: 'May be outdated' },
  unknown: { max: null, color: '#6B7280', label: 'Unknown' },
};
```

### API Service Layer

**File:** `frontend/src/services/palantirApi.js`

```javascript
const palantirApi = {
  // Threat Intelligence
  getActiveThreats: () => api.get('/api/v1/palantir/threats/active'),
  getThreatDetails: (id) => api.get(`/api/v1/palantir/threats/${id}`),

  // CVE Prioritization
  getPrioritizedCVEs: (params) => api.get('/api/v1/palantir/cve/prioritized', { params }),
  getCVEContext: (cveId) => api.get(`/api/v1/palantir/cve/${cveId}/context`),

  // Asset Criticality
  getAssetCriticality: () => api.get('/api/v1/palantir/assets/criticality'),
  getRepositoryCriticality: (repoId) => api.get(`/api/v1/palantir/assets/${repoId}`),

  // Compliance
  getComplianceDrift: () => api.get('/api/v1/palantir/compliance/drift'),
  getControlStatus: (controlId) => api.get(`/api/v1/palantir/compliance/${controlId}`),

  // Sync & Health
  getSyncStatus: () => api.get('/api/v1/palantir/sync/status'),
  getCircuitBreakerStatus: () => api.get('/api/v1/palantir/health/circuit-breaker'),
  getIntegrationHealth: () => api.get('/api/v1/palantir/health'),

  // Configuration
  testConnection: (config) => api.post('/api/v1/palantir/test-connection', config),
  saveConfiguration: (config) => api.post('/api/v1/palantir/configuration', config),
  getConfiguration: () => api.get('/api/v1/palantir/configuration'),

  // Admin Actions
  forceCircuitBreaker: (state) => api.post('/api/v1/palantir/circuit-breaker', { state }),
  retryQueuedEvents: () => api.post('/api/v1/palantir/events/retry'),
};
```

**File:** `frontend/src/hooks/usePalantirSync.js`

```javascript
const usePalantirSync = () => {
  const [syncStatus, setSyncStatus] = useState(null);
  const [circuitBreaker, setCircuitBreaker] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Poll sync status every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchStatus, 30000);
    fetchStatus();
    return () => clearInterval(interval);
  }, []);

  return { syncStatus, circuitBreaker, lastSync, isLoading, error, refetch };
};
```

### Integration with Existing Settings

Add to `frontend/src/components/SettingsPage.jsx` navigation:

```javascript
const navGroups = [
  // ... existing groups
  {
    id: 'integrations',
    label: 'Integrations',
    items: [
      // ... existing items
      {
        id: 'palantir',
        label: 'Palantir AIP',
        icon: ShieldExclamationIcon,
        component: PalantirIntegrationSettings,
      },
    ],
  },
];
```

### Integration Provider Entry

Add to `frontend/src/services/integrationApi.js`:

```javascript
palantir_aip: {
  id: 'palantir_aip',
  name: 'Palantir AIP',
  category: 'data_platforms',
  description: 'Enterprise data platform for threat-informed code security',
  icon: 'shield-exclamation',
  authType: 'mtls',
  isImplemented: true,
  govCloudCompatible: true,
  features: [
    'Threat intelligence correlation',
    'Asset criticality scoring',
    'CVE prioritization',
    'Compliance mapping',
    'Bidirectional sync',
  ],
  configFields: [
    { name: 'ontology_url', label: 'Ontology API URL', type: 'url', required: true },
    { name: 'foundry_url', label: 'Foundry API URL', type: 'url', required: true },
    { name: 'api_key', label: 'API Key', type: 'password', required: true },
    { name: 'client_cert', label: 'mTLS Certificate', type: 'textarea', required: true },
    { name: 'tenant_id', label: 'Organization ID', type: 'text', required: true },
    { name: 'sync_frequency', label: 'Sync Frequency', type: 'select',
      options: ['hourly', '6h', '12h', 'daily'], required: true },
    { name: 'object_types', label: 'Object Types', type: 'tags', required: true },
  ],
},
```

## Use Case Workflows

### Use Case 1: Threat-Informed Remediation

**3-Step Workflow:**

1. **Alert Notification** - Toast/banner when active campaign affects user's repos
2. **Prioritized Queue** - Table showing repos ranked by composite score
3. **Patch Approval** - Detail view with threat context, proposed patch, sandbox results

### Use Case 2: DIB Supply Chain Security

**Dashboard View:**
- Vendor risk alert banner
- Dependency graph showing affected repos
- SBOM compliance status card
- Remediation option cards (upgrade vs. replace)

### Use Case 3: Healthcare HIPAA Compliance

**Integration Points:**
- PHI Handling badge on repository cards
- HIPAA Control Mapping section in patch details
- Evidence generation for compliance audits

### Use Case 4: Insider Threat Detection

**Elevated Scrutiny UI:**
- User risk escalation banner (RBAC restricted)
- Behavioral indicators list
- Suspicious pattern scan results
- Escalation actions (SOC, access revocation)

### Use Case 5: Compliance Drift Detection

**Workflow:**
1. Control failure notification
2. Code-to-control mapping display
3. Automated remediation patches table
4. Evidence package generation

## Accessibility Requirements

### WCAG 2.1 AA Compliance

| Requirement | Implementation |
|-------------|----------------|
| Color Independence | Icons + color + text labels for all states |
| Keyboard Navigation | All interactive elements in tab order |
| Screen Reader | ARIA labels, live regions for status changes |
| Focus Management | Visible focus rings, trap focus in modals |
| Reduced Motion | Respect `prefers-reduced-motion` |

### Specific Implementations

**Circuit Breaker (Screen Reader):**
```jsx
<div
  role="status"
  aria-live="polite"
  aria-label={`Circuit breaker status: ${state}. ${description}`}
>
  {/* Visual indicator */}
</div>
```

**Attack Surface Map:**
```jsx
<div
  role="img"
  aria-label="Attack surface visualization showing threat actors, vulnerabilities, and affected repositories"
>
  {/* Provide sortable data table alternative */}
</div>
```

## GovCloud Compatibility

Per ADR-074 GovCloud requirements:

| Requirement | UI Implementation |
|-------------|-------------------|
| PrivateLink URLs | Use relative API paths, no hardcoded URLs |
| FIPS-compliant | Note FIPS requirements on credential inputs |
| IL5 data handling | ABAC-gated detail views for sensitive data |
| No external CDN | Bundle all fonts, icons locally |

## Implementation Phases

### Phase 1: Core Widgets (Week 1-2)

| Component | LOC | Priority |
|-----------|-----|----------|
| IntegrationHealthCard | 150 | P0 |
| CircuitBreakerIndicator | 100 | P0 |
| DataFreshnessIndicator | 80 | P0 |
| ThreatIntelWidget | 250 | P0 |
| SyncStatusWidget | 150 | P0 |
| palantirApi.js service | 200 | P0 |
| usePalantirSync.js hook | 100 | P0 |
| **Phase 1 Total** | **~1,030** | |

### Phase 2: Data Visualizations (Week 3-4)

| Component | LOC | Priority |
|-----------|-----|----------|
| PrioritizedVulnsWidget | 300 | P1 |
| AssetCriticalityWidget | 250 | P1 |
| ComplianceDriftWidget | 200 | P1 |
| EPSSTrendWidget | 200 | P1 |
| InsiderRiskWidget | 100 | P1 |
| MTTRWidget | 100 | P1 |
| **Phase 2 Total** | **~1,150** | |

### Phase 3: Advanced Features (Week 5-6)

| Component | LOC | Priority |
|-----------|-----|----------|
| PalantirIntegrationSettings (Wizard) | 500 | P1 |
| AttackSurfaceMap (D3) | 400 | P2 |
| ComplianceDriftTimeline | 250 | P2 |
| Use case workflow pages | 600 | P2 |
| **Phase 3 Total** | **~1,750** | |

### Total Implementation

| Metric | Value |
|--------|-------|
| Total Components | ~15 new files |
| Total Lines of Code | ~3,930 |
| Estimated Tests | ~150 (38 tests per 1K LOC) |
| Widget Registry Updates | 8 new entries |
| Settings Page Updates | 1 new tab |
| API Service Methods | ~15 methods |

## File Structure

```
frontend/src/
├── components/
│   ├── dashboard/
│   │   ├── widgets/
│   │   │   ├── ThreatIntelWidget.jsx
│   │   │   ├── PrioritizedVulnsWidget.jsx
│   │   │   ├── AssetCriticalityWidget.jsx
│   │   │   ├── EPSSTrendWidget.jsx
│   │   │   ├── SyncStatusWidget.jsx
│   │   │   ├── ComplianceDriftWidget.jsx
│   │   │   ├── InsiderRiskWidget.jsx
│   │   │   └── MTTRWidget.jsx
│   │   └── widgetRegistry.js (updated)
│   ├── palantir/
│   │   ├── AttackSurfaceMap.jsx
│   │   ├── CircuitBreakerIndicator.jsx
│   │   ├── DataFreshnessIndicator.jsx
│   │   ├── IntegrationHealthCard.jsx
│   │   └── ComplianceDriftTimeline.jsx
│   └── settings/
│       └── PalantirIntegrationSettings.jsx
├── hooks/
│   └── usePalantirSync.js
├── services/
│   ├── palantirApi.js
│   └── integrationApi.js (updated)
└── pages/
    └── palantir/
        ├── ThreatRemediationWorkflow.jsx
        ├── SupplyChainDashboard.jsx
        ├── ComplianceDriftPage.jsx
        └── InsiderThreatPage.jsx
```

## Testing Strategy

### Unit Tests

| Component | Test Coverage |
|-----------|---------------|
| Widgets | Render, loading, error states, refresh |
| CircuitBreaker | All 3 states, transitions, animations |
| Wizard | Step navigation, validation, submission |
| API Service | Request/response, error handling |

### Integration Tests

| Scenario | Coverage |
|----------|----------|
| Widget data fetch | Mock API responses |
| Configuration save | Settings persistence |
| Circuit breaker updates | Real-time state changes |

### E2E Tests

| Flow | Coverage |
|------|----------|
| Integration setup wizard | Full 5-step flow |
| Threat remediation workflow | Alert to approval |
| Dashboard widget interaction | Click-through to details |

## Consequences

### Positive

- **Enhanced visibility**: Security teams can see Palantir threat intelligence in Aura dashboard
- **Streamlined workflows**: 5 use cases have dedicated UI flows
- **Operational awareness**: Admins can monitor integration health
- **Consistent UX**: Follows existing design system and widget patterns
- **Accessibility**: WCAG 2.1 AA compliance maintained

### Negative

- **Increased complexity**: 15 new components to maintain
- **Bundle size**: D3.js for attack surface visualization adds ~100KB
- **Testing burden**: ~150 new tests required

### Neutral

- **Feature flag required**: Widgets only visible when Palantir integration enabled
- **Role-based visibility**: Some widgets restricted by RBAC

## Related ADRs

- **ADR-074**: Palantir AIP Integration (parent architecture)
- **ADR-064**: Customizable Dashboard Widgets (widget infrastructure)
- **ADR-073**: Attribute-Based Access Control (role-gated widgets)
- **ADR-069**: Guardrail Configuration UI (settings pattern)

## Implementation Resources

### Design Files

- Widget mockups in Figma (to be created)
- Attack surface map interaction spec (to be created)

### Documentation Updates

- `docs/product/user-guides/palantir-integration.md` (to be created)
- `docs/support/api-reference/palantir-api.md` (to be created)

### Infrastructure Dependencies

- ADR-074 backend services must be deployed first
- API endpoints must be available before UI implementation

## Implementation Notes

### IntegrationHub Wiring (Jan 29, 2026)

The Palantir AIP integration has been fully wired into the platform's Integration Hub, accessible via `/integrations`.

**Changes to `frontend/src/services/integrationApi.js`:**

1. **New Category Added:**
   ```javascript
   threat_intelligence: {
     id: 'threat_intelligence',
     name: 'Threat Intelligence',
     description: 'Enterprise threat intelligence and data platforms',
     icon: 'shield-exclamation',
   }
   ```

2. **Provider Definition:**
   ```javascript
   palantir_aip: {
     id: 'palantir_aip',
     name: 'Palantir AIP',
     category: 'threat_intelligence',
     description: 'Enterprise data platform for threat intelligence, asset criticality, and compliance correlation',
     authType: 'api_key_mtls',
     isImplemented: true,
     govCloudCompatible: true,
     features: [
       'Threat intelligence correlation',
       'Asset criticality from CMDB',
       'EPSS score trends',
       'Compliance drift detection',
       'Insider risk monitoring',
       'Ontology sync with circuit breaker',
     ],
     configFields: [
       { name: 'ontology_api_url', label: 'Ontology API URL', type: 'url', required: true },
       { name: 'foundry_api_url', label: 'Foundry API URL', type: 'url', required: true },
       { name: 'api_key', label: 'API Key', type: 'password', required: true },
       { name: 'client_cert_path', label: 'mTLS Certificate Path', type: 'text', required: false },
       { name: 'sync_frequency', label: 'Sync Frequency', type: 'select', required: true },
       { name: 'object_types', label: 'Object Types to Sync', type: 'tags', required: true },
       { name: 'event_stream_target', label: 'Event Stream Target', type: 'select', required: false },
     ],
     supportedObjectTypes: ['ThreatActor', 'Vulnerability', 'Asset', 'Repository', 'Compliance'],
   }
   ```

**Changes to `frontend/src/components/integrations/IntegrationHub.jsx`:**

1. **Category Configuration:** Added `threat_intelligence` to `CATEGORY_CONFIG` with critical-level styling (red theme)
2. **Modal Import:** Added import for `PalantirIntegrationSettings` component
3. **Modal Routing:** Added case for `palantir_aip` in `renderConfigModal()` switch statement
4. **Category Order:** Added `threat_intelligence` to `categoryOrder` array (first position for visibility)

**User Experience:**

1. Navigate to `/integrations` (Integration Hub)
2. Click "Add Integration" button
3. "Threat Intelligence" category appears first with Palantir AIP option
4. Click to open the 5-step configuration wizard:
   - Step 1: Connection Details (Ontology/Foundry URLs)
   - Step 2: Authentication (API Key, mTLS)
   - Step 3: Data Mapping (Object types, sync frequency)
   - Step 4: Event Stream (Kafka/EventBridge/Kinesis)
   - Step 5: Review & Confirm

**Test Coverage:**

All 103 Palantir-related frontend tests pass:
- `palantirApi.test.js` - API service tests
- `usePalantirSync.test.js` - Hook tests
- `CircuitBreakerIndicator.test.jsx` - Component tests
- `PalantirIntegrationSettings.test.jsx` - Wizard tests
- `SyncStatusWidget.test.jsx` - Widget tests
- `IntegrationHub.test.jsx` - Integration tests (includes Palantir wiring)
