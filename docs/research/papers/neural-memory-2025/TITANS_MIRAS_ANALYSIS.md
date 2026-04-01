# Neural Memory and Test-Time Training: Titans & MIRAS Analysis

**Research Category:** Memory Architecture for AI Agents
**Date:** December 6, 2025
**Researcher:** AI Research Scientist, Project Aura
**Relevance:** HIGH - Direct applicability to cognitive memory architecture

---

## Executive Summary

Google Research presented two groundbreaking papers at NeurIPS 2024/2025 that introduce architectures capable of **learning and updating parameters during inference**. This represents a paradigm shift from static context windows to dynamic "neural long-term memory" systems.

**Key Innovation:** Models that can selectively memorize information at test-time based on a "surprise metric," enabling 2M+ token context windows while outperforming GPT-4 on recall tasks with fewer parameters.

**Strategic Relevance to Project Aura:** These techniques directly enhance our existing dual-agent cognitive memory architecture (MemoryAgent + CriticAgent) by providing:
1. More efficient long-term memory storage than episodic snapshots
2. Surprise-driven memory consolidation aligned with our confidence-based routing
3. A theoretical framework (MIRAS) for customizing memory objectives

---

## Paper 1: Titans - Learning to Memorize at Test Time

### Citation
```
Behrouz, A., Zhong, P., & Mirrokni, V. (2025).
Titans: Learning to Memorize at Test Time.
arXiv:2501.00663
```

### Core Problem Addressed

Traditional attention mechanisms face a fundamental tension:
- **Strength:** Can attend to entire context, capturing direct token dependencies
- **Weakness:** Quadratic cost O(n²) limits practical context length

Linear RNNs (Mamba, RWKV) solve efficiency but compress information into fixed-size states, losing representational richness.

### Architecture Innovation

#### Three-Layer Memory System (Mirrors Human Cognition)

| Layer | Name | Function | Analogy |
|-------|------|----------|---------|
| 1 | **Persistent Memory** | Fixed learnable weights | Long-term procedural knowledge |
| 2 | **Core** | Standard attention mechanism | Working memory / in-context learning |
| 3 | **Contextual Memory** | Deep MLP neural memory | Episodic long-term memory |

#### The Surprise Metric (Gradient-Based Memory Gating)

The key innovation is **selective memory updates** driven by gradient magnitude:

```
surprise(x_t) = ||∇_θ L(f_θ(x_t), x_t)||
```

**Low Surprise (Low Gradient):**
- Input aligns with model expectations
- Example: Model expects "animal", receives "cat"
- Action: Skip permanent storage, minimal memory update

**High Surprise (High Gradient):**
- Input dramatically breaks patterns
- Example: Financial document → banana peel image
- Action: Trigger long-term memory consolidation

This mechanism is **directly analogous** to Project Aura's confidence-based routing:
- High confidence (low surprise) → autonomous action
- Low confidence (high surprise) → escalate/memorize

#### Deep MLP Memory Module

Unlike vector/matrix compression in linear RNNs, Titans uses a **multi-layer perceptron as the memory module**:

```python
# Conceptual architecture
class TitanMemory(nn.Module):
    def __init__(self, dim, depth=3):
        self.layers = nn.ModuleList([
            nn.Linear(dim, dim) for _ in range(depth)
        ])
        self.activations = nn.GELU()

    def forward(self, x, update_signal):
        # Memory retrieval
        for layer in self.layers:
            x = self.activations(layer(x))
        return x

    def update(self, x, surprise_score):
        # Test-time training update
        if surprise_score > threshold:
            # Gradient descent on memory parameters
            loss = self.compute_memory_loss(x)
            loss.backward()
            self.optimizer.step()
```

**Why MLPs outperform vectors/matrices:**
- Significantly higher expressiveness
- Can learn non-linear transformations
- Better compression of complex patterns
- Depth improves perplexity (ablation confirmed)

