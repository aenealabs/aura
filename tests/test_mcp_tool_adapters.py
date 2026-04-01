"""
Tests for MCP Tool Adapters.

Covers AuraAgentCategory/AgentCapability enums, AuraToolDefinition/AdapterInvocationResult
dataclasses, and various adapter implementations for exposing Aura agents as MCP tools.
"""

import sys
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Clean Module Cache and Apply Mocks BEFORE importing mcp_tool_adapters
# =============================================================================

# Save original modules before mocking to prevent test pollution
_original_src_config = sys.modules.get("src.config")
_original_mcp_adapters = sys.modules.get("src.services.mcp_tool_adapters")

# Remove any cached imports that might be polluted
modules_to_clear = [
    "src.services.mcp_tool_adapters",
    "src.config",
]
for mod in modules_to_clear:
    if mod in sys.modules:
        del sys.modules[mod]


# Create mock decorator that passes through
def mock_enterprise_decorator(func):
    """Mock decorator that just returns the function unchanged."""
    return func


# Create a proper mock config module
class MockConfig:
    """Mock config module."""

    require_enterprise_mode = staticmethod(mock_enterprise_decorator)

    @staticmethod
    def get_integration_config():
        return MagicMock()


sys.modules["src.config"] = MockConfig()

# Now import the module with clean state
from src.services.mcp_tool_adapters import (
    AdapterInvocationResult,
    AgentCapability,
    ArchitectureAnalyzerAdapter,
    AuraAgentCategory,
    AuraToolAdapter,
    AuraToolDefinition,
    BaseAgentAdapter,
    CodeReviewerAdapter,
    DocumentationGeneratorAdapter,
    PatchGeneratorAdapter,
    SecurityScannerAdapter,
    ThreatIntelligenceAdapter,
    get_aura_tool_ids,
    get_aura_tools,
)

# Restore original modules to prevent pollution of other tests
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_mcp_adapters is not None:
    sys.modules["src.services.mcp_tool_adapters"] = _original_mcp_adapters


# =============================================================================
# AuraAgentCategory Enum Tests
# =============================================================================


class TestAuraAgentCategory:
    """Tests for AuraAgentCategory enum."""

    def test_security(self):
        """Test security category."""
        assert AuraAgentCategory.SECURITY.value == "security"

    def test_code_analysis(self):
        """Test code analysis category."""
        assert AuraAgentCategory.CODE_ANALYSIS.value == "code_analysis"

    def test_orchestration(self):
        """Test orchestration category."""
        assert AuraAgentCategory.ORCHESTRATION.value == "orchestration"

    def test_documentation(self):
        """Test documentation category."""
        assert AuraAgentCategory.DOCUMENTATION.value == "documentation"

    def test_testing(self):
        """Test testing category."""
        assert AuraAgentCategory.TESTING.value == "testing"

    def test_intelligence(self):
        """Test intelligence category."""
        assert AuraAgentCategory.INTELLIGENCE.value == "intelligence"

    def test_category_count(self):
        """Test that all 6 categories exist."""
        assert len(AuraAgentCategory) == 6


# =============================================================================
# AgentCapability Enum Tests
# =============================================================================


class TestAgentCapability:
    """Tests for AgentCapability enum."""

    def test_vulnerability_detection(self):
        """Test vulnerability detection capability."""
        assert (
            AgentCapability.VULNERABILITY_DETECTION.value == "vulnerability_detection"
        )

    def test_code_review(self):
        """Test code review capability."""
        assert AgentCapability.CODE_REVIEW.value == "code_review"

    def test_patch_generation(self):
        """Test patch generation capability."""
        assert AgentCapability.PATCH_GENERATION.value == "patch_generation"

    def test_architecture_analysis(self):
        """Test architecture analysis capability."""
        assert AgentCapability.ARCHITECTURE_ANALYSIS.value == "architecture_analysis"

    def test_threat_assessment(self):
        """Test threat assessment capability."""
        assert AgentCapability.THREAT_ASSESSMENT.value == "threat_assessment"

    def test_documentation_generation(self):
        """Test documentation generation capability."""
        assert (
            AgentCapability.DOCUMENTATION_GENERATION.value == "documentation_generation"
        )

    def test_test_generation(self):
        """Test test generation capability."""
        assert AgentCapability.TEST_GENERATION.value == "test_generation"

    def test_compliance_check(self):
        """Test compliance check capability."""
        assert AgentCapability.COMPLIANCE_CHECK.value == "compliance_check"

    def test_capability_count(self):
        """Test that all 8 capabilities exist."""
        assert len(AgentCapability) == 8


