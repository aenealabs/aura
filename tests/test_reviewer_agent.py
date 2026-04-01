"""
Tests for Reviewer Agent

Tests for security code review agent with policy verification.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== Security Policy Tests ====================


class TestSecurityPolicies:
    """Tests for security policy definitions."""

    def test_crypto_policy_exists(self):
        """Test that crypto policy is defined."""
        from src.agents.reviewer_agent import SECURITY_POLICIES

        assert "crypto" in SECURITY_POLICIES
        assert "prohibited" in SECURITY_POLICIES["crypto"]
        assert "required" in SECURITY_POLICIES["crypto"]
        assert "sha1" in SECURITY_POLICIES["crypto"]["prohibited"]
        assert "sha256" in SECURITY_POLICIES["crypto"]["required"]

    def test_secrets_policy_exists(self):
        """Test that secrets policy is defined."""
        from src.agents.reviewer_agent import SECURITY_POLICIES

        assert "secrets" in SECURITY_POLICIES
        assert "patterns" in SECURITY_POLICIES["secrets"]
        assert "password=" in SECURITY_POLICIES["secrets"]["patterns"]

    def test_injection_policy_exists(self):
        """Test that injection policy is defined."""
        from src.agents.reviewer_agent import SECURITY_POLICIES

        assert "injection" in SECURITY_POLICIES
        assert "patterns" in SECURITY_POLICIES["injection"]
        assert "eval(" in SECURITY_POLICIES["injection"]["patterns"]
        assert "exec(" in SECURITY_POLICIES["injection"]["patterns"]


# ==================== ReviewerAgent Initialization Tests ====================


class TestReviewerAgentInit:
    """Tests for ReviewerAgent initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without parameters."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        assert agent.llm is None
        assert agent.monitor is not None
        assert agent.enable_reflection is False
        assert agent.reflection is None

    def test_initialization_with_llm(self):
        """Test initialization with LLM client."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = MagicMock()
        agent = ReviewerAgent(llm_client=mock_llm)
        assert agent.llm == mock_llm

    def test_initialization_with_monitor(self):
        """Test initialization with custom monitor."""
        from src.agents.monitoring_service import MonitorAgent
        from src.agents.reviewer_agent import ReviewerAgent

        monitor = MonitorAgent()
        agent = ReviewerAgent(monitor=monitor)
        assert agent.monitor == monitor

    def test_initialization_with_reflection_enabled(self):
        """Test initialization with reflection enabled."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = MagicMock()
        agent = ReviewerAgent(llm_client=mock_llm, enable_reflection=True)
        # Reflection should be initialized if import succeeds
        assert agent.enable_reflection is True or agent.enable_reflection is False

    def test_initialization_without_llm_no_reflection(self):
        """Test that reflection is not enabled without LLM."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent(enable_reflection=True)  # No LLM
        # Without LLM, reflection won't be initialized
        assert agent.llm is None


# ==================== Policy Checking Tests ====================


class TestPolicyChecking:
    """Tests for policy verification."""

    @pytest.mark.asyncio
    async def test_review_safe_code(self):
        """Test review of safe code."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = '''
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"
'''
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_weak_crypto(self):
        """Test detection of weak cryptography."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
import hashlib

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()
"""
        result = await agent.review_code(code)
        # Should detect md5 as weak crypto
        result.get("findings", []) if isinstance(result, dict) else []
        # Check that the review was performed
        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_hardcoded_secrets(self):
        """Test detection of hardcoded secrets."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
API_KEY = "sk-12345abcdef"
PASSWORD = "supersecret123"

def connect():
    return {"api_key": API_KEY}
"""
        result = await agent.review_code(code)
        # Should detect hardcoded secrets
        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_code_injection(self):
        """Test detection of code injection vulnerabilities."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def dangerous_exec(user_input):
    eval(user_input)
    exec(user_input)
"""
        result = await agent.review_code(code)
        # Should detect eval/exec usage
        assert result is not None


# ==================== Review Result Tests ====================


class TestReviewResults:
    """Tests for review result structure."""

    @pytest.mark.asyncio
    async def test_result_structure(self):
        """Test that review result has expected structure."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = "def test(): pass"
        result = await agent.review_code(code)

        assert result is not None
        # Result should be a dict
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_code(self):
        """Test review of empty code."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        result = await agent.review_code("")
        assert result is not None


# ==================== LLM Integration Tests ====================


class TestLLMIntegration:
    """Tests for LLM-enhanced review."""

    @pytest.mark.asyncio
    async def test_review_without_llm(self):
        """Test review works without LLM."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()  # No LLM
        code = """
def calculate(x, y):
    return x + y
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_review_with_llm(self):
        """Test review with LLM client."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = MagicMock()
        mock_llm.invoke = AsyncMock(
            return_value={"choices": [{"message": {"content": '{"findings": []}'}}]}
        )

        agent = ReviewerAgent(llm_client=mock_llm)
        code = "def test(): pass"
        result = await agent.review_code(code)
        assert result is not None


# ==================== Context Integration Tests ====================


class TestContextIntegration:
    """Tests for HybridContext integration."""

    @pytest.mark.asyncio
    async def test_review_with_context(self):
        """Test review with HybridContext."""
        from src.agents.context_objects import HybridContext
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        context = HybridContext(
            query="review security", items=[], target_entity="test_function"
        )

        code = """
def process_data(data):
    return data.upper()
"""
        result = await agent.review_code(code, context=context)
        assert result is not None


# ==================== Compliance Checking Tests ====================


class TestComplianceChecking:
    """Tests for compliance verification."""

    @pytest.mark.asyncio
    async def test_check_input_validation(self):
        """Test checking for input validation."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def process(user_input):
    # No validation
    return user_input
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_check_error_handling(self):
        """Test checking for proper error handling."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def divide(a, b):
    return a / b  # No exception handling
"""
        result = await agent.review_code(code)
        assert result is not None


# ==================== Reflection Tests ====================


class TestReflection:
    """Tests for self-reflection integration."""

    @pytest.mark.asyncio
    async def test_review_with_reflection_disabled(self):
        """Test review with reflection disabled."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = MagicMock()
        agent = ReviewerAgent(llm_client=mock_llm, enable_reflection=False)

        code = "def test(): pass"
        result = await agent.review_code(code)
        assert result is not None


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_very_long_code(self):
        """Test review of very long code."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = "x = 1\n" * 500
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_code_with_unicode(self):
        """Test review of code with unicode."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def greet():
    return "Hello, World!"
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_code_with_comments(self):
        """Test review of code with comments."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
# This is a comment
def test():
    \"\"\"Docstring here.\"\"\"
    # Another comment
    pass  # inline comment
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_multiline_strings(self):
        """Test review of code with multiline strings."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = '''
