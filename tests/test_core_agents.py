"""Project Aura - Core Agent Tests

Comprehensive tests for CoderAgent, ReviewerAgent, and ValidatorAgent.
"""

# ruff: noqa: PLR2004

from unittest.mock import AsyncMock

import pytest

from src.agents.coder_agent import CoderAgent, create_coder_agent
from src.agents.context_objects import HybridContext
from src.agents.monitoring_service import MonitorAgent
from src.agents.reviewer_agent import ReviewerAgent, create_reviewer_agent
from src.agents.validator_agent import ValidatorAgent, create_validator_agent


class TestCoderAgent:
    """Test suite for CoderAgent."""

    def test_initialization(self):
        """Test CoderAgent initialization."""
        agent = CoderAgent()

        assert agent.llm is None
        assert agent.monitor is not None

    def test_initialization_with_llm(self):
        """Test CoderAgent initialization with LLM client."""
        mock_llm = AsyncMock()
        monitor = MonitorAgent()

        agent = CoderAgent(llm_client=mock_llm, monitor=monitor)

        assert agent.llm is mock_llm
        assert agent.monitor is monitor

    @pytest.mark.asyncio
    async def test_generate_code_fallback_no_remediation(self):
        """Test code generation without remediation context."""
        agent = CoderAgent()
        context = HybridContext(items=[], query="test", target_entity="Test")

        result = await agent.generate_code(context, "Generate code")

        assert "code" in result
        assert result["language"] == "python"
        assert result["has_remediation"] is False
        # Fallback should generate vulnerable code first
        assert "sha1" in result["code"].lower()

    @pytest.mark.asyncio
    async def test_generate_code_fallback_with_remediation(self):
        """Test code generation with remediation context."""
        agent = CoderAgent()
        context = HybridContext(items=[], query="test", target_entity="Test")
        context.add_remediation("Use SHA256 instead of SHA1", confidence=1.0)

        result = await agent.generate_code(context, "Fix security issue")

        assert "code" in result
        assert result["has_remediation"] is True
        # Remediation should use SHA256
        assert "sha256" in result["code"].lower()

    @pytest.mark.asyncio
    async def test_generate_code_with_mock_llm(self):
        """Test code generation with mock LLM."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        return hashlib.sha256(data.encode()).hexdigest()
"""
        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(items=[], query="test", target_entity="Test")

        result = await agent.generate_code(context, "Generate secure code")

        assert "sha256" in result["code"]
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_patch_fallback(self):
        """Test patch generation fallback."""
        agent = CoderAgent()
        original_code = "hashlib.sha1(data).hexdigest()"
        vulnerability = {"finding": "SHA1 is insecure", "severity": "High"}
        context = HybridContext(items=[], query="test", target_entity="Test")

        result = await agent.generate_patch(original_code, vulnerability, context)

        assert "patched_code" in result
        assert "changes_made" in result
        assert "confidence" in result
        assert "sha256" in result["patched_code"]

    def test_create_coder_agent_mock(self):
        """Test factory function with mock mode."""
        agent = create_coder_agent(use_mock=True)

        assert agent.llm is not None
        assert isinstance(agent, CoderAgent)


