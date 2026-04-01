# ADR-023: AgentCore Gateway Integration for Dual-Track Architecture

**Status:** Deployed
**Date:** 2025-12-05
**Decision Makers:** Project Aura Team
**Related:** ADR-018 (MetaOrchestrator), ADR-021 (Guardrails Cognitive Architecture)

## Context

Project Aura is a security-focused autonomous code intelligence platform with two distinct market segments:

**Defense/Government Track:**
- CMMC Level 3, NIST 800-53, FedRAMP compliance requirements
- AWS GovCloud deployment with air-gap capability
- No external dependencies or third-party integrations
- FULL_HITL (Human-in-the-Loop) approval for all actions
- Strict data residency and security controls

**Commercial Enterprise Track:**
- Standard enterprise security is sufficient
- AWS Commercial Cloud deployment
- Integration with existing enterprise tools (Slack, Jira, PagerDuty)
- Configurable autonomy levels (AUDIT_ONLY, FULL_AUTONOMOUS)
- Faster time-to-value prioritized

**Competitive Landscape (AWS re:Invent 2025):**

Amazon Bedrock AgentCore was announced with capabilities that complement but don't replace Aura's core value proposition:

| Capability | AgentCore | Project Aura |
|------------|-----------|--------------|
| Agent Framework | 6 frameworks (generic) | 16 specialized security agents |
| Memory System | Short/long-term | Neuroscience-inspired cognitive memory |
| HITL Governance | Not built-in | 4 autonomy levels, 6 org presets |
| Security Depth | Generic | Penetration testing, business logic analysis |
| Compliance | Standard AWS | CMMC L3, FedRAMP, GovCloud-first |
| Tool Gateway | MCP-compatible | Native implementation |

**Strategic Opportunity:**

AgentCore Gateway provides MCP (Model Context Protocol) compatibility at low cost ($5/million invocations) that could:
1. Enable integration with 100+ external tools for commercial customers
2. Reduce development effort for Slack/Jira/PagerDuty connectors
3. Support A2A (Agent-to-Agent) protocol for multi-vendor orchestration
4. NOT be used for defense customers (security risk)

## Decision

We adopt a **Dual-Track Architecture** that:

1. **Defense Track:** Maintains current isolated architecture with no external dependencies
2. **Enterprise Track:** Integrates AgentCore Gateway for MCP-compatible tool access

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Project Aura Platform                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│   │     DEFENSE TRACK               │  │     ENTERPRISE TRACK            │  │
│   │     IntegrationMode.DEFENSE     │  │     IntegrationMode.ENTERPRISE  │  │
│   ├─────────────────────────────────┤  ├─────────────────────────────────┤  │
│   │                                 │  │                                 │  │
│   │  ┌───────────────────────────┐  │  │  ┌───────────────────────────┐  │  │
│   │  │ MetaOrchestrator          │  │  │  │ MetaOrchestrator          │  │  │
│   │  │ (Native Agents Only)      │  │  │  │ (Native + MCP Gateway)    │  │  │
│   │  └───────────────────────────┘  │  │  └───────────────────────────┘  │  │
│   │             │                   │  │             │                   │  │
│   │             ▼                   │  │             ▼                   │  │
│   │  ┌───────────────────────────┐  │  │  ┌───────────────────────────┐  │  │
│   │  │ 16 Native Aura Agents     │  │  │  │ 16 Native Agents          │  │  │
│   │  │ • No external deps        │  │  │  │ + MCPGatewayClient        │  │  │
│   │  │ • Air-gap compatible      │  │  │  │ + ExternalToolRegistry    │  │  │
│   │  └───────────────────────────┘  │  │  └───────────────────────────┘  │  │
│   │             │                   │  │             │                   │  │
│   │             ▼                   │  │             ▼                   │  │
│   │  ┌───────────────────────────┐  │  │  ┌───────────────────────────┐  │  │
│   │  │ HITL Approval             │  │  │  │ AgentCore Gateway         │  │  │
│   │  │ (FULL_HITL enforced)      │  │  │  │ (MCP Protocol)            │  │  │
│   │  └───────────────────────────┘  │  │  └───────────────────────────┘  │  │
│   │                                 │  │             │                   │  │
│   │  Security Controls:             │  │             ▼                   │  │
│   │  ❌ No MCP/Gateway              │  │  ┌───────────────────────────┐  │  │
│   │  ❌ No external OAuth           │  │  │ External Tools            │  │  │
│   │  ❌ No A2A protocol             │  │  │ • Slack (notifications)   │  │  │
│   │  ✅ GovCloud compatible         │  │  │ • Jira (ticket creation)  │  │  │
│   │  ✅ STIG/FIPS compliant         │  │  │ • PagerDuty (alerting)    │  │  │
│   │  ✅ Air-gap capable             │  │  │ • GitHub (PR automation)  │  │  │
│   │                                 │  │  │ • Datadog (metrics)       │  │  │
│   └─────────────────────────────────┘  │  └───────────────────────────┘  │  │
│                                        │                                 │  │
│                                        │  Features:                      │  │
│                                        │  ✅ MCP Gateway enabled          │  │
│                                        │  ✅ OAuth integrations           │  │
│                                        │  ✅ A2A protocol support         │  │
│                                        │  ✅ Full autonomy options        │  │
│                                        │  ✅ Cost tracking/budgets        │  │
│                                        └─────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**

