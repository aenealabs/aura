# ADR-080: Evo-Memory Enhancements for Test-Time Memory Evolution

## Status

Deployed (ALL PHASES COMPLETE - 336 tests)

## Date

2026-02-04

## Context

### Research Foundation

The Evo-Memory framework (arXiv:2511.20857) introduces a paradigm shift from static memory retrieval to **test-time memory evolution**. Key insight: agents should not just recall past context but **reuse reasoning strategies** across task sequences.

### Current Aura Capabilities

Aura already implements significant memory infrastructure:

| Capability | ADR | Implementation |
|------------|-----|----------------|
| Titan Neural Memory | ADR-024 | Test-time training, 237 tests |
| Multi-tier Memory | ADR-030 | SHORT_TERM, LONG_TERM, EPISODIC, SEMANTIC |
| Cognitive Memory | - | Procedural memory, dual-mode (System 1/2) |
| Memory Consolidation | ADR-024 | Weight pruning, slot reduction, layer reset |
| Recursive Context | ADR-051 | 100x context scaling via decomposition |
| Experience Learning | ADR-050 | SWE-RL with history-aware bug injection |

### Gap Analysis

| Evo-Memory Concept | Aura Status | Gap |
|-------------------|-------------|-----|
| Search → Synthesis → Evolve | Implemented | None |
| Experience Reuse | Implemented | None |
| Multi-tier Memory | Implemented | None |
| **Explicit Refine Operation** | Partial | No discrete "Refine" action in ReAct loop |
| **Benchmark Framework** | Missing | No formal memory evolution metrics |
| **Evolution Tracking** | Missing | No metrics for memory improvement over time |

## Decision

Enhance Aura's memory system with three components:

1. **ReMem Action Framework** - Add explicit `Refine` operation to agent action space
2. **Memory Evolution Benchmark** - Implement evaluation framework for memory effectiveness
3. **Evolution Metrics Service** - Track memory improvement across task sequences

## Architecture

### 1. ReMem Action Framework

Extend the ReAct pattern with memory-specific meta-reasoning:

```
Agent Action Space (Extended):
├── Think    - Decompose task into subtasks
├── Act      - Execute environment action
├── Observe  - Process action result
└── Refine   - Meta-reasoning over memory (NEW)
    ├── CONSOLIDATE - Merge related memories (Phase 1a)
    ├── PRUNE       - Remove low-value memories (Phase 1a)
    ├── REINFORCE   - Strengthen successful patterns (Phase 1b)
    ├── ABSTRACT    - Extract strategy from experiences (Phase 3)
    ├── LINK        - Create cross-memory associations (Phase 5)
    ├── CORRECT     - Fix incorrect memories (Phase 5)
    └── ROLLBACK    - Restore from previous state (Phase 5)
```

```python
# src/services/memory/refine_operations.py

class RefineOperation(Enum):
    """Memory refinement operations for ReMem framework."""

    CONSOLIDATE = "consolidate"  # Merge similar experiences
    PRUNE = "prune"              # Remove low-value memories
    REINFORCE = "reinforce"      # Strengthen successful patterns (Titan TTT)
    ABSTRACT = "abstract"        # Extract generalizable strategy
    LINK = "link"                # Create cross-memory associations (Neptune)
    CORRECT = "correct"          # Fix incorrect memories
    ROLLBACK = "rollback"        # Restore from DynamoDB Streams


@dataclass
class RefineAction:
    """A discrete refinement action in the agent loop."""

    operation: RefineOperation
    target_memory_ids: list[str]
    reasoning: str  # Why this refinement (encrypted at rest)
    confidence: float
    tenant_id: str  # Required for multi-tenant isolation
    security_domain: str  # For domain boundary enforcement
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefineResult:
    """Result of a refinement operation."""

    success: bool
    operation: RefineOperation
    affected_memory_ids: list[str]
    rollback_token: str | None  # For ROLLBACK operation
    error: str | None = None
    latency_ms: float = 0.0
```

### CognitiveMemoryService Interface Extensions

Required methods for MemoryRefiner integration:

```python
# src/services/cognitive_memory_service.py (interface additions)

class CognitiveMemoryService:
    """Extended interface for Refine operations."""

    async def merge_memories(
        self,
        memory_ids: list[str],
        merge_strategy: str = "weighted_average"
    ) -> Memory:
        """Merge multiple memories into one consolidated memory."""
        ...

    async def extract_abstraction(
        self,
        memory_ids: list[str],
        abstraction_level: str = "strategy"
    ) -> SemanticMemory:
        """Extract generalizable strategy from episodic memories."""
        ...

    async def update_memory_weight(
        self,
        memory_id: str,
        weight_delta: float,
        reason: str
    ) -> None:
        """Adjust memory importance weight (for REINFORCE)."""
        ...

    async def get_memories_by_domain(
        self,
        security_domain: str,
        tenant_id: str
    ) -> list[Memory]:
        """Get memories within security domain boundary."""
        ...

    async def restore_memory_state(
        self,
        rollback_token: str
    ) -> list[Memory]:
        """Restore memories from DynamoDB Streams snapshot."""
        ...
```

