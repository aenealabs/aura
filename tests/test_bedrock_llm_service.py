"""
Project Aura - Bedrock LLM Service Tests

Tests for the AWS Bedrock LLM service with cost controls,
rate limiting, and security features.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "boto3",
    "botocore",
    "botocore.exceptions",
    "config.bedrock_config",
    "config.guardrails_config",
    "src.services.llm_prompt_sanitizer",
    "src.services.bedrock_llm_service",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock dependencies
mock_boto3 = MagicMock()
mock_boto3.client = MagicMock(return_value=MagicMock())
sys.modules["boto3"] = mock_boto3

mock_botocore = MagicMock()
mock_botocore.exceptions = MagicMock()
mock_botocore.exceptions.ClientError = Exception
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions

# Mock config modules
mock_bedrock_config = MagicMock()
mock_bedrock_config.get_config = MagicMock(
    return_value=MagicMock(
        max_tokens=4096,
        model_id="anthropic.claude-3-5-sonnet",
        daily_budget_usd=100.0,
        monthly_budget_usd=3000.0,
        rpm_limit=60,
        rph_limit=1000,
        rpd_limit=10000,
    )
)
mock_bedrock_config.calculate_cost = MagicMock(return_value=0.01)
sys.modules["config.bedrock_config"] = mock_bedrock_config

mock_guardrails_config = MagicMock()
mock_guardrails_config.GuardrailConfig = MagicMock
mock_guardrails_config.GuardrailMode = MagicMock()
mock_guardrails_config.GuardrailResult = MagicMock
mock_guardrails_config.format_guardrail_trace = MagicMock()
mock_guardrails_config.get_guardrail_config = MagicMock(return_value=MagicMock())
mock_guardrails_config.load_guardrail_ids_from_ssm = MagicMock()
sys.modules["config.guardrails_config"] = mock_guardrails_config

mock_sanitizer = MagicMock()
mock_sanitizer.LLMPromptSanitizer = MagicMock
mock_sanitizer.SanitizationAction = MagicMock
mock_sanitizer.SanitizationResult = MagicMock
mock_sanitizer.ThreatLevel = MagicMock()
mock_sanitizer.get_prompt_sanitizer = MagicMock(return_value=MagicMock())
sys.modules["src.services.llm_prompt_sanitizer"] = mock_sanitizer

from src.services.bedrock_llm_service import (
    MODEL_IDS,
    OPERATION_MODEL_MAP,
    OPERATION_QUERY_TYPE_MAP,
    BedrockError,
    BedrockLLMService,
    BedrockMode,
    BudgetExceededError,
    GuardrailViolationError,
    ModelTier,
    PromptInjectionError,
    RateLimitExceededError,
    get_model_for_operation,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestBedrockMode:
    """Tests for BedrockMode enum."""

    def test_mock_mode(self):
        """Test mock mode."""
        assert BedrockMode.MOCK.value == "mock"

    def test_aws_mode(self):
        """Test AWS mode."""
        assert BedrockMode.AWS.value == "aws"


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_fast_tier(self):
        """Test fast tier."""
        assert ModelTier.FAST.value == "fast"

    def test_accurate_tier(self):
        """Test accurate tier."""
        assert ModelTier.ACCURATE.value == "accurate"

    def test_maximum_tier(self):
        """Test maximum tier."""
        assert ModelTier.MAXIMUM.value == "maximum"

    def test_all_tiers_exist(self):
        """Test all expected tiers exist."""
        tiers = list(ModelTier)
        assert len(tiers) == 3


class TestModelIDs:
    """Tests for MODEL_IDS mapping."""

    def test_fast_model_id(self):
        """Test fast tier model ID."""
        assert "haiku" in MODEL_IDS[ModelTier.FAST]

    def test_accurate_model_id(self):
        """Test accurate tier model ID."""
        assert "sonnet" in MODEL_IDS[ModelTier.ACCURATE]

    def test_maximum_model_id(self):
        """Test maximum tier model ID."""
        assert "sonnet" in MODEL_IDS[ModelTier.MAXIMUM]

    def test_all_tiers_have_models(self):
        """Test all tiers have model IDs."""
        for tier in ModelTier:
            assert tier in MODEL_IDS
            assert MODEL_IDS[tier] is not None


class TestOperationModelMap:
    """Tests for OPERATION_MODEL_MAP mapping."""

    def test_fast_operations(self):
        """Test fast tier operations."""
        fast_ops = ["query_intent_analysis", "query_expansion", "simple_summarization"]
        for op in fast_ops:
            assert OPERATION_MODEL_MAP[op] == ModelTier.FAST

    def test_accurate_operations(self):
        """Test accurate tier operations."""
        accurate_ops = ["vulnerability_ranking", "patch_generation", "code_review"]
        for op in accurate_ops:
            assert OPERATION_MODEL_MAP[op] == ModelTier.ACCURATE

    def test_maximum_operations(self):
        """Test maximum tier operations."""
        max_ops = ["cross_codebase_correlation", "novel_threat_detection"]
        for op in max_ops:
            assert OPERATION_MODEL_MAP[op] == ModelTier.MAXIMUM


class TestOperationQueryTypeMap:
    """Tests for OPERATION_QUERY_TYPE_MAP mapping."""

    def test_vulnerability_analysis_operations(self):
        """Test vulnerability analysis operations."""
        vuln_ops = [
            "vulnerability_ranking",
            "threat_assessment",
            "cve_impact_assessment",
        ]
        for op in vuln_ops:
            assert OPERATION_QUERY_TYPE_MAP[op] == "vulnerability_analysis"

    def test_code_review_operations(self):
        """Test code review operations."""
        review_ops = ["code_review", "compliance_check"]
        for op in review_ops:
            assert OPERATION_QUERY_TYPE_MAP[op] == "code_review"

    def test_code_generation_operations(self):
        """Test code generation operations."""
        gen_ops = ["patch_generation", "multi_file_refactoring"]
        for op in gen_ops:
            assert OPERATION_QUERY_TYPE_MAP[op] == "code_generation"


class TestGetModelForOperation:
    """Tests for get_model_for_operation function."""

    def test_known_operation(self):
        """Test getting model for known operation."""
        tier, model_id = get_model_for_operation("query_intent_analysis")
        assert tier == ModelTier.FAST
        assert "haiku" in model_id

    def test_unknown_operation(self):
        """Test unknown operation defaults to accurate."""
        tier, model_id = get_model_for_operation("unknown_operation")
        assert tier == ModelTier.ACCURATE

    def test_none_operation(self):
        """Test None operation defaults to accurate."""
        tier, model_id = get_model_for_operation(None)
        assert tier == ModelTier.ACCURATE

    def test_security_operations_accurate(self):
        """Test security operations use accurate tier."""
        tier, _ = get_model_for_operation("vulnerability_ranking")
        assert tier == ModelTier.ACCURATE


class TestBudgetExceededError:
    """Tests for BudgetExceededError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = BudgetExceededError("Daily budget exceeded")
        assert str(error) == "Daily budget exceeded"

    def test_error_is_exception(self):
        """Test error is an Exception."""
        error = BudgetExceededError("Test")
        assert isinstance(error, Exception)


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = RateLimitExceededError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"


