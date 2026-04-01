# ADR-019: Market Intelligence Agent for Autonomous Competitive Research

**Status:** Deployed
**Date:** 2025-12-03
**Decision Makers:** Project Aura Team
**Related:** ADR-018 (MetaOrchestrator Dynamic Agent Spawning), ADR-010 (Autonomous ADR Generation Pipeline)

## Context

### Market Research Findings

At AWS re:Invent 2025, Amazon unveiled **AWS Security Agent** as part of their "Frontier Agents" initiative. This competitor analysis reveals both capability alignment and gaps:

#### AWS Security Agent Capabilities (December 2025)

| Capability | AWS Security Agent | Project Aura Status |
|------------|-------------------|---------------------|
| Context-aware penetration testing | ✅ Multi-step attack scenarios | ❌ CVE-based only |
| Automated remediation with PR creation | ✅ Direct GitHub PRs | ⚠️ Sandbox testing, manual PR |
| Design document security review | ✅ Proactive design analysis | ❌ Code-only analysis |
| Business logic vulnerability detection | ✅ Context-aware detection | ⚠️ Limited to known patterns |
| OWASP Top 10 scanning | ✅ Yes | ✅ Yes |
| GitHub PR integration | ✅ Comments + remediation PRs | ⚠️ Planned (Priority 2) |
| Multi-cloud/hybrid support | ✅ AWS, multicloud, hybrid | ✅ AWS-focused, extensible |
| On-demand pen testing | ✅ Hours instead of weeks | ⚠️ Sandbox testing only |
| Dynamic agent spawning | ✅ Yes | ✅ MetaOrchestrator (ADR-018) |
| Configurable autonomy levels | ✅ 4-scope model | ✅ 4-level model |

#### AWS Agentic AI Security Scoping Matrix

AWS published a security framework defining 4 autonomy scopes:
- **Scope 1: No Agency** - Read-only, recommendations only
- **Scope 2: Prescribed Agency** - HITL mandatory for all changes
- **Scope 3: Supervised Agency** - Autonomous execution, human-initiated
- **Scope 4: Full Agency** - Fully autonomous, self-initiating

**Comparison:** Our `AutonomyLevel` enum (FULL_HITL, CRITICAL_HITL, AUDIT_ONLY, FULL_AUTONOMOUS) maps closely to AWS's scopes, demonstrating architectural alignment.

### Gap Analysis

**Immediate Capability Gaps:**
1. **Penetration Testing** - AWS performs active exploitation; we rely on static CVE matching
2. **Design Document Review** - AWS proactively reviews architecture; we analyze code only
3. **GitHub PR Creation** - AWS auto-creates remediation PRs; we require manual intervention
4. **Business Logic Testing** - AWS detects context-specific vulnerabilities

**Strategic Gap: No Market Intelligence Capability**

Project Aura has **zero agents** capable of:
- Monitoring competitor announcements and product features
- Tracking industry technology trends
- Fetching and analyzing external documentation
- Identifying emerging security threats from market sources
- Benchmarking capabilities against competitors

This research was performed manually. Future competitive intelligence should be **automated and continuous**.

### Current Agent Inventory

Our agent system has 17 implementations, but only **1 agent** (ThreatIntelligenceAgent) has external data gathering capabilities, limited to security threat feeds:
- NVD (National Vulnerability Database)
- CISA Known Exploited Vulnerabilities
- GitHub Security Advisories

No agents perform market research, competitive analysis, or technology trend monitoring.

### Key Question

How should Project Aura implement autonomous market intelligence capabilities to:
1. Continuously monitor competitor products and announcements
2. Track industry technology trends and best practices
3. Identify capability gaps requiring remediation
4. Share findings with other specialized agents
5. Maintain documentation of market position and competitive landscape

## Decision

We will implement a **MarketIntelligenceAgent** that operates autonomously to gather, analyze, and disseminate competitive intelligence throughout the agent system.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MarketIntelligenceAgent                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Research Orchestrator                              │  │
│  │  - Schedules research tasks (daily, weekly, on-demand)                │  │
│  │  - Prioritizes intelligence gathering based on relevance              │  │
│  │  - Spawns specialized sub-agents for deep-dive analysis               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          ▼                         ▼                         ▼              │
│  ┌───────────────┐       ┌─────────────────┐       ┌────────────────┐      │
│  │CompetitorWatch│       │  TrendAnalysis  │       │DocAggregator   │      │
│  │    Agent      │       │     Agent       │       │    Agent       │      │
│  ├───────────────┤       ├─────────────────┤       ├────────────────┤      │
│  │• AWS announcements    │• GitHub trending │       │• API docs fetch│      │
│  │• Azure/GCP releases   │• HackerNews      │       │• Best practices│      │
│  │• Startup funding      │• Reddit r/devops │       │• Standards orgs│      │
│  │• Analyst reports      │• Tech blogs      │       │• Competitor docs│     │
│  └───────────────┘       └─────────────────┘       └────────────────┘      │
│                                    │                                         │
│                                    ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Knowledge Dissemination                             │  │
│  │  - Updates shared knowledge base (DynamoDB/S3)                        │  │
│  │  - Generates intelligence reports (Markdown)                          │  │
│  │  - Triggers capability gap alerts                                     │  │
│  │  - Informs other agents via context injection                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. MarketIntelligenceAgent

