"""
Project Aura - Supply Chain Security Contracts

Data contracts for SBOM attestation, dependency confusion detection,
and license compliance services.

Enums:
- SBOMFormat: CycloneDX 1.5, SPDX 2.3
- SigningMethod: Sigstore keyless, offline Ed25519, HSM
- ConfusionType: Typosquatting, namespace hijacking, combosquatting
- LicenseCategory: Permissive, weak copyleft, strong copyleft, proprietary
- RiskLevel: Info, low, medium, high, critical

Dataclasses:
- SBOMComponent: Individual package in SBOM
- SBOMDocument: Complete SBOM with metadata
- Attestation: Signed attestation record
- ConfusionIndicator: Single confusion detection signal
- ConfusionResult: Analysis result for a package
- LicenseInfo: License metadata
- LicenseViolation: Policy violation record
- ComplianceReport: Overall compliance assessment
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SBOMFormat(Enum):
    """Supported SBOM output formats."""

    CYCLONEDX_1_5_JSON = "cyclonedx-1.5-json"
    CYCLONEDX_1_5_XML = "cyclonedx-1.5-xml"
    CYCLONEDX_1_4_JSON = "cyclonedx-1.4-json"
    SPDX_2_3_JSON = "spdx-2.3-json"
    SPDX_2_3_RDF = "spdx-2.3-rdf"
    INTERNAL = "internal"  # Aura's internal format


class SigningMethod(Enum):
    """SBOM attestation signing methods."""

    SIGSTORE_KEYLESS = "sigstore-keyless"  # OIDC-based, no persistent keys
    OFFLINE_ED25519 = "offline-ed25519"  # For air-gapped environments
    OFFLINE_KEY = "offline-key"  # Alias for offline-ed25519
    HSM_PKCS11 = "hsm-pkcs11"  # Hardware security module
    HSM = "hsm"  # Alias for hsm-pkcs11
    NONE = "none"  # Unsigned (for testing only)


class ConfusionType(Enum):
    """Types of dependency confusion attacks."""

    TYPOSQUATTING = "typosquatting"  # Similar name to popular package
    NAMESPACE_HIJACK = "namespace-hijack"  # Internal namespace on public registry
    COMBOSQUATTING = "combosquatting"  # Legitimate name with suffix/prefix
    DEPENDENCY_CONFUSION = "dependency-confusion"  # Internal vs external resolution
    MAINTAINER_COMPROMISE = "maintainer-compromise"  # Suspicious maintainer change
    VERSION_CONFUSION = "version-confusion"  # Higher version on public registry
    UNKNOWN = "unknown"  # Unknown confusion type
    NONE = "none"  # No confusion detected


class LicenseCategory(Enum):
    """License categories for compliance checking."""

    PERMISSIVE = "permissive"  # MIT, Apache-2.0, BSD
    WEAK_COPYLEFT = "weak-copyleft"  # LGPL, MPL
    STRONG_COPYLEFT = "strong-copyleft"  # GPL, AGPL
    PROPRIETARY = "proprietary"  # Commercial licenses
    PUBLIC_DOMAIN = "public-domain"  # CC0, Unlicense
    UNKNOWN = "unknown"  # Unidentified license


class RiskLevel(Enum):
    """Risk severity levels with numeric ordering."""

    NONE = -1  # No risk detected
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RiskLevel):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, RiskLevel):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, RiskLevel):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, RiskLevel):
            return self.value >= other.value
        return NotImplemented


class ComplianceStatus(Enum):
    """Overall compliance status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non-compliant"
    VIOLATION = "violation"  # Alias for non-compliant
    WARNING = "warning"  # License requires review
    REVIEW_REQUIRED = "review-required"
    UNKNOWN = "unknown"


class VerificationStatus(Enum):
    """Attestation verification status."""

    VERIFIED = "verified"
    NOT_VERIFIED = "not-verified"  # Not yet verified
    INVALID_SIGNATURE = "invalid-signature"
    EXPIRED_CERTIFICATE = "expired-certificate"
    REVOKED = "revoked"
    NOT_FOUND = "not-found"
    ERROR = "error"


# Type aliases for domain clarity
SBOMId = str
AttestationId = str
RepositoryId = str
PackageURL = str  # PURL format: pkg:ecosystem/name@version


@dataclass
class SBOMComponent:
    """Individual component (package/library) in an SBOM."""

    name: str
    version: str
    purl: Optional[str] = None  # Package URL (pkg:pip/requests@2.28.0)
    component_type: str = "library"  # library, application, framework, etc.
    ecosystem: str = "unknown"  # pip, npm, go, cargo, etc.
    supplier: Optional[str] = None  # Author or maintainer
    licenses: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)  # sha256, sha512, etc.
    source_file: Optional[str] = None  # Manifest file where detected
    is_dev_dependency: bool = False
    is_direct: bool = True  # Direct vs transitive dependency

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "purl": self.purl,
            "component_type": self.component_type,
            "ecosystem": self.ecosystem,
            "supplier": self.supplier,
            "licenses": self.licenses,
            "hashes": self.hashes,
            "source_file": self.source_file,
            "is_dev_dependency": self.is_dev_dependency,
            "is_direct": self.is_direct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SBOMComponent":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            version=data["version"],
            purl=data.get("purl"),
            component_type=data.get("component_type", "library"),
            ecosystem=data.get("ecosystem", "unknown"),
            supplier=data.get("supplier"),
            licenses=data.get("licenses", []),
            hashes=data.get("hashes", {}),
            source_file=data.get("source_file"),
            is_dev_dependency=data.get("is_dev_dependency", False),
            is_direct=data.get("is_direct", True),
        )


