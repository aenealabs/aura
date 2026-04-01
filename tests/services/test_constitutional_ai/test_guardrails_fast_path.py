"""Unit tests for Bedrock Guardrails fast-path service.

Tests the GuardrailsFastPath class for fast-fail detection of CRITICAL
constitutional principle violations.
"""

from unittest.mock import MagicMock

import pytest

from src.services.constitutional_ai.guardrails_fast_path import (
    CRITICAL_PRINCIPLE_GUARDRAIL_MAP,
    CRITICAL_PRINCIPLE_IDS,
    FastPathMode,
    FastPathResult,
    FastPathViolation,
    GuardrailAction,
    GuardrailsFastPath,
)

# =============================================================================
# Test FastPathMode Enum
# =============================================================================


class TestFastPathMode:
    """Tests for FastPathMode enum."""

    def test_enum_values(self):
        """Should have expected modes."""
        assert FastPathMode.ENABLED.value == "enabled"
        assert FastPathMode.DISABLED.value == "disabled"
        assert FastPathMode.MOCK.value == "mock"


# =============================================================================
# Test GuardrailAction Enum
# =============================================================================


class TestGuardrailAction:
    """Tests for GuardrailAction enum."""

    def test_enum_values(self):
        """Should have expected actions."""
        assert GuardrailAction.NONE.value == "none"
        assert GuardrailAction.BLOCKED.value == "blocked"
        assert GuardrailAction.MODIFIED.value == "modified"


# =============================================================================
# Test FastPathViolation
# =============================================================================


class TestFastPathViolation:
    """Tests for FastPathViolation dataclass."""

    def test_creation(self):
        """Should create violation with all fields."""
        violation = FastPathViolation(
            principle_id="principle_1_security_first",
            guardrail_type="CONTENT_POLICY",
            confidence=0.95,
            matched_content="exec(user_input)",
            action=GuardrailAction.BLOCKED,
        )

        assert violation.principle_id == "principle_1_security_first"
        assert violation.guardrail_type == "CONTENT_POLICY"
        assert violation.confidence == 0.95
        assert violation.matched_content == "exec(user_input)"
        assert violation.action == GuardrailAction.BLOCKED


# =============================================================================
# Test FastPathResult
# =============================================================================


class TestFastPathResult:
    """Tests for FastPathResult dataclass."""

    def test_creation_minimal(self):
        """Should create result with minimal fields."""
        result = FastPathResult(blocked=False)

        assert result.blocked is False
        assert result.violations == []
        assert result.latency_ms == 0.0
        assert result.principle_ids_blocked == []

    def test_to_dict(self):
        """Should convert to dictionary representation."""
        violation = FastPathViolation(
            principle_id="principle_1_security_first",
            guardrail_type="CONTENT_POLICY",
            confidence=0.95,
            matched_content="x" * 150,  # Long content
            action=GuardrailAction.BLOCKED,
        )
        result = FastPathResult(
            blocked=True,
            violations=[violation],
            latency_ms=50.5,
            principle_ids_blocked=["principle_1_security_first"],
            guardrail_id="test-guardrail",
        )

        d = result.to_dict()

        assert d["blocked"] is True
        assert d["latency_ms"] == 50.5
        assert d["principle_ids_blocked"] == ["principle_1_security_first"]
        assert d["guardrail_id"] == "test-guardrail"
        assert len(d["violations"]) == 1
        # Matched content should be truncated to 100 chars
        assert len(d["violations"][0]["matched_content"]) == 100


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_critical_principle_ids(self):
        """Should have three CRITICAL principles."""
        assert len(CRITICAL_PRINCIPLE_IDS) == 3
        assert "principle_1_security_first" in CRITICAL_PRINCIPLE_IDS
        assert "principle_2_data_protection" in CRITICAL_PRINCIPLE_IDS
        assert "principle_3_sandbox_isolation" in CRITICAL_PRINCIPLE_IDS

    def test_guardrail_map_coverage(self):
        """Each CRITICAL principle should map to guardrail types."""
        for principle_id in CRITICAL_PRINCIPLE_IDS:
            assert principle_id in CRITICAL_PRINCIPLE_GUARDRAIL_MAP
            guardrail_types = CRITICAL_PRINCIPLE_GUARDRAIL_MAP[principle_id]
            assert len(guardrail_types) > 0


# =============================================================================
# Test GuardrailsFastPath Initialization
# =============================================================================


