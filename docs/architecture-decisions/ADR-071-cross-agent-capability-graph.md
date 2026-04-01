# ADR-071: Cross-Agent Capability Graph Analysis

## Status

Deployed

## Date

2026-01-27

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Implementation | Claude Code | 2026-01-27 | Deployed |

### Review Summary

**Deployed on 2026-01-27** with the following implementation:

| Component | Location | LOC | Tests |
|-----------|----------|-----|-------|
| Graph Contracts | `src/services/capability_governance/graph_contracts.py` | ~280 | 30 |
| Graph Sync | `src/services/capability_governance/graph_sync.py` | ~350 | 18 |
| Graph Analyzer | `src/services/capability_governance/graph_analyzer.py` | ~600 | 38 |
| REST API | `src/api/capability_graph_endpoints.py` | ~300 | - |
| React Component | `frontend/src/components/capability/CapabilityGraph.jsx` | ~400 | - |
| Hook | `frontend/src/components/capability/useCapabilityGraph.js` | ~100 | - |
| **Total** | | **~2,030** | **86** |

**Key Features Implemented:**
- 5 core analysis methods (escalation paths, coverage gaps, toxic combinations, inheritance tree, effective capabilities)
- PolicyGraphSynchronizer for Neptune sync (mock mode)
- REST API with 10 endpoints
- React force-directed graph visualization
- Color-coded nodes by classification (SAFE/MONITORING/DANGEROUS/CRITICAL)
- Escalation path highlighting

**Filter Functionality (Jan 27, 2026):**
Full interactive filtering implemented in the Capability Graph visualization:

| Filter | Type | Description |
|--------|------|-------------|
| Agent Types | Checkbox (5) | Filter by Coder, Reviewer, Validator, Security, Orchestrator |
| Tool Classification | Toggle badges (4) | SAFE (green), MONITORING (amber), DANGEROUS (orange), CRITICAL (red) |
| Show Escalation Paths | Toggle | Highlights edges in red that are part of detected escalation paths |
| Highlight Coverage Gaps | Toggle | Amber "?" badge on agents with dangerous/critical tools but no monitoring |
| Show Toxic Combinations | Toggle | Pulsing red dashed ring around nodes with toxic tool pairs |
| Risk Threshold | Slider (0-100%) | Filters escalation path highlighting to paths above threshold |

**Visual Indicators:**
- Red arrowhead markers for escalation path edges
- Amber badge with "?" for coverage gap indicators on agent nodes
- Pulsing red dashed ring for toxic combination indicators
- Dynamic legend that shows indicator explanations when filters are active

**Toxic Combination Detection:**
Predefined toxic tool pairs that violate separation of duties:
- `deployment` + `database_access`
- `iam_modify` + `production_access`
- `secrets_manager` + `deployment`
- `file_write` + `production_access`

## Context

### Current State

ADR-066 implemented Agent Capability Governance with per-agent policies, but lacks visibility into cross-agent relationships:

| Aspect | Current State | Gap |
|--------|---------------|-----|
| Policy visibility | Per-agent YAML/code | No holistic view |
| Inheritance analysis | Runtime evaluation | Cannot visualize inheritance trees |
| Escalation paths | Not analyzed | Unknown privilege escalation risks |
| Coverage gaps | Manual review | No automated gap detection |
| Capability relationships | Implicit in code | No explicit graph model |

### Security Risks Without Graph Analysis

```text
Cross-Agent Security Risks:
├── Privilege Escalation Paths
│   ├── AgentA delegates to AgentB which has CRITICAL access
│   ├── Inheritance chain grants unintended capabilities
│   └── Multi-hop escalation invisible in per-agent view
├── Coverage Gaps
│   ├── Agent has DANGEROUS tools but no MONITORING for audit
│   ├── Missing defensive capabilities for risky operations
│   └── Orphaned agents without governance
├── Toxic Combinations
│   ├── Agent has both create_credentials AND access_secrets
│   ├── Conflicting capabilities on same agent
│   └── Capability combinations that violate separation of duties
└── Inheritance Complexity
    ├── Deep inheritance chains hard to reason about
    ├── Override conflicts between parent policies
    └── Circular dependencies possible without detection
```

