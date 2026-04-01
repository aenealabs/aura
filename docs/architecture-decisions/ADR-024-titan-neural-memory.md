# ADR-024: Titan Neural Memory Architecture Integration

**Status:** Deployed
**Date:** December 6, 2025
**Accepted:** December 6, 2025
**Deployed:** December 16, 2025
**Decision Makers:** Platform Architecture Team
**Technical Area:** Agent Memory Architecture

---

## Summary

We will implement a **Hybrid Memory Architecture** using Inferentia2 for retrieval and GPU for test-time training (TTT). The architecture is designed for large enterprise scale but deployed with minimal resources during development, using configuration-driven scaling.

**Key Documents:**
- Performance Analysis: `../research/experiments/hybrid-memory-architecture/PERFORMANCE_ANALYSIS.md`
- Resource Scaling: `../research/experiments/hybrid-memory-architecture/RESOURCE_SCALING_GUIDE.md`
- Enterprise Tiers: `../research/experiments/hybrid-memory-architecture/ENTERPRISE_TIER_CONFIG.md`

---

## Context

Project Aura's cognitive memory architecture currently uses:
- **Episodic Memory:** Full context snapshots with TTL-based expiration
- **Semantic Memory:** Guardrails, patterns, schemas stored as structured data
- **Procedural Memory:** Action sequences with success rate tracking

Recent research from Google (Titans and MIRAS, NeurIPS 2024/2025) demonstrates that:
1. Deep MLP memory modules significantly outperform vector/matrix storage
2. Gradient-based "surprise" metrics enable selective memorization
3. Test-time training allows models to learn during inference
4. Huber loss provides outlier-robust memory updates

This ADR proposes integrating these advances into Project Aura's agent memory system.

---

## Decision

**We will implement a Titan-inspired neural memory module as an optional enhancement to the existing CognitiveMemoryService.**

### Key Components

1. **DeepMLPMemory Module**
   - Replace vector-based episodic storage with 3-layer MLP
   - Residual connections for stable training
   - Persistent memory parameters for task-specific knowledge

2. **Surprise-Driven Consolidation**
   - Compute gradient magnitude as surprise score
   - Apply momentum for temporal smoothing
   - Only memorize experiences above surprise threshold

3. **MIRAS Configuration**
   - Configurable attentional bias (L2, L1, Huber, Cosine)
   - Configurable retention gate (weight decay, exponential, adaptive)
   - Per-organization memory policies

4. **Test-Time Training (Optional)**
   - Gradient descent on memory parameters during inference
   - Bounded update rate to prevent catastrophic forgetting
   - Audit logging of all memory updates

5. **Hybrid Compute Architecture**
   - **Retrieval Path:** Inferentia2 (inf2) for optimized inference
   - **TTT Path:** GPU (g5) for gradient computation
   - **Development:** CPU fallback (t3) for cost-effective iteration
   - **Scaling:** Configuration-driven, same code across all environments

### Compute Strategy

| Environment | Retrieval | TTT | Monthly Cost |
|-------------|-----------|-----|--------------|
| Development | t3.medium (CPU) | t3.large (CPU) | ~$70 |
| Staging | inf2.xlarge | g5.xlarge (0-1) | ~$600 |
| Prod (Small) | inf2.xlarge × 2 | g5.xlarge (0-1) | ~$1,400 |
| Prod (Medium) | inf2.8xlarge × 2 | g5.xlarge (0-2) | ~$3,000 |
| Prod (Large) | inf2.8xlarge × 4 | g5.2xlarge (0-3) | ~$5,500 |

### Why Hybrid Over GPU-Only

Based on theoretical performance analysis (`PERFORMANCE_ANALYSIS.md`):

