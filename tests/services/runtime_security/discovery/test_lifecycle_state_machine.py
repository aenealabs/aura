"""
Tests for the Agent Lifecycle State Machine (ADR-086 Phase 1).

Covers state transitions, invalid transition rejection, trigger handling,
HITL co-sign requirements, agent registration, and singleton lifecycle.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.runtime_security.discovery.lifecycle_state_machine import (
    AgentLifecycleRecord,
    DecommissionTrigger,
    InvalidTransitionError,
    LifecycleState,
    LifecycleStateMachine,
    LifecycleTransition,
    get_lifecycle_state_machine,
    reset_lifecycle_state_machine,
)


# ---------------------------------------------------------------------------
# LifecycleState enum
# ---------------------------------------------------------------------------


class TestLifecycleState:
    """Tests for LifecycleState enum."""

    def test_all_states_defined(self):
        states = {s.value for s in LifecycleState}
        assert states == {
            "active", "dormant", "decommissioning",
            "remediation_required", "attested", "archived",
        }

    def test_state_values_are_lowercase(self):
        for state in LifecycleState:
            assert state.value == state.value.lower()


# ---------------------------------------------------------------------------
# DecommissionTrigger enum
# ---------------------------------------------------------------------------


class TestDecommissionTrigger:
    """Tests for DecommissionTrigger enum."""

    def test_all_triggers_defined(self):
        triggers = {t.value for t in DecommissionTrigger}
        assert "explicit_shutdown" in triggers
        assert "dormancy_threshold" in triggers
        assert "owner_deactivated" in triggers
        assert "anomaly_quarantine" in triggers
        assert len(triggers) == 7


# ---------------------------------------------------------------------------
# LifecycleTransition frozen dataclass
# ---------------------------------------------------------------------------


class TestLifecycleTransition:
    """Tests for LifecycleTransition frozen dataclass."""

    def test_create_transition(self):
        now = datetime.now(timezone.utc)
        t = LifecycleTransition(
            agent_id="agent-1",
            from_state=LifecycleState.ACTIVE,
            to_state=LifecycleState.DORMANT,
            trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
            initiated_by="scanner",
            timestamp=now,
            reason="Inactive 30 days",
        )
        assert t.agent_id == "agent-1"
        assert t.from_state == LifecycleState.ACTIVE
        assert t.to_state == LifecycleState.DORMANT

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        t = LifecycleTransition(
            agent_id="agent-1",
            from_state=LifecycleState.ACTIVE,
            to_state=LifecycleState.DORMANT,
            trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
            initiated_by="scanner",
            timestamp=now,
        )
        d = t.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["from_state"] == "active"
        assert d["to_state"] == "dormant"
        assert d["trigger"] == "dormancy_threshold"

    def test_to_dict_no_trigger(self):
        now = datetime.now(timezone.utc)
        t = LifecycleTransition(
            agent_id="agent-1",
            from_state=LifecycleState.ATTESTED,
            to_state=LifecycleState.ARCHIVED,
            trigger=None,
            initiated_by="admin",
            timestamp=now,
        )
        d = t.to_dict()
        assert d["trigger"] is None

    def test_frozen(self):
        now = datetime.now(timezone.utc)
        t = LifecycleTransition(
            agent_id="agent-1",
            from_state=LifecycleState.ACTIVE,
            to_state=LifecycleState.DORMANT,
            trigger=None,
            initiated_by="system",
            timestamp=now,
        )
        with pytest.raises(AttributeError):
            t.agent_id = "other"


# ---------------------------------------------------------------------------
# AgentLifecycleRecord
# ---------------------------------------------------------------------------


class TestAgentLifecycleRecord:
    """Tests for AgentLifecycleRecord."""

    def test_defaults(self):
        r = AgentLifecycleRecord(agent_id="a1")
        assert r.current_state == LifecycleState.ACTIVE
        assert r.agent_tier == 4
        assert r.owner_id is None
        assert r.pending_trigger is None
        assert len(r.transitions) == 0

    def test_to_dict(self):
        r = AgentLifecycleRecord(agent_id="a1", owner_id="user-1", agent_tier=2)
        d = r.to_dict()
        assert d["agent_id"] == "a1"
        assert d["owner_id"] == "user-1"
        assert d["agent_tier"] == 2
        assert d["current_state"] == "active"


# ---------------------------------------------------------------------------
# LifecycleStateMachine
# ---------------------------------------------------------------------------


class TestLifecycleStateMachine:
    """Tests for LifecycleStateMachine."""

    def setup_method(self):
        self.sm = LifecycleStateMachine()

    def test_register_agent(self):
        record = self.sm.register_agent("agent-1", owner_id="user-1", agent_tier=2)
        assert record.agent_id == "agent-1"
        assert record.current_state == LifecycleState.ACTIVE
        assert record.agent_tier == 2

    def test_get_agent(self):
        self.sm.register_agent("agent-1")
        assert self.sm.get_agent("agent-1") is not None
        assert self.sm.get_agent("nonexistent") is None

    def test_get_state(self):
        self.sm.register_agent("agent-1")
        assert self.sm.get_state("agent-1") == LifecycleState.ACTIVE
        assert self.sm.get_state("nonexistent") is None

    # Valid transitions
    def test_active_to_dormant(self):
        self.sm.register_agent("a1")
        t = self.sm.transition(
            "a1", LifecycleState.DORMANT,
            trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
            initiated_by="scanner",
        )
        assert t.to_state == LifecycleState.DORMANT
        assert self.sm.get_state("a1") == LifecycleState.DORMANT

    def test_active_to_decommissioning(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        assert self.sm.get_state("a1") == LifecycleState.DECOMMISSIONING

    def test_dormant_to_active(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DORMANT)
        self.sm.transition("a1", LifecycleState.ACTIVE)
        assert self.sm.get_state("a1") == LifecycleState.ACTIVE

    def test_dormant_to_decommissioning(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DORMANT)
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        assert self.sm.get_state("a1") == LifecycleState.DECOMMISSIONING

    def test_decommissioning_to_attested(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        self.sm.transition("a1", LifecycleState.ATTESTED)
        assert self.sm.get_state("a1") == LifecycleState.ATTESTED

    def test_decommissioning_to_remediation(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        self.sm.transition("a1", LifecycleState.REMEDIATION_REQUIRED)
        assert self.sm.get_state("a1") == LifecycleState.REMEDIATION_REQUIRED

    def test_remediation_to_decommissioning(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        self.sm.transition("a1", LifecycleState.REMEDIATION_REQUIRED)
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        assert self.sm.get_state("a1") == LifecycleState.DECOMMISSIONING

    def test_attested_to_archived(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        self.sm.transition("a1", LifecycleState.ATTESTED)
        self.sm.transition("a1", LifecycleState.ARCHIVED)
        assert self.sm.get_state("a1") == LifecycleState.ARCHIVED

    def test_full_happy_path(self):
        """Test the complete decommission flow."""
        self.sm.register_agent("a1", agent_tier=3)
        self.sm.transition("a1", LifecycleState.DORMANT,
                           trigger=DecommissionTrigger.DORMANCY_THRESHOLD)
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING,
                           trigger=DecommissionTrigger.DORMANCY_THRESHOLD)
        self.sm.transition("a1", LifecycleState.ATTESTED,
                           initiated_by="verifier")
        self.sm.transition("a1", LifecycleState.ARCHIVED)
        assert self.sm.get_state("a1") == LifecycleState.ARCHIVED
        assert len(self.sm.get_transitions("a1")) == 4

    # Invalid transitions
    def test_invalid_active_to_attested(self):
        self.sm.register_agent("a1")
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("a1", LifecycleState.ATTESTED)

    def test_invalid_active_to_archived(self):
        self.sm.register_agent("a1")
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("a1", LifecycleState.ARCHIVED)

    def test_invalid_archived_to_anything(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DECOMMISSIONING)
        self.sm.transition("a1", LifecycleState.ATTESTED)
        self.sm.transition("a1", LifecycleState.ARCHIVED)
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("a1", LifecycleState.ACTIVE)

    def test_invalid_dormant_to_attested(self):
        self.sm.register_agent("a1")
        self.sm.transition("a1", LifecycleState.DORMANT)
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("a1", LifecycleState.ATTESTED)

    def test_unknown_agent_raises_key_error(self):
        with pytest.raises(KeyError):
            self.sm.transition("nonexistent", LifecycleState.DORMANT)

    # Metadata and records
    def test_transition_records_metadata(self):
        self.sm.register_agent("a1")
        t = self.sm.transition(
            "a1", LifecycleState.DORMANT,
            metadata={"scan_id": "abc123"},
        )
        assert ("scan_id", "abc123") in t.metadata

    def test_record_activity(self):
        self.sm.register_agent("a1")
        old_activity = self.sm.get_agent("a1").last_activity
        self.sm.record_activity("a1")
        assert self.sm.get_agent("a1").last_activity >= old_activity

    def test_record_activity_nonexistent_agent(self):
        # Should not raise
        self.sm.record_activity("nonexistent")

    # Listing and counting
    def test_list_agents(self):
        self.sm.register_agent("a1")
        self.sm.register_agent("a2")
        assert len(self.sm.list_agents()) == 2

    def test_list_agents_by_state(self):
        self.sm.register_agent("a1")
        self.sm.register_agent("a2")
        self.sm.transition("a2", LifecycleState.DORMANT)
        active = self.sm.list_agents(state=LifecycleState.ACTIVE)
        dormant = self.sm.list_agents(state=LifecycleState.DORMANT)
        assert len(active) == 1
        assert len(dormant) == 1

    def test_count_by_state(self):
        self.sm.register_agent("a1")
        self.sm.register_agent("a2")
        self.sm.transition("a2", LifecycleState.DORMANT)
        counts = self.sm.count_by_state()
        assert counts["active"] == 1
        assert counts["dormant"] == 1

    # HITL requirement
    def test_requires_hitl_tier_1(self):
        self.sm.register_agent("a1", agent_tier=1)
        assert self.sm.requires_hitl_cosign("a1") is True

    def test_requires_hitl_tier_2(self):
        self.sm.register_agent("a1", agent_tier=2)
        assert self.sm.requires_hitl_cosign("a1") is True

    def test_no_hitl_tier_3(self):
        self.sm.register_agent("a1", agent_tier=3)
        assert self.sm.requires_hitl_cosign("a1") is False

    def test_no_hitl_tier_4(self):
        self.sm.register_agent("a1", agent_tier=4)
        assert self.sm.requires_hitl_cosign("a1") is False

    def test_hitl_unknown_agent_defaults_true(self):
        assert self.sm.requires_hitl_cosign("unknown") is True

    def test_get_transitions_empty(self):
        assert self.sm.get_transitions("unknown") == []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestLifecycleStateMachineSingleton:
    """Tests for singleton lifecycle."""

    def setup_method(self):
        reset_lifecycle_state_machine()

    def teardown_method(self):
        reset_lifecycle_state_machine()

    def test_singleton_returns_same_instance(self):
        sm1 = get_lifecycle_state_machine()
        sm2 = get_lifecycle_state_machine()
        assert sm1 is sm2

    def test_reset_creates_new_instance(self):
        sm1 = get_lifecycle_state_machine()
        reset_lifecycle_state_machine()
        sm2 = get_lifecycle_state_machine()
        assert sm1 is not sm2


# ---------------------------------------------------------------------------
# InvalidTransitionError
# ---------------------------------------------------------------------------


class TestInvalidTransitionError:
    """Tests for InvalidTransitionError."""

    def test_error_message(self):
        err = InvalidTransitionError(
            "agent-1", LifecycleState.ACTIVE, LifecycleState.ARCHIVED
        )
        assert "agent-1" in str(err)
        assert "active" in str(err)
        assert "archived" in str(err)

    def test_error_attributes(self):
        err = InvalidTransitionError(
            "agent-1", LifecycleState.ACTIVE, LifecycleState.ARCHIVED
        )
        assert err.agent_id == "agent-1"
        assert err.from_state == LifecycleState.ACTIVE
        assert err.to_state == LifecycleState.ARCHIVED
