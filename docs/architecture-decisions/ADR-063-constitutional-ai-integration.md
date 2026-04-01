# ADR-063: Constitutional AI Integration

## Status

Deployed

## Date

2026-01-21

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-21 | Approve with modifications |
| Systems Review | Senior Systems Architect | 2026-01-21 | Approve with revisions |
| Kelly | Test Architect | 2026-01-21 | Approve with required changes |

### Review Summary

**Key Modifications (AWS/Infrastructure):**
- P1: Batch 16 principles into 2-3 LLM calls to meet <500ms P95 latency target
- P1: Use Haiku for critique (~$0.25/1M) and Sonnet for revision (~$3/1M) for cost optimization
- P1: Add SQS queue for async audit logging to avoid blocking critical path
- P2: Integrate with existing SemanticCacheService (ADR-029) for 30-40% cost savings
- P2: Use Bedrock Guardrails for CRITICAL principles (fast-fail under 100ms)
- P2: Add tiered critique strategy based on autonomy level

**Key Modifications (Systems Architecture):**
- P0: Implement explicit `ConstitutionalFailureConfig` with configurable policies
- P1: Make constitutional critique explicit at MetaOrchestrator level, not hidden in wrapper
- P1: Extend `DecisionAuditLogger` with constitutional-specific record types
- P1: Use `ConstitutionalMixin` pattern instead of wrapper for transparency
- P2: Split into `ConstitutionalCritiqueService` and `ConstitutionalRevisionService`
- P2: Add two-phase critique: parallel evaluation, sequential conflict resolution

**Kelly's Key Modifications (Testing Strategy):**
- P0: Implement 3-tier LLM mocking strategy (full mock, replay, semantic matching)
- P0: Create 100-case golden set before any principle deployment
- P1: Expand tests to 300+ (170 unit, 80 integration, 50 regression)
- P1: Build `assert_semantic_match` utilities for non-deterministic LLM outputs
- P2: Curate 500+ evaluation pairs with diversity requirements
- P2: Deploy CloudWatch metrics dashboard for CAI monitoring

## Context

### The Challenge of AI Agent Behavior

As Project Aura's autonomous agents (Coder, Reviewer, Validator) gain more capability and autonomy, ensuring consistent, safe, and helpful behavior becomes increasingly challenging. Current mechanisms have gaps:

| Current Mechanism | Gap |
|-------------------|-----|
| GUARDRAILS.md (ADR-021) | Rule-based, not principle-based reasoning |
| HITL Workflow (ADR-005) | Reactive approval, not proactive behavior shaping |
| Autonomy Framework (ADR-032) | Policy-based autonomy, not output quality assurance |
| Alignment Principles (ADR-052) | Framework exists but lacks formal critique-revision pipeline |

### Constitutional AI Methodology

Anthropic's Constitutional AI (CAI) research (arXiv:2212.08073) presents a training methodology that uses explicit principles—a "constitution"—to guide AI behavior through self-supervision:

**Key Findings from Research:**
- RLAIF (RL from AI Feedback) matches or exceeds RLHF (human feedback) quality
- Chain-of-thought reasoning improves evaluation accuracy: 26.0% → 5.8% error rate
- Non-evasive responses explain objections constructively rather than refusing to engage
- Soft preference labels (clamped to [0.4, 0.6] for CoT) improve training stability

### Opportunity

Implementing CAI methodology for Aura's agents enables:
1. **Principled output filtering** - Agent outputs critiqued against explicit security, compliance, and quality principles
2. **Non-evasive engagement** - Agents explain security concerns constructively, not refuse to help
3. **Transparent reasoning** - Chain-of-thought reasoning visible in audit logs
4. **Continuous improvement** - Critique-revision history informs agent fine-tuning

## Decision

Implement a Constitutional AI integration layer that applies critique-revision to all agent outputs before they reach users or downstream systems.

### Core Capabilities

1. **Constitutional Critique** - Evaluate agent outputs against 16 domain-specific principles
2. **Chain-of-Thought Reasoning** - Transparent reasoning chains for all critiques
3. **Automatic Revision** - Revise outputs that violate CRITICAL/HIGH severity principles
4. **Preference Evaluation** - Compare response pairs for agent training improvement
5. **Non-Evasive Patterns** - Explain objections constructively, offer alternatives

## Architecture