| Metric | Hybrid | GPU-Only | Winner |
|--------|--------|----------|--------|
| Retrieval throughput | 100K req/s | 60K req/s | Hybrid +67% |
| Retrieval p99 latency | 3.2ms | 8.5ms | Hybrid -62% |
| TTT p99 latency | 8.5ms | 85ms | Hybrid -90% |
| Cost at 500M req/mo | $5,100 | $7,920 | Hybrid -36% |
| Failure isolation | Excellent | Poor | Hybrid |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TitanMemoryService                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │ Persistent Memory │    │   MIRAS Config   │                  │
│  │ (Fixed Weights)   │    │ - Attentional Bias│                  │
│  └────────┬─────────┘    │ - Retention Gate  │                  │
│           │              │ - Memory Algorithm│                  │
│           ▼              └─────────┬─────────┘                  │
│  ┌──────────────────────────────────┐                          │
│  │        DeepMLPMemory             │                          │
│  │  ┌─────────────────────────────┐ │                          │
│  │  │ Layer 1: Linear → GELU → LN │ │                          │
│  │  └─────────────┬───────────────┘ │                          │
│  │  ┌─────────────▼───────────────┐ │                          │
│  │  │ Layer 2: Linear → GELU → LN │ │                          │
│  │  └─────────────┬───────────────┘ │                          │
│  │  ┌─────────────▼───────────────┐ │                          │
│  │  │ Layer 3: Linear → GELU → LN │ │                          │
│  │  └─────────────────────────────┘ │                          │
│  └──────────────────────────────────┘                          │
│                    │                                            │
│         ┌─────────┴─────────┐                                  │
│         ▼                   ▼                                  │
│  ┌──────────────┐    ┌──────────────┐                          │
│  │   Retrieve   │    │    Update    │                          │
│  │   (Query)    │    │  (TTT/Learn) │                          │
│  └──────────────┘    └──────────────┘                          │
│                              │                                  │
│                    ┌─────────┴─────────┐                       │
│                    ▼                   ▼                        │
│            ┌──────────────┐    ┌──────────────┐                │
│            │   Surprise   │    │   Retention  │                │
│            │   Compute    │    │ Regularizer  │                │
│            └──────────────┘    └──────────────┘                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Existing Architecture

### CognitiveMemoryService Enhancement

```python
class CognitiveMemoryService:
    def __init__(self, config: MemoryConfig):
        # Existing memory systems
        self.episodic_memory = EpisodicMemory()
        self.semantic_memory = SemanticMemory()
        self.procedural_memory = ProceduralMemory()

        # NEW: Titan neural memory (optional)
        if config.enable_titan_memory:
            self.titan_memory = TitanMemoryService(
                dim=config.memory_dim,
                depth=config.memory_depth,
                miras_config=config.miras_config
            )

    async def store_experience(self, experience: Experience):
        # Compute surprise score
        surprise = self.titan_memory.compute_surprise(experience)

        # Selective memorization
        if surprise > self.config.memorization_threshold:
            # Store in neural memory (test-time training)
            await self.titan_memory.update(experience)

            # Also store in episodic for audit trail
            await self.episodic_memory.store(experience, surprise=surprise)

    async def retrieve(self, query: str) -> HybridContext:
        # Retrieve from neural memory
        neural_context = await self.titan_memory.retrieve(query)

        # Combine with existing retrieval
        episodic_context = await self.episodic_memory.retrieve(query)
        semantic_context = await self.semantic_memory.retrieve(query)

        return self.merge_contexts(neural_context, episodic_context, semantic_context)
```

### MemoryAgent Integration

```python
class MemoryAgent:
    def __init__(self, cognitive_service: CognitiveMemoryService):
        self.memory = cognitive_service
        self.mode = AgentMode.AUTO  # SINGLE, DUAL, AUTO

    async def make_decision(self, task: Task, context: HybridContext) -> Decision:
        # Retrieve from titan memory
        memory_context = await self.memory.titan_memory.retrieve(
            self.encode_task(task)
        )

        # Compute surprise as confidence inverse
        surprise = self.memory.titan_memory.last_surprise
        confidence = 1.0 - min(surprise, 1.0)

        # Route based on surprise (maps to confidence thresholds)
        if confidence >= 0.85:
            action = RecommendedAction.PROCEED_AUTONOMOUS
        elif confidence >= 0.70:
            action = RecommendedAction.PROCEED_WITH_LOGGING
        elif confidence >= 0.50:
            action = RecommendedAction.REQUEST_REVIEW
        else:
            action = RecommendedAction.ESCALATE_TO_HUMAN

        # If dual mode and uncertain, engage critic
        if self.mode == AgentMode.DUAL and confidence < 0.70:
            critic_eval = await self.critic_agent.evaluate(decision)
            decision = self.reconcile_with_critic(decision, critic_eval)

        return Decision(action=action, confidence=confidence, ...)
```

---

## Configuration

### Memory Configuration

