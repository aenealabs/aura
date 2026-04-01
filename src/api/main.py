"""
Project Aura - FastAPI Application

Main API application exposing:
- Health check endpoints (Kubernetes probes, AWS ALB)
- Git ingestion webhook endpoints (GitHub webhooks)
- Job management endpoints (status, list, cancel)

Author: Project Aura Team
Created: 2025-11-28
Version: 1.0.0
"""

import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from src.agents.ast_parser_agent import ASTParserAgent
from src.api.agent_registry_endpoints import router as agent_registry_router
from src.api.anomaly_triggers import AnomalyTriggers, set_triggers
from src.api.approval_endpoints import router as approval_router
from src.api.auth import User, get_current_user, get_optional_user
from src.api.billing_endpoints import router as billing_router
from src.api.compliance_endpoints import router as compliance_router
from src.api.customer_health_endpoints import router as customer_health_router
from src.api.dashboard_endpoints import router as dashboard_router
from src.api.dashboard_endpoints import widget_router
from src.api.dependencies import set_anomaly_detector, set_monitoring_integration
from src.api.disaster_recovery_endpoints import router as dr_router
from src.api.documentation_endpoints import router as documentation_router
from src.api.edition_endpoints import router as edition_router
from src.api.env_validator_endpoints import router as env_validator_router
from src.api.environment_endpoints import router as environment_router
from src.api.explainability_endpoints import router as explainability_router
from src.api.export_endpoints import router as export_router
from src.api.extension_endpoints import router as extension_router
from src.api.feature_flags_endpoints import router as feature_flags_router
from src.api.feedback_endpoints import router as feedback_router
from src.api.gpu_scheduler_endpoints import router as gpu_scheduler_router
from src.api.guardrails_endpoints import router as guardrails_router
from src.api.health_endpoints import HealthCheckEndpoints
from src.api.health_metrics_endpoints import router as health_metrics_router
from src.api.incidents import router as incidents_router
from src.api.integration_endpoints import integration_router
from src.api.marketplace_endpoints import router as marketplace_router
from src.api.model_router_endpoints import router as model_router_router
from src.api.oauth_endpoints import router as oauth_router
from src.api.onboarding_endpoints import router as onboarding_router
from src.api.orchestration_endpoints import router as orchestration_router
from src.api.orchestrator_settings_endpoints import (
    router as orchestrator_settings_router,
)
from src.api.query_decomposition_endpoints import query_decomposition_router
from src.api.recurring_task_endpoints import router as recurring_task_router
from src.api.red_team_endpoints import red_team_router
from src.api.repository_endpoints import router as repository_router
from src.api.security_middleware import add_security_middleware
from src.api.settings_endpoints import router as settings_router
from src.api.sla_endpoints import router as sla_router
from src.api.team_endpoints import router as team_router
from src.api.ticketing_endpoints import router as ticketing_router
from src.api.trace_endpoints import router as trace_router
from src.api.trust_center_endpoints import router as trust_center_router
from src.api.usage_analytics_endpoints import router as usage_analytics_router
from src.api.webhook_handler import GitHubWebhookHandler, WebhookEvent
from src.services.anomaly_detection_service import AnomalyDetectionService
from src.services.database_connections import (
    get_database_services,
    get_embedding_service,
    get_llm_service,
    print_connection_status,
)
from src.services.git_ingestion_service import GitIngestionService
from src.services.observability_service import get_monitor, start_event_loop_monitor
from src.services.realtime_monitoring_integration import RealTimeMonitoringIntegration

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class IngestionRequest(BaseModel):
    """Request to trigger repository ingestion."""

    repository_url: str
    branch: str = "main"
    force_refresh: bool = False
    shallow_clone: bool = True


class IngestionResponse(BaseModel):
    """Response from ingestion request."""

    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    files_processed: int
    entities_indexed: int
    embeddings_generated: int
    errors: list[str]
    metadata: dict[str, Any]


