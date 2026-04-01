"""
Unit tests for anomaly_persistence_service.py

Tests the anomaly persistence layer including:
- Enums and data classes
- Mock persistence operations
- Query methods
- Statistics tracking
- Factory functions
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.services.anomaly_persistence_service import (
    AnomalyPersistenceService,
    AnomalyRecord,
    PersistenceMode,
    PersistenceStats,
    QueryResult,
    create_anomaly_persistence_service,
    get_anomaly_persistence_service,
)

# =============================================================================
# ENUM TESTS
# =============================================================================


class TestPersistenceMode:
    """Test PersistenceMode enum."""

    def test_values(self):
        """Test enum values."""
        assert PersistenceMode.AWS.value == "aws"
        assert PersistenceMode.MOCK.value == "mock"

    def test_enum_comparison(self):
        """Test enum comparison."""
        assert PersistenceMode.AWS != PersistenceMode.MOCK


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestAnomalyRecord:
    """Test AnomalyRecord dataclass."""

    @pytest.fixture
    def sample_record(self):
        """Create sample anomaly record."""
        return AnomalyRecord(
            anomaly_id="anom-123",
            timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            severity="critical",
            status="active",
            type="vulnerability",
            title="Test Anomaly",
            description="Test description",
            source="test_source",
            dedup_key="test-dedup-key",
            affected_components=["comp1", "comp2"],
            recommended_action="Fix it",
            cve_id="CVE-2025-1234",
            orchestrator_task_id="task-456",
            hitl_approval_id="approval-789",
            metadata={"key": "value"},
            ttl=1704067200,
        )

    def test_basic_creation(self, sample_record):
        """Test basic record creation."""
        assert sample_record.anomaly_id == "anom-123"
        assert sample_record.severity == "critical"
        assert sample_record.status == "active"

    def test_default_values(self):
        """Test default values."""
        record = AnomalyRecord(
            anomaly_id="anom-1",
            timestamp=datetime.now(timezone.utc),
            severity="low",
            status="active",
            type="security",
            title="Title",
            description="Desc",
            source="src",
            dedup_key="key",
        )
        assert record.affected_components == []
        assert record.recommended_action is None
        assert record.cve_id is None
        assert record.orchestrator_task_id is None
        assert record.hitl_approval_id is None
        assert record.metadata == {}
        assert record.resolved_at is None
        assert record.resolved_by is None
        assert record.ttl is None

    def test_to_dynamo_item_basic(self, sample_record):
        """Test converting to DynamoDB item."""
        item = sample_record.to_dynamo_item()

        assert item["anomaly_id"] == "anom-123"
        assert item["severity"] == "critical"
        assert item["status"] == "active"
        assert "sort_key" in item
        assert "#critical" in item["sort_key"]

    def test_to_dynamo_item_optional_fields(self, sample_record):
        """Test optional fields in DynamoDB item."""
        item = sample_record.to_dynamo_item()

        assert item["recommended_action"] == "Fix it"
        assert item["cve_id"] == "CVE-2025-1234"
        assert item["orchestrator_task_id"] == "task-456"
        assert item["hitl_approval_id"] == "approval-789"
        assert item["metadata"] == {"key": "value"}
        assert item["ttl"] == 1704067200

    def test_to_dynamo_item_no_optional_fields(self):
        """Test DynamoDB item without optional fields."""
        record = AnomalyRecord(
            anomaly_id="anom-1",
            timestamp=datetime.now(timezone.utc),
            severity="low",
            status="active",
            type="security",
            title="Title",
            description="Desc",
            source="src",
            dedup_key="key",
        )
        item = record.to_dynamo_item()

        assert "recommended_action" not in item
        assert "cve_id" not in item
        assert "orchestrator_task_id" not in item
        assert "hitl_approval_id" not in item
        assert "resolved_at" not in item
        assert "resolved_by" not in item
        assert "ttl" not in item

    def test_to_dynamo_item_with_resolved(self):
        """Test DynamoDB item with resolved fields."""
        record = AnomalyRecord(
            anomaly_id="anom-1",
            timestamp=datetime.now(timezone.utc),
            severity="low",
            status="resolved",
            type="security",
            title="Title",
            description="Desc",
            source="src",
            dedup_key="key",
            resolved_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            resolved_by="admin",
        )
        item = record.to_dynamo_item()

        assert "resolved_at" in item
        assert item["resolved_by"] == "admin"

    def test_from_dynamo_item(self, sample_record):
        """Test creating from DynamoDB item."""
        item = sample_record.to_dynamo_item()
        reconstructed = AnomalyRecord.from_dynamo_item(item)

        assert reconstructed.anomaly_id == sample_record.anomaly_id
        assert reconstructed.severity == sample_record.severity
        assert reconstructed.status == sample_record.status
        assert reconstructed.cve_id == sample_record.cve_id

    def test_from_dynamo_item_minimal(self):
        """Test creating from minimal DynamoDB item."""
        item = {
            "anomaly_id": "anom-1",
            "timestamp": "2025-01-15T10:00:00+00:00",
            "severity": "low",
            "status": "active",
            "type": "security",
            "title": "Title",
            "description": "Desc",
            "source": "src",
            "dedup_key": "key",
        }
        record = AnomalyRecord.from_dynamo_item(item)

        assert record.anomaly_id == "anom-1"
        assert record.affected_components == []
        assert record.metadata == {}


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_basic_creation(self):
        """Test basic query result creation."""
        result = QueryResult(items=[], count=0)
        assert result.items == []
        assert result.count == 0
        assert result.last_evaluated_key is None
        assert result.has_more is False

    def test_with_items(self):
        """Test query result with items."""
        record = AnomalyRecord(
            anomaly_id="anom-1",
            timestamp=datetime.now(timezone.utc),
            severity="low",
            status="active",
            type="security",
            title="Title",
            description="Desc",
            source="src",
            dedup_key="key",
        )
        result = QueryResult(
            items=[record],
            count=1,
            last_evaluated_key={"pk": "value"},
            has_more=True,
        )
        assert len(result.items) == 1
        assert result.has_more is True


class TestPersistenceStats:
    """Test PersistenceStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = PersistenceStats()
        assert stats.items_written == 0
        assert stats.items_read == 0
        assert stats.items_updated == 0
        assert stats.write_errors == 0
        assert stats.read_errors == 0
        assert stats.last_write_time is None
        assert stats.last_read_time is None

    def test_update_stats(self):
        """Test updating stats."""
        stats = PersistenceStats()
        stats.items_written = 5
        stats.items_read = 10
        stats.last_write_time = datetime.now(timezone.utc)

        assert stats.items_written == 5
        assert stats.items_read == 10
        assert stats.last_write_time is not None


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestAnomalyPersistenceServiceInit:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        # In test environment without AWS, defaults to MOCK
        service = AnomalyPersistenceService()
        assert service.mode == PersistenceMode.MOCK
        assert service.region == "us-east-1"
        assert "aura-anomalies" in service.table_name
        assert service.ttl_days == 90

    def test_explicit_mock_mode(self):
        """Test explicit mock mode."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        assert service.mode == PersistenceMode.MOCK

    def test_custom_config(self):
        """Test custom configuration."""
        service = AnomalyPersistenceService(
            mode=PersistenceMode.MOCK,
            region="us-west-2",
            table_name="custom-table",
            ttl_days=30,
        )
        assert service.region == "us-west-2"
        assert service.table_name == "custom-table"
        assert service.ttl_days == 30

    def test_env_var_table_name(self):
        """Test table name from environment variable."""
        with patch.dict(os.environ, {"ANOMALY_TABLE_NAME": "env-table"}):
            service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
            assert service.table_name == "env-table"

    def test_env_var_ttl(self):
        """Test TTL from environment variable."""
        with patch.dict(os.environ, {"ANOMALY_TTL_DAYS": "60"}):
            service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
            assert service.ttl_days == 60

    def test_stats_initialization(self):
        """Test stats are initialized."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        assert service.stats.items_written == 0
        assert service.stats.items_read == 0