### Why Neptune Is Ideal

Project Aura already uses Neptune for GraphRAG. Extending it for capability governance provides:

- Native graph traversal for path analysis
- Efficient cycle detection
- Built-in visualization support
- Existing operational expertise

## Decision

Implement Cross-Agent Capability Graph Analysis using Neptune to model, analyze, and visualize capability relationships across the entire agent ecosystem.

## Architecture

### Graph Schema

```text
Neptune Graph Schema for Capability Governance:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPABILITY GRAPH MODEL                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  VERTICES                                                                    │
│  ─────────                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │     Agent       │  │   Capability    │  │     Policy      │             │
│  │                 │  │                 │  │                 │             │
│  │ • id            │  │ • id            │  │ • id            │             │
│  │ • name          │  │ • name          │  │ • version       │             │
│  │ • type          │  │ • classification│  │ • effective_date│             │
│  │ • tier          │  │ • risk_score    │  │ • status        │             │
│  │ • status        │  │ • description   │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                                  │
│  │    Context      │  │   AuditEvent    │                                  │
│  │                 │  │                 │                                  │
│  │ • id            │  │ • id            │                                  │
│  │ • environment   │  │ • timestamp     │                                  │
│  │ • sensitivity   │  │ • decision      │                                  │
│  │ • constraints   │  │ • reason        │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
│                                                                              │
│  EDGES                                                                       │
│  ─────                                                                       │
│  Agent ──[HAS_CAPABILITY]──► Capability                                     │
│         • granted_by: policy_id                                             │
│         • grant_time: timestamp                                             │
│         • expiry: timestamp (optional)                                      │
│         • conditions: json                                                  │
│                                                                              │
│  Agent ──[INHERITS_FROM]──► Agent                                           │
│         • inheritance_order: int                                            │
│         • override_allowed: bool                                            │
│                                                                              │
│  Agent ──[DELEGATES_TO]──► Agent                                            │
│         • scope: list[capability_id]                                        │
│         • max_tier: classification                                          │
│                                                                              │
│  Capability ──[REQUIRES]──► Capability                                      │
│         • dependency_type: prerequisite | corequisite                       │
│                                                                              │
│  Capability ──[CONFLICTS_WITH]──► Capability                                │
│         • conflict_type: mutual_exclusion | separation_of_duties            │
│                                                                              │
│  Policy ──[GOVERNS]──► Agent                                                │
│         • priority: int                                                     │
│                                                                              │
│  Capability ──[RESTRICTED_TO]──► Context                                    │
│         • enforcement: hard | soft                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Analysis Queries

```python
# src/services/capability_governance/graph_analyzer.py

