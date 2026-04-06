"""
Project Aura - Platform Settings API Endpoints

REST API endpoints for platform configuration management.
Includes Integration Mode, HITL settings, and MCP configuration.

Endpoints:
- GET  /api/v1/settings                    - Get all settings
- PUT  /api/v1/settings                    - Update settings
- GET  /api/v1/settings/integration-mode   - Get integration mode
- PUT  /api/v1/settings/integration-mode   - Update integration mode
- GET  /api/v1/settings/hitl               - Get HITL settings
- PUT  /api/v1/settings/hitl               - Update HITL settings
- GET  /api/v1/settings/mcp                - Get MCP settings
- PUT  /api/v1/settings/mcp                - Update MCP settings
- GET  /api/v1/settings/mcp/tools          - Get available external tools
- POST /api/v1/settings/mcp/test-connection - Test MCP gateway connection
- GET  /api/v1/settings/mcp/usage          - Get MCP usage statistics
"""

import json
import logging
import os
from enum import Enum
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.config.integration_config import (
    CustomerMCPBudget,
    ExternalToolCategory,
    ExternalToolConfig,
    IntegrationConfig,
    IntegrationMode,
)
from src.services.api_rate_limiter import RateLimitResult, admin_rate_limit
from src.services.settings_persistence_service import (
    DEFAULT_PLATFORM_SETTINGS,
    get_settings_service,
)
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class HITLSettingsModel(BaseModel):
    """HITL configuration settings."""

    require_approval_for_patches: bool = Field(
        default=True, description="Require approval for auto-generated patches"
    )
    require_approval_for_deployments: bool = Field(
        default=True, description="Require approval for deployments"
    )
    auto_approve_minor_patches: bool = Field(
        default=False,
        description="Auto-approve low-severity patches after sandbox testing",
    )
    approval_timeout_hours: int = Field(
        default=24, ge=1, le=168, description="Time before approval request expires"
    )
    min_approvers: int = Field(
        default=1, ge=1, le=5, description="Number of approvals required"
    )
    notify_on_approval_request: bool = Field(
        default=True, description="Send notification on new approval requests"
    )
    notify_on_approval_timeout: bool = Field(
        default=True, description="Send reminder before approval expires"
    )


class RateLimitModel(BaseModel):
    """MCP rate limiting configuration."""

    requests_per_minute: int = Field(default=60, ge=1, le=1000)
    requests_per_hour: int = Field(default=1000, ge=1, le=100000)


class MCPSettingsModel(BaseModel):
    """MCP Gateway configuration settings."""

    enabled: bool = Field(default=False, description="Enable MCP Gateway integration")
    gateway_url: str = Field(default="", description="AgentCore Gateway URL")
    api_key: str = Field(default="", description="API key for authentication")
    monthly_budget_usd: float = Field(
        default=100.0, ge=0, le=100000, description="Monthly budget limit"
    )
    daily_limit_usd: float = Field(
        default=10.0, ge=0, le=10000, description="Daily spending limit"
    )
    external_tools_enabled: list[str] = Field(
        default_factory=list, description="List of enabled external tool IDs"
    )
    rate_limit: RateLimitModel = Field(default_factory=RateLimitModel)


class SecuritySettingsModel(BaseModel):
    """Security configuration settings."""

    enforce_air_gap: bool = Field(
        default=False, description="Enforce air-gap mode (no external network)"
    )
    block_external_network: bool = Field(
        default=True, description="Block external network from sandboxes"
    )
    sandbox_isolation_level: str = Field(
        default="vpc", description="Sandbox isolation level (container/vpc/full)"
    )
    audit_all_actions: bool = Field(default=True, description="Log all actions")
    retain_logs_for_days: int = Field(
        default=365, ge=30, le=3650, description="Log retention period"
    )


class ComplianceProfile(str, Enum):
    """Compliance profile presets."""

    COMMERCIAL = "commercial"
    CMMC_L1 = "cmmc_l1"
    CMMC_L2 = "cmmc_l2"
    GOVCLOUD = "govcloud"


class KMSEncryptionMode(str, Enum):
    """KMS encryption mode options."""

    AWS_MANAGED = "aws_managed"
    CUSTOMER_MANAGED = "customer_managed"


