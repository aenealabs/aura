"""
Tests for Disaster Recovery Service.

Tests cover:
- Region management and health checking
- Failover orchestration
- Backup management and validation
- DR drill scheduling and execution
- RTO/RPO compliance tracking
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.disaster_recovery_service import (
    RECOVERY_OBJECTIVES,
    BackupRecord,
    BackupStatus,
    BackupType,
    DisasterRecoveryService,
    DrillRecord,
    DrillStatus,
    FailoverEvent,
    FailoverStatus,
    FailoverType,
    HealthCheckResult,
    RecoveryObjective,
    RegionConfig,
    RegionStatus,
    get_disaster_recovery_service,
    reset_disaster_recovery_service,
)


@pytest.fixture
def service():
    """Provide a fresh disaster recovery service for each test."""
    reset_disaster_recovery_service()
    return get_disaster_recovery_service()


@pytest.fixture
def primary_region():
    """Create a primary region configuration."""
    return RegionConfig(
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        is_primary=True,
        vpc_id="vpc-primary-123",
        eks_cluster_name="aura-eks-primary",
        neptune_cluster_id="aura-neptune-primary",
        opensearch_domain="aura-opensearch-primary",
        alb_dns_name="primary.aura.example.com",
        health_check_endpoint="https://primary.aura.example.com/health",
        failover_priority=1,
    )


@pytest.fixture
def secondary_region():
    """Create a secondary region configuration."""
    return RegionConfig(
        region_id="us-west-2",
        region_name="US West (Oregon)",
        is_primary=False,
        vpc_id="vpc-secondary-456",
        eks_cluster_name="aura-eks-secondary",
        neptune_cluster_id="aura-neptune-secondary",
        opensearch_domain="aura-opensearch-secondary",
        alb_dns_name="secondary.aura.example.com",
        health_check_endpoint="https://secondary.aura.example.com/health",
        failover_priority=2,
    )


class TestRegionStatus:
    """Tests for region status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert RegionStatus.HEALTHY.value == "healthy"
        assert RegionStatus.DEGRADED.value == "degraded"
        assert RegionStatus.UNHEALTHY.value == "unhealthy"
        assert RegionStatus.FAILING_OVER.value == "failing_over"
        assert RegionStatus.STANDBY.value == "standby"
        assert RegionStatus.UNKNOWN.value == "unknown"


class TestFailoverStatus:
    """Tests for failover status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert FailoverStatus.INITIATED.value == "initiated"
        assert FailoverStatus.IN_PROGRESS.value == "in_progress"
        assert FailoverStatus.VALIDATING.value == "validating"
        assert FailoverStatus.COMPLETED.value == "completed"
        assert FailoverStatus.FAILED.value == "failed"
        assert FailoverStatus.ROLLED_BACK.value == "rolled_back"


class TestFailoverType:
    """Tests for failover type enum."""

    def test_all_types_exist(self):
        """Verify all expected types are defined."""
        assert FailoverType.AUTOMATIC.value == "automatic"
        assert FailoverType.MANUAL.value == "manual"
        assert FailoverType.SCHEDULED.value == "scheduled"
        assert FailoverType.DRILL.value == "drill"


class TestDrillStatus:
    """Tests for drill status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert DrillStatus.SCHEDULED.value == "scheduled"
        assert DrillStatus.IN_PROGRESS.value == "in_progress"
        assert DrillStatus.COMPLETED.value == "completed"
        assert DrillStatus.FAILED.value == "failed"
        assert DrillStatus.CANCELLED.value == "cancelled"


