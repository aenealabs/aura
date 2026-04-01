"""Integration of TitanMemoryService with CognitiveMemoryService.

This module provides the integration layer between the neural memory
(TitanMemoryService) and the existing cognitive memory architecture.

Key integration points:
1. Surprise-driven selective memorization for episodic storage
2. Neural retrieval combined with existing pattern completion
3. Confidence estimation enhanced with neural memory signals

Reference: ADR-024 - Titan Neural Memory Architecture Integration
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cognitive_memory_service import (
    AgentMode,
    CognitiveMemoryService,
    ConfidenceEstimate,
    EmbeddingService,
    EpisodicMemory,
    EpisodicStore,
    OutcomeStatus,
    ProceduralStore,
    RecommendedAction,
    RetrievedMemory,
    SemanticStore,
    Strategy,
)

logger = logging.getLogger(__name__)

# Conditional import for TitanMemoryService (requires PyTorch)
try:
    import torch

    from .titan_memory_service import (
        RetrievalResult,
        TitanMemoryService,
        TitanMemoryServiceConfig,
        create_titan_memory_service,
    )

    TITAN_AVAILABLE = True
except ImportError:
    TITAN_AVAILABLE = False
    TitanMemoryService = None  # type: ignore[assignment,misc]
    TitanMemoryServiceConfig = None  # type: ignore[assignment,misc]
    create_titan_memory_service = None  # type: ignore[assignment]
    logger.info("TitanMemoryService not available (PyTorch not installed)")


@dataclass
class TitanIntegrationConfig:
    """Configuration for Titan-Cognitive integration.

    Attributes:
        enable_titan_memory: Enable neural memory enhancement
        memory_dim: Neural memory dimension
        memory_depth: Neural memory depth (MLP layers)
        miras_preset: MIRAS preset for memory behavior
        enable_ttt: Enable test-time training
        memorization_threshold: Surprise threshold for storing in neural memory
        retrieval_weight: Weight for neural retrieval (0-1)
        use_neural_confidence: Use neural surprise for confidence adjustment
        neural_confidence_weight: Weight for neural confidence signal
    """

    enable_titan_memory: bool = True
    memory_dim: int = 512
    memory_depth: int = 3
    miras_preset: str = "enterprise_standard"
    enable_ttt: bool = True
    memorization_threshold: float = 0.7
    retrieval_weight: float = 0.3  # 30% neural, 70% traditional
    use_neural_confidence: bool = True
    neural_confidence_weight: float = 0.2


@dataclass
class HybridRetrievalResult:
    """Combined retrieval result from neural and traditional memory."""

    # Retrieved memories from both sources
    traditional_memories: List[RetrievedMemory]
    neural_content: Optional[Any] = None  # torch.Tensor when available

    # Combined scores
    combined_confidence: float = 0.5
    neural_surprise: float = 0.0
    neural_confidence: float = 0.5

    # Diagnostics
    neural_latency_ms: float = 0.0
    traditional_latency_ms: float = 0.0

    # Source weights used
    neural_weight: float = 0.3
    traditional_weight: float = 0.7


class TitanCognitiveService:
    """Enhanced CognitiveMemoryService with Titan neural memory.

    This service wraps the existing CognitiveMemoryService and adds
    neural memory capabilities when available. Key enhancements:

    1. **Hybrid Retrieval**: Combines neural memory retrieval with
       traditional pattern completion for richer context.

    2. **Surprise-Driven Memorization**: Uses gradient-based surprise
       to selectively store experiences in neural memory.

    3. **Neural Confidence Signals**: Incorporates neural memory
       surprise as an additional confidence signal.

    Usage:
        ```python
        # Create with integration config
        config = TitanIntegrationConfig(
            enable_titan_memory=True,
            miras_preset="enterprise_standard",
        )

        service = TitanCognitiveService(
            episodic_store=episodic_store,
            semantic_store=semantic_store,
            procedural_store=procedural_store,
            embedding_service=embedding_service,
            integration_config=config,
        )

        # Initialize (required for neural memory)
        await service.initialize()

        # Use enhanced cognitive context
        context = await service.load_cognitive_context(
            task_description="Fix authentication bug",
            domain="SECURITY",
        )

        # Cleanup
        await service.shutdown()
        ```
    """

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        procedural_store: ProceduralStore,
        embedding_service: EmbeddingService,
        integration_config: Optional[TitanIntegrationConfig] = None,
    ):
        """Initialize TitanCognitiveService.

        Args:
            episodic_store: Storage for episodic memories
            semantic_store: Storage for semantic memories
            procedural_store: Storage for procedural memories
            embedding_service: Service for generating embeddings
            integration_config: Configuration for Titan integration
        """
        self.config = integration_config or TitanIntegrationConfig()

        # Initialize base cognitive service
        self.cognitive_service = CognitiveMemoryService(
            episodic_store=episodic_store,
            semantic_store=semantic_store,
            procedural_store=procedural_store,
            embedding_service=embedding_service,
        )

        # Neural memory (initialized in initialize())
        self.titan_service: Optional[TitanMemoryService] = None
        self._is_initialized = False
        self._titan_enabled = False

    async def initialize(self) -> None:
        """Initialize the service, including neural memory if available."""
        if self._is_initialized:
            logger.warning("TitanCognitiveService already initialized")
            return

        # Check if Titan should be enabled
        if self.config.enable_titan_memory and TITAN_AVAILABLE:
            try:
                # Create Titan service
                titan_config = TitanMemoryServiceConfig(
                    memory_dim=self.config.memory_dim,
                    memory_depth=self.config.memory_depth,
                    miras_preset=self.config.miras_preset,
                    enable_ttt=self.config.enable_ttt,
                    memorization_threshold=self.config.memorization_threshold,
                )
                self.titan_service = TitanMemoryService(titan_config)
                self.titan_service.initialize()
                self._titan_enabled = True

                logger.info(
                    f"TitanMemoryService initialized: "
                    f"dim={self.config.memory_dim}, "
                    f"depth={self.config.memory_depth}, "
                    f"preset={self.config.miras_preset}"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize TitanMemoryService: {e}")
                self._titan_enabled = False
        else:
            if self.config.enable_titan_memory and not TITAN_AVAILABLE:
                logger.info(
                    "Titan memory requested but PyTorch not available. "
                    "Using traditional memory only."
                )
            self._titan_enabled = False

        self._is_initialized = True
        logger.info(
            f"TitanCognitiveService initialized "
            f"(neural_memory={'enabled' if self._titan_enabled else 'disabled'})"
        )

    async def shutdown(self) -> None:
        """Shutdown the service and release resources."""
        if self.titan_service is not None:
            self.titan_service.shutdown()
            self.titan_service = None

        self._titan_enabled = False
        self._is_initialized = False
        logger.info("TitanCognitiveService shutdown complete")

    async def load_cognitive_context(
        self,
        task_description: str,
        domain: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load cognitive context with neural memory enhancement.

        This method extends the base cognitive context loading by:
        1. Performing neural memory retrieval in parallel
        2. Combining neural signals with traditional retrieval
        3. Adjusting confidence based on neural surprise

        Args:
            task_description: Description of the task
            domain: Domain context (e.g., "SECURITY", "CICD")
            session_id: Optional session ID for working memory

        Returns:
            Enhanced cognitive context with neural memory signals
        """
        # Get base cognitive context
        base_context = await self.cognitive_service.load_cognitive_context(
            task_description=task_description,
            domain=domain,
            session_id=session_id,
        )

        # If neural memory not enabled, return base context
        if not self._titan_enabled or self.titan_service is None:
            return base_context

        # Perform neural memory retrieval
        try:
            # Embed the task for neural query
            embedding = await self.cognitive_service.embedding_service.embed(
                task_description
            )
            query_tensor = torch.tensor([embedding], dtype=torch.float32)

            # Neural retrieval
            neural_result = self.titan_service.retrieve(query_tensor)

            # Combine results
            hybrid_result = self._combine_retrieval_results(
                traditional_memories=base_context["retrieved_memories"],
                neural_result=neural_result,
            )

            # Adjust confidence with neural signal
            adjusted_confidence = self._adjust_confidence_with_neural(
                base_confidence=base_context["confidence"],
                neural_surprise=neural_result.surprise,
            )

            # Update context with neural enhancements
            enhanced_context = dict(base_context)
            enhanced_context.update(
                {
                    "confidence": adjusted_confidence,
                    "neural_memory": {
                        "enabled": True,
                        "surprise": neural_result.surprise,
                        "neural_confidence": neural_result.confidence,
                        "latency_ms": neural_result.latency_ms,
                    },
                    "hybrid_retrieval": hybrid_result,
                }
            )

            return enhanced_context

        except Exception as e:
            logger.warning(f"Neural retrieval failed, using base context: {e}")
            base_context["neural_memory"] = {"enabled": False, "error": str(e)}
            return base_context

    async def record_episode(
        self,
        task_description: str,
        domain: str,
        decision: str,
        reasoning: str,
        outcome: OutcomeStatus,
        outcome_details: str,
        confidence_at_decision: float,
        error_message: Optional[str] = None,
        guardrail_violated: Optional[str] = None,
    ) -> EpisodicMemory:
        """Record an episode with neural memory consolidation.

        This method extends episodic recording by:
        1. Computing surprise score for the experience
        2. Selectively storing in neural memory based on surprise
        3. Recording the neural memorization decision

        Args:
            task_description: Description of the task
            domain: Domain context
            decision: Decision made
            reasoning: Reasoning for the decision
            outcome: Outcome status
            outcome_details: Details about the outcome
            confidence_at_decision: Confidence when decision was made
            error_message: Optional error message
            guardrail_violated: Optional violated guardrail ID

        Returns:
            The recorded episodic memory
        """
        # Record in base cognitive service
        episode = await self.cognitive_service.record_episode(
            task_description=task_description,
            domain=domain,
            decision=decision,
            reasoning=reasoning,
            outcome=outcome,
            outcome_details=outcome_details,
            confidence_at_decision=confidence_at_decision,
            error_message=error_message,
            guardrail_violated=guardrail_violated,
        )

        # Store in neural memory if enabled and surprising
        if self._titan_enabled and self.titan_service is not None:
            try:
                # Create embedding for neural storage
                experience_text = (
                    f"{task_description} {decision} {outcome.value} {outcome_details}"
                )
                embedding = await self.cognitive_service.embedding_service.embed(
                    experience_text
                )
                key_tensor = torch.tensor([embedding], dtype=torch.float32)

                # Create value tensor (could be enhanced with more structured info)
                value_tensor = key_tensor.clone()

                # Store in neural memory (surprise-gated)
                was_memorized, surprise = self.titan_service.update(
                    key=key_tensor,
                    value=value_tensor,
                    # Force memorize failures (high learning value)
                    force_memorize=(outcome == OutcomeStatus.FAILURE),
                )

                if was_memorized:
                    logger.debug(
                        f"Episode {episode.episode_id} stored in neural memory "
                        f"(surprise={surprise:.3f})"
                    )
                    # Add pattern discovered note
                    episode.pattern_discovered = f"neural_surprise:{surprise:.3f}"

            except Exception as e:
                logger.warning(f"Failed to store episode in neural memory: {e}")

        return episode

    async def run_consolidation(self) -> Dict[str, Any]:
        """Run consolidation with neural memory integration."""
        # Run base consolidation
        result = await self.cognitive_service.run_consolidation()

        # Add neural memory stats if enabled
        if self._titan_enabled and self.titan_service is not None:
            stats = self.titan_service.get_stats()
            result["neural_memory"] = {
                "update_count": stats.get("update_count", 0),
                "retrieval_count": stats.get("retrieval_count", 0),
                "memory_age": stats.get("memory_age", 0),
                "memory_size_mb": stats.get("memory_size_mb", 0),
            }

        return result

    def _combine_retrieval_results(
        self,
        traditional_memories: List[RetrievedMemory],
        neural_result: "RetrievalResult",
    ) -> HybridRetrievalResult:
        """Combine traditional and neural retrieval results.

        Uses weighted combination based on configuration.
        """
        neural_weight = self.config.retrieval_weight
        traditional_weight = 1.0 - neural_weight

        # Compute combined confidence
        if traditional_memories:
            traditional_conf = max(m.combined_score for m in traditional_memories)
        else:
            traditional_conf = 0.0

        combined_confidence = (
            traditional_weight * traditional_conf
            + neural_weight * neural_result.confidence
        )

        return HybridRetrievalResult(
            traditional_memories=traditional_memories,
            neural_content=neural_result.content,
            combined_confidence=combined_confidence,
            neural_surprise=neural_result.surprise,
            neural_confidence=neural_result.confidence,
            neural_latency_ms=neural_result.latency_ms,
            neural_weight=neural_weight,
            traditional_weight=traditional_weight,
        )

    def _adjust_confidence_with_neural(
        self,
        base_confidence: ConfidenceEstimate,
        neural_surprise: float,
    ) -> ConfidenceEstimate:
        """Adjust confidence estimate with neural memory signal.

        High neural surprise indicates the input doesn't match learned
        patterns, suggesting lower confidence is warranted.
        """
        if not self.config.use_neural_confidence:
            return base_confidence

        # Neural confidence = inverse of surprise
        neural_confidence = 1.0 - min(neural_surprise, 1.0)

        # Weighted combination
        weight = self.config.neural_confidence_weight
        adjusted_score = (
            1.0 - weight
        ) * base_confidence.score + weight * neural_confidence

        # Create adjusted estimate
        adjusted_factors = dict(base_confidence.factors)
        adjusted_factors["neural_memory"] = neural_confidence

        adjusted_weights = dict(base_confidence.weights)
        # Redistribute weights to include neural signal
        scale = 1.0 - weight
        for k in adjusted_weights:
            adjusted_weights[k] *= scale
        adjusted_weights["neural_memory"] = weight

        # Update uncertainties if neural confidence is low
        adjusted_uncertainties = list(base_confidence.uncertainties)
        if neural_confidence < 0.5:
            adjusted_uncertainties.append("neural_memory")

        return ConfidenceEstimate(
            score=adjusted_score,
            factors=adjusted_factors,
            weights=adjusted_weights,
            uncertainties=adjusted_uncertainties,
            recommended_action=base_confidence.recommended_action,
            confidence_interval=base_confidence.confidence_interval,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        stats = {
            "is_initialized": self._is_initialized,
            "titan_enabled": self._titan_enabled,
            "config": {
                "memory_dim": self.config.memory_dim,
                "memory_depth": self.config.memory_depth,
                "miras_preset": self.config.miras_preset,
                "retrieval_weight": self.config.retrieval_weight,
            },
        }

        if self._titan_enabled and self.titan_service is not None:
            stats["titan_stats"] = self.titan_service.get_stats()

        return stats

    async def __aenter__(self) -> "TitanCognitiveService":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()


def create_titan_cognitive_service(
    episodic_store: EpisodicStore,
    semantic_store: SemanticStore,
    procedural_store: ProceduralStore,
    embedding_service: EmbeddingService,
    enable_titan: bool = True,
    miras_preset: str = "enterprise_standard",
    memory_dim: int = 512,
) -> TitanCognitiveService:
    """Factory function to create a TitanCognitiveService.

    Args:
        episodic_store: Storage for episodic memories
        semantic_store: Storage for semantic memories
        procedural_store: Storage for procedural memories
        embedding_service: Service for generating embeddings
        enable_titan: Enable neural memory enhancement
        miras_preset: MIRAS preset for memory behavior
        memory_dim: Neural memory dimension

    Returns:
        Configured TitanCognitiveService (call initialize() to start)
    """
    config = TitanIntegrationConfig(
        enable_titan_memory=enable_titan,
        miras_preset=miras_preset,
        memory_dim=memory_dim,
    )

    return TitanCognitiveService(
        episodic_store=episodic_store,
        semantic_store=semantic_store,
        procedural_store=procedural_store,
        embedding_service=embedding_service,
        integration_config=config,
    )


# =============================================================================
# MEMORY AGENT - Surprise-Confidence Routing (ADR-024)
# =============================================================================


@dataclass
class MemoryAgentDecision:
    """Result of MemoryAgent decision making.

    Attributes:
        action: Recommended action based on confidence
        confidence: Confidence score (0-1)
        surprise: Neural memory surprise score
        reasoning: Explanation for the decision
        strategy: Selected problem-solving strategy
        requires_critic: Whether dual-agent mode should engage critic
        escalation_reason: Reason if escalation recommended
    """

    action: "RecommendedAction"
    confidence: float
    surprise: float
    reasoning: str
    strategy: Strategy
    requires_critic: bool = False
    escalation_reason: Optional[str] = None
    neural_memory_used: bool = False
    latency_ms: float = 0.0


class MemoryAgent:
    """Agent that uses neural memory for decision routing.

    The MemoryAgent uses Titan neural memory's surprise scores to route
    decisions through appropriate confidence levels:

    - **High confidence (≥0.85)**: Proceed autonomously
    - **Medium confidence (≥0.70)**: Proceed with logging
    - **Low-medium confidence (≥0.50)**: Request review
    - **Low confidence (<0.50)**: Escalate to human

    This implements the surprise → confidence mapping from ADR-024:
    confidence = 1.0 - min(surprise, 1.0)

    Neuroscience analog:
    - Surprise correlates with hippocampal prediction error
    - High prediction error = novel situation = lower confidence
    - Low prediction error = familiar pattern = higher confidence

    Usage:
        ```python
        # Create agent with cognitive service
        agent = MemoryAgent(
            cognitive_service=titan_cognitive_service,
            mode=AgentMode.AUTO,
        )

        # Make a decision
        decision = await agent.make_decision(
            task_description="Fix authentication bug",
            domain="SECURITY",
        )

        if decision.action == RecommendedAction.PROCEED_AUTONOMOUS:
            # Execute with confidence
            ...
        elif decision.action == RecommendedAction.ESCALATE_TO_HUMAN:
            # Route to human review
            ...
        ```
    """

    # Confidence thresholds for routing
    THRESHOLD_AUTONOMOUS = 0.85
    THRESHOLD_LOGGING = 0.70
    THRESHOLD_REVIEW = 0.50

    def __init__(
        self,
        cognitive_service: TitanCognitiveService,
        mode: AgentMode = AgentMode.AUTO,
        enable_metrics: bool = True,
    ):
        """Initialize MemoryAgent.

        Args:
            cognitive_service: TitanCognitiveService for memory operations
            mode: Agent mode (SINGLE, DUAL, AUTO)
            enable_metrics: Enable CloudWatch metrics publishing
        """
        self.cognitive_service = cognitive_service
        self.mode = mode
        self.enable_metrics = enable_metrics

        # Metrics storage (for CloudWatch publishing)
        self._decision_count = 0
        self._autonomous_count = 0
        self._escalation_count = 0
        self._metrics: List[Dict[str, Any]] = []

    async def make_decision(
        self,
        task_description: str,
        domain: str,
        proposed_action: Optional[str] = None,
    ) -> MemoryAgentDecision:
        """Make a routing decision based on neural memory surprise.

        This method:
        1. Retrieves context from neural memory
        2. Maps surprise score to confidence
        3. Routes to appropriate action based on thresholds
        4. Optionally engages critic in DUAL mode

        Args:
            task_description: Description of the task
            domain: Domain context (e.g., "SECURITY", "CICD")
            proposed_action: Optional proposed action to evaluate

        Returns:
            MemoryAgentDecision with routing recommendation
        """
        import time

        start_time = time.perf_counter()

        # Load cognitive context (includes neural memory if enabled)
        context = await self.cognitive_service.load_cognitive_context(
            task_description=task_description,
            domain=domain,
        )

        # Extract neural memory signals
        neural_info = context.get("neural_memory", {})
        neural_enabled = neural_info.get("enabled", False)
        surprise = neural_info.get("surprise", 0.5)
        neural_confidence = neural_info.get("neural_confidence", 0.5)

        # Map surprise to confidence (ADR-024 formula)
        # confidence = 1.0 - min(surprise, 1.0)
        if neural_enabled:
            # Use neural confidence directly (already computed this way)
            base_confidence = neural_confidence
        else:
            # Fall back to traditional confidence
            base_confidence = context["confidence"].score

        # Get strategy from context
        strategy = context["strategy"]

        # Determine recommended action based on confidence thresholds
        action, reasoning = self._route_by_confidence(base_confidence, domain)

        # Check if critic should be engaged (DUAL/AUTO mode)
        requires_critic = self._should_engage_critic(
            confidence=base_confidence,
            task_description=task_description,
            domain=domain,
        )

        # Determine escalation reason if applicable
        escalation_reason = None
        if action == RecommendedAction.ESCALATE_TO_HUMAN:
            escalation_reason = self._get_escalation_reason(
                confidence=base_confidence,
                surprise=surprise,
                context=context,
            )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Update metrics
        self._decision_count += 1
        if action == RecommendedAction.PROCEED_AUTONOMOUS:
            self._autonomous_count += 1
        elif action == RecommendedAction.ESCALATE_TO_HUMAN:
            self._escalation_count += 1

        # Record metric for CloudWatch
        if self.enable_metrics:
            self._record_metric(
                {
                    "operation": "make_decision",
                    "confidence": base_confidence,
                    "surprise": surprise,
                    "action": action.value,
                    "domain": domain,
                    "neural_enabled": neural_enabled,
                    "latency_ms": latency_ms,
                }
            )

        return MemoryAgentDecision(
            action=action,
            confidence=base_confidence,
            surprise=surprise,
            reasoning=reasoning,
            strategy=strategy,
            requires_critic=requires_critic,
            escalation_reason=escalation_reason,
            neural_memory_used=neural_enabled,
            latency_ms=latency_ms,
        )

    def _route_by_confidence(
        self,
        confidence: float,
        domain: str,
    ) -> tuple["RecommendedAction", str]:
        """Route to action based on confidence thresholds.

        Args:
            confidence: Confidence score (0-1)
            domain: Domain context for reasoning

        Returns:
            Tuple of (action, reasoning)
        """
        from .cognitive_memory_service import RecommendedAction

        if confidence >= self.THRESHOLD_AUTONOMOUS:
            return (
                RecommendedAction.PROCEED_AUTONOMOUS,
                f"High confidence ({confidence:.0%}) - neural memory recognizes "
                f"similar patterns in {domain} domain",
            )
        elif confidence >= self.THRESHOLD_LOGGING:
            return (
                RecommendedAction.PROCEED_WITH_LOGGING,
                f"Medium confidence ({confidence:.0%}) - proceeding with "
                f"enhanced logging for audit trail",
            )
        elif confidence >= self.THRESHOLD_REVIEW:
            return (
                RecommendedAction.REQUEST_REVIEW,
                f"Low-medium confidence ({confidence:.0%}) - requesting "
                f"review before proceeding",
            )
        else:
            return (
                RecommendedAction.ESCALATE_TO_HUMAN,
                f"Low confidence ({confidence:.0%}) - neural memory shows "
                f"high surprise (unfamiliar pattern), escalating to human",
            )

    def _should_engage_critic(
        self,
        confidence: float,
        task_description: str,
        domain: str,
    ) -> bool:
        """Determine if critic agent should be engaged.

        In DUAL/AUTO mode, the critic is engaged when:
        - Confidence is moderate (not too high, not too low)
        - Domain is high-risk (SECURITY, COMPLIANCE, PRODUCTION)
        - Task contains risk indicators

        Args:
            confidence: Current confidence score
            task_description: Task description
            domain: Domain context

        Returns:
            True if critic should be engaged
        """
        if self.mode == AgentMode.SINGLE:
            return False

        if self.mode == AgentMode.DUAL:
            # Always engage critic in DUAL mode
            return True

        # AUTO mode: engage based on risk indicators
        high_risk_domains = {"SECURITY", "COMPLIANCE", "PRODUCTION"}
        if domain.upper() in high_risk_domains:
            return True

        # Engage for moderate confidence (uncertain zone)
        if 0.50 <= confidence < 0.85:
            return True

        # Check for risk keywords in task
        risk_keywords = [
            "production",
            "critical",
            "security",
            "compliance",
            "migration",
            "rollback",
            "incident",
            "data",
        ]
        task_lower = task_description.lower()
        if any(kw in task_lower for kw in risk_keywords):
            return True

        return False

    def _get_escalation_reason(
        self,
        confidence: float,
        surprise: float,
        context: Dict[str, Any],
    ) -> str:
        """Generate explanation for escalation.

        Args:
            confidence: Confidence score
            surprise: Surprise score
            context: Full cognitive context

        Returns:
            Human-readable escalation reason
        """
        reasons = []

        if confidence < 0.30:
            reasons.append("Very low confidence")

        if surprise > 0.8:
            reasons.append("High surprise (unfamiliar pattern)")

        # Check for uncertainty sources from confidence estimate
        uncertainties = context.get("confidence", {})
        if hasattr(uncertainties, "uncertainties"):
            for u in uncertainties.uncertainties[:2]:
                reasons.append(f"Uncertainty: {u}")

        if not reasons:
            reasons.append("Confidence below threshold")

        return "; ".join(reasons)

    def _record_metric(self, metric: Dict[str, Any]) -> None:
        """Record metric for CloudWatch publishing."""
        import time

        metric["timestamp"] = time.time()
        self._metrics.append(metric)

        # Keep last 1000 metrics
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]

    def get_metrics(self) -> List[Dict[str, Any]]:
        """Get collected metrics for CloudWatch publishing."""
        return list(self._metrics)

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "decision_count": self._decision_count,
            "autonomous_count": self._autonomous_count,
            "escalation_count": self._escalation_count,
            "autonomous_rate": (
                self._autonomous_count / self._decision_count
                if self._decision_count > 0
                else 0.0
            ),
            "escalation_rate": (
                self._escalation_count / self._decision_count
                if self._decision_count > 0
                else 0.0
            ),
            "mode": self.mode.value,
            "metrics_enabled": self.enable_metrics,
        }


