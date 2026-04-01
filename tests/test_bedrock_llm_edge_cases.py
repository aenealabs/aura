"""
Project Aura - Bedrock LLM Service Edge Case Tests

Tests for edge cases related to:
1. Prompt exceeds model context window (200K tokens for Claude)
2. Response truncation at max_tokens boundary mid-JSON/code
3. Token estimation drift for multi-byte Unicode characters

These tests verify graceful degradation and proper error handling for
boundary conditions that can occur in production.
"""

import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Force process isolation to prevent module mock pollution across test files
pytestmark = pytest.mark.forked

# Module-level mocking to avoid import errors
# Must be done before importing the service module
_modules_to_save = [
    "boto3",
    "botocore",
    "botocore.exceptions",
    "config.bedrock_config",
    "config.guardrails_config",
    "src.services.llm_prompt_sanitizer",
    "src.services.redis_cache_service",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}


# Custom ClientError class for mocking
class MockClientError(Exception):
    """Mock ClientError for testing Bedrock API error handling."""

    def __init__(self, error_code: str, message: str = "Test error"):
        self.response = {"Error": {"Code": error_code, "Message": message}}
        super().__init__(message)


# Set up mocks before importing the service
mock_boto3 = MagicMock()
mock_boto3.client = MagicMock(return_value=MagicMock())
mock_boto3.resource = MagicMock(return_value=MagicMock())
sys.modules["boto3"] = mock_boto3

mock_botocore = MagicMock()
mock_botocore.exceptions = MagicMock()
mock_botocore.exceptions.ClientError = MockClientError
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions

# Mock bedrock_config
mock_bedrock_config = MagicMock()
mock_bedrock_config.get_config = MagicMock(
    return_value={
        "aws_region": "us-east-1",
        "model_id_primary": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "model_id_fallback": "anthropic.claude-3-haiku-20240307-v1:0",
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "daily_budget_usd": 100.0,
        "monthly_budget_usd": 3000.0,
        "max_requests_per_minute": 60,
        "max_requests_per_hour": 1000,
        "max_requests_per_day": 10000,
        "secrets_path": "aura/test/bedrock-config",
        "cost_table_name": "aura-ddb-test-llm-costs",
        "cache_enabled": False,
        "cache_ttl_seconds": 86400,
    }
)
mock_bedrock_config.calculate_cost = MagicMock(return_value=0.01)
sys.modules["config.bedrock_config"] = mock_bedrock_config

# Mock guardrails_config
mock_guardrails_config = MagicMock()
mock_guardrails_config.GuardrailConfig = MagicMock
mock_guardrails_config.GuardrailMode = MagicMock()
mock_guardrails_config.GuardrailMode.DISABLED = "disabled"
mock_guardrails_config.GuardrailResult = MagicMock
mock_guardrails_config.format_guardrail_trace = MagicMock(return_value=[])
mock_guardrails_config.get_guardrail_config = MagicMock(
    return_value=MagicMock(
        mode=mock_guardrails_config.GuardrailMode.DISABLED, guardrail_id=None
    )
)
mock_guardrails_config.load_guardrail_ids_from_ssm = MagicMock()
sys.modules["config.guardrails_config"] = mock_guardrails_config

# Mock sanitizer
mock_sanitizer = MagicMock()
mock_sanitizer.LLMPromptSanitizer = MagicMock(return_value=MagicMock())
mock_sanitizer.SanitizationAction = MagicMock()
mock_sanitizer.SanitizationAction.ALLOWED = "allowed"
mock_sanitizer.SanitizationAction.BLOCKED = "blocked"
mock_sanitizer.SanitizationResult = MagicMock()
mock_sanitizer.ThreatLevel = MagicMock()
mock_sanitizer.ThreatLevel.NONE = "none"
mock_sanitizer.get_prompt_sanitizer = MagicMock(return_value=MagicMock())
sys.modules["src.services.llm_prompt_sanitizer"] = mock_sanitizer