# =============================================================================
# AuraToolDefinition Dataclass Tests
# =============================================================================


class TestAuraToolDefinition:
    """Tests for AuraToolDefinition dataclass."""

    def test_create_basic_definition(self):
        """Test creating a basic tool definition."""
        tool = AuraToolDefinition(
            tool_id="test_tool",
            name="Test Tool",
            description="A test tool",
            category=AuraAgentCategory.SECURITY,
            capabilities=[AgentCapability.VULNERABILITY_DETECTION],
        )
        assert tool.tool_id == "test_tool"
        assert tool.name == "Test Tool"
        assert tool.description == "A test tool"
        assert tool.category == AuraAgentCategory.SECURITY

    def test_default_values(self):
        """Test default values for optional fields."""
        tool = AuraToolDefinition(
            tool_id="test",
            name="Test",
            description="Test",
            category=AuraAgentCategory.TESTING,
            capabilities=[],
        )
        assert tool.version == "1.0"
        assert tool.input_schema == {}
        assert tool.output_schema == {}
        assert tool.max_execution_time_seconds == 300
        assert tool.requires_sandbox is False
        assert tool.requires_hitl_approval is False
        assert tool.estimated_tokens_per_invocation == 1000
        assert tool.estimated_cost_usd == 0.01

    def test_full_definition(self):
        """Test tool definition with all fields."""
        tool = AuraToolDefinition(
            tool_id="security_scanner",
            name="Security Scanner",
            description="Scan for vulnerabilities",
            category=AuraAgentCategory.SECURITY,
            capabilities=[
                AgentCapability.VULNERABILITY_DETECTION,
                AgentCapability.COMPLIANCE_CHECK,
            ],
            version="2.0",
            input_schema={"repository": "string"},
            output_schema={"vulnerabilities": "array"},
            max_execution_time_seconds=600,
            requires_sandbox=True,
            requires_hitl_approval=True,
            estimated_tokens_per_invocation=2000,
            estimated_cost_usd=0.05,
        )
        assert tool.version == "2.0"
        assert tool.requires_sandbox is True
        assert tool.requires_hitl_approval is True
        assert len(tool.capabilities) == 2


# =============================================================================
# AdapterInvocationResult Dataclass Tests
# =============================================================================