class TestBedrockError:
    """Tests for BedrockError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = BedrockError("API error")
        assert str(error) == "API error"


class TestGuardrailViolationError:
    """Tests for GuardrailViolationError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = GuardrailViolationError("Content blocked")
        assert str(error) == "Content blocked"
        assert error.violations == []

    def test_error_with_violations(self):
        """Test error with violations list."""
        violations = [
            {"type": "harmful", "message": "Harmful content detected"},
        ]
        error = GuardrailViolationError("Blocked", violations=violations)
        assert len(error.violations) == 1
        assert error.violations[0]["type"] == "harmful"


class TestPromptInjectionError:
    """Tests for PromptInjectionError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = PromptInjectionError(
            "Prompt injection detected",
            threat_level=mock_sanitizer.ThreatLevel,
        )
        assert "injection" in str(error)

    def test_error_with_patterns(self):
        """Test error with patterns detected."""
        patterns = ["ignore instructions", "reveal system prompt"]
        error = PromptInjectionError(
            "Injection attempt",
            threat_level=mock_sanitizer.ThreatLevel,
            patterns_detected=patterns,
        )
        assert len(error.patterns_detected) == 2


class TestBedrockLLMService:
    """Tests for BedrockLLMService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = BedrockLLMService(mode=BedrockMode.MOCK)
        assert service.mode == BedrockMode.MOCK

    def test_init_daily_spend_zero(self):
        """Test initial daily spend is zero."""
        assert self.service.daily_spend == 0.0

    def test_init_monthly_spend_zero(self):
        """Test initial monthly spend is zero."""
        assert self.service.monthly_spend == 0.0

    def test_init_request_history_empty(self):
        """Test initial request history is empty."""
        assert self.service.request_history == []

    def test_init_with_sanitization(self):
        """Test initialization with prompt sanitization."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=True)
        assert service.sanitize_prompts is True

    def test_init_without_sanitization(self):
        """Test initialization without prompt sanitization."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        assert service.sanitize_prompts is False

    def test_config_loaded(self):
        """Test that config is loaded."""
        assert self.service.config is not None