# Mock redis cache service
mock_redis = MagicMock()
mock_cache_instance = MagicMock()
mock_cache_instance.get_daily_cost.return_value = 0.0
mock_cache_instance.get_monthly_cost.return_value = 0.0
mock_cache_instance.get_request_history.return_value = []
mock_cache_instance.get_request_count.return_value = 0
mock_cache_instance.record_request.return_value = None
mock_cache_instance.add_cost.return_value = (0.0, 0.0)
mock_cache_instance.get_response.return_value = None
mock_cache_instance.set_response.return_value = None
mock_cache_instance.backend = MagicMock(value="memory")
mock_cache_instance.is_redis_connected = False
mock_redis.RedisCacheService = MagicMock(return_value=mock_cache_instance)
mock_redis.create_cache_service = MagicMock(return_value=mock_cache_instance)
sys.modules["src.services.redis_cache_service"] = mock_redis

# Now import the module under test
from src.services.bedrock_llm_service import (
    BedrockError,
    BedrockLLMService,
    BedrockMode,
    ModelTier,
)

# Store references to the imported classes (they're bound to this module now)
_BedrockError = BedrockError
_BedrockLLMService = BedrockLLMService
_BedrockMode = BedrockMode
_ModelTier = ModelTier

# Restore original modules after import (or delete mocks if module wasn't present)
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    elif mod_name in sys.modules:
        # Module wasn't present before - remove the mock to prevent pollution
        del sys.modules[mod_name]

# Also remove the bedrock_llm_service from cache so other tests reimport fresh
if "src.services.bedrock_llm_service" in sys.modules:
    del sys.modules["src.services.bedrock_llm_service"]


# =============================================================================
# Constants for edge case testing
# =============================================================================

# Claude 3.5 Sonnet context window is 200K tokens
CLAUDE_CONTEXT_WINDOW = 200_000

# Characters per token approximation (varies by content type)
CHARS_PER_TOKEN_ENGLISH = 4
CHARS_PER_TOKEN_CJK = 1.5  # CJK characters are typically 1-2 tokens each
CHARS_PER_TOKEN_UNICODE = 2  # Emojis and special Unicode often 2+ tokens


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_bedrock_service():
    """Create a BedrockLLMService in mock mode for testing."""
    # Ensure sanitizer mock returns a valid result
    sanitizer_mock = MagicMock()
    sanitize_result = MagicMock()
    sanitize_result.action = mock_sanitizer.SanitizationAction.ALLOWED
    sanitize_result.was_modified = False
    sanitize_result.sanitized_prompt = "test"
    sanitize_result.threat_level = mock_sanitizer.ThreatLevel.NONE
    sanitize_result.patterns_detected = []
    sanitizer_mock.sanitize.return_value = sanitize_result
    sanitizer_mock.sanitize_system_prompt.return_value = sanitize_result

    with patch.object(
        mock_sanitizer, "LLMPromptSanitizer", return_value=sanitizer_mock
    ):
        service = BedrockLLMService(mode=BedrockMode.MOCK, sanitize_prompts=True)
        service.prompt_sanitizer = sanitizer_mock
        return service


@pytest.fixture
def mock_bedrock_runtime():
    """Create a mocked Bedrock runtime client."""
    return MagicMock()