### Titan Memory Integration (REINFORCE Operation)

Map REINFORCE to Titan's test-time training:

```python
# src/services/memory/titan_integration.py

class TitanRefineIntegration:
    """Integrates Refine operations with Titan neural memory."""

    def __init__(
        self,
        titan_service: TitanMemoryService,
        surprise_calculator: SurpriseCalculator
    ):
        self.titan = titan_service
        self.surprise = surprise_calculator

    async def reinforce_pattern(
        self,
        action: RefineAction,
        outcome: TaskOutcome
    ) -> RefineResult:
        """
        Strengthen successful patterns via Titan TTT.

        Maps to:
        - Positive outcome: Lower memorization_threshold for pattern
        - High reuse: Increase TTT learning rate for related memories
        """
        # Calculate surprise delta based on outcome
        surprise_delta = self.surprise.compute_delta(
            expected_outcome=action.metadata.get("expected_outcome"),
            actual_outcome=outcome
        )

        # Adjust Titan memory parameters
        if outcome.success:
            # Lower threshold = more likely to be retrieved
            await self.titan.adjust_memorization_threshold(
                memory_ids=action.target_memory_ids,
                threshold_delta=-0.1 * action.confidence
            )
            # Increase learning rate for successful patterns
            await self.titan.modulate_ttt_learning_rate(
                memory_ids=action.target_memory_ids,
                rate_multiplier=1.0 + (0.2 * action.confidence)
            )

        return RefineResult(
            success=True,
            operation=RefineOperation.REINFORCE,
            affected_memory_ids=action.target_memory_ids,
            rollback_token=None  # TTT changes are continuous
        )
```

### Neptune Integration (LINK Operation)

Store memory relationships as graph edges:

```python
# src/services/memory/neptune_links.py

class MemoryLinkService:
    """Manages memory associations in Neptune."""

    def __init__(self, neptune_service: NeptuneGraphService):
        self.neptune = neptune_service

    async def create_link(
        self,
        action: RefineAction
    ) -> RefineResult:
        """
        Create cross-memory association in Neptune.

        Edge types:
        - STRATEGY_DERIVED_FROM: Strategy abstracted from experiences
        - REINFORCES: Successful pattern connection
        - CONTRADICTS: Conflicting information link
        - SUPERSEDES: Memory update chain
        """
        source_id = action.target_memory_ids[0]
        target_id = action.target_memory_ids[1]
        link_type = action.metadata.get("link_type", "RELATED_TO")

        # Create edge in Neptune
        query = """
        g.V().has('memory', 'memory_id', source_id)
          .addE(link_type)
          .to(g.V().has('memory', 'memory_id', target_id))
          .property('confidence', confidence)
          .property('created_at', timestamp)
          .property('tenant_id', tenant_id)
          .property('security_domain', security_domain)
        """

        await self.neptune.execute_gremlin(
            query,
            bindings={
                "source_id": source_id,
                "target_id": target_id,
                "link_type": link_type,
                "confidence": action.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tenant_id": action.tenant_id,
                "security_domain": action.security_domain
            }
        )

        return RefineResult(
            success=True,
            operation=RefineOperation.LINK,
            affected_memory_ids=action.target_memory_ids,
            rollback_token=f"edge:{source_id}:{target_id}:{link_type}"
        )
```

### Async Execution Architecture

