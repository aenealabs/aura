"""Tests for the model-upgrade re-validation watcher (issue #212)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pytest

from src.services.model_assurance.model_upgrade_watcher import (
    BedrockModelVersion,
    ModelVersionWatcher,
    RevalidationCoordinator,
    RevalidationStatus,
)

# =============================================================================
# Fakes
# =============================================================================


@dataclass
class _FakeRegistry:
    versions: tuple[BedrockModelVersion, ...] = ()

    def current_versions(self) -> tuple[BedrockModelVersion, ...]:
        return self.versions


@dataclass
class _FakeFlag:
    set_tiers: set[str] = field(default_factory=set)
    set_reasons: dict[str, str] = field(default_factory=dict)
    cleared_tiers: list[str] = field(default_factory=list)

    def is_set(self, *, tier: str) -> bool:
        return tier in self.set_tiers

    def set(self, *, tier: str, reason: str) -> None:
        self.set_tiers.add(tier)
        self.set_reasons[tier] = reason

    def clear(self, *, tier: str) -> None:
        self.set_tiers.discard(tier)
        self.cleared_tiers.append(tier)


@dataclass
class _FakeOracle:
    pass_count: int = 380
    total_count: int = 400
    raise_for_tier: Optional[str] = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    def rerun_reference_cases(
        self, *, tier: str, model_identity: str
    ) -> tuple[int, int]:
        self.calls.append((tier, model_identity))
        if self.raise_for_tier and tier == self.raise_for_tier:
            raise RuntimeError("oracle simulated failure")
        return self.pass_count, self.total_count


@dataclass
class _FakeIncident:
    opened: list[tuple[str, str, int, int, str]] = field(default_factory=list)
    next_ticket: int = 1

    def open_incident(
        self,
        *,
        tier: str,
        model_identity: str,
        cases_passed: int,
        cases_total: int,
        rationale: str,
    ) -> str:
        self.opened.append((tier, model_identity, cases_passed, cases_total, rationale))
        ticket = f"INC-{self.next_ticket}"
        self.next_ticket += 1
        return ticket


@dataclass
class _FakeMetric:
    emitted: list[dict] = field(default_factory=list)

    def emit(
        self,
        *,
        tier: str,
        model_identity: str,
        status: str,
        cases_passed: int,
        cases_total: int,
    ) -> None:
        self.emitted.append(
            {
                "tier": tier,
                "model_identity": model_identity,
                "status": status,
                "cases_passed": cases_passed,
                "cases_total": cases_total,
            }
        )


# =============================================================================
# Watcher
# =============================================================================


class TestModelVersionWatcher:
    def test_no_initial_snapshot_treats_first_tick_as_bump(self):
        registry = _FakeRegistry(
            versions=(BedrockModelVersion(tier="STANDARD", model_id="m1"),)
        )
        watcher = ModelVersionWatcher(registry=registry)
        events = watcher.tick()
        assert len(events) == 1
        assert events[0].tier == "STANDARD"
        assert events[0].is_bump is True
        assert events[0].previous.identity == ""

    def test_same_version_on_next_tick_is_not_a_bump(self):
        registry = _FakeRegistry(
            versions=(BedrockModelVersion(tier="STANDARD", model_id="m1"),)
        )
        watcher = ModelVersionWatcher(
            registry=registry,
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        )
        events = watcher.tick()
        assert len(events) == 1
        assert events[0].is_bump is False

    def test_bump_detected_when_model_id_changes(self):
        registry = _FakeRegistry(
            versions=(BedrockModelVersion(tier="STANDARD", model_id="m2"),)
        )
        watcher = ModelVersionWatcher(
            registry=registry,
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        )
        events = watcher.tick()
        assert events[0].is_bump is True
        assert events[0].previous.identity == "m1"
        assert events[0].current.identity == "m2"

    def test_bump_detected_when_version_changes_only(self):
        registry = _FakeRegistry(
            versions=(
                BedrockModelVersion(tier="STANDARD", model_id="claude", version="4.7"),
            )
        )
        watcher = ModelVersionWatcher(
            registry=registry,
            initial_snapshot=(
                BedrockModelVersion(tier="STANDARD", model_id="claude", version="4.6"),
            ),
        )
        events = watcher.tick()
        assert events[0].is_bump is True


# =============================================================================
# Coordinator
# =============================================================================


class TestRevalidationCoordinator:
    def _make(self, **overrides):
        flag = overrides.get("flag", _FakeFlag())
        oracle = overrides.get("oracle", _FakeOracle())
        incident = overrides.get("incident", _FakeIncident())
        metric = overrides.get("metric", _FakeMetric())
        threshold = overrides.get("pass_rate_threshold", 0.95)
        return (
            RevalidationCoordinator(
                flag=flag,
                oracle=oracle,
                incident=incident,
                metric=metric,
                pass_rate_threshold=threshold,
            ),
            flag,
            oracle,
            incident,
            metric,
        )

    def test_no_bump_results_in_skipped(self):
        coord, flag, oracle, incident, metric = self._make()
        events = ModelVersionWatcher(
            registry=_FakeRegistry(
                versions=(BedrockModelVersion(tier="STANDARD", model_id="m1"),)
            ),
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        ).tick()
        outcomes = coord.process(events)
        assert len(outcomes) == 1
        assert outcomes[0].status == RevalidationStatus.SKIPPED
        assert flag.set_tiers == set()
        assert metric.emitted == []
        assert incident.opened == []
        assert oracle.calls == []

    def test_bump_pass_clears_flag_and_emits_metric(self):
        oracle = _FakeOracle(pass_count=390, total_count=400)  # 0.975 > 0.95
        coord, flag, oracle, incident, metric = self._make(oracle=oracle)
        events = ModelVersionWatcher(
            registry=_FakeRegistry(
                versions=(BedrockModelVersion(tier="STANDARD", model_id="m2"),)
            ),
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        ).tick()
        outcomes = coord.process(events)
        assert outcomes[0].status == RevalidationStatus.PASSED
        assert outcomes[0].flag_set is True
        assert outcomes[0].flag_cleared is True
        assert outcomes[0].metric_emitted is True
        assert outcomes[0].incident_ticket_id == ""
        # Flag was set then cleared.
        assert "STANDARD" not in flag.set_tiers
        assert "STANDARD" in flag.cleared_tiers
        # Metric emitted with PASSED status.
        assert len(metric.emitted) == 1
        assert metric.emitted[0]["status"] == "passed"
        # No incident.
        assert incident.opened == []

    def test_bump_below_threshold_opens_hitl_incident(self):
        oracle = _FakeOracle(pass_count=300, total_count=400)  # 0.75 < 0.95
        coord, flag, oracle, incident, metric = self._make(oracle=oracle)
        events = ModelVersionWatcher(
            registry=_FakeRegistry(
                versions=(BedrockModelVersion(tier="ADVANCED", model_id="m2"),)
            ),
            initial_snapshot=(BedrockModelVersion(tier="ADVANCED", model_id="m1"),),
        ).tick()
        outcomes = coord.process(events)
        assert outcomes[0].status == RevalidationStatus.FAILED
        # Flag stays set.
        assert "ADVANCED" in flag.set_tiers
        assert flag.cleared_tiers == []
        # Incident opened with INC-1.
        assert len(incident.opened) == 1
        opened = incident.opened[0]
        assert opened[0] == "ADVANCED"
        assert opened[2] == 300
        assert opened[3] == 400
        assert outcomes[0].incident_ticket_id == "INC-1"
        # Metric emitted with FAILED status.
        assert metric.emitted[0]["status"] == "failed"

    def test_oracle_exception_treated_as_failed(self):
        oracle = _FakeOracle(raise_for_tier="STANDARD")
        coord, flag, oracle, incident, metric = self._make(oracle=oracle)
        events = ModelVersionWatcher(
            registry=_FakeRegistry(
                versions=(BedrockModelVersion(tier="STANDARD", model_id="m2"),)
            ),
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        ).tick()
        outcomes = coord.process(events)
        assert outcomes[0].status == RevalidationStatus.FAILED
        assert outcomes[0].incident_ticket_id == "INC-1"
        assert "oracle raised" in outcomes[0].rationale.lower()
        # Flag stays set.
        assert "STANDARD" in flag.set_tiers

    def test_multiple_tiers_processed_independently(self):
        # STANDARD bumps and passes; ADVANCED bumps and fails.
        registry = _FakeRegistry(
            versions=(
                BedrockModelVersion(tier="STANDARD", model_id="s2"),
                BedrockModelVersion(tier="ADVANCED", model_id="a2"),
            )
        )
        watcher = ModelVersionWatcher(
            registry=registry,
            initial_snapshot=(
                BedrockModelVersion(tier="STANDARD", model_id="s1"),
                BedrockModelVersion(tier="ADVANCED", model_id="a1"),
            ),
        )
        events = watcher.tick()

        # Use an oracle that fails ADVANCED only.
        class _SplitOracle:
            calls: list[str] = []

            def rerun_reference_cases(self, *, tier: str, model_identity: str):
                self.calls.append(tier)
                if tier == "ADVANCED":
                    return 200, 400  # 0.5 < 0.95
                return 400, 400  # 1.0 >= 0.95

        oracle = _SplitOracle()
        flag = _FakeFlag()
        incident = _FakeIncident()
        metric = _FakeMetric()
        coord = RevalidationCoordinator(
            flag=flag, oracle=oracle, incident=incident, metric=metric
        )
        outcomes = coord.process(events)

        statuses = {o.tier: o.status for o in outcomes}
        assert statuses["STANDARD"] == RevalidationStatus.PASSED
        assert statuses["ADVANCED"] == RevalidationStatus.FAILED
        # STANDARD: flag set then cleared. ADVANCED: flag stays set + incident.
        assert "STANDARD" not in flag.set_tiers
        assert "ADVANCED" in flag.set_tiers
        assert len(incident.opened) == 1
        assert incident.opened[0][0] == "ADVANCED"
        assert len(metric.emitted) == 2

    def test_pass_rate_threshold_validation(self):
        flag = _FakeFlag()
        oracle = _FakeOracle()
        incident = _FakeIncident()
        metric = _FakeMetric()
        with pytest.raises(ValueError):
            RevalidationCoordinator(
                flag=flag,
                oracle=oracle,
                incident=incident,
                metric=metric,
                pass_rate_threshold=1.5,
            )
        with pytest.raises(ValueError):
            RevalidationCoordinator(
                flag=flag,
                oracle=oracle,
                incident=incident,
                metric=metric,
                pass_rate_threshold=0.0,
            )

    def test_outcome_audit_dict_shape(self):
        coord, _flag, _oracle, _incident, _metric = self._make()
        events = ModelVersionWatcher(
            registry=_FakeRegistry(
                versions=(BedrockModelVersion(tier="STANDARD", model_id="m2"),)
            ),
            initial_snapshot=(BedrockModelVersion(tier="STANDARD", model_id="m1"),),
        ).tick()
        outcomes = coord.process(events)
        audit = outcomes[0].to_audit_dict()
        for key in (
            "status",
            "tier",
            "model_identity",
            "cases_total",
            "cases_passed",
            "rationale",
            "incident_ticket_id",
            "flag_cleared",
            "flag_set",
            "metric_emitted",
            "completed_at",
        ):
            assert key in audit
