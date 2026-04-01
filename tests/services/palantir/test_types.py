"""
Tests for Palantir AIP Data Types

Tests data models, enums, and type validation.
"""

from src.services.palantir.types import (
    CONFLICT_RESOLUTION_RULES,
    AssetContext,
    BatchResult,
    ConflictResolutionStrategy,
    DataClassification,
    PalantirConfig,
    PalantirObjectType,
    RemediationEvent,
    RemediationEventType,
    SyncResult,
    SyncStatus,
    ThreatContext,
)

# =============================================================================
# ThreatContext Tests
# =============================================================================


class TestThreatContext:
    """Tests for ThreatContext dataclass."""

    def test_create_minimal(self):
        """Test creating ThreatContext with minimal fields."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
        )
        assert threat.threat_id == "threat-001"
        assert threat.source_platform == "palantir_aip"
        assert threat.cves == []
        assert threat.epss_score is None
        assert threat.mitre_ttps == []

    def test_create_full(self):
        """Test creating ThreatContext with all fields."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
            epss_score=0.85,
            mitre_ttps=["T1059", "T1190"],
            targeted_industries=["finance"],
            active_campaigns=["Campaign-Alpha"],
            threat_actors=["APT29"],
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-15T00:00:00Z",
            raw_metadata={"source": "test"},
        )
        assert threat.cves == ["CVE-2024-1234"]
        assert threat.epss_score == 0.85
        assert threat.threat_actors == ["APT29"]

    def test_priority_score_high_epss(self):
        """Test priority score with high EPSS."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            epss_score=0.9,
            active_campaigns=["Campaign-Alpha"],
        )
        # High EPSS + active campaign should result in high priority
        assert threat.priority_score > 0.8

    def test_priority_score_low_epss(self):
        """Test priority score with low EPSS."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            epss_score=0.1,
        )
        # Score: 0.1 * 40 (epss) + 10 (medium severity) = 14
        assert threat.priority_score == 14.0

    def test_priority_score_no_epss(self):
        """Test priority score without EPSS."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
        )
        # Only severity contributes: 10 (medium)
        assert threat.priority_score == 10.0

    def test_priority_score_with_active_campaigns(self):
        """Test priority score with active campaigns."""
        threat_no_campaigns = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            epss_score=0.5,
        )
        threat_with_campaigns = ThreatContext(
            threat_id="threat-002",
            source_platform="palantir_aip",
            epss_score=0.5,
            active_campaigns=["Campaign-Alpha"],
        )
        # Score with campaign: 0.5*40 + 10 + 10 = 40
        # Score without: 0.5*40 + 10 = 30
        assert threat_with_campaigns.priority_score > threat_no_campaigns.priority_score

    def test_is_actively_exploited(self):
        """Test is_actively_exploited property."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            active_campaigns=["Campaign-Alpha"],
        )
        assert threat.is_actively_exploited is True

    def test_is_actively_exploited_high_epss(self):
        """Test is_actively_exploited with high EPSS."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            epss_score=0.95,
        )
        assert threat.is_actively_exploited is True


# =============================================================================
# AssetContext Tests
# =============================================================================


class TestAssetContext:
    """Tests for AssetContext dataclass."""

    def test_create_minimal(self):
        """Test creating AssetContext with minimal fields."""
        asset = AssetContext(asset_id="asset-001")
        assert asset.asset_id == "asset-001"
        assert asset.criticality_score == 5  # default
        assert asset.data_classification == DataClassification.INTERNAL

    def test_create_full(self):
        """Test creating AssetContext with all fields."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=9,
            data_classification=DataClassification.CONFIDENTIAL,
            business_owner="security-team",
            pii_handling=True,
            phi_handling=True,
        )
        assert asset.criticality_score == 9
        assert asset.pii_handling is True
        # compliance_flags is computed property
        assert "HIPAA" in asset.compliance_flags

    def test_is_high_value_critical(self):
        """Test is_high_value for critical asset."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=9,
        )
        assert asset.is_high_value is True

    def test_is_high_value_phi(self):
        """Test is_high_value for PHI handling asset."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=5,
            phi_handling=True,
        )
        assert asset.is_high_value is True

    def test_is_high_value_pci(self):
        """Test is_high_value for PCI scope asset."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=5,
            pci_scope=True,
        )
        assert asset.is_high_value is True

    def test_is_high_value_internet_facing(self):
        """Test is_high_value for internet-facing non-public asset."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=5,
            data_classification=DataClassification.INTERNAL,
            internet_facing=True,
        )
        assert asset.is_high_value is True

    def test_is_high_value_false(self):
        """Test is_high_value for low-value asset."""
        asset = AssetContext(
            asset_id="asset-001",
            criticality_score=3,
            data_classification=DataClassification.PUBLIC,
        )
        assert asset.is_high_value is False

    def test_compliance_flags_hipaa(self):
        """Test compliance flags for HIPAA."""
        asset = AssetContext(
            asset_id="asset-001",
            phi_handling=True,
        )
        flags = asset.compliance_flags
        assert "HIPAA" in flags

    def test_compliance_flags_cmmc(self):
        """Test compliance flags for CMMC."""
        asset = AssetContext(
            asset_id="asset-001",
            data_classification=DataClassification.RESTRICTED,
        )
        flags = asset.compliance_flags
        assert "CMMC" in flags

    def test_compliance_flags_pci(self):
        """Test compliance flags for PCI-DSS."""
        asset = AssetContext(
            asset_id="asset-001",
            pci_scope=True,
        )
        flags = asset.compliance_flags
        assert "PCI-DSS" in flags


