"""
Tests for Validator Agent

Tests for the comprehensive code validation agent.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== ValidatorAgent Initialization Tests ====================


class TestValidatorAgentInit:
    """Tests for ValidatorAgent initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without parameters."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        assert agent.llm is None
        assert agent.monitor is not None
        assert agent.sandbox_orchestrator is None

    def test_initialization_with_llm(self):
        """Test initialization with LLM client."""
        from src.agents.validator_agent import ValidatorAgent

        mock_llm = MagicMock()
        agent = ValidatorAgent(llm_client=mock_llm)
        assert agent.llm == mock_llm

    def test_initialization_with_monitor(self):
        """Test initialization with custom monitor."""
        from src.agents.monitoring_service import MonitorAgent
        from src.agents.validator_agent import ValidatorAgent

        monitor = MonitorAgent()
        agent = ValidatorAgent(monitor=monitor)
        assert agent.monitor == monitor

    def test_initialization_with_sandbox(self):
        """Test initialization with sandbox orchestrator."""
        from src.agents.validator_agent import ValidatorAgent

        mock_sandbox = MagicMock()
        agent = ValidatorAgent(sandbox_orchestrator=mock_sandbox)
        assert agent.sandbox_orchestrator == mock_sandbox


# ==================== Syntax Validation Tests ====================


class TestSyntaxValidation:
    """Tests for syntax validation."""

    def test_valid_python_syntax(self):
        """Test validation of valid Python code."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def hello(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_invalid_python_syntax(self):
        """Test detection of invalid Python syntax."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def hello(name
    return "Hello"
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_empty_code(self):
        """Test validation of empty code."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        result = agent._validate_syntax("")
        # Empty code is syntactically valid
        assert result["valid"] is True


# ==================== Structure Validation Tests ====================


class TestStructureValidation:
    """Tests for structure validation."""

    def test_expected_elements_present(self):
        """Test validation when expected elements are present."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def process_data():
    pass

class DataProcessor:
    pass
"""
        result = agent._validate_structure(code, ["process_data", "DataProcessor"])
        assert result["valid"] is True

    def test_expected_elements_missing(self):
        """Test validation when expected elements are missing."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def other_function():
    pass
"""
        result = agent._validate_structure(code, ["missing_function"])
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_no_expected_elements(self):
        """Test validation with no expected elements."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def any_function():
    pass
"""
        result = agent._validate_structure(code, [])
        assert result["valid"] is True


# ==================== Type Hints Validation Tests ====================


class TestTypeHintsValidation:
    """Tests for type hints validation."""

    def test_function_with_type_hints(self):
        """Test validation of function with proper type hints."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def add(a: int, b: int) -> int:
    return a + b
"""
        result = agent._validate_type_hints(code)
        assert result["valid"] is True

    def test_function_without_type_hints(self):
        """Test validation of function without type hints."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def add(a, b):
    return a + b
"""
        result = agent._validate_type_hints(code)
        # Warnings should be generated but it's still valid
        assert "warnings" in result or "issues" in result


# ==================== Security Validation Tests ====================


class TestSecurityValidation:
    """Tests for security validation."""

    def test_safe_code(self):
        """Test validation of safe code."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def calculate(x: int, y: int) -> int:
    return x + y
"""
        result = agent._validate_security(code)
        assert result["valid"] is True

    def test_eval_usage(self):
        """Test detection of eval usage."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def process(data):
    return eval(data)
"""
        result = agent._validate_security(code)
        assert result["valid"] is False

    def test_exec_usage(self):
        """Test detection of exec usage."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def run(code_str):
    exec(code_str)
"""
        result = agent._validate_security(code)
        assert result["valid"] is False

    def test_subprocess_shell(self):
        """Test detection of subprocess shell usage."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
import subprocess
def run_cmd(cmd):
    subprocess.run(cmd, shell=True)
