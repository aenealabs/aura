# Research Proposal: Recursive Context Scaling and Embedding Prediction for Project Aura

**Proposal ID:** PROP-2026-001
**Date:** 2026-01-04
**Authors:** Platform Architecture Team
**Status:** Draft - Pending Architectural Review
**Related ADR:** ADR-051

---

## Abstract

This proposal presents a comprehensive integration strategy for two breakthrough research paradigms from MIT CSAIL and Meta FAIR (December 2025) into Project Aura's autonomous agent architecture. By combining Recursive Language Models (RLMs) for 100x context scaling with VL-JEPA's selective decoding for 2.85x inference efficiency, we can dramatically enhance Aura's ability to reason across entire enterprise codebases while reducing computational costs.

---

## 1. Research Background

### 1.1 Recursive Language Models (MIT CSAIL, December 2025)

**Paper Title:** "Recursive Language Models"
**Key Authors:** MIT Computer Science and Artificial Intelligence Laboratory
**Publication:** arXiv, December 2025

#### Core Innovation

RLMs introduce a paradigm shift in how LLMs handle long contexts. Instead of attempting to process massive inputs in a single forward pass, RLMs treat long prompts as **external environment variables** accessible through a Python REPL interface.

#### Technical Approach

1. **REPL Environment:** The LLM operates within a sandboxed Python environment where large inputs (10M+ tokens) are stored as variables
2. **Programmatic Examination:** The LLM generates Python code to parse, filter, and extract relevant sections
3. **Recursive Sub-Calling:** Complex tasks are decomposed into recursive LLM calls on sub-problems
4. **Result Aggregation:** Sub-results are combined programmatically

#### Key Results from Paper

| Benchmark | Base LLM | RLM | Improvement |
|-----------|----------|-----|-------------|
| RULER (128K) | 67.4% | 89.2% | +32.3% |
| LongBench | 45.1% | 72.8% | +61.4% |
| InfiniteBench | 31.2% | 68.5% | +119.6% |
| Complexity-Scaled Cost | O(n) | O(k) | n/k reduction |

Where `n` = input size, `k` = task complexity

#### Theoretical Foundation

The paper proves that for tasks where the answer depends on a subset of the input, RLMs achieve:
- **Time complexity:** O(k log n) instead of O(n)
- **Cost complexity:** Proportional to task difficulty, not input size
- **Accuracy:** Maintains or exceeds base LLM on long-context benchmarks

### 1.2 VL-JEPA: Joint Embedding Predictive Architecture (Meta FAIR, December 2025)

**Paper Title:** "VL-JEPA: Joint Embedding Predictive Architecture for Vision-Language"
**Key Authors:** Meta Fundamental AI Research
**Publication:** arXiv, December 2025

#### Core Innovation

VL-JEPA fundamentally rethinks multimodal understanding by predicting **continuous embeddings** instead of discrete tokens. This enables:
- Non-generative tasks to skip the expensive decoder entirely
- Unified architecture for classification, retrieval, and QA
- 50% reduction in trainable parameters

#### Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        VL-JEPA Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input (Text/Vision)                                           │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                              │
│  │  X-Encoder   │ ─────────────────────────────────┐           │
│  │  (Frozen)    │                                  │           │
│  └──────┬───────┘                                  │           │
│         │                                          │           │
│         ▼                                          ▼           │
│  ┌──────────────┐                         ┌──────────────┐     │
│  │  Predictor   │                         │  Y-Encoder   │     │
│  │  (Trainable) │                         │  (Target)    │     │
│  └──────┬───────┘                         └──────┬───────┘     │
│         │                                        │             │
│         ▼                                        ▼             │
│  ┌──────────────────────────────────────────────────────┐     │
│  │              InfoNCE Contrastive Loss                 │     │
│  │                                                       │     │
│  │  L = -log(exp(sim(y_pred, y_true)/τ) /               │     │
│  │            Σ exp(sim(y_pred, y_neg)/τ))              │     │
│  └───────────────────────┬──────────────────────────────┘     │
│                          │                                     │
│         ┌────────────────┴────────────────┐                   │
│         ▼                                 ▼                   │
│  ┌──────────────┐                 ┌──────────────┐            │
│  │ Fast Path    │                 │ Slow Path    │            │
│  │ (No Decoder) │                 │ (Y-Decoder)  │            │
│  │              │                 │              │            │
│  │ Classification│                │ Generation   │            │
│  │ Retrieval    │                 │ Explanation  │            │
│  │ Similarity   │                 │ Code Gen     │            │
│  └──────────────┘                 └──────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Results from Paper

