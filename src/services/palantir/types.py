"""
Palantir AIP Integration Types

Data models for ADR-074: Palantir AIP Integration.

Defines platform-agnostic types that can be used with any enterprise data platform:
- ThreatContext: Threat intelligence data
- AssetContext: Asset criticality and classification
- RemediationEvent: Events published to Palantir
- SyncResult: Object synchronization results
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class PalantirObjectType(Enum):
    """Palantir Ontology object types supported for sync."""

    THREAT_ACTOR = "ThreatActor"
    VULNERABILITY = "Vulnerability"
    ASSET = "Asset"
    REPOSITORY = "Repository"
    COMPLIANCE = "Compliance"


class SyncStatus(Enum):
    """Status of object synchronization."""

    SYNCED = "synced"  # Successfully synced
    PENDING = "pending"  # Awaiting sync
    FAILED = "failed"  # Sync failed
    STALE = "stale"  # Data may be outdated
    PARTIAL = "partial"  # Partially synced


class RemediationEventType(Enum):
    """Types of remediation events published to Palantir."""

    VULNERABILITY_DETECTED = "aura.vuln.detected"
    PATCH_GENERATED = "aura.patch.generated"
    SANDBOX_VALIDATED = "aura.sandbox.validated"
    REMEDIATION_COMPLETE = "aura.remediation.done"
    HITL_APPROVAL = "aura.hitl.decision"
    HITL_REJECTION = "aura.hitl.rejected"
    DEPLOYMENT_STARTED = "aura.deployment.started"
    DEPLOYMENT_COMPLETE = "aura.deployment.complete"
    DEPLOYMENT_FAILED = "aura.deployment.failed"


class DataClassification(Enum):
    """Data classification levels from Palantir CMDB."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_CLASSIFIED = "top_secret"  # GovCloud IL5+  # nosec: enum value


class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategies per ADR-074."""

    PALANTIR_AUTHORITATIVE = "palantir"  # Palantir wins
    AURA_AUTHORITATIVE = "aura"  # Aura wins
    MERGE = "merge"  # Merge fields from both
    LAST_WRITE_WINS = "lww"  # Most recent timestamp wins
    MANUAL = "manual"  # Require manual resolution


# =============================================================================
# Data Classes - Threat Intelligence
# =============================================================================


@dataclass
class ThreatContext:
    """
    Platform-agnostic threat context.

    Represents threat intelligence data that can be retrieved from
    Palantir, Databricks, or other enterprise data platforms.

    Attributes:
        threat_id: Unique identifier for the threat
        source_platform: Platform that provided this data (e.g., "palantir_aip")
        cves: List of associated CVE IDs
        epss_score: EPSS (Exploit Prediction Scoring System) score 0-1
        mitre_ttps: MITRE ATT&CK technique IDs
        targeted_industries: Industries actively targeted
        active_campaigns: Names of active threat campaigns
        threat_actors: Names of associated threat actors
        first_seen: When threat was first observed
        last_seen: Most recent observation
        severity: Threat severity (critical, high, medium, low)
        raw_metadata: Platform-specific additional fields
    """

    threat_id: str
    source_platform: str
    cves: list[str] = field(default_factory=list)
    epss_score: float | None = None
    mitre_ttps: list[str] = field(default_factory=list)
    targeted_industries: list[str] = field(default_factory=list)
    active_campaigns: list[str] = field(default_factory=list)
    threat_actors: list[str] = field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    severity: str = "medium"
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate threat context after initialization."""
        if self.epss_score is not None:
            if not 0 <= self.epss_score <= 1:
                raise ValueError(f"EPSS score must be 0-1, got {self.epss_score}")
        if self.severity not in ("critical", "high", "medium", "low"):
            raise ValueError(f"Invalid severity: {self.severity}")

    @property
    def is_actively_exploited(self) -> bool:
        """Check if this threat has active exploitation."""
        return len(self.active_campaigns) > 0 or (
            self.epss_score is not None and self.epss_score > 0.9
        )

    @property
    def priority_score(self) -> float:
        """Calculate priority score (0-100) for remediation ordering."""
        score = 0.0

        # EPSS contributes up to 40 points
        if self.epss_score is not None:
            score += self.epss_score * 40

        # Active campaigns contribute up to 30 points
        if self.active_campaigns:
            score += min(len(self.active_campaigns) * 10, 30)

        # Severity contributes up to 20 points
        severity_scores = {"critical": 20, "high": 15, "medium": 10, "low": 5}
        score += severity_scores.get(self.severity, 0)

        # Known threat actors contribute up to 10 points
        if self.threat_actors:
            score += min(len(self.threat_actors) * 5, 10)

        return min(score, 100.0)


