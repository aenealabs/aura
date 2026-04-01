"""
Project Aura - Integration Management API Endpoints

REST API endpoints for the Integration Hub (ADR-028 Phase 3 - Issue #34).
Manages external integrations including security scanners, CI/CD pipelines,
and enterprise tools.

Endpoints:
- GET    /api/v1/integrations           - List configured integrations
- GET    /api/v1/integrations/{id}      - Get integration details
- POST   /api/v1/integrations           - Create new integration
- PUT    /api/v1/integrations/{id}      - Update integration
- DELETE /api/v1/integrations/{id}      - Remove integration
- POST   /api/v1/integrations/{id}/test - Test connection
- GET    /api/v1/integrations/available - List available connectors
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])


# ============================================================================
# Enums
# ============================================================================


class IntegrationCategory(str, Enum):
    """Category of integration."""

    SECURITY = "security"
    CICD = "cicd"
    MONITORING = "monitoring"
    CLOUD = "cloud"
    COMMUNICATION = "communication"
    TICKETING = "ticketing"


class IntegrationStatus(str, Enum):
    """Status of an integration connection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"


class AuthType(str, Enum):
    """Authentication type for integrations."""

    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN = "token"
    CERTIFICATE = "certificate"


class SyncFrequency(str, Enum):
    """Data sync frequency options."""

    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


# ============================================================================
# Pydantic Models
# ============================================================================


class IntegrationField(BaseModel):
    """Configuration field for an integration."""

    name: str = Field(description="Field name/key")
    label: str = Field(description="Display label")
    type: str = Field(description="Field type (text, password, select, url)")
    required: bool = Field(True, description="Whether field is required")
    placeholder: str | None = Field(None, description="Placeholder text")
    options: list[str] | None = Field(None, description="Options for select type")
    description: str | None = Field(None, description="Help text for field")


class FieldMapping(BaseModel):
    """Mapping between integration field and Aura field."""

    source_field: str = Field(description="Field name in external system")
    target_field: str = Field(description="Field name in Aura")
    transform: str | None = Field(None, description="Optional transformation")


class AvailableIntegration(BaseModel):
    """An integration connector available for configuration."""

    id: str = Field(description="Unique connector identifier")
    name: str = Field(description="Display name")
    description: str = Field(description="Brief description")
    category: IntegrationCategory = Field(description="Integration category")
    icon: str = Field(description="Icon identifier")
    auth_type: AuthType = Field(description="Authentication method")
    config_fields: list[IntegrationField] = Field(description="Configuration fields")
    features: list[str] = Field(description="Supported features")
    documentation_url: str | None = Field(None, description="Link to docs")


class ConfiguredIntegration(BaseModel):
    """A configured and active integration."""

    id: str = Field(description="Unique integration instance ID")
    connector_id: str = Field(description="Base connector ID")
    name: str = Field(description="User-defined name")
    description: str | None = Field(None, description="User-defined description")
    category: IntegrationCategory = Field(description="Integration category")
    status: IntegrationStatus = Field(description="Connection status")
    icon: str = Field(description="Icon identifier")
    config: dict[str, Any] = Field(
        description="Configuration (sensitive fields masked)"
    )
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    sync_frequency: SyncFrequency = Field(SyncFrequency.DAILY)
    last_sync: str | None = Field(None, description="Last successful sync timestamp")
    last_error: str | None = Field(None, description="Last error message if any")
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")
    sync_stats: dict[str, int] | None = Field(None, description="Sync statistics")


class CreateIntegrationRequest(BaseModel):
    """Request to create a new integration."""

    connector_id: str = Field(description="Base connector ID to use")
    name: str = Field(min_length=1, max_length=100, description="Display name")
    description: str | None = Field(None, max_length=500)
    config: dict[str, Any] = Field(description="Configuration values")
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    sync_frequency: SyncFrequency = Field(SyncFrequency.DAILY)


