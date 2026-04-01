"""
Tests for Coder Agent

Tests for secure code generation agent.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== CoderAgent Initialization Tests ====================


class TestCoderAgentInit:
    """Tests for CoderAgent initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without parameters."""
        from src.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        assert agent.llm is None
        assert agent.monitor is not None

    def test_initialization_with_llm(self):
        """Test initialization with LLM client."""
        from src.agents.coder_agent import CoderAgent

        mock_llm = MagicMock()
        agent = CoderAgent(llm_client=mock_llm)
        assert agent.llm == mock_llm

    def test_initialization_with_monitor(self):
        """Test initialization with custom monitor."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.monitoring_service import MonitorAgent

        monitor = MonitorAgent()
        agent = CoderAgent(monitor=monitor)
        assert agent.monitor == monitor


# ==================== Code Generation Tests ====================


class TestCodeGeneration:
    """Tests for code generation."""

    @pytest.mark.asyncio
    async def test_generate_code_without_llm(self):
        """Test code generation without LLM uses fallback."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()  # No LLM
        context = HybridContext(
            items=[], query="Generate hash function", target_entity="DataProcessor"
        )

        result = await agent.generate_code(context, "Create a secure hash function")
        assert "code" in result
        assert "language" in result
        assert result["language"] == "python"
        assert "hashlib" in result["code"]

    @pytest.mark.asyncio
    async def test_generate_code_with_llm(self):
        """Test code generation with LLM."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value="def secure_hash(data):\n    return hashlib.sha256(data).hexdigest()"
        )

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(
            items=[], query="Generate hash", target_entity="secure_hash"
        )

        result = await agent.generate_code(context, "Create secure hash")
        assert "code" in result
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_code_llm_failure_fallback(self):
        """Test that LLM failure falls back gracefully."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(items=[], query="Generate code", target_entity="test")

        result = await agent.generate_code(context, "Generate code")
        # Should fallback to template code
        assert "code" in result

    @pytest.mark.asyncio
    async def test_generate_code_with_remediation_context(self):
        """Test code generation with remediation context."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import ContextItem, ContextSource, HybridContext

        agent = CoderAgent()
        context = HybridContext(
            items=[
                ContextItem(
                    content="Use SHA256 instead of SHA1",
                    source=ContextSource.REMEDIATION,
                    confidence=1.0,
                )
            ],
            query="Fix hash vulnerability",
            target_entity="calculate_checksum",
        )

        result = await agent.generate_code(context, "Fix hash function")
        assert result["has_remediation"] is True
        # Remediation code should use SHA256
        assert "sha256" in result["code"].lower()


# ==================== Patch Generation Tests ====================


class TestPatchGeneration:
    """Tests for security patch generation."""

    @pytest.mark.asyncio
    async def test_generate_patch_fallback(self):
        """Test patch generation fallback."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()  # No LLM
        context = HybridContext(
            items=[], query="Patch SHA1 vulnerability", target_entity="hash_function"
        )

        original_code = """
def hash_data(data):
    # VULNERABILITY: Insecure hash function used
    return hashlib.sha1(data.encode()).hexdigest()
