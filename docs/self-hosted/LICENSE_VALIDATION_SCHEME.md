# Ed25519 License Validation Scheme

**Status:** Decided
**Date:** 2026-01-03
**Decision Makers:** Platform Architecture Team
**Context:** ADR-049 Phase 0 Prerequisite

---

## Executive Summary

This document defines the cryptographic license validation scheme for Project Aura self-hosted deployments using Ed25519 digital signatures. The scheme enables:

- **Offline validation** without network connectivity (air-gapped environments)
- **Hardware fingerprinting** for node-locked licenses
- **Feature gating** based on edition (Community/Enterprise)
- **Tamper detection** via cryptographic signatures
- **Expiration enforcement** with grace periods

---

## Cryptographic Foundation

### Why Ed25519?

| Property | Ed25519 | RSA-2048 | ECDSA P-256 |
|----------|---------|----------|-------------|
| Key Size | 32 bytes | 256 bytes | 32 bytes |
| Signature Size | 64 bytes | 256 bytes | 64 bytes |
| Verification Speed | ~15,000/sec | ~3,000/sec | ~8,000/sec |
| FIPS Approved | Yes (186-5) | Yes | Yes |
| Deterministic | Yes | No | No |
| Side-channel Resistant | Yes | Varies | Varies |

**Ed25519 Advantages:**
1. Small signatures (64 bytes) embedded in license file
2. Fast verification for startup performance
3. FIPS 186-5 approved (August 2023) for government compliance
4. Deterministic - same message always produces same signature
5. No padding or nonce management complexity

### Key Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    AENEA LABS LICENSE SERVER                     │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  SIGNING PRIVATE KEY                      │  │
│   │   Ed25519 Private Key (32 bytes)                         │  │
│   │   - HSM-protected (AWS KMS, Azure Key Vault, HashiCorp)  │  │
│   │   - Never leaves HSM boundary                            │  │
│   │   - Backup in secure offline storage                     │  │
│   └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         │ Signs license payload                                  │
│         ▼                                                        │
│   ┌──────────────────┐                                          │
│   │  License File    │────────────────────────────────────────► │
│   │  (Signed)        │         Delivered to customer            │
│   └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER DEPLOYMENT                           │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  VERIFICATION PUBLIC KEY                  │  │
│   │   Ed25519 Public Key (32 bytes)                          │  │
│   │   - Embedded in Aura binary at compile time              │  │
│   │   - Read-only, cannot sign new licenses                  │  │
│   │   - Multiple keys supported (key rotation)               │  │
│   └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         │ Verifies signature                                     │
│         ▼                                                        │
│   ┌──────────────────┐                                          │
│   │  License Valid?  │──► Feature flags enabled                 │
│   └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## License File Format

### Structure

The license file uses a two-part structure: JSON payload + Ed25519 signature, base64-encoded together.