class TestGuardrailsFastPathInit:
    """Tests for GuardrailsFastPath initialization."""

    def test_default_mode_is_mock(self):
        """Default mode should be MOCK for safety."""
        fast_path = GuardrailsFastPath()

        assert fast_path.mode == FastPathMode.MOCK

    def test_enabled_mode_requires_guardrail_id(self):
        """ENABLED mode without guardrail_id should fallback to MOCK."""
        fast_path = GuardrailsFastPath(mode=FastPathMode.ENABLED)

        assert fast_path.mode == FastPathMode.MOCK

    def test_enabled_mode_with_guardrail_id(self):
        """ENABLED mode with guardrail_id should stay ENABLED."""
        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail-id",
        )

        assert fast_path.mode == FastPathMode.ENABLED
        assert fast_path.guardrail_id == "test-guardrail-id"

    def test_custom_version(self):
        """Should accept custom guardrail version."""
        fast_path = GuardrailsFastPath(
            mode=FastPathMode.MOCK,
            guardrail_version="v1.0",
        )

        assert fast_path.guardrail_version == "v1.0"


# =============================================================================
# Test GuardrailsFastPath - DISABLED Mode
# =============================================================================


class TestGuardrailsFastPathDisabled:
    """Tests for DISABLED mode behavior."""

    @pytest.mark.asyncio
    async def test_disabled_returns_not_blocked(self):
        """DISABLED mode should always return not blocked."""
        fast_path = GuardrailsFastPath(mode=FastPathMode.DISABLED)

        result = await fast_path.check_critical_principles(
            output="exec(malicious_code)"
        )

        assert result.blocked is False
        assert result.violations == []
        assert result.latency_ms == 0.0


# =============================================================================
# Test GuardrailsFastPath - MOCK Mode
# =============================================================================


class TestGuardrailsFastPathMock:
    """Tests for MOCK mode behavior."""

    @pytest.fixture
    def mock_fast_path(self):
        """Create fast-path in MOCK mode."""
        return GuardrailsFastPath(mode=FastPathMode.MOCK)

    @pytest.mark.asyncio
    async def test_safe_output_not_blocked(self, mock_fast_path):
        """Safe output should not be blocked."""
        result = await mock_fast_path.check_critical_principles(
            output="def add(a, b): return a + b"
        )

        assert result.blocked is False
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_sql_injection_blocked(self, mock_fast_path):
        """SQL injection patterns should trigger security principle."""
        # Uses the literal "sql injection" pattern that mock check looks for
        result = await mock_fast_path.check_critical_principles(
            output="This code is vulnerable to SQL injection attacks"
        )

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_exec_pattern_blocked(self, mock_fast_path):
        """exec() calls should trigger security principle."""
        result = await mock_fast_path.check_critical_principles(
            output="exec(user_input)"
        )

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_eval_pattern_blocked(self, mock_fast_path):
        """eval() calls should trigger security principle."""
        result = await mock_fast_path.check_critical_principles(
            output="result = eval(user_code)"
        )

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_os_system_blocked(self, mock_fast_path):
        """os.system() calls should trigger security principle."""
        result = await mock_fast_path.check_critical_principles(
            output="os.system(command)"
        )

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_template_injection_blocked(self, mock_fast_path):
        """Template injection (${...}) should trigger security principle."""
        result = await mock_fast_path.check_critical_principles(
            output='query = f"SELECT * FROM users WHERE id = ${user_id}"'
        )

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_hardcoded_password_blocked(self, mock_fast_path):
        """Hardcoded passwords should trigger data protection principle."""
        result = await mock_fast_path.check_critical_principles(
            output="config = {'password=' + '12345'}"
        )

        assert result.blocked is True
        assert "principle_2_data_protection" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_api_key_blocked(self, mock_fast_path):
        """API keys in output should trigger data protection principle."""
        result = await mock_fast_path.check_critical_principles(
            output="headers = {'Authorization': 'api_key=' + key}"
        )

        assert result.blocked is True
        assert "principle_2_data_protection" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_aws_key_blocked(self, mock_fast_path):
        """AWS access keys should trigger data protection principle."""
        result = await mock_fast_path.check_critical_principles(
            output="AWS_ACCESS_KEY = 'AKIA...'"
        )

        assert result.blocked is True
        assert "principle_2_data_protection" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_docker_escape_blocked(self, mock_fast_path):
        """Docker escape patterns should trigger sandbox isolation principle."""
        result = await mock_fast_path.check_critical_principles(
            output="# How to perform docker escape from container"
        )

        assert result.blocked is True
        assert "principle_3_sandbox_isolation" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_container_breakout_blocked(self, mock_fast_path):
        """Container breakout patterns should trigger sandbox isolation."""
        result = await mock_fast_path.check_critical_principles(
            output="Attempting container breakout via CVE-2024..."
        )

        assert result.blocked is True
        assert "principle_3_sandbox_isolation" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_nsenter_blocked(self, mock_fast_path):
        """nsenter command should trigger sandbox isolation."""
        result = await mock_fast_path.check_critical_principles(
            output="nsenter -t 1 -m -u -i -n"
        )

        assert result.blocked is True
        assert "principle_3_sandbox_isolation" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_tracks_latency(self, mock_fast_path):
        """Should track check latency."""
        result = await mock_fast_path.check_critical_principles(output="safe output")

        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_guardrail_id_is_mock(self, mock_fast_path):
        """Mock mode should use 'mock-guardrail' ID."""
        result = await mock_fast_path.check_critical_principles(output="exec(bad)")

        assert result.guardrail_id == "mock-guardrail"

    @pytest.mark.asyncio
    async def test_violation_details(self, mock_fast_path):
        """Violations should contain detailed information."""
        result = await mock_fast_path.check_critical_principles(
            output="exec(user_input)"
        )

        assert len(result.violations) > 0
        violation = result.violations[0]
        assert violation.principle_id == "principle_1_security_first"
        assert violation.guardrail_type == "CONTENT_POLICY"
        assert violation.confidence > 0
        assert violation.action == GuardrailAction.BLOCKED


