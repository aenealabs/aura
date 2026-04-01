"""
Tests for explainability configuration.
"""

from src.services.explainability.config import (
    AlternativesConfig,
    ConfidenceConfig,
    ConsistencyConfig,
    ExplainabilityConfig,
    InterAgentConfig,
    ReasoningChainConfig,
    configure_explainability,
    get_explainability_config,
    reset_explainability_config,
)


class TestExplainabilityConfig:
    """Tests for ExplainabilityConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExplainabilityConfig()

        # Check min reasoning steps
        assert config.min_reasoning_steps["trivial"] == 1
        assert config.min_reasoning_steps["normal"] == 2
        assert config.min_reasoning_steps["significant"] == 3
        assert config.min_reasoning_steps["critical"] == 5

        # Check min alternatives
        assert config.min_alternatives["trivial"] == 2
        assert config.min_alternatives["normal"] == 2
        assert config.min_alternatives["significant"] == 3
        assert config.min_alternatives["critical"] == 4

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExplainabilityConfig(
            min_reasoning_steps={"trivial": 2, "normal": 3},
            min_alternatives={"trivial": 3},
            consistency_threshold=0.9,
            low_confidence_threshold=0.6,
        )

        assert config.min_reasoning_steps["trivial"] == 2
        assert config.min_reasoning_steps["normal"] == 3
        assert config.min_alternatives["trivial"] == 3
        assert config.consistency_threshold == 0.9
        assert config.low_confidence_threshold == 0.6

    def test_get_min_reasoning_steps(self):
        """Test getting minimum reasoning steps for severity."""
        config = ExplainabilityConfig()

        # Config methods accept severity string or enum value
        assert config.get_min_reasoning_steps("trivial") == 1
        assert config.get_min_reasoning_steps("normal") == 2
        assert config.get_min_reasoning_steps("significant") == 3
        assert config.get_min_reasoning_steps("critical") == 5

    def test_get_min_alternatives(self):
        """Test getting minimum alternatives for severity."""
        config = ExplainabilityConfig()

        # Config methods accept severity string or enum value
        assert config.get_min_alternatives("trivial") == 2
        assert config.get_min_alternatives("normal") == 2
        assert config.get_min_alternatives("significant") == 3
        assert config.get_min_alternatives("critical") == 4

    def test_score_weights(self):
        """Test score weights sum to 1.0."""
        config = ExplainabilityConfig()

        total = (
            config.score_weights["reasoning_completeness"]
            + config.score_weights["alternatives_coverage"]
            + config.score_weights["confidence_calibration"]
            + config.score_weights["consistency_score"]
            + config.score_weights["inter_agent_trust"]
        )
        assert abs(total - 1.0) < 0.001


class TestReasoningChainConfig:
    """Tests for ReasoningChainConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ReasoningChainConfig()

        assert config.extraction_model == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.extraction_temperature == 0.1
        assert config.max_evidence_per_step == 5
        assert config.enable_llm_extraction is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ReasoningChainConfig(
            extraction_model="anthropic.claude-3-sonnet",
            extraction_temperature=0.5,
            max_evidence_per_step=10,
            enable_llm_extraction=False,
        )

        assert config.extraction_model == "anthropic.claude-3-sonnet"
        assert config.extraction_temperature == 0.5
        assert config.max_evidence_per_step == 10
        assert config.enable_llm_extraction is False


class TestAlternativesConfig:
    """Tests for AlternativesConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AlternativesConfig()

        assert config.analysis_model == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.analysis_temperature == 0.3
        assert config.max_alternatives == 6
        assert config.comparison_criteria_count == 5
        assert config.enable_llm_analysis is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AlternativesConfig(
            max_alternatives=10,
            comparison_criteria_count=8,
            enable_llm_analysis=False,
        )

        assert config.max_alternatives == 10
        assert config.comparison_criteria_count == 8
        assert config.enable_llm_analysis is False


class TestConfidenceConfig:
    """Tests for ConfidenceConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConfidenceConfig()

        assert config.default_calibration_method == "ensemble_disagreement"
        assert config.min_samples_for_mc == 5
        assert config.max_uncertainty_sources == 5
        assert config.calibration_temperature == 1.5

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConfidenceConfig(
            default_calibration_method="monte_carlo_dropout",
            min_samples_for_mc=10,
            max_uncertainty_sources=10,
        )

        assert config.default_calibration_method == "monte_carlo_dropout"
        assert config.min_samples_for_mc == 10
        assert config.max_uncertainty_sources == 10


class TestConsistencyConfig:
    """Tests for ConsistencyConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConsistencyConfig()

        assert config.verification_model == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.verification_temperature == 0.1
        assert config.max_claims_per_verification == 10
        assert config.enable_llm_verification is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConsistencyConfig(
            max_claims_per_verification=20,
            enable_llm_verification=False,
        )

        assert config.max_claims_per_verification == 20
        assert config.enable_llm_verification is False


class TestInterAgentConfig:
    """Tests for InterAgentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = InterAgentConfig()

        assert config.trust_adjustment_range == 0.2
        assert config.enable_cross_reference is True
        assert config.default_confidence_unverified == 0.3
        assert config.verification_timeout_seconds == 30.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = InterAgentConfig(
            trust_adjustment_range=0.3,
            enable_cross_reference=False,
            default_confidence_unverified=0.4,
        )

        assert config.trust_adjustment_range == 0.3
        assert config.enable_cross_reference is False
        assert config.default_confidence_unverified == 0.4


class TestGlobalConfigManagement:
    """Tests for global configuration management functions."""

    def setup_method(self):
        """Reset config before each test."""
        reset_explainability_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_explainability_config()

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = get_explainability_config()
        assert config is not None
        assert isinstance(config, ExplainabilityConfig)

    def test_configure_explainability(self):
        """Test configuring explainability."""
        custom_config = ExplainabilityConfig(
            consistency_threshold=0.9,
        )
        result = configure_explainability(custom_config)

        assert result.consistency_threshold == 0.9

        # Verify global config updated
        global_config = get_explainability_config()
        assert global_config.consistency_threshold == 0.9

    def test_reset_config(self):
        """Test resetting configuration."""
        # Configure with custom values
        custom_config = ExplainabilityConfig(consistency_threshold=0.9)
        configure_explainability(custom_config)

        # Reset
        reset_explainability_config()

        # Should get fresh default config
        config = get_explainability_config()
        assert config.consistency_threshold == 0.8  # Default value

    def test_config_persistence(self):
        """Test that configured values persist across calls."""
        custom_config = ExplainabilityConfig(
            low_confidence_threshold=0.7,
        )
        configure_explainability(custom_config)

        # Multiple gets should return same instance
        config1 = get_explainability_config()
        config2 = get_explainability_config()

        assert config1 is config2
        assert config1.low_confidence_threshold == 0.7
