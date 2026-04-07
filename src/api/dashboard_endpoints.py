"""
Dashboard Configuration API Endpoints.

Provides REST API for customizable dashboard management per ADR-064:
- GET /api/v1/dashboards - List user's dashboards
- POST /api/v1/dashboards - Create new dashboard
- GET /api/v1/dashboards/{id} - Get dashboard by ID
- PUT /api/v1/dashboards/{id} - Update dashboard
- DELETE /api/v1/dashboards/{id} - Delete dashboard
- POST /api/v1/dashboards/{id}/clone - Clone dashboard
- POST /api/v1/dashboards/{id}/share - Share dashboard
- GET /api/v1/dashboards/{id}/shares - List shares
- DELETE /api/v1/dashboards/{id}/shares/{user_id} - Revoke share
- GET /api/v1/dashboards/defaults/{role} - Get role default
- GET /api/v1/dashboards/templates - List dashboard templates
- GET /api/v1/widgets/catalog - List available widgets
- GET/POST /api/v1/widgets/custom - Custom widget CRUD (Phase 3)
- GET/POST /api/v1/dashboards/{id}/schedules - Scheduled reports (Phase 3)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.dashboard import (
    CustomWidget,
    CustomWidgetCreate,
    CustomWidgetUpdate,
    Dashboard,
    DashboardCreate,
    DashboardUpdate,
    DataSourceType,
    DayOfWeek,
    EmbedMode,
    EmbedTheme,
    EmbedToken,
    EmbedTokenCreate,
    EmbedTokenUpdate,
    LayoutConfig,
    LayoutItem,
    QueryDefinition,
    QueryType,
    ReportFormat,
    ScheduleConfig,
    ScheduledReport,
    ScheduledReportCreate,
    ScheduledReportUpdate,
    ScheduleFrequency,
    ShareCreate,
    SharePermission,
    ShareRecord,
    UserRole,
    WidgetCategory,
    WidgetConfig,
    get_custom_widget_service,
    get_dashboard_service,
    get_embed_service,
    get_scheduled_report_service,
    get_widget_catalog,
    get_widgets_by_category,
)
from src.services.dashboard.exceptions import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    DashboardValidationError,
    ShareNotFoundError,
)
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dashboards",
    tags=["Dashboards"],
)

widget_router = APIRouter(
    prefix="/api/v1/widgets",
    tags=["Widgets"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class DashboardCreateRequest(BaseModel):
    """Request body for creating a dashboard."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    layout: list[dict[str, Any]] = Field(default_factory=list)
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    is_default: bool = Field(default=False)


class DashboardUpdateRequest(BaseModel):
    """Request body for updating a dashboard."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    layout: list[dict[str, Any]] | None = None
    widgets: list[dict[str, Any]] | None = None
    is_default: bool | None = None


class DashboardResponse(BaseModel):
    """Dashboard response model."""

    dashboard_id: str
    user_id: str
    name: str
    description: str | None
    layout: list[dict[str, Any]]
    widgets: list[dict[str, Any]]
    is_default: bool
    version: int
    created_at: str
    updated_at: str


class DashboardListResponse(BaseModel):
    """Response for listing dashboards."""

    dashboards: list[DashboardResponse]
    total: int


class ShareRequest(BaseModel):
    """Request body for sharing a dashboard."""

    user_id: str | None = Field(default=None, description="User ID to share with")
    org_id: str | None = Field(
        default=None, description="Organization ID for org-wide share"
    )
    permission: str = Field(default="view", pattern="^(view|edit)$")


class ShareResponse(BaseModel):
    """Share record response."""

    dashboard_id: str
    shared_with_user_id: str | None
    shared_with_org_id: str | None
    permission: str
    shared_by: str
    shared_at: str


class ShareListResponse(BaseModel):
    """Response for listing shares."""

    shares: list[ShareResponse]
    total: int


class CloneRequest(BaseModel):
    """Request body for cloning a dashboard."""

    name: str | None = Field(default=None, min_length=1, max_length=100)


class WidgetDefinitionResponse(BaseModel):
    """Widget definition response."""

    id: str
    widget_type: str
    category: str
    name: str
    description: str
    default_data_source: str
    default_refresh_seconds: int
    supports_sparkline: bool
    supports_trend: bool
    min_width: int
    min_height: int
    default_width: int
    default_height: int
    default_color: str


class WidgetCatalogResponse(BaseModel):
    """Widget catalog response."""

    widgets: list[WidgetDefinitionResponse]
    categories: list[str]


class DashboardTemplateResponse(BaseModel):
    """Dashboard template response."""

    id: str
    name: str
    description: str
    role: str
    preview_image: str | None
    widget_count: int


class TemplateListResponse(BaseModel):
    """Response for listing templates."""

    templates: list[DashboardTemplateResponse]


# =============================================================================
# Helper Functions
# =============================================================================


def dashboard_to_response(dashboard: Dashboard) -> DashboardResponse:
    """Convert Dashboard model to response."""
    return DashboardResponse(
        dashboard_id=dashboard.dashboard_id,
        user_id=dashboard.user_id,
        name=dashboard.name,
        description=dashboard.description,
        layout=[item.model_dump() for item in dashboard.layout.items],
        widgets=[widget.model_dump() for widget in dashboard.widgets],
        is_default=dashboard.is_default,
        version=dashboard.version,
        created_at=dashboard.created_at.isoformat(),
        updated_at=dashboard.updated_at.isoformat(),
    )


def share_to_response(share: ShareRecord) -> ShareResponse:
    """Convert ShareRecord to response."""
    return ShareResponse(
        dashboard_id=share.dashboard_id,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_org_id=share.shared_with_org_id,
        permission=share.permission.value,
        shared_by=share.shared_by,
        shared_at=share.shared_at.isoformat(),
    )


# =============================================================================
# Dashboard CRUD Endpoints
# =============================================================================


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    include_shared: bool = Query(default=True, description="Include shared dashboards"),
    current_user: User = Depends(get_current_user),
) -> DashboardListResponse:
    """List all dashboards accessible by the current user."""
    try:
        service = get_dashboard_service()
        dashboards = service.list_dashboards(
            user_id=current_user.sub,
            include_shared=include_shared,
        )
        return DashboardListResponse(
            dashboards=[dashboard_to_response(d) for d in dashboards],
            total=len(dashboards),
        )
    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list dashboards",
        )


@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    request: DashboardCreateRequest,
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Create a new dashboard."""
    try:
        service = get_dashboard_service()

        # Convert layout list to LayoutConfig
        layout_items = (
            [LayoutItem(**item) for item in request.layout] if request.layout else []
        )
        layout_config = LayoutConfig(items=layout_items)

        # Convert widgets list to WidgetConfig objects
        widget_configs = (
            [WidgetConfig(**w) for w in request.widgets] if request.widgets else []
        )

        # Convert request to DashboardCreate model
        dashboard_data = DashboardCreate(
            name=request.name,
            description=request.description or "",
            layout=layout_config,
            widgets=widget_configs,
            is_default=request.is_default,
        )

        dashboard = service.create_dashboard(
            user_id=current_user.sub,
            dashboard_data=dashboard_data,
        )

        logger.info(
            f"Dashboard created: {dashboard.dashboard_id} by user {current_user.sub}"
        )
        return dashboard_to_response(dashboard)

    except DashboardLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except DashboardValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dashboard",
        )