# =============================================================================
# CLOUDWATCH METRICS FOR NEURAL MEMORY
# =============================================================================


@dataclass
class NeuralMemoryMetricDatum:
    """Single metric data point for CloudWatch."""

    metric_name: str
    value: float
    unit: str = "Count"
    dimensions: Dict[str, str] = field(default_factory=dict)

    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        from datetime import datetime, timezone

        datum = {
            "MetricName": self.metric_name,
            "Value": self.value,
            "Unit": self.unit,
            "Timestamp": datetime.now(timezone.utc),
            "StorageResolution": 60,  # Standard resolution
        }
        if self.dimensions:
            datum["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in self.dimensions.items()
            ]
        return datum


class NeuralMemoryMetricsPublisher:
    """CloudWatch metrics publisher for neural memory operations.

    Publishes metrics to the Aura/NeuralMemory namespace:
    - SurpriseScore: Neural memory surprise scores
    - RetrievalLatency: Time to retrieve from neural memory
    - UpdateLatency: Time to update neural memory
    - TTTSteps: Test-time training steps performed
    - MemorizationDecisions: Count of memorization decisions
    - ConfidenceScore: Confidence scores from memory agent
    - EscalationCount: Number of escalations to human

    Usage:
        ```python
        publisher = NeuralMemoryMetricsPublisher(environment="dev")

        # Publish from TitanMemoryService metrics
        for metric in titan_service.get_metrics():
            publisher.publish_memory_metric(metric)

        # Publish from MemoryAgent metrics
        for metric in memory_agent.get_metrics():
            publisher.publish_agent_metric(metric)

        # Flush batch to CloudWatch
        await publisher.flush()
        ```
    """

    NAMESPACE = "Aura/NeuralMemory"
    MAX_BATCH_SIZE = 1000

    def __init__(
        self,
        environment: str = "dev",
        region: str = "us-east-1",
        mock_mode: bool = False,
    ):
        """Initialize metrics publisher.

        Args:
            environment: Environment name (dev, staging, prod)
            region: AWS region
            mock_mode: If True, don't make real AWS calls
        """
        self.environment = environment
        self.region = region
        self.mock_mode = mock_mode

        self._pending_metrics: List[NeuralMemoryMetricDatum] = []
        self._published_count = 0
        self._failed_count = 0

        # Initialize CloudWatch client if not in mock mode
        if not mock_mode:
            try:
                import boto3

                self._cloudwatch = boto3.client(
                    "cloudwatch",
                    region_name=region,
                )
            except Exception as e:
                logger.warning(f"Failed to create CloudWatch client: {e}")
                self._cloudwatch = None
        else:
            self._cloudwatch = None

    def publish_memory_metric(
        self,
        operation: str,
        latency_ms: float,
        surprise_score: Optional[float] = None,
        was_memorized: bool = False,
        ttt_steps: int = 0,
        memory_usage_mb: float = 0.0,
    ) -> None:
        """Publish a memory operation metric.

        Args:
            operation: Operation type (retrieve, update)
            latency_ms: Operation latency in milliseconds
            surprise_score: Neural surprise score (if available)
            was_memorized: Whether the input was memorized
            ttt_steps: Number of TTT steps performed
            memory_usage_mb: Current memory usage in MB
        """
        base_dimensions = {
            "Environment": self.environment,
            "Operation": operation,
        }

        # Latency metric
        self._pending_metrics.append(
            NeuralMemoryMetricDatum(
                metric_name=f"{operation.capitalize()}Latency",
                value=latency_ms,
                unit="Milliseconds",
                dimensions=base_dimensions,
            )
        )

        # Surprise score metric
        if surprise_score is not None:
            self._pending_metrics.append(
                NeuralMemoryMetricDatum(
                    metric_name="SurpriseScore",
                    value=surprise_score,
                    unit="None",
                    dimensions=base_dimensions,
                )
            )

        # Memorization decision metric
        if operation == "update":
            self._pending_metrics.append(
                NeuralMemoryMetricDatum(
                    metric_name="MemorizationDecisions",
                    value=1.0 if was_memorized else 0.0,
                    unit="Count",
                    dimensions=base_dimensions,
                )
            )

            # TTT steps metric
            if ttt_steps > 0:
                self._pending_metrics.append(
                    NeuralMemoryMetricDatum(
                        metric_name="TTTSteps",
                        value=float(ttt_steps),
                        unit="Count",
                        dimensions=base_dimensions,
                    )
                )

        # Memory usage metric
        if memory_usage_mb > 0:
            self._pending_metrics.append(
                NeuralMemoryMetricDatum(
                    metric_name="MemoryUsageMB",
                    value=memory_usage_mb,
                    unit="Megabytes",
                    dimensions={"Environment": self.environment},
                )
            )

    def publish_agent_metric(
        self,
        confidence: float,
        surprise: float,
        action: str,
        domain: str,
        latency_ms: float,
        neural_enabled: bool = True,
    ) -> None:
        """Publish a memory agent decision metric.

        Args:
            confidence: Confidence score (0-1)
            surprise: Surprise score
            action: Action taken (proceed_autonomous, escalate_to_human, etc.)
            domain: Domain context
            latency_ms: Decision latency in milliseconds
            neural_enabled: Whether neural memory was used
        """
        dimensions = {
            "Environment": self.environment,
            "Domain": domain,
            "Action": action,
        }

        # Confidence score
        self._pending_metrics.append(
            NeuralMemoryMetricDatum(
                metric_name="ConfidenceScore",
                value=confidence,
                unit="None",
                dimensions=dimensions,
            )
        )

        # Decision latency
        self._pending_metrics.append(
            NeuralMemoryMetricDatum(
                metric_name="DecisionLatency",
                value=latency_ms,
                unit="Milliseconds",
                dimensions=dimensions,
            )
        )

        # Action count (for tracking autonomous vs escalation rates)
        self._pending_metrics.append(
            NeuralMemoryMetricDatum(
                metric_name=f"{action.replace('_', ' ').title().replace(' ', '')}Count",
                value=1.0,
                unit="Count",
                dimensions={
                    "Environment": self.environment,
                    "Domain": domain,
                },
            )
        )

        # Neural memory usage
        self._pending_metrics.append(
            NeuralMemoryMetricDatum(
                metric_name="NeuralMemoryUsed",
                value=1.0 if neural_enabled else 0.0,
                unit="Count",
                dimensions={"Environment": self.environment},
            )
        )

    async def flush(self) -> Dict[str, int]:
        """Flush pending metrics to CloudWatch.

        Returns:
            Dictionary with published and failed counts
        """
        if not self._pending_metrics:
            return {"published": 0, "failed": 0}

        if self.mock_mode or self._cloudwatch is None:
            # Mock mode: just clear metrics
            count = len(self._pending_metrics)
            self._pending_metrics = []
            self._published_count += count
            logger.debug(f"Mock published {count} neural memory metrics")
            return {"published": count, "failed": 0}

        # Batch metrics (CloudWatch limit is 1000 per request)
        published = 0
        failed = 0

        for i in range(0, len(self._pending_metrics), self.MAX_BATCH_SIZE):
            batch = self._pending_metrics[i : i + self.MAX_BATCH_SIZE]

            try:
                metric_data = [m.to_cloudwatch_format() for m in batch]
                self._cloudwatch.put_metric_data(
                    Namespace=self.NAMESPACE,
                    MetricData=metric_data,
                )
                published += len(batch)
                logger.debug(f"Published {len(batch)} neural memory metrics")
            except Exception as e:
                failed += len(batch)
                logger.error(f"Failed to publish metrics batch: {e}")

        self._pending_metrics = []
        self._published_count += published
        self._failed_count += failed

        return {"published": published, "failed": failed}

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            "pending_metrics": len(self._pending_metrics),
            "published_count": self._published_count,
            "failed_count": self._failed_count,
            "namespace": self.NAMESPACE,
            "environment": self.environment,
            "mock_mode": self.mock_mode,
        }
