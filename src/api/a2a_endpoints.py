"""
Project Aura - A2A Protocol API Endpoints (ADR-028 Phase 6)

FastAPI endpoints for the A2A (Agent-to-Agent) protocol, enabling:
- Agent Card discovery (.well-known/agent.json)
- JSON-RPC 2.0 task management
- Agent registry operations
- Health and metrics endpoints

IMPORTANT: These endpoints are ONLY available in ENTERPRISE mode.
Defense/GovCloud deployments return 403 Forbidden for all A2A operations.

Endpoints:
- GET  /.well-known/agent.json - Agent Card discovery
- POST /a2a/jsonrpc           - JSON-RPC 2.0 endpoint
- GET  /a2a/agents            - List registered agents
- POST /a2a/agents            - Register external agent
- GET  /a2a/agents/{id}       - Get agent details
- DELETE /a2a/agents/{id}     - Unregister agent
- GET  /a2a/tasks/{id}        - Get task status
- POST /a2a/notifications     - Receive push notifications
- GET  /a2a/health            - A2A subsystem health
- GET  /a2a/metrics           - A2A metrics

Author: Project Aura Team
Created: 2025-12-07
Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.config import get_integration_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["A2A Protocol"])


# =============================================================================
# Dependencies
# =============================================================================


def get_a2a_gateway():
    """
    Dependency to get the A2A gateway instance.

    Raises HTTPException 403 if not in ENTERPRISE mode.
    """
    config = get_integration_config()

    if config.is_defense_mode:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "A2A protocol not available",
                "message": "A2A protocol is disabled in DEFENSE mode for security. "
                "This deployment does not support cross-platform agent communication.",
                "mode": config.mode.value,
            },
        )

    if not config.a2a_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "A2A not enabled",
                "message": "A2A protocol is not enabled. Set AURA_A2A_ENABLED=true to enable.",
            },
        )

    # Import here to avoid circular imports and defense mode instantiation
    from src.services.a2a_gateway import A2AGateway

    # In production, use singleton pattern with dependency injection
    return A2AGateway(config=config)


def get_agent_registry():
    """
    Dependency to get the A2A agent registry instance.

    Raises HTTPException 403 if not in ENTERPRISE mode.
    """
    config = get_integration_config()

    if config.is_defense_mode:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Agent registry not available",
                "message": "Agent registry is disabled in DEFENSE mode.",
            },
        )

    from src.services.a2a_agent_registry import A2AAgentRegistry

    return A2AAgentRegistry(config=config)


# =============================================================================
# Request/Response Models
# =============================================================================


class CapabilityModel(BaseModel):
    """Agent capability model."""

    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    streaming_supported: bool = False


class AgentCardModel(BaseModel):
    """Agent Card model for registration."""

    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent display name")
    description: str = Field(..., description="Agent description")
    endpoint: str = Field(..., description="Agent A2A endpoint URL")
    provider: str = Field(default="external", description="Agent provider")
    capabilities: list[CapabilityModel] = Field(default_factory=list)
    version: str = Field(default="1.0.0")
    documentation_url: str | None = None
    support_email: str | None = None


class AgentRegistrationRequest(BaseModel):
    """Request to register an external agent."""

    agent_card: AgentCardModel = Field(..., description="Agent Card")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")
    verify: bool = Field(default=True, description="Verify agent endpoint")


class AgentRegistrationResponse(BaseModel):
    """Response from agent registration."""

    registration_id: str
    agent_id: str
    status: str
    trust_level: str
    registered_at: str
    message: str


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: str = Field(default="2.0")
    method: str = Field(..., description="Method name")
    params: dict[str, Any] = Field(default_factory=dict)
    id: str | None = Field(default=None, description="Request ID")


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    id: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class TaskStatusResponse(BaseModel):
    """Task status response."""

    task_id: str
    status: str
    status_message: str
    capability_name: str
    created_at: str
    updated_at: str
    completed_at: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class PushNotificationRequest(BaseModel):
    """Push notification from external agent."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any]


