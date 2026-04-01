"""Tests for Self-Reflection Module (ADR-029 Phase 2.2).

Tests the ReflectionModule for agent self-critique and output refinement.
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.agents.reflection_module import (
    CODER_REFLECTION_PROMPT,
    REVIEWER_REFLECTION_PROMPT,
    ReflectionModule,
    ReflectionResult,
    create_reflection_module,
)


class TestReflectionResult:
    """Tests for ReflectionResult dataclass."""

    def test_reflection_result_creation(self):
        """Test ReflectionResult can be created with all fields."""
        result = ReflectionResult(
            original_output={"status": "FAIL_SECURITY"},
            critique="Review appears accurate",
            confidence=0.85,
            issues_found=["possible false positive"],
            revised_output={"status": "PASS"},
            iteration=2,
        )

        assert result.original_output == {"status": "FAIL_SECURITY"}
        assert result.critique == "Review appears accurate"
        assert result.confidence == 0.85
        assert len(result.issues_found) == 1
        assert result.revised_output == {"status": "PASS"}
        assert result.iteration == 2
        assert result.timestamp is not None

    def test_was_refined_true(self):
        """Test was_refined returns True when output changed."""
        result = ReflectionResult(
            original_output={"status": "FAIL_SECURITY"},
            critique="Review refined",
            confidence=0.9,
            issues_found=[],
            revised_output={"status": "PASS"},
            iteration=1,
        )

        assert result.was_refined() is True

    def test_was_refined_false_same_output(self):
        """Test was_refined returns False when output unchanged."""
        original = {"status": "PASS", "finding": "Code is secure"}
        result = ReflectionResult(
            original_output=original,
            critique="No changes needed",
            confidence=0.95,
            issues_found=[],
            revised_output=original,
            iteration=1,
        )

        assert result.was_refined() is False

    def test_was_refined_false_none_output(self):
        """Test was_refined returns False when revised_output is None."""
        result = ReflectionResult(
            original_output={"status": "PASS"},
            critique="No revision performed",
            confidence=0.8,
            issues_found=[],
            revised_output=None,
            iteration=1,
        )

        assert result.was_refined() is False

    def test_confidence_improved(self):
        """Test confidence_improved calculates correctly."""
        result = ReflectionResult(
            original_output={},
            critique="Improved confidence",
            confidence=0.92,
            issues_found=[],
            revised_output={},
            iteration=2,
        )

        # Baseline is 0.7, so improvement = 0.92 - 0.7 = 0.22
        assert abs(result.confidence_improved() - 0.22) < 0.001

    def test_to_dict(self):
        """Test to_dict serialization."""
        result = ReflectionResult(
            original_output={"status": "PASS"},
            critique="Test critique",
            confidence=0.85,
            issues_found=["issue1"],
            revised_output={"status": "PASS", "refined": True},
            iteration=2,
        )

        d = result.to_dict()

        assert d["confidence"] == 0.85
        assert d["iteration"] == 2
        assert d["was_refined"] is True
        assert "timestamp" in d
        assert "confidence_improvement" in d


class TestReflectionModule:
    """Tests for ReflectionModule class."""

    def test_initialization(self):
        """Test ReflectionModule initialization."""
        mock_llm = AsyncMock()

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="TestAgent",
        )

        assert module.llm is mock_llm
        assert module.agent_name == "TestAgent"
        assert module.max_iterations == 3
        assert module.confidence_threshold == 0.9

    def test_initialization_custom_params(self):
        """Test ReflectionModule with custom parameters."""
        mock_llm = AsyncMock()

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="CustomAgent",
            max_iterations=5,
            confidence_threshold=0.95,
        )

        assert module.max_iterations == 5
        assert module.confidence_threshold == 0.95

    def test_initialization_without_llm(self):
        """Test ReflectionModule can be created without LLM (fallback mode)."""
        module = ReflectionModule(
            llm_client=None,
            agent_name="FallbackAgent",
        )

        assert module.llm is None
        assert module.agent_name == "FallbackAgent"

    @pytest.mark.asyncio
    async def test_reflect_and_refine_high_confidence_first_iteration(self):
        """Test reflection stops early with high confidence."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "critique": "Review is accurate and complete.",
                "issues": [],
                "confidence": 0.95,
            }
        )

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        initial_output = {
            "status": "PASS",
            "finding": "Code is secure",
            "vulnerabilities": [],
        }

        result = await module.reflect_and_refine(
            initial_output=initial_output,
            context="Test code context",
            reflection_prompt="Test prompt",
        )

        assert result.confidence >= 0.9
        assert result.iteration == 1
        assert len(result.issues_found) == 0

    @pytest.mark.asyncio
    async def test_reflect_and_refine_iterates_on_low_confidence(self):
        """Test reflection iterates when confidence is low."""
        mock_llm = AsyncMock()
        # First call: low confidence with issues
        # Second call: high confidence, no issues
        mock_llm.generate.side_effect = [
            json.dumps(
                {
                    "critique": "Some findings uncertain.",
                    "issues": ["Finding 1 may be false positive"],
                    "confidence": 0.6,
                }
            ),
            json.dumps(
                {
                    "status": "PASS",
                    "finding": "Refined review",
                    "vulnerabilities": [],
                }
            ),
            json.dumps(
                {
                    "critique": "Review is now accurate.",
                    "issues": [],
                    "confidence": 0.92,
                }
            ),
        ]

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        initial_output = {
            "status": "FAIL_SECURITY",
            "finding": "Found vulnerability",
            "vulnerabilities": [{"type": "WEAK_CRYPTO"}],
        }

        result = await module.reflect_and_refine(
            initial_output=initial_output,
            context="Test code context",
        )

        assert result.iteration >= 2
        # LLM was called multiple times
        assert mock_llm.generate.call_count >= 2

    @pytest.mark.asyncio
    async def test_reflect_and_refine_max_iterations(self):
        """Test reflection stops at max iterations."""
        mock_llm = AsyncMock()
        # Always return low confidence
        mock_llm.generate.return_value = json.dumps(
            {
                "critique": "Still uncertain.",
                "issues": ["Uncertain about findings"],
                "confidence": 0.5,
            }
        )

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
            max_iterations=2,
        )

        initial_output = {"status": "FAIL_SECURITY"}

        result = await module.reflect_and_refine(
            initial_output=initial_output,
            context="Test context",
        )

        assert result.iteration == 2
        assert result.confidence < 0.9
        assert len(result.issues_found) > 0

    @pytest.mark.asyncio
    async def test_self_critique_fallback_pass_status(self):
        """Test fallback critique for PASS status."""
        module = ReflectionModule(
            llm_client=None,  # Force fallback
            agent_name="Reviewer",
        )

        output = {
            "status": "PASS",
            "finding": "Code is secure",
            "vulnerabilities": [],
        }

        critique = module._self_critique_fallback(output)

        assert critique["confidence"] == 0.85
        assert "passed" in critique["critique"].lower()
        assert len(critique["issues"]) == 0

    @pytest.mark.asyncio
    async def test_self_critique_fallback_many_vulnerabilities(self):
        """Test fallback critique with many vulnerabilities."""
        module = ReflectionModule(
            llm_client=None,
            agent_name="Reviewer",
        )

        output = {
            "status": "FAIL_SECURITY",
            "vulnerabilities": [
                {"type": "WEAK_CRYPTO"},
                {"type": "SQL_INJECTION"},
                {"type": "XSS"},
                {"type": "HARDCODED_SECRET"},
                {"type": "CSRF"},
                {"type": "BUFFER_OVERFLOW"},  # 6 vulnerabilities
            ],
        }

        critique = module._self_critique_fallback(output)

        # Lower confidence for many findings (may include false positives)
        assert critique["confidence"] == 0.65
        assert "false positive" in critique["critique"].lower()
        assert len(critique["issues"]) > 0

    @pytest.mark.asyncio
    async def test_self_critique_fallback_few_vulnerabilities(self):
        """Test fallback critique with few vulnerabilities."""
        module = ReflectionModule(
            llm_client=None,
            agent_name="Reviewer",
        )

        output = {
            "status": "FAIL_SECURITY",
            "vulnerabilities": [
                {"type": "WEAK_CRYPTO"},
            ],
        }

        critique = module._self_critique_fallback(output)

        assert critique["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_revise_output_fallback(self):
        """Test fallback revision adds reflection note."""
        module = ReflectionModule(
            llm_client=None,
            agent_name="Reviewer",
        )

        output = {
            "status": "FAIL_SECURITY",
            "vulnerabilities": [{"type": "WEAK_CRYPTO"}],
        }

        revised = module._revise_output_fallback(
            output=output,
            issues=["Finding may be false positive"],
        )

        assert "reflection_note" in revised
        assert "false positive" in revised["reflection_note"].lower()


class TestReflectionModuleWithLLM:
    """Tests for ReflectionModule LLM integration."""

    @pytest.mark.asyncio
    async def test_self_critique_parses_llm_response(self):
        """Test _self_critique correctly parses LLM response."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "critique": "Review appears thorough.",
                "issues": ["One uncertain finding"],
                "confidence": 0.82,
            }
        )

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        critique = await module._self_critique(
            output={"status": "FAIL_SECURITY"},
            context="Test context",
            reflection_prompt="Test prompt",
        )

        assert critique["confidence"] == 0.82
        assert len(critique["issues"]) == 1
        assert "thorough" in critique["critique"]

    @pytest.mark.asyncio
    async def test_self_critique_handles_invalid_json(self):
        """Test _self_critique falls back on invalid JSON."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "This is not valid JSON"

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        critique = await module._self_critique(
            output={"status": "PASS"},
            context="Test context",
            reflection_prompt="Test prompt",
        )

        # Should use fallback
        assert "confidence" in critique
        assert critique["confidence"] > 0

    @pytest.mark.asyncio
    async def test_self_critique_handles_llm_error(self):
        """Test _self_critique handles LLM errors gracefully."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM error")

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        critique = await module._self_critique(
            output={"status": "PASS"},
            context="Test context",
            reflection_prompt="Test prompt",
        )

        # Should use fallback
        assert "confidence" in critique

    @pytest.mark.asyncio
    async def test_revise_output_parses_llm_response(self):
        """Test _revise_output correctly parses LLM response."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "status": "PASS",
                "finding": "Revised: code is secure after review",
                "vulnerabilities": [],
            }
        )

        module = ReflectionModule(
            llm_client=mock_llm,
            agent_name="Reviewer",
        )

        revised = await module._revise_output(
            output={"status": "FAIL_SECURITY"},
            critique="Found false positive",
            issues=["Crypto finding is false positive"],
        )

        assert revised["status"] == "PASS"
        assert "Revised" in revised["finding"]