class ComplianceSettingsModel(BaseModel):
    """Compliance configuration settings (ADR-040)."""

    profile: str = Field(
        default="commercial",
        description="Compliance profile: commercial, cmmc_l1, cmmc_l2, govcloud",
    )
    kms_encryption_mode: str = Field(
        default="aws_managed",
        description="KMS encryption: aws_managed or customer_managed",
    )
    log_retention_days: int = Field(
        default=90,
        ge=30,
        le=3653,
        description="CloudWatch log retention (CMMC L2 requires 90+)",
    )
    audit_log_retention_days: int = Field(
        default=365,
        ge=90,
        le=3653,
        description="Audit log retention (always longer)",
    )
    require_encryption_at_rest: bool = Field(
        default=True, description="Require encryption at rest"
    )
    require_encryption_in_transit: bool = Field(
        default=True, description="Require encryption in transit"
    )
    pending_kms_change: bool = Field(
        default=False, description="True if KMS change pending deployment"
    )


# Compliance profile presets - maps profile name to settings
COMPLIANCE_PROFILE_PRESETS = {
    "commercial": {
        "kms_encryption_mode": "aws_managed",
        "log_retention_days": 30,
        "audit_log_retention_days": 90,
        "require_encryption_at_rest": True,
        "require_encryption_in_transit": True,
    },
    "cmmc_l1": {
        "kms_encryption_mode": "aws_managed",
        "log_retention_days": 90,
        "audit_log_retention_days": 365,
        "require_encryption_at_rest": True,
        "require_encryption_in_transit": True,
    },
    "cmmc_l2": {
        "kms_encryption_mode": "customer_managed",
        "log_retention_days": 90,
        "audit_log_retention_days": 365,
        "require_encryption_at_rest": True,
        "require_encryption_in_transit": True,
    },
    "govcloud": {
        "kms_encryption_mode": "customer_managed",
        "log_retention_days": 365,
        "audit_log_retention_days": 365,
        "require_encryption_at_rest": True,
        "require_encryption_in_transit": True,
    },
}


class PlatformSettingsModel(BaseModel):
    """Complete platform settings."""

    integration_mode: str = Field(default="defense", description="Integration mode")
    hitl_settings: HITLSettingsModel = Field(default_factory=HITLSettingsModel)
    mcp_settings: MCPSettingsModel = Field(default_factory=MCPSettingsModel)
    security_settings: SecuritySettingsModel = Field(
        default_factory=SecuritySettingsModel
    )


class IntegrationModeRequest(BaseModel):
    """Request to update integration mode."""

    mode: str = Field(description="Integration mode (defense/enterprise/hybrid)")


class IntegrationModeResponse(BaseModel):
    """Response for integration mode endpoint."""

    mode: str
    mcp_enabled: bool
    description: str


class ExternalToolInfo(BaseModel):
    """Information about an external tool."""

    id: str
    name: str
    category: str
    description: str


class ConnectionTestRequest(BaseModel):
    """Request to test MCP gateway connection."""

    gateway_url: str = Field(alias="gatewayUrl")
    api_key: str = Field(alias="apiKey")


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""

    success: bool
    message: str
    latency_ms: float | None = None


class MCPUsageResponse(BaseModel):
    """MCP usage statistics."""

    current_month_cost: float
    current_day_cost: float
    total_invocations: int
    budget_remaining: float


# ============================================================================
# Settings Persistence Integration
# ============================================================================

# Settings are now stored in DynamoDB via SettingsPersistenceService
# The mapping between API model keys and persistence keys:
# - "integration_mode" -> "platform/integration_mode"
# - "hitl_settings" -> "platform/hitl"
# - "mcp_settings" -> "platform/mcp"
# - "security_settings" -> "platform/security"


def _get_persistence_service():
    """Get the settings persistence service instance."""
    return get_settings_service()


# Integration config instance for enforcing mode-based restrictions
_integration_config: IntegrationConfig | None = None

