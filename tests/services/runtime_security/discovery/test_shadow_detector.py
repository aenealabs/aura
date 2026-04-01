"""
Tests for the Shadow Agent Detector.

Covers ShadowDetector scan behaviour, severity classification
(INFO / WARNING / HIGH / CRITICAL), auto-quarantine, quarantine
release, ShadowAlert frozen dataclass serialization, and tool
category detection logic.
"""

from datetime import datetime, timezone

import pytest

from src.services.runtime_security.discovery import (
    AgentDiscoveryService,
    ShadowAlert,
    ShadowAlertSeverity,
    ShadowDetector,
)
from src.services.runtime_security.discovery.agent_discovery import AgentStatus

# ---------------------------------------------------------------------------
# ShadowAlert frozen dataclass
# ---------------------------------------------------------------------------


class TestShadowAlert:
    """Tests for the ShadowAlert frozen dataclass."""

    def _make_alert(self, **overrides):
        """Helper to build a ShadowAlert with sensible defaults."""
        now = datetime.now(timezone.utc)
        defaults = dict(
            alert_id="sa-test123",
            timestamp=now,
            agent_id="shadow-1",
            agent_type="unknown",
            severity=ShadowAlertSeverity.WARNING,
            reason="Unregistered agent detected",
            first_seen=now,
            event_count=2,
            tools_observed=("read_logs",),
            mcp_servers_observed=(),
            recommended_action="Investigate",
        )
        defaults.update(overrides)
        return ShadowAlert(**defaults)

    def test_create_shadow_alert(self):
        """Test creating a ShadowAlert with all fields."""
        alert = self._make_alert()
        assert alert.alert_id == "sa-test123"
        assert alert.agent_id == "shadow-1"
        assert alert.severity == ShadowAlertSeverity.WARNING
        assert alert.quarantined is False

    def test_shadow_alert_is_frozen(self):
        """Test that ShadowAlert cannot be mutated."""
        alert = self._make_alert()
        with pytest.raises(AttributeError):
            alert.severity = ShadowAlertSeverity.CRITICAL  # type: ignore[misc]

    def test_to_dict_serialization(self):
        """Test ShadowAlert.to_dict produces expected keys and values."""
        now = datetime.now(timezone.utc)
        alert = self._make_alert(
            timestamp=now,
            first_seen=now,
            tools_observed=("execute_code", "write_file"),
            mcp_servers_observed=("mcp-unknown",),
            quarantined=True,
        )
        d = alert.to_dict()

        assert d["alert_id"] == "sa-test123"
        assert d["agent_id"] == "shadow-1"
        assert d["agent_type"] == "unknown"
        assert d["severity"] == "warning"
        assert d["timestamp"] == now.isoformat()
        assert d["first_seen"] == now.isoformat()
        assert d["event_count"] == 2
        assert d["tools_observed"] == ["execute_code", "write_file"]
        assert d["mcp_servers_observed"] == ["mcp-unknown"]
        assert d["quarantined"] is True

    def test_to_dict_empty_collections(self):
        """Test to_dict with empty tool and MCP tuples."""
        alert = self._make_alert(tools_observed=(), mcp_servers_observed=())
        d = alert.to_dict()
        assert d["tools_observed"] == []
        assert d["mcp_servers_observed"] == []


# ---------------------------------------------------------------------------
# ShadowAlertSeverity enum
# ---------------------------------------------------------------------------


class TestShadowAlertSeverity:
    """Tests for ShadowAlertSeverity enum values."""

    def test_all_severity_values(self):
        """Test that all severity levels exist with correct values."""
        assert ShadowAlertSeverity.INFO.value == "info"
        assert ShadowAlertSeverity.WARNING.value == "warning"
        assert ShadowAlertSeverity.HIGH.value == "high"
        assert ShadowAlertSeverity.CRITICAL.value == "critical"

    def test_severity_count(self):
        """Test that there are exactly 4 severity levels."""
        assert len(ShadowAlertSeverity) == 4


# ---------------------------------------------------------------------------
# Severity classification logic
# ---------------------------------------------------------------------------