class TestReviewerAgentWithReflection:
    """Tests for ReviewerAgent with self-reflection enabled."""

    @pytest.mark.asyncio
    async def test_reviewer_accepts_enable_reflection(self):
        """Test ReviewerAgent accepts enable_reflection parameter."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = AsyncMock()

        reviewer = ReviewerAgent(
            llm_client=mock_llm,
            enable_reflection=True,
        )

        assert reviewer.enable_reflection is True
        assert reviewer.reflection is not None

    @pytest.mark.asyncio
    async def test_reviewer_reflection_disabled_by_default(self):
        """Test reflection is disabled by default."""
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(llm_client=None)

        assert reviewer.enable_reflection is False
        assert reviewer.reflection is None

    @pytest.mark.asyncio
    async def test_reviewer_reflection_requires_llm(self):
        """Test reflection requires LLM to be enabled."""
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(
            llm_client=None,
            enable_reflection=True,  # Requested but can't work without LLM
        )

        # Reflection should not be initialized without LLM
        assert reviewer.reflection is None

    @pytest.mark.asyncio
    async def test_review_code_returns_reflection_metadata(self):
        """Test review_code includes reflection metadata in result."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "status": "PASS",
                "finding": "Code is secure",
                "vulnerabilities": [],
                "recommendations": [],
            }
        )

        reviewer = ReviewerAgent(
            llm_client=mock_llm,
            enable_reflection=False,
        )

        result = await reviewer.review_code("import hashlib\nclass Test: pass")

        assert "reflection_applied" in result
        assert result["reflection_applied"] is False
        assert "reflection_iterations" in result
        assert "reflection_confidence" in result

    @pytest.mark.asyncio
    async def test_review_code_with_reflection_enabled(self):
        """Test review_code with self-reflection enabled."""
        from src.agents.reviewer_agent import ReviewerAgent

        mock_llm = AsyncMock()
        # Initial review response
        mock_llm.generate.side_effect = [
            json.dumps(
                {
                    "status": "PASS",
                    "finding": "Code is secure",
                    "vulnerabilities": [],
                    "recommendations": [],
                }
            ),
            # Reflection critique response
            json.dumps(
                {
                    "critique": "Review is accurate",
                    "issues": [],
                    "confidence": 0.92,
                }
            ),
        ]

        reviewer = ReviewerAgent(
            llm_client=mock_llm,
            enable_reflection=True,
        )

        result = await reviewer.review_code("import hashlib\nclass Test: pass")

        assert result["reflection_applied"] is True
        assert result["reflection_iterations"] >= 1
        assert result["reflection_confidence"] is not None
        assert result["reflection_confidence"] >= 0.9