1. **Configuration-Driven:** Integration mode set via SSM Parameter or environment variable
2. **Feature Flags:** All MCP/Gateway code behind conditional checks
3. **Cost Controls:** Per-customer MCP budget limits prevent runaway costs
4. **Graceful Degradation:** If Gateway unavailable, fall back to native agents
5. **Audit Everything:** All external tool invocations logged for compliance

## Implementation Plan

### Phase 1: Feature Flag Architecture

Create `IntegrationMode` enum and configuration infrastructure:

```python
# src/config/integration_config.py
class IntegrationMode(Enum):
    DEFENSE = "defense"      # No external dependencies, GovCloud-ready
    ENTERPRISE = "enterprise" # AgentCore Gateway enabled
    HYBRID = "hybrid"        # Per-repository configuration
```

Files created:
- `src/config/integration_config.py` - Mode enum and configuration
- SSM Parameter: `/aura/{env}/integration-mode`

### Phase 2: MCP Adapter Layer

Expose Aura's 16 agents as MCP-compatible tools:

```python
# src/services/mcp_gateway_client.py
class MCPGatewayClient:
    """Client for AgentCore Gateway MCP protocol."""

    async def invoke_tool(self, tool_name: str, params: dict) -> dict:
        """Invoke external tool via MCP Gateway."""

    async def search_tools(self, query: str) -> list[MCPTool]:
        """Semantic search for available tools."""
```

Files created:
- `src/services/mcp_gateway_client.py` - Gateway client
- `src/services/mcp_tool_adapters.py` - Aura agents as MCP tools
- `src/services/external_tool_registry.py` - External tool registration

### Phase 3: External Tool Integration

Implement connectors for common enterprise tools:

| Tool | Capability | MCP Operations |
|------|------------|----------------|
| Slack | Notifications | `send_message`, `create_channel` |
| Jira | Ticket Management | `create_issue`, `update_issue`, `add_comment` |
| PagerDuty | Alerting | `create_incident`, `resolve_incident` |
| GitHub | PR Automation | `create_pr`, `add_review`, `merge_pr` |
| Datadog | Metrics Export | `submit_metric`, `create_event` |

Files created:
- `src/integrations/slack_integration.py`
- `src/integrations/jira_integration.py`
- `src/integrations/pagerduty_integration.py`

## Cost Analysis

### AgentCore Gateway Pricing

| Component | Cost | Per Unit |
|-----------|------|----------|
| Tool Invocations | $0.000005 | per request ($5/million) |
| Search Queries | $0.000025 | per request ($25/million) |
| Tool Indexing | $0.02 | per 100 tools/month |

### Projected Monthly Costs by Customer Tier

