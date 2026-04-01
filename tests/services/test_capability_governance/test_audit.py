"""
Tests for capability governance audit service.

Tests audit logging, sampling, batch writes, and DynamoDB integration.
"""

from datetime import datetime, timezone

import pytest

from src.services.capability_governance import (
    CapabilityCheckResult,
    CapabilityDecision,
    CapabilityEscalationRequest,
    CapabilityViolation,
)
from src.services.capability_governance.audit import (
    AuditConfig,
    AuditRecord,
    CapabilityAuditService,
    get_audit_service,
)


class TestAuditConfig:
    """Test AuditConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AuditConfig()
        assert config.table_name == "aura-capability-audit"
        assert config.audit_retention_days == 90
        assert config.safe_sample_rate == 0.1
        assert config.monitoring_sample_rate == 1.0
        assert config.batch_size == 25
        assert config.enable_async_writes is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AuditConfig(
            table_name="custom-audit-table",
            safe_sample_rate=0.5,
            batch_size=50,
        )
        assert config.table_name == "custom-audit-table"
        assert config.safe_sample_rate == 0.5
        assert config.batch_size == 50


class TestAuditRecord:
    """Test AuditRecord dataclass."""

    def test_creation(self):
        """Test creating an audit record."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            record_id="test-001",
            timestamp=now,
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="Allowed by policy",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        assert record.record_id == "test-001"
        assert record.decision == CapabilityDecision.ALLOW

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item format."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            record_id="test-001",
            timestamp=now,
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        item = record.to_dynamodb_item()

        assert item["PK"]["S"] == "AUDIT#agent-001"
        assert item["record_id"]["S"] == "test-001"
        assert item["decision"]["S"] == "allow"
        assert item["GSI1PK"]["S"] == "TOOL#semantic_search"
        assert "TTL" in item

    def test_to_dynamodb_item_with_optional_fields(self):
        """Test DynamoDB item includes optional fields when present."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            record_id="test-001",
            timestamp=now,
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=5.0,
            parent_agent_id="parent-001",
            execution_id="exec-001",
            session_id="session-001",
        )
        item = record.to_dynamodb_item()

        assert "parent_agent_id" in item
        assert item["parent_agent_id"]["S"] == "parent-001"
        assert "execution_id" in item
        assert "session_id" in item

    def test_from_check_result(self, sample_check_result: CapabilityCheckResult):
        """Test creating audit record from check result."""
        record = AuditRecord.from_check_result(
            sample_check_result,
            session_id="test-session",
        )

        assert record.agent_id == sample_check_result.agent_id
        assert record.tool_name == sample_check_result.tool_name
        assert record.decision == sample_check_result.decision
        assert record.session_id == "test-session"


class TestCapabilityAuditService:
    """Test CapabilityAuditService."""

    def test_initialization(self):
        """Test service initialization."""
        service = CapabilityAuditService()
        assert service.config is not None
        assert service._records_logged == 0
        assert service._running is False

    def test_initialization_with_config(self, audit_config: AuditConfig):
        """Test initialization with custom config."""
        service = CapabilityAuditService(config=audit_config)
        assert service.config.table_name == "test-capability-audit"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the service."""
        service = CapabilityAuditService()
        await service.start()
        assert service._running is True
        await service.stop()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test that start is idempotent."""
        service = CapabilityAuditService()
        await service.start()
        task1 = service._flush_task
        await service.start()
        assert service._flush_task is task1
        await service.stop()


class TestAuditServiceLogging:
    """Test audit service logging functionality."""

    @pytest.mark.asyncio
    async def test_log_check_allow_sampled(self, mock_dynamodb_client):
        """Test logging allowed check with sampling."""
        config = AuditConfig(
            safe_sample_rate=1.0,  # Always log for test
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="semantic_search",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged = await service.log_check(result)
        assert logged is True
        assert service._records_logged == 1
        mock_dynamodb_client.put_item.assert_called()

    @pytest.mark.asyncio
    async def test_log_check_deny_always_logged(self, mock_dynamodb_client):
        """Test that denials are always logged."""
        config = AuditConfig(
            safe_sample_rate=0.0,  # No sampling for SAFE
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="semantic_search",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="production",
            reason="Context not allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged = await service.log_check(result)
        assert logged is True
        mock_dynamodb_client.put_item.assert_called()

    @pytest.mark.asyncio
    async def test_log_check_escalate_always_logged(self, mock_dynamodb_client):
        """Test that escalations are always logged."""
        config = AuditConfig(
            safe_sample_rate=0.0,
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="provision_sandbox",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Requires HITL",
            policy_version="1.0",
            capability_source="base",
        )

        logged = await service.log_check(result)
        assert logged is True

    @pytest.mark.asyncio
    async def test_log_check_force_log(self, mock_dynamodb_client):
        """Test force logging bypasses sampling."""
        config = AuditConfig(
            safe_sample_rate=0.0,
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="semantic_search",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged = await service.log_check(result, force_log=True)
        assert logged is True

    @pytest.mark.asyncio
    async def test_log_check_sampled_out(self):
        """Test that some checks are sampled out."""
        config = AuditConfig(
            safe_sample_rate=0.0,  # Never log SAFE tools
            enable_async_writes=False,
        )
        service = CapabilityAuditService(config=config)

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="semantic_search",  # SAFE tool
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged = await service.log_check(result)
        assert logged is False
        assert service._records_sampled_out == 1


class TestAuditServiceSync:
    """Test synchronous logging functionality."""

    def test_log_check_sync_queues_record(self):
        """Test synchronous logging queues record."""
        config = AuditConfig(
            enable_async_writes=True,
        )
        service = CapabilityAuditService(config=config)

        result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="test_tool",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Denied",
            policy_version="1.0",
            capability_source="base",
        )

        logged = service.log_check_sync(result)
        assert logged is True
        assert service._records_logged == 1
        assert service._audit_queue.qsize() == 1

    def test_log_check_sync_sampled_out(self):
        """Test synchronous logging respects sampling."""
        config = AuditConfig(
            safe_sample_rate=0.0,
        )
        service = CapabilityAuditService(config=config)

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="semantic_search",
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged = service.log_check_sync(result)
        assert logged is False
        assert service._records_sampled_out == 1


class TestAuditServiceEscalations:
    """Test escalation logging."""

    @pytest.mark.asyncio
    async def test_log_escalation(
        self,
        mock_dynamodb_client,
        sample_escalation_request: CapabilityEscalationRequest,
    ):
        """Test logging escalation request."""
        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        await service.log_escalation(sample_escalation_request)
        mock_dynamodb_client.put_item.assert_called_once()

        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]["Item"]
        assert "ESCALATION#" in item["PK"]["S"]
        assert item["status"]["S"] == "pending"

    @pytest.mark.asyncio
    async def test_log_escalation_handles_error(self, mock_dynamodb_client):
        """Test error handling in escalation logging."""
        mock_dynamodb_client.put_item.side_effect = Exception("DynamoDB error")

        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        request = CapabilityEscalationRequest(
            request_id="test-001",
            agent_id="agent-001",
            agent_type="CoderAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Test",
        )

        # Should not raise
        await service.log_escalation(request)
        assert service._write_errors == 1


class TestAuditServiceViolations:
    """Test violation logging."""

    @pytest.mark.asyncio
    async def test_log_violation(self, mock_dynamodb_client):
        """Test logging a violation."""
        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        violation = CapabilityViolation(
            violation_id="viol-001",
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            context="development",
            decision=CapabilityDecision.DENY,
            reason="Not permitted",
            severity="high",
        )

        await service.log_violation(violation)
        mock_dynamodb_client.put_item.assert_called_once()

        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]["Item"]
        assert "VIOLATION#" in item["PK"]["S"]
        assert item["severity"]["S"] == "high"


class TestAuditServiceQueries:
    """Test audit query functionality."""

    @pytest.mark.asyncio
    async def test_query_agent_audit(self, mock_dynamodb_client):
        """Test querying agent audit records."""
        mock_dynamodb_client.query.return_value = {
            "Items": [
                {"record_id": {"S": "test-001"}},
                {"record_id": {"S": "test-002"}},
            ]
        }

        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        records = await service.query_agent_audit("agent-001", limit=10)
        assert len(records) == 2
        mock_dynamodb_client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_agent_audit_with_time_range(self, mock_dynamodb_client):
        """Test querying with time range filter."""
        mock_dynamodb_client.query.return_value = {"Items": []}

        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)

        await service.query_agent_audit("agent-001", start_time=start, end_time=end)
        call_args = mock_dynamodb_client.query.call_args
        assert ":start" in call_args[1]["ExpressionAttributeValues"]
        assert ":end" in call_args[1]["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_query_violations(self, mock_dynamodb_client):
        """Test querying violations."""
        mock_dynamodb_client.query.return_value = {
            "Items": [{"violation_id": {"S": "viol-001"}}]
        }

        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        violations = await service.query_violations(severity="high")
        assert len(violations) == 1
        mock_dynamodb_client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_violations_no_severity_filter(self, mock_dynamodb_client):
        """Test querying all violations without severity filter."""
        mock_dynamodb_client.scan.return_value = {"Items": []}

        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        await service.query_violations()
        mock_dynamodb_client.scan.assert_called_once()


class TestAuditServiceMetrics:
    """Test audit service metrics."""

    def test_get_metrics(self):
        """Test getting service metrics."""
        service = CapabilityAuditService()
        service._records_logged = 100
        service._records_sampled_out = 50
        service._batch_writes = 10
        service._write_errors = 2

        metrics = service.get_metrics()
        assert metrics["records_logged"] == 100
        assert metrics["records_sampled_out"] == 50
        assert metrics["batch_writes"] == 10
        assert metrics["write_errors"] == 2
        assert "queue_size" in metrics
        assert "buffer_size" in metrics


class TestAuditServiceSingleton:
    """Test global audit service singleton."""

    def test_get_audit_service_singleton(self):
        """Test global singleton."""
        service1 = get_audit_service()
        service2 = get_audit_service()
        assert service1 is service2


class TestAuditServiceSampling:
    """Test sampling logic for different tool classifications."""

    @pytest.mark.parametrize(
        "sample_rate,expected_samples",
        [
            (1.0, 10),  # 100% rate should log all
            (0.0, 0),  # 0% rate should log none
        ],
    )
    @pytest.mark.asyncio
    async def test_sampling_rates(
        self,
        mock_dynamodb_client,
        sample_rate: float,
        expected_samples: int,
    ):
        """Test different sampling rates."""
        config = AuditConfig(
            safe_sample_rate=sample_rate,
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="semantic_search",  # SAFE tool
            agent_id="agent-001",
            agent_type="CoderAgent",
            action="execute",
            context="development",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )

        logged_count = 0
        for _ in range(10):
            if await service.log_check(result):
                logged_count += 1

        assert logged_count == expected_samples


class TestAuditServiceBatch:
    """Test batch writing functionality."""

    @pytest.mark.asyncio
    async def test_flush_batch(self, mock_dynamodb_client):
        """Test batch flushing."""
        config = AuditConfig(
            enable_async_writes=False,
        )
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        # Add records to buffer
        now = datetime.now(timezone.utc)
        for i in range(5):
            record = AuditRecord(
                record_id=f"test-{i:03d}",
                timestamp=now,
                agent_id="agent-001",
                agent_type="CoderAgent",
                tool_name="semantic_search",
                action="execute",
                context="development",
                decision=CapabilityDecision.ALLOW,
                reason="Allowed",
                policy_version="1.0",
                capability_source="base",
                processing_time_ms=1.0,
            )
            service._batch_buffer.append(record)

        await service._flush_batch()
        mock_dynamodb_client.batch_write_item.assert_called()
        assert len(service._batch_buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_empty_batch(self, mock_dynamodb_client):
        """Test flushing empty batch does nothing."""
        config = AuditConfig()
        service = CapabilityAuditService(
            config=config,
            dynamodb_client=mock_dynamodb_client,
        )

        await service._flush_batch()
        mock_dynamodb_client.batch_write_item.assert_not_called()