Execute Refine operations asynchronously to avoid blocking agent loop:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Agent Orchestrator                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐    │
│  │  Think  │→ │   Act   │→ │ Observe │→ │  Refine Decision        │    │
│  └─────────┘  └─────────┘  └─────────┘  │  (confidence check)     │    │
│                                          └───────────┬─────────────┘    │
└──────────────────────────────────────────────────────│──────────────────┘
                                                       │
                         ┌─────────────────────────────┼─────────────────┐
                         │                             │                 │
                    confidence >= 0.9            confidence < 0.9        │
                         │                             │                 │
                         ▼                             ▼                 │
              ┌──────────────────┐         ┌───────────────────┐        │
              │  Sync Execution  │         │   SQS Queue       │        │
              │  (inline refine) │         │   (async batch)   │        │
              │  latency < 100ms │         │                   │        │
              └────────┬─────────┘         └─────────┬─────────┘        │
                       │                             │                   │
                       │         ┌───────────────────▼─────────────┐    │
                       │         │  RefineWorker Lambda            │    │
                       │         │  - Processes batch every 1 min  │    │
                       │         │  - Circuit breaker if p95>500ms │    │
                       │         └───────────────────┬─────────────┘    │
                       │                             │                   │
                       └──────────────┬──────────────┘                   │
                                      ▼                                  │
              ┌───────────────────────────────────────────────────────┐  │
              │                    Memory Layer                        │  │
              │  ┌─────────────────────────────────────────────────┐  │  │
              │  │              MemoryRefiner                       │  │  │
              │  │  CONSOLIDATE│PRUNE│REINFORCE│ABSTRACT│LINK      │  │  │
              │  └─────────────────────────────────────────────────┘  │  │
              │                          │                            │  │
              │  ┌──────────────┐  ┌─────▼─────┐  ┌────────────────┐  │  │
              │  │CognitiveMemory│ │  Titan    │  │   Neptune      │  │  │
              │  │   Service    │  │  Memory   │  │   (LINK ops)   │  │  │
              │  └──────────────┘  └───────────┘  └────────────────┘  │  │
              └───────────────────────────────────────────────────────┘  │
                                                                         │
              ┌───────────────────────────────────────────────────────┐  │
              │               Observability Layer                      │  │
              │  ┌─────────────────┐  ┌─────────────────────────────┐ │  │
              │  │EvolutionTracker │  │ NeuralMemoryAuditLogger     │ │  │
              │  │  (metrics)      │  │   (compliance audit)        │ │  │
              │  └─────────────────┘  └─────────────────────────────┘ │  │
              └───────────────────────────────────────────────────────┘  │
                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Feature Flag Integration

Gradual rollout via feature flags:

```python
# src/services/memory/refine_integration.py

class RefineIntegration:
    """Integrates Refine operations with AgentOrchestrator."""

    async def maybe_refine(
        self,
        agent_id: str,
        tenant_id: str,
        task_outcome: TaskOutcome,
        memories_used: list[str]
    ) -> list[RefineResult]:
        """Execute refinement if enabled for tenant."""

        # Check feature flag
        if not await self.feature_flags.is_enabled(
            "evo_memory_refine",
            tenant_id=tenant_id,
            default=False
        ):
            return []

        # Check operation-specific flags
        enabled_ops = await self.feature_flags.get_variant(
            "evo_memory_refine_operations",
            tenant_id=tenant_id,
            default=["CONSOLIDATE", "PRUNE"]  # Phase 1a only by default
        )

        # Generate refine actions
        actions = await self._generate_refine_actions(
            agent_id, task_outcome, memories_used, enabled_ops
        )

        # Execute based on confidence
        results = []
        for action in actions:
            if action.confidence >= 0.9:
                # Sync execution
                result = await self.refiner.refine(action)
            else:
                # Queue for async processing
                await self.sqs.send_message(
                    QueueUrl=self.refine_queue_url,
                    MessageBody=json.dumps(asdict(action))
                )
                result = RefineResult(
                    success=True,
                    operation=action.operation,
                    affected_memory_ids=action.target_memory_ids,
                    rollback_token=None
                )
            results.append(result)

        return results
```

### Error Handling

```python
# src/services/memory/refine_error_handling.py

class RefineErrorHandler:
    """Handles errors during refinement operations."""

    async def handle_consolidate_failure(
        self,
        action: RefineAction,
        error: Exception
    ) -> RefineResult:
        """
        Handle CONSOLIDATE failure.

        Strategy: Partial consolidation is worse than no consolidation.
        Roll back any partial changes.
        """
        logger.error(f"CONSOLIDATE failed: {error}", extra={
            "action": asdict(action),
            "error_type": type(error).__name__
        })

        # Attempt rollback if partial changes made
        if hasattr(error, "partial_merge_ids"):
            await self.memory_service.restore_memory_state(
                error.partial_merge_ids
            )

        return RefineResult(
            success=False,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=[],
            rollback_token=None,
            error=str(error)
        )

    async def handle_abstract_failure(
        self,
        action: RefineAction,
        error: Exception
    ) -> RefineResult:
        """
        Handle ABSTRACT failure (LLM call failed).

        Strategy: Log and continue - abstraction is non-critical.
        Retry via async queue with exponential backoff.
        """
        logger.warning(f"ABSTRACT failed, queuing retry: {error}")

        # Queue for retry with backoff
        retry_count = action.metadata.get("retry_count", 0)
        if retry_count < 3:
            action.metadata["retry_count"] = retry_count + 1
            delay_seconds = 60 * (2 ** retry_count)  # 1min, 2min, 4min
            await self.sqs.send_message(
                QueueUrl=self.refine_queue_url,
                MessageBody=json.dumps(asdict(action)),
                DelaySeconds=min(delay_seconds, 900)  # Max 15 min
            )

        return RefineResult(
            success=False,
            operation=RefineOperation.ABSTRACT,
            affected_memory_ids=[],
            rollback_token=None,
            error=f"Queued for retry ({retry_count + 1}/3)"
        )

    async def handle_transient_failure(
        self,
        action: RefineAction,
        error: Exception
    ) -> RefineResult:
        """Handle transient failures (network, timeout)."""
        if self._is_retryable(error):
            await self.sqs.send_message(
                QueueUrl=self.refine_queue_url,
                MessageBody=json.dumps(asdict(action)),
                DelaySeconds=30
            )
            return RefineResult(
                success=False,
                operation=action.operation,
                affected_memory_ids=[],
                error="Transient failure, queued for retry"
            )
        raise error
```

