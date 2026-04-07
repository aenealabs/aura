"""
Project Aura - Repository Management API Endpoints

REST API endpoints for repository CRUD and ingestion operations.
Part of the Repository Onboarding Wizard (ADR-043).

Endpoints:
- GET    /api/v1/repositories                  - List user's repositories
- GET    /api/v1/repositories/available        - List repos from OAuth provider
- POST   /api/v1/repositories                  - Add repository (manual URL+token)
- GET    /api/v1/repositories/{id}             - Get repository details
- PUT    /api/v1/repositories/{id}             - Update repository settings
- DELETE /api/v1/repositories/{id}             - Remove repository
- POST   /api/v1/repositories/ingest           - Start ingestion for repositories
- GET    /api/v1/repositories/ingestion-status - Get ingestion job statuses
- POST   /api/v1/repositories/ingestion/{id}/cancel - Cancel ingestion job
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.api.auth import User, get_current_user
from src.services.api_rate_limiter import (
    RateLimitResult,
    admin_rate_limit,
    standard_rate_limit,
)
from src.services.repository_onboard_service import RepositoryConfig as RepoConfigModel
from src.services.repository_onboard_service import (
    RepositoryOnboardService,
    get_repository_service,
)
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/repositories", tags=["Repositories"])

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


# SECURITY: Allowed URL patterns for clone_url to prevent SSRF attacks
# Only GitHub and GitLab URLs are permitted
# Defined at module level to avoid Pydantic ModelPrivateAttr issues
_ALLOWED_CLONE_URL_PATTERNS: list[re.Pattern[str]] = [
    # GitHub HTTPS URLs
    re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?$"),
    # GitHub SSH URLs
    re.compile(r"^git@github\.com:[\w.-]+/[\w.-]+(?:\.git)?$"),
    # GitLab HTTPS URLs (gitlab.com and self-hosted)
    re.compile(r"^https://gitlab\.com/[\w.-]+/[\w.-]+(?:\.git)?$"),
    re.compile(r"^https://[\w.-]+\.gitlab\.[\w.-]+/[\w.-]+/[\w.-]+(?:\.git)?$"),
    # GitLab SSH URLs
    re.compile(r"^git@gitlab\.com:[\w.-]+/[\w.-]+(?:\.git)?$"),
    # GitHub Enterprise (common patterns)
    re.compile(r"^https://github\.[\w.-]+\.[\w.-]+/[\w.-]+/[\w.-]+(?:\.git)?$"),
]


class RepositoryConfigRequest(BaseModel):
    """Request to add or update a repository."""

    connection_id: str | None = Field(None, description="OAuth connection ID")
    provider_repo_id: str | None = Field(
        None, description="Repository ID from provider"
    )
    clone_url: str | None = Field(None, description="Repository URL for manual entry")
    token: str | None = Field(
        None, description="Personal access token for manual entry"
    )
    name: str = Field(..., description="Repository display name")
    branch: str = Field("main", description="Default branch to track")
    languages: list[str] = Field(
        default=["python", "javascript", "typescript"],
        description="Languages to parse",
    )
    scan_frequency: str = Field(
        "on_push",
        description="Scan frequency: on_push, daily, weekly, manual",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude (e.g., node_modules/)",
    )
    enable_webhook: bool = Field(True, description="Enable webhook for push events")

    @field_validator("clone_url")
    @classmethod
    def validate_clone_url(cls, v: str | None) -> str | None:
        """
        Validate clone_url to prevent SSRF attacks.

        Only allows URLs from trusted providers (GitHub, GitLab).
        This prevents attackers from using the repository clone feature
        to make requests to internal services or arbitrary endpoints.
        """
        if v is None:
            return v

        # Check against allowed patterns
        for pattern in _ALLOWED_CLONE_URL_PATTERNS:
            if pattern.match(v):
                return v

        raise ValueError(
            "clone_url must be a valid GitHub or GitLab repository URL. "
            "Supported formats: https://github.com/owner/repo, "
            "https://gitlab.com/owner/repo, git@github.com:owner/repo"
        )


class RepositoryResponse(BaseModel):
    """Repository information response."""

    repository_id: str
    name: str
    provider: str
    clone_url: str
    branch: str
    languages: list[str]
    scan_frequency: str
    status: str
    last_ingestion_at: str | None = None
    file_count: int = 0
    entity_count: int = 0
    webhook_active: bool = False
    created_at: str
    updated_at: str


class IngestionRequestModel(BaseModel):
    """Request to start ingestion for multiple repositories."""

    repositories: list[RepositoryConfigRequest] = Field(
        ..., description="List of repository configurations to ingest"
    )


class IngestionJobResponse(BaseModel):
    """Ingestion job status response."""

    job_id: str
    repository_id: str
    repository_name: str
    status: str
    progress: int = 0
    stage: str | None = None
    files_processed: int = 0
    entities_indexed: int = 0
    embeddings_generated: int = 0
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None


class IngestionStartResponse(BaseModel):
    """Response from starting ingestion."""

    jobs: list[IngestionJobResponse]
    message: str


# ============================================================================
# Dependency Injection
# ============================================================================


def get_repo_svc() -> RepositoryOnboardService:
    """Get the repository service instance."""
    return get_repository_service()


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    status: str | None = Query(None, description="Filter by status"),  # noqa: B008
    provider: str | None = Query(None, description="Filter by provider"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    List user's connected repositories.

    Returns all repositories the user has onboarded to Project Aura.

    Args:
        status: Filter by status (active, error, syncing, pending)
        provider: Filter by provider (github, gitlab, manual)

    Returns:
        List of repository information
    """
    try:
        repos = await repo_service.list_repositories(user.sub)

        # Filter by status if specified
        if status:
            repos = [r for r in repos if r.status == status]

        # Filter by provider if specified
        if provider:
            repos = [r for r in repos if r.provider == provider]

        return [
            RepositoryResponse(
                repository_id=repo.repository_id,
                name=repo.name,
                provider=repo.provider,
                clone_url=repo.clone_url,
                branch=repo.branch,
                languages=repo.languages,
                scan_frequency=repo.scan_frequency,
                status=repo.status,
                last_ingestion_at=repo.last_ingestion_at,
                file_count=repo.file_count,
                entity_count=repo.entity_count,
                webhook_active=repo.webhook_id is not None,
                created_at=repo.created_at,
                updated_at=repo.updated_at,
            )
            for repo in repos
        ]

    except Exception as e:
        logger.error(f"Failed to list repositories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list repositories")


