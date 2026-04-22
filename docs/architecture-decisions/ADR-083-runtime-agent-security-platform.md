# ADR-083: Runtime Agent Security Platform

## Status

Deployed

## Date

2026-02-18

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Security Review | Cybersecurity Analyst | 2026-02-18 | Approved |
| Product Review | AI Product Manager | 2026-02-18 | Approved |
| Pending | Senior Systems Architect | - | - |
| Pending | Test Architect | - | - |

### Review Summary

Architecture designed with cybersecurity threat modeling (AURA-ATT&CK taxonomy, 97 techniques), product strategy, and technical integration analysis (8 existing interception points, 7 deployed security ADRs). Phase 1 implementation focuses on traffic interception and agent discovery.

## Context

### The Runtime Visibility Gap

Aura has 71,377 lines of agent security code across 7 deployed ADRs:

| ADR | Capability | When It Acts |
|-----|-----------|-------------|
| ADR-065: Semantic Guardrails | 6-layer threat detection on inputs | **Pre-execution** |
| ADR-066: Capability Governance | Tool access control, 4-tier classification | **Pre-execution** |
| ADR-063: Constitutional AI | 16-principle critique-revision pipeline | **Post-generation** |
| ADR-067: Context Provenance | Trust scoring, anomaly detection | **Index-time** |
| ADR-072: Anomaly Detection | Statistical detector, honeypot | **Periodic** |
| ADR-077: Cloud Runtime Security | K8s admission, container escape | **Infrastructure** |
| ADR-042: Real-Time Intervention | CloudTrail, IAM alerting | **Event-driven** |

These controls secure what agents **produce** and what infrastructure **allows**, but no layer provides continuous visibility into what agents **do at runtime**: which tools they call, how frequently, what data flows between agents, whether unregistered agents appear, or how agent behavior drifts over time.

### Competitive Landscape

As of February 2026, startups including Akto.io (which announced a $13M Series A), Lasso Security, and Prompt Security are building standalone runtime agent security products. Based on their publicly documented capabilities at that time, their approach centers on detecting runtime anomalies and generating alerts. We are not aware of any of these vendors publicly documenting autonomous source-code remediation as part of their runtime agent security offering as of that date; readers should verify current capabilities directly.

Aura's GraphRAG infrastructure (Neptune + OpenSearch) enables tracing runtime security events back to source code root causes and generating patches autonomously — a combination we are not aware of being publicly documented by other runtime agent security vendors as of February 2026. This creates a closed-loop security system: **detect → trace → fix → verify**.

### Strategic Imperative

Building runtime agent security into Aura transforms it from a code intelligence platform into a **full-lifecycle AI security platform**. The differentiator is not detection (commodity) but the runtime-to-code correlation that only a GraphRAG architecture can provide.

## Decision

Implement a **Runtime Agent Security Platform** as an extension to the existing `src/services/runtime_security/` package (ADR-077). The platform adds 5 new service modules across 4 implementation phases:

1. **Agent Traffic Interceptor** — real-time capture of all agent communications
2. **Agent Discovery Service** — continuous inventory with shadow agent detection
3. **Behavioral Baseline Engine** — per-agent behavioral profiling and drift detection
4. **Automated Red Teaming Engine** — adversarial testing with AURA-ATT&CK taxonomy
5. **Runtime-to-Code Correlator** — GraphRAG-powered root cause analysis and remediation

### Core Capabilities

1. **Full Traffic Visibility** — capture agent-to-agent, agent-to-tool, and agent-to-LLM traffic via 8 existing interception points
2. **Shadow Agent Detection** — identify unregistered agents via traffic pattern analysis against ADR-066 capability registry
3. **Behavioral Baselines** — statistical profiles per agent with drift alerting (extends ADR-072 statistical detector)
4. **AURA-ATT&CK Taxonomy** — 97 adversarial techniques across 11 MITRE-style categories for automated red teaming
5. **Runtime-to-Code Correlation** — trace runtime anomalies to source code via Neptune CALL_GRAPH + OpenSearch semantic search
6. **Autonomous Remediation** — generate patches via Coder agent, route through HITL approval (ADR-032)

## Architecture

### Pipeline Position