class UpdateIntegrationRequest(BaseModel):
    """Request to update an existing integration."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    config: dict[str, Any] | None = Field(None)
    field_mappings: list[FieldMapping] | None = Field(None)
    sync_frequency: SyncFrequency | None = Field(None)


class TestConnectionResult(BaseModel):
    """Result of testing an integration connection."""

    success: bool = Field(description="Whether connection test passed")
    message: str = Field(description="Status message")
    latency_ms: float | None = Field(None, description="Connection latency")
    details: dict[str, Any] | None = Field(None, description="Additional details")
    tested_at: str = Field(description="Test timestamp")


class IntegrationListResponse(BaseModel):
    """Response for listing integrations."""

    integrations: list[ConfiguredIntegration]
    total: int


class AvailableIntegrationsResponse(BaseModel):
    """Response for listing available connectors."""

    integrations: list[AvailableIntegration]
    categories: list[dict[str, str]]


# ============================================================================
# In-Memory Data Store (Replace with service in production)
# ============================================================================

# Available integration connectors (static catalog)
_available_integrations: dict[str, dict[str, Any]] = {
    "crowdstrike": {
        "id": "crowdstrike",
        "name": "CrowdStrike Falcon",
        "description": "Endpoint detection and response platform",
        "category": IntegrationCategory.SECURITY,
        "icon": "shield-check",
        "auth_type": AuthType.OAUTH2,
        "config_fields": [
            {
                "name": "client_id",
                "label": "Client ID",
                "type": "text",
                "required": True,
                "placeholder": "Enter your CrowdStrike Client ID",
            },
            {
                "name": "client_secret",
                "label": "Client Secret",
                "type": "password",
                "required": True,
                "placeholder": "Enter your Client Secret",
            },
            {
                "name": "base_url",
                "label": "API Base URL",
                "type": "select",
                "required": True,
                "options": [
                    "https://api.crowdstrike.com",
                    "https://api.us-2.crowdstrike.com",
                    "https://api.eu-1.crowdstrike.com",
                    "https://api.laggar.gcw.crowdstrike.com",
                ],
            },
        ],
        "features": ["vulnerability-sync", "detection-alerts", "host-inventory"],
        "documentation_url": "https://falcon.crowdstrike.com/documentation",
    },
    "qualys": {
        "id": "qualys",
        "name": "Qualys VMDR",
        "description": "Vulnerability management, detection and response",
        "category": IntegrationCategory.SECURITY,
        "icon": "bug-ant",
        "auth_type": AuthType.BASIC,
        "config_fields": [
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {
                "name": "password",
                "label": "Password",
                "type": "password",
                "required": True,
            },
            {
                "name": "platform",
                "label": "Platform",
                "type": "select",
                "required": True,
                "options": [
                    "US1",
                    "US2",
                    "US3",
                    "US4",
                    "EU1",
                    "EU2",
                    "IN1",
                    "CA1",
                    "AE1",
                ],
            },
        ],
        "features": ["vulnerability-sync", "compliance-reports", "asset-inventory"],
        "documentation_url": "https://www.qualys.com/docs/",
    },
    "github": {
        "id": "github",
        "name": "GitHub",
        "description": "Code repository and CI/CD workflows",
        "category": IntegrationCategory.CICD,
        "icon": "code-bracket",
        "auth_type": AuthType.TOKEN,
        "config_fields": [
            {
                "name": "token",
                "label": "Personal Access Token",
                "type": "password",
                "required": True,
                "description": "Token with repo and workflow scopes",
            },
            {
                "name": "organization",
                "label": "Organization",
                "type": "text",
                "required": False,
                "placeholder": "Optional: GitHub organization name",
            },
        ],
        "features": [
            "code-sync",
            "pr-integration",
            "actions-trigger",
            "security-alerts",
        ],
        "documentation_url": "https://docs.github.com/en/rest",
    },
    "gitlab": {
        "id": "gitlab",
        "name": "GitLab",
        "description": "DevOps platform with CI/CD pipelines",
        "category": IntegrationCategory.CICD,
        "icon": "code-bracket-square",
        "auth_type": AuthType.TOKEN,
        "config_fields": [
            {
                "name": "token",
                "label": "Access Token",
                "type": "password",
                "required": True,
            },
            {
                "name": "base_url",
                "label": "GitLab URL",
                "type": "url",
                "required": True,
                "placeholder": "https://gitlab.com or self-hosted URL",
            },
        ],
        "features": [
            "code-sync",
            "mr-integration",
            "pipeline-trigger",
            "security-scanning",
        ],
        "documentation_url": "https://docs.gitlab.com/ee/api/",
    },
    "jira": {
        "id": "jira",
        "name": "Jira",
        "description": "Issue and project tracking",
        "category": IntegrationCategory.TICKETING,
        "icon": "ticket",
        "auth_type": AuthType.API_KEY,
        "config_fields": [
            {"name": "email", "label": "Email", "type": "text", "required": True},
            {
                "name": "api_token",
                "label": "API Token",
                "type": "password",
                "required": True,
            },
            {
                "name": "base_url",
                "label": "Jira URL",
                "type": "url",
                "required": True,
                "placeholder": "https://your-domain.atlassian.net",
            },
            {
                "name": "project_key",
                "label": "Default Project Key",
                "type": "text",
                "required": False,
            },
        ],
        "features": [
            "issue-creation",
            "issue-sync",
            "workflow-triggers",
            "custom-fields",
        ],
        "documentation_url": "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
    },
    "slack": {
        "id": "slack",
        "name": "Slack",
        "description": "Team communication and notifications",
        "category": IntegrationCategory.COMMUNICATION,
        "icon": "chat-bubble-left-right",
        "auth_type": AuthType.OAUTH2,
        "config_fields": [
            {
                "name": "bot_token",
                "label": "Bot Token",
                "type": "password",
                "required": True,
                "description": "xoxb- token from your Slack app",
            },
            {
                "name": "default_channel",
                "label": "Default Channel",
                "type": "text",
                "required": False,
                "placeholder": "#security-alerts",
            },
        ],
        "features": ["notifications", "interactive-messages", "channel-alerts"],
        "documentation_url": "https://api.slack.com/",
    },
    "pagerduty": {
        "id": "pagerduty",
        "name": "PagerDuty",
        "description": "Incident management and alerting",
        "category": IntegrationCategory.MONITORING,
        "icon": "bell-alert",
        "auth_type": AuthType.API_KEY,
        "config_fields": [
            {
                "name": "api_key",
                "label": "API Key",
                "type": "password",
                "required": True,
            },
            {
                "name": "service_id",
                "label": "Service ID",
                "type": "text",
                "required": True,
                "description": "PagerDuty service to create incidents in",
            },
        ],
        "features": ["incident-creation", "alert-routing", "on-call-lookup"],
        "documentation_url": "https://developer.pagerduty.com/api-reference/",
    },
    "aws": {
        "id": "aws",
        "name": "AWS Security Hub",
        "description": "AWS security findings aggregation",
        "category": IntegrationCategory.CLOUD,
        "icon": "cloud",
        "auth_type": AuthType.API_KEY,
        "config_fields": [
            {
                "name": "access_key_id",
                "label": "Access Key ID",
                "type": "text",
                "required": True,
            },
            {
                "name": "secret_access_key",
                "label": "Secret Access Key",
                "type": "password",
                "required": True,
            },
            {
                "name": "region",
                "label": "Region",
                "type": "select",
                "required": True,
                "options": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "eu-west-1",
                    "eu-central-1",
                ],
            },
        ],
        "features": ["findings-sync", "compliance-status", "resource-inventory"],
        "documentation_url": "https://docs.aws.amazon.com/securityhub/",
    },
    "datadog": {
        "id": "datadog",
        "name": "Datadog",
        "description": "Infrastructure monitoring and APM",
        "category": IntegrationCategory.MONITORING,
        "icon": "chart-bar",
        "auth_type": AuthType.API_KEY,
        "config_fields": [
            {
                "name": "api_key",
                "label": "API Key",
                "type": "password",
                "required": True,
            },
            {
                "name": "app_key",
                "label": "Application Key",
                "type": "password",
                "required": True,
            },
            {
                "name": "site",
                "label": "Datadog Site",
                "type": "select",
                "required": True,
                "options": [
                    "datadoghq.com",
                    "us3.datadoghq.com",
                    "us5.datadoghq.com",
                    "datadoghq.eu",
                ],
            },
        ],
        "features": ["metrics-sync", "log-shipping", "apm-traces", "dashboards"],
        "documentation_url": "https://docs.datadoghq.com/api/",
    },
    "servicenow": {
        "id": "servicenow",
        "name": "ServiceNow",
        "description": "IT service management platform",
        "category": IntegrationCategory.TICKETING,
        "icon": "building-office",
        "auth_type": AuthType.BASIC,
        "config_fields": [
            {
                "name": "instance_url",
                "label": "Instance URL",
                "type": "url",
                "required": True,
                "placeholder": "https://your-instance.service-now.com",
            },
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {
                "name": "password",
                "label": "Password",
                "type": "password",
                "required": True,
            },
        ],
        "features": ["incident-creation", "cmdb-sync", "change-requests", "workflows"],
        "documentation_url": "https://developer.servicenow.com/",
    },
}

# Configured integrations (dynamic, user-created)
_configured_integrations: dict[str, dict[str, Any]] = {}


def _mask_sensitive_config(config: dict[str, Any], connector_id: str) -> dict[str, Any]:
    """Mask sensitive fields in configuration."""
    connector = _available_integrations.get(connector_id)
    if not connector:
        return config

    masked = {}
    sensitive_types = {"password"}
    sensitive_fields = {
        f["name"]
        for f in connector["config_fields"]
        if f.get("type") in sensitive_types
    }

    for key, value in config.items():
        if key in sensitive_fields and value:
            masked[key] = "••••••••"
        else:
            masked[key] = value

    return masked


def _validate_config(connector_id: str, config: dict[str, Any]) -> list[str]:
    """Validate configuration against connector requirements."""
    connector = _available_integrations.get(connector_id)
    if not connector:
        return [f"Unknown connector: {connector_id}"]

    errors = []
    for field in connector["config_fields"]:
        if field["required"] and not config.get(field["name"]):
            errors.append(f"Required field missing: {field['label']}")

    return errors


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/available", response_model=AvailableIntegrationsResponse)
async def list_available_integrations(
    category: IntegrationCategory | None = Query(  # noqa: B008
        None, description="Filter by category"
    ),
) -> AvailableIntegrationsResponse:
    """
    List available integration connectors.

    Returns the catalog of integration types that can be configured.
    """
    integrations = []
    for data in _available_integrations.values():
        if category and data["category"] != category:
            continue
        integrations.append(
            AvailableIntegration(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                category=data["category"],
                icon=data["icon"],
                auth_type=data["auth_type"],
                config_fields=[IntegrationField(**f) for f in data["config_fields"]],
                features=data["features"],
                documentation_url=data.get("documentation_url"),
            )
        )

    # Sort by category then name
    integrations.sort(key=lambda x: (x.category.value, x.name))

    categories = [
        {
            "id": IntegrationCategory.SECURITY.value,
            "name": "Security",
            "icon": "shield-check",
        },
        {"id": IntegrationCategory.CICD.value, "name": "CI/CD", "icon": "code-bracket"},
        {
            "id": IntegrationCategory.MONITORING.value,
            "name": "Monitoring",
            "icon": "chart-bar",
        },
        {"id": IntegrationCategory.CLOUD.value, "name": "Cloud", "icon": "cloud"},
        {
            "id": IntegrationCategory.COMMUNICATION.value,
            "name": "Communication",
            "icon": "chat-bubble-left-right",
        },
        {
            "id": IntegrationCategory.TICKETING.value,
            "name": "Ticketing",
            "icon": "ticket",
        },
    ]

    return AvailableIntegrationsResponse(
        integrations=integrations, categories=categories
    )


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    category: IntegrationCategory | None = Query(  # noqa: B008
        None, description="Filter by category"
    ),
    status: IntegrationStatus | None = Query(  # noqa: B008
        None, description="Filter by status"
    ),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
) -> IntegrationListResponse:
    """
    List configured integrations.

    Returns all integration instances the user has configured.
    """
    all_integrations = list(_configured_integrations.values())

    # Apply filters
    if category:
        all_integrations = [i for i in all_integrations if i["category"] == category]
    if status:
        all_integrations = [i for i in all_integrations if i["status"] == status]

    # Sort by name
    all_integrations.sort(key=lambda x: x["name"].lower())

    total = len(all_integrations)
    paginated = all_integrations[offset : offset + limit]

    integrations = [
        ConfiguredIntegration(
            id=i["id"],
            connector_id=i["connector_id"],
            name=i["name"],
            description=i.get("description"),
            category=i["category"],
            status=i["status"],
            icon=i["icon"],
            config=_mask_sensitive_config(i["config"], i["connector_id"]),
            field_mappings=[FieldMapping(**fm) for fm in i.get("field_mappings", [])],
            sync_frequency=i.get("sync_frequency", SyncFrequency.DAILY),
            last_sync=i.get("last_sync"),
            last_error=i.get("last_error"),
            created_at=i["created_at"],
            updated_at=i["updated_at"],
            sync_stats=i.get("sync_stats"),
        )
        for i in paginated
    ]

    return IntegrationListResponse(integrations=integrations, total=total)


@router.get("/{integration_id}", response_model=ConfiguredIntegration)
async def get_integration(integration_id: str) -> ConfiguredIntegration:
    """
    Get a specific integration by ID.
    """
    integration = _configured_integrations.get(integration_id)
    if not integration:
        raise HTTPException(
            status_code=404, detail=f"Integration {integration_id} not found"
        )

    return ConfiguredIntegration(
        id=integration["id"],
        connector_id=integration["connector_id"],
        name=integration["name"],
        description=integration.get("description"),
        category=integration["category"],
        status=integration["status"],
        icon=integration["icon"],
        config=_mask_sensitive_config(
            integration["config"], integration["connector_id"]
        ),
        field_mappings=[
            FieldMapping(**fm) for fm in integration.get("field_mappings", [])
        ],
        sync_frequency=integration.get("sync_frequency", SyncFrequency.DAILY),
        last_sync=integration.get("last_sync"),
        last_error=integration.get("last_error"),
        created_at=integration["created_at"],
        updated_at=integration["updated_at"],
        sync_stats=integration.get("sync_stats"),
    )


@router.post("", response_model=ConfiguredIntegration, status_code=201)
async def create_integration(
    request: CreateIntegrationRequest,
) -> ConfiguredIntegration:
    """
    Create a new integration.

    Configures a new integration instance from an available connector.
    """
    connector = _available_integrations.get(request.connector_id)
    if not connector:
        raise HTTPException(
            status_code=400, detail=f"Unknown connector: {request.connector_id}"
        )

    # Validate configuration
    errors = _validate_config(request.connector_id, request.config)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    now = datetime.now(timezone.utc).isoformat()
    integration_id = str(uuid.uuid4())

    integration = {
        "id": integration_id,
        "connector_id": request.connector_id,
        "name": request.name,
        "description": request.description,
        "category": connector["category"],
        "status": IntegrationStatus.PENDING,
        "icon": connector["icon"],
        "config": request.config,
        "field_mappings": [fm.model_dump() for fm in request.field_mappings],
        "sync_frequency": request.sync_frequency,
        "last_sync": None,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
        "sync_stats": None,
    }

    _configured_integrations[integration_id] = integration
    logger.info(f"Created integration: {request.name} ({request.connector_id})")

    return ConfiguredIntegration(
        id=integration["id"],
        connector_id=integration["connector_id"],
        name=integration["name"],
        description=integration.get("description"),
        category=integration["category"],
        status=integration["status"],
        icon=integration["icon"],
        config=_mask_sensitive_config(
            integration["config"], integration["connector_id"]
        ),
        field_mappings=[
            FieldMapping(**fm) for fm in integration.get("field_mappings", [])
        ],
        sync_frequency=integration.get("sync_frequency", SyncFrequency.DAILY),
        last_sync=integration.get("last_sync"),
        last_error=integration.get("last_error"),
        created_at=integration["created_at"],
        updated_at=integration["updated_at"],
        sync_stats=integration.get("sync_stats"),
    )


@router.put("/{integration_id}", response_model=ConfiguredIntegration)
async def update_integration(
    integration_id: str,
    request: UpdateIntegrationRequest,
) -> ConfiguredIntegration:
    """
    Update an existing integration.
    """
    integration = _configured_integrations.get(integration_id)
    if not integration:
        raise HTTPException(
            status_code=404, detail=f"Integration {integration_id} not found"
        )

    # Update fields if provided
    if request.name is not None:
        integration["name"] = request.name
    if request.description is not None:
        integration["description"] = request.description
    if request.config is not None:
        errors = _validate_config(integration["connector_id"], request.config)
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})
        integration["config"] = request.config
        # Reset status when config changes
        integration["status"] = IntegrationStatus.PENDING
    if request.field_mappings is not None:
        integration["field_mappings"] = [
            fm.model_dump() for fm in request.field_mappings
        ]
    if request.sync_frequency is not None:
        integration["sync_frequency"] = request.sync_frequency

    integration["updated_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(f"Updated integration: {integration['name']} ({integration_id})")

    return ConfiguredIntegration(
        id=integration["id"],
        connector_id=integration["connector_id"],
        name=integration["name"],
        description=integration.get("description"),
        category=integration["category"],
        status=integration["status"],
        icon=integration["icon"],
        config=_mask_sensitive_config(
            integration["config"], integration["connector_id"]
        ),
        field_mappings=[
            FieldMapping(**fm) for fm in integration.get("field_mappings", [])
        ],
        sync_frequency=integration.get("sync_frequency", SyncFrequency.DAILY),
        last_sync=integration.get("last_sync"),
        last_error=integration.get("last_error"),
        created_at=integration["created_at"],
        updated_at=integration["updated_at"],
        sync_stats=integration.get("sync_stats"),
    )


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(integration_id: str) -> None:
    """
    Delete an integration.
    """
    if integration_id not in _configured_integrations:
        raise HTTPException(
            status_code=404, detail=f"Integration {integration_id} not found"
        )

    integration = _configured_integrations.pop(integration_id)
    logger.info(f"Deleted integration: {integration['name']} ({integration_id})")


@router.post("/{integration_id}/test", response_model=TestConnectionResult)
async def test_integration_connection(integration_id: str) -> TestConnectionResult:
    """
    Test an integration connection.

    Validates credentials and connectivity to the external service.
    """
    import random

    integration = _configured_integrations.get(integration_id)
    if not integration:
        raise HTTPException(
            status_code=404, detail=f"Integration {integration_id} not found"
        )

    # Mock connection test (in production, actually test the connection)
    now = datetime.now(timezone.utc).isoformat()

    # Simulate success/failure with 85% success rate
    success = random.random() < 0.85
    latency = round(random.uniform(50, 500), 1)

    if success:
        integration["status"] = IntegrationStatus.CONNECTED
        integration["last_error"] = None
        integration["last_sync"] = now
        integration["sync_stats"] = {
            "items_synced": random.randint(100, 5000),
            "last_duration_ms": random.randint(500, 5000),
            "errors": 0,
        }

        return TestConnectionResult(
            success=True,
            message="Connection successful",
            latency_ms=latency,
            details={
                "api_version": "v1",
                "rate_limit_remaining": random.randint(500, 1000),
                "authenticated_as": integration["config"].get(
                    "username", integration["config"].get("email", "api-user")
                ),
            },
            tested_at=now,
        )
    else:
        integration["status"] = IntegrationStatus.ERROR
        integration["last_error"] = "Authentication failed: Invalid credentials"

        return TestConnectionResult(
            success=False,
            message="Connection failed: Authentication error",
            latency_ms=latency,
            details={
                "error_code": "AUTH_FAILED",
                "suggestion": "Please verify your credentials and try again",
            },
            tested_at=now,
        )


# ============================================================================
# Export Router
# ============================================================================

integration_router = router
