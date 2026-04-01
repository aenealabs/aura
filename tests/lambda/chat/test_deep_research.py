"""
Phase 3: Deep Research Service Tests

Tests for the async research task service:
- DeepResearchService class
- ResearchTask dataclass
- Task lifecycle (create, update, complete, fail)
- Tool function interfaces
- Mock data generation
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

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


# All tests need AWS mocked
# Skip all tests - mypy_boto3_dynamodb type stubs not installed in test environment
pytestmark = [
    pytest.mark.usefixtures("aws_credentials"),
    pytest.mark.skip(
        reason="mypy_boto3_dynamodb type stubs not installed - see docs/reference/KNOWN_ISSUES.md"
    ),
]


class TestResearchEnums:
    """Test research-related enumerations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import research tools module."""
        from research_tools import ResearchScope, ResearchStatus, ResearchUrgency

        self.ResearchStatus = ResearchStatus
        self.ResearchScope = ResearchScope
        self.ResearchUrgency = ResearchUrgency

    def test_research_status_values(self):
        """ResearchStatus enum should have expected values."""
        expected = ["pending", "in_progress", "completed", "failed", "cancelled"]
        actual = [s.value for s in self.ResearchStatus]
        for status in expected:
            assert status in actual

    def test_research_scope_values(self):
        """ResearchScope enum should have expected values."""
        expected = ["repository", "codebase", "organization"]
        actual = [s.value for s in self.ResearchScope]
        for scope in expected:
            assert scope in actual

    def test_research_urgency_values(self):
        """ResearchUrgency enum should have expected values."""
        expected = ["standard", "urgent"]
        actual = [u.value for u in self.ResearchUrgency]
        for urgency in expected:
            assert urgency in actual


class TestResearchTask:
    """Test ResearchTask dataclass."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import research tools module."""
        from research_tools import ResearchStatus, ResearchTask

        self.ResearchTask = ResearchTask
        self.ResearchStatus = ResearchStatus

    def test_research_task_creation(self):
        """Should create ResearchTask with all fields."""
        now = datetime.now(timezone.utc).isoformat()
        task = self.ResearchTask(
            task_id="RSH-TEST123ABC",
            user_id="test-user",
            tenant_id="test-tenant",
            query="Analyze security vulnerabilities",
            scope="repository",
            urgency="standard",
            data_sources=["code_graph", "security_findings"],
            status="pending",
            progress=0,
            created_at=now,
            updated_at=now,
        )
        assert task.task_id == "RSH-TEST123ABC"
        assert task.user_id == "test-user"
        assert task.status == "pending"
        assert task.progress == 0

    def test_research_task_to_dynamodb_item(self):
        """Should convert to DynamoDB item format."""
        now = datetime.now(timezone.utc).isoformat()
        task = self.ResearchTask(
            task_id="RSH-TEST123ABC",
            user_id="test-user",
            tenant_id="test-tenant",
            query="Test query",
            scope="repository",
            urgency="standard",
            data_sources=["code_graph"],
            status="pending",
            progress=0,
            created_at=now,
            updated_at=now,
        )
        item = task.to_dynamodb_item()
        assert isinstance(item, dict)
        assert item["task_id"] == "RSH-TEST123ABC"
        assert item["user_id"] == "test-user"
        assert "result" not in item  # Should not include None values
        assert "error" not in item

    def test_research_task_from_dynamodb_item(self):
        """Should create from DynamoDB item."""
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "task_id": "RSH-TEST123ABC",
            "user_id": "test-user",
            "tenant_id": "test-tenant",
            "query": "Test query",
            "scope": "repository",
            "urgency": "standard",
            "data_sources": ["code_graph"],
            "status": "pending",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
        }
        task = self.ResearchTask.from_dynamodb_item(item)
        assert task.task_id == "RSH-TEST123ABC"
        assert task.data_sources == ["code_graph"]

    def test_research_task_with_result(self):
        """Should handle task with result data."""
        now = datetime.now(timezone.utc).isoformat()
        result_data = {"type": "security_analysis", "findings": []}
        task = self.ResearchTask(
            task_id="RSH-TEST123ABC",
            user_id="test-user",
            tenant_id="test-tenant",
            query="Security audit",
            scope="codebase",
            urgency="urgent",
            data_sources=["security_findings"],
            status="completed",
            progress=100,
            created_at=now,
            updated_at=now,
            result=result_data,
        )
        item = task.to_dynamodb_item()
        assert "result" in item
        assert item["result"]["type"] == "security_analysis"