#### Supporting Mechanisms

**Momentum (Temporal Smoothing):**
```
effective_surprise = α * current_surprise + (1-α) * past_surprise
```
Ensures related information captures even when individual tokens lack surprise.

**Weight Decay (Adaptive Forgetting):**
- Manages finite memory during extremely long sequences
- Mathematically equivalent to retention regularization
- Allows discarding outdated information

### Training: Chunked Parallelization

The training paradigm balances efficiency and expressiveness:

```
Sequence: [chunk_1] [chunk_2] [chunk_3] ... [chunk_n]
           ↓          ↓          ↓           ↓
         Linear    Linear     Linear      Linear    (within-chunk)
           ↓          ↓          ↓           ↓
         ----→ Non-linear updates across chunks ----→
```

- **Within chunks:** Linear operations (parallelizable)
- **Across chunks:** Non-linear memory updates (sequential)
- **Result:** Fast training + expressive memory

### Experimental Results

| Benchmark | Titans Performance |
|-----------|-------------------|
| **Needle in Haystack (2M+ tokens)** | Outperforms GPT-4 with fewer parameters |
| **Language Modeling (C4, WikiText)** | Higher accuracy, lower perplexity |
| **Commonsense Reasoning (HellaSwag, PIQA)** | Beats Mamba-2, Gated DeltaNet |
| **BABILong (extreme reasoning)** | Outperforms all baselines including GPT-4 |
| **Genomics & Time Series** | Validated cross-domain applicability |

**Key Finding:** Deep memory modules exhibit trade-off where increased depth improves perplexity but slightly reduces training throughput (worth the cost for quality).

---

## Paper 2: MIRAS - Memory as an Optimization Problem

### Citation
```
Behrouz, A., Razaviyayn, M., Zhong, P., & Mirrokni, V. (2025).
MIRAS: A Unified Framework for Memory-Integrated Recurrent Architectures.
arXiv:2504.13173
```

### Core Insight

MIRAS reconceptualizes neural architectures as **associative memory modules** guided by "attentional bias"—an internal objective inspired by human cognitive tendencies.

**Key Observation:** Existing sequence models (Transformers, Mamba, RWKV) all rely on:
- Dot-product similarity, or
- L2 regression (Mean Squared Error)

These create sensitivity to outliers and limit architectural exploration.

### Four Design Dimensions

MIRAS provides a **generative framework** with four customizable components:

| Dimension | Options | Purpose |
|-----------|---------|---------|
| **1. Memory Architecture** | Vector, Matrix, Deep MLP | Information storage structure |
| **2. Attentional Bias** | L2, L1, Huber, Custom | Internal learning objective |
| **3. Retention Gate** | Weight decay, Exponential, Custom | Balance new vs. retained knowledge |
| **4. Memory Algorithm** | SGD, Adam, Online Learning | Optimization method for updates |

### Novel Insight: Forgetting = Regularization

MIRAS proves mathematically that **forgetting mechanisms in recurrent models are equivalent to retention regularization**:

```
L_total = L_memory + λ * ||θ - θ_prev||²
           ↑              ↑
      Learning        Retention (prevents catastrophic forgetting)
```

This unifies disparate approaches:
- Weight decay = forgetting
- Momentum = temporal smoothing
- Regularization = retention

### Three MIRAS Variants

| Variant | Attentional Bias | Characteristics |
|---------|------------------|-----------------|
| **YAAD** | Huber Loss | Gentler penalty for outliers, robust to messy data |
| **MONETA** | Generalized Norms | Stricter learning/forgetting rules |
| **MEMORA** | Probability Mapping | Controlled, balanced updates |

**Why Huber Loss (YAAD) matters:**
```python
def huber_loss(y_pred, y_true, delta=1.0):
    error = y_pred - y_true
    is_small_error = abs(error) <= delta

    # L2 for small errors (accurate gradients)
    small_error_loss = 0.5 * error**2

    # L1 for large errors (outlier robust)
    large_error_loss = delta * (abs(error) - 0.5 * delta)

    return where(is_small_error, small_error_loss, large_error_loss)
```