class WebhookResponse(BaseModel):
    """Response from webhook processing."""

    status: str
    message: str
    job_id: str | None = None
    details: dict[str, Any] | None = None


# ============================================================================
# Global Service Instances
# ============================================================================

# These will be initialized in the lifespan context
# NOTE: git_ingestion_service, webhook_handler, health_endpoints are local to this module
# because they require complex initialization with database services.
# For services shared across modules, use src.api.dependencies (DI pattern).
git_ingestion_service: GitIngestionService | None = None
webhook_handler: GitHubWebhookHandler | None = None
health_endpoints: HealthCheckEndpoints | None = None
anomaly_triggers: AnomalyTriggers | None = None
_event_loop_monitor_task: asyncio.Task[None] | None = None


# ============================================================================
# API Latency Tracking Middleware (Optimization #10)
# ============================================================================

# Pre-compiled regex patterns for path normalization
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_NUMERIC_ID_PATTERN = re.compile(r"/\d+(/|$)")


class LatencyTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API request latency for all endpoints.

    Records latency metrics for p50/p95/p99 analysis and SLO monitoring.
    Excludes health check endpoints to avoid noise.
    """

    # Endpoints to exclude from latency tracking (health probes)
    EXCLUDED_PATHS = {"/health", "/health/live", "/health/ready", "/health/startup"}

    async def dispatch(self, request: Request, call_next):
        """Track request latency and record to observability service."""
        path = request.url.path

        # Skip health check endpoints
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        monitor = get_monitor()
        start_time = time.time()

        try:
            response = await call_next(request)

            # Record successful request latency
            latency_seconds = time.time() - start_time
            operation = f"api.{request.method}.{self._normalize_path(path)}"
            monitor.record_latency(operation, latency_seconds)
            monitor.record_success(operation)
            monitor.record_request(operation)

            return response

        except Exception as e:
            # Record failed request
            latency_seconds = time.time() - start_time
            operation = f"api.{request.method}.{self._normalize_path(path)}"
            monitor.record_latency(operation, latency_seconds)
            monitor.record_error(operation, e)
            raise

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for consistent metric grouping.

        Replaces variable path segments (UUIDs, IDs) with placeholders
        to group similar endpoints together.
        """
        # Replace UUIDs with placeholder
        path = _UUID_PATTERN.sub("{id}", path)
        # Replace numeric IDs with placeholder
        path = _NUMERIC_ID_PATTERN.sub("/{id}\\1", path)
        # Replace leading slash and convert to dot notation
        return path.strip("/").replace("/", ".")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes services on startup and cleans up on shutdown.
    """
    global git_ingestion_service, webhook_handler, health_endpoints, anomaly_triggers

    logger.info("Starting Project Aura API...")

    # Initialize services with environment-aware database connections
    # Mode (MOCK vs AWS) is auto-detected based on environment variables:
    #   - NEPTUNE_ENDPOINT: Enables real Neptune connection
    #   - OPENSEARCH_ENDPOINT: Enables real OpenSearch connection
    #   - AWS_REGION: Enables real DynamoDB connection
    try:
        # Print connection status for startup diagnostics
        print_connection_status()

        # Get database services (Neptune, OpenSearch, DynamoDB)
        db_services = get_database_services()
        neptune_service = db_services["neptune"]
        opensearch_service = db_services["opensearch"]
        persistence_service = db_services["persistence"]

        # Get embedding service (Titan via Bedrock)
        embedding_service = get_embedding_service()

        # Get LLM service (Claude via Bedrock)
        llm_service = get_llm_service()

        # AST Parser for code analysis
        ast_parser = ASTParserAgent()

        # Git Ingestion Service with real database connections
        git_ingestion_service = GitIngestionService(
            neptune_service=neptune_service,
            opensearch_service=opensearch_service,
            embedding_service=embedding_service,
            ast_parser=ast_parser,
            clone_base_path=os.environ.get(
                "AURA_CLONE_PATH", "/tmp/aura-repos"
            ),  # nosec B108
            persistence_service=persistence_service,
        )
        logger.info("GitIngestionService initialized")

        # Webhook Handler
        webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        allowed_branches = os.environ.get(
            "AURA_ALLOWED_BRANCHES", "main,master,develop"
        ).split(",")

        webhook_handler = GitHubWebhookHandler(
            webhook_secret=webhook_secret,
            ingestion_service=git_ingestion_service,
            allowed_branches=allowed_branches,
        )
        logger.info("GitHubWebhookHandler initialized")

        # Health Endpoints with real service references for health checks
        health_endpoints = HealthCheckEndpoints(
            neptune_service=neptune_service,
            opensearch_service=opensearch_service,
            bedrock_service=llm_service,
        )
        logger.info("HealthCheckEndpoints initialized")

        # Notification Service initialization is now handled by src.api.dependencies
        # via @lru_cache factory (get_notification_service). Environment-aware mode
        # selection happens at first call via Depends(get_notification_service).
        logger.info("NotificationService will be initialized on first use via DI")

        # Real-Time Anomaly Detection and Monitoring Integration
        # Wires anomaly detection to CloudWatch, EventBridge, DynamoDB, and notifications
        # These are shared across modules via src.api.dependencies
        _anomaly_detector = AnomalyDetectionService(
            baseline_window_hours=24,
            min_samples_for_baseline=30,
            enable_notifications=True,
        )
        set_anomaly_detector(_anomaly_detector)
        logger.info("AnomalyDetectionService initialized (via dependencies)")

        _monitoring_integration = RealTimeMonitoringIntegration()
        _monitoring_integration.connect(_anomaly_detector)
        await _monitoring_integration.start()
        set_monitoring_integration(_monitoring_integration)
        logger.info(
            "RealTimeMonitoringIntegration initialized and connected to anomaly detector"
        )

        # Anomaly Triggers for API event tracking
        # Wires API events (HITL, webhooks, requests) to anomaly detection
        anomaly_triggers = AnomalyTriggers(_anomaly_detector)
        set_triggers(anomaly_triggers)
        logger.info("AnomalyTriggers initialized and connected to anomaly detector")

        # Start event loop lag monitor (optimization #10)
        # Measures event loop blocking to detect sync code in async paths
        global _event_loop_monitor_task
        _event_loop_monitor_task = asyncio.create_task(start_event_loop_monitor(5.0))
        logger.info("Event loop lag monitor started (5s interval)")

        logger.info("Project Aura API started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Project Aura API...")

    # Stop event loop monitor (global declared at function start)
    if _event_loop_monitor_task:
        _event_loop_monitor_task.cancel()
        try:
            await _event_loop_monitor_task
        except asyncio.CancelledError:
            pass
        _event_loop_monitor_task = None
        logger.info("Event loop lag monitor stopped")

    # Stop monitoring integration (flushes pending metrics)
    # Access via dependencies module (DI pattern)
    from src.api.dependencies import get_monitoring_integration

    _mon_int = get_monitoring_integration()
    if _mon_int:
        await _mon_int.stop()
        set_monitoring_integration(None)
        logger.info("RealTimeMonitoringIntegration stopped")

    # Clear anomaly detector reference
    set_anomaly_detector(None)


# ============================================================================
# Service Getters (for use by other modules)
# ============================================================================
# NOTE: get_anomaly_detector() and get_monitoring_integration() are now in
# src.api.dependencies for proper dependency injection pattern.


def get_anomaly_triggers() -> AnomalyTriggers | None:
    """Get the global anomaly triggers instance."""
    return anomaly_triggers


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Project Aura API",
    description="Autonomous Code Intelligence Platform - Git Ingestion & Analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for frontend access
# In production, restrict origins to specific domains
cors_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware (headers, request ID, size limits, exception handling)
# Enable HSTS in production, disable in development
# Explicit validation: ENVIRONMENT should always be set in deployed environments
_environment = os.environ.get("ENVIRONMENT")
if _environment is None:
    import logging as _logging

    _logging.warning(
        "ENVIRONMENT not set, defaulting to 'dev'. "
        "HSTS will be disabled. Set ENVIRONMENT=prod for production security."
    )
    _environment = "dev"
enable_hsts = _environment != "dev"
debug_mode = os.environ.get("DEBUG", "false").lower() == "true"
add_security_middleware(
    app,
    enable_hsts=enable_hsts,
    max_content_length=10 * 1024 * 1024,  # 10 MB
    debug=debug_mode,
)

# API latency tracking middleware (optimization #10)
# Records p50/p95/p99 latency for all API endpoints
app.add_middleware(LatencyTrackingMiddleware)


# ============================================================================
# Authentication Endpoints
# ============================================================================


@app.get("/api/v1/auth/me", tags=["Authentication"])
async def get_current_user_info(user: User = Depends(get_current_user)):  # noqa: B008
    """
    Get the currently authenticated user's information.

    Requires a valid JWT token in the Authorization header.
    Returns user profile including roles/groups.
    """
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "groups": user.groups,
    }


@app.get("/api/v1/auth/validate", tags=["Authentication"])
async def validate_token(user: User | None = Depends(get_optional_user)):  # noqa: B008
    """
    Validate an authentication token.

    Returns whether the token is valid and user info if authenticated.
    Does not require authentication (returns valid=false for unauthenticated).
    """
    if user:
        return {
            "valid": True,
            "user": {
                "sub": user.sub,
                "email": user.email,
                "name": user.name,
                "roles": user.roles,
            },
        }
    return {"valid": False, "user": None}


# ============================================================================
# Health Check Endpoints
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """AWS ALB health check - simple 200 OK response."""
    if health_endpoints:
        return await health_endpoints.aws_health_check()
    return {"status": "healthy", "timestamp": "unknown"}


@app.get("/health/live", tags=["Health"])
async def liveness_probe():
    """Kubernetes liveness probe - is the service alive?"""
    if health_endpoints:
        result = await health_endpoints.liveness_probe()
        if result["status"] == "dead":
            raise HTTPException(status_code=500, detail="Service is not alive")
        return result
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness_probe():
    """Kubernetes readiness probe - can the service accept traffic?"""
    if health_endpoints:
        result = await health_endpoints.readiness_probe()
        if result["status"] == "not_ready":
            raise HTTPException(
                status_code=503, detail="Service is not ready to accept traffic"
            )
        return result
    return {"status": "ready"}


@app.get("/health/startup", tags=["Health"])
async def startup_probe():
    """Kubernetes startup probe - has the service finished initializing?"""
    if health_endpoints:
        result = await health_endpoints.startup_probe()
        if result["status"] == "starting":
            raise HTTPException(status_code=503, detail=result)
        return result
    return {"status": "started"}


@app.get("/health/detailed", tags=["Health"])
async def detailed_health():
    """Detailed health metrics for monitoring dashboards."""
    if health_endpoints:
        return await health_endpoints.detailed_health()
    return {"status": "unknown", "message": "Health endpoints not initialized"}


# ============================================================================
# Git Ingestion Endpoints
# ============================================================================


@app.post("/api/v1/ingest", response_model=IngestionResponse, tags=["Ingestion"])
async def trigger_ingestion(
    request: IngestionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger full repository ingestion.

    This endpoint accepts a repository URL and triggers a background
    ingestion job. The job will:
    1. Clone or fetch the repository
    2. Parse all supported source files
    3. Populate the Neptune graph database
    4. Generate embeddings and index in OpenSearch

    Returns immediately with a job_id for tracking.
    """
    if not git_ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    try:
        # Generate job ID and queue the job
        job_id = git_ingestion_service._generate_job_id(
            request.repository_url, request.branch
        )

        # Add ingestion task to background
        background_tasks.add_task(
            _run_ingestion,
            request.repository_url,
            request.branch,
            request.force_refresh,
            request.shallow_clone,
        )

        logger.info(f"Ingestion job {job_id} queued for {request.repository_url}")

        return IngestionResponse(
            job_id=job_id,
            status="queued",
            message=f"Ingestion job queued for {request.repository_url}",
        )

    except Exception as e:
        logger.error("Failed to queue ingestion: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to queue ingestion")