class TestCreateReflectionModule:
    """Tests for create_reflection_module factory function."""

    def test_create_with_mock(self):
        """Test factory creates module with mock LLM."""
        module = create_reflection_module(
            use_mock=True,
            agent_name="TestAgent",
        )

        assert module is not None
        assert module.llm is not None
        assert module.agent_name == "TestAgent"

    def test_create_with_custom_params(self):
        """Test factory creates module with custom parameters."""
        module = create_reflection_module(
            use_mock=True,
            agent_name="CustomAgent",
            max_iterations=5,
            confidence_threshold=0.95,
        )

        assert module.max_iterations == 5
        assert module.confidence_threshold == 0.95


class TestReflectionPrompts:
    """Tests for reflection prompt constants."""

    def test_reviewer_prompt_exists(self):
        """Test REVIEWER_REFLECTION_PROMPT is defined."""
        assert REVIEWER_REFLECTION_PROMPT is not None
        assert len(REVIEWER_REFLECTION_PROMPT) > 50
        assert "security" in REVIEWER_REFLECTION_PROMPT.lower()

    def test_coder_prompt_exists(self):
        """Test CODER_REFLECTION_PROMPT is defined."""
        assert CODER_REFLECTION_PROMPT is not None
        assert len(CODER_REFLECTION_PROMPT) > 50
        assert "code" in CODER_REFLECTION_PROMPT.lower()
