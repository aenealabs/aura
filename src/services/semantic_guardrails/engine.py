"""
Project Aura - Semantic Guardrails Engine

Main orchestrator that coordinates all 6 detection layers to produce
a final threat assessment with recommended action.

Architecture:
- L1: Normalize input (5ms) - Sequential, always runs
- L2: Pattern check (10ms) - Sequential, fast exit on CRITICAL
- L3+L4: Embedding + Intent (max 150ms) - Parallel execution
- L5: Session tracking (20ms) - Sequential, updates cumulative score
- L6: Decision engine (5ms) - Sequential, final assessment

Performance Targets:
- P50 <150ms, P95 <300ms, P99 <500ms
- >95% detection rate on novel attack variants
- <1% false positive rate

Security Rationale:
- Layered defense catches different attack types
- Fast-path exit prevents resource waste on obvious attacks
- Session tracking catches gradual escalation
- Full audit trail for security review

Author: Project Aura Team
Created: 2026-01-25
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from .config import GuardrailsConfig, get_guardrails_config
from .contracts import (
    EmbeddingMatchResult,
    IntentClassificationResult,
    PatternMatchResult,
    SessionThreatScore,
    ThreatAssessment,
    ThreatLevel,
)
from .decision_engine import DecisionEngine
from .embedding_detector import EmbeddingDetector
from .intent_classifier import IntentClassifier
from .metrics import GuardrailsMetricsPublisher
from .multi_turn_tracker import MultiTurnTracker
from .normalizer import TextNormalizer
from .pattern_matcher import PatternMatcher

logger = logging.getLogger(__name__)


class SemanticGuardrailsEngine:
    """
    Main orchestrator for the 6-layer semantic guardrails system.

    Coordinates all detection layers and produces a final threat assessment
    with recommended action (ALLOW, SANITIZE, BLOCK, ESCALATE_HITL).

    Layer Pipeline:
    1. Normalization (5ms) - Canonical form, homograph mapping
    2. Pattern Matching (10ms) - Regex patterns, blocklist
    3. Embedding Detection (50ms) - k-NN similarity search
    4. Intent Classification (150ms) - LLM-as-judge
    5. Session Tracking (20ms) - Multi-turn cumulative scoring
    6. Decision Engine (5ms) - Final aggregation and audit

    Usage:
        engine = SemanticGuardrailsEngine()

        # Synchronous assessment
        assessment = engine.assess_threat(
            input_text="User input to check",
            session_id="session-123",
        )

        if assessment.requires_intervention:
            if assessment.recommended_action == RecommendedAction.BLOCK:
                block_request()
            elif assessment.recommended_action == RecommendedAction.ESCALATE_HITL:
                escalate_to_human(assessment)

        # Async assessment (recommended for high throughput)
        assessment = await engine.assess_threat_async(input_text, session_id)

    Thread-safe: Yes (all components are thread-safe)
    """

    def __init__(
        self,
        config: Optional[GuardrailsConfig] = None,
        normalizer: Optional[TextNormalizer] = None,
        pattern_matcher: Optional[PatternMatcher] = None,
        embedding_detector: Optional[EmbeddingDetector] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        session_tracker: Optional[MultiTurnTracker] = None,
        decision_engine: Optional[DecisionEngine] = None,
        metrics_publisher: Optional[GuardrailsMetricsPublisher] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize the semantic guardrails engine.

        Args:
            config: Global configuration (uses defaults if None)
            normalizer: Layer 1 normalizer (creates new if None)
            pattern_matcher: Layer 2 pattern matcher (creates new if None)
            embedding_detector: Layer 3 embedding detector (creates new if None)
            intent_classifier: Layer 4 intent classifier (creates new if None)
            session_tracker: Layer 5 session tracker (creates new if None)
            decision_engine: Layer 6 decision engine (creates new if None)
            metrics_publisher: Metrics publisher (creates new if None)
            strict_mode: If True, block on any suspicious activity
        """
        self.config = config or get_guardrails_config()
        self.strict_mode = strict_mode

        # Initialize layers (use provided or create new)
        self._normalizer = normalizer or TextNormalizer(
            config=self.config.normalization
        )
        self._pattern_matcher = pattern_matcher or PatternMatcher(
            config=self.config.pattern_match
        )
        self._embedding_detector = embedding_detector or EmbeddingDetector(
            config=self.config.embedding
        )
        self._intent_classifier = intent_classifier or IntentClassifier(
            config=self.config.intent
        )
        self._session_tracker = session_tracker or MultiTurnTracker(
            config=self.config.session
        )
        self._decision_engine = decision_engine or DecisionEngine(
            config=self.config.decision,
            strict_mode=strict_mode,
        )
        self._metrics = metrics_publisher or GuardrailsMetricsPublisher(
            config=self.config.metrics
        )

        # Thread pool for parallel layer execution
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="guardrails"
        )

        logger.info(
            f"SemanticGuardrailsEngine initialized "
            f"(strict_mode={strict_mode}, layers=6)"
        )

    def assess_threat(
        self,
        input_text: str,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        skip_embedding: bool = False,
        skip_intent: bool = False,
        skip_session: bool = False,
    ) -> ThreatAssessment:
        """
        Assess threat level of input text (synchronous).

        Args:
            input_text: Text to assess for threats
            context: Optional context (metadata, user info, etc.)
            session_id: Session identifier for multi-turn tracking
            skip_embedding: Skip Layer 3 embedding detection
            skip_intent: Skip Layer 4 intent classification
            skip_session: Skip Layer 5 session tracking

        Returns:
            ThreatAssessment with final decision and layer results
        """
        start_time = time.perf_counter()

        # Layer 1: Normalization (5ms target)
        normalization_result = self._normalizer.normalize(input_text)
        normalized_text = normalization_result.normalized_text

        # Layer 2: Pattern Matching (10ms target)
        pattern_result = self._pattern_matcher.match(normalized_text)

        # Fast exit on CRITICAL pattern match
        if pattern_result.should_fast_exit:
            logger.warning(
                f"Fast exit triggered: {pattern_result.threat_level.name} threat detected"
            )
            # Still record session turn for multi-turn tracking even on fast exit
            fast_exit_session_result: Optional[SessionThreatScore] = None
            if not skip_session and session_id:
                turn_score = self._calculate_turn_score(
                    pattern_result=pattern_result,
                    embedding_result=None,
                    intent_result=None,
                )
                fast_exit_session_result = self._session_tracker.record_turn(
                    session_id=session_id,
                    turn_score=turn_score,
                    threat_level=pattern_result.threat_level,
                    metadata=context,
                )
            assessment = self._decision_engine.assess(
                input_text=input_text,
                normalization_result=normalization_result,
                pattern_result=pattern_result,
                session_result=fast_exit_session_result,
                session_id=session_id,
            )
            self._metrics.record_assessment(assessment)
            return assessment

        # Layers 3+4: Parallel execution (max 150ms target)
        embedding_result: Optional[EmbeddingMatchResult] = None
        intent_result: Optional[IntentClassificationResult] = None

        if not skip_embedding and not skip_intent:
            # Run both in parallel
            embedding_future = self._executor.submit(
                self._embedding_detector.detect, normalized_text
            )
            intent_future = self._executor.submit(
                self._intent_classifier.classify, normalized_text
            )

            embedding_result = embedding_future.result()
            intent_result = intent_future.result()
        elif not skip_embedding:
            embedding_result = self._embedding_detector.detect(normalized_text)
        elif not skip_intent:
            intent_result = self._intent_classifier.classify(normalized_text)

        # Layer 5: Session Tracking (20ms target)
        session_result: Optional[SessionThreatScore] = None
        if not skip_session and session_id:
            # Calculate turn score from pattern and embedding results
            turn_score = self._calculate_turn_score(
                pattern_result=pattern_result,
                embedding_result=embedding_result,
                intent_result=intent_result,
            )
            turn_threat_level = self._get_max_threat_level(
                pattern_result, embedding_result, intent_result
            )

            session_result = self._session_tracker.record_turn(
                session_id=session_id,
                turn_score=turn_score,
                threat_level=turn_threat_level,
                metadata=context,
            )

            # Record escalation metric if triggered
            if session_result.escalation_triggered:
                self._metrics.record_session_escalation(
                    session_id=session_id,
                    cumulative_score=session_result.cumulative_score,
                )

        # Layer 6: Decision Engine (5ms target)
        assessment = self._decision_engine.assess(
            input_text=input_text,
            normalization_result=normalization_result,
            pattern_result=pattern_result,
            embedding_result=embedding_result,
            intent_result=intent_result,
            session_result=session_result,
            session_id=session_id,
        )

        # Record metrics
        self._metrics.record_assessment(assessment)

        # Record corpus match metric
        if embedding_result:
            self._metrics.record_corpus_match(
                matched=embedding_result.similar_threats_found,
                similarity_score=embedding_result.max_similarity_score,
            )

        total_time_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"Threat assessment complete: {assessment.threat_level.name} "
            f"({assessment.recommended_action.value}) in {total_time_ms:.2f}ms"
        )

        return assessment

    async def assess_threat_async(
        self,
        input_text: str,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        skip_embedding: bool = False,
        skip_intent: bool = False,
        skip_session: bool = False,
    ) -> ThreatAssessment:
        """
        Assess threat level of input text (asynchronous).

        This is the recommended method for high-throughput scenarios.
        Uses asyncio for concurrent layer execution.

        Args:
            input_text: Text to assess for threats
            context: Optional context (metadata, user info, etc.)
            session_id: Session identifier for multi-turn tracking
            skip_embedding: Skip Layer 3 embedding detection
            skip_intent: Skip Layer 4 intent classification
            skip_session: Skip Layer 5 session tracking

        Returns:
            ThreatAssessment with final decision and layer results
        """
        loop = asyncio.get_event_loop()

        start_time = time.perf_counter()

        # Layer 1: Normalization (5ms target)
        normalization_result = await loop.run_in_executor(
            self._executor, self._normalizer.normalize, input_text
        )
        normalized_text = normalization_result.normalized_text

        # Layer 2: Pattern Matching (10ms target)
        pattern_result = await loop.run_in_executor(
            self._executor, self._pattern_matcher.match, normalized_text
        )

        # Fast exit on CRITICAL pattern match
        if pattern_result.should_fast_exit:
            logger.warning(
                f"Fast exit triggered: {pattern_result.threat_level.name} threat detected"
            )
            # Still record session turn for multi-turn tracking even on fast exit
            fast_exit_session_result: Optional[SessionThreatScore] = None
            if not skip_session and session_id:
                turn_score = self._calculate_turn_score(
                    pattern_result=pattern_result,
                    embedding_result=None,
                    intent_result=None,
                )
                fast_exit_session_result = await loop.run_in_executor(
                    self._executor,
                    lambda: self._session_tracker.record_turn(
                        session_id=session_id,
                        turn_score=turn_score,
                        threat_level=pattern_result.threat_level,
                        metadata=context,
                    ),
                )
            assessment = self._decision_engine.assess(
                input_text=input_text,
                normalization_result=normalization_result,
                pattern_result=pattern_result,
                session_result=fast_exit_session_result,
                session_id=session_id,
            )
            self._metrics.record_assessment(assessment)
            return assessment

        # Layers 3+4: Parallel execution (max 150ms target)
        embedding_result: Optional[EmbeddingMatchResult] = None
        intent_result: Optional[IntentClassificationResult] = None

        tasks = []
        if not skip_embedding:
            tasks.append(
                loop.run_in_executor(
                    self._executor, self._embedding_detector.detect, normalized_text
                )
            )
        if not skip_intent:
            tasks.append(
                loop.run_in_executor(
                    self._executor, self._intent_classifier.classify, normalized_text
                )
            )

        if tasks:
            results = await asyncio.gather(*tasks)
            result_idx = 0
            if not skip_embedding:
                embedding_result = results[result_idx]
                result_idx += 1
            if not skip_intent:
                intent_result = results[result_idx]

        # Layer 5: Session Tracking (20ms target)
        session_result: Optional[SessionThreatScore] = None
        if not skip_session and session_id:
            turn_score = self._calculate_turn_score(
                pattern_result=pattern_result,
                embedding_result=embedding_result,
                intent_result=intent_result,
            )
            turn_threat_level = self._get_max_threat_level(
                pattern_result, embedding_result, intent_result
            )

            session_result = await loop.run_in_executor(
                self._executor,
                lambda: self._session_tracker.record_turn(
                    session_id=session_id,
                    turn_score=turn_score,
                    threat_level=turn_threat_level,
                    metadata=context,
                ),
            )

            if session_result.escalation_triggered:
                self._metrics.record_session_escalation(
                    session_id=session_id,
                    cumulative_score=session_result.cumulative_score,
                )

        # Layer 6: Decision Engine (5ms target)
        assessment = self._decision_engine.assess(
            input_text=input_text,
            normalization_result=normalization_result,
            pattern_result=pattern_result,
            embedding_result=embedding_result,
            intent_result=intent_result,
            session_result=session_result,
            session_id=session_id,
        )

        # Record metrics
        self._metrics.record_assessment(assessment)

        if embedding_result:
            self._metrics.record_corpus_match(
                matched=embedding_result.similar_threats_found,
                similarity_score=embedding_result.max_similarity_score,
            )

        total_time_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"Async threat assessment complete: {assessment.threat_level.name} "
            f"({assessment.recommended_action.value}) in {total_time_ms:.2f}ms"
        )

        return assessment

    def assess_fast_path(self, input_text: str) -> ThreatAssessment:
        """
        Fast-path assessment using only L1-L2 (Normalization + Pattern).

        Use this for high-volume, latency-sensitive scenarios where
        only obvious attacks need to be caught quickly.

        Target latency: <15ms

        Args:
            input_text: Text to assess

        Returns:
            ThreatAssessment from fast-path layers only
        """
        # L1: Normalize
        normalization_result = self._normalizer.normalize(input_text)

        # L2: Pattern match
        pattern_result = self._pattern_matcher.match(
            normalization_result.normalized_text
        )

        # L6: Decision (fast path only)
        assessment = self._decision_engine.assess(
            input_text=input_text,
            normalization_result=normalization_result,
            pattern_result=pattern_result,
        )

        self._metrics.record_assessment(assessment)
        return assessment

    def _calculate_turn_score(
        self,
        pattern_result: Optional[PatternMatchResult],
        embedding_result: Optional[EmbeddingMatchResult],
        intent_result: Optional[IntentClassificationResult],
    ) -> float:
        """
        Calculate a single turn threat score for session tracking.

        Returns a value between 0.0 (safe) and 1.0 (critical threat).
        """
        scores = []

        # Pattern result contributes based on threat level
        if pattern_result:
            level_scores = {
                ThreatLevel.SAFE: 0.0,
                ThreatLevel.LOW: 0.2,
                ThreatLevel.MEDIUM: 0.4,
                ThreatLevel.HIGH: 0.7,
                ThreatLevel.CRITICAL: 1.0,
            }
            scores.append(level_scores.get(pattern_result.threat_level, 0.0))

        # Embedding result contributes based on similarity score
        if embedding_result and embedding_result.similar_threats_found:
            scores.append(embedding_result.max_similarity_score)

        # Intent result contributes based on threat level and confidence
        if intent_result and not intent_result.is_legitimate:
            level_scores = {
                ThreatLevel.SAFE: 0.0,
                ThreatLevel.LOW: 0.2,
                ThreatLevel.MEDIUM: 0.4,
                ThreatLevel.HIGH: 0.7,
                ThreatLevel.CRITICAL: 1.0,
            }
            base_score = level_scores.get(intent_result.threat_level, 0.0)
            # Weight by confidence
            scores.append(base_score * intent_result.confidence)

        if not scores:
            return 0.0

        # Return max score (most threatening signal)
        return max(scores)

    def _get_max_threat_level(
        self,
        pattern_result: Optional[PatternMatchResult],
        embedding_result: Optional[EmbeddingMatchResult],
        intent_result: Optional[IntentClassificationResult],
    ) -> ThreatLevel:
        """Get the maximum threat level from all layer results."""
        levels = [ThreatLevel.SAFE]

        if pattern_result:
            levels.append(pattern_result.threat_level)
        if embedding_result:
            levels.append(embedding_result.threat_level)
        if intent_result:
            levels.append(intent_result.threat_level)

        return max(levels)

    def get_session_score(self, session_id: str) -> Optional[SessionThreatScore]:
        """
        Get current session threat score without recording a turn.

        Args:
            session_id: Session identifier

        Returns:
            SessionThreatScore or None if session not found
        """
        return self._session_tracker.get_session_score(session_id)

    def reset_session(self, session_id: str) -> bool:
        """
        Reset a session's threat tracking.

        Args:
            session_id: Session identifier

        Returns:
            True if session was reset, False if not found
        """
        return self._session_tracker.reset_session(session_id)

    def create_session_id(self) -> str:
        """Generate a new unique session ID."""
        return self._session_tracker.create_session_id()

    def flush_metrics(self) -> int:
        """
        Flush buffered metrics to CloudWatch.

        Returns:
            Number of metrics flushed
        """
        return self._metrics.flush()

    def get_metrics_stats(self) -> dict[str, Any]:
        """Get metrics publisher statistics."""
        return {
            "buffer_size": self._metrics.get_buffer_size(),
            "buffer_age_seconds": self._metrics.get_buffer_age_seconds(),
        }

    def shutdown(self) -> None:
        """Shutdown the engine and release resources."""
        self._executor.shutdown(wait=True)
        self._metrics.flush()
        logger.info("SemanticGuardrailsEngine shutdown complete")


