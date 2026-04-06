"""
Tests for the Ghost Agent Scanner (ADR-086 Phase 1).

Covers dormancy detection, severity classification, ghost finding
generation, auto-decommission triggering, and Lambda handler.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.runtime_security.discovery.credential_enumerators.enumerators import (
    IAMRoleEnumerator,
    MCPTokenEnumerator,
    BaselineRecordEnumerator,
)
from src.services.runtime_security.discovery.credential_enumerators.registry import (
    EnumeratorRegistry,
)
from src.services.runtime_security.discovery.ghost_agent_scanner import (
    GhostAgentFinding,
    GhostAgentScanner,
    GhostFindingSeverity,
    ScanResult,
    lambda_handler,
)
from src.services.runtime_security.discovery.lifecycle_state_machine import (
    LifecycleState,
    LifecycleStateMachine,
)


class TestGhostAgentScanner:
    """Tests for GhostAgentScanner."""

    def setup_method(self):
        self.sm = LifecycleStateMachine()
        self.registry = EnumeratorRegistry()
        self.scanner = GhostAgentScanner(
            state_machine=self.sm,
            enumerator_registry=self.registry,
            dormancy_days=30,
        )

    def _make_dormant_agent(self, agent_id, tier=4, days_inactive=60):
        """Register agent with old last_activity."""
        record = self.sm.register_agent(agent_id, agent_tier=tier)
        record.last_activity = datetime.now(timezone.utc) - timedelta(
            days=days_inactive
        )
        return record

    def _register_active_enumerator(self, credential_class="aws_iam_roles"):
        """Register an enumerator that returns active credentials."""
        mock_client = MagicMock()
        attr_name = {
            "aws_iam_roles": "list_roles_for_agent",
            "mcp_tokens": "list_mcp_tokens",
            "baseline_records": "list_baselines",
        }.get(credential_class, "list_roles_for_agent")
        getattr(mock_client, attr_name).return_value = [
            {"role_arn": "arn:test", "role_name": "test",
             "token_id": "tok-1", "server_id": "s1",
             "baseline_id": "b1", "metric_type": "frequency"}
        ]
        enum_cls = {
            "aws_iam_roles": IAMRoleEnumerator,
            "mcp_tokens": MCPTokenEnumerator,
            "baseline_records": BaselineRecordEnumerator,
        }.get(credential_class, IAMRoleEnumerator)
        self.registry.register(enum_cls(client=mock_client))

    def test_no_agents_returns_empty(self):
        result = self.scanner.scan()
        assert result.agents_scanned == 0
        assert result.ghost_agents_found == 0

    def test_active_agent_not_ghost(self):
        """Recently active agent is not a ghost."""
        self.sm.register_agent("a1")  # Just registered = recent activity
        self._register_active_enumerator()
        result = self.scanner.scan()
        assert result.ghost_agents_found == 0

    def test_dormant_no_credentials_not_ghost(self):
        """Dormant agent with no credentials is not a ghost."""
        self._make_dormant_agent("a1", days_inactive=60)
        self.registry.register(IAMRoleEnumerator())  # No client = zero
        result = self.scanner.scan()
        assert result.ghost_agents_found == 0

    def test_dormant_with_credentials_is_ghost(self):
        """Dormant agent with active credentials is a ghost."""
        self._make_dormant_agent("a1", tier=3, days_inactive=60)
        self._register_active_enumerator()
        result = self.scanner.scan()
        assert result.ghost_agents_found == 1
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.agent_id == "a1"
        assert finding.active_credential_count > 0

    def test_multiple_agents(self):
        """Scan multiple agents, mix of ghosts and non-ghosts."""
        self._make_dormant_agent("ghost-1", tier=3, days_inactive=60)
        self.sm.register_agent("active-1")  # Active
        self._register_active_enumerator()
        result = self.scanner.scan()
        assert result.agents_scanned == 2
        assert result.ghost_agents_found == 1

    def test_dormant_state_scanned(self):
        """Agents in DORMANT state are scanned."""
        self.sm.register_agent("a1")
        record = self.sm.get_agent("a1")
        record.last_activity = datetime.now(timezone.utc) - timedelta(days=60)
        self.sm.transition("a1", LifecycleState.DORMANT)
        self._register_active_enumerator()
        result = self.scanner.scan()
        assert result.ghost_agents_found == 1

    def test_scan_result_to_dict(self):
        result = ScanResult()
        d = result.to_dict()
        assert "agents_scanned" in d
        assert "ghost_agents_found" in d


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


class TestSeverityClassification:
    """Tests for ghost finding severity classification."""

    def setup_method(self):
        self.sm = LifecycleStateMachine()
        self.registry = EnumeratorRegistry()
        self.scanner = GhostAgentScanner(
            state_machine=self.sm,
            enumerator_registry=self.registry,
            dormancy_days=30,
        )

    def test_critical_tier1_iam(self):
        sev = self.scanner._classify_severity(
            agent_tier=1, active_count=1,
            active_classes=["aws_iam_roles"],
        )
        assert sev == GhostFindingSeverity.CRITICAL

    def test_critical_tier2_secrets(self):
        sev = self.scanner._classify_severity(
            agent_tier=2, active_count=1,
            active_classes=["secrets_manager"],
        )
        assert sev == GhostFindingSeverity.CRITICAL

    def test_high_tier1_no_sensitive(self):
        sev = self.scanner._classify_severity(
            agent_tier=1, active_count=1,
            active_classes=["mcp_tokens"],
        )
        assert sev == GhostFindingSeverity.HIGH

    def test_high_tier4_iam(self):
        sev = self.scanner._classify_severity(
            agent_tier=4, active_count=1,
            active_classes=["aws_access_keys"],
        )
        assert sev == GhostFindingSeverity.HIGH

    def test_medium_tier4_multiple(self):
        sev = self.scanner._classify_severity(
            agent_tier=4, active_count=3,
            active_classes=["mcp_tokens", "remem_grants"],
        )
        assert sev == GhostFindingSeverity.MEDIUM

    def test_low_tier4_single(self):
        sev = self.scanner._classify_severity(
            agent_tier=4, active_count=1,
            active_classes=["baseline_records"],
        )
        assert sev == GhostFindingSeverity.LOW


# ---------------------------------------------------------------------------
# Auto-trigger decommission
# ---------------------------------------------------------------------------


class TestAutoTriggerDecommission:
    """Tests for auto-decommission triggering."""

    def setup_method(self):
        self.sm = LifecycleStateMachine()
        self.registry = EnumeratorRegistry()

    def test_auto_trigger_transitions_to_decommissioning(self):
        mock_client = MagicMock()
        mock_client.list_roles_for_agent.return_value = [
            {"role_arn": "arn:test", "role_name": "test"},
        ]
        self.registry.register(IAMRoleEnumerator(client=mock_client))

        scanner = GhostAgentScanner(
            state_machine=self.sm,
            enumerator_registry=self.registry,
            dormancy_days=30,
            auto_trigger_decommission=True,
        )
        record = self.sm.register_agent("a1")
        record.last_activity = datetime.now(timezone.utc) - timedelta(days=60)

        result = scanner.scan()
        assert result.auto_triggered_decommissions == 1
        assert self.sm.get_state("a1") == LifecycleState.DECOMMISSIONING


# ---------------------------------------------------------------------------
# GhostAgentFinding
# ---------------------------------------------------------------------------


class TestGhostAgentFinding:
    """Tests for GhostAgentFinding frozen dataclass."""

    def test_to_dict(self):
        finding = GhostAgentFinding(
            finding_id="f-1",
            agent_id="a1",
            severity=GhostFindingSeverity.HIGH,
            reason="Dormant with credentials",
            active_credential_classes=("aws_iam_roles",),
            active_credential_count=2,
            agent_tier=2,
        )
        d = finding.to_dict()
        assert d["finding_id"] == "f-1"
        assert d["severity"] == "high"
        assert d["active_credential_count"] == 2

    def test_frozen(self):
        finding = GhostAgentFinding(
            finding_id="f-1",
            agent_id="a1",
            severity=GhostFindingSeverity.LOW,
            reason="test",
            active_credential_classes=(),
            active_credential_count=0,
        )
        with pytest.raises(AttributeError):
            finding.agent_id = "other"
