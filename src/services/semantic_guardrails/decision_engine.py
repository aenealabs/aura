"""
Project Aura - Semantic Guardrails Layer 6: Decision Engine & Audit

Aggregates results from all detection layers and produces final threat assessment
with recommended action and audit trail.
Target latency: P50 <5ms.

Decision Matrix:
- Any CRITICAL → BLOCK
- Multiple HIGH → BLOCK
- Cumulative session score > 2.5 → ESCALATE_HITL
- Single HIGH with low confidence → SANITIZE
- MEDIUM/LOW → ALLOW with monitoring

Security Rationale:
- Unified decision point prevents conflicting actions
- Full audit trail for security review and model improvement
- Conservative defaults (block on uncertainty in strict mode)

Author: Project Aura Team
Created: 2026-01-25
"""

import hashlib
import logging
import time
from typing import Optional

from .config import DecisionEngineConfig, get_guardrails_config
from .contracts import (
    EmbeddingMatchResult,
    IntentClassificationResult,
    LayerResult,
    NormalizationResult,
    PatternMatchResult,
    RecommendedAction,
    SessionThreatScore,
    ThreatAssessment,
    ThreatCategory,
    ThreatLevel,
)

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Layer 6: Decision Engine & Audit.

    Aggregates threat signals from all detection layers and produces
    a final ThreatAssessment with recommended action.

    Decision Logic:
    1. Check for CRITICAL threats → BLOCK
    2. Check for multiple HIGH threats → BLOCK
    3. Check session cumulative score → ESCALATE_HITL
    4. Check for uncertain classifications → ESCALATE_HITL (if enabled)
    5. Otherwise → ALLOW or SANITIZE based on threat level

    Usage:
        engine = DecisionEngine()
        assessment = engine.assess(
            input_text="User input",
            normalization_result=norm_result,
            pattern_result=pattern_result,
            embedding_result=embed_result,
            intent_result=intent_result,
            session_result=session_result,
        )
        if assessment.requires_intervention:
            handle_threat(assessment)

    Thread-safe: Yes (stateless)
    Target Latency: P50 <5ms
    """

    def __init__(
        self,
        config: Optional[DecisionEngineConfig] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize the decision engine.

        Args:
            config: Decision engine configuration (uses global config if None)
            strict_mode: If True, block on any suspicious activity
        """
        if config is None:
            global_config = get_guardrails_config()
            config = global_config.decision
        self.config = config
        self.strict_mode = strict_mode

        logger.info(
            f"DecisionEngine initialized "
            f"(strict_mode={strict_mode}, hitl_enabled={config.enable_hitl_escalation})"
        )

    def assess(
        self,
        input_text: str,
        normalization_result: Optional[NormalizationResult] = None,
        pattern_result: Optional[PatternMatchResult] = None,
        embedding_result: Optional[EmbeddingMatchResult] = None,
        intent_result: Optional[IntentClassificationResult] = None,
        session_result: Optional[SessionThreatScore] = None,
        session_id: Optional[str] = None,
    ) -> ThreatAssessment:
        """
        Assess threat level and determine recommended action.

        Args:
            input_text: Original input text (for hashing)
            normalization_result: Result from Layer 1
            pattern_result: Result from Layer 2
            embedding_result: Result from Layer 3
            intent_result: Result from Layer 4
            session_result: Result from Layer 5
            session_id: Optional session identifier

        Returns:
            ThreatAssessment with final decision
        """
        start_time = time.perf_counter()

        # Compute input hash for audit
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()

        # Collect layer results
        layer_results: list[LayerResult] = []
        all_categories: list[ThreatCategory] = []
        threat_levels: list[ThreatLevel] = []
        confidences: list[float] = []

        # Process Layer 1: Normalization
        if normalization_result:
            layer_results.append(
                LayerResult(
                    layer_name="normalization",
                    layer_number=1,
                    threat_level=ThreatLevel.SAFE,  # Normalization doesn't assess threats
                    processing_time_ms=normalization_result.processing_time_ms,
                    details={
                        "was_modified": normalization_result.was_modified,
                        "transformations": normalization_result.transformations_applied,
                    },
                )
            )

        # Process Layer 2: Pattern Matching
        if pattern_result:
            layer_results.append(
                LayerResult(
                    layer_name="pattern_matcher",
                    layer_number=2,
                    threat_level=pattern_result.threat_level,
                    threat_categories=pattern_result.threat_categories,
                    processing_time_ms=pattern_result.processing_time_ms,
                    details={
                        "patterns_detected": pattern_result.patterns_detected,
                        "blocklist_hit": pattern_result.blocklist_hit,
                    },
                )
            )
            threat_levels.append(pattern_result.threat_level)
            all_categories.extend(pattern_result.threat_categories)
            confidences.append(1.0)  # Pattern matches are deterministic

        # Process Layer 3: Embedding Detection
        if embedding_result:
            layer_results.append(
                LayerResult(
                    layer_name="embedding_detector",
                    layer_number=3,
                    threat_level=embedding_result.threat_level,
                    threat_categories=embedding_result.threat_categories,
                    confidence=embedding_result.max_similarity_score,
                    processing_time_ms=embedding_result.processing_time_ms,
                    details={
                        "max_similarity": embedding_result.max_similarity_score,
                        "matches_found": len(embedding_result.top_matches),
                    },
                )
            )
            if embedding_result.similar_threats_found:
                threat_levels.append(embedding_result.threat_level)
                all_categories.extend(embedding_result.threat_categories)
                confidences.append(embedding_result.max_similarity_score)

        # Process Layer 4: Intent Classification
        if intent_result:
            layer_results.append(
                LayerResult(
                    layer_name="intent_classifier",
                    layer_number=4,
                    threat_level=intent_result.threat_level,
                    threat_categories=intent_result.threat_categories,
                    confidence=intent_result.confidence,
                    processing_time_ms=intent_result.processing_time_ms,
                    details={
                        "classification": intent_result.classification,
                        "cached": intent_result.cached,
                        "model_used": intent_result.model_used,
                    },
                )
            )
            if not intent_result.is_legitimate:
                threat_levels.append(intent_result.threat_level)
                all_categories.extend(intent_result.threat_categories)
                confidences.append(intent_result.confidence)

        # Process Layer 5: Session Tracking
        if session_result:
            layer_results.append(
                LayerResult(
                    layer_name="session_tracker",
                    layer_number=5,
                    threat_level=session_result.threat_level,
                    processing_time_ms=session_result.processing_time_ms,
                    details={
                        "turn_number": session_result.turn_number,
                        "cumulative_score": session_result.cumulative_score,
                        "escalation_triggered": session_result.escalation_triggered,
                    },
                )
            )
            if session_result.needs_hitl_review:
                threat_levels.append(ThreatLevel.HIGH)
                all_categories.append(ThreatCategory.MULTI_TURN_ATTACK)

        # Determine overall threat level and action
        final_threat_level, recommended_action, primary_category, reasoning = (
            self._decide(
                threat_levels=threat_levels,
                categories=all_categories,
                confidences=confidences,
                pattern_result=pattern_result,
                session_result=session_result,
                intent_result=intent_result,
            )
        )

        # Calculate overall confidence
        overall_confidence = sum(confidences) / len(confidences) if confidences else 1.0

        # Deduplicate categories
        unique_categories = list(dict.fromkeys(all_categories))

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        assessment = ThreatAssessment(
            input_hash=input_hash,
            threat_level=final_threat_level,
            recommended_action=recommended_action,
            primary_category=primary_category,
            all_categories=unique_categories,
            confidence=overall_confidence,
            reasoning=reasoning,
            layer_results=layer_results,
            session_id=session_id
            or (session_result.session_id if session_result else None),
            total_processing_time_ms=self._calculate_total_time(layer_results)
            + processing_time_ms,
        )

        # Log assessment for audit
        self._log_assessment(assessment)

        return assessment

    def _decide(
        self,
        threat_levels: list[ThreatLevel],
        categories: list[ThreatCategory],
        confidences: list[float],
        pattern_result: Optional[PatternMatchResult],
        session_result: Optional[SessionThreatScore],
        intent_result: Optional[IntentClassificationResult],
    ) -> tuple[ThreatLevel, RecommendedAction, ThreatCategory, str]:
        """
        Make final decision based on aggregated signals.

        Returns:
            Tuple of (threat_level, action, primary_category, reasoning)
        """
        reasoning_parts = []

        # Rule 1: Any CRITICAL threat → BLOCK
        if ThreatLevel.CRITICAL in threat_levels:
            if self.config.block_on_critical:
                reasoning_parts.append("CRITICAL threat detected")
                primary_category = self._get_primary_category(
                    categories, ThreatLevel.CRITICAL
                )
                return (
                    ThreatLevel.CRITICAL,
                    RecommendedAction.BLOCK,
                    primary_category,
                    "; ".join(reasoning_parts),
                )

        # Rule 2: Blocklist hit → BLOCK
        if pattern_result and pattern_result.blocklist_hit:
            reasoning_parts.append("Blocklist match")
            return (
                ThreatLevel.CRITICAL,
                RecommendedAction.BLOCK,
                ThreatCategory.PROMPT_INJECTION,
                "Blocklist match",
            )

        # Rule 3: Multiple HIGH threats → BLOCK
        high_count = sum(1 for t in threat_levels if t == ThreatLevel.HIGH)
        if high_count >= self.config.multiple_high_count:
            if self.config.block_on_multiple_high:
                reasoning_parts.append(f"{high_count} HIGH threats detected")
                primary_category = self._get_primary_category(
                    categories, ThreatLevel.HIGH
                )
                return (
                    ThreatLevel.HIGH,
                    RecommendedAction.BLOCK,
                    primary_category,
                    "; ".join(reasoning_parts),
                )

        # Rule 4: Session cumulative score exceeds threshold → ESCALATE_HITL
        if session_result and session_result.needs_hitl_review:
            if self.config.enable_hitl_escalation:
                reasoning_parts.append(
                    f"Session cumulative score {session_result.cumulative_score:.2f} exceeds threshold"
                )
                return (
                    ThreatLevel.HIGH,
                    RecommendedAction.ESCALATE_HITL,
                    ThreatCategory.MULTI_TURN_ATTACK,
                    "; ".join(reasoning_parts),
                )

        # Rule 5: Uncertain classification → ESCALATE_HITL (if enabled)
        if intent_result and self.config.hitl_on_uncertain:
            if intent_result.confidence < self.config.uncertainty_threshold:
                reasoning_parts.append(
                    f"Low confidence classification ({intent_result.confidence:.2f})"
                )
                primary_category = categories[0] if categories else ThreatCategory.NONE
                return (
                    ThreatLevel.MEDIUM,
                    RecommendedAction.ESCALATE_HITL,
                    primary_category,
                    "; ".join(reasoning_parts),
                )

        # Rule 6: Strict mode with any threat → BLOCK
        if self.strict_mode and threat_levels:
            max_threat = max(threat_levels)
            if max_threat >= ThreatLevel.MEDIUM:
                reasoning_parts.append("Strict mode: blocking on medium+ threat")
                primary_category = categories[0] if categories else ThreatCategory.NONE
                return (
                    max_threat,
                    RecommendedAction.BLOCK,
                    primary_category,
                    "; ".join(reasoning_parts),
                )

        # Rule 7: Single HIGH threat → SANITIZE
        if ThreatLevel.HIGH in threat_levels:
            reasoning_parts.append("HIGH threat detected, sanitizing")
            primary_category = self._get_primary_category(categories, ThreatLevel.HIGH)
            return (
                ThreatLevel.HIGH,
                RecommendedAction.SANITIZE,
                primary_category,
                "; ".join(reasoning_parts),
            )

        # Rule 8: MEDIUM threat → SANITIZE
        if ThreatLevel.MEDIUM in threat_levels:
            reasoning_parts.append("MEDIUM threat detected, sanitizing")
            primary_category = self._get_primary_category(
                categories, ThreatLevel.MEDIUM
            )
            return (
                ThreatLevel.MEDIUM,
                RecommendedAction.SANITIZE,
                primary_category,
                "; ".join(reasoning_parts),
            )

        # Rule 9: LOW threat → ALLOW with monitoring
        if ThreatLevel.LOW in threat_levels:
            reasoning_parts.append("LOW threat detected, allowing with monitoring")
            primary_category = categories[0] if categories else ThreatCategory.NONE
            return (
                ThreatLevel.LOW,
                RecommendedAction.ALLOW,
                primary_category,
                "; ".join(reasoning_parts),
            )

        # Default: SAFE → ALLOW
        return (
            ThreatLevel.SAFE,
            RecommendedAction.ALLOW,
            ThreatCategory.NONE,
            "No threats detected",
        )

    def _get_primary_category(
        self,
        categories: list[ThreatCategory],
        threat_level: ThreatLevel,
    ) -> ThreatCategory:
        """Get primary threat category for a given threat level."""
        # Priority order for categories
        priority = [
            ThreatCategory.PROMPT_INJECTION,
            ThreatCategory.JAILBREAK,
            ThreatCategory.DELIMITER_INJECTION,
            ThreatCategory.ROLE_CONFUSION,
            ThreatCategory.DATA_EXFILTRATION,
            ThreatCategory.MULTI_TURN_ATTACK,
            ThreatCategory.CONTEXT_POISONING,
            ThreatCategory.ENCODING_BYPASS,
        ]

        for cat in priority:
            if cat in categories:
                return cat

        return categories[0] if categories else ThreatCategory.NONE

    def _calculate_total_time(self, layer_results: list[LayerResult]) -> float:
        """Calculate total processing time from all layers."""
        return sum(r.processing_time_ms for r in layer_results)

    def _log_assessment(self, assessment: ThreatAssessment) -> None:
        """Log assessment for audit trail."""
        if not self.config.enable_audit_logging:
            return

        # Only log threats (unless configured to log all)
        if (
            assessment.threat_level == ThreatLevel.SAFE
            and not self.config.log_safe_assessments
        ):
            return

        log_level = (
            logging.WARNING if assessment.requires_intervention else logging.INFO
        )
        logger.log(
            log_level,
            f"ThreatAssessment: level={assessment.threat_level.name}, "
            f"action={assessment.recommended_action.value}, "
            f"category={assessment.primary_category.value}, "
            f"confidence={assessment.confidence:.2f}, "
            f"time_ms={assessment.total_processing_time_ms:.2f}",
        )


# =============================================================================
# Module-level convenience functions
# =============================================================================

_engine_instance: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get singleton DecisionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DecisionEngine()
    return _engine_instance


def assess_threat(
    input_text: str,
    pattern_result: Optional[PatternMatchResult] = None,
    embedding_result: Optional[EmbeddingMatchResult] = None,
    intent_result: Optional[IntentClassificationResult] = None,
    session_result: Optional[SessionThreatScore] = None,
) -> ThreatAssessment:
    """
    Convenience function to assess threat.

    Args:
        input_text: Input text to assess
        pattern_result: Optional pattern matching result
        embedding_result: Optional embedding detection result
        intent_result: Optional intent classification result
        session_result: Optional session tracking result

    Returns:
        ThreatAssessment with final decision
    """
    return get_decision_engine().assess(
        input_text=input_text,
        pattern_result=pattern_result,
        embedding_result=embedding_result,
        intent_result=intent_result,
        session_result=session_result,
    )


def reset_decision_engine() -> None:
    """Reset decision engine singleton (for testing)."""
    global _engine_instance
    _engine_instance = None
