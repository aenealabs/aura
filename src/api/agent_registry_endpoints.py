"""
Project Aura - Agent Registry UI Endpoints (GitHub Issue #35)

FastAPI endpoints for the Agent Registry and Marketplace UI, enabling:
- View internal Aura agents (Orchestrator, Coder, Reviewer, Validator)
- View and manage external A2A-connected agents
- Browse marketplace of available agents to connect
- Agent configuration and metrics

Routes:
- GET  /api/v1/agents                      - List all agents (internal + external)
- GET  /api/v1/agents/internal             - List internal Aura agents
- GET  /api/v1/agents/external             - List external A2A agents
- GET  /api/v1/agents/marketplace          - List available marketplace agents
- GET  /api/v1/agents/{agent_id}           - Get agent details
- POST /api/v1/agents/connect              - Connect external agent
- DELETE /api/v1/agents/{agent_id}         - Disconnect external agent
- PUT  /api/v1/agents/{agent_id}/config    - Update agent configuration
- GET  /api/v1/agents/{agent_id}/metrics   - Get agent metrics
- POST /api/v1/agents/{agent_id}/test      - Test agent connection

Author: Project Aura Team
Created: 2025-12-08
Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Registry"])


# =============================================================================
# Enums
# =============================================================================


class AgentType(str, Enum):
    """Type of agent."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    MARKETPLACE = "marketplace"