### Constitutional AI Integration Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Constitutional AI Integration                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        MetaOrchestrator                              │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │   │
│  │  │ Coder Agent │   │ Reviewer    │   │ Validator   │                │   │
│  │  │ (+ Mixin)   │   │ Agent       │   │ Agent       │                │   │
│  │  │             │   │ (+ Mixin)   │   │ (+ Mixin)   │                │   │
│  │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                │   │
│  │         │                 │                 │                        │   │
│  │         └─────────────────┼─────────────────┘                        │   │
│  │                           ▼                                          │   │
│  │              ┌─────────────────────────────┐                         │   │
│  │              │ ConstitutionalCritiqueService│                        │   │
│  │              │ (Parallel, Batched)          │                        │   │
│  │              └──────────────┬───────────────┘                        │   │
│  │                             │                                        │   │
│  │              ┌──────────────┼──────────────┐                         │   │
│  │              ▼              ▼              ▼                         │   │
│  │        ┌──────────┐  ┌───────────┐  ┌──────────┐                    │   │
│  │        │ Bedrock  │  │ Bedrock   │  │ Semantic │                    │   │
│  │        │ Guardrails│  │ Haiku    │  │ Cache    │                    │   │
│  │        │ (Fast)   │  │ (Critique)│  │ (ADR-029)│                    │   │
│  │        └──────────┘  └───────────┘  └──────────┘                    │   │
│  │                             │                                        │   │
│  │              ┌──────────────▼───────────────┐                        │   │
│  │              │ ConstitutionalRevisionService │                        │   │
│  │              │ (Sonnet, Stateful)            │                        │   │
│  │              └──────────────┬───────────────┘                        │   │
│  └─────────────────────────────┼───────────────────────────────────────┘   │
│                                │                                            │
│  ┌─────────────────────────────▼───────────────────────────────────────┐   │
│  │                    Supporting Services                               │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ DecisionAudit   │  │ CognitiveMemory │  │ SQS Audit Queue     │  │   │
│  │  │ Logger          │  │ Service         │  │ (Async Persistence) │  │   │
│  │  │ (ADR-052)       │  │ (ADR-021)       │  │                     │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Optimized Latency Architecture (Per Architecture Review)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│              Critique Pipeline - Target: <500ms P95                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Agent Output                                                           │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Semantic Cache Check (10ms)                            │   │
│  │ - Hash(output + context)                                        │   │
│  │ - Check Redis for recent identical critique                     │   │
│  │ - Target hit rate: 30-40%                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │ Cache miss                                                      │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: Bedrock Guardrails Fast-Fail (100ms)                   │   │
│  │ - Parallel safety check for CRITICAL principles (1-3)          │   │
│  │ - No LLM call for blocked content                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │ Pass                                                            │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 3: Batched Principle Critique (200-300ms)                 │   │
│  │ - Batch 16 principles into 2-3 Haiku calls                      │   │
│  │ - Single prompt evaluates 5-6 principles with CoT               │   │
│  │ - Parallel execution of batches                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Layer 4: Async Persistence (0ms perceived)                      │   │
│  │ - Fire-and-forget to SQS queue                                  │   │
│  │ - Lambda consumer writes to DynamoDB/Neptune                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Total Critical Path: 10 + 100 + 300 = 410ms P95                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Constitutional Principles

### Aura Constitution (16 Principles)

| ID | Name | Severity | Category |
|----|------|----------|----------|
| 1 | Security-First Code Generation | CRITICAL | Safety |
| 2 | Non-Destructive Defaults | CRITICAL | Safety |
| 3 | Sandbox Containment Awareness | CRITICAL | Safety |
| 4 | Regulatory Compliance | HIGH | Compliance |
| 5 | Decision Audit Trail | HIGH | Compliance |
| 6 | Honest Uncertainty Expression | MEDIUM | Transparency |
| 7 | Transparent Reasoning Chain | MEDIUM | Transparency |
| 8 | Genuine Technical Assistance | MEDIUM | Helpfulness |
| 9 | Non-Evasive Security Discussion | MEDIUM | Helpfulness |
| 10 | Independent Technical Judgment | HIGH | Anti-Sycophancy |
| 11 | Constructive Technical Pushback | MEDIUM | Anti-Sycophancy |
| 12 | Long-Term Maintainability | LOW | Code Quality |
| 13 | Minimal Necessary Change | LOW | Code Quality |
| 14 | Codebase Pattern Consistency | LOW | Context |
| 15 | Context Window Preservation | LOW | Context |
| 16 | Principle Conflict Resolution | HIGH | Meta |

### Principle Priority Ordering

When principles conflict, resolution follows this priority:
1. **Security** (Principles 1-3) - Always highest priority
2. **Compliance** (Principles 4-5) - Regulatory requirements
3. **Anti-Sycophancy** (Principles 10-11) - Honest feedback over agreement
4. **Helpfulness** (Principles 8-9) - Genuine assistance
5. **Code Quality** (Principles 12-15) - Lowest priority

## Implementation

### Service Layer (Per Systems Architecture Review)

