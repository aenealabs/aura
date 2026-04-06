"""
Project Aura - Support Ticketing API Endpoints

REST API endpoints for support ticketing integration.
Supports configurable ticketing providers (GitHub Issues, Zendesk, Linear, ServiceNow).
See ADR-046 for architecture details.

Endpoints:
- GET  /api/v1/ticketing/config           - Get ticketing configuration
- POST /api/v1/ticketing/config           - Save ticketing configuration
- PATCH /api/v1/ticketing/config          - Update ticketing configuration
- POST /api/v1/ticketing/test-connection  - Test provider connection
- GET  /api/v1/ticketing/providers        - Get available providers
- POST /api/v1/ticketing/tickets          - Create a ticket
- GET  /api/v1/ticketing/tickets          - List tickets
- GET  /api/v1/ticketing/tickets/{id}     - Get ticket by ID
- PATCH /api/v1/ticketing/tickets/{id}    - Update ticket
- POST /api/v1/ticketing/tickets/{id}/comments - Add comment
- POST /api/v1/ticketing/tickets/{id}/close    - Close ticket
- POST /api/v1/ticketing/tickets/{id}/reopen   - Reopen ticket
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.api_rate_limiter import admin_rate_limit, standard_rate_limit
from src.services.ticketing import (
from src.api.log_sanitizer import sanitize_log
    TicketCreate,
    TicketFilters,
    TicketingConnectorFactory,
    TicketPriority,
    TicketStatus,
    TicketUpdate,
    get_ticketing_connector,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/ticketing", tags=["Ticketing"])

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class TicketingConfigModel(BaseModel):
    """Ticketing provider configuration."""

    provider: Optional[str] = Field(
        default=None,
        description="Ticketing provider (github, zendesk, linear, servicenow)",
    )
    enabled: bool = Field(default=False, description="Enable ticketing integration")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )
    default_labels: List[str] = Field(
        default_factory=lambda: ["support", "aura"],
        description="Default labels for new tickets",
    )
    auto_assign: bool = Field(
        default=False, description="Auto-assign tickets to on-call"
    )
    last_tested_at: Optional[str] = Field(
        default=None, description="Last successful connection test timestamp"
    )


class TicketCreateModel(BaseModel):
    """Request model for creating a ticket."""

    title: str = Field(..., min_length=1, max_length=200, description="Ticket title")
    description: str = Field(..., min_length=1, description="Ticket description")
    priority: str = Field(
        default="medium",
        description="Priority level (low, medium, high, critical)",
    )
    labels: List[str] = Field(default_factory=list, description="Labels to apply")
    assignee: Optional[str] = Field(default=None, description="Assignee username")
    customer_id: Optional[str] = Field(default=None, description="Customer identifier")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TicketUpdateModel(BaseModel):
    """Request model for updating a ticket."""

    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    labels: Optional[List[str]] = Field(default=None)
    assignee: Optional[str] = Field(default=None)


class TicketCommentModel(BaseModel):
    """Request model for adding a comment."""

    comment: str = Field(..., min_length=1, description="Comment text")
    is_internal: bool = Field(
        default=False, description="Internal note (not visible to customer)"
    )


class TicketCloseModel(BaseModel):
    """Request model for closing a ticket."""

    resolution: Optional[str] = Field(default=None, description="Resolution summary")


class TicketReopenModel(BaseModel):
    """Request model for reopening a ticket."""

    reason: Optional[str] = Field(default=None, description="Reason for reopening")


class TestConnectionModel(BaseModel):
    """Request model for testing connection."""

    provider: str = Field(..., description="Provider to test")
    config: Dict[str, Any] = Field(..., description="Provider configuration")


class TicketResponse(BaseModel):
    """Response model for a ticket."""

    id: str
    external_id: str
    title: str
    description: str
    status: str
    priority: str
    labels: List[str]
    assignee: Optional[str]
    reporter: str
    created_at: str
    updated_at: str
    external_url: str
    customer_id: Optional[str] = None


class ProviderMetadata(BaseModel):
    """Metadata for a ticketing provider."""

    id: str
    name: str
    description: str
    icon: str
    is_implemented: bool
    config_fields: List[Dict[str, Any]]


# ============================================================================
# In-Memory Configuration Storage (Replace with DynamoDB in production)
# ============================================================================

_ticketing_config: Dict[str, TicketingConfigModel] = {}


def get_config(customer_id: str = "default") -> TicketingConfigModel:
    """Get ticketing configuration for a customer."""
    return _ticketing_config.get(customer_id, TicketingConfigModel())


def save_config(config: TicketingConfigModel, customer_id: str = "default") -> None:
    """Save ticketing configuration for a customer."""
    _ticketing_config[customer_id] = config


# ============================================================================
# Configuration Endpoints
# ============================================================================


@router.get("/config", response_model=TicketingConfigModel)
async def get_ticketing_config(
    customer_id: str = Query(  # noqa: B008
        default="default", description="Customer identifier"
    ),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> TicketingConfigModel:
    """
    Get the current ticketing configuration.

    Returns the provider configuration for the specified customer.
    """
    config = get_config(customer_id)
    # Mask sensitive fields
    if config.config:
        masked_config = {
            k: "***" if k in ["token", "api_token", "password", "api_key"] else v
            for k, v in config.config.items()
        }
        config = config.model_copy(update={"config": masked_config})
    return config


@router.post("/config", response_model=TicketingConfigModel)
async def save_ticketing_config(
    config: TicketingConfigModel,
    customer_id: str = Query(  # noqa: B008
        default="default", description="Customer identifier"
    ),  # noqa: B008
    rate_limit=Depends(admin_rate_limit),  # noqa: B008
) -> TicketingConfigModel:
    """
    Save ticketing configuration.

    Creates or updates the ticketing provider configuration for a customer.
    """
    logger.info(
        f"Saving ticketing config for customer {sanitize_log(customer_id)}: provider={sanitize_log(config.provider)}"
    )
    save_config(config, customer_id)
    return get_config(customer_id)


@router.patch("/config", response_model=TicketingConfigModel)
async def update_ticketing_config(
    updates: Dict[str, Any],
    customer_id: str = Query(  # noqa: B008
        default="default", description="Customer identifier"
    ),  # noqa: B008
    rate_limit=Depends(admin_rate_limit),  # noqa: B008
) -> TicketingConfigModel:
    """
    Partially update ticketing configuration.

    Updates only the specified fields of the configuration.
    """
    current = get_config(customer_id)
    updated_data = current.model_dump()
    updated_data.update(updates)
    updated_config = TicketingConfigModel(**updated_data)
    save_config(updated_config, customer_id)
    return updated_config


@router.post("/test-connection")
async def test_ticketing_connection(
    request: TestConnectionModel,
    rate_limit=Depends(admin_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Test the ticketing provider connection.

    Validates credentials and connectivity to the external system.
    """
    logger.info(f"Testing connection for provider: {sanitize_log(request.provider)}")

    try:
        factory = TicketingConnectorFactory()
        connector = await factory._create_connector(request.provider, request.config)

        if connector is None:
            return {
                "success": False,
                "error_message": f"Unknown provider: {request.provider}",
            }

        success = await connector.test_connection()

        if success:
            return {
                "success": True,
                "message": "Connection successful",
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "success": False,
                "error_message": "Connection test failed. Please verify your credentials.",
            }

    except Exception as e:
        logger.exception(f"Connection test error: {sanitize_log(e)}")
        return {
            "success": False,
            "error_message": "Connection test failed due to an internal error.",
        }


