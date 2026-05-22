"""Regression tests for issue #214-S5: op-ledger tenant scoping + monotonic recorded_at.

Sally's review surfaced two T1565 / cross-tenant attacks:

  - Ledger keyed by ``(campaign_id, phase_id, operation_id)`` -- if
    two tenants shared a UUID (collision, tenant import, or a
    malicious tenant_id spoof), one could read or replay the other's
    outcomes.
  - ``recorded_at`` was free-text and never compared against a
    high-water-mark -- a write-race or clock-rewind could serve a
    stale outcome as fresh.

These tests must FAIL against the pre-#214-S5 ledger (no tenant_id
parameter, no monotonic check) and PASS against the fixed version.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.campaign_manager.contracts import OperationOutcome, OperationStatus
from src.services.campaign_manager.exceptions import OperationAlreadyClaimedError
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger

# =============================================================================
# Tenant scoping
# =============================================================================


class TestTenantScoping:
    @pytest.mark.asyncio
    async def test_same_campaign_id_across_tenants_is_independent(self):
        # Two tenants happen to use the same campaign_id (UUID collision,
        # malicious tenant_id spoof, or imported state). The ledger
        # MUST treat them as distinct keys.
        ledger = InMemoryOperationLedger()
        claim_a = await ledger.claim("tenant-A", "shared-uuid", "p1", "op1")
        claim_b = await ledger.claim("tenant-B", "shared-uuid", "p1", "op1")
        # Tenant A claimed first; Tenant B's claim is a NEW claim, not
        # a re-read of A's outcome.
        assert claim_a.status == OperationStatus.CLAIMED
        assert claim_b.status == OperationStatus.CLAIMED
        # And recording an outcome for A does not leak to B.
        await ledger.record_outcome(
            "tenant-A",
            "shared-uuid",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="A succeeded"),
        )
        outcome_b = await ledger.get_outcome("tenant-B", "shared-uuid", "p1", "op1")
        assert outcome_b is None  # B has only claimed; no outcome recorded

    @pytest.mark.asyncio
    async def test_cross_tenant_read_does_not_leak(self):
        # Tenant A records an outcome containing tenant-A-specific
        # summary. Tenant B querying the same (campaign_id, phase, op)
        # gets nothing -- the tenant_id is part of the key.
        ledger = InMemoryOperationLedger()
        await ledger.claim("tenant-A", "c1", "p1", "op1")
        await ledger.record_outcome(
            "tenant-A",
            "c1",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="TENANT_A_SECRET"),
        )
        outcome_b = await ledger.get_outcome("tenant-B", "c1", "p1", "op1")
        assert outcome_b is None
        claim_b = await ledger.claim("tenant-B", "c1", "p1", "op1")
        # B's first claim on the same campaign id is a fresh CLAIMED,
        # not an ALREADY_EXECUTED that leaks A's outcome.
        assert claim_b.status == OperationStatus.CLAIMED
        assert claim_b.prior_outcome is None

    @pytest.mark.asyncio
    async def test_record_outcome_with_wrong_tenant_does_not_satisfy_claim(
        self,
    ):
        # Tenant A claims an op; an attacker tries to record an outcome
        # under tenant B with the same campaign / phase / op_id. The
        # record_outcome MUST raise (no matching claim) rather than
        # silently associating the outcome with B.
        ledger = InMemoryOperationLedger()
        await ledger.claim("tenant-A", "c1", "p1", "op1")
        with pytest.raises(OperationAlreadyClaimedError):
            await ledger.record_outcome(
                "tenant-B",
                "c1",
                "p1",
                "op1",
                OperationOutcome(success=True, summary="injected"),
            )

    @pytest.mark.asyncio
    async def test_independent_high_water_per_tenant(self):
        # Tenant A records a late-timestamped outcome; tenant B's
        # earlier-timestamped outcome on the SAME campaign id MUST be
        # accepted (high-water-mark is per-tenant, not per-campaign-id).
        ledger = InMemoryOperationLedger()
        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        past = datetime(2025, 1, 1, tzinfo=timezone.utc)
        await ledger.claim("tenant-A", "c-shared", "p1", "op1")
        await ledger.record_outcome(
            "tenant-A",
            "c-shared",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="A", recorded_at=future),
        )
        # Tenant B records earlier-timestamped outcome on same campaign id;
        # MUST succeed because tenant B has its own high-water-mark.
        await ledger.claim("tenant-B", "c-shared", "p1", "op1")
        await ledger.record_outcome(
            "tenant-B",
            "c-shared",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="B", recorded_at=past),
        )


# =============================================================================
# Monotonic recorded_at
# =============================================================================


class TestMonotonicRecordedAt:
    @pytest.mark.asyncio
    async def test_in_order_writes_succeed(self):
        ledger = InMemoryOperationLedger()
        t0 = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(3):
            await ledger.claim("t1", "c1", "p1", f"op{i}")
            await ledger.record_outcome(
                "t1",
                "c1",
                "p1",
                f"op{i}",
                OperationOutcome(
                    success=True,
                    summary=f"op{i}",
                    recorded_at=t0 + timedelta(seconds=i),
                ),
            )
        # All three landed.
        for i in range(3):
            outcome = await ledger.get_outcome("t1", "c1", "p1", f"op{i}")
            assert outcome is not None

    @pytest.mark.asyncio
    async def test_clock_rewind_within_tenant_campaign_is_rejected(self):
        # An attacker (or a buggy worker) tries to record an outcome
        # with a recorded_at earlier than the high-water-mark for this
        # (tenant, campaign). MUST raise.
        ledger = InMemoryOperationLedger()
        t1 = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
        t0 = t1 - timedelta(hours=1)
        await ledger.claim("t1", "c1", "p1", "op1")
        await ledger.record_outcome(
            "t1",
            "c1",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="first", recorded_at=t1),
        )
        await ledger.claim("t1", "c1", "p1", "op2")
        with pytest.raises(OperationAlreadyClaimedError, match="earlier"):
            await ledger.record_outcome(
                "t1",
                "c1",
                "p1",
                "op2",
                OperationOutcome(success=True, summary="rewound", recorded_at=t0),
            )

    @pytest.mark.asyncio
    async def test_equal_recorded_at_is_accepted(self):
        # Equal timestamps are allowed -- clock granularity can produce
        # identical timestamps for rapid writes; rejecting equality
        # would be too strict.
        ledger = InMemoryOperationLedger()
        t = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
        await ledger.claim("t1", "c1", "p1", "op1")
        await ledger.record_outcome(
            "t1",
            "c1",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="a", recorded_at=t),
        )
        await ledger.claim("t1", "c1", "p1", "op2")
        await ledger.record_outcome(
            "t1",
            "c1",
            "p1",
            "op2",
            OperationOutcome(success=True, summary="b", recorded_at=t),
        )

    @pytest.mark.asyncio
    async def test_high_water_isolated_per_campaign(self):
        # Two campaigns under the same tenant must have independent
        # high-water-marks. A future-dated outcome in one campaign
        # must NOT block a past-dated outcome in another.
        ledger = InMemoryOperationLedger()
        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        past = datetime(2025, 1, 1, tzinfo=timezone.utc)
        await ledger.claim("t1", "c-future", "p1", "op1")
        await ledger.record_outcome(
            "t1",
            "c-future",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="f", recorded_at=future),
        )
        # Different campaign, earlier timestamp -- must succeed.
        await ledger.claim("t1", "c-past", "p1", "op1")
        await ledger.record_outcome(
            "t1",
            "c-past",
            "p1",
            "op1",
            OperationOutcome(success=True, summary="p", recorded_at=past),
        )