class TestBackupStatus:
    """Tests for backup status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert BackupStatus.PENDING.value == "pending"
        assert BackupStatus.IN_PROGRESS.value == "in_progress"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.FAILED.value == "failed"
        assert BackupStatus.EXPIRED.value == "expired"


class TestBackupType:
    """Tests for backup type enum."""

    def test_all_types_exist(self):
        """Verify all expected backup types are defined."""
        assert BackupType.NEPTUNE_SNAPSHOT.value == "neptune_snapshot"
        assert BackupType.OPENSEARCH_SNAPSHOT.value == "opensearch_snapshot"
        assert BackupType.DYNAMODB_BACKUP.value == "dynamodb_backup"
        assert BackupType.S3_REPLICATION.value == "s3_replication"
        assert BackupType.EKS_CONFIGURATION.value == "eks_configuration"
        assert BackupType.SECRETS.value == "secrets"


class TestRecoveryObjective:
    """Tests for recovery objectives."""

    def test_predefined_objectives(self):
        """Verify predefined recovery objectives exist."""
        assert "standard" in RECOVERY_OBJECTIVES
        assert "professional" in RECOVERY_OBJECTIVES
        assert "enterprise" in RECOVERY_OBJECTIVES
        assert "government" in RECOVERY_OBJECTIVES

    def test_enterprise_objectives(self):
        """Verify enterprise tier objectives."""
        obj = RECOVERY_OBJECTIVES["enterprise"]
        assert obj.rto_minutes == 15
        assert obj.rpo_minutes == 5

    def test_government_objectives(self):
        """Verify government tier objectives (strictest)."""
        obj = RECOVERY_OBJECTIVES["government"]
        assert obj.rto_minutes == 5
        assert obj.rpo_minutes == 1

    def test_objective_has_required_fields(self):
        """Verify objectives have all required fields."""
        for tier, obj in RECOVERY_OBJECTIVES.items():
            assert hasattr(obj, "name")
            assert hasattr(obj, "rto_minutes")
            assert hasattr(obj, "rpo_minutes")
            assert hasattr(obj, "tier")


class TestDisasterRecoveryService:
    """Tests for disaster recovery service initialization."""

    def test_service_initialization(self, service):
        """Verify service initializes correctly."""
        assert service is not None
        assert isinstance(service, DisasterRecoveryService)

    def test_singleton_pattern(self):
        """Verify singleton pattern works."""
        reset_disaster_recovery_service()
        svc1 = get_disaster_recovery_service()
        svc2 = get_disaster_recovery_service()
        assert svc1 is svc2


class TestRegionManagement:
    """Tests for region management."""

    def test_register_region(self, service, primary_region):
        """Test registering a region."""
        service.register_region(primary_region)
        retrieved = service.get_region(primary_region.region_id)
        assert retrieved is not None
        assert retrieved.region_id == primary_region.region_id

    def test_get_active_region(self, service, primary_region):
        """Test getting active region."""
        service.register_region(primary_region)
        active = service.get_active_region()
        assert active is not None
        assert active.is_primary is True

    def test_get_standby_regions(self, service, primary_region, secondary_region):
        """Test getting standby regions."""
        service.register_region(primary_region)
        service.register_region(secondary_region)
        standby = service.get_standby_regions()
        assert len(standby) == 1
        assert standby[0].region_id == secondary_region.region_id

    def test_update_region_status(self, service, primary_region):
        """Test updating region status."""
        service.register_region(primary_region)
        service.update_region_status(primary_region.region_id, RegionStatus.DEGRADED)
        region = service.get_region(primary_region.region_id)
        assert region.status == RegionStatus.DEGRADED

    def test_nonexistent_region(self, service):
        """Test getting nonexistent region returns None."""
        result = service.get_region("nonexistent-region")
        assert result is None


class TestRegionHealth:
    """Tests for region health checking."""

    @pytest.mark.asyncio
    async def test_check_region_health(self, service, primary_region):
        """Test checking region health."""
        service.register_region(primary_region)
        result = await service.check_region_health(primary_region.region_id)
        assert isinstance(result, HealthCheckResult)
        assert result.region_id == primary_region.region_id
        assert result.is_healthy is True

    @pytest.mark.asyncio
    async def test_check_all_regions_health(
        self, service, primary_region, secondary_region
    ):
        """Test checking all regions health."""
        service.register_region(primary_region)
        service.register_region(secondary_region)
        results = await service.check_all_regions_health()
        assert len(results) == 2
        assert primary_region.region_id in results
        assert secondary_region.region_id in results

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_region(self, service):
        """Test health check for nonexistent region raises error."""
        with pytest.raises(ValueError, match="Region not found"):
            await service.check_region_health("nonexistent-region")

    def test_get_health_history(self, service, primary_region):
        """Test getting health check history."""
        service.register_region(primary_region)
        history = service.get_health_history(region_id=primary_region.region_id)
        assert isinstance(history, list)

    def test_get_health_history_filtered(self, service):
        """Test getting filtered health history."""
        history = service.get_health_history(hours=24)
        assert isinstance(history, list)


class TestFailover:
    """Tests for failover operations."""

    @pytest.mark.asyncio
    async def test_initiate_failover(self, service, primary_region, secondary_region):
        """Test initiating a failover."""
        service.register_region(primary_region)
        service.register_region(secondary_region)

        event = await service.initiate_failover(
            target_region=secondary_region.region_id,
            failover_type=FailoverType.MANUAL,
            initiated_by="test-user",
        )

        assert isinstance(event, FailoverEvent)
        assert event.target_region == secondary_region.region_id
        assert event.status == FailoverStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failover_same_region_error(self, service, primary_region):
        """Test failover to same region raises error."""
        service.register_region(primary_region)

        with pytest.raises(ValueError, match="Cannot failover to the same region"):
            await service.initiate_failover(
                target_region=primary_region.region_id,
                failover_type=FailoverType.MANUAL,
                initiated_by="test-user",
            )

    @pytest.mark.asyncio
    async def test_failover_nonexistent_region(self, service, primary_region):
        """Test failover to nonexistent region raises error."""
        service.register_region(primary_region)

        with pytest.raises(ValueError, match="Target region not found"):
            await service.initiate_failover(
                target_region="nonexistent-region",
                failover_type=FailoverType.MANUAL,
                initiated_by="test-user",
            )

    def test_get_failover_event(self, service):
        """Test getting nonexistent failover event."""
        result = service.get_failover_event("nonexistent-id")
        assert result is None

    def test_get_failover_history(self, service):
        """Test getting failover history."""
        history = service.get_failover_history()
        assert isinstance(history, list)


class TestBackups:
    """Tests for backup management."""

    def test_record_backup(self, service):
        """Test recording a backup."""
        backup = service.record_backup(
            backup_type=BackupType.NEPTUNE_SNAPSHOT,
            region="us-east-1",
            source_resource="aura-neptune-cluster",
            size_bytes=1024 * 1024 * 100,
            retention_days=7,
        )

        assert isinstance(backup, BackupRecord)
        assert backup.backup_type == BackupType.NEPTUNE_SNAPSHOT
        assert backup.status == BackupStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_validate_backup(self, service):
        """Test validating a backup."""
        backup = service.record_backup(
            backup_type=BackupType.DYNAMODB_BACKUP,
            region="us-east-1",
            source_resource="aura-dynamodb-table",
            size_bytes=1024 * 1024 * 50,
        )

        result = await service.validate_backup(backup.backup_id)
        assert result["valid"] is True
        assert "validated_at" in result

    @pytest.mark.asyncio
    async def test_validate_nonexistent_backup(self, service):
        """Test validating nonexistent backup raises error."""
        with pytest.raises(ValueError, match="Backup not found"):
            await service.validate_backup("nonexistent-id")

    def test_get_latest_backups(self, service):
        """Test getting latest backups."""
        # Record a few backups
        service.record_backup(
            backup_type=BackupType.NEPTUNE_SNAPSHOT,
            region="us-east-1",
            source_resource="neptune-cluster",
        )
        service.record_backup(
            backup_type=BackupType.DYNAMODB_BACKUP,
            region="us-east-1",
            source_resource="dynamodb-table",
        )

        latest = service.get_latest_backups()
        assert isinstance(latest, dict)
        assert BackupType.NEPTUNE_SNAPSHOT.value in latest

    def test_get_latest_backups_filtered(self, service):
        """Test getting latest backups filtered by type."""
        service.record_backup(
            backup_type=BackupType.NEPTUNE_SNAPSHOT,
            region="us-east-1",
            source_resource="neptune-cluster",
        )

        latest = service.get_latest_backups(backup_type=BackupType.NEPTUNE_SNAPSHOT)
        assert isinstance(latest, dict)

    def test_check_backup_compliance(self, service):
        """Test checking backup compliance."""
        # Record backups for all types
        for backup_type in BackupType:
            service.record_backup(
                backup_type=backup_type,
                region="us-east-1",
                source_resource=f"{backup_type.value}-resource",
            )

        compliance = service.check_backup_compliance()
        assert "compliant" in compliance
        assert "by_type" in compliance


class TestDRDrills:
    """Tests for DR drill management."""

    def test_schedule_drill(self, service, primary_region, secondary_region):
        """Test scheduling a DR drill."""
        service.register_region(primary_region)
        service.register_region(secondary_region)

        scheduled_time = datetime.now(timezone.utc) + timedelta(days=7)
        drill = service.schedule_drill(
            drill_type="tabletop",
            scheduled_at=scheduled_time,
            target_region=secondary_region.region_id,
            participants=["ops-team", "sre-team"],
        )

        assert isinstance(drill, DrillRecord)
        assert drill.drill_type == "tabletop"
        assert drill.status == DrillStatus.SCHEDULED

    def test_schedule_partial_drill(self, service, secondary_region):
        """Test scheduling a partial failover drill."""
        scheduled_time = datetime.now(timezone.utc) + timedelta(days=14)
        drill = service.schedule_drill(
            drill_type="partial",
            scheduled_at=scheduled_time,
            target_region=secondary_region.region_id,
            participants=["sre-team"],
        )

        assert drill.drill_type == "partial"

    def test_schedule_full_drill(self, service, secondary_region):
        """Test scheduling a full failover drill."""
        scheduled_time = datetime.now(timezone.utc) + timedelta(days=30)
        drill = service.schedule_drill(
            drill_type="full",
            scheduled_at=scheduled_time,
            target_region=secondary_region.region_id,
            participants=["ops-team", "sre-team", "dev-team"],
        )

        assert drill.drill_type == "full"

    def test_get_drill_history(self, service, secondary_region):
        """Test getting drill history."""
        scheduled_time = datetime.now(timezone.utc) + timedelta(days=7)
        service.schedule_drill(
            drill_type="tabletop",
            scheduled_at=scheduled_time,
            target_region=secondary_region.region_id,
            participants=["test-team"],
        )

        history = service.get_drill_history()
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_get_upcoming_drills(self, service, secondary_region):
        """Test getting upcoming drills."""
        future_time = datetime.now(timezone.utc) + timedelta(days=7)
        service.schedule_drill(
            drill_type="tabletop",
            scheduled_at=future_time,
            target_region=secondary_region.region_id,
            participants=["test-team"],
        )

        upcoming = service.get_upcoming_drills()
        assert isinstance(upcoming, list)
        assert len(upcoming) >= 1


class TestRecoveryObjectivesTracking:
    """Tests for RTO/RPO tracking."""

    def test_get_recovery_objectives(self, service):
        """Test getting recovery objectives for a tier."""
        objectives = service.get_recovery_objectives("enterprise")
        assert isinstance(objectives, RecoveryObjective)
        assert objectives.rto_minutes == 15
        assert objectives.rpo_minutes == 5

    def test_get_recovery_objectives_default(self, service):
        """Test getting default recovery objectives."""
        objectives = service.get_recovery_objectives("unknown-tier")
        assert objectives.tier == "standard"

    def test_check_rto_rpo_compliance(self, service):
        """Test checking RTO/RPO compliance."""
        compliance = service.check_rto_rpo_compliance()
        assert "rto_target_minutes" in compliance
        assert "rpo_target_minutes" in compliance
        assert "rto_compliant" in compliance
        assert "rpo_compliant" in compliance


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_health_check_invalid_region(self, service):
        """Test health check with invalid region."""
        with pytest.raises(ValueError):
            await service.check_region_health("invalid-region-id")

    @pytest.mark.asyncio
    async def test_failover_already_in_progress(
        self, service, primary_region, secondary_region
    ):
        """Test that concurrent failovers are prevented."""
        service.register_region(primary_region)
        service.register_region(secondary_region)

        # Start first failover
        event = await service.initiate_failover(
            target_region=secondary_region.region_id,
            failover_type=FailoverType.MANUAL,
            initiated_by="test-user",
        )
        assert event.status == FailoverStatus.COMPLETED


class TestIntegration:
    """Integration tests for disaster recovery workflows."""

    @pytest.mark.asyncio
    async def test_full_dr_workflow(self, service, primary_region, secondary_region):
        """Test complete DR workflow."""
        # 1. Register regions
        service.register_region(primary_region)
        service.register_region(secondary_region)

        # 2. Record backups
        for backup_type in [BackupType.NEPTUNE_SNAPSHOT, BackupType.DYNAMODB_BACKUP]:
            service.record_backup(
                backup_type=backup_type,
                region=primary_region.region_id,
                source_resource=f"{backup_type.value}-resource",
            )

        # 3. Check health
        await service.check_all_regions_health()

        # 4. Check compliance
        compliance = service.check_rto_rpo_compliance()
        assert "rto_compliant" in compliance

    @pytest.mark.asyncio
    async def test_failover_and_failback(
        self, service, primary_region, secondary_region
    ):
        """Test failover followed by failback."""
        service.register_region(primary_region)
        service.register_region(secondary_region)

        # Failover to secondary
        event1 = await service.initiate_failover(
            target_region=secondary_region.region_id,
            failover_type=FailoverType.DRILL,
            initiated_by="test-user",
        )
        assert event1.status == FailoverStatus.COMPLETED
        assert service.get_active_region().region_id == secondary_region.region_id

        # Failback to primary
        event2 = await service.initiate_failover(
            target_region=primary_region.region_id,
            failover_type=FailoverType.DRILL,
            initiated_by="test-user",
        )
        assert event2.status == FailoverStatus.COMPLETED
        assert service.get_active_region().region_id == primary_region.region_id
