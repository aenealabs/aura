"""Unit tests for RuntimeIncidentAgent (ADR-025).

Tests cover:
- Incident context parsing (CloudWatch, PagerDuty, Datadog)
- Deployment correlation
- Code entity correlation with Neptune
- Git commit search in OpenSearch
- RCA hypothesis generation
- Mitigation plan generation
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.runtime_incident_agent import (
    CodeEntity,
    DeploymentEvent,
    GitCommit,
    IncidentContext,
    IncidentSeverity,
    IncidentSource,
    InvestigationResult,
    RCAHypothesis,
    RuntimeIncidentAgent,
)


@pytest.fixture
def mock_llm_client():
    """Mock BedrockLLMService."""
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value='{"hypothesis": "Recent deployment introduced a null pointer exception", "confidence": 85, "evidence": ["Error spike after deployment", "Stack trace shows NullPointerException"], "alternatives": ["Database connection timeout"]}'
    )
    return llm


@pytest.fixture
def mock_context_service():
    """Mock ContextRetrievalService."""
    context = AsyncMock()
    context.graph_store = AsyncMock()
    context.graph_store.get_entity_by_name = AsyncMock(
        return_value={
            "id": "func-123",
            "name": "handle_request",
            "file_path": "src/api/handlers.py",
            "line_number": 42,
        }
    )
    context.vector_store = AsyncMock()
    context.vector_store.semantic_search = AsyncMock(return_value=[])
    context.vector_store.search_commits = AsyncMock(
        return_value=[
            {
                "sha": "abc123",
                "message": "Fix null check in handler",
                "author": "dev@example.com",
                "timestamp": "2025-12-06T10:00:00Z",
            }
        ]
    )
    return context


@pytest.fixture
def mock_mcp_adapters():
    """Mock MCPToolAdapters."""
    mcp = MagicMock()
    mcp.is_enterprise_mode = MagicMock(return_value=True)
    mcp.datadog_query_traces = AsyncMock(
        return_value=[{"trace_id": "123", "error": "NullPointerException"}]
    )
    mcp.prometheus_query_range = AsyncMock(
        return_value={"data": {"result": [{"values": [[1638835200, "0.5"]]}]}}
    )
    return mcp


@pytest.fixture
def agent(mock_llm_client, mock_context_service, mock_mcp_adapters):
    """Create RuntimeIncidentAgent with mocked dependencies."""
    with patch("src.agents.runtime_incident_agent.boto3"):
        agent = RuntimeIncidentAgent(
            llm_client=mock_llm_client,
            context_service=mock_context_service,
            mcp_adapters=mock_mcp_adapters,
        )
        # Mock DynamoDB tables
        agent.deployments_table = MagicMock()
        agent.investigations_table = MagicMock()
        agent.cloudwatch_logs = AsyncMock()
        return agent


class TestIncidentContextParsing:
    """Test parsing of incident events from different sources."""

    def test_parse_cloudwatch_alarm(self, agent):
        """Test parsing CloudWatch alarm event."""
        detail = {
            "alarmName": "aura-api-high-cpu-dev",
            "newStateValue": "ALARM",
            "newStateReason": "CPU usage exceeded 80%",
            "stateChangeTime": "2025-12-06T10:30:00Z",
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {"name": "CPUUtilization"},
                            "stat": "Average",
                        }
                    }
                ]
            },
        }

        context = agent._parse_incident_context(IncidentSource.CLOUDWATCH.value, detail)

        assert context.alert_name == "aura-api-high-cpu-dev"
        assert context.affected_service == "aura-api"
        assert context.error_message == "CPU usage exceeded 80%"
        assert context.metric_name == "CPUUtilization"
        assert context.severity == IncidentSeverity.HIGH
        assert context.source == IncidentSource.CLOUDWATCH

    def test_parse_pagerduty_incident(self, agent):
        """Test parsing PagerDuty incident event."""
        detail = {
            "incident": {
                "title": "Database connection timeout",
                "urgency": "high",
                "service": {"name": "aura-api"},
                "body": {"details": "Connection pool exhausted"},
                "created_at": "2025-12-06T11:00:00Z",
            }
        }

        context = agent._parse_incident_context(IncidentSource.PAGERDUTY.value, detail)

        assert context.alert_name == "Database connection timeout"
        assert context.affected_service == "aura-api"
        assert context.error_message == "Connection pool exhausted"
        assert context.severity == IncidentSeverity.CRITICAL
        assert context.source == IncidentSource.PAGERDUTY

    def test_parse_datadog_alert(self, agent):
        """Test parsing Datadog alert event."""
        detail = {
            "title": "High error rate in API",
            "priority": "P2",
            "body": "Error rate > 5%",
            "tags": {"service": "aura-api"},
            "date": "2025-12-06T12:00:00Z",
        }

        context = agent._parse_incident_context(IncidentSource.DATADOG.value, detail)

        assert context.alert_name == "High error rate in API"
        assert context.affected_service == "aura-api"
        assert context.error_message == "Error rate > 5%"
        assert context.severity == IncidentSeverity.HIGH
        assert context.source == IncidentSource.DATADOG

    def test_extract_service_from_alarm(self, agent):
        """Test service name extraction from alarm names."""
        assert agent._extract_service_from_alarm("aura-api-high-cpu-dev") == "aura-api"
        assert (
            agent._extract_service_from_alarm("aura-frontend-errors-prod")
            == "aura-frontend"
        )
        assert agent._extract_service_from_alarm("single") == "unknown"

    def test_extract_function_names_from_stack_trace(self, agent):
        """Test function name extraction from Python stack traces."""
        stack_trace = """Traceback (most recent call last):
  File "/app/src/api.py", line 45, in handle_request
    result = process_data(input)
  File "/app/src/processor.py", line 120, in process_data
    return validate(data)
  File "/app/src/validator.py", line 30, in validate
    raise ValueError("Invalid data")