```python
@dataclass
class TitanMemoryConfig:
    # Architecture
    memory_dim: int = 512
    memory_depth: int = 3
    hidden_multiplier: int = 4

    # MIRAS settings
    attentional_bias: str = "huber"  # l2, l1, huber, cosine
    retention_gate: str = "adaptive"  # weight_decay, exponential, adaptive
    retention_strength: float = 0.01

    # Test-time training
    enable_ttt: bool = True
    learning_rate: float = 0.001
    max_updates_per_inference: int = 3

    # Surprise thresholds
    memorization_threshold: float = 0.7
    momentum: float = 0.9

    # Safety
    max_memory_size_mb: int = 100
    audit_all_updates: bool = True
```

### Organization Presets

```python
MEMORY_PRESETS = {
    "defense_contractor": TitanMemoryConfig(
        enable_ttt=False,  # No runtime learning (security)
        audit_all_updates=True,
        memorization_threshold=0.9,  # Only highly surprising
    ),
    "enterprise_standard": TitanMemoryConfig(
        enable_ttt=True,
        retention_gate="adaptive",
        memorization_threshold=0.7,
    ),
    "research_lab": TitanMemoryConfig(
        enable_ttt=True,
        memory_depth=5,  # Deeper memory
        memorization_threshold=0.5,  # Learn more
    ),
}
```

---

## Consequences

### Positive

1. **Better long-term recall** - Deep MLP memory captures complex patterns
2. **Efficient storage** - Only surprising experiences memorized
3. **Outlier robustness** - Huber loss prevents anomaly sensitivity
4. **Unified framework** - MIRAS provides theoretical foundation
5. **Competitive advantage** - 2M+ token effective context

### Negative

1. **Compute overhead** - MLP forward/backward passes per query
2. **Complexity** - More hyperparameters to tune
3. **Audit challenges** - Neural memory less interpretable than structured storage
4. **Training stability** - Test-time training requires careful bounds

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Memory corruption from bad updates | Bounded learning rate, rollback capability |
| Unbounded memory growth | Max size limits, periodic consolidation |
| Catastrophic forgetting | Retention regularization (MIRAS) |
| Security: adversarial memory injection | Audit logging, anomaly detection on updates |

---

## Implementation Plan

### Phase 1: Core Module ✅ Complete
- [x] Implement `DeepMLPMemory` class (`src/services/models/deep_mlp_memory.py`)
- [x] Implement `MIRASConfig` with loss functions (`src/services/models/miras_config.py`)
- [x] CPU memory backend (`src/services/memory_backends/cpu_backend.py`)
- [x] Unit tests for memory retrieval/update (29 tests)

### Phase 2: Surprise Computation ✅ Complete
- [x] Implement gradient-based surprise metric (`SurpriseCalculator` in `deep_mlp_memory.py`)
- [x] Add momentum for temporal smoothing
- [x] Integration tests with mock experiences
- [x] PyTorch 2.5.1 compatibility verified

### Phase 3: Benchmarking ✅ Complete
- [x] GPU/MPS backend (`src/services/memory_backends/gpu_backend.py`)
- [x] Comprehensive benchmarking module (`src/services/memory_backends/benchmark.py`)
- [x] CPU vs MPS performance comparison
- [x] Results documented (`../experiments/hybrid-memory-architecture/BENCHMARK_RESULTS.md`)

### Phase 4: Service Integration ✅ Complete
- [x] `TitanCognitiveService` wraps `CognitiveMemoryService` (`src/services/titan_cognitive_integration.py`)
- [x] `MemoryAgent` with surprise-confidence mapping (see Implementation Notes below)
- [x] `NeuralMemoryMetricsPublisher` for CloudWatch (`Aura/NeuralMemory` namespace)
- [x] Integration tests (23 tests)

### Phase 5: Production Hardening ✅ Complete
- [x] Memory size limits and consolidation (`src/services/memory_consolidation.py`)
  - `MemoryConsolidationManager` with configurable strategies
  - `MemorySizeLimiter` for enforcing size limits
  - Strategies: FULL_RESET, WEIGHT_PRUNING, SLOT_REDUCTION, LAYER_RESET, WARN_ONLY
  - `MemoryPressureLevel` enum with NORMAL/WARNING/HIGH/CRITICAL levels
- [x] Audit logging for all updates (`src/services/neural_memory_audit.py`)
  - `NeuralMemoryAuditLogger` with structured audit records
  - `AuditRecord` with checksum for integrity verification
  - Support for InMemoryAuditStorage and FileAuditStorage backends
  - Compliance-ready format with correlation IDs
- [x] Integration with TitanMemoryService
  - Auto-consolidation on high memory pressure
  - Audit logging for retrieve, update, checkpoint, init, shutdown
  - Callbacks for pressure changes and limit exceeded events
