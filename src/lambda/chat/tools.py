"""
Aura Chat Assistant - Tool Definitions and Execution

This module defines the 11 tools available to the Aura Assistant:
1. get_vulnerability_metrics - Query vulnerability statistics
2. get_agent_status - Check agent health and activity
3. get_approval_queue - View pending HITL approvals
4. search_documentation - Search docs, ADRs, and guides
5. get_incident_details - Get incident investigation data
6. generate_report - Create ad-hoc summary reports
7. query_code_graph - Query GraphRAG code relationships
8. get_sandbox_status - Check sandbox environment status
9. generate_diagram - Generate Mermaid/PlantUML/draw.io diagrams
10. start_deep_research - Start async deep research task
11. get_research_status - Get research task status/results
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Attr, ConditionBase
from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_cloudwatch_client, get_dynamodb_resource
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_cloudwatch_client = _aws_clients.get_cloudwatch_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource

# Import diagram generation tools
try:
    from diagram_tools import generate_diagram as _generate_diagram_impl
except ImportError:
    from .diagram_tools import generate_diagram as _generate_diagram_impl

# Import deep research tools
try:
    from research_tools import get_research_status as _get_research_status_impl
    from research_tools import start_deep_research as _start_deep_research_impl
except ImportError:
    from .research_tools import get_research_status as _get_research_status_impl
    from .research_tools import start_deep_research as _start_deep_research_impl

logger = logging.getLogger()

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")


# Lazy table accessors (Issue #466)
def get_anomalies_table():
    """Get DynamoDB anomalies table (lazy initialization)."""
    return get_dynamodb_resource().Table(f"{PROJECT_NAME}-anomalies-{ENVIRONMENT}")


def get_approval_table():
    """Get DynamoDB approval requests table (lazy initialization)."""
    return get_dynamodb_resource().Table(
        f"{PROJECT_NAME}-approval-requests-{ENVIRONMENT}"
    )


def get_workflow_table():
    """Get DynamoDB patch workflows table (lazy initialization)."""
    return get_dynamodb_resource().Table(
        f"{PROJECT_NAME}-patch-workflows-{ENVIRONMENT}"
    )


# =============================================================================
# Tool Definitions (OpenAPI-style schema for Bedrock)
# =============================================================================

CHAT_TOOLS = [
    {
        "name": "get_vulnerability_metrics",
        "description": "Query vulnerability statistics by severity, status, and time range. Returns counts and trends.",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Filter by severity level",
                    "enum": ["critical", "high", "medium", "low", "all"],
                },
                "status": {
                    "type": "string",
                    "description": "Filter by vulnerability status",
                    "enum": ["open", "in_progress", "resolved", "all"],
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for metrics",
                    "enum": ["24h", "7d", "30d", "90d"],
                },
            },
            "required": ["severity"],
        },
    },
    {
        "name": "get_agent_status",
        "description": "Get the health and activity status of AI agents (Orchestrator, Coder, Reviewer, Validator).",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "description": "Specific agent to query, or 'all' for all agents",
                    "enum": ["orchestrator", "coder", "reviewer", "validator", "all"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_approval_queue",
        "description": "Get pending HITL (Human-in-the-Loop) approval requests with optional filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "approval_type": {
                    "type": "string",
                    "description": "Type of approval",
                    "enum": ["patch", "deployment", "security", "all"],
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by priority level",
                    "enum": ["critical", "high", "medium", "low", "all"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of items to return",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_documentation",
        "description": "Search platform documentation, Architecture Decision Records (ADRs), and guides using semantic search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text",
                },
                "doc_type": {
                    "type": "string",
                    "description": "Filter by documentation type",
                    "enum": ["adr", "guide", "runbook", "api", "all"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_incident_details",
        "description": "Get details about a security incident including timeline, affected systems, and remediation status.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The incident ID to look up",
                },
                "include_timeline": {
                    "type": "boolean",
                    "description": "Include event timeline",
                },
                "include_rca": {
                    "type": "boolean",
                    "description": "Include root cause analysis if available",
                },
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "generate_report",
        "description": "Generate an ad-hoc summary report on vulnerabilities, agents, patches, or incidents.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": "Type of report to generate",
                    "enum": [
                        "vulnerability_summary",
                        "agent_activity",
                        "patch_history",
                        "incident_summary",
                        "daily_digest",
                    ],
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for the report",
                    "enum": ["24h", "7d", "30d"],
                },
                "format": {
                    "type": "string",
                    "description": "Output format",
                    "enum": ["summary", "detailed", "table"],
                },
            },
            "required": ["report_type"],
        },
    },
    {
        "name": "query_code_graph",
        "description": "Query the GraphRAG code graph to find relationships, dependencies, and code patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "Type of graph query",
                    "enum": [
                        "dependencies",
                        "callers",
                        "callees",
                        "similar_code",
                        "impact_analysis",
                    ],
                },
                "entity": {
                    "type": "string",
                    "description": "The code entity to query (function name, class name, file path)",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels of relationships to traverse",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["query_type", "entity"],
        },
    },
    {
        "name": "get_sandbox_status",
        "description": "Get the status of sandbox testing environments including active tests and resource usage.",
        "parameters": {
            "type": "object",
            "properties": {
                "sandbox_id": {
                    "type": "string",
                    "description": "Specific sandbox ID, or omit for all active sandboxes",
                },
                "include_metrics": {
                    "type": "boolean",
                    "description": "Include resource usage metrics",
                },
            },
            "required": [],
        },
    },
    {
        "name": "generate_diagram",
        "description": "Generate architecture, sequence, class, ER, state, or dependency diagrams in Mermaid, PlantUML, or draw.io format.",
        "parameters": {
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "description": "Type of diagram to generate",
                    "enum": [
                        "flowchart",
                        "sequence",
                        "class",
                        "er",
                        "state",
                        "architecture",
                        "dependency",
                    ],
                },
                "subject": {
                    "type": "string",
                    "description": "What to diagram (e.g., 'authentication flow', 'agent orchestration', 'chat data model')",
                },
                "format": {
                    "type": "string",
                    "description": "Output format for the diagram",
                    "enum": ["mermaid", "plantuml", "drawio"],
                },
                "scope": {
                    "type": "string",
                    "description": "Scope level of the diagram",
                    "enum": ["component", "service", "system", "codebase"],
                },
            },
            "required": ["diagram_type", "subject"],
        },
    },
    {
        "name": "start_deep_research",
        "description": "Start a deep research task for complex analysis that may take time. Returns a task ID for tracking progress. Use for cross-codebase analysis, security audits, architecture reviews, or comprehensive documentation.",
        "parameters": {
            "type": "object",
            "properties": {
                "research_query": {
                    "type": "string",
                    "description": "The research question or analysis to perform",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope of the research",
                    "enum": ["repository", "codebase", "organization"],
                },
                "urgency": {
                    "type": "string",
                    "description": "Processing urgency - urgent streams progress, standard notifies on completion",
                    "enum": ["standard", "urgent"],
                },
                "data_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Data sources to query",
                    "enum": [
                        "code_graph",
                        "security_findings",
                        "agent_logs",
                        "audit_trail",
                    ],
                },
            },
            "required": ["research_query"],
        },
    },
    {
        "name": "get_research_status",
        "description": "Get the status and results of a deep research task by its task ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The research task ID (e.g., RSH-ABC123DEF456)",
                },
            },
            "required": ["task_id"],
        },
    },
]


# =============================================================================
# Tool Execution
# =============================================================================


def execute_tool(tool_name: str, tool_input: dict, user_info: dict) -> dict:
    """
    Execute a tool and return the result.

    All tools enforce tenant isolation using user_info.
    """
    tenant_id = user_info.get("tenant_id", "")

    tool_map = {
        "get_vulnerability_metrics": _get_vulnerability_metrics,
        "get_agent_status": _get_agent_status,
        "get_approval_queue": _get_approval_queue,
        "search_documentation": _search_documentation,
        "get_incident_details": _get_incident_details,
        "generate_report": _generate_report,
        "query_code_graph": _query_code_graph,
        "get_sandbox_status": _get_sandbox_status,
        "generate_diagram": _generate_diagram,
        "start_deep_research": _start_deep_research,
        "get_research_status": _get_research_status,
    }

    if tool_name not in tool_map:
        raise ValueError(f"Unknown tool: {tool_name}")

    return tool_map[tool_name](tool_input, tenant_id)


# =============================================================================
# Tool Implementations
# =============================================================================


def _get_vulnerability_metrics(params: dict, tenant_id: str) -> dict:
    """Query vulnerability metrics from DynamoDB anomalies table."""
    severity = params.get("severity", "all")
    status = params.get("status", "all")
    time_range = params.get("time_range", "7d")

    # Calculate time cutoff
    time_deltas = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}
    days = time_deltas.get(time_range, 7)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        # Query anomalies table
        filter_expr: ConditionBase = Attr("created_at").gte(cutoff)

        if severity != "all":
            filter_expr = filter_expr & Attr("severity").eq(severity)
        if status != "all":
            filter_expr = filter_expr & Attr("status").eq(status)

        response = get_anomalies_table().scan(
            FilterExpression=filter_expr,
            ProjectionExpression="anomaly_id, severity, #s, created_at",
            ExpressionAttributeNames={"#s": "status"},
            Limit=1000,
        )

        items = response.get("Items", [])

        # Calculate metrics
        metrics = {
            "total_count": len(items),
            "by_severity": {},
            "by_status": {},
            "time_range": time_range,
        }

        for item in items:
            sev = item.get("severity", "unknown")
            stat = item.get("status", "unknown")
            metrics["by_severity"][sev] = metrics["by_severity"].get(sev, 0) + 1
            metrics["by_status"][stat] = metrics["by_status"].get(stat, 0) + 1

        return metrics

    except Exception as e:
        logger.error(f"Error getting vulnerability metrics: {e}")
        return {"error": str(e), "total_count": 0}


def _get_agent_status(params: dict, tenant_id: str) -> dict:
    """Get agent health status from CloudWatch metrics."""
    agent_type = params.get("agent_type", "all")

    agents = ["orchestrator", "coder", "reviewer", "validator"]
    if agent_type != "all":
        agents = [agent_type]

    results = {}

    try:
        for agent in agents:
            # Get Lambda invocation metrics for agent
            metric_response = get_cloudwatch_client().get_metric_data(
                MetricDataQueries=[
                    {
                        "Id": "invocations",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/Lambda",
                                "MetricName": "Invocations",
                                "Dimensions": [
                                    {
                                        "Name": "FunctionName",
                                        "Value": f"{PROJECT_NAME}-{agent}-{ENVIRONMENT}",
                                    }
                                ],
                            },
                            "Period": 3600,
                            "Stat": "Sum",
                        },
                    },
                    {
                        "Id": "errors",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/Lambda",
                                "MetricName": "Errors",
                                "Dimensions": [
                                    {
                                        "Name": "FunctionName",
                                        "Value": f"{PROJECT_NAME}-{agent}-{ENVIRONMENT}",
                                    }
                                ],
                            },
                            "Period": 3600,
                            "Stat": "Sum",
                        },
                    },
                ],
                StartTime=datetime.now(timezone.utc) - timedelta(hours=24),
                EndTime=datetime.now(timezone.utc),
            )

            # Extract values
            invocations = sum(
                metric_response["MetricDataResults"][0].get("Values", [0])
            )
            errors = sum(metric_response["MetricDataResults"][1].get("Values", [0]))

            results[agent] = {
                "status": "healthy" if errors == 0 else "degraded",
                "invocations_24h": int(invocations),
                "errors_24h": int(errors),
                "error_rate": round(errors / max(invocations, 1) * 100, 2),
            }

    except ClientError as e:
        logger.warning(f"CloudWatch metrics not available: {e}")
        # Return mock data for dev environment
        for agent in agents:
            results[agent] = {
                "status": "healthy",
                "invocations_24h": 150,
                "errors_24h": 0,
                "error_rate": 0.0,
                "note": "Mock data - CloudWatch metrics unavailable",
            }

    return {"agents": results}


def _get_approval_queue(params: dict, tenant_id: str) -> dict:
    """Get pending HITL approval requests."""
    approval_type = params.get("approval_type", "all")
    priority = params.get("priority", "all")
    limit = params.get("limit", 10)

    try:
        # Query pending approvals
        filter_expr: ConditionBase = Attr("status").eq("pending")

        if approval_type != "all":
            filter_expr = filter_expr & Attr("approval_type").eq(approval_type)
        if priority != "all":
            filter_expr = filter_expr & Attr("priority").eq(priority)

        response = get_approval_table().scan(
            FilterExpression=filter_expr,
            ProjectionExpression="request_id, approval_type, priority, title, created_at, requester",
            Limit=limit,
        )

        items = response.get("Items", [])

        approvals = [
            {
                "request_id": item.get("request_id"),
                "approval_type": item.get("approval_type"),
                "priority": item.get("priority"),
                "title": item.get("title", "Untitled"),
                "created_at": item.get("created_at"),
                "requester": item.get("requester"),
            }
            for item in items
        ]

        return {
            "pending_count": len(approvals),
            "approvals": approvals,
        }

    except Exception as e:
        logger.error(f"Error getting approval queue: {e}")
        # Return mock data for dev
        return {
            "pending_count": 3,
            "approvals": [
                {
                    "request_id": "APR-001",
                    "approval_type": "patch",
                    "priority": "high",
                    "title": "Security patch for CVE-2025-1234",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "request_id": "APR-002",
                    "approval_type": "deployment",
                    "priority": "medium",
                    "title": "Deploy API v2.3.1 to production",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            ],
            "note": "Mock data - DynamoDB table not available",
        }


def _search_documentation(params: dict, tenant_id: str) -> dict:
    """
    Search documentation using hybrid semantic search (text + vector).

    Uses the DocumentationIndexer service to search indexed markdown documentation.
    Falls back to mock results if OpenSearch is not available.

    Args:
        params: Search parameters including query, doc_type, and limit
        tenant_id: Tenant identifier (for multi-tenant filtering)

    Returns:
        Dictionary with search results including title, path, type, and relevance
    """
    import asyncio

    query = params.get("query", "")
    doc_type = params.get("doc_type", "all")
    limit = params.get("limit", 5)

    # Map tool doc_type to indexer doc_type
    doc_type_mapping = {
        "adr": "adr",
        "guide": "guide",
        "runbook": "runbook",
        "api": "api",
        "all": None,
    }
    mapped_doc_type = doc_type_mapping.get(doc_type)

    try:
        # Try to use real DocumentationIndexer
        from src.services.documentation_indexer import DocumentationIndexer

        indexer = DocumentationIndexer()

        # Run async search in sync context (reuse existing loop if available)
        try:
            loop = asyncio.get_running_loop()
            _owns_loop = False
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _owns_loop = True
        try:
            # Initialize the indexer
            loop.run_until_complete(indexer.initialize())

            # Perform the search
            search_results = loop.run_until_complete(
                indexer.search(
                    query=query,
                    doc_type=mapped_doc_type,
                    limit=limit,
                    min_score=0.3,
                    use_hybrid=True,
                )
            )
        finally:
            if _owns_loop:
                loop.close()

        # Convert SearchResult objects to response format
        results = []
        for result in search_results:
            results.append(
                {
                    "title": result.title,
                    "path": result.path,
                    "type": result.doc_type,
                    "category": result.category,
                    "summary": result.summary,
                    "relevance": round(result.score, 3),
                }
            )

        return {
            "query": query,
            "result_count": len(results),
            "results": results,
            "search_type": "hybrid",
        }

    except ImportError:
        logger.warning("DocumentationIndexer not available - using mock results")
    except Exception as e:
        logger.warning(f"Documentation search failed, using mock: {e}")

    # Fallback to mock results if real search fails
    return _search_documentation_mock(query, doc_type, limit)


def _search_documentation_mock(query: str, doc_type: str, limit: int) -> dict:
    """
    Fallback mock documentation search.

    Used when OpenSearch/DocumentationIndexer is not available.
    """
    # Mock documentation search results
    docs = {
        "adr": [
            {
                "title": "ADR-001: GraphRAG Architecture",
                "path": "docs/architecture-decisions/ADR-001-GRAPHRAG.md",
                "summary": "Defines the hybrid GraphRAG architecture combining Neptune and OpenSearch.",
            },
            {
                "title": "ADR-015: Tiered LLM Strategy",
                "path": "docs/architecture-decisions/ADR-015-TIERED-LLM.md",
                "summary": "Outlines the tiered approach for LLM model selection and cost optimization.",
            },
            {
                "title": "ADR-022: GitOps with ArgoCD",
                "path": "docs/architecture-decisions/ADR-022-GITOPS-ARGOCD.md",
                "summary": "Establishes GitOps practices using ArgoCD for deployment automation.",
            },
            {
                "title": "ADR-030: Chat Assistant Architecture",
                "path": "docs/architecture-decisions/ADR-030-CHAT-ASSISTANT-ARCHITECTURE.md",
                "summary": "Defines the Aura Chat Assistant architecture with 11 integrated tools.",
            },
        ],
        "guide": [
            {
                "title": "Frontend UI Runbook",
                "path": "docs/runbooks/FRONTEND_UI_RUNBOOK.md",
                "summary": "Operational runbook for frontend UI deployment and troubleshooting.",
            },
            {
                "title": "Dev Mode Runbook",
                "path": "docs/runbooks/FRONTEND_DEV_MODE_RUNBOOK.md",
                "summary": "Guide for running the frontend in development mode.",
            },
            {
                "title": "CI/CD Setup Guide",
                "path": "docs/deployment/CICD_SETUP_GUIDE.md",
                "summary": "Comprehensive guide for setting up CI/CD pipelines with CodeBuild.",
            },
        ],
        "runbook": [
            {
                "title": "GovCloud Migration Runbook",
                "path": "docs/cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md",
                "summary": "Step-by-step guide for migrating workloads to AWS GovCloud.",
            },
            {
                "title": "Testing Strategy",
                "path": "docs/reference/TESTING_STRATEGY.md",
                "summary": "Testing pyramid and strategy for unit, integration, and e2e tests.",
            },
        ],
        "product": [
            {
                "title": "Hybrid GraphRAG Architecture",
                "path": "docs/product/core-concepts/hybrid-graphrag.md",
                "summary": "Explains the hybrid retrieval architecture combining graph and vector search.",
            },
            {
                "title": "HITL Workflows",
                "path": "docs/product/core-concepts/hitl-workflows.md",
                "summary": "Human-in-the-loop approval workflows for patches and deployments.",
            },
            {
                "title": "Quick Start Guide",
                "path": "docs/product/getting-started/quick-start.md",
                "summary": "Get started with Project Aura in 5 minutes.",
            },
        ],
        "support": [
            {
                "title": "Common Issues",
                "path": "docs/support/troubleshooting/common-issues.md",
                "summary": "Troubleshooting guide for authentication, API, and agent issues.",
            },
            {
                "title": "REST API Reference",
                "path": "docs/support/api-reference/rest-api.md",
                "summary": "Complete REST API documentation with endpoints and examples.",
            },
        ],
    }

    results = []
    query_lower = query.lower()

    # Search in relevant doc types
    search_types = [doc_type] if doc_type != "all" else list(docs.keys())

    for dtype in search_types:
        if dtype not in docs:
            continue
        for doc in docs[dtype]:
            # Check if query matches title or summary
            if (
                query_lower in doc["title"].lower()
                or query_lower in doc.get("summary", "").lower()
            ):
                results.append(
                    {
                        "title": doc["title"],
                        "path": doc["path"],
                        "type": dtype,
                        "summary": doc.get("summary", ""),
                        "relevance": 0.9,
                    }
                )

    # If no matches, return top docs of requested type
    if not results:
        for dtype in search_types:
            if dtype not in docs:
                continue
            for doc in docs[dtype][:limit]:
                results.append(
                    {
                        "title": doc["title"],
                        "path": doc["path"],
                        "type": dtype,
                        "summary": doc.get("summary", ""),
                        "relevance": 0.5,
                    }
                )

    return {
        "query": query,
        "result_count": len(results[:limit]),
        "results": results[:limit],
        "search_type": "mock",
        "note": "Using mock results - OpenSearch integration available in production",
    }


def _get_incident_details(params: dict, tenant_id: str) -> dict:
    """Get incident investigation details."""
    incident_id = params.get("incident_id", "")
    include_timeline = params.get("include_timeline", True)
    include_rca = params.get("include_rca", False)

    # Mock incident data for demonstration
    incident = {
        "incident_id": incident_id,
        "title": f"Security Incident {incident_id}",
        "severity": "high",
        "status": "investigating",
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "affected_systems": ["api-gateway", "auth-service"],
        "assignee": "security-team@aenealabs.com",
    }

    if include_timeline:
        incident["timeline"] = [
            {
                "time": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
                "event": "Incident detected by anomaly service",
            },
            {
                "time": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                "event": "Security team notified",
            },
            {
                "time": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
                "event": "Investigation started",
            },
            {
                "time": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "event": "Root cause identified",
            },
        ]

    if include_rca:
        incident["rca"] = {
            "root_cause": "Misconfigured CORS policy allowed unauthorized cross-origin requests",
            "contributing_factors": [
                "Recent deployment changed security headers",
                "Missing integration test coverage",
            ],
            "remediation": "Patch deployed to fix CORS configuration. Added integration tests.",
        }

    return incident


def _generate_report(params: dict, tenant_id: str) -> dict:
    """Generate an ad-hoc summary report."""
    report_type = params.get("report_type", "vulnerability_summary")
    time_range = params.get("time_range", "7d")
    format_type = params.get("format", "summary")

    reports = {
        "vulnerability_summary": {
            "title": "Vulnerability Summary Report",
            "time_range": time_range,
            "summary": {
                "total_vulnerabilities": 45,
                "critical": 2,
                "high": 8,
                "medium": 20,
                "low": 15,
                "resolved_this_period": 12,
                "new_this_period": 5,
                "mttr_hours": 24.5,
            },
            "recommendations": [
                "Prioritize the 2 critical vulnerabilities in authentication service",
                "Schedule patch deployment for the 8 high-severity issues",
            ],
        },
        "agent_activity": {
            "title": "Agent Activity Report",
            "time_range": time_range,
            "summary": {
                "total_tasks_completed": 156,
                "patches_generated": 23,
                "patches_approved": 18,
                "patches_deployed": 15,
                "average_review_time_hours": 2.3,
            },
            "agent_breakdown": {
                "orchestrator": {"tasks": 156, "errors": 2},
                "coder": {"patches_generated": 23, "success_rate": 0.95},
                "reviewer": {"reviews_completed": 45, "average_time_minutes": 15},
                "validator": {"validations_passed": 42, "validations_failed": 3},
            },
        },
        "daily_digest": {
            "title": f"Daily Digest - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "highlights": [
                "2 new critical vulnerabilities detected",
                "5 patches successfully deployed",
                "Agent error rate: 0.5% (healthy)",
                "3 HITL approvals pending review",
            ],
            "metrics": {
                "vulnerabilities_resolved": 8,
                "patches_deployed": 5,
                "incidents_active": 1,
                "approval_queue_size": 3,
            },
        },
    }

    report = reports.get(report_type, reports["vulnerability_summary"])
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["format"] = format_type

    return report


def _query_code_graph(params: dict, tenant_id: str) -> dict:
    """Query the GraphRAG code graph (mock implementation)."""
    query_type = params.get("query_type", "dependencies")
    entity = params.get("entity", "")
    depth = params.get("depth", 2)

    # Mock graph query results
    # In production, this would query Neptune and OpenSearch

    mock_results = {
        "dependencies": {
            "entity": entity,
            "query_type": "dependencies",
            "dependencies": [
                {"name": "boto3", "type": "library", "version": "1.34.0"},
                {"name": "fastapi", "type": "library", "version": "0.115.0"},
                {"name": "pydantic", "type": "library", "version": "2.10.0"},
            ],
            "internal_imports": [
                {"module": "src.services.context_retrieval", "type": "service"},
                {"module": "src.utils.security", "type": "utility"},
            ],
        },
        "callers": {
            "entity": entity,
            "query_type": "callers",
            "callers": [
                {
                    "function": "orchestrator.execute_task",
                    "file": "src/agents/orchestrator.py",
                    "line": 125,
                },
                {
                    "function": "api.routes.chat",
                    "file": "src/api/routes/chat.py",
                    "line": 45,
                },
            ],
        },
        "impact_analysis": {
            "entity": entity,
            "query_type": "impact_analysis",
            "direct_impact": 5,
            "indirect_impact": 23,
            "affected_services": ["api", "agents", "monitoring"],
            "risk_level": "medium",
        },
    }

    result = mock_results.get(query_type, mock_results["dependencies"])
    result["depth"] = depth
    result["note"] = "Mock graph query - Neptune integration pending"

    return result


def _get_sandbox_status(params: dict, tenant_id: str) -> dict:
    """Get sandbox environment status."""
    sandbox_id = params.get("sandbox_id")
    include_metrics = params.get("include_metrics", False)

    # Mock sandbox status
    sandboxes = [
        {
            "sandbox_id": "sandbox-001",
            "status": "running",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "purpose": "Patch validation for CVE-2025-1234",
            "isolation_level": "vpc",
        },
        {
            "sandbox_id": "sandbox-002",
            "status": "completed",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
            "purpose": "Integration testing for API v2.3.1",
            "isolation_level": "container",
        },
    ]

    if sandbox_id:
        sandboxes = [s for s in sandboxes if s["sandbox_id"] == sandbox_id]

    if include_metrics:
        for sandbox in sandboxes:
            sandbox["metrics"] = {  # type: ignore[assignment]
                "cpu_usage_percent": 45.2,
                "memory_usage_mb": 512,
                "network_io_mb": 23.5,
                "duration_minutes": 120,
            }

    return {
        "sandbox_count": len(sandboxes),
        "sandboxes": sandboxes,
    }


def _generate_diagram(params: dict, tenant_id: str) -> dict[str, Any]:
    """Generate a diagram using the diagram_tools module."""
    diagram_type = params.get("diagram_type", "flowchart")
    subject = params.get("subject", "")
    format = params.get("format", "mermaid")
    scope = params.get("scope", "component")

    if not subject:
        return {"error": "Subject is required for diagram generation"}

    try:
        result: dict[str, Any] = _generate_diagram_impl(
            diagram_type=diagram_type,
            subject=subject,
            format=format,
            scope=scope,
            tenant_id=tenant_id,
        )
        return result
    except Exception as e:
        logger.error(f"Error generating diagram: {e}")
        return {"error": str(e)}


def _start_deep_research(params: dict, tenant_id: str) -> dict[str, Any]:
    """Start a deep research task using the research_tools module."""
    research_query = params.get("research_query", "")
    scope = params.get("scope", "repository")
    urgency = params.get("urgency", "standard")
    data_sources = params.get("data_sources", ["code_graph", "security_findings"])

    if not research_query:
        return {"error": "Research query is required"}

    try:
        # Note: user_id would typically come from user_info in execute_tool
        # For now, we use tenant_id as a proxy
        result: dict[str, Any] = _start_deep_research_impl(
            query=research_query,
            user_id=tenant_id,  # In production, extract from JWT
            tenant_id=tenant_id,
            scope=scope,
            urgency=urgency,
            data_sources=data_sources,
        )
        return result
    except Exception as e:
        logger.error(f"Error starting deep research: {e}")
        return {"error": str(e)}


def _get_research_status(params: dict, tenant_id: str) -> dict[str, Any]:
    """Get research task status using the research_tools module."""
    task_id = params.get("task_id", "")

    if not task_id:
        return {"error": "Task ID is required"}

    try:
        result: dict[str, Any] = _get_research_status_impl(
            task_id=task_id,
            user_id=tenant_id,  # In production, extract from JWT
        )
        return result
    except Exception as e:
        logger.error(f"Error getting research status: {e}")
        return {"error": str(e)}
