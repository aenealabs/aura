"""Tests for Constitutional AI failure policy configuration.

This module tests the failure handling policies and configuration
for the Constitutional AI system.
"""

import os
from unittest.mock import patch

import pytest

from src.services.constitutional_ai.failure_policy import (
    DEVELOPMENT_CONFIG,
    LENIENT_CONFIG,
    PRODUCTION_CONFIG,
    STRICT_CONFIG,
    ConstitutionalFailureConfig,
    CritiqueFailurePolicy,
    RevisionFailurePolicy,
    get_config_for_environment,
    get_failure_config,
)

# =============================================================================
# CritiqueFailurePolicy Enum Tests
# =============================================================================


class TestCritiqueFailurePolicy:
    """Tests for CritiqueFailurePolicy enum."""

    def test_policy_values(self):
        """Test that all policy values are correct."""
        assert CritiqueFailurePolicy.BLOCK.value == "block"
        assert CritiqueFailurePolicy.PROCEED_LOGGED.value == "proceed_logged"
        assert CritiqueFailurePolicy.PROCEED_FLAGGED.value == "proceed_flagged"
        assert CritiqueFailurePolicy.RETRY_THEN_BLOCK.value == "retry_then_block"

    def test_from_string_valid(self):
        """Test from_string with valid values."""
        assert CritiqueFailurePolicy.from_string("block") == CritiqueFailurePolicy.BLOCK
        assert (
            CritiqueFailurePolicy.from_string("proceed_logged")
            == CritiqueFailurePolicy.PROCEED_LOGGED
        )
        assert (
            CritiqueFailurePolicy.from_string("proceed_flagged")
            == CritiqueFailurePolicy.PROCEED_FLAGGED
        )
        assert (
            CritiqueFailurePolicy.from_string("retry_then_block")
            == CritiqueFailurePolicy.RETRY_THEN_BLOCK
        )

    def test_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert CritiqueFailurePolicy.from_string("BLOCK") == CritiqueFailurePolicy.BLOCK
        assert (
            CritiqueFailurePolicy.from_string("Proceed_Flagged")
            == CritiqueFailurePolicy.PROCEED_FLAGGED
        )

    def test_from_string_invalid(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError) as exc_info:
            CritiqueFailurePolicy.from_string("invalid_policy")
        assert "Invalid critique failure policy" in str(exc_info.value)

    def test_policy_count(self):
        """Test that there are exactly 4 critique failure policies."""
        assert len(CritiqueFailurePolicy) == 4


# =============================================================================
# RevisionFailurePolicy Enum Tests
# =============================================================================


class TestRevisionFailurePolicy:
    """Tests for RevisionFailurePolicy enum."""

    def test_policy_values(self):
        """Test that all policy values are correct."""
        assert RevisionFailurePolicy.RETURN_ORIGINAL.value == "return_original"
        assert RevisionFailurePolicy.RETURN_BEST_EFFORT.value == "return_best_effort"
        assert RevisionFailurePolicy.BLOCK_FOR_HITL.value == "block_for_hitl"

    def test_from_string_valid(self):
        """Test from_string with valid values."""
        assert (
            RevisionFailurePolicy.from_string("return_original")
            == RevisionFailurePolicy.RETURN_ORIGINAL
        )
        assert (
            RevisionFailurePolicy.from_string("return_best_effort")
            == RevisionFailurePolicy.RETURN_BEST_EFFORT
        )
        assert (
            RevisionFailurePolicy.from_string("block_for_hitl")
            == RevisionFailurePolicy.BLOCK_FOR_HITL
        )

    def test_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert (
            RevisionFailurePolicy.from_string("BLOCK_FOR_HITL")
            == RevisionFailurePolicy.BLOCK_FOR_HITL
        )

    def test_from_string_invalid(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError) as exc_info:
            RevisionFailurePolicy.from_string("invalid_policy")
        assert "Invalid revision failure policy" in str(exc_info.value)

    def test_policy_count(self):
        """Test that there are exactly 3 revision failure policies."""
        assert len(RevisionFailurePolicy) == 3


# =============================================================================
# ConstitutionalFailureConfig Tests
# =============================================================================


