# ADR Pipeline Agents - Project Aura

**Agent Type:** Autonomous ADR Generation Pipeline
**Domain:** Architecture Documentation, Threat Intelligence, Security Analysis
**Target Scope:** Continuous architecture oversight, automated documentation generation

---

## Pipeline Overview

The ADR Pipeline consists of four specialized agents working in coordination to autonomously generate Architecture Decision Records from threat intelligence and architectural analysis.

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ THREAT INTEL     │    │ ADAPTIVE         │    │ ARCHITECTURE     │    │ ADR GENERATOR    │
│ AGENT            │───▶│ INTELLIGENCE     │───▶│ REVIEW AGENT     │───▶│ AGENT            │
│                  │    │ AGENT            │    │                  │    │                  │
│ Monitors feeds   │    │ Analyzes impact  │    │ Detects triggers │    │ Generates docs   │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## Agent 1: Threat Intelligence Agent

### Configuration

```yaml
name: threat-intelligence-agent
description: Continuously monitors external threat feeds and internal telemetry to identify security vulnerabilities and compliance changes affecting the platform.
tools: WebFetch, WebSearch, Grep, Read
model: haiku
color: yellow
```

### Responsibilities

- Monitor NVD (National Vulnerability Database) for new CVEs
- Fetch CISA Known Exploited Vulnerabilities (KEV) catalog
- Track GitHub Security Advisories for Python ecosystem
- Analyze internal telemetry (WAF logs, anomaly detection)
- Match vulnerabilities against project SBOM

### Input Sources

| Source | URL/API | Frequency |
|--------|---------|-----------|
| NVD | `https://services.nvd.nist.gov/rest/json/cves/2.0` | Real-time |
| CISA KEV | `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | Daily |
| GitHub | `https://api.github.com/advisories` | Real-time |
| Internal | CloudWatch WAF Logs, GuardDuty | Continuous |

### Output

```python
@dataclass
class ThreatIntelReport:
    id: str
    title: str
    category: ThreatCategory  # CVE, ADVISORY, COMPLIANCE, PATTERN, INTERNAL
    severity: ThreatSeverity  # CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL
    source: str
    published_date: datetime
    description: str
    affected_components: list[str]
    cve_ids: list[str]
    cvss_score: float | None
    recommended_actions: list[str]
    references: list[str]
```

### Usage Example

```python
from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent, ThreatIntelConfig

# Initialize with custom config
config = ThreatIntelConfig(
    nvd_api_key=os.environ.get("NVD_API_KEY"),
    check_interval_minutes=30,
    severity_threshold=ThreatSeverity.MEDIUM,
)

agent = ThreatIntelligenceAgent(config=config)

# Set project dependencies for matching
agent.set_dependency_sbom([
    {"name": "requests", "version": "2.28.0"},
    {"name": "fastapi", "version": "0.108.0"},
    {"name": "opensearch-py", "version": "2.4.0"},
])

# Gather intelligence
reports = await agent.gather_intelligence()
for report in reports:
    print(f"[{report.severity.value}] {report.title}")
```

---

## Agent 2: Adaptive Intelligence Agent

### Configuration

```yaml
name: adaptive-intelligence-agent
description: Analyzes threat intelligence reports, assesses codebase impact using GraphRAG, and generates prioritized recommendations with risk scoring and best practice alignment.
tools: Grep, Read, Glob
model: sonnet
color: blue
```

### Responsibilities

- Assess codebase impact using GraphRAG context retrieval
- Generate risk scores based on severity, dependencies, compliance
- Find applicable industry best practices
- Estimate implementation effort
- Produce prioritized recommendations

### Risk Scoring Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| CVSS Score | Base | Starting point from vulnerability database |
| Direct Dependency | +1.0 | Affects project dependencies directly |
| Infrastructure Impact | +0.5 | Affects CloudFormation/Kubernetes |
| Compliance Relevance | +0.5 | Has CMMC/NIST/SOX implications |
| Active Exploitation | +2.0 | Listed in CISA KEV |

### Output