"""

        function_names = agent._extract_function_names(stack_trace)

        assert "handle_request" in function_names
        assert "process_data" in function_names
        assert "validate" in function_names
        assert len(function_names) == 3


class TestObservabilityQuerying:
    """Test observability platform integration."""

    @pytest.mark.asyncio
    async def test_query_cloudwatch_logs(self, agent):
        """Test CloudWatch Logs querying."""
        agent.cloudwatch_logs.filter_log_events = MagicMock(
            return_value={
                "events": [
                    {"message": "ERROR: Connection timeout", "timestamp": 1638835200000}
                ]
            }
        )

        start_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        end_time = datetime.now(timezone.utc)

        logs = await agent._query_cloudwatch_logs(
            log_group="/ecs/aura-api",
            start_time=start_time,
            end_time=end_time,
            filter_pattern="ERROR",
        )

        assert len(logs) == 1
        assert "Connection timeout" in logs[0]["message"]
        agent.cloudwatch_logs.filter_log_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_cloudwatch_logs_failure(self, agent):
        """Test CloudWatch Logs query failure handling."""
        agent.cloudwatch_logs.filter_log_events = MagicMock(
            side_effect=Exception("Log group not found")
        )

        start_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        end_time = datetime.now(timezone.utc)

        logs = await agent._query_cloudwatch_logs(
            log_group="/ecs/nonexistent",
            start_time=start_time,
            end_time=end_time,
            filter_pattern="ERROR",
        )

        assert logs == []

    @pytest.mark.asyncio
    async def test_query_observability_with_mcp(self, agent):
        """Test multi-vendor observability querying with MCP."""
        incident_context = IncidentContext(
            alert_name="test-alert",
            affected_service="aura-api",
            timestamp="2025-12-06T10:00:00Z",
            error_message="Test error",
        )

        agent.cloudwatch_logs.filter_log_events = MagicMock(
            return_value={"events": [{"message": "ERROR"}]}
        )

        metrics = await agent._query_observability(incident_context)

        assert "cloudwatch_logs" in metrics
        assert "datadog_traces" in metrics
        assert "prometheus_cpu" in metrics
        assert len(metrics["datadog_traces"]) == 1
        assert metrics["datadog_traces"][0]["trace_id"] == "123"


class TestDeploymentCorrelation:
    """Test deployment event correlation."""

    @pytest.mark.asyncio
    async def test_query_recent_deployments(self, agent):
        """Test querying deployment history."""
        agent.deployments_table.query = MagicMock(
            return_value={
                "Items": [
                    {
                        "deployment_id": "deploy-001",
                        "timestamp": "2025-12-06T09:00:00Z",
                        "application_name": "aura-api",
                        "commit_sha": "abc123",
                        "commit_message": "Fix null check",
                        "argocd_sync_status": "Synced",
                        "rollout_status": "Healthy",
                        "image_tag": "v1.2.3",
                        "deployed_by": "argocd",
                        "source": "argocd",
                    }
                ]
            }
        )

        deployments = await agent._query_recent_deployments(
            service_name="aura-api", incident_time="2025-12-06T10:00:00Z"
        )

        assert len(deployments) == 1
        assert deployments[0].deployment_id == "deploy-001"
        assert deployments[0].commit_sha == "abc123"
        assert deployments[0].rollout_status == "Healthy"

    @pytest.mark.asyncio
    async def test_query_deployments_no_results(self, agent):
        """Test deployment query with no recent deployments."""
        agent.deployments_table.query = MagicMock(return_value={"Items": []})

        deployments = await agent._query_recent_deployments(
            service_name="aura-api", incident_time="2025-12-06T10:00:00Z"
        )

        assert deployments == []

    @pytest.mark.asyncio
    async def test_query_deployments_error_handling(self, agent):
        """Test deployment query error handling."""
        agent.deployments_table.query = MagicMock(
            side_effect=Exception("DynamoDB error")
        )

        deployments = await agent._query_recent_deployments(
            service_name="aura-api", incident_time="2025-12-06T10:00:00Z"
        )

        assert deployments == []


class TestCodeEntityCorrelation:
    """Test code entity correlation with Neptune."""

    @pytest.mark.asyncio
    async def test_correlate_with_code_graph(self, agent):
        """Test mapping stack trace to Neptune code entities."""
        stack_trace = """  File "/app/src/api.py", line 45, in handle_request
    result = process_data(input)