async def _run_ingestion(
    repository_url: str,
    branch: str,
    force_refresh: bool,
    shallow_clone: bool,
):
    """Background task to run ingestion."""
    if git_ingestion_service is None:
        logger.error(f"Ingestion service not initialized for {repository_url}")
        return
    try:
        await git_ingestion_service.ingest_repository(
            repository_url=repository_url,
            branch=branch,
            force_refresh=force_refresh,
            shallow=shallow_clone,  # API uses shallow_clone, service uses shallow
        )
    except Exception as e:
        logger.error(f"Ingestion failed for {repository_url}: {e}", exc_info=True)


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Ingestion"])
async def get_job_status(job_id: str):
    """
    Get the status of an ingestion job.

    Returns current status, progress metrics, and any errors.
    """
    if not git_ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    job = git_ingestion_service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        files_processed=job.files_processed,
        entities_indexed=job.entities_indexed,
        embeddings_generated=job.embeddings_generated,
        errors=job.errors,
        metadata=job.metadata,
    )


@app.get("/api/v1/jobs", tags=["Ingestion"])
async def list_jobs(active_only: bool = False):
    """
    List all ingestion jobs.

    Args:
        active_only: If true, only return active (in-progress) jobs
    """
    if not git_ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    if active_only:
        jobs = git_ingestion_service.list_active_jobs()
    else:
        # Return both active and completed jobs
        active = git_ingestion_service.list_active_jobs()
        completed = git_ingestion_service.completed_jobs
        jobs = active + completed

    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "repository_url": job.repository_url,
                "branch": job.branch,
                "status": job.status.value,
                "files_processed": job.files_processed,
            }
            for job in jobs
        ],
        "total": len(jobs),
    }