class TestAdapterInvocationResult:
    """Tests for AdapterInvocationResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = AdapterInvocationResult(
            tool_id="security_scanner",
            success=True,
            data={"vulnerabilities": 3},
        )
        assert result.tool_id == "security_scanner"
        assert result.success is True
        assert result.data == {"vulnerabilities": 3}

    def test_create_failure_result(self):
        """Test creating a failed result."""
        result = AdapterInvocationResult(
            tool_id="code_reviewer",
            success=False,
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_default_values(self):
        """Test default values."""
        result = AdapterInvocationResult(
            tool_id="test",
            success=True,
        )
        assert result.data == {}
        assert result.error is None
        assert result.execution_time_ms == 0.0
        assert result.tokens_used == 0
        assert result.agent_trace == []

    def test_full_result(self):
        """Test result with all fields."""
        result = AdapterInvocationResult(
            tool_id="patch_generator",
            success=True,
            data={"patch": "...diff..."},
            execution_time_ms=250.5,
            tokens_used=1500,
            agent_trace=["Step 1", "Step 2", "Step 3"],
        )
        assert result.execution_time_ms == 250.5
        assert result.tokens_used == 1500
        assert len(result.agent_trace) == 3


# =============================================================================
# BaseAgentAdapter Tests
# =============================================================================


class TestBaseAgentAdapter:
    """Tests for BaseAgentAdapter abstract class."""

    def test_tool_id_property(self):
        """Test tool_id property returns definition tool_id."""
        definition = AuraToolDefinition(
            tool_id="test_adapter",
            name="Test",
            description="Test",
            category=AuraAgentCategory.TESTING,
            capabilities=[],
        )

        # Create a concrete implementation for testing
        class ConcreteAdapter(BaseAgentAdapter):
            async def invoke(self, params):
                return AdapterInvocationResult(tool_id=self.tool_id, success=True)

        adapter = ConcreteAdapter(definition)
        assert adapter.tool_id == "test_adapter"

    def test_describe_returns_mcp_format(self):
        """Test describe returns MCP-compatible format."""
        definition = AuraToolDefinition(
            tool_id="describe_test",
            name="Describe Test Tool",
            description="A tool for testing describe",
            category=AuraAgentCategory.TESTING,
            capabilities=[],
            input_schema={"param": "string"},
            output_schema={"result": "object"},
        )

        class ConcreteAdapter(BaseAgentAdapter):
            async def invoke(self, params):
                return AdapterInvocationResult(tool_id=self.tool_id, success=True)

        adapter = ConcreteAdapter(definition)
        desc = adapter.describe()

        assert desc["name"] == "Describe Test Tool"
        assert desc["description"] == "A tool for testing describe"
        assert desc["inputSchema"] == {"param": "string"}
        assert desc["outputSchema"] == {"result": "object"}

    def test_get_metrics_initial(self):
        """Test get_metrics returns zeroed metrics initially."""
        definition = AuraToolDefinition(
            tool_id="metrics_test",
            name="Metrics Test",
            description="Test",
            category=AuraAgentCategory.TESTING,
            capabilities=[],
        )

        class ConcreteAdapter(BaseAgentAdapter):
            async def invoke(self, params):
                return AdapterInvocationResult(tool_id=self.tool_id, success=True)

        adapter = ConcreteAdapter(definition)
        metrics = adapter.get_metrics()

        assert metrics["tool_id"] == "metrics_test"
        assert metrics["invocation_count"] == 0
        assert metrics["total_execution_time_ms"] == 0.0
        assert metrics["avg_execution_time_ms"] == 0.0


# =============================================================================
# SecurityScannerAdapter Tests
# =============================================================================


class TestSecurityScannerAdapter:
    """Tests for SecurityScannerAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="security_scanner",
            name="Security Scanner",
            description="Scan for vulnerabilities",
            category=AuraAgentCategory.SECURITY,
            capabilities=[AgentCapability.VULNERABILITY_DETECTION],
        )
        self.adapter = SecurityScannerAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful security scan invocation."""
        result = await self.adapter.invoke(
            {
                "repository": "org/repo",
                "branch": "main",
                "scan_type": "full",
            }
        )

        assert result.success is True
        assert result.tool_id == "security_scanner"
        assert "vulnerabilities_found" in result.data
        assert "severity_breakdown" in result.data
        assert "recommendations" in result.data
        assert result.execution_time_ms > 0
        assert result.tokens_used > 0

    @pytest.mark.asyncio
    async def test_invoke_increments_count(self):
        """Test that invocation increments counter."""
        assert self.adapter._invocation_count == 0

        await self.adapter.invoke({"repository": "test"})
        assert self.adapter._invocation_count == 1

        await self.adapter.invoke({"repository": "test"})
        assert self.adapter._invocation_count == 2

    @pytest.mark.asyncio
    async def test_invoke_with_defaults(self):
        """Test invocation with default parameters."""
        result = await self.adapter.invoke({})

        assert result.success is True
        assert result.data["repository"] == ""
        assert result.data["branch"] == "main"
        assert result.data["scan_type"] == "full"


# =============================================================================
# CodeReviewerAdapter Tests
# =============================================================================


class TestCodeReviewerAdapter:
    """Tests for CodeReviewerAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="code_reviewer",
            name="Code Reviewer",
            description="Review code",
            category=AuraAgentCategory.CODE_ANALYSIS,
            capabilities=[AgentCapability.CODE_REVIEW],
        )
        self.adapter = CodeReviewerAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful code review invocation."""
        result = await self.adapter.invoke(
            {
                "file_path": "src/main.py",
                "review_type": "comprehensive",
            }
        )

        assert result.success is True
        assert "issues_found" in result.data
        assert "categories" in result.data
        assert "suggestions" in result.data
        assert "overall_score" in result.data

    @pytest.mark.asyncio
    async def test_invoke_returns_suggestions(self):
        """Test that review returns suggestions with line numbers."""
        result = await self.adapter.invoke({"file_path": "test.py"})

        assert result.success is True
        suggestions = result.data["suggestions"]
        assert len(suggestions) > 0
        assert "line" in suggestions[0]
        assert "severity" in suggestions[0]
        assert "message" in suggestions[0]


# =============================================================================
# PatchGeneratorAdapter Tests
# =============================================================================


class TestPatchGeneratorAdapter:
    """Tests for PatchGeneratorAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="patch_generator",
            name="Patch Generator",
            description="Generate patches",
            category=AuraAgentCategory.SECURITY,
            capabilities=[AgentCapability.PATCH_GENERATION],
        )
        self.adapter = PatchGeneratorAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful patch generation."""
        result = await self.adapter.invoke(
            {
                "vulnerability_id": "CVE-2024-1234",
                "file_path": "src/vulnerable.py",
                "strategy": "minimal",
            }
        )

        assert result.success is True
        assert result.data["patch_generated"] is True
        assert "diff" in result.data
        assert "confidence" in result.data
        assert result.data["requires_review"] is True

    @pytest.mark.asyncio
    async def test_invoke_returns_diff(self):
        """Test that patch includes diff format."""
        result = await self.adapter.invoke(
            {
                "vulnerability_id": "VULN-001",
                "file_path": "app.py",
            }
        )

        assert "---" in result.data["diff"]
        assert "+++" in result.data["diff"]


# =============================================================================
# ArchitectureAnalyzerAdapter Tests
# =============================================================================


class TestArchitectureAnalyzerAdapter:
    """Tests for ArchitectureAnalyzerAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="architecture_analyzer",
            name="Architecture Analyzer",
            description="Analyze architecture",
            category=AuraAgentCategory.CODE_ANALYSIS,
            capabilities=[AgentCapability.ARCHITECTURE_ANALYSIS],
        )
        self.adapter = ArchitectureAnalyzerAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful architecture analysis."""
        result = await self.adapter.invoke(
            {
                "repository": "org/microservices",
                "depth": "deep",
            }
        )

        assert result.success is True
        assert "architecture_type" in result.data
        assert "components" in result.data
        assert "patterns_detected" in result.data
        assert "coupling_score" in result.data
        assert "cohesion_score" in result.data

    @pytest.mark.asyncio
    async def test_invoke_returns_components(self):
        """Test that analysis returns component details."""
        result = await self.adapter.invoke({"repository": "test"})

        components = result.data["components"]
        assert len(components) > 0
        assert "name" in components[0]
        assert "type" in components[0]
        assert "dependencies" in components[0]


# =============================================================================
# ThreatIntelligenceAdapter Tests
# =============================================================================


class TestThreatIntelligenceAdapter:
    """Tests for ThreatIntelligenceAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="threat_intelligence",
            name="Threat Intelligence",
            description="Threat assessment",
            category=AuraAgentCategory.INTELLIGENCE,
            capabilities=[AgentCapability.THREAT_ASSESSMENT],
        )
        self.adapter = ThreatIntelligenceAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful threat intelligence gathering."""
        result = await self.adapter.invoke(
            {
                "target": "production-api",
                "type": "comprehensive",
            }
        )

        assert result.success is True
        assert "threat_level" in result.data
        assert "active_threats" in result.data
        assert "exposure_score" in result.data
        assert "recommendations" in result.data

    @pytest.mark.asyncio
    async def test_invoke_returns_threat_details(self):
        """Test that threats include CVE information."""
        result = await self.adapter.invoke({"target": "test"})

        threats = result.data["active_threats"]
        if len(threats) > 0:
            assert "cve" in threats[0]
            assert "severity" in threats[0]


# =============================================================================
# DocumentationGeneratorAdapter Tests
# =============================================================================


class TestDocumentationGeneratorAdapter:
    """Tests for DocumentationGeneratorAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.definition = AuraToolDefinition(
            tool_id="documentation_generator",
            name="Documentation Generator",
            description="Generate docs",
            category=AuraAgentCategory.DOCUMENTATION,
            capabilities=[AgentCapability.DOCUMENTATION_GENERATION],
        )
        self.adapter = DocumentationGeneratorAdapter(self.definition)

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """Test successful documentation generation."""
        result = await self.adapter.invoke(
            {
                "target": "src/api/endpoints.py",
                "doc_type": "api",
            }
        )

        assert result.success is True
        assert result.data["generated"] is True
        assert "sections" in result.data
        assert "word_count" in result.data
        assert "format" in result.data

    @pytest.mark.asyncio
    async def test_invoke_returns_content_preview(self):
        """Test that docs include content preview."""
        result = await self.adapter.invoke({"target": "module.py"})

        assert "content_preview" in result.data
        assert result.data["format"] == "markdown"