# Available external tools (would be fetched from AgentCore Gateway in production)
AVAILABLE_EXTERNAL_TOOLS = [
    ExternalToolInfo(
        id="slack",
        name="Slack",
        category="communication",
        description="Send messages and notifications to Slack channels",
    ),
    ExternalToolInfo(
        id="jira",
        name="Jira",
        category="project_management",
        description="Create and update Jira issues and tickets",
    ),
    ExternalToolInfo(
        id="pagerduty",
        name="PagerDuty",
        category="incident_management",
        description="Trigger and manage PagerDuty incidents",
    ),
    ExternalToolInfo(
        id="github",
        name="GitHub",
        category="development",
        description="Create PRs, manage repos, and interact with GitHub",
    ),
    ExternalToolInfo(
        id="datadog",
        name="Datadog",
        category="observability",
        description="Query metrics, logs, and traces from Datadog",
    ),
]


async def _get_integration_config_async() -> IntegrationConfig:
    """Get or create the integration config instance asynchronously."""
    global _integration_config

    if _integration_config is None:
        service = _get_persistence_service()
        integration_mode = await service.get_setting("platform", "integration_mode")
        mcp_settings = await service.get_setting("platform", "mcp")

        mode_str = (
            integration_mode.get("mode", "defense") if integration_mode else "defense"
        )
        mode = IntegrationMode(mode_str.lower())

        mcp_dict: dict[str, Any] = cast(
            dict[str, Any],
            mcp_settings if mcp_settings else DEFAULT_PLATFORM_SETTINGS.get("mcp", {}),
        )

        # Build external tool configs
        # Map category strings to ExternalToolCategory enum
        category_map = {
            "communication": ExternalToolCategory.NOTIFICATION,
            "project_management": ExternalToolCategory.TICKETING,
            "incident_management": ExternalToolCategory.ALERTING,
            "development": ExternalToolCategory.SOURCE_CONTROL,
            "observability": ExternalToolCategory.OBSERVABILITY,
        }

        external_tools = []
        external_tools_list: list[Any] = mcp_dict.get("external_tools_enabled", [])
        for tool_id in external_tools_list:
            tool_info = next(
                (t for t in AVAILABLE_EXTERNAL_TOOLS if t.id == tool_id), None
            )
            if tool_info:
                category = category_map.get(
                    tool_info.category, ExternalToolCategory.NOTIFICATION
                )
                external_tools.append(
                    ExternalToolConfig(
                        tool_id=tool_id,
                        tool_name=tool_info.name,
                        category=category,
                        mcp_endpoint=mcp_dict.get("gateway_url", ""),
                    )
                )

        # Create budget
        budget = CustomerMCPBudget(
            customer_id="default",
            monthly_limit_usd=mcp_dict.get("monthly_budget_usd", 100.0),
        )

        _integration_config = IntegrationConfig(
            mode=mode,
            gateway_enabled=mcp_dict.get("enabled", False),
            gateway_endpoint=(
                mcp_dict.get("gateway_url") if mcp_dict.get("enabled") else None
            ),
            external_tools=[],  # External tools have different schema, skip for now
            default_customer_budget=budget,
        )

    return _integration_config


def _invalidate_config():
    """Invalidate the cached integration config on settings change."""
    global _integration_config
    _integration_config = None