```python
class MarketIntelligenceAgent(SpawnableAgent):
    """
    Autonomous agent for gathering and analyzing market intelligence.

    Capabilities:
    - Competitor monitoring (AWS, Azure, GCP, startups)
    - Technology trend analysis
    - External documentation aggregation
    - Capability gap identification
    - Knowledge base maintenance
    """

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.MARKET_INTELLIGENCE  # New capability

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute market research task."""
        # 1. Parse research request
        # 2. Spawn appropriate sub-agents
        # 3. Aggregate findings
        # 4. Update knowledge base
        # 5. Generate report
```

#### 2. Data Sources

| Source Category | Examples | Update Frequency |
|----------------|----------|------------------|
| **Competitor Announcements** | AWS Blog, Azure Updates, GCP Release Notes | Daily |
| **Security Advisories** | AWS Security Blog, Microsoft Security Response | Daily |
| **Technology Trends** | GitHub Trending, HackerNews, Reddit | Daily |
| **Industry Standards** | NIST, OWASP, CIS Benchmarks | Weekly |
| **Market Analysis** | Gartner, Forrester (if accessible) | Monthly |
| **Open Source Tools** | GitHub repos, npm/PyPI packages | Weekly |

#### 3. Knowledge Base Schema

```python
@dataclass
class IntelligenceReport:
    """Market intelligence finding."""
    report_id: str
    report_type: str  # competitor, trend, capability_gap, standard
    source: str
    title: str
    summary: str
    relevance_score: float  # 0.0 - 1.0
    capability_impact: list[AgentCapability]  # Which capabilities affected
    recommendations: list[str]
    raw_content: str | None
    source_url: str
    discovered_at: str
    expires_at: str | None  # TTL for time-sensitive intel

@dataclass
class CapabilityGapAlert:
    """Alert when competitor capability exceeds ours."""
    alert_id: str
    competitor: str
    capability: str
    our_status: str  # "missing", "partial", "equivalent", "superior"
    gap_severity: str  # "critical", "high", "medium", "low"
    recommended_action: str
    related_reports: list[str]
```

#### 4. Integration with Existing Agents

The MarketIntelligenceAgent will integrate with the MetaOrchestrator via:

1. **New AgentCapability**: Add `MARKET_INTELLIGENCE` to enum
2. **Knowledge Injection**: Other agents query intelligence reports for context
3. **Gap Alerts**: MetaOrchestrator receives capability gap notifications
4. **ADR Triggers**: ArchitectureReviewAgent receives new technology recommendations

### Sub-Agent Specifications

#### CompetitorWatchAgent
- **Sources**: RSS feeds, API endpoints, web scraping
- **Output**: Competitor announcements, feature comparisons
- **Frequency**: Daily scan, immediate alerts for major announcements

#### TrendAnalysisAgent
- **Sources**: GitHub API, social platforms, tech news
- **Output**: Emerging technologies, adoption patterns, security trends
- **Frequency**: Daily aggregation, weekly trend reports

#### DocumentationAggregatorAgent
- **Sources**: Official docs, best practice guides, standards
- **Output**: Updated documentation references, API changes
- **Frequency**: Weekly sync, immediate for breaking changes

### Autonomy Configuration

```python
# Market research is low-risk, suitable for high autonomy
MARKET_INTELLIGENCE_PRESETS = {
    "continuous_monitoring": {
        "default_level": AutonomyLevel.AUDIT_ONLY,
        "severity_overrides": {
            "capability_gap_critical": AutonomyLevel.CRITICAL_HITL,
        },
        "allowed_actions": [
            "web_fetch", "api_query", "report_generation",
            "knowledge_base_update", "alert_creation"
        ],
        "blocked_actions": [
            "code_modification", "deployment", "external_notification"
        ]
    }
}
```

### Implementation Phases

#### Phase 1: Foundation (2 weeks)
- [ ] Add `MARKET_INTELLIGENCE` to AgentCapability enum
- [ ] Create MarketIntelligenceAgent base class
- [ ] Implement web fetch and RSS feed parsing
- [ ] Create IntelligenceReport schema and DynamoDB table
- [ ] Basic competitor blog monitoring (AWS, Azure)

#### Phase 2: Sub-Agents (2 weeks)
- [ ] Implement CompetitorWatchAgent
- [ ] Implement TrendAnalysisAgent
- [ ] Implement DocumentationAggregatorAgent
- [ ] Add spawnable agent adapters for MetaOrchestrator

#### Phase 3: Knowledge Dissemination (1 week)
- [ ] Implement knowledge base query API
- [ ] Add context injection for other agents
- [ ] Create capability gap alerting system
- [ ] Generate automated intelligence reports