```python
@dataclass
class AdaptiveRecommendation:
    id: str
    title: str
    recommendation_type: RecommendationType
    severity: ThreatSeverity
    risk_score: float  # 0.0-10.0
    risk_level: RiskLevel  # MINIMAL, LOW, MODERATE, HIGH, CRITICAL
    effort_level: EffortLevel  # TRIVIAL, SMALL, MEDIUM, LARGE, MAJOR
    description: str
    rationale: str
    affected_components: list[str]
    affected_files: list[str]
    implementation_steps: list[str]
    best_practices: list[BestPractice]
    compliance_impact: list[str]
    rollback_plan: str
    validation_criteria: list[str]
```

### Usage Example

```python
from src.agents.adaptive_intelligence_agent import AdaptiveIntelligenceAgent

agent = AdaptiveIntelligenceAgent(
    context_service=context_retrieval_service,  # GraphRAG service
)

# Analyze threat reports
recommendations = agent.analyze_threats(threat_reports)

for rec in recommendations:
    print(f"[{rec.risk_level.value}] {rec.title}")
    print(f"  Risk Score: {rec.risk_score}/10")
    print(f"  Effort: {rec.effort_level.value}")
    print(f"  Steps: {len(rec.implementation_steps)}")
```

---

## Agent 3: Architecture Review Agent

### Configuration

```yaml
name: architecture-review-agent
description: Detects ADR-worthy decisions by analyzing recommendations, identifying pattern deviations from existing ADRs, and evaluating architectural significance.
tools: Read, Grep, Glob
model: sonnet
color: purple
```

### Responsibilities

- Evaluate recommendations for ADR-worthiness
- Detect pattern deviations from existing ADRs
- Determine ADR significance level
- Identify HITL approval requirements
- Find related existing ADRs

### ADR-Worthiness Criteria

An ADR is generated when ANY of these conditions are met:

1. **Security** - Critical or High severity threat remediation
2. **Architecture** - Changes to system architecture
3. **Compliance** - Regulatory requirement changes
4. **Effort** - Large or Major implementation effort
5. **Risk** - High or Critical risk level
6. **Pattern** - Deviation from established architecture patterns
7. **Infrastructure** - Changes to CloudFormation/Kubernetes/IAM

### Significance Levels

| Level | HITL Required | Description |
|-------|---------------|-------------|
| CRITICAL | Yes | Immediate review required |
| HIGH | Yes | HITL approval needed |
| MEDIUM | No | Auto-approve with notification |
| LOW | No | Auto-approve, log only |
| INFORMATIONAL | No | No ADR needed, changelog only |

### Output

```python
@dataclass
class ADRTriggerEvent:
    id: str
    title: str
    category: ADRCategory  # SECURITY, INFRASTRUCTURE, DEPENDENCY, etc.
    significance: ADRSignificance
    description: str
    context_summary: str
    affected_components: list[str]
    source_recommendation: AdaptiveRecommendation
    existing_adr_references: list[str]
    pattern_deviations: list[str]
    requires_hitl: bool
    auto_approve_reason: str
```

### Usage Example

```python
from src.agents.architecture_review_agent import ArchitectureReviewAgent

agent = ArchitectureReviewAgent(
    adr_directory="docs/architecture-decisions",
)

# Evaluate recommendations
trigger_events = agent.evaluate_recommendations(recommendations)

for trigger in trigger_events:
    print(f"[{trigger.significance.value}] {trigger.title}")
    print(f"  Category: {trigger.category.value}")
    print(f"  HITL Required: {trigger.requires_hitl}")
    if trigger.pattern_deviations:
        print(f"  Pattern Deviations: {trigger.pattern_deviations}")
```

---

## Agent 4: ADR Generator Agent

### Configuration

```yaml
name: adr-generator-agent
description: Generates fully-structured Architecture Decision Records from ADR trigger events, including context, alternatives, consequences, and references.
tools: Read, Write, Glob
model: sonnet
color: green
```

### Responsibilities

- Synthesize context from threat intelligence and recommendations
- Formulate decision with implementation steps
- Evaluate alternatives with pros/cons
- Analyze consequences (positive, negative, mitigation)
- Compile references
- Generate markdown ADR document
- Update README.md index

### ADR Document Structure

