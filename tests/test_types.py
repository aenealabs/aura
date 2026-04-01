"""
Tests for shared type definitions.

These tests verify that TypedDict definitions in src/types/__init__.py
are correctly defined and usable for type checking.
"""

from src.types import (
    AgentMetrics,
    DatabaseConfig,
    DynamoDBItem,
    DynamoDBQueryResponse,
    ErrorResponse,
    GraphNode,
    GraphRelationship,
    GuardrailResult,
    LLMResponse,
    LLMResponseWithCost,
    PaginatedResponse,
    ServiceHealth,
    ToolInvocation,
    VectorSearchResult,
)


class TestLLMResponseTypes:
    """Tests for LLM response TypedDicts."""

    def test_llm_response_structure(self):
        """Test LLMResponse TypedDict structure."""
        response: LLMResponse = {
            "text": "Hello, world!",
            "tokens_input": 10,
            "tokens_output": 5,
        }
        assert response["text"] == "Hello, world!"
        assert response["tokens_input"] == 10
        assert response["tokens_output"] == 5

    def test_llm_response_with_cost_structure(self):
        """Test LLMResponseWithCost TypedDict structure."""
        response: LLMResponseWithCost = {
            "text": "Response text",
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.0015,
        }
        assert response["cost_usd"] == 0.0015
        assert "text" in response

    def test_guardrail_result_structure(self):
        """Test GuardrailResult TypedDict structure."""
        result: GuardrailResult = {
            "action": "BLOCKED",
            "blocked": True,
            "reason": "Content policy violation",
        }
        assert result["action"] == "BLOCKED"
        assert result["blocked"] is True
        assert result["reason"] == "Content policy violation"


class TestDynamoDBTypes:
    """Tests for DynamoDB TypedDicts."""

    def test_dynamodb_item_structure(self):
        """Test DynamoDBItem TypedDict structure."""
        item: DynamoDBItem = {"Item": {"pk": {"S": "user#123"}, "sk": {"S": "profile"}}}
        assert "Item" in item
        assert item["Item"]["pk"] == {"S": "user#123"}

    def test_dynamodb_query_response_structure(self):
        """Test DynamoDBQueryResponse TypedDict structure."""
        response: DynamoDBQueryResponse = {
            "Items": [{"pk": {"S": "item1"}}, {"pk": {"S": "item2"}}],
            "Count": 2,
            "ScannedCount": 2,
            "LastEvaluatedKey": None,
        }
        assert response["Count"] == 2
        assert len(response["Items"]) == 2


class TestAgentTypes:
    """Tests for Agent TypedDicts."""

    def test_agent_metrics_structure(self):
        """Test AgentMetrics TypedDict structure."""
        metrics: AgentMetrics = {
            "tasks_executed": 100,
            "tasks_succeeded": 95,
            "tasks_failed": 5,
            "total_execution_time_ms": 5000.0,
            "average_execution_time_ms": 50.0,
        }
        assert metrics["tasks_executed"] == 100
        assert metrics["tasks_succeeded"] == 95

    def test_tool_invocation_structure(self):
        """Test ToolInvocation TypedDict structure."""
        invocation: ToolInvocation = {
            "tool_name": "code_search",
            "parameters": {"query": "function definition"},
            "result": {"matches": 5},
            "execution_time_ms": 150.0,
            "success": True,
        }
        assert invocation["tool_name"] == "code_search"
        assert invocation["success"] is True


class TestGraphTypes:
    """Tests for Graph/Vector TypedDicts."""

    def test_graph_node_structure(self):
        """Test GraphNode TypedDict structure."""
        node: GraphNode = {
            "id": "node-123",
            "label": "Function",
            "properties": {"name": "main", "language": "python"},
        }
        assert node["id"] == "node-123"
        assert node["label"] == "Function"

    def test_graph_relationship_structure(self):
        """Test GraphRelationship TypedDict structure."""
        rel: GraphRelationship = {
            "id": "rel-456",
            "type": "CALLS",
            "source_id": "node-123",
            "target_id": "node-789",
            "properties": {"frequency": 10},
        }
        assert rel["type"] == "CALLS"
        assert rel["source_id"] == "node-123"

    def test_vector_search_result_structure(self):
        """Test VectorSearchResult TypedDict structure."""
        result: VectorSearchResult = {
            "id": "doc-001",
            "score": 0.95,
            "content": "This is a code snippet",
            "metadata": {"file": "main.py", "line": 42},
        }
        assert result["score"] == 0.95
        assert result["metadata"]["file"] == "main.py"


class TestAPIResponseTypes:
    """Tests for API Response TypedDicts."""

    def test_paginated_response_structure(self):
        """Test PaginatedResponse TypedDict structure."""
        response: PaginatedResponse = {
            "items": [{"id": 1}, {"id": 2}],
            "total": 100,
            "cursor": "next_cursor_token",
        }
        assert response["total"] == 100
        assert len(response["items"]) == 2

    def test_error_response_structure(self):
        """Test ErrorResponse TypedDict structure."""
        error: ErrorResponse = {
            "error": "Not Found",
            "detail": "Resource does not exist",
            "status_code": 404,
        }
        assert error["error"] == "Not Found"
        assert error["status_code"] == 404


class TestServiceConfigTypes:
    """Tests for Service Configuration TypedDicts."""

    def test_database_config_structure(self):
        """Test DatabaseConfig TypedDict structure."""
        config: DatabaseConfig = {
            "endpoint": "localhost",
            "port": 5432,
            "region": "us-east-1",
            "use_iam_auth": True,
        }
        assert config["endpoint"] == "localhost"
        assert config["use_iam_auth"] is True

    def test_service_health_structure(self):
        """Test ServiceHealth TypedDict structure."""
        health: ServiceHealth = {
            "healthy": True,
            "latency_ms": 15.5,
            "message": None,
        }
        assert health["healthy"] is True
        assert health["latency_ms"] == 15.5