### 2. Memory Evolution Benchmark

Implement evaluation framework with sampling for production:

```python
# src/services/memory/evolution_benchmark.py

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""

    sampling_rate: float = 0.01  # 1% of tasks
    max_tasks_per_benchmark: int = 100
    exclude_production: bool = True  # Default to staging only
    off_peak_only: bool = True  # Run during off-peak hours
    off_peak_start_hour: int = 2  # 2 AM UTC
    off_peak_end_hour: int = 6  # 6 AM UTC


class MemoryBenchmarkSuite:
    """Benchmark suite for memory evolution effectiveness."""

    BENCHMARK_CATEGORIES = {
        "factual_recall": [
            "entity_tracking",      # Track entities across conversation
            "temporal_ordering",    # Remember event sequences
            "attribute_binding",    # Associate properties with entities
        ],
        "strategy_transfer": [
            "similar_task_reuse",   # Apply strategy to similar problems
            "domain_adaptation",    # Transfer across domains
            "abstraction_quality",  # Measure strategy generalization
        ],
        "multi_turn_learning": [
            "cumulative_accuracy",  # Improvement over task sequence
            "forgetting_resistance",# Retention after intervening tasks
            "interference_handling",# Handle conflicting information
        ],
        "evolution_efficiency": [
            "memory_utilization",   # Useful vs total memories
            "consolidation_rate",   # Speed of strategy formation
            "adaptation_speed",     # How fast memory improves
        ],
    }

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.baseline_metrics: dict[str, float] = {}

    async def capture_baseline(
        self,
        agent: Agent
    ) -> dict[str, float]:
        """Capture baseline metrics at agent initialization."""
        baseline = {}
        for category in self.BENCHMARK_CATEGORIES:
            baseline[category] = await self._measure_category(agent, category)
        self.baseline_metrics[agent.agent_id] = baseline
        return baseline

    async def run_benchmark(
        self,
        agent: Agent,
        category: str,
        task_sequence: list[Task]
    ) -> BenchmarkResult:
        """Run benchmark on agent's memory system."""

        # Check if we should run (sampling + off-peak)
        if not self._should_run(agent):
            return BenchmarkResult(skipped=True, reason="sampling/timing")

        # Run benchmark tasks
        results = []
        for task in task_sequence[:self.config.max_tasks_per_benchmark]:
            result = await self._execute_benchmark_task(agent, task)
            results.append(result)

        # Compute delta from baseline
        current_score = self._compute_category_score(results)
        baseline_score = self.baseline_metrics.get(agent.agent_id, {}).get(category, 0)
        evolution_delta = current_score - baseline_score

        return BenchmarkResult(
            category=category,
            score=current_score,
            baseline=baseline_score,
            evolution_delta=evolution_delta,
            task_count=len(results),
            timestamp=datetime.now(timezone.utc)
        )
```

### 3. Evolution Metrics Service

Track memory improvement with aggregated CloudWatch metrics:

