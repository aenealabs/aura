"""
Tests for Model Router Service (ADR-028 Phase 2)

Tests routing logic, A/B testing, cost estimation, and SSM integration.
"""

import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.model_router import (
    DEFAULT_MODELS,
    DEFAULT_ROUTING_RULES,
    ABTestConfig,
    ModelRouter,
    ModelTier,
    RoutingDecision,
    RoutingRule,
    TaskComplexity,
    get_router,
    route,
)


class TestModelRouter:
    """Tests for ModelRouter class."""

    @pytest.fixture
    def router(self):
        """Create a router with SSM and metrics disabled for testing."""
        return ModelRouter(enable_ssm=False, enable_metrics=False)

    def test_initialization(self, router):
        """Test router initializes with default configuration."""
        assert router.environment == "dev"
        assert len(router.models) == 3
        assert len(router.rules) == len(DEFAULT_ROUTING_RULES)
        assert not router.ab_test.enabled

    def test_route_simple_task(self, router):
        """Test routing a simple task to FAST tier."""
        decision = router.route("query_intent_analysis")

        assert decision.tier == ModelTier.FAST
        assert decision.complexity == TaskComplexity.SIMPLE
        assert decision.rule_matched == "query_intent_analysis"
        assert "haiku" in decision.model_id.lower()
        assert decision.estimated_cost_per_1k_tokens < 0.001  # Very cheap

    def test_route_medium_task(self, router):
        """Test routing a medium task to ACCURATE tier."""
        decision = router.route("patch_generation")

        assert decision.tier == ModelTier.ACCURATE
        assert decision.complexity == TaskComplexity.MEDIUM
        assert decision.rule_matched == "patch_generation"
        assert "sonnet" in decision.model_id.lower()

    def test_route_complex_task(self, router):
        """Test routing a complex task to MAXIMUM tier."""
        decision = router.route("cross_codebase_correlation")

        assert decision.tier == ModelTier.MAXIMUM
        assert decision.complexity == TaskComplexity.COMPLEX
        assert decision.rule_matched == "cross_codebase_correlation"
        assert "opus" in decision.model_id.lower()

    def test_route_unknown_task_defaults_to_accurate(self, router):
        """Test unknown tasks default to ACCURATE tier for safety."""
        decision = router.route("unknown_task_xyz")

        assert decision.tier == ModelTier.ACCURATE
        assert decision.rule_matched == "default"

    def test_route_with_override(self, router):
        """Test override_tier bypasses routing logic."""
        # Even though query_intent_analysis should route to FAST,
        # override should force MAXIMUM
        decision = router.route(
            "query_intent_analysis", override_tier=ModelTier.MAXIMUM
        )

        assert decision.tier == ModelTier.MAXIMUM
        assert decision.rule_matched == "override"

    def test_routing_decision_includes_cost_estimate(self, router):
        """Test that routing decisions include cost estimates."""
        decision = router.route("patch_generation")

        assert decision.estimated_cost_per_1k_tokens > 0
        assert decision.decision_time_ms >= 0

    def test_get_model_for_tier(self, router):
        """Test getting model configuration by tier."""
        fast_model = router.get_model_for_tier(ModelTier.FAST)
        accurate_model = router.get_model_for_tier(ModelTier.ACCURATE)
        maximum_model = router.get_model_for_tier(ModelTier.MAXIMUM)

        assert fast_model.input_cost_per_million < accurate_model.input_cost_per_million
        assert (
            accurate_model.input_cost_per_million < maximum_model.input_cost_per_million
        )

    def test_get_routing_rules(self, router):
        """Test getting routing rules."""
        rules = router.get_routing_rules()

        assert len(rules) > 0
        assert all(isinstance(rule, RoutingRule) for rule in rules)

        # Check for expected task types
        task_types = [rule.task_type for rule in rules]
        assert "query_intent_analysis" in task_types
        assert "patch_generation" in task_types
        assert "cross_codebase_correlation" in task_types

    def test_get_stats(self, router):
        """Test getting routing statistics."""
        # Make some routing decisions
        router.route("query_intent_analysis")
        router.route("patch_generation")
        router.route("cross_codebase_correlation")

        stats = router.get_stats()

        assert stats["total_decisions"] == 3
        assert "tier_counts" in stats
        assert "tier_distribution_percent" in stats
        assert "estimated_cost_savings_usd" in stats


