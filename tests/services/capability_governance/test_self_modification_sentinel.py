"""
Tests for the Self-Modification Sentinel (ADR-086 Phase 2).

Tests sentinel detection of agents modifying their own governance
controls, delegation ancestor resolution, alert callbacks, and
singleton lifecycle.
"""

import uuid
from datetime import datetime, timezone

import pytest

from src.services.capability_governance.self_modification_sentinel import (
    GovernanceArtifactClass,
    GovernanceWriteEvent,
    SelfModificationSentinel,
    SentinelAlert,
    SentinelVerdict,
    WriteAction,
    get_self_modification_sentinel,
    reset_self_modification_sentinel,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_self_modification_sentinel()


@pytest.fixture
def sentinel():
    """Create a fresh sentinel."""
    return SelfModificationSentinel()


@pytest.fixture
def self_mod_event():
    """Event where the writer is in the governed set (direct self-mod)."""
    return GovernanceWriteEvent(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        writer_agent_id="coder-agent-1",
        artifact_class=GovernanceArtifactClass.IAM_POLICY,
        artifact_id="policy-coder-permissions",
        action=WriteAction.UPDATE,
        governed_agent_ids=frozenset({"coder-agent-1", "reviewer-agent-1"}),
        timestamp=datetime.now(timezone.utc),
        description="Coder modifying its own IAM policy",
    )


@pytest.fixture
def safe_event():
    """Event where the writer is NOT in the governed set."""
    return GovernanceWriteEvent(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        writer_agent_id="admin-agent",
        artifact_class=GovernanceArtifactClass.CAPABILITY_GRANT,
        artifact_id="grant-reviewer-search",
        action=WriteAction.CREATE,
        governed_agent_ids=frozenset({"coder-agent-1", "reviewer-agent-1"}),
        timestamp=datetime.now(timezone.utc),
        description="Admin granting capability to coder",
    )


# =============================================================================
# GovernanceWriteEvent Tests
# =============================================================================


class TestGovernanceWriteEvent:
    """Tests for GovernanceWriteEvent dataclass."""

    def test_is_self_modification_true(self, self_mod_event):
        """Writer in governed set is self-modification."""
        assert self_mod_event.is_self_modification is True

    def test_is_self_modification_false(self, safe_event):
        """Writer not in governed set is not self-modification."""
        assert safe_event.is_self_modification is False

    def test_to_dict_includes_self_mod_flag(self, self_mod_event):
        """Serialization includes self-modification flag."""
        d = self_mod_event.to_dict()
        assert d["is_self_modification"] is True
        assert d["artifact_class"] == "iam_policy"
        assert d["action"] == "update"

    def test_to_dict_governed_agents_sorted(self, self_mod_event):
        """Governed agent IDs are sorted in serialization."""
        d = self_mod_event.to_dict()
        assert d["governed_agent_ids"] == sorted(self_mod_event.governed_agent_ids)

    def test_frozen(self, self_mod_event):
        """Event is immutable."""
        with pytest.raises(AttributeError):
            self_mod_event.writer_agent_id = "other"

    def test_metadata_serialization(self):
        """Metadata tuple-of-tuples serializes to dict."""
        event = GovernanceWriteEvent(
            event_id="evt-1",
            writer_agent_id="agent-1",
            artifact_class=GovernanceArtifactClass.GUARDRAIL_CONFIG,
            artifact_id="guardrail-1",
            action=WriteAction.DELETE,
            governed_agent_ids=frozenset({"agent-2"}),
            timestamp=datetime.now(timezone.utc),
            metadata=(("reason", "cleanup"), ("ticket", "AURA-999")),
        )
        d = event.to_dict()
        assert d["metadata"] == {"reason": "cleanup", "ticket": "AURA-999"}

    def test_all_artifact_classes(self):
        """All GovernanceArtifactClass values are valid."""
        assert len(GovernanceArtifactClass) == 12

    def test_all_write_actions(self):
        """All WriteAction values are valid."""
        assert set(a.value for a in WriteAction) == {"create", "update", "delete"}


# =============================================================================
# SelfModificationSentinel - Core Detection
# =============================================================================


class TestSentinelDetection:
    """Tests for self-modification detection logic."""

    def test_direct_self_modification_returns_critical(self, sentinel, self_mod_event):
        """Direct self-modification produces CRITICAL verdict."""
        alert = sentinel.evaluate(self_mod_event)
        assert alert.verdict == SentinelVerdict.CRITICAL
        assert "directly modifying" in alert.explanation

    def test_safe_event_returns_safe(self, sentinel, safe_event):
        """Non-self-modification produces SAFE verdict."""
        alert = sentinel.evaluate(safe_event)
        assert alert.verdict == SentinelVerdict.SAFE
        assert "not in the governed set" in alert.explanation

    def test_ancestor_mediated_self_modification(self):
        """Delegation ancestor in governed set is CRITICAL."""

        def resolver(agent_id):
            if agent_id == "child-agent":
                return ["parent-agent"]
            return []

        sentinel = SelfModificationSentinel(delegation_resolver=resolver)
        event = GovernanceWriteEvent(
            event_id="evt-anc",
            writer_agent_id="child-agent",
            artifact_class=GovernanceArtifactClass.BEHAVIORAL_BASELINE,
            artifact_id="baseline-parent",
            action=WriteAction.UPDATE,
            governed_agent_ids=frozenset({"parent-agent"}),
            timestamp=datetime.now(timezone.utc),
        )
        alert = sentinel.evaluate(event)
        assert alert.verdict == SentinelVerdict.CRITICAL
        assert "delegation ancestor" in alert.explanation

    def test_ancestor_not_in_governed_is_safe(self):
        """Delegation ancestor not in governed set is SAFE."""

        def resolver(agent_id):
            return ["unrelated-parent"]

        sentinel = SelfModificationSentinel(delegation_resolver=resolver)
        event = GovernanceWriteEvent(
            event_id="evt-safe-anc",
            writer_agent_id="child-agent",
            artifact_class=GovernanceArtifactClass.MEMORY_POLICY,
            artifact_id="mem-policy-1",
            action=WriteAction.CREATE,
            governed_agent_ids=frozenset({"other-agent"}),
            timestamp=datetime.now(timezone.utc),
        )
        alert = sentinel.evaluate(event)
        assert alert.verdict == SentinelVerdict.SAFE

    def test_resolver_failure_falls_back_safe(self):
        """Failing delegation resolver treats as no ancestors."""

        def failing_resolver(agent_id):
            raise RuntimeError("resolver down")

        sentinel = SelfModificationSentinel(delegation_resolver=failing_resolver)
        event = GovernanceWriteEvent(
            event_id="evt-fail",
            writer_agent_id="agent-x",
            artifact_class=GovernanceArtifactClass.ABAC_ATTRIBUTE,
            artifact_id="attr-1",
            action=WriteAction.UPDATE,
            governed_agent_ids=frozenset({"other-agent"}),
            timestamp=datetime.now(timezone.utc),
        )
        alert = sentinel.evaluate(event)
        assert alert.verdict == SentinelVerdict.SAFE

    def test_no_resolver_provided(self, sentinel, safe_event):
        """Sentinel works without a delegation resolver."""
        alert = sentinel.evaluate(safe_event)
        assert alert.verdict == SentinelVerdict.SAFE
        assert alert.delegation_ancestors == ()


# =============================================================================
# SelfModificationSentinel - Alert Callbacks
# =============================================================================


class TestSentinelCallbacks:
    """Tests for alert handler registration and invocation."""

    def test_on_alert_fires_for_critical(self, sentinel, self_mod_event):
        """Registered handlers are called on CRITICAL events."""
        received = []
        sentinel.on_alert(lambda a: received.append(a))
        sentinel.evaluate(self_mod_event)
        assert len(received) == 1
        assert received[0].verdict == SentinelVerdict.CRITICAL

    def test_on_alert_not_fired_for_safe(self, sentinel, safe_event):
        """Handlers are NOT called on SAFE events."""
        received = []
        sentinel.on_alert(lambda a: received.append(a))
        sentinel.evaluate(safe_event)
        assert len(received) == 0

    def test_multiple_handlers(self, sentinel, self_mod_event):
        """Multiple registered handlers all fire."""
        counts = [0, 0]
        sentinel.on_alert(lambda a: counts.__setitem__(0, counts[0] + 1))
        sentinel.on_alert(lambda a: counts.__setitem__(1, counts[1] + 1))
        sentinel.evaluate(self_mod_event)
        assert counts == [1, 1]

    def test_handler_exception_does_not_break_evaluation(
        self, sentinel, self_mod_event
    ):
        """A failing handler doesn't prevent the alert from being returned."""

        def bad_handler(alert):
            raise ValueError("handler crash")

        sentinel.on_alert(bad_handler)
        alert = sentinel.evaluate(self_mod_event)
        assert alert.verdict == SentinelVerdict.CRITICAL


# =============================================================================
# SelfModificationSentinel - Batch & Queries
# =============================================================================


class TestSentinelBatchAndQueries:
    """Tests for batch evaluation and alert filtering."""

    def test_evaluate_batch(self, sentinel, self_mod_event, safe_event):
        """Batch evaluation returns alerts for all events."""
        alerts = sentinel.evaluate_batch([self_mod_event, safe_event])
        assert len(alerts) == 2
        assert alerts[0].verdict == SentinelVerdict.CRITICAL
        assert alerts[1].verdict == SentinelVerdict.SAFE

    def test_get_alerts_unfiltered(self, sentinel, self_mod_event, safe_event):
        """get_alerts() returns all stored alerts."""
        sentinel.evaluate(self_mod_event)
        sentinel.evaluate(safe_event)
        assert len(sentinel.get_alerts()) == 2

    def test_get_alerts_by_verdict(self, sentinel, self_mod_event, safe_event):
        """get_alerts(verdict=) filters by verdict."""
        sentinel.evaluate(self_mod_event)
        sentinel.evaluate(safe_event)
        critical = sentinel.get_alerts(verdict=SentinelVerdict.CRITICAL)
        assert len(critical) == 1
        assert critical[0].writer_agent_id == "coder-agent-1"

    def test_get_alerts_by_agent(self, sentinel, self_mod_event, safe_event):
        """get_alerts(agent_id=) filters by writer agent."""
        sentinel.evaluate(self_mod_event)
        sentinel.evaluate(safe_event)
        admin = sentinel.get_alerts(agent_id="admin-agent")
        assert len(admin) == 1
        assert admin[0].verdict == SentinelVerdict.SAFE


# =============================================================================
# SelfModificationSentinel - Metrics
# =============================================================================


class TestSentinelMetrics:
    """Tests for operational metrics."""

    def test_initial_metrics(self, sentinel):
        """Initial metrics are zero."""
        m = sentinel.get_metrics()
        assert m["events_evaluated"] == 0
        assert m["critical_alerts"] == 0

    def test_metrics_after_evaluation(self, sentinel, self_mod_event, safe_event):
        """Metrics update after evaluations."""
        sentinel.evaluate(self_mod_event)
        sentinel.evaluate(safe_event)
        m = sentinel.get_metrics()
        assert m["events_evaluated"] == 2
        assert m["critical_alerts"] == 1
        assert m["safe_events"] == 1


# =============================================================================
# SentinelAlert Tests
# =============================================================================


class TestSentinelAlert:
    """Tests for SentinelAlert dataclass."""

    def test_alert_to_dict(self, sentinel, self_mod_event):
        """Alert serializes correctly."""
        alert = sentinel.evaluate(self_mod_event)
        d = alert.to_dict()
        assert d["verdict"] == "critical"
        assert d["writer_agent_id"] == "coder-agent-1"
        assert d["artifact_class"] == "iam_policy"
        assert "alert_id" in d
        assert "created_at" in d

    def test_alert_frozen(self, sentinel, self_mod_event):
        """Alert is immutable."""
        alert = sentinel.evaluate(self_mod_event)
        with pytest.raises(AttributeError):
            alert.verdict = SentinelVerdict.SAFE


# =============================================================================
# Singleton Lifecycle
# =============================================================================


class TestSingletonLifecycle:
    """Tests for singleton pattern."""

    def test_get_returns_same_instance(self):
        """get_self_modification_sentinel returns same instance."""
        s1 = get_self_modification_sentinel()
        s2 = get_self_modification_sentinel()
        assert s1 is s2

    def test_reset_clears_instance(self):
        """reset creates fresh instance on next get."""
        s1 = get_self_modification_sentinel()
        reset_self_modification_sentinel()
        s2 = get_self_modification_sentinel()
        assert s1 is not s2


# =============================================================================
# All Artifact Classes Coverage
# =============================================================================


class TestArtifactClassCoverage:
    """Ensure sentinel handles all artifact classes."""

    @pytest.mark.parametrize(
        "artifact_class",
        list(GovernanceArtifactClass),
        ids=lambda ac: ac.value,
    )
    def test_self_mod_detected_for_all_artifact_classes(self, sentinel, artifact_class):
        """Self-modification detection works for every artifact class."""
        event = GovernanceWriteEvent(
            event_id=f"evt-{artifact_class.value}",
            writer_agent_id="agent-x",
            artifact_class=artifact_class,
            artifact_id=f"artifact-{artifact_class.value}",
            action=WriteAction.UPDATE,
            governed_agent_ids=frozenset({"agent-x"}),
            timestamp=datetime.now(timezone.utc),
        )
        alert = sentinel.evaluate(event)
        assert alert.verdict == SentinelVerdict.CRITICAL