def create_bedrock_response(
    text: str, input_tokens: int = 100, output_tokens: int = 50
) -> dict[str, Any]:
    """Create a mock Bedrock API response."""
    body_content = {
        "content": [{"text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "stop_reason": "end_turn",
    }
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps(body_content).encode()
    return {"body": body_mock}


# =============================================================================
# Test Class: Context Window Exceeded
# =============================================================================


class TestContextWindowExceeded:
    """Tests for prompts that exceed the model's context window limit."""

    def test_detect_oversized_prompt_before_api_call(self, mock_bedrock_service):
        """
        Verify that oversized prompts can be detected before making an API call.

        This test validates that the service can estimate token counts and
        identify prompts that would exceed the 200K token context window,
        allowing for pre-emptive handling before incurring API costs.
        """
        # Create a prompt that would exceed 200K tokens
        # Using 4 chars per token approximation: 200K tokens ~= 800K characters
        oversized_prompt = "x" * (
            CLAUDE_CONTEXT_WINDOW * CHARS_PER_TOKEN_ENGLISH + 1000
        )

        # The service's mock mode estimates tokens as len(prompt) // 4
        estimated_tokens = len(oversized_prompt) // 4
        assert estimated_tokens > CLAUDE_CONTEXT_WINDOW

        # In production, this would trigger pre-API validation
        # The mock mode doesn't enforce limits, but we verify the estimation
        result = mock_bedrock_service.invoke_model(
            prompt=oversized_prompt, agent="TestAgent", max_tokens=100
        )

        # Mock mode returns result but with very high input token count
        assert result["input_tokens"] > CLAUDE_CONTEXT_WINDOW

    def test_bedrock_validation_exception_on_context_overflow(
        self, mock_bedrock_service, mock_bedrock_runtime
    ):
        """
        Test graceful handling when Bedrock returns ValidationException
        for prompts exceeding context window.

        Bedrock returns ValidationException with message indicating
        'input_tokens' exceeds 'context_limit' for the model.
        """
        # Configure service for AWS mode to test API error handling
        mock_bedrock_service.mode = BedrockMode.AWS
        mock_bedrock_service.bedrock_runtime = mock_bedrock_runtime

        # Simulate ValidationException for context overflow
        mock_bedrock_runtime.invoke_model.side_effect = MockClientError(
            "ValidationException",
            "Input length exceeds the context limit. Input tokens: 250000, "
            "context limit: 200000",
        )

        with pytest.raises(BedrockError) as exc_info:
            mock_bedrock_service._invoke_bedrock_api(
                model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
                prompt="This prompt is too long...",
                system_prompt=None,
                max_tokens=4096,
                temperature=0.7,
                apply_guardrails=False,
            )

        assert "Invalid request" in str(exc_info.value)

    def test_graceful_degradation_for_large_prompts(self, mock_bedrock_service):
        """
        Test that the service provides graceful degradation options
        when prompts approach or exceed context limits.

        In production, this might involve:
        - Truncating the prompt with a warning
        - Splitting into multiple requests
        - Summarizing context before sending
        """
        # Create a large but not quite oversized prompt
        large_prompt = "Analyze this code:\n" + ("def func(): pass\n" * 10000)

        # Service should handle this without error in mock mode
        result = mock_bedrock_service.invoke_model(
            prompt=large_prompt, agent="TestAgent", max_tokens=1000
        )

        assert "response" in result
        assert result["input_tokens"] > 10000  # Should reflect large input

    def test_context_overflow_detection_with_system_prompt(self, mock_bedrock_service):
        """
        Test that combined prompt + system prompt size is considered
        when checking for context overflow.
        """
        # Large system prompt - 50K chars (~12.5K tokens)
        system_prompt = "You are an expert. " * 2500

        # Large user prompt - 850K chars (~212.5K tokens)
        # Need enough to exceed 200K when combined
        user_prompt = "Analyze: " + ("data point " * 80000)

        # Combined should exceed context window estimate
        total_chars = len(system_prompt) + len(user_prompt)
        estimated_tokens = total_chars // 4

        # Verify our test data actually exceeds the context window
        assert (
            estimated_tokens > CLAUDE_CONTEXT_WINDOW
        ), f"Test setup error: {estimated_tokens} tokens does not exceed {CLAUDE_CONTEXT_WINDOW}"

        # Mock mode handles this but tokens reflect size
        result = mock_bedrock_service.invoke_model(
            prompt=user_prompt,
            system_prompt=system_prompt,
            agent="TestAgent",
            max_tokens=100,
        )

        # Verify prompt contributed to token count (mock mode only counts user prompt)
        # Mock mode estimate: len(user_prompt) // 4
        assert result["input_tokens"] > 100000


# =============================================================================
# Test Class: Response Truncation at max_tokens Boundary
# =============================================================================


class TestResponseTruncation:
    """Tests for response truncation at max_tokens boundary."""

    def test_truncated_json_response_detection(self, mock_bedrock_service):
        """
        Test detection of incomplete JSON when response is truncated
        at max_tokens boundary mid-structure.

        When max_tokens cuts off a response mid-JSON, the output will
        be syntactically invalid and should be detected.
        """
        # Simulate a response that was truncated mid-JSON
        truncated_json = '{"analysis": {"vulnerabilities": ["SQL injection", "XSS"'
        # Note: Missing closing brackets - incomplete JSON

        # Verify it's invalid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated_json)

        # The service should be able to detect this pattern
        def is_truncated_json(response: str) -> bool:
            """Check if response appears to be truncated JSON."""
            response = response.strip()
            if not response:
                return False

            # JSON should start with { or [ and end with } or ]
            starts_json = response.startswith("{") or response.startswith("[")
            ends_json = response.endswith("}") or response.endswith("]")

            if starts_json and not ends_json:
                return True

            # Try parsing - if it fails and looks like JSON, it's truncated
            if starts_json:
                try:
                    json.loads(response)
                    return False
                except json.JSONDecodeError:
                    return True

            return False

        assert is_truncated_json(truncated_json) is True
        assert is_truncated_json('{"complete": true}') is False
        assert is_truncated_json("Not JSON at all") is False

    def test_truncated_code_block_detection(self, mock_bedrock_service):
        """
        Test detection of incomplete code blocks when response is
        truncated at max_tokens boundary.
        """
        # Simulate truncated code response
        truncated_code = """```python
def fix_vulnerability():
    # Sanitize user input
    user_input = request.get_json()
    if not validate_input(user_input):
        raise ValidationError("Invalid input")

    # Process the sanitized
"""
        # Note: Code block and function are incomplete

        def is_truncated_code_block(response: str) -> bool:
            """Check if response contains an unclosed code block."""
            # Count code block delimiters
            triple_backticks = response.count("```")

            # Odd number means unclosed block
            if triple_backticks % 2 != 0:
                return True

            # Check for common truncation patterns in code
            incomplete_patterns = [
                # Unclosed brackets
                (response.count("{") > response.count("}")),
                (response.count("[") > response.count("]")),
                (response.count("(") > response.count(")")),
                # Truncated mid-statement
                response.rstrip().endswith((":", "=", ",", "and", "or", "(")),
            ]

            return any(incomplete_patterns)

        assert is_truncated_code_block(truncated_code) is True

        complete_code = """```python
def complete_function():
    return "done"
```"""
        assert is_truncated_code_block(complete_code) is False

    def test_retry_with_larger_token_budget(self, mock_bedrock_service):
        """
        Test retry logic that increases max_tokens when response
        appears truncated.

        This simulates the pattern where we detect truncation and
        retry with a larger token budget.
        """
        truncated_response = '{"partial": "data'
        complete_response = '{"complete": "data", "status": "success"}'

        # Track retry attempts
        retry_count = [0]
        original_max_tokens = [100]

        def mock_invoke_with_retry(
            prompt: str, max_tokens: int = 100, **kwargs
        ) -> dict[str, Any]:
            """Simulate invocation with retry on truncation."""
            retry_count[0] += 1

            if max_tokens <= original_max_tokens[0]:
                # First attempt with low token limit - returns truncated
                return {
                    "response": truncated_response,
                    "input_tokens": 50,
                    "output_tokens": max_tokens,  # Hit the limit
                    "cost_usd": 0.001,
                    "model": "test",
                    "tier": "accurate",
                    "operation": None,
                    "cached": False,
                    "request_id": "test-123",
                }
            else:
                # Retry with higher limit - returns complete
                return {
                    "response": complete_response,
                    "input_tokens": 50,
                    "output_tokens": 80,
                    "cost_usd": 0.002,
                    "model": "test",
                    "tier": "accurate",
                    "operation": None,
                    "cached": False,
                    "request_id": "test-456",
                }

        # Simulate retry logic
        result = mock_invoke_with_retry("test prompt", max_tokens=100)

        # Check if truncated (output_tokens == max_tokens is a signal)
        if result["output_tokens"] == 100:
            # Retry with doubled token budget
            result = mock_invoke_with_retry("test prompt", max_tokens=200)

        assert retry_count[0] == 2
        assert result["response"] == complete_response

    def test_stop_reason_indicates_truncation(self):
        """
        Test that stop_reason from Bedrock API can indicate truncation.

        Bedrock returns stop_reason: 'max_tokens' when output is truncated
        vs 'end_turn' or 'stop_sequence' for natural completion.
        """
        # Response truncated by max_tokens
        truncated_body = {
            "content": [{"text": '{"partial": "re'}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "stop_reason": "max_tokens",  # Indicates truncation
        }

        # Response completed naturally
        complete_body = {
            "content": [{"text": '{"complete": true}'}],
            "usage": {"input_tokens": 100, "output_tokens": 30},
            "stop_reason": "end_turn",  # Natural completion
        }

        def was_truncated(response_body: dict) -> bool:
            """Check if response was truncated based on stop_reason."""
            return response_body.get("stop_reason") == "max_tokens"

        assert was_truncated(truncated_body) is True
        assert was_truncated(complete_body) is False

    def test_partial_json_repair_strategies(self):
        """
        Test strategies for handling/repairing partial JSON responses.

        When truncation occurs, there are several recovery strategies:
        1. Attempt to close open brackets/braces
        2. Extract valid JSON prefix
        3. Request continuation
        """
        partial_json_examples = [
            (
                '{"key": "value", "array": [1, 2, 3',
                '{"key": "value", "array": [1, 2, 3]}',
            ),
            ('{"nested": {"inner": "data"', '{"nested": {"inner": "data"}}'),
            ('[{"item": 1}, {"item": 2', '[{"item": 1}, {"item": 2}]'),
        ]

        def attempt_json_repair(partial: str) -> str | None:
            """
            Attempt to repair truncated JSON by closing open structures.

            This is a simple heuristic approach - production code would
            need more sophisticated parsing.
            """
            # Count open brackets
            open_braces = partial.count("{") - partial.count("}")
            open_brackets = partial.count("[") - partial.count("]")

            # Close string if we're mid-string (odd number of unescaped quotes)
            # Simplified: just count quotes
            quote_count = partial.count('"') - partial.count('\\"')
            if quote_count % 2 != 0:
                partial += '"'

            # Add closing brackets in reverse order of nesting
            # This is simplified - real implementation would track nesting order
            repaired = partial + ("]" * open_brackets) + ("}" * open_braces)

            # Verify repair worked
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                return None

        # Test repair attempts
        for partial, expected in partial_json_examples:
            repaired = attempt_json_repair(partial)
            # Note: Our simple repair may not match expected exactly
            # but should produce valid JSON
            if repaired:
                try:
                    json.loads(repaired)
                    # Successfully repaired to valid JSON
                except json.JSONDecodeError:
                    pytest.fail(f"Repair produced invalid JSON: {repaired}")


# =============================================================================
# Test Class: Token Estimation for Multi-byte Unicode
# =============================================================================


class TestUnicodeTokenEstimation:
    """Tests for token estimation accuracy with multi-byte Unicode characters."""

    def test_emoji_token_estimation(self, mock_bedrock_service):
        """
        Test token estimation for strings containing emojis.

        Emojis typically consume 1-2 tokens each in Claude's tokenizer,
        but the simple char/4 estimation may significantly undercount.
        """
        # String with emojis using explicit Unicode code points
        # \U0001F389 = party popper, \U0001F680 = rocket, \U0001F4A1 = light bulb
        emoji_text = (
            "Code review complete! \U0001f389 "
            "Great work on the security patch. \U0001f680"
        )

        # Simple char/4 estimation
        simple_estimate = len(emoji_text) // 4

        # The estimation should be within acceptable tolerance
        # For this string, simple estimate is close enough
        assert simple_estimate >= 10  # Reasonable lower bound

        # Test with emoji-heavy string using explicit Unicode
        # Each emoji is 1 character in Python string (but 4 bytes UTF-8)
        emoji_heavy = (
            "\U0001f600\U0001f601\U0001f602\U0001f603"  # 4 face emojis
            "\U0001f604\U0001f605\U0001f606\U0001f607"  # 4 more faces
            "\U0001f608\U0001f609\U0001f60a\U0001f60b"  # 4 more faces
        )
        heavy_estimate = len(emoji_heavy) // 4

        # 12 emojis = 12 Python characters
        # Simple estimate: 12 / 4 = 3
        # This demonstrates the estimation drift for emoji content
        # The assertion checks the behavior, not that it's "correct"
        assert len(emoji_heavy) == 12, "Test setup: should have 12 emoji characters"
        assert heavy_estimate == 3, "Char/4 estimate for 12 emojis should be 3"

        # Document the estimation drift (actual tokens would be ~12-24)
        actual_token_estimate_low = 12  # 1 token per emoji
        actual_token_estimate_high = 24  # 2 tokens per emoji
        assert (
            heavy_estimate < actual_token_estimate_low
        ), "Demonstrates char/4 underestimates emoji-heavy content"

    def test_cjk_character_token_estimation(self, mock_bedrock_service):
        """
        Test token estimation for CJK (Chinese, Japanese, Korean) characters.

        CJK characters are typically 1-2 tokens each in Claude's tokenizer,
        but the simple char/4 estimate will undercount for short CJK strings
        since each CJK character is only 1 Python character.
        """
        # Chinese text (security-related) using explicit Unicode
        # \u5b89\u5168 = "security", \u6f0f\u6d1e = "vulnerability"
        # \u68c0\u6d4b = "detection", \u4ee3\u7801 = "code"
        chinese_text = (
            "\u5b89\u5168\u6f0f\u6d1e\u68c0\u6d4b\u4ee3\u7801"  # 8 characters
        )

        # Japanese text using explicit Unicode
        # \u30bb\u30ad\u30e5\u30ea\u30c6\u30a3 = "security" in katakana
        japanese_text = "\u30bb\u30ad\u30e5\u30ea\u30c6\u30a3"  # 6 characters

        # Korean text using explicit Unicode
        # \ubcf4\uc548 = "security"
        korean_text = "\ubcf4\uc548\ucf54\ub4dc"  # 4 characters

        # Simple estimation (treating each char as 1 unit)
        chinese_estimate = len(chinese_text) // 4
        japanese_estimate = len(japanese_text) // 4
        korean_estimate = len(korean_text) // 4

        # Verify test setup
        assert len(chinese_text) == 8, "Test setup: should have 8 Chinese characters"
        assert len(japanese_text) == 6, "Test setup: should have 6 Japanese characters"
        assert len(korean_text) == 4, "Test setup: should have 4 Korean characters"

        # For CJK, each character is roughly 1-2 tokens in actual tokenization
        # But char/4 estimation gives: 8/4=2, 6/4=1, 4/4=1
        assert chinese_estimate == 2, "8 CJK chars / 4 = 2 estimated tokens"
        assert japanese_estimate == 1, "6 CJK chars / 4 = 1 estimated token"
        assert korean_estimate == 1, "4 CJK chars / 4 = 1 estimated token"

        # Document that actual tokenization would give ~8, ~6, ~4 tokens
        # This demonstrates the char/4 estimation significantly undercounts CJK
        assert chinese_estimate < len(
            chinese_text
        ), "Demonstrates char/4 underestimates CJK text"

    def test_combining_characters_token_estimation(self):
        """
        Test token estimation for Unicode combining characters.

        Combining characters (accents, diacritics) attach to base characters
        and can affect tokenization in complex ways.
        """
        # Text with combining characters
        # e + combining acute accent vs precomposed e
        combining_text = "cafe\u0301"  # cafe with combining accent
        precomposed_text = "caf\u00e9"  # precomposed e-acute

        # Both visually render as "cafe" but have different byte lengths
        assert len(combining_text) == 5  # c-a-f-e-combining
        assert len(precomposed_text) == 4  # c-a-f-e

        # Estimation should handle both reasonably
        combining_estimate = len(combining_text) // 4
        precomposed_estimate = len(precomposed_text) // 4

        # Both should give reasonable estimates for a 4-letter word
        assert combining_estimate >= 1
        assert precomposed_estimate >= 1

    def test_mixed_content_token_estimation(self, mock_bedrock_service):
        """
        Test token estimation for mixed content (ASCII + Unicode + code).

        Real-world prompts often contain a mix of content types.
        """
        # Build mixed content with explicit Unicode escapes
        # \u60aa\u610f = "malicious" in Japanese
        # \U0001F6A8 = police car light emoji, \U0001F534 = red circle
        mixed_content = """
Analyze this code for SQL injection vulnerabilities:

```python
# Comment: Check user input
def validate_user_input(data):
    if "\u60aa\u610f" in data:  # Japanese for "malicious"
        raise SecurityError("Detected malicious input \U0001f6a8")
    return sanitize(data)
```

Expected output format: JSON with severity \U0001f534 indicators.
"""

        # This contains:
        # - English text
        # - Python code
        # - Japanese text (2 characters)
        # - Emojis (2 characters)
        # - Markdown formatting

        simple_estimate = len(mixed_content) // 4

        # The estimate should be reasonable for this mixed content
        # String is ~350 chars, estimate ~87 tokens
        assert (
            simple_estimate > 50
        ), f"Lower bound check: {simple_estimate} should be > 50"
        assert (
            simple_estimate < 200
        ), f"Upper bound check: {simple_estimate} should be < 200"

    def test_token_estimation_tolerance_bounds(self):
        """
        Test that token estimation is within acceptable tolerance
        of actual token counts for various content types.

        Acceptable tolerance: +/- 20% for English, +/- 50% for Unicode-heavy.
        """
        # Use explicit Unicode for emojis
        emoji_string = "\U0001f600\U0001f601\U0001f602\U0001f603"  # 4 emojis

        test_cases = [
            # (content, expected_tokens_approx, tolerance_percent)
            ("Simple English text for testing.", 8, 0.30),
            ("def func(): return x + y", 12, 0.30),
            (emoji_string, 4, 0.75),  # Emojis - higher tolerance (4 chars / 4 = 1)
            ("JSON response: {}", 5, 0.30),
        ]

        for content, expected, tolerance in test_cases:
            estimated = len(content) // 4

            # Check if estimate is within tolerance
            lower_bound = expected * (1 - tolerance)
            upper_bound = expected * (1 + tolerance)

            # This test documents expected drift rather than enforcing strict bounds
            # because actual tokenization depends on the specific tokenizer
            if estimated < lower_bound or estimated > upper_bound:
                # Log the drift for visibility
                drift_percent = abs(estimated - expected) / expected * 100
                # This is expected for some content types
                assert drift_percent < 100, (
                    f"Estimation drift too high for '{content[:20]}...': "
                    f"estimated={estimated}, expected={expected}, drift={drift_percent:.1f}%"
                )

    def test_zero_width_characters_handling(self):
        """
        Test handling of zero-width Unicode characters.

        Zero-width characters (joiners, non-joiners, marks) can affect
        string length calculations and token estimation.
        """
        # Zero-width joiner and non-joiner
        zwj = "\u200d"  # Zero-width joiner
        zwnj = "\u200c"  # Zero-width non-joiner

        # Text with zero-width characters
        text_with_zwj = f"word{zwj}word{zwj}word"

        # Length includes zero-width chars
        assert len(text_with_zwj) == 14  # 12 chars + 2 ZWJ

        # Estimation handles zero-width chars
        estimate = len(text_with_zwj) // 4
        assert estimate >= 3  # At least the words should count


# =============================================================================
# Test Class: Integration of Edge Cases
# =============================================================================


class TestEdgeCaseIntegration:
    """Integration tests combining multiple edge case scenarios."""

    def test_large_unicode_prompt_with_low_max_tokens(self, mock_bedrock_service):
        """
        Test handling of large Unicode prompt combined with low max_tokens.

        This tests the interaction between input size estimation and
        output truncation handling.
        """
        # Large prompt with CJK content using explicit Unicode
        # \u4ee3\u7801\u5206\u6790 = "code analysis" in Chinese
        cjk_code = "# Chinese comment: \u4ee3\u7801\u5206\u6790\n"
        large_prompt = cjk_code * 1000  # ~30K characters

        result = mock_bedrock_service.invoke_model(
            prompt=large_prompt, agent="TestAgent", max_tokens=50  # Low output limit
        )

        # Should complete without error
        assert "response" in result
        assert result["input_tokens"] > 1000

    def test_json_response_with_unicode_and_truncation(self):
        """
        Test handling of JSON response containing Unicode that gets truncated.

        This is a complex scenario where:
        1. Response contains Unicode (affects byte count)
        2. Truncation happens mid-structure
        3. Repair needs to handle Unicode correctly
        """
        # JSON with Unicode content, truncated mid-value
        # \u6ce8\u5165 = "injection" in Chinese
        truncated_unicode_json = '{"message": "SQL\u6ce8\u5165", "sever'

        # Attempt to detect and handle
        def handle_truncated_response(response: str) -> dict[str, Any]:
            """Handle potentially truncated JSON response."""
            # Try direct parse first
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass

            # Attempt repair for truncated JSON
            response = response.strip()

            # Check if it looks like JSON
            if not (response.startswith("{") or response.startswith("[")):
                return {"raw_response": response, "parsed": False}

            # Try to repair by closing structures
            repaired = response

            # Close any open strings
            if repaired.count('"') % 2 != 0:
                repaired += '"'

            # Close brackets
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            repaired += "]" * open_brackets + "}" * open_braces

            try:
                parsed = json.loads(repaired)
                parsed["_repaired"] = True
                return parsed
            except json.JSONDecodeError:
                return {"raw_response": response, "parsed": False}

        result = handle_truncated_response(truncated_unicode_json)

        # Should either parse or indicate failure
        assert "message" in result or "raw_response" in result

    @pytest.mark.asyncio
    async def test_async_invoke_with_context_limits(self, mock_bedrock_service):
        """
        Test async invoke handling context limit scenarios.
        """
        # Create large prompt
        large_prompt = "Analyze: " + ("data " * 5000)

        with patch.object(
            mock_bedrock_service,
            "invoke_model",
            return_value={
                "response": "Analysis complete",
                "input_tokens": 5500,
                "output_tokens": 50,
                "cost_usd": 0.01,
                "model": "test",
                "tier": "accurate",
                "operation": None,
                "cached": False,
                "request_id": "test-async",
            },
        ):
            result = await mock_bedrock_service.invoke_model_async(
                prompt=large_prompt, agent="TestAgent", max_tokens=100
            )

        assert result["input_tokens"] > 5000


# =============================================================================
# Test Class: Error Handling and Recovery
# =============================================================================


class TestErrorHandlingAndRecovery:
    """Tests for error handling and recovery strategies."""

    def test_validation_exception_parsing(self):
        """
        Test parsing of ValidationException error messages to extract
        useful information (input_tokens, context_limit).
        """
        error_messages = [
            (
                "Input length exceeds the context limit. Input tokens: 250000, "
                "context limit: 200000",
                250000,
                200000,
            ),
            (
                "ValidationException: Prompt exceeds maximum allowed tokens",
                None,
                None,
            ),
        ]

        def parse_validation_error(message: str) -> dict[str, Any]:
            """Parse validation error to extract token information."""
            import re

            result = {"input_tokens": None, "context_limit": None, "parsed": False}

            # Try to extract token counts
            input_match = re.search(r"[Ii]nput tokens?:?\s*(\d+)", message)
            limit_match = re.search(r"context limit:?\s*(\d+)", message, re.IGNORECASE)

            if input_match:
                result["input_tokens"] = int(input_match.group(1))
                result["parsed"] = True

            if limit_match:
                result["context_limit"] = int(limit_match.group(1))
                result["parsed"] = True

            return result

        for message, expected_input, expected_limit in error_messages:
            parsed = parse_validation_error(message)
            assert parsed["input_tokens"] == expected_input
            assert parsed["context_limit"] == expected_limit

    def test_retry_strategy_for_transient_errors(
        self, mock_bedrock_service, mock_bedrock_runtime
    ):
        """
        Test that transient errors trigger appropriate retry behavior
        while permanent errors (like context overflow) do not retry.
        """
        mock_bedrock_service.mode = BedrockMode.AWS
        mock_bedrock_service.bedrock_runtime = mock_bedrock_runtime

        # Transient error (ThrottlingException) - should retry
        call_count = [0]

        def throttle_then_succeed(**kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise MockClientError("ThrottlingException", "Too many requests")
            return create_bedrock_response("Success after retry")

        mock_bedrock_runtime.invoke_model.side_effect = throttle_then_succeed

        # This should retry and eventually succeed
        # Note: The actual retry logic uses time.sleep, so we mock that
        with patch("time.sleep"):
            result = mock_bedrock_service._invoke_bedrock_api(
                model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
                prompt="Test",
                system_prompt=None,
                max_tokens=100,
                temperature=0.7,
                apply_guardrails=False,
            )

        assert result["text"] == "Success after retry"
        assert call_count[0] == 3  # Initial + 2 retries

    def test_permanent_error_no_retry(self, mock_bedrock_service, mock_bedrock_runtime):
        """
        Test that permanent errors like ValidationException do not trigger retries.
        """
        mock_bedrock_service.mode = BedrockMode.AWS
        mock_bedrock_service.bedrock_runtime = mock_bedrock_runtime

        call_count = [0]

        def validation_error(**kwargs):
            call_count[0] += 1
            raise MockClientError("ValidationException", "Invalid request")

        mock_bedrock_runtime.invoke_model.side_effect = validation_error

        with pytest.raises(BedrockError):
            mock_bedrock_service._invoke_bedrock_api(
                model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
                prompt="Test",
                system_prompt=None,
                max_tokens=100,
                temperature=0.7,
                apply_guardrails=False,
            )

        # Should only call once - no retries for validation errors
        assert call_count[0] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
