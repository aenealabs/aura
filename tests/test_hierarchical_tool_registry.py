"""
Tests for Hierarchical Tool Registry.

Covers ToolLevel enum, ToolDefinition dataclass, ToolSelectionContext dataclass,
and HierarchicalToolRegistry service for context-efficient tool presentation.
"""

import pytest

from src.services.hierarchical_tool_registry import (
    HierarchicalToolRegistry,
    ToolDefinition,
    ToolLevel,
    ToolSelectionContext,
)

# =============================================================================
# ToolLevel Enum Tests
# =============================================================================


class TestToolLevel:
    """Tests for ToolLevel enum."""

    def test_atomic_level(self):
        """Test atomic level value."""
        assert ToolLevel.ATOMIC.value == 1

    def test_domain_level(self):
        """Test domain level value."""
        assert ToolLevel.DOMAIN.value == 2

    def test_expert_level(self):
        """Test expert level value."""
        assert ToolLevel.EXPERT.value == 3

    def test_level_count(self):
        """Test that all 3 levels exist."""
        assert len(ToolLevel) == 3

    def test_level_ordering(self):
        """Test that levels are ordered correctly."""
        assert ToolLevel.ATOMIC.value < ToolLevel.DOMAIN.value < ToolLevel.EXPERT.value


# =============================================================================
# ToolDefinition Dataclass Tests
# =============================================================================


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_create_basic_tool(self):
        """Test creating a basic tool definition."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            level=ToolLevel.ATOMIC,
            input_schema={"param": "string"},
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.level == ToolLevel.ATOMIC
        assert tool.input_schema == {"param": "string"}

    def test_default_values(self):
        """Test default values for optional fields."""
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            level=ToolLevel.ATOMIC,
            input_schema={},
        )
        assert tool.domain is None
        assert tool.handler is None
        assert tool.requires_hitl is False
        assert tool.example_usage is None
        assert tool.output_schema is None
        assert tool.tags == []

    def test_full_tool(self):
        """Test tool with all fields populated."""
        tool = ToolDefinition(
            name="vuln_scan",
            description="Scan for vulnerabilities",
            level=ToolLevel.DOMAIN,
            input_schema={"target": "string"},
            domain="security",
            requires_hitl=True,
            example_usage="vuln_scan(target='/app')",
            output_schema={"vulnerabilities": "array"},
            tags=["security", "scanning"],
        )
        assert tool.domain == "security"
        assert tool.requires_hitl is True
        assert tool.tags == ["security", "scanning"]

    def test_to_prompt_format_compact(self):
        """Test compact prompt format."""
        tool = ToolDefinition(
            name="file_read",
            description="Read contents of a file",
            level=ToolLevel.ATOMIC,
            input_schema={"path": "string"},
        )
        formatted = tool.to_prompt_format("compact")
        assert formatted == "- file_read: Read contents of a file"

    def test_to_prompt_format_compact_with_hitl(self):
        """Test compact format with HITL marker."""
        tool = ToolDefinition(
            name="run_command",
            description="Execute shell command",
            level=ToolLevel.ATOMIC,
            input_schema={"cmd": "string"},
            requires_hitl=True,
        )
        formatted = tool.to_prompt_format("compact")
        assert "[HITL]" in formatted
        assert formatted == "- run_command: Execute shell command [HITL]"

    def test_to_prompt_format_full(self):
        """Test full prompt format."""
        tool = ToolDefinition(
            name="scan_vuln",
            description="Scan for vulnerabilities",
            level=ToolLevel.DOMAIN,
            input_schema={"target": "string"},
            requires_hitl=True,
            example_usage="scan_vuln('/app')",
        )
        formatted = tool.to_prompt_format("full")
        assert "## scan_vuln" in formatted
        assert "Description: Scan for vulnerabilities" in formatted
        assert "Inputs:" in formatted
        assert "Requires: Human approval" in formatted
        assert "Example: scan_vuln('/app')" in formatted

    def test_to_prompt_format_full_without_hitl(self):
        """Test full format without HITL requirement."""
        tool = ToolDefinition(
            name="file_read",
            description="Read a file",
            level=ToolLevel.ATOMIC,
            input_schema={"path": "string"},
        )
        formatted = tool.to_prompt_format("full")
        assert "Human approval" not in formatted


# =============================================================================
# ToolSelectionContext Dataclass Tests
# =============================================================================


class TestToolSelectionContext:
    """Tests for ToolSelectionContext dataclass."""

    def test_create_empty_context(self):
        """Test creating empty context with defaults."""
        context = ToolSelectionContext()
        assert context.detected_domains == []
        assert context.task_complexity == "standard"
        assert context.agent_type is None
        assert context.max_tools is None

    def test_create_full_context(self):
        """Test creating context with all fields."""
        context = ToolSelectionContext(
            detected_domains=["security", "infrastructure"],
            task_complexity="complex",
            agent_type="security_agent",
            max_tools=25,
        )
        assert context.detected_domains == ["security", "infrastructure"]
        assert context.task_complexity == "complex"
        assert context.agent_type == "security_agent"
        assert context.max_tools == 25

    def test_context_mutable_domains(self):
        """Test that domains list is mutable."""
        context = ToolSelectionContext()
        context.detected_domains.append("security")
        assert "security" in context.detected_domains


# =============================================================================
# HierarchicalToolRegistry Initialization Tests
# =============================================================================


class TestHierarchicalToolRegistryInit:
    """Tests for HierarchicalToolRegistry initialization."""

    def test_initialization(self):
        """Test basic registry initialization."""
        registry = HierarchicalToolRegistry()
        assert registry is not None
        assert len(registry._tools) > 0

    def test_atomic_tools_registered(self):
        """Test that atomic tools are registered on init."""
        registry = HierarchicalToolRegistry()
        atomic_tools = [
            t for t in registry._tools.values() if t.level == ToolLevel.ATOMIC
        ]
        # Should have approximately 20 atomic tools
        assert len(atomic_tools) >= 15
        assert (
            len(atomic_tools) <= registry.MAX_ATOMIC_TOOLS + 5
        )  # Allow some flexibility

    def test_known_atomic_tools_exist(self):
        """Test that known atomic tools exist."""
        registry = HierarchicalToolRegistry()
        expected_tools = [
            "file_read",
            "file_write",
            "search_code",
            "run_command",
            "store_memory",
        ]
        for tool_name in expected_tools:
            assert tool_name in registry._tools, f"Missing atomic tool: {tool_name}"

    def test_max_tool_constants(self):
        """Test max tool constants are set."""
        assert HierarchicalToolRegistry.MAX_ATOMIC_TOOLS == 20
        assert HierarchicalToolRegistry.MAX_TOTAL_TOOLS == 30


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestToolRegistration:
    """Tests for tool registration methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_register_domain_tool(self):
        """Test registering a domain tool."""
        tool = ToolDefinition(
            name="vuln_scan",
            description="Scan for vulnerabilities",
            level=ToolLevel.ATOMIC,  # Will be changed to DOMAIN
            input_schema={"target": "string"},
        )
        self.registry.register_domain_tool(tool, "security")

        assert "vuln_scan" in self.registry._tools
        assert self.registry._tools["vuln_scan"].level == ToolLevel.DOMAIN
        assert self.registry._tools["vuln_scan"].domain == "security"
        assert "vuln_scan" in self.registry._domain_tools.get("security", [])

    def test_register_expert_tool(self):
        """Test registering an expert tool."""
        tool = ToolDefinition(
            name="pentest_suite",
            description="Full penetration testing suite",
            level=ToolLevel.ATOMIC,  # Will be changed to EXPERT
            input_schema={"target": "string", "scope": "array"},
        )
        self.registry.register_expert_tool(tool, "security")

        assert "pentest_suite" in self.registry._tools
        assert self.registry._tools["pentest_suite"].level == ToolLevel.EXPERT
        assert self.registry._tools["pentest_suite"].domain == "security"

    def test_register_multiple_domain_tools(self):
        """Test registering multiple tools in same domain."""
        tool1 = ToolDefinition(
            name="sec_tool_1",
            description="Security tool 1",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        tool2 = ToolDefinition(
            name="sec_tool_2",
            description="Security tool 2",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        self.registry.register_domain_tool(tool1, "security")
        self.registry.register_domain_tool(tool2, "security")

        assert len(self.registry._domain_tools["security"]) == 2

    def test_register_agent_tools(self):
        """Test registering tools for specific agent type."""
        self.registry.register_agent_tools(
            "security_agent",
            ["file_read", "search_code", "run_command"],
        )

        assert "security_agent" in self.registry._agent_tools
        assert len(self.registry._agent_tools["security_agent"]) == 3


# =============================================================================
# Tool Retrieval Tests
# =============================================================================


class TestToolRetrieval:
    """Tests for tool retrieval methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_get_tool_exists(self):
        """Test getting an existing tool."""
        tool = self.registry.get_tool("file_read")
        assert tool is not None
        assert tool.name == "file_read"

    def test_get_tool_not_exists(self):
        """Test getting a non-existent tool."""
        tool = self.registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_get_tools_for_empty_context(self):
        """Test getting tools with empty context returns atomic tools."""
        tools = self.registry.get_tools_for_context()
        assert len(tools) > 0
        # All should be atomic level
        for tool in tools:
            assert tool.level == ToolLevel.ATOMIC

    def test_get_tools_for_domain_context(self):
        """Test getting tools with domain context."""
        # First register a domain tool
        domain_tool = ToolDefinition(
            name="security_scan",
            description="Security scanner",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        self.registry.register_domain_tool(domain_tool, "security")

        context = ToolSelectionContext(detected_domains=["security"])
        tools = self.registry.get_tools_for_context(context)

        tool_names = [t.name for t in tools]
        assert "security_scan" in tool_names

    def test_get_tools_for_complex_context_includes_expert(self):
        """Test that complex tasks include expert tools."""
        # Register an expert tool
        expert_tool = ToolDefinition(
            name="full_pentest",
            description="Full penetration test",
            level=ToolLevel.EXPERT,
            input_schema={},
        )
        self.registry.register_expert_tool(expert_tool, "security")

        context = ToolSelectionContext(
            detected_domains=["security"],
            task_complexity="complex",
        )
        tools = self.registry.get_tools_for_context(context)

        tool_names = [t.name for t in tools]
        assert "full_pentest" in tool_names

    def test_get_tools_respects_max_tools_limit(self):
        """Test that tool limit is enforced."""
        # Register many domain tools
        for i in range(50):
            tool = ToolDefinition(
                name=f"domain_tool_{i}",
                description=f"Domain tool {i}",
                level=ToolLevel.DOMAIN,
                input_schema={},
            )
            self.registry.register_domain_tool(tool, "security")

        context = ToolSelectionContext(
            detected_domains=["security"],
            max_tools=25,
        )
        tools = self.registry.get_tools_for_context(context)

        assert len(tools) <= 25

    def test_get_tools_for_agent_context(self):
        """Test getting tools for specific agent type."""
        self.registry.register_agent_tools("test_agent", ["file_read", "search_code"])

        context = ToolSelectionContext(agent_type="test_agent")
        tools = self.registry.get_tools_for_context(context)

        tool_names = [t.name for t in tools]
        assert "file_read" in tool_names
        assert "search_code" in tool_names


# =============================================================================
# Domain Detection Tests
# =============================================================================


class TestDomainDetection:
    """Tests for domain detection from text."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_detect_security_domain(self):
        """Test detecting security domain."""
        domains = self.registry.detect_domains(
            "Check for SQL injection vulnerabilities"
        )
        assert "security" in domains

    def test_detect_infrastructure_domain(self):
        """Test detecting infrastructure domain."""
        domains = self.registry.detect_domains("Deploy to Kubernetes cluster")
        assert "infrastructure" in domains

    def test_detect_code_analysis_domain(self):
        """Test detecting code analysis domain."""
        domains = self.registry.detect_domains("Analyze code complexity and coverage")
        assert "code_analysis" in domains

    def test_detect_testing_domain(self):
        """Test detecting testing domain."""
        domains = self.registry.detect_domains("Write pytest unit tests")
        assert "testing" in domains

    def test_detect_documentation_domain(self):
        """Test detecting documentation domain."""
        domains = self.registry.detect_domains("Update the README and API docs")
        assert "documentation" in domains

    def test_detect_multiple_domains(self):
        """Test detecting multiple domains."""
        domains = self.registry.detect_domains(
            "Run security vulnerability scan and deploy to AWS"
        )
        assert "security" in domains
        assert "infrastructure" in domains

    def test_detect_no_domains(self):
        """Test text with no domain keywords."""
        domains = self.registry.detect_domains("Hello world")
        assert domains == []

    def test_domain_detection_case_insensitive(self):
        """Test that detection is case insensitive."""
        domains = self.registry.detect_domains("SECURITY VULNERABILITY CVE")
        assert "security" in domains


# =============================================================================
# Complexity Assessment Tests
# =============================================================================


class TestComplexityAssessment:
    """Tests for task complexity assessment."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_assess_simple_task(self):
        """Test assessing simple task."""
        complexity = self.registry.assess_complexity("Quick fix for this one file")
        assert complexity == "simple"

    def test_assess_complex_task(self):
        """Test assessing complex task."""
        complexity = self.registry.assess_complexity("Comprehensive security review")
        assert complexity == "complex"

    def test_assess_standard_task(self):
        """Test assessing standard task."""
        complexity = self.registry.assess_complexity(
            "Update the function to add logging"
        )
        assert complexity == "standard"

    def test_assess_penetration_test_complex(self):
        """Test that penetration test is complex."""
        complexity = self.registry.assess_complexity("Run a penetration test")
        assert complexity == "complex"

    def test_assess_full_audit_complex(self):
        """Test that full audit is complex."""
        complexity = self.registry.assess_complexity(
            "Perform a full audit of the system"
        )
        assert complexity == "complex"

    def test_assess_just_single_simple(self):
        """Test that 'just' indicates simple."""
        complexity = self.registry.assess_complexity("Just update this variable")
        assert complexity == "simple"


# =============================================================================
# Prompt Formatting Tests
# =============================================================================


class TestPromptFormatting:
    """Tests for tool prompt formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_format_empty_tools(self):
        """Test formatting empty tool list."""
        result = self.registry.format_tools_for_prompt([])
        assert result == "No tools available."

    def test_format_tools_compact(self):
        """Test compact formatting."""
        tools = [
            ToolDefinition(
                name="tool_a",
                description="Tool A description",
                level=ToolLevel.ATOMIC,
                input_schema={},
            ),
            ToolDefinition(
                name="tool_b",
                description="Tool B description",
                level=ToolLevel.ATOMIC,
                input_schema={},
            ),
        ]
        result = self.registry.format_tools_for_prompt(tools, "compact")
        assert "- tool_a: Tool A description" in result
        assert "- tool_b: Tool B description" in result

    def test_format_tools_full(self):
        """Test full formatting."""
        tools = [
            ToolDefinition(
                name="tool_x",
                description="Tool X",
                level=ToolLevel.DOMAIN,
                input_schema={"param": "string"},
            ),
        ]
        result = self.registry.format_tools_for_prompt(tools, "full")
        assert "## tool_x" in result
        assert "Description: Tool X" in result


# =============================================================================
# Domain and HITL Query Tests
# =============================================================================


class TestDomainAndHitlQueries:
    """Tests for domain and HITL queries."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_get_all_domains_empty(self):
        """Test getting domains when none registered."""
        # Fresh registry has no domain tools
        domains = self.registry.get_all_domains()
        assert domains == []

    def test_get_all_domains_with_tools(self):
        """Test getting domains after registering tools."""
        tool = ToolDefinition(
            name="sec_tool",
            description="Security tool",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        self.registry.register_domain_tool(tool, "security")

        domains = self.registry.get_all_domains()
        assert "security" in domains

    def test_get_tools_by_domain(self):
        """Test getting tools by domain."""
        tool = ToolDefinition(
            name="infra_tool",
            description="Infrastructure tool",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        self.registry.register_domain_tool(tool, "infrastructure")

        tools = self.registry.get_tools_by_domain("infrastructure")
        assert len(tools) == 1
        assert tools[0].name == "infra_tool"

    def test_get_tools_by_nonexistent_domain(self):
        """Test getting tools from nonexistent domain."""
        tools = self.registry.get_tools_by_domain("nonexistent")
        assert tools == []

    def test_get_tools_requiring_hitl(self):
        """Test getting tools that require HITL."""
        hitl_tools = self.registry.get_tools_requiring_hitl()
        # run_command requires HITL by default
        tool_names = [t.name for t in hitl_tools]
        assert "run_command" in tool_names

    def test_hitl_tools_all_require_hitl(self):
        """Test that all returned HITL tools actually require HITL."""
        hitl_tools = self.registry.get_tools_requiring_hitl()
        for tool in hitl_tools:
            assert tool.requires_hitl is True


# =============================================================================
# Registry Statistics Tests
# =============================================================================


class TestRegistryStats:
    """Tests for registry statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_get_registry_stats(self):
        """Test getting registry statistics."""
        stats = self.registry.get_registry_stats()

        assert "total_tools" in stats
        assert "atomic_tools" in stats
        assert "domain_tools" in stats
        assert "expert_tools" in stats
        assert "domains" in stats
        assert "hitl_required" in stats

    def test_stats_counts_are_valid(self):
        """Test that stats counts are valid numbers."""
        stats = self.registry.get_registry_stats()

        assert stats["total_tools"] > 0
        assert stats["atomic_tools"] > 0
        assert (
            stats["atomic_tools"] == stats["total_tools"]
        )  # Initially only atomic tools
        assert stats["domain_tools"] == 0
        assert stats["expert_tools"] == 0

    def test_stats_update_after_registration(self):
        """Test that stats update after registering tools."""
        initial_stats = self.registry.get_registry_stats()
        initial_total = initial_stats["total_tools"]

        tool = ToolDefinition(
            name="new_domain_tool",
            description="New domain tool",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        self.registry.register_domain_tool(tool, "security")

        new_stats = self.registry.get_registry_stats()
        assert new_stats["total_tools"] == initial_total + 1
        assert new_stats["domain_tools"] == 1


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_register_tool_overwrites_existing(self):
        """Test that registering a tool with same name overwrites."""
        tool1 = ToolDefinition(
            name="duplicate_tool",
            description="Original",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )
        tool2 = ToolDefinition(
            name="duplicate_tool",
            description="Replacement",
            level=ToolLevel.DOMAIN,
            input_schema={},
        )

        self.registry.register_domain_tool(tool1, "security")
        self.registry.register_domain_tool(tool2, "security")

        retrieved = self.registry.get_tool("duplicate_tool")
        assert retrieved.description == "Replacement"

    def test_empty_domain_detection_text(self):
        """Test domain detection with empty text."""
        domains = self.registry.detect_domains("")
        assert domains == []

    def test_complexity_assessment_empty_text(self):
        """Test complexity assessment with empty text."""
        complexity = self.registry.assess_complexity("")
        assert complexity == "standard"  # Default

    def test_max_tools_preserves_atomic(self):
        """Test that max_tools limit preserves atomic tools.

        By design, atomic tools are ALWAYS preserved, even if max_tools
        is lower than the number of atomic tools. This is intentional -
        atomic tools are considered essential.
        """
        # Register many domain tools
        for i in range(20):
            tool = ToolDefinition(
                name=f"domain_{i}",
                description=f"Domain tool {i}",
                level=ToolLevel.DOMAIN,
                input_schema={},
            )
            self.registry.register_domain_tool(tool, "test")

        # Count atomic tools first
        atomic_count = len(
            [t for t in self.registry._tools.values() if t.level == ToolLevel.ATOMIC]
        )

        context = ToolSelectionContext(
            detected_domains=["test"],
            max_tools=atomic_count + 5,  # Atomic + 5 domain tools
        )
        tools = self.registry.get_tools_for_context(context)

        # Should have all atomic tools plus limited domain tools
        atomic_in_result = len([t for t in tools if t.level == ToolLevel.ATOMIC])
        domain_in_result = len([t for t in tools if t.level == ToolLevel.DOMAIN])

        assert atomic_in_result == atomic_count  # All atomic preserved
        assert domain_in_result == 5  # Only 5 domain tools allowed


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = HierarchicalToolRegistry()

    def test_full_workflow_security_task(self):
        """Test full workflow for security task."""
        # Register security domain tools
        vuln_scan = ToolDefinition(
            name="vuln_scanner",
            description="Scan for vulnerabilities",
            level=ToolLevel.DOMAIN,
            input_schema={"target": "string"},
        )
        self.registry.register_domain_tool(vuln_scan, "security")

        # Analyze task
        task = "Check for SQL injection vulnerabilities in the login form"
        domains = self.registry.detect_domains(task)
        complexity = self.registry.assess_complexity(task)

        assert "security" in domains
        assert complexity == "standard"

        # Get tools for context
        context = ToolSelectionContext(
            detected_domains=domains,
            task_complexity=complexity,
        )
        tools = self.registry.get_tools_for_context(context)

        # Should include security tool
        tool_names = [t.name for t in tools]
        assert "vuln_scanner" in tool_names

        # Format for prompt
        formatted = self.registry.format_tools_for_prompt(tools, "compact")
        assert "vuln_scanner" in formatted

    def test_full_workflow_complex_infra_task(self):
        """Test full workflow for complex infrastructure task."""
        # Register infrastructure tools
        deploy = ToolDefinition(
            name="deploy_stack",
            description="Deploy CloudFormation stack",
            level=ToolLevel.DOMAIN,
            input_schema={"template": "string"},
            requires_hitl=True,
        )
        self.registry.register_domain_tool(deploy, "infrastructure")

        audit = ToolDefinition(
            name="infra_audit",
            description="Full infrastructure audit",
            level=ToolLevel.EXPERT,
            input_schema={"scope": "array"},
        )
        self.registry.register_expert_tool(audit, "infrastructure")

        # Analyze complex task
        task = "Comprehensive infrastructure audit and deploy to AWS"
        domains = self.registry.detect_domains(task)
        complexity = self.registry.assess_complexity(task)

        assert "infrastructure" in domains
        assert complexity == "complex"

        # Get tools - should include expert tools
        context = ToolSelectionContext(
            detected_domains=domains,
            task_complexity=complexity,
        )
        tools = self.registry.get_tools_for_context(context)

        tool_names = [t.name for t in tools]
        assert "deploy_stack" in tool_names
        assert "infra_audit" in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