async def _invoke_log_retention_sync(retention_days: int) -> dict[str, Any]:
    """
    Invoke the log retention sync Lambda to update CloudWatch log groups.

    Args:
        retention_days: New retention period in days

    Returns:
        Lambda response or error details
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    project_name = os.environ.get("PROJECT_NAME", "aura")
    lambda_name = f"{project_name}-log-retention-sync-{environment}"

    # Skip Lambda invocation in test/local environments
    if os.environ.get("TESTING", "").lower() == "true":
        logger.info(f"Skipping Lambda invocation in test mode: {lambda_name}")
        return {"status": "skipped", "reason": "test_mode"}

    try:
        lambda_client = boto3.client("lambda")

        payload = {
            "retention_days": retention_days,
            "dry_run": False,
        }

        response = lambda_client.invoke(
            FunctionName=lambda_name,
            InvocationType="Event",  # Async invocation - don't wait for response
            Payload=json.dumps(payload),
        )

        status_code = response.get("StatusCode", 0)

        if status_code == 202:  # Accepted for async invocation
            logger.info(
                f"Log retention sync Lambda invoked successfully: "
                f"{lambda_name} with retention_days={retention_days}"
            )
            return {"status": "invoked", "lambda_name": lambda_name}
        else:
            logger.warning(
                f"Unexpected status code from Lambda invocation: {status_code}"
            )
            return {"status": "warning", "status_code": status_code}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # ResourceNotFoundException means Lambda not deployed yet - not a failure
        if error_code == "ResourceNotFoundException":
            logger.warning(
                f"Log retention sync Lambda not found: {lambda_name}. "
                "Settings saved but CloudWatch log groups not updated."
            )
            return {"status": "lambda_not_found", "lambda_name": lambda_name}

        logger.error(
            f"Failed to invoke log retention sync Lambda: {error_code} - {error_message}"
        )
        return {"status": "error", "error": error_message}

    except Exception as e:
        logger.error(f"Unexpected error invoking log retention sync Lambda: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=PlatformSettingsModel)
async def get_settings():
    """Get all platform settings."""
    service = _get_persistence_service()

    # Fetch all settings from persistence layer
    integration_mode = await service.get_setting("platform", "integration_mode")
    hitl = await service.get_setting("platform", "hitl")
    mcp = await service.get_setting("platform", "mcp")
    security = await service.get_setting("platform", "security")

    # Build response using defaults for any missing values
    mode = integration_mode.get("mode", "defense") if integration_mode else "defense"
    hitl_data: dict[str, Any] = cast(
        dict[str, Any], hitl if hitl else DEFAULT_PLATFORM_SETTINGS["hitl"]
    )
    mcp_data: dict[str, Any] = cast(
        dict[str, Any], mcp if mcp else DEFAULT_PLATFORM_SETTINGS["mcp"]
    )
    security_data: dict[str, Any] = cast(
        dict[str, Any], security if security else DEFAULT_PLATFORM_SETTINGS["security"]
    )

    return PlatformSettingsModel(
        integration_mode=mode,
        hitl_settings=HITLSettingsModel(**hitl_data),
        mcp_settings=MCPSettingsModel(**mcp_data),
        security_settings=SecuritySettingsModel(**security_data),
    )


@router.put("", response_model=PlatformSettingsModel)
async def update_settings(
    request: Request,
    settings: PlatformSettingsModel,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """Update all platform settings."""
    service = _get_persistence_service()

    # Update all settings in persistence layer
    await service.update_setting(
        "platform",
        "integration_mode",
        {"mode": settings.integration_mode},
        updated_by="api",
    )
    await service.update_setting(
        "platform",
        "hitl",
        settings.hitl_settings.model_dump(),
        updated_by="api",
    )
    await service.update_setting(
        "platform",
        "mcp",
        settings.mcp_settings.model_dump(),
        updated_by="api",
    )
    await service.update_setting(
        "platform",
        "security",
        settings.security_settings.model_dump(),
        updated_by="api",
    )

    _invalidate_config()

    logger.info(
        f"Platform settings updated: mode={sanitize_log(settings.integration_mode)}"
    )

    return settings


@router.get("/integration-mode", response_model=IntegrationModeResponse)
async def get_integration_mode():
    """Get current integration mode."""
    service = _get_persistence_service()

    integration_mode = await service.get_setting("platform", "integration_mode")
    mcp_settings = await service.get_setting("platform", "mcp")

    mode = integration_mode.get("mode", "defense") if integration_mode else "defense"
    mcp_dict: dict[str, Any] = cast(
        dict[str, Any],
        mcp_settings if mcp_settings else DEFAULT_PLATFORM_SETTINGS["mcp"],
    )
    mcp_enabled = mcp_dict.get("enabled", False)

    descriptions = {
        "defense": "Maximum security mode - air-gap compatible, no external dependencies",
        "enterprise": "Full integration mode - AgentCore Gateway enabled with external tools",
        "hybrid": "Balanced mode - selective integrations with strict HITL controls",
    }

    return IntegrationModeResponse(
        mode=mode,
        mcp_enabled=mcp_enabled and mode != "defense",
        description=descriptions.get(mode, "Unknown mode"),
    )


@router.put("/integration-mode", response_model=IntegrationModeResponse)
async def update_integration_mode(
    http_request: Request,
    request: IntegrationModeRequest,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """Update integration mode."""
    mode = request.mode.lower()

    if mode not in ["defense", "enterprise", "hybrid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}. Must be defense, enterprise, or hybrid",
        )

    service = _get_persistence_service()

    # Get current mode for logging
    old_integration = await service.get_setting("platform", "integration_mode")
    old_mode = old_integration.get("mode", "defense") if old_integration else "defense"

    # Update integration mode
    await service.update_setting(
        "platform",
        "integration_mode",
        {"mode": mode},
        updated_by="api",
    )

    # If switching to defense mode, disable MCP
    mcp_settings = await service.get_setting("platform", "mcp")
    if mcp_settings:
        mcp_dict: dict[str, Any] = dict(cast(dict[str, Any], mcp_settings))
    else:
        # Create a mutable copy of the default settings
        mcp_dict = {**cast(dict[str, Any], DEFAULT_PLATFORM_SETTINGS["mcp"])}

    if mode == "defense":
        mcp_dict["enabled"] = False
        await service.update_setting("platform", "mcp", mcp_dict, updated_by="api")
        logger.info("MCP disabled due to defense mode activation")

    _invalidate_config()

    logger.info(f"Integration mode changed: {old_mode} -> {mode}")

    descriptions = {
        "defense": "Maximum security mode - air-gap compatible, no external dependencies",
        "enterprise": "Full integration mode - AgentCore Gateway enabled with external tools",
        "hybrid": "Balanced mode - selective integrations with strict HITL controls",
    }

    return IntegrationModeResponse(
        mode=mode,
        mcp_enabled=mcp_dict.get("enabled", False) and mode != "defense",
        description=descriptions.get(mode, "Unknown mode"),
    )


@router.get("/hitl", response_model=HITLSettingsModel)
async def get_hitl_settings():
    """Get HITL settings."""
    service = _get_persistence_service()
    hitl = await service.get_setting("platform", "hitl")
    hitl_data: dict[str, Any] = cast(
        dict[str, Any], hitl if hitl else DEFAULT_PLATFORM_SETTINGS["hitl"]
    )
    return HITLSettingsModel(**hitl_data)


@router.put("/hitl", response_model=HITLSettingsModel)
async def update_hitl_settings(
    request: Request,
    settings: HITLSettingsModel,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """Update HITL settings."""
    service = _get_persistence_service()
    await service.update_setting(
        "platform",
        "hitl",
        settings.model_dump(),
        updated_by="api",
    )
    logger.info("HITL settings updated")
    return settings


@router.get("/mcp", response_model=MCPSettingsModel)
async def get_mcp_settings():
    """Get MCP settings."""
    service = _get_persistence_service()

    # Check if MCP is allowed in current mode
    integration_mode = await service.get_setting("platform", "integration_mode")
    mode = integration_mode.get("mode", "defense") if integration_mode else "defense"

    if mode == "defense":
        return MCPSettingsModel(
            enabled=False, external_tools_enabled=[], rate_limit=RateLimitModel()
        )

    mcp = await service.get_setting("platform", "mcp")
    mcp_data: dict[str, Any] = cast(
        dict[str, Any], mcp if mcp else DEFAULT_PLATFORM_SETTINGS["mcp"]
    )
    return MCPSettingsModel(**mcp_data)


@router.put("/mcp", response_model=MCPSettingsModel)
async def update_mcp_settings(
    request: Request,
    settings: MCPSettingsModel,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """Update MCP settings."""
    service = _get_persistence_service()

    integration_mode = await service.get_setting("platform", "integration_mode")
    mode = integration_mode.get("mode", "defense") if integration_mode else "defense"

    # Prevent enabling MCP in defense mode
    if mode == "defense" and settings.enabled:
        raise HTTPException(
            status_code=400,
            detail="Cannot enable MCP Gateway in Defense mode. Switch to Enterprise or Hybrid mode first.",
        )

    await service.update_setting(
        "platform",
        "mcp",
        settings.model_dump(),
        updated_by="api",
    )
    _invalidate_config()

    logger.info(f"MCP settings updated: enabled={sanitize_log(settings.enabled)}")

    return settings


@router.get("/mcp/tools", response_model=list[ExternalToolInfo])
async def get_available_external_tools():
    """Get list of available external tools for MCP integration."""
    return AVAILABLE_EXTERNAL_TOOLS


@router.post("/mcp/test-connection", response_model=ConnectionTestResponse)
async def test_mcp_connection(request: ConnectionTestRequest):
    """Test connection to MCP Gateway."""
    import asyncio
    import time

    service = _get_persistence_service()
    integration_mode = await service.get_setting("platform", "integration_mode")
    mode = integration_mode.get("mode", "defense") if integration_mode else "defense"

    if mode == "defense":
        raise HTTPException(
            status_code=400, detail="Cannot test MCP connection in Defense mode"
        )

    if not request.gateway_url:
        raise HTTPException(status_code=400, detail="Gateway URL is required")

    if not request.api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Simulate connection test (in production, this would actually hit the gateway)
    start_time = time.time()

    try:
        # In production, this would be:
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(f"{request.gateway_url}/health",
        #                           headers={"Authorization": f"Bearer {request.api_key}"}) as resp:
        #         if resp.status != 200:
        #             raise Exception(f"Gateway returned {resp.status}")

        # Simulate network delay
        await asyncio.sleep(0.1)

        # For demo purposes, accept any valid-looking URL
        if not request.gateway_url.startswith(("http://", "https://")):
            return ConnectionTestResponse(
                success=False, message="Invalid gateway URL format"
            )

        latency = (time.time() - start_time) * 1000

        logger.info(
            f"MCP connection test successful: {sanitize_log(request.gateway_url)}"
        )

        return ConnectionTestResponse(
            success=True, message="Connection successful", latency_ms=round(latency, 2)
        )

    except Exception as e:
        logger.error(f"MCP connection test failed: {e}")
        return ConnectionTestResponse(success=False, message=str(e))


@router.get("/mcp/usage", response_model=MCPUsageResponse)
async def get_mcp_usage():
    """Get MCP usage statistics."""
    # In production, this would query usage data from DynamoDB or the MCP Gateway
    config = await _get_integration_config_async()
    budget = config.default_customer_budget

    if budget:
        return MCPUsageResponse(
            current_month_cost=budget.current_spend_usd,
            current_day_cost=0.0,  # Daily tracking not implemented in CustomerMCPBudget
            total_invocations=0,  # Invocation count not tracked in CustomerMCPBudget
            budget_remaining=budget.remaining_budget_usd,
        )

    service = _get_persistence_service()
    mcp = await service.get_setting("platform", "mcp")
    mcp_data: dict[str, Any] = cast(
        dict[str, Any], mcp if mcp else DEFAULT_PLATFORM_SETTINGS["mcp"]
    )

    return MCPUsageResponse(
        current_month_cost=0.0,
        current_day_cost=0.0,
        total_invocations=0,
        budget_remaining=mcp_data.get("monthly_budget_usd", 100),
    )


@router.get("/security", response_model=SecuritySettingsModel)
async def get_security_settings():
    """Get security settings including log retention."""
    service = _get_persistence_service()
    security = await service.get_setting("platform", "security")
    security_data: dict[str, Any] = cast(
        dict[str, Any], security if security else DEFAULT_PLATFORM_SETTINGS["security"]
    )
    return SecuritySettingsModel(**security_data)


@router.put("/security", response_model=SecuritySettingsModel)
async def update_security_settings(
    request: Request,
    settings: SecuritySettingsModel,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """Update security settings including log retention."""
    service = _get_persistence_service()

    # Get old settings for audit logging
    old_security = await service.get_setting("platform", "security")
    old_retention = (
        old_security.get("retain_logs_for_days", 365) if old_security else 365
    )

    await service.update_setting(
        "platform",
        "security",
        settings.model_dump(),
        updated_by="api",
    )

    # If retention changed, invoke Lambda to sync CloudWatch log groups
    if old_retention != settings.retain_logs_for_days:
        logger.info(
            f"Log retention changed: {sanitize_log(old_retention)} -> {sanitize_log(settings.retain_logs_for_days)} days"
        )

        # Invoke log retention sync Lambda asynchronously
        sync_result = await _invoke_log_retention_sync(settings.retain_logs_for_days)
        logger.info(f"Log retention sync result: {sync_result}")

    logger.info("Security settings updated")
    return settings


# ============================================================================
# Compliance Settings Endpoints (ADR-040)
# ============================================================================


async def _invoke_compliance_settings_sync(
    settings: ComplianceSettingsModel,
) -> dict[str, Any]:
    """
    Invoke the compliance settings sync Lambda to update SSM parameters.

    Args:
        settings: Compliance settings to sync

    Returns:
        Lambda response or error details
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    project_name = os.environ.get("PROJECT_NAME", "aura")
    lambda_name = f"{project_name}-compliance-settings-sync-{environment}"

    # Skip Lambda invocation in test/local environments
    if os.environ.get("TESTING", "").lower() == "true":
        logger.info(f"Skipping Lambda invocation in test mode: {lambda_name}")
        return {"status": "skipped", "reason": "test_mode"}

    try:
        lambda_client = boto3.client("lambda")

        payload = {
            "profile": settings.profile,
            "kms_encryption_mode": settings.kms_encryption_mode,
            "log_retention_days": settings.log_retention_days,
            "audit_log_retention_days": settings.audit_log_retention_days,
        }

        response = lambda_client.invoke(
            FunctionName=lambda_name,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload),
        )

        status_code = response.get("StatusCode", 0)

        if status_code == 202:
            logger.info(f"Compliance settings sync Lambda invoked: {lambda_name}")
            return {"status": "invoked", "lambda_name": lambda_name}
        else:
            logger.warning(f"Unexpected status from Lambda: {status_code}")
            return {"status": "warning", "status_code": status_code}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "ResourceNotFoundException":
            logger.warning(
                f"Compliance settings sync Lambda not found: {lambda_name}. "
                "Settings saved but SSM parameters not updated."
            )
            return {"status": "lambda_not_found", "lambda_name": lambda_name}

        logger.error(f"Failed to invoke compliance sync Lambda: {error_code}")
        return {"status": "error", "error": error_message}

    except Exception as e:
        logger.error(f"Unexpected error invoking compliance sync Lambda: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/compliance", response_model=ComplianceSettingsModel)
