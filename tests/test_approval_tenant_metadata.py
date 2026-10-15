"""Approval requests created by orchestrators carry tenant scope, and blocked
orchestrations escalate their anomaly instead of reading as in progress."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.anomaly_detection_service import (
    AnomalyDetectionService,
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)


def _anomaly() -> AnomalyEvent:
    return AnomalyEvent(
        id="anom-1",
        type=AnomalyType.NEW_CVE,
        severity=AnomalySeverity.HIGH,
        title="CVE",
        description="test",
        source="test",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["hitl_request_failed", "failed"])
async def test_blocked_orchestration_escalates_anomaly(status):
    service = AnomalyDetectionService()
    orchestrator = MagicMock()
    orchestrator.execute = AsyncMock(
        return_value=SimpleNamespace(
            status=status,
            hitl_required=True,
            hitl_request_id=None,
            success=False,
            task_id="t-1",
        )
    )
    anomaly = _anomaly()
    await service.trigger_orchestrator(anomaly, orchestrator)
    assert anomaly.status == AnomalyStatus.ESCALATED
    assert anomaly.hitl_approval_id is None


@pytest.mark.asyncio
async def test_awaiting_hitl_still_investigating():
    service = AnomalyDetectionService()
    orchestrator = MagicMock()
    orchestrator.execute = AsyncMock(
        return_value=SimpleNamespace(
            status="awaiting_hitl",
            hitl_required=True,
            hitl_request_id="req-9",
            success=False,
            task_id="t-1",
        )
    )
    anomaly = _anomaly()
    await service.trigger_orchestrator(anomaly, orchestrator)
    assert anomaly.status == AnomalyStatus.INVESTIGATING
    assert anomaly.hitl_approval_id == "req-9"


@pytest.mark.asyncio
async def test_system2_approval_carries_organization_id():
    from tests.test_agent_orchestrator import _hitl_ready_orchestrator

    hitl = MagicMock()
    hitl.create_approval_request.return_value = MagicMock(
        approval_id="appr-1",
        patch_id="patch-1",
        created_at="t0",
        expires_at="t1",
        patch_diff="diff",
    )
    orchestrator = _hitl_ready_orchestrator(hitl)

    await orchestrator.execute_request_with_hitl(
        user_prompt="Fix checksum",
        vulnerability_id="VULN-9",
        organization_id="org-acme",
    )

    metadata = hitl.create_approval_request.call_args.kwargs["metadata"]
    assert metadata["organization_id"] == "org-acme"


@pytest.mark.asyncio
async def test_meta_orchestrator_approval_carries_policy_organization():
    from src.agents.meta_orchestrator import AgentCapability, MetaOrchestrator
    from src.services.autonomy_policy_service import AutonomyLevel, AutonomyPolicy
    from tests.test_meta_orchestrator_hitl_guardrails import _hitl_mock, _single_task

    policy = AutonomyPolicy(
        policy_id="policy-acme",
        organization_id="org-acme",
        default_level=AutonomyLevel.FULL_HITL,
    )
    hitl = _hitl_mock()
    orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
    _single_task(orchestrator, AgentCapability.CODE_GENERATION)

    result = await orchestrator.execute(task="Patch the parser", severity="HIGH")

    assert result.status == "awaiting_hitl"
    metadata = hitl.create_approval_request.call_args.kwargs["metadata"]
    assert metadata["organization_id"] == "org-acme"
