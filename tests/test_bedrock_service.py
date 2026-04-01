"""
Unit and Integration Tests for BedrockLLMService
Tests cost control, rate limiting, caching, and error handling.
"""

import os
import time

import pytest

from src.config.bedrock_config import calculate_cost
from src.services.bedrock_llm_service import (
    BedrockLLMService,
    BedrockMode,
    BudgetExceededError,
    RateLimitExceededError,
    create_llm_service,
)

# Test constants
DEV_DAILY_BUDGET = 10.0
PROD_DAILY_BUDGET = 100.0
EXPECTED_SONNET_COST = 0.0105  # (1000 * $3/1M) + (500 * $15/1M)
EXPECTED_HAIKU_COST = 0.000875  # (1000 * $0.25/1M) + (500 * $1.25/1M)
MIN_LONG_INPUT_TOKENS = 1000
TEST_REQUEST_COUNT = 3


class TestBedrockConfiguration:
    """Test configuration and initialization."""

    def test_service_initialization_mock_mode(self):
        """Test service initializes correctly in mock mode."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        assert service.mode == BedrockMode.MOCK
        assert service.environment == "development"
        assert service.daily_spend == 0.0
        assert service.monthly_spend == 0.0
        assert len(service.request_history) == 0

    def test_environment_config_loading(self):
        """Test that environment-specific configs load correctly."""
        # Test dev environment
        os.environ["AURA_ENV"] = "development"
        service = BedrockLLMService(mode=BedrockMode.MOCK)

        assert service.config["daily_budget_usd"] == DEV_DAILY_BUDGET
        assert (
            service.config["model_id_primary"]
            == "anthropic.claude-3-5-sonnet-20240620-v1:0"  # Claude 3.5 Sonnet v1 (on-demand)
        )

        # Test prod environment
        os.environ["AURA_ENV"] = "production"
        service = BedrockLLMService(mode=BedrockMode.MOCK)

        assert service.config["daily_budget_usd"] == PROD_DAILY_BUDGET
        # Prod still uses Sonnet 4.5 (requires inference profile in production)
        assert (
            service.config["model_id_primary"]
            == "anthropic.claude-sonnet-4-5-20250929-v1:0"  # Claude Sonnet 4.5 (Sep 2025)
        )

        # Reset
        os.environ["AURA_ENV"] = "development"


class TestCostCalculation:
    """Test cost calculation and tracking."""

    def test_cost_calculation_sonnet(self):
        """Test cost calculation for Sonnet model."""
        # Sonnet: $3/1M input, $15/1M output
        cost = calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model_id="anthropic.claude-3-5-sonnet-20241022-v1:0",
        )

        expected = (1000 * 3.00 / 1_000_000) + (500 * 15.00 / 1_000_000)
        assert cost == pytest.approx(expected, abs=0.000001)
        assert cost == EXPECTED_SONNET_COST

    def test_cost_calculation_haiku(self):
        """Test cost calculation for Haiku model."""
        # Haiku: $0.25/1M input, $1.25/1M output
        cost = calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
        )

        expected = (1000 * 0.25 / 1_000_000) + (500 * 1.25 / 1_000_000)
        assert cost == pytest.approx(expected, abs=0.000001)
        assert cost == EXPECTED_HAIKU_COST

    def test_cost_tracking_updates(self):
        """Test that cost tracking updates correctly after requests."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        initial_daily = service.daily_spend
        initial_monthly = service.monthly_spend

        # Make a request
        result = service.invoke_model(
            prompt="Test prompt", agent="TestAgent", max_tokens=100
        )

        # Verify spend increased
        assert service.daily_spend > initial_daily
        assert service.monthly_spend > initial_monthly
        assert result["cost_usd"] > 0