class TestSeverityClassification:
    """Tests for severity determination based on agent behaviour."""

    def test_info_severity_single_event_no_tools(
        self, discovery_service, shadow_detector
    ):
        """Test INFO severity for a single-event agent with no tools."""
        discovery_service.record_agent_activity(
            agent_id="transient-agent",
            agent_type="probe",
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.INFO

    def test_warning_severity_multiple_events(self, discovery_service, shadow_detector):
        """Test WARNING severity for an agent seen multiple times."""
        discovery_service.record_agent_activity(
            agent_id="repeat-agent", agent_type="unknown"
        )
        discovery_service.record_agent_activity(
            agent_id="repeat-agent", agent_type="unknown"
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.WARNING

    def test_warning_severity_safe_tools(self, discovery_service, shadow_detector):
        """Test WARNING severity when an agent uses non-dangerous tools."""
        discovery_service.record_agent_activity(
            agent_id="safe-shadow",
            agent_type="unknown",
            tools_used=["list_files"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.WARNING

    def test_high_severity_dangerous_tools(self, discovery_service, shadow_detector):
        """Test HIGH severity when a shadow agent uses dangerous tools."""
        discovery_service.record_agent_activity(
            agent_id="dangerous-agent",
            agent_type="unknown",
            tools_used=["execute_code"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.HIGH

    def test_high_severity_two_mcp_servers(self, discovery_service, shadow_detector):
        """Test HIGH severity when agent accesses two or more MCP servers."""
        discovery_service.record_agent_activity(
            agent_id="multi-mcp-agent",
            agent_type="unknown",
            mcp_servers_used=["mcp-a", "mcp-b"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.HIGH

    def test_critical_severity_critical_tools(self, discovery_service, shadow_detector):
        """Test CRITICAL severity when a shadow agent uses critical tools."""
        discovery_service.record_agent_activity(
            agent_id="critical-agent",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.CRITICAL

    def test_critical_severity_three_mcp_servers(
        self, discovery_service, shadow_detector
    ):
        """Test CRITICAL severity when agent accesses 3+ MCP servers."""
        discovery_service.record_agent_activity(
            agent_id="mcp-heavy",
            agent_type="unknown",
            mcp_servers_used=["mcp-a", "mcp-b", "mcp-c"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.CRITICAL

    def test_critical_trumps_dangerous(self, discovery_service, shadow_detector):
        """Test that critical tools override dangerous tools in severity."""
        discovery_service.record_agent_activity(
            agent_id="mixed-agent",
            agent_type="unknown",
            tools_used=["execute_code", "modify_iam_policy"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].severity == ShadowAlertSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Scan behaviour
# ---------------------------------------------------------------------------


class TestScanBehaviour:
    """Tests for the scan method."""

    def test_scan_returns_empty_for_no_shadows(
        self, discovery_service, shadow_detector
    ):
        """Test that scan returns empty when all agents are registered."""
        discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        alerts = shadow_detector.scan()
        assert alerts == []

    def test_scan_produces_alerts_for_shadows(self, discovery_service, shadow_detector):
        """Test that scan produces alerts for shadow agents."""
        discovery_service.record_agent_activity(
            agent_id="rogue-1", agent_type="unknown"
        )
        discovery_service.record_agent_activity(
            agent_id="rogue-2",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 2
        agent_ids = {a.agent_id for a in alerts}
        assert "rogue-1" in agent_ids
        assert "rogue-2" in agent_ids

    def test_scan_sorted_by_severity_descending(
        self, discovery_service, shadow_detector
    ):
        """Test that scan results are sorted by severity (critical first)."""
        discovery_service.record_agent_activity(
            agent_id="info-agent", agent_type="probe"
        )
        discovery_service.record_agent_activity(
            agent_id="critical-agent",
            agent_type="unknown",
            tools_used=["delete_resource"],
        )
        alerts = shadow_detector.scan()
        assert alerts[0].severity == ShadowAlertSeverity.CRITICAL
        assert alerts[1].severity == ShadowAlertSeverity.INFO

    def test_scan_accumulates_history(self, discovery_service, shadow_detector):
        """Test that multiple scans accumulate in get_all_alerts."""
        discovery_service.record_agent_activity(
            agent_id="rogue-a", agent_type="unknown"
        )
        shadow_detector.scan()
        discovery_service.record_agent_activity(
            agent_id="rogue-b", agent_type="unknown"
        )
        shadow_detector.scan()
        # rogue-a quarantined = no, so it appears again in second scan
        all_alerts = shadow_detector.get_all_alerts()
        assert len(all_alerts) >= 2

    def test_scan_skips_quarantined_agents(self, discovery_service, shadow_detector):
        """Test that quarantined agents are not re-alerted on subsequent scans."""
        discovery_service.record_agent_activity(
            agent_id="quarantine-me",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        first_scan = shadow_detector.scan()
        assert len(first_scan) == 1
        assert first_scan[0].quarantined is True

        second_scan = shadow_detector.scan()
        quarantine_alerts = [a for a in second_scan if a.agent_id == "quarantine-me"]
        assert quarantine_alerts == []

    def test_alert_contains_correct_fields(self, discovery_service, shadow_detector):
        """Test that generated alerts contain the expected agent data."""
        discovery_service.record_agent_activity(
            agent_id="detailed-rogue",
            agent_type="scraper",
            tools_used=["execute_code"],
            mcp_servers_used=["dark-mcp"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.agent_id == "detailed-rogue"
        assert alert.agent_type == "scraper"
        assert "execute_code" in alert.tools_observed
        assert "dark-mcp" in alert.mcp_servers_observed
        assert alert.alert_id.startswith("sa-")
        assert alert.event_count == 1

    def test_get_alerts_by_severity(self, discovery_service, shadow_detector):
        """Test filtering alerts by severity level."""
        discovery_service.record_agent_activity(
            agent_id="info-shadow", agent_type="probe"
        )
        discovery_service.record_agent_activity(
            agent_id="high-shadow",
            agent_type="unknown",
            tools_used=["write_file"],
        )
        shadow_detector.scan()

        info_alerts = shadow_detector.get_alerts_by_severity(ShadowAlertSeverity.INFO)
        high_alerts = shadow_detector.get_alerts_by_severity(ShadowAlertSeverity.HIGH)
        assert all(a.severity == ShadowAlertSeverity.INFO for a in info_alerts)
        assert all(a.severity == ShadowAlertSeverity.HIGH for a in high_alerts)

    def test_total_alerts_property(self, discovery_service, shadow_detector):
        """Test total_alerts property returns cumulative count."""
        assert shadow_detector.total_alerts == 0
        discovery_service.record_agent_activity(
            agent_id="shadow-x", agent_type="unknown"
        )
        shadow_detector.scan()
        assert shadow_detector.total_alerts == 1


# ---------------------------------------------------------------------------
# Auto-quarantine
# ---------------------------------------------------------------------------


class TestAutoQuarantine:
    """Tests for auto-quarantine behaviour."""

    def test_critical_agent_auto_quarantined(self, discovery_service, shadow_detector):
        """Test that CRITICAL agents are auto-quarantined."""
        discovery_service.record_agent_activity(
            agent_id="auto-q",
            agent_type="unknown",
            tools_used=["modify_iam_policy"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].quarantined is True
        assert shadow_detector.is_quarantined("auto-q") is True

    def test_non_critical_not_quarantined(self, discovery_service, shadow_detector):
        """Test that non-critical agents are not auto-quarantined."""
        discovery_service.record_agent_activity(
            agent_id="mild-shadow", agent_type="unknown"
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert alerts[0].quarantined is False
        assert shadow_detector.is_quarantined("mild-shadow") is False

    def test_custom_quarantine_threshold(self, discovery_service):
        """Test quarantine with a lower threshold (HIGH)."""
        detector = ShadowDetector(
            discovery=discovery_service,
            auto_quarantine_threshold=ShadowAlertSeverity.HIGH,
        )
        discovery_service.record_agent_activity(
            agent_id="high-risk",
            agent_type="unknown",
            tools_used=["execute_code"],
        )
        alerts = detector.scan()
        assert len(alerts) == 1
        assert alerts[0].quarantined is True
        assert detector.is_quarantined("high-risk") is True

    def test_quarantine_count_property(self, discovery_service, shadow_detector):
        """Test quarantined_count property."""
        assert shadow_detector.quarantined_count == 0
        discovery_service.record_agent_activity(
            agent_id="q1", agent_type="unknown", tools_used=["delete_resource"]
        )
        discovery_service.record_agent_activity(
            agent_id="q2", agent_type="unknown", tools_used=["modify_iam_policy"]
        )
        shadow_detector.scan()
        assert shadow_detector.quarantined_count == 2


# ---------------------------------------------------------------------------
# Release quarantine
# ---------------------------------------------------------------------------


class TestReleaseQuarantine:
    """Tests for releasing agents from quarantine."""

    def test_release_quarantined_agent(self, discovery_service, shadow_detector):
        """Test releasing a quarantined agent."""
        discovery_service.record_agent_activity(
            agent_id="release-me",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        shadow_detector.scan()
        assert shadow_detector.is_quarantined("release-me") is True

        result = shadow_detector.release_quarantine("release-me")
        assert result is True
        assert shadow_detector.is_quarantined("release-me") is False

    def test_release_non_quarantined_agent(self, shadow_detector):
        """Test releasing an agent that is not quarantined returns False."""
        result = shadow_detector.release_quarantine("not-quarantined")
        assert result is False

    def test_released_agent_appears_in_next_scan(
        self, discovery_service, shadow_detector
    ):
        """Test that a released agent appears in the next scan."""
        discovery_service.record_agent_activity(
            agent_id="recur-agent",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        shadow_detector.scan()
        assert shadow_detector.is_quarantined("recur-agent") is True

        shadow_detector.release_quarantine("recur-agent")
        new_alerts = shadow_detector.scan()
        recur_alerts = [a for a in new_alerts if a.agent_id == "recur-agent"]
        assert len(recur_alerts) == 1


# ---------------------------------------------------------------------------
# Tool detection categories
# ---------------------------------------------------------------------------


class TestToolDetectionCategories:
    """Tests for critical, dangerous, and monitoring tool detection."""

    def test_default_critical_tools(self):
        """Test default critical tools set."""
        detector = ShadowDetector()
        assert "deploy_to_production" in detector.critical_tools
        assert "modify_iam_policy" in detector.critical_tools
        assert "delete_resource" in detector.critical_tools
        assert "access_secrets" in detector.critical_tools
        assert "modify_security_group" in detector.critical_tools

    def test_default_dangerous_tools(self):
        """Test default dangerous tools set."""
        detector = ShadowDetector()
        assert "execute_code" in detector.dangerous_tools
        assert "write_file" in detector.dangerous_tools
        assert "create_sandbox" in detector.dangerous_tools
        assert "invoke_llm" in detector.dangerous_tools
        assert "modify_configuration" in detector.dangerous_tools

    def test_default_monitoring_tools(self):
        """Test default monitoring tools set."""
        detector = ShadowDetector()
        assert "read_logs" in detector.monitoring_tools
        assert "query_database" in detector.monitoring_tools
        assert "scan_repository" in detector.monitoring_tools
        assert "list_resources" in detector.monitoring_tools

    def test_custom_tool_sets(self, discovery_service):
        """Test ShadowDetector with custom tool category sets."""
        detector = ShadowDetector(
            discovery=discovery_service,
            critical_tools={"nuke_everything"},
            dangerous_tools={"run_script"},
            monitoring_tools={"peek"},
        )
        assert detector.critical_tools == {"nuke_everything"}
        assert detector.dangerous_tools == {"run_script"}
        assert detector.monitoring_tools == {"peek"}

    def test_reason_includes_critical_tool_names(
        self, discovery_service, shadow_detector
    ):
        """Test that the alert reason mentions critical tool names."""
        discovery_service.record_agent_activity(
            agent_id="crit-tool-agent",
            agent_type="unknown",
            tools_used=["modify_iam_policy", "delete_resource"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert (
            "modify_iam_policy" in alerts[0].reason
            or "delete_resource" in alerts[0].reason
        )

    def test_reason_includes_dangerous_tool_names(
        self, discovery_service, shadow_detector
    ):
        """Test that the alert reason mentions dangerous tool names."""
        discovery_service.record_agent_activity(
            agent_id="danger-agent",
            agent_type="unknown",
            tools_used=["execute_code"],
        )
        alerts = shadow_detector.scan()
        assert len(alerts) == 1
        assert "execute_code" in alerts[0].reason

    def test_recommended_action_by_severity(self, discovery_service, shadow_detector):
        """Test that recommended actions match severity levels."""
        # INFO
        discovery_service.record_agent_activity(agent_id="info-a", agent_type="probe")
        # CRITICAL
        discovery_service.record_agent_activity(
            agent_id="crit-a",
            agent_type="unknown",
            tools_used=["deploy_to_production"],
        )
        alerts = shadow_detector.scan()
        for alert in alerts:
            if alert.severity == ShadowAlertSeverity.INFO:
                assert "Monitor" in alert.recommended_action
            elif alert.severity == ShadowAlertSeverity.CRITICAL:
                assert "Quarantine" in alert.recommended_action