@app.delete("/api/v1/repositories", tags=["Ingestion"])
async def delete_repository(repository_url: str):
    """
    Delete a repository from the index.

    Removes all code entities from Neptune graph, all embeddings
    from OpenSearch, and deletes the local clone.

    Args:
        repository_url: URL of the repository to delete
    """
    if not git_ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    try:
        result = await git_ingestion_service.delete_repository(repository_url)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Repository deletion partially failed",
                    "errors": result["errors"],
                    "details": result,
                },
            )

        return {
            "status": "deleted",
            "repository_url": repository_url,
            "neptune_entities_deleted": result["neptune_entities_deleted"],
            "opensearch_documents_deleted": result["opensearch_documents_deleted"],
            "local_clone_removed": result["local_clone_removed"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Repository deletion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete repository")


# ============================================================================
# GitHub Webhook Endpoints
# ============================================================================


@app.post("/webhook/github", response_model=WebhookResponse, tags=["Webhooks"])
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),  # noqa: B008
    x_hub_signature_256: str | None = Header(  # noqa: B008
        None, alias="X-Hub-Signature-256"
    ),
    x_github_delivery: str | None = Header(  # noqa: B008
        None, alias="X-GitHub-Delivery"
    ),
):
    """
    GitHub webhook endpoint for push and pull request events.

    Configure in GitHub repository settings:
    - Payload URL: https://your-domain/webhook/github
    - Content type: application/json
    - Secret: (your webhook secret)
    - Events: Push, Pull requests

    The webhook will:
    1. Validate the signature (if secret configured)
    2. Parse the event type and changed files
    3. Trigger incremental ingestion for changed files
    """
    if not webhook_handler:
        raise HTTPException(status_code=503, detail="Webhook handler not initialized")

    try:
        # Get raw body for signature validation
        body = await request.body()

        # Build headers dict
        headers = {
            "X-GitHub-Event": x_github_event or "",
            "X-Hub-Signature-256": x_hub_signature_256 or "",
            "X-GitHub-Delivery": x_github_delivery or "",
        }

        # Parse the event
        event = webhook_handler.parse_event(headers, body)

        if not event:
            return WebhookResponse(
                status="ignored",
                message="Event not processed (unsupported type or invalid signature)",
            )

        # Log the event
        logger.info(
            f"Received webhook: {event.event_type.value} for "
            f"{event.repository_name}/{event.branch} "
            f"({len(event.changed_files)} files)"
        )

        # Process in background
        background_tasks.add_task(_process_webhook_event, event)

        return WebhookResponse(
            status="accepted",
            message=f"Webhook accepted for {event.repository_name}/{event.branch}",
            details={
                "event_type": event.event_type.value,
                "repository": event.repository_name,
                "branch": event.branch,
                "changed_files": len(event.changed_files),
                "delivery_id": x_github_delivery,
            },
        )

    except Exception as e:
        logger.error("Webhook processing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process webhook")


