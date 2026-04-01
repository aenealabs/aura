"""
Project Aura - Edition Service

Provides edition detection and feature flag management for self-hosted deployments.
Maps the 5-tier SaaS model to 3-tier self-hosted editions.

See ADR-049: Self-Hosted Deployment Strategy
See docs/self-hosted/FEATURE_FLAG_EDITION_MAPPING.md

Editions:
- Community: Free tier with core features (Apache 2.0 licensed)
- Enterprise: Paid tier with advanced features
- Enterprise+: Premium tier with all features including GovCloud support
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Edition(Enum):
    """Self-hosted edition tiers."""

    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
    ENTERPRISE_PLUS = "enterprise_plus"


@dataclass
class LicenseInfo:
    """License information for self-hosted deployments."""

    license_key: str
    edition: Edition
    organization: str
    issued_at: datetime
    expires_at: datetime | None
    features: list[str] = field(default_factory=list)
    max_users: int | None = None
    max_repositories: int | None = None
    support_tier: str = "community"
    is_valid: bool = True
    validation_error: str | None = None

    def is_expired(self) -> bool:
        """Check if license is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "license_key": self._mask_key(self.license_key),
            "edition": self.edition.value,
            "organization": self.organization,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "features": self.features,
            "max_users": self.max_users,
            "max_repositories": self.max_repositories,
            "support_tier": self.support_tier,
            "is_valid": self.is_valid and not self.is_expired(),
            "is_expired": self.is_expired(),
            "validation_error": self.validation_error,
        }

    def _mask_key(self, key: str) -> str:
        """Mask license key for display."""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"


# Feature definitions for each edition
EDITION_FEATURES = {
    Edition.COMMUNITY: [
        "repository_onboarding",
        "code_search",
        "graphrag_basic",
        "security_scanning_basic",
        "chat_assistant",
        "dark_mode",
        "api_access",
    ],
    Edition.ENTERPRISE: [
        # All Community features
        "repository_onboarding",
        "code_search",
        "graphrag_basic",
        "security_scanning_basic",
        "chat_assistant",
        "dark_mode",
        "api_access",
        # Enterprise features
        "graphrag_advanced",
        "security_scanning_advanced",
        "autonomous_patching",
        "custom_agents",
        "sso_integration",
        "audit_logging",
        "priority_support",
        "model_router",
        "a2a_protocol",
        "sandbox_isolation",
        "team_management",
        "rbac",
        "ticketing_integrations",
        "ide_plugins",
    ],
    Edition.ENTERPRISE_PLUS: [
        # All Enterprise features
        "repository_onboarding",
        "code_search",
        "graphrag_basic",
        "graphrag_advanced",
        "security_scanning_basic",
        "security_scanning_advanced",
        "autonomous_patching",
        "custom_agents",
        "chat_assistant",
        "dark_mode",
        "api_access",
        "sso_integration",
        "audit_logging",
        "priority_support",
        "model_router",
        "a2a_protocol",
        "sandbox_isolation",
        "team_management",
        "rbac",
        "ticketing_integrations",
        "ide_plugins",
        # Enterprise+ exclusive features
        "govcloud_support",
        "cmmc_compliance",
        "air_gapped_deployment",
        "dedicated_support",
        "custom_training",
        "white_label",
        "multi_region",
        "disaster_recovery",
    ],
}