Standard L2 (MSE) makes memory **sensitive to outliers**—a single anomalous token can dominate gradients. Huber loss provides stability while maintaining accuracy.

### Performance

MIRAS variants achieve:
- Improved language modeling over Transformers
- Better commonsense reasoning than linear RNNs
- Exceptional recall-intensive task performance
- Maintained fast, parallelizable training

---

## Implications for Project Aura's Agent Architecture

### Current State: Cognitive Memory Service

Project Aura already implements a neuroscience-inspired memory system in `src/services/cognitive_memory_service.py`:

```python
class CognitiveMemoryService:
    episodic_memory: EpisodicMemory    # Hippocampus - specific instances
    semantic_memory: SemanticMemory    # Neocortex - generalized knowledge
    procedural_memory: ProceduralMemory # Basal ganglia - action sequences
```

**Current Limitations:**
1. **Episodic memory stores full context snapshots** - inefficient for long sequences
2. **No surprise-based consolidation** - all experiences treated equally
3. **Fixed confidence thresholds** - not learned from data
4. **L2-based similarity** - potentially sensitive to outliers

### Proposed Enhancements

#### Enhancement 1: Surprise-Driven Memory Consolidation

Replace fixed episodic storage with gradient-based surprise detection:

```python
class TitanEpisodicMemory:
    """Surprise-driven episodic memory inspired by Titans."""

    def __init__(self, memory_dim: int, depth: int = 3):
        self.memory_mlp = DeepMLPMemory(memory_dim, depth)
        self.surprise_threshold = 0.7
        self.momentum = 0.9
        self.past_surprise = 0.0

    def compute_surprise(self, experience: Experience) -> float:
        """Compute gradient-based surprise score."""
        with torch.enable_grad():
            prediction = self.memory_mlp(experience.context)
            loss = self.compute_prediction_loss(prediction, experience.outcome)
            loss.backward()

            # Gradient magnitude as surprise
            grad_norm = sum(p.grad.norm() for p in self.memory_mlp.parameters())

        # Apply momentum for temporal smoothing
        effective_surprise = (
            self.momentum * grad_norm +
            (1 - self.momentum) * self.past_surprise
        )
        self.past_surprise = effective_surprise
        return effective_surprise

    def should_memorize(self, experience: Experience) -> bool:
        """Selective memorization based on surprise."""
        surprise = self.compute_surprise(experience)
        return surprise > self.surprise_threshold

    def update_memory(self, experience: Experience):
        """Test-time training update to memory MLP."""
        if self.should_memorize(experience):
            # Gradient descent on memory parameters
            self.optimizer.step()
            self.log_consolidation(experience, surprise)
```

**Benefits:**
- Only memorable (surprising) experiences stored
- Memory capacity used more efficiently
- Aligns with human memory formation (emotional/surprising events remembered better)

#### Enhancement 2: Deep MLP Memory Module

Replace vector/matrix episodic storage with deep neural memory:

```python
class DeepMLPMemory(nn.Module):
    """Deep MLP memory module from Titans architecture."""

    def __init__(self, dim: int, depth: int = 3, hidden_mult: int = 4):
        super().__init__()
        self.layers = nn.ModuleList()

        for i in range(depth):
            self.layers.append(nn.Sequential(
                nn.Linear(dim, dim * hidden_mult),
                nn.GELU(),
                nn.Linear(dim * hidden_mult, dim),
                nn.LayerNorm(dim)
            ))

        # Persistent memory (fixed learned weights)
        self.persistent_memory = nn.Parameter(torch.randn(1, dim))

    def retrieve(self, query: Tensor) -> Tensor:
        """Retrieve from memory given query."""
        x = query
        for layer in self.layers:
            x = x + layer(x)  # Residual connections

        # Combine with persistent memory
        return x + self.persistent_memory

    def update(self, key: Tensor, value: Tensor, learning_rate: float = 0.01):
        """Test-time training update."""
        # Compute memory prediction
        prediction = self.retrieve(key)

        # Huber loss for outlier robustness (from MIRAS)
        loss = F.huber_loss(prediction, value, delta=1.0)

        # Update memory parameters
        loss.backward()
        with torch.no_grad():
            for param in self.parameters():
                if param.grad is not None:
                    param -= learning_rate * param.grad
                    param.grad.zero_()
```

