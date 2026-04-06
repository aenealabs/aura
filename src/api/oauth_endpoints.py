"""
Project Aura - OAuth API Endpoints

REST API endpoints for OAuth provider integration.
Handles OAuth flows for GitHub and GitLab to enable repository access.

Endpoints:
- GET  /api/v1/oauth/{provider}/authorize      - Initiate OAuth flow
- GET  /api/v1/oauth/callback                  - OAuth callback handler
- GET  /api/v1/oauth/connections               - List user's OAuth connections
- GET  /api/v1/oauth/connections/{id}          - Get connection details
- DELETE /api/v1/oauth/connections/{id}        - Revoke OAuth connection
- GET  /api/v1/oauth/connections/{id}/repos    - List repos from connection
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.api_rate_limiter import RateLimitResult, standard_rate_limit
from src.services.oauth_provider_service import OAuthProviderService, get_oauth_service
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/oauth", tags=["OAuth"])

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class OAuthInitiateResponse(BaseModel):
    """Response from OAuth initiation."""

    authorization_url: str = Field(description="URL to redirect user for OAuth")
    state: str = Field(description="CSRF state token to validate callback")


class OAuthConnectionResponse(BaseModel):
    """OAuth connection information."""

    connection_id: str
    provider: str
    provider_user_id: str
    provider_username: str
    scopes: list[str]
    status: str
    created_at: str
    expires_at: str | None = None


class OAuthCallbackResponse(BaseModel):
    """Response from OAuth callback."""

    connection_id: str
    status: str
    provider: str
    provider_username: str


class ProviderRepositoryResponse(BaseModel):
    """Repository from OAuth provider."""

    id: str
    name: str
    full_name: str
    description: str | None = None
    clone_url: str
    default_branch: str
    language: str | None = None
    size_kb: int
    private: bool
    last_pushed_at: str | None = None
    already_connected: bool = False


# ============================================================================
# Dependency Injection
# ============================================================================


def get_oauth_svc() -> OAuthProviderService:
    """Get the OAuth service instance."""
    return get_oauth_service()


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/{provider}/authorize", response_model=OAuthInitiateResponse)
async def initiate_oauth(
    provider: str,
    user: User = Depends(get_current_user),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Initiate OAuth flow for a provider.

    Generates an authorization URL that the frontend should redirect to.
    The state parameter should be stored in session for callback validation.

    Args:
        provider: OAuth provider (github, gitlab)

    Returns:
        Authorization URL and state token
    """
    if provider not in ["github", "gitlab"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider}. Must be 'github' or 'gitlab'",
        )

    try:
        auth_url, state = await oauth_service.initiate_oauth(provider, user.sub)
        logger.info(f"OAuth initiated for user {user.sub} with provider {provider}")

        return OAuthInitiateResponse(authorization_url=auth_url, state=state)

    except ValueError as e:
        logger.warning(f"OAuth initiation validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid OAuth request parameters")
    except Exception as e:
        logger.error(f"OAuth initiation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate OAuth flow")


@router.get("/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    code: str = Query(  # noqa: B008
        ..., description="Authorization code from provider"
    ),  # noqa: B008
    state: str = Query(..., description="CSRF state token"),  # noqa: B008
    provider: str = Query(None, description="Provider hint (optional)"),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
):
    """
    Handle OAuth callback from provider.

    Exchanges the authorization code for access tokens and stores
    the connection in DynamoDB with tokens in Secrets Manager.

    Note: This endpoint doesn't require authentication as it's called
    during the OAuth redirect flow. The state parameter validates the request.

    Args:
        code: Authorization code from provider
        state: CSRF state token (must match initiation)
        provider: Provider hint (github, gitlab) - can be inferred from state

    Returns:
        Connection ID and status
    """
    try:
        connection = await oauth_service.complete_oauth(
            provider=provider or "github",  # Default, will be validated
            code=code,
            state=state,
        )

        logger.info(
            f"OAuth completed for user {connection.user_id} "
            f"with {connection.provider}: {connection.provider_username}"
        )

        return OAuthCallbackResponse(
            connection_id=connection.connection_id,
            status="connected",
            provider=connection.provider,
            provider_username=connection.provider_username,
        )

    except ValueError as e:
        logger.warning(f"OAuth callback validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid OAuth callback parameters")
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to complete OAuth flow")