- [x] Production hardening tests (40 tests in `tests/services/test_production_hardening.py`)
- [x] Performance benchmarking (completed in Phase 3)

---

## Implementation Notes

### Architecture Clarification: Strategy vs ConfidenceEstimate

The cognitive memory architecture separates **what approach to take** from **how confident we are**:

```python
# Strategy: Defines the approach (no confidence/reasoning fields)
@dataclass
class Strategy:
    strategy_type: StrategyType      # PROCEDURAL_EXECUTION, SCHEMA_GUIDED, etc.
    procedure: Optional[ProceduralMemory]  # Supporting procedure if applicable
    schema: Optional[dict]           # Supporting schema if applicable
    guardrails: list[str]            # Safety constraints
    logging_level: str               # NORMAL, ENHANCED, DEBUG
    checkpoint_frequency: str        # LOW, MEDIUM, HIGH

# ConfidenceEstimate: Tracks confidence separately
@dataclass
class ConfidenceEstimate:
    score: float                     # 0.0 to 1.0
    factors: dict[str, float]        # Contributing factors
    weights: dict[str, float]        # Factor weights
    uncertainties: list[str]         # Sources of uncertainty
    recommended_action: RecommendedAction
    confidence_interval: tuple[float, float]
```

The `load_cognitive_context()` method returns both as separate fields:

```python
{
    "confidence": ConfidenceEstimate(...),  # Confidence lives here
    "strategy": Strategy(...),               # Just the approach
    "retrieved_memories": [...],             # Supporting memories
    "neural_memory": {                       # Neural memory signals
        "enabled": True,
        "surprise": 0.3,
        "neural_confidence": 0.7,
    },
}
```

### MemoryAgent Routing Implementation

The `MemoryAgent` pulls confidence from the context and routes accordingly:

```python
# From src/services/titan_cognitive_integration.py
class MemoryAgent:
    THRESHOLD_AUTONOMOUS = 0.85
    THRESHOLD_LOGGING = 0.70
    THRESHOLD_REVIEW = 0.50

    async def make_decision(self, task_description: str, domain: str):
        context = await self.cognitive_service.load_cognitive_context(...)

        # Get neural confidence (already = 1 - surprise)
        neural_info = context.get("neural_memory", {})
        if neural_info.get("enabled"):
            confidence = neural_info["neural_confidence"]
        else:
            confidence = context["confidence"].score

        # Route by threshold
        if confidence >= 0.85:
            return PROCEED_AUTONOMOUS
        elif confidence >= 0.70:
            return PROCEED_WITH_LOGGING
        elif confidence >= 0.50:
            return REQUEST_REVIEW
        else:
            return ESCALATE_TO_HUMAN
```

### CloudWatch Metrics (Aura/NeuralMemory Namespace)

| Metric | Unit | Description |
|--------|------|-------------|
| SurpriseScore | None | Neural memory surprise (0-1) |
| RetrievalLatency | Milliseconds | Time to retrieve from memory |
| UpdateLatency | Milliseconds | Time to update memory (TTT) |
| TTTSteps | Count | Test-time training steps performed |
| MemorizationDecisions | Count | 1 if memorized, 0 if skipped |
| ConfidenceScore | None | Agent confidence (0-1) |
| DecisionLatency | Milliseconds | Time to make routing decision |
| EscalationCount | Count | Escalations to human |

---

## Alternatives Considered

### Alternative 1: Vector Memory (Current State)
- **Pros:** Simple, interpretable, fast
- **Cons:** Limited expressiveness, poor long-sequence recall
- **Decision:** Insufficient for 2M+ token contexts

### Alternative 2: External Vector Database (Pinecone/Weaviate)
- **Pros:** Scalable, managed service
- **Cons:** Latency, no test-time learning, additional cost
- **Decision:** Complementary but doesn't replace neural memory

### Alternative 3: Full Transformer Memory
- **Pros:** Proven architecture
- **Cons:** Quadratic cost, not practical for 2M+ tokens
- **Decision:** Titans explicitly designed to overcome this limitation

---

## References

1. Titans: Learning to Memorize at Test Time (arXiv:2501.00663)
2. MIRAS: Memory-Integrated Recurrent Architectures (arXiv:2504.13173)
3. Project Aura ADR-021: Guardrails Cognitive Architecture
4. Research Analysis: `../research/papers/neural-memory-2025/TITANS_MIRAS_ANALYSIS.md`

---

*ADR-024 v1.1 - Deployed December 16, 2025*
