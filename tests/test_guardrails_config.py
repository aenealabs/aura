"""
Unit Tests for Bedrock Guardrails Configuration (ADR-029)
Tests guardrail configuration, environment settings, and trace parsing.
"""

import os
from unittest.mock import MagicMock

import pytest

from src.config.guardrails_config import (
    DEFAULT_BLOCKED_TOPICS,
    DEFAULT_CONTENT_FILTERS,
    DEFAULT_PII_ENTITIES,
    DEFAULT_SENSITIVE_PATTERNS,
    ContentFilterConfig,
    ContentFilterStrength,
    GuardrailConfig,
    GuardrailEnvironment,
    GuardrailMode,
    GuardrailResult,
    PIIAction,
    PIIEntityConfig,
    TopicConfig,
    format_guardrail_trace,
    get_guardrail_config,
    get_guardrail_environment,
    load_guardrail_ids_from_ssm,
)


class TestGuardrailEnvironment:
    """Test environment detection for guardrails."""

    def test_default_environment_is_dev(self):
        """Test default environment is dev when AURA_ENV not set."""
        if "AURA_ENV" in os.environ:
            del os.environ["AURA_ENV"]
        env = get_guardrail_environment()
        assert env == GuardrailEnvironment.DEV

    def test_dev_environment_detection(self):
        """Test dev environment is detected correctly."""
        for env_str in ["dev", "development"]:
            os.environ["AURA_ENV"] = env_str
            assert get_guardrail_environment() == GuardrailEnvironment.DEV

    def test_qa_environment_detection(self):
        """Test qa environment is detected correctly."""
        os.environ["AURA_ENV"] = "qa"
        assert get_guardrail_environment() == GuardrailEnvironment.QA

    def test_staging_environment_detection(self):
        """Test staging environment is detected correctly."""
        for env_str in ["staging", "stage"]:
            os.environ["AURA_ENV"] = env_str
            assert get_guardrail_environment() == GuardrailEnvironment.STAGING

    def test_prod_environment_detection(self):
        """Test production environment is detected correctly."""
        for env_str in ["prod", "production"]:
            os.environ["AURA_ENV"] = env_str
            assert get_guardrail_environment() == GuardrailEnvironment.PROD


class TestGuardrailConfig:
    """Test guardrail configuration loading."""

    def setup_method(self):
        """Reset environment before each test."""
        os.environ["AURA_ENV"] = "dev"

    def test_dev_config_mode(self):
        """Test dev environment uses DETECT mode."""
        config = get_guardrail_config(GuardrailEnvironment.DEV)
        assert config.mode == GuardrailMode.DETECT

    def test_qa_config_mode(self):
        """Test qa environment uses ENFORCE mode."""
        config = get_guardrail_config(GuardrailEnvironment.QA)
        assert config.mode == GuardrailMode.ENFORCE

    def test_prod_config_mode(self):
        """Test prod environment uses ENFORCE mode."""
        config = get_guardrail_config(GuardrailEnvironment.PROD)
        assert config.mode == GuardrailMode.ENFORCE

    def test_dev_automated_reasoning_disabled(self):
        """Test dev environment has automated reasoning disabled by default."""
        config = get_guardrail_config(GuardrailEnvironment.DEV)
        assert config.automated_reasoning_enabled is False

    def test_prod_automated_reasoning_enabled(self):
        """Test prod environment has automated reasoning enabled."""
        config = get_guardrail_config(GuardrailEnvironment.PROD)
        assert config.automated_reasoning_enabled is True

    def test_config_has_content_filters(self):
        """Test all environments have content filters."""
        for env in GuardrailEnvironment:
            config = get_guardrail_config(env)
            assert len(config.content_filters) > 0
            assert any(
                cf.filter_type == "PROMPT_ATTACK" for cf in config.content_filters
            )

    def test_config_has_pii_entities(self):
        """Test all environments have PII entity configurations."""
        for env in GuardrailEnvironment:
            config = get_guardrail_config(env)
            assert len(config.pii_entities) > 0
            # Must block AWS credentials
            assert any(
                pii.entity_type == "AWS_ACCESS_KEY" and pii.action == PIIAction.BLOCK
                for pii in config.pii_entities
            )

    def test_config_has_blocked_topics(self):
        """Test all environments have blocked topics."""
        for env in GuardrailEnvironment:
            config = get_guardrail_config(env)
            assert len(config.blocked_topics) > 0
            # Must block malware creation
            assert any(
                topic.name == "malware-creation" for topic in config.blocked_topics
            )

    def test_ssm_parameter_prefix_per_env(self):
        """Test SSM parameter prefix differs per environment."""
        dev_config = get_guardrail_config(GuardrailEnvironment.DEV)
        prod_config = get_guardrail_config(GuardrailEnvironment.PROD)

        assert "/dev/" in dev_config.ssm_parameter_prefix
        assert "/prod/" in prod_config.ssm_parameter_prefix