class TestReviewerAgent:
    """Test suite for ReviewerAgent."""

    def test_initialization(self):
        """Test ReviewerAgent initialization."""
        agent = ReviewerAgent()

        assert agent.llm is None
        assert agent.monitor is not None

    @pytest.mark.asyncio
    async def test_review_code_fallback_secure(self):
        """Test review of secure code."""
        agent = ReviewerAgent()
        secure_code = """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        return hashlib.sha256(data.encode()).hexdigest()
"""
        result = await agent.review_code(secure_code)

        assert result["status"] == "PASS"
        assert len(result["vulnerabilities"]) == 0

    @pytest.mark.asyncio
    async def test_review_code_fallback_weak_crypto(self):
        """Test detection of weak cryptographic algorithm."""
        agent = ReviewerAgent()
        vulnerable_code = """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        return hashlib.sha1(data.encode()).hexdigest()
"""
        result = await agent.review_code(vulnerable_code)

        assert result["status"] == "FAIL_SECURITY"
        assert result["severity"] == "High"
        assert len(result["vulnerabilities"]) > 0
        assert any(v["type"] == "WEAK_CRYPTOGRAPHY" for v in result["vulnerabilities"])

    @pytest.mark.asyncio
    async def test_review_code_fallback_md5(self):
        """Test detection of MD5."""
        agent = ReviewerAgent()
        vulnerable_code = "hashlib.md5(data).hexdigest()"

        result = await agent.review_code(vulnerable_code)

        assert result["status"] == "FAIL_SECURITY"

    @pytest.mark.asyncio
    async def test_review_code_with_mock_llm(self):
        """Test review with mock LLM."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """{
            "status": "PASS",
            "finding": "Code is secure",
            "vulnerabilities": [],
            "recommendations": []
        }"""
        agent = ReviewerAgent(llm_client=mock_llm)

        result = await agent.review_code("print('hello')")

        assert result["status"] == "PASS"
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_patch_valid(self):
        """Test patch verification for valid patch."""
        agent = ReviewerAgent()
        original = "hashlib.sha1(data)"
        patched = "hashlib.sha256(data)"
        vulnerability = {"finding": "SHA1 detected", "severity": "High"}

        result = await agent.review_patch(original, patched, vulnerability)

        assert result["patch_valid"] is True
        assert result["regression_check"] is True

    @pytest.mark.asyncio
    async def test_review_patch_invalid(self):
        """Test patch verification for invalid patch."""
        agent = ReviewerAgent()
        original = "hashlib.sha1(data)"
        patched = "hashlib.sha1(data)"  # Still using SHA1
        vulnerability = {"finding": "SHA1 detected", "severity": "High"}

        result = await agent.review_patch(original, patched, vulnerability)

        assert result["patch_valid"] is False

    def test_create_reviewer_agent_mock(self):
        """Test factory function with mock mode."""
        agent = create_reviewer_agent(use_mock=True)

        assert agent.llm is not None
        assert isinstance(agent, ReviewerAgent)


class TestValidatorAgent:
    """Test suite for ValidatorAgent."""

    def test_initialization(self):
        """Test ValidatorAgent initialization."""
        agent = ValidatorAgent()

        assert agent.llm is None
        assert agent.monitor is not None

    @pytest.mark.asyncio
    async def test_validate_code_valid_syntax(self):
        """Test validation of code with valid syntax."""
        agent = ValidatorAgent()
        valid_code = """import hashlib

def calculate_checksum(data):
    return hashlib.sha256(data.encode()).hexdigest()
"""
        result = await agent.validate_code(valid_code)

        assert result["valid"] is True
        assert result["syntax_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_code_invalid_syntax(self):
        """Test validation of code with invalid syntax."""
        agent = ValidatorAgent()
        invalid_code = "def foo(:\n    pass"

        result = await agent.validate_code(invalid_code)

        assert result["valid"] is False
        assert result["syntax_valid"] is False
        assert len(result["issues"]) > 0
        assert result["issues"][0]["type"] == "SYNTAX_ERROR"

    @pytest.mark.asyncio
    async def test_validate_code_missing_elements(self):
        """Test validation with missing expected elements."""
        agent = ValidatorAgent()
        code = "print('hello')"

        result = await agent.validate_code(
            code, expected_elements=["import hashlib", "calculate_checksum"]
        )

        assert result["structure_valid"] is False

    @pytest.mark.asyncio
    async def test_validate_code_security_issues(self):
        """Test detection of security issues."""
        agent = ValidatorAgent()
        dangerous_code = """