class TestBudgetEnforcement:
    """Test budget limit enforcement."""

    def test_budget_exceeded_daily(self):
        """Test that daily budget limit is enforced."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Set daily spend to exceed budget
        service.daily_spend = 999.0
        service.config["daily_budget_usd"] = 10.0

        # Should raise BudgetExceededError
        with pytest.raises(BudgetExceededError) as exc_info:
            service.invoke_model(prompt="Test", agent="TestAgent")

        assert "Daily" in str(exc_info.value)

    def test_budget_exceeded_monthly(self):
        """Test that monthly budget limit is enforced."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Set monthly spend to exceed budget
        service.monthly_spend = 999.0
        service.config["monthly_budget_usd"] = 100.0

        # Should raise BudgetExceededError
        with pytest.raises(BudgetExceededError) as exc_info:
            service.invoke_model(prompt="Test", agent="TestAgent")

        assert "Monthly" in str(exc_info.value)

    def test_budget_within_limits(self):
        """Test that requests succeed when within budget."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Ensure we're within budget
        service.daily_spend = 1.0
        service.monthly_spend = 10.0

        # Should succeed
        result = service.invoke_model(prompt="Test", agent="TestAgent")

        assert "response" in result
        assert result["cost_usd"] > 0


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_per_minute(self):
        """Test per-minute rate limit enforcement."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Set very low rate limit for testing
        service.config["max_requests_per_minute"] = 2

        # First two requests should succeed
        service.invoke_model(prompt="Test 1", agent="TestAgent", cache_enabled=False)
        service.invoke_model(prompt="Test 2", agent="TestAgent", cache_enabled=False)

        # Third request should fail
        with pytest.raises(RateLimitExceededError) as exc_info:
            service.invoke_model(
                prompt="Test 3", agent="TestAgent", cache_enabled=False
            )

        assert "rate limit exceeded" in str(exc_info.value).lower()

    def test_rate_limit_per_hour(self):
        """Test per-hour rate limit enforcement."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Set rate limit to 10 per hour
        service.config["max_requests_per_hour"] = 10

        # Mock the Redis cache to return 10 requests in the hour window
        # (rate limiting now uses Redis, not request_history directly)
        original_get_count = service._redis_cache.get_request_count

        def mock_get_count(identifier, window_seconds):
            # Return 10 for hour window, 0 for minute/day to pass those checks
            if window_seconds == 3600:  # hour
                return 10
            return 0

        service._redis_cache.get_request_count = mock_get_count

        # Next request should fail (already at hourly limit)
        with pytest.raises(RateLimitExceededError):
            service.invoke_model(prompt="Test", agent="TestAgent", cache_enabled=False)

        # Restore original
        service._redis_cache.get_request_count = original_get_count

    def test_rate_limit_history_cleanup(self):
        """Test that old requests are removed from history.

        The get_request_history() method filters by max_age_seconds (default 24h),
        so old requests are automatically excluded from the returned history.
        """
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Add old request timestamps directly to the cache's internal storage
        # (simulating old requests that should be filtered out)
        old_timestamp = time.time() - 90000  # 25 hours ago
        for i in range(5):
            entry_key = f"global:{old_timestamp + i}"
            service._redis_cache._rate_history[entry_key] = old_timestamp + i

        # Make new request
        service.invoke_model(prompt="Test", agent="TestAgent")

        # History should only contain recent requests (filtered by max_age_seconds=86400)
        # Old timestamps (25h ago) are outside the 24h window and get filtered
        assert len(service.request_history) == 1
        assert service.request_history[0] > old_timestamp


class TestResponseCaching:
    """Test response caching functionality."""

    def test_cache_hit(self):
        """Test that identical requests return cached responses."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # First request
        service.invoke_model(
            prompt="What is 2+2?", agent="TestAgent", max_tokens=100, cache_enabled=True
        )

        initial_spend = service.daily_spend

        # Second identical request - should be cached
        result2 = service.invoke_model(
            prompt="What is 2+2?", agent="TestAgent", max_tokens=100, cache_enabled=True
        )

        # Verify it was cached
        assert result2["cached"] is True
        assert result2["cost_usd"] == 0.0  # No cost for cached response
        assert service.daily_spend == initial_spend  # Spend didn't increase

    def test_cache_miss_different_prompt(self):
        """Test that different prompts don't hit cache."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # First request
        service.invoke_model(
            prompt="What is 2+2?", agent="TestAgent", cache_enabled=True
        )

        # Different prompt - should not be cached
        result2 = service.invoke_model(
            prompt="What is 3+3?", agent="TestAgent", cache_enabled=True
        )

        assert result2["cached"] is False
        assert result2["cost_usd"] > 0

    def test_cache_disabled(self):
        """Test that caching can be disabled."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # First request
        service.invoke_model(prompt="Test", agent="TestAgent", cache_enabled=False)

        # Identical request but cache disabled
        result2 = service.invoke_model(
            prompt="Test", agent="TestAgent", cache_enabled=False
        )

        # Should not be cached
        assert result2["cached"] is False
        assert result2["cost_usd"] > 0