class CapabilityGraphAnalyzer:
    """Analyze capability relationships across agents using Neptune."""

    def __init__(self, neptune_client: NeptuneGraphService):
        self.neptune = neptune_client

    # Query configuration
    MAX_TRAVERSAL_DEPTH = 5  # Prevent exponential path explosion
    QUERY_TIMEOUT_SECONDS = 10  # Fail fast on complex queries

    async def detect_escalation_paths(
        self,
        source_tier: str = "standard",
        target_classification: str = "CRITICAL",
        max_depth: int = None,
    ) -> list[EscalationPath]:
        """
        Find paths where lower-tier agents can reach CRITICAL capabilities.

        Performance considerations:
        - Depth limited to MAX_TRAVERSAL_DEPTH (default 5) to prevent O(n^d) explosion
        - Query timeout of 10 seconds to fail fast
        - simplePath() prevents cycles but still exponential in worst case
        - Results limited to 100 paths; paginate for full analysis

        Gremlin Query:
        g.V().hasLabel('Agent').has('tier', source_tier)
          .repeat(out('INHERITS_FROM', 'DELEGATES_TO').simplePath()).times(5)
          .emit(out('HAS_CAPABILITY').has('classification', target_classification))
          .path()
          .by(valueMap('name', 'tier'))
        """
        depth = max_depth or self.MAX_TRAVERSAL_DEPTH

        query = f"""
        g.V().hasLabel('Agent').has('tier', '{source_tier}')
          .repeat(out('INHERITS_FROM', 'DELEGATES_TO').simplePath())
          .times({depth})
          .emit(out('HAS_CAPABILITY').has('classification', '{target_classification}'))
          .path()
          .limit(100)
        """
        results = await self.neptune.execute_query(
            query,
            timeout_seconds=self.QUERY_TIMEOUT_SECONDS,
        )
        return [self._parse_escalation_path(r) for r in results]

    async def find_coverage_gaps(self) -> list[CoverageGap]:
        """
        Find agents with DANGEROUS capabilities but no MONITORING.

        Agents with destructive capabilities should have audit capabilities.
        """
        query = """
        g.V().hasLabel('Agent')
          .where(out('HAS_CAPABILITY').has('classification', 'DANGEROUS'))
          .where(__.not(out('HAS_CAPABILITY').has('classification', 'MONITORING')))
          .project('agent', 'dangerous_caps')
          .by(valueMap('name', 'tier'))
          .by(out('HAS_CAPABILITY').has('classification', 'DANGEROUS').values('name').fold())
        """
        results = await self.neptune.execute_query(query)
        return [CoverageGap(
            agent_name=r['agent']['name'],
            dangerous_capabilities=r['dangerous_caps'],
            missing="MONITORING capabilities for audit trail",
        ) for r in results]

    async def detect_toxic_combinations(self) -> list[ToxicCombination]:
        """
        Find agents with conflicting capabilities.

        Example: create_credentials + access_secrets violates separation of duties.
        """
        query = """
        g.V().hasLabel('Agent').as('agent')
          .out('HAS_CAPABILITY').as('cap1')
          .out('CONFLICTS_WITH').as('cap2')
          .where(__.select('agent').out('HAS_CAPABILITY').as('cap2'))
          .select('agent', 'cap1', 'cap2')
          .by(valueMap('name'))
          .by(valueMap('name', 'classification'))
          .by(valueMap('name', 'classification'))
        """
        results = await self.neptune.execute_query(query)
        return [ToxicCombination(
            agent_name=r['agent']['name'],
            capability_a=r['cap1']['name'],
            capability_b=r['cap2']['name'],
            conflict_type="separation_of_duties",
        ) for r in results]

    async def get_inheritance_tree(self, agent_name: str) -> InheritanceTree:
        """
        Get full inheritance tree for an agent with all inherited capabilities.
        """
        query = f"""
        g.V().hasLabel('Agent').has('name', '{agent_name}')
          .emit()
          .repeat(out('INHERITS_FROM'))
          .tree()
          .by('name')
          .by(out('HAS_CAPABILITY').values('name').fold())
        """
        result = await self.neptune.execute_query(query)
        return self._parse_inheritance_tree(result)

    async def calculate_effective_capabilities(
        self,
        agent_name: str,
        context: str = "production",
    ) -> EffectiveCapabilities:
        """
        Calculate all capabilities an agent has, including inherited ones.

        Considers:
        - Direct grants
        - Inherited capabilities (with override rules)
        - Context restrictions
        - Active temporary grants
        """
        query = f"""
        g.V().hasLabel('Agent').has('name', '{agent_name}')
          .union(
            identity(),
            repeat(out('INHERITS_FROM')).emit()
          )
          .out('HAS_CAPABILITY')
          .where(
            __.not(out('RESTRICTED_TO'))
            .or()
            .out('RESTRICTED_TO').has('environment', '{context}')
          )
          .dedup()
          .project('name', 'classification', 'source')
          .by('name')
          .by('classification')
          .by(__.in('HAS_CAPABILITY').values('name').fold())
        """
        results = await self.neptune.execute_query(query)
        return EffectiveCapabilities(
            agent_name=agent_name,
            context=context,
            capabilities=[self._parse_capability(r) for r in results],
        )