class A2AHealthResponse(BaseModel):
    """A2A subsystem health response."""

    status: str
    a2a_enabled: bool
    integration_mode: str
    gateway_status: str
    registry_status: str
    timestamp: str


class A2AMetricsResponse(BaseModel):
    """A2A metrics response."""

    gateway: dict[str, Any]
    registry: dict[str, Any]
    timestamp: str


# =============================================================================
# Agent Discovery Endpoints
# =============================================================================


@router.get(
    "/.well-known/agent.json",
    response_model=dict[str, Any],
    summary="Agent Card Discovery",
    description="Returns the Agent Card for Aura's agents per A2A specification",
)
async def get_agent_card(
    agent_id: str | None = Query(None, description="Specific agent ID"),  # noqa: B008
    gateway=Depends(get_a2a_gateway),  # noqa: B008
):
    """
    Get Agent Card(s) for A2A discovery.

    This endpoint follows the A2A specification for agent discovery.
    External agents can use this to discover Aura's capabilities.
    """
    if agent_id:
        card = gateway.get_local_agent_card(agent_id)
        if not card:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {agent_id}",
            )
        return card.to_dict()

    # Return all agent cards
    cards = gateway.list_local_agent_cards()
    return {
        "protocol_version": "1.0",
        "provider": "aenealabs",
        "agents": [card.to_dict() for card in cards],
    }


# =============================================================================
# JSON-RPC Endpoint
# =============================================================================


@router.post(
    "/a2a/jsonrpc",
    response_model=JsonRpcResponse,
    summary="JSON-RPC 2.0 Endpoint",
    description="Handle A2A JSON-RPC 2.0 requests for task management",
)
async def jsonrpc_endpoint(
    request: JsonRpcRequest,
    gateway=Depends(get_a2a_gateway),  # noqa: B008
):
    """
    Handle JSON-RPC 2.0 requests per A2A protocol.

    Supported methods:
    - tasks/send: Submit a new task
    - tasks/get: Get task status
    - tasks/cancel: Cancel a task
    - agent_card_request: Get agent cards
    """
    response = await gateway.handle_jsonrpc_request(request.model_dump())
    return JsonRpcResponse(**response.to_dict())


# =============================================================================
# Agent Registry Endpoints
# =============================================================================


@router.get(
    "/a2a/agents",
    response_model=list[dict[str, Any]],
    summary="List Registered Agents",
    description="List all agents registered in the A2A registry",
)
async def list_agents(
    status: str | None = Query(None, description="Filter by status"),  # noqa: B008
    limit: int = Query(100, ge=1, le=500),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """List registered external agents."""
    from src.services.a2a_agent_registry import AgentStatus

    status_filter = None
    if status:
        try:
            status_filter = AgentStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in AgentStatus]}",
            )

    agents = await registry.list_agents(
        status=status_filter, limit=limit, offset=offset
    )
    return [a.to_dict() for a in agents]


