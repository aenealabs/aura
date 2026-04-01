"""
Project Aura - Semantic Guardrails Engine Configuration

Centralized configuration for the 6-layer semantic threat detection engine.
All thresholds, timeouts, and feature flags are configurable here.

Performance Targets (ADR-065):
- P50 <150ms, P95 <300ms, P99 <500ms
- >95% detection rate on novel attack variants
- <1% false positive rate

Author: Project Aura Team
Created: 2026-01-25
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NormalizationConfig:
    """Configuration for Layer 1: Canonical Normalization."""

    # Unicode normalization
    unicode_form: str = "NFKC"  # NFC, NFD, NFKC, NFKD

    # Homograph detection
    enable_homograph_detection: bool = True
    homograph_mapping_file: Optional[str] = None

    # Zero-width character handling
    remove_zero_width_chars: bool = True

    # Multi-encoding decode
    enable_base64_decode: bool = True
    enable_url_decode: bool = True
    enable_html_entity_decode: bool = True
    max_decode_iterations: int = 3  # Prevent decode bombs

    # Whitespace normalization
    collapse_whitespace: bool = True

    # Performance
    max_input_length: int = 100_000  # 100k characters
    target_latency_ms: float = 5.0


@dataclass
class PatternMatchConfig:
    """Configuration for Layer 2: Fast-Path Pattern Matching."""

    # Pattern matching
    enable_pattern_matching: bool = True
    case_insensitive: bool = True

    # Blocklist
    enable_blocklist: bool = True
    blocklist_file: Optional[str] = None
    blocklist_hash_algorithm: str = "sha256"

    # Pattern categories to check
    check_system_override: bool = True
    check_jailbreak: bool = True
    check_hidden_instructions: bool = True
    check_delimiter_injection: bool = True
    check_exfiltration: bool = True

    # Performance
    target_latency_ms: float = 10.0


@dataclass
class EmbeddingConfig:
    """Configuration for Layer 3: Embedding Similarity Detection."""

    # OpenSearch index
    index_name: str = "aura-threat-embeddings"
    vector_dimension: int = 1024
    similarity_algorithm: str = "cosinesimil"  # cosinesimil, l2, innerproduct

    # k-NN search
    k_neighbors: int = 10
    min_score: float = 0.5

    # Threat thresholds
    high_similarity_threshold: float = 0.85  # ThreatLevel.HIGH
    medium_similarity_threshold: float = 0.70  # ThreatLevel.MEDIUM

    # Caching
    enable_query_cache: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes

    # Performance
    target_latency_ms: float = 50.0


@dataclass
class IntentClassificationConfig:
    """Configuration for Layer 4: LLM Intent Classification."""

    # Model selection
    model_tier: str = "fast"  # fast (Haiku), balanced (Sonnet), accurate (Opus)
    model_id: Optional[str] = None  # Override specific model

    # Classification
    classification_prompt_version: str = "v1"
    require_structured_output: bool = True

    # Confidence thresholds
    high_confidence_threshold: float = 0.8
    low_confidence_threshold: float = 0.5

    # Caching (integrates with semantic cache ADR-029)
    enable_semantic_cache: bool = True
    cache_similarity_threshold: float = 0.95

    # Performance
    max_input_tokens: int = 2000
    max_output_tokens: int = 500
    target_latency_ms: float = 150.0
    timeout_ms: int = 5000


@dataclass
class SessionTrackingConfig:
    """Configuration for Layer 5: Multi-Turn Session Tracking."""

    # DynamoDB table
    table_name: str = "aura-guardrails-sessions"
    ttl_hours: int = 24

    # Cumulative scoring
    decay_factor: float = 0.9  # Score decay per turn
    hitl_threshold: float = 2.5  # Cumulative score for HITL escalation
    max_turns_tracked: int = 50

    # Performance
    target_latency_ms: float = 20.0


@dataclass
class DecisionEngineConfig:
    """Configuration for Layer 6: Decision Engine & Audit."""

    # Decision thresholds
    block_on_critical: bool = True
    block_on_multiple_high: bool = True
    multiple_high_count: int = 2

    # HITL escalation
    enable_hitl_escalation: bool = True
    hitl_on_uncertain: bool = True
    uncertainty_threshold: float = 0.5

    # Audit logging
    enable_audit_logging: bool = True
    audit_queue_name: str = "aura-guardrails-audit"
    log_safe_assessments: bool = False  # Only log threats by default

    # Performance
    target_latency_ms: float = 5.0


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics publishing."""

    namespace: str = "Aura/SemanticGuardrails"
    enabled: bool = True  # Global enable/disable
    enable_metrics: bool = True  # Alias for compatibility

    # Buffer settings
    buffer_size: int = 100  # Metrics to buffer before flush
    flush_interval_seconds: int = 60  # Auto-flush interval

    # Metric names
    metric_threat_detected: str = "ThreatDetected"
    metric_processing_latency: str = "ProcessingLatencyMs"
    metric_false_positive: str = "FalsePositiveCount"
    metric_corpus_hit_rate: str = "CorpusHitRate"
    metric_cache_hit_rate: str = "CacheHitRate"

    # Dimensions
    include_environment: bool = True
    include_layer: bool = True
    include_threat_category: bool = True