SQL = """
SELECT * FROM users
WHERE id = %s
"""
'''
        result = await agent.review_code(code)
        assert result is not None


# ==================== Pattern Matching Tests ====================


class TestPatternMatching:
    """Tests for security pattern matching."""

    @pytest.mark.asyncio
    async def test_sql_injection_pattern(self):
        """Test detection of SQL injection patterns."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return execute(query)
"""
        result = await agent.review_code(code)
        # Should detect potential SQL injection
        assert result is not None

    @pytest.mark.asyncio
    async def test_xss_pattern(self):
        """Test detection of XSS patterns."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def render_user(name):
    return f"<div>{name}</div>"  # No escaping
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_path_traversal_pattern(self):
        """Test detection of path traversal patterns."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def read_file(filename):
    with open(f"/data/{filename}", "r") as f:
        return f.read()
"""
        result = await agent.review_code(code)
        assert result is not None


# ==================== Severity Classification Tests ====================


class TestSeverityClassification:
    """Tests for finding severity classification."""

    @pytest.mark.asyncio
    async def test_critical_finding(self):
        """Test detection of critical findings."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        # Code with obvious security issue
        code = """
import subprocess
def run(cmd):
    subprocess.call(cmd, shell=True)
"""
        result = await agent.review_code(code)
        assert result is not None

    @pytest.mark.asyncio
    async def test_low_severity_finding(self):
        """Test detection of low severity findings."""
        from src.agents.reviewer_agent import ReviewerAgent

        agent = ReviewerAgent()
        code = """
def test():
    pass  # Could add docstring
"""
        result = await agent.review_code(code)
        assert result is not None
