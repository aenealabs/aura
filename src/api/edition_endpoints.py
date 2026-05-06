"""
Project Aura - Edition and License API Endpoints

API endpoints for edition detection and license management
in self-hosted deployments.

See ADR-049: Self-Hosted Deployment Strategy
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.services.edition_service import Edition, EditionService, get_edition_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/edition", tags=["edition"])


class EditionResponse(BaseModel):
    """Response model for edition information."""

    edition: str = Field(
        description="Current edition (community, enterprise, enterprise_plus)"
    )
    is_self_hosted: bool = Field(description="Whether running in self-hosted mode")
    features: list[str] = Field(description="List of available features")
    feature_count: int = Field(description="Number of available features")
    license_required: bool = Field(description="Whether a license is required")
    has_valid_license: bool = Field(description="Whether a valid license is present")


class LicenseResponse(BaseModel):
    """Response model for license information."""

    license_key: str = Field(description="Masked license key")
    edition: str = Field(description="Licensed edition")
    organization: str = Field(description="Organization name")
    issued_at: str = Field(description="License issue date (ISO format)")
    expires_at: str | None = Field(description="License expiry date (ISO format)")
    features: list[str] = Field(description="Licensed features")
    max_users: int | None = Field(description="Maximum users allowed")
    max_repositories: int | None = Field(description="Maximum repositories allowed")
    support_tier: str = Field(description="Support tier level")
    is_valid: bool = Field(description="Whether license is currently valid")
    is_expired: bool = Field(description="Whether license is expired")
    validation_error: str | None = Field(description="Validation error if any")


class LicenseValidateRequest(BaseModel):
    """Request model for license validation."""

    license_key: str = Field(
        description="License key to validate",
        min_length=20,
        examples=["AURA-ENT-ACME1234-XXXX"],
    )


class FeatureCheckRequest(BaseModel):
    """Request model for feature check."""

    feature: str = Field(description="Feature name to check")


class FeatureCheckResponse(BaseModel):
    """Response model for feature check."""

    feature: str = Field(description="Feature name")
    available: bool = Field(description="Whether feature is available")
    edition: str = Field(description="Current edition")
    requires_upgrade: bool = Field(description="Whether upgrade is needed for feature")


@router.get("", response_model=EditionResponse)
async def get_edition(
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> EditionResponse:
    """
    Get current edition information.

    Returns information about the current edition, including
    available features and license status.
    """
    info = service.get_edition_info()
    return EditionResponse(**info)


@router.get("/features", response_model=list[str])
async def get_available_features(
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> list[str]:
    """
    Get list of features available in current edition.

    Returns a list of feature identifiers that are enabled
    for the current edition.
    """
    return service.get_available_features()


@router.post("/features/check", response_model=FeatureCheckResponse)
async def check_feature(
    request: FeatureCheckRequest,
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> FeatureCheckResponse:
    """
    Check if a specific feature is available.

    Returns whether the specified feature is available in
    the current edition, and whether an upgrade is needed.
    """
    edition = service.get_edition()
    available = service.has_feature(request.feature)

    # Check which edition has this feature
    from src.services.edition_service import EDITION_FEATURES

    requires_upgrade = False
    if not available:
        for ed in [Edition.ENTERPRISE, Edition.ENTERPRISE_PLUS]:
            if request.feature in EDITION_FEATURES.get(ed, []):
                requires_upgrade = True
                break

    return FeatureCheckResponse(
        feature=request.feature,
        available=available,
        edition=edition.value,
        requires_upgrade=requires_upgrade,
    )


@router.get("/license", response_model=LicenseResponse | None)
async def get_license(
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> LicenseResponse | None:
    """
    Get current license information.

    Returns the current license details if a license is registered,
    or null if running without a license (Community edition).
    """
    license_info = service.get_license_info()
    if license_info is None:
        return None
    return LicenseResponse(**license_info.to_dict())


@router.post("/license/validate", response_model=LicenseResponse)
async def validate_license(
    request: LicenseValidateRequest,
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> LicenseResponse:
    """
    Validate and register a license key.

    Validates the provided license key and, if valid, registers it
    as the current license. Returns the license details.
    """
    license_info = service.validate_license(request.license_key)

    if not license_info.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=license_info.validation_error or "Invalid license key",
        )

    return LicenseResponse(**license_info.to_dict())


@router.delete("/license")
async def clear_license(
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> dict[str, str]:
    """
    Clear the current license.

    Removes the current license registration, reverting to
    Community edition features.
    """
    service.clear_license()
    return {"status": "success", "message": "License cleared"}


@router.get("/upgrade-info")
async def get_upgrade_info(
    service: EditionService = Depends(get_edition_service),  # noqa: B008
) -> dict[str, Any]:
    """
    Get information about available upgrades.

    Returns details about what features would be available
    with higher edition tiers.
    """
    from src.services.edition_service import EDITION_FEATURES

    current_edition = service.get_edition()
    current_features = set(service.get_available_features())

    upgrade_info = {
        "current_edition": current_edition.value,
        "available_upgrades": [],
    }

    # Show upgrade options
    if current_edition == Edition.COMMUNITY:
        enterprise_features = set(EDITION_FEATURES[Edition.ENTERPRISE])
        new_features = enterprise_features - current_features
        upgrade_info["available_upgrades"].append(
            {
                "edition": "enterprise",
                "new_features": sorted(new_features),
                "feature_count": len(new_features),
                "support_tier": "standard",
            }
        )

        enterprise_plus_features = set(EDITION_FEATURES[Edition.ENTERPRISE_PLUS])
        new_features = enterprise_plus_features - current_features
        upgrade_info["available_upgrades"].append(
            {
                "edition": "enterprise_plus",
                "new_features": sorted(new_features),
                "feature_count": len(new_features),
                "support_tier": "premium",
            }
        )

    elif current_edition == Edition.ENTERPRISE:
        enterprise_plus_features = set(EDITION_FEATURES[Edition.ENTERPRISE_PLUS])
        new_features = enterprise_plus_features - current_features
        upgrade_info["available_upgrades"].append(
            {
                "edition": "enterprise_plus",
                "new_features": sorted(new_features),
                "feature_count": len(new_features),
                "support_tier": "premium",
            }
        )

    return upgrade_info