"""

        code_entities = await agent._correlate_with_code_graph(
            error_message="Test error", stack_trace=stack_trace
        )

        assert len(code_entities) >= 1
        assert code_entities[0].name == "handle_request"
        assert code_entities[0].file_path == "src/api/handlers.py"
        assert code_entities[0].line_number == 42

    @pytest.mark.asyncio
    async def test_correlate_no_stack_trace(self, agent):
        """Test code correlation without stack trace."""
        code_entities = await agent._correlate_with_code_graph(
            error_message=None, stack_trace=None
        )

        assert code_entities == []

    @pytest.mark.asyncio
    async def test_correlate_with_semantic_search(self, agent, mock_context_service):
        """Test semantic search in OpenSearch for error messages."""
        mock_context_service.vector_store.semantic_search = AsyncMock(
            return_value=[
                {
                    "id": "func-456",
                    "entity_type": "function",
                    "name": "error_handler",
                    "file_path": "src/errors.py",
                    "line_number": 10,
                }
            ]
        )
        agent.context = mock_context_service

        code_entities = await agent._correlate_with_code_graph(
            error_message="NullPointerException in handler", stack_trace=None
        )

        assert len(code_entities) >= 1


class TestGitCommitSearch:
    """Test git commit search in OpenSearch."""

    @pytest.mark.asyncio
    async def test_search_recent_changes(self, agent):
        """Test searching for recent commits affecting code entities."""
        code_entities = [
            CodeEntity(
                entity_id="func-123",
                entity_type="function",
                name="handle_request",
                file_path="src/api/handlers.py",
            )
        ]

        git_commits = await agent._search_recent_changes(
            code_entities=code_entities, incident_time="2025-12-06T10:00:00Z"
        )

        assert len(git_commits) >= 1
        assert git_commits[0].sha == "abc123"
        assert git_commits[0].message == "Fix null check in handler"

    @pytest.mark.asyncio
    async def test_search_commits_no_entities(self, agent):
        """Test commit search with no code entities."""
        git_commits = await agent._search_recent_changes(
            code_entities=[], incident_time="2025-12-06T10:00:00Z"
        )

        assert git_commits == []


class TestRCAGeneration:
    """Test RCA hypothesis generation."""

    @pytest.mark.asyncio
    async def test_generate_rca_hypothesis(self, agent):
        """Test LLM-powered RCA generation."""
        incident_context = IncidentContext(
            alert_name="api-errors",
            affected_service="aura-api",
            timestamp="2025-12-06T10:00:00Z",
            error_message="NullPointerException",
        )

        rca_result = await agent._generate_rca_hypothesis(
            incident_context=incident_context,
            metrics={},
            deployments=[],
            code_entities=[],
            git_commits=[],
        )

        assert rca_result.hypothesis != ""
        assert 0 <= rca_result.confidence <= 100
        assert len(rca_result.evidence) > 0

    @pytest.mark.asyncio
    async def test_generate_rca_no_llm(self, agent):
        """Test RCA generation without LLM client."""
        agent.llm = None

        incident_context = IncidentContext(
            alert_name="test-alert",
            affected_service="aura-api",
            timestamp="2025-12-06T10:00:00Z",
            error_message="Test error",
        )

        rca_result = await agent._generate_rca_hypothesis(
            incident_context=incident_context,
            metrics={},
            deployments=[],
            code_entities=[],
            git_commits=[],
        )

        assert rca_result.confidence == 0
        assert "no llm" in rca_result.hypothesis.lower()

    def test_parse_rca_response_valid_json(self, agent):
        """Test parsing valid RCA JSON response."""
        response = '{"hypothesis": "Test hypothesis", "confidence": 90, "evidence": ["Evidence 1"], "alternatives": []}'

        rca_result = agent._parse_rca_response(response)

        assert rca_result.hypothesis == "Test hypothesis"
        assert rca_result.confidence == 90
        assert len(rca_result.evidence) == 1

    def test_parse_rca_response_with_markdown(self, agent):
        """Test parsing RCA response with markdown code blocks."""
        response = """Here's the analysis:

