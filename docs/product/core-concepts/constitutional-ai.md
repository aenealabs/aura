# Constitutional AI

**Version:** 1.1
**Last Updated:** October 2026

---

## Overview

Constitutional AI (CAI) is Project Aura's principled approach to AI safety and alignment. Based on Anthropic's research (arXiv:2212.08073), it applies explicit principles to evaluate and refine agent outputs before they reach users or downstream systems.

Unlike traditional guardrails that simply block potentially harmful outputs, Constitutional AI engages constructively. When an agent output violates a principle, the system provides transparent reasoning and attempts revision rather than silent rejection.

> **Current status (October 2026):** The critique, revision, tiered-critique, fast-path, audit-queue, golden-set, and LLM-as-judge services are implemented with 535 tests, and the nightly evaluation Lambda runs them offline. Inline critique of live agent output is not yet active: agents opt in through `ConstitutionalMixin`, and no production agent class (Coder, Reviewer, Validator, or the orchestrator) uses it yet. The agent integration described below is the designed behavior.

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

- **Principled behavior**: Outputs are evaluated against explicit, documented principles (once agents adopt the mixin)
- **Transparent reasoning**: Users can see why outputs were flagged or revised
- **Constructive engagement**: Issues are explained, not just blocked
- **Continuous improvement**: Critique-revision history enables quality monitoring
- **Audit readiness**: Complete decision trails for compliance requirements

---

## The 16 Constitutional Principles

Aura's constitution (`src/services/constitutional_ai/constitution.yaml`) defines 16 principles across seven categories, each with a severity level that determines handling.

### Safety Principles (Critical Severity)

| Principle | Description |
|-----------|-------------|
| **Security-First Code Generation** | Never generate code that introduces vulnerabilities such as injection flaws or weakened security posture |
| **Data Protection and Privacy** | Avoid exposing or logging PII, credentials, or other sensitive data |
| **Sandbox Environment Isolation** | Never attempt to access resources outside the sandbox boundary |

### Compliance Principles (High Severity)

| Principle | Description |
|-----------|-------------|
| **Regulatory Compliance (CMMC/SOX/NIST)** | Outputs must align with applicable compliance frameworks |
| **Comprehensive Audit Trail** | Generated code logs security-relevant events with user attribution |

### Transparency Principles (High/Medium Severity)

| Principle | Severity | Description |
|-----------|----------|-------------|
| **Honest Capability Representation** | High | Do not claim actions or guarantees the system cannot deliver |
| **Transparent Reasoning Process** | Medium | Explain major decisions, trade-offs, and assumptions |

### Helpfulness Principles (Medium/Low Severity)

| Principle | Severity | Description |
|-----------|----------|-------------|
| **Genuinely Helpful Assistance** | Medium | Address the user's actual need with practical, actionable information |
| **Comprehensive Error Handling** | Medium | Handle operations that can fail with clear error messages |
| **Code Maintainability** | Low | Keep generated code readable, documented, and of manageable complexity |

### Anti-Sycophancy Principles (High/Medium Severity)

| Principle | Severity | Description |
|-----------|----------|-------------|
| **Honest Disagreement** | High | Do not agree with incorrect technical claims or validate bad practices |
| **Appropriate Opinion Persistence** | Medium | Do not abandon a correct position without new evidence |
| **Objective Technical Assessment** | Medium | Evaluate approaches without bias toward the user's preference |

### Code Quality Principles (Medium Severity)

| Principle | Description |
|-----------|-------------|
| **Project Pattern Consistency** | Follow established naming, structure, and error-handling conventions |
| **Code Testability** | Avoid hard dependencies, global state, and non-determinism that block testing |

### Meta Principles (High Severity)

| Principle | Description |
|-----------|-------------|
| **Principle Conflict Resolution** | When principles conflict, resolve the tension explicitly and prioritize by severity |

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

Constitutional AI is designed to integrate with Aura's multi-agent system through the `ConstitutionalMixin` (not yet adopted by production agent classes):

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
| Coder Agent | `code_generation`, `security` | Security-First Code Generation, Project Pattern Consistency, Code Testability |
| Reviewer Agent | `review`, `analysis` | Honest Disagreement, Objective Technical Assessment |
| Security Agent | `security`, `compliance` | Regulatory Compliance, Comprehensive Audit Trail |
| Validator Agent | `validation`, `testing` | Sandbox Environment Isolation, Comprehensive Error Handling |

---

## Trust Center Dashboard

The AI Trust Center provides visibility into Constitutional AI operations. By default the Trust Center API runs in mock mode and returns sample data; with `USE_AWS_DYNAMODB` set it reads principles, CloudWatch safety metrics, and DynamoDB audit decisions, but the Overview tab's compliance score (0.94) and 24-hour decision counts are still fixed placeholder values:

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
- [Trust Center Troubleshooting](../../support/troubleshooting/constitutional-ai-issues.md) - Debugging guide

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