class TestCostEstimation:
    """Tests for cost estimation functionality."""

    @pytest.fixture
    def router(self):
        return ModelRouter(enable_ssm=False, enable_metrics=False)

    def test_estimate_savings_with_typical_distribution(self, router):
        """Test cost savings estimation with typical task distribution."""
        # Use a distribution where FAST tier dominates to show savings
        task_dist = {
            "query_intent_analysis": 400,  # FAST
            "query_expansion": 200,  # FAST
            "patch_generation": 300,  # ACCURATE
            "code_review": 100,  # ACCURATE
        }

        savings = router.estimate_savings(task_dist)

        assert savings["task_count"] == 1000
        assert savings["baseline_cost_per_1k_calls"] > 0
        assert savings["optimized_cost_per_1k_calls"] > 0
        # With 60% going to FAST tier, we should see meaningful savings
        assert savings["savings_percent"] > 0

    def test_estimate_savings_all_simple_tasks(self, router):
        """Test cost savings when all tasks are simple (maximum savings)."""
        task_dist = {
            "query_intent_analysis": 500,
            "query_expansion": 500,
        }

        savings = router.estimate_savings(task_dist)

        # All FAST tier should give ~90%+ savings vs all ACCURATE
        assert savings["savings_percent"] > 80

    def test_estimate_savings_all_complex_tasks(self, router):
        """Test cost savings when all tasks are complex (no savings)."""
        task_dist = {
            "cross_codebase_correlation": 500,
            "novel_threat_detection": 500,
        }

        savings = router.estimate_savings(task_dist)

        # All MAXIMUM tier costs more than ACCURATE baseline
        # So savings should be negative
        assert savings["savings_percent"] < 0


class TestABTesting:
    """Tests for A/B testing functionality."""

    @pytest.fixture
    def router_with_ab_test(self):
        """Create router with A/B test enabled."""
        router = ModelRouter(enable_ssm=False, enable_metrics=False)
        router.ab_test = ABTestConfig(
            enabled=True,
            experiment_id="test-experiment-001",
            control_tier=ModelTier.ACCURATE,
            treatment_tier=ModelTier.FAST,
            traffic_split=0.5,
            task_types=["patch_generation"],
        )
        return router

    def test_ab_test_applies_to_configured_tasks(self, router_with_ab_test):
        """Test A/B test only applies to configured task types."""
        # patch_generation is in task_types, should apply A/B test
        decision = router_with_ab_test.route(
            "patch_generation", context={"request_id": "test-123"}
        )
        assert decision.is_ab_test
        assert decision.ab_variant in ["control", "treatment"]

        # query_intent_analysis is not in task_types, should not apply A/B test
        decision = router_with_ab_test.route("query_intent_analysis")
        assert not decision.is_ab_test

    def test_ab_test_consistent_assignment(self, router_with_ab_test):
        """Test same request always gets same A/B variant."""
        context = {"request_id": "consistent-test-123"}

        decisions = [
            router_with_ab_test.route("patch_generation", context=context)
            for _ in range(10)
        ]

        # All decisions should have the same variant
        variants = [d.ab_variant for d in decisions]
        assert len(set(variants)) == 1

    def test_ab_test_disabled_by_default(self):
        """Test A/B testing is disabled by default."""
        router = ModelRouter(enable_ssm=False, enable_metrics=False)
        assert not router.ab_test.enabled

    def test_ab_test_records_experiment_id(self, router_with_ab_test):
        """Test A/B test decision includes experiment ID."""
        decision = router_with_ab_test.route(
            "patch_generation", context={"request_id": "test"}
        )

        assert decision.is_ab_test
        assert "test-experiment-001" in decision.rule_matched


