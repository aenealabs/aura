"""
Tests for HoneypotDetector (ADR-072).

Tests honeypot capability detection and automatic quarantine.
Honeypots are the ONLY detection mechanism that can trigger automatic quarantine
without HITL approval (zero false positives by design).
"""

import pytest

from src.services.capability_governance import (
    AlertSeverity,
    AnomalyType,
    HoneypotCapability,
    InvocationContext,
    QuarantineReason,
)
from src.services.capability_governance.honeypot_detector import (
    HONEYPOT_CAPABILITIES,
    HoneypotDetector,
    get_honeypot_detector,
    reset_honeypot_detector,
)


class TestHoneypotCapabilities:
    """Tests for predefined honeypot capabilities."""

    def test_default_honeypots_defined(self):
        """Test default honeypot capabilities are defined."""
        assert len(HONEYPOT_CAPABILITIES) >= 5

        expected_honeypots = [
            "admin_override",
            "export_all_credentials",
            "disable_audit_logging",
            "bypass_hitl_approval",
            "access_all_tenants",
        ]

        for name in expected_honeypots:
            assert name in HONEYPOT_CAPABILITIES

    def test_all_honeypots_are_critical(self):
        """Test all honeypots have CRITICAL classification."""
        for name, honeypot in HONEYPOT_CAPABILITIES.items():
            assert honeypot.classification == "CRITICAL", f"{name} is not CRITICAL"

    def test_all_honeypots_have_no_legitimate_use(self):
        """Test all honeypots have no legitimate use."""
        for name, honeypot in HONEYPOT_CAPABILITIES.items():
            assert honeypot.legitimate_use is False, f"{name} has legitimate use"

    def test_all_honeypots_are_p1_severity(self):
        """Test all honeypots have P1 alert severity."""
        for name, honeypot in HONEYPOT_CAPABILITIES.items():
            assert honeypot.alert_severity == AlertSeverity.P1, f"{name} is not P1"


class TestHoneypotDetectorBasic:
    """Basic tests for HoneypotDetector."""

    def test_is_honeypot_returns_true_for_honeypots(self):
        """Test is_honeypot returns True for honeypot tools."""
        detector = HoneypotDetector()

        assert detector.is_honeypot("admin_override") is True
        assert detector.is_honeypot("export_all_credentials") is True

    def test_is_honeypot_returns_false_for_normal_tools(self):
        """Test is_honeypot returns False for normal tools."""
        detector = HoneypotDetector()

        assert detector.is_honeypot("semantic_search") is False
        assert detector.is_honeypot("read_file") is False

    def test_get_honeypot_returns_capability(self):
        """Test get_honeypot returns capability definition."""
        detector = HoneypotDetector()

        honeypot = detector.get_honeypot("admin_override")
        assert honeypot is not None
        assert honeypot.name == "admin_override"
        assert honeypot.alert_severity == AlertSeverity.P1

    def test_get_honeypot_returns_none_for_normal_tools(self):
        """Test get_honeypot returns None for normal tools."""
        detector = HoneypotDetector()

        assert detector.get_honeypot("semantic_search") is None

    def test_list_honeypots_returns_all(self):
        """Test list_honeypots returns all defined honeypots."""
        detector = HoneypotDetector()

        honeypots = detector.list_honeypots()
        assert len(honeypots) == len(HONEYPOT_CAPABILITIES)


