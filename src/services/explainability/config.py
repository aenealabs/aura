"""
Project Aura - Explainability Configuration

Configuration classes for the Universal Explainability Framework.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExplainabilityConfig:
    """Configuration for the Universal Explainability Service."""

    # Severity requirements
    min_reasoning_steps: dict[str, int] = field(default_factory=dict)
    min_alternatives: dict[str, int] = field(default_factory=dict)

    # Score weights (must sum to 1.0)
    score_weights: dict[str, float] = field(default_factory=dict)

    # Thresholds
    consistency_threshold: float = 0.8
    confidence_calibration_threshold: float = 0.7
    inter_agent_trust_threshold: float = 0.75
    explainability_score_threshold: float = 0.7

    # HITL escalation
    escalate_on_contradiction: bool = True
    escalate_on_low_confidence: bool = True
    low_confidence_threshold: float = 0.5
    escalate_on_low_score: bool = True
    low_score_threshold: float = 0.5

    # Performance
    enable_caching: bool = True
    async_persistence: bool = True
    max_processing_time_ms: int = 500
    cache_ttl_seconds: int = 300

    # Storage
    dynamodb_table_name: str = "aura-explainability-records"
    neptune_enabled: bool = True
    s3_bucket_name: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    cloudwatch_namespace: str = "Aura/Explainability"

    # Feature flags
    enable_constitutional_critique: bool = True
    enable_inter_agent_verification: bool = True
    enable_dashboard_api: bool = True

    def __post_init__(self) -> None:
        """Set default values for severity requirements."""
        if not self.min_reasoning_steps:
            self.min_reasoning_steps = {
                "trivial": 1,
                "normal": 2,
                "significant": 3,
                "critical": 5,
            }
        if not self.min_alternatives:
            self.min_alternatives = {
                "trivial": 2,
                "normal": 2,
                "significant": 3,
                "critical": 4,
            }
        if not self.score_weights:
            self.score_weights = {
                "reasoning_completeness": 0.25,
                "alternatives_coverage": 0.20,
                "confidence_calibration": 0.15,
                "consistency_score": 0.25,
                "inter_agent_trust": 0.15,
            }

    def get_min_reasoning_steps(self, severity: str) -> int:
        """Get minimum reasoning steps for a severity level."""
        return self.min_reasoning_steps.get(severity.lower(), 2)

    def get_min_alternatives(self, severity: str) -> int:
        """Get minimum alternatives for a severity level."""
        return self.min_alternatives.get(severity.lower(), 2)

    @classmethod
    def from_environment(cls) -> ExplainabilityConfig:
        """Create configuration from environment variables."""
        return cls(
            consistency_threshold=float(
                os.getenv("EXPLAINABILITY_CONSISTENCY_THRESHOLD", "0.8")
            ),
            confidence_calibration_threshold=float(
                os.getenv("EXPLAINABILITY_CONFIDENCE_THRESHOLD", "0.7")
            ),
            inter_agent_trust_threshold=float(
                os.getenv("EXPLAINABILITY_TRUST_THRESHOLD", "0.75")
            ),
            explainability_score_threshold=float(
                os.getenv("EXPLAINABILITY_SCORE_THRESHOLD", "0.7")
            ),
            escalate_on_contradiction=os.getenv(
                "EXPLAINABILITY_ESCALATE_CONTRADICTION", "true"
            ).lower()
            == "true",
            escalate_on_low_confidence=os.getenv(
                "EXPLAINABILITY_ESCALATE_LOW_CONFIDENCE", "true"
            ).lower()
            == "true",
            low_confidence_threshold=float(
                os.getenv("EXPLAINABILITY_LOW_CONFIDENCE_THRESHOLD", "0.5")
            ),
            enable_caching=os.getenv("EXPLAINABILITY_ENABLE_CACHING", "true").lower()
            == "true",
            async_persistence=os.getenv(
                "EXPLAINABILITY_ASYNC_PERSISTENCE", "true"
            ).lower()
            == "true",
            max_processing_time_ms=int(
                os.getenv("EXPLAINABILITY_MAX_PROCESSING_MS", "500")
            ),
            cache_ttl_seconds=int(os.getenv("EXPLAINABILITY_CACHE_TTL", "300")),
            dynamodb_table_name=os.getenv(
                "EXPLAINABILITY_DYNAMODB_TABLE", "aura-explainability-records"
            ),
            neptune_enabled=os.getenv("EXPLAINABILITY_NEPTUNE_ENABLED", "true").lower()
            == "true",
            s3_bucket_name=os.getenv("EXPLAINABILITY_S3_BUCKET"),
            log_level=os.getenv("EXPLAINABILITY_LOG_LEVEL", "INFO"),
            cloudwatch_namespace=os.getenv(
                "EXPLAINABILITY_CW_NAMESPACE", "Aura/Explainability"
            ),
            enable_constitutional_critique=os.getenv(
                "EXPLAINABILITY_CONSTITUTIONAL_CRITIQUE", "true"
            ).lower()
            == "true",
            enable_inter_agent_verification=os.getenv(
                "EXPLAINABILITY_INTER_AGENT_VERIFICATION", "true"
            ).lower()
            == "true",
            enable_dashboard_api=os.getenv(
                "EXPLAINABILITY_DASHBOARD_API", "true"
            ).lower()
            == "true",
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "min_reasoning_steps": self.min_reasoning_steps,
            "min_alternatives": self.min_alternatives,
            "consistency_threshold": self.consistency_threshold,
            "confidence_calibration_threshold": self.confidence_calibration_threshold,
            "inter_agent_trust_threshold": self.inter_agent_trust_threshold,
            "explainability_score_threshold": self.explainability_score_threshold,
            "escalate_on_contradiction": self.escalate_on_contradiction,
            "escalate_on_low_confidence": self.escalate_on_low_confidence,
            "low_confidence_threshold": self.low_confidence_threshold,
            "escalate_on_low_score": self.escalate_on_low_score,
            "low_score_threshold": self.low_score_threshold,
            "enable_caching": self.enable_caching,
            "async_persistence": self.async_persistence,
            "max_processing_time_ms": self.max_processing_time_ms,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "dynamodb_table_name": self.dynamodb_table_name,
            "neptune_enabled": self.neptune_enabled,
            "s3_bucket_name": self.s3_bucket_name,
            "log_level": self.log_level,
            "cloudwatch_namespace": self.cloudwatch_namespace,
            "enable_constitutional_critique": self.enable_constitutional_critique,
            "enable_inter_agent_verification": self.enable_inter_agent_verification,
            "enable_dashboard_api": self.enable_dashboard_api,
        }


@dataclass
class ReasoningChainConfig:
    """Configuration for reasoning chain builder."""

    max_steps: int = 10
    min_evidence_per_step: int = 1
    max_evidence_per_step: int = 5
    min_confidence: float = 0.5
    enable_llm_extraction: bool = True
    extraction_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    extraction_temperature: float = 0.1
    max_tokens: int = 2000

    @classmethod
    def from_environment(cls) -> ReasoningChainConfig:
        """Create configuration from environment variables."""
        return cls(
            max_steps=int(os.getenv("REASONING_MAX_STEPS", "10")),
            min_evidence_per_step=int(os.getenv("REASONING_MIN_EVIDENCE", "1")),
            min_confidence=float(os.getenv("REASONING_MIN_CONFIDENCE", "0.5")),
            enable_llm_extraction=os.getenv("REASONING_LLM_EXTRACTION", "true").lower()
            == "true",
            extraction_model=os.getenv(
                "REASONING_EXTRACTION_MODEL",
                "anthropic.claude-3-haiku-20240307-v1:0",
            ),
            extraction_temperature=float(os.getenv("REASONING_EXTRACTION_TEMP", "0.1")),
            max_tokens=int(os.getenv("REASONING_MAX_TOKENS", "2000")),
        )


@dataclass
class AlternativesConfig:
    """Configuration for alternatives analyzer."""

    max_alternatives: int = 6
    min_pros_cons: int = 2
    comparison_criteria_count: int = 5
    enable_llm_analysis: bool = True
    analysis_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    analysis_temperature: float = 0.3

    @classmethod
    def from_environment(cls) -> AlternativesConfig:
        """Create configuration from environment variables."""
        return cls(
            max_alternatives=int(os.getenv("ALTERNATIVES_MAX", "6")),
            min_pros_cons=int(os.getenv("ALTERNATIVES_MIN_PROS_CONS", "2")),
            comparison_criteria_count=int(
                os.getenv("ALTERNATIVES_CRITERIA_COUNT", "3")
            ),
            enable_llm_analysis=os.getenv("ALTERNATIVES_LLM_ANALYSIS", "true").lower()
            == "true",
            analysis_model=os.getenv(
                "ALTERNATIVES_ANALYSIS_MODEL",
                "anthropic.claude-3-haiku-20240307-v1:0",
            ),
            analysis_temperature=float(os.getenv("ALTERNATIVES_ANALYSIS_TEMP", "0.2")),
        )


@dataclass
class ConfidenceConfig:
    """Configuration for confidence quantifier."""

    default_calibration_method: str = "ensemble_disagreement"
    interval_coverage: float = 0.95  # 95% confidence interval
    min_samples_for_mc: int = 5  # Minimum samples for Monte Carlo
    enable_platt_scaling: bool = True
    max_uncertainty_sources: int = 5
    calibration_temperature: float = 1.5

    @classmethod
    def from_environment(cls) -> ConfidenceConfig:
        """Create configuration from environment variables."""
        return cls(
            default_calibration_method=os.getenv(
                "CONFIDENCE_CALIBRATION_METHOD", "ensemble_disagreement"
            ),
            interval_coverage=float(os.getenv("CONFIDENCE_INTERVAL_COVERAGE", "0.95")),
            min_samples_for_mc=int(os.getenv("CONFIDENCE_MIN_MC_SAMPLES", "10")),
            enable_platt_scaling=os.getenv("CONFIDENCE_PLATT_SCALING", "true").lower()
            == "true",
            max_uncertainty_sources=int(
                os.getenv("CONFIDENCE_MAX_UNCERTAINTY_SOURCES", "5")
            ),
        )


@dataclass
class ConsistencyConfig:
    """Configuration for consistency verifier."""

    verification_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    verification_temperature: float = 0.1
    max_claims_per_verification: int = 10
    contradiction_severity_weights: dict[str, float] = field(default_factory=dict)
    enable_llm_verification: bool = True

    def __post_init__(self) -> None:
        """Set default contradiction severity weights."""
        if not self.contradiction_severity_weights:
            self.contradiction_severity_weights = {
                "minor": 0.05,
                "moderate": 0.15,
                "major": 0.30,
                "critical": 0.50,
            }

    @classmethod
    def from_environment(cls) -> ConsistencyConfig:
        """Create configuration from environment variables."""
        return cls(
            verification_model=os.getenv(
                "CONSISTENCY_VERIFICATION_MODEL",
                "anthropic.claude-3-haiku-20240307-v1:0",
            ),
            verification_temperature=float(
                os.getenv("CONSISTENCY_VERIFICATION_TEMP", "0.1")
            ),
            max_claims_per_verification=int(os.getenv("CONSISTENCY_MAX_CLAIMS", "10")),
            enable_llm_verification=os.getenv(
                "CONSISTENCY_LLM_VERIFICATION", "true"
            ).lower()
            == "true",
        )


@dataclass
class InterAgentConfig:
    """Configuration for inter-agent verifier."""

    verification_strategies: dict[str, str] = field(default_factory=dict)
    default_confidence_unverified: float = 0.3
    trust_adjustment_range: float = 0.2  # +/- 0.1
    neptune_query_timeout_ms: int = 5000
    enable_cross_reference: bool = True
    verification_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Set default verification strategies."""
        if not self.verification_strategies:
            self.verification_strategies = {
                "security_assessment": "neptune_security_graph",
                "test_result": "test_execution_logs",
                "code_analysis": "static_analysis_rerun",
                "vulnerability_found": "cve_database",
                "default": "basic_evidence_check",
            }

    @classmethod
    def from_environment(cls) -> InterAgentConfig:
        """Create configuration from environment variables."""
        return cls(
            default_confidence_unverified=float(
                os.getenv("INTER_AGENT_DEFAULT_CONFIDENCE", "0.3")
            ),
            trust_adjustment_range=float(
                os.getenv("INTER_AGENT_TRUST_ADJUSTMENT_RANGE", "0.2")
            ),
            neptune_query_timeout_ms=int(
                os.getenv("INTER_AGENT_NEPTUNE_TIMEOUT_MS", "5000")
            ),
            enable_cross_reference=os.getenv(
                "INTER_AGENT_CROSS_REFERENCE", "true"
            ).lower()
            == "true",
        )


# Global instance management
_explainability_config: Optional[ExplainabilityConfig] = None


def get_explainability_config() -> ExplainabilityConfig:
    """Get the global explainability configuration."""
    global _explainability_config
    if _explainability_config is None:
        _explainability_config = ExplainabilityConfig()
    return _explainability_config


def configure_explainability(config: ExplainabilityConfig) -> ExplainabilityConfig:
    """Configure and return the global explainability configuration."""
    global _explainability_config
    _explainability_config = config
    return _explainability_config


def reset_explainability_config() -> None:
    """Reset the global explainability configuration."""
    global _explainability_config
    _explainability_config = None