# =============================================================================
# Static Routes (must be before parameterized routes)
# =============================================================================


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> TemplateListResponse:
    """List available dashboard templates."""
    # Pre-built templates based on roles
    templates = [
        DashboardTemplateResponse(
            id="security-overview",
            name="Security Overview",
            description="Security-focused dashboard for vulnerability management and HITL approvals",
            role=UserRole.SECURITY_ENGINEER.value,
            preview_image="/images/templates/security-overview.png",
            widget_count=6,
        ),
        DashboardTemplateResponse(
            id="devops-operations",
            name="DevOps Operations",
            description="Operations dashboard for sandbox management and deployment tracking",
            role=UserRole.DEVOPS.value,
            preview_image="/images/templates/devops-operations.png",
            widget_count=6,
        ),
        DashboardTemplateResponse(
            id="engineering-metrics",
            name="Engineering Metrics",
            description="Team productivity and code quality metrics for engineering managers",
            role=UserRole.ENGINEERING_MANAGER.value,
            preview_image="/images/templates/engineering-metrics.png",
            widget_count=6,
        ),
        DashboardTemplateResponse(
            id="executive-summary",
            name="Executive Summary",
            description="High-level risk posture and compliance overview for executives",
            role=UserRole.EXECUTIVE.value,
            preview_image="/images/templates/executive-summary.png",
            widget_count=4,
        ),
        DashboardTemplateResponse(
            id="superuser-full",
            name="SuperUser Dashboard",
            description="Complete visibility across all Aura metrics and services",
            role=UserRole.SUPERUSER.value,
            preview_image="/images/templates/superuser-full.png",
            widget_count=4,
        ),
    ]

    return TemplateListResponse(templates=templates)


@router.get("/defaults/{role}", response_model=DashboardResponse)
async def get_role_default(
    role: str,
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Get the default dashboard configuration for a role."""
    try:
        # Validate role
        try:
            user_role = UserRole(role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid roles: {[r.value for r in UserRole]}",
            )

        service = get_dashboard_service()
        dashboard = service.get_role_default(user_role)
        return dashboard_to_response(dashboard)

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No default dashboard found for role: {role}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get role default for {sanitize_log(role)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get role default",
        )


# =============================================================================
# Dashboard Parameterized Endpoints
# =============================================================================


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Get a dashboard by ID."""
    try:
        service = get_dashboard_service()
        dashboard = service.get_dashboard(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
        )
        return dashboard_to_response(dashboard)

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this dashboard",
        )
    except Exception as e:
        logger.error(
            f"Failed to get dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard",
        )


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Update a dashboard."""
    try:
        service = get_dashboard_service()

        # Convert layout if provided
        layout_config = None
        if request.layout is not None:
            layout_items = [LayoutItem(**item) for item in request.layout]
            layout_config = LayoutConfig(items=layout_items)

        # Convert widgets if provided
        widget_configs = None
        if request.widgets is not None:
            widget_configs = [WidgetConfig(**w) for w in request.widgets]

        # Build update dict with only provided fields
        update_data = DashboardUpdate(
            name=request.name,
            description=request.description,
            layout=layout_config,
            widgets=widget_configs,
            is_default=request.is_default,
        )

        dashboard = service.update_dashboard(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
            updates=update_data,
        )

        logger.info(
            f"Dashboard updated: {sanitize_log(dashboard_id)} by user {sanitize_log(current_user.sub)}"
        )
        return dashboard_to_response(dashboard)

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - you can only update your own dashboards",
        )
    except DashboardConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except DashboardValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to update dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dashboard",
        )


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a dashboard."""
    try:
        service = get_dashboard_service()
        service.delete_dashboard(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
        )
        logger.info(
            f"Dashboard deleted: {sanitize_log(dashboard_id)} by user {sanitize_log(current_user.sub)}"
        )

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - you can only delete your own dashboards",
        )
    except Exception as e:
        logger.error(
            f"Failed to delete dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dashboard",
        )