```python
# src/services/constitutional_ai/critique_service.py

class ConstitutionalCritiqueService:
    """Stateless critique evaluation - horizontally scalable."""

    async def critique_output(
        self,
        agent_output: str,
        context: Dict[str, Any],
        applicable_principles: Optional[List[str]] = None
    ) -> List[CritiqueResult]:
        """
        Apply constitutional critique with parallel batched evaluation.

        Uses two-phase approach:
        1. Parallel evaluation of principle batches
        2. Sequential conflict resolution (Principle 16)
        """
        ...


# src/services/constitutional_ai/revision_service.py

class ConstitutionalRevisionService:
    """Orchestrates revision cycles - maintains session state."""

    async def revise_with_feedback(
        self,
        agent_output: str,
        critiques: List[CritiqueResult],
        context: Dict[str, Any],
        max_iterations: int = 3
    ) -> RevisionResult:
        """Apply revision with isolated session state."""
        ...
```

### Failure Handling (Per Systems Architecture Review - P0)

```python
# src/services/constitutional_ai/failure_policy.py

class CritiqueFailurePolicy(Enum):
    BLOCK = "block"                    # Block output, require HITL
    PROCEED_LOGGED = "proceed_logged"  # Log failure, proceed
    PROCEED_FLAGGED = "proceed_flagged" # Proceed but flag for review (DEFAULT)
    RETRY_THEN_BLOCK = "retry_then_block"

class RevisionFailurePolicy(Enum):
    RETURN_ORIGINAL = "return_original"
    RETURN_BEST_EFFORT = "return_best_effort"
    BLOCK_FOR_HITL = "block_for_hitl"  # DEFAULT for CRITICAL issues

@dataclass
class ConstitutionalFailureConfig:
    critique_failure_policy: CritiqueFailurePolicy = CritiqueFailurePolicy.PROCEED_FLAGGED
    revision_failure_policy: RevisionFailurePolicy = RevisionFailurePolicy.BLOCK_FOR_HITL
    max_critique_retries: int = 2
    require_audit_trail: bool = True
```

### Agent Integration (ConstitutionalMixin Pattern)

```python
# src/agents/constitutional_mixin.py

class ConstitutionalMixin:
    """
    Mixin that adds constitutional oversight to agents.

    Preferred over wrapper pattern for:
    - Transparency (explicit opt-in)
    - Type preservation (maintains agent type hierarchy)
    - Testability (easy to test in isolation)

    Usage:
        class CoderAgent(ConstitutionalMixin, MCPEnabledAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                result = await self._generate_code(task)
                return await self.finalize_with_constitutional(result, task)
    """

    async def finalize_with_constitutional(
        self,
        result: AgentResult,
        task: AgentTask,
    ) -> AgentResult:
        """Apply constitutional critique before returning result."""
        ...
```

### Files Created

| File | Purpose |
|------|---------|
| `src/services/constitutional_ai/__init__.py` | Package initialization |
| `src/services/constitutional_ai/constitution.yaml` | 16 principles with prompts |
| `src/services/constitutional_ai/preference_principles.yaml` | RLAIF evaluation principles |
| `src/services/constitutional_ai/critique_service.py` | Stateless critique evaluation |
| `src/services/constitutional_ai/revision_service.py` | Stateful revision orchestration |
| `src/services/constitutional_ai/failure_policy.py` | Failure handling configuration |
| `src/services/constitutional_ai/contracts.py` | Pydantic contract schemas |
| `src/services/constitutional_ai/metrics.py` | Observability metrics |
| `src/agents/constitutional_mixin.py` | Agent integration mixin |
| `tests/services/test_constitutional_ai/` | Test suite (300+ tests) |
| `tests/fixtures/constitutional_ai_dataset/` | Evaluation dataset (500+ pairs) |

### DynamoDB Tables

| Table | Purpose |
|-------|---------|
| `aura-constitutional-audit-{env}` | Critique/revision audit records |
| `aura-constitutional-metrics-{env}` | Aggregated metrics for dashboards |

### CloudWatch Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `CritiqueLatencyP95` | P95 latency for critique | <500ms |
| `CritiqueAccuracy` | Agreement with human evaluation | >90% |
| `RevisionConvergenceRate` | Revisions that resolve issues | >95% |
| `CacheHitRate` | Semantic cache effectiveness | >30% |
| `NonEvasiveRate` | Constructive engagement rate | >70% |

## Cost Analysis

### Monthly Cost Projections

| Scenario | Bedrock Calls/Day | Monthly Cost |
|----------|-------------------|--------------|
| Unoptimized (16 sequential) | 160,000 | $12,000-15,000 |
| Optimized (batched) | 30,000 | $2,500-3,500 |
| With Caching (40% hit) | 18,000 | $1,500-2,000 |

### Cost Optimization Strategies

1. **Model Tiering:** Haiku for critique ($0.25/1M), Sonnet for revision ($3/1M)
2. **Semantic Caching:** Integrate with ADR-029 infrastructure (30-40% savings)
3. **Tiered Critique:** FULL_HITL gets MINIMAL critique (human reviews anyway)
4. **Batch Processing:** Combine principles into fewer LLM calls