| Tier | MCP Invocations | Search Queries | Monthly Cost |
|------|-----------------|----------------|--------------|
| Small (50 devs) | 50,000 | 10,000 | $0.50 |
| Medium (200 devs) | 500,000 | 100,000 | $5.00 |
| Large (1,000 devs) | 10,000,000 | 2,000,000 | $100.00 |
| Enterprise (5,000+ devs) | 50,000,000+ | 10,000,000+ | $750.00+ |

### Cost Controls

```python
@dataclass
class CustomerMCPBudget:
    customer_id: str
    monthly_limit_usd: float = 100.00  # Default $100/month
    current_spend_usd: float = 0.0
    alert_threshold_pct: float = 0.80  # Alert at 80%
```

## Alternatives Considered

### Alternative 1: Build Native Integrations (Rejected)

**Pros:**
- No external dependencies
- Full control over implementation

**Cons:**
- 200+ hours of development per integration
- Ongoing maintenance burden
- Not competitive with AgentCore's 100+ pre-built tools

### Alternative 2: Full AgentCore Adoption (Rejected)

**Pros:**
- Fastest time-to-market
- Managed infrastructure

**Cons:**
- Loses Aura's differentiation (16 specialized agents)
- Cannot support defense customers (no GovCloud runtime)
- Vendor lock-in to AWS managed service

### Alternative 3: Dual-Track with Gateway (Selected)

**Pros:**
- Preserves defense customer capability
- Low-cost integration for enterprise ($5/million)
- Maintains Aura's specialized agent advantage
- Future-proofs for MCP ecosystem growth

**Cons:**
- Additional complexity (two code paths)
- Must maintain feature flags

## Consequences

### Positive

1. **Market Expansion:** Can now serve both defense and commercial enterprise
2. **Faster Integrations:** 100+ external tools via MCP without custom development
3. **Cost Efficiency:** Gateway cost is minimal (<1% of infrastructure)
4. **Competitive Positioning:** Combines Aura's depth with AgentCore's breadth
5. **Future-Proof:** A2A protocol enables multi-vendor agent orchestration

### Negative

1. **Code Complexity:** Two code paths require more testing
2. **Feature Parity:** Must ensure defense track has equivalent notification capabilities
3. **Dependency Risk:** Enterprise track depends on AgentCore availability
4. **Training:** Teams must understand when to use each track

### Neutral

1. **Documentation:** Must clearly document which features require which mode
2. **UI Configuration:** Future UI must make mode selection intuitive
3. **Pricing:** May need tiered pricing for enterprise customers using MCP

## Security Considerations

### Defense Track (DEFENSE Mode)

- **No external network calls** from agent execution
- **Air-gap compatible** - can run without internet
- **STIG/FIPS compliance** maintained
- **All secrets in AWS Secrets Manager** (no external vaults)

### Enterprise Track (ENTERPRISE Mode)

- **OAuth tokens stored in AgentCore Identity** (secure vault)
- **VPC endpoints** for Gateway traffic (no public internet)
- **Audit logging** of all external tool invocations
- **Budget limits** prevent cost overruns
- **Tool allowlisting** - only approved tools enabled per customer

## Metrics and Monitoring

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `mcp_invocations_total` | Total MCP tool invocations | N/A |
| `mcp_invocations_failed` | Failed MCP invocations | >5% error rate |
| `mcp_latency_p99` | 99th percentile latency | >5 seconds |
| `mcp_monthly_cost_usd` | Monthly Gateway spend | >$500/customer |
| `integration_mode_usage` | Customers by mode | N/A (tracking) |

### CloudWatch Dashboard

Create `aura-mcp-gateway-{env}` dashboard with:
- Invocation counts by tool
- Error rates by tool
- Cost tracking by customer
- Latency distribution

## References

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AgentCore Gateway Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [ADR-018: MetaOrchestrator Dynamic Agent Spawning](./ADR-018-meta-orchestrator-dynamic-agent-spawning.md)
- [ADR-021: Guardrails Cognitive Architecture](./ADR-021-guardrails-cognitive-architecture.md)