async def _process_webhook_event(event: WebhookEvent):
    """Background task to process webhook event."""
    if webhook_handler is None:
        logger.error("Webhook handler not initialized")
        return

    import time

    start_time = time.time()
    success = False
    error_msg = None

    try:
        result = await webhook_handler.process_event(event)
        success = result.get("status") not in ("error", "failed")
        logger.info(f"Webhook event processed: {result}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to process webhook event: {e}", exc_info=True)
    finally:
        # Record webhook processing metrics for anomaly detection
        if anomaly_triggers:
            processing_time_ms = (time.time() - start_time) * 1000
            anomaly_triggers.record_webhook_event(
                success=success,
                event_type=event.event_type.value,
                error=error_msg,
                processing_time_ms=processing_time_ms,
            )


@app.get("/webhook/queue", tags=["Webhooks"])
async def get_webhook_queue():
    """Get the current webhook event queue status."""
    if not webhook_handler:
        raise HTTPException(status_code=503, detail="Webhook handler not initialized")

    return webhook_handler.get_queue_status()


@app.delete("/webhook/queue", tags=["Webhooks"])
async def clear_webhook_queue():
    """Clear the webhook event queue."""
    if not webhook_handler:
        raise HTTPException(status_code=503, detail="Webhook handler not initialized")

    count = webhook_handler.clear_queue()
    return {"status": "cleared", "events_removed": count}