class TestHoneypotDetectorCheck:
    """Tests for honeypot access checking."""

    @pytest.mark.asyncio
    async def test_non_honeypot_not_triggered(self):
        """Test non-honeypot tool does not trigger."""
        detector = HoneypotDetector()

        result = await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="semantic_search",
        )

        assert result.triggered is False
        assert result.honeypot_name is None
        assert result.action_taken is None

    @pytest.mark.asyncio
    async def test_honeypot_triggered(self):
        """Test honeypot access triggers alert and quarantine."""
        detector = HoneypotDetector()

        result = await detector.check_honeypot_access(
            agent_id="agent-malicious-001",
            tool_name="admin_override",
        )

        assert result.triggered is True
        assert result.honeypot_name == "admin_override"
        assert result.action_taken == "quarantine"
        assert result.agent_id == "agent-malicious-001"

    @pytest.mark.asyncio
    async def test_honeypot_quarantines_agent(self):
        """Test honeypot access quarantines the agent."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-malicious-001",
            tool_name="export_all_credentials",
        )

        assert detector.is_quarantined("agent-malicious-001") is True

    @pytest.mark.asyncio
    async def test_honeypot_logs_forensic_event(self):
        """Test honeypot access logs forensic data."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-malicious-001",
            tool_name="disable_audit_logging",
        )

        logs = detector.get_forensic_logs(agent_id="agent-malicious-001")
        assert len(logs) >= 1
        assert logs[0]["tool_name"] == "disable_audit_logging"

    @pytest.mark.asyncio
    async def test_honeypot_with_context(self):
        """Test honeypot access with invocation context."""
        detector = HoneypotDetector()

        context = InvocationContext(
            session_id="sess-001",
            parent_agent="orchestrator-001",
            environment="production",
            tenant_id="tenant-123",
        )

        result = await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="bypass_hitl_approval",
            context=context,
        )

        assert result.triggered is True

        # Check context is in forensic logs
        logs = detector.get_forensic_logs(agent_id="agent-001")
        assert logs[0]["context"]["session_id"] == "sess-001"

    @pytest.mark.asyncio
    async def test_honeypot_creates_alert(self):
        """Test honeypot access creates security alert."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="access_all_tenants",
        )

        alerts = detector.get_alert_history()
        assert len(alerts) >= 1
        assert alerts[-1]["event_type"] == "HONEYPOT_TRIGGERED"
        assert alerts[-1]["severity"] == "P1"


class TestHoneypotDetectorQuarantine:
    """Tests for quarantine functionality."""

    @pytest.mark.asyncio
    async def test_quarantine_record_created(self):
        """Test quarantine record is created on trigger."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )

        record = detector.get_quarantine_record("agent-001")
        assert record is not None
        assert record.agent_id == "agent-001"
        assert record.reason == QuarantineReason.HONEYPOT_TRIGGERED
        assert record.triggered_by == "admin_override"
        assert record.is_active is True

    @pytest.mark.asyncio
    async def test_release_from_quarantine(self):
        """Test agent can be released from quarantine."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )

        assert detector.is_quarantined("agent-001") is True

        released = await detector.release_from_quarantine(
            agent_id="agent-001",
            released_by="security-admin@example.com",
            notes="Investigation complete, false positive due to misconfiguration",
        )

        assert released is True
        assert detector.is_quarantined("agent-001") is False

        record = detector.get_quarantine_record("agent-001")
        assert record.released_at is not None
        assert record.hitl_approved_by == "security-admin@example.com"

    @pytest.mark.asyncio
    async def test_release_nonexistent_agent_returns_false(self):
        """Test releasing non-quarantined agent returns False."""
        detector = HoneypotDetector()

        released = await detector.release_from_quarantine(
            agent_id="agent-not-quarantined",
            released_by="admin@example.com",
        )

        assert released is False

    @pytest.mark.asyncio
    async def test_double_release_returns_false(self):
        """Test releasing already-released agent returns False."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )

        await detector.release_from_quarantine(
            agent_id="agent-001",
            released_by="admin@example.com",
        )

        # Second release should return False
        released = await detector.release_from_quarantine(
            agent_id="agent-001",
            released_by="admin@example.com",
        )

        assert released is False


