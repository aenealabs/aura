"""Unit tests for Chain of Draft (CoD) prompting templates.

Tests the CoD prompt generation module including:
- CoDPromptMode enum and mode switching
- Template generation for all agent types
- Token savings estimation
- Fallback to CoT prompts

ADR-029 Phase 1.2 Implementation
"""

import pytest

from src.prompts.cod_templates import (
    COD_CODER_PROMPT,
    COD_QUERY_PLANNER_PROMPT,
    COD_REVIEWER_PROMPT,
    COD_VALIDATOR_INSIGHTS_PROMPT,
    COD_VALIDATOR_REQUIREMENTS_PROMPT,
    CoDPromptMode,
    build_cod_prompt,
    estimate_token_savings,
    get_prompt_mode,
    set_prompt_mode,
)


class TestCoDPromptMode:
    """Tests for CoDPromptMode enum and mode management."""

    def test_prompt_modes_exist(self):
        """Verify all expected prompt modes are defined."""
        assert CoDPromptMode.COD.value == "cod"
        assert CoDPromptMode.COT.value == "cot"
        assert CoDPromptMode.AUTO.value == "auto"

    def test_set_and_get_prompt_mode(self):
        """Test setting and getting global prompt mode."""
        # Save original mode
        original = get_prompt_mode()

        try:
            # Test setting COT mode
            set_prompt_mode(CoDPromptMode.COT)
            assert get_prompt_mode() == CoDPromptMode.COT

            # Test setting AUTO mode
            set_prompt_mode(CoDPromptMode.AUTO)
            assert get_prompt_mode() == CoDPromptMode.AUTO

            # Test setting COD mode
            set_prompt_mode(CoDPromptMode.COD)
            assert get_prompt_mode() == CoDPromptMode.COD
        finally:
            # Restore original mode
            set_prompt_mode(original)

    def test_env_var_override(self, monkeypatch):
        """Test environment variable can override prompt mode."""
        # Test COT override
        monkeypatch.setenv("AURA_PROMPT_MODE", "cot")
        assert get_prompt_mode() == CoDPromptMode.COT

        # Test AUTO override
        monkeypatch.setenv("AURA_PROMPT_MODE", "auto")
        assert get_prompt_mode() == CoDPromptMode.AUTO

        # Test invalid value defaults to global setting
        monkeypatch.setenv("AURA_PROMPT_MODE", "invalid")
        set_prompt_mode(CoDPromptMode.COD)
        assert get_prompt_mode() == CoDPromptMode.COD