class EditionService:
    """
    Service for edition detection and license management.

    In self-hosted mode, edition is determined by:
    1. License key validation (if present)
    2. Environment variable AURA_EDITION
    3. Default to Community if neither present
    """

    def __init__(self):
        self._license_info: LicenseInfo | None = None
        self._edition: Edition | None = None

    def get_edition(self) -> Edition:
        """Get current edition."""
        if self._edition is not None:
            return self._edition

        # Check for license-based edition
        if self._license_info and self._license_info.is_valid:
            self._edition = self._license_info.edition
            return self._edition

        # Check environment variable
        edition_str = os.environ.get("AURA_EDITION", "community").lower()
        edition_map = {
            "community": Edition.COMMUNITY,
            "enterprise": Edition.ENTERPRISE,
            "enterprise_plus": Edition.ENTERPRISE_PLUS,
            "enterprise+": Edition.ENTERPRISE_PLUS,
        }
        self._edition = edition_map.get(edition_str, Edition.COMMUNITY)
        return self._edition

    def is_self_hosted(self) -> bool:
        """Check if running in self-hosted mode."""
        provider_str = os.environ.get("CLOUD_PROVIDER", "").lower()
        return provider_str == "self_hosted"

    def get_edition_info(self) -> dict[str, Any]:
        """Get current edition information."""
        edition = self.get_edition()
        return {
            "edition": edition.value,
            "is_self_hosted": self.is_self_hosted(),
            "features": EDITION_FEATURES.get(edition, []),
            "feature_count": len(EDITION_FEATURES.get(edition, [])),
            "license_required": edition != Edition.COMMUNITY,
            "has_valid_license": self._license_info is not None
            and self._license_info.is_valid,
        }

    def has_feature(self, feature: str) -> bool:
        """Check if current edition has a specific feature."""
        edition = self.get_edition()
        return feature in EDITION_FEATURES.get(edition, [])

    def get_available_features(self) -> list[str]:
        """Get list of features available in current edition."""
        edition = self.get_edition()
        return EDITION_FEATURES.get(edition, [])

    def get_license_info(self) -> LicenseInfo | None:
        """Get current license information."""
        return self._license_info

    def validate_license(self, license_key: str) -> LicenseInfo:
        """
        Validate a license key and extract license information.

        In production, this would call a license validation service.
        For now, we implement basic validation.
        """
        try:
            # Basic format validation
            if not license_key or len(license_key) < 20:
                return LicenseInfo(
                    license_key=license_key or "",
                    edition=Edition.COMMUNITY,
                    organization="",
                    issued_at=datetime.now(timezone.utc),
                    expires_at=None,
                    is_valid=False,
                    validation_error="Invalid license key format",
                )

            # Parse license key
            # Format: AURA-{edition}-{org_hash}-{signature}
            parts = license_key.split("-")
            if len(parts) < 4 or parts[0] != "AURA":
                return LicenseInfo(
                    license_key=license_key,
                    edition=Edition.COMMUNITY,
                    organization="",
                    issued_at=datetime.now(timezone.utc),
                    expires_at=None,
                    is_valid=False,
                    validation_error="Invalid license key prefix",
                )

            edition_code = parts[1].upper()
            edition_map = {
                "COM": Edition.COMMUNITY,
                "ENT": Edition.ENTERPRISE,
                "ENTP": Edition.ENTERPRISE_PLUS,
            }
            edition = edition_map.get(edition_code, Edition.COMMUNITY)

            # Create license info
            # In production, would verify cryptographic signature
            license_info = LicenseInfo(
                license_key=license_key,
                edition=edition,
                organization=parts[2] if len(parts) > 2 else "Unknown",
                issued_at=datetime.now(timezone.utc),
                expires_at=None,  # Would be extracted from signed payload
                features=EDITION_FEATURES.get(edition, []),
                max_users=None if edition == Edition.COMMUNITY else 1000,
                max_repositories=None if edition == Edition.COMMUNITY else 100,
                support_tier=(
                    "premium"
                    if edition == Edition.ENTERPRISE_PLUS
                    else "standard" if edition == Edition.ENTERPRISE else "community"
                ),
                is_valid=True,
            )

            self._license_info = license_info
            self._edition = edition
            logger.info(f"License validated: {edition.value} edition for {parts[2]}")
            return license_info

        except Exception as e:
            logger.error(f"License validation error: {e}")
            return LicenseInfo(
                license_key=license_key,
                edition=Edition.COMMUNITY,
                organization="",
                issued_at=datetime.now(timezone.utc),
                expires_at=None,
                is_valid=False,
                validation_error=str(e),
            )

    def clear_license(self) -> None:
        """Clear current license information."""
        self._license_info = None
        self._edition = None
        logger.info("License cleared")


# Singleton instance
_edition_service: EditionService | None = None


def get_edition_service() -> EditionService:
    """Get singleton EditionService instance."""
    global _edition_service
    if _edition_service is None:
        _edition_service = EditionService()
    return _edition_service
