"""REST API Endpoints for Environment Validator Agent.

Provides REST interface for environment validation, drift detection,
and configuration management (ADR-062).
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.env_validator.baseline_manager import (
    BaselineManager,
    MockBaselineManager,
)
from src.services.env_validator.config import load_environment_registry
from src.services.env_validator.drift_detector import DriftDetector, DriftReport
from src.services.env_validator.engine import ValidationEngine
from src.services.env_validator.models import (
    TriggerType,
    ValidationResult,
    ValidationRun,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/environment", tags=["environment-validator"])


# =============================================================================
# Pydantic Request/Response Models for API
# =============================================================================


class ValidateManifestRequest(BaseModel):
    """Request to validate a Kubernetes manifest."""

    manifest: str = Field(
        ...,
        description="Kubernetes manifest YAML content",
        min_length=1,
    )
    target_env: str = Field(
        ...,
        description="Target environment (dev, qa, staging, prod)",
        pattern="^(dev|qa|staging|prod)$",
    )
    strict: bool = Field(
        default=False,
        description="If true, warnings are treated as failures",
    )
    save_baseline: bool = Field(
        default=False,
        description="If true and validation passes, save as baseline",
    )


class ViolationResponse(BaseModel):
    """Response model for a single violation."""

    rule_id: str
    severity: str
    resource_type: str
    resource_name: str
    field_path: str
    expected_value: str
    actual_value: str
    message: str
    suggested_fix: str | None = None
    auto_remediable: bool = False


class ValidationResponse(BaseModel):
    """Response containing validation results."""

    valid: bool
    result: str
    run_id: str
    environment: str
    timestamp: datetime
    duration_ms: int
    resources_scanned: int
    violations: list[ViolationResponse]
    warnings: list[ViolationResponse]
    info: list[ViolationResponse]
    baseline_saved: bool = False

    @classmethod
    def from_validation_run(
        cls,
        run: ValidationRun,
        baseline_saved: bool = False,
    ) -> "ValidationResponse":
        """Create response from ValidationRun."""
        return cls(
            valid=run.result != ValidationResult.FAIL,
            result=run.result.value,
            run_id=run.run_id,
            environment=run.environment,
            timestamp=run.timestamp,
            duration_ms=run.duration_ms,
            resources_scanned=run.resources_scanned,
            violations=[
                ViolationResponse(
                    rule_id=v.rule_id,
                    severity=v.severity.value,
                    resource_type=v.resource_type,
                    resource_name=v.resource_name,
                    field_path=v.field_path,
                    expected_value=v.expected_value,
                    actual_value=v.actual_value,
                    message=v.message,
                    suggested_fix=v.suggested_fix,
                    auto_remediable=v.auto_remediable,
                )
                for v in run.violations
            ],
            warnings=[
                ViolationResponse(
                    rule_id=v.rule_id,
                    severity=v.severity.value,
                    resource_type=v.resource_type,
                    resource_name=v.resource_name,
                    field_path=v.field_path,
                    expected_value=v.expected_value,
                    actual_value=v.actual_value,
                    message=v.message,
                    suggested_fix=v.suggested_fix,
                    auto_remediable=v.auto_remediable,
                )
                for v in run.warnings
            ],
            info=[
                ViolationResponse(
                    rule_id=v.rule_id,
                    severity=v.severity.value,
                    resource_type=v.resource_type,
                    resource_name=v.resource_name,
                    field_path=v.field_path,
                    expected_value=v.expected_value,
                    actual_value=v.actual_value,
                    message=v.message,
                    suggested_fix=v.suggested_fix,
                    auto_remediable=v.auto_remediable,
                )
                for v in run.info
            ],
            baseline_saved=baseline_saved,
        )


class DriftEventResponse(BaseModel):
    """Response model for a drift event."""

    event_id: str
    resource_type: str
    resource_name: str
    namespace: str
    field_path: str
    baseline_value: str
    current_value: str
    detected_at: datetime
    severity: str
    baseline_hash: str
    current_hash: str


class DriftResponse(BaseModel):
    """Response containing drift detection results."""

    drift_detected: bool
    run_id: str
    environment: str
    timestamp: datetime
    resources_checked: int
    critical_drift_count: int
    drifted_resources: list[DriftEventResponse]
    validation_result: ValidationResponse | None = None

    @classmethod
    def from_drift_report(cls, report: DriftReport) -> "DriftResponse":
        """Create response from DriftReport."""
        return cls(
            drift_detected=report.has_drift,
            run_id=report.run_id,
            environment=report.environment,
            timestamp=report.timestamp,
            resources_checked=report.resources_checked,
            critical_drift_count=report.critical_drift_count,
            drifted_resources=[
                DriftEventResponse(
                    event_id=e.event_id,
                    resource_type=e.resource_type,
                    resource_name=e.resource_name,
                    namespace=e.namespace,
                    field_path=e.field_path,
                    baseline_value=e.baseline_value,
                    current_value=e.current_value,
                    detected_at=e.detected_at,
                    severity=e.severity.value,
                    baseline_hash=e.baseline_hash,
                    current_hash=e.current_hash,
                )
                for e in report.drift_events
            ],
            validation_result=(
                ValidationResponse.from_validation_run(report.validation_run)
                if report.validation_run
                else None
            ),
        )


class DetectDriftRequest(BaseModel):
    """Request to detect drift against baseline."""

    manifest: str = Field(
        ...,
        description="Current Kubernetes manifest YAML content",
        min_length=1,
    )


class EnvironmentConfigResponse(BaseModel):
    """Response model for environment configuration."""

    account_id: str
    ecr_registry: str
    neptune_cluster: str
    opensearch_domain: str
    resource_suffix: str
    eks_cluster: str
    region: str


class EnvironmentRegistryResponse(BaseModel):
    """Response containing environment registry."""

    environments: dict[str, EnvironmentConfigResponse]


class ValidationHistoryItem(BaseModel):
    """Single item in validation history."""

    run_id: str
    environment: str
    timestamp: datetime
    trigger: str
    result: str
    violations_count: int
    warnings_count: int
    resources_scanned: int


class ValidationHistoryResponse(BaseModel):
    """Response containing validation history."""

    items: list[ValidationHistoryItem]
    total_count: int
    has_more: bool


class BaselineResponse(BaseModel):
    """Response for baseline operations."""

    environment: str
    resource_type: str
    resource_name: str
    namespace: str
    content_hash: str
    validated_at: datetime
    validation_run_id: str
    created_by: str


class BaselineListResponse(BaseModel):
    """Response containing list of baselines."""

    baselines: list[BaselineResponse]
    count: int


class SaveBaselineRequest(BaseModel):
    """Request to save a validated manifest as baseline."""

    manifest: str = Field(
        ...,
        description="Validated Kubernetes manifest YAML content",
        min_length=1,
    )
    created_by: str = Field(
        default="api",
        description="User or system creating the baseline",
    )


class HealthResponse(BaseModel):
    """Response for health check."""

    service: str
    healthy: bool
    environment: str
    registry_loaded: bool
    baseline_table_status: str


# =============================================================================
# Dependency Injection
# =============================================================================


def get_validation_engine(
    env: str = Query(..., description="Target environment"),
) -> ValidationEngine:
    """Get validation engine for the specified environment."""
    return ValidationEngine(env)


def get_baseline_manager(
    env: str = Query(..., description="Target environment"),
) -> BaselineManager:
    """Get baseline manager for the specified environment."""
    # In production, use real DynamoDB; for testing, use mock
    import os

    if os.environ.get("ENV_VALIDATOR_USE_MOCK", "false").lower() == "true":
        return MockBaselineManager(env)
    return BaselineManager(env)


def get_drift_detector(
    env: str = Query(..., description="Target environment"),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
) -> DriftDetector:
    """Get drift detector for the specified environment."""
    return DriftDetector(env, baseline_manager)


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate a Kubernetes manifest",
)
async def validate_manifest(request: ValidateManifestRequest):
    """Validate a Kubernetes manifest for environment consistency.

    Checks that all resource references (ARNs, endpoints, image registries)
    match the target environment. Returns violations, warnings, and info.
    """
    try:
        engine = ValidationEngine(request.target_env)
        run = engine.validate_manifest(request.manifest, TriggerType.MANUAL)

        # Handle strict mode
        if request.strict and run.warnings:
            run.result = ValidationResult.FAIL
            run.violations.extend(run.warnings)
            run.warnings = []

        # Save baseline if requested and validation passed
        baseline_saved = False
        if request.save_baseline and run.result != ValidationResult.FAIL:
            import os

            if os.environ.get("ENV_VALIDATOR_USE_MOCK", "false").lower() == "true":
                manager = MockBaselineManager(request.target_env)
            else:
                manager = BaselineManager(request.target_env)
            manager.save_baseline(request.manifest, run.run_id, "api")
            baseline_saved = True

        return ValidationResponse.from_validation_run(run, baseline_saved)

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get(
    "/drift",
    response_model=DriftResponse,
    summary="Get drift status for environment",
)
async def get_drift_status(
    env: str = Query(..., description="Target environment"),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """Get current drift status for an environment.

    Returns information about detected drift from baselines.
    Note: Requires stored baselines for the environment.
    """
    try:
        # Get unresolved drift events from history
        unresolved = baseline_manager.get_unresolved_drift(env)

        # Build response
        return DriftResponse(
            drift_detected=len(unresolved) > 0,
            run_id="status-check",
            environment=env,
            timestamp=datetime.utcnow(),
            resources_checked=0,
            critical_drift_count=sum(1 for d in unresolved if d.severity == "critical"),
            drifted_resources=[
                DriftEventResponse(
                    event_id=d.event_id,
                    resource_type=d.resource_type,
                    resource_name=d.resource_name,
                    namespace=d.namespace,
                    field_path=d.field_path,
                    baseline_value=d.baseline_value,
                    current_value=d.current_value,
                    detected_at=d.detected_at,
                    severity=d.severity,
                    baseline_hash="",
                    current_hash="",
                )
                for d in unresolved
            ],
            validation_result=None,
        )

    except Exception as e:
        logger.error(f"Failed to get drift status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get drift status: {str(e)}",
        )


@router.post(
    "/drift/detect",
    response_model=DriftResponse,
    summary="Detect drift against baseline",
)
async def detect_drift(
    request: DetectDriftRequest,
    env: str = Query(..., description="Target environment"),
    drift_detector: DriftDetector = Depends(get_drift_detector),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """Detect configuration drift between current manifest and baseline.

    Compares the provided manifest against stored baselines and
    identifies any changes to critical configuration fields.
    """
    try:
        report = drift_detector.detect_drift(request.manifest)

        # Save drift events to history
        for event in report.drift_events:
            baseline_manager.save_drift_event(event)

        return DriftResponse.from_drift_report(report)

    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Drift detection failed: {str(e)}",
        )


@router.get(
    "/registry",
    response_model=EnvironmentRegistryResponse,
    summary="Get environment registry",
)
async def get_registry():
    """Get the environment configuration registry.

    Returns configuration for all known environments including
    account IDs, ECR registries, and endpoints.
    """
    try:
        registry = load_environment_registry()

        return EnvironmentRegistryResponse(
            environments={
                name: EnvironmentConfigResponse(
                    account_id=config.account_id,
                    ecr_registry=config.ecr_registry,
                    neptune_cluster=config.neptune_cluster,
                    opensearch_domain=config.opensearch_domain,
                    resource_suffix=config.resource_suffix,
                    eks_cluster=config.eks_cluster,
                    region=config.region,
                )
                for name, config in registry.environments.items()
            }
        )

    except Exception as e:
        logger.error(f"Failed to get registry: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get registry: {str(e)}",
        )


@router.get(
    "/validation-history",
    response_model=ValidationHistoryResponse,
    summary="Get validation history",
)
async def get_validation_history(
    env: str = Query(..., description="Target environment"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """Get recent validation runs for an environment.

    Returns validation history with results, counts, and timestamps.
    """
    try:
        # TODO: Implement validation history storage in DynamoDB
        # For now, return empty history
        return ValidationHistoryResponse(
            items=[],
            total_count=0,
            has_more=False,
        )

    except Exception as e:
        logger.error(f"Failed to get validation history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get validation history: {str(e)}",
        )


# =============================================================================
# Baseline Management Endpoints
# =============================================================================


@router.get(
    "/baselines",
    response_model=BaselineListResponse,
    summary="List baselines",
)
async def list_baselines(
    env: str = Query(..., description="Target environment"),
    resource_type: str | None = Query(
        default=None,
        description="Filter by resource type (ConfigMap, Deployment, etc.)",
    ),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """List all baselines for an environment.

    Optionally filter by resource type.
    """
    try:
        baselines = baseline_manager.list_baselines(env, resource_type)

        return BaselineListResponse(
            baselines=[
                BaselineResponse(
                    environment=b.environment,
                    resource_type=b.resource_type,
                    resource_name=b.resource_name,
                    namespace=b.namespace,
                    content_hash=b.content_hash,
                    validated_at=b.validated_at,
                    validation_run_id=b.validation_run_id,
                    created_by=b.created_by,
                )
                for b in baselines
            ],
            count=len(baselines),
        )

    except Exception as e:
        logger.error(f"Failed to list baselines: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list baselines: {str(e)}",
        )


@router.post(
    "/baselines",
    response_model=BaselineListResponse,
    status_code=201,
    summary="Save baseline",
)
async def save_baseline(
    request: SaveBaselineRequest,
    env: str = Query(..., description="Target environment"),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """Save a validated manifest as baseline.

    The manifest should already be validated before saving as baseline.
    """
    try:
        # Validate first
        engine = ValidationEngine(env)
        run = engine.validate_manifest(request.manifest, TriggerType.MANUAL)

        if run.result == ValidationResult.FAIL:
            raise HTTPException(
                status_code=400,
                detail="Cannot save baseline: manifest has validation errors",
            )

        # Save baseline
        baselines = baseline_manager.save_baseline(
            request.manifest,
            run.run_id,
            request.created_by,
        )

        return BaselineListResponse(
            baselines=[
                BaselineResponse(
                    environment=b.environment,
                    resource_type=b.resource_type,
                    resource_name=b.resource_name,
                    namespace=b.namespace,
                    content_hash=b.content_hash,
                    validated_at=b.validated_at,
                    validation_run_id=b.validation_run_id,
                    created_by=b.created_by,
                )
                for b in baselines
            ],
            count=len(baselines),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save baseline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save baseline: {str(e)}",
        )


@router.delete(
    "/baselines/{resource_type}/{namespace}/{resource_name}",
    summary="Delete baseline",
)
async def delete_baseline(
    resource_type: str,
    namespace: str,
    resource_name: str,
    env: str = Query(..., description="Target environment"),
    baseline_manager: BaselineManager = Depends(get_baseline_manager),
):
    """Delete a baseline for a specific resource."""
    try:
        result = baseline_manager.delete_baseline(
            env,
            resource_type,
            resource_name,
            namespace,
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Baseline not found: {resource_type}/{namespace}/{resource_name}",
            )

        return {"deleted": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete baseline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete baseline: {str(e)}",
        )


# =============================================================================
# Health Check
# =============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check(
    env: str = Query(default="dev", description="Environment to check"),
):
    """Check environment validator service health."""
    try:
        # Check registry loading
        registry = load_environment_registry()
        registry_loaded = len(registry.environments) > 0

        return HealthResponse(
            service="environment-validator",
            healthy=registry_loaded,
            environment=env,
            registry_loaded=registry_loaded,
            baseline_table_status="unknown",  # Would check DynamoDB in prod
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            service="environment-validator",
            healthy=False,
            environment=env,
            registry_loaded=False,
            baseline_table_status=f"error: {str(e)}",
        )
