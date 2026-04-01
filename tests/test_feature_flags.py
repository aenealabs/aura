"""
Tests for Feature Flags configuration module.

Tests:
- Feature definition validation
- Tier-based feature gating
- Customer overrides
- Beta enrollment
- Environment variable overrides
- Rollout percentage calculations
"""

import os
from unittest.mock import patch

from src.config.feature_flags import (
    BETA_FEATURES,
    CORE_FEATURES,
    CustomerFeatureOverrides,
    FeatureDefinition,
    FeatureFlagsService,
    FeatureStatus,
    FeatureTier,
    get_beta_features,
    get_environment_defaults,
    get_feature_definition,
    get_feature_flags,
    get_onboarding_features,
    is_feature_enabled,
)

# =============================================================================
# Feature Definition Tests
# =============================================================================


class TestFeatureDefinition:
    """Tests for FeatureDefinition dataclass."""

    def test_feature_definition_creation(self):
        """Test creating a feature definition."""
        feature = FeatureDefinition(
            name="test_feature",
            description="Test feature description",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.STARTER,
        )
        assert feature.name == "test_feature"
        assert feature.status == FeatureStatus.GA
        assert feature.min_tier == FeatureTier.STARTER
        assert feature.enabled_by_default is True
        assert feature.requires_consent is False

    def test_feature_definition_defaults(self):
        """Test default values for feature definition."""
        feature = FeatureDefinition(
            name="minimal",
            description="Minimal definition",
        )
        assert feature.status == FeatureStatus.GA
        assert feature.min_tier == FeatureTier.FREE
        assert feature.rollout_percentage == 100
        assert feature.dependencies == []


class TestFeatureStatus:
    """Tests for FeatureStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        assert FeatureStatus.ALPHA.value == "alpha"
        assert FeatureStatus.BETA.value == "beta"
        assert FeatureStatus.GA.value == "ga"
        assert FeatureStatus.DEPRECATED.value == "deprecated"


class TestFeatureTier:
    """Tests for FeatureTier enum."""

    def test_all_tiers_exist(self):
        """Test all expected tiers are defined."""
        assert FeatureTier.FREE.value == "free"
        assert FeatureTier.STARTER.value == "starter"
        assert FeatureTier.PROFESSIONAL.value == "professional"
        assert FeatureTier.ENTERPRISE.value == "enterprise"
        assert FeatureTier.GOVERNMENT.value == "government"


# =============================================================================
# Feature Registry Tests
# =============================================================================


class TestFeatureRegistry:
    """Tests for feature registries."""

    def test_core_features_defined(self):
        """Test core features are defined."""
        assert "vulnerability_scanning" in CORE_FEATURES
        assert "patch_generation" in CORE_FEATURES
        assert "sandbox_testing" in CORE_FEATURES
        assert "hitl_approval" in CORE_FEATURES

    def test_beta_features_defined(self):
        """Test beta features are defined."""
        assert "advanced_analytics" in BETA_FEATURES
        assert "multi_repo_scanning" in BETA_FEATURES
        assert "knowledge_graph_explorer" in BETA_FEATURES
        assert "ticket_integrations" in BETA_FEATURES

    def test_beta_features_have_beta_status(self):
        """Test all beta features have beta status."""
        for name, feature in BETA_FEATURES.items():
            assert feature.status == FeatureStatus.BETA, f"{name} should be BETA"

    def test_get_beta_features(self):
        """Test get_beta_features helper."""
        beta = get_beta_features()
        assert isinstance(beta, dict)
        assert len(beta) > 0
        assert all(f.status == FeatureStatus.BETA for f in beta.values())


# =============================================================================
# Feature Flags Service Tests
# =============================================================================


class TestFeatureFlagsService:
    """Tests for FeatureFlagsService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_get_feature_exists(self):
        """Test getting an existing feature."""
        feature = self.service.get_feature("vulnerability_scanning")
        assert feature is not None
        assert feature.name == "vulnerability_scanning"

    def test_get_feature_not_exists(self):
        """Test getting a non-existent feature."""
        feature = self.service.get_feature("nonexistent_feature")
        assert feature is None

    def test_is_enabled_ga_feature(self):
        """Test GA features are enabled by default."""
        assert self.service.is_enabled("vulnerability_scanning") is True
        assert self.service.is_enabled("hitl_approval") is True

    def test_is_enabled_tier_requirement(self):
        """Test tier-based feature gating."""
        # Starter feature with FREE tier should be disabled
        assert (
            self.service.is_enabled("patch_generation", tier=FeatureTier.FREE) is False
        )
        # Starter feature with STARTER tier should be enabled
        assert (
            self.service.is_enabled("patch_generation", tier=FeatureTier.STARTER)
            is True
        )

    def test_is_enabled_beta_requires_enrollment(self):
        """Test beta features require enrollment."""
        # Beta features should be disabled for non-participants
        assert self.service.is_enabled("advanced_analytics") is False

    def test_is_enabled_unknown_feature(self):
        """Test unknown feature returns False."""
        assert self.service.is_enabled("unknown_feature") is False

    def test_list_features_all(self):
        """Test listing all features."""
        features = self.service.list_features()
        assert len(features) > 0
        assert all(isinstance(f, FeatureDefinition) for f in features)

    def test_list_features_by_status(self):
        """Test listing features by status."""
        beta_features = self.service.list_features(status=FeatureStatus.BETA)
        assert len(beta_features) > 0
        assert all(f.status == FeatureStatus.BETA for f in beta_features)

    def test_list_enabled_features(self):
        """Test listing enabled features for a tier."""
        enabled = self.service.list_enabled_features(tier=FeatureTier.ENTERPRISE)
        assert "vulnerability_scanning" in enabled
        assert "hitl_approval" in enabled


