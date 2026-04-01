"""
Project Aura Licensing Module.

Provides enterprise license validation with support for:
- Online validation via license server
- Offline validation with hardware fingerprinting
- Ed25519 cryptographic signatures
- Edition-based feature gating
"""

from src.services.licensing.hardware_fingerprint import (
    HardwareFingerprint,
    generate_hardware_fingerprint,
)
from src.services.licensing.license_service import (
    LicenseEdition,
    LicenseInfo,
    LicenseService,
    LicenseValidationError,
)
from src.services.licensing.offline_validator import OfflineLicenseValidator

__all__ = [
    "LicenseEdition",
    "LicenseInfo",
    "LicenseService",
    "LicenseValidationError",
    "HardwareFingerprint",
    "generate_hardware_fingerprint",
    "OfflineLicenseValidator",
]
