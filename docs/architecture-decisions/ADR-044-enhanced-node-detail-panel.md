# ADR-044: Enhanced Node Detail Panel for GraphRAG Explorer

**Status:** Deployed
**Date:** 2025-12-18 | **Deployed:** 2025-12-31
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-024 (Titan Neural Memory), ADR-034 (Context Engineering Implementation)

---

## Executive Summary

This ADR documents the decision to enhance the GraphRAG Explorer's Node Detail Panel with semantic descriptions, relationship visualization, and actionable interactions. The enhancement enables users to understand not just what a node is, but what it does and what it affects.

**Key Outcomes:**
- AI-generated descriptions for each node (140 char limit, pre-computed)
- Collapsible relationship sections showing connected nodes by direction
- Clickable relationships that navigate to connected nodes in the graph
- Action bar with Center, Copy ID, Filter, and Open Code functionality
- Tiered description generation (Haiku for basic, Sonnet for impact analysis)

---

## Context

### Current State

The GraphRAG Explorer (`frontend/src/components/CKGEConsole.jsx`) provides a visual interface for exploring the code knowledge graph. The Node Detail Panel currently shows:

| Node Type | Current Properties |
|-----------|-------------------|
| File | Path, Lines of Code |
| Class | Methods count, Attributes count |
| Function | Complexity score, Call count |
| Dependency | Version, Risk level |
| Vulnerability | Severity, CWE identifier |

While this metadata is useful, it lacks **semantic context**:
- Users cannot understand *what* a node does without reading the source
- Relationships are only visible as edges in the graph, not in the detail panel
- No actionable interactions (copy, filter, navigate)

### Problem Statement

1. **Lack of Context:** Raw metrics (lines, complexity) don't explain purpose or impact
2. **Hidden Relationships:** Users must trace edges visually to understand dependencies
3. **Navigation Friction:** Clicking a node shows details but doesn't help explore connections
4. **No Quick Actions:** Common operations (copy ID, center view) require multiple steps

### Requirements

1. **Semantic Descriptions:** 1-2 sentence explanation of what each node represents
2. **Relationship Display:** Show incoming/outgoing connections grouped by type
3. **Click Navigation:** Allow clicking relationship items to navigate graph
4. **Action Bar:** Quick access to Center, Copy ID, Filter, Open Code
5. **Performance:** Panel updates must be <100ms for pre-computed data
6. **Cost Control:** LLM-generated descriptions must be cost-optimized

---

## Decision

**Implement an Enhanced Node Detail Panel with tiered description generation and relationship visualization.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENHANCED NODE DETAIL ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

                                    USER CLICKS NODE
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React)                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Enhanced NodeDetailPanel                                             │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  HEADER: Icon + Name + Type + Close                            │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │  DESCRIPTION: AI-generated summary (140 chars)                 │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │  PROPERTIES: Type-specific metadata (existing)                 │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │  RELATIONSHIPS:                                                │  │   │
│  │  │    > Incoming (N) - collapsible                                │  │   │
│  │  │    > Outgoing (N) - collapsible                                │  │   │
│  │  │    > Affected by (vulnerabilities)                             │  │   │
│  │  ├────────────────────────────────────────────────────────────────┤  │   │
│  │  │  ACTIONS: [Center] [Copy ID] [Filter] [Open Code]              │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                           │
                          ┌────────────────┴────────────────┐
                          │                                 │
                          ▼                                 ▼
              ┌─────────────────────┐         ┌─────────────────────────────┐
              │ Pre-computed Data   │         │ On-demand Generation        │
              │ (Redis + Neptune)   │         │ (Bedrock API)               │
              │                     │         │                             │
              │ • Basic summary     │         │ • Detailed analysis         │
              │ • Impact summary    │         │ • "Generate Details" button │
              │ • Relationships     │         │ • Cached after first call   │
              │                     │         │                             │
              │ Latency: <100ms     │         │ Latency: 2-3s (cached: <50ms)│
              └─────────────────────┘         └─────────────────────────────┘
```

### Tiered Description Generation Strategy

| Tier | Description Type | LLM Model | When Generated | Storage | Cost/Call |
|------|------------------|-----------|----------------|---------|-----------|
| 1 | Basic Summary | Claude 3 Haiku | Code ingestion | Neptune property | $0.0003 |
| 2 | Impact Summary | Claude 3.5 Sonnet | Nightly batch | Neptune property | $0.003 |
| 3 | Detailed Analysis | Claude 3.5 Sonnet | On-demand (user clicks) | Redis cache | $0.008 |

**Cost Estimate:** ~$42/month for 10,000 nodes

### Neptune Schema Extensions

```gremlin
// Extended node properties for descriptions
g.V().has('entity_id', $entityId)
  .property('summary', 'Authentication service handling JWT validation...')
  .property('impact_summary', 'Affects 12 downstream services...')
  .property('summary_version', '1.0')
  .property('summary_generated_at', '2025-12-18T10:00:00Z')
```

### Relationship Query Pattern

```gremlin
// Fetch 1-hop neighbors with relationship metadata
g.V().has('entity_id', $entityId)
  .bothE()
  .project('type', 'direction', 'connectedNode')
    .by(label())
    .by(choose(inV().has('entity_id', $entityId),
        constant('incoming'), constant('outgoing')))
    .by(otherV().valueMap('entity_id', 'name', 'type', 'summary').by(unfold()))
  .limit(50)
