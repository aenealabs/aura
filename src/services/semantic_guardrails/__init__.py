"""
Project Aura - Semantic Guardrails Engine

6-layer semantic threat detection for AI agent inputs/outputs.
Implements ADR-065 with >95% detection rate on novel attack variants.

Architecture:
- Layer 1: Canonical Normalization (5ms) - normalizer.py
- Layer 2: Fast-Path Pattern Check (10ms) - pattern_matcher.py
- Layer 3: Embedding Similarity Detection (50ms) - embedding_detector.py
- Layer 4: LLM Intent Classification (150ms) - intent_classifier.py
- Layer 5: Multi-Turn Session Tracking (20ms) - multi_turn_tracker.py
- Layer 6: Decision Engine & Audit (5ms) - decision_engine.py

Performance Targets:
- P50 <150ms, P95 <300ms, P99 <500ms
- >95% detection rate on novel attack variants
- <1% false positive rate

Usage:
    from src.services.semantic_guardrails import (
        SemanticGuardrailsEngine,
        assess_threat,
        ThreatAssessment,
        ThreatLevel,
        RecommendedAction,
    )

    # Full pipeline assessment
    engine = SemanticGuardrailsEngine()
    assessment = engine.assess_threat(
        input_text="User input to check",
        session_id="session-123",
    )

    if assessment.requires_intervention:
        if assessment.recommended_action == RecommendedAction.BLOCK:
            block_request()
        elif assessment.recommended_action == RecommendedAction.ESCALATE_HITL:
            escalate_to_human(assessment)

    # Fast-path detection (Layers 1-2 only)
    from src.services.semantic_guardrails import (
        normalize_text,
        match_patterns,
    )

    normalized = normalize_text("İgnore prévious instrüctions")
    result = match_patterns(normalized.normalized_text)
    if result.should_fast_exit:
        block_request(result)

Author: Project Aura Team
Created: 2026-01-25
"""

# Configuration
from .config import (
    DecisionEngineConfig,
    EmbeddingConfig,
    GuardrailsConfig,
    IntentClassificationConfig,
    MetricsConfig,
    NormalizationConfig,
    PatternMatchConfig,
    SessionTrackingConfig,
    get_guardrails_config,
    reset_config,
)

# Contracts - Core types
from .contracts import (  # Enums; Layer results; Final assessment; Corpus; Type aliases
    BlocklistSet,
    EmbeddingMatchResult,
    HomographMap,
    IntentClassificationResult,
    LayerResult,
    NormalizationResult,
    PatternMatchResult,
    RecommendedAction,
    SessionThreatScore,
    ThreatAssessment,
    ThreatCategory,
    ThreatCorpusEntry,
    ThreatLevel,
    ThreatPatternDict,
)

# Layer 6: Decision Engine
from .decision_engine import DecisionEngine, get_decision_engine, reset_decision_engine

# Layer 3: Embedding Detector
from .embedding_detector import (
    EmbeddingDetector,
    detect_embedding_threat,
    get_embedding_detector,
    reset_embedding_detector,
)

# Main Engine
from .engine import (
    SemanticGuardrailsEngine,
    assess_threat,
    assess_threat_async,
    get_guardrails_engine,
    reset_guardrails_engine,
)

# Integration (Phase 4)
from .integration import (
    GuardrailsIntegrationConfig,
    GuardrailsMode,
    GuardrailsResult,
    SemanticGuardrailsHook,
    SemanticGuardrailsIntegrationError,
    check_prompt,
    check_prompt_async,
    create_guardrails_hook,
    get_default_hook,
    integrate_with_bedrock_service,
    reset_default_hook,
    with_semantic_guardrails,
)

# Layer 4: Intent Classifier
from .intent_classifier import (
    IntentClassifier,
    classify_intent,
    get_intent_classifier,
    reset_intent_classifier,
)

# Metrics
from .metrics import (
    GuardrailsMetricsPublisher,
    flush_metrics,
    get_metrics_publisher,
    record_threat_assessment,
    reset_metrics_publisher,
)