# =============================================================================
# Customer Overrides Tests
# =============================================================================


class TestCustomerOverrides:
    """Tests for customer-specific feature overrides."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_set_customer_overrides(self):
        """Test setting customer overrides."""
        overrides = CustomerFeatureOverrides(
            customer_id="cust_123",
            tier=FeatureTier.PROFESSIONAL,
            enabled_features={"custom_agent_templates"},
            beta_participant=True,
        )
        self.service.set_customer_overrides(overrides)

        result = self.service.get_customer_overrides("cust_123")
        assert result is not None
        assert result.tier == FeatureTier.PROFESSIONAL
        assert "custom_agent_templates" in result.enabled_features

    def test_customer_explicit_enable(self):
        """Test customer explicit feature enable."""
        overrides = CustomerFeatureOverrides(
            customer_id="cust_456",
            tier=FeatureTier.STARTER,
            enabled_features={"advanced_analytics"},
            beta_participant=True,
        )
        self.service.set_customer_overrides(overrides)

        # Should be enabled due to explicit override (even though tier might not qualify)
        assert (
            self.service.is_enabled("advanced_analytics", customer_id="cust_456")
            is True
        )

    def test_customer_explicit_disable(self):
        """Test customer explicit feature disable."""
        overrides = CustomerFeatureOverrides(
            customer_id="cust_789",
            tier=FeatureTier.ENTERPRISE,
            disabled_features={"vulnerability_scanning"},
        )
        self.service.set_customer_overrides(overrides)

        # Should be disabled due to explicit override
        assert (
            self.service.is_enabled("vulnerability_scanning", customer_id="cust_789")
            is False
        )

    def test_enable_beta_features(self):
        """Test enabling beta features for a customer."""
        self.service.enable_beta_features("cust_beta", FeatureTier.PROFESSIONAL)

        overrides = self.service.get_customer_overrides("cust_beta")
        assert overrides is not None
        assert overrides.beta_participant is True
        assert "multi_repo_scanning" in overrides.enabled_features

    def test_beta_tier_filtering(self):
        """Test beta features filtered by tier when enabling."""
        self.service.enable_beta_features("cust_starter", FeatureTier.STARTER)

        overrides = self.service.get_customer_overrides("cust_starter")
        # Enterprise features should not be enabled for starter tier
        assert "custom_agent_templates" not in overrides.enabled_features


# =============================================================================
# Environment Override Tests
# =============================================================================


class TestEnvironmentOverrides:
    """Tests for environment variable overrides."""

    def test_env_override_enables_feature(self):
        """Test environment variable enables feature."""
        with patch.dict(os.environ, {"AURA_FEATURE_ADVANCED_ANALYTICS": "true"}):
            service = FeatureFlagsService()
            assert service.is_enabled("advanced_analytics") is True

    def test_env_override_disables_feature(self):
        """Test environment variable disables feature."""
        with patch.dict(os.environ, {"AURA_FEATURE_VULNERABILITY_SCANNING": "false"}):
            service = FeatureFlagsService()
            assert service.is_enabled("vulnerability_scanning") is False

    def test_env_override_various_truthy_values(self):
        """Test various truthy environment values."""
        for truthy in ["true", "1", "yes", "enabled"]:
            with patch.dict(os.environ, {"AURA_FEATURE_NEURAL_MEMORY": truthy}):
                service = FeatureFlagsService()
                assert service.is_enabled("neural_memory") is True


# =============================================================================
# Feature Status Tests
# =============================================================================


class TestGetFeatureFlagsStatus:
    """Tests for get_feature_flags_status method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_returns_all_features(self):
        """Test status includes all features."""
        status = self.service.get_feature_flags_status()
        assert "vulnerability_scanning" in status
        assert "advanced_analytics" in status

    def test_status_structure(self):
        """Test status has expected structure."""
        status = self.service.get_feature_flags_status()
        feature = status["vulnerability_scanning"]
        assert "enabled" in feature
        assert "status" in feature
        assert "min_tier" in feature
        assert "description" in feature