```

---

## UI/UX Specifications

### Panel Layout

```
+--------------------------------------------+
|  HEADER                                    |
|  [Icon]  UserAuthService           [X]    |
|          Class                             |
+--------------------------------------------+
|  DESCRIPTION                               |
|  Handles user authentication and session   |
|  management. Core service with 15 methods. |
+--------------------------------------------+
|  PROPERTIES                                |
|  Methods          15                       |
|  Attributes       8                        |
|  Complexity       Medium                   |
+--------------------------------------------+
|  RELATIONSHIPS                             |
|  ▼ Incoming (7)                            |
|    [imports] AuthController.ts         >   |
|    [imports] SessionMiddleware.ts      >   |
|    [calls]   validateCredentials       >   |
|    + Show 4 more                           |
|  ▶ Outgoing (4)                            |
|  ▶ Affected by (1 vulnerability)           |
+--------------------------------------------+
|  ACTIONS                                   |
|  [Center] [Copy ID] [Filter] [Open]        |
+--------------------------------------------+
```

### Description Specifications

| Property | Value | Rationale |
|----------|-------|-----------|
| Max characters | 140 | Readable in 2-3 lines |
| Font size | 13px | Secondary hierarchy |
| Line height | 1.5 | Comfortable reading |
| Truncation | Ellipsis + "Show more" | Handles edge cases |

### Relationship Display Rules

| Count | Behavior |
|-------|----------|
| 0 | Show "No connections" with muted text |
| 1-5 | Show all items |
| 6-10 | Show 5 + "Show N more" link |
| 10+ | Show 5 + "View all (N)" opens expanded view |

### Action Bar Functions

| Action | Icon | Behavior | Keyboard |
|--------|------|----------|----------|
| Center | ArrowsPointingOutIcon | Pan/zoom to center node | `C` |
| Copy ID | ClipboardIcon | Copy node ID with toast | `Cmd+C` |
| Filter | FunnelIcon | Show only connected nodes | `F` |
| Open | CodeBracketIcon | Open source file (code nodes) | `O` |

---

## API Design

### Get Node Details Endpoint

```
GET /api/v1/graph/nodes/{node_id}
  ?include_relationships=true
  ?relationship_limit=20
  ?generate_description=false
```

**Response:**
```json
{
  "id": "src/services/auth_service.py::AuthService",
  "type": "class",
  "name": "AuthService",
  "summary": "Core authentication service implementing OAuth2 and JWT flows",
  "impact_summary": "Central dependency for all authenticated API endpoints",
  "properties": {
    "methods": 12,
    "attributes": 5,
    "complexity": "medium"
  },
  "relationships": [
    {
      "type": "imports",
      "direction": "incoming",
      "connected_node": {
        "id": "src/controllers/auth_controller.ts::AuthController",
        "name": "AuthController",
        "type": "class"
      }
    }
  ],
  "relationship_count": 15,
  "has_more_relationships": true
}
```

---

## Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React Query)                   │
│                     TTL: 5 minutes                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     ElastiCache (Redis)                      │
│                     TTL: 15 minutes                          │
│                     Key: node:{id}:detail                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Neptune (Source of Truth)                │
│                     Properties: summary, impact_summary      │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Frontend UI Enhancement (Complete)
- [x] Update mock data with `summary`, `impact_summary`, and `relationships`
- [x] Implement enhanced `NodeDetailPanel` component
- [x] Add collapsible relationship groups
- [x] Add action bar with Center, Copy ID, Filter, Open Code functions
- [x] Add `DocumentationLink` component for dependencies and vulnerabilities
- [x] Add `RelationshipSection` component with expand/collapse and "Show more" functionality

### Phase 2: Backend API (Future)
- Create `/api/v1/graph/nodes/{id}` endpoint
- Implement relationship query with pagination
- Add Redis caching layer

### Phase 3: Description Generation (Future)
- Integrate LLM summary generation during code ingestion
- Create nightly batch job for impact summaries
- Implement on-demand detailed analysis endpoint

---

## Alternatives Considered

### Alternative 1: Sidebar Drawer Instead of Panel
**Rejected:** Panel integrates better with existing layout; drawer would occlude graph.

### Alternative 2: Real-time LLM Generation for All Descriptions
**Rejected:** Too expensive (~$0.008 per view) and slow (2-3s latency). Pre-computation is more efficient.

### Alternative 3: Separate "Relationships" Page
**Rejected:** Context switching disrupts exploration flow. Inline display maintains graph context.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM cost overrun | High | Tiered generation; pre-compute 80% |
| Stale descriptions | Medium | Version tracking; re-generate on code change |
| Panel too cluttered | Medium | Collapsible sections; progressive disclosure |
| Slow relationship queries | Medium | Limit to 50 nodes; pagination for large graphs |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Panel load time (pre-computed) | <100ms | P95 latency |
| Description coverage | >90% of nodes | Nodes with non-null summary |
| User engagement | +30% node clicks | Analytics comparison |
| Relationship navigation | 5+ clicks/session | Click-through rate |

---

## References

- [Design Design Recommendations](#) - Panel layout and interaction design
- [Architecture Analysis](#) - Neptune schema and caching strategy
- ADR-024: Titan Neural Memory - Cognitive architecture context
- ADR-034: Context Engineering Implementation - Retrieval patterns

---

## Appendix: Mock Data Schema

```javascript
// Extended mock node for UI prototyping
const MOCK_NODES = [
  {
    id: 'class-1',
    type: 'class',
    label: 'UserController',
    methods: 12,
    attributes: 5,
    // NEW FIELDS
    summary: 'Handles user authentication and session management for the web API.',
    impact_summary: 'Central controller affecting 8 downstream services.',
    relationships: {
      incoming: [
        { type: 'imports', node: { id: 'file-1', label: 'app.ts', type: 'file' } },
      ],
      outgoing: [
        { type: 'calls', node: { id: 'func-1', label: 'validateToken()', type: 'function' } },
      ],
      affected_by: [
        { type: 'affects', node: { id: 'vuln-1', label: 'CVE-2024-1234', type: 'vulnerability' } },
      ],
    },
  },
];
```
