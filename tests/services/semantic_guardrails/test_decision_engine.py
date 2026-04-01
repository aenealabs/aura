"""
Unit tests for Semantic Guardrails Layer 6: Decision Engine.

Tests cover:
- Decision matrix rules
- Threat level aggregation
- Recommended action determination
- HITL escalation logic
- Audit logging
- All decision paths

Author: Project Aura Team
Created: 2026-01-25
"""

import pytest

from src.services.semantic_guardrails.config import DecisionEngineConfig
from src.services.semantic_guardrails.contracts import (
    EmbeddingMatchResult,
    IntentClassificationResult,
    NormalizationResult,
    PatternMatchResult,
    RecommendedAction,
    SessionThreatScore,
    ThreatCategory,
    ThreatLevel,
)
from src.services.semantic_guardrails.decision_engine import (
    DecisionEngine,
    assess_threat,
    get_decision_engine,
    reset_decision_engine,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_decision_engine()
    yield
    reset_decision_engine()


def create_pattern_result(
    threat_level: ThreatLevel = ThreatLevel.SAFE,
    categories: list[ThreatCategory] = None,
    blocklist_hit: bool = False,
) -> PatternMatchResult:
    """Helper to create PatternMatchResult."""
    matched = threat_level != ThreatLevel.SAFE or bool(categories) or blocklist_hit
    return PatternMatchResult(
        matched=matched,
        threat_level=threat_level,
        patterns_detected=["test_pattern"] if matched else [],
        threat_categories=categories or [],
        blocklist_hit=blocklist_hit,
        processing_time_ms=5.0,
    )


def create_embedding_result(
    threat_level: ThreatLevel = ThreatLevel.SAFE,
    categories: list[ThreatCategory] = None,
    similarity: float = 0.0,
    found: bool = False,
) -> EmbeddingMatchResult:
    """Helper to create EmbeddingMatchResult."""
    return EmbeddingMatchResult(
        similar_threats_found=found,
        max_similarity_score=similarity,
        top_matches=[],
        threat_level=threat_level,
        threat_categories=categories or [],
        corpus_version="test-v1",
        processing_time_ms=30.0,
    )


def create_intent_result(
    classification: str = "A) LEGITIMATE",
    confidence: float = 0.9,
    threat_level: ThreatLevel = ThreatLevel.SAFE,
    categories: list[ThreatCategory] = None,
) -> IntentClassificationResult:
    """Helper to create IntentClassificationResult."""
    return IntentClassificationResult(
        classification=classification,
        confidence=confidence,
        reasoning="Test reasoning",
        threat_level=threat_level,
        threat_categories=categories or [],
        model_used="test",
        cached=False,
        processing_time_ms=100.0,
    )


def create_session_result(
    cumulative_score: float = 0.0,
    needs_hitl: bool = False,
    escalation_triggered: bool = False,
) -> SessionThreatScore:
    """Helper to create SessionThreatScore."""
    # needs_hitl_review is a property that checks cumulative_score > hitl_threshold (2.5)
    # So if needs_hitl=True, we set cumulative_score to 3.0 to trigger it
    actual_score = 3.0 if needs_hitl and cumulative_score == 0.0 else cumulative_score
    return SessionThreatScore(
        session_id="test-session",
        turn_number=1,
        current_turn_score=0.5,
        cumulative_score=actual_score,
        escalation_triggered=escalation_triggered or needs_hitl,
        turn_history=[0.5],
        threat_level=ThreatLevel.HIGH if needs_hitl else ThreatLevel.SAFE,
        processing_time_ms=10.0,
    )


class TestDecisionEngineBasics:
    """Basic functionality tests."""

    def test_creation(self):
        """Test decision engine creates successfully."""
        engine = DecisionEngine()
        assert engine is not None

    def test_creation_with_strict_mode(self):
        """Test creation with strict mode enabled."""
        engine = DecisionEngine(strict_mode=True)
        assert engine.strict_mode is True

    def test_assess_empty_input(self):
        """Test assessing empty input."""
        engine = DecisionEngine()
        assessment = engine.assess(input_text="")
        assert assessment.threat_level == ThreatLevel.SAFE
        assert assessment.recommended_action == RecommendedAction.ALLOW

    def test_input_hash_generated(self):
        """Test input hash is generated."""
        engine = DecisionEngine()
        assessment = engine.assess(input_text="Test input")
        assert assessment.input_hash is not None
        assert len(assessment.input_hash) == 64  # SHA-256 hex length

    def test_processing_time_calculated(self):
        """Test total processing time is calculated."""
        engine = DecisionEngine()
        assessment = engine.assess(input_text="Test input")
        assert assessment.total_processing_time_ms >= 0.0


class TestDecisionRules:
    """Tests for decision matrix rules."""

    def test_rule_critical_blocks(self):
        """Rule 1: Any CRITICAL threat → BLOCK."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.CRITICAL,
            categories=[ThreatCategory.PROMPT_INJECTION],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.threat_level == ThreatLevel.CRITICAL
        assert assessment.recommended_action == RecommendedAction.BLOCK

    def test_rule_blocklist_blocks(self):
        """Rule 2: Blocklist hit → BLOCK."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            blocklist_hit=True,
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.threat_level == ThreatLevel.CRITICAL
        assert assessment.recommended_action == RecommendedAction.BLOCK

    def test_rule_multiple_high_blocks(self):
        """Rule 3: Multiple HIGH threats → BLOCK."""
        engine = DecisionEngine()

        # Pattern with HIGH
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.JAILBREAK],
        )
        # Embedding with HIGH
        embedding_result = create_embedding_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.PROMPT_INJECTION],
            found=True,
            similarity=0.9,
        )

        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
            embedding_result=embedding_result,
        )
        assert assessment.recommended_action == RecommendedAction.BLOCK

    def test_rule_session_escalation(self):
        """Rule 4: Session cumulative score exceeds threshold → ESCALATE_HITL."""
        engine = DecisionEngine()
        session_result = create_session_result(
            cumulative_score=3.0,
            needs_hitl=True,
            escalation_triggered=True,
        )
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        assert assessment.recommended_action == RecommendedAction.ESCALATE_HITL

    def test_rule_uncertain_classification(self):
        """Rule 5: Uncertain classification → ESCALATE_HITL (if enabled)."""
        config = DecisionEngineConfig(
            hitl_on_uncertain=True,
            uncertainty_threshold=0.7,
        )
        engine = DecisionEngine(config=config)

        intent_result = create_intent_result(
            classification="B) OVERRIDE_ATTEMPT",
            confidence=0.5,  # Below threshold
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.PROMPT_INJECTION],
        )
        assessment = engine.assess(
            input_text="Test",
            intent_result=intent_result,
        )
        assert assessment.recommended_action == RecommendedAction.ESCALATE_HITL

    def test_rule_strict_mode_blocks(self):
        """Rule 6: Strict mode with any threat → BLOCK."""
        engine = DecisionEngine(strict_mode=True)
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.MEDIUM,
            categories=[ThreatCategory.JAILBREAK],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.recommended_action == RecommendedAction.BLOCK

    def test_rule_single_high_sanitizes(self):
        """Rule 7: Single HIGH threat → SANITIZE."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.JAILBREAK],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.recommended_action == RecommendedAction.SANITIZE

    def test_rule_medium_sanitizes(self):
        """Rule 8: MEDIUM threat → SANITIZE."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.MEDIUM,
            categories=[ThreatCategory.ENCODING_BYPASS],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.recommended_action == RecommendedAction.SANITIZE

    def test_rule_low_allows(self):
        """Rule 9: LOW threat → ALLOW."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.LOW,
            categories=[ThreatCategory.CONTEXT_POISONING],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.recommended_action == RecommendedAction.ALLOW

    def test_rule_safe_allows(self):
        """Default: SAFE → ALLOW."""
        engine = DecisionEngine()
        assessment = engine.assess(input_text="Hello world")
        assert assessment.threat_level == ThreatLevel.SAFE
        assert assessment.recommended_action == RecommendedAction.ALLOW


class TestThreatLevelAggregation:
    """Tests for threat level aggregation."""

    def test_max_threat_level_selected(self):
        """Test highest threat level is selected."""
        engine = DecisionEngine()

        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.LOW,
        )
        embedding_result = create_embedding_result(
            threat_level=ThreatLevel.HIGH,
            found=True,
            similarity=0.9,
        )
        intent_result = create_intent_result(
            classification="B) OVERRIDE_ATTEMPT",
            threat_level=ThreatLevel.MEDIUM,
        )

        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
            embedding_result=embedding_result,
            intent_result=intent_result,
        )
        # HIGH is the max
        assert assessment.threat_level == ThreatLevel.HIGH

    def test_categories_deduplicated(self):
        """Test threat categories are deduplicated."""
        engine = DecisionEngine()

        # Both have JAILBREAK category
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.JAILBREAK, ThreatCategory.PROMPT_INJECTION],
        )
        embedding_result = create_embedding_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.JAILBREAK],
            found=True,
            similarity=0.9,
        )

        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
            embedding_result=embedding_result,
        )
        # Should not have duplicate JAILBREAK
        assert assessment.all_categories.count(ThreatCategory.JAILBREAK) == 1


class TestPrimaryCategorySelection:
    """Tests for primary category selection."""

    def test_prompt_injection_priority(self):
        """Test PROMPT_INJECTION has highest priority."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[
                ThreatCategory.ROLE_CONFUSION,
                ThreatCategory.PROMPT_INJECTION,
                ThreatCategory.JAILBREAK,
            ],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.primary_category == ThreatCategory.PROMPT_INJECTION

    def test_jailbreak_priority(self):
        """Test JAILBREAK has second priority."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[
                ThreatCategory.ROLE_CONFUSION,
                ThreatCategory.JAILBREAK,
                ThreatCategory.DATA_EXFILTRATION,
            ],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.primary_category == ThreatCategory.JAILBREAK


class TestLayerResults:
    """Tests for layer result collection."""

    def test_normalization_result_included(self):
        """Test normalization result is included."""
        engine = DecisionEngine()
        norm_result = NormalizationResult(
            original_text="Test",
            normalized_text="test",
            transformations_applied=["lowercase"],
            processing_time_ms=2.0,
        )
        assessment = engine.assess(
            input_text="Test",
            normalization_result=norm_result,
        )
        layer_names = [r.layer_name for r in assessment.layer_results]
        assert "normalization" in layer_names

    def test_pattern_result_included(self):
        """Test pattern result is included."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(threat_level=ThreatLevel.LOW)
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        layer_names = [r.layer_name for r in assessment.layer_results]
        assert "pattern_matcher" in layer_names

    def test_embedding_result_included(self):
        """Test embedding result is included."""
        engine = DecisionEngine()
        embedding_result = create_embedding_result(found=False)
        assessment = engine.assess(
            input_text="Test",
            embedding_result=embedding_result,
        )
        layer_names = [r.layer_name for r in assessment.layer_results]
        assert "embedding_detector" in layer_names

    def test_intent_result_included(self):
        """Test intent result is included."""
        engine = DecisionEngine()
        intent_result = create_intent_result()
        assessment = engine.assess(
            input_text="Test",
            intent_result=intent_result,
        )
        layer_names = [r.layer_name for r in assessment.layer_results]
        assert "intent_classifier" in layer_names

    def test_session_result_included(self):
        """Test session result is included."""
        engine = DecisionEngine()
        session_result = create_session_result()
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        layer_names = [r.layer_name for r in assessment.layer_results]
        assert "session_tracker" in layer_names


