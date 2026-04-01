# ADR-021: Guardrails Cognitive Architecture for Specialized Agents

**Status:** Deployed
**Date:** 2025-12-04
**Decision Makers:** Project Aura Team
**Related:** `agent-config/schemas/cognitive-memory-schema.md`, `src/services/cognitive_memory_service.py`

## Context

Project Aura's specialized agents (Security Code Reviewer, Code Quality Reviewer, etc.) operate autonomously on complex tasks. During development, we observed agents repeating mistakes that had been solved previously, deviating from established codebase patterns, and failing to leverage institutional knowledge.

**Problem Statement:**
- Agents lack persistent memory across sessions
- Lessons learned from debugging sessions are lost
- Pattern compliance requires manual enforcement
- No mechanism for agents to "learn" from past failures
- Context window limitations prevent loading all relevant documentation

**Triggering Incident:**
A CI/CD buildspec modification failed repeatedly due to YAML parsing errors. The correct pattern (multiline blocks) existed in other buildspec files, but the agent attempted novel approaches instead of checking existing patterns first. This wasted significant development time and highlighted the need for institutional memory.

**Research Foundation:**
Neuroscience research on human cognition informs this design:
- Working memory has limited capacity (Miller's Law: 7±2 items)
- Long-term memory uses semantic, episodic, and procedural stores
- Schema-based reasoning enables decisions with ambiguous information
- Metacognition allows confidence estimation and strategy selection
- Hippocampal pattern completion enables retrieval from sparse cues
- Memory consolidation extracts patterns during "offline" processing

**Target Performance:** 85% accuracy when operating with incomplete context

## Decision

We implement a **Guardrails Cognitive Architecture** with three tiers:

```
┌─────────────────────────────────────────────────────────────────┐
│                 Guardrails Cognitive Architecture                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TIER 1: Static Guardrails              │  │
│  │                                                            │  │
│  │  GUARDRAILS.md ──────────────┐                            │  │
│  │  (Pattern Compliance,        │                            │  │
│  │   Anti-patterns,             │  Semantic Index            │  │
│  │   Required Patterns)         │  (Vector Embeddings)       │  │
│  │                              ▼                            │  │
│  │  Domain Schemas ────────> OpenSearch                      │  │
│  │  (CI/CD, IAM, Security)   Vector Store                    │  │
│  │                                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              │ Query by domain tags             │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 TIER 2: Dynamic Context                   │  │
│  │                                                            │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │  │
│  │  │   Attention  │    │  Confidence  │    │   Schema   │  │  │
│  │  │   Gating     │    │  Estimation  │    │ Activation │  │  │
│  │  └──────┬───────┘    └──────┬───────┘    └─────┬──────┘  │  │
│  │         │                   │                   │         │  │
│  │         │   ┌───────────────┼───────────────┐   │         │  │
│  │         └───►   Working Memory (Context)   ◄───┘         │  │
│  │             │   - Current task context     │             │  │
│  │             │   - Retrieved guardrails     │             │  │
│  │             │   - Active schema            │             │  │
│  │             └───────────────┬───────────────┘             │  │
│  │                             │                             │  │
│  └─────────────────────────────┼─────────────────────────────┘  │
│                                │                                │
│                                │ Execution + Outcome            │
│                                ▼                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 TIER 3: Learning Loop                     │  │
│  │                                                            │  │
│  │  Task Outcome ─────► Consolidation ─────► New Guardrails  │  │
│  │  (Success/Fail)      (Pattern Extract)   (Proposed Entry) │  │
│  │                                                            │  │
│  │  Human Review ──────────────────────────► GUARDRAILS.md   │  │
│  │                     Approval                              │  │
│  │                                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation Components:**

| Component | Purpose | Location |
|-----------|---------|----------|
| `GUARDRAILS.md` | Structured lessons learned with domain tags | Root directory |
| Domain Schemas | Structured templates for common task types | `agent-config/schemas/` |
| Confidence Thresholds | Severity-based guardrail selection | Agent configuration |
| Consolidation Prompts | Extract patterns from failures | Agent templates |

**Cognitive Mechanisms:**

| Mechanism | Human Analog | Implementation |
|-----------|--------------|----------------|
| **Attention Gating** | Selective attention | Domain tags filter relevant guardrails |
| **Schema Activation** | Mental models | Pre-loaded templates for task types |
| **Confidence Estimation** | Metacognition | Severity levels + query specificity |
| **Consolidation** | Sleep-based memory consolidation | End-of-task pattern extraction |

## Alternatives Considered

### Alternative 1: Comprehensive Documentation Loading

Load all documentation (CLAUDE.md, design principles, runbooks) into context for every task.

**Pros:**
- Complete information always available
- No retrieval complexity
- Simple implementation

**Cons:**
- Context window exhaustion (100K+ tokens of docs)
- Slow response times
- No prioritization of relevant information
- Same information regardless of task type
- **Does not scale as documentation grows**

### Alternative 2: Pure RAG (No Structure)

Use vector similarity search without domain tags or schemas.

**Pros:**
- Fully automated retrieval
- No manual tagging required
- Adapts to query content

**Cons:**
- May retrieve irrelevant similar-looking content
- No severity prioritization
- Harder to audit what was retrieved
- Missing structural constraints for specific domains
- **Unpredictable behavior on edge cases**

### Alternative 3: Rule-Based Expert System

Hard-coded rules for each domain with if-then logic.

**Pros:**
- Predictable behavior
- Auditable decisions
- Fast execution

**Cons:**
- Brittle to new situations
- Requires developer updates for new rules
- Cannot handle ambiguous cases
- No learning from failures
- **Does not leverage LLM reasoning capabilities**

### Alternative 4: Fine-Tuned Models

Train domain-specific models on Project Aura patterns.

**Pros:**
- Patterns encoded in weights
- Fast inference
- No retrieval needed

**Cons:**
- Expensive to train and maintain
- Requires large training dataset
- Catastrophic forgetting when updating
- Cannot easily audit what was learned
- **Not practical for rapidly evolving patterns**

## Consequences

### Positive

1. **Pattern Compliance**
   - Agents automatically check relevant guardrails before implementation
   - Established patterns are surfaced contextually
   - Reduces deviation from approved approaches

2. **Institutional Memory**
   - Lessons learned persist across sessions
   - New team members (human or AI) inherit accumulated knowledge
   - Debugging insights captured in structured format

3. **Scalable Context Management**
   - Only relevant guardrails loaded per task
   - Domain tags enable efficient filtering
   - Schemas provide structure without exhausting context

4. **Auditable Decisions**
   - Guardrail IDs referenced in agent reasoning
   - Clear traceability from decision to source
   - Human-reviewable learning loop

5. **Graceful Degradation**
   - Low confidence → more guardrails loaded
   - Unknown domains → fall back to general patterns
   - Missing guardrails → agent proceeds with caution flag

### Negative

1. **Maintenance Overhead**
   - Guardrails must be kept up-to-date
   - Deprecated patterns need archival
   - Schema evolution requires coordination

2. **Initial Setup Cost**
   - Requires populating initial guardrails from existing knowledge
   - Domain schemas must be created
   - Vector index integration needed

3. **False Confidence Risk**
   - Agents may over-rely on guardrails
   - Novel situations not covered by existing entries
   - Guardrails may become outdated without review

### Mitigation

- **Scheduled Review:** Quarterly guardrail audit for relevance
- **Confidence Calibration:** Track guardrail application success rate
- **Feedback Loop:** Easy mechanism to propose new guardrails from failures
- **Staleness Detection:** Flag guardrails not referenced in N months

## Implementation Details

### Phase 1: Foundation (Current)

```markdown
# GUARDRAILS.md Structure

## GR-{DOMAIN}-{NUMBER}: {Title}

**Domain:** [CICD|IAM|SECURITY|CFN|...]
**Severity:** Critical | High | Medium | Low
**Date Added:** YYYY-MM-DD

### Context
{When this guardrail applies}

### Required Pattern
{Code examples of correct approach}

### Anti-Pattern
{Code examples of what NOT to do}

### Verification
{How to confirm compliance}
```

### Phase 2: Schema Integration

```yaml
# agent-config/schemas/cicd-schema.md
name: CI/CD Task Schema
domain: CICD
required_guardrails:
  - GR-CICD-001  # Pattern Compliance
  - GR-SEC-001   # SSM Parameters
pre_task_checks:
  - "Search for existing buildspec patterns"
  - "Check if similar deployment exists"
post_task_validation:
  - "Verify YAML syntax"
  - "Confirm no hardcoded values"
```

### Phase 3: Vector Integration

```python
# Pseudo-code for guardrail retrieval
def retrieve_guardrails(task_description: str, domain: str) -> list[Guardrail]:
    # 1. Filter by domain tag
    domain_guardrails = filter_by_domain(domain)

    # 2. Semantic search within domain
    relevant = vector_search(task_description, domain_guardrails)

    # 3. Sort by severity (Critical first)
    sorted_guardrails = sort_by_severity(relevant)

    # 4. Apply context budget
    return truncate_to_budget(sorted_guardrails, max_tokens=2000)
```

## Security Considerations

1. **Guardrail Integrity**
   - GUARDRAILS.md is version-controlled
   - Changes require human review (PR process)
   - Audit log of modifications

2. **Injection Prevention**
   - Guardrail content sanitized before embedding
   - Agent cannot modify GUARDRAILS.md directly
   - Proposed guardrails go through human approval

3. **Access Control**
   - Agents have read-only access to guardrails
   - Only approved roles can merge guardrail updates
   - Sensitive guardrails can be restricted by domain

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Pattern compliance rate | >95% | Manual audit of agent outputs |
| Repeated mistakes | <5% | Track recurring error types |
| Guardrail utilization | >80% | Log guardrail references in reasoning |
| Time to resolve failures | -30% | Compare pre/post implementation |
| False positive rate | <10% | Guardrails flagged but irrelevant |

## References

- `GUARDRAILS.md` - Active guardrails document
- `agent-config/agents/security-code-reviewer.md` - Specialized agent template
- `CLAUDE.md#pattern-compliance` - Pattern compliance requirements
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [Schema Theory in Cognitive Psychology](https://en.wikipedia.org/wiki/Schema_(psychology))

---

## Extended Architecture: Full Neuroscience Mapping

The following extends the three-tier architecture with a complete neuroscience-inspired memory system.

### Neuroscience-to-Architecture Mapping

| Brain Region | Function | Implementation | Storage |
|-------------|----------|----------------|---------|
| **Hippocampus** | Episodic memory (specific events) | `EpisodicMemory` class | DynamoDB |
| **Neocortex** | Semantic memory (facts, concepts) | `SemanticMemory` class | Neptune + OpenSearch |
| **Basal Ganglia** | Procedural memory (skills, habits) | `ProceduralMemory` class | DynamoDB + Neptune |
| **Prefrontal Cortex** | Working memory, executive function | `WorkingMemory` class | In-memory |
| **CA3 Region** | Pattern completion | `PatternCompletionRetriever` | Algorithm |
| **Hippocampal Replay** | Memory consolidation | `ConsolidationPipeline` | Lambda + Step Functions |

### Full Cognitive Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COGNITIVE MEMORY ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     METACOGNITIVE LAYER                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │  Confidence  │  │   Strategy   │  │   Accuracy   │               │   │
│  │  │  Estimator   │  │   Selector   │  │   Monitor    │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       WORKING MEMORY (7±2 items)                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │   │
│  │  │ Current │ │Retrieved│ │  Active │ │ Pending │                    │   │
│  │  │  Task   │ │Memories │ │ Schema  │ │ Actions │                    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          │                    ▲                             │
│              ┌───────────┴────────────────────┴───────────┐                │
│              │    PATTERN COMPLETION RETRIEVER             │                │
│              │  (Sparse Cues → Full Memory Reconstruction) │                │
│              └───────────────────┬─────────────────────────┘                │
│                                  │                                          │
│  ┌───────────────────────────────┴──────────────────────────────────────┐  │
│  │                    LONG-TERM MEMORY STORES                            │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │    EPISODIC     │  │    SEMANTIC     │  │   PROCEDURAL    │       │  │
│  │  │   (DynamoDB)    │  │   (Neptune +    │  │   (DynamoDB +   │       │  │
│  │  │                 │  │   OpenSearch)   │  │    Neptune)     │       │  │
│  │  │ • Problem       │  │ • GUARDRAILS.md │  │ • Workflows     │       │  │
│  │  │   episodes      │  │ • Schemas       │  │ • Tool chains   │       │  │
│  │  │ • Context       │  │ • Patterns      │  │ • Action        │       │  │
│  │  │   snapshots     │  │ • Abstractions  │  │   sequences     │       │  │
│  │  │ • Outcomes      │  │                 │  │                 │       │  │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘       │  │
│  │           └────────────────────┼────────────────────┘                │  │
│  │                    ┌───────────┴───────────┐                         │  │
│  │                    │     CONSOLIDATION     │                         │  │
│  │                    │      PIPELINE         │                         │  │
│  │                    └───────────────────────┘                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Confidence-Based Strategy Selection

The metacognitive layer selects strategies based on confidence:

| Confidence | Strategy | Action | Logging |
|------------|----------|--------|---------|
| ≥ 0.85 | `PROCEDURAL_EXECUTION` | Execute known procedure | Minimal |
| 0.70-0.84 | `PROCEED_WITH_LOGGING` | Execute with checkpoints | Normal |
| 0.50-0.69 | `SCHEMA_GUIDED` | Follow schema, request review | Verbose |
| < 0.50 | `ACTIVE_LEARNING` / `HUMAN_GUIDANCE` | Ask questions, escalate | Verbose |

### Confidence Factor Weights

```python
DEFAULT_WEIGHTS = {
    "memory_coverage": 0.25,    # Do we have relevant experience?
    "memory_agreement": 0.25,   # Do memories agree on approach?
    "recency": 0.15,            # How recent are relevant memories?
    "outcome_history": 0.25,    # How have similar decisions fared?
    "schema_match": 0.10,       # Does task match a known schema?
}
```

### 85% Accuracy Target Strategy

| Confidence Band | Target Accuracy | Population % | Contribution |
|-----------------|-----------------|--------------|--------------|
| High (≥0.85) | 95% | ~40% | 38% |
| Medium (0.50-0.84) | 85% | ~40% | 34% |
| Low (<0.50) | 75%* | ~20% | 15% |
| **Weighted Total** | | | **87%** |

*Low confidence cases are escalated to humans, so "accuracy" includes human corrections.

### Memory Consolidation Process

```
1. EPISODE COLLECTION
   │ Every task execution creates an EpisodicMemory
   ▼
2. CLUSTERING (Daily/Weekly)
   │ Group episodes by domain + outcome
   │ Minimum 3 episodes per cluster
   ▼
3. PATTERN EXTRACTION
   │ Use LLM to identify common elements
   │ Extract decision patterns, preconditions
   ▼
4. VALIDATION
   │ Test pattern on held-out episodes
   │ Require ≥85% accuracy
   ▼
5. SEMANTIC CREATION/STRENGTHENING
   │ Create new guardrail/pattern OR
   │ Strengthen existing with new evidence
   ▼
6. EPISODE PRUNING
   │ TTL-based expiration (30 days default)
   │ Failures kept 2x longer (60 days)
```

### Implementation Files

| Component | File | Purpose |
|-----------|------|---------|
| Service | `src/services/cognitive_memory_service.py` | Main service interface |
| Schema | `agent-config/schemas/cognitive-memory-schema.md` | Data structure definitions |
| Guardrails | `GUARDRAILS.md` | Seed semantic memories |
| Task Schema | `agent-config/schemas/cicd-schema.md` | Domain-specific procedures |

### Usage Example

```python
from src.services.cognitive_memory_service import CognitiveMemoryService

# Initialize with storage backends
service = CognitiveMemoryService(
    episodic_store=dynamodb_episodic,
    semantic_store=neptune_semantic,
    procedural_store=dynamodb_procedural,
    embedding_service=bedrock_embeddings,
)

# Load cognitive context for a task
context = await service.load_cognitive_context(
    task_description="Deploy CloudFormation stack for ECR repository",
    domain="CICD",
)

# Use context for decision making
confidence = context["confidence"]
strategy = context["strategy"]
guardrails = context["guardrails"]

if confidence.score >= 0.85:
    # High confidence: execute procedure
    procedure = strategy.procedure
    await execute_procedure(procedure)
elif confidence.score >= 0.50:
    # Medium confidence: schema-guided with guardrails
    for guardrail in guardrails:
        logger.info(f"Applying guardrail: {guardrail['id']}")
else:
    # Low confidence: escalate
    await escalate_to_human(context["strategy"].questions)

# Record episode for future learning
await service.record_episode(
    task_description="Deploy CloudFormation stack for ECR repository",
    domain="CICD",
    decision="Used aws cloudformation deploy with --no-fail-on-empty-changeset",
    reasoning="Followed GR-CICD-001 pattern from buildspec-data.yml",
    outcome=OutcomeStatus.SUCCESS,
    outcome_details="Stack deployed successfully",
    confidence_at_decision=confidence.score,
)
```

### Integration with Existing Agent System

The `CognitiveMemoryService` integrates with the existing agent orchestrator:

```python
# In agent_orchestrator.py
class AgentOrchestrator:
    def __init__(self, ..., cognitive_memory: CognitiveMemoryService):
        self.cognitive_memory = cognitive_memory

    async def execute_task(self, task: Task) -> Result:
        # Load cognitive context
        context = await self.cognitive_memory.load_cognitive_context(
            task_description=task.description,
            domain=task.domain,
        )

        # Add to HybridContext
        hybrid_context = HybridContext(...)
        hybrid_context.cognitive_context = context

        # Select agent based on strategy
        if context["strategy"].strategy_type == StrategyType.PROCEDURAL_EXECUTION:
            return await self._execute_procedure(context["strategy"].procedure)
        else:
            return await self._execute_with_guardrails(
                task, context["guardrails"]
            )
```