class TestDeepResearchService:
    """Test DeepResearchService class."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars, mock_research_tasks_table):
        """Set up test environment."""
        # Patch DynamoDB before importing
        with patch("research_tools.dynamodb") as mock_dynamodb:
            mock_dynamodb.Table.return_value = mock_research_tasks_table["table"]

            from research_tools import DeepResearchService, ResearchStatus

            self.DeepResearchService = DeepResearchService
            self.ResearchStatus = ResearchStatus
            self.mock_table = mock_research_tasks_table["table"]
            self.service = DeepResearchService()
            self.service.table = self.mock_table

    def test_start_research_creates_task(self):
        """start_research should create a new task."""
        task = self.service.start_research(
            query="Analyze authentication module",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert task is not None
        assert task.task_id.startswith("RSH-")
        assert task.query == "Analyze authentication module"
        assert task.user_id == "test-user"

    def test_start_research_generates_unique_id(self):
        """Each task should have a unique ID."""
        task1 = self.service.start_research(
            query="Query 1",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        task2 = self.service.start_research(
            query="Query 2",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert task1.task_id != task2.task_id

    def test_start_research_with_custom_scope(self):
        """Should accept custom scope parameter."""
        task = self.service.start_research(
            query="Organization-wide analysis",
            user_id="test-user",
            tenant_id="test-tenant",
            scope="organization",
        )
        assert task.scope == "organization"

    def test_start_research_with_custom_urgency(self):
        """Should accept custom urgency parameter."""
        task = self.service.start_research(
            query="Urgent analysis",
            user_id="test-user",
            tenant_id="test-tenant",
            urgency="urgent",
        )
        assert task.urgency == "urgent"

    def test_start_research_with_data_sources(self):
        """Should accept custom data sources."""
        sources = ["code_graph", "security_findings", "agent_logs"]
        task = self.service.start_research(
            query="Comprehensive analysis",
            user_id="test-user",
            tenant_id="test-tenant",
            data_sources=sources,
        )
        assert task.data_sources == sources

    def test_start_research_default_data_sources(self):
        """Should use default data sources if not specified."""
        task = self.service.start_research(
            query="Basic analysis",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert "code_graph" in task.data_sources
        assert "security_findings" in task.data_sources


class TestQuickResearchDetection:
    """Test quick research query detection."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            from research_tools import DeepResearchService

            self.service = DeepResearchService()
            self.service.table = None  # Force mock mode

    def test_status_query_is_quick(self):
        """Status queries should be detected as quick."""
        assert self.service._is_quick_research("What is the status of agents?")
        assert self.service._is_quick_research("Check agent STATUS")

    def test_count_query_is_quick(self):
        """Count queries should be detected as quick."""
        assert self.service._is_quick_research("Count the vulnerabilities")
        assert self.service._is_quick_research("What is the count of issues?")

    def test_list_query_is_quick(self):
        """List queries should be detected as quick."""
        assert self.service._is_quick_research("List all agents")
        assert self.service._is_quick_research("Show me the listing")

    def test_summary_query_is_quick(self):
        """Summary queries should be detected as quick."""
        assert self.service._is_quick_research("Give me a summary")
        assert self.service._is_quick_research("Quick summary please")

    def test_recent_query_is_quick(self):
        """Recent queries should be detected as quick."""
        assert self.service._is_quick_research("Show recent changes")
        assert self.service._is_quick_research("What are the recent deployments?")

    def test_complex_query_is_not_quick(self):
        """Complex queries should not be detected as quick."""
        assert not self.service._is_quick_research(
            "Analyze the architecture of the entire agent system"
        )
        assert not self.service._is_quick_research(
            "Compare authentication implementations across repositories"
        )