class TestModeDetection:
    """Test mode detection logic."""

    def test_detect_mock_env(self):
        """Test mock mode from environment."""
        with patch.dict(os.environ, {"ANOMALY_PERSISTENCE_MODE": "mock"}, clear=True):
            service = AnomalyPersistenceService()
            assert service.mode == PersistenceMode.MOCK

    def test_detect_aws_env(self):
        """Test AWS mode from environment."""
        with patch.dict(os.environ, {"ANOMALY_PERSISTENCE_MODE": "aws"}, clear=True):
            service = AnomalyPersistenceService()
            # Note: Will detect AWS mode but may fail to connect
            assert service.mode == PersistenceMode.AWS

    def test_detect_lambda_env(self):
        """Test AWS mode detection from Lambda environment."""
        with patch.dict(
            os.environ, {"AWS_EXECUTION_ENV": "AWS_Lambda_python3.12"}, clear=True
        ):
            service = AnomalyPersistenceService()
            assert service.mode == PersistenceMode.AWS

    def test_detect_ecs_env(self):
        """Test AWS mode detection from ECS environment."""
        with patch.dict(
            os.environ,
            {"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/..."},
            clear=True,
        ):
            service = AnomalyPersistenceService()
            assert service.mode == PersistenceMode.AWS

    def test_detect_irsa_env(self):
        """Test AWS mode detection from IRSA environment."""
        with patch.dict(
            os.environ,
            {"AWS_WEB_IDENTITY_TOKEN_FILE": "/var/run/secrets/token"},
            clear=True,
        ):
            service = AnomalyPersistenceService()
            assert service.mode == PersistenceMode.AWS

    def test_detect_default_mock(self):
        """Test default to mock when no indicators."""
        with patch.dict(os.environ, {}, clear=True):
            service = AnomalyPersistenceService()
            assert service.mode == PersistenceMode.MOCK