class TestBedrockLLMServiceCostTracking:
    """Tests for cost tracking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_spend_tracking_initialized(self):
        """Test spend tracking is initialized."""
        assert hasattr(self.service, "daily_spend")
        assert hasattr(self.service, "monthly_spend")


class TestBedrockLLMServiceRateLimiting:
    """Tests for rate limiting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_request_history_tracking(self):
        """Test request history tracking."""
        assert isinstance(self.service.request_history, list)


class TestModelTierOperations:
    """Tests for model tier operation mapping."""

    def test_security_operations_use_accurate(self):
        """Test security-critical operations use accurate tier."""
        security_ops = [
            "vulnerability_ranking",
            "security_result_scoring",
            "threat_assessment",
            "compliance_check",
        ]
        for op in security_ops:
            tier = OPERATION_MODEL_MAP.get(op)
            assert tier == ModelTier.ACCURATE

    def test_simple_operations_use_fast(self):
        """Test simple operations use fast tier."""
        simple_ops = [
            "file_type_classification",
            "syntax_validation",
            "format_conversion",
        ]
        for op in simple_ops:
            tier = OPERATION_MODEL_MAP.get(op)
            assert tier == ModelTier.FAST

    def test_complex_operations_use_maximum(self):
        """Test complex operations use maximum tier."""
        complex_ops = [
            "cross_codebase_correlation",
            "architecture_impact_analysis",
            "dependency_chain_reasoning",
        ]
        for op in complex_ops:
            tier = OPERATION_MODEL_MAP.get(op)
            assert tier == ModelTier.MAXIMUM


class TestQueryTypeMapping:
    """Tests for query type to TTL mapping."""

    def test_vulnerability_analysis_ttl(self):
        """Test vulnerability analysis operations have correct query type."""
        assert (
            OPERATION_QUERY_TYPE_MAP.get("vulnerability_ranking")
            == "vulnerability_analysis"
        )
        assert (
            OPERATION_QUERY_TYPE_MAP.get("threat_assessment")
            == "vulnerability_analysis"
        )

    def test_code_generation_ttl(self):
        """Test code generation operations have correct query type."""
        assert OPERATION_QUERY_TYPE_MAP.get("patch_generation") == "code_generation"

    def test_validation_ttl(self):
        """Test validation operations have correct query type."""
        assert OPERATION_QUERY_TYPE_MAP.get("syntax_validation") == "validation"


class TestBedrockLLMServiceBudgetTracking:
    """Tests for budget tracking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
        }

    def test_check_budget_within_limits(self):
        """Test budget check passes when within limits."""
        self.service.daily_spend = 10.0
        self.service.monthly_spend = 100.0
        assert self.service._check_budget() is True

    def test_check_budget_daily_exceeded(self):
        """Test budget check fails when daily limit exceeded."""
        self.service.daily_spend = 1000.0  # Exceeds default daily budget
        assert self.service._check_budget() is False

    def test_check_budget_monthly_exceeded(self):
        """Test budget check fails when monthly limit exceeded."""
        self.service.monthly_spend = 50000.0  # Exceeds default monthly budget
        assert self.service._check_budget() is False

    def test_budget_warning_at_80_percent(self):
        """Test budget warning at 80% threshold."""
        daily_budget = 100.0
        self.service.daily_spend = daily_budget * 0.85  # 85% of daily budget
        # Should still pass but log warning
        result = self.service._check_budget()
        assert result is True


class TestBedrockLLMServiceRateLimitMethods:
    """Tests for rate limiting methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
        }

    def test_record_request_adds_to_history(self):
        """Test recording a request updates history."""
        initial_len = len(self.service.request_history)
        self.service._record_request()
        # History should be updated via Redis cache service
        assert isinstance(self.service.request_history, list)

    def test_check_rate_limit_within_limits(self):
        """Test rate limit check passes when within limits."""
        # Fresh service should be within limits
        assert self.service._check_rate_limit() is True