```text
Existing Security Pipeline (ADR-065/066/063/067/072/077/042)
    │
    │  ┌─────────────────────────────────────────────────────────────────┐
    │  │              NEW: Runtime Agent Security Platform                │
    │  │                                                                 │
    │  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
    │  │  │ Traffic          │  │ Agent           │  │ Behavioral   │  │
    │  │  │ Interceptor      │──│ Discovery       │──│ Baselines    │  │
    │  │  │ (captures all    │  │ (shadow agent   │  │ (drift       │  │
    │  │  │  agent traffic)  │  │  detection)     │  │  detection)  │  │
    │  │  └────────┬─────────┘  └────────┬────────┘  └──────┬───────┘  │
    │  │           │                     │                   │          │
    │  │           ▼                     ▼                   ▼          │
    │  │  ┌──────────────────────────────────────────────────────────┐  │
    │  │  │              Red Teaming Engine                          │  │
    │  │  │  (97 techniques, 11 MITRE-style categories)             │  │
    │  │  └────────────────────────┬─────────────────────────────────┘  │
    │  │                           │                                    │
    │  │                           ▼                                    │
    │  │  ┌──────────────────────────────────────────────────────────┐  │
    │  │  │         Runtime-to-Code Correlator                      │  │
    │  │  │  Neptune CALL_GRAPH → OpenSearch → Coder Agent → HITL   │  │
    │  │  │  (detect → trace → fix → verify)                        │  │
    │  │  └──────────────────────────────────────────────────────────┘  │
    │  │                                                                 │
    │  └─────────────────────────────────────────────────────────────────┘
```

### 8 Existing Interception Points

The traffic interceptor hooks into these existing pipeline points:

| # | Interception Point | Existing ADR | Traffic Type |
|---|-------------------|-------------|-------------|
| 1 | FastAPI middleware | Core | HTTP request/response |
| 2 | Capability Governance middleware | ADR-066 | Tool invocations |
| 3 | LLM Prompt Sanitizer | ADR-065 | LLM prompts/completions |
| 4 | MCP Tool Server | Core | MCP tool calls |
| 5 | Execution Checkpoints | ADR-042 | Agent state snapshots |
| 6 | K8s Admission Controller | ADR-077 | Container operations |
| 7 | Container Escape Detector | ADR-077 | Syscall monitoring |
| 8 | Constitutional AI post-generation | ADR-063 | Revised outputs |

### AURA-ATT&CK Threat Taxonomy

97 techniques across 11 MITRE-style categories:

| ID | Category | Techniques | Key NIST Controls |
|----|----------|-----------|-------------------|
| ATA-01 | Prompt Injection | 12 (direct, indirect, recursive, multi-modal, context window) | SI-10, SC-18 |
| ATA-02 | Tool Abuse | 10 (parameter manipulation, chain exploitation, capability escalation) | AC-6, CM-7 |
| ATA-03 | Agent Confusion | 9 (role hijacking, goal drift, memory poisoning, identity spoofing) | IA-2, SC-7 |
| ATA-04 | Data Exfiltration | 8 (side-channel encoding, token-level leakage, embedding extraction) | SC-8, SC-28 |
| ATA-05 | Privilege Escalation | 10 (horizontal, vertical, cross-tenant, approval bypass) | AC-2, AC-6 |
| ATA-06 | Denial of Service | 8 (token exhaustion, recursive loops, resource starvation) | SC-5, CP-9 |
| ATA-07 | Supply Chain | 9 (MCP server poisoning, dependency confusion, model weight tampering) | SA-12, SR-3 |
| ATA-08 | Evasion | 9 (encoding bypass, language switching, semantic obfuscation) | SI-3, SI-4 |
| ATA-09 | Cryptographic Weaknesses | 8 (weak algorithms, key management, protocol downgrade) | SC-12, SC-13 |
| ATA-10 | Memory Safety | 8 (buffer overflow, use-after-free, uninitialized memory) | SI-16, SA-11 |
| ATA-11 | Sandbox/Isolation Escape | 6 (container breakout, namespace escape, network bypass) | SC-7, SC-39 |

### Data Models

```python
# New contracts extend existing runtime_security.contracts

@dataclass(frozen=True)
class InterceptionPoint(Enum):
    FASTAPI_MIDDLEWARE = "fastapi_middleware"
    CAPABILITY_GOVERNANCE = "capability_governance"
    LLM_PROMPT_SANITIZER = "llm_prompt_sanitizer"
    MCP_TOOL_SERVER = "mcp_tool_server"
    EXECUTION_CHECKPOINT = "execution_checkpoint"
    K8S_ADMISSION = "k8s_admission"
    CONTAINER_ESCAPE = "container_escape"
    CONSTITUTIONAL_AI = "constitutional_ai"

@dataclass(frozen=True)
class TrafficEvent:
    event_id: str
    timestamp: datetime
    source_agent_id: str
    target_agent_id: Optional[str]
    interception_point: InterceptionPoint
    direction: TrafficDirection  # INBOUND, OUTBOUND, INTERNAL
    event_type: TrafficEventType  # AGENT_TO_AGENT, AGENT_TO_TOOL, AGENT_TO_LLM
    payload_hash: str
    latency_ms: float
    token_count: Optional[int]
    tool_name: Optional[str]
    approval_required: bool
    approval_decision: Optional[str]

@dataclass(frozen=True)
class AgentRegistration:
    agent_id: str
    agent_type: str
    registered: bool  # In ADR-066 capability registry
    first_seen: datetime
    last_seen: datetime
    tool_capabilities: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    is_shadow: bool  # True if not in capability registry

@dataclass(frozen=True)
class BehavioralProfile:
    agent_id: str
    window_hours: int
    tool_call_frequency: dict[str, float]
    avg_token_consumption: float
    approval_rate: float
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    computed_at: datetime
```