```python
# src/services/memory/evolution_metrics.py

@dataclass
class EvolutionMetrics:
    """Metrics tracking memory evolution effectiveness."""

    # Accuracy metrics
    retrieval_precision: float      # Relevant memories retrieved
    retrieval_recall: float         # All relevant memories found
    strategy_reuse_rate: float      # % tasks using prior strategies

    # Evolution metrics
    consolidation_count: int        # Memories merged
    abstractions_created: int       # Strategies extracted
    memories_pruned: int            # Low-value memories removed
    reinforcements_applied: int     # Patterns strengthened

    # Efficiency metrics
    memory_utilization: float       # Active / Total memories
    avg_memory_age_at_use: float    # How old are reused memories
    strategy_transfer_success: float # Cross-domain strategy success

    # Quality metrics
    false_memory_rate: float        # Incorrect memories retrieved
    interference_events: int        # Conflicting memory activations
    evolution_gain: float           # Performance improvement over time


@dataclass
class EvolutionTrackerConfig:
    """Configuration for evolution tracking."""

    retention_days_dev: int = 90
    retention_days_prod: int = 365
    metrics_aggregation_interval: int = 60  # seconds
    store_full_refine_actions: bool = False  # Store in S3 instead


class EvolutionTracker:
    """Tracks memory evolution across agent sessions."""

    def __init__(
        self,
        dynamodb_table: str,
        s3_bucket: str,
        config: EvolutionTrackerConfig,
        audit_logger: NeuralMemoryAuditLogger
    ):
        self.table = dynamodb_table
        self.s3_bucket = s3_bucket
        self.config = config
        self.audit_logger = audit_logger
        self.metrics_buffer: list[EvolutionMetrics] = []

    async def record_task_completion(
        self,
        agent_id: str,
        task_id: str,
        tenant_id: str,
        memories_used: list[str],
        strategies_applied: list[str],
        outcome: TaskOutcome,
        refine_actions: list[RefineAction]
    ) -> None:
        """Record memory usage and evolution for a completed task."""

        # Create audit record for compliance
        await self.audit_logger.log_memory_evolution(
            agent_id=agent_id,
            task_id=task_id,
            tenant_id=tenant_id,
            refine_actions=refine_actions,
            outcome=outcome
        )

        # Store action summaries in DynamoDB (not full actions)
        action_summary = self._summarize_actions(refine_actions)

        # Store full refine actions in S3 if needed
        s3_key = None
        if self.config.store_full_refine_actions and refine_actions:
            s3_key = f"refine-actions/{tenant_id}/{agent_id}/{task_id}.json"
            await self._store_to_s3(s3_key, refine_actions)

        # Compute TTL based on environment
        ttl = self._compute_ttl()

        # Write to DynamoDB with date-bucketed partition key
        date_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await self.dynamodb.put_item(
            TableName=self.table,
            Item={
                "pk": f"{agent_id}#{date_bucket}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task_id,
                "tenant_id": tenant_id,
                "memories_used_count": len(memories_used),
                "strategies_applied_count": len(strategies_applied),
                "outcome": outcome.value,
                "action_summary": action_summary,
                "s3_detail_key": s3_key,
                "ttl": ttl
            }
        )

    async def compute_evolution_gain(
        self,
        agent_id: str,
        window_size: int = 100
    ) -> float:
        """Compute performance improvement over last N tasks."""

        # Query using GSI for time-ordered tasks
        response = await self.dynamodb.query(
            TableName=self.table,
            IndexName="agent-task-sequence-index",
            KeyConditionExpression="agent_id = :aid",
            ExpressionAttributeValues={":aid": agent_id},
            ScanIndexForward=False,  # Most recent first
            Limit=window_size
        )

        if len(response["Items"]) < 10:
            return 0.0  # Not enough data

        # Compare first half vs second half performance
        items = response["Items"]
        first_half = items[len(items)//2:]
        second_half = items[:len(items)//2]

        first_success_rate = sum(1 for i in first_half if i["outcome"] == "success") / len(first_half)
        second_success_rate = sum(1 for i in second_half if i["outcome"] == "success") / len(second_half)

        return second_success_rate - first_success_rate


class MetricsPublisher:
    """Publishes aggregated metrics to CloudWatch."""

    NAMESPACE = "Aura/MemoryEvolution"

    async def publish_aggregated_metrics(
        self,
        metrics: EvolutionMetrics,
        dimensions: dict[str, str]
    ) -> None:
        """
        Publish metrics aggregated at 1-minute intervals.

        Publishes 5 key metrics (not all 13) to control costs:
        - evolution_gain
        - strategy_reuse_rate
        - retrieval_precision
        - memory_utilization
        - consolidation_count
        """
        await self.cloudwatch.put_metric_data(
            Namespace=self.NAMESPACE,
            MetricData=[
                {
                    "MetricName": "EvolutionGain",
                    "Value": metrics.evolution_gain,
                    "Unit": "None",
                    "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()]
                },
                {
                    "MetricName": "StrategyReuseRate",
                    "Value": metrics.strategy_reuse_rate,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()]
                },
                {
                    "MetricName": "RetrievalPrecision",
                    "Value": metrics.retrieval_precision,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()]
                },
                {
                    "MetricName": "MemoryUtilization",
                    "Value": metrics.memory_utilization,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()]
                },
                {
                    "MetricName": "ConsolidationCount",
                    "Value": metrics.consolidation_count,
                    "Unit": "Count",
                    "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()]
                },
            ]
        )
```

## Implementation Plan

### Phase 1a: Low-Latency Operations ✅ COMPLETE (~1,500 LOC, 68 tests)

| File | Description | LOC | Status |
|------|-------------|-----|--------|
| `src/services/memory_evolution/contracts.py` | RefineOperation enum, RefineAction, RefineResult | 325 | ✅ |
| `src/services/memory_evolution/config.py` | MemoryEvolutionConfig, feature flags | 292 | ✅ |
| `src/services/memory_evolution/exceptions.py` | Custom exceptions with rich context | 258 | ✅ |
| `src/services/memory_evolution/memory_refiner.py` | MemoryRefiner with CONSOLIDATE/PRUNE, circuit breaker | 652 | ✅ |

### Phase 1b: Titan Integration ✅ COMPLETE (~900 LOC, 39 tests)