# =============================================================================
# Module-level convenience functions
# =============================================================================

_engine_instance: Optional[SemanticGuardrailsEngine] = None


def get_guardrails_engine() -> SemanticGuardrailsEngine:
    """Get singleton SemanticGuardrailsEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SemanticGuardrailsEngine()
    return _engine_instance


def assess_threat(
    input_text: str,
    session_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> ThreatAssessment:
    """
    Convenience function to assess threat.

    Args:
        input_text: Text to assess
        session_id: Optional session identifier
        context: Optional context metadata

    Returns:
        ThreatAssessment with final decision
    """
    return get_guardrails_engine().assess_threat(
        input_text=input_text,
        session_id=session_id,
        context=context,
    )


async def assess_threat_async(
    input_text: str,
    session_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> ThreatAssessment:
    """
    Async convenience function to assess threat.

    Args:
        input_text: Text to assess
        session_id: Optional session identifier
        context: Optional context metadata

    Returns:
        ThreatAssessment with final decision
    """
    return await get_guardrails_engine().assess_threat_async(
        input_text=input_text,
        session_id=session_id,
        context=context,
    )


def reset_guardrails_engine() -> None:
    """Reset guardrails engine singleton (for testing)."""
    global _engine_instance
    if _engine_instance:
        _engine_instance.shutdown()
    _engine_instance = None