| Task Type | Standard Approach | VL-JEPA | Speedup |
|-----------|-------------------|---------|---------|
| Classification | Full decode | Embedding only | 2.85x |
| Retrieval | Full decode | Embedding only | 3.1x |
| Visual QA | Full decode | Selective decode | 1.8x |
| Generation | Full decode | Full decode | 1.0x |

**Parameter Efficiency:**
- Y-Encoder: 50% of total parameters (understanding)
- Y-Decoder: 15% of total parameters (generation)
- Predictor: 35% of total parameters (mapping)

For non-generative tasks, only X-Encoder + Predictor needed = 65% parameter reduction.

---

## 2. Relevance to Project Aura

### 2.1 Current Limitations Addressed

| Limitation | RLM Solution | VL-JEPA Solution |
|------------|--------------|------------------|
| 200K token context limit | Recursive decomposition to 10M+ | N/A |
| Uniform inference cost | Cost scales with complexity | Selective decoding |
| No programmatic analysis | REPL-based code examination | N/A |
| Slow classification/routing | N/A | 2.85x faster embedding path |
| Separate models per task | N/A | Unified embedding architecture |

### 2.2 Aura Component Mapping

#### RLM Applications

| Aura Component | RLM Enhancement |
|----------------|-----------------|
| **Codebase Ingestion** | Recursively analyze 10M+ token repos |
| **Vulnerability Scanning** | Decompose analysis across files/modules |
| **Dependency Analysis** | Cross-repository recursive reasoning |
| **Patch Generation** | Context-aware patches with full codebase understanding |
| **SSR Bug Injection** | Analyze entire repos for injection candidates |

#### VL-JEPA Applications

| Aura Component | VL-JEPA Enhancement |
|----------------|---------------------|
| **Agent Routing** | Fast embedding-based task routing |
| **Vulnerability Classification** | 2.85x faster CVE categorization |
| **Code Similarity** | Efficient clone/duplicate detection |
| **Priority Ranking** | Embedding-based issue triage |
| **Memory Retrieval** | Faster Titan Memory pattern matching |

### 2.3 Integration with Existing ADRs

#### ADR-024: Titan Neural Memory

**Synergy:** VL-JEPA embeddings can be stored directly in Titan Memory's DeepMLP architecture. The embedding prediction aligns naturally with the surprise-gated memorization:
- High-confidence embeddings (low surprise) → Skip memorization
- Novel embeddings (high surprise) → Store in neural memory

**Integration Points:**
- JEPA predictor outputs feed into Titan's surprise calculation
- Titan patterns enhance JEPA's Y-Encoder training
- Unified embedding space across both systems

#### ADR-034: Context Engineering

**Synergy:** RLM's recursive decomposition extends the context engineering framework:
- Context scoring can guide decomposition priorities
- HopRAG can be used within recursive sub-calls
- Summarization uses JEPA's efficient embedding path

**Integration Points:**
- ContextScoringService ranks chunks for RLM processing
- ContextStackManager tracks recursive call depth
- HopRAGService provides multi-hop context for sub-problems

#### ADR-050: Self-Play SWE-RL

**Synergy:** Both paradigms enhance SSR training:
- RLM enables bug injection across entire codebases
- VL-JEPA speeds up patch classification (valid/invalid)
- Training cost reduced by 2.85x for non-generative validation steps

**Integration Points:**
- BugInjectionAgent uses RLM for codebase-wide analysis
- ConsistencyValidationPipeline uses JEPA for fast classification
- RewardComputation uses embedding similarity for difficulty scoring

---

## 3. Proposed Architecture

### 3.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UNIFIED CONTEXT INTELLIGENCE LAYER                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RECURSIVE CONTEXT ENGINE (RLM)                    │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Decomposition │  │ REPL Sandbox │  │ Sub-Agent    │               │   │
│  │  │ Planner      │  │ (EKS Fargate)│  │ Orchestrator │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  │  Context Variables: CONTEXT (10M+ tokens), TASK, GRAPH_STRUCTURE    │   │
│  │  Helper Functions: context_search, context_chunk, recursive_call     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   SELECTIVE DECODING ENGINE (JEPA)                   │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Task Router  │  │ Embedding    │  │ Lightweight  │               │   │
│  │  │ (Classifier) │  │ Predictor    │  │ Decoder      │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  │  Fast Path: Classification, Retrieval, Similarity, Routing (2.85x)  │   │
│  │  Slow Path: Generation, Explanation, Code Creation (1.0x)           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
           │ Titan Neural │  │   GraphRAG   │  │    Agent     │
           │ Memory       │  │   (Neptune)  │  │ Orchestrator │
           │ (ADR-024)    │  │   (Issue 151)│  │              │
           └──────────────┘  └──────────────┘  └──────────────┘