**Benefits:**
- Dramatically higher expressiveness than vector storage
- Better compression of complex agent experiences
- Non-linear pattern learning

#### Enhancement 3: MIRAS-Inspired Attentional Bias

Implement configurable memory objectives:

```python
class MIRASMemoryConfig:
    """MIRAS framework for customizable memory objectives."""

    class AttentionalBias(Enum):
        L2 = "l2"           # Standard MSE (current)
        L1 = "l1"           # Robust to outliers
        HUBER = "huber"     # Best of both worlds
        COSINE = "cosine"   # Angular similarity

    class RetentionGate(Enum):
        WEIGHT_DECAY = "weight_decay"
        EXPONENTIAL = "exponential"
        ADAPTIVE = "adaptive"

    def __init__(
        self,
        bias: AttentionalBias = AttentionalBias.HUBER,
        retention: RetentionGate = RetentionGate.ADAPTIVE,
        retention_strength: float = 0.01
    ):
        self.bias = bias
        self.retention = retention
        self.retention_strength = retention_strength

    def compute_loss(self, prediction: Tensor, target: Tensor) -> Tensor:
        """Compute memory loss based on attentional bias."""
        if self.bias == self.AttentionalBias.L2:
            return F.mse_loss(prediction, target)
        elif self.bias == self.AttentionalBias.L1:
            return F.l1_loss(prediction, target)
        elif self.bias == self.AttentionalBias.HUBER:
            return F.huber_loss(prediction, target, delta=1.0)
        elif self.bias == self.AttentionalBias.COSINE:
            return 1 - F.cosine_similarity(prediction, target).mean()

    def compute_retention_penalty(self, current: Tensor, previous: Tensor) -> Tensor:
        """Compute retention regularization (forgetting penalty)."""
        if self.retention == self.RetentionGate.WEIGHT_DECAY:
            return self.retention_strength * (current - previous).pow(2).sum()
        elif self.retention == self.RetentionGate.EXPONENTIAL:
            return self.retention_strength * torch.exp(-(current - previous).pow(2)).sum()
        elif self.retention == self.RetentionGate.ADAPTIVE:
            # Stronger retention for low-surprise, weaker for high-surprise
            return self.retention_strength * F.softplus(current - previous).sum()
```

#### Enhancement 4: Integration with Dual-Agent Architecture

Connect Titans memory to MemoryAgent + CriticAgent:

```python
class TitanEnhancedMemoryAgent:
    """MemoryAgent enhanced with Titans neural memory."""

    def __init__(self, config: MIRASMemoryConfig):
        self.neural_memory = DeepMLPMemory(dim=512, depth=3)
        self.config = config
        self.critic_agent = CriticAgent()  # No memory (as designed)

    async def make_decision(self, task: Task, context: HybridContext) -> Decision:
        # Retrieve from neural long-term memory
        memory_context = self.neural_memory.retrieve(
            self.encode_task(task)
        )

        # Combine with current context
        enriched_context = self.merge_contexts(context, memory_context)

        # Make initial decision
        decision = await self.decide(task, enriched_context)

        # Compute surprise for this decision
        surprise = self.compute_surprise(task, decision)

        # Route based on surprise (analogous to confidence)
        if surprise > CRITICAL_THRESHOLD:
            # High surprise = uncertain = get critic evaluation
            critic_eval = await self.critic_agent.evaluate(decision)
            decision = self.reconcile(decision, critic_eval)

        # Update memory if surprising (test-time training)
        if surprise > MEMORIZATION_THRESHOLD:
            self.neural_memory.update(
                key=self.encode_task(task),
                value=self.encode_outcome(decision)
            )

        return decision
```