@dataclass
class SBOMDocument:
    """Complete Software Bill of Materials document."""

    sbom_id: SBOMId
    name: str  # Project/repository name
    version: str  # Project version
    format: SBOMFormat
    spec_version: str  # "1.5" for CycloneDX, "2.3" for SPDX
    repository_id: RepositoryId
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    components: list[SBOMComponent] = field(default_factory=list)
    hash_value: Optional[str] = None  # SHA256 hash of SBOM content
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tool_name: str = "aura-sbom-generator"
    tool_version: str = "1.0.0"
    serial_number: Optional[str] = None  # CycloneDX serial number
    document_namespace: Optional[str] = None  # SPDX document namespace
    content_hash: Optional[str] = None  # Alias for hash_value

    @property
    def component_count(self) -> int:
        """Total number of components."""
        return len(self.components)

    @property
    def direct_count(self) -> int:
        """Number of direct dependencies."""
        return sum(1 for c in self.components if c.is_direct)

    @property
    def dev_count(self) -> int:
        """Number of dev dependencies."""
        return sum(1 for c in self.components if c.is_dev_dependency)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "sbom_id": self.sbom_id,
            "name": self.name,
            "version": self.version,
            "repository_id": self.repository_id,
            "format": self.format.value,
            "spec_version": self.spec_version,
            "components": [c.to_dict() for c in self.components],
            "created_at": self.created_at.isoformat(),
            "hash_value": self.hash_value,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "serial_number": self.serial_number,
            "document_namespace": self.document_namespace,
            "content_hash": self.content_hash,
            "component_count": self.component_count,
            "direct_count": self.direct_count,
            "dev_count": self.dev_count,
        }


@dataclass
class Attestation:
    """Signed attestation for an SBOM."""

    attestation_id: AttestationId
    sbom_id: SBOMId
    predicate_type: str = "https://slsa.dev/provenance/v1"
    signing_method: SigningMethod = SigningMethod.SIGSTORE_KEYLESS
    signature: Optional[str] = None  # Base64-encoded signature
    certificate: Optional[str] = None  # PEM certificate (for keyless)
    signer_identity: Optional[str] = None  # OIDC identity or key fingerprint
    rekor_log_index: Optional[int] = None  # Transparency log index
    rekor_log_id: Optional[str] = None  # Transparency log ID
    rekor_uuid: Optional[str] = None  # Transparency log UUID (alias for rekor_log_id)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    subject_digest: Optional[str] = None  # SHA256 of SBOM content

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attestation_id": self.attestation_id,
            "sbom_id": self.sbom_id,
            "predicate_type": self.predicate_type,
            "signing_method": self.signing_method.value,
            "signature": self.signature,
            "certificate": self.certificate,
            "signer_identity": self.signer_identity,
            "rekor_log_index": self.rekor_log_index,
            "rekor_log_id": self.rekor_log_id,
            "rekor_uuid": self.rekor_uuid,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "subject_digest": self.subject_digest,
        }


@dataclass
class VerificationResult:
    """Result of attestation verification."""

    attestation_id: AttestationId
    status: VerificationStatus
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signer_identity: Optional[str] = None
    certificate_issuer: Optional[str] = None
    rekor_verified: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attestation_id": self.attestation_id,
            "status": self.status.value,
            "verified_at": self.verified_at.isoformat(),
            "signer_identity": self.signer_identity,
            "certificate_issuer": self.certificate_issuer,
            "rekor_verified": self.rekor_verified,
            "error_message": self.error_message,
        }


@dataclass
class ConfusionIndicator:
    """Single indicator of potential dependency confusion."""

    confusion_type: ConfusionType
    confidence: float  # 0.0 to 1.0
    description: str
    similar_package: Optional[str] = None  # Package being impersonated
    edit_distance: Optional[int] = None  # Levenshtein distance
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "confusion_type": self.confusion_type.value,
            "confidence": self.confidence,
            "description": self.description,
            "similar_package": self.similar_package,
            "edit_distance": self.edit_distance,
            "evidence": self.evidence,
        }