```
┌─────────────────────────────────────────────────────────────────┐
│                        LICENSE FILE                              │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                    BASE64 ENVELOPE                        │  │
│   │                                                           │  │
│   │   ┌─────────────────────────────────────────────────────┐│  │
│   │   │              JSON PAYLOAD (variable)                ││  │
│   │   │   {                                                 ││  │
│   │   │     "license_id": "...",                           ││  │
│   │   │     "customer_id": "...",                          ││  │
│   │   │     "edition": "enterprise",                       ││  │
│   │   │     "features": [...],                             ││  │
│   │   │     "limits": {...},                               ││  │
│   │   │     "hardware_id": "...",                          ││  │
│   │   │     "issued_at": "...",                            ││  │
│   │   │     "expires_at": "..."                            ││  │
│   │   │   }                                                 ││  │
│   │   └─────────────────────────────────────────────────────┘│  │
│   │                            +                              │  │
│   │   ┌─────────────────────────────────────────────────────┐│  │
│   │   │           ED25519 SIGNATURE (64 bytes)              ││  │
│   │   │   Sign(private_key, canonical_json(payload))        ││  │
│   │   └─────────────────────────────────────────────────────┘│  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### License Payload Schema

```json
{
  "$schema": "https://aenealabs.com/schemas/license-v1.json",
  "version": 1,
  "license_id": "lic_01HQXYZ123456789ABCDEF",
  "customer_id": "cust_01HQABC987654321FEDCBA",
  "customer_name": "Acme Corporation",

  "edition": "enterprise",
  "tier": "standard",

  "features": [
    "graphrag",
    "multi_agent",
    "security_scanning",
    "hitl_approval",
    "sso_saml",
    "audit_logging",
    "custom_models",
    "priority_support"
  ],

  "limits": {
    "max_repositories": 100,
    "max_users": 500,
    "max_agents": 50,
    "max_nodes": 10,
    "retention_days": 365
  },

  "hardware_id": "hw_sha256_a1b2c3d4e5f6...",
  "hardware_id_type": "composite",

  "issued_at": "2026-01-03T00:00:00Z",
  "expires_at": "2027-01-03T23:59:59Z",
  "grace_period_days": 14,

  "issuer": "Aenea Labs License Authority",
  "issuer_key_id": "key_prod_2026_001"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | int | Yes | Schema version for forward compatibility |
| `license_id` | string | Yes | Unique license identifier (ULID format) |
| `customer_id` | string | Yes | Customer account identifier |
| `customer_name` | string | Yes | Human-readable customer name (for logs) |
| `edition` | enum | Yes | `community`, `enterprise`, `enterprise_plus` |
| `tier` | enum | No | `standard`, `premium`, `unlimited` (Enterprise only) |
| `features` | array | Yes | Enabled feature flags |
| `limits` | object | Yes | Numeric limits for resources |
| `hardware_id` | string | No | Hardware fingerprint (null = floating license) |
| `hardware_id_type` | enum | No | `composite`, `machine_id`, `mac_address`, `tpm` |
| `issued_at` | datetime | Yes | License issue timestamp (ISO 8601) |
| `expires_at` | datetime | Yes | License expiration (ISO 8601) |
| `grace_period_days` | int | Yes | Days after expiration before hard cutoff |
| `issuer` | string | Yes | Signing authority name |
| `issuer_key_id` | string | Yes | Public key ID for key rotation |

---

## Edition Feature Matrix

### Feature Flags by Edition

| Feature | Community | Enterprise | Enterprise+ |
|---------|-----------|------------|-------------|
| `graphrag` | ✅ | ✅ | ✅ |
| `multi_agent` | ✅ (3 agents) | ✅ (50 agents) | ✅ (unlimited) |
| `security_scanning` | ✅ (basic) | ✅ (full) | ✅ (full) |
| `hitl_approval` | ❌ | ✅ | ✅ |
| `sso_saml` | ❌ | ✅ | ✅ |
| `sso_oidc` | ❌ | ✅ | ✅ |
| `audit_logging` | ❌ | ✅ | ✅ |
| `custom_models` | ❌ | ✅ | ✅ |
| `priority_support` | ❌ | ✅ | ✅ |
| `24x7_support` | ❌ | ❌ | ✅ |
| `dedicated_tam` | ❌ | ❌ | ✅ |
| `ha_clustering` | ❌ | ✅ | ✅ |
| `disaster_recovery` | ❌ | ❌ | ✅ |
| `compliance_reports` | ❌ | ✅ | ✅ |
| `air_gap_deployment` | ❌ | ❌ | ✅ |

### Default Limits by Edition

```json
{
  "community": {
    "max_repositories": 5,
    "max_users": 10,
    "max_agents": 3,
    "max_nodes": 1,
    "retention_days": 30
  },
  "enterprise": {
    "max_repositories": 100,
    "max_users": 500,
    "max_agents": 50,
    "max_nodes": 10,
    "retention_days": 365
  },
  "enterprise_plus": {
    "max_repositories": -1,
    "max_users": -1,
    "max_agents": -1,
    "max_nodes": -1,
    "retention_days": -1
  }
}
```

Note: `-1` indicates unlimited.

---

## Hardware Fingerprinting

### Fingerprint Generation

Hardware fingerprinting creates a stable identifier for node-locked licenses. The fingerprint must be:
1. **Stable** - Survives reboots and minor hardware changes
2. **Unique** - Distinguishes between different machines
3. **Non-transferable** - Cannot be easily spoofed on another machine

### Composite Hardware ID (Recommended)

The composite approach combines multiple hardware identifiers with weighted scoring:

```python
# src/licensing/hardware_fingerprint.py

import hashlib
import platform
import subprocess
from typing import Optional

class HardwareFingerprint:
    """Generate stable hardware fingerprint for license validation."""

    COMPONENTS = [
        ("machine_id", 30),    # /etc/machine-id or equivalent
        ("cpu_id", 25),        # CPU serial/model
        ("motherboard", 20),   # SMBIOS motherboard serial
        ("disk_serial", 15),   # Primary disk serial
        ("mac_address", 10),   # Primary NIC MAC
    ]

    MATCH_THRESHOLD = 60  # Minimum score to consider valid

    def generate(self) -> str:
        """Generate composite hardware fingerprint."""
        components = {
            "machine_id": self._get_machine_id(),
            "cpu_id": self._get_cpu_id(),
            "motherboard": self._get_motherboard_serial(),
            "disk_serial": self._get_disk_serial(),
            "mac_address": self._get_primary_mac(),
        }

        # Create deterministic hash of components
        fingerprint_data = "|".join(
            f"{k}:{v}" for k, v in sorted(components.items()) if v
        )

        return "hw_" + hashlib.sha256(
            fingerprint_data.encode()
        ).hexdigest()[:32]

    def validate(
        self,
        stored_fingerprint: str,
        current_fingerprint: str
    ) -> tuple[bool, int]:
        """
        Validate hardware fingerprint with tolerance for minor changes.

        Returns:
            (is_valid, match_score)
        """
        if stored_fingerprint == current_fingerprint:
            return (True, 100)

        # Partial match scoring
        score = 0
        for component, weight in self.COMPONENTS:
            stored_val = self._extract_component(stored_fingerprint, component)
            current_val = self._extract_component(current_fingerprint, component)
            if stored_val and stored_val == current_val:
                score += weight

        return (score >= self.MATCH_THRESHOLD, score)

    def _get_machine_id(self) -> Optional[str]:
        """Get OS-assigned machine identifier."""
        if platform.system() == "Linux":
            try:
                with open("/etc/machine-id", "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
        elif platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True
                )
                for line in result.stdout.split("\n"):
                    if "IOPlatformUUID" in line:
                        return line.split('"')[-2]
            except Exception:
                pass
        elif platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "UUID"],
                    capture_output=True, text=True
                )
                return result.stdout.split("\n")[1].strip()
            except Exception:
                pass
        return None

    def _get_cpu_id(self) -> Optional[str]:
        """Get CPU identifier."""
        if platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            except Exception:
                pass
        return platform.processor() or None

    def _get_motherboard_serial(self) -> Optional[str]:
        """Get motherboard serial from SMBIOS."""
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["dmidecode", "-s", "baseboard-serial-number"],
                    capture_output=True, text=True
                )
                serial = result.stdout.strip()
                if serial and serial != "Not Specified":
                    return serial
            except Exception:
                pass
        return None

    def _get_disk_serial(self) -> Optional[str]:
        """Get primary disk serial number."""
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["lsblk", "-no", "SERIAL", "/dev/sda"],
                    capture_output=True, text=True
                )
                return result.stdout.strip() or None
            except Exception:
                pass
        return None

    def _get_primary_mac(self) -> Optional[str]:
        """Get primary network interface MAC address."""
        import uuid
        return hex(uuid.getnode())[2:]
```

### Hardware ID Types

| Type | Description | Stability | Security |
|------|-------------|-----------|----------|
| `composite` | Weighted hash of multiple components | High | High |
| `machine_id` | OS-assigned machine identifier | High | Medium |
| `mac_address` | Primary NIC MAC (not recommended alone) | Low | Low |
| `tpm` | TPM 2.0 endorsement key | Very High | Very High |

### Kubernetes/Container Considerations

For containerized deployments, hardware fingerprinting is problematic because containers are ephemeral. Solutions:

1. **Node-locked license** - Fingerprint the Kubernetes node, not the pod
2. **Floating license** - No hardware binding (`hardware_id: null`)
3. **Cluster license** - License bound to Kubernetes cluster UID

```yaml
# Kubernetes cluster UID as hardware ID
kind: ConfigMap
metadata:
  name: aura-license
data:
  hardware_id_type: "kubernetes_cluster"
  # Cluster UID from: kubectl get namespace kube-system -o jsonpath='{.metadata.uid}'
  hardware_id: "hw_k8s_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

---

## Validation Flow

### Startup Validation Sequence

```
┌─────────────────────────────────────────────────────────────────┐
│                      AURA STARTUP SEQUENCE                       │
│                                                                  │
│   1. Load license file                                          │
│      └── /etc/aura/license.key or AURA_LICENSE env var          │
│                          │                                       │
│                          ▼                                       │
│   2. Decode base64 envelope                                     │
│      └── Extract JSON payload + signature                       │
│                          │                                       │
│                          ▼                                       │
│   3. Verify Ed25519 signature                                   │
│      └── Using embedded public key (key_id from payload)        │
│                          │                                       │
│              ┌───────────┴───────────┐                          │
│              │                       │                          │
│         VALID ✅                INVALID ❌                       │
│              │                       │                          │
│              ▼                       ▼                          │
│   4. Check expiration           Log error                       │
│      └── expires_at +           Exit with code 78               │
│          grace_period           (EX_CONFIG)                     │
│                          │                                       │
│              ┌───────────┴───────────┐                          │
│              │                       │                          │
│         NOT EXPIRED             EXPIRED                          │
│              │                       │                          │
│              ▼                       ▼                          │
│   5. Verify hardware ID         Within grace?                   │
│      └── Generate current           │                           │
│          fingerprint         ┌──────┴──────┐                    │
│                              │             │                    │
│                          YES (grace)   NO (hard)                │
│                              │             │                    │
│                              ▼             ▼                    │
│                         Warn + run     Exit with                │
│                         (degraded)     code 78                  │
│                          │                                       │
│              ┌───────────┴───────────┐                          │
│              │                       │                          │
│         MATCH ✅              MISMATCH ❌                        │
│              │                       │                          │
│              ▼                       ▼                          │
│   6. Load feature flags         Log error                       │
│      └── Enable features        Exit with code 78               │
│          per license                                            │
│                          │                                       │
│                          ▼                                       │
│   7. Initialize services                                        │
│      └── Enforce limits                                         │
│          from license                                           │
│                          │                                       │
│                          ▼                                       │
│            APPLICATION RUNNING                                  │
│            (Features enabled per license)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Runtime Enforcement

After startup validation, licenses are re-verified:

| Check | Frequency | Action on Failure |
|-------|-----------|-------------------|
| Expiration | Every 24 hours | Degrade to Community after grace |
| Hardware ID | On config change | Shutdown if mismatch |
| Feature access | Per request | Deny access, log attempt |
| Limit enforcement | Per operation | Deny operation, return 429 |

---

## Implementation

### License Verification Service

```python
# src/licensing/license_service.py

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import base64
import json
import os

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from .hardware_fingerprint import HardwareFingerprint


class LicenseStatus(Enum):
    VALID = "valid"
    EXPIRED = "expired"
    GRACE_PERIOD = "grace_period"
    INVALID_SIGNATURE = "invalid_signature"
    HARDWARE_MISMATCH = "hardware_mismatch"
    NOT_FOUND = "not_found"


@dataclass
class LicenseInfo:
    """Parsed and validated license information."""
    status: LicenseStatus
    license_id: str
    customer_name: str
    edition: str
    features: list[str]
    limits: dict[str, int]
    expires_at: datetime
    days_remaining: int
    hardware_match_score: int

    @property
    def is_valid(self) -> bool:
        return self.status in (LicenseStatus.VALID, LicenseStatus.GRACE_PERIOD)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def check_limit(self, limit_name: str, current_value: int) -> bool:
        max_value = self.limits.get(limit_name, 0)
        if max_value == -1:  # Unlimited
            return True
        return current_value < max_value


class LicenseService:
    """Ed25519 license validation service."""

    # Embedded public keys (compiled into binary)
    # Format: {key_id: base64_encoded_public_key}
    PUBLIC_KEYS = {
        "key_prod_2026_001": "MCowBQYDK2VwAyEA...",  # Production key
        "key_dev_2026_001": "MCowBQYDK2VwAyEA...",   # Development key
    }

    SIGNATURE_LENGTH = 64  # Ed25519 signature is always 64 bytes

    def __init__(self, license_path: Optional[str] = None):
        self.license_path = license_path or self._default_license_path()
        self.hardware_fingerprint = HardwareFingerprint()
        self._cached_license: Optional[LicenseInfo] = None

    def _default_license_path(self) -> str:
        """Determine license file location."""
        # Priority: env var > standard paths
        if os.environ.get("AURA_LICENSE"):
            return os.environ["AURA_LICENSE"]

        paths = [
            "/etc/aura/license.key",
            "/opt/aura/license.key",
            Path.home() / ".aura" / "license.key",
        ]
        for p in paths:
            if Path(p).exists():
                return str(p)

        return str(paths[0])  # Default location

    def validate(self) -> LicenseInfo:
        """Validate license file and return license information."""
        # Check cache
        if self._cached_license and self._cached_license.is_valid:
            return self._cached_license

        # Load license file
        try:
            license_data = self._load_license_file()
        except FileNotFoundError:
            return self._community_fallback(LicenseStatus.NOT_FOUND)

        # Decode and split payload/signature
        try:
            decoded = base64.b64decode(license_data)
            signature = decoded[-self.SIGNATURE_LENGTH:]
            payload_bytes = decoded[:-self.SIGNATURE_LENGTH]
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as e:
            return self._community_fallback(LicenseStatus.INVALID_SIGNATURE)

        # Verify signature
        key_id = payload.get("issuer_key_id", "")
        if key_id not in self.PUBLIC_KEYS:
            return self._community_fallback(LicenseStatus.INVALID_SIGNATURE)

        try:
            public_key_bytes = base64.b64decode(self.PUBLIC_KEYS[key_id])
            verify_key = VerifyKey(public_key_bytes)
            verify_key.verify(payload_bytes, signature)
        except BadSignatureError:
            return self._community_fallback(LicenseStatus.INVALID_SIGNATURE)

        # Check expiration
        expires_at = datetime.fromisoformat(
            payload["expires_at"].replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        days_remaining = (expires_at - now).days
        grace_days = payload.get("grace_period_days", 14)

        if days_remaining < -grace_days:
            return self._community_fallback(LicenseStatus.EXPIRED)

        status = LicenseStatus.VALID
        if days_remaining < 0:
            status = LicenseStatus.GRACE_PERIOD

        # Verify hardware ID (if specified)
        hardware_match_score = 100
        stored_hw_id = payload.get("hardware_id")
        if stored_hw_id:
            current_hw_id = self.hardware_fingerprint.generate()
            is_valid, hardware_match_score = self.hardware_fingerprint.validate(
                stored_hw_id, current_hw_id
            )
            if not is_valid:
                return self._community_fallback(LicenseStatus.HARDWARE_MISMATCH)

        # Build license info
        license_info = LicenseInfo(
            status=status,
            license_id=payload["license_id"],
            customer_name=payload["customer_name"],
            edition=payload["edition"],
            features=payload.get("features", []),
            limits=payload.get("limits", {}),
            expires_at=expires_at,
            days_remaining=max(days_remaining, 0),
            hardware_match_score=hardware_match_score,
        )

        self._cached_license = license_info
        return license_info

    def _load_license_file(self) -> str:
        """Load license from file or environment."""
        if os.environ.get("AURA_LICENSE_KEY"):
            return os.environ["AURA_LICENSE_KEY"]

        with open(self.license_path, "r") as f:
            return f.read().strip()

    def _community_fallback(self, status: LicenseStatus) -> LicenseInfo:
        """Return Community edition license on validation failure."""
        return LicenseInfo(
            status=status,
            license_id="community",
            customer_name="Community User",
            edition="community",
            features=["graphrag", "multi_agent", "security_scanning"],
            limits={
                "max_repositories": 5,
                "max_users": 10,
                "max_agents": 3,
                "max_nodes": 1,
                "retention_days": 30,
            },
            expires_at=datetime.max.replace(tzinfo=timezone.utc),
            days_remaining=999999,
            hardware_match_score=100,
        )

    def invalidate_cache(self) -> None:
        """Force re-validation on next check."""
        self._cached_license = None
```

### Feature Gate Decorator

```python
# src/licensing/feature_gate.py

from functools import wraps
from typing import Callable

from fastapi import HTTPException, status

from .license_service import LicenseService


_license_service: LicenseService = None


def get_license_service() -> LicenseService:
    global _license_service
    if _license_service is None:
        _license_service = LicenseService()
    return _license_service


def requires_feature(feature: str):
    """Decorator to gate endpoints by license feature."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            license_info = get_license_service().validate()

            if not license_info.has_feature(feature):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "feature_not_licensed",
                        "feature": feature,
                        "edition": license_info.edition,
                        "upgrade_url": "https://aenealabs.com/upgrade",
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def requires_limit(limit_name: str, get_current: Callable[..., int]):
    """Decorator to enforce license limits."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            license_info = get_license_service().validate()
            current_value = get_current(*args, **kwargs)

            if not license_info.check_limit(limit_name, current_value):
                max_value = license_info.limits.get(limit_name, 0)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "limit_exceeded",
                        "limit": limit_name,
                        "current": current_value,
                        "maximum": max_value,
                        "edition": license_info.edition,
                        "upgrade_url": "https://aenealabs.com/upgrade",
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### Usage Examples

```python
# src/api/hitl_endpoints.py

from fastapi import APIRouter
from src.licensing.feature_gate import requires_feature, requires_limit

router = APIRouter()


@router.post("/approvals")
@requires_feature("hitl_approval")
async def create_approval_request(request: ApprovalRequest):
    """Create HITL approval - requires Enterprise license."""
    # Implementation...
    pass


@router.post("/repositories")
@requires_limit("max_repositories", lambda: get_repository_count())
async def add_repository(repo: RepositoryCreate):
    """Add repository - subject to license limits."""
    # Implementation...
    pass
```

---

## License File Locations

### Supported Paths (Priority Order)

| Priority | Location | Use Case |
|----------|----------|----------|
| 1 | `AURA_LICENSE_KEY` env var | CI/CD, Kubernetes secrets |
| 2 | `AURA_LICENSE` env var (file path) | Custom locations |
| 3 | `/etc/aura/license.key` | Linux system-wide |
| 4 | `/opt/aura/license.key` | Container/appliance |
| 5 | `~/.aura/license.key` | Single-user development |

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aura-license
  namespace: aura
type: Opaque
stringData:
  license.key: |
    eyJ2ZXJzaW9uIjoxLCJsaWNlbnNlX2lkIjoibGljXzAxSFFYWVoxMjM...
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
spec:
  template:
    spec:
      containers:
      - name: aura
        env:
        - name: AURA_LICENSE_KEY
          valueFrom:
            secretKeyRef:
              name: aura-license
              key: license.key
```

---

## Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|------------|
| License file tampering | Ed25519 signature verification |
| Signature forging | 128-bit security level (2^128 operations) |
| Key extraction from binary | Keys are public (verification only) |
| Hardware ID spoofing | Multi-component fingerprint with threshold |
| Clock manipulation | NTP sync + grace period warnings |
| License sharing | Hardware fingerprint binding |
| Replay attacks | Unique license_id per issuance |

### Key Rotation

Public keys can be rotated by:
1. Adding new key to `PUBLIC_KEYS` dictionary
2. Issuing new licenses with `issuer_key_id` pointing to new key
3. Old licenses continue to validate with old key
4. Remove old key after all licenses renewed

### Audit Logging

All license validation events should be logged:

```python
logger.info(
    "license_validated",
    license_id=license_info.license_id,
    customer=license_info.customer_name,
    edition=license_info.edition,
    status=license_info.status.value,
    days_remaining=license_info.days_remaining,
    hardware_score=license_info.hardware_match_score,
)
```

---

## CLI Tools

### License Info Command

```bash
$ aura license info

License Information
───────────────────────────────────────
License ID:     lic_01HQXYZ123456789ABCDEF
Customer:       Acme Corporation
Edition:        Enterprise
Status:         Valid ✓
Expires:        2027-01-03 (365 days remaining)
Hardware Match: 100%

Features Enabled:
  ✓ graphrag
  ✓ multi_agent
  ✓ security_scanning
  ✓ hitl_approval
  ✓ sso_saml
  ✓ audit_logging

Limits:
  Repositories: 45/100
  Users:        127/500
  Agents:       12/50
  Nodes:        3/10
```

### Hardware Fingerprint Command

```bash
$ aura license hardware-id

Hardware Fingerprint
───────────────────────────────────────
Fingerprint:    hw_sha256_a1b2c3d4e5f67890...
Type:           composite
Generated:      2026-01-03T12:00:00Z

Components:
  machine_id:   ✓ 550e8400-e29b-41d4-a716-...
  cpu_id:       ✓ Intel(R) Xeon(R) CPU E5-2690
  motherboard:  ✓ ABCD1234
  disk_serial:  ✓ WD-WCAV12345678
  mac_address:  ✓ 00:1A:2B:3C:4D:5E
```

---

## Testing Strategy

### Unit Tests

```python
# tests/licensing/test_license_service.py

import pytest
from datetime import datetime, timedelta, timezone
from src.licensing.license_service import LicenseService, LicenseStatus


class TestLicenseValidation:
    def test_valid_license_signature(self, valid_license_file):
        service = LicenseService(valid_license_file)
        info = service.validate()
        assert info.status == LicenseStatus.VALID
        assert info.is_valid is True

    def test_invalid_signature_rejected(self, tampered_license_file):
        service = LicenseService(tampered_license_file)
        info = service.validate()
        assert info.status == LicenseStatus.INVALID_SIGNATURE
        assert info.edition == "community"  # Fallback

    def test_expired_license_with_grace(self, expired_license_in_grace):
        service = LicenseService(expired_license_in_grace)
        info = service.validate()
        assert info.status == LicenseStatus.GRACE_PERIOD
        assert info.is_valid is True  # Still valid during grace

    def test_expired_license_past_grace(self, expired_license_past_grace):
        service = LicenseService(expired_license_past_grace)
        info = service.validate()
        assert info.status == LicenseStatus.EXPIRED
        assert info.is_valid is False

    def test_hardware_mismatch_rejected(self, license_wrong_hardware):
        service = LicenseService(license_wrong_hardware)
        info = service.validate()
        assert info.status == LicenseStatus.HARDWARE_MISMATCH

    def test_community_fallback_on_missing(self):
        service = LicenseService("/nonexistent/path")
        info = service.validate()
        assert info.status == LicenseStatus.NOT_FOUND
        assert info.edition == "community"
        assert info.limits["max_repositories"] == 5
```

### Integration Tests

```python
# tests/integration/test_feature_gating.py

import pytest
from fastapi.testclient import TestClient


class TestFeatureGating:
    def test_hitl_blocked_for_community(self, client_with_community_license):
        response = client_with_community_license.post("/api/v1/approvals")
        assert response.status_code == 402
        assert response.json()["error"] == "feature_not_licensed"

    def test_hitl_allowed_for_enterprise(self, client_with_enterprise_license):
        response = client_with_enterprise_license.post("/api/v1/approvals")
        assert response.status_code != 402

    def test_repository_limit_enforced(self, client_at_limit):
        response = client_at_limit.post("/api/v1/repositories")
        assert response.status_code == 429
        assert response.json()["error"] == "limit_exceeded"
```

---

## References

- [Ed25519 Paper](https://ed25519.cr.yp.to/ed25519-20110926.pdf)
- [FIPS 186-5 Digital Signature Standard](https://csrc.nist.gov/publications/detail/fips/186/5/final)
- [PyNaCl Documentation](https://pynacl.readthedocs.io/)
- [Keygen Licensing Best Practices](https://keygen.sh/docs/choosing-a-licensing-model/)
- ADR-049: Self-Hosted Deployment Strategy
- ADR-040: Configurable Compliance Settings