### Mapping Titans Concepts to Project Aura

| Titans Concept | Project Aura Equivalent | Enhancement |
|----------------|------------------------|-------------|
| Surprise Metric | Confidence Score | Gradient-based computation |
| Contextual Memory | Episodic Memory | Deep MLP storage |
| Persistent Memory | Semantic Memory | Fixed learnable weights |
| Core (Attention) | Working Memory | HybridContext |
| Weight Decay | Memory TTL | Retention regularization |
| Momentum | Temporal Smoothing | Past surprise integration |
| Huber Loss | Similarity Metric | Outlier robustness |

### Implementation Roadmap

#### Phase 1: Research Validation (2 weeks)
- [ ] Implement DeepMLPMemory module
- [ ] Benchmark against current episodic storage
- [ ] Validate surprise metric computation

#### Phase 2: MIRAS Integration (3 weeks)
- [ ] Implement MIRASMemoryConfig
- [ ] Add Huber loss option to memory service
- [ ] Test retention regularization vs. TTL-based expiration

#### Phase 3: Test-Time Training (4 weeks)
- [ ] Implement gradient-based memory updates
- [ ] Add momentum for temporal smoothing
- [ ] Profile inference overhead

#### Phase 4: Production Integration (2 weeks)
- [ ] Wire to CognitiveMemoryService
- [ ] Update MemoryAgent with neural memory
- [ ] Add CloudWatch metrics for surprise distribution

---

## Key Takeaways

### For Project Aura

1. **Our dual-agent architecture is aligned with Titans' philosophy** - surprise-driven routing maps to confidence-based HITL decisions

2. **Deep MLP memory >> vector storage** - significant accuracy gains worth the compute cost

3. **Huber loss should replace L2** - makes memory robust to anomalous agent experiences

4. **Forgetting is regularization** - our TTL-based expiration can be mathematically unified with weight decay

5. **Test-time training is feasible** - Titans proves inference-time learning works at scale

### For the Field

1. **Hybrid architectures are the future** - attention for short-term, neural memory for long-term

2. **2M+ token contexts are achievable** - with proper memory architecture

3. **Smaller models can beat GPT-4** - on specific tasks with better memory

4. **MIRAS provides theoretical foundation** - for designing custom memory objectives

---

## References

1. Behrouz, A., Zhong, P., & Mirrokni, V. (2025). Titans: Learning to Memorize at Test Time. arXiv:2501.00663

2. Behrouz, A., Razaviyayn, M., Zhong, P., & Mirrokni, V. (2025). MIRAS: A Unified Framework for Memory-Integrated Recurrent Architectures. arXiv:2504.13173

3. Google Research Blog: "Titans + MIRAS: Helping AI have long-term memory" https://research.google/blog/titans-miras-helping-ai-have-long-term-memory/

---

## Appendix A: Code References

**Existing Project Aura Memory Architecture:**
- `src/services/cognitive_memory_service.py` - CognitiveMemoryService
- `src/agents/meta_orchestrator.py` - AgentRegistry, AutonomyPolicy
- `src/agents/context_objects.py` - HybridContext, ContextItem

**Proposed New Modules:**
- `src/services/titan_memory_service.py` - DeepMLPMemory, TitanEpisodicMemory
- `src/services/miras_config.py` - MIRASMemoryConfig, AttentionalBias
- `src/agents/titan_memory_agent.py` - TitanEnhancedMemoryAgent

---

*Document Version: 1.0*
*Last Updated: December 6, 2025*