```markdown
# ADR-NNN: Title

**Status:** Proposed
**Date:** YYYY-MM-DD
**Decision Makers:** Aura Adaptive Intelligence

## Context
[Synthesized from threat intel, recommendations, and pattern analysis]

## Decision
[Implementation approach with steps, best practices, validation criteria]

## Alternatives Considered
[Category-specific alternatives with pros/cons]

## Consequences
### Positive
### Negative
### Mitigation

## References
[Related ADRs, CVEs, best practices, affected files]
```

### Output

```python
@dataclass
class ADRDocument:
    number: int
    title: str
    status: str
    date: str
    decision_makers: str
    context: str
    decision: str
    alternatives: list[dict]
    consequences_positive: list[str]
    consequences_negative: list[str]
    consequences_mitigation: list[str]
    references: list[str]

    def to_markdown(self) -> str: ...
    def get_filename(self) -> str: ...
```

### Usage Example

```python
from src.agents.adr_generator_agent import ADRGeneratorAgent

agent = ADRGeneratorAgent(
    adr_directory="docs/architecture-decisions",
)

# Generate ADRs from triggers
adrs = agent.generate_adrs(trigger_events)

# Save to filesystem
for adr in adrs:
    filepath = agent.save_adr(adr)
    print(f"Saved: {filepath}")

# Update README index
agent.update_readme_index(adrs)
```

---

## Full Pipeline Example

```python
import asyncio
from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent
from src.agents.adaptive_intelligence_agent import AdaptiveIntelligenceAgent
from src.agents.architecture_review_agent import ArchitectureReviewAgent
from src.agents.adr_generator_agent import ADRGeneratorAgent

async def run_adr_pipeline():
    # Initialize agents
    threat_agent = ThreatIntelligenceAgent()
    adaptive_agent = AdaptiveIntelligenceAgent()
    review_agent = ArchitectureReviewAgent()
    generator_agent = ADRGeneratorAgent()

    # Phase 1: Gather threat intelligence
    threat_reports = await threat_agent.gather_intelligence()
    print(f"Gathered {len(threat_reports)} threat reports")

    # Phase 2: Analyze and generate recommendations
    recommendations = adaptive_agent.analyze_threats(threat_reports)
    print(f"Generated {len(recommendations)} recommendations")

    # Phase 3: Evaluate for ADR-worthiness
    trigger_events = review_agent.evaluate_recommendations(recommendations)
    print(f"Identified {len(trigger_events)} ADR triggers")

    # Phase 4: Generate ADRs
    adrs = generator_agent.generate_adrs(trigger_events)
    print(f"Generated {len(adrs)} ADR documents")

    # Save and update index
    for adr in adrs:
        filepath = generator_agent.save_adr(adr)
        print(f"Saved: {filepath}")

    generator_agent.update_readme_index(adrs)

    return adrs

# Run pipeline
adrs = asyncio.run(run_adr_pipeline())
```

---

## Integration Points

### HITL Approval Workflow

For Critical/High significance ADRs:

1. ADR generated with `status: Proposed`
2. Notification sent via SNS to security team
3. Human reviews ADR in approval dashboard
4. Approve → Status changes to `Accepted`, changes deployed
5. Reject → Status changes to `Rejected`, feedback captured

### Sandbox Validation

Before HITL approval:

1. Recommended changes deployed to sandbox
2. Automated tests executed
3. Security scans run
4. Validation criteria checked
5. Results attached to ADR for review

### Cost Controls

Pipeline integrates with ADR-008 cost controls:

- LLM calls tracked per agent
- Token budgets enforced
- Rate limiting applied
- Costs attributed to ADR pipeline

---

## References

- `ADR-010-autonomous-adr-generation-pipeline.md` - Architecture decision
- `src/agents/threat_intelligence_agent.py` - Threat Intel Agent
- `src/agents/adaptive_intelligence_agent.py` - Adaptive Intel Agent
- `src/agents/architecture_review_agent.py` - Architecture Review Agent
- `src/agents/adr_generator_agent.py` - ADR Generator Agent
- `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Approval workflow
- `agent-config/agents/security-code-reviewer.md` - Security review patterns