@router.post(
    "/a2a/agents",
    response_model=AgentRegistrationResponse,
    status_code=201,
    summary="Register External Agent",
    description="Register a new external A2A-compatible agent",
)
async def register_agent(
    request: AgentRegistrationRequest,
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """
    Register an external A2A-compatible agent.

    The agent will be verified (if requested) and added to the registry
    for task routing and capability matching.
    """
    from src.services.a2a_gateway import AgentCapability, AgentCard

    # Convert request to AgentCard
    agent_card = AgentCard(
        agent_id=request.agent_card.agent_id,
        name=request.agent_card.name,
        description=request.agent_card.description,
        endpoint=request.agent_card.endpoint,
        provider=request.agent_card.provider,
        version=request.agent_card.version,
        documentation_url=request.agent_card.documentation_url,
        support_email=request.agent_card.support_email,
        capabilities=[
            AgentCapability(
                name=cap.name,
                description=cap.description,
                input_schema=cap.input_schema,
                output_schema=cap.output_schema,
                streaming_supported=cap.streaming_supported,
            )
            for cap in request.agent_card.capabilities
        ],
    )

    registration = await registry.register_agent(
        agent_card=agent_card,
        tags=request.tags,
        verify=request.verify,
    )

    return AgentRegistrationResponse(
        registration_id=registration.registration_id,
        agent_id=registration.agent_id,
        status=registration.status.value,
        trust_level=registration.trust_level.value,
        registered_at=registration.registered_at.isoformat(),
        message="Agent registered successfully",
    )


@router.get(
    "/a2a/agents/{agent_id}",
    response_model=dict[str, Any],
    summary="Get Agent Details",
    description="Get details for a specific registered agent",
)
async def get_agent(
    agent_id: str,
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """Get details for a registered agent."""
    agent = await registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )
    return agent.to_dict()


@router.delete(
    "/a2a/agents/{agent_id}",
    status_code=204,
    summary="Unregister Agent",
    description="Remove an agent from the registry",
)
async def unregister_agent(
    agent_id: str,
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """Unregister an agent from the registry."""
    success = await registry.unregister_agent(agent_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )


@router.post(
    "/a2a/agents/search",
    response_model=list[dict[str, Any]],
    summary="Search Agents",
    description="Search for agents matching capability and other criteria",
)
async def search_agents(
    capability: str | None = Query(None, description="Capability name"),  # noqa: B008
    provider: str | None = Query(None, description="Provider name"),  # noqa: B008
    status: str | None = Query(None, description="Agent status"),  # noqa: B008
    min_success_rate: float = Query(0.0, ge=0.0, le=1.0),  # noqa: B008
    tags: list[str] = Query(default=[]),  # noqa: B008
    limit: int = Query(10, ge=1, le=100),  # noqa: B008
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """
    Search for agents matching criteria.

    This is useful for finding agents that can handle specific capabilities
    with desired quality metrics.
    """
    from src.services.a2a_agent_registry import AgentSearchCriteria, AgentStatus

    status_filter = None
    if status:
        try:
            status_filter = AgentStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}",
            )

    criteria = AgentSearchCriteria(
        capability_name=capability,
        provider=provider,
        status=status_filter,
        min_success_rate=min_success_rate,
        tags=tags,
        limit=limit,
    )

    agents = await registry.search_agents(criteria)
    return [a.to_dict() for a in agents]


# =============================================================================
# Task Endpoints
# =============================================================================


@router.get(
    "/a2a/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get Task Status",
    description="Get the status of an A2A task",
)
async def get_task_status(
    task_id: str,
    gateway=Depends(get_a2a_gateway),  # noqa: B008
):
    """Get the status of an A2A task."""
    task = await gateway.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}",
        )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        status_message=task.status_message,
        capability_name=task.capability_name,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        output=task.output_data,
        artifacts=[a.to_dict() for a in task.artifacts],
    )


@router.post(
    "/a2a/tasks/{task_id}/cancel",
    response_model=dict[str, Any],
    summary="Cancel Task",
    description="Cancel an in-progress A2A task",
)
async def cancel_task(
    task_id: str,
    reason: str = Query("", description="Cancellation reason"),  # noqa: B008
    gateway=Depends(get_a2a_gateway),  # noqa: B008
):
    """Cancel an A2A task."""
    task = await gateway.cancel_task(task_id, reason)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}",
        )

    return {
        "task_id": task_id,
        "status": "canceled",
        "message": reason or "Task canceled",
    }


# =============================================================================
# Push Notifications
# =============================================================================