class TestConstitutionalFailureConfig:
    """Tests for ConstitutionalFailureConfig dataclass."""

    def test_default_values(self, default_failure_config):
        """Test default configuration values."""
        assert (
            default_failure_config.critique_failure_policy
            == CritiqueFailurePolicy.PROCEED_FLAGGED
        )
        assert (
            default_failure_config.revision_failure_policy
            == RevisionFailurePolicy.BLOCK_FOR_HITL
        )
        assert default_failure_config.max_critique_retries == 2
        assert default_failure_config.critique_retry_delay_ms == 500
        assert default_failure_config.critique_timeout_seconds == 30.0
        assert default_failure_config.revision_timeout_seconds == 60.0
        assert default_failure_config.max_revision_iterations == 3
        assert default_failure_config.require_audit_trail is True
        assert default_failure_config.audit_failure_blocks_execution is False
        assert default_failure_config.enable_metrics is True

    def test_strict_config(self, strict_failure_config):
        """Test strict configuration values."""
        assert (
            strict_failure_config.critique_failure_policy == CritiqueFailurePolicy.BLOCK
        )
        assert (
            strict_failure_config.revision_failure_policy
            == RevisionFailurePolicy.BLOCK_FOR_HITL
        )
        assert strict_failure_config.max_critique_retries == 3
        assert strict_failure_config.max_revision_iterations == 5
        assert strict_failure_config.audit_failure_blocks_execution is True

    def test_lenient_config(self, lenient_failure_config):
        """Test lenient configuration values."""
        assert (
            lenient_failure_config.critique_failure_policy
            == CritiqueFailurePolicy.PROCEED_LOGGED
        )
        assert (
            lenient_failure_config.revision_failure_policy
            == RevisionFailurePolicy.RETURN_BEST_EFFORT
        )
        assert lenient_failure_config.max_critique_retries == 1
        assert lenient_failure_config.require_audit_trail is False

    def test_validation_negative_retries(self):
        """Test that negative max_critique_retries raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalFailureConfig(max_critique_retries=-1)
        assert "max_critique_retries must be non-negative" in str(exc_info.value)

    def test_validation_negative_retry_delay(self):
        """Test that negative critique_retry_delay_ms raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalFailureConfig(critique_retry_delay_ms=-1)
        assert "critique_retry_delay_ms must be non-negative" in str(exc_info.value)

    def test_validation_zero_critique_timeout(self):
        """Test that zero critique_timeout_seconds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalFailureConfig(critique_timeout_seconds=0)
        assert "critique_timeout_seconds must be positive" in str(exc_info.value)

    def test_validation_zero_revision_timeout(self):
        """Test that zero revision_timeout_seconds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalFailureConfig(revision_timeout_seconds=0)
        assert "revision_timeout_seconds must be positive" in str(exc_info.value)

    def test_validation_zero_max_iterations(self):
        """Test that zero max_revision_iterations raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalFailureConfig(max_revision_iterations=0)
        assert "max_revision_iterations must be at least 1" in str(exc_info.value)

    def test_to_dict(self, default_failure_config):
        """Test configuration serialization to dict."""
        data = default_failure_config.to_dict()
        assert data["critique_failure_policy"] == "proceed_flagged"
        assert data["revision_failure_policy"] == "block_for_hitl"
        assert data["max_critique_retries"] == 2
        assert "critique_timeout_seconds" in data

    def test_from_dict(self):
        """Test configuration deserialization from dict."""
        data = {
            "critique_failure_policy": "block",
            "revision_failure_policy": "return_original",
            "max_critique_retries": 5,
            "max_revision_iterations": 10,
        }
        config = ConstitutionalFailureConfig.from_dict(data)
        assert config.critique_failure_policy == CritiqueFailurePolicy.BLOCK
        assert config.revision_failure_policy == RevisionFailurePolicy.RETURN_ORIGINAL
        assert config.max_critique_retries == 5

    def test_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing values."""
        config = ConstitutionalFailureConfig.from_dict({})
        assert config.critique_failure_policy == CritiqueFailurePolicy.PROCEED_FLAGGED
        assert config.max_critique_retries == 2


# =============================================================================
# get_failure_config Tests
# =============================================================================