| File | Description | LOC | Status |
|------|-------------|-----|--------|
| `src/services/memory_evolution/titan_integration.py` | TitanRefineIntegration, SurpriseCalculator | 471 | ✅ |
| `src/services/memory_evolution/refine_integration.py` | RefineActionRouter, RefineDecisionMaker | 445 | ✅ |

### Phase 2: Evolution Metrics ✅ COMPLETE (~1,500 LOC, 50 tests)

| File | Description | LOC | Status |
|------|-------------|-----|--------|
| `src/services/memory_evolution/evolution_metrics.py` | EvolutionMetrics, EvolutionTracker | 619 | ✅ |
| `src/services/memory_evolution/metrics_publisher.py` | CloudWatch metrics publisher | 461 | ✅ |
| `src/services/memory_evolution/audit_integration.py` | NeuralMemoryAuditLogger integration | 402 | ✅ |

### Phase 3: ABSTRACT Operation ✅ COMPLETE (~1,050 LOC, 38 tests)

| File | Description | LOC | Status |
|------|-------------|-----|--------|
| `src/services/memory_evolution/abstract_operation.py` | LLM-based strategy extraction, HDBSCAN clustering | 936 | ✅ |
| `src/services/memory_evolution/contracts.py` | AbstractionCandidate, AbstractedStrategy dataclasses | +114 | ✅ |

### Phase 4: Benchmark Framework ✅ COMPLETE (~1,400 LOC, 42 tests)

| File | Description | LOC | Status |
|------|-------------|-----|--------|
| `src/services/memory_evolution/evolution_benchmark.py` | MemoryEvolutionBenchmark, DriftDetector, AdaptiveSampler, TaskGenerator | 1386 | ✅ |

### Phase 5: Advanced Operations (~600 LOC, 45 tests)

| File | Description | LOC |
|------|-------------|-----|
| `src/services/memory/neptune_links.py` | LINK operation via Neptune | 250 |
| `src/services/memory/correct_operation.py` | CORRECT with LLM verification | 200 |
| `src/services/memory/rollback_operation.py` | ROLLBACK from DynamoDB Streams | 150 |

### Phase 6: Multi-Agent Sharing (~400 LOC, 30 tests)

| File | Description | LOC |
|------|-------------|-----|
| `src/services/memory/cross_agent_propagation.py` | Strategy broadcast between agents | 250 |
| `src/services/memory/strategy_promotion.py` | Approval workflow for shared strategies | 150 |

**Total: ~3,800 LOC, 280 tests**

## Infrastructure

### DynamoDB Table: Memory Evolution Metrics

```yaml
# deploy/cloudformation/memory-evolution-dynamodb.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 2.19 - Memory Evolution (ADR-080)'

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, qa, prod]
  ProjectName:
    Type: String
    Default: aura

Resources:
  MemoryEvolutionKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: KMS key for memory evolution data encryption
      EnableKeyRotation: true
      KeyPolicy:
        Version: '2012-10-17'
        Statement:
          - Sid: Enable IAM User Permissions
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'
          - Sid: Allow DynamoDB
            Effect: Allow
            Principal:
              Service: dynamodb.amazonaws.com
            Action:
              - kms:Encrypt
              - kms:Decrypt
              - kms:GenerateDataKey
            Resource: '*'
            Condition:
              StringEquals:
                kms:ViaService: !Sub 'dynamodb.${AWS::Region}.amazonaws.com'
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-memory-evolution-key-${Environment}'

  MemoryEvolutionTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-memory-evolution-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
        - AttributeName: agent_id
          AttributeType: S
        - AttributeName: task_sequence_number
          AttributeType: N
        - AttributeName: task_id
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: task-index
          KeySchema:
            - AttributeName: task_id
              KeyType: HASH
          Projection:
            ProjectionType: ALL
        - IndexName: agent-task-sequence-index
          KeySchema:
            - AttributeName: agent_id
              KeyType: HASH
            - AttributeName: task_sequence_number
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !GetAtt MemoryEvolutionKMSKey.Arn
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-memory-evolution-${Environment}'
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment
        - Key: ADR
          Value: ADR-080
        - Key: DataClassification
          Value: CONFIDENTIAL

  RefineAsyncQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-refine-async-${Environment}'
      VisibilityTimeout: 300
      MessageRetentionPeriod: 86400
      KmsMasterKeyId: !GetAtt MemoryEvolutionKMSKey.Arn
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt RefineDeadLetterQueue.Arn
        maxReceiveCount: 3
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-refine-async-${Environment}'

  RefineDeadLetterQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-refine-dlq-${Environment}'
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !GetAtt MemoryEvolutionKMSKey.Arn

Outputs:
  MemoryEvolutionTableName:
    Value: !Ref MemoryEvolutionTable
    Export:
      Name: !Sub '${AWS::StackName}-TableName'

  MemoryEvolutionTableArn:
    Value: !GetAtt MemoryEvolutionTable.Arn
    Export:
      Name: !Sub '${AWS::StackName}-TableArn'

  RefineAsyncQueueUrl:
    Value: !Ref RefineAsyncQueue
    Export:
      Name: !Sub '${AWS::StackName}-QueueUrl'

  RefineAsyncQueueArn:
    Value: !GetAtt RefineAsyncQueue.Arn
    Export:
      Name: !Sub '${AWS::StackName}-QueueArn'
```