@dataclass
class ConfusionResult:
    """Complete analysis result for dependency confusion detection."""

    package_name: str
    ecosystem: str
    version: str
    confusion_type: ConfusionType = ConfusionType.NONE
    risk_level: RiskLevel = RiskLevel.NONE
    indicators: list[ConfusionIndicator] = field(default_factory=list)
    is_safe: bool = True
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendation: Optional[str] = None

    @property
    def highest_confidence(self) -> float:
        """Highest confidence among indicators."""
        if not self.indicators:
            return 0.0
        return max(i.confidence for i in self.indicators)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "package_name": self.package_name,
            "ecosystem": self.ecosystem,
            "version": self.version,
            "confusion_type": self.confusion_type.value,
            "risk_level": self.risk_level.value,
            "indicators": [i.to_dict() for i in self.indicators],
            "is_safe": self.is_safe,
            "analyzed_at": self.analyzed_at.isoformat(),
            "recommendation": self.recommendation,
            "highest_confidence": self.highest_confidence,
        }


@dataclass
class LicenseInfo:
    """License metadata from SPDX database."""

    spdx_id: str  # "MIT", "Apache-2.0", etc.
    name: str  # Full name
    category: LicenseCategory
    osi_approved: bool = False
    fsf_free: bool = False  # FSF Free Software
    fsf_libre: bool = False  # Alias for fsf_free
    copyleft: bool = False
    patent_grant: bool = False
    attribution_required: bool = True
    disclosure_required: bool = False
    url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "spdx_id": self.spdx_id,
            "name": self.name,
            "category": self.category.value,
            "osi_approved": self.osi_approved,
            "fsf_libre": self.fsf_libre,
            "copyleft": self.copyleft,
            "patent_grant": self.patent_grant,
            "attribution_required": self.attribution_required,
            "disclosure_required": self.disclosure_required,
            "url": self.url,
        }


@dataclass
class LicenseViolation:
    """License policy violation."""

    violation_id: str
    component_name: str
    component_version: str
    detected_license: str
    violation_type: str  # "prohibited", "incompatible", "requires_review"
    severity: RiskLevel
    policy_rule: str  # Which policy rule was violated
    description: str
    recommendation: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "violation_id": self.violation_id,
            "component_name": self.component_name,
            "component_version": self.component_version,
            "detected_license": self.detected_license,
            "violation_type": self.violation_type,
            "severity": self.severity.value,
            "policy_rule": self.policy_rule,
            "description": self.description,
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class LicensePolicy:
    """Organization license policy."""

    name: str
    allowed_categories: list[LicenseCategory] = field(default_factory=list)
    prohibited_licenses: list[str] = field(default_factory=list)  # SPDX IDs
    require_osi_approved: bool = False
    allow_unknown: bool = False
    policy_id: Optional[str] = None  # Optional identifier
    allowed_licenses: list[str] = field(default_factory=list)  # Override prohibited
    copyleft_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "allowed_categories": [c.value for c in self.allowed_categories],
            "prohibited_licenses": self.prohibited_licenses,
            "require_osi_approved": self.require_osi_approved,
            "allow_unknown": self.allow_unknown,
            "policy_id": self.policy_id,
            "allowed_licenses": self.allowed_licenses,
            "copyleft_allowed": self.copyleft_allowed,
        }


@dataclass
class ComplianceReport:
    """Overall license compliance assessment."""

    report_id: str
    repository_id: RepositoryId
    sbom_id: SBOMId
    status: ComplianceStatus
    violations: list[LicenseViolation] = field(default_factory=list)
    components_analyzed: int = 0
    components_compliant: int = 0
    policy_applied: Optional[str] = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def compliance_rate(self) -> float:
        """Percentage of compliant components."""
        if self.components_analyzed == 0:
            return 0.0
        return (self.components_compliant / self.components_analyzed) * 100

    @property
    def violation_count(self) -> int:
        """Total number of violations."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "report_id": self.report_id,
            "repository_id": self.repository_id,
            "sbom_id": self.sbom_id,
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "components_analyzed": self.components_analyzed,
            "components_compliant": self.components_compliant,
            "compliance_rate": self.compliance_rate,
            "violation_count": self.violation_count,
            "policy_applied": self.policy_applied,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ProvenanceChain:
    """Provenance chain for a package."""

    package_url: PackageURL  # Primary field name
    attestations: list[Any] = field(default_factory=list)  # Attestation dicts
    sbom_ids: list[SBOMId] = field(default_factory=list)
    verified: bool = False
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    latest_attestation_id: Optional[AttestationId] = None
    latest_attestation_at: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    repository_count: int = 0

    @property
    def purl(self) -> PackageURL:
        """Alias for package_url."""
        return self.package_url

    @property
    def sboms(self) -> list[SBOMId]:
        """Alias for sbom_ids."""
        return self.sbom_ids

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "package_url": self.package_url,
            "purl": self.purl,
            "attestations": self.attestations,
            "sbom_ids": self.sbom_ids,
            "verified": self.verified,
            "verification_status": self.verification_status.value,
            "latest_attestation_id": self.latest_attestation_id,
            "latest_attestation_at": (
                self.latest_attestation_at.isoformat()
                if self.latest_attestation_at
                else None
            ),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "repository_count": self.repository_count,
        }