class TestConfidenceCalculation:
    """Tests for confidence calculation."""

    def test_confidence_averaged(self):
        """Test confidence is averaged from layers."""
        engine = DecisionEngine()

        embedding_result = create_embedding_result(
            threat_level=ThreatLevel.HIGH,
            found=True,
            similarity=0.9,  # Confidence from embedding
        )
        intent_result = create_intent_result(
            classification="B) OVERRIDE_ATTEMPT",
            confidence=0.8,  # Confidence from intent
            threat_level=ThreatLevel.HIGH,
        )

        assessment = engine.assess(
            input_text="Test",
            embedding_result=embedding_result,
            intent_result=intent_result,
        )
        # Average of 0.9, 0.8 = 0.85
        assert abs(assessment.confidence - 0.85) < 0.01

    def test_pattern_confidence_is_one(self):
        """Test pattern matches contribute 1.0 confidence."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
            categories=[ThreatCategory.JAILBREAK],
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        # Only pattern, confidence should be 1.0
        assert assessment.confidence == 1.0


class TestRequiresIntervention:
    """Tests for requires_intervention property."""

    def test_block_requires_intervention(self):
        """Test BLOCK requires intervention."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.CRITICAL,
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert assessment.requires_intervention is True

    def test_escalate_requires_intervention(self):
        """Test ESCALATE_HITL requires intervention."""
        engine = DecisionEngine()
        session_result = create_session_result(needs_hitl=True)
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        assert assessment.requires_intervention is True

    def test_sanitize_does_not_require_intervention(self):
        """Test SANITIZE does not require intervention (only BLOCK and ESCALATE do)."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        # SANITIZE is not considered intervention - only BLOCK and ESCALATE_HITL
        assert assessment.recommended_action == RecommendedAction.SANITIZE
        assert assessment.requires_intervention is False

    def test_allow_no_intervention(self):
        """Test ALLOW does not require intervention."""
        engine = DecisionEngine()
        assessment = engine.assess(input_text="Hello")
        assert assessment.requires_intervention is False


class TestConfigurationOptions:
    """Tests for configuration options."""

    def test_block_on_critical_disabled(self):
        """Test block_on_critical can be disabled."""
        config = DecisionEngineConfig(block_on_critical=False)
        engine = DecisionEngine(config=config)

        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.CRITICAL,
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        # Should not auto-block even on CRITICAL
        assert assessment.recommended_action != RecommendedAction.BLOCK

    def test_multiple_high_count_threshold(self):
        """Test multiple_high_count threshold."""
        config = DecisionEngineConfig(multiple_high_count=3)
        engine = DecisionEngine(config=config)

        # Only 2 HIGH threats - should not block
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.HIGH,
        )
        embedding_result = create_embedding_result(
            threat_level=ThreatLevel.HIGH,
            found=True,
            similarity=0.9,
        )

        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
            embedding_result=embedding_result,
        )
        # With threshold 3, 2 HIGHs should not block
        assert assessment.recommended_action != RecommendedAction.BLOCK

    def test_hitl_escalation_disabled(self):
        """Test HITL escalation can be disabled."""
        config = DecisionEngineConfig(enable_hitl_escalation=False)
        engine = DecisionEngine(config=config)

        session_result = create_session_result(needs_hitl=True)
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        # Should not escalate when disabled
        assert assessment.recommended_action != RecommendedAction.ESCALATE_HITL


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_decision_engine_singleton(self):
        """Test get_decision_engine returns singleton."""
        e1 = get_decision_engine()
        e2 = get_decision_engine()
        assert e1 is e2

    def test_assess_threat_function(self):
        """Test assess_threat convenience function."""
        assessment = assess_threat(input_text="Test input")
        assert assessment is not None
        assert assessment.threat_level in ThreatLevel

    def test_reset_decision_engine(self):
        """Test reset_decision_engine clears singleton."""
        e1 = get_decision_engine()
        reset_decision_engine()
        e2 = get_decision_engine()
        assert e1 is not e2


class TestReasoning:
    """Tests for reasoning generation."""

    def test_reasoning_includes_threat_info(self):
        """Test reasoning includes threat information."""
        engine = DecisionEngine()
        pattern_result = create_pattern_result(
            threat_level=ThreatLevel.CRITICAL,
        )
        assessment = engine.assess(
            input_text="Test",
            pattern_result=pattern_result,
        )
        assert "CRITICAL" in assessment.reasoning

    def test_reasoning_includes_session_info(self):
        """Test reasoning includes session escalation info."""
        engine = DecisionEngine()
        session_result = create_session_result(
            cumulative_score=3.0,
            needs_hitl=True,
        )
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        assert (
            "cumulative" in assessment.reasoning.lower()
            or "session" in assessment.reasoning.lower()
        )


class TestSessionIdHandling:
    """Tests for session ID handling."""

    def test_session_id_from_parameter(self):
        """Test session ID from parameter is used."""
        engine = DecisionEngine()
        assessment = engine.assess(
            input_text="Test",
            session_id="my-session-123",
        )
        assert assessment.session_id == "my-session-123"

    def test_session_id_from_session_result(self):
        """Test session ID from session result is used."""
        engine = DecisionEngine()
        session_result = create_session_result()
        assessment = engine.assess(
            input_text="Test",
            session_result=session_result,
        )
        assert assessment.session_id == "test-session"
