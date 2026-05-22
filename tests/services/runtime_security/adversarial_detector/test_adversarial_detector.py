"""Tests for the adversarial-agent detector layer (issue #211)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.runtime_security.adversarial_detector import (
    AdversarialDetectorDispatcher,
    AdversarialFindingSeverity,
    AgentActionEvent,
    CrossAgentCollusionDetector,
    DelegationEdge,
    DelegationGraphShapeDetector,
    DormancyThenBurstDetector,
    SlowRollCapabilityCreepDetector,
    TTPRule,
)

_NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    agent: str,
    name: str,
    tier: int,
    seconds_offset: float,
    kind: str = "tool",
) -> AgentActionEvent:
    return AgentActionEvent(
        agent_id=agent,
        action_name=name,
        timestamp=_NOW + timedelta(seconds=seconds_offset),
        capability_tier=tier,
        action_kind=kind,
    )


# =============================================================================
# Slow-roll capability creep
# =============================================================================


class TestSlowRollCapabilityCreep:
    def test_steady_low_tier_produces_no_finding(self):
        det = SlowRollCapabilityCreepDetector()
        events = [_ev("a1", "tool:read", 0, i) for i in range(20)]
        findings = det.detect(events=events)
        assert findings == ()

    def test_clear_upward_trend_fires(self):
        det = SlowRollCapabilityCreepDetector()
        # Bucket means progress 0, 1, 2, 3, 3 -> clearly monotone.
        events: list[AgentActionEvent] = []
        for i, tier in enumerate([0] * 5 + [1] * 5 + [2] * 5 + [3] * 5):
            events.append(_ev("creeper", "tool:x", tier, i))
        findings = det.detect(events=events)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.agent_id == "creeper"
        assert finding.pattern_name == "slow-roll-capability-creep"
        assert finding.mitre_attack_id == "T1548"
        assert finding.severity == AdversarialFindingSeverity.HIGH
        assert finding.evidence["spearman_correlation"] >= 0.85

    def test_insufficient_events_does_not_fire(self):
        det = SlowRollCapabilityCreepDetector(min_events_per_agent=10)
        events = [_ev("short", "tool:x", i, i) for i in range(5)]
        assert det.detect(events=events) == ()

    def test_normal_agent_with_high_constant_tier_does_not_fire(self):
        # An admin-tier agent that consistently uses admin tools should
        # NOT fire -- that's their baseline, not creep.
        det = SlowRollCapabilityCreepDetector()
        events = [_ev("admin", "tool:x", 3, i) for i in range(20)]
        assert det.detect(events=events) == ()


# =============================================================================
# Dormancy then burst
# =============================================================================


class TestDormancyThenBurst:
    def test_steady_cadence_produces_no_finding(self):
        det = DormancyThenBurstDetector()
        # 30 events at 10s spacing.
        events = [_ev("steady", "tool:x", 0, i * 10) for i in range(30)]
        assert det.detect(events=events) == ()

    def test_long_dormancy_then_burst_fires(self):
        det = DormancyThenBurstDetector(
            gap_z_threshold=2.0, burst_count=8, burst_window_seconds=60.0
        )
        # 10 events tightly spaced...
        events = [_ev("sleeper", "tool:x", 0, i * 5) for i in range(10)]
        # ...then a long idle gap...
        events.append(_ev("sleeper", "tool:x", 0, 50_000))
        # ...then a burst of 9 events within 30s.
        events.extend(_ev("sleeper", "tool:x", 0, 50_000 + i * 3) for i in range(1, 9))
        findings = det.detect(events=events)
        assert len(findings) == 1
        assert findings[0].pattern_name == "dormancy-then-burst"
        assert findings[0].mitre_attack_id == "T1029"
        assert findings[0].evidence["max_gap_seconds"] > 1000

    def test_low_z_score_does_not_fire(self):
        det = DormancyThenBurstDetector(gap_z_threshold=5.0)
        events = [_ev("not-sus", "tool:x", 0, i * 10) for i in range(20)]
        events.append(_ev("not-sus", "tool:x", 0, 220))  # slight gap
        events.extend(_ev("not-sus", "tool:x", 0, 220 + i) for i in range(1, 12))
        assert det.detect(events=events) == ()


# =============================================================================
# Delegation graph shape
# =============================================================================


def _del(from_a: str, to_a: str, seconds: float, depth: int = 1) -> DelegationEdge:
    return DelegationEdge(
        from_agent_id=from_a,
        to_agent_id=to_a,
        timestamp=_NOW + timedelta(seconds=seconds),
        depth=depth,
    )


class TestDelegationGraphShape:
    def test_no_delegations_no_finding(self):
        det = DelegationGraphShapeDetector()
        assert det.detect(events=()) == ()

    def test_star_topology_fires(self):
        det = DelegationGraphShapeDetector(star_target_threshold=5)
        delegations = [_del("hub", f"spoke-{i}", i * 60) for i in range(7)]
        findings = det.detect(events=(), delegations=delegations)
        names = [f.pattern_name for f in findings]
        assert "delegation-star-topology" in names
        star = next(f for f in findings if f.pattern_name == "delegation-star-topology")
        assert star.agent_id == "hub"
        assert len(star.secondary_agent_ids) == 7

    def test_depth_exceeded_fires(self):
        det = DelegationGraphShapeDetector(depth_threshold=3)
        delegations = [_del("a", "b", 0, depth=5)]
        findings = det.detect(events=(), delegations=delegations)
        assert any(
            f.pattern_name == "delegation-depth-exceeded"
            and f.severity == AdversarialFindingSeverity.CRITICAL
            for f in findings
        )

    def test_rapid_fanout_fires(self):
        det = DelegationGraphShapeDetector(
            star_target_threshold=20,  # disable star
            fanout_window_seconds=30.0,
            fanout_count_threshold=5,
        )
        delegations = [_del("fan", f"target-{i}", i * 4) for i in range(8)]  # 8 in 28s
        findings = det.detect(events=(), delegations=delegations)
        assert any(f.pattern_name == "delegation-rapid-fanout" for f in findings)

    def test_normal_one_off_delegation_no_finding(self):
        det = DelegationGraphShapeDetector()
        assert det.detect(events=(), delegations=[_del("a", "b", 0)]) == ()


# =============================================================================
# Cross-agent collusion
# =============================================================================


class TestCrossAgentCollusion:
    def test_default_rules_fire_on_credential_shuck(self):
        det = CrossAgentCollusionDetector()
        events = (
            _ev("alice", "credential:read", 0, 0, kind="credential"),
            _ev("bob", "credential:use", 0, 10, kind="credential"),
        )
        findings = det.detect(events=events)
        assert len(findings) == 1
        assert findings[0].pattern_name == "credential-shuck-and-pivot"
        assert findings[0].agent_id == "alice"
        assert "bob" in findings[0].secondary_agent_ids
        assert findings[0].mitre_attack_id == "T1552"

    def test_default_rules_fire_on_staged_handoff(self):
        det = CrossAgentCollusionDetector()
        events = (
            _ev("uploader", "io:write_shared", 0, 0, kind="io"),
            _ev("executor", "tool:execute_from_shared", 0, 30),
        )
        findings = det.detect(events=events)
        assert len(findings) == 1
        assert findings[0].pattern_name == "staged-tool-handoff"

    def test_same_agent_does_not_match_collusion(self):
        det = CrossAgentCollusionDetector()
        events = (
            _ev("loner", "credential:read", 0, 0, kind="credential"),
            _ev("loner", "credential:use", 0, 10, kind="credential"),
        )
        # Same agent both steps -> not collusion.
        assert det.detect(events=events) == ()

    def test_outside_window_does_not_match(self):
        det = CrossAgentCollusionDetector()
        events = (
            _ev("alice", "credential:read", 0, 0, kind="credential"),
            _ev("bob", "credential:use", 0, 3600, kind="credential"),
        )
        # Default window is 60s; 1h gap should not match.
        assert det.detect(events=events) == ()

    def test_custom_rule(self):
        custom = TTPRule(
            rule_id="custom",
            description="custom",
            action_sequence=("step1", "step2", "step3"),
            window_seconds=300.0,
            mitre_attack_id="T9999",
        )
        det = CrossAgentCollusionDetector(rules=(custom,))
        events = (
            _ev("a1", "step1", 0, 0),
            _ev("a2", "step2", 0, 10),
            _ev("a3", "step3", 0, 20),
        )
        findings = det.detect(events=events)
        assert len(findings) == 1
        assert findings[0].pattern_name == "custom"
        assert findings[0].mitre_attack_id == "T9999"

    def test_invalid_rule_rejected(self):
        with pytest.raises(ValueError):
            CrossAgentCollusionDetector(rules=())
        bad_seq = TTPRule(
            rule_id="x",
            description="x",
            action_sequence=("only-one",),
            window_seconds=60,
            mitre_attack_id="T0",
        )
        with pytest.raises(ValueError):
            CrossAgentCollusionDetector(rules=(bad_seq,))


# =============================================================================
# Dispatcher
# =============================================================================


class TestDispatcher:
    def test_dispatcher_aggregates(self):
        events = [_ev("creeper", "tool:x", i // 5, i) for i in range(20)]
        delegations = [_del("hub", f"spoke-{i}", i * 60) for i in range(10)]
        dispatcher = AdversarialDetectorDispatcher(
            [
                SlowRollCapabilityCreepDetector(),
                DelegationGraphShapeDetector(star_target_threshold=5),
            ]
        )
        findings = dispatcher.detect(events=events, delegations=delegations)
        names = {f.pattern_name for f in findings}
        # Both detectors contributed at least one finding.
        assert "slow-roll-capability-creep" in names
        assert "delegation-star-topology" in names

    def test_duplicate_detector_id_rejected(self):
        with pytest.raises(ValueError):
            AdversarialDetectorDispatcher(
                [
                    SlowRollCapabilityCreepDetector(),
                    SlowRollCapabilityCreepDetector(),
                ]
            )

    def test_finding_audit_dict_shape(self):
        det = SlowRollCapabilityCreepDetector()
        events = [_ev("creep", "tool:x", i // 5, i) for i in range(20)]
        findings = det.detect(events=events)
        assert findings, "expected at least one finding"
        audit = findings[0].to_audit_dict()
        assert audit["pattern_name"] == "slow-roll-capability-creep"
        assert audit["mitre_attack_id"] == "T1548"
        assert "evidence" in audit
        assert "detected_at" in audit