## Implementation

### Package Structure

```
src/services/runtime_security/
├── __init__.py                    # Existing (ADR-077) - extend exports
├── contracts.py                   # Existing (ADR-077)
├── config.py                      # Existing (ADR-077) - extend config
├── interceptor/
│   ├── __init__.py
│   ├── traffic_interceptor.py     # Core async traffic capture proxy
│   ├── protocol.py                # Traffic event data models (frozen dataclasses)
│   └── storage.py                 # DynamoDB metadata + S3 payload storage
├── discovery/
│   ├── __init__.py
│   ├── agent_discovery.py         # Continuous agent inventory
│   ├── shadow_detector.py         # Shadow agent detection via traffic patterns
│   └── topology.py                # Neptune agent topology graph builder
├── baselines/
│   ├── __init__.py
│   ├── baseline_engine.py         # Per-agent behavioral profile builder
│   ├── metrics.py                 # Metric definitions (frozen dataclasses)
│   └── drift_detector.py          # Behavioral drift detection + alerting
├── red_team/
│   ├── __init__.py
│   ├── engine.py                  # Red team test orchestrator
│   ├── taxonomy.py                # AURA-ATT&CK 97 technique definitions
│   ├── generators/                # Attack payload generators (per category)
│   │   ├── __init__.py
│   │   ├── prompt_injection.py
│   │   ├── tool_abuse.py
│   │   ├── agent_confusion.py
│   │   ├── data_exfiltration.py
│   │   ├── privilege_escalation.py
│   │   ├── denial_of_service.py
│   │   ├── supply_chain.py
│   │   └── evasion.py
│   └── evaluators/
│       ├── __init__.py
│       └── attack_evaluator.py    # Success/failure evaluation
└── correlation/
    ├── __init__.py
    ├── correlator.py              # Main runtime-to-code correlation engine
    ├── graph_tracer.py            # Neptune CALL_GRAPH traversal
    ├── vector_matcher.py          # OpenSearch semantic similarity search
    └── remediation.py             # Patch generation via Coder agent + HITL
```

### Integration Points

| New Service | Integrates With | How |
|-------------|----------------|-----|
| Traffic Interceptor | ADR-066 middleware | Hook into `CapabilityGovernanceMiddleware.check()` |
| Traffic Interceptor | ADR-065 guardrails | Hook into `SemanticGuardrailsEngine.evaluate()` |
| Traffic Interceptor | ADR-063 constitutional | Hook into `ConstitutionalMixin.finalize_with_constitutional()` |
| Traffic Interceptor | ADR-042 checkpoints | Hook into `ExecutionCheckpoint.save()` |
| Agent Discovery | ADR-066 registry | Read `ToolCapabilityRegistry` as source of truth |
| Behavioral Baselines | ADR-072 anomaly detection | Extend `StatisticalDetector` with agent-specific metrics |
| Red Teaming | ADR-077 sandbox | Execute attacks in isolated sandbox network |
| Correlation | Neptune GraphRAG | Query CALL_GRAPH, DEPENDENCIES, INHERITANCE edges |
| Correlation | OpenSearch | Semantic search for vulnerability pattern matching |
| Correlation | ADR-032 HITL | Route generated patches through approval workflow |

## Implementation Phases

### Phase 1: Traffic Interceptor + Agent Discovery

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `interceptor/protocol.py` | Frozen dataclass traffic event models | ~300 |
| `interceptor/traffic_interceptor.py` | Async traffic capture proxy | ~600 |
| `interceptor/storage.py` | DynamoDB + S3 storage adapter | ~400 |
| `discovery/agent_discovery.py` | Continuous agent inventory engine | ~400 |
| `discovery/shadow_detector.py` | Shadow agent detection | ~350 |
| `discovery/topology.py` | Neptune topology graph builder | ~350 |
| Tests | ~200 tests (interceptor: ~120, discovery: ~80) | ~1,100 |
| **Phase 1 Total** | | **~3,500** |