#### Phase 4: Integration (1 week)
- [ ] Integrate with MetaOrchestrator
- [ ] Add scheduled execution (EventBridge)
- [ ] Create intelligence dashboard endpoints
- [ ] Documentation and testing

## Alternatives Considered

### Alternative 1: Manual Research Only
**Description:** Continue relying on manual competitive research.

**Pros:**
- No development cost
- Human judgment for relevance

**Cons:**
- Not scalable
- Delayed awareness of competitor moves
- Inconsistent coverage
- No integration with agent system

**Decision:** Rejected - does not support autonomous operation goals.

### Alternative 2: Third-Party Intelligence Platform
**Description:** Integrate with commercial CI/CD intelligence tools (e.g., Crayon, Klue).

**Pros:**
- Mature platforms with comprehensive data
- Dedicated analyst support

**Cons:**
- High cost ($50K+/year)
- Vendor lock-in
- Not integrated with agent system
- Generic, not security-focused

**Decision:** Rejected - cost prohibitive and lacks agent integration.

### Alternative 3: Extend ThreatIntelligenceAgent
**Description:** Add market research capabilities to existing ThreatIntelligenceAgent.

**Pros:**
- Reuses existing external data infrastructure
- Single agent for all external intelligence

**Cons:**
- Violates single responsibility principle
- Conflates security threats with market intelligence
- Different update frequencies and priorities
- Harder to maintain and test

**Decision:** Rejected - prefer separation of concerns.

## Consequences

### Positive
1. **Continuous Competitive Awareness** - Automated tracking of competitor capabilities
2. **Proactive Capability Development** - Early identification of gaps
3. **Knowledge Sharing** - Intelligence available to all agents
4. **Reduced Manual Effort** - Eliminates ad-hoc market research
5. **Audit Trail** - All findings documented and timestamped

### Negative
1. **Development Investment** - 6 weeks of implementation effort
2. **API Costs** - Web scraping and API calls incur costs
3. **Information Overload Risk** - Must tune relevance filtering
4. **Maintenance Overhead** - External sources change frequently

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Source reliability | Multiple sources per topic, credibility scoring |
| Information staleness | TTL on reports, freshness indicators |
| Rate limiting | Respectful scraping, caching, API quotas |
| Irrelevant noise | LLM-powered relevance filtering, human review for critical alerts |

## References

### External Sources (from this research)
- [AWS Security Agent Features](https://aws.amazon.com/security-agent/features/)
- [AWS Security Agent Documentation](https://docs.aws.amazon.com/securityagent/latest/userguide/how-it-works.html)
- [AWS Agentic AI Security Scoping Matrix](https://aws.amazon.com/ai/security/agentic-ai-scoping-matrix/)
- [AWS re:Invent 2025 Announcements](https://aws.amazon.com/blogs/aws/top-announcements-of-aws-reinvent-2025/)
- [AWS Frontier Agents Announcement](https://www.aboutamazon.com/news/aws/amazon-ai-frontier-agents-autonomous-kiro)

### Internal References
- ADR-018: MetaOrchestrator with Dynamic Agent Spawning
- ADR-010: Autonomous ADR Generation Pipeline
- `src/agents/threat_intelligence_agent.py` - External data gathering patterns
- `src/agents/meta_orchestrator.py` - SpawnableAgent interface

## Appendix: Capability Comparison Matrix

### AWS Security Agent vs Project Aura (Post ADR-018)

| Capability | AWS Security Agent | Project Aura | Gap Status |
|------------|-------------------|--------------|------------|
| Dynamic agent spawning | ✅ | ✅ MetaOrchestrator | **Parity** |
| Configurable autonomy | ✅ 4-scope model | ✅ 4-level model | **Parity** |
| OWASP vulnerability scanning | ✅ | ✅ ReviewerAgent | **Parity** |
| Security patch generation | ✅ | ✅ CoderAgent | **Parity** |
| Sandbox testing | ✅ | ✅ PatchValidationWorkflow | **Parity** |
| HITL approval workflow | ✅ | ✅ HITLApprovalService | **Parity** |
| Threat feed integration | ✅ | ✅ ThreatIntelligenceAgent | **Parity** |
| GitHub PR comments | ✅ | ❌ | **Gap** |
| Auto-create remediation PRs | ✅ | ❌ | **Gap** |
| Design document review | ✅ | ❌ | **Gap** |
| Active penetration testing | ✅ | ❌ | **Gap** |
| Business logic vulnerability | ✅ | ⚠️ Limited | **Partial Gap** |
| Market intelligence | ❌ | ❌ (proposed) | **N/A** |

### Priority Recommendations

Based on this analysis, recommended roadmap additions:

1. **High Priority**: GitHub PR integration for remediation (aligns with Priority 1/2)
2. **Medium Priority**: Design document security review capability
3. **Medium Priority**: Market Intelligence Agent (this ADR)
4. **Lower Priority**: Active penetration testing (complex, regulatory considerations)