### CloudWatch Alarms

```yaml
# deploy/cloudformation/memory-evolution-monitoring.yaml

Resources:
  RefineSuccessRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-refine-success-rate-${Environment}'
      AlarmDescription: Alert if refine operation success rate drops below 80%
      MetricName: RefineSuccessRate
      Namespace: Aura/MemoryEvolution
      Statistic: Average
      Period: 300
      EvaluationPeriods: 3
      Threshold: 0.8
      ComparisonOperator: LessThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-alerts-${Environment}'

  StrategyReuseAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-strategy-reuse-rate-${Environment}'
      AlarmDescription: Alert if strategy reuse rate drops below 30%
      MetricName: StrategyReuseRate
      Namespace: Aura/MemoryEvolution
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 2
      Threshold: 30
      ComparisonOperator: LessThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-alerts-${Environment}'

  EvolutionRegressionAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-evolution-regression-${Environment}'
      AlarmDescription: Alert if evolution gain becomes negative
      MetricName: EvolutionGain
      Namespace: Aura/MemoryEvolution
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 3
      Threshold: 0
      ComparisonOperator: LessThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-alerts-${Environment}'

  RefineLatencyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-refine-latency-${Environment}'
      AlarmDescription: Alert if p95 refine latency exceeds 500ms (trigger circuit breaker)
      MetricName: RefineLatency
      Namespace: Aura/MemoryEvolution
      ExtendedStatistic: p95
      Period: 300
      EvaluationPeriods: 2
      Threshold: 500
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-alerts-${Environment}'
```

## Security Considerations

### Data Classification

- **RefineAction.reasoning**: May contain sensitive code context. Encrypted using envelope encryption with per-record KMS data keys.
- **Memory associations**: Multi-tenant isolation enforced via `tenant_id` and `security_domain` fields.
- **Audit trail**: All Refine operations logged via `NeuralMemoryAuditLogger` for compliance.

### Access Control

```python
# Security domain boundary enforcement
async def validate_consolidation(
    action: RefineAction,
    memories: list[Memory]
) -> bool:
    """Ensure all memories in CONSOLIDATE are same security domain."""
    domains = {m.security_domain for m in memories}
    if len(domains) > 1:
        raise SecurityDomainViolation(
            f"Cannot consolidate memories across domains: {domains}"
        )
    return True

# Tenant isolation for ABSTRACT
async def validate_abstraction(
    action: RefineAction,
    memories: list[Memory]
) -> bool:
    """Ensure abstraction doesn't leak across tenant boundaries."""
    tenants = {m.tenant_id for m in memories}
    if action.tenant_id not in tenants or len(tenants) > 1:
        raise TenantIsolationViolation(
            f"Abstraction would leak across tenants"
        )
    return True
```

### Compliance (CMMC/NIST 800-53)

| Control | Implementation |
|---------|----------------|
| AU-11 Audit Record Retention | TTL: 90 days (dev), 365 days (prod) |
| SI-12 Information Handling | Security domain boundary enforcement |
| AC-4 Information Flow | Tenant isolation checks before ABSTRACT |
| AU-3 Content of Audit Records | Full RefineAction stored in S3 with encryption |

## Integration Tests

| Scenario | Services Involved | Expected Outcome |
|----------|-------------------|------------------|
| Consolidate episodic memories | EpisodicMemoryService, MemoryRefiner | Single merged memory with combined content |
| Consolidate cross-domain (should fail) | CognitiveMemoryService | SecurityDomainViolation raised |
| Abstract strategy from patterns | CognitiveMemoryService, Bedrock | New SemanticMemory of type PATTERN |
| Prune low-value memories | DynamoDB, EvolutionTracker | Memory count reduced, audit logged |
| Reinforce successful pattern | TitanMemoryService | TTT learning rate increased |
| Link memories in Neptune | NeptuneGraphService | Edge created with confidence |
| Rollback consolidation | DynamoDB Streams | Original memories restored |
| Async queue processing | SQS, Lambda | Actions processed within 5 minutes |
| Circuit breaker activation | CloudWatch, Feature Flags | Sync execution disabled |
| Multi-tenant isolation | All services | No cross-tenant data leakage |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Strategy reuse rate | >40% | % tasks leveraging prior strategies |
| Retrieval precision | >85% | Relevant memories / retrieved memories |
| Evolution gain | >15% | Performance improvement over 100 tasks |
| Consolidation efficiency | >30% | Memories consolidated / total memories |
| Refine success rate | >95% | Successful / total refine operations |
| Refine p95 latency | <500ms | Sync execution latency |
| Benchmark coverage | 100% | All 4 categories implemented |