# =============================================================================
# RemediationEvent Tests
# =============================================================================


class TestRemediationEvent:
    """Tests for RemediationEvent dataclass."""

    def test_create_event(self):
        """Test creating RemediationEvent."""
        event = RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.VULNERABILITY_DETECTED,
            timestamp="2024-01-15T00:00:00Z",
            tenant_id="tenant-001",
            payload={"cve_id": "CVE-2024-1234"},
        )
        assert event.event_id == "evt-001"
        assert event.event_type == RemediationEventType.VULNERABILITY_DETECTED
        assert event.payload["cve_id"] == "CVE-2024-1234"

    def test_all_event_types(self):
        """Test all remediation event types."""
        event_types = [
            RemediationEventType.VULNERABILITY_DETECTED,
            RemediationEventType.PATCH_GENERATED,
            RemediationEventType.SANDBOX_VALIDATED,
            RemediationEventType.REMEDIATION_COMPLETE,
            RemediationEventType.HITL_APPROVAL,
            RemediationEventType.HITL_REJECTION,
        ]
        for event_type in event_types:
            event = RemediationEvent(
                event_id="evt-001",
                event_type=event_type,
                timestamp="2024-01-15T00:00:00Z",
                tenant_id="tenant-001",
                payload={},
            )
            assert event.event_type == event_type

    def test_to_dict(self):
        """Test to_dict method."""
        event = RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.PATCH_GENERATED,
            timestamp="2024-01-15T00:00:00Z",
            tenant_id="tenant-001",
            payload={"patch_id": "patch-001"},
        )
        d = event.to_dict()
        assert d["event_id"] == "evt-001"
        assert d["event_type"] == "aura.patch.generated"
        assert d["payload"]["patch_id"] == "patch-001"

    def test_from_dict(self):
        """Test from_dict class method."""
        data = {
            "event_id": "evt-001",
            "event_type": "aura.sandbox.validated",
            "timestamp": "2024-01-15T00:00:00Z",
            "tenant_id": "tenant-001",
            "payload": {"sandbox_id": "sandbox-001"},
        }
        event = RemediationEvent.from_dict(data)
        assert event.event_id == "evt-001"
        assert event.event_type == RemediationEventType.SANDBOX_VALIDATED


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum types."""

    def test_data_classification_values(self):
        """Test DataClassification enum values."""
        assert DataClassification.PUBLIC.value == "public"
        assert DataClassification.INTERNAL.value == "internal"
        assert DataClassification.CONFIDENTIAL.value == "confidential"
        assert DataClassification.RESTRICTED.value == "restricted"

    def test_palantir_object_type_values(self):
        """Test PalantirObjectType enum values."""
        assert PalantirObjectType.THREAT_ACTOR.value == "ThreatActor"
        assert PalantirObjectType.VULNERABILITY.value == "Vulnerability"
        assert PalantirObjectType.ASSET.value == "Asset"
        assert PalantirObjectType.REPOSITORY.value == "Repository"
        assert PalantirObjectType.COMPLIANCE.value == "Compliance"

    def test_sync_status_values(self):
        """Test SyncStatus enum values."""
        assert SyncStatus.SYNCED.value == "synced"
        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.FAILED.value == "failed"
        assert SyncStatus.STALE.value == "stale"

    def test_conflict_resolution_strategy_values(self):
        """Test ConflictResolutionStrategy enum values."""
        assert ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE.value == "palantir"
        assert ConflictResolutionStrategy.AURA_AUTHORITATIVE.value == "aura"
        assert ConflictResolutionStrategy.MERGE.value == "merge"
        assert ConflictResolutionStrategy.LAST_WRITE_WINS.value == "lww"


# =============================================================================
# Conflict Resolution Rules Tests
# =============================================================================


class TestConflictResolutionRules:
    """Tests for conflict resolution rules."""

    def test_threat_actor_palantir_authoritative(self):
        """Test ThreatActor is Palantir authoritative."""
        assert (
            CONFLICT_RESOLUTION_RULES[PalantirObjectType.THREAT_ACTOR]
            == ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE
        )

    def test_vulnerability_merge(self):
        """Test Vulnerability uses merge strategy."""
        assert (
            CONFLICT_RESOLUTION_RULES[PalantirObjectType.VULNERABILITY]
            == ConflictResolutionStrategy.MERGE
        )

    def test_asset_palantir_authoritative(self):
        """Test Asset is Palantir authoritative."""
        assert (
            CONFLICT_RESOLUTION_RULES[PalantirObjectType.ASSET]
            == ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE
        )

    def test_repository_aura_authoritative(self):
        """Test Repository is Aura authoritative."""
        assert (
            CONFLICT_RESOLUTION_RULES[PalantirObjectType.REPOSITORY]
            == ConflictResolutionStrategy.AURA_AUTHORITATIVE
        )

    def test_compliance_merge(self):
        """Test Compliance uses merge strategy."""
        assert (
            CONFLICT_RESOLUTION_RULES[PalantirObjectType.COMPLIANCE]
            == ConflictResolutionStrategy.MERGE
        )


# =============================================================================
# SyncResult Tests
# =============================================================================


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_create_successful_sync(self):
        """Test creating successful SyncResult."""
        result = SyncResult(
            object_type=PalantirObjectType.VULNERABILITY,
            status=SyncStatus.SYNCED,
            objects_synced=10,
            objects_failed=0,
            conflicts_resolved=2,
        )
        assert result.status == SyncStatus.SYNCED
        assert result.objects_synced == 10

    def test_create_failed_sync(self):
        """Test creating failed SyncResult."""
        result = SyncResult(
            object_type=PalantirObjectType.THREAT_ACTOR,
            status=SyncStatus.FAILED,
            objects_synced=0,
            objects_failed=5,
            error_message="Connection timeout",
        )
        assert result.status == SyncStatus.FAILED
        assert result.error_message == "Connection timeout"


# =============================================================================
# BatchResult Tests
# =============================================================================


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_create_batch_result(self):
        """Test creating BatchResult."""
        result = BatchResult(
            total_events=10,
            successful=8,
            failed=2,
            failed_events=["evt-001", "evt-002"],
        )
        assert result.total_events == 10
        assert result.successful == 8
        assert len(result.failed_events) == 2

    def test_batch_result_all_success(self):
        """Test BatchResult with all successes."""
        result = BatchResult(
            total_events=5,
            successful=5,
            failed=0,
        )
        assert result.failed_events == []
        assert result.all_succeeded is True

    def test_batch_result_success_rate(self):
        """Test BatchResult success rate calculation."""
        result = BatchResult(
            total_events=10,
            successful=8,
            failed=2,
        )
        assert result.success_rate == 80.0


# =============================================================================
# PalantirConfig Tests
# =============================================================================


class TestPalantirConfig:
    """Tests for PalantirConfig dataclass."""

    def test_create_minimal_config(self):
        """Test creating minimal PalantirConfig."""
        config = PalantirConfig(
            enabled=True,
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key_secret_name="palantir/api-key",
            tenant_id="tenant-001",
        )
        assert config.ontology_api_url == "https://test.palantir.com/ontology"
        assert config.api_key_secret_name == "palantir/api-key"
        assert config.cache_ttl_seconds == 300  # default

    def test_create_full_config(self):
        """Test creating full PalantirConfig."""
        config = PalantirConfig(
            enabled=True,
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key_secret_name="palantir/api-key",
            client_cert_secret_name="palantir/client-cert",
            tenant_id="tenant-001",
            sync_frequency_hours=2,
            cache_ttl_seconds=600,
        )
        assert config.client_cert_secret_name == "palantir/client-cert"
        assert config.sync_frequency_hours == 2
        assert config.cache_ttl_seconds == 600

    def test_config_validation_valid(self):
        """Test config validation with valid config."""
        config = PalantirConfig(
            enabled=True,
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key_secret_name="palantir/api-key",
            tenant_id="tenant-001",
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_config_validation_missing_fields(self):
        """Test config validation with missing required fields."""
        config = PalantirConfig(enabled=True)
        errors = config.validate()
        assert len(errors) > 0
        assert any("ontology_api_url" in e for e in errors)