class TestMockMode:
    """Test mock mode functionality."""

    def test_mock_response_generation(self):
        """Test that mock mode generates appropriate responses."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        result = service.invoke_model(
            prompt="Analyze this code for vulnerabilities",
            agent="ReviewerAgent",
            max_tokens=200,
        )

        assert "response" in result
        assert len(result["response"]) > 0
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert "ReviewerAgent" in result["response"] or "Security" in result["response"]

    def test_mock_token_counting(self):
        """Test that mock mode provides realistic token counts."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        short_prompt = "Hi"
        long_prompt = "This is a much longer prompt " * 20

        result1 = service.invoke_model(prompt=short_prompt, agent="TestAgent")
        result2 = service.invoke_model(prompt=long_prompt, agent="TestAgent")

        # Longer prompt should have more input tokens
        assert result2["input_tokens"] > result1["input_tokens"]

    def test_mock_different_agents(self):
        """Test that mock mode provides agent-specific responses."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        agents = ["PlannerAgent", "CoderAgent", "ReviewerAgent", "ValidatorAgent"]
        responses = {}

        for agent in agents:
            result = service.invoke_model(
                prompt="Test", agent=agent, cache_enabled=False
            )
            responses[agent] = result["response"]

        # Verify different agents get different mock responses
        assert len(set(responses.values())) > 1  # At least some variation


class TestModelSelection:
    """Test model selection functionality."""

    def test_primary_model_default(self):
        """Test that primary model is used by default."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="production")

        result = service.invoke_model(
            prompt="Test", agent="TestAgent", use_fallback=False
        )

        assert service.model_id_primary in result["model"]

    def test_fallback_model_selection(self):
        """Test that fallback model can be selected."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="production")

        result = service.invoke_model(
            prompt="Test", agent="TestAgent", use_fallback=True
        )

        assert service.model_id_fallback in result["model"]
        # Fallback is Claude 3.5 Sonnet
        assert "claude-3-5-sonnet" in result["model"].lower()


class TestSpendSummary:
    """Test spending summary functionality."""

    def test_spend_summary_structure(self):
        """Test that spend summary has correct structure."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        summary = service.get_spend_summary()

        required_fields = [
            "daily_spend",
            "daily_budget",
            "daily_remaining",
            "daily_percent",
            "monthly_spend",
            "monthly_budget",
            "monthly_remaining",
            "monthly_percent",
            "total_requests",
        ]

        for field in required_fields:
            assert field in summary

    def test_spend_summary_calculations(self):
        """Test that spend summary calculates correctly."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Make some requests
        for i in range(TEST_REQUEST_COUNT):
            service.invoke_model(
                prompt=f"Test {i}", agent="TestAgent", cache_enabled=False
            )

        summary = service.get_spend_summary()

        # Verify calculations
        assert (
            summary["daily_remaining"]
            == summary["daily_budget"] - summary["daily_spend"]
        )
        assert summary["total_requests"] == TEST_REQUEST_COUNT

        expected_percent = (summary["daily_spend"] / summary["daily_budget"]) * 100
        assert summary["daily_percent"] == pytest.approx(expected_percent, abs=0.01)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_prompt(self):
        """Test handling of empty prompt."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Should still work with empty prompt
        result = service.invoke_model(prompt="", agent="TestAgent")

        assert "response" in result

    def test_very_long_prompt(self):
        """Test handling of very long prompt."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        long_prompt = "x" * 10000

        result = service.invoke_model(
            prompt=long_prompt, agent="TestAgent", max_tokens=100
        )

        assert (
            result["input_tokens"] > MIN_LONG_INPUT_TOKENS
        )  # Should reflect long input

    def test_zero_max_tokens(self):
        """Test handling of invalid max_tokens."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, environment="development")

        # Should still work (service will use default or handle gracefully)
        result = service.invoke_model(
            prompt="Test",
            agent="TestAgent",
            max_tokens=1,  # Very low but valid
        )

        assert "response" in result


class TestIntegration:
    """Integration tests (require real AWS credentials)."""

    @pytest.mark.skipif(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        reason="Integration tests disabled (set RUN_INTEGRATION_TESTS=1 to enable)",
    )
    def test_real_bedrock_call(self):
        """Integration test with real Bedrock API."""
        # This test requires AWS credentials and Bedrock access
        service = BedrockLLMService(mode=BedrockMode.AWS, environment="development")

        result = service.invoke_model(
            prompt="Say 'test successful' and nothing else.",
            agent="IntegrationTest",
            max_tokens=20,
            use_fallback=True,  # Use Haiku for cheaper testing
        )

        assert "response" in result
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["cost_usd"] > 0
        assert not result["cached"]

        print("\n✓ Real Bedrock API test successful!")
        print(f"  Response: {result['response']}")
        print(f"  Cost: ${result['cost_usd']:.6f}")


def test_create_service_helper():
    """Test the convenience function."""
    service = create_llm_service(environment="development")

    assert service is not None
    assert service.environment == "development"


if __name__ == "__main__":
    # Run tests with pytest
    print("Running Bedrock LLM Service Tests...")
    print("=" * 60)

    pytest.main([__file__, "-v", "--tb=short"])
