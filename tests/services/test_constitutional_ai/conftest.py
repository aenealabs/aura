"""Test fixtures for Constitutional AI tests.

This module provides reusable fixtures for testing the Constitutional AI
services, including mock LLM services and deterministic response factories.
"""

import json
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    CritiqueFailurePolicy,
    RevisionFailurePolicy,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalPrinciple,
    CritiqueResult,
    PrincipleCategory,
    PrincipleSeverity,
    RevisionResult,
)

# =============================================================================
# Mock LLM Service Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Create a mock BedrockLLMService.

    Returns:
        MagicMock configured to behave like BedrockLLMService
    """
    service = MagicMock()
    service.invoke_model_async = AsyncMock()
    return service


@pytest.fixture
def mock_llm_response_factory() -> Callable[..., Dict[str, Any]]:
    """Factory for creating mock LLM responses.

    Returns:
        Factory function that creates mock response dictionaries
    """

    def _create(
        response_text: str,
        usage: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        return {
            "response": response_text,
            "usage": usage or {"input_tokens": 100, "output_tokens": 50},
        }

    return _create


# =============================================================================
# Critique Response Fixtures
# =============================================================================


@pytest.fixture
def critique_response_factory() -> Callable[..., str]:
    """Factory for creating deterministic critique response JSON.

    Returns:
        Factory function that creates JSON critique responses
    """

    def _create(
        principle_id: str,
        issues: Optional[List[str]] = None,
        requires_revision: bool = False,
        reasoning: str = "Test reasoning",
        confidence: float = 0.85,
    ) -> str:
        return json.dumps(
            [
                {
                    "principle_id": principle_id,
                    "issues_found": issues or [],
                    "reasoning": reasoning,
                    "requires_revision": requires_revision,
                    "confidence": confidence,
                }
            ]
        )

    return _create


@pytest.fixture
def batch_critique_response_factory() -> Callable[..., str]:
    """Factory for creating batch critique response JSON.

    Returns:
        Factory function that creates JSON with multiple critique evaluations
    """

    def _create(evaluations: List[Dict[str, Any]]) -> str:
        return json.dumps(evaluations)

    return _create


@pytest.fixture
def revision_response_factory() -> Callable[..., str]:
    """Factory for creating revision response JSON.

    Returns:
        Factory function that creates JSON revision responses
    """

    def _create(
        revised_output: str,
        reasoning: str = "Test revision reasoning",
        addressed: Optional[List[str]] = None,
    ) -> str:
        return json.dumps(
            {
                "revised_output": revised_output,
                "reasoning": reasoning,
                "addressed": addressed or [],
            }
        )

    return _create


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_principle() -> ConstitutionalPrinciple:
    """Create a sample constitutional principle.

    Returns:
        ConstitutionalPrinciple instance for testing
    """
    return ConstitutionalPrinciple(
        id="test_principle_1",
        name="Test Principle",
        critique_prompt="Test critique prompt for evaluation",
        revision_prompt="Test revision prompt for fixing issues",
        severity=PrincipleSeverity.HIGH,
        category=PrincipleCategory.SAFETY,
        domain_tags=["test", "security"],
    )


@pytest.fixture
def sample_critical_principle() -> ConstitutionalPrinciple:
    """Create a sample critical severity principle.

    Returns:
        ConstitutionalPrinciple with CRITICAL severity
    """
    return ConstitutionalPrinciple(
        id="critical_principle_1",
        name="Critical Test Principle",
        critique_prompt="Critical security check",
        revision_prompt="Fix critical security issues",
        severity=PrincipleSeverity.CRITICAL,
        category=PrincipleCategory.SAFETY,
        domain_tags=["security"],
    )


@pytest.fixture
def sample_principles() -> List[ConstitutionalPrinciple]:
    """Create a list of sample principles for testing.

    Returns:
        List of ConstitutionalPrinciple instances
    """
    return [
        ConstitutionalPrinciple(
            id="principle_security",
            name="Security Check",
            critique_prompt="Check for security issues",
            revision_prompt="Fix security issues",
            severity=PrincipleSeverity.CRITICAL,
            category=PrincipleCategory.SAFETY,
            domain_tags=["security"],
        ),
        ConstitutionalPrinciple(
            id="principle_compliance",
            name="Compliance Check",
            critique_prompt="Check for compliance issues",
            revision_prompt="Fix compliance issues",
            severity=PrincipleSeverity.HIGH,
            category=PrincipleCategory.COMPLIANCE,
            domain_tags=["compliance", "cmmc"],
        ),
        ConstitutionalPrinciple(
            id="principle_helpfulness",
            name="Helpfulness Check",
            critique_prompt="Check for helpfulness issues",
            revision_prompt="Improve helpfulness",
            severity=PrincipleSeverity.MEDIUM,
            category=PrincipleCategory.HELPFULNESS,
            domain_tags=["quality"],
        ),
        ConstitutionalPrinciple(
            id="principle_style",
            name="Code Style Check",
            critique_prompt="Check for style issues",
            revision_prompt="Fix style issues",
            severity=PrincipleSeverity.LOW,
            category=PrincipleCategory.CODE_QUALITY,
            domain_tags=["quality", "style"],
        ),
    ]


@pytest.fixture
def sample_context() -> ConstitutionalContext:
    """Create a sample evaluation context.

    Returns:
        ConstitutionalContext instance for testing
    """
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="code_generation",
        user_request="Generate a function to process data",
        domain_tags=["security", "code_generation"],
    )


@pytest.fixture
def sample_critique_result() -> CritiqueResult:
    """Create a sample critique result.

    Returns:
        CritiqueResult instance for testing
    """
    return CritiqueResult(
        principle_id="test_principle_1",
        principle_name="Test Principle",
        severity=PrincipleSeverity.HIGH,
        issues_found=["Issue 1", "Issue 2"],
        reasoning="Test reasoning for the critique",
        requires_revision=True,
        confidence=0.85,
    )


@pytest.fixture
def sample_critique_result_no_issues() -> CritiqueResult:
    """Create a sample critique result with no issues.

    Returns:
        CritiqueResult instance with no issues found
    """
    return CritiqueResult(
        principle_id="test_principle_2",
        principle_name="Clean Principle",
        severity=PrincipleSeverity.MEDIUM,
        issues_found=[],
        reasoning="No issues detected",
        requires_revision=False,
        confidence=0.95,
    )


@pytest.fixture
def sample_critical_critique_result() -> CritiqueResult:
    """Create a critical critique result.

    Returns:
        CritiqueResult with CRITICAL severity and issues
    """
    return CritiqueResult(
        principle_id="critical_principle_1",
        principle_name="Critical Security Principle",
        severity=PrincipleSeverity.CRITICAL,
        issues_found=["SQL injection vulnerability", "Missing input validation"],
        reasoning="Critical security issues found that must be addressed",
        requires_revision=True,
        confidence=0.95,
    )


@pytest.fixture
def sample_revision_result() -> RevisionResult:
    """Create a sample revision result.

    Returns:
        RevisionResult instance for testing
    """
    return RevisionResult(
        original_output="def process(data): return data",
        revised_output="def process(data):\n    validated = validate(data)\n    return validated",
        critiques_addressed=["test_principle_1"],
        reasoning_chain="Added input validation to address security concerns",
        revision_iterations=1,
        converged=True,
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def default_failure_config() -> ConstitutionalFailureConfig:
    """Create default failure configuration.

    Returns:
        ConstitutionalFailureConfig with default values
    """
    return ConstitutionalFailureConfig()


@pytest.fixture
def strict_failure_config() -> ConstitutionalFailureConfig:
    """Create strict failure configuration.

    Returns:
        ConstitutionalFailureConfig with strict settings
    """
    return ConstitutionalFailureConfig(
        critique_failure_policy=CritiqueFailurePolicy.BLOCK,
        revision_failure_policy=RevisionFailurePolicy.BLOCK_FOR_HITL,
        max_critique_retries=3,
        max_revision_iterations=5,
        require_audit_trail=True,
        audit_failure_blocks_execution=True,
    )


@pytest.fixture
def lenient_failure_config() -> ConstitutionalFailureConfig:
    """Create lenient failure configuration.

    Returns:
        ConstitutionalFailureConfig with lenient settings
    """
    return ConstitutionalFailureConfig(
        critique_failure_policy=CritiqueFailurePolicy.PROCEED_LOGGED,
        revision_failure_policy=RevisionFailurePolicy.RETURN_BEST_EFFORT,
        max_critique_retries=1,
        max_revision_iterations=2,
        require_audit_trail=False,
        audit_failure_blocks_execution=False,
    )


# =============================================================================
# Sample Output Fixtures
# =============================================================================


@pytest.fixture
def sample_code_output() -> str:
    """Create sample code output for testing.

    Returns:
        String containing sample code
    """
    return '''def process_user_data(user_id):
    """Process user data from database."""
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db.execute(query)
    return result
'''


@pytest.fixture
def sample_secure_code_output() -> str:
    """Create sample secure code output.

    Returns:
        String containing secure code
    """
    return '''def process_user_data(user_id: int) -> dict:
    """Process user data from database.

    Args:
        user_id: The user ID to look up

    Returns:
        User data dictionary
    """
    query = "SELECT * FROM users WHERE id = %s"
    result = db.execute(query, (user_id,))
    return result
'''


@pytest.fixture
def sample_explanation_output() -> str:
    """Create sample explanation output for testing.

    Returns:
        String containing sample explanation
    """
    return """To implement this feature, you should:
1. Create a new service class
2. Add the necessary dependencies
3. Implement the core logic
4. Write unit tests

This approach is absolutely correct and will definitely work perfectly.
"""


# =============================================================================
# Test YAML Fixtures
# =============================================================================


@pytest.fixture
def minimal_constitution_yaml(tmp_path) -> str:
    """Create a minimal constitution YAML file for testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to the created YAML file
    """
    yaml_content = """
version: "1.0.0"
effective_date: "2026-01-21"

principles:
  test_principle_1:
    name: "Test Principle 1"
    severity: high
    category: safety
    domain_tags: ["test"]
    critique_prompt: |
      Test critique prompt
    revision_prompt: |
      Test revision prompt

  test_principle_2:
    name: "Test Principle 2"
    severity: medium
    category: helpfulness
    domain_tags: ["test"]
    critique_prompt: |
      Another critique prompt
    revision_prompt: |
      Another revision prompt
"""
    yaml_path = tmp_path / "test_constitution.yaml"
    yaml_path.write_text(yaml_content)
    return str(yaml_path)


@pytest.fixture
def full_constitution_yaml(tmp_path) -> str:
    """Create a full constitution YAML file for testing.

    This fixture creates a constitution with multiple principles across
    different categories and severities for comprehensive testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to the created YAML file
    """
    yaml_content = """