# =============================================================================
# Clone Endpoint
# =============================================================================


@router.post(
    "/{dashboard_id}/clone",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_dashboard(
    dashboard_id: str,
    request: CloneRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Clone a dashboard to create a copy."""
    try:
        service = get_dashboard_service()

        new_name = request.name if request else None

        dashboard = service.clone_dashboard(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
            new_name=new_name,
        )

        logger.info(
            f"Dashboard cloned: {sanitize_log(dashboard_id)} -> {sanitize_log(dashboard.dashboard_id)} "
            f"by user {current_user.sub}"
        )
        return dashboard_to_response(dashboard)

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to clone this dashboard",
        )
    except DashboardLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to clone dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clone dashboard",
        )


# =============================================================================
# Share Endpoints
# =============================================================================


@router.post(
    "/{dashboard_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def share_dashboard(
    dashboard_id: str,
    request: ShareRequest,
    current_user: User = Depends(get_current_user),
) -> ShareResponse:
    """Share a dashboard with a user or organization."""
    try:
        if not request.user_id and not request.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or org_id must be provided",
            )

        service = get_dashboard_service()

        share_data = ShareCreate(
            user_id=request.user_id,
            org_id=request.org_id,
            permission=SharePermission(request.permission),
        )

        share = service.share_dashboard(
            dashboard_id=dashboard_id,
            owner_user_id=current_user.sub,
            share_data=share_data,
        )

        logger.info(
            f"Dashboard shared: {sanitize_log(dashboard_id)} with "
            f"user={sanitize_log(request.user_id)} org={sanitize_log(request.org_id)} "
            f"by {sanitize_log(current_user.sub)}"
        )
        return share_to_response(share)

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the dashboard owner can share it",
        )
    except DashboardValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to share dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to share dashboard",
        )


@router.get("/{dashboard_id}/shares", response_model=ShareListResponse)
async def list_shares(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
) -> ShareListResponse:
    """List all shares for a dashboard."""
    try:
        service = get_dashboard_service()
        shares = service.list_shares(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
        )
        return ShareListResponse(
            shares=[share_to_response(s) for s in shares],
            total=len(shares),
        )

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the dashboard owner can view shares",
        )
    except Exception as e:
        logger.error(
            f"Failed to list shares for dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list shares",
        )


@router.delete(
    "/{dashboard_id}/shares/{share_user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_share(
    dashboard_id: str,
    share_user_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke a share for a dashboard."""
    try:
        service = get_dashboard_service()
        service.revoke_share(
            dashboard_id=dashboard_id,
            owner_user_id=current_user.sub,
            shared_with_user_id=share_user_id,
        )
        logger.info(
            f"Share revoked: dashboard={sanitize_log(dashboard_id)} user={sanitize_log(share_user_id)} "
            f"by {current_user.sub}"
        )

    except DashboardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found",
        )
    except ShareNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Share not found for user {share_user_id}",
        )
    except DashboardAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the dashboard owner can revoke shares",
        )
    except Exception as e:
        logger.error(
            f"Failed to revoke share for dashboard {sanitize_log(dashboard_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke share",
        )


# =============================================================================
# Widget Catalog Endpoints
# =============================================================================


@widget_router.get("/catalog", response_model=WidgetCatalogResponse)
async def get_widget_catalog_endpoint(
    category: str | None = Query(default=None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
) -> WidgetCatalogResponse:
    """Get the widget catalog with all available widgets."""
    try:
        if category:
            # Validate category
            try:
                widget_category = WidgetCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {category}. Valid: {[c.value for c in WidgetCategory]}",
                )
            widgets = get_widgets_by_category(widget_category)
        else:
            catalog = get_widget_catalog()
            widgets = catalog.widgets

        widget_responses = [
            WidgetDefinitionResponse(
                id=w.widget_type.value,
                widget_type=w.widget_type.value,
                category=w.category.value,
                name=w.name,
                description=w.description,
                default_data_source=w.default_data_source,
                default_refresh_seconds=w.default_refresh_seconds,
                supports_sparkline=w.supports_sparkline,
                supports_trend=w.supports_trend,
                min_width=w.min_width,
                min_height=w.min_height,
                default_width=w.default_width,
                default_height=w.default_height,
                default_color="aura",
            )
            for w in widgets
        ]

        return WidgetCatalogResponse(
            widgets=widget_responses,
            categories=[c.value for c in WidgetCategory],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget catalog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get widget catalog",
        )


# =============================================================================
# Custom Widget Endpoints (Phase 3)
# =============================================================================


class CustomWidgetCreateRequest(BaseModel):
    """Request body for creating a custom widget."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    widget_type: str = Field(..., description="Widget display type")
    category: str = Field(default="analytics", description="Widget category")
    query: dict[str, Any] = Field(..., description="Query definition")
    display_config: dict[str, Any] = Field(
        default_factory=dict, description="Display configuration"
    )
    refresh_seconds: int = Field(default=60, ge=10, le=3600)


class CustomWidgetUpdateRequest(BaseModel):
    """Request body for updating a custom widget."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    widget_type: str | None = None
    category: str | None = None
    query: dict[str, Any] | None = None
    display_config: dict[str, Any] | None = None
    refresh_seconds: int | None = Field(default=None, ge=10, le=3600)
    is_published: bool | None = None


