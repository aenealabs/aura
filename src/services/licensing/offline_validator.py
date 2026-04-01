"""
Offline License Validator for Air-Gapped Deployments.

Provides cryptographic license validation without network connectivity.
Uses Ed25519 signatures and hardware fingerprinting.
"""

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.services.licensing.hardware_fingerprint import generate_hardware_fingerprint
from src.services.licensing.license_service import (
    LicenseEdition,
    LicenseInfo,
    LicenseValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class OfflineLicenseData:
    """Raw offline license data before validation."""

    payload: dict
    signature: bytes
    payload_raw: str


class OfflineLicenseValidator:
    """
    Validates offline licenses using Ed25519 cryptographic signatures.

    Offline licenses are structured as:
    base64url(json_payload).base64url(ed25519_signature)

    The payload contains:
    - license_id: Unique license identifier
    - edition: License tier (community/enterprise/enterprise_plus)
    - organization: Licensed organization name
    - issued_at: ISO timestamp of license issuance
    - expires_at: ISO timestamp of license expiration
    - hardware_id: SHA-256 hash of hardware fingerprint (optional)
    - features: List of enabled features
    - max_users: Maximum allowed users (0 = unlimited)
    - max_repositories: Maximum allowed repositories (0 = unlimited)
    """

    # Aenea Labs Ed25519 public key for license verification
    # Base64-encoded 32-byte public key
    DEFAULT_PUBLIC_KEY = os.getenv(
        "AURA_LICENSE_PUBLIC_KEY",
        # Development key - replace with production key
        "11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo=",
    )

    def __init__(
        self,
        public_key_b64: Optional[str] = None,
        allow_hardware_mismatch: bool = False,
        grace_period_days: int = 7,
    ):
        """
        Initialize offline validator.

        Args:
            public_key_b64: Base64-encoded Ed25519 public key
            allow_hardware_mismatch: Skip hardware verification (testing only)
            grace_period_days: Days after expiry to allow (grace period)
        """
        self._public_key_b64 = public_key_b64 or self.DEFAULT_PUBLIC_KEY
        self._allow_hardware_mismatch = allow_hardware_mismatch
        self._grace_period_days = grace_period_days
        self._public_key = None  # Lazy loaded

    def validate(self, license_key: str) -> LicenseInfo:
        """
        Validate an offline license key.

        Args:
            license_key: License key string (payload.signature format)

        Returns:
            Validated LicenseInfo

        Raises:
            LicenseValidationError: If validation fails
        """
        # Parse license key
        license_data = self._parse_license_key(license_key)

        # Verify cryptographic signature
        self._verify_signature(license_data)

        # Create license info from payload
        license_info = self._create_license_info(license_data.payload)

        # Verify hardware fingerprint
        if not self._allow_hardware_mismatch:
            self._verify_hardware(license_info)

        # Check expiration (with grace period)
        self._verify_expiration(license_info)

        logger.info(
            "Offline license validated: %s (%s) - expires %s",
            license_info.organization,
            license_info.edition.value,
            license_info.expires_at.date(),
        )

        return license_info

    def _parse_license_key(self, license_key: str) -> OfflineLicenseData:
        """Parse license key into components."""
        try:
            parts = license_key.strip().split(".")

            if len(parts) != 2:
                raise LicenseValidationError(
                    "Invalid license format: expected 'payload.signature'",
                    code="INVALID_FORMAT",
                )

            payload_b64, signature_b64 = parts

            # Decode payload
            payload_json = self._b64_decode(payload_b64)
            payload = json.loads(payload_json)

            # Decode signature
            signature = self._b64_decode(signature_b64, as_bytes=True)

            return OfflineLicenseData(
                payload=payload,
                signature=signature,
                payload_raw=payload_b64,
            )

        except json.JSONDecodeError as e:
            raise LicenseValidationError(
                f"Invalid license payload JSON: {e}",
                code="INVALID_PAYLOAD",
            )
        except Exception as e:
            if isinstance(e, LicenseValidationError):
                raise
            raise LicenseValidationError(
                f"Failed to parse license key: {e}",
                code="PARSE_ERROR",
            )

    def _b64_decode(self, data: str, as_bytes: bool = False) -> str | bytes:
        """Decode base64url data with padding handling."""
        # Add padding if needed
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding

        decoded = base64.urlsafe_b64decode(data)
        return decoded if as_bytes else decoded.decode("utf-8")

    def _get_public_key(self):
        """Get Ed25519 public key, loading lazily."""
        if self._public_key is not None:
            return self._public_key

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            key_bytes = base64.b64decode(self._public_key_b64)

            if len(key_bytes) == 32:
                # Raw 32-byte key
                self._public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
            else:
                # DER-encoded key
                from cryptography.hazmat.primitives import serialization

                self._public_key = serialization.load_der_public_key(key_bytes)

            return self._public_key

        except ImportError:
            raise LicenseValidationError(
                "cryptography library required for offline validation",
                code="MISSING_DEPENDENCY",
            )
        except Exception as e:
            raise LicenseValidationError(
                f"Failed to load public key: {e}",
                code="INVALID_PUBLIC_KEY",
            )

    def _verify_signature(self, license_data: OfflineLicenseData) -> None:
        """Verify Ed25519 signature."""
        try:
            public_key = self._get_public_key()
            message = license_data.payload_raw.encode("utf-8")
            public_key.verify(license_data.signature, message)

        except LicenseValidationError:
            raise
        except Exception as e:
            logger.warning("Signature verification failed: %s", e)
            raise LicenseValidationError(
                "License signature verification failed",
                code="INVALID_SIGNATURE",
            )

    def _create_license_info(self, payload: dict) -> LicenseInfo:
        """Create LicenseInfo from validated payload."""
        try:
            # Parse required fields
            license_id = payload.get("license_id") or payload.get("id")
            if not license_id:
                raise LicenseValidationError(
                    "License missing required field: license_id",
                    code="MISSING_FIELD",
                )

            edition_str = payload.get("edition", "community")
            try:
                edition = LicenseEdition(edition_str)
            except ValueError:
                raise LicenseValidationError(
                    f"Invalid license edition: {edition_str}",
                    code="INVALID_EDITION",
                )

            # Parse timestamps
            issued_at = self._parse_timestamp(payload.get("issued_at"))
            expires_at = self._parse_timestamp(payload.get("expires_at"))

            if not issued_at or not expires_at:
                raise LicenseValidationError(
                    "License missing required timestamps",
                    code="MISSING_TIMESTAMPS",
                )

            return LicenseInfo(
                license_id=license_id,
                edition=edition,
                organization=payload.get("organization", "Unknown"),
                issued_at=issued_at,
                expires_at=expires_at,
                max_users=payload.get("max_users", 0),
                max_repositories=payload.get("max_repositories", 0),
                features=payload.get("features", []),
                hardware_id=payload.get("hardware_id"),
                is_trial=payload.get("is_trial", False),
                is_offline=True,
            )

        except LicenseValidationError:
            raise
        except Exception as e:
            raise LicenseValidationError(
                f"Failed to parse license payload: {e}",
                code="PAYLOAD_ERROR",
            )

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            # ISO format
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass

        return None

    def _verify_hardware(self, license_info: LicenseInfo) -> None:
        """Verify hardware fingerprint matches license."""
        if not license_info.hardware_id:
            # No hardware binding
            logger.debug("License has no hardware binding")
            return

        current_fingerprint = generate_hardware_fingerprint()

        # Exact match
        if license_info.hardware_id == current_fingerprint:
            logger.debug("Hardware fingerprint matches exactly")
            return

        # Allow prefix match (first 32 chars = 16 bytes)
        if (
            len(license_info.hardware_id) >= 32
            and len(current_fingerprint) >= 32
            and license_info.hardware_id[:32] == current_fingerprint[:32]
        ):
            logger.info("Hardware fingerprint matched by prefix")
            return

        logger.warning(
            "Hardware mismatch: expected=%s..., current=%s...",
            license_info.hardware_id[:16],
            current_fingerprint[:16],
        )

        support_email = os.environ.get("SUPPORT_EMAIL", "support@aura.local")
        raise LicenseValidationError(
            f"License is not valid for this hardware. "
            f"Contact {support_email} for assistance.",
            code="HARDWARE_MISMATCH",
        )

    def _verify_expiration(self, license_info: LicenseInfo) -> None:
        """Verify license has not expired."""
        now = datetime.now(timezone.utc)

        if license_info.expires_at >= now:
            # Not expired
            return

        # Check grace period
        days_expired = (now - license_info.expires_at).days

        if days_expired <= self._grace_period_days:
            logger.warning(
                "License expired %d days ago (within %d day grace period)",
                days_expired,
                self._grace_period_days,
            )
            return

        renewal_url = os.environ.get(
            "LICENSE_RENEWAL_URL", "https://app.aura.local/renew"
        )
        raise LicenseValidationError(
            f"License expired on {license_info.expires_at.date()}. "
            f"Please renew your license at {renewal_url}",
            code="LICENSE_EXPIRED",
        )

    @staticmethod
    def generate_license_request() -> dict:
        """
        Generate a license request for offline activation.

        Returns:
            Dictionary containing hardware fingerprint and system info
            to send to Aenea Labs for offline license generation.
        """
        import platform

        from src.services.licensing.hardware_fingerprint import get_fingerprint_details

        details = get_fingerprint_details()

        return {
            "fingerprint": details["fingerprint_hash"],
            "system": {
                "platform": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
            },
            "request_time": datetime.now(timezone.utc).isoformat(),
        }


def create_test_license(
    organization: str = "Test Organization",
    edition: LicenseEdition = LicenseEdition.ENTERPRISE,
    days_valid: int = 365,
    hardware_id: Optional[str] = None,
    features: Optional[list[str]] = None,
) -> str:
    """
    Create a test license for development/testing.

    WARNING: This uses a test key and should NEVER be used in production.

    Args:
        organization: Organization name
        edition: License edition
        days_valid: Number of days until expiration
        hardware_id: Hardware fingerprint hash (optional)
        features: List of enabled features

    Returns:
        License key string
    """
    from datetime import timedelta

    # Test private key (Ed25519) - NEVER use in production
    # This matches the test public key in OfflineLicenseValidator
    TEST_PRIVATE_KEY_B64 = "nWGxgBgrq5Rv/agJhzQH+RJWZeD62n/DpPTH6XLDNE8="

    now = datetime.now(timezone.utc)

    payload = {
        "license_id": f"TEST-{hashlib.sha256(organization.encode()).hexdigest()[:8].upper()}",
        "edition": edition.value,
        "organization": organization,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=days_valid)).isoformat(),
        "max_users": 0,  # Unlimited
        "max_repositories": 0,  # Unlimited
        "features": features or [],
        "hardware_id": hardware_id,
        "is_trial": True,
    }

    # Encode payload
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

    # Sign with test key
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key_bytes = base64.b64decode(TEST_PRIVATE_KEY_B64)
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)

        signature = private_key.sign(payload_b64.encode())
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{payload_b64}.{signature_b64}"

    except ImportError:
        logger.warning("cryptography library not available for test license")
        return f"{payload_b64}.UNSIGNED"