### Phase 2: Behavioral Baselines

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `baselines/metrics.py` | Metric definitions | ~200 |
| `baselines/baseline_engine.py` | Profile builder + deviation scorer | ~700 |
| `baselines/drift_detector.py` | Behavioral drift detection | ~400 |
| Tests | ~100 tests | ~700 |
| **Phase 2 Total** | | **~2,000** |

### Phase 3: Red Teaming Engine

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `red_team/taxonomy.py` | 75 technique definitions | ~600 |
| `red_team/engine.py` | Orchestrator | ~500 |
| `red_team/generators/` | 8 attack generators | ~1,200 |
| `red_team/evaluators/` | Attack success evaluators | ~400 |
| Tests | ~150 unit + red team cases | ~1,300 |
| **Phase 3 Total** | | **~4,000** |

### Phase 4: Runtime-to-Code Correlation

| Task | Deliverable | Est. LOC |
|------|-------------|----------|
| `correlation/graph_tracer.py` | Neptune CALL_GRAPH traversal | ~500 |
| `correlation/vector_matcher.py` | OpenSearch similarity search | ~400 |
| `correlation/correlator.py` | Main correlation engine | ~600 |
| `correlation/remediation.py` | Patch generation orchestrator | ~400 |
| Tests | ~100 tests | ~600 |
| **Phase 4 Total** | | **~2,500** |

## GovCloud Compatibility

All services use `${AWS::Partition}` in ARNs. Dependencies:

| Service | GovCloud Available | Usage |
|---------|-------------------|-------|
| DynamoDB | Yes | Traffic metadata, baselines |
| S3 | Yes | Full payload storage |
| Neptune | Yes (provisioned) | Agent topology, call graph |
| OpenSearch | Yes | Semantic search |
| EventBridge | Yes | Discovery event rules |
| CloudWatch | Yes | Metrics, alarms |
| EKS | Yes | Service hosting |

## Cost Analysis

### Monthly Cost Estimate (DEV environment)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| DynamoDB (traffic metadata) | PAY_PER_REQUEST, ~1M writes/mo | ~$1.25 |
| S3 (payload storage) | ~10GB/mo, 90-day lifecycle | ~$0.25 |
| Neptune (topology graph) | Shared cluster | $0 incremental |
| OpenSearch (semantic search) | Shared cluster | $0 incremental |
| EventBridge (discovery) | ~500K events/mo | ~$0.50 |
| CloudWatch (metrics) | ~30 custom metrics | ~$9.00 |
| **Total incremental** | | **~$11/month** |

## Consequences

### Positive

1. **Full-lifecycle security** — detect, trace, fix, verify in a single platform
2. **Shadow agent detection** — identify unregistered agents before they cause damage
3. **Behavioral drift alerting** — catch gradual agent degradation or compromise
4. **Automated red teaming** — continuous adversarial validation with 97 techniques
5. **Competitive differentiation** — runtime-to-code correlation via GraphRAG is a capability we are not aware of being publicly documented by comparable runtime agent security vendors as of February 2026
6. **Compliance readiness** — NIST 800-53 SI-4, AU-6 continuous monitoring requirements

### Negative

1. **Traffic overhead** — interceptor adds ~2-5ms per agent call for capture
2. **Storage growth** — full payload storage requires S3 lifecycle management
3. **Complexity** — 5 new service modules increase system surface area
4. **Baseline cold start** — behavioral profiles need 24-72h of traffic to stabilize

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Interceptor latency impact | Medium | Medium | Async capture, non-blocking writes |
| False positive shadow detection | Medium | Low | Cross-reference with capability registry before alert |
| Red team test escape | Low | High | Execute in ADR-077 sandboxed network only |
| Baseline gaming | Low | Medium | Multiple window sizes (1h, 24h, 7d) resist manipulation |

## Success Metrics

| Metric | Target |
|--------|--------|
| Traffic capture rate | >99.5% of agent calls |
| Shadow agent detection time | <60 seconds |
| Baseline drift alert latency | <5 minutes |
| Red team coverage | 97/97 AURA-ATT&CK techniques |
| Runtime-to-code correlation accuracy | >85% |
| Interceptor overhead | <5ms P95 |
| Unit test count | >550 |

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

## References

1. ADR-065: Semantic Guardrails Engine
2. ADR-066: Agent Capability Governance
3. ADR-063: Constitutional AI Integration
4. ADR-067: Context Provenance and Integrity
5. ADR-072: ML-Based Anomaly Detection
6. ADR-077: Cloud Runtime Security
7. ADR-042: Real-Time Agent Intervention
8. ADR-032: Configurable Autonomy Framework (HITL)
9. MITRE ATT&CK Framework
10. NIST SP 800-53 Rev. 5