# =============================================================================
# AuraToolAdapter Factory Tests
# =============================================================================


class TestAuraToolAdapter:
    """Tests for AuraToolAdapter factory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = AuraToolAdapter()

    def test_initialization(self):
        """Test adapter factory initialization."""
        assert self.adapter is not None
        assert len(self.adapter._adapters) > 0

    def test_list_tools_returns_definitions(self):
        """Test listing all available tools."""
        tools = self.adapter.list_tools()

        assert len(tools) > 0
        assert all(isinstance(t, AuraToolDefinition) for t in tools)

    def test_get_tool_definition_exists(self):
        """Test getting existing tool definition."""
        definition = self.adapter.get_tool_definition("security_scanner")

        assert definition is not None
        assert definition.tool_id == "security_scanner"

    def test_get_tool_definition_not_exists(self):
        """Test getting non-existent tool definition."""
        definition = self.adapter.get_tool_definition("nonexistent")

        assert definition is None

    def test_describe_tool_exists(self):
        """Test describing an existing tool."""
        desc = self.adapter.describe_tool("code_reviewer")

        assert desc is not None
        assert "name" in desc
        assert "description" in desc
        assert "inputSchema" in desc

    def test_describe_tool_not_exists(self):
        """Test describing a non-existent tool."""
        desc = self.adapter.describe_tool("nonexistent")

        assert desc is None

    @pytest.mark.asyncio
    async def test_invoke_existing_tool(self):
        """Test invoking an existing tool."""
        result = await self.adapter.invoke(
            "security_scanner",
            {"repository": "test/repo"},
        )

        assert result.success is True
        assert result.tool_id == "security_scanner"

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self):
        """Test invoking a non-existent tool."""
        result = await self.adapter.invoke(
            "nonexistent_tool",
            {},
        )

        assert result.success is False
        assert "Unknown Aura tool" in result.error

    def test_get_metrics_all_adapters(self):
        """Test getting metrics for all adapters."""
        metrics = self.adapter.get_metrics()

        assert len(metrics) > 0
        for tool_id, tool_metrics in metrics.items():
            assert "invocation_count" in tool_metrics
            assert "total_execution_time_ms" in tool_metrics


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_aura_tools_returns_list(self):
        """Test get_aura_tools returns list of definitions."""
        tools = get_aura_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0
        assert all(isinstance(t, AuraToolDefinition) for t in tools)

    def test_get_aura_tools_contains_expected(self):
        """Test that expected tools are present."""
        tools = get_aura_tools()
        tool_ids = [t.tool_id for t in tools]

        assert "security_scanner" in tool_ids
        assert "code_reviewer" in tool_ids
        assert "patch_generator" in tool_ids

    def test_get_aura_tool_ids_returns_list(self):
        """Test get_aura_tool_ids returns list of strings."""
        ids = get_aura_tool_ids()

        assert isinstance(ids, list)
        assert len(ids) > 0
        assert all(isinstance(i, str) for i in ids)

    def test_get_aura_tool_ids_matches_tools(self):
        """Test that tool IDs match tool definitions."""
        ids = get_aura_tool_ids()
        tools = get_aura_tools()
        tool_ids = [t.tool_id for t in tools]

        assert set(ids) == set(tool_ids)


# =============================================================================
# Integration Tests
# =============================================================================


class TestMCPToolAdaptersIntegration:
    """Integration tests for MCP tool adapters."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = AuraToolAdapter()

    @pytest.mark.asyncio
    async def test_full_workflow_scan_then_patch(self):
        """Test complete workflow: scan then generate patch."""
        # First, run a security scan
        scan_result = await self.adapter.invoke(
            "security_scanner",
            {"repository": "org/vulnerable-app", "scan_type": "full"},
        )
        assert scan_result.success is True
        assert scan_result.data["vulnerabilities_found"] > 0

        # Then generate a patch
        patch_result = await self.adapter.invoke(
            "patch_generator",
            {
                "vulnerability_id": "CVE-2024-1234",
                "file_path": "src/auth.py",
                "strategy": "defensive",
            },
        )
        assert patch_result.success is True
        assert patch_result.data["patch_generated"] is True

    @pytest.mark.asyncio
    async def test_metrics_accumulate(self):
        """Test that metrics accumulate across invocations."""
        # Get initial metrics
        initial = self.adapter.get_metrics()["security_scanner"]["invocation_count"]

        # Run multiple invocations
        await self.adapter.invoke("security_scanner", {"repository": "test1"})
        await self.adapter.invoke("security_scanner", {"repository": "test2"})
        await self.adapter.invoke("security_scanner", {"repository": "test3"})

        # Check metrics increased
        final = self.adapter.get_metrics()["security_scanner"]["invocation_count"]
        assert final == initial + 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
