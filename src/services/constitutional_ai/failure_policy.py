"""Failure handling policies for Constitutional AI.

This module defines the configurable failure handling behavior for the
Constitutional AI system, including how to handle critique failures,
revision failures, and audit trail requirements.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class CritiqueFailurePolicy(Enum):
    """Policy for handling critique evaluation failures.

    Defines how the system should respond when critique evaluation
    fails (e.g., LLM timeout, parsing error).

    Values:
        BLOCK: Stop execution entirely, require intervention
        PROCEED_LOGGED: Continue but log the failure for review
        PROCEED_FLAGGED: Continue but flag output for manual review (DEFAULT)
        RETRY_THEN_BLOCK: Retry configured number of times, then block
    """

    BLOCK = "block"
    PROCEED_LOGGED = "proceed_logged"
    PROCEED_FLAGGED = "proceed_flagged"
    RETRY_THEN_BLOCK = "retry_then_block"

    @classmethod
    def from_string(cls, value: str) -> "CritiqueFailurePolicy":
        """Create policy from string value.

        Args:
            value: String representation of policy

        Returns:
            Corresponding CritiqueFailurePolicy enum value

        Raises:
            ValueError: If value doesn't match any policy
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [p.value for p in cls]
            raise ValueError(
                f"Invalid critique failure policy '{value}'. Must be one of: {valid_values}"
            )


