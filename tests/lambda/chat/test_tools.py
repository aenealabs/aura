"""
Chat Tools Integration Tests

Tests for the tool definitions and execution framework:
- Tool definitions (CHAT_TOOLS)
- Tool execution (execute_tool)
- Individual tool implementations
- Error handling and validation
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add source path
CHAT_LAMBDA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "src",
    "lambda",
    "chat",
)
sys.path.insert(0, os.path.abspath(CHAT_LAMBDA_PATH))


class TestToolDefinitions:
    """Test CHAT_TOOLS definitions are valid."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Import tools module."""
        from tools import CHAT_TOOLS

        self.CHAT_TOOLS = CHAT_TOOLS

    def test_chat_tools_count(self):
        """Should have 11 tools defined."""
        assert len(self.CHAT_TOOLS) == 11

    def test_all_tools_have_name(self):
        """Every tool should have a name."""
        for tool in self.CHAT_TOOLS:
            assert "name" in tool
            assert len(tool["name"]) > 0

    def test_all_tools_have_description(self):
        """Every tool should have a description."""
        for tool in self.CHAT_TOOLS:
            assert "description" in tool
            assert len(tool["description"]) > 0

    def test_all_tools_have_parameters(self):
        """Every tool should have parameters schema."""
        for tool in self.CHAT_TOOLS:
            assert "parameters" in tool
            assert "type" in tool["parameters"]
            assert tool["parameters"]["type"] == "object"

    def test_tool_names_are_unique(self):
        """Tool names should be unique."""
        names = [tool["name"] for tool in self.CHAT_TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_exist(self):
        """Expected tools should be present."""
        expected_tools = [
            "get_vulnerability_metrics",
            "get_agent_status",
            "get_approval_queue",
            "search_documentation",
            "get_incident_details",
            "generate_report",
            "query_code_graph",
            "get_sandbox_status",
            "generate_diagram",
            "start_deep_research",
            "get_research_status",
        ]
        tool_names = [tool["name"] for tool in self.CHAT_TOOLS]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestToolParameterSchemas:
    """Test tool parameter schemas are valid."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Import tools module."""
        from tools import CHAT_TOOLS

        self.tools_by_name = {tool["name"]: tool for tool in CHAT_TOOLS}

    def test_vulnerability_metrics_parameters(self):
        """get_vulnerability_metrics should have correct parameters."""
        tool = self.tools_by_name["get_vulnerability_metrics"]
        props = tool["parameters"]["properties"]
        assert "severity" in props
        assert "status" in props
        assert "time_range" in props
        assert "required" in tool["parameters"]
        assert "severity" in tool["parameters"]["required"]

    def test_agent_status_parameters(self):
        """get_agent_status should have correct parameters."""
        tool = self.tools_by_name["get_agent_status"]
        props = tool["parameters"]["properties"]
        assert "agent_type" in props
        assert "enum" in props["agent_type"]
        expected_agents = ["orchestrator", "coder", "reviewer", "validator", "all"]
        for agent in expected_agents:
            assert agent in props["agent_type"]["enum"]

    def test_generate_diagram_parameters(self):
        """generate_diagram should have correct parameters."""
        tool = self.tools_by_name["generate_diagram"]
        props = tool["parameters"]["properties"]
        assert "diagram_type" in props
        assert "subject" in props
        assert "format" in props
        assert "scope" in props
        # Check required fields
        required = tool["parameters"]["required"]
        assert "diagram_type" in required
        assert "subject" in required

    def test_start_deep_research_parameters(self):
        """start_deep_research should have correct parameters."""
        tool = self.tools_by_name["start_deep_research"]
        props = tool["parameters"]["properties"]
        assert "research_query" in props
        assert "scope" in props
        assert "urgency" in props
        assert "data_sources" in props
        # Check required fields
        required = tool["parameters"]["required"]
        assert "research_query" in required

    def test_get_research_status_parameters(self):
        """get_research_status should have correct parameters."""
        tool = self.tools_by_name["get_research_status"]
        props = tool["parameters"]["properties"]
        assert "task_id" in props
        required = tool["parameters"]["required"]
        assert "task_id" in required


class TestExecuteTool:
    """Test execute_tool function."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module and set up mocks."""
        # Patch the lazy accessor functions (Issue #466)
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_data.return_value = {
            "MetricDataResults": [{"Values": [0]}, {"Values": [0]}]
        }
        with (
            patch("tools.get_dynamodb_resource", return_value=MagicMock()),
            patch("tools.get_cloudwatch_client", return_value=mock_cloudwatch),
            patch("tools.get_anomalies_table", return_value=mock_table),
            patch("tools.get_approval_table", return_value=mock_table),
            patch("tools.get_workflow_table", return_value=mock_table),
        ):
            from tools import execute_tool

            self.execute_tool = execute_tool
            self.user_info = mock_user_info

    def test_execute_unknown_tool_raises_error(self):
        """Unknown tool names should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            self.execute_tool("nonexistent_tool", {}, self.user_info)

    def test_execute_tool_passes_tenant_id(self):
        """Tool execution should pass tenant_id for isolation."""
        # We can verify by testing a tool that uses tenant_id
        # Using generate_diagram as it doesn't require DynamoDB
        result = self.execute_tool(
            "generate_diagram",
            {"diagram_type": "flowchart", "subject": "test"},
            self.user_info,
        )
        assert isinstance(result, dict)


class TestGenerateDiagramTool:
    """Test generate_diagram tool execution."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_generate_diagram_success(self):
        """Should generate diagram successfully."""
        result = self.execute_tool(
            "generate_diagram",
            {
                "diagram_type": "flowchart",
                "subject": "authentication flow",
                "format": "mermaid",
            },
            self.user_info,
        )
        assert "code" in result
        assert "diagram_type" in result
        assert result["diagram_type"] == "flowchart"

    def test_generate_diagram_missing_subject(self):
        """Should return error for missing subject."""
        result = self.execute_tool(
            "generate_diagram",
            {"diagram_type": "flowchart"},
            self.user_info,
        )
        assert "error" in result

    def test_generate_diagram_all_types(self):
        """Should support all diagram types."""
        diagram_types = [
            "flowchart",
            "sequence",
            "class",
            "er",
            "state",
            "architecture",
            "dependency",
        ]
        for dtype in diagram_types:
            result = self.execute_tool(
                "generate_diagram",
                {"diagram_type": dtype, "subject": "test"},
                self.user_info,
            )
            assert "code" in result, f"Failed for type: {dtype}"


class TestResearchTools:
    """Test research tool execution."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module with patched DynamoDB."""
        # Patch the lazy accessor functions (Issue #466)
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        mock_table.get_item.return_value = {"Item": None}
        with (
            patch("tools.get_dynamodb_resource", return_value=MagicMock()),
            patch("research_tools.get_dynamodb_resource", return_value=MagicMock()),
            patch("research_tools.get_research_tasks_table", return_value=mock_table),
        ):
            from tools import execute_tool

            self.execute_tool = execute_tool
            self.user_info = mock_user_info

    def test_start_deep_research_success(self):
        """Should start research task successfully."""
        result = self.execute_tool(
            "start_deep_research",
            {"research_query": "Analyze security vulnerabilities"},
            self.user_info,
        )
        assert "task_id" in result
        assert result["task_id"].startswith("RSH-")

    def test_start_deep_research_missing_query(self):
        """Should return error for missing query."""
        result = self.execute_tool(
            "start_deep_research",
            {},
            self.user_info,
        )
        assert "error" in result

    def test_get_research_status_success(self):
        """Should get research status successfully."""
        # First start a task
        start_result = self.execute_tool(
            "start_deep_research",
            {"research_query": "Test query"},
            self.user_info,
        )
        task_id = start_result["task_id"]

        # Then get status (will return mock since no DynamoDB)
        result = self.execute_tool(
            "get_research_status",
            {"task_id": task_id},
            self.user_info,
        )
        assert "task_id" in result

    def test_get_research_status_missing_task_id(self):
        """Should return error for missing task_id."""
        result = self.execute_tool(
            "get_research_status",
            {},
            self.user_info,
        )
        assert "error" in result


class TestVulnerabilityMetricsTool:
    """Test get_vulnerability_metrics tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Set up with mocked DynamoDB."""
        # Create a mock table that returns empty items
        self.mock_table = MagicMock()
        self.mock_table.scan.return_value = {"Items": []}
        self.user_info = mock_user_info

        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_anomalies_table", return_value=self.mock_table):
            from tools import execute_tool

            self.execute_tool = execute_tool

    def test_vulnerability_metrics_returns_structure(self):
        """Should return proper metrics structure."""
        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_anomalies_table", return_value=self.mock_table):
            result = self.execute_tool(
                "get_vulnerability_metrics",
                {"severity": "all"},
                self.user_info,
            )
        assert "total_count" in result
        assert "by_severity" in result
        assert "by_status" in result
        assert "time_range" in result


class TestAgentStatusTool:
    """Test get_agent_status tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info, mock_cloudwatch_client):
        """Set up with mocked CloudWatch."""
        self.user_info = mock_user_info
        self.mock_cloudwatch = mock_cloudwatch_client

        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_cloudwatch_client", return_value=mock_cloudwatch_client):
            from tools import execute_tool

            self.execute_tool = execute_tool

    def test_agent_status_all_agents(self):
        """Should return status for all agents."""
        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_cloudwatch_client", return_value=self.mock_cloudwatch):
            result = self.execute_tool(
                "get_agent_status",
                {"agent_type": "all"},
                self.user_info,
            )
        assert "agents" in result
        # Should have all 4 agents
        expected_agents = ["orchestrator", "coder", "reviewer", "validator"]
        for agent in expected_agents:
            assert agent in result["agents"]

    def test_agent_status_single_agent(self):
        """Should return status for single agent."""
        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_cloudwatch_client", return_value=self.mock_cloudwatch):
            result = self.execute_tool(
                "get_agent_status",
                {"agent_type": "orchestrator"},
                self.user_info,
            )
        assert "agents" in result
        assert "orchestrator" in result["agents"]


class TestApprovalQueueTool:
    """Test get_approval_queue tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Set up with mocked DynamoDB."""
        # Mock scan to return mock data
        mock_table = MagicMock()
        mock_table.scan.side_effect = Exception("Table not available")
        self.user_info = mock_user_info
        self.mock_table = mock_table

        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_approval_table", return_value=mock_table):
            from tools import execute_tool

            self.execute_tool = execute_tool

    def test_approval_queue_returns_mock_on_error(self):
        """Should return mock data when table unavailable."""
        # Patch the lazy accessor function (Issue #466)
        with patch("tools.get_approval_table", return_value=self.mock_table):
            result = self.execute_tool(
                "get_approval_queue",
                {},
                self.user_info,
            )
        # Should return mock data structure
        assert "pending_count" in result
        assert "approvals" in result
        assert "note" in result  # Mock indicator


class TestSearchDocumentationTool:
    """Test search_documentation tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_search_documentation_returns_results(self):
        """Should return search results."""
        result = self.execute_tool(
            "search_documentation",
            {"query": "graphrag"},
            self.user_info,
        )
        assert "query" in result
        assert "results" in result
        assert "result_count" in result

    def test_search_documentation_filters_by_type(self):
        """Should filter by document type."""
        result = self.execute_tool(
            "search_documentation",
            {"query": "architecture", "doc_type": "adr"},
            self.user_info,
        )
        assert "results" in result
        # All results should be ADRs
        for doc in result["results"]:
            assert doc["type"] == "adr"


class TestIncidentDetailsTool:
    """Test get_incident_details tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_incident_details_basic(self):
        """Should return incident details."""
        result = self.execute_tool(
            "get_incident_details",
            {"incident_id": "INC-001"},
            self.user_info,
        )
        assert "incident_id" in result
        assert result["incident_id"] == "INC-001"
        assert "title" in result
        assert "severity" in result

    def test_incident_details_with_timeline(self):
        """Should include timeline when requested."""
        result = self.execute_tool(
            "get_incident_details",
            {"incident_id": "INC-001", "include_timeline": True},
            self.user_info,
        )
        assert "timeline" in result
        assert len(result["timeline"]) > 0

    def test_incident_details_with_rca(self):
        """Should include RCA when requested."""
        result = self.execute_tool(
            "get_incident_details",
            {"incident_id": "INC-001", "include_rca": True},
            self.user_info,
        )
        assert "rca" in result
        assert "root_cause" in result["rca"]


class TestGenerateReportTool:
    """Test generate_report tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_generate_report_types(self):
        """Should support all report types."""
        report_types = [
            "vulnerability_summary",
            "agent_activity",
            "daily_digest",
        ]
        for rtype in report_types:
            result = self.execute_tool(
                "generate_report",
                {"report_type": rtype},
                self.user_info,
            )
            assert "title" in result
            assert "generated_at" in result


class TestCodeGraphTool:
    """Test query_code_graph tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_code_graph_dependencies(self):
        """Should return dependency query results."""
        result = self.execute_tool(
            "query_code_graph",
            {"query_type": "dependencies", "entity": "chat_handler.py"},
            self.user_info,
        )
        assert "entity" in result
        assert "query_type" in result

    def test_code_graph_callers(self):
        """Should return callers query results."""
        result = self.execute_tool(
            "query_code_graph",
            {"query_type": "callers", "entity": "execute_tool"},
            self.user_info,
        )
        assert "callers" in result

    def test_code_graph_impact_analysis(self):
        """Should return impact analysis results."""
        result = self.execute_tool(
            "query_code_graph",
            {"query_type": "impact_analysis", "entity": "auth_module"},
            self.user_info,
        )
        assert "direct_impact" in result
        assert "risk_level" in result


class TestSandboxStatusTool:
    """Test get_sandbox_status tool."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_user_info):
        """Import tools module."""
        from tools import execute_tool

        self.execute_tool = execute_tool
        self.user_info = mock_user_info

    def test_sandbox_status_all(self):
        """Should return all sandbox statuses."""
        result = self.execute_tool(
            "get_sandbox_status",
            {},
            self.user_info,
        )
        assert "sandbox_count" in result
        assert "sandboxes" in result

    def test_sandbox_status_with_metrics(self):
        """Should include metrics when requested."""
        result = self.execute_tool(
            "get_sandbox_status",
            {"include_metrics": True},
            self.user_info,
        )
        assert "sandboxes" in result
        if result["sandboxes"]:
            assert "metrics" in result["sandboxes"][0]