class TestSSMIntegration:
    """Tests for SSM Parameter Store integration."""

    def test_works_without_ssm(self):
        """Test router works when SSM is disabled."""
        router = ModelRouter(enable_ssm=False, enable_metrics=False)

        assert len(router.models) == 3
        assert len(router.rules) > 0

        decision = router.route("patch_generation")
        assert decision.tier == ModelTier.ACCURATE

    def test_ssm_disabled_uses_defaults(self):
        """Test that disabling SSM uses default configurations."""
        router = ModelRouter(enable_ssm=False, enable_metrics=False)

        # Should have all default models
        assert ModelTier.FAST in router.models
        assert ModelTier.ACCURATE in router.models
        assert ModelTier.MAXIMUM in router.models

        # Should have all default rules
        assert len(router.rules) == len(DEFAULT_ROUTING_RULES)


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_router_singleton(self):
        """Test get_router returns singleton instance."""
        # Reset the global router and use a pre-configured one
        import src.services.model_router as router_module

        # Create router with SSM disabled to avoid AWS calls
        test_router = ModelRouter(enable_ssm=False, enable_metrics=False)
        router_module._default_router = test_router

        router1 = get_router()
        router2 = get_router()

        assert router1 is router2
        assert router1 is test_router

    def test_route_convenience_function(self):
        """Test module-level route function."""
        # Reset the global router with SSM disabled
        import src.services.model_router as router_module

        test_router = ModelRouter(enable_ssm=False, enable_metrics=False)
        router_module._default_router = test_router

        decision = route("query_intent_analysis")

        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.FAST


class TestRoutingRuleValidation:
    """Tests for routing rule validation."""

    def test_all_default_rules_are_valid(self):
        """Test all default routing rules have valid configuration."""
        for rule in DEFAULT_ROUTING_RULES:
            assert rule.task_type
            assert isinstance(rule.complexity, TaskComplexity)
            assert isinstance(rule.tier, ModelTier)

    def test_tier_complexity_mapping_is_consistent(self):
        """Test tier to complexity mapping is consistent in default rules."""
        tier_complexity_map = {
            ModelTier.FAST: TaskComplexity.SIMPLE,
            ModelTier.ACCURATE: TaskComplexity.MEDIUM,
            ModelTier.MAXIMUM: TaskComplexity.COMPLEX,
        }

        for rule in DEFAULT_ROUTING_RULES:
            expected_complexity = tier_complexity_map[rule.tier]
            assert rule.complexity == expected_complexity, (
                f"Rule '{rule.task_type}' has tier {rule.tier.value} "
                f"but complexity {rule.complexity.value}, expected {expected_complexity.value}"
            )


class TestModelConfigurations:
    """Tests for model configurations."""

    def test_all_tiers_have_models(self):
        """Test all model tiers have configurations."""
        for tier in ModelTier:
            assert tier in DEFAULT_MODELS

    def test_model_costs_are_ordered(self):
        """Test model costs increase with tier capability."""
        fast = DEFAULT_MODELS[ModelTier.FAST]
        accurate = DEFAULT_MODELS[ModelTier.ACCURATE]
        maximum = DEFAULT_MODELS[ModelTier.MAXIMUM]

        assert fast.input_cost_per_million < accurate.input_cost_per_million
        assert accurate.input_cost_per_million <= maximum.input_cost_per_million

    def test_model_ids_are_valid_format(self):
        """Test model IDs follow expected format."""
        for tier, model in DEFAULT_MODELS.items():
            assert model.model_id.startswith("anthropic.claude")
            assert "v1:0" in model.model_id


class TestSecurityOperationRouting:
    """Tests for security-critical operation routing."""

    @pytest.fixture
    def router(self):
        return ModelRouter(enable_ssm=False, enable_metrics=False)

    @pytest.mark.parametrize(
        "security_task",
        [
            "vulnerability_ranking",
            "security_result_scoring",
            "patch_generation",
            "threat_assessment",
            "compliance_check",
            "cve_impact_assessment",
        ],
    )
    def test_security_tasks_use_accurate_or_higher(self, router, security_task):
        """Test security-critical tasks never route to FAST tier."""
        decision = router.route(security_task)

        assert decision.tier in [ModelTier.ACCURATE, ModelTier.MAXIMUM], (
            f"Security task '{security_task}' routed to {decision.tier.value}, "
            "expected ACCURATE or MAXIMUM"
        )

    @pytest.mark.parametrize(
        "complex_task",
        [
            "cross_codebase_correlation",
            "novel_threat_detection",
            "zero_day_pattern_analysis",
        ],
    )
    def test_complex_tasks_use_maximum(self, router, complex_task):
        """Test complex tasks route to MAXIMUM tier."""
        decision = router.route(complex_task)

        assert decision.tier == ModelTier.MAXIMUM