```

### Visualization API

```python
# src/api/capability_graph_endpoints.py

@router.get("/capability-graph/agent/{agent_name}")
async def get_agent_capability_graph(
    agent_name: str,
    include_inheritance: bool = True,
    include_escalation_paths: bool = False,
    depth: int = 3,
    user: User = Depends(require_role("admin", "security-engineer")),
) -> CapabilityGraphResponse:
    """
    Get graph data for agent capability visualization.

    Returns D3.js-compatible nodes and edges.
    """
    analyzer = CapabilityGraphAnalyzer(neptune_service)

    nodes = []
    edges = []

    # Get agent and direct capabilities
    agent_data = await analyzer.get_agent_with_capabilities(agent_name)
    nodes.append(GraphNode(
        id=agent_data.id,
        type="agent",
        label=agent_data.name,
        tier=agent_data.tier,
    ))

    for cap in agent_data.capabilities:
        nodes.append(GraphNode(
            id=cap.id,
            type="capability",
            label=cap.name,
            classification=cap.classification,
            risk_score=cap.risk_score,
        ))
        edges.append(GraphEdge(
            source=agent_data.id,
            target=cap.id,
            relationship="HAS_CAPABILITY",
        ))

    # Include inheritance tree
    if include_inheritance:
        tree = await analyzer.get_inheritance_tree(agent_name)
        for parent in tree.ancestors:
            nodes.append(GraphNode(id=parent.id, type="agent", label=parent.name))
            edges.append(GraphEdge(
                source=agent_data.id,
                target=parent.id,
                relationship="INHERITS_FROM",
            ))

    # Highlight escalation paths
    escalation_paths = []
    if include_escalation_paths:
        paths = await analyzer.detect_escalation_paths()
        escalation_paths = [p for p in paths if agent_name in p.agent_chain]

    return CapabilityGraphResponse(
        nodes=nodes,
        edges=edges,
        escalation_paths=escalation_paths,
        metadata={
            "agent": agent_name,
            "depth": depth,
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
```

### Dashboard Visualization

```typescript
// src/frontend/components/CapabilityGraph.tsx

interface CapabilityGraphProps {
  agentId: string;
  showInheritance: boolean;
  showEscalationPaths: boolean;
  highlightRisk: 'all' | 'high' | 'critical';
  onNodeClick: (node: GraphNode) => void;
}

const CapabilityGraph: React.FC<CapabilityGraphProps> = ({
  agentId,
  showInheritance,
  showEscalationPaths,
  highlightRisk,
  onNodeClick,
}) => {
  const { data, isLoading } = useCapabilityGraph(agentId, {
    includeInheritance: showInheritance,
    includeEscalationPaths: showEscalationPaths,
  });

  // Color coding by classification
  const getNodeColor = (node: GraphNode) => {
    if (node.type === 'agent') return '#3B82F6'; // Blue
    switch (node.classification) {
      case 'SAFE': return '#10B981';      // Green
      case 'MONITORING': return '#F59E0B'; // Amber
      case 'DANGEROUS': return '#EA580C';  // Orange
      case 'CRITICAL': return '#DC2626';   // Red
      default: return '#6B7280';           // Gray
    }
  };

  // Highlight escalation paths in red
  const getEdgeStyle = (edge: GraphEdge) => {
    const isEscalationPath = data?.escalation_paths?.some(
      path => path.edges.includes(edge.id)
    );
    return {
      stroke: isEscalationPath ? '#DC2626' : '#9CA3AF',
      strokeWidth: isEscalationPath ? 3 : 1,
      strokeDasharray: isEscalationPath ? '5,5' : 'none',
    };
  };

  return (
    <ForceGraph2D
      graphData={data}
      nodeColor={getNodeColor}
      linkDirectionalArrowLength={6}
      linkColor={edge => getEdgeStyle(edge).stroke}
      onNodeClick={onNodeClick}
      nodeLabel={node => `${node.label}\n${node.classification || node.tier}`}
    />
  );
};
```

## Implementation

### Phase 1: Graph Schema (Week 1-2)

| Task | Deliverable |
|------|-------------|
| Define Neptune schema | Vertex and edge labels, properties |
| Create migration script | Populate graph from existing policies |
| Build graph service | `CapabilityGraphService` class |
| Unit tests | Graph query tests with mocked data |

### Phase 2: Analysis Queries (Week 2-3)

| Task | Deliverable |
|------|-------------|
| Escalation path detection | `detect_escalation_paths()` |
| Coverage gap analysis | `find_coverage_gaps()` |
| Toxic combination detection | `detect_toxic_combinations()` |
| Inheritance tree calculation | `get_inheritance_tree()` |

### Phase 3: API and Visualization (Week 3-5)

| Task | Deliverable |
|------|-------------|
| GraphQL/REST API | `/api/v1/capability-graph/*` endpoints |
| React visualization component | `CapabilityGraph.tsx` |
| Dashboard integration | Security dashboard widget |
| Export capabilities | SVG, PNG, JSON export |

### Phase 4: Continuous Analysis (Week 5-6)

| Task | Deliverable |
|------|-------------|
| Scheduled analysis jobs | EventBridge + Lambda |
| Alerting on new risks | SNS notifications |
| Integration with Policy-as-Code | Pre-merge graph analysis |
| Metrics and reporting | CloudWatch dashboard |

## AWS Services

| Service | Purpose |
|---------|---------|
| **Amazon Neptune** | Graph storage and Gremlin queries |
| **EventBridge** | Scheduled analysis triggers, policy sync events |
| **Lambda** | Analysis job execution |
| **SNS** | Alert notifications |
| **CloudWatch** | Dashboards and metrics (preferred over QuickSight for cost) |
| **API Gateway** | REST API for visualization (simpler than AppSync) |

**Note:** Neptune ML and QuickSight were considered but deferred. CloudWatch Dashboards + existing React dashboard pattern provide sufficient visualization without additional licensing costs.

## Consequences

### Positive

- **Visibility**: Holistic view of capability landscape
- **Proactive security**: Detect escalation paths before exploitation
- **Audit readiness**: Visual evidence for compliance audits
- **Decision support**: Informed policy changes with impact analysis
- **Competitive differentiation**: Unique capability visualization

### Negative

- **Complexity**: Additional graph to maintain synchronized
- **Performance**: Complex queries may be slow on large graphs
- **Learning curve**: Team must learn Gremlin query language

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Graph becomes stale | Event-driven updates on policy changes |
| Query performance | Caching, query optimization, pagination |
| False positives in analysis | Tunable thresholds, human review workflow |

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Escalation path detection coverage | 100% of CRITICAL capabilities | All CRITICAL tools have path analysis |
| Graph sync latency | <30 seconds | Time from policy deploy to graph update |
| Query P99 latency | <2 seconds | Escalation path query response time |
| Query timeout rate | <1% | Queries exceeding 10s timeout |
| Coverage gap detection | 100% of agents | All agents analyzed for gaps |

## Related ADRs

- **ADR-066**: Agent Capability Governance (foundation)
- **ADR-070**: Policy-as-Code with GitOps (policy source, provides sync events)
- **ADR-072**: ML-Based Anomaly Detection (consumes graph patterns)

## References

- [MI9: Runtime Governance Framework for Agentic AI](https://arxiv.org/abs/2508.03858) - Delegation chain management for permission inheritance across spawned subagents
- [Amazon Neptune Documentation](https://docs.aws.amazon.com/neptune/)
- [Gremlin Query Language](https://tinkerpop.apache.org/gremlin.html)
- [D3.js Force-Directed Graphs](https://d3js.org/)
- [React Force Graph](https://github.com/vasturiano/react-force-graph)