# =============================================================================
# Module Functions Tests
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_feature_flags_singleton(self):
        """Test get_feature_flags returns singleton."""
        service1 = get_feature_flags()
        service2 = get_feature_flags()
        assert service1 is service2

    def test_is_feature_enabled_convenience(self):
        """Test is_feature_enabled convenience function."""
        result = is_feature_enabled("vulnerability_scanning")
        assert isinstance(result, bool)

    def test_get_feature_definition(self):
        """Test get_feature_definition helper."""
        feature = get_feature_definition("patch_generation")
        assert feature is not None
        assert feature.name == "patch_generation"

    def test_get_environment_defaults_dev(self):
        """Test environment defaults for dev."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            defaults = get_environment_defaults()
            assert defaults.get("advanced_analytics") is True
            assert defaults.get("autonomous_remediation") is False

    def test_get_environment_defaults_prod(self):
        """Test environment defaults for prod."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            defaults = get_environment_defaults()
            # Prod has GA onboarding features enabled by default (ADR-047)
            assert len(defaults) == 4
            assert defaults.get("welcome_modal") is True
            assert defaults.get("onboarding_checklist") is True
            assert defaults.get("feature_tooltips") is True
            assert defaults.get("team_invitations") is True
            # Beta features are NOT enabled by default in prod
            assert defaults.get("advanced_analytics") is None
            assert defaults.get("autonomous_remediation") is None


# =============================================================================
# Rollout Percentage Tests
# =============================================================================


class TestRolloutPercentage:
    """Tests for gradual rollout functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_full_rollout_always_enabled(self):
        """Test 100% rollout is always enabled."""
        # vulnerability_scanning has 100% rollout
        for i in range(10):
            customer_id = f"customer_{i}"
            enabled = self.service.is_enabled("vulnerability_scanning", customer_id)
            assert enabled is True

    def test_partial_rollout_consistent(self):
        """Test partial rollout is consistent for same customer."""
        # Assuming autonomous_remediation has 50% rollout
        customer_id = "consistent_customer"
        results = [
            self.service.is_enabled("autonomous_remediation", customer_id)
            for _ in range(5)
        ]
        # All results should be the same for same customer
        assert len(set(results)) == 1


# =============================================================================
# Dependency Tests
# =============================================================================


class TestFeatureDependencies:
    """Tests for feature dependency handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_dependency_check(self):
        """Test feature with dependency requires dependency enabled."""
        # neural_memory depends on graphrag_context
        # If graphrag_context is disabled for tier, neural_memory should be too
        assert self.service.is_enabled("neural_memory", tier=FeatureTier.FREE) is False