@dataclass
class ThreatActor:
    """
    Threat actor from Palantir Ontology.

    Attributes:
        actor_id: Unique identifier
        name: Actor name (e.g., "APT29")
        aliases: Alternative names
        ttps: MITRE ATT&CK techniques used
        targeted_industries: Industries this actor targets
        targeted_regions: Geographic regions targeted
        active_since: When actor became active
        last_activity: Most recent known activity
        attribution: Country/group attribution
        description: Description of the actor
    """

    actor_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    ttps: list[str] = field(default_factory=list)
    targeted_industries: list[str] = field(default_factory=list)
    targeted_regions: list[str] = field(default_factory=list)
    active_since: datetime | None = None
    last_activity: datetime | None = None
    attribution: str | None = None
    description: str | None = None


# =============================================================================
# Data Classes - Asset Management
# =============================================================================


@dataclass
class AssetContext:
    """
    Platform-agnostic asset criticality context.

    Represents asset information from Palantir CMDB or similar systems.

    Attributes:
        asset_id: Unique identifier for the asset
        criticality_score: Business criticality 1-10 (10 = most critical)
        data_classification: Data classification level
        business_owner: Email or ID of business owner
        technical_owner: Email or ID of technical owner
        department: Owning department
        cost_center: Financial cost center
        pii_handling: Whether asset handles PII
        phi_handling: Whether asset handles PHI (HIPAA)
        pci_scope: Whether asset is in PCI scope
        internet_facing: Whether asset is internet-accessible
        environment: Environment (prod, staging, dev)
        tags: Additional metadata tags
    """

    asset_id: str
    criticality_score: int = 5
    data_classification: DataClassification = DataClassification.INTERNAL
    business_owner: str | None = None
    technical_owner: str | None = None
    department: str | None = None
    cost_center: str | None = None
    pii_handling: bool = False
    phi_handling: bool = False
    pci_scope: bool = False
    internet_facing: bool = False
    environment: str = "unknown"
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate asset context after initialization."""
        if not 1 <= self.criticality_score <= 10:
            raise ValueError(
                f"Criticality score must be 1-10, got {self.criticality_score}"
            )

    @property
    def is_high_value(self) -> bool:
        """Check if this is a high-value asset requiring priority remediation."""
        return (
            self.criticality_score >= 8
            or self.phi_handling
            or self.pci_scope
            or (
                self.internet_facing
                and self.data_classification != DataClassification.PUBLIC
            )
        )

    @property
    def compliance_flags(self) -> list[str]:
        """Get list of compliance frameworks affecting this asset."""
        flags = []
        if self.phi_handling:
            flags.append("HIPAA")
        if self.pci_scope:
            flags.append("PCI-DSS")
        if self.pii_handling:
            flags.append("GDPR")
        if self.data_classification in (
            DataClassification.RESTRICTED,
            DataClassification.TOP_CLASSIFIED,
        ):
            flags.append("CMMC")
        return flags


# =============================================================================
# Data Classes - Remediation Events
# =============================================================================


@dataclass
class RemediationEvent:
    """
    Event published to Palantir Foundry.

    Represents an Aura remediation workflow event that flows to Palantir
    for dashboarding, analytics, and compliance evidence.

    Attributes:
        event_id: Unique event identifier
        event_type: Type of remediation event
        timestamp: When event occurred (ISO format)
        tenant_id: Customer tenant identifier
        correlation_id: ID linking related events in a workflow
        vulnerability_id: Related vulnerability ID
        repository_id: Affected repository
        patch_id: Related patch ID (if applicable)
        payload: Event-specific data
        schema_version: Event schema version for compatibility
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: RemediationEventType = RemediationEventType.VULNERABILITY_DETECTED
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tenant_id: str = ""
    correlation_id: str | None = None
    vulnerability_id: str | None = None
    repository_id: str | None = None
    patch_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "vulnerability_id": self.vulnerability_id,
            "repository_id": self.repository_id,
            "patch_id": self.patch_id,
            "payload": self.payload,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemediationEvent":
        """Create from dictionary."""
        event_type = data.get("event_type", "aura.vuln.detected")
        if isinstance(event_type, str):
            event_type = RemediationEventType(event_type)
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=event_type,
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            tenant_id=data.get("tenant_id", ""),
            correlation_id=data.get("correlation_id"),
            vulnerability_id=data.get("vulnerability_id"),
            repository_id=data.get("repository_id"),
            patch_id=data.get("patch_id"),
            payload=data.get("payload", {}),
            schema_version=data.get("schema_version", "1.0"),
        )


# =============================================================================
# Data Classes - Sync Results
# =============================================================================