class AgentStatus(str, Enum):
    """Status of an agent."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    PENDING = "pending"
    SUSPENDED = "suspended"


class TrustLevel(str, Enum):
    """Trust level for agents."""

    VERIFIED = "verified"
    TRUSTED = "trusted"
    STANDARD = "standard"
    UNTRUSTED = "untrusted"


# =============================================================================
# Request/Response Models
# =============================================================================


class AgentCapability(BaseModel):
    """Agent capability definition."""

    name: str = Field(..., description="Capability identifier")
    description: str = Field("", description="Capability description")
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class AgentMetrics(BaseModel):
    """Agent usage metrics."""

    requests_today: int = 0
    requests_total: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    last_request_at: str | None = None


class InternalAgentResponse(BaseModel):
    """Internal Aura agent response."""

    agent_id: str
    name: str
    description: str
    agent_type: AgentType = AgentType.INTERNAL
    status: AgentStatus
    capabilities: list[str]
    metrics: AgentMetrics
    version: str = "1.0.0"
    created_at: str


class ExternalAgentResponse(BaseModel):
    """External A2A-connected agent response."""

    agent_id: str
    name: str
    description: str
    agent_type: AgentType = AgentType.EXTERNAL
    status: AgentStatus
    trust_level: TrustLevel
    capabilities: list[str]
    provider: str
    endpoint: str
    protocol_version: str = "1.0"
    metrics: AgentMetrics
    connected_at: str
    last_health_check: str | None = None


class MarketplaceAgentResponse(BaseModel):
    """Marketplace agent available for connection."""

    agent_id: str
    name: str
    description: str
    agent_type: AgentType = AgentType.MARKETPLACE
    provider: str
    capabilities: list[str]
    protocol_version: str = "1.0"
    verified: bool = False
    documentation_url: str | None = None
    pricing_tier: str = "free"


class ConnectAgentRequest(BaseModel):
    """Request to connect an external agent."""

    agent_id: str = Field(..., description="Marketplace agent ID to connect")
    endpoint: str = Field(..., description="Agent A2A endpoint URL")
    api_key: str | None = Field(None, description="API key if required")
    custom_config: dict[str, Any] = Field(default_factory=dict)


class ConnectAgentResponse(BaseModel):
    """Response after connecting an agent."""

    agent_id: str
    status: AgentStatus
    trust_level: TrustLevel
    message: str
    connected_at: str


class UpdateConfigRequest(BaseModel):
    """Request to update agent configuration."""

    enabled: bool | None = None
    rate_limit_per_minute: int | None = None
    timeout_ms: int | None = None
    priority: int | None = None
    custom_config: dict[str, Any] = Field(default_factory=dict)


class TestConnectionResponse(BaseModel):
    """Response from testing agent connection."""

    agent_id: str
    status: str
    latency_ms: float
    message: str
    tested_at: str


class AgentListResponse(BaseModel):
    """Response for agent list endpoints."""

    agents: list[dict[str, Any]]
    total: int
    internal_count: int
    external_count: int
    pending_count: int


# =============================================================================
# Mock Data Store (In production, use DynamoDB + A2A Registry)
# =============================================================================


# Internal Aura agents (always present)
_INTERNAL_AGENTS: dict[str, dict[str, Any]] = {
    "aura-orchestrator": {
        "agent_id": "aura-orchestrator",
        "name": "MetaOrchestrator Agent",
        "description": "Coordinates multi-agent workflows, routes tasks to specialized agents, and manages execution flow.",
        "status": AgentStatus.ACTIVE,
        "capabilities": ["orchestrate", "route", "coordinate", "monitor"],
        "version": "1.0.0",
        "created_at": "2025-01-01T00:00:00Z",
        "metrics": {
            "requests_today": 1247,
            "requests_total": 45230,
            "avg_latency_ms": 45.2,
            "success_rate": 0.998,
            "last_request_at": None,
        },
    },
    "aura-coder": {
        "agent_id": "aura-coder",
        "name": "Coder Agent",
        "description": "Generates security patches, refactors code, and implements fixes based on vulnerability analysis.",
        "status": AgentStatus.ACTIVE,
        "capabilities": [
            "generate_patch",
            "refactor_code",
            "explain_code",
            "implement_fix",
        ],
        "version": "1.0.0",
        "created_at": "2025-01-01T00:00:00Z",
        "metrics": {
            "requests_today": 890,
            "requests_total": 28450,
            "avg_latency_ms": 2100.0,
            "success_rate": 0.945,
            "last_request_at": None,
        },
    },
    "aura-reviewer": {
        "agent_id": "aura-reviewer",
        "name": "Reviewer Agent",
        "description": "Performs security code review, validates patches, and assesses vulnerability fixes.",
        "status": AgentStatus.ACTIVE,
        "capabilities": [
            "review_code",
            "validate_patch",
            "security_scan",
            "assess_risk",
        ],
        "version": "1.0.0",
        "created_at": "2025-01-01T00:00:00Z",
        "metrics": {
            "requests_today": 756,
            "requests_total": 22100,
            "avg_latency_ms": 1800.0,
            "success_rate": 0.967,
            "last_request_at": None,
        },
    },
    "aura-validator": {
        "agent_id": "aura-validator",
        "name": "Validator Agent",
        "description": "Runs tests in sandbox environments, verifies patch correctness, and validates security fixes.",
        "status": AgentStatus.ACTIVE,
        "capabilities": [
            "run_tests",
            "verify_patch",
            "sandbox_execute",
            "validate_security",
        ],
        "version": "1.0.0",
        "created_at": "2025-01-01T00:00:00Z",
        "metrics": {
            "requests_today": 445,
            "requests_total": 15670,
            "avg_latency_ms": 3200.0,
            "success_rate": 0.989,
            "last_request_at": None,
        },
    },
}

# External connected agents (mock data)
_EXTERNAL_AGENTS: dict[str, dict[str, Any]] = {
    "foundry-research": {
        "agent_id": "foundry-research",
        "name": "Microsoft Foundry Research Agent",
        "description": "Deep research capabilities for codebase analysis and security research.",
        "status": AgentStatus.ACTIVE,
        "trust_level": TrustLevel.VERIFIED,
        "capabilities": ["deep_research", "web_search", "summarize", "analyze"],
        "provider": "Microsoft",
        "endpoint": "https://foundry.azure.com/a2a",
        "protocol_version": "1.0",
        "connected_at": "2025-12-01T10:30:00Z",
        "last_health_check": "2025-12-08T14:00:00Z",
        "metrics": {
            "requests_today": 45,
            "requests_total": 890,
            "avg_latency_ms": 2100.0,
            "success_rate": 0.978,
            "last_request_at": None,
        },
    },
    "langgraph-planner": {
        "agent_id": "langgraph-planner",
        "name": "LangGraph Task Planner",
        "description": "Multi-step task planning and decomposition using LangGraph workflows.",
        "status": AgentStatus.ACTIVE,
        "trust_level": TrustLevel.TRUSTED,
        "capabilities": ["plan", "decompose", "sequence", "optimize"],
        "provider": "LangChain",
        "endpoint": "https://api.langchain.com/a2a",
        "protocol_version": "1.0",
        "connected_at": "2025-12-03T15:45:00Z",
        "last_health_check": "2025-12-08T14:00:00Z",
        "metrics": {
            "requests_today": 23,
            "requests_total": 456,
            "avg_latency_ms": 1500.0,
            "success_rate": 0.991,
            "last_request_at": None,
        },
    },
}

# Marketplace agents available for connection
_MARKETPLACE_AGENTS: list[dict[str, Any]] = [
    {
        "agent_id": "snyk-scanner",
        "name": "Snyk Security Scanner",
        "description": "Real-time vulnerability detection for dependencies and container images.",
        "provider": "Snyk",
        "capabilities": [
            "scan_vulnerabilities",
            "dependency_check",
            "container_scan",
            "report",
        ],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://docs.snyk.io/a2a",
        "pricing_tier": "enterprise",
    },
    {
        "agent_id": "datadog-apm",
        "name": "Datadog APM Agent",
        "description": "Application performance monitoring and distributed tracing integration.",
        "provider": "Datadog",
        "capabilities": ["trace", "monitor", "alert", "analyze_performance"],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://docs.datadoghq.com/a2a",
        "pricing_tier": "enterprise",
    },
    {
        "agent_id": "sonarqube-analyzer",
        "name": "SonarQube Code Analyzer",
        "description": "Continuous code quality inspection and static analysis.",
        "provider": "SonarSource",
        "capabilities": [
            "analyze_code",
            "detect_bugs",
            "code_smells",
            "security_hotspots",
        ],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://docs.sonarqube.org/a2a",
        "pricing_tier": "enterprise",
    },
    {
        "agent_id": "github-copilot",
        "name": "GitHub Copilot Agent",
        "description": "AI-powered code completion and suggestion integration.",
        "provider": "GitHub",
        "capabilities": ["suggest_code", "complete", "explain", "generate_tests"],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://docs.github.com/copilot/a2a",
        "pricing_tier": "enterprise",
    },
    {
        "agent_id": "aws-codewhisperer",
        "name": "AWS CodeWhisperer Agent",
        "description": "ML-powered code recommendations trained on Amazon and open-source code.",
        "provider": "AWS",
        "capabilities": ["suggest_code", "security_scan", "reference_tracking"],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://aws.amazon.com/codewhisperer/a2a",
        "pricing_tier": "free",
    },
    {
        "agent_id": "semgrep-sast",
        "name": "Semgrep SAST Agent",
        "description": "Fast, customizable static analysis for finding bugs and enforcing code standards.",
        "provider": "Semgrep",
        "capabilities": ["sast_scan", "custom_rules", "autofix", "ci_integration"],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://semgrep.dev/docs/a2a",
        "pricing_tier": "free",
    },
    {
        "agent_id": "trivy-scanner",
        "name": "Trivy Security Scanner",
        "description": "Comprehensive vulnerability scanner for containers, filesystems, and Git repositories.",
        "provider": "Aqua Security",
        "capabilities": [
            "container_scan",
            "filesystem_scan",
            "sbom_generate",
            "license_check",
        ],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://aquasecurity.github.io/trivy/a2a",
        "pricing_tier": "free",
    },
    {
        "agent_id": "checkmarx-sast",
        "name": "Checkmarx SAST Agent",
        "description": "Enterprise static application security testing with compliance reporting.",
        "provider": "Checkmarx",
        "capabilities": [
            "sast_scan",
            "compliance_report",
            "risk_scoring",
            "remediation",
        ],
        "protocol_version": "1.0",
        "verified": True,
        "documentation_url": "https://checkmarx.com/docs/a2a",
        "pricing_tier": "enterprise",
    },
]


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=AgentListResponse,
    summary="List All Agents",
    description="List all agents including internal Aura agents and external A2A agents",
)
async def list_all_agents(
    agent_type: AgentType | None = Query(  # noqa: B008
        None, description="Filter by agent type"
    ),  # noqa: B008
    status: AgentStatus | None = Query(  # noqa: B008
        None, description="Filter by status"
    ),  # noqa: B008
    capability: str | None = Query(  # noqa: B008
        None, description="Filter by capability"
    ),  # noqa: B008
    search: str | None = Query(None, description="Search by name"),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
):
    """List all registered agents."""
    agents = []

    # Add internal agents
    if agent_type is None or agent_type == AgentType.INTERNAL:
        for agent in _INTERNAL_AGENTS.values():
            if _matches_filters(agent, status, capability, search, is_internal=True):
                agents.append({**agent, "agent_type": AgentType.INTERNAL})

    # Add external agents
    if agent_type is None or agent_type == AgentType.EXTERNAL:
        for agent in _EXTERNAL_AGENTS.values():
            if _matches_filters(agent, status, capability, search, is_internal=False):
                agents.append({**agent, "agent_type": AgentType.EXTERNAL})

    # Calculate counts
    internal_count = len(
        [a for a in agents if a.get("agent_type") == AgentType.INTERNAL]
    )
    external_count = len(
        [a for a in agents if a.get("agent_type") == AgentType.EXTERNAL]
    )
    pending_count = len([a for a in agents if a.get("status") == AgentStatus.PENDING])

    # Paginate
    total = len(agents)
    agents = agents[offset : offset + limit]

    return AgentListResponse(
        agents=agents,
        total=total,
        internal_count=internal_count,
        external_count=external_count,
        pending_count=pending_count,
    )


@router.get(
    "/internal",
    response_model=list[dict[str, Any]],
    summary="List Internal Agents",
    description="List internal Aura agents (Orchestrator, Coder, Reviewer, Validator)",
)
async def list_internal_agents():
    """List internal Aura agents."""
    agents = []
    for agent in _INTERNAL_AGENTS.values():
        agents.append(
            {
                **agent,
                "agent_type": AgentType.INTERNAL,
                "metrics": AgentMetrics(**agent["metrics"]).model_dump(),
            }
        )
    return agents


@router.get(
    "/external",
    response_model=list[dict[str, Any]],
    summary="List External Agents",
    description="List connected external A2A agents",
)
async def list_external_agents(
    status: AgentStatus | None = Query(  # noqa: B008
        None, description="Filter by status"
    ),  # noqa: B008
):
    """List external A2A-connected agents."""
    agents = []
    for agent in _EXTERNAL_AGENTS.values():
        if status is None or agent.get("status") == status:
            agents.append(
                {
                    **agent,
                    "agent_type": AgentType.EXTERNAL,
                    "metrics": AgentMetrics(**agent["metrics"]).model_dump(),
                }
            )
    return agents


@router.get(
    "/marketplace",
    response_model=list[MarketplaceAgentResponse],
    summary="List Marketplace Agents",
    description="List available agents in the marketplace for connection",
)
async def list_marketplace_agents(
    provider: str | None = Query(None, description="Filter by provider"),  # noqa: B008
    capability: str | None = Query(  # noqa: B008
        None, description="Filter by capability"
    ),  # noqa: B008
    verified_only: bool = Query(  # noqa: B008
        False, description="Only show verified agents"
    ),  # noqa: B008
    pricing_tier: str | None = Query(  # noqa: B008
        None, description="Filter by pricing tier"
    ),  # noqa: B008
):
    """List agents available in the marketplace."""
    agents = []

    for agent in _MARKETPLACE_AGENTS:
        # Skip if already connected
        if agent["agent_id"] in _EXTERNAL_AGENTS:
            continue

        # Apply filters
        if provider and agent["provider"].lower() != provider.lower():
            continue
        if capability and capability not in agent["capabilities"]:
            continue
        if verified_only and not agent.get("verified", False):
            continue
        if pricing_tier and agent.get("pricing_tier") != pricing_tier:
            continue

        agents.append(
            MarketplaceAgentResponse(
                agent_id=agent["agent_id"],
                name=agent["name"],
                description=agent["description"],
                provider=agent["provider"],
                capabilities=agent["capabilities"],
                protocol_version=agent["protocol_version"],
                verified=agent.get("verified", False),
                documentation_url=agent.get("documentation_url"),
                pricing_tier=agent.get("pricing_tier", "free"),
            )
        )

    return agents


@router.get(
    "/{agent_id}",
    response_model=dict[str, Any],
    summary="Get Agent Details",
    description="Get detailed information about a specific agent",
)
async def get_agent(agent_id: str):
    """Get details for a specific agent."""
    # Check internal agents
    if agent_id in _INTERNAL_AGENTS:
        agent = _INTERNAL_AGENTS[agent_id]
        return {
            **agent,
            "agent_type": AgentType.INTERNAL,
            "metrics": AgentMetrics(**agent["metrics"]).model_dump(),
        }

    # Check external agents
    if agent_id in _EXTERNAL_AGENTS:
        agent = _EXTERNAL_AGENTS[agent_id]
        return {
            **agent,
            "agent_type": AgentType.EXTERNAL,
            "metrics": AgentMetrics(**agent["metrics"]).model_dump(),
        }

    # Check marketplace
    for agent in _MARKETPLACE_AGENTS:
        if agent["agent_id"] == agent_id:
            return {
                **agent,
                "agent_type": AgentType.MARKETPLACE,
            }

    raise HTTPException(
        status_code=404,
        detail=f"Agent not found: {agent_id}",
    )


@router.post(
    "/connect",
    response_model=ConnectAgentResponse,
    status_code=201,
    summary="Connect External Agent",
    description="Connect an agent from the marketplace",
)
async def connect_agent(request: ConnectAgentRequest):
    """Connect an external agent from the marketplace."""
    # Find in marketplace
    marketplace_agent = None
    for agent in _MARKETPLACE_AGENTS:
        if agent["agent_id"] == request.agent_id:
            marketplace_agent = agent
            break

    if not marketplace_agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found in marketplace: {request.agent_id}",
        )

    if request.agent_id in _EXTERNAL_AGENTS:
        raise HTTPException(
            status_code=409,
            detail=f"Agent already connected: {request.agent_id}",
        )

    # Determine trust level
    trust_level = (
        TrustLevel.VERIFIED
        if marketplace_agent.get("verified")
        else TrustLevel.STANDARD
    )

    now = datetime.now(timezone.utc).isoformat()

    # Add to external agents
    _EXTERNAL_AGENTS[request.agent_id] = {
        "agent_id": request.agent_id,
        "name": marketplace_agent["name"],
        "description": marketplace_agent["description"],
        "status": AgentStatus.PENDING,
        "trust_level": trust_level,
        "capabilities": marketplace_agent["capabilities"],
        "provider": marketplace_agent["provider"],
        "endpoint": request.endpoint,
        "protocol_version": marketplace_agent["protocol_version"],
        "connected_at": now,
        "last_health_check": None,
        "metrics": {
            "requests_today": 0,
            "requests_total": 0,
            "avg_latency_ms": 0.0,
            "success_rate": 1.0,
            "last_request_at": None,
        },
        "config": request.custom_config,
    }

    logger.info(
        f"Connected agent: {request.agent_id} from {marketplace_agent['provider']}"
    )

    return ConnectAgentResponse(
        agent_id=request.agent_id,
        status=AgentStatus.PENDING,
        trust_level=trust_level,
        message="Agent connected successfully. Verification in progress.",
        connected_at=now,
    )


@router.delete(
    "/{agent_id}",
    status_code=204,
    summary="Disconnect Agent",
    description="Disconnect an external agent",
)
async def disconnect_agent(agent_id: str):
    """Disconnect an external agent."""
    if agent_id in _INTERNAL_AGENTS:
        raise HTTPException(
            status_code=400,
            detail="Cannot disconnect internal agents",
        )

    if agent_id not in _EXTERNAL_AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )

    del _EXTERNAL_AGENTS[agent_id]
    logger.info(f"Disconnected agent: {agent_id}")


@router.put(
    "/{agent_id}/config",
    response_model=dict[str, Any],
    summary="Update Agent Configuration",
    description="Update configuration for an agent",
)
async def update_agent_config(agent_id: str, request: UpdateConfigRequest):
    """Update agent configuration."""
    if agent_id in _INTERNAL_AGENTS:
        agent = _INTERNAL_AGENTS[agent_id]
        # Internal agents have limited config options
        if request.enabled is not None:
            agent["status"] = (
                AgentStatus.ACTIVE if request.enabled else AgentStatus.SUSPENDED
            )
        return {**agent, "agent_type": AgentType.INTERNAL}

    if agent_id in _EXTERNAL_AGENTS:
        agent = _EXTERNAL_AGENTS[agent_id]
        if request.enabled is not None:
            agent["status"] = (
                AgentStatus.ACTIVE if request.enabled else AgentStatus.SUSPENDED
            )
        if request.custom_config:
            agent["config"] = {**agent.get("config", {}), **request.custom_config}
        return {**agent, "agent_type": AgentType.EXTERNAL}

    raise HTTPException(
        status_code=404,
        detail=f"Agent not found: {agent_id}",
    )


@router.get(
    "/{agent_id}/metrics",
    response_model=AgentMetrics,
    summary="Get Agent Metrics",
    description="Get usage metrics for an agent",
)
async def get_agent_metrics(agent_id: str):
    """Get metrics for a specific agent."""
    if agent_id in _INTERNAL_AGENTS:
        return AgentMetrics(**_INTERNAL_AGENTS[agent_id]["metrics"])

    if agent_id in _EXTERNAL_AGENTS:
        return AgentMetrics(**_EXTERNAL_AGENTS[agent_id]["metrics"])

    raise HTTPException(
        status_code=404,
        detail=f"Agent not found: {agent_id}",
    )


@router.post(
    "/{agent_id}/test",
    response_model=TestConnectionResponse,
    summary="Test Agent Connection",
    description="Test connection to an agent",
)
async def test_agent_connection(agent_id: str):
    """Test connection to an agent."""
    import random

    if agent_id in _INTERNAL_AGENTS:
        # Internal agents always respond
        return TestConnectionResponse(
            agent_id=agent_id,
            status="healthy",
            latency_ms=round(random.uniform(10, 50), 1),
            message="Internal agent responding normally",
            tested_at=datetime.now(timezone.utc).isoformat(),
        )

    if agent_id in _EXTERNAL_AGENTS:
        agent = _EXTERNAL_AGENTS[agent_id]
        # Simulate connection test
        latency = round(random.uniform(100, 2000), 1)
        success = random.random() > 0.1  # 90% success rate

        if success:
            agent["status"] = AgentStatus.ACTIVE
            agent["last_health_check"] = datetime.now(timezone.utc).isoformat()
            return TestConnectionResponse(
                agent_id=agent_id,
                status="healthy",
                latency_ms=latency,
                message=f"Connection successful to {agent['endpoint']}",
                tested_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            agent["status"] = AgentStatus.DEGRADED
            return TestConnectionResponse(
                agent_id=agent_id,
                status="degraded",
                latency_ms=latency,
                message="Connection timeout - agent may be experiencing issues",
                tested_at=datetime.now(timezone.utc).isoformat(),
            )

    raise HTTPException(
        status_code=404,
        detail=f"Agent not found: {agent_id}",
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _matches_filters(
    agent: dict[str, Any],
    status: AgentStatus | None,
    capability: str | None,
    search: str | None,
    is_internal: bool,
) -> bool:
    """Check if agent matches the given filters."""
    # Status filter
    if status is not None:
        agent_status = agent.get("status")
        if isinstance(agent_status, AgentStatus):
            if agent_status != status:
                return False
        elif agent_status != status.value:
            return False

    # Capability filter
    if capability:
        capabilities = agent.get("capabilities", [])
        if capability not in capabilities:
            return False

    # Search filter
    if search:
        search_lower = search.lower()
        name = agent.get("name", "").lower()
        description = agent.get("description", "").lower()
        if search_lower not in name and search_lower not in description:
            return False

    return True
