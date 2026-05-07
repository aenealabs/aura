# Constitutional AI

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

Constitutional AI (CAI) is Project Aura's principled approach to AI safety and alignment. Based on Anthropic's research (arXiv:2212.08073), it applies explicit principles to evaluate and refine agent outputs before they reach users or downstream systems.

Unlike traditional guardrails that simply block potentially harmful outputs, Constitutional AI engages constructively. When an agent output violates a principle, the system provides transparent reasoning and attempts revision rather than silent rejection.

---

## Why Constitutional AI Matters

Enterprise AI systems face a fundamental tension:

| Challenge | Traditional Approach | Constitutional AI Approach |
|-----------|---------------------|---------------------------|
| **Safety** | Hard blocks, refusals | Constructive engagement with explanation |
| **Compliance** | Static rule matching | Principled evaluation with audit trail |
| **Sycophancy** | Unchecked agreement | Independent judgment, constructive pushback |
| **Transparency** | Black-box decisions | Explicit reasoning chains |
| **Trust** | "Trust us" claims | Verifiable principle adherence |

Constitutional AI provides:

- **Principled behavior**: Every output is evaluated against explicit, documented principles
- **Transparent reasoning**: Users can see why outputs were flagged or revised
- **Constructive engagement**: Issues are explained, not just blocked
- **Continuous improvement**: Critique-revision history enables quality monitoring
- **Audit readiness**: Complete decision trails for compliance requirements

---

## The 16 Constitutional Principles

Aura's constitution defines 16 principles across six categories, each with specific severity levels that determine handling.

### Safety Principles (Critical Severity)

| Principle | Description |
|-----------|-------------|
| **Security-First** | Never generate code that introduces vulnerabilities or weakens security posture |
| **Non-Destructive Defaults** | Default to read-only operations; require explicit confirmation for destructive actions |
| **Sandbox Containment** | All generated code must be testable in isolated sandbox environments |

### Compliance Principles (High Severity)

| Principle | Description |
|-----------|-------------|
| **Regulatory Alignment** | Outputs must align with applicable compliance frameworks (CMMC, SOX, NIST) |
| **Audit Trail** | All decisions must be logged with sufficient detail for compliance audits |

### Anti-Sycophancy Principles (High/Medium Severity)

| Principle | Description |
|-----------|-------------|
| **Independent Judgment** | Maintain technical accuracy even when it contradicts user expectations |
| **Constructive Pushback** | Respectfully challenge requests that would compromise security or quality |

### Transparency Principles (Medium Severity)

| Principle | Description |
|-----------|-------------|
| **Uncertainty Expression** | Clearly communicate confidence levels and limitations |
| **Reasoning Chain** | Provide step-by-step explanation for significant decisions |

### Helpfulness Principles (Medium Severity)

| Principle | Description |
|-----------|-------------|
| **Genuine Assistance** | Focus on solving the user's actual problem, not just the literal request |
| **Non-Evasive Engagement** | When unable to fulfill a request, explain why and offer alternatives |

### Code Quality Principles (Low Severity)

| Principle | Description |
|-----------|-------------|
| **Maintainability** | Generated code should be readable, well-structured, and maintainable |
| **Minimal Change** | Patches should make the minimum changes necessary to fix the issue |
| **Pattern Consistency** | Follow existing codebase patterns and conventions |
| **Context Preservation** | Maintain surrounding code context and avoid unintended side effects |

### Meta Principles (High Severity)

| Principle | Description |
|-----------|-------------|
| **Principle Conflict Resolution** | When principles conflict, prioritize by severity (Critical > High > Medium > Low) |

---

## How Constitutional AI Works

### The Critique-Revision Pipeline

```
Agent Output
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    CRITIQUE PHASE                           │
│                                                             │
│  1. Load applicable principles (filtered by domain tags)    │
│  2. Batch principles into 2-3 LLM calls for efficiency      │
│  3. Evaluate output against each principle                  │
│  4. Generate critique with severity and reasoning           │
│                                                             │
│  Model: Claude Haiku (fast, cost-effective)                 │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    DECISION GATE                            │
│                                                             │
│  No Issues Found ──────────────────────────▶ Pass Through   │
│                                                             │
│  Issues Found:                                              │
│    - CRITICAL severity ──▶ Block or HITL escalation         │
│    - HIGH severity ──────▶ Revision required                │
│    - MEDIUM/LOW severity ─▶ Flag and proceed (configurable) │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    REVISION PHASE                           │
│                                                             │
│  1. Provide original output + critique to revision model    │
│  2. Generate revised output addressing identified issues    │
│  3. Re-evaluate revised output (max 3 iterations)           │
│  4. Return final output with revision history               │
│                                                             │
│  Model: Claude Sonnet (higher capability for revisions)     │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
Final Output (with audit trail)
```

### Cost Optimization

Constitutional AI uses tiered model selection to balance quality and cost:

| Phase | Model | Cost (per 1M tokens) | Rationale |
|-------|-------|---------------------|-----------|
| Critique | Claude Haiku | ~$0.25 | Fast pattern matching, high volume |
| Revision | Claude Sonnet | ~$3.00 | Higher capability for nuanced fixes |
| Deep Analysis | Claude Opus | ~$15.00 | Complex edge cases only |