```json
{
  "hypothesis": "Deployment bug",
  "confidence": 85,
  "evidence": ["Stack trace", "Recent deployment"],
  "alternatives": ["Database issue"]
}
```
"""

        rca_result = agent._parse_rca_response(response)

        assert rca_result.hypothesis == "Deployment bug"
        assert rca_result.confidence == 85

    def test_parse_rca_response_invalid(self, agent):
        """Test parsing invalid RCA response."""
        response = "Invalid JSON response"

        rca_result = agent._parse_rca_response(response)

        assert rca_result.confidence == 0
        assert "parsing error" in rca_result.hypothesis.lower()

    def test_parse_rca_response_confidence_bounds(self, agent):
        """Test RCA confidence is clamped to 0-100."""
        response = '{"hypothesis": "Test", "confidence": 150, "evidence": []}'

        rca_result = agent._parse_rca_response(response)

        assert rca_result.confidence == 100  # Clamped to max

        response = '{"hypothesis": "Test", "confidence": -50, "evidence": []}'
        rca_result = agent._parse_rca_response(response)

        assert rca_result.confidence == 0  # Clamped to min


class TestMitigationPlanGeneration:
    """Test mitigation plan generation."""

    @pytest.mark.asyncio
    async def test_generate_mitigation_plan(self, agent, mock_llm_client):
        """Test mitigation plan generation."""
        mock_llm_client.generate = AsyncMock(
            return_value="""1. Rollback deployment to previous version
