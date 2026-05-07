"""
Feature Flags API Endpoints.

Provides REST API for feature flag management:
- GET /api/v1/features - List all features
- GET /api/v1/features/{name} - Get feature details
- GET /api/v1/features/status - Get feature status for current user
- POST /api/v1/features/beta/enroll - Enroll in beta program
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import User, get_current_user, require_role
from src.api.log_sanitizer import sanitize_log
from src.config.feature_flags import (
    CustomerFeatureOverrides,
    FeatureDefinition,
    FeatureStatus,
    FeatureTier,
    get_beta_features,
    get_feature_flags,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/features",
    tags=["Feature Flags"],
)


# =============================================================================
# Response Models
# =============================================================================


class FeatureResponse(BaseModel):
    """Feature flag response."""

    name: str
    description: str
    status: str
    min_tier: str
    enabled: bool
    enabled_by_default: bool
    requires_consent: bool
    rollout_percentage: int


class FeatureStatusResponse(BaseModel):
    """Feature status for current user."""

    features: Dict[str, Dict[str, Any]]
    tier: str
    beta_participant: bool
    enabled_count: int
    total_count: int


class BetaEnrollmentRequest(BaseModel):
    """Beta program enrollment request."""

    accept_terms: bool = False
    features: Optional[List[str]] = None


class BetaEnrollmentResponse(BaseModel):
    """Beta program enrollment response."""

    enrolled: bool
    enabled_features: List[str]
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def feature_to_response(
    feature: FeatureDefinition,
    enabled: bool = True,
) -> FeatureResponse:
    """Convert FeatureDefinition to response model."""
    return FeatureResponse(
        name=feature.name,
        description=feature.description,
        status=feature.status.value,
        min_tier=feature.min_tier.value,
        enabled=enabled,
        enabled_by_default=feature.enabled_by_default,
        requires_consent=feature.requires_consent,
        rollout_percentage=feature.rollout_percentage,
    )


def get_user_tier(user: User) -> FeatureTier:
    """Get pricing tier for user (from user metadata or default)."""
    # In production, this would come from subscription data
    tier_str = getattr(user, "tier", "starter")
    try:
        return FeatureTier(tier_str)
    except ValueError:
        return FeatureTier.STARTER


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "",
    response_model=List[FeatureResponse],
    summary="List all features",
    description="Get all available feature flags with their definitions.",
)
async def list_features(
    status: Optional[str] = Query(  # noqa: B008
        default=None,
        description="Filter by status (alpha, beta, ga, deprecated)",
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List all feature flags."""
    try:
        service = get_feature_flags()
        tier = get_user_tier(current_user)
        customer_id = getattr(current_user, "customer_id", None)

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = FeatureStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: alpha, beta, ga, deprecated",
                )

        features = service.list_features(status=status_filter)

        return [
            feature_to_response(
                f,
                enabled=service.is_enabled(f.name, customer_id, tier),
            )
            for f in features
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing features: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list features")


@router.get(
    "/status",
    response_model=FeatureStatusResponse,
    summary="Get feature status",
    description="Get feature flag status for the current user.",
)
async def get_feature_status(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get feature status for current user."""
    try:
        service = get_feature_flags()
        tier = get_user_tier(current_user)
        customer_id = getattr(current_user, "customer_id", None)

        # Get full status
        status = service.get_feature_flags_status(customer_id, tier)

        # Check beta participation
        overrides = service.get_customer_overrides(customer_id) if customer_id else None
        beta_participant = overrides.beta_participant if overrides else False

        enabled_count = sum(1 for f in status.values() if f["enabled"])

        return FeatureStatusResponse(
            features=status,
            tier=tier.value,
            beta_participant=beta_participant,
            enabled_count=enabled_count,
            total_count=len(status),
        )

    except Exception as e:
        logger.error("Error getting feature status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve feature status")


@router.get(
    "/beta",
    response_model=List[FeatureResponse],
    summary="List beta features",
    description="Get all features currently in beta.",
)
async def list_beta_features(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List all beta features."""
    try:
        service = get_feature_flags()
        tier = get_user_tier(current_user)
        customer_id = getattr(current_user, "customer_id", None)

        beta_features = get_beta_features()

        return [
            feature_to_response(
                f,
                enabled=service.is_enabled(f.name, customer_id, tier),
            )
            for f in beta_features.values()
        ]

    except Exception as e:
        logger.error("Error listing beta features: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list beta features")


@router.post(
    "/beta/enroll",
    response_model=BetaEnrollmentResponse,
    summary="Enroll in beta program",
    description="Enroll the current user's organization in the beta program.",
)
async def enroll_in_beta(
    request: BetaEnrollmentRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Enroll in the beta program."""
    try:
        if not request.accept_terms:
            raise HTTPException(
                status_code=400,
                detail="Must accept beta program terms to enroll",
            )

        service = get_feature_flags()
        tier = get_user_tier(current_user)
        customer_id = getattr(current_user, "customer_id", None)

        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail="Customer ID required for beta enrollment",
            )

        # Enable beta features
        service.enable_beta_features(customer_id, tier)

        # Get enabled features list
        enabled_features = service.list_enabled_features(customer_id, tier)
        beta_features = [f for f in enabled_features if f in get_beta_features()]

        logger.info(f"Customer {customer_id} enrolled in beta program")

        return BetaEnrollmentResponse(
            enrolled=True,
            enabled_features=beta_features,
            message=f"Successfully enrolled in beta program. {len(beta_features)} beta features enabled.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error enrolling in beta: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enroll in beta")


@router.get(
    "/{feature_name}",
    response_model=FeatureResponse,
    summary="Get feature details",
    description="Get details for a specific feature flag.",
)
async def get_feature(
    feature_name: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get details for a specific feature."""
    try:
        service = get_feature_flags()
        tier = get_user_tier(current_user)
        customer_id = getattr(current_user, "customer_id", None)

        feature = service.get_feature(feature_name)
        if not feature:
            raise HTTPException(
                status_code=404,
                detail=f"Feature not found: {feature_name}",
            )

        return feature_to_response(
            feature,
            enabled=service.is_enabled(feature_name, customer_id, tier),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting feature: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve feature")


@router.post(
    "/admin/override",
    summary="Set feature override (admin only)",
    description="Set feature flag override for a specific customer.",
)
async def set_feature_override(
    customer_id: str,
    feature_name: str,
    enabled: bool,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    """Set feature override for a customer (admin only)."""
    try:
        service = get_feature_flags()

        feature = service.get_feature(feature_name)
        if not feature:
            raise HTTPException(
                status_code=404,
                detail=f"Feature not found: {feature_name}",
            )

        # Get or create overrides
        overrides = service.get_customer_overrides(customer_id)
        if not overrides:
            overrides = CustomerFeatureOverrides(
                customer_id=customer_id,
                tier=FeatureTier.STARTER,
            )

        # Set override
        if enabled:
            overrides.enabled_features.add(feature_name)
            overrides.disabled_features.discard(feature_name)
        else:
            overrides.disabled_features.add(feature_name)
            overrides.enabled_features.discard(feature_name)

        service.set_customer_overrides(overrides)

        logger.info(
            f"Admin {sanitize_log(current_user.email)} set {sanitize_log(feature_name)}={sanitize_log(enabled)} for customer {sanitize_log(customer_id)}"
        )

        return {
            "status": "success",
            "customer_id": customer_id,
            "feature": feature_name,
            "enabled": enabled,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error setting override: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set feature override")