class CustomWidgetResponse(BaseModel):
    """Custom widget response model."""

    widget_id: str
    user_id: str
    name: str
    description: str
    widget_type: str
    category: str
    query: dict[str, Any]
    display_config: dict[str, Any]
    refresh_seconds: int
    is_published: bool
    version: int
    created_at: str
    updated_at: str


class CustomWidgetListResponse(BaseModel):
    """Response for listing custom widgets."""

    widgets: list[CustomWidgetResponse]
    total: int


class QueryPreviewRequest(BaseModel):
    """Request body for previewing a query."""

    query_type: str = Field(..., description="Type of query")
    data_source: str = Field(..., description="Data source type")
    endpoint: str = Field(..., description="API endpoint path")
    parameters: dict[str, Any] = Field(default_factory=dict)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    aggregation: str | None = None
    group_by: list[str] = Field(default_factory=list)
    time_range: str = Field(default="24h")
    limit: int = Field(default=10, ge=1, le=100)


class QueryResultResponse(BaseModel):
    """Query execution result response."""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: int
    cached: bool


def custom_widget_to_response(widget: CustomWidget) -> CustomWidgetResponse:
    """Convert CustomWidget model to response."""
    return CustomWidgetResponse(
        widget_id=widget.widget_id,
        user_id=widget.user_id,
        name=widget.name,
        description=widget.description,
        widget_type=widget.widget_type.value,
        category=widget.category.value,
        query=widget.query.model_dump(),
        display_config=widget.display_config,
        refresh_seconds=widget.refresh_seconds,
        is_published=widget.is_published,
        version=widget.version,
        created_at=widget.created_at.isoformat(),
        updated_at=widget.updated_at.isoformat(),
    )


@widget_router.get("/custom", response_model=CustomWidgetListResponse)
async def list_custom_widgets(
    include_published: bool = Query(
        default=True, description="Include published widgets from others"
    ),
    current_user: User = Depends(get_current_user),
) -> CustomWidgetListResponse:
    """List custom widgets accessible by the current user."""
    try:
        service = get_custom_widget_service()
        widgets = service.list_custom_widgets(
            user_id=current_user.sub,
            include_published=include_published,
        )
        return CustomWidgetListResponse(
            widgets=[custom_widget_to_response(w) for w in widgets],
            total=len(widgets),
        )
    except Exception as e:
        logger.error(f"Failed to list custom widgets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list custom widgets",
        )


@widget_router.post(
    "/custom", response_model=CustomWidgetResponse, status_code=status.HTTP_201_CREATED
)
async def create_custom_widget(
    request: CustomWidgetCreateRequest,
    current_user: User = Depends(get_current_user),
) -> CustomWidgetResponse:
    """Create a new custom widget."""
    try:
        service = get_custom_widget_service()

        # Convert request to CustomWidgetCreate model
        from src.services.dashboard.models import WidgetType

        widget_data = CustomWidgetCreate(
            name=request.name,
            description=request.description or "",
            widget_type=WidgetType(request.widget_type),
            category=WidgetCategory(request.category),
            query=QueryDefinition(**request.query),
            display_config=request.display_config,
            refresh_seconds=request.refresh_seconds,
        )

        widget = service.create_custom_widget(
            user_id=current_user.sub,
            widget_data=widget_data,
        )

        logger.info(f"Custom widget created: {widget.widget_id} by {current_user.sub}")
        return custom_widget_to_response(widget)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create custom widget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom widget",
        )