@router.post(
    "/a2a/notifications",
    status_code=202,
    summary="Receive Push Notification",
    description="Receive push notifications from external agents",
)
async def receive_notification(
    notification: PushNotificationRequest,
    gateway=Depends(get_a2a_gateway),  # noqa: B008
):
    """
    Receive push notifications from external agents.

    External agents send status updates here when tasks complete.
    """
    logger.info(
        f"Received push notification: method={notification.method}, "
        f"params={notification.params}"
    )

    # Process notification based on method
    method = notification.method
    params = notification.params

    if method == "tasks/statusUpdate":
        task_id = params.get("task_id")
        status = params.get("status")
        _message = params.get("message", "")  # noqa: F841

        logger.info(
            f"Task status update from external agent: "
            f"task_id={task_id}, status={status}"
        )

        # TODO: Update local tracking of external tasks

    return {"status": "accepted"}


# =============================================================================
# Health & Metrics
# =============================================================================


@router.get(
    "/a2a/health",
    response_model=A2AHealthResponse,
    summary="A2A Health Check",
    description="Health check for A2A subsystem",
)
async def a2a_health():
    """
    Check health of A2A subsystem.

    Returns status even if A2A is disabled (to enable monitoring).
    """
    config = get_integration_config()

    gateway_status = "disabled"
    registry_status = "disabled"

    if config.is_enterprise_mode and config.a2a_enabled:
        gateway_status = "healthy"
        registry_status = "healthy"
    elif config.is_enterprise_mode:
        gateway_status = "not_enabled"
        registry_status = "not_enabled"

    return A2AHealthResponse(
        status="healthy" if config.a2a_enabled else "disabled",
        a2a_enabled=config.a2a_enabled,
        integration_mode=config.mode.value,
        gateway_status=gateway_status,
        registry_status=registry_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/a2a/metrics",
    response_model=A2AMetricsResponse,
    summary="A2A Metrics",
    description="Get A2A subsystem metrics",
)
async def a2a_metrics(
    gateway=Depends(get_a2a_gateway),  # noqa: B008
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """Get A2A subsystem metrics."""
    return A2AMetricsResponse(
        gateway=gateway.get_metrics(),
        registry=registry.get_metrics(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# Capability Discovery
# =============================================================================


@router.get(
    "/a2a/capabilities",
    response_model=list[dict[str, Any]],
    summary="List All Capabilities",
    description="List all capabilities available across registered agents",
)
async def list_capabilities(
    include_local: bool = Query(  # noqa: B008
        True, description="Include local Aura agents"
    ),  # noqa: B008
    include_external: bool = Query(  # noqa: B008
        True, description="Include external agents"
    ),  # noqa: B008
    gateway=Depends(get_a2a_gateway),  # noqa: B008
    registry=Depends(get_agent_registry),  # noqa: B008
):
    """
    List all capabilities available in the system.

    Useful for discovering what operations can be performed
    across all registered agents.
    """
    capabilities = []
    seen = set()

    # Local agent capabilities
    if include_local:
        for card in gateway.list_local_agent_cards():
            for cap in card.capabilities:
                if cap.name not in seen:
                    capabilities.append(
                        {
                            "name": cap.name,
                            "description": cap.description,
                            "agent_id": card.agent_id,
                            "agent_name": card.name,
                            "provider": card.provider,
                            "is_local": True,
                            "streaming_supported": cap.streaming_supported,
                        }
                    )
                    seen.add(cap.name)

    # External agent capabilities
    if include_external:
        agents = await registry.list_agents(limit=1000)
        for agent in agents:
            for cap in agent.capabilities:
                cap_key = f"{agent.agent_id}:{cap.name}"
                if cap_key not in seen:
                    capabilities.append(
                        {
                            "name": cap.name,
                            "description": cap.description,
                            "agent_id": agent.agent_id,
                            "agent_name": agent.agent_card.name,
                            "provider": agent.agent_card.provider,
                            "is_local": False,
                            "streaming_supported": cap.streaming_supported,
                        }
                    )
                    seen.add(cap_key)

    return capabilities