class TestDefaultConfigurations:
    """Test default guardrail configurations."""

    def test_default_content_filters_count(self):
        """Test default content filters include all required types."""
        assert len(DEFAULT_CONTENT_FILTERS) >= 6
        filter_types = {cf.filter_type for cf in DEFAULT_CONTENT_FILTERS}
        assert "HATE" in filter_types
        assert "SEXUAL" in filter_types
        assert "VIOLENCE" in filter_types
        assert "PROMPT_ATTACK" in filter_types

    def test_prompt_attack_filter_config(self):
        """Test prompt attack filter has correct configuration."""
        prompt_filter = next(
            (cf for cf in DEFAULT_CONTENT_FILTERS if cf.filter_type == "PROMPT_ATTACK"),
            None,
        )
        assert prompt_filter is not None
        # High on input to block injection attempts
        assert prompt_filter.input_strength == ContentFilterStrength.HIGH
        # None on output (responses don't contain prompt attacks)
        assert prompt_filter.output_strength == ContentFilterStrength.NONE

    def test_default_pii_entities_block_credentials(self):
        """Test default PII entities block sensitive credentials."""
        block_entities = {
            pii.entity_type
            for pii in DEFAULT_PII_ENTITIES
            if pii.action == PIIAction.BLOCK
        }
        assert "US_SOCIAL_SECURITY_NUMBER" in block_entities
        assert "CREDIT_DEBIT_CARD_NUMBER" in block_entities
        assert "AWS_ACCESS_KEY" in block_entities
        assert "AWS_SECRET_KEY" in block_entities

    def test_default_pii_entities_anonymize_contact_info(self):
        """Test default PII entities anonymize contact information."""
        anonymize_entities = {
            pii.entity_type
            for pii in DEFAULT_PII_ENTITIES
            if pii.action == PIIAction.ANONYMIZE
        }
        assert "EMAIL" in anonymize_entities
        assert "PHONE" in anonymize_entities
        assert "IP_ADDRESS" in anonymize_entities

    def test_default_blocked_topics(self):
        """Test default blocked topics include security threats."""
        topic_names = {topic.name for topic in DEFAULT_BLOCKED_TOPICS}
        assert "malware-creation" in topic_names
        assert "social-engineering" in topic_names
        assert "credential-theft" in topic_names

    def test_default_sensitive_patterns(self):
        """Test default sensitive patterns detect secrets."""
        pattern_names = {p["name"] for p in DEFAULT_SENSITIVE_PATTERNS}
        assert "api-key-pattern" in pattern_names
        assert "jwt-token-pattern" in pattern_names
        assert "private-key-pattern" in pattern_names


class TestSSMParameterLoading:
    """Test SSM parameter loading for guardrail IDs."""

    def test_load_guardrail_ids_disabled_mode(self):
        """Test SSM loading is skipped when guardrails disabled."""
        config = GuardrailConfig(mode=GuardrailMode.DISABLED)
        result = load_guardrail_ids_from_ssm(config)
        assert result.guardrail_id is None

    def test_load_guardrail_ids_success(self):
        """Test successful SSM parameter loading."""
        config = GuardrailConfig(
            mode=GuardrailMode.ENFORCE,
            ssm_parameter_prefix="/aura/test/guardrails",
        )

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = [
            {"Parameter": {"Value": "test-guardrail-id-123"}},
            {"Parameter": {"Value": "1"}},
        ]

        result = load_guardrail_ids_from_ssm(config, ssm_client=mock_ssm)

        assert result.guardrail_id == "test-guardrail-id-123"
        assert result.guardrail_version == "1"

    def test_load_guardrail_ids_parameter_not_found(self):
        """Test SSM loading handles missing parameters gracefully."""
        config = GuardrailConfig(
            mode=GuardrailMode.ENFORCE,
            ssm_parameter_prefix="/aura/test/guardrails",
        )

        # Mock SSM client with ParameterNotFound exception
        mock_ssm = MagicMock()
        mock_ssm.exceptions.ParameterNotFound = Exception
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound

        result = load_guardrail_ids_from_ssm(config, ssm_client=mock_ssm)

        # Should still return config with None values
        assert result.guardrail_id is None