@router.get("/connections", response_model=list[OAuthConnectionResponse])
async def list_connections(
    provider: str | None = Query(None, description="Filter by provider"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    List user's OAuth connections.

    Returns all active OAuth connections for the authenticated user.
    Optionally filter by provider.

    Args:
        provider: Filter by provider (github, gitlab)

    Returns:
        List of OAuth connections
    """
    try:
        connections = await oauth_service.list_connections(user.sub)

        # Filter by provider if specified
        if provider:
            connections = [c for c in connections if c.provider == provider]

        return [
            OAuthConnectionResponse(
                connection_id=conn.connection_id,
                provider=conn.provider,
                provider_user_id=conn.provider_user_id,
                provider_username=conn.provider_username,
                scopes=conn.scopes,
                status=conn.status,
                created_at=conn.created_at,
                expires_at=conn.expires_at,
            )
            for conn in connections
        ]

    except Exception as e:
        logger.error(f"Failed to list connections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list OAuth connections")


@router.get("/connections/{connection_id}", response_model=OAuthConnectionResponse)
async def get_connection(
    connection_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get a specific OAuth connection.

    Args:
        connection_id: Connection ID

    Returns:
        Connection details
    """
    try:
        connections = await oauth_service.list_connections(user.sub)
        connection = next(
            (c for c in connections if c.connection_id == connection_id), None
        )

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        return OAuthConnectionResponse(
            connection_id=connection.connection_id,
            provider=connection.provider,
            provider_user_id=connection.provider_user_id,
            provider_username=connection.provider_username,
            scopes=connection.scopes,
            status=connection.status,
            created_at=connection.created_at,
            expires_at=connection.expires_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get OAuth connection")


@router.delete("/connections/{connection_id}")
async def revoke_connection(
    connection_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Revoke an OAuth connection.

    Deletes the connection from DynamoDB and removes stored tokens
    from Secrets Manager. Also attempts to revoke the token with
    the OAuth provider.

    Args:
        connection_id: Connection ID to revoke

    Returns:
        Revocation status
    """
    try:
        await oauth_service.revoke_connection(user.sub, connection_id)
        logger.info(f"OAuth connection {sanitize_log(connection_id)} revoked for user {sanitize_log(user.sub)}")

        return {"status": "revoked", "connection_id": connection_id}

    except ValueError as e:
        logger.warning(f"Connection revoke error - not found: {e}")
        raise HTTPException(status_code=404, detail="OAuth connection not found")
    except Exception as e:
        logger.error(f"Failed to revoke connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke OAuth connection")


@router.get(
    "/connections/{connection_id}/repos",
    response_model=list[ProviderRepositoryResponse],
)
async def list_connection_repositories(
    connection_id: str,
    page: int = Query(1, ge=1, description="Page number"),  # noqa: B008
    per_page: int = Query(30, ge=1, le=100, description="Items per page"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    oauth_service: OAuthProviderService = Depends(get_oauth_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    List repositories accessible via an OAuth connection.

    Fetches repositories from the OAuth provider using the stored tokens.

    Args:
        connection_id: Connection ID
        page: Page number for pagination
        per_page: Items per page (max 100)

    Returns:
        List of repositories from the provider
    """
    try:
        # Verify the connection belongs to the user
        connections = await oauth_service.list_connections(user.sub)
        connection = next(
            (c for c in connections if c.connection_id == connection_id), None
        )

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        repos = await oauth_service.list_repositories(connection_id)

        return [
            ProviderRepositoryResponse(
                id=repo.provider_repo_id,
                name=repo.name,
                full_name=repo.full_name,
                description=None,  # ProviderRepository doesn't have description
                clone_url=repo.clone_url,
                default_branch=repo.default_branch,
                language=repo.language,
                size_kb=repo.size_kb,
                private=repo.private,
                last_pushed_at=repo.updated_at,
                already_connected=False,  # ProviderRepository doesn't have this field
            )
            for repo in repos
        ]

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Repository list validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid repository request parameters"
        )
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list repositories from provider"
        )