# ============================================================================
# HITL Approval Endpoints (mounted via router)
# ============================================================================

app.include_router(approval_router)

# ============================================================================
# Platform Settings Endpoints (mounted via router)
# ============================================================================

app.include_router(settings_router)

# ============================================================================
# Incident Investigation Endpoints (ADR-025 Phase 4)
# ============================================================================

app.include_router(incidents_router)

# ============================================================================
# VS Code Extension Endpoints (ADR-028 Phase 4)
# ============================================================================

app.include_router(extension_router)

# ============================================================================
# Red Team Dashboard Endpoints (ADR-028 Phase 7 - Issue #33)
# ============================================================================

app.include_router(red_team_router)

# ============================================================================
# Query Decomposition Endpoints (ADR-028 Phase 3 - Issue #32)
# ============================================================================

app.include_router(query_decomposition_router)

# ============================================================================
# Integration Hub Endpoints (ADR-028 Phase 3 - Issue #34)
# ============================================================================

app.include_router(integration_router)

# ============================================================================
# Agent Registry Endpoints (ADR-028 - Issue #35)
# ============================================================================

app.include_router(agent_registry_router)

# ============================================================================
# Test Environment Provisioning Endpoints (ADR-039)
# ============================================================================

app.include_router(environment_router)

# ============================================================================
# Agent Orchestration Endpoints (Hybrid Architecture)
# ============================================================================