@router.get("/providers", response_model=Dict[str, ProviderMetadata])
async def get_ticketing_providers(
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get available ticketing providers.

    Returns metadata for all supported ticketing providers including
    configuration fields and implementation status.
    """
    return TicketingConnectorFactory.get_provider_metadata()


# ============================================================================
# Ticket CRUD Endpoints
# ============================================================================


@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(
    ticket: TicketCreateModel,
    customer_id: str = Query(  # noqa: B008
        default="default", description="Customer identifier"
    ),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Create a new support ticket.

    Creates a ticket in the configured external ticketing system.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(
            status_code=400,
            detail="Ticketing not configured. Please configure a provider first.",
        )

    try:
        priority = TicketPriority[ticket.priority.upper()]
    except KeyError:
        priority = TicketPriority.MEDIUM

    ticket_create = TicketCreate(
        title=ticket.title,
        description=ticket.description,
        priority=priority,
        labels=ticket.labels,
        assignee=ticket.assignee,
        customer_id=ticket.customer_id,
        metadata=ticket.metadata,
    )

    result = await connector.create_ticket(ticket_create)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return _ticket_to_response(result.ticket)


@router.get("/tickets", response_model=List[TicketResponse])
async def list_tickets(
    customer_id: str = Query(default="default"),  # noqa: B008
    status: Optional[str] = Query(default=None),  # noqa: B008
    priority: Optional[str] = Query(default=None),  # noqa: B008
    assignee: Optional[str] = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> List[Dict[str, Any]]:
    """
    List tickets with optional filters.

    Returns tickets from the configured external ticketing system.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(
            status_code=400,
            detail="Ticketing not configured.",
        )

    filters = TicketFilters(
        limit=limit,
        offset=offset,
    )

    if status:
        try:
            filters.status = [TicketStatus[status.upper()]]
        except KeyError:
            pass

    if priority:
        try:
            filters.priority = [TicketPriority[priority.upper()]]
        except KeyError:
            pass

    if assignee:
        filters.assignee = assignee

    tickets = await connector.list_tickets(filters)
    return [_ticket_to_response(t) for t in tickets]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: str,
    customer_id: str = Query(default="default"),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get a ticket by ID.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Ticketing not configured.")

    ticket = await connector.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return _ticket_to_response(ticket)


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: str,
    updates: TicketUpdateModel,
    customer_id: str = Query(default="default"),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Update an existing ticket.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Ticketing not configured.")

    ticket_update = TicketUpdate()

    if updates.title is not None:
        ticket_update.title = updates.title
    if updates.description is not None:
        ticket_update.description = updates.description
    if updates.status is not None:
        try:
            ticket_update.status = TicketStatus[updates.status.upper()]
        except KeyError:
            pass
    if updates.priority is not None:
        try:
            ticket_update.priority = TicketPriority[updates.priority.upper()]
        except KeyError:
            pass
    if updates.labels is not None:
        ticket_update.labels = updates.labels
    if updates.assignee is not None:
        ticket_update.assignee = updates.assignee

    result = await connector.update_ticket(ticket_id, ticket_update)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return _ticket_to_response(result.ticket)


@router.post("/tickets/{ticket_id}/comments", response_model=TicketResponse)
async def add_ticket_comment(
    ticket_id: str,
    comment: TicketCommentModel,
    customer_id: str = Query(default="default"),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Add a comment to an existing ticket.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Ticketing not configured.")

    result = await connector.add_comment(
        ticket_id, comment.comment, comment.is_internal
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return _ticket_to_response(result.ticket)


@router.post("/tickets/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(
    ticket_id: str,
    request: TicketCloseModel,
    customer_id: str = Query(default="default"),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Close a ticket with optional resolution note.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Ticketing not configured.")

    result = await connector.close_ticket(ticket_id, request.resolution)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return _ticket_to_response(result.ticket)


@router.post("/tickets/{ticket_id}/reopen", response_model=TicketResponse)
async def reopen_ticket(
    ticket_id: str,
    request: TicketReopenModel,
    customer_id: str = Query(default="default"),  # noqa: B008
    rate_limit=Depends(standard_rate_limit),  # noqa: B008
) -> Dict[str, Any]:
    """
    Reopen a closed ticket.
    """
    connector = await get_ticketing_connector(customer_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Ticketing not configured.")

    result = await connector.reopen_ticket(ticket_id, request.reason)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return _ticket_to_response(result.ticket)


# ============================================================================
# Helper Functions
# ============================================================================


def _ticket_to_response(ticket) -> Dict[str, Any]:
    """Convert Ticket dataclass to response dict."""
    return {
        "id": ticket.id,
        "external_id": ticket.external_id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "labels": ticket.labels,
        "assignee": ticket.assignee,
        "reporter": ticket.reporter,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "external_url": ticket.external_url,
        "customer_id": ticket.customer_id,
    }