## Cost Analysis

| Component | Dev (10K tasks/day) | Prod (100K tasks/day) |
|-----------|---------------------|----------------------|
| DynamoDB writes | $0.38/month | $3.75/month |
| DynamoDB reads | $0.19/month | $1.88/month |
| DynamoDB storage | $0.90/month | $9.00/month |
| CloudWatch metrics (5 aggregated) | $1.50/month | $1.50/month |
| SQS queue | $0.10/month | $1.00/month |
| S3 (full action logs) | $0.50/month | $5.00/month |
| **Total** | **~$3.50/month** | **~$22/month** |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Refine operations slow agent loop | High | Async execution via SQS, confidence threshold |
| Memory consolidation loses information | High | ROLLBACK operation, audit trail, DynamoDB Streams |
| Benchmark overhead in production | Medium | Sampling (1%), off-peak execution, staging-only default |
| Strategy over-generalization | Medium | Confidence thresholds, domain boundaries |
| Cross-tenant data leakage | Critical | Security domain enforcement, tenant isolation checks |
| LLM cost for ABSTRACT | Medium | Phase 3 rollout, async processing, caching |

## Alternatives Considered

### 1. Full Evo-Memory Reimplementation

**Rejected:** Aura already has 90% of the capabilities. Full reimplementation would duplicate existing code.

### 2. External Memory Service (Redis/Memcached)

**Rejected:** Loses integration with Titan neural memory and cognitive services. Adds operational complexity.

### 3. No Changes (Current State)

**Rejected:** Leaves gap in explicit refinement operations and lacks metrics for measuring memory evolution effectiveness.

## References

- [Evo-Memory: Towards Evolving Test-Time Memory for LLM Agents](https://arxiv.org/html/2511.20857v1)
- ADR-024: Titan Neural Memory Architecture
- ADR-030: AWS Agent Parity (Episodic Memory)
- ADR-050: Self-Play SWE-RL
- ADR-051: Recursive Context and Embedding Prediction

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-02-04 | Conditional Approval |
| Mike | Principal ML Engineer | 2026-02-04 | Conditional Approval |
| Pending | Senior Database Engineer | - | - |

### Review Summary

**Architecture Review - 2026-02-04:**

Conditional approval granted. The ADR is architecturally sound and appropriately scoped. Key feedback incorporated:

- Added customer-managed KMS key for DynamoDB encryption
- Added TTL specification for data retention (90 days dev, 365 days prod)
- Changed partition key to composite `agent_id#YYYY-MM-DD` to prevent hot partitions
- Added async execution path via SQS to avoid blocking agent loop
- Integrated with existing `NeuralMemoryAuditLogger` for compliance
- Added Neptune integration for LINK operation
- Added feature flag integration for gradual rollout
- Added comprehensive error handling specification
- Added security domain boundary enforcement
- Added tenant isolation checks for ABSTRACT operation
- Adjusted phases to prioritize low-latency operations (1a) and Titan integration (1b)

**Mike (Principal ML Engineer) - 2026-02-04:**

Conditional approval granted. Key feedback to address before Phase 1b:

**High Priority (Required for Phase 1b):**
- Titan interface does not have per-memory-id `adjust_memorization_threshold()` or `modulate_ttt_learning_rate()` - must extend TitanMemoryServiceConfig
- Replace linear threshold adjustment with sigmoid/tanh for bounded, non-linear adjustment
- Add TTT stability safeguards: rate cooldown period, exponential decay for multipliers, reinforcement budget per window
- Add confidence intervals and statistical tests (two-proportion z-test) to evolution_gain calculation

**Medium Priority (Phase 2-3):**
- ABSTRACT operation: implement hybrid embedding clustering (HDBSCAN) + LLM refinement pipeline
- Add abstraction quality metrics: transfer_success_rate, compression_ratio, reconstruction_accuracy
- Implement adaptive/stratified sampling for benchmarks (1% base, 10% during anomalies)
- Add drift detection with Population Stability Index (PSI) threshold of 0.2

**Recommended Additional Metrics:**
- `memory_churn_rate` - rate of memory creation/deletion
- `ttt_convergence_rate` - fraction of TTT updates converging within budget
- `abstraction_depth` - levels of abstraction hierarchy
- `retrieval_latency_p99` - critical for production SLOs
- `drift_detection_score` - distribution shift measure

**Deferred (Future ADR):**
- Versioned strategy schema for A/B testing and rollback
- ExperimentManager for sequential A/B testing with early stopping
