"""
License Service for Project Aura.

Provides license validation, edition detection, and feature gating.
Supports both online and offline validation modes.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LicenseEdition(str, Enum):
    """License edition tiers."""

    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
    ENTERPRISE_PLUS = "enterprise_plus"


class LicenseValidationError(Exception):
    """Raised when license validation fails."""

    def __init__(self, message: str, code: str = "INVALID_LICENSE"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class LicenseInfo:
    """License information container."""

    license_id: str
    edition: LicenseEdition
    organization: str
    issued_at: datetime
    expires_at: datetime
    max_users: int = 0
    max_repositories: int = 0
    features: list[str] = field(default_factory=list)
    hardware_id: Optional[str] = None
    is_trial: bool = False
    is_offline: bool = False
    signature: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if license is currently valid (not expired)."""
        now = datetime.now(timezone.utc)
        return self.issued_at <= now <= self.expires_at

    @property
    def days_until_expiry(self) -> int:
        """Get days until license expires."""
        now = datetime.now(timezone.utc)
        delta = self.expires_at - now
        return max(0, delta.days)

    @property
    def is_expiring_soon(self) -> bool:
        """Check if license expires within 30 days."""
        return 0 < self.days_until_expiry <= 30

    def has_feature(self, feature: str) -> bool:
        """Check if license includes a specific feature."""
        if self.edition == LicenseEdition.ENTERPRISE_PLUS:
            return True  # Enterprise Plus has all features
        return feature in self.features

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "license_id": self.license_id,
            "edition": self.edition.value,
            "organization": self.organization,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "max_users": self.max_users,
            "max_repositories": self.max_repositories,
            "features": self.features,
            "hardware_id": self.hardware_id,
            "is_trial": self.is_trial,
            "is_offline": self.is_offline,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LicenseInfo":
        """Create from dictionary."""
        return cls(
            license_id=data["license_id"],
            edition=LicenseEdition(data["edition"]),
            organization=data["organization"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            max_users=data.get("max_users", 0),
            max_repositories=data.get("max_repositories", 0),
            features=data.get("features", []),
            hardware_id=data.get("hardware_id"),
            is_trial=data.get("is_trial", False),
            is_offline=data.get("is_offline", False),
            signature=data.get("signature"),
        )


# Feature definitions by edition
EDITION_FEATURES: dict[LicenseEdition, set[str]] = {
    LicenseEdition.COMMUNITY: {
        "graphrag_basic",
        "vulnerability_detection",
        "single_repo",
        "basic_agents",
        "api_access",
    },
    LicenseEdition.ENTERPRISE: {
        # All community features
        "graphrag_basic",
        "vulnerability_detection",
        "single_repo",
        "basic_agents",
        "api_access",
        # Enterprise additions
        "graphrag_advanced",
        "multi_repo",
        "custom_agents",
        "sso_saml",
        "audit_logging",
        "priority_support",
        "sla_99_9",
        "api_rate_limit_high",
    },
    LicenseEdition.ENTERPRISE_PLUS: {
        # All enterprise features plus
        "graphrag_basic",
        "vulnerability_detection",
        "single_repo",
        "basic_agents",
        "api_access",
        "graphrag_advanced",
        "multi_repo",
        "custom_agents",
        "sso_saml",
        "audit_logging",
        "priority_support",
        "sla_99_9",
        "api_rate_limit_high",
        # Enterprise Plus additions
        "air_gap_deployment",
        "fips_compliance",
        "custom_llm_integration",
        "multi_tenant",
        "compliance_reporting",
        "dedicated_support",
        "sla_99_99",
        "unlimited_repos",
        "unlimited_users",
    },
}


class LicenseService:
    """
    License management service.

    Handles license validation, caching, and feature checks.
    Supports both online validation via API and offline validation
    using Ed25519 signatures and hardware fingerprinting.
    """

    # Aenea Labs public key for license verification (Ed25519)
    # In production, this would be the actual public key
    PUBLIC_KEY_B64 = os.getenv(
        "AURA_LICENSE_PUBLIC_KEY",
        # Default test key - replace with production key
        "MCowBQYDK2VwAyEAYmxhY2tib3ggdGVzdCBrZXkgZm9yIGRldmVsb3BtZW50",
    )

    def __init__(
        self,
        license_key: Optional[str] = None,
        offline_mode: bool = False,
        hardware_id: Optional[str] = None,
    ):
        """
        Initialize license service.

        Args:
            license_key: License key string (JWT-like format)
            offline_mode: Enable offline validation (no API calls)
            hardware_id: Hardware fingerprint for offline validation
        """
        self._license_key = license_key or os.getenv("AURA_LICENSE_KEY", "")
        self._offline_mode = (
            offline_mode or os.getenv("AURA_OFFLINE_LICENSE", "false").lower() == "true"
        )
        self._hardware_id = hardware_id
        self._cached_license: Optional[LicenseInfo] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 3600  # 1 hour cache

    @property
    def is_licensed(self) -> bool:
        """Check if valid license is present."""
        try:
            license_info = self.get_license_info()
            return license_info is not None and license_info.is_valid
        except LicenseValidationError:
            return False

    @property
    def edition(self) -> LicenseEdition:
        """Get current license edition."""
        try:
            license_info = self.get_license_info()
            if license_info:
                return license_info.edition
        except LicenseValidationError:
            pass
        return LicenseEdition.COMMUNITY

    def get_license_info(self) -> Optional[LicenseInfo]:
        """
        Get validated license information.

        Returns:
            LicenseInfo if valid license exists, None for community edition

        Raises:
            LicenseValidationError: If license is invalid or expired
        """
        # Check cache
        if self._is_cache_valid():
            return self._cached_license

        # No license key = community edition
        if not self._license_key:
            logger.info("No license key configured - using Community Edition")
            return None

        # Validate and cache
        license_info = self._validate_license()
        self._cached_license = license_info
        self._cache_time = datetime.now(timezone.utc)

        return license_info

    def has_feature(self, feature: str) -> bool:
        """
        Check if current license includes a feature.

        Args:
            feature: Feature identifier to check

        Returns:
            True if feature is available
        """
        edition = self.edition
        edition_features = EDITION_FEATURES.get(edition, set())
        return feature in edition_features

    def require_feature(self, feature: str) -> None:
        """
        Require a specific feature, raising if not available.

        Args:
            feature: Feature identifier to require

        Raises:
            LicenseValidationError: If feature is not available
        """
        if not self.has_feature(feature):
            raise LicenseValidationError(
                f"Feature '{feature}' requires an upgraded license. "
                f"Current edition: {self.edition.value}",
                code="FEATURE_NOT_LICENSED",
            )

    def require_edition(self, minimum_edition: LicenseEdition) -> None:
        """
        Require a minimum edition level.

        Args:
            minimum_edition: Minimum required edition

        Raises:
            LicenseValidationError: If current edition is insufficient
        """
        edition_order = [
            LicenseEdition.COMMUNITY,
            LicenseEdition.ENTERPRISE,
            LicenseEdition.ENTERPRISE_PLUS,
        ]
        current_idx = edition_order.index(self.edition)
        required_idx = edition_order.index(minimum_edition)

        if current_idx < required_idx:
            raise LicenseValidationError(
                f"This feature requires {minimum_edition.value} edition. "
                f"Current edition: {self.edition.value}",
                code="EDITION_REQUIRED",
            )

    def _is_cache_valid(self) -> bool:
        """Check if cached license is still valid."""
        if self._cached_license is None or self._cache_time is None:
            return False

        age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return age < self._cache_ttl_seconds

    def _validate_license(self) -> LicenseInfo:
        """
        Validate the license key.

        Returns:
            Validated LicenseInfo

        Raises:
            LicenseValidationError: If validation fails
        """
        if self._offline_mode:
            return self._validate_offline()
        return self._validate_online()

    def _validate_offline(self) -> LicenseInfo:
        """
        Validate license offline using Ed25519 signature.

        Returns:
            Validated LicenseInfo

        Raises:
            LicenseValidationError: If validation fails
        """
        try:
            # Parse license key (format: base64(json).base64(signature))
            parts = self._license_key.split(".")
            if len(parts) != 2:
                raise LicenseValidationError(
                    "Invalid license format", code="INVALID_FORMAT"
                )

            payload_b64, signature_b64 = parts

            # Decode payload
            try:
                payload_json = base64.urlsafe_b64decode(
                    payload_b64 + "=" * (4 - len(payload_b64) % 4)
                )
                payload = json.loads(payload_json)
            except (ValueError, json.JSONDecodeError) as e:
                raise LicenseValidationError(
                    f"Invalid license payload: {e}", code="INVALID_PAYLOAD"
                )

            # Verify signature
            if not self._verify_signature(payload_b64, signature_b64):
                raise LicenseValidationError(
                    "License signature verification failed", code="INVALID_SIGNATURE"
                )

            # Create license info
            license_info = LicenseInfo.from_dict(payload)
            license_info.is_offline = True
            license_info.signature = signature_b64

            # Verify hardware ID for offline licenses
            if license_info.hardware_id:
                if not self._hardware_id:
                    from src.services.licensing.hardware_fingerprint import (
                        generate_hardware_fingerprint,
                    )

                    self._hardware_id = generate_hardware_fingerprint()

                if not self._verify_hardware_id(
                    license_info.hardware_id, self._hardware_id
                ):
                    raise LicenseValidationError(
                        "License is not valid for this hardware",
                        code="HARDWARE_MISMATCH",
                    )

            # Check expiration
            if not license_info.is_valid:
                raise LicenseValidationError(
                    f"License expired on {license_info.expires_at.date()}",
                    code="LICENSE_EXPIRED",
                )

            logger.info(
                "Offline license validated: %s (%s)",
                license_info.organization,
                license_info.edition.value,
            )
            return license_info

        except LicenseValidationError:
            raise
        except Exception as e:
            logger.exception("License validation error")
            raise LicenseValidationError(
                f"License validation failed: {e}", code="VALIDATION_ERROR"
            )

    def _validate_online(self) -> LicenseInfo:
        """
        Validate license online via API.

        Returns:
            Validated LicenseInfo

        Raises:
            LicenseValidationError: If validation fails
        """
        # For now, fall back to offline validation
        # In production, this would call the license server API
        logger.debug("Online validation not configured, using offline validation")
        return self._validate_offline()

    def _verify_signature(self, payload_b64: str, signature_b64: str) -> bool:
        """
        Verify Ed25519 signature.

        Args:
            payload_b64: Base64-encoded payload
            signature_b64: Base64-encoded signature

        Returns:
            True if signature is valid
        """
        try:
            # Import cryptography library
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            # Decode public key
            public_key_bytes = base64.b64decode(self.PUBLIC_KEY_B64)

            # Handle both raw and DER-encoded keys
            if len(public_key_bytes) == 32:
                # Raw 32-byte key
                public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            else:
                # DER-encoded key
                public_key = serialization.load_der_public_key(public_key_bytes)

            # Decode signature
            signature = base64.urlsafe_b64decode(
                signature_b64 + "=" * (4 - len(signature_b64) % 4)
            )

            # Verify
            public_key.verify(signature, payload_b64.encode())
            return True

        except ImportError:
            logger.warning(
                "cryptography library not available, signature verification skipped"
            )
            # In production, this should fail
            # For development, allow skipping verification
            return os.getenv("AURA_SKIP_LICENSE_SIGNATURE", "false").lower() == "true"
        except Exception as e:
            logger.warning("Signature verification failed: %s", e)
            return False

    def _verify_hardware_id(self, licensed_id: str, current_id: str) -> bool:
        """
        Verify hardware ID matches license.

        Uses a fuzzy match to allow for minor hardware changes.

        Args:
            licensed_id: Hardware ID in license
            current_id: Current hardware fingerprint

        Returns:
            True if hardware matches
        """
        # Exact match
        if licensed_id == current_id:
            return True

        # Allow hash prefix match (first 16 chars) for flexibility
        if len(licensed_id) >= 16 and len(current_id) >= 16:
            if licensed_id[:16] == current_id[:16]:
                logger.info("Hardware ID matched by prefix")
                return True

        return False

    def get_status(self) -> dict[str, Any]:
        """
        Get license status summary.

        Returns:
            Dictionary with license status information
        """
        try:
            license_info = self.get_license_info()
            if license_info:
                return {
                    "licensed": True,
                    "edition": license_info.edition.value,
                    "organization": license_info.organization,
                    "expires_at": license_info.expires_at.isoformat(),
                    "days_until_expiry": license_info.days_until_expiry,
                    "is_expiring_soon": license_info.is_expiring_soon,
                    "is_trial": license_info.is_trial,
                    "is_offline": license_info.is_offline,
                    "max_users": license_info.max_users,
                    "max_repositories": license_info.max_repositories,
                }
            return {
                "licensed": False,
                "edition": LicenseEdition.COMMUNITY.value,
                "organization": None,
                "expires_at": None,
            }
        except LicenseValidationError as e:
            return {
                "licensed": False,
                "edition": LicenseEdition.COMMUNITY.value,
                "error": e.message,
                "error_code": e.code,
            }


# Global license service instance
_license_service: Optional[LicenseService] = None


def get_license_service() -> LicenseService:
    """Get the global license service instance."""
    global _license_service
    if _license_service is None:
        _license_service = LicenseService()
    return _license_service


def set_license_service(service: LicenseService) -> None:
    """Set the global license service instance (for testing)."""
    global _license_service
    _license_service = service