2. Verify error rate returns to normal
3. If rollback fails, restart affected services
4. Long-term: Add null check validation"""
        )

        rca_result = RCAHypothesis(
            hypothesis="Recent deployment introduced bug",
            confidence=85,
            evidence=["Error spike", "Stack trace"],
        )

        mitigation_plan = await agent._generate_mitigation_plan(
            rca_result=rca_result, recent_deployments=[]
        )

        assert "Rollback" in mitigation_plan
        assert "verify" in mitigation_plan.lower()

    @pytest.mark.asyncio
    async def test_generate_mitigation_no_llm(self, agent):
        """Test mitigation generation without LLM."""
        agent.llm = None

        rca_result = RCAHypothesis(hypothesis="Test", confidence=80, evidence=[])

        mitigation_plan = await agent._generate_mitigation_plan(
            rca_result=rca_result, recent_deployments=[]
        )

        assert "no LLM client" in mitigation_plan


class TestFormattingHelpers:
    """Test formatting helper methods."""

    def test_format_deployments(self, agent):
        """Test deployment formatting for LLM prompts."""
        deployments = [
            DeploymentEvent(
                deployment_id="d1",
                timestamp="2025-12-06T09:00:00Z",
                application_name="aura-api",
                commit_sha="abc123def456",
                commit_message="Fix bug",
                argocd_sync_status="Synced",
                rollout_status="Healthy",
                image_tag="v1.2.3",
                deployed_by="argocd",
                source="argocd",
            )
        ]

        formatted = agent._format_deployments(deployments)

        assert "aura-api" in formatted
        assert "abc123d" in formatted  # First 7 chars of SHA
        assert "Healthy" in formatted

    def test_format_code_entities(self, agent):
        """Test code entity formatting."""
        entities = [
            CodeEntity(
                entity_id="e1",
                entity_type="function",
                name="handle_request",
                file_path="src/api.py",
            )
        ]

        formatted = agent._format_code_entities(entities)

        assert "handle_request" in formatted
        assert "function" in formatted
        assert "src/api.py" in formatted

    def test_format_git_commits(self, agent):
        """Test git commit formatting."""
        commits = [
            GitCommit(
                sha="abc123def456",
                message="Fix null check",
                author="dev@example.com",
                timestamp="2025-12-06T08:00:00Z",
                file_path="src/api.py",
            )
        ]

        formatted = agent._format_git_commits(commits)

        assert "Fix null check" in formatted
        assert "abc123d" in formatted  # First 7 chars
        assert "dev@example.com" in formatted

    def test_summarize_prometheus_data(self, agent):
        """Test Prometheus data summarization."""
        prometheus_data = {
            "data": {"result": [{"values": [[1638835200, "0.5"], [1638835260, "0.8"]]}]}
        }

        summary = agent._summarize_prometheus_data(prometheus_data)

        assert "avg=" in summary
        assert "max=" in summary

    def test_summarize_prometheus_no_data(self, agent):
        """Test Prometheus summarization with no data."""
        assert agent._summarize_prometheus_data({}) == "No data"
        # Invalid data structure returns "Invalid data" (safe fallback)
        assert "data" in agent._summarize_prometheus_data({"data": {}}).lower()


class TestInvestigationWorkflow:
    """Test complete investigation workflow."""

    @pytest.mark.asyncio
    async def test_full_investigation(self, agent):
        """Test end-to-end investigation workflow."""
        incident_event = {
            "id": "incident-123",
            "source": "aws.cloudwatch",
            "detail": {
                "alarmName": "aura-api-errors-dev",
                "newStateValue": "ALARM",
                "newStateReason": "Error rate > 5%",
                "stateChangeTime": "2025-12-06T10:00:00Z",
            },
        }

        # Mock all dependencies
        agent.cloudwatch_logs.filter_log_events = MagicMock(return_value={"events": []})
        agent.deployments_table.query = MagicMock(return_value={"Items": []})
        agent.investigations_table.put_item = MagicMock()

        investigation = await agent.investigate(incident_event)

        assert investigation.incident_id == "incident-123"
        assert investigation.affected_service == "aura-api"
        assert investigation.confidence_score >= 0
        assert investigation.hitl_status == "pending"
        agent.investigations_table.put_item.assert_called_once()

    def test_investigation_result_to_dynamodb_item(self):
        """Test InvestigationResult DynamoDB conversion."""
        investigation = InvestigationResult(
            incident_id="test-123",
            timestamp="2025-12-06T10:00:00Z",
            source="cloudwatch",
            alert_name="test-alert",
            affected_service="aura-api",
            rca_hypothesis="Test hypothesis",
            confidence_score=85,
            deployment_correlation=[],
            code_entities=[],
            git_commits=[],
            mitigation_plan="Test plan",
        )

        item = investigation.to_dynamodb_item()

        assert item["incident_id"] == "test-123"
        assert item["confidence_score"] == 85
        assert item["hitl_status"] == "pending"
        assert "ttl" in item
        assert isinstance(item["ttl"], int)