app.include_router(orchestration_router)

# ============================================================================
# Orchestrator Settings Endpoints (Deployment Mode Configuration)
# ============================================================================

app.include_router(orchestrator_settings_router)

# ============================================================================
# OAuth Endpoints (ADR-043 Repository Onboarding)
# ============================================================================

app.include_router(oauth_router)

# ============================================================================
# Repository Management Endpoints (ADR-043 Repository Onboarding)
# ============================================================================

app.include_router(repository_router)

# ============================================================================
# Recurring Task Endpoints (ADR-055 Phase 3 Recurring Tasks)
# ============================================================================

app.include_router(recurring_task_router)

# ============================================================================
# Support Ticketing Endpoints (ADR-046 Support Ticketing Connectors)
# ============================================================================

app.include_router(ticketing_router)

# ============================================================================
# Customer Health Metrics Endpoints
# ============================================================================

app.include_router(health_metrics_router)

# ============================================================================
# Feature Flags Endpoints
# ============================================================================

app.include_router(feature_flags_router)

# ============================================================================
# Beta Feedback Endpoints
# ============================================================================

app.include_router(feedback_router)

# ============================================================================
# Usage Analytics Endpoints
# ============================================================================

app.include_router(usage_analytics_router)

# ============================================================================
# Billing Endpoints
# ============================================================================

app.include_router(billing_router)

# ============================================================================
# GPU Scheduler Endpoints (ADR-061)
# ============================================================================
app.include_router(gpu_scheduler_router)

# ============================================================================
# Customer Health Endpoints
# ============================================================================

app.include_router(customer_health_router)

# ============================================================================
# Generic Export API Endpoints (ADR-048 Phase 5)
# ============================================================================

app.include_router(export_router)

# ============================================================================
# AWS Marketplace Endpoints
# ============================================================================

app.include_router(marketplace_router)

# ============================================================================
# SLA Monitoring Endpoints
# ============================================================================

app.include_router(sla_router)

# ============================================================================
# Disaster Recovery Endpoints
# ============================================================================

app.include_router(dr_router)

# ============================================================================
# Compliance Evidence Endpoints
# ============================================================================

app.include_router(compliance_router)

# ============================================================================
# Model Router Endpoints (Issue #31 - LLM Cost Optimization Dashboard)
# ============================================================================

app.include_router(model_router_router)

# ============================================================================
# Trace Explorer Endpoints (Issue #30 - OpenTelemetry Visualization)
# ============================================================================

app.include_router(trace_router)

# ============================================================================
# Customer Onboarding Endpoints (ADR-047)
# ============================================================================

app.include_router(onboarding_router)

# ============================================================================
# Team Management Endpoints (ADR-047)
# ============================================================================

app.include_router(team_router)

# ============================================================================
# Edition and License Endpoints (ADR-049 Self-Hosted Deployment)
# ============================================================================

app.include_router(edition_router)

# ============================================================================
# Documentation Agent Endpoints (ADR-056)
# ============================================================================

app.include_router(documentation_router)

# ============================================================================
# Environment Validator Endpoints (ADR-062)
# ============================================================================

app.include_router(env_validator_router)

# ============================================================================
# AI Trust Center Endpoints (Constitutional AI Dashboard)
# ============================================================================

app.include_router(trust_center_router)

# ============================================================================
# Dashboard Configuration Endpoints (ADR-064)
# ============================================================================

app.include_router(dashboard_router)
app.include_router(widget_router)

# ============================================================================
# Guardrails Configuration Endpoints (ADR-069)
# ============================================================================

app.include_router(guardrails_router)

# ============================================================================
# Explainability Framework Endpoints (ADR-068)
# ============================================================================

app.include_router(explainability_router)

# ============================================================================
# Anomaly Detection Diagnostic Endpoints
# ============================================================================