class TestBuildCoDPrompt:
    """Tests for build_cod_prompt function."""

    def test_reviewer_cod_prompt(self):
        """Test building CoD prompt for reviewer agent."""
        prompt = build_cod_prompt(
            "reviewer",
            code="def foo(): pass",
            mode=CoDPromptMode.COD,
        )

        # Verify CoD-specific elements
        assert "Draft reasoning" in prompt
        assert "[Crypto check]" in prompt
        assert "[Secrets check]" in prompt
        assert "[Injection check]" in prompt
        assert "[OWASP check]" in prompt
        assert "def foo(): pass" in prompt

    def test_reviewer_cot_prompt(self):
        """Test building CoT prompt for reviewer agent."""
        prompt = build_cod_prompt(
            "reviewer",
            code="def foo(): pass",
            mode=CoDPromptMode.COT,
        )

        # Verify CoT-specific elements
        assert "You are a security code reviewer" in prompt
        assert "CMMC Level 3" in prompt
        assert "PROHIBITED: SHA1, MD5" in prompt
        assert "def foo(): pass" in prompt
        # CoT should NOT have draft reasoning
        assert "Draft reasoning" not in prompt

    def test_coder_cod_prompt(self):
        """Test building CoD prompt for coder agent (remediation)."""
        prompt = build_cod_prompt(
            "coder",
            vulnerability="SQL injection",
            context="User input handling",
            code="query = f'SELECT * FROM users'",
            mode=CoDPromptMode.COD,
        )

        assert "Fix: SQL injection" in prompt
        assert "User input handling" in prompt
        assert "Draft" in prompt
        assert "[Issue]" in prompt
        assert "[Fix]" in prompt

    def test_coder_initial_cod_prompt(self):
        """Test building CoD prompt for coder agent (initial generation)."""
        prompt = build_cod_prompt(
            "coder_initial",
            task="Create authentication handler",
            context="JWT tokens for API",
            mode=CoDPromptMode.COD,
        )

        assert "Create authentication handler" in prompt
        assert "JWT tokens for API" in prompt
        assert "[Approach]" in prompt
        assert "[Security]" in prompt
        assert "[Implementation]" in prompt

    def test_validator_insights_cod_prompt(self):
        """Test building CoD prompt for validator insights."""
        prompt = build_cod_prompt(
            "validator_insights",
            code="import hashlib; hashlib.sha1(data)",
            issues="WEAK_CRYPTOGRAPHY: SHA1 detected",
            mode=CoDPromptMode.COD,
        )

        assert "import hashlib" in prompt
        assert "WEAK_CRYPTOGRAPHY" in prompt
        assert "[Security gaps]" in prompt
        assert "[Quality issues]" in prompt

    def test_validator_requirements_cod_prompt(self):
        """Test building CoD prompt for validator requirements."""
        prompt = build_cod_prompt(
            "validator_requirements",
            code="def process(): pass",
            requirements="1. Must use SHA256\n2. Must validate inputs",
            mode=CoDPromptMode.COD,
        )

        assert "def process(): pass" in prompt
        assert "Must use SHA256" in prompt

    def test_query_planner_cod_prompt(self):
        """Test building CoD prompt for query planner."""
        prompt = build_cod_prompt(
            "query_planner",
            query="Find authentication code",
            budget=100000,
            mode=CoDPromptMode.COD,
        )

        assert "Find authentication code" in prompt
        assert "100000" in prompt
        assert "[Intent]" in prompt
        assert "[Primary]" in prompt
        assert "[Secondary]" in prompt

    def test_invalid_agent_type(self):
        """Test that invalid agent type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            build_cod_prompt("invalid_agent", code="test")

    def test_auto_mode_defaults_to_cod(self):
        """Test that AUTO mode defaults to CoD prompts."""
        prompt = build_cod_prompt(
            "reviewer",
            code="def foo(): pass",
            mode=CoDPromptMode.AUTO,
        )

        # AUTO should use CoD
        assert "Draft reasoning" in prompt

    def test_uses_global_mode_when_none_provided(self):
        """Test that global mode is used when mode parameter is None."""
        original = get_prompt_mode()

        try:
            # Set global to COT
            set_prompt_mode(CoDPromptMode.COT)
            prompt = build_cod_prompt("reviewer", code="def foo(): pass")
            assert "You are a security code reviewer" in prompt
            assert "Draft reasoning" not in prompt

            # Set global to COD
            set_prompt_mode(CoDPromptMode.COD)
            prompt = build_cod_prompt("reviewer", code="def foo(): pass")
            assert "Draft reasoning" in prompt
        finally:
            set_prompt_mode(original)


class TestPromptTemplates:
    """Tests for raw prompt template strings."""

    def test_cod_reviewer_prompt_structure(self):
        """Verify COD_REVIEWER_PROMPT has expected structure."""
        assert "{code}" in COD_REVIEWER_PROMPT
        assert "Draft reasoning" in COD_REVIEWER_PROMPT
        assert (
            "CMMC" in COD_REVIEWER_PROMPT or "compliance" in COD_REVIEWER_PROMPT.lower()
        )

    def test_cod_coder_prompt_structure(self):
        """Verify COD_CODER_PROMPT has expected structure."""
        assert "{vulnerability}" in COD_CODER_PROMPT
        assert "{context}" in COD_CODER_PROMPT
        assert "{code}" in COD_CODER_PROMPT
        assert "Draft" in COD_CODER_PROMPT

    def test_cod_validator_insights_prompt_structure(self):
        """Verify COD_VALIDATOR_INSIGHTS_PROMPT has expected structure."""
        assert "{code}" in COD_VALIDATOR_INSIGHTS_PROMPT
        assert "{issues}" in COD_VALIDATOR_INSIGHTS_PROMPT
        assert "Draft" in COD_VALIDATOR_INSIGHTS_PROMPT

    def test_cod_validator_requirements_prompt_structure(self):
        """Verify COD_VALIDATOR_REQUIREMENTS_PROMPT has expected structure."""
        assert "{code}" in COD_VALIDATOR_REQUIREMENTS_PROMPT
        assert "{requirements}" in COD_VALIDATOR_REQUIREMENTS_PROMPT
        assert "Draft" in COD_VALIDATOR_REQUIREMENTS_PROMPT

    def test_cod_query_planner_prompt_structure(self):
        """Verify COD_QUERY_PLANNER_PROMPT has expected structure."""
        assert "{query}" in COD_QUERY_PLANNER_PROMPT
        assert "{budget}" in COD_QUERY_PLANNER_PROMPT
        assert "Draft" in COD_QUERY_PLANNER_PROMPT


class TestTokenSavingsEstimation:
    """Tests for token savings estimation function."""

    def test_estimate_token_savings_basic(self):
        """Test basic token savings estimation."""
        cod_prompt = "Short CoD prompt with minimal text."
        cot_prompt = "This is a much longer Chain of Thought prompt that includes many more words and explanations and detailed reasoning steps."

        result = estimate_token_savings(cod_prompt, cot_prompt)

        assert "cod_tokens" in result
        assert "cot_tokens" in result
        assert "savings_percent" in result
        assert "tokens_saved" in result
        assert result["cod_tokens"] < result["cot_tokens"]
        assert result["savings_percent"] > 0
        assert result["tokens_saved"] > 0

    def test_estimate_token_savings_equal_prompts(self):
        """Test estimation when prompts are equal length."""
        prompt = "Same length prompt."

        result = estimate_token_savings(prompt, prompt)

        assert result["savings_percent"] == 0.0
        assert result["tokens_saved"] == 0

    def test_estimate_token_savings_real_templates(self):
        """Test token savings with actual CoD vs CoT templates."""
        # Build actual prompts
        cod = build_cod_prompt(
            "reviewer", code="def foo(): pass", mode=CoDPromptMode.COD
        )
        cot = build_cod_prompt(
            "reviewer", code="def foo(): pass", mode=CoDPromptMode.COT
        )

        result = estimate_token_savings(cod, cot)

        # CoD should be significantly smaller
        assert result["savings_percent"] > 30  # At least 30% savings
        print(f"\nReviewer savings: {result['savings_percent']}%")

    def test_estimate_token_savings_query_planner(self):
        """Test token savings for query planner prompts."""
        cod = build_cod_prompt(
            "query_planner",
            query="Find auth code",
            budget=100000,
            mode=CoDPromptMode.COD,
        )
        cot = build_cod_prompt(
            "query_planner",
            query="Find auth code",
            budget=100000,
            mode=CoDPromptMode.COT,
        )

        result = estimate_token_savings(cod, cot)

        # CoD should be significantly smaller
        assert result["savings_percent"] > 30  # At least 30% savings
        print(f"\nQuery planner savings: {result['savings_percent']}%")


class TestAgentIntegration:
    """Tests verifying agents can use CoD prompts correctly."""

    def test_reviewer_agent_imports(self):
        """Verify reviewer agent can import CoD prompts."""
        from src.agents.reviewer_agent import ReviewerAgent

        # Agent should be importable without errors
        assert ReviewerAgent is not None

    def test_coder_agent_imports(self):
        """Verify coder agent can import CoD prompts."""
        from src.agents.coder_agent import CoderAgent

        # Agent should be importable without errors
        assert CoderAgent is not None

    def test_validator_agent_imports(self):
        """Verify validator agent can import CoD prompts."""
        from src.agents.validator_agent import ValidatorAgent

        # Agent should be importable without errors
        assert ValidatorAgent is not None

    def test_query_planning_agent_imports(self):
        """Verify query planning agent can import CoD prompts."""
        from src.agents.query_planning_agent import QueryPlanningAgent

        # Agent should be importable without errors
        assert QueryPlanningAgent is not None