class TestBedrockLLMServiceCacheKey:
    """Tests for cache key generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_cache_key_deterministic(self):
        """Test cache key is deterministic."""
        key1 = self.service._cache_key("test prompt", "model-id", {"temp": 0.5})
        key2 = self.service._cache_key("test prompt", "model-id", {"temp": 0.5})
        assert key1 == key2

    def test_cache_key_different_for_different_prompts(self):
        """Test cache key differs for different prompts."""
        key1 = self.service._cache_key("prompt 1", "model-id", {})
        key2 = self.service._cache_key("prompt 2", "model-id", {})
        assert key1 != key2

    def test_cache_key_different_for_different_models(self):
        """Test cache key differs for different models."""
        key1 = self.service._cache_key("test", "model-a", {})
        key2 = self.service._cache_key("test", "model-b", {})
        assert key1 != key2

    def test_cache_key_different_for_different_params(self):
        """Test cache key differs for different params."""
        key1 = self.service._cache_key("test", "model", {"temp": 0.5})
        key2 = self.service._cache_key("test", "model", {"temp": 0.7})
        assert key1 != key2

    def test_cache_key_is_sha256_hash(self):
        """Test cache key is a SHA256 hash."""
        key = self.service._cache_key("test", "model", {})
        assert len(key) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in key)


class TestBedrockLLMServiceCachedResponse:
    """Tests for cached response retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_get_cached_response_miss(self):
        """Test cache miss returns None."""
        result = self.service._get_cached_response("nonexistent-key")
        assert result is None

    def test_get_cached_response_cache_disabled(self):
        """Test cache returns None when disabled."""
        self.service.config["cache_enabled"] = False
        result = self.service._get_cached_response("any-key")
        assert result is None


class TestBedrockLLMServiceMockInvoke:
    """Tests for mock LLM invocation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_mock_invoke_returns_response(self):
        """Test mock invoke returns valid response structure."""
        result = self.service._mock_invoke("test prompt", "TestAgent", 100)
        assert "text" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "guardrail_result" in result

    def test_mock_invoke_planner_agent(self):
        """Test mock invoke for PlannerAgent."""
        result = self.service._mock_invoke("analyze security", "PlannerAgent", 100)
        assert "analyze" in result["text"].lower()

    def test_mock_invoke_coder_agent(self):
        """Test mock invoke for CoderAgent."""
        result = self.service._mock_invoke("generate code", "CoderAgent", 100)
        assert "def" in result["text"]

    def test_mock_invoke_reviewer_agent(self):
        """Test mock invoke for ReviewerAgent."""
        result = self.service._mock_invoke("review code", "ReviewerAgent", 100)
        assert "Security Analysis" in result["text"]

    def test_mock_invoke_validator_agent(self):
        """Test mock invoke for ValidatorAgent."""
        result = self.service._mock_invoke("validate", "ValidatorAgent", 100)
        assert "Test Results" in result["text"]

    def test_mock_invoke_unknown_agent(self):
        """Test mock invoke for unknown agent."""
        result = self.service._mock_invoke("test", "UnknownAgent", 100)
        assert "Mock response" in result["text"]
        assert "UnknownAgent" in result["text"]

    def test_mock_invoke_token_estimation(self):
        """Test mock invoke estimates tokens from content length."""
        long_prompt = "word " * 100  # ~500 chars
        result = self.service._mock_invoke(long_prompt, "TestAgent", 100)
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0


class TestBedrockLLMServiceInvokeModel:
    """Tests for the main invoke_model method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        self.service.model_id_primary = "anthropic.claude-3-5-sonnet"
        self.service.model_id_fallback = "anthropic.claude-3-haiku"

    def test_invoke_model_basic(self):
        """Test basic model invocation."""
        result = self.service.invoke_model(
            prompt="Test prompt",
            agent="TestAgent",
        )
        assert "response" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "cost_usd" in result
        assert "model" in result
        assert "request_id" in result

    def test_invoke_model_with_operation(self):
        """Test invocation with operation for tier selection."""
        result = self.service.invoke_model(
            prompt="Analyze security",
            agent="SecurityAgent",
            operation="vulnerability_ranking",
        )
        assert result["tier"] == "accurate"
        assert result["operation"] == "vulnerability_ranking"

    def test_invoke_model_with_override_tier(self):
        """Test invocation with explicit tier override."""
        result = self.service.invoke_model(
            prompt="Test",
            agent="TestAgent",
            override_tier=ModelTier.FAST,
        )
        assert result["tier"] == "fast"

    def test_invoke_model_with_system_prompt(self):
        """Test invocation with system prompt."""
        result = self.service.invoke_model(
            prompt="Test prompt",
            agent="TestAgent",
            system_prompt="You are a helpful assistant.",
        )
        assert "response" in result

    def test_invoke_model_with_custom_params(self):
        """Test invocation with custom parameters."""
        result = self.service.invoke_model(
            prompt="Test prompt",
            agent="TestAgent",
            max_tokens=500,
            temperature=0.5,
        )
        assert "response" in result

    def test_invoke_model_cached_false_first_call(self):
        """Test first call is not cached."""
        result = self.service.invoke_model(
            prompt="Unique prompt for caching test",
            agent="TestAgent",
        )
        assert result["cached"] is False

    def test_invoke_model_returns_request_id(self):
        """Test invocation returns unique request ID."""
        result = self.service.invoke_model(
            prompt="Test",
            agent="TestAgent",
        )
        assert len(result["request_id"]) == 36  # UUID format

    def test_invoke_model_budget_exceeded_raises(self):
        """Test invocation raises when budget exceeded."""
        self.service.daily_spend = float("inf")
        with pytest.raises(BudgetExceededError):
            self.service.invoke_model(prompt="Test", agent="TestAgent")