@dataclass
class GuardrailsConfig:
    """
    Master configuration for the Semantic Guardrails Engine.

    Usage:
        # Default configuration
        config = GuardrailsConfig()

        # Custom configuration
        config = GuardrailsConfig(
            enabled=True,
            strict_mode=True,
            normalization=NormalizationConfig(max_input_length=50000),
            embedding=EmbeddingConfig(high_similarity_threshold=0.90),
        )

        # From environment
        config = GuardrailsConfig.from_environment()
    """

    # Global settings
    enabled: bool = True
    strict_mode: bool = False  # Block on any suspicion vs. allow with sanitization
    environment: str = "dev"  # dev, qa, staging, prod

    # Feature flags
    enable_layer_1_normalization: bool = True
    enable_layer_2_pattern_match: bool = True
    enable_layer_3_embedding: bool = True
    enable_layer_4_intent: bool = True
    enable_layer_5_session: bool = True
    enable_layer_6_decision: bool = True

    # Layer configurations
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    pattern_match: PatternMatchConfig = field(default_factory=PatternMatchConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    intent: IntentClassificationConfig = field(
        default_factory=IntentClassificationConfig
    )
    session: SessionTrackingConfig = field(default_factory=SessionTrackingConfig)
    decision: DecisionEngineConfig = field(default_factory=DecisionEngineConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    # Performance budget (total)
    target_p50_latency_ms: float = 150.0
    target_p95_latency_ms: float = 300.0
    target_p99_latency_ms: float = 500.0

    # Fallback behavior
    fallback_to_legacy_sanitizer: bool = True  # Use LLMPromptSanitizer on failure
    fail_open: bool = (
        False  # Allow input on service failure (DANGER: set True carefully)
    )

    @classmethod
    def from_environment(cls) -> "GuardrailsConfig":
        """
        Create configuration from environment variables.

        Environment variables:
            GUARDRAILS_ENABLED: Enable/disable guardrails (default: true)
            GUARDRAILS_STRICT_MODE: Block suspicious inputs (default: false)
            GUARDRAILS_ENVIRONMENT: Deployment environment (default: dev)
            GUARDRAILS_FAIL_OPEN: Allow on failure (default: false)
            ... (layer-specific settings follow same pattern)
        """
        return cls(
            enabled=os.environ.get("GUARDRAILS_ENABLED", "true").lower() == "true",
            strict_mode=os.environ.get("GUARDRAILS_STRICT_MODE", "false").lower()
            == "true",
            environment=os.environ.get("GUARDRAILS_ENVIRONMENT", "dev"),
            fail_open=os.environ.get("GUARDRAILS_FAIL_OPEN", "false").lower() == "true",
            fallback_to_legacy_sanitizer=os.environ.get(
                "GUARDRAILS_FALLBACK_LEGACY", "true"
            ).lower()
            == "true",
            # Layer feature flags
            enable_layer_1_normalization=os.environ.get(
                "GUARDRAILS_LAYER_1", "true"
            ).lower()
            == "true",
            enable_layer_2_pattern_match=os.environ.get(
                "GUARDRAILS_LAYER_2", "true"
            ).lower()
            == "true",
            enable_layer_3_embedding=os.environ.get(
                "GUARDRAILS_LAYER_3", "true"
            ).lower()
            == "true",
            enable_layer_4_intent=os.environ.get("GUARDRAILS_LAYER_4", "true").lower()
            == "true",
            enable_layer_5_session=os.environ.get("GUARDRAILS_LAYER_5", "true").lower()
            == "true",
            enable_layer_6_decision=os.environ.get("GUARDRAILS_LAYER_6", "true").lower()
            == "true",
            # Embedding layer overrides
            embedding=EmbeddingConfig(
                index_name=os.environ.get(
                    "GUARDRAILS_EMBEDDING_INDEX", "aura-threat-embeddings"
                ),
                high_similarity_threshold=float(
                    os.environ.get("GUARDRAILS_HIGH_SIMILARITY", "0.85")
                ),
                medium_similarity_threshold=float(
                    os.environ.get("GUARDRAILS_MEDIUM_SIMILARITY", "0.70")
                ),
            ),
            # Session layer overrides
            session=SessionTrackingConfig(
                table_name=os.environ.get(
                    "GUARDRAILS_SESSION_TABLE", "aura-guardrails-sessions"
                ),
                hitl_threshold=float(
                    os.environ.get("GUARDRAILS_HITL_THRESHOLD", "2.5")
                ),
            ),
            # Metrics overrides
            metrics=MetricsConfig(
                namespace=os.environ.get(
                    "GUARDRAILS_METRICS_NAMESPACE", "Aura/SemanticGuardrails"
                ),
                enable_metrics=os.environ.get(
                    "GUARDRAILS_METRICS_ENABLED", "true"
                ).lower()
                == "true",
            ),
        )

    @classmethod
    def for_production(cls) -> "GuardrailsConfig":
        """Create production-hardened configuration."""
        return cls(
            enabled=True,
            strict_mode=True,
            environment="prod",
            fail_open=False,
            fallback_to_legacy_sanitizer=True,
            decision=DecisionEngineConfig(
                block_on_critical=True,
                block_on_multiple_high=True,
                enable_hitl_escalation=True,
                enable_audit_logging=True,
                log_safe_assessments=False,
            ),
            metrics=MetricsConfig(
                enable_metrics=True,
                include_environment=True,
                include_layer=True,
                include_threat_category=True,
            ),
        )

    @classmethod
    def for_testing(cls) -> "GuardrailsConfig":
        """Create configuration for unit tests."""
        return cls(
            enabled=True,
            strict_mode=False,
            environment="test",
            fail_open=False,
            fallback_to_legacy_sanitizer=False,
            # Disable external dependencies
            enable_layer_3_embedding=False,  # Requires OpenSearch
            enable_layer_4_intent=False,  # Requires Bedrock
            enable_layer_5_session=False,  # Requires DynamoDB
            decision=DecisionEngineConfig(
                enable_audit_logging=False,
            ),
            metrics=MetricsConfig(
                enable_metrics=False,
            ),
        )

    def validate(self) -> list[str]:
        """
        Validate configuration for consistency and safety.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check latency budget
        # Note: L3 and L4 run in parallel, so we use parallel latency
        parallel_latency = (
            self.normalization.target_latency_ms
            + self.pattern_match.target_latency_ms
            + max(self.embedding.target_latency_ms, self.intent.target_latency_ms)
            + self.session.target_latency_ms
            + self.decision.target_latency_ms
        )
        if parallel_latency > self.target_p50_latency_ms:
            errors.append(
                f"Layer latencies ({parallel_latency}ms) exceed P50 target "
                f"({self.target_p50_latency_ms}ms)"
            )

        # Check threshold consistency
        if (
            self.embedding.high_similarity_threshold
            <= self.embedding.medium_similarity_threshold
        ):
            errors.append(
                "high_similarity_threshold must be > medium_similarity_threshold"
            )

        # Check dangerous production settings
        if self.environment == "prod":
            if self.fail_open:
                errors.append("fail_open=True is dangerous in production")
            if not self.decision.enable_audit_logging:
                errors.append("Audit logging should be enabled in production")
            if not self.metrics.enable_metrics:
                errors.append("Metrics should be enabled in production")

        return errors


# Singleton instance
_config_instance: Optional[GuardrailsConfig] = None


def get_guardrails_config() -> GuardrailsConfig:
    """
    Get singleton configuration instance.

    Returns:
        GuardrailsConfig loaded from environment
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = GuardrailsConfig.from_environment()
    return _config_instance


def reset_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config_instance
    _config_instance = None