```

### 3.2 Data Flow

#### Large Codebase Analysis Flow

```
1. User Request: "Find all SQL injection vulnerabilities in repository X"
                                    │
                                    ▼
2. Context Router determines: Repository X = 5M tokens > 200K limit
                                    │
                                    ▼
3. RLM Decomposition Engine activates:
   - Generates Python decomposition code
   - Creates sub-tasks by module/directory
   - Spawns recursive sub-agents
                                    │
                                    ▼
4. For each sub-task (parallel):
   a. JEPA classifies: "Is this code security-relevant?" (fast path)
   b. If yes → Full analysis with LLM
   c. If no → Skip (saves compute)
                                    │
                                    ▼
5. Results aggregated via RLM helper functions
                                    │
                                    ▼
6. Final output: Structured vulnerability report
   - Stored in Titan Memory for pattern learning
   - Indexed in GraphRAG for future retrieval
```

#### Agent Routing Flow (Fast Path)

```
1. Task: "Review this PR for security issues"
                    │
                    ▼
2. JEPA Task Router (embedding classification):
   - Encode task description
   - Compare to agent capability embeddings
   - Select best agent in ~10ms
                    │
                    ▼
3. Route to: SecurityCodeReviewerAgent
   (No full LLM decode needed for routing)
```

---

## 4. Technical Specifications

### 4.1 RLM Configuration

```python
@dataclass
class RLMConfig:
    """Configuration for Recursive Language Model engine."""

    # Decomposition limits
    max_recursion_depth: int = 5
    max_sub_agents: int = 50
    chunk_size_tokens: int = 100_000

    # REPL sandbox settings
    sandbox_timeout_seconds: float = 30.0
    max_memory_mb: int = 2048
    allowed_imports: list[str] = field(default_factory=lambda: [
        "re", "json", "collections", "itertools", "functools"
    ])

    # Cost controls
    max_total_tokens: int = 10_000_000
    cost_budget_usd: float = 10.0

    # Integration
    use_graphrag_structure: bool = True
    cache_sub_results: bool = True
    cache_ttl_seconds: int = 3600
```

### 4.2 JEPA Configuration

```python
@dataclass
class JEPAConfig:
    """Configuration for JEPA selective decoding."""

    # Architecture
    embed_dim: int = 768
    predictor_layers: int = 6
    decoder_layers: int = 2
    num_attention_heads: int = 12

    # Training
    infonce_temperature: float = 0.07
    negative_samples: int = 256

    # Task routing thresholds
    classification_confidence: float = 0.9
    retrieval_similarity: float = 0.8
    generation_fallback: bool = True

    # Deployment
    endpoint_type: str = "sagemaker"
    instance_type: str = "ml.inf2.xlarge"  # Inferentia2
    autoscaling_min: int = 1
    autoscaling_max: int = 10
```

### 4.3 API Design

```python
class UnifiedContextAPI:
    """Public API for RLM + JEPA unified context intelligence."""

    async def analyze(
        self,
        repository_id: str,
        task: str,
        options: AnalysisOptions = None
    ) -> AnalysisResult:
        """
        Analyze repository with automatic context scaling.

        Args:
            repository_id: Repository to analyze
            task: Natural language task description
            options: Optional configuration overrides

        Returns:
            AnalysisResult with findings and metadata
        """
        pass

    async def classify(
        self,
        content: str,
        categories: list[str]
    ) -> ClassificationResult:
        """
        Classify content using JEPA fast path (2.85x faster).

        Args:
            content: Text to classify
            categories: Target categories

        Returns:
            Classification with confidence scores
        """
        pass

    async def route_task(
        self,
        task_description: str,
        available_agents: list[AgentConfig]
    ) -> RoutingDecision:
        """
        Route task to best agent using embedding similarity.

        Args:
            task_description: Natural language task
            available_agents: Agents to choose from

        Returns:
            Routing decision with confidence
        """
        pass

    async def find_similar(
        self,
        query: str,
        corpus: list[str],
        top_k: int = 10
    ) -> list[SimilarityMatch]:
        """
        Find similar items using JEPA embeddings.

        Args:
            query: Query text
            corpus: Items to search
            top_k: Number of results

        Returns:
            Ranked similarity matches
        """
        pass