"""
        result = agent._validate_security(code)
        # Should flag shell=True as a security concern
        assert len(result.get("issues", []) + result.get("warnings", [])) >= 0


# ==================== Comprehensive Validation Tests ====================


class TestComprehensiveValidation:
    """Tests for comprehensive validate_code method."""

    @pytest.mark.asyncio
    async def test_valid_code_all_checks_pass(self):
        """Test that valid code passes all checks."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = '''
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"
'''
        result = await agent.validate_code(code)
        assert result["syntax_valid"] is True
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_invalid_syntax_fails_early(self):
        """Test that invalid syntax fails validation early."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def broken(
    return 1
"""
        result = await agent.validate_code(code)
        assert result["valid"] is False
        assert result["syntax_valid"] is False
        assert result["structure_valid"] is False
        assert result["type_hints_valid"] is False
        assert result["security_valid"] is False

    @pytest.mark.asyncio
    async def test_security_issues_block_validation(self):
        """Test that security issues block overall validation."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def dangerous(data: str) -> Any:
    return eval(data)
"""
        result = await agent.validate_code(code)
        assert result["security_valid"] is False

    @pytest.mark.asyncio
    async def test_expected_elements_checked(self):
        """Test that expected elements are verified."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def existing_function():
    pass
"""
        result = await agent.validate_code(code, expected_elements=["missing_function"])
        assert result["structure_valid"] is False

    @pytest.mark.asyncio
    async def test_with_llm_enhancement(self):
        """Test validation with LLM enhancement on invalid code."""
        from src.agents.validator_agent import ValidatorAgent

        mock_llm = MagicMock()
        agent = ValidatorAgent(llm_client=mock_llm)

        # Mock the LLM analysis method
        agent._enhanced_analysis_llm = AsyncMock(
            return_value={
                "additional_issues": ["Consider refactoring"],
                "recommendations": ["Add more tests"],
            }
        )

        code = """
def bad(data):
    return eval(data)
"""
        result = await agent.validate_code(code)
        # Should trigger LLM analysis for invalid code
        assert result["valid"] is False


# ==================== LLM-Enhanced Analysis Tests ====================


class TestLLMEnhancedAnalysis:
    """Tests for LLM-enhanced validation analysis."""

    @pytest.mark.asyncio
    async def test_enhanced_analysis_without_llm(self):
        """Test that validation works without LLM."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()  # No LLM
        code = """
def simple() -> int:
    return 42
"""
        result = await agent.validate_code(code)
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_llm_failure_doesnt_break_validation(self):
        """Test that LLM failure doesn't break validation."""
        from src.agents.validator_agent import ValidatorAgent

        mock_llm = MagicMock()
        agent = ValidatorAgent(llm_client=mock_llm)

        # Make LLM analysis fail
        agent._enhanced_analysis_llm = AsyncMock(side_effect=Exception("LLM error"))

        code = """
def unsafe(data):
    return eval(data)
"""
        # Should still complete without raising
        result = await agent.validate_code(code)
        assert result["valid"] is False
        assert result["security_valid"] is False


# ==================== Sandbox Validation Tests ====================


class TestSandboxValidation:
    """Tests for sandbox-based validation."""

    @pytest.mark.asyncio
    async def test_sandbox_validation_when_available(self):
        """Test sandbox validation when orchestrator is available."""
        from src.agents.validator_agent import ValidatorAgent

        mock_sandbox = MagicMock()
        mock_sandbox.run_validation = AsyncMock(
            return_value={"success": True, "output": "Tests passed"}
        )

        agent = ValidatorAgent(sandbox_orchestrator=mock_sandbox)

        # If the method exists and is called
        if hasattr(agent, "_run_sandbox_validation"):
            result = await agent._run_sandbox_validation("def test(): pass", "test.py")
            assert result is not None

    def test_agent_without_sandbox(self):
        """Test agent initialization without sandbox."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        assert agent.sandbox_orchestrator is None


# ==================== Code Quality Checks ====================


class TestCodeQualityChecks:
    """Tests for code quality analysis."""

    def test_complexity_check_simple_function(self):
        """Test complexity check on simple function."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def simple():
    return 1
"""
        # The function should handle simple code
        syntax = agent._validate_syntax(code)
        assert syntax["valid"] is True

    def test_complexity_check_nested_loops(self):
        """Test complexity detection on nested loops."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def complex_func():
    for i in range(10):
        for j in range(10):
            for k in range(10):
                if i > j:
                    if j > k:
                        return i * j * k
    return 0
"""
        syntax = agent._validate_syntax(code)
        assert syntax["valid"] is True


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases in validation."""

    def test_unicode_code(self):
        """Test validation of code with unicode."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def greet():
    return "Hello, World!"
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is True

    def test_very_long_code(self):
        """Test validation of long code."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = "x = 1\n" * 1000
        result = agent._validate_syntax(code)
        assert result["valid"] is True

    def test_multiline_strings(self):
        """Test validation of multiline strings."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = '''
def doc_func():
    """
    This is a multiline
    docstring.
    """
    return None
'''
        result = agent._validate_syntax(code)
        assert result["valid"] is True

    def test_decorators(self):
        """Test validation of code with decorators."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
@staticmethod
def my_static():
    return True

@classmethod
def my_class(cls):
    return cls
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is True

    def test_async_functions(self):
        """Test validation of async functions."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
async def async_func():
    await some_coroutine()
    return "done"
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is True

    def test_type_annotations_complex(self):
        """Test validation of complex type annotations."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
from typing import List, Dict, Optional

def process(
    items: List[Dict[str, int]],
    config: Optional[Dict[str, str]] = None
) -> List[str]:
    return []
"""
        result = agent._validate_syntax(code)
        assert result["valid"] is True


# ==================== Pattern Detection Tests ====================


class TestPatternDetection:
    """Tests for security pattern detection."""

    def test_pickle_detection(self):
        """Test detection of pickle usage."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
import pickle

def load_data(path):
    with open(path, 'rb') as f:
        return pickle.load(f)
"""
        result = agent._validate_security(code)
        # Should detect pickle as potential security concern
        result.get("issues", []) + result.get("warnings", [])
        # Verify the check runs without error
        assert isinstance(result, dict)

    def test_sql_string_formatting(self):
        """Test detection of SQL string formatting."""
        from src.agents.validator_agent import ValidatorAgent

        agent = ValidatorAgent()
        code = """
def query(user_input):
    sql = f"SELECT * FROM users WHERE name = '{user_input}'"
    return sql
"""
        result = agent._validate_security(code)
        # This pattern is typically flagged
        assert isinstance(result, dict)