## Testing Strategy (Per Kelly's Review)

### Test Pyramid

| Tier | Tests | Coverage |
|------|-------|----------|
| Unit Tests | 170 | All principles, parsing, conflict resolution |
| Integration Tests | 80 | Agent integration, audit logging, memory storage |
| Regression Tests | 50 | Golden set baseline preservation |
| **Total** | **300** | |

### LLM Mocking Strategy (3-Tier)

1. **Tier 1 (Unit Tests):** Full LLM mocking with deterministic responses
2. **Tier 2 (Integration):** Replay recorded responses with semantic matching
3. **Tier 3 (Evaluation):** LLM-as-Judge for quality metrics (nightly)

### Semantic Matching for Non-Deterministic Outputs

```python
def assert_semantic_match(
    actual: str,
    expected_concepts: List[str],
    min_concept_matches: int = 2
) -> None:
    """Assert text contains expected semantic concepts."""
    ...
```

### Golden Set Requirements

- 100 hand-verified critique/revision pairs
- Coverage of all 16 principles
- Security/compliance scenarios prioritized
- Run before any principle changes

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

| Task | Deliverable |
|------|-------------|
| Create constitution.yaml | 16 principles with critique/revision prompts |
| Implement ConstitutionalCritiqueService | Batched parallel critique |
| Implement failure handling | ConstitutionalFailureConfig |
| Unit tests with mocking | 170 tests |

### Phase 2: Integration (Weeks 3-4)

| Task | Deliverable |
|------|-------------|
| Implement ConstitutionalMixin | Agent integration pattern |
| Extend DecisionAuditLogger | Constitutional record types |
| Connect to CognitiveMemoryService | Episodic memory for learning |
| Integration tests | 80 tests |

### Phase 3: Optimization (Weeks 5-6)

| Task | Deliverable |
|------|-------------|
| Integrate semantic caching | ADR-029 integration |
| Add Bedrock Guardrails fast-path | CRITICAL principle acceleration |
| Implement tiered critique strategy | Autonomy-based critique levels |
| SQS async audit queue | Non-blocking persistence |

### Phase 4: Evaluation (Weeks 7-8)

| Task | Deliverable |
|------|-------------|
| Curate evaluation dataset | 500+ response pairs |
| Implement LLM-as-Judge pipeline | Nightly quality evaluation |
| Deploy CloudWatch dashboard | Observability metrics |
| Create regression golden set | 100 verified cases |

### Phase 5: Production (Week 9)

| Task | Deliverable |
|------|-------------|
| Enable for FULL_AUTONOMOUS agents | High-risk agents first |
| Human evaluation baseline | Monthly review protocol |
| Documentation | Operations runbook |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| Amazon Bedrock | Yes | Claude 3.x models available |
| DynamoDB | Yes | Full feature parity |
| Neptune | Yes | Provisioned only (no Serverless) |
| SQS | Yes | FIFO queues supported |
| Lambda | Yes | Full feature parity |

**GovCloud-Specific Requirements:**
- Use `${AWS::Partition}` in all ARNs
- Configure FIPS endpoints for Bedrock
- Neptune must use provisioned instances (not Serverless)
- Audit log retention must meet CMMC requirements (1+ year)

## Consequences

### Positive

1. **Principled Agent Behavior:** All outputs reviewed against explicit constitution
2. **Non-Evasive Engagement:** Agents explain concerns constructively
3. **Transparent Reasoning:** CoT reasoning visible in audit logs
4. **Cost-Effective:** Optimized architecture reduces costs by ~85%
5. **Compliance-Ready:** Full audit trail for CMMC/SOX requirements

### Negative

1. **Latency Overhead:** 400-500ms added to agent execution
2. **Complexity:** Additional service layer to maintain
3. **LLM Dependency:** Critique quality depends on model capability

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-revision degrades quality | Medium | High | A/B testing, configurable severity threshold |
| Latency exceeds target | Medium | Medium | Parallel batching, caching, fast-path for common patterns |
| Principle conflicts create deadlock | Low | High | Explicit priority ordering (Principle 16) |
| LLM hallucination in critique | Medium | Medium | Require specific evidence citations, semantic validation |

## References

1. Bai, Y., et al. "Constitutional AI: Harmlessness from AI Feedback." arXiv:2212.08073, 2022.
2. ADR-052: AI Alignment Principles
3. ADR-021: Guardrails Cognitive Architecture
4. ADR-032: Configurable Autonomy Framework
5. ADR-029: Agent Optimization (Semantic Caching)
6. Research Proposal: `/docs/research/proposals/CONSTITUTIONAL-AI-PROPOSAL.md`