```

---

## 5. Implementation Roadmap

### Phase 1: Research Validation (Weeks 1-2)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Reproduce RLM paper results on small benchmark | Validation report |
| 1.2 | Reproduce JEPA efficiency claims | Benchmark measurements |
| 1.3 | Identify Aura-specific adaptations needed | Gap analysis document |
| 1.4 | Security review of REPL sandbox approach | Security assessment |

### Phase 2: Core Implementation (Weeks 3-8)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Implement RLM RecursiveContextEngine | `src/services/rlm/` |
| 2.2 | Implement JEPA EmbeddingPredictor | `src/services/jepa/` |
| 2.3 | Create REPL sandbox on EKS Fargate | CloudFormation template |
| 2.4 | Deploy JEPA to SageMaker/Inferentia2 | Deployment scripts |
| 2.5 | Unit and integration tests | 90%+ coverage |

### Phase 3: Integration (Weeks 9-12)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Integrate with Titan Memory (ADR-024) | Memory pattern storage |
| 3.2 | Integrate with GraphRAG (Issue #151) | Structure-aware decomposition |
| 3.3 | Integrate with SSR (ADR-050) | Enhanced training pipeline |
| 3.4 | Create UnifiedContextService | Public API |

### Phase 4: Production (Weeks 13-16)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | CloudWatch metrics and dashboards | Observability |
| 4.2 | Cost tracking and optimization | Budget controls |
| 4.3 | Operational runbook | `docs/operations/` |
| 4.4 | Performance benchmarks on real repos | Benchmark report |

---

## 6. Success Criteria

### Quantitative Metrics

| Metric | Current | Target | Validation Method |
|--------|---------|--------|-------------------|
| Max context size | 200K tokens | 10M+ tokens | RLM decomposition test |
| Classification latency | 500ms | <50ms | JEPA benchmark |
| Inference efficiency | 1.0x | 2.85x | Operation profiling |
| Agent routing latency | 200ms | <20ms | Embedding similarity test |
| Codebase analysis success | N/A | >95% | Real repository tests |

### Qualitative Criteria

- [ ] Security review passes with no HIGH findings
- [ ] Integration tests pass for all existing ADR integrations
- [ ] Documentation complete for operators and developers
- [ ] Cost projections validated within 20% of estimates

---

## 7. Risks and Mitigations

### High Priority Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| REPL sandbox escape | Low | Critical | Container isolation, syscall filtering, network policies |
| Recursive runaway | Medium | High | Depth limits, timeouts, circuit breakers |
| Model quality degradation | Medium | High | Extensive validation, A/B testing, rollback plan |

### Medium Priority Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cost overruns | Medium | Medium | Budget alerts, depth limits, caching |
| Integration complexity | Medium | Medium | Phased rollout, feature flags |
| Training data requirements | Low | Medium | Use existing embeddings as starting point |

---

## 8. Resource Requirements

### Compute

| Resource | Quantity | Purpose | Monthly Cost |
|----------|----------|---------|--------------|
| SageMaker ml.inf2.xlarge | 1-10 | JEPA inference | $450-$4,500 |
| EKS Fargate (RLM sandbox) | On-demand | REPL execution | $200-$2,000 |
| OpenSearch Serverless | 2-10 OCU | Embedding index | $175-$875 |

### Personnel

| Role | Effort | Duration |
|------|--------|----------|
| ML Engineer | 1.0 FTE | 16 weeks |
| Backend Engineer | 0.5 FTE | 16 weeks |
| Security Engineer | 0.25 FTE | 4 weeks |
| DevOps Engineer | 0.25 FTE | 4 weeks |

---

## 9. Conclusion

The combination of RLM recursive decomposition and VL-JEPA selective decoding offers a compelling enhancement to Project Aura's capabilities. By enabling 100x context scaling with 2.85x efficiency gains, we can unlock analysis of entire enterprise codebases while reducing inference costs.

**Recommendation:** Proceed with Phase 1 research validation, pending architectural review by Architecture Review.

---

## References

1. "Recursive Language Models" - MIT CSAIL (December 2025)
2. "VL-JEPA: Joint Embedding Predictive Architecture for Vision-Language" - Meta FAIR (December 2025)
3. ADR-024: Titan Neural Memory Architecture
4. ADR-034: Context Engineering Framework
5. ADR-050: Self-Play SWE-RL Integration
6. Issue #151: Hybrid GraphRAG Implementation