@app.get("/api/v1/anomalies/status", tags=["Diagnostics"])
async def anomaly_status():
    """Get the status of anomaly detection services."""
    from src.api.dependencies import get_anomaly_detector, get_monitoring_integration

    detector = get_anomaly_detector()
    mon_int = get_monitoring_integration()
    return {
        "anomaly_detector": {
            "initialized": detector is not None,
            "notifications_enabled": (
                detector.enable_notifications if detector else False
            ),
            "baseline_window_hours": (
                detector.baseline_window_hours if detector else 0
            ),
        },
        "monitoring_integration": {
            "initialized": mon_int is not None,
            "running": (mon_int._running if mon_int else False),
        },
        "anomaly_triggers": {
            "initialized": anomaly_triggers is not None,
            "enabled": anomaly_triggers.enabled if anomaly_triggers else False,
        },
    }


@app.post("/api/v1/anomalies/test", tags=["Diagnostics"])
async def test_anomaly_pipeline(
    metric_name: str = "test.metric",
    value: float = 100.0,
    severity: str = "MEDIUM",
):
    """
    Test the anomaly detection pipeline with synthetic data.

    This endpoint directly injects a metric into the anomaly detector
    to validate the full pipeline is working.
    """
    from src.api.dependencies import get_anomaly_detector

    detector = get_anomaly_detector()
    if not detector:
        raise HTTPException(
            status_code=503,
            detail="AnomalyDetectionService not initialized",
        )

    if not anomaly_triggers:
        raise HTTPException(
            status_code=503,
            detail="AnomalyTriggers not initialized",
        )

    import uuid

    test_id = str(uuid.uuid4())[:8]
    full_metric_name = f"{metric_name}.{test_id}"

    # Record a test metric through the anomaly detector
    anomaly_result = detector.record_metric(
        metric_name=full_metric_name,
        value=value,
    )

    # Also trigger through AnomalyTriggers to test the API integration path
    anomaly_triggers.record_security_event(
        event_type="diagnostic_test",
        severity=severity,
        description=f"Diagnostic test event {test_id}",
        affected_components=["diagnostic-endpoint"],
    )

    return {
        "status": "ok",
        "test_id": test_id,
        "metric_recorded": full_metric_name,
        "anomaly_detected": anomaly_result is not None,
        "security_event_triggered": True,
        "message": "Test data injected into anomaly pipeline",
    }


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    request_id = getattr(request.state, "request_id", None)
    content = {
        "error": exc.detail if isinstance(exc.detail, str) else "Request failed",
        "status_code": exc.status_code,
        "path": str(request.url.path),
    }
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors.

    Security: Never expose internal exception details to clients.
    The full exception is logged server-side for debugging.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unexpected error [request_id=%s, path=%s]: %s",
        request_id,
        request.url.path,
        exc,
        exc_info=True,
    )
    content = {
        "error": "Internal server error",
        "message": "An unexpected error occurred. Please try again or contact support.",
        "path": str(request.url.path),
    }
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=500, content=content)


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", tags=["Root"])
async def root():
    """API root - returns service information."""
    return {
        "service": "Project Aura API",
        "version": "1.0.0",
        "description": "Autonomous Code Intelligence Platform",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "auth": "/api/v1/auth/me",
            "ingestion": "/api/v1/ingest",
            "jobs": "/api/v1/jobs",
            "webhook": "/webhook/github",
            "approvals": "/api/v1/approvals",
            "settings": "/api/v1/settings",
            "incidents": "/api/v1/incidents",
            "extension": "/api/v1/extension",
            "oauth": "/api/v1/oauth",
            "repositories": "/api/v1/repositories",
            "onboarding": "/api/v1/onboarding",
            "team": "/api/v1/team",
            "edition": "/edition",
            "documentation": "/api/v1/documentation",
            "trust_center": "/api/v1/trust-center",
        },
    }


# ============================================================================
# Development Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run development server
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",  # nosec B104 - dev server binding
        port=8080,
        reload=True,
        log_level="info",
    )