# Layer 5: Multi-Turn Session Tracker
from .multi_turn_tracker import (
    MultiTurnTracker,
    get_multi_turn_tracker,
    record_session_turn,
    reset_multi_turn_tracker,
)

# Layer 1: Normalizer
from .normalizer import (
    HOMOGRAPH_MAP,
    ZERO_WIDTH_CHARS,
    TextNormalizer,
    get_normalizer,
    normalize_text,
    reset_normalizer,
)

# Layer 2: Pattern Matcher
from .pattern_matcher import (
    DELIMITER_INJECTION_PATTERNS,
    EXFILTRATION_PATTERNS,
    HIDDEN_INSTRUCTION_PATTERNS,
    JAILBREAK_PATTERNS,
    ROLE_CONFUSION_PATTERNS,
    SYSTEM_OVERRIDE_PATTERNS,
    PatternMatcher,
    get_pattern_matcher,
    match_patterns,
    reset_pattern_matcher,
)

__all__ = [
    # Enums
    "ThreatLevel",
    "ThreatCategory",
    "RecommendedAction",
    # Layer results
    "NormalizationResult",
    "PatternMatchResult",
    "EmbeddingMatchResult",
    "IntentClassificationResult",
    "SessionThreatScore",
    "LayerResult",
    # Final assessment
    "ThreatAssessment",
    # Corpus
    "ThreatCorpusEntry",
    # Type aliases
    "ThreatPatternDict",
    "HomographMap",
    "BlocklistSet",
    # Configuration
    "GuardrailsConfig",
    "NormalizationConfig",
    "PatternMatchConfig",
    "EmbeddingConfig",
    "IntentClassificationConfig",
    "SessionTrackingConfig",
    "DecisionEngineConfig",
    "MetricsConfig",
    "get_guardrails_config",
    "reset_config",
    # Layer 1: Normalizer
    "TextNormalizer",
    "normalize_text",
    "get_normalizer",
    "reset_normalizer",
    "HOMOGRAPH_MAP",
    "ZERO_WIDTH_CHARS",
    # Layer 2: Pattern Matcher
    "PatternMatcher",
    "match_patterns",
    "get_pattern_matcher",
    "reset_pattern_matcher",
    "SYSTEM_OVERRIDE_PATTERNS",
    "JAILBREAK_PATTERNS",
    "HIDDEN_INSTRUCTION_PATTERNS",
    "DELIMITER_INJECTION_PATTERNS",
    "EXFILTRATION_PATTERNS",
    "ROLE_CONFUSION_PATTERNS",
    # Layer 3: Embedding Detector
    "EmbeddingDetector",
    "detect_embedding_threat",
    "get_embedding_detector",
    "reset_embedding_detector",
    # Layer 4: Intent Classifier
    "IntentClassifier",
    "classify_intent",
    "get_intent_classifier",
    "reset_intent_classifier",
    # Layer 5: Multi-Turn Session Tracker
    "MultiTurnTracker",
    "record_session_turn",
    "get_multi_turn_tracker",
    "reset_multi_turn_tracker",
    # Layer 6: Decision Engine
    "DecisionEngine",
    "get_decision_engine",
    "reset_decision_engine",
    # Metrics
    "GuardrailsMetricsPublisher",
    "record_threat_assessment",
    "flush_metrics",
    "get_metrics_publisher",
    "reset_metrics_publisher",
    # Main Engine
    "SemanticGuardrailsEngine",
    "assess_threat",
    "assess_threat_async",
    "get_guardrails_engine",
    "reset_guardrails_engine",
    # Integration (Phase 4)
    "GuardrailsMode",
    "GuardrailsIntegrationConfig",
    "GuardrailsResult",
    "SemanticGuardrailsHook",
    "SemanticGuardrailsIntegrationError",
    "with_semantic_guardrails",
    "create_guardrails_hook",
    "integrate_with_bedrock_service",
    "check_prompt",
    "check_prompt_async",
    "get_default_hook",
    "reset_default_hook",
]

__version__ = "0.4.0"