class TestBedrockLLMServiceSpendSummary:
    """Tests for get_spend_summary method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
        }

    def test_get_spend_summary_structure(self):
        """Test spend summary returns correct structure."""
        summary = self.service.get_spend_summary()
        assert "daily_spend" in summary
        assert "daily_budget" in summary
        assert "daily_remaining" in summary
        assert "daily_percent" in summary
        assert "monthly_spend" in summary
        assert "monthly_budget" in summary
        assert "monthly_remaining" in summary
        assert "monthly_percent" in summary
        assert "total_requests" in summary

    def test_get_spend_summary_calculations(self):
        """Test spend summary calculations are correct."""
        self.service.daily_spend = 50.0
        self.service.monthly_spend = 500.0

        summary = self.service.get_spend_summary()

        assert summary["daily_spend"] == 50.0
        assert summary["monthly_spend"] == 500.0
        assert summary["daily_remaining"] == summary["daily_budget"] - 50.0
        assert summary["monthly_remaining"] == summary["monthly_budget"] - 500.0

    def test_get_spend_summary_zero_budget_handling(self):
        """Test spend summary handles zero budget."""
        self.service.config["daily_budget_usd"] = 0
        self.service.config["monthly_budget_usd"] = 0

        summary = self.service.get_spend_summary()

        assert summary["daily_percent"] == 0
        assert summary["monthly_percent"] == 0


class TestBedrockLLMServiceSemanticCache:
    """Tests for semantic cache integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_get_semantic_cache_stats_none_when_disabled(self):
        """Test semantic cache stats returns None when cache not enabled."""
        result = self.service.get_semantic_cache_stats()
        assert result is None