class TestTTLCalculation:
    """Test TTL calculation."""

    def test_calculate_ttl(self):
        """Test TTL calculation."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK, ttl_days=30)
        ttl = service._calculate_ttl()

        # TTL should be ~30 days from now
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        assert abs(ttl - int(expected.timestamp())) < 60  # Within 1 minute


class TestTypeConversion:
    """Test DynamoDB type conversion."""

    def test_convert_float_to_decimal(self):
        """Test float to Decimal conversion."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        item = {"score": 0.95}
        converted = service._convert_to_dynamo_types(item)

        assert isinstance(converted["score"], Decimal)
        assert converted["score"] == Decimal("0.95")

    def test_convert_nested_dict(self):
        """Test nested dict conversion."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        item = {"metadata": {"score": 0.5}}
        converted = service._convert_to_dynamo_types(item)

        assert isinstance(converted["metadata"]["score"], Decimal)

    def test_convert_list_with_dicts(self):
        """Test list with dict conversion."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        item = {"items": [{"score": 0.5}, "string"]}
        converted = service._convert_to_dynamo_types(item)

        assert isinstance(converted["items"][0]["score"], Decimal)
        assert converted["items"][1] == "string"

    def test_convert_string_unchanged(self):
        """Test string unchanged."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        item = {"name": "test"}
        converted = service._convert_to_dynamo_types(item)

        assert converted["name"] == "test"


# =============================================================================
# MOCK WRITE OPERATIONS TESTS
# =============================================================================


class TestMockWriteOperations:
    """Test mock write operations."""

    @pytest.fixture
    def service(self):
        """Create mock service."""
        return AnomalyPersistenceService(mode=PersistenceMode.MOCK)

    @pytest.fixture
    def sample_record(self):
        """Create sample record."""
        return AnomalyRecord(
            anomaly_id="anom-123",
            timestamp=datetime.now(timezone.utc),
            severity="critical",
            status="active",
            type="vulnerability",
            title="Test Anomaly",
            description="Test description",
            source="test_source",
            dedup_key="test-dedup-key",
        )

    @pytest.mark.asyncio
    async def test_put_item_mock(self, service, sample_record):
        """Test putting item in mock mode."""
        result = await service.put_item(sample_record)

        assert result is True
        assert service.stats.items_written == 1
        assert sample_record.anomaly_id in service._mock_items

    @pytest.mark.asyncio
    async def test_update_status_mock_success(self, service, sample_record):
        """Test updating status in mock mode."""
        await service.put_item(sample_record)
        result = await service.update_status(
            sample_record.anomaly_id, "resolved", "admin"
        )

        assert result is True
        assert service._mock_items[sample_record.anomaly_id]["status"] == "resolved"
        assert service._mock_items[sample_record.anomaly_id]["resolved_by"] == "admin"
        assert service.stats.items_updated == 1

    @pytest.mark.asyncio
    async def test_update_status_mock_not_found(self, service):
        """Test updating non-existent anomaly."""
        result = await service.update_status("nonexistent", "resolved")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_mock_not_resolved(self, service, sample_record):
        """Test updating status without resolution."""
        await service.put_item(sample_record)
        result = await service.update_status(sample_record.anomaly_id, "investigating")

        assert result is True
        assert (
            service._mock_items[sample_record.anomaly_id]["status"] == "investigating"
        )
        assert "resolved_by" not in service._mock_items[sample_record.anomaly_id]

    @pytest.mark.asyncio
    async def test_link_orchestrator_task_mock(self, service, sample_record):
        """Test linking orchestrator task in mock mode."""
        await service.put_item(sample_record)
        result = await service.link_orchestrator_task(
            sample_record.anomaly_id, "task-456"
        )

        assert result is True
        assert (
            service._mock_items[sample_record.anomaly_id]["orchestrator_task_id"]
            == "task-456"
        )

    @pytest.mark.asyncio
    async def test_link_orchestrator_task_not_found(self, service):
        """Test linking to non-existent anomaly."""
        result = await service.link_orchestrator_task("nonexistent", "task-456")

        assert result is False

    @pytest.mark.asyncio
    async def test_link_hitl_approval_mock(self, service, sample_record):
        """Test linking HITL approval in mock mode."""
        await service.put_item(sample_record)
        result = await service.link_hitl_approval(
            sample_record.anomaly_id, "approval-789"
        )

        assert result is True
        assert (
            service._mock_items[sample_record.anomaly_id]["hitl_approval_id"]
            == "approval-789"
        )

    @pytest.mark.asyncio
    async def test_link_hitl_approval_not_found(self, service):
        """Test linking HITL to non-existent anomaly."""
        result = await service.link_hitl_approval("nonexistent", "approval-789")

        assert result is False


# =============================================================================
# MOCK READ OPERATIONS TESTS
# =============================================================================


class TestMockReadOperations:
    """Test mock read operations."""

    @pytest.fixture
    def service(self):
        """Create mock service with sample data."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        return service

    @pytest.fixture
    def populated_service(self, service):
        """Create service with sample data."""
        # Add some mock items
        now = datetime.now(timezone.utc)
        items = [
            {
                "anomaly_id": "anom-1",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
                "severity": "critical",
                "status": "active",
                "type": "vulnerability",
                "title": "Critical Issue",
                "description": "Desc",
                "source": "src",
                "dedup_key": "key-1",
            },
            {
                "anomaly_id": "anom-2",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "created_at": (now - timedelta(hours=2)).isoformat(),
                "severity": "high",
                "status": "active",
                "type": "security",
                "title": "High Issue",
                "description": "Desc",
                "source": "src",
                "dedup_key": "key-2",
            },
            {
                "anomaly_id": "anom-3",
                "timestamp": (now - timedelta(hours=48)).isoformat(),
                "created_at": (now - timedelta(hours=48)).isoformat(),
                "severity": "critical",
                "status": "resolved",
                "type": "vulnerability",
                "title": "Old Issue",
                "description": "Desc",
                "source": "src",
                "dedup_key": "key-1",  # Same dedup key as anom-1
            },
        ]
        for item in items:
            service._mock_items[item["anomaly_id"]] = item
        return service

    @pytest.mark.asyncio
    async def test_get_anomaly_mock(self, populated_service):
        """Test getting anomaly in mock mode."""
        result = await populated_service.get_anomaly("anom-1")

        assert result is not None
        assert result.anomaly_id == "anom-1"
        assert result.severity == "critical"
        assert populated_service.stats.items_read == 1

    @pytest.mark.asyncio
    async def test_get_anomaly_not_found(self, populated_service):
        """Test getting non-existent anomaly."""
        result = await populated_service.get_anomaly("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_query_by_status_mock(self, populated_service):
        """Test querying by status in mock mode."""
        result = await populated_service.query_by_status("active")

        assert result.count == 2
        assert all(r.status == "active" for r in result.items)

    @pytest.mark.asyncio
    async def test_query_by_status_mock_no_results(self, populated_service):
        """Test querying by status with no results."""
        result = await populated_service.query_by_status("nonexistent")

        assert result.count == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_query_by_severity_mock(self, populated_service):
        """Test querying by severity in mock mode."""
        result = await populated_service.query_by_severity("critical", hours=24)

        # Should only get recent critical (not the 48-hour old one)
        assert result.count == 1
        assert result.items[0].anomaly_id == "anom-1"

    @pytest.mark.asyncio
    async def test_query_by_severity_mock_longer_window(self, populated_service):
        """Test querying by severity with longer window."""
        result = await populated_service.query_by_severity("critical", hours=72)

        # Should get both critical anomalies
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_check_dedup_window_mock(self, populated_service):
        """Test dedup window check in mock mode."""
        result = await populated_service.check_dedup_window("key-1", hours=1)

        # Should only get recent one, not the 48-hour old one
        assert len(result) == 1
        assert result[0].anomaly_id == "anom-1"

    @pytest.mark.asyncio
    async def test_check_dedup_window_mock_longer_window(self, populated_service):
        """Test dedup window with longer window."""
        result = await populated_service.check_dedup_window("key-1", hours=72)

        # Should get both with same dedup key
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_query_recent_mock(self, populated_service):
        """Test querying recent anomalies in mock mode."""
        result = await populated_service.query_recent(hours=24)

        # Should get the two recent ones
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_query_recent_mock_sorted(self, populated_service):
        """Test recent query is sorted by timestamp."""
        result = await populated_service.query_recent(hours=24)

        # Should be sorted by timestamp descending
        if len(result.items) > 1:
            assert result.items[0].timestamp >= result.items[1].timestamp

    @pytest.mark.asyncio
    async def test_query_recent_mock_with_limit(self, populated_service):
        """Test recent query with limit."""
        result = await populated_service.query_recent(hours=72, limit=1)

        assert result.count == 1


# =============================================================================
# SUMMARY AND STATS TESTS
# =============================================================================


class TestSummaryAndStats:
    """Test summary and statistics methods."""

    @pytest.fixture
    def populated_service(self):
        """Create service with sample data."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        now = datetime.now(timezone.utc)

        items = [
            {
                "anomaly_id": f"anom-{i}",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
                "severity": "critical" if i % 2 == 0 else "high",
                "status": "active" if i < 3 else "resolved",
                "type": "vulnerability" if i % 2 == 0 else "security",
                "title": f"Issue {i}",
                "description": "Desc",
                "source": "src",
                "dedup_key": f"key-{i}",
            }
            for i in range(5)
        ]
        for item in items:
            service._mock_items[item["anomaly_id"]] = item
        return service

    @pytest.mark.asyncio
    async def test_get_anomaly_summary(self, populated_service):
        """Test getting anomaly summary."""
        summary = await populated_service.get_anomaly_summary(hours=24)

        assert summary["total"] == 5
        assert summary["time_window_hours"] == 24
        assert "by_status" in summary
        assert "by_severity" in summary
        assert "by_type" in summary

    @pytest.mark.asyncio
    async def test_get_anomaly_summary_breakdown(self, populated_service):
        """Test summary breakdown counts."""
        summary = await populated_service.get_anomaly_summary(hours=24)

        # Check status breakdown
        assert summary["by_status"]["active"] == 3
        assert summary["by_status"]["resolved"] == 2

        # Check severity breakdown
        assert summary["by_severity"]["critical"] == 3  # 0, 2, 4
        assert summary["by_severity"]["high"] == 2  # 1, 3

    def test_get_stats(self):
        """Test getting service statistics."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK, ttl_days=60)
        service.stats.items_written = 10
        service.stats.items_read = 20
        service.stats.last_write_time = datetime.now(timezone.utc)

        stats = service.get_stats()

        assert stats["mode"] == "mock"
        assert stats["ttl_days"] == 60
        assert stats["items_written"] == 10
        assert stats["items_read"] == 20
        assert stats["last_write_time"] is not None

    def test_get_stats_no_times(self):
        """Test getting stats without times."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        stats = service.get_stats()

        assert stats["last_write_time"] is None
        assert stats["last_read_time"] is None


# =============================================================================
# MOCK HELPERS TESTS
# =============================================================================


class TestMockHelpers:
    """Test mock helper methods."""

    def test_get_mock_items(self):
        """Test getting mock items."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        service._mock_items["test"] = {"key": "value"}

        items = service.get_mock_items()

        assert "test" in items
        # Should be a copy
        items["new"] = "value"
        assert "new" not in service._mock_items

    def test_clear_mock_items(self):
        """Test clearing mock items."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        service._mock_items["test"] = {"key": "value"}

        service.clear_mock_items()

        assert len(service._mock_items) == 0


# =============================================================================
# PERSIST ANOMALY TESTS
# =============================================================================


class TestPersistAnomaly:
    """Test persist_anomaly callback method."""

    @pytest.fixture
    def service(self):
        """Create mock service."""
        return AnomalyPersistenceService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_persist_invalid_type(self, service):
        """Test persisting invalid type."""
        result = await service.persist_anomaly("not an anomaly")

        assert result is False

    @pytest.mark.asyncio
    async def test_persist_valid_anomaly(self, service):
        """Test persisting valid anomaly event."""
        from src.services.anomaly_detection_service import (
            AnomalyEvent,
            AnomalySeverity,
            AnomalyStatus,
            AnomalyType,
        )

        anomaly = AnomalyEvent(
            id="test-id",
            type=AnomalyType.SECURITY_EVENT,
            severity=AnomalySeverity.HIGH,
            status=AnomalyStatus.DETECTED,
            title="Test",
            description="Test description",
            source="test",
            dedup_key="test-key",
            timestamp=datetime.now(timezone.utc),
        )

        result = await service.persist_anomaly(anomaly)

        assert result is True
        assert "test-id" in service._mock_items


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_get_singleton(self):
        """Test singleton getter."""
        # Reset singleton
        import src.services.anomaly_persistence_service as module

        module._persistence_instance = None

        service1 = get_anomaly_persistence_service()
        service2 = get_anomaly_persistence_service()

        assert service1 is service2

    def test_create_new_instance(self):
        """Test creating new instance."""
        service = create_anomaly_persistence_service(
            mode=PersistenceMode.MOCK,
            region="us-west-2",
            table_name="test-table",
            ttl_days=30,
        )

        assert service.mode == PersistenceMode.MOCK
        assert service.region == "us-west-2"
        assert service.table_name == "test-table"
        assert service.ttl_days == 30


# =============================================================================
# LAZY INITIALIZATION TESTS
# =============================================================================


class TestLazyInitialization:
    """Test lazy initialization of clients."""

    def test_client_property_mock(self):
        """Test client property in mock mode returns None."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        assert service.client is None

    def test_table_property_mock(self):
        """Test table property in mock mode returns None."""
        service = AnomalyPersistenceService(mode=PersistenceMode.MOCK)
        assert service.table is None

    @patch("boto3.client")
    def test_client_property_aws(self, mock_boto_client):
        """Test client property in AWS mode."""
        service = AnomalyPersistenceService(mode=PersistenceMode.AWS)
        _ = service.client

        mock_boto_client.assert_called_with("dynamodb", region_name="us-east-1")

    @patch("boto3.resource")
    def test_table_property_aws(self, mock_boto_resource):
        """Test table property in AWS mode."""
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        service = AnomalyPersistenceService(mode=PersistenceMode.AWS)
        table = service.table

        assert table == mock_table
