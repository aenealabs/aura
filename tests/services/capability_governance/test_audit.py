"""
Tests for capability governance audit module.

Tests audit logging, sampling, and DynamoDB integration.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.capability_governance.audit import (
    AuditConfig,
    AuditRecord,
    CapabilityAuditService,
    get_audit_service,
    reset_audit_service,
)
from src.services.capability_governance.contracts import (
    CapabilityApprovalResponse,
    CapabilityCheckResult,
    CapabilityDecision,
    CapabilityEscalationRequest,
    CapabilityScope,
    CapabilityViolation,
)
from src.services.capability_governance.registry import reset_capability_registry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singletons after each test."""
    yield
    reset_audit_service()
    reset_capability_registry()


@pytest.fixture
def audit_config():
    """Create test audit configuration."""
    return AuditConfig(
        table_name="test-capability-audit",
        escalation_table_name="test-capability-escalations",
        violation_table_name="test-capability-violations",
        enable_async_writes=False,
    )


@pytest.fixture
def audit_service(audit_config):
    """Create audit service with test config."""
    return CapabilityAuditService(config=audit_config)


@pytest.fixture
def mock_dynamodb():
    """Create mock DynamoDB client."""
    mock = MagicMock()
    mock.put_item = MagicMock(return_value={})
    mock.batch_write_item = MagicMock(return_value={"UnprocessedItems": {}})
    mock.query = MagicMock(return_value={"Items": []})
    mock.scan = MagicMock(return_value={"Items": []})
    mock.update_item = MagicMock(return_value={})
    return mock


@pytest.fixture
def check_result():
    """Create a sample check result."""
    return CapabilityCheckResult(
        decision=CapabilityDecision.ALLOW,
        tool_name="semantic_search",
        agent_id="agent-123",
        agent_type="CoderAgent",
        action="execute",
        context="sandbox",
        reason="Policy allows",
        policy_version="1.0.0",
        capability_source="base",
        processing_time_ms=5.5,
    )


# =============================================================================
# AuditConfig Tests
# =============================================================================


class TestAuditConfig:
    """Tests for AuditConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AuditConfig()
        assert config.table_name == "aura-capability-audit"
        assert config.audit_retention_days == 90
        assert config.safe_sample_rate == 0.1
        assert config.critical_sample_rate == 1.0
        assert config.batch_size == 25

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AuditConfig(
            table_name="custom-table",
            audit_retention_days=180,
            safe_sample_rate=0.5,
        )
        assert config.table_name == "custom-table"
        assert config.audit_retention_days == 180
        assert config.safe_sample_rate == 0.5


# =============================================================================
# AuditRecord Tests
# =============================================================================


class TestAuditRecord:
    """Tests for AuditRecord dataclass."""

    def test_basic_creation(self):
        """Test basic audit record creation."""
        record = AuditRecord(
            record_id="rec-123",
            timestamp=datetime.now(timezone.utc),
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="sandbox",
            decision=CapabilityDecision.ALLOW,
            reason="Policy allows",
            policy_version="1.0.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        assert record.record_id == "rec-123"
        assert record.agent_id == "agent-456"
        assert record.sampled is True

    def test_to_dynamodb_item(self):
        """Test DynamoDB item conversion."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            record_id="rec-123",
            timestamp=now,
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="sandbox",
            decision=CapabilityDecision.ALLOW,
            reason="Policy allows",
            policy_version="1.0.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        item = record.to_dynamodb_item()

        assert item["PK"]["S"] == "AUDIT#agent-456"
        assert "SK" in item
        assert item["record_id"]["S"] == "rec-123"
        assert item["decision"]["S"] == "allow"
        assert item["GSI1PK"]["S"] == "TOOL#semantic_search"
        assert item["GSI2PK"]["S"] == "DECISION#allow"

    def test_from_check_result(self, check_result):
        """Test creating audit record from check result."""
        record = AuditRecord.from_check_result(
            check_result,
            session_id="session-789",
        )

        assert record.agent_id == "agent-123"
        assert record.tool_name == "semantic_search"
        assert record.decision == CapabilityDecision.ALLOW
        assert record.session_id == "session-789"


# =============================================================================
# CapabilityAuditService Basic Tests
# =============================================================================


class TestCapabilityAuditServiceBasic:
    """Basic tests for CapabilityAuditService."""

    def test_initialization(self, audit_service):
        """Test service initialization."""
        assert audit_service is not None
        assert audit_service.config is not None

    @pytest.mark.asyncio
    async def test_log_check_allow(self, audit_service, check_result, mock_dynamodb):
        """Test logging an allowed check."""
        audit_service._dynamodb = mock_dynamodb

        logged = await audit_service.log_check(check_result)

        # ALLOW decisions for SAFE tools may be sampled out
        # Force log to ensure it's logged
        logged = await audit_service.log_check(check_result, force_log=True)
        assert logged is True

    @pytest.mark.asyncio
    async def test_log_check_deny_always_logged(self, audit_service, mock_dynamodb):
        """Test that DENY decisions are always logged."""
        audit_service._dynamodb = mock_dynamodb

        deny_result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="dangerous_tool",
            agent_id="agent-123",
            agent_type="CoderAgent",
            action="execute",
            context="sandbox",
            reason="Not authorized",
            policy_version="1.0.0",
            capability_source="base",
        )

        logged = await audit_service.log_check(deny_result)
        assert logged is True

    @pytest.mark.asyncio
    async def test_log_check_escalate_always_logged(self, audit_service, mock_dynamodb):
        """Test that ESCALATE decisions are always logged."""
        audit_service._dynamodb = mock_dynamodb

        escalate_result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="critical_tool",
            agent_id="agent-123",
            agent_type="CoderAgent",
            action="execute",
            context="sandbox",
            reason="Requires approval",
            policy_version="1.0.0",
            capability_source="base",
        )

        logged = await audit_service.log_check(escalate_result)
        assert logged is True

    def test_log_check_sync(self, audit_service, check_result, mock_dynamodb):
        """Test synchronous logging."""
        audit_service._dynamodb = mock_dynamodb

        logged = audit_service.log_check_sync(check_result, force_log=True)
        assert logged is True