class TestGetFailureConfig:
    """Tests for get_failure_config function."""

    def test_default_config(self):
        """Test get_failure_config returns defaults without env vars."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_failure_config()
            assert (
                config.critique_failure_policy == CritiqueFailurePolicy.PROCEED_FLAGGED
            )
            assert (
                config.revision_failure_policy == RevisionFailurePolicy.BLOCK_FOR_HITL
            )

    def test_env_critique_policy(self):
        """Test critique policy from environment variable."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_CRITIQUE_FAILURE_POLICY": "block"},
            clear=True,
        ):
            config = get_failure_config()
            assert config.critique_failure_policy == CritiqueFailurePolicy.BLOCK

    def test_env_revision_policy(self):
        """Test revision policy from environment variable."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_REVISION_FAILURE_POLICY": "return_original"},
            clear=True,
        ):
            config = get_failure_config()
            assert (
                config.revision_failure_policy == RevisionFailurePolicy.RETURN_ORIGINAL
            )

    def test_env_max_retries(self):
        """Test max retries from environment variable."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_MAX_CRITIQUE_RETRIES": "5"},
            clear=True,
        ):
            config = get_failure_config()
            assert config.max_critique_retries == 5

    def test_env_boolean_true(self):
        """Test boolean true from environment variable."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_AUDIT_FAILURE_BLOCKS": "true"},
            clear=True,
        ):
            config = get_failure_config()
            assert config.audit_failure_blocks_execution is True

    def test_env_boolean_false(self):
        """Test boolean false from environment variable."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_REQUIRE_AUDIT_TRAIL": "false"},
            clear=True,
        ):
            config = get_failure_config()
            assert config.require_audit_trail is False

    def test_env_invalid_policy_uses_default(self):
        """Test that invalid policy in env uses default."""
        with patch.dict(
            os.environ,
            {"CONSTITUTIONAL_AI_CRITIQUE_FAILURE_POLICY": "invalid"},
            clear=True,
        ):
            config = get_failure_config()
            assert (
                config.critique_failure_policy == CritiqueFailurePolicy.PROCEED_FLAGGED
            )


# =============================================================================
# get_config_for_environment Tests
# =============================================================================


class TestGetConfigForEnvironment:
    """Tests for get_config_for_environment function."""

    def test_dev_environment(self):
        """Test configuration for dev environment."""
        config = get_config_for_environment("dev")
        assert config.require_audit_trail is False
        assert config.enable_metrics is False

    def test_development_environment(self):
        """Test configuration for development environment."""
        config = get_config_for_environment("development")
        assert config.require_audit_trail is False

    def test_production_environment(self):
        """Test configuration for production environment."""
        config = get_config_for_environment("prod")
        assert config.require_audit_trail is True
        assert config.audit_failure_blocks_execution is True
        assert config.enable_metrics is True

    def test_qa_environment(self):
        """Test configuration for qa environment."""
        config = get_config_for_environment("qa")
        assert config.require_audit_trail is True
        assert config.max_critique_retries == 3

    def test_staging_environment(self):
        """Test configuration for staging environment."""
        config = get_config_for_environment("staging")
        assert config.max_revision_iterations == 5

    def test_unknown_environment_uses_production(self):
        """Test that unknown environment uses production config."""
        config = get_config_for_environment("unknown")
        assert config.require_audit_trail is True
        assert config.audit_failure_blocks_execution is True


# =============================================================================
# Pre-defined Configuration Tests
# =============================================================================


class TestPredefinedConfigs:
    """Tests for pre-defined configuration constants."""

    def test_strict_config_exists(self):
        """Test STRICT_CONFIG is properly defined."""
        assert (
            STRICT_CONFIG.critique_failure_policy
            == CritiqueFailurePolicy.RETRY_THEN_BLOCK
        )
        assert STRICT_CONFIG.audit_failure_blocks_execution is True

    def test_lenient_config_exists(self):
        """Test LENIENT_CONFIG is properly defined."""
        assert (
            LENIENT_CONFIG.critique_failure_policy
            == CritiqueFailurePolicy.PROCEED_LOGGED
        )
        assert (
            LENIENT_CONFIG.revision_failure_policy
            == RevisionFailurePolicy.RETURN_BEST_EFFORT
        )

    def test_development_config_exists(self):
        """Test DEVELOPMENT_CONFIG is properly defined."""
        assert DEVELOPMENT_CONFIG.enable_metrics is False
        assert DEVELOPMENT_CONFIG.require_audit_trail is False
        assert DEVELOPMENT_CONFIG.critique_timeout_seconds == 60.0

    def test_production_config_exists(self):
        """Test PRODUCTION_CONFIG is properly defined."""
        assert PRODUCTION_CONFIG.enable_metrics is True
        assert PRODUCTION_CONFIG.require_audit_trail is True
        assert PRODUCTION_CONFIG.critique_timeout_seconds == 30.0