@dataclass
class SyncResult:
    """
    Result of an object synchronization operation.

    Attributes:
        object_type: Type of objects synced
        status: Overall sync status
        objects_synced: Number of objects successfully synced
        objects_failed: Number of objects that failed to sync
        objects_skipped: Number of objects skipped (no changes)
        conflicts_resolved: Number of conflicts auto-resolved
        conflicts_pending: Number of conflicts requiring manual resolution
        started_at: When sync started
        completed_at: When sync completed
        error_message: Error message if sync failed
        details: Additional sync details
    """

    object_type: PalantirObjectType
    status: SyncStatus = SyncStatus.PENDING
    objects_synced: int = 0
    objects_failed: int = 0
    objects_skipped: int = 0
    conflicts_resolved: int = 0
    conflicts_pending: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate sync duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.objects_synced + self.objects_failed
        if total == 0:
            return 100.0
        return (self.objects_synced / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "object_type": self.object_type.value,
            "status": self.status.value,
            "objects_synced": self.objects_synced,
            "objects_failed": self.objects_failed,
            "objects_skipped": self.objects_skipped,
            "conflicts_resolved": self.conflicts_resolved,
            "conflicts_pending": self.conflicts_pending,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class BatchResult:
    """
    Result of a batch event publishing operation.

    Attributes:
        total_events: Total events in batch
        successful: Number successfully published
        failed: Number that failed
        failed_events: List of failed event IDs
        error_messages: Error messages keyed by event ID
    """

    total_events: int = 0
    successful: int = 0
    failed: int = 0
    failed_events: list[str] = field(default_factory=list)
    error_messages: dict[str, str] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_events == 0:
            return 100.0
        return (self.successful / self.total_events) * 100

    @property
    def all_succeeded(self) -> bool:
        """Check if all events were published successfully."""
        return self.failed == 0


# =============================================================================
# Data Classes - Configuration
# =============================================================================


@dataclass
class PalantirConfig:
    """
    Palantir integration configuration.

    Attributes:
        enabled: Whether integration is enabled
        ontology_api_url: Palantir Ontology API URL
        foundry_api_url: Palantir Foundry API URL
        api_key_secret_name: AWS Secrets Manager secret name for API key
        client_cert_secret_name: Secret name for mTLS client certificate
        tenant_id: Palantir organization ID
        sync_frequency_hours: Hours between full syncs
        incremental_sync_enabled: Enable real-time incremental sync
        object_types: Object types to sync
        event_stream_mode: How to publish events (eventbridge, kinesis, direct)
        kinesis_stream_name: Kinesis stream for events (if mode=kinesis)
        eventbridge_bus_name: EventBridge bus (if mode=eventbridge)
        cache_ttl_seconds: TTL for cached data
        circuit_breaker_enabled: Enable circuit breaker pattern
    """

    enabled: bool = False
    ontology_api_url: str = ""
    foundry_api_url: str = ""
    api_key_secret_name: str = ""
    client_cert_secret_name: str | None = None
    tenant_id: str = ""
    sync_frequency_hours: int = 1
    incremental_sync_enabled: bool = True
    object_types: list[PalantirObjectType] = field(
        default_factory=lambda: [
            PalantirObjectType.THREAT_ACTOR,
            PalantirObjectType.VULNERABILITY,
            PalantirObjectType.ASSET,
        ]
    )
    event_stream_mode: str = "eventbridge"  # eventbridge | kinesis | direct
    kinesis_stream_name: str | None = None
    eventbridge_bus_name: str | None = None
    cache_ttl_seconds: int = 300  # 5 minutes
    circuit_breaker_enabled: bool = True

    def validate(self) -> list[str]:
        """Validate configuration, return list of errors."""
        errors = []
        if self.enabled:
            if not self.ontology_api_url:
                errors.append("ontology_api_url is required when enabled")
            if not self.foundry_api_url:
                errors.append("foundry_api_url is required when enabled")
            if not self.api_key_secret_name:
                errors.append("api_key_secret_name is required when enabled")
            if not self.tenant_id:
                errors.append("tenant_id is required when enabled")
            if self.event_stream_mode == "kinesis" and not self.kinesis_stream_name:
                errors.append("kinesis_stream_name required when mode=kinesis")
        return errors


# =============================================================================
# Conflict Resolution Configuration
# =============================================================================

# Per ADR-074 Conflict Resolution Matrix
CONFLICT_RESOLUTION_RULES: dict[PalantirObjectType, ConflictResolutionStrategy] = {
    PalantirObjectType.THREAT_ACTOR: ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE,
    PalantirObjectType.VULNERABILITY: ConflictResolutionStrategy.MERGE,
    PalantirObjectType.ASSET: ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE,
    PalantirObjectType.REPOSITORY: ConflictResolutionStrategy.AURA_AUTHORITATIVE,
    PalantirObjectType.COMPLIANCE: ConflictResolutionStrategy.MERGE,
}