# =============================================================================
# Escalation Logging Tests
# =============================================================================


class TestEscalationLogging:
    """Tests for escalation logging."""

    @pytest.mark.asyncio
    async def test_log_escalation(self, audit_service, mock_dynamodb):
        """Test logging an escalation request."""
        audit_service._dynamodb = mock_dynamodb

        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical fix",
        )

        await audit_service.log_escalation(request)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["TableName"] == audit_service.config.escalation_table_name

    @pytest.mark.asyncio
    async def test_log_escalation_response(self, audit_service, mock_dynamodb):
        """Test logging an escalation response."""
        audit_service._dynamodb = mock_dynamodb

        response = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-789",
            scope=CapabilityScope.SINGLE_USE,
            reason="Approved for hotfix",
        )

        await audit_service.log_escalation_response(response)

        mock_dynamodb.update_item.assert_called_once()


# =============================================================================
# Violation Logging Tests
# =============================================================================


class TestViolationLogging:
    """Tests for violation logging."""

    @pytest.mark.asyncio
    async def test_log_violation(self, audit_service, mock_dynamodb):
        """Test logging a violation."""
        audit_service._dynamodb = mock_dynamodb

        violation = CapabilityViolation(
            violation_id="viol-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="delete_repository",
            action="delete",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Not authorized for production",
            severity="critical",
        )

        await audit_service.log_violation(violation)

        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["TableName"] == audit_service.config.violation_table_name


# =============================================================================
# Sampling Tests
# =============================================================================


class TestAuditSampling:
    """Tests for audit sampling."""

    def test_should_sample_safe_tool(self, audit_service):
        """Test sampling rate for SAFE tool."""
        # Run multiple times to check sampling
        sampled_count = 0
        for _ in range(100):
            if audit_service._should_sample("semantic_search"):
                sampled_count += 1

        # With 10% sampling, expect roughly 10 sampled
        assert 0 <= sampled_count <= 30  # Allow some variance

    def test_should_sample_critical_tool(self, audit_service):
        """Test sampling rate for CRITICAL tool."""
        # CRITICAL tools should always be sampled (100%)
        sampled_count = 0
        for _ in range(100):
            if audit_service._should_sample("deploy_to_production"):
                sampled_count += 1

        assert sampled_count == 100


# =============================================================================
# Query Tests
# =============================================================================


class TestAuditQueries:
    """Tests for audit queries."""

    @pytest.mark.asyncio
    async def test_query_agent_audit(self, audit_service, mock_dynamodb):
        """Test querying audit records for an agent."""
        audit_service._dynamodb = mock_dynamodb

        results = await audit_service.query_agent_audit(
            agent_id="agent-123",
            limit=50,
        )

        mock_dynamodb.query.assert_called_once()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_query_agent_audit_with_time_range(
        self, audit_service, mock_dynamodb
    ):
        """Test querying audit records with time range."""
        audit_service._dynamodb = mock_dynamodb

        now = datetime.now(timezone.utc)
        results = await audit_service.query_agent_audit(
            agent_id="agent-123",
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        mock_dynamodb.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_violations(self, audit_service, mock_dynamodb):
        """Test querying violations."""
        audit_service._dynamodb = mock_dynamodb

        results = await audit_service.query_violations(severity="critical")

        mock_dynamodb.query.assert_called_once()


# =============================================================================
# Metrics Tests
# =============================================================================


class TestAuditMetrics:
    """Tests for audit service metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, audit_service, check_result, mock_dynamodb):
        """Test getting audit service metrics."""
        audit_service._dynamodb = mock_dynamodb

        # Log some records
        await audit_service.log_check(check_result, force_log=True)
        await audit_service.log_check(check_result, force_log=True)

        metrics = audit_service.get_metrics()

        assert "records_logged" in metrics
        assert metrics["records_logged"] >= 2
        assert "records_sampled_out" in metrics
        assert "queue_size" in metrics


# =============================================================================
# Async Batch Tests
# =============================================================================


class TestAsyncBatchWriting:
    """Tests for async batch writing."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the service."""
        config = AuditConfig(enable_async_writes=True)
        service = CapabilityAuditService(config=config)

        await service.start()
        assert service._running is True

        await service.stop()
        assert service._running is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestAuditSingleton:
    """Tests for audit service singleton."""

    def test_get_audit_service(self):
        """Test getting global audit service."""
        reset_audit_service()
        s1 = get_audit_service()
        s2 = get_audit_service()
        assert s1 is s2

    def test_reset_audit_service(self):
        """Test resetting global audit service."""
        s1 = get_audit_service()
        reset_audit_service()
        s2 = get_audit_service()
        assert s1 is not s2
