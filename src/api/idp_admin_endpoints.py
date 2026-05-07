"""
Project Aura - Identity Provider Admin API Endpoints

FastAPI routes for managing IdP configurations.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import User, require_role
from src.api.log_sanitizer import sanitize_log
from src.services.identity.audit_service import get_audit_service
from src.services.identity.base_provider import IdentityProviderFactory
from src.services.identity.idp_config_service import get_idp_config_service
from src.services.identity.models import (
    AttributeMapping,
    AuthAction,
    GroupMapping,
    IdentityProviderConfig,
    IdPType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/identity-providers", tags=["idp-admin"])

# Require admin role for all endpoints
require_admin = require_role("admin")


# =============================================================================
# Request/Response Models
# =============================================================================


class AttributeMappingModel(BaseModel):
    """Attribute mapping configuration."""

    source_attribute: str
    target_attribute: str
    transform: str | None = None
    required: bool = False
    default_value: str | None = None


class GroupMappingModel(BaseModel):
    """Group to role mapping configuration."""

    source_group: str
    target_role: str
    is_regex: bool = False
    priority: int = 100


class IdPConfigCreate(BaseModel):
    """Request to create a new IdP configuration."""

    organization_id: str
    idp_type: str  # cognito, ldap, saml, oidc, pingid, sso
    name: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    priority: int = Field(default=100, ge=1, le=1000)
    connection_settings: dict[str, Any]
    credentials_secret_arn: str | None = None
    certificate_settings: dict[str, Any] = Field(default_factory=dict)
    attribute_mappings: list[AttributeMappingModel] = Field(default_factory=list)
    group_mappings: list[GroupMappingModel] = Field(default_factory=list)
    email_domains: list[str] = Field(default_factory=list)


class IdPConfigUpdate(BaseModel):
    """Request to update an IdP configuration."""

    name: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    connection_settings: dict[str, Any] | None = None
    credentials_secret_arn: str | None = None
    certificate_settings: dict[str, Any] | None = None
    attribute_mappings: list[AttributeMappingModel] | None = None
    group_mappings: list[GroupMappingModel] | None = None
    email_domains: list[str] | None = None


class IdPConfigResponse(BaseModel):
    """IdP configuration response."""

    idp_id: str
    organization_id: str
    idp_type: str
    name: str
    enabled: bool
    priority: int
    connection_settings: dict[str, Any]
    credentials_secret_arn: str | None
    certificate_settings: dict[str, Any]
    attribute_mappings: list[AttributeMappingModel]
    group_mappings: list[GroupMappingModel]
    email_domains: list[str]
    created_at: str
    updated_at: str
    created_by: str

    @classmethod
    def from_config(cls, config: IdentityProviderConfig) -> "IdPConfigResponse":
        """Create response from config model."""
        return cls(
            idp_id=config.idp_id,
            organization_id=config.organization_id,
            idp_type=config.idp_type.value,
            name=config.name,
            enabled=config.enabled,
            priority=config.priority,
            connection_settings=config.connection_settings,
            credentials_secret_arn=config.credentials_secret_arn,
            certificate_settings=config.certificate_settings,
            attribute_mappings=[
                AttributeMappingModel(
                    source_attribute=m.source_attribute,
                    target_attribute=m.target_attribute,
                    transform=m.transform,
                    required=m.required,
                    default_value=m.default_value,
                )
                for m in config.attribute_mappings
            ],
            group_mappings=[
                GroupMappingModel(
                    source_group=m.source_group,
                    target_role=m.target_role,
                    is_regex=m.is_regex,
                    priority=m.priority,
                )
                for m in config.group_mappings
            ],
            email_domains=config.email_domains,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
        )


class TestCredentials(BaseModel):
    """Credentials for testing IdP connection."""

    username: str | None = None
    password: str | None = None


class TestResult(BaseModel):
    """Result of IdP connection test."""

    healthy: bool
    status: str
    latency_ms: float
    message: str | None
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogEntryResponse(BaseModel):
    """Audit log entry response."""

    audit_id: str
    idp_id: str
    organization_id: str
    action_type: str
    actor_id: str | None
    target_user_id: str | None
    timestamp: str
    success: bool
    error_message: str | None
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any]


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.get("/", response_model=list[IdPConfigResponse])
async def list_idp_configs(
    org_id: str,
    enabled_only: bool = False,
    user: User = Depends(require_admin),
) -> list[IdPConfigResponse]:
    """
    List all IdP configurations for an organization.

    Requires admin role.
    """
    config_service = get_idp_config_service()

    configs = await config_service.list_configs_for_org(
        organization_id=org_id,
        enabled_only=enabled_only,
    )

    return [IdPConfigResponse.from_config(c) for c in configs]


@router.get("/{idp_id}", response_model=IdPConfigResponse)
async def get_idp_config(
    idp_id: str,
    user: User = Depends(require_admin),
) -> IdPConfigResponse:
    """
    Get a specific IdP configuration.

    Requires admin role.
    """
    config_service = get_idp_config_service()

    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    return IdPConfigResponse.from_config(config)


@router.post("/", response_model=IdPConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_idp_config(
    config: IdPConfigCreate,
    user: User = Depends(require_admin),
) -> IdPConfigResponse:
    """
    Create a new IdP configuration.

    Requires admin role.
    """
    config_service = get_idp_config_service()
    audit_service = get_audit_service()

    # Validate IdP type
    try:
        idp_type = IdPType.from_string(config.idp_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create config model
    idp_config = IdentityProviderConfig(
        idp_id="",  # Will be generated
        organization_id=config.organization_id,
        idp_type=idp_type,
        name=config.name,
        enabled=config.enabled,
        priority=config.priority,
        connection_settings=config.connection_settings,
        credentials_secret_arn=config.credentials_secret_arn,
        certificate_settings=config.certificate_settings,
        attribute_mappings=[
            AttributeMapping(
                source_attribute=m.source_attribute,
                target_attribute=m.target_attribute,
                transform=m.transform,
                required=m.required,
                default_value=m.default_value,
            )
            for m in config.attribute_mappings
        ],
        group_mappings=[
            GroupMapping(
                source_group=m.source_group,
                target_role=m.target_role,
                is_regex=m.is_regex,
                priority=m.priority,
            )
            for m in config.group_mappings
        ],
        email_domains=[d.lower() for d in config.email_domains],
    )

    # Create in database
    created = await config_service.create_config(idp_config, actor_id=user.sub)

    # Log audit event
    await audit_service.log_config_change(
        action=AuthAction.CONFIG_CREATE,
        idp_id=created.idp_id,
        organization_id=created.organization_id,
        actor_id=user.sub,
        changes={"name": created.name, "type": created.idp_type.value},
    )

    logger.info(f"Created IdP config {created.idp_id} by user {user.sub}")

    return IdPConfigResponse.from_config(created)


@router.put("/{idp_id}", response_model=IdPConfigResponse)
async def update_idp_config(
    idp_id: str,
    updates: IdPConfigUpdate,
    user: User = Depends(require_admin),
) -> IdPConfigResponse:
    """
    Update an IdP configuration.

    Requires admin role.
    """
    config_service = get_idp_config_service()
    audit_service = get_audit_service()

    # Get existing config
    existing = await config_service.get_config(idp_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    # Build updates dict
    update_dict: dict[str, Any] = {}

    if updates.name is not None:
        update_dict["name"] = updates.name
    if updates.enabled is not None:
        update_dict["enabled"] = updates.enabled
    if updates.priority is not None:
        update_dict["priority"] = updates.priority
    if updates.connection_settings is not None:
        update_dict["connection_settings"] = updates.connection_settings
    if updates.credentials_secret_arn is not None:
        update_dict["credentials_secret_arn"] = updates.credentials_secret_arn
    if updates.certificate_settings is not None:
        update_dict["certificate_settings"] = updates.certificate_settings
    if updates.attribute_mappings is not None:
        update_dict["attribute_mappings"] = [
            m.dict() for m in updates.attribute_mappings
        ]
    if updates.group_mappings is not None:
        update_dict["group_mappings"] = [m.dict() for m in updates.group_mappings]
    if updates.email_domains is not None:
        update_dict["email_domains"] = [d.lower() for d in updates.email_domains]

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Update in database
    updated = await config_service.update_config(
        idp_id=idp_id,
        updates=update_dict,
        actor_id=user.sub,
    )

    # Log audit event
    await audit_service.log_config_change(
        action=AuthAction.CONFIG_UPDATE,
        idp_id=idp_id,
        organization_id=existing.organization_id,
        actor_id=user.sub,
        changes=update_dict,
    )

    logger.info(
        f"Updated IdP config {sanitize_log(idp_id)} by user {sanitize_log(user.sub)}"
    )

    return IdPConfigResponse.from_config(updated)


@router.delete("/{idp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_idp_config(
    idp_id: str,
    user: User = Depends(require_admin),
) -> None:
    """
    Delete an IdP configuration.

    Requires admin role.
    """
    config_service = get_idp_config_service()
    audit_service = get_audit_service()

    # Get existing config for audit
    existing = await config_service.get_config(idp_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    # Delete
    deleted = await config_service.delete_config(idp_id, actor_id=user.sub)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete configuration",
        )

    # Log audit event
    await audit_service.log_config_change(
        action=AuthAction.CONFIG_DELETE,
        idp_id=idp_id,
        organization_id=existing.organization_id,
        actor_id=user.sub,
        changes={"name": existing.name},
    )

    logger.info(
        f"Deleted IdP config {sanitize_log(idp_id)} by user {sanitize_log(user.sub)}"
    )


# =============================================================================
# Test Endpoints
# =============================================================================


@router.post("/{idp_id}/test", response_model=TestResult)
async def test_idp_connection(
    idp_id: str,
    credentials: TestCredentials | None = None,
    user: User = Depends(require_admin),
) -> TestResult:
    """
    Test IdP connectivity and optionally test authentication.

    Requires admin role.

    If credentials are provided, attempts authentication.
    Otherwise, just tests connectivity/health.
    """
    config_service = get_idp_config_service()

    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    try:
        provider = IdentityProviderFactory.create(config)
        health_result = await provider.health_check()

        return TestResult(
            healthy=health_result.healthy,
            status=health_result.status.value,
            latency_ms=health_result.latency_ms,
            message=health_result.message,
            details=health_result.details,
        )

    except Exception as e:
        logger.exception(f"IdP test error: {e}")
        return TestResult(
            healthy=False,
            status="error",
            latency_ms=0,
            message=str(e),
            details={},
        )


# =============================================================================
# Audit Endpoints
# =============================================================================


@router.get("/{idp_id}/audit", response_model=list[AuditLogEntryResponse])
async def get_idp_audit_log(
    idp_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 100,
    user: User = Depends(require_admin),
) -> list[AuditLogEntryResponse]:
    """
    Get audit log for IdP configuration changes and auth events.

    Requires admin role.
    """
    config_service = get_idp_config_service()
    audit_service = get_audit_service()

    # Verify IdP exists
    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    # Get audit logs
    entries = await audit_service.get_audit_logs(
        idp_id=idp_id,
        start_time=start_date,
        end_time=end_date,
        limit=limit,
    )

    return [
        AuditLogEntryResponse(
            audit_id=e.audit_id,
            idp_id=e.idp_id,
            organization_id=e.organization_id,
            action_type=e.action_type,
            actor_id=e.actor_id,
            target_user_id=e.target_user_id,
            timestamp=e.timestamp,
            success=e.success,
            error_message=e.error_message,
            ip_address=e.ip_address,
            user_agent=e.user_agent,
            details=e.details,
        )
        for e in entries
    ]


# =============================================================================
# Metadata Endpoints
# =============================================================================


@router.get("/{idp_id}/saml-metadata")
async def get_saml_metadata(
    idp_id: str,
    user: User = Depends(require_admin),
) -> str:
    """
    Get SAML SP metadata XML for IdP configuration.

    Used to configure the enterprise IdP with Aura's SP settings.
    """
    config_service = get_idp_config_service()

    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IdP configuration {idp_id} not found",
        )

    if config.idp_type != IdPType.SAML:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SAML metadata only available for SAML providers",
        )

    try:
        from src.services.identity.providers.saml_provider import SAMLProvider

        provider = IdentityProviderFactory.create(config)
        if isinstance(provider, SAMLProvider):
            return provider.generate_sp_metadata()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate metadata",
        )

    except Exception as e:
        logger.exception(f"SAML metadata generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/supported-types")
async def get_supported_idp_types() -> list[dict[str, str]]:
    """
    Get list of supported identity provider types.

    Public endpoint - no auth required.
    """
    return [
        {
            "type": "cognito",
            "name": "AWS Cognito",
            "description": "AWS Cognito User Pool (OAuth2/OIDC)",
        },
        {
            "type": "ldap",
            "name": "LDAP / Active Directory",
            "description": "LDAP v3 or Microsoft Active Directory",
        },
        {
            "type": "saml",
            "name": "SAML 2.0",
            "description": "SAML 2.0 federation (Okta, Azure AD, OneLogin, etc.)",
        },
        {
            "type": "oidc",
            "name": "OpenID Connect",
            "description": "OIDC provider (Azure AD, Google, Auth0, etc.)",
        },
        {
            "type": "pingid",
            "name": "PingID / PingFederate",
            "description": "PingIdentity PingFederate or PingID",
        },
        {
            "type": "sso",
            "name": "Generic SSO",
            "description": "Generic enterprise SSO integration",
        },
    ]