"""
        vulnerability = {"finding": "Use of SHA1 detected", "severity": "High"}

        result = await agent.generate_patch(original_code, vulnerability, context)
        assert "patched_code" in result
        assert "changes_made" in result
        assert "confidence" in result
        assert "sha256" in result["patched_code"].lower()

    @pytest.mark.asyncio
    async def test_generate_patch_with_llm(self):
        """Test patch generation with LLM."""
        import json

        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "patched_code": "def safe(): return sha256()",
                    "changes_made": "Replaced insecure algorithm",
                    "confidence": 0.95,
                }
            )
        )

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(items=[], query="Patch code", target_entity="test")

        result = await agent.generate_patch("original", {"finding": "test"}, context)
        assert result["patched_code"] == "def safe(): return sha256()"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_generate_patch_llm_invalid_json(self):
        """Test patch generation when LLM returns invalid JSON."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="not valid json")

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(items=[], query="Patch", target_entity="test")

        result = await agent.generate_patch("code", {"finding": "sha1"}, context)
        # Should fallback
        assert "patched_code" in result

    @pytest.mark.asyncio
    async def test_patch_no_automatic_fix(self):
        """Test patch when no automatic fix is available."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()
        context = HybridContext(
            items=[], query="Patch unknown issue", target_entity="test"
        )

        result = await agent.generate_patch(
            "def unknown(): pass",
            {"finding": "Unknown vulnerability", "severity": "Medium"},
            context,
        )
        assert result["confidence"] == 0.0
        assert "No automatic patch" in result["changes_made"]


# ==================== Fallback Code Tests ====================


class TestFallbackCode:
    """Tests for fallback code generation."""

    def test_fallback_without_remediation(self):
        """Test fallback generates vulnerable code without remediation."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()
        context = HybridContext(items=[], query="Generate code", target_entity="test")

        code = agent._generate_code_fallback(context)
        # Without remediation, generates vulnerable code (sha1)
        assert "sha1" in code

    def test_fallback_with_remediation(self):
        """Test fallback generates secure code with remediation."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import ContextItem, ContextSource, HybridContext

        agent = CoderAgent()
        context = HybridContext(
            items=[
                ContextItem(
                    content="Fix vulnerability",
                    source=ContextSource.REMEDIATION,
                    confidence=1.0,
                )
            ],
            query="Fix code",
            target_entity="test",
        )

        code = agent._generate_code_fallback(context)
        # With remediation, generates secure code (sha256)
        assert "sha256" in code


# ==================== Factory Function Tests ====================


class TestCreateCoderAgent:
    """Tests for create_coder_agent factory function."""

    def test_create_with_mock(self):
        """Test creating agent with mock LLM."""
        from src.agents.coder_agent import create_coder_agent

        agent = create_coder_agent(use_mock=True)
        assert agent.llm is not None


# ==================== LLM Code Generation Tests ====================


class TestLLMCodeGeneration:
    """Tests for LLM-powered code generation."""

    @pytest.mark.asyncio
    async def test_code_extraction_from_markdown(self):
        """Test extracting code from markdown blocks."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value="```python\ndef test():\n    pass\n```"
        )

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(items=[], query="Generate", target_entity="test")

        result = await agent.generate_code(context, "Generate function")
        # Should strip markdown
        assert "```" not in result["code"]

    @pytest.mark.asyncio
    async def test_generate_with_neural_memory_context(self):
        """Test generation with neural memory context."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import ContextItem, ContextSource, HybridContext

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="def from_memory(): pass")

        agent = CoderAgent(llm_client=mock_llm)
        context = HybridContext(
            items=[
                ContextItem(
                    content="Past experience: similar pattern worked",
                    source=ContextSource.NEURAL_MEMORY,
                    confidence=0.8,
                )
            ],
            query="Generate from memory",
            target_entity="function",
        )

        result = await agent.generate_code(context, "Generate similar code")
        assert "code" in result


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_context(self):
        """Test generation with empty context."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()
        context = HybridContext(items=[], query="", target_entity="")

        result = await agent.generate_code(context, "Generate code")
        assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_task_description(self):
        """Test with very long task description."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()
        context = HybridContext(items=[], query="Test", target_entity="test")

        long_description = "Generate a function that " + " ".join(
            ["processes data"] * 100
        )
        result = await agent.generate_code(context, long_description)
        assert result is not None

    @pytest.mark.asyncio
    async def test_special_characters_in_code(self):
        """Test handling of special characters."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext

        agent = CoderAgent()
        context = HybridContext(
            items=[], query="Handle special chars", target_entity="test"
        )

        original = "def func(): return 'Hello, \"World\"!'"
        result = await agent.generate_patch(
            original, {"finding": "Test", "severity": "Low"}, context
        )
        assert result is not None


# ==================== Monitoring Integration ====================


class TestMonitoringIntegration:
    """Tests for monitoring integration."""

    @pytest.mark.asyncio
    async def test_monitor_records_activity(self):
        """Test that monitor records code generation activity."""
        from src.agents.coder_agent import CoderAgent
        from src.agents.context_objects import HybridContext
        from src.agents.monitoring_service import MonitorAgent

        monitor = MonitorAgent()
        agent = CoderAgent(monitor=monitor)
        context = HybridContext(items=[], query="Test", target_entity="test")

        await agent.generate_code(context, "Generate code")
        # Monitor should have recorded activity
        report = monitor.finalize_report()
        assert report is not None
        assert "total_tokens_used" in report