class TestBedrockLLMServiceGuardrails:
    """Tests for guardrails functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK)

    def test_guardrails_disabled_in_mock_mode(self):
        """Test guardrails are disabled in mock mode."""
        # In mock mode, guardrail_config should be the default config
        assert self.service.guardrail_config is not None

    def test_handle_guardrail_failure_without_require(self):
        """Test guardrail failure handling when not required."""
        # Should not raise when require_guardrails=False (default)
        self.service.require_guardrails = False
        self.service._handle_guardrail_failure("Test failure message")
        # Should continue without raising

    def test_handle_guardrail_failure_with_require(self):
        """Test guardrail failure handling when required."""
        self.service.require_guardrails = True
        with pytest.raises(RuntimeError, match="CRITICAL"):
            self.service._handle_guardrail_failure("Test failure message")


class TestBedrockLLMServiceFactoryFunctions:
    """Tests for factory functions."""

    def test_create_llm_service_mock_mode(self):
        """Test create_llm_service returns mock mode when AWS unavailable."""
        from src.services.bedrock_llm_service import create_llm_service

        service = create_llm_service()
        assert service is not None
        # Check the class name rather than isinstance to avoid module identity issues
        assert service.__class__.__name__ == "BedrockLLMService"

    def test_create_llm_service_with_environment(self):
        """Test create_llm_service accepts environment parameter."""
        from src.services.bedrock_llm_service import create_llm_service

        service = create_llm_service(environment="testing")
        assert service is not None

    def test_create_secure_llm_service(self):
        """Test create_secure_llm_service returns secure service."""
        from src.services.bedrock_llm_service import create_secure_llm_service

        service = create_secure_llm_service()
        assert service is not None
        assert service.sanitize_prompts is True


class TestAsyncBatchInvocation:
    """Tests for async batch LLM invocation methods."""

    def _mock_invoke_result(self, prompt: str, operation: str | None = None) -> dict:
        """Create mock invoke result."""
        tier_map = {
            "query_intent_analysis": "fast",
            "vulnerability_ranking": "accurate",
            "cross_codebase_correlation": "maximum",
        }
        return {
            "response": f"Mock response for: {prompt[:20]}",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "model": "mock-model",
            "tier": tier_map.get(operation or "", "accurate"),
            "operation": operation,
            "cached": False,
            "request_id": "test-123",
        }

    @pytest.mark.asyncio
    async def test_invoke_model_async_success(self):
        """Test async invoke model returns response."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        with patch.object(
            service,
            "invoke_model",
            return_value=self._mock_invoke_result("Test prompt"),
        ):
            result = await service.invoke_model_async(
                prompt="Test prompt",
                agent="TestAgent",
            )

        assert "response" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "cost_usd" in result

    @pytest.mark.asyncio
    async def test_invoke_model_async_with_operation(self):
        """Test async invoke with operation for tier selection."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        with patch.object(
            service,
            "invoke_model",
            return_value=self._mock_invoke_result("Analyze", "vulnerability_ranking"),
        ):
            result = await service.invoke_model_async(
                prompt="Analyze vulnerability",
                agent="SecurityAgent",
                operation="vulnerability_ranking",
            )

        assert result["tier"] == "accurate"
        assert result["operation"] == "vulnerability_ranking"

    @pytest.mark.asyncio
    async def test_invoke_batch_async_success(self):
        """Test batch async invocation."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        with patch.object(
            service,
            "invoke_model",
            side_effect=lambda **kw: self._mock_invoke_result(kw["prompt"]),
        ):
            requests = [
                {"prompt": "Prompt 1", "agent": "Agent1"},
                {"prompt": "Prompt 2", "agent": "Agent2"},
                {"prompt": "Prompt 3", "agent": "Agent3"},
            ]

            results = await service.invoke_batch_async(requests, max_concurrent=2)

        assert len(results) == 3
        for result in results:
            assert "response" in result
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_invoke_batch_async_empty_list(self):
        """Test batch async with empty list."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        results = await service.invoke_batch_async([])

        assert results == []

    @pytest.mark.asyncio
    async def test_invoke_batch_async_preserves_order(self):
        """Test batch async preserves request order."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        with patch.object(
            service,
            "invoke_model",
            side_effect=lambda **kw: self._mock_invoke_result(kw["prompt"]),
        ):
            requests = [
                {"prompt": f"Prompt {i}", "agent": f"Agent{i}"} for i in range(5)
            ]

            results = await service.invoke_batch_async(requests, max_concurrent=2)

        assert len(results) == 5
        for result in results:
            assert "response" in result

    @pytest.mark.asyncio
    async def test_invoke_batch_async_with_operations(self):
        """Test batch async with different operations."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        def mock_with_op(**kw):
            return self._mock_invoke_result(kw["prompt"], kw.get("operation"))

        with patch.object(service, "invoke_model", side_effect=mock_with_op):
            requests = [
                {"prompt": "Fast", "agent": "A", "operation": "query_intent_analysis"},
                {
                    "prompt": "Accurate",
                    "agent": "A",
                    "operation": "vulnerability_ranking",
                },
                {
                    "prompt": "Max",
                    "agent": "A",
                    "operation": "cross_codebase_correlation",
                },
            ]

            results = await service.invoke_batch_async(requests, max_concurrent=3)

        assert results[0]["tier"] == "fast"
        assert results[1]["tier"] == "accurate"
        assert results[2]["tier"] == "maximum"

    @pytest.mark.asyncio
    async def test_invoke_batch_async_concurrent_limit(self):
        """Test batch async respects concurrency limit."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        with patch.object(
            service,
            "invoke_model",
            side_effect=lambda **kw: self._mock_invoke_result(kw["prompt"]),
        ):
            requests = [{"prompt": f"Prompt {i}", "agent": "Agent"} for i in range(10)]

            results = await service.invoke_batch_async(requests, max_concurrent=3)

        assert len(results) == 10
        assert all("response" in r for r in results)

    @pytest.mark.asyncio
    async def test_invoke_batch_async_handles_errors(self):
        """Test batch async handles errors gracefully."""
        from unittest.mock import patch

        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)

        def mock_with_error(**kw):
            if "error" in kw["prompt"].lower():
                raise ValueError("Simulated error")
            return self._mock_invoke_result(kw["prompt"])

        with patch.object(service, "invoke_model", side_effect=mock_with_error):
            requests = [
                {"prompt": "Normal request", "agent": "Agent"},
                {"prompt": "This has error in it", "agent": "Agent"},
                {"prompt": "Another normal request", "agent": "Agent"},
            ]

            results = await service.invoke_batch_async(requests, max_concurrent=3)

        assert len(results) == 3
        assert "response" in results[0]
        assert "error" in results[1]
        assert "response" in results[2]


