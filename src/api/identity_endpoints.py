"""
Project Aura - Identity Authentication API Endpoints

FastAPI routes for multi-IdP authentication flows.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.identity.audit_service import get_audit_service
from src.services.identity.base_provider import IdentityProviderFactory
from src.services.identity.idp_config_service import (
    get_idp_config_service,
    get_idp_routing_service,
)
from src.services.identity.models import AuthAction, AuthCredentials, IdPType
from src.services.identity.token_service import get_token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ProviderInfo(BaseModel):
    """Information about an available identity provider."""

    idp_id: str
    name: str
    type: str
    priority: int
    is_preferred: bool = False


class ProvidersResponse(BaseModel):
    """Response with list of available providers."""

    providers: list[ProviderInfo]
    preferred_idp_id: str | None = None


class LDAPLoginRequest(BaseModel):
    """LDAP login request."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Authentication token response."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: dict[str, Any]


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class LogoutResponse(BaseModel):
    """Logout response."""

    success: bool
    message: str


# =============================================================================
# Provider Discovery Endpoints
# =============================================================================


@router.get("/providers", response_model=ProvidersResponse)
async def get_available_providers(
    email: str | None = None,
    org_id: str | None = None,
) -> ProvidersResponse:
    """
    Get available identity providers for login.

    If email is provided, returns providers configured for that email domain
    with the matching provider marked as preferred.

    Args:
        email: User email address for domain-based routing
        org_id: Organization ID to filter providers
    """
    routing_service = get_idp_routing_service()

    providers = await routing_service.list_available_idps(
        organization_id=org_id,
        email=email,
    )

    preferred_id = None
    if email:
        preferred_config = await routing_service.get_idp_for_email(email, org_id)
        if preferred_config:
            preferred_id = preferred_config.idp_id

    return ProvidersResponse(
        providers=[ProviderInfo(**p) for p in providers],
        preferred_idp_id=preferred_id,
    )


# =============================================================================
# LDAP Authentication
# =============================================================================


@router.post("/login/ldap", response_model=TokenResponse)
async def login_ldap(
    request: Request,
    idp_id: str,
    credentials: LDAPLoginRequest,
) -> TokenResponse:
    """
    Authenticate via LDAP/Active Directory.

    Args:
        idp_id: IdP configuration ID
        credentials: Username and password
    """
    config_service = get_idp_config_service()
    token_service = get_token_service()
    audit_service = get_audit_service()

    # Get IdP configuration
    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity provider {idp_id} not found",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity provider is disabled",
        )

    if config.idp_type != IdPType.LDAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IdP {idp_id} is not an LDAP provider",
        )

    # Get client info for audit
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Create provider and authenticate
    try:
        provider = IdentityProviderFactory.create(config)
        auth_result = await provider.authenticate(
            AuthCredentials(
                username=credentials.username,
                password=credentials.password,
            )
        )

        if not auth_result.success:
            # Log failed auth
            await audit_service.log_auth_failure(
                idp_id=idp_id,
                organization_id=config.organization_id,
                username=credentials.username,
                error=auth_result.error,
                ip_address=client_ip,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result.error or "Authentication failed",
            )

        # Issue Aura tokens
        tokens, session = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=config,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Log successful auth
        await audit_service.log_auth_success(
            idp_id=idp_id,
            organization_id=config.organization_id,
            user_id=auth_result.user_id or "",
            email=auth_result.email,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "sub": session.user_sub,
                "email": auth_result.email,
                "name": auth_result.name,
                "roles": auth_result.roles,
                "organization_id": config.organization_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"LDAP authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


# =============================================================================
# SAML Authentication
# =============================================================================


@router.get("/saml/login/{idp_id}")
async def saml_login(
    idp_id: str,
    relay_state: str | None = None,
) -> RedirectResponse:
    """
    Initiate SAML SP-initiated SSO.

    Redirects user to IdP login page.
    """
    config_service = get_idp_config_service()

    config = await config_service.get_config(idp_id)
    if not config or not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found or disabled",
        )

    if config.idp_type != IdPType.SAML:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IdP {idp_id} is not a SAML provider",
        )

    try:
        provider = IdentityProviderFactory.create(config)

        # Import SAML provider to access generate_auth_request
        from src.services.identity.providers.saml_provider import SAMLProvider

        if isinstance(provider, SAMLProvider):
            # Load credentials first
            await provider._load_credentials()
            auth_request = provider.generate_auth_request(relay_state=relay_state)
            return RedirectResponse(
                url=auth_request.redirect_url,
                status_code=status.HTTP_302_FOUND,
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider type mismatch",
        )

    except Exception as e:
        logger.exception(f"SAML login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate SAML login",
        )