class TestResearchResultGeneration:
    """Test research result generation."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            from research_tools import DeepResearchService

            self.service = DeepResearchService()
            self.service.table = None

    def test_security_query_generates_security_result(self):
        """Security queries should generate security analysis results."""
        result = self.service._generate_research_result(
            query="security vulnerabilities in auth",
            scope="repository",
            data_sources=["security_findings"],
        )
        assert result["type"] == "security_analysis"
        assert "findings" in result
        assert "metrics" in result

    def test_architecture_query_generates_architecture_result(self):
        """Architecture queries should generate architecture analysis results."""
        result = self.service._generate_research_result(
            query="architecture design patterns",
            scope="codebase",
            data_sources=["code_graph"],
        )
        assert result["type"] == "architecture_analysis"
        assert "components" in result
        assert "recommendations" in result

    def test_quality_query_generates_quality_result(self):
        """Code quality queries should generate quality analysis results."""
        result = self.service._generate_research_result(
            query="code quality and technical debt",
            scope="repository",
            data_sources=["code_graph"],
        )
        assert result["type"] == "code_quality_analysis"
        assert "hotspots" in result
        assert "metrics" in result

    def test_generic_query_generates_comprehensive_result(self):
        """Generic queries should generate comprehensive results."""
        result = self.service._generate_research_result(
            query="general analysis of the codebase",
            scope="repository",
            data_sources=["code_graph"],
        )
        assert result["type"] == "comprehensive_analysis"
        assert "findings" in result

    def test_result_includes_data_sources(self):
        """Results should include data sources used."""
        sources = ["code_graph", "security_findings"]
        result = self.service._generate_research_result(
            query="any query",
            scope="repository",
            data_sources=sources,
        )
        assert result["data_sources_used"] == sources


class TestToolFunctions:
    """Test tool function interfaces."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            from research_tools import (
                get_research_service,
                get_research_status,
                start_deep_research,
            )

            self.start_deep_research = start_deep_research
            self.get_research_status = get_research_status
            self.get_research_service = get_research_service

    def test_start_deep_research_returns_dict(self):
        """start_deep_research should return a dictionary."""
        result = self.start_deep_research(
            query="Test research query",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert isinstance(result, dict)
        assert "task_id" in result
        assert "status" in result
        assert "message" in result

    def test_start_deep_research_includes_task_id(self):
        """Result should include task ID for tracking."""
        result = self.start_deep_research(
            query="Test query",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert result["task_id"].startswith("RSH-")

    def test_get_research_status_for_mock_task(self):
        """get_research_status should return task details."""
        # First create a task
        start_result = self.start_deep_research(
            query="Test query",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        task_id = start_result["task_id"]

        # Then get status (will return mock data since no DynamoDB)
        status_result = self.get_research_status(
            task_id=task_id,
            user_id="test-user",
        )
        assert isinstance(status_result, dict)
        assert "task_id" in status_result

    def test_get_research_status_not_found(self):
        """Should handle non-existent task gracefully."""
        # The service falls back to mock data, so we need to verify behavior
        result = self.get_research_status(
            task_id="RSH-NONEXISTENT",
            user_id="test-user",
        )
        # In mock mode, it returns a mock task
        assert isinstance(result, dict)


class TestMockTaskGeneration:
    """Test mock task generation for development."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            from research_tools import DeepResearchService, ResearchStatus

            self.service = DeepResearchService()
            self.service.table = None  # Force mock mode
            self.ResearchStatus = ResearchStatus

    def test_get_mock_task(self):
        """Should return a mock task for development."""
        task = self.service._get_mock_task("RSH-TEST123")
        assert task.task_id == "RSH-TEST123"
        assert task.status == self.ResearchStatus.COMPLETED.value
        assert task.result is not None

    def test_get_mock_task_list(self):
        """Should return a list of mock tasks."""
        tasks = self.service._get_mock_task_list()
        assert len(tasks) == 2
        assert tasks[0].task_id == "RSH-MOCK001"
        assert tasks[1].task_id == "RSH-MOCK002"

    def test_mock_task_list_has_varied_statuses(self):
        """Mock task list should have different statuses."""
        tasks = self.service._get_mock_task_list()
        statuses = {t.status for t in tasks}
        assert len(statuses) > 1  # Should have varied statuses


class TestServiceSingleton:
    """Test singleton pattern for research service."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            # Clear singleton before test
            import research_tools

            research_tools._research_service = None

            from research_tools import get_research_service

            self.get_research_service = get_research_service

    def test_singleton_returns_same_instance(self):
        """get_research_service should return same instance."""
        service1 = self.get_research_service()
        service2 = self.get_research_service()
        assert service1 is service2


class TestTaskTTL:
    """Test task TTL (time-to-live) functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up test environment."""
        with patch("research_tools.dynamodb"):
            from research_tools import DeepResearchService

            self.service = DeepResearchService()
            self.service.table = None

    def test_task_has_ttl(self):
        """New tasks should have TTL set."""
        task = self.service.start_research(
            query="Test query",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        assert task.ttl is not None

    def test_ttl_is_7_days_in_future(self):
        """TTL should be approximately 7 days from creation."""
        task = self.service.start_research(
            query="Test query",
            user_id="test-user",
            tenant_id="test-tenant",
        )
        now = datetime.now(timezone.utc)
        ttl_datetime = datetime.fromtimestamp(task.ttl)
        days_diff = (ttl_datetime - now).days
        assert 6 <= days_diff <= 7  # Allow for slight timing differences