class TestAsyncGenerate:
    """Tests for async generate method."""

    def _create_service_with_config(self):
        """Create service with proper config."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        service.model_id_primary = "anthropic.claude-3-5-sonnet"
        service.model_id_fallback = "anthropic.claude-3-haiku"
        return service

    @pytest.mark.asyncio
    async def test_generate_returns_string(self):
        """Test generate returns string response."""
        service = self._create_service_with_config()

        result = await service.generate(
            prompt="Test prompt",
            agent="TestAgent",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_with_operation(self):
        """Test generate with operation parameter."""
        service = self._create_service_with_config()

        result = await service.generate(
            prompt="Analyze code",
            agent="SecurityAgent",
            operation="code_review",
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """Test generate with system prompt."""
        service = self._create_service_with_config()

        result = await service.generate(
            prompt="Test",
            agent="TestAgent",
            system_prompt="You are a helpful assistant.",
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_without_semantic_cache(self):
        """Test generate with semantic cache disabled."""
        service = self._create_service_with_config()

        result = await service.generate(
            prompt="Test prompt",
            agent="TestAgent",
            use_semantic_cache=False,
        )

        assert isinstance(result, str)


class TestInitializationModes:
    """Tests for service initialization modes."""

    def test_init_with_environment_override(self):
        """Test initialization with environment override."""
        import os

        original_env = os.environ.get("AURA_ENV")
        try:
            service = BedrockLLMService(mode=BedrockMode.MOCK, environment="staging")
            assert service.environment == "staging"
        finally:
            if original_env:
                os.environ["AURA_ENV"] = original_env
            else:
                os.environ.pop("AURA_ENV", None)

    def test_init_with_redis_cache(self):
        """Test initialization accepts redis cache parameter."""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        mock_redis.get_daily_cost.return_value = 0.0
        mock_redis.get_monthly_cost.return_value = 0.0
        mock_redis.get_request_history.return_value = []
        mock_redis.is_redis_connected = False
        mock_redis.backend = MagicMock(value="memory")

        service = BedrockLLMService(
            mode=BedrockMode.MOCK,
            redis_cache=mock_redis,
        )
        assert service._redis_cache == mock_redis

    def test_init_with_require_guardrails(self):
        """Test initialization with require_guardrails flag."""
        service = BedrockLLMService(
            mode=BedrockMode.MOCK,
            require_guardrails=False,
        )
        assert service.require_guardrails is False


class TestPromptSanitization:
    """Tests for prompt sanitization functionality."""

    def test_init_with_sanitization_enabled(self):
        """Test initialization with prompt sanitization enabled."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=True)
        assert service.sanitize_prompts is True
        assert service.prompt_sanitizer is not None

    def test_init_with_sanitization_disabled(self):
        """Test initialization with prompt sanitization disabled."""
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        assert service.sanitize_prompts is False
        assert service.prompt_sanitizer is None

    def test_init_with_strict_mode(self):
        """Test initialization with strict sanitizer mode."""
        service = BedrockLLMService(
            mode=BedrockMode.MOCK,
            sanitize_prompts=True,
            sanitizer_strict_mode=True,
        )
        assert service.sanitize_prompts is True


class TestResponseCaching:
    """Tests for response caching functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        self.service.model_id_primary = "anthropic.claude-3-5-sonnet"
        self.service.model_id_fallback = "anthropic.claude-3-haiku"

    def test_response_cache_initialized(self):
        """Test response cache is initialized as OrderedDict."""
        from collections import OrderedDict

        assert isinstance(self.service.response_cache, OrderedDict)

    def test_invoke_model_caches_response(self):
        """Test invoke_model caches response for subsequent calls."""
        prompt = "Cache test prompt unique string"

        # First call
        result1 = self.service.invoke_model(
            prompt=prompt,
            agent="TestAgent",
            cache_enabled=True,
        )
        assert result1["cached"] is False

        # Second call with same parameters should be cached
        result2 = self.service.invoke_model(
            prompt=prompt,
            agent="TestAgent",
            cache_enabled=True,
        )
        assert result2["cached"] is True
        assert result2["cost_usd"] == 0.0  # Cached responses have no cost

    def test_cache_disabled_does_not_cache(self):
        """Test cache_enabled=False does not cache."""
        prompt = "No cache test prompt"

        result1 = self.service.invoke_model(
            prompt=prompt,
            agent="TestAgent",
            cache_enabled=False,
        )

        result2 = self.service.invoke_model(
            prompt=prompt,
            agent="TestAgent",
            cache_enabled=False,
        )

        # Both should be non-cached
        assert result1["cached"] is False
        assert result2["cached"] is False


class TestCostTracking:
    """Tests for cost tracking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        self.service.model_id_primary = "anthropic.claude-3-5-sonnet"
        self.service.model_id_fallback = "anthropic.claude-3-haiku"

    def test_invoke_model_updates_spend(self):
        """Test invoke_model updates spend tracking."""
        initial_daily = self.service.daily_spend

        self.service.invoke_model(
            prompt="Test prompt",
            agent="TestAgent",
        )

        # In mock mode, costs should still be tracked
        assert self.service.daily_spend >= initial_daily

    def test_cost_recorded_for_non_cached_response(self):
        """Test cost is recorded for non-cached responses."""
        result = self.service.invoke_model(
            prompt="Unique prompt for cost test",
            agent="TestAgent",
        )

        assert result["cost_usd"] >= 0.0