class RevisionFailurePolicy(Enum):
    """Policy for handling revision failures.

    Defines how the system should respond when revision fails to
    resolve all critical issues within the maximum iterations.

    Values:
        RETURN_ORIGINAL: Return the original unmodified output
        RETURN_BEST_EFFORT: Return the best revision achieved
        BLOCK_FOR_HITL: Block and require human-in-the-loop review (DEFAULT)
    """

    RETURN_ORIGINAL = "return_original"
    RETURN_BEST_EFFORT = "return_best_effort"
    BLOCK_FOR_HITL = "block_for_hitl"

    @classmethod
    def from_string(cls, value: str) -> "RevisionFailurePolicy":
        """Create policy from string value.

        Args:
            value: String representation of policy

        Returns:
            Corresponding RevisionFailurePolicy enum value

        Raises:
            ValueError: If value doesn't match any policy
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [p.value for p in cls]
            raise ValueError(
                f"Invalid revision failure policy '{value}'. Must be one of: {valid_values}"
            )


@dataclass
class ConstitutionalFailureConfig:
    """Configuration for Constitutional AI failure handling.

    This configuration controls how the system responds to various
    failure scenarios during critique and revision operations.

    Attributes:
        critique_failure_policy: How to handle critique failures
        revision_failure_policy: How to handle revision failures
        max_critique_retries: Max retries for RETRY_THEN_BLOCK policy
        critique_retry_delay_ms: Delay between critique retries
        critique_timeout_seconds: Timeout for critique LLM calls
        revision_timeout_seconds: Timeout for revision LLM calls
        max_revision_iterations: Maximum revision loop iterations
        require_audit_trail: Whether audit logging is required
        audit_failure_blocks_execution: Whether audit failures block execution
        enable_metrics: Whether to emit CloudWatch metrics
    """

    critique_failure_policy: CritiqueFailurePolicy = (
        CritiqueFailurePolicy.PROCEED_FLAGGED
    )
    revision_failure_policy: RevisionFailurePolicy = (
        RevisionFailurePolicy.BLOCK_FOR_HITL
    )
    max_critique_retries: int = 2
    critique_retry_delay_ms: int = 500
    critique_timeout_seconds: float = 30.0
    revision_timeout_seconds: float = 60.0
    max_revision_iterations: int = 3
    require_audit_trail: bool = True
    audit_failure_blocks_execution: bool = False
    enable_metrics: bool = True

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.max_critique_retries < 0:
            raise ValueError(
                f"max_critique_retries must be non-negative, got {self.max_critique_retries}"
            )
        if self.critique_retry_delay_ms < 0:
            raise ValueError(
                f"critique_retry_delay_ms must be non-negative, got {self.critique_retry_delay_ms}"
            )
        if self.critique_timeout_seconds <= 0:
            raise ValueError(
                f"critique_timeout_seconds must be positive, got {self.critique_timeout_seconds}"
            )
        if self.revision_timeout_seconds <= 0:
            raise ValueError(
                f"revision_timeout_seconds must be positive, got {self.revision_timeout_seconds}"
            )
        if self.max_revision_iterations < 1:
            raise ValueError(
                f"max_revision_iterations must be at least 1, got {self.max_revision_iterations}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary representation.

        Returns:
            Dictionary with all configuration fields
        """
        return {
            "critique_failure_policy": self.critique_failure_policy.value,
            "revision_failure_policy": self.revision_failure_policy.value,
            "max_critique_retries": self.max_critique_retries,
            "critique_retry_delay_ms": self.critique_retry_delay_ms,
            "critique_timeout_seconds": self.critique_timeout_seconds,
            "revision_timeout_seconds": self.revision_timeout_seconds,
            "max_revision_iterations": self.max_revision_iterations,
            "require_audit_trail": self.require_audit_trail,
            "audit_failure_blocks_execution": self.audit_failure_blocks_execution,
            "enable_metrics": self.enable_metrics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConstitutionalFailureConfig":
        """Create configuration from dictionary.

        Args:
            data: Dictionary containing configuration fields

        Returns:
            ConstitutionalFailureConfig instance
        """
        critique_policy = data.get("critique_failure_policy", "proceed_flagged")
        if isinstance(critique_policy, str):
            critique_policy = CritiqueFailurePolicy.from_string(critique_policy)

        revision_policy = data.get("revision_failure_policy", "block_for_hitl")
        if isinstance(revision_policy, str):
            revision_policy = RevisionFailurePolicy.from_string(revision_policy)

        return cls(
            critique_failure_policy=critique_policy,
            revision_failure_policy=revision_policy,
            max_critique_retries=data.get("max_critique_retries", 2),
            critique_retry_delay_ms=data.get("critique_retry_delay_ms", 500),
            critique_timeout_seconds=data.get("critique_timeout_seconds", 30.0),
            revision_timeout_seconds=data.get("revision_timeout_seconds", 60.0),
            max_revision_iterations=data.get("max_revision_iterations", 3),
            require_audit_trail=data.get("require_audit_trail", True),
            audit_failure_blocks_execution=data.get(
                "audit_failure_blocks_execution", False
            ),
            enable_metrics=data.get("enable_metrics", True),
        )


# Environment variable names for configuration
ENV_CRITIQUE_FAILURE_POLICY = "CONSTITUTIONAL_AI_CRITIQUE_FAILURE_POLICY"
ENV_REVISION_FAILURE_POLICY = "CONSTITUTIONAL_AI_REVISION_FAILURE_POLICY"
ENV_MAX_CRITIQUE_RETRIES = "CONSTITUTIONAL_AI_MAX_CRITIQUE_RETRIES"
ENV_CRITIQUE_RETRY_DELAY_MS = "CONSTITUTIONAL_AI_CRITIQUE_RETRY_DELAY_MS"
ENV_CRITIQUE_TIMEOUT_SECONDS = "CONSTITUTIONAL_AI_CRITIQUE_TIMEOUT_SECONDS"
ENV_REVISION_TIMEOUT_SECONDS = "CONSTITUTIONAL_AI_REVISION_TIMEOUT_SECONDS"
ENV_MAX_REVISION_ITERATIONS = "CONSTITUTIONAL_AI_MAX_REVISION_ITERATIONS"
ENV_REQUIRE_AUDIT_TRAIL = "CONSTITUTIONAL_AI_REQUIRE_AUDIT_TRAIL"
ENV_AUDIT_FAILURE_BLOCKS = "CONSTITUTIONAL_AI_AUDIT_FAILURE_BLOCKS"
ENV_ENABLE_METRICS = "CONSTITUTIONAL_AI_ENABLE_METRICS"


def _get_bool_env(name: str, default: bool) -> bool:
    """Get boolean value from environment variable.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value from environment or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_int_env(name: str, default: int) -> int:
    """Get integer value from environment variable.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Integer value from environment or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    """Get float value from environment variable.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Float value from environment or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_failure_config() -> ConstitutionalFailureConfig:
    """Get failure configuration from environment variables or defaults.

    Environment variables (all optional):
        CONSTITUTIONAL_AI_CRITIQUE_FAILURE_POLICY: Critique failure policy
        CONSTITUTIONAL_AI_REVISION_FAILURE_POLICY: Revision failure policy
        CONSTITUTIONAL_AI_MAX_CRITIQUE_RETRIES: Max critique retries
        CONSTITUTIONAL_AI_CRITIQUE_RETRY_DELAY_MS: Critique retry delay
        CONSTITUTIONAL_AI_CRITIQUE_TIMEOUT_SECONDS: Critique timeout
        CONSTITUTIONAL_AI_REVISION_TIMEOUT_SECONDS: Revision timeout
        CONSTITUTIONAL_AI_MAX_REVISION_ITERATIONS: Max revision iterations
        CONSTITUTIONAL_AI_REQUIRE_AUDIT_TRAIL: Require audit trail
        CONSTITUTIONAL_AI_AUDIT_FAILURE_BLOCKS: Audit failure blocks
        CONSTITUTIONAL_AI_ENABLE_METRICS: Enable metrics

    Returns:
        ConstitutionalFailureConfig with values from environment or defaults
    """
    # Get policy values from environment
    critique_policy_str = os.environ.get(ENV_CRITIQUE_FAILURE_POLICY)
    revision_policy_str = os.environ.get(ENV_REVISION_FAILURE_POLICY)

    # Parse policies or use defaults
    critique_policy = CritiqueFailurePolicy.PROCEED_FLAGGED
    if critique_policy_str:
        try:
            critique_policy = CritiqueFailurePolicy.from_string(critique_policy_str)
        except ValueError:
            pass  # Use default on invalid value

    revision_policy = RevisionFailurePolicy.BLOCK_FOR_HITL
    if revision_policy_str:
        try:
            revision_policy = RevisionFailurePolicy.from_string(revision_policy_str)
        except ValueError:
            pass  # Use default on invalid value

    return ConstitutionalFailureConfig(
        critique_failure_policy=critique_policy,
        revision_failure_policy=revision_policy,
        max_critique_retries=_get_int_env(ENV_MAX_CRITIQUE_RETRIES, 2),
        critique_retry_delay_ms=_get_int_env(ENV_CRITIQUE_RETRY_DELAY_MS, 500),
        critique_timeout_seconds=_get_float_env(ENV_CRITIQUE_TIMEOUT_SECONDS, 30.0),
        revision_timeout_seconds=_get_float_env(ENV_REVISION_TIMEOUT_SECONDS, 60.0),
        max_revision_iterations=_get_int_env(ENV_MAX_REVISION_ITERATIONS, 3),
        require_audit_trail=_get_bool_env(ENV_REQUIRE_AUDIT_TRAIL, True),
        audit_failure_blocks_execution=_get_bool_env(ENV_AUDIT_FAILURE_BLOCKS, False),
        enable_metrics=_get_bool_env(ENV_ENABLE_METRICS, True),
    )


# Pre-defined configurations for common scenarios
STRICT_CONFIG = ConstitutionalFailureConfig(
    critique_failure_policy=CritiqueFailurePolicy.RETRY_THEN_BLOCK,
    revision_failure_policy=RevisionFailurePolicy.BLOCK_FOR_HITL,
    max_critique_retries=3,
    max_revision_iterations=5,
    require_audit_trail=True,
    audit_failure_blocks_execution=True,
)

LENIENT_CONFIG = ConstitutionalFailureConfig(
    critique_failure_policy=CritiqueFailurePolicy.PROCEED_LOGGED,
    revision_failure_policy=RevisionFailurePolicy.RETURN_BEST_EFFORT,
    max_critique_retries=1,
    max_revision_iterations=2,
    require_audit_trail=True,
    audit_failure_blocks_execution=False,
)

DEVELOPMENT_CONFIG = ConstitutionalFailureConfig(
    critique_failure_policy=CritiqueFailurePolicy.PROCEED_FLAGGED,
    revision_failure_policy=RevisionFailurePolicy.RETURN_BEST_EFFORT,
    max_critique_retries=1,
    critique_timeout_seconds=60.0,  # Longer timeout for debugging
    revision_timeout_seconds=120.0,
    max_revision_iterations=2,
    require_audit_trail=False,
    audit_failure_blocks_execution=False,
    enable_metrics=False,
)

PRODUCTION_CONFIG = ConstitutionalFailureConfig(
    critique_failure_policy=CritiqueFailurePolicy.RETRY_THEN_BLOCK,
    revision_failure_policy=RevisionFailurePolicy.BLOCK_FOR_HITL,
    max_critique_retries=2,
    critique_timeout_seconds=30.0,
    revision_timeout_seconds=60.0,
    max_revision_iterations=3,
    require_audit_trail=True,
    audit_failure_blocks_execution=True,
    enable_metrics=True,
)


def get_config_for_environment(environment: str) -> ConstitutionalFailureConfig:
    """Get appropriate configuration for the specified environment.

    Args:
        environment: Environment name (dev, qa, staging, prod, production)

    Returns:
        ConstitutionalFailureConfig appropriate for the environment
    """
    env_lower = environment.lower()
    if env_lower in ("dev", "development", "local"):
        return DEVELOPMENT_CONFIG
    elif env_lower in ("prod", "production"):
        return PRODUCTION_CONFIG
    elif env_lower in ("qa", "staging"):
        return STRICT_CONFIG
    else:
        # Default to production-like settings for unknown environments
        return PRODUCTION_CONFIG