@router.get("/available")
async def list_available_repositories(
    connection_id: str = Query(..., description="OAuth connection ID"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    List available repositories from OAuth provider.

    Fetches repositories accessible via the specified OAuth connection.
    Marks repositories that are already connected.

    Args:
        connection_id: OAuth connection ID

    Returns:
        List of available repositories with connection status
    """
    try:
        repos = await repo_service.list_available_repositories(user.sub, connection_id)

        return {
            "repositories": [
                {
                    "id": repo.provider_repo_id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": None,  # ProviderRepository doesn't have description
                    "clone_url": repo.clone_url,
                    "default_branch": repo.default_branch,
                    "language": repo.language,
                    "size_kb": repo.size_kb,
                    "private": repo.private,
                    "last_pushed_at": repo.updated_at,
                    "already_connected": False,  # Would need to be calculated
                }
                for repo in repos
            ],
            "total": len(repos),
        }

    except ValueError as e:
        logger.warning(f"List repositories validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid repository list parameters"
        )
    except Exception as e:
        logger.error(f"Failed to list available repositories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list available repositories"
        )


@router.post("", response_model=RepositoryResponse)
async def add_repository(
    config: RepositoryConfigRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Add a repository.

    Can be added via OAuth connection or manual URL+token.
    For OAuth, provide connection_id and provider_repo_id.
    For manual, provide clone_url and token.

    Args:
        config: Repository configuration

    Returns:
        Created repository information
    """
    # Validate input
    if config.connection_id and config.provider_repo_id:
        mode = "oauth"  # noqa: F841
    elif config.clone_url:
        _mode = "manual"  # noqa: F841
    else:
        raise HTTPException(
            status_code=400,
            detail="Either connection_id+provider_repo_id or clone_url is required",
        )

    try:
        repo_config = RepoConfigModel(
            connection_id=config.connection_id,
            provider_repo_id=config.provider_repo_id,
            clone_url=config.clone_url,
            token=config.token,
            name=config.name,
            branch=config.branch,
            languages=config.languages,
            scan_frequency=config.scan_frequency,
            exclude_patterns=config.exclude_patterns,
            enable_webhook=config.enable_webhook,
        )

        repo = await repo_service.add_repository(user.sub, repo_config)
        logger.info(f"Repository {repo.name} added for user {user.sub}")

        return RepositoryResponse(
            repository_id=repo.repository_id,
            name=repo.name,
            provider=repo.provider,
            clone_url=repo.clone_url,
            branch=repo.branch,
            languages=repo.languages,
            scan_frequency=repo.scan_frequency,
            status=repo.status,
            last_ingestion_at=repo.last_ingestion_at,
            file_count=repo.file_count,
            entity_count=repo.entity_count,
            webhook_active=repo.webhook_id is not None,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        )

    except ValueError as e:
        logger.warning(f"Add repository validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid repository configuration")
    except Exception as e:
        logger.error(f"Failed to add repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add repository")


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get repository details.

    Args:
        repository_id: Repository ID

    Returns:
        Repository information
    """
    try:
        repo = await repo_service.get_repository(user.sub, repository_id)

        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        return RepositoryResponse(
            repository_id=repo.repository_id,
            name=repo.name,
            provider=repo.provider,
            clone_url=repo.clone_url,
            branch=repo.branch,
            languages=repo.languages,
            scan_frequency=repo.scan_frequency,
            status=repo.status,
            last_ingestion_at=repo.last_ingestion_at,
            file_count=repo.file_count,
            entity_count=repo.entity_count,
            webhook_active=repo.webhook_id is not None,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get repository")


@router.put("/{repository_id}", response_model=RepositoryResponse)
async def update_repository(
    repository_id: str,
    config: RepositoryConfigRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Update repository settings.

    Args:
        repository_id: Repository ID
        config: Updated configuration

    Returns:
        Updated repository information
    """
    try:
        repo_config = RepoConfigModel(
            connection_id=config.connection_id,
            provider_repo_id=config.provider_repo_id,
            clone_url=config.clone_url,
            token=config.token,
            name=config.name,
            branch=config.branch,
            languages=config.languages,
            scan_frequency=config.scan_frequency,
            exclude_patterns=config.exclude_patterns,
            enable_webhook=config.enable_webhook,
        )

        repo = await repo_service.update_repository(
            user.sub, repository_id, repo_config
        )
        logger.info(
            f"Repository {sanitize_log(repository_id)} updated for user {sanitize_log(user.sub)}"
        )

        return RepositoryResponse(
            repository_id=repo.repository_id,
            name=repo.name,
            provider=repo.provider,
            clone_url=repo.clone_url,
            branch=repo.branch,
            languages=repo.languages,
            scan_frequency=repo.scan_frequency,
            status=repo.status,
            last_ingestion_at=repo.last_ingestion_at,
            file_count=repo.file_count,
            entity_count=repo.entity_count,
            webhook_active=repo.webhook_id is not None,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        )

    except ValueError as e:
        logger.warning(f"Update repository error - not found: {e}")
        raise HTTPException(status_code=404, detail="Repository not found")
    except Exception as e:
        logger.error(f"Failed to update repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update repository")


@router.delete("/{repository_id}")
async def delete_repository(
    repository_id: str,
    delete_data: bool = Query(  # noqa: B008
        True, description="Also delete indexed data from Neptune/OpenSearch"
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(admin_rate_limit),  # noqa: B008
):
    """
    Remove a repository.

    Deletes the repository from the user's account. Optionally deletes
    all indexed data (graph entities and embeddings).

    Args:
        repository_id: Repository ID
        delete_data: Whether to delete indexed data (default: True)

    Returns:
        Deletion status
    """
    try:
        await repo_service.delete_repository(user.sub, repository_id)
        logger.info(
            f"Repository {sanitize_log(repository_id)} deleted for user {sanitize_log(user.sub)} "
            f"(delete_data={sanitize_log(delete_data)})"
        )

        return {
            "status": "deleted",
            "repository_id": repository_id,
            "data_deleted": delete_data,
        }

    except ValueError as e:
        logger.warning(f"Delete repository error - not found: {e}")
        raise HTTPException(status_code=404, detail="Repository not found")
    except Exception as e:
        logger.error(f"Failed to delete repository: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete repository")


@router.post("/ingest", response_model=IngestionStartResponse)
async def start_ingestion(
    request: IngestionRequestModel,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Start ingestion for multiple repositories.

    Queues ingestion jobs for the specified repositories.
    Jobs run asynchronously; use /ingestion-status to monitor progress.

    Args:
        request: List of repository configurations to ingest

    Returns:
        Created ingestion jobs
    """
    if not request.repositories:
        raise HTTPException(
            status_code=400, detail="At least one repository is required"
        )

    if len(request.repositories) > 10:
        raise HTTPException(
            status_code=400, detail="Maximum 10 repositories per ingestion request"
        )

    try:
        configs = [
            RepoConfigModel(
                connection_id=r.connection_id,
                provider_repo_id=r.provider_repo_id,
                clone_url=r.clone_url,
                token=r.token,
                name=r.name,
                branch=r.branch,
                languages=r.languages,
                scan_frequency=r.scan_frequency,
                exclude_patterns=r.exclude_patterns,
                enable_webhook=r.enable_webhook,
            )
            for r in request.repositories
        ]

        jobs = await repo_service.start_ingestion(user.sub, configs)
        logger.info(f"Started {len(jobs)} ingestion jobs for user {user.sub}")

        return IngestionStartResponse(
            jobs=[
                IngestionJobResponse(
                    job_id=job.job_id,
                    repository_id=job.repository_id,
                    repository_name="",  # IngestionJob doesn't have repository_name
                    status=job.status,
                    progress=job.progress,
                    stage=job.current_stage,
                    files_processed=job.files_processed,
                    entities_indexed=job.entities_indexed,
                    embeddings_generated=job.embeddings_generated,
                    error_message=job.error_message,
                    started_at=job.started_at or "",
                    completed_at=job.completed_at,
                )
                for job in jobs
            ],
            message=f"Started {len(jobs)} ingestion job(s)",
        )

    except ValueError as e:
        logger.warning(f"Start ingestion validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ingestion request")
    except Exception as e:
        logger.error(f"Failed to start ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start ingestion")


@router.get("/ingestion-status", response_model=list[IngestionJobResponse])
async def get_ingestion_status(
    job_ids: str = Query(..., description="Comma-separated job IDs"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get ingestion status for jobs.

    Returns current status for the specified ingestion jobs.

    Args:
        job_ids: Comma-separated list of job IDs

    Returns:
        List of job statuses
    """
    ids = [id.strip() for id in job_ids.split(",") if id.strip()]

    if not ids:
        raise HTTPException(status_code=400, detail="At least one job_id is required")

    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 job IDs per request")

    try:
        jobs = await repo_service.get_ingestion_status(user.sub, ids)

        return [
            IngestionJobResponse(
                job_id=job.job_id,
                repository_id=job.repository_id,
                repository_name="",  # IngestionJob doesn't have repository_name
                status=job.status,
                progress=job.progress,
                stage=job.current_stage,
                files_processed=job.files_processed,
                entities_indexed=job.entities_indexed,
                embeddings_generated=job.embeddings_generated,
                error_message=job.error_message,
                started_at=job.started_at or "",
                completed_at=job.completed_at,
            )
            for job in jobs
        ]

    except Exception as e:
        logger.error(f"Failed to get ingestion status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get ingestion status")


@router.post("/ingestion/{job_id}/cancel")
async def cancel_ingestion(
    job_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Cancel an in-progress ingestion job.

    Args:
        job_id: Job ID to cancel

    Returns:
        Cancellation status
    """
    try:
        await repo_service.cancel_ingestion(user.sub, job_id)
        logger.info(
            f"Ingestion job {sanitize_log(job_id)} cancelled for user {sanitize_log(user.sub)}"
        )

        return {"status": "cancelled", "job_id": job_id}

    except ValueError as e:
        logger.warning(f"Cancel ingestion error - not found: {e}")
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    except Exception as e:
        logger.error(f"Failed to cancel ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel ingestion")


@router.post("/{repository_id}/sync")
async def trigger_sync(
    repository_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    repo_service: RepositoryOnboardService = Depends(get_repo_svc),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Trigger a manual sync for a repository.

    Queues a re-ingestion job for the repository.

    Args:
        repository_id: Repository ID

    Returns:
        Sync job information
    """
    try:
        # Get repository to create config
        repo = await repo_service.get_repository(user.sub, repository_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Create config for re-ingestion
        from src.services.repository_onboard_service import RepositoryConfig

        config = RepositoryConfig(
            repository_id=repository_id,
            name=repo.name,
            clone_url=repo.clone_url,
            branch=repo.branch,
            languages=repo.languages,
            scan_frequency=repo.scan_frequency,
            exclude_patterns=repo.exclude_patterns,
        )

        # Start ingestion
        jobs = await repo_service.start_ingestion(user.sub, [config])
        if not jobs:
            raise HTTPException(
                status_code=500, detail="Failed to create ingestion job"
            )

        job = jobs[0]
        logger.info(
            f"Manual sync triggered for repository {sanitize_log(repository_id)}"
        )

        return {
            "status": "queued",
            "job_id": job.job_id,
            "repository_id": repository_id,
        }

    except ValueError as e:
        logger.warning(f"Trigger sync error - not found: {e}")
        raise HTTPException(status_code=404, detail="Repository not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to trigger sync")