class TestHoneypotDetectorAnomalyResult:
    """Tests for integration with anomaly scoring."""

    @pytest.mark.asyncio
    async def test_get_anomaly_result_not_honeypot(self):
        """Test anomaly result for non-honeypot tool."""
        detector = HoneypotDetector()

        result = await detector.get_anomaly_result(
            agent_id="agent-001",
            tool_name="semantic_search",
        )

        assert result.is_anomaly is False
        assert result.score == 0.0
        assert result.anomaly_type == AnomalyType.HONEYPOT

    @pytest.mark.asyncio
    async def test_get_anomaly_result_honeypot(self):
        """Test anomaly result for honeypot tool."""
        detector = HoneypotDetector()

        result = await detector.get_anomaly_result(
            agent_id="agent-001",
            tool_name="admin_override",
        )

        assert result.is_anomaly is True
        assert result.score == 1.0
        assert result.anomaly_type == AnomalyType.HONEYPOT
        assert result.details["triggered"] is True


class TestHoneypotDetectorCustomCapabilities:
    """Tests for custom honeypot capabilities."""

    def test_custom_honeypots(self):
        """Test detector with custom honeypot capabilities."""
        custom_honeypots = {
            "custom_trap": HoneypotCapability(
                name="custom_trap",
                description="A custom trap capability",
            ),
        }

        detector = HoneypotDetector(capabilities=custom_honeypots)

        assert detector.is_honeypot("custom_trap") is True
        assert detector.is_honeypot("admin_override") is False  # Not in custom set

    @pytest.mark.asyncio
    async def test_custom_honeypot_triggers(self):
        """Test custom honeypot triggers correctly."""
        custom_honeypots = {
            "secret_trap": HoneypotCapability(
                name="secret_trap",
                description="Secret trap for testing",
            ),
        }

        detector = HoneypotDetector(capabilities=custom_honeypots)

        result = await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="secret_trap",
        )

        assert result.triggered is True
        assert result.honeypot_name == "secret_trap"


class TestHoneypotDetectorHistory:
    """Tests for alert and forensic history."""

    @pytest.mark.asyncio
    async def test_alert_history_limit(self):
        """Test alert history respects limit."""
        detector = HoneypotDetector()

        # Trigger multiple honeypots
        for i in range(5):
            await detector.check_honeypot_access(
                agent_id=f"agent-{i}",
                tool_name="admin_override",
            )

        alerts = detector.get_alert_history(limit=3)
        assert len(alerts) == 3

    @pytest.mark.asyncio
    async def test_forensic_logs_filter_by_agent(self):
        """Test forensic logs can be filtered by agent."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )
        await detector.check_honeypot_access(
            agent_id="agent-002",
            tool_name="export_all_credentials",
        )

        logs_001 = detector.get_forensic_logs(agent_id="agent-001")
        logs_002 = detector.get_forensic_logs(agent_id="agent-002")

        assert len(logs_001) == 1
        assert logs_001[0]["agent_id"] == "agent-001"
        assert len(logs_002) == 1
        assert logs_002[0]["agent_id"] == "agent-002"

    @pytest.mark.asyncio
    async def test_forensic_logs_all_agents(self):
        """Test forensic logs without filter returns all."""
        detector = HoneypotDetector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )
        await detector.check_honeypot_access(
            agent_id="agent-002",
            tool_name="admin_override",
        )

        all_logs = detector.get_forensic_logs()
        assert len(all_logs) == 2


class TestHoneypotDetectorSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_honeypot_detector()
        detector1 = get_honeypot_detector()
        detector2 = get_honeypot_detector()
        assert detector1 is detector2

    def test_reset_creates_new_instance(self):
        """Test reset creates new instance."""
        detector1 = get_honeypot_detector()
        reset_honeypot_detector()
        detector2 = get_honeypot_detector()
        assert detector1 is not detector2

    @pytest.mark.asyncio
    async def test_reset_clears_quarantine_state(self):
        """Test reset clears quarantine state."""
        detector = get_honeypot_detector()

        await detector.check_honeypot_access(
            agent_id="agent-001",
            tool_name="admin_override",
        )

        assert detector.is_quarantined("agent-001") is True

        reset_honeypot_detector()
        new_detector = get_honeypot_detector()

        assert new_detector.is_quarantined("agent-001") is False
