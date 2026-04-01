"""
Project Aura - Shared Type Definitions

Centralized TypedDict and Protocol definitions for consistent
typing across the codebase. Use these types to avoid Any
propagation from external libraries.
"""

from typing import Any, TypedDict

# =============================================================================
# LLM Response Types
# =============================================================================


class LLMResponse(TypedDict):
    """Standard response from Bedrock LLM invocations."""

    text: str
    tokens_input: int
    tokens_output: int


class LLMResponseWithCost(LLMResponse):
    """LLM response with cost tracking."""

    cost_usd: float


class GuardrailResult(TypedDict):
    """Result from Bedrock Guardrails evaluation."""

    action: str  # "NONE", "BLOCKED", "GUARDRAIL_INTERVENED"
    blocked: bool
    reason: str | None


# =============================================================================
# DynamoDB Types
# =============================================================================


class DynamoDBItem(TypedDict, total=False):
    """Generic DynamoDB item response."""

    Item: dict[str, Any]


class DynamoDBQueryResponse(TypedDict, total=False):
    """DynamoDB Query/Scan response."""

    Items: list[dict[str, Any]]
    Count: int
    ScannedCount: int
    LastEvaluatedKey: dict[str, Any] | None


# =============================================================================
# Agent Types
# =============================================================================


class AgentMetrics(TypedDict):
    """Metrics returned by agent execution."""

    tasks_executed: int
    tasks_succeeded: int
    tasks_failed: int
    total_execution_time_ms: float
    average_execution_time_ms: float


class ToolInvocation(TypedDict):
    """Record of a tool invocation by an agent."""

    tool_name: str
    parameters: dict[str, Any]
    result: dict[str, Any]
    execution_time_ms: float
    success: bool


# =============================================================================
# Graph/Vector Types
# =============================================================================


class GraphNode(TypedDict):
    """Node returned from Neptune graph queries."""

    id: str
    label: str
    properties: dict[str, Any]


class GraphRelationship(TypedDict):
    """Relationship returned from Neptune graph queries."""

    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any]


class VectorSearchResult(TypedDict):
    """Result from OpenSearch vector similarity search."""

    id: str
    score: float
    content: str
    metadata: dict[str, Any]


# =============================================================================
# API Response Types
# =============================================================================


class PaginatedResponse(TypedDict):
    """Standard paginated API response."""

    items: list[dict[str, Any]]
    total: int
    cursor: str | None


class ErrorResponse(TypedDict):
    """Standard error response."""

    error: str
    detail: str | None
    status_code: int


# =============================================================================
# Service Configuration Types
# =============================================================================


class DatabaseConfig(TypedDict, total=False):
    """Database connection configuration."""

    endpoint: str
    port: int
    region: str
    use_iam_auth: bool


class ServiceHealth(TypedDict):
    """Health check result for a service."""

    healthy: bool
    latency_ms: float
    message: str | None