async def get_compliance_settings():
    """
    Get compliance settings including profile, KMS mode, and retention policies.

    Returns current compliance configuration used for CMMC/GovCloud compliance.
    """
    service = _get_persistence_service()
    compliance = await service.get_setting("platform", "compliance")
    compliance_data: dict[str, Any] = cast(
        dict[str, Any],
        compliance if compliance else DEFAULT_PLATFORM_SETTINGS.get("compliance", {}),
    )
    return ComplianceSettingsModel(**compliance_data)


@router.put("/compliance", response_model=ComplianceSettingsModel)
async def update_compliance_settings(
    request: Request,
    settings: ComplianceSettingsModel,
    rate_check: RateLimitResult = Depends(admin_rate_limit),  # noqa: B008
):
    """
    Update compliance settings.

    - Profile changes apply preset values for KMS mode, log retention, etc.
    - KMS mode changes are marked as pending (requires redeployment)
    - Log retention changes trigger Lambda sync to update CloudWatch log groups
    """
    service = _get_persistence_service()

    # Get old settings for comparison
    old_compliance = await service.get_setting("platform", "compliance")
    old_data: dict[str, Any] = cast(
        dict[str, Any],
        (
            old_compliance
            if old_compliance
            else DEFAULT_PLATFORM_SETTINGS.get("compliance", {})
        ),
    )
    old_kms_mode = old_data.get("kms_encryption_mode", "aws_managed")
    old_log_retention = old_data.get("log_retention_days", 90)

    # Check if KMS mode is changing (requires deployment)
    kms_mode_changing = old_kms_mode != settings.kms_encryption_mode
    if kms_mode_changing:
        settings.pending_kms_change = True
        logger.info(
            f"KMS mode change pending: {sanitize_log(old_kms_mode)} -> {sanitize_log(settings.kms_encryption_mode)}"
        )

    # Validate profile
    if settings.profile not in COMPLIANCE_PROFILE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid compliance profile: {settings.profile}. "
            f"Must be one of: {list(COMPLIANCE_PROFILE_PRESETS.keys())}",
        )

    # Validate CMMC L2 log retention requirement
    if settings.profile in ["cmmc_l2", "govcloud"] and settings.log_retention_days < 90:
        raise HTTPException(
            status_code=400,
            detail="CMMC L2 and GovCloud profiles require minimum 90-day log retention",
        )

    # Save to persistence layer
    await service.update_setting(
        "platform",
        "compliance",
        settings.model_dump(),
        updated_by="api",
    )

    # If log retention changed, invoke the log retention sync Lambda
    if old_log_retention != settings.log_retention_days:
        logger.info(
            f"Compliance log retention changed: {sanitize_log(old_log_retention)} -> {sanitize_log(settings.log_retention_days)}"
        )
        await _invoke_log_retention_sync(settings.log_retention_days)

    # Invoke compliance settings sync Lambda to update SSM parameters
    sync_result = await _invoke_compliance_settings_sync(settings)
    logger.info(f"Compliance settings sync result: {sync_result}")

    logger.info(
        f"Compliance settings updated: profile={sanitize_log(settings.profile)}"
    )
    return settings