@widget_router.get("/custom/data-sources")
async def list_data_sources(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List available data sources and their allowed endpoints."""
    from src.services.dashboard.custom_widget_service import ALLOWED_ENDPOINTS

    return {
        "data_sources": [
            {
                "type": ds.value,
                "name": ds.value.replace("_", " ").title(),
                "endpoints": endpoints,
            }
            for ds, endpoints in ALLOWED_ENDPOINTS.items()
        ],
        "query_types": [qt.value for qt in QueryType],
    }


@widget_router.post("/custom/preview", response_model=QueryResultResponse)
async def preview_query(
    request: QueryPreviewRequest,
    current_user: User = Depends(get_current_user),
) -> QueryResultResponse:
    """Preview a query without saving a widget."""
    try:
        service = get_custom_widget_service()

        query = QueryDefinition(
            query_type=QueryType(request.query_type),
            data_source=DataSourceType(request.data_source),
            endpoint=request.endpoint,
            parameters=request.parameters,
            filters=request.filters,
            aggregation=request.aggregation,
            group_by=request.group_by,
            time_range=request.time_range,
            limit=request.limit,
        )

        result = service.preview_query(
            query=query,
            user_id=current_user.sub,
        )

        return QueryResultResponse(
            success=result.success,
            data=result.data,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            cached=result.cached,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to preview query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview query",
        )


@widget_router.get("/custom/{widget_id}", response_model=CustomWidgetResponse)
async def get_custom_widget(
    widget_id: str,
    current_user: User = Depends(get_current_user),
) -> CustomWidgetResponse:
    """Get a custom widget by ID."""
    try:
        service = get_custom_widget_service()
        widget = service.get_custom_widget(
            widget_id=widget_id,
            user_id=current_user.sub,
        )
        return custom_widget_to_response(widget)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom widget {widget_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this widget",
        )
    except Exception as e:
        logger.error(
            f"Failed to get custom widget {sanitize_log(widget_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get custom widget",
        )


@widget_router.put("/custom/{widget_id}", response_model=CustomWidgetResponse)
async def update_custom_widget(
    widget_id: str,
    request: CustomWidgetUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> CustomWidgetResponse:
    """Update a custom widget."""
    try:
        service = get_custom_widget_service()
        from src.services.dashboard.models import WidgetType

        # Build update model
        update_data = CustomWidgetUpdate(
            name=request.name,
            description=request.description,
            widget_type=(
                WidgetType(request.widget_type) if request.widget_type else None
            ),
            category=WidgetCategory(request.category) if request.category else None,
            query=QueryDefinition(**request.query) if request.query else None,
            display_config=request.display_config,
            refresh_seconds=request.refresh_seconds,
            is_published=request.is_published,
        )

        widget = service.update_custom_widget(
            widget_id=widget_id,
            user_id=current_user.sub,
            updates=update_data,
        )

        logger.info(
            f"Custom widget updated: {sanitize_log(widget_id)} by {sanitize_log(current_user.sub)}"
        )
        return custom_widget_to_response(widget)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom widget {widget_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update this widget",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to update custom widget {sanitize_log(widget_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update custom widget",
        )


@widget_router.delete("/custom/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_widget(
    widget_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a custom widget."""
    try:
        service = get_custom_widget_service()
        service.delete_custom_widget(
            widget_id=widget_id,
            user_id=current_user.sub,
        )
        logger.info(
            f"Custom widget deleted: {sanitize_log(widget_id)} by {sanitize_log(current_user.sub)}"
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom widget {widget_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this widget",
        )
    except Exception as e:
        logger.error(
            f"Failed to delete custom widget {sanitize_log(widget_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete custom widget",
        )


@widget_router.post("/custom/{widget_id}/execute", response_model=QueryResultResponse)
async def execute_custom_widget_query(
    widget_id: str,
    current_user: User = Depends(get_current_user),
) -> QueryResultResponse:
    """Execute a custom widget's query and return results."""
    try:
        service = get_custom_widget_service()
        result = service.execute_query(
            widget_id=widget_id,
            user_id=current_user.sub,
        )
        return QueryResultResponse(
            success=result.success,
            data=result.data,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            cached=result.cached,
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom widget {widget_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this widget",
        )
    except Exception as e:
        logger.error(
            f"Failed to execute query for widget {sanitize_log(widget_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute query",
        )


# =============================================================================
# Scheduled Report Request/Response Models
# =============================================================================


class ScheduleConfigRequest(BaseModel):
    """Request model for schedule configuration."""

    frequency: str = Field(..., pattern="^(daily|weekly|biweekly|monthly)$")
    time_utc: str = Field(
        default="09:00",
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
    )
    day_of_week: str | None = Field(
        default=None,
        pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$",
    )
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    timezone: str = Field(default="UTC")


class ScheduledReportCreateRequest(BaseModel):
    """Request body for creating a scheduled report."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    recipients: list[str] = Field(..., min_length=1, max_length=20)
    schedule: ScheduleConfigRequest
    format: str = Field(default="html_email", pattern="^(pdf|html_email|csv)$")
    include_widgets: list[str] | None = None
    subject_template: str = Field(
        default="{dashboard_name} - {report_name} Report",
        max_length=200,
    )


class ScheduledReportUpdateRequest(BaseModel):
    """Request body for updating a scheduled report."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    recipients: list[str] | None = Field(default=None, min_length=1, max_length=20)
    schedule: ScheduleConfigRequest | None = None
    format: str | None = Field(default=None, pattern="^(pdf|html_email|csv)$")
    include_widgets: list[str] | None = None
    subject_template: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ScheduledReportResponse(BaseModel):
    """Response model for scheduled report."""

    report_id: str
    dashboard_id: str
    user_id: str
    name: str
    description: str
    recipients: list[str]
    schedule: dict[str, Any]
    format: str
    include_widgets: list[str] | None
    subject_template: str
    is_active: bool
    last_sent_at: str | None
    next_run_at: str | None
    send_count: int
    failure_count: int
    created_at: str
    updated_at: str


class ScheduledReportListResponse(BaseModel):
    """Response model for listing scheduled reports."""

    schedules: list[ScheduledReportResponse]
    total: int


class ReportDeliveryResponse(BaseModel):
    """Response model for report delivery result."""

    success: bool
    report_id: str
    recipients_sent: list[str]
    recipients_failed: list[str]
    error: str | None
    sent_at: str


def scheduled_report_to_response(report: ScheduledReport) -> ScheduledReportResponse:
    """Convert ScheduledReport to response model."""
    return ScheduledReportResponse(
        report_id=report.report_id,
        dashboard_id=report.dashboard_id,
        user_id=report.user_id,
        name=report.name,
        description=report.description,
        recipients=report.recipients,
        schedule=report.schedule.model_dump(),
        format=report.format.value,
        include_widgets=report.include_widgets,
        subject_template=report.subject_template,
        is_active=report.is_active,
        last_sent_at=report.last_sent_at.isoformat() if report.last_sent_at else None,
        next_run_at=report.next_run_at.isoformat() if report.next_run_at else None,
        send_count=report.send_count,
        failure_count=report.failure_count,
        created_at=report.created_at.isoformat(),
        updated_at=report.updated_at.isoformat(),
    )


# =============================================================================
# Scheduled Report Endpoints
# =============================================================================


@router.get("/{dashboard_id}/schedules", response_model=ScheduledReportListResponse)
async def list_scheduled_reports(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
) -> ScheduledReportListResponse:
    """List scheduled reports for a dashboard."""
    try:
        service = get_scheduled_report_service()
        schedules = service.list_schedules(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
        )
        return ScheduledReportListResponse(
            schedules=[scheduled_report_to_response(s) for s in schedules],
            total=len(schedules),
        )
    except Exception as e:
        logger.error(f"Failed to list scheduled reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled reports",
        )


@router.post(
    "/{dashboard_id}/schedules",
    response_model=ScheduledReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scheduled_report(
    dashboard_id: str,
    request: ScheduledReportCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ScheduledReportResponse:
    """Create a new scheduled report for a dashboard."""
    try:
        service = get_scheduled_report_service()

        # Build schedule config
        schedule_config = ScheduleConfig(
            frequency=ScheduleFrequency(request.schedule.frequency),
            time_utc=request.schedule.time_utc,
            day_of_week=(
                DayOfWeek(request.schedule.day_of_week)
                if request.schedule.day_of_week
                else None
            ),
            day_of_month=request.schedule.day_of_month,
            timezone=request.schedule.timezone,
        )

        # Build create model
        schedule_data = ScheduledReportCreate(
            name=request.name,
            description=request.description,
            recipients=request.recipients,
            schedule=schedule_config,
            format=ReportFormat(request.format),
            include_widgets=request.include_widgets,
            subject_template=request.subject_template,
        )

        report = service.create_schedule(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
            schedule_data=schedule_data,
        )

        logger.info(
            f"Scheduled report created: {report.report_id} by {current_user.sub}"
        )
        return scheduled_report_to_response(report)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create scheduled report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scheduled report",
        )


@router.get(
    "/{dashboard_id}/schedules/{report_id}",
    response_model=ScheduledReportResponse,
)
async def get_scheduled_report(
    dashboard_id: str,
    report_id: str,
    current_user: User = Depends(get_current_user),
) -> ScheduledReportResponse:
    """Get a scheduled report by ID."""
    try:
        service = get_scheduled_report_service()
        report = service.get_schedule(
            report_id=report_id,
            user_id=current_user.sub,
        )

        # Verify dashboard matches
        if report.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report schedule {report_id} not found for dashboard",
            )

        return scheduled_report_to_response(report)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report schedule {report_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this report schedule",
        )
    except Exception as e:
        logger.error(
            f"Failed to get scheduled report {sanitize_log(report_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scheduled report",
        )


@router.put(
    "/{dashboard_id}/schedules/{report_id}",
    response_model=ScheduledReportResponse,
)
async def update_scheduled_report(
    dashboard_id: str,
    report_id: str,
    request: ScheduledReportUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ScheduledReportResponse:
    """Update a scheduled report."""
    try:
        service = get_scheduled_report_service()

        # Build update model
        schedule_config = None
        if request.schedule:
            schedule_config = ScheduleConfig(
                frequency=ScheduleFrequency(request.schedule.frequency),
                time_utc=request.schedule.time_utc,
                day_of_week=(
                    DayOfWeek(request.schedule.day_of_week)
                    if request.schedule.day_of_week
                    else None
                ),
                day_of_month=request.schedule.day_of_month,
                timezone=request.schedule.timezone,
            )

        update_data = ScheduledReportUpdate(
            name=request.name,
            description=request.description,
            recipients=request.recipients,
            schedule=schedule_config,
            format=ReportFormat(request.format) if request.format else None,
            include_widgets=request.include_widgets,
            subject_template=request.subject_template,
            is_active=request.is_active,
        )

        report = service.update_schedule(
            report_id=report_id,
            user_id=current_user.sub,
            updates=update_data,
        )

        # Verify dashboard matches
        if report.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report schedule {report_id} not found for dashboard",
            )

        logger.info(
            f"Scheduled report updated: {sanitize_log(report_id)} by {sanitize_log(current_user.sub)}"
        )
        return scheduled_report_to_response(report)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report schedule {report_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update this report schedule",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to update scheduled report {sanitize_log(report_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scheduled report",
        )


@router.delete(
    "/{dashboard_id}/schedules/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scheduled_report(
    dashboard_id: str,
    report_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a scheduled report."""
    try:
        service = get_scheduled_report_service()

        # Verify report exists and user has access
        report = service.get_schedule(report_id, current_user.sub)
        if report.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report schedule {report_id} not found for dashboard",
            )

        service.delete_schedule(
            report_id=report_id,
            user_id=current_user.sub,
        )
        logger.info(
            f"Scheduled report deleted: {sanitize_log(report_id)} by {sanitize_log(current_user.sub)}"
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report schedule {report_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this report schedule",
        )
    except Exception as e:
        logger.error(
            f"Failed to delete scheduled report {sanitize_log(report_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scheduled report",
        )


@router.post(
    "/{dashboard_id}/schedules/{report_id}/send",
    response_model=ReportDeliveryResponse,
)
async def send_report_now(
    dashboard_id: str,
    report_id: str,
    current_user: User = Depends(get_current_user),
) -> ReportDeliveryResponse:
    """Manually trigger report delivery."""
    try:
        service = get_scheduled_report_service()

        # Verify report exists and user has access
        report = service.get_schedule(report_id, current_user.sub)
        if report.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report schedule {report_id} not found for dashboard",
            )

        result = service.send_report_now(
            report_id=report_id,
            user_id=current_user.sub,
        )

        logger.info(
            f"Manual report send triggered: {sanitize_log(report_id)} by {sanitize_log(current_user.sub)}"
        )

        return ReportDeliveryResponse(
            success=result.success,
            report_id=result.report_id,
            recipients_sent=result.recipients_sent,
            recipients_failed=result.recipients_failed,
            error=result.error,
            sent_at=result.sent_at.isoformat(),
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report schedule {report_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this report schedule",
        )
    except Exception as e:
        logger.error(
            f"Failed to send report {sanitize_log(report_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send report",
        )


@router.get("/user/schedules", response_model=ScheduledReportListResponse)
async def list_user_scheduled_reports(
    current_user: User = Depends(get_current_user),
) -> ScheduledReportListResponse:
    """List all scheduled reports for the current user."""
    try:
        service = get_scheduled_report_service()
        schedules = service.list_user_schedules(user_id=current_user.sub)
        return ScheduledReportListResponse(
            schedules=[scheduled_report_to_response(s) for s in schedules],
            total=len(schedules),
        )
    except Exception as e:
        logger.error(f"Failed to list user scheduled reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled reports",
        )


# =============================================================================
# Dashboard Embedding Request/Response Models
# =============================================================================


class EmbedTokenCreateRequest(BaseModel):
    """Request body for creating an embed token."""

    expires_in_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Token expiration in hours (1-720, max 30 days)",
    )
    allowed_domains: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Allowed domains for iframe embedding",
    )
    mode: str = Field(
        default="minimal",
        pattern="^(full|minimal|widget_only)$",
        description="Dashboard display mode",
    )
    theme: str = Field(
        default="light",
        pattern="^(light|dark|auto)$",
        description="Color theme",
    )
    show_title: bool = Field(default=True, description="Show dashboard title")
    show_refresh: bool = Field(default=True, description="Show refresh button")
    show_fullscreen: bool = Field(default=False, description="Show fullscreen toggle")
    widget_ids: list[str] | None = Field(
        default=None,
        description="Specific widget IDs to display",
    )
    custom_css: str | None = Field(
        default=None,
        max_length=5000,
        description="Custom CSS for styling",
    )


class EmbedTokenUpdateRequest(BaseModel):
    """Request body for updating an embed token."""

    is_active: bool | None = Field(default=None, description="Enable/disable token")
    allowed_domains: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Update allowed domains",
    )


class EmbedTokenResponse(BaseModel):
    """Response model for embed token."""

    token_id: str
    dashboard_id: str
    user_id: str
    token: str
    embed_url: str
    iframe_html: str
    mode: str
    theme: str
    show_title: bool
    show_refresh: bool
    show_fullscreen: bool
    widget_ids: list[str] | None
    allowed_domains: list[str]
    expires_at: str
    created_at: str
    is_active: bool
    access_count: int
    last_accessed_at: str | None


class EmbedTokenListResponse(BaseModel):
    """Response for listing embed tokens."""

    tokens: list[EmbedTokenResponse]
    total: int


class EmbedDashboardResponse(BaseModel):
    """Response model for embedded dashboard data."""

    dashboard_id: str
    name: str
    description: str
    layout: dict[str, Any]
    widgets: list[dict[str, Any]]
    mode: str
    theme: str
    show_title: bool
    show_refresh: bool
    show_fullscreen: bool
    custom_css: str | None


def embed_token_to_response(token: EmbedToken) -> EmbedTokenResponse:
    """Convert EmbedToken to response model."""
    service = get_embed_service()
    return EmbedTokenResponse(
        token_id=token.token_id,
        dashboard_id=token.dashboard_id,
        user_id=token.user_id,
        token=token.token,
        embed_url=token.embed_url,
        iframe_html=service.get_iframe_html(token.token),
        mode=token.mode.value,
        theme=token.theme.value,
        show_title=token.show_title,
        show_refresh=token.show_refresh,
        show_fullscreen=token.show_fullscreen,
        widget_ids=token.widget_ids,
        allowed_domains=token.allowed_domains,
        expires_at=token.expires_at.isoformat(),
        created_at=token.created_at.isoformat(),
        is_active=token.is_active,
        access_count=token.access_count,
        last_accessed_at=(
            token.last_accessed_at.isoformat() if token.last_accessed_at else None
        ),
    )


# =============================================================================
# Dashboard Embedding Endpoints
# =============================================================================


@router.get("/{dashboard_id}/embed", response_model=EmbedTokenListResponse)
async def list_embed_tokens(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
) -> EmbedTokenListResponse:
    """List embed tokens for a dashboard."""
    try:
        service = get_embed_service()
        tokens = service.list_tokens(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
        )
        return EmbedTokenListResponse(
            tokens=[embed_token_to_response(t) for t in tokens],
            total=len(tokens),
        )
    except Exception as e:
        logger.error(f"Failed to list embed tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list embed tokens",
        )


@router.post(
    "/{dashboard_id}/embed",
    response_model=EmbedTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_embed_token(
    dashboard_id: str,
    request: EmbedTokenCreateRequest,
    current_user: User = Depends(get_current_user),
) -> EmbedTokenResponse:
    """Create an embed token for a dashboard.

    Generates a secure, signed token that allows embedding the dashboard
    in external applications via iframe.
    """
    try:
        # Verify user has access to the dashboard
        dashboard_service = get_dashboard_service()
        try:
            dashboard_service.get_dashboard(dashboard_id, current_user.sub)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard {dashboard_id} not found",
            )

        embed_service = get_embed_service()

        token_data = EmbedTokenCreate(
            expires_in_hours=request.expires_in_hours,
            allowed_domains=request.allowed_domains,
            mode=EmbedMode(request.mode),
            theme=EmbedTheme(request.theme),
            show_title=request.show_title,
            show_refresh=request.show_refresh,
            show_fullscreen=request.show_fullscreen,
            widget_ids=request.widget_ids,
            custom_css=request.custom_css,
        )

        token = embed_service.create_embed_token(
            dashboard_id=dashboard_id,
            user_id=current_user.sub,
            token_data=token_data,
        )

        logger.info(f"Embed token created: {token.token_id} by {current_user.sub}")
        return embed_token_to_response(token)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create embed token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create embed token",
        )


@router.get("/{dashboard_id}/embed/{token_id}", response_model=EmbedTokenResponse)
async def get_embed_token(
    dashboard_id: str,
    token_id: str,
    current_user: User = Depends(get_current_user),
) -> EmbedTokenResponse:
    """Get an embed token by ID."""
    try:
        service = get_embed_service()
        token = service.get_token(token_id=token_id, user_id=current_user.sub)

        if token.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Embed token {token_id} not found for dashboard",
            )

        return embed_token_to_response(token)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embed token {token_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this embed token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get embed token {sanitize_log(token_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get embed token",
        )


@router.put("/{dashboard_id}/embed/{token_id}", response_model=EmbedTokenResponse)
async def update_embed_token(
    dashboard_id: str,
    token_id: str,
    request: EmbedTokenUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> EmbedTokenResponse:
    """Update an embed token."""
    try:
        service = get_embed_service()

        # Verify token belongs to dashboard
        token = service.get_token(token_id=token_id, user_id=current_user.sub)
        if token.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Embed token {token_id} not found for dashboard",
            )

        updates = EmbedTokenUpdate(
            is_active=request.is_active,
            allowed_domains=request.allowed_domains,
        )

        updated_token = service.update_token(
            token_id=token_id,
            user_id=current_user.sub,
            updates=updates,
        )

        logger.info(
            f"Embed token updated: {sanitize_log(token_id)} by {sanitize_log(current_user.sub)}"
        )
        return embed_token_to_response(updated_token)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embed token {token_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update this embed token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update embed token {sanitize_log(token_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update embed token",
        )


@router.delete(
    "/{dashboard_id}/embed/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_embed_token(
    dashboard_id: str,
    token_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete (revoke) an embed token."""
    try:
        service = get_embed_service()

        # Verify token belongs to dashboard
        token = service.get_token(token_id=token_id, user_id=current_user.sub)
        if token.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Embed token {token_id} not found for dashboard",
            )

        service.delete_token(token_id=token_id, user_id=current_user.sub)
        logger.info(
            f"Embed token deleted: {sanitize_log(token_id)} by {sanitize_log(current_user.sub)}"
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embed token {token_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this embed token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete embed token {sanitize_log(token_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete embed token",
        )


@router.post("/{dashboard_id}/embed/{token_id}/revoke")
async def revoke_embed_token(
    dashboard_id: str,
    token_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke an embed token (deactivate without deleting)."""
    try:
        service = get_embed_service()

        # Verify token belongs to dashboard
        token = service.get_token(token_id=token_id, user_id=current_user.sub)
        if token.dashboard_id != dashboard_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Embed token {token_id} not found for dashboard",
            )

        service.revoke_token(token_id=token_id, user_id=current_user.sub)
        logger.info(
            f"Embed token revoked: {sanitize_log(token_id)} by {sanitize_log(current_user.sub)}"
        )

        return {"message": f"Embed token {token_id} has been revoked"}

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embed token {token_id} not found",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can revoke this embed token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to revoke embed token {sanitize_log(token_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke embed token",
        )


@router.get("/user/embed-tokens", response_model=EmbedTokenListResponse)
async def list_user_embed_tokens(
    current_user: User = Depends(get_current_user),
) -> EmbedTokenListResponse:
    """List all embed tokens for the current user."""
    try:
        service = get_embed_service()
        tokens = service.list_user_tokens(user_id=current_user.sub)
        return EmbedTokenListResponse(
            tokens=[embed_token_to_response(t) for t in tokens],
            total=len(tokens),
        )
    except Exception as e:
        logger.error(f"Failed to list user embed tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list embed tokens",
        )


# =============================================================================
# Public Embed Endpoint (No Auth Required)
# =============================================================================

embed_router = APIRouter(
    prefix="/api/v1/embed",
    tags=["Embed"],
)


@embed_router.get("/{token}")
async def get_embedded_dashboard(
    token: str,
    domain: str | None = Query(default=None, description="Requesting domain"),
) -> EmbedDashboardResponse:
    """Get dashboard data for embedding (public endpoint).

    This endpoint validates the embed token and returns dashboard data
    suitable for rendering in an iframe or external application.
    """
    try:
        embed_service = get_embed_service()

        # Validate token
        validation = embed_service.validate_token(
            token=token,
            requesting_domain=domain,
        )

        if not validation.valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=validation.error or "Invalid embed token",
            )

        # Get dashboard data
        dashboard_service = get_dashboard_service()

        # Use internal method to bypass auth for embed access
        dashboard = dashboard_service._get_dashboard_by_id(validation.dashboard_id)

        if not dashboard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dashboard not found",
            )

        # Filter widgets if specified
        widgets = dashboard.widgets
        if validation.widget_ids:
            widgets = [w for w in widgets if w.get("id") in validation.widget_ids]

        return EmbedDashboardResponse(
            dashboard_id=dashboard.dashboard_id,
            name=dashboard.name,
            description=dashboard.description,
            layout={"items": [item.model_dump() for item in dashboard.layout.items]},
            widgets=[
                w.model_dump() if hasattr(w, "model_dump") else w for w in widgets
            ],
            mode=validation.mode.value if validation.mode else "minimal",
            theme=validation.theme.value if validation.theme else "light",
            show_title=validation.show_title,
            show_refresh=validation.show_refresh,
            show_fullscreen=validation.show_fullscreen,
            custom_css=validation.custom_css,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get embedded dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load embedded dashboard",
        )