# =============================================================================
# Test GuardrailsFastPath - ENABLED Mode
# =============================================================================


class TestGuardrailsFastPathEnabled:
    """Tests for ENABLED mode (mocked Bedrock calls)."""

    @pytest.mark.asyncio
    async def test_no_client_returns_not_blocked(self):
        """Missing Bedrock client should fail-open (not block)."""
        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=None,
        )

        result = await fast_path.check_critical_principles(
            output="potentially bad output"
        )

        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_bedrock_not_intervened(self):
        """Bedrock response with no intervention should not block."""
        mock_client = MagicMock()
        mock_client.apply_guardrail.return_value = {
            "action": "NONE",
            "assessments": [],
        }

        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=mock_client,
        )

        result = await fast_path.check_critical_principles(output="safe output")

        assert result.blocked is False
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_bedrock_content_policy_blocked(self):
        """Bedrock content policy violation should block."""
        mock_client = MagicMock()
        mock_client.apply_guardrail.return_value = {
            "action": "GUARDRAIL_INTERVENED",
            "assessments": [
                {
                    "contentPolicy": {
                        "filters": [{"action": "BLOCKED", "confidence": 0.95}]
                    }
                }
            ],
        }

        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=mock_client,
        )

        result = await fast_path.check_critical_principles(output="malicious content")

        assert result.blocked is True
        assert "principle_1_security_first" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_bedrock_pii_blocked(self):
        """Bedrock PII detection should block."""
        mock_client = MagicMock()
        mock_client.apply_guardrail.return_value = {
            "action": "GUARDRAIL_INTERVENED",
            "assessments": [
                {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [{"action": "BLOCKED", "type": "SSN"}]
                    }
                }
            ],
        }

        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=mock_client,
        )

        result = await fast_path.check_critical_principles(output="SSN: 123-45-6789")

        assert result.blocked is True
        assert "principle_2_data_protection" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_bedrock_topic_blocked(self):
        """Bedrock topic policy violation should block."""
        mock_client = MagicMock()
        mock_client.apply_guardrail.return_value = {
            "action": "GUARDRAIL_INTERVENED",
            "assessments": [
                {
                    "topicPolicy": {
                        "topics": [{"action": "BLOCKED", "name": "sandbox_escape"}]
                    }
                }
            ],
        }

        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=mock_client,
        )

        result = await fast_path.check_critical_principles(output="escape sandbox")

        assert result.blocked is True
        assert "principle_3_sandbox_isolation" in result.principle_ids_blocked

    @pytest.mark.asyncio
    async def test_bedrock_exception_fails_open(self):
        """Bedrock exceptions should fail-open (not block)."""
        mock_client = MagicMock()
        mock_client.apply_guardrail.side_effect = Exception("Bedrock error")

        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test-guardrail",
            bedrock_client=mock_client,
        )

        result = await fast_path.check_critical_principles(output="any output")

        assert result.blocked is False


# =============================================================================
# Test Helper Methods
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_critical_principles(self):
        """Should return copy of critical principle IDs."""
        fast_path = GuardrailsFastPath()
        principles = fast_path.get_critical_principles()

        assert principles == CRITICAL_PRINCIPLE_IDS
        # Should be a copy, not the original
        principles.append("new_principle")
        assert "new_principle" not in fast_path.get_critical_principles()

    def test_is_enabled_mock_mode(self):
        """MOCK mode should be considered enabled."""
        fast_path = GuardrailsFastPath(mode=FastPathMode.MOCK)
        assert fast_path.is_enabled() is True

    def test_is_enabled_enabled_mode(self):
        """ENABLED mode should be considered enabled."""
        fast_path = GuardrailsFastPath(
            mode=FastPathMode.ENABLED,
            guardrail_id="test",
        )
        assert fast_path.is_enabled() is True

    def test_is_enabled_disabled_mode(self):
        """DISABLED mode should not be considered enabled."""
        fast_path = GuardrailsFastPath(mode=FastPathMode.DISABLED)
        assert fast_path.is_enabled() is False