version: "1.0.0"
effective_date: "2026-01-21"

principles:
  principle_critical_1:
    name: "Critical Security"
    severity: critical
    category: safety
    domain_tags: ["security"]
    critique_prompt: Check for critical security issues
    revision_prompt: Fix critical security issues

  principle_high_1:
    name: "High Compliance"
    severity: high
    category: compliance
    domain_tags: ["compliance"]
    critique_prompt: Check for compliance issues
    revision_prompt: Fix compliance issues

  principle_medium_1:
    name: "Medium Helpfulness"
    severity: medium
    category: helpfulness
    domain_tags: ["quality"]
    critique_prompt: Check for helpfulness
    revision_prompt: Improve helpfulness

  principle_low_1:
    name: "Low Style"
    severity: low
    category: code_quality
    domain_tags: ["style"]
    critique_prompt: Check code style
    revision_prompt: Fix code style

  principle_disabled:
    name: "Disabled Principle"
    severity: low
    category: code_quality
    domain_tags: ["disabled"]
    enabled: false
    critique_prompt: Should not run
    revision_prompt: Should not run
"""
    yaml_path = tmp_path / "full_constitution.yaml"
    yaml_path.write_text(yaml_content)
    return str(yaml_path)


@pytest.fixture
def invalid_constitution_yaml(tmp_path) -> str:
    """Create an invalid constitution YAML file for error testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to the created invalid YAML file
    """
    yaml_content = """
version: "1.0.0"
# Missing principles key - should cause error
other_key: value
"""
    yaml_path = tmp_path / "invalid_constitution.yaml"
    yaml_path.write_text(yaml_content)
    return str(yaml_path)


# =============================================================================
# Async Test Helpers
# =============================================================================


@pytest.fixture
def event_loop_policy():
    """Return the default event loop policy for async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