class TestGuardrailTraceFormatting:
    """Test guardrail trace parsing and formatting."""

    def test_format_empty_trace(self):
        """Test formatting empty trace returns empty list."""
        violations = format_guardrail_trace({})
        assert violations == []

    def test_format_none_trace(self):
        """Test formatting None trace returns empty list."""
        violations = format_guardrail_trace(None)
        assert violations == []

    def test_format_topic_violation(self):
        """Test formatting topic policy violation."""
        trace = {
            "inputAssessments": [
                {
                    "topicPolicy": {
                        "topics": [{"name": "malware-creation", "action": "BLOCKED"}]
                    }
                }
            ]
        }

        violations = format_guardrail_trace(trace)

        assert len(violations) == 1
        assert violations[0]["type"] == "topic"
        assert violations[0]["name"] == "malware-creation"
        assert violations[0]["direction"] == "input"
        assert violations[0]["action"] == "blocked"

    def test_format_content_violation(self):
        """Test formatting content policy violation."""
        trace = {
            "outputAssessments": [
                {
                    "contentPolicy": {
                        "filters": [
                            {
                                "type": "VIOLENCE",
                                "action": "BLOCKED",
                                "confidence": "HIGH",
                            }
                        ]
                    }
                }
            ]
        }

        violations = format_guardrail_trace(trace)

        assert len(violations) == 1
        assert violations[0]["type"] == "content"
        assert violations[0]["category"] == "VIOLENCE"
        assert violations[0]["direction"] == "output"
        assert violations[0]["confidence"] == "HIGH"

    def test_format_pii_detection(self):
        """Test formatting PII detection."""
        trace = {
            "outputAssessments": [
                {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [
                            {
                                "type": "EMAIL",
                                "action": "ANONYMIZED",
                                "match": "test@example.com",
                            }
                        ]
                    }
                }
            ]
        }

        violations = format_guardrail_trace(trace)

        assert len(violations) == 1
        assert violations[0]["type"] == "pii"
        assert violations[0]["entity_type"] == "EMAIL"
        assert violations[0]["action"] == "anonymized"

    def test_format_multiple_violations(self):
        """Test formatting multiple violations from different sources."""
        trace = {
            "inputAssessments": [
                {
                    "topicPolicy": {
                        "topics": [{"name": "malware-creation", "action": "BLOCKED"}]
                    },
                    "contentPolicy": {
                        "filters": [
                            {
                                "type": "PROMPT_ATTACK",
                                "action": "BLOCKED",
                                "confidence": "HIGH",
                            }
                        ]
                    },
                }
            ],
            "outputAssessments": [
                {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [{"type": "AWS_ACCESS_KEY", "action": "BLOCKED"}]
                    }
                }
            ],
        }

        violations = format_guardrail_trace(trace)

        assert len(violations) == 3
        assert any(v["type"] == "topic" for v in violations)
        assert any(v["type"] == "content" for v in violations)
        assert any(v["type"] == "pii" for v in violations)


class TestGuardrailResult:
    """Test GuardrailResult dataclass."""

    def test_result_passed_no_violations(self):
        """Test result with no violations."""
        result = GuardrailResult(
            passed=True,
            action_taken="none",
            violations=[],
        )
        assert result.passed is True
        assert result.action_taken == "none"
        assert len(result.violations) == 0

    def test_result_blocked_with_violations(self):
        """Test result with blocked content."""
        violations = [
            {"type": "topic", "name": "malware-creation", "action": "blocked"}
        ]
        result = GuardrailResult(
            passed=False,
            action_taken="blocked",
            violations=violations,
            guardrail_id="test-guardrail",
        )
        assert result.passed is False
        assert result.action_taken == "blocked"
        assert len(result.violations) == 1
        assert result.guardrail_id == "test-guardrail"


class TestContentFilterConfig:
    """Test ContentFilterConfig dataclass."""

    def test_create_content_filter(self):
        """Test creating a content filter configuration."""
        cf = ContentFilterConfig(
            filter_type="HATE",
            input_strength=ContentFilterStrength.HIGH,
            output_strength=ContentFilterStrength.HIGH,
        )
        assert cf.filter_type == "HATE"
        assert cf.input_strength == ContentFilterStrength.HIGH
        assert cf.output_strength == ContentFilterStrength.HIGH


class TestPIIEntityConfig:
    """Test PIIEntityConfig dataclass."""

    def test_create_pii_block_config(self):
        """Test creating a PII block configuration."""
        pii = PIIEntityConfig(
            entity_type="US_SOCIAL_SECURITY_NUMBER",
            action=PIIAction.BLOCK,
        )
        assert pii.entity_type == "US_SOCIAL_SECURITY_NUMBER"
        assert pii.action == PIIAction.BLOCK

    def test_create_pii_anonymize_config(self):
        """Test creating a PII anonymize configuration."""
        pii = PIIEntityConfig(
            entity_type="EMAIL",
            action=PIIAction.ANONYMIZE,
        )
        assert pii.entity_type == "EMAIL"
        assert pii.action == PIIAction.ANONYMIZE


class TestTopicConfig:
    """Test TopicConfig dataclass."""

    def test_create_topic_config(self):
        """Test creating a topic configuration."""
        topic = TopicConfig(
            name="test-topic",
            definition="Test topic definition",
            examples=["Example 1", "Example 2"],
        )
        assert topic.name == "test-topic"
        assert topic.definition == "Test topic definition"
        assert len(topic.examples) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