**Projected savings:** ~85% cost reduction vs. using Sonnet for all evaluations.

### Semantic Caching

To further optimize costs and latency, Constitutional AI implements semantic caching:

- Similar outputs reuse cached critique results
- Cache hit rate target: >30%
- TTL-based expiration prevents stale evaluations
- Hash-based keys enable fast lookups

---

## Failure Handling Policies

When Constitutional AI detects principle violations, the response is configurable:

| Policy | Behavior | Use Case |
|--------|----------|----------|
| **BLOCK** | Halt processing, return error | Critical security violations |
| **PROCEED_FLAGGED** | Continue with warning flag | Medium-severity issues for human review |
| **RETRY_THEN_BLOCK** | Attempt revision, block if unresolved | High-severity issues worth attempting fix |
| **PROCEED_LOGGED** | Continue silently, log for audit | Low-severity, informational issues |

Organizations can configure default policies per principle severity level.

---

## Integration with Agents

Constitutional AI integrates with Aura's multi-agent system through the `ConstitutionalMixin`:

```
┌─────────────────────────────────────────────────────────────┐
│                     CODER AGENT                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ConstitutionalMixin                    │    │
│  │                                                     │    │
│  │  process_with_constitutional(output)                │    │
│  │    → Applies Security, Code Quality principles      │    │
│  │    → Domain tags: ["code_generation", "security"]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    REVIEWER AGENT                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ConstitutionalMixin                    │    │
│  │                                                     │    │
│  │  process_with_constitutional(output)                │    │
│  │    → Applies Anti-Sycophancy, Transparency          │    │
│  │    → Domain tags: ["review", "analysis"]            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Each agent type has preconfigured domain tags that determine which principles apply:

| Agent | Domain Tags | Primary Principles |
|-------|-------------|-------------------|
| Coder Agent | `code_generation`, `security` | Security-First, Minimal Change, Pattern Consistency |
| Reviewer Agent | `review`, `analysis` | Independent Judgment, Constructive Pushback |
| Security Agent | `security`, `compliance` | Regulatory Alignment, Audit Trail |
| Validator Agent | `validation`, `testing` | Sandbox Containment, Non-Destructive Defaults |

---

## Trust Center Dashboard

The AI Trust Center provides real-time visibility into Constitutional AI operations:

### Overview Tab
- System health status (Healthy / Warning / Critical)
- Compliance score gauge
- Active principles count
- Pending HITL approvals

### Principles Tab
- Browse all 16 principles
- Filter by category and severity
- View principle definitions and examples

### Autonomy Tab
- Current autonomy level indicator
- HITL configuration status
- Guardrail settings

### Metrics Tab
- Critique accuracy trend (target: >90%)
- Revision convergence rate (target: >95%)
- Cache hit rate (target: >30%)
- Latency P95 (target: <500ms)
- Issues by severity breakdown

### Audit Tab
- Decision timeline with filtering
- Principle violation history
- HITL escalation records

---

## Performance Targets

| Metric | Target | Description |
|--------|--------|-------------|
| **Critique Latency P95** | <500ms | 95th percentile response time for critique evaluation |
| **Critique Accuracy** | >90% | Agreement with human evaluation on golden set |
| **Revision Convergence** | >95% | Percentage of revisions that successfully resolve issues |
| **Cache Hit Rate** | >30% | Semantic cache effectiveness for repeated patterns |
| **Non-Evasive Rate** | >70% | Constructive engagement vs. refusal rate |
| **Golden Set Pass Rate** | >95% | Regression test suite for known-good behaviors |

---

## Quality Assurance

### LLM-as-Judge Evaluation

Nightly automated evaluation pipeline:

1. Load 50-100 response pairs from evaluation dataset
2. Run LLM-as-Judge assessment (independent model)
3. Compare with human-labeled preferences
4. Compute accuracy and convergence metrics
5. Publish results to CloudWatch dashboard
6. Alert on regressions via SNS

### Golden Set Regression Testing

100 verified test cases covering:

- Security edge cases (30 cases)
- Compliance scenarios (25 cases)
- Helpfulness balance (25 cases)
- Anti-sycophancy challenges (20 cases)

Any regression in golden set pass rate triggers immediate investigation.

---

## Related Documentation

### Technical References
- [ADR-063: Constitutional AI Integration](../../architecture-decisions/ADR-063-constitutional-ai-integration.md) - Full technical specification
- [Trust Center Troubleshooting](../../support/troubleshooting/constitutional-ai-troubleshooting.md) - Debugging guide

### Related Concepts
- [Multi-Agent System](./multi-agent-system.md) - How agents use Constitutional AI
- [HITL Workflows](./hitl-workflows.md) - Human approval integration
- [Sandbox Security](./sandbox-security.md) - Isolated validation environments

---

## Key Takeaways

1. **Constitutional AI is principled, not reactive** - Explicit principles guide behavior, not ad-hoc rules
2. **Engagement over refusal** - The system explains concerns and attempts revision before blocking
3. **Transparency is built-in** - Every decision has an audit trail with reasoning
4. **Cost-optimized by design** - Tiered models and caching keep costs manageable at scale
5. **Continuously monitored** - Nightly evaluation ensures quality doesn't degrade over time

---

## Questions?

If you have questions about Constitutional AI:

- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Email:** support@aenealabs.com