@router.post("/saml/acs")
async def saml_assertion_consumer(
    request: Request,
    SAMLResponse: str = Form(...),
    RelayState: str | None = Form(None),
) -> TokenResponse:
    """
    SAML Assertion Consumer Service endpoint.

    Receives SAML Response from IdP and issues Aura tokens.
    """
    config_service = get_idp_config_service()
    token_service = get_token_service()
    audit_service = get_audit_service()

    # TODO: In production, extract IdP ID from SAML response or relay state
    # For now, we need to identify which IdP sent this response
    # This is typically done by parsing the Issuer in the SAML response

    # Parse relay state to get IdP ID (simplified implementation)
    if not RelayState:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RelayState with IdP ID required",
        )

    idp_id = RelayState  # In real impl, decode from state

    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid IdP in relay state",
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        provider = IdentityProviderFactory.create(config)
        auth_result = await provider.authenticate(
            AuthCredentials(
                saml_response=SAMLResponse,
                relay_state=RelayState,
            )
        )

        if not auth_result.success:
            await audit_service.log_auth_failure(
                idp_id=idp_id,
                organization_id=config.organization_id,
                error=auth_result.error,
                ip_address=client_ip,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result.error or "SAML authentication failed",
            )

        tokens, session = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=config,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        await audit_service.log_auth_success(
            idp_id=idp_id,
            organization_id=config.organization_id,
            user_id=auth_result.user_id or "",
            email=auth_result.email,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "sub": session.user_sub,
                "email": auth_result.email,
                "name": auth_result.name,
                "roles": auth_result.roles,
                "organization_id": config.organization_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"SAML ACS error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SAML processing error",
        )


# =============================================================================
# OIDC Authentication
# =============================================================================


@router.get("/oidc/login/{idp_id}")
async def oidc_login(
    idp_id: str,
) -> RedirectResponse:
    """
    Initiate OIDC authorization code flow.

    Redirects user to IdP authorization endpoint.
    """
    config_service = get_idp_config_service()

    config = await config_service.get_config(idp_id)
    if not config or not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found or disabled",
        )

    if config.idp_type not in [IdPType.OIDC, IdPType.PINGID]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IdP {idp_id} is not an OIDC provider",
        )

    try:
        provider = IdentityProviderFactory.create(config)

        # Import OIDC provider
        from src.services.identity.providers.oidc_provider import OIDCProvider

        if isinstance(provider, OIDCProvider):
            await provider.discover()
            auth_request = provider.generate_auth_request()

            # TODO: Store state and nonce in DynamoDB for validation
            # For now, include idp_id in state
            return RedirectResponse(
                url=auth_request.authorization_url,
                status_code=status.HTTP_302_FOUND,
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider type mismatch",
        )

    except Exception as e:
        logger.exception(f"OIDC login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OIDC login",
        )


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str,
    state: str,
) -> TokenResponse:
    """
    OIDC authorization code callback.

    Exchanges code for tokens and issues Aura JWT.
    """
    # TODO: Look up state from DynamoDB to get IdP ID and code_verifier
    # For simplified implementation, state contains IdP ID

    config_service = get_idp_config_service()
    token_service = get_token_service()
    audit_service = get_audit_service()

    # In production, decode state properly
    idp_id = state  # Simplified

    config = await config_service.get_config(idp_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        provider = IdentityProviderFactory.create(config)

        # TODO: Get code_verifier and nonce from stored state
        auth_result = await provider.authenticate(
            AuthCredentials(
                code=code,
                state=state,
                code_verifier=None,  # Would come from stored state
                nonce=None,  # Would come from stored state
            )
        )

        if not auth_result.success:
            await audit_service.log_auth_failure(
                idp_id=idp_id,
                organization_id=config.organization_id,
                error=auth_result.error,
                ip_address=client_ip,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result.error or "OIDC authentication failed",
            )

        tokens, session = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=config,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        await audit_service.log_auth_success(
            idp_id=idp_id,
            organization_id=config.organization_id,
            user_id=auth_result.user_id or "",
            email=auth_result.email,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "sub": session.user_sub,
                "email": auth_result.email,
                "name": auth_result.name,
                "roles": auth_result.roles,
                "organization_id": config.organization_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"OIDC callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC authentication error",
        )


# =============================================================================
# Token Management
# =============================================================================


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
) -> TokenResponse:
    """
    Refresh Aura access token.

    Uses refresh token rotation for security.
    """
    token_service = get_token_service()

    try:
        # Validate refresh token
        validation = await token_service.validate_token(body.refresh_token)
        if not validation.valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=validation.error or "Invalid refresh token",
            )

        claims = validation.claims

        # Get IdP config and session
        # TODO: Look up session from DynamoDB using claims
        # For now, issue new tokens based on claims

        config_service = get_idp_config_service()
        config = await config_service.get_config(claims.get("idp", ""))

        if not config:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="IdP configuration not found",
            )

        # Create minimal session for refresh
        from src.services.identity.models import AuthSession

        session = AuthSession(
            session_id=claims.get("session_id", ""),
            user_sub=claims.get("sub", ""),
            idp_id=claims.get("idp", ""),
            organization_id=claims.get("org_id", ""),
            refresh_token_jti=claims.get("jti", ""),
        )

        tokens, updated_session = await token_service.refresh_tokens(
            refresh_token=body.refresh_token,
            session=session,
            idp_config=config,
        )

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "sub": updated_session.user_sub,
                "organization_id": updated_session.organization_id,
                "roles": updated_session.roles,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
) -> LogoutResponse:
    """
    Logout user and invalidate tokens.

    Requires valid access token.
    """
    audit_service = get_audit_service()

    # TODO: Invalidate refresh token in session store

    # Log logout event
    await audit_service.log_event(
        action=AuthAction.SESSION_LOGOUT,
        idp_id="",  # Would get from token claims
        organization_id="",  # Would get from token claims
        actor_id=user.sub,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return LogoutResponse(
        success=True,
        message="Logged out successfully",
    )