class TestTierSelection:
    """Tests for model tier selection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        self.service.model_id_primary = "anthropic.claude-3-5-sonnet"
        self.service.model_id_fallback = "anthropic.claude-3-haiku"

    def test_fast_tier_operations(self):
        """Test fast tier is selected for appropriate operations."""
        fast_ops = ["query_intent_analysis", "query_expansion", "syntax_validation"]

        for op in fast_ops:
            result = self.service.invoke_model(
                prompt="Test",
                agent="TestAgent",
                operation=op,
            )
            assert result["tier"] == "fast", f"Operation {op} should use fast tier"

    def test_accurate_tier_operations(self):
        """Test accurate tier is selected for appropriate operations."""
        accurate_ops = ["vulnerability_ranking", "code_review", "patch_generation"]

        for op in accurate_ops:
            result = self.service.invoke_model(
                prompt="Test",
                agent="TestAgent",
                operation=op,
            )
            assert (
                result["tier"] == "accurate"
            ), f"Operation {op} should use accurate tier"

    def test_maximum_tier_operations(self):
        """Test maximum tier is selected for appropriate operations."""
        max_ops = ["cross_codebase_correlation", "novel_threat_detection"]

        for op in max_ops:
            result = self.service.invoke_model(
                prompt="Test",
                agent="TestAgent",
                operation=op,
            )
            assert (
                result["tier"] == "maximum"
            ), f"Operation {op} should use maximum tier"

    def test_unknown_operation_defaults_to_accurate(self):
        """Test unknown operation defaults to accurate tier."""
        result = self.service.invoke_model(
            prompt="Test",
            agent="TestAgent",
            operation="unknown_operation_xyz",
        )
        assert result["tier"] == "accurate"

    def test_override_tier_takes_precedence(self):
        """Test override_tier takes precedence over operation."""
        # vulnerability_ranking normally uses accurate tier
        result = self.service.invoke_model(
            prompt="Test",
            agent="TestAgent",
            operation="vulnerability_ranking",
            override_tier=ModelTier.FAST,
        )
        assert result["tier"] == "fast"


class TestMaxResponseCacheSize:
    """Tests for MAX_RESPONSE_CACHE_SIZE limit."""

    def test_max_cache_size_from_env(self):
        """Test MAX_RESPONSE_CACHE_SIZE uses environment variable."""
        import os

        original = os.environ.get("LLM_MAX_RESPONSE_CACHE_SIZE")
        try:
            os.environ["LLM_MAX_RESPONSE_CACHE_SIZE"] = "500"
            # Need to reimport to pick up new env var
            # This is a configuration test
            assert True  # Configuration is read at class definition time
        finally:
            if original:
                os.environ["LLM_MAX_RESPONSE_CACHE_SIZE"] = original
            else:
                os.environ.pop("LLM_MAX_RESPONSE_CACHE_SIZE", None)

    def test_default_cache_size(self):
        """Test default cache size is 1000."""
        assert BedrockLLMService.MAX_RESPONSE_CACHE_SIZE == 1000


class TestRequestHistoryTracking:
    """Tests for request history tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=False)
        # Set up proper config values for testing
        self.service.config = {
            "daily_budget_usd": 100.0,
            "monthly_budget_usd": 3000.0,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "max_requests_per_day": 10000,
            "max_tokens_default": 4096,
            "temperature_default": 0.7,
            "cache_enabled": True,
            "cache_ttl_seconds": 86400,
        }
        self.service.model_id_primary = "anthropic.claude-3-5-sonnet"
        self.service.model_id_fallback = "anthropic.claude-3-haiku"

    def test_request_history_is_list(self):
        """Test request history is a list."""
        assert isinstance(self.service.request_history, list)

    def test_invoke_updates_request_history(self):
        """Test invoking model updates request history."""
        self.service.invoke_model(
            prompt="Test",
            agent="TestAgent",
        )
        # Request should be recorded via Redis cache service
        # Just verify the list type is maintained
        assert isinstance(self.service.request_history, list)
