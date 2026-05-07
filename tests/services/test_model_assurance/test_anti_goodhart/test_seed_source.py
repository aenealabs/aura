"""Tests for the rotation seed source (ADR-088 Phase 3.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.model_assurance.anti_goodhart import (
    AgentControlledSeedSource,
    CronSeedSource,
    InjectedSeedSource,
    SeedBucketGranularity,
    is_agent_controlled,
)


class TestCronSeedSource:
    def test_salt_required(self) -> None:
        with pytest.raises(ValueError, match="salt"):
            CronSeedSource(salt="")

    def test_seed_is_deterministic_within_bucket(self) -> None:
        clock = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)
        a = CronSeedSource(salt="aura-q2", clock=clock).current_seed()
        b = CronSeedSource(salt="aura-q2", clock=clock).current_seed()
        assert a == b

    def test_seed_changes_across_days(self) -> None:
        d1 = datetime(2026, 5, 6, tzinfo=timezone.utc)
        d2 = datetime(2026, 5, 7, tzinfo=timezone.utc)
        a = CronSeedSource(salt="x", clock=d1).current_seed()
        b = CronSeedSource(salt="x", clock=d2).current_seed()
        assert a != b

    def test_seed_changes_across_salts(self) -> None:
        clock = datetime(2026, 5, 6, tzinfo=timezone.utc)
        a = CronSeedSource(salt="a", clock=clock).current_seed()
        b = CronSeedSource(salt="b", clock=clock).current_seed()
        assert a != b

    def test_hourly_changes_each_hour(self) -> None:
        d1 = datetime(2026, 5, 6, 1, tzinfo=timezone.utc)
        d2 = datetime(2026, 5, 6, 2, tzinfo=timezone.utc)
        a = CronSeedSource(
            salt="x", granularity=SeedBucketGranularity.HOURLY, clock=d1,
        ).current_seed()
        b = CronSeedSource(
            salt="x", granularity=SeedBucketGranularity.HOURLY, clock=d2,
        ).current_seed()
        assert a != b

    def test_daily_stable_across_hours(self) -> None:
        d1 = datetime(2026, 5, 6, 1, tzinfo=timezone.utc)
        d2 = datetime(2026, 5, 6, 23, tzinfo=timezone.utc)
        a = CronSeedSource(
            salt="x", granularity=SeedBucketGranularity.DAILY, clock=d1,
        ).current_seed()
        b = CronSeedSource(
            salt="x", granularity=SeedBucketGranularity.DAILY, clock=d2,
        ).current_seed()
        assert a == b

    def test_weekly_stable_within_iso_week(self) -> None:
        # ISO week 19 of 2026
        d1 = datetime(2026, 5, 4, tzinfo=timezone.utc)   # Monday
        d2 = datetime(2026, 5, 10, tzinfo=timezone.utc)  # Sunday
        granularity = SeedBucketGranularity.WEEKLY
        a = CronSeedSource(salt="x", granularity=granularity, clock=d1).current_seed()
        b = CronSeedSource(salt="x", granularity=granularity, clock=d2).current_seed()
        assert a == b

    def test_seed_is_in_unsigned_32bit_range(self) -> None:
        clock = datetime(2026, 5, 6, tzinfo=timezone.utc)
        seed = CronSeedSource(salt="x", clock=clock).current_seed()
        assert 0 <= seed < 2**32

    def test_not_agent_controllable(self) -> None:
        clock = datetime(2026, 5, 6, tzinfo=timezone.utc)
        src = CronSeedSource(salt="x", clock=clock)
        assert is_agent_controlled(src) is False


class TestInjectedSeedSource:
    def test_returns_fixed_seed(self) -> None:
        src = InjectedSeedSource(seed=42)
        assert src.current_seed() == 42
        assert src.current_seed() == 42  # idempotent

    def test_marked_agent_controllable(self) -> None:
        """Injected seed sources are blocklisted in production by the validator."""
        src = InjectedSeedSource(seed=1)
        assert is_agent_controlled(src) is True


class TestAgentControlledSeedSource:
    def test_marked_agent_controllable(self) -> None:
        src = AgentControlledSeedSource(initial_seed=1)
        assert is_agent_controlled(src) is True


class TestProductionValidator:
    def test_only_cron_passes_production_gate(self) -> None:
        # Production deployment validator pseudocode: if any source
        # is_agent_controlled, reject.
        clock = datetime(2026, 5, 6, tzinfo=timezone.utc)
        good = CronSeedSource(salt="x", clock=clock)
        bad1 = InjectedSeedSource(seed=1)
        bad2 = AgentControlledSeedSource(initial_seed=1)
        assert is_agent_controlled(good) is False
        assert is_agent_controlled(bad1) is True
        assert is_agent_controlled(bad2) is True


class TestImmutability:
    def test_cron_source_is_frozen(self) -> None:
        src = CronSeedSource(
            salt="x",
            clock=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )
        with pytest.raises((AttributeError, TypeError)):
            src.salt = "evil"  # type: ignore[misc]