@router.post("/compliance/apply-profile")
async def apply_compliance_profile(
    request: Request,
    profile: str,
    rate_check: RateLimitResult = Depends(admin_rate_limit),  # noqa: B008
):
    """
    Apply a compliance profile preset.

    Profiles:
    - commercial: AWS-managed KMS, 30-day logs
    - cmmc_l1: AWS-managed KMS, 90-day logs
    - cmmc_l2: Customer-managed KMS, 90-day logs
    - govcloud: Customer-managed KMS, 365-day logs
    """
    if profile not in COMPLIANCE_PROFILE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {profile}. "
            f"Must be one of: {list(COMPLIANCE_PROFILE_PRESETS.keys())}",
        )

    service = _get_persistence_service()

    # Get current settings
    old_compliance = await service.get_setting("platform", "compliance")
    old_data: dict[str, Any] = cast(
        dict[str, Any],
        (
            old_compliance
            if old_compliance
            else DEFAULT_PLATFORM_SETTINGS.get("compliance", {})
        ),
    )
    old_kms_mode = old_data.get("kms_encryption_mode", "aws_managed")

    # Get preset values
    preset = COMPLIANCE_PROFILE_PRESETS[profile]
    new_kms_mode = preset["kms_encryption_mode"]

    # Build new settings from preset
    new_settings = {
        "profile": profile,
        "kms_encryption_mode": new_kms_mode,
        "log_retention_days": preset["log_retention_days"],
        "audit_log_retention_days": preset["audit_log_retention_days"],
        "require_encryption_at_rest": preset["require_encryption_at_rest"],
        "require_encryption_in_transit": preset["require_encryption_in_transit"],
        "pending_kms_change": old_kms_mode != new_kms_mode,
        "last_profile_change_at": None,  # Will be set by persistence layer
        "last_profile_change_by": "api",
    }

    # Save to persistence layer
    await service.update_setting(
        "platform",
        "compliance",
        new_settings,
        updated_by="api",
    )

    # Invoke Lambda to sync SSM parameters
    settings_model = ComplianceSettingsModel(**new_settings)
    await _invoke_compliance_settings_sync(settings_model)

    # If log retention changed, sync CloudWatch log groups
    old_log_retention = old_data.get("log_retention_days", 90)
    new_log_retention = cast(int, preset["log_retention_days"])
    if old_log_retention != new_log_retention:
        await _invoke_log_retention_sync(new_log_retention)

    logger.info(f"Applied compliance profile: {sanitize_log(profile)}")

    return {
        "status": "success",
        "profile": profile,
        "settings_applied": preset,
        "kms_change_pending": old_kms_mode != new_kms_mode,
    }


@router.get("/compliance/profiles")
async def get_compliance_profiles():
    """
    Get available compliance profiles and their settings.

    Returns all preset profiles with their configured values.
    """
    return {
        "profiles": COMPLIANCE_PROFILE_PRESETS,
        "current_profile": (await get_compliance_settings()).profile,
    }