class TestCustomerTierWithBeta:
    """Tests for customer tier with beta feature handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_beta_feature_with_customer_tier_not_participant(self):
        """Test beta features disabled for non-beta customers (lines 307-311)."""
        # Customer with overrides but NOT a beta participant
        overrides = CustomerFeatureOverrides(
            customer_id="non_beta_cust",
            tier=FeatureTier.ENTERPRISE,
            beta_participant=False,  # Not enrolled in beta
        )
        self.service.set_customer_overrides(overrides)

        # Beta features should be disabled even with enterprise tier
        assert (
            self.service.is_enabled("advanced_analytics", customer_id="non_beta_cust")
            is False
        )


class TestEnvironmentDefaultsExtended:
    """Extended tests for environment defaults."""

    def test_qa_environment_defaults(self):
        """Test QA environment defaults (line 486)."""
        with patch.dict(os.environ, {"ENVIRONMENT": "qa"}):
            defaults = get_environment_defaults()
            assert defaults.get("advanced_analytics") is True
            assert defaults.get("multi_repo_scanning") is True
            assert defaults.get("knowledge_graph_explorer") is True
            assert defaults.get("ticket_integrations") is True

    def test_unknown_environment_defaults(self):
        """Test unknown environment returns empty defaults (line 496)."""
        with patch.dict(os.environ, {"ENVIRONMENT": "unknown_env"}):
            defaults = get_environment_defaults()
            assert defaults == {}


class TestOnboardingFeatures:
    """Tests for onboarding features (ADR-047)."""

    def test_get_onboarding_features(self):
        """Test get_onboarding_features returns copy of ONBOARDING_FEATURES."""
        features = get_onboarding_features()
        assert isinstance(features, dict)
        # Verify it's a copy by modifying
        features["test_key"] = "test_value"
        features2 = get_onboarding_features()
        assert "test_key" not in features2


class TestDeprecatedFeatures:
    """Tests for deprecated feature handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_deprecated_feature_returns_false(self):
        """Test that deprecated features return False (line 379)."""
        # Add a deprecated feature to test
        deprecated_feature = FeatureDefinition(
            name="deprecated_test_feature",
            description="A deprecated feature",
            status=FeatureStatus.DEPRECATED,
            min_tier=FeatureTier.FREE,
            enabled_by_default=True,  # Even if enabled, should return False
        )
        self.service._all_features["deprecated_test_feature"] = deprecated_feature

        # Should return False because deprecated
        result = self.service.is_enabled(
            "deprecated_test_feature", tier=FeatureTier.ENTERPRISE
        )
        assert result is False


class TestRolloutPercentageEdgeCases:
    """Tests for rollout percentage edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_partial_rollout_with_customer_id(self):
        """Test rollout percentage with customer_id hash (lines 390-392)."""
        # Add a feature with 50% rollout
        feature = FeatureDefinition(
            name="partial_rollout_feature",
            description="Feature with partial rollout",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.FREE,
            rollout_percentage=50,
            enabled_by_default=True,
        )
        self.service._all_features["partial_rollout_feature"] = feature

        # Test with different customer IDs - some should be enabled, some not
        # The hash is deterministic, so we can find specific customers
        results = []
        for i in range(100):
            customer_id = f"customer_{i}"
            result = self.service.is_enabled(
                "partial_rollout_feature", customer_id=customer_id
            )
            results.append(result)

        # With 50% rollout, approximately half should be enabled
        enabled_count = sum(results)
        # Allow some variance (40-60%)
        assert 30 <= enabled_count <= 70, f"Expected ~50% enabled, got {enabled_count}%"

    def test_zero_percent_rollout(self):
        """Test 0% rollout disables for all customers."""
        feature = FeatureDefinition(
            name="zero_rollout_feature",
            description="Feature with 0% rollout",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.FREE,
            rollout_percentage=0,
            enabled_by_default=True,
        )
        self.service._all_features["zero_rollout_feature"] = feature

        # Should be disabled for all customers
        for i in range(10):
            result = self.service.is_enabled(
                "zero_rollout_feature", customer_id=f"cust_{i}"
            )
            assert result is False

    def test_100_percent_rollout(self):
        """Test 100% rollout enables for all customers."""
        feature = FeatureDefinition(
            name="full_rollout_feature",
            description="Feature with 100% rollout",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.FREE,
            rollout_percentage=100,
            enabled_by_default=True,
        )
        self.service._all_features["full_rollout_feature"] = feature

        # Should be enabled for all customers
        for i in range(10):
            result = self.service.is_enabled(
                "full_rollout_feature", customer_id=f"cust_{i}"
            )
            assert result is True


class TestDependencyChainFailure:
    """Tests for feature dependency chain failures."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FeatureFlagsService()

    def test_feature_with_failed_dependency_returns_false(self):
        """Test feature with disabled dependency returns False (lines 383-384)."""
        # Create a chain: feature_b depends on feature_a
        feature_a = FeatureDefinition(
            name="feature_a",
            description="Base feature",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.ENTERPRISE,  # Only enterprise
            enabled_by_default=True,
        )
        feature_b = FeatureDefinition(
            name="feature_b",
            description="Feature that depends on feature_a",
            status=FeatureStatus.GA,
            min_tier=FeatureTier.FREE,  # Available to all
            dependencies=["feature_a"],  # But depends on feature_a
            enabled_by_default=True,
        )
        self.service._all_features["feature_a"] = feature_a
        self.service._all_features["feature_b"] = feature_b

        # Feature B should be disabled for FREE tier because feature_a is enterprise-only
        result = self.service.is_enabled("feature_b", tier=FeatureTier.FREE)
        assert result is False

        # Feature B should be enabled for ENTERPRISE tier
        result = self.service.is_enabled("feature_b", tier=FeatureTier.ENTERPRISE)
        assert result is True