import os
os.system('rm -rf /')
"""
        result = await agent.validate_code(dangerous_code)

        assert result["security_valid"] is False
        assert any(i["type"] == "OS_SYSTEM" for i in result["issues"])

    @pytest.mark.asyncio
    async def test_validate_code_eval_detection(self):
        """Test detection of eval() usage."""
        agent = ValidatorAgent()
        dangerous_code = "result = eval(user_input)"

        result = await agent.validate_code(dangerous_code)

        assert result["security_valid"] is False
        assert any(i["type"] == "EVAL_USAGE" for i in result["issues"])

    def test_validate_syntax_only(self):
        """Test quick syntax-only validation."""
        agent = ValidatorAgent()

        assert agent.validate_syntax_only("print('hello')") is True
        assert agent.validate_syntax_only("def foo(:") is False

    @pytest.mark.asyncio
    async def test_validate_against_requirements(self):
        """Test requirement-based validation."""
        agent = ValidatorAgent()
        code = """import hashlib
def calculate_checksum(data):
    return hashlib.sha256(data.encode()).hexdigest()
"""
        requirements = [
            "Use SHA256 for hashing",
            "Must import hashlib",
        ]

        result = await agent.validate_against_requirements(code, requirements)

        assert result["all_met"] is True

    @pytest.mark.asyncio
    async def test_validate_against_requirements_not_met(self):
        """Test requirement-based validation when requirements not met."""
        agent = ValidatorAgent()
        code = "print('hello')"
        requirements = ["Use SHA256 for hashing"]

        result = await agent.validate_against_requirements(code, requirements)

        assert result["all_met"] is False

    def test_create_validator_agent_mock(self):
        """Test factory function with mock mode."""
        agent = create_validator_agent(use_mock=True)

        assert agent.llm is not None
        assert isinstance(agent, ValidatorAgent)


class TestAgentIntegration:
    """Integration tests for agent cooperation."""

    @pytest.mark.asyncio
    async def test_coder_reviewer_workflow(self):
        """Test CoderAgent → ReviewerAgent workflow."""
        coder = CoderAgent()
        reviewer = ReviewerAgent()

        # Create context with remediation to get secure code
        context = HybridContext(items=[], query="secure hash", target_entity="Test")
        context.add_remediation("Use SHA256", confidence=1.0)

        # Generate code
        coder_result = await coder.generate_code(context, "Generate secure hash")

        # Review generated code
        review_result = await reviewer.review_code(coder_result["code"])

        # Code with remediation should pass review
        assert review_result["status"] == "PASS"

    @pytest.mark.asyncio
    async def test_full_agent_pipeline(self):
        """Test full pipeline: Coder → Reviewer → Validator."""
        coder = CoderAgent()
        reviewer = ReviewerAgent()
        validator = ValidatorAgent()

        # Generate secure code
        context = HybridContext(items=[], query="secure", target_entity="Test")
        context.add_remediation("Use SHA256", confidence=1.0)

        coder_result = await coder.generate_code(context, "Generate secure code")

        # Review code
        review_result = await reviewer.review_code(coder_result["code"])
        assert review_result["status"] == "PASS"

        # Validate code
        validation_result = await validator.validate_code(
            coder_result["code"],
            expected_elements=["import hashlib"],
        )
        assert validation_result["valid"] is True
        assert validation_result["syntax_valid"] is True

    @pytest.mark.asyncio
    async def test_vulnerability_remediation_cycle(self):
        """Test vulnerability detection and remediation cycle."""
        coder = CoderAgent()
        reviewer = ReviewerAgent()

        # First iteration: no remediation context → vulnerable code
        context1 = HybridContext(items=[], query="hash", target_entity="Test")
        result1 = await coder.generate_code(context1, "Generate hash")
        review1 = await reviewer.review_code(result1["code"])

        # Should detect vulnerability
        assert review1["status"] == "FAIL_SECURITY"

        # Second iteration: with remediation context → secure code
        context2 = HybridContext(items=[], query="hash", target_entity="Test")
        context2.add_remediation("Use SHA256 instead of SHA1", confidence=1.0)
        result2 = await coder.generate_code(context2, "Generate secure hash")
        review2 = await reviewer.review_code(result2["code"])

        # Should pass review
        assert review2["status"] == "PASS"
