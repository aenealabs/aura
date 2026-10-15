"""
Tests for MetaOrchestrator HITL evidence, fail-closed behavior, and the
consolidated autonomy policy (single source of truth in
src.services.autonomy_policy_service).
"""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.agents import meta_orchestrator as meta_module
from src.agents.meta_orchestrator import (
    NO_PATCH_DIFF_MARKER,
    AgentCapability,
    AgentResult,
    AutonomyLevel,
    AutonomyPolicy,
    MetaOrchestrator,
    SpawnableAgent,
    TaskNode,
)
from src.services import autonomy_policy_service
from src.services.hitl_approval_service import (
    HITLApprovalService,
    HITLMode,
    PatchSeverity,
)

# =============================================================================
# Helpers
# =============================================================================


def _register_static_agent(
    orchestrator: MetaOrchestrator,
    capability: AgentCapability,
    output: Any,
) -> None:
    """Register an agent for ``capability`` that returns a fixed output."""

    def factory(
        llm_client: Any = None,
        max_spawn_depth: int = 2,
        can_spawn: bool = True,
        registry: Any = None,
    ) -> SpawnableAgent:
        class StaticAgent(SpawnableAgent):
            @property
            def capability(self) -> AgentCapability:
                return capability

            async def execute(self, task: str, context: Any = None) -> AgentResult:
                return AgentResult(
                    agent_id=self.agent_id,
                    capability=capability,
                    success=True,
                    output=output,
                    execution_time_seconds=0.0,
                )

        return StaticAgent(
            llm_client=llm_client,
            max_spawn_depth=max_spawn_depth,
            can_spawn=can_spawn,
            registry=registry,
        )

    orchestrator.registry.register_agent(capability, factory)


def _single_task(orchestrator: MetaOrchestrator, capability: AgentCapability):
    orchestrator.decomposer.decompose = AsyncMock(
        return_value=[TaskNode.create(description="do work", capability=capability)]
    )


def _hitl_mock(approval_id: str = "approval-abc") -> AsyncMock:
    service = AsyncMock()
    service.create_approval_request = AsyncMock(
        return_value=Mock(
            approval_id=approval_id,
            created_at="2026-01-01T00:00:00",
            expires_at="2026-01-02T00:00:00",
        )
    )
    return service


# =============================================================================
# Consolidation: one source of truth
# =============================================================================


class TestAutonomyPolicyConsolidation:
    """MetaOrchestrator re-exports the service's policy types."""

    def test_reexported_types_are_service_types(self):
        assert AutonomyPolicy is autonomy_policy_service.AutonomyPolicy
        assert AutonomyLevel is autonomy_policy_service.AutonomyLevel
        assert meta_module.AutonomyPolicy is autonomy_policy_service.AutonomyPolicy

    def test_default_guardrails_preserved(self):
        policy = AutonomyPolicy.from_preset("enterprise_standard")
        assert set(policy.guardrails) == {
            "production_deployment",
            "credential_modification",
            "access_control_change",
            "database_migration",
            "infrastructure_change",
        }

    def test_immutable_guardrails_present(self):
        assert {
            "credential_modification",
            "production_deployment",
        } <= AutonomyPolicy.IMMUTABLE_GUARDRAILS

    def test_from_preset_without_organization_id(self):
        policy = AutonomyPolicy.from_preset("fintech_startup")
        assert policy.organization_id == "default"
        assert policy.preset_name == "fintech_startup"


# =============================================================================
# Guardrails on the MetaOrchestrator execution path
# =============================================================================


class TestMetaOrchestratorGuardrails:
    """IMMUTABLE_GUARDRAILS must be honored by MetaOrchestrator.execute()."""

    @pytest.mark.asyncio
    async def test_production_deployment_requires_hitl_with_fully_autonomous_preset(
        self,
    ):
        policy = AutonomyPolicy.from_preset("fully_autonomous")
        assert policy.hitl_enabled is False
        assert policy.default_level == AutonomyLevel.FULL_AUTONOMOUS

        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(
            task="Deploy release to production",
            repository="org/app",
            severity="LOW",
        )

        assert result.status == "awaiting_hitl"
        assert result.hitl_required is True
        assert result.auto_approved is False
        assert result.hitl_request_id == "approval-abc"
        hitl.create_approval_request.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("task", "operation"),
        [
            ("Deploy release to production", "production_deployment"),
            ("Rotate the database password", "credential_modification"),
        ],
    )
    async def test_immutable_guardrails_cannot_be_configured_away(
        self, task: str, operation: str
    ):
        """Even with guardrails emptied and an explicit override, HITL holds."""
        policy = AutonomyPolicy(
            policy_id="policy-test",
            organization_id="org-test",
            hitl_enabled=False,
            default_level=AutonomyLevel.FULL_AUTONOMOUS,
            operation_overrides={operation: AutonomyLevel.FULL_AUTONOMOUS},
            guardrails=[],
        )
        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        assert orchestrator._classify_operation(task) == operation
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task=task, severity="LOW")

        assert result.status == "awaiting_hitl"
        assert result.hitl_required is True
        assert result.auto_approved is False

    @pytest.mark.asyncio
    async def test_non_guardrail_operation_auto_approves_when_hitl_disabled(self):
        """Control: the same preset auto-approves a non-guardrail operation."""
        policy = AutonomyPolicy.from_preset("fully_autonomous")
        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.DOCUMENTATION)

        result = await orchestrator.execute(
            task="Write a summary document", severity="CRITICAL"
        )

        assert result.status == "completed"
        assert result.auto_approved is True
        hitl.create_approval_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_hitl_master_toggle_respected_for_full_hitl_default(self):
        """hitl_enabled=False skips HITL for non-guardrail ops, with audit."""
        policy = AutonomyPolicy(
            policy_id="policy-test",
            organization_id="org-test",
            hitl_enabled=False,
            default_level=AutonomyLevel.FULL_HITL,
        )
        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.DOCUMENTATION)

        result = await orchestrator.execute(task="Write a summary", severity="HIGH")

        assert result.status == "completed"
        assert result.audit_logged is True
        hitl.create_approval_request.assert_not_called()


# =============================================================================
# HITL evidence
# =============================================================================


class TestHITLEvidence:
    """Approval requests carry real evidence, or explicit 'not run' markers."""

    @pytest.mark.asyncio
    async def test_evidence_passed_to_approval_and_notification(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = _hitl_mock()
        notifier = Mock()
        notifier.send_approval_notification = Mock(return_value=[])
        orchestrator = MetaOrchestrator(
            autonomy_policy=policy,
            hitl_service=hitl,
            notification_service=notifier,
        )
        _register_static_agent(
            orchestrator,
            AgentCapability.CODE_GENERATION,
            {
                "original_code": "h = hashlib.sha1(x)\n",
                "patched_code": "h = hashlib.sha256(x)\n",
                "changes_made": "sha1 -> sha256",
            },
        )
        _register_static_agent(
            orchestrator,
            AgentCapability.PATCH_VALIDATION,
            {
                "valid": True,
                "static_validation": {"valid": True},
                "sandbox_validation": {"sandbox_valid": True, "tests_run": 12},
            },
        )
        _register_static_agent(
            orchestrator,
            AgentCapability.SECURITY_REVIEW,
            {
                "status": "PASS",
                "finding": "Patch is secure",
                "vulnerabilities": [],
            },
        )
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create("gen", AgentCapability.CODE_GENERATION),
                TaskNode.create("validate", AgentCapability.PATCH_VALIDATION),
                TaskNode.create("review", AgentCapability.SECURITY_REVIEW),
            ]
        )

        result = await orchestrator.execute(
            task="Fix weak hash", repository="org/app", severity="HIGH"
        )

        assert result.status == "awaiting_hitl"
        kwargs = hitl.create_approval_request.await_args.kwargs
        assert "-h = hashlib.sha1(x)" in kwargs["patch_diff"]
        assert "+h = hashlib.sha256(x)" in kwargs["patch_diff"]
        assert kwargs["original_code"] == "h = hashlib.sha1(x)\n"
        assert kwargs["severity"] == PatchSeverity.HIGH
        sandbox = kwargs["sandbox_results"]
        assert sandbox["status"] == "completed"
        assert sandbox["passed"] is True
        assert sandbox["runs"][0]["tests_run"] == 12
        metadata = kwargs["metadata"]
        assert metadata["severity"] == "HIGH"
        assert metadata["patch_diff_available"] is True
        assert metadata["review_findings"][0]["finding"] == "Patch is secure"

        notify_kwargs = notifier.send_approval_notification.call_args.kwargs
        assert notify_kwargs["approval_id"] == "approval-abc"
        assert notify_kwargs["sandbox_results"] == sandbox
        assert notify_kwargs["patch_diff"] == kwargs["patch_diff"]
        assert notify_kwargs["expires_at"] == "2026-01-02T00:00:00"

    @pytest.mark.asyncio
    async def test_missing_evidence_is_marked_not_run(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.DOCUMENTATION)

        result = await orchestrator.execute(task="Summarize", severity="HIGH")

        assert result.status == "awaiting_hitl"
        kwargs = hitl.create_approval_request.await_args.kwargs
        assert kwargs["sandbox_results"]["status"] == "not_run"
        assert kwargs["sandbox_results"]["reason"]
        assert kwargs["sandbox_results"] != {}
        assert kwargs["patch_diff"] == NO_PATCH_DIFF_MARKER
        assert kwargs["metadata"]["patch_diff_available"] is False

    @pytest.mark.asyncio
    async def test_failed_sandbox_reported_as_not_passed(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = _hitl_mock()
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _register_static_agent(
            orchestrator,
            AgentCapability.PATCH_VALIDATION,
            {"valid": False, "sandbox_validation": {"sandbox_valid": False}},
        )
        _single_task(orchestrator, AgentCapability.PATCH_VALIDATION)

        await orchestrator.execute(task="Validate in sandbox", severity="HIGH")

        sandbox = hitl.create_approval_request.await_args.kwargs["sandbox_results"]
        assert sandbox["status"] == "completed"
        assert sandbox["passed"] is False

    @pytest.mark.asyncio
    async def test_real_sync_hitl_service_receives_evidence(self):
        """The real (synchronous) HITLApprovalService works on this path."""
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = HITLApprovalService(mode=HITLMode.MOCK)
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _register_static_agent(
            orchestrator,
            AgentCapability.CODE_GENERATION,
            {"original_code": "a = 1\n", "patched_code": "a = 2\n"},
        )
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="CRITICAL")

        assert result.status == "awaiting_hitl"
        assert result.hitl_request_id
        request = hitl.get_request(result.hitl_request_id)
        assert request is not None
        assert request.severity == PatchSeverity.CRITICAL
        assert "+a = 2" in request.patch_diff
        assert request.sandbox_test_results["status"] == "not_run"


# =============================================================================
# Fail-closed HITL request creation
# =============================================================================


class TestHITLFailClosed:
    """If an approval request cannot be created, execution is blocked."""

    @pytest.mark.asyncio
    async def test_hitl_create_exception_blocks(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = AsyncMock()
        hitl.create_approval_request = AsyncMock(
            side_effect=RuntimeError("dynamodb unavailable")
        )
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="HIGH")

        assert result.status == "hitl_request_failed"
        assert result.status != "awaiting_hitl"
        assert result.hitl_required is True
        assert result.auto_approved is False
        assert result.hitl_request_id is None
        assert "dynamodb unavailable" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_hitl_service_blocks(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=None)
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="HIGH")

        assert result.status == "hitl_request_failed"
        assert result.auto_approved is False
        assert "no HITL service" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_approval_id_blocks(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = AsyncMock()
        hitl.create_approval_request = AsyncMock(return_value={"status": "pending"})
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="HIGH")

        assert result.status == "hitl_request_failed"
        assert result.hitl_request_id is None

    @pytest.mark.asyncio
    async def test_dict_request_id_accepted(self):
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = AsyncMock()
        hitl.create_approval_request = AsyncMock(
            return_value={"request_id": "req-1", "status": "pending"}
        )
        orchestrator = MetaOrchestrator(autonomy_policy=policy, hitl_service=hitl)
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="HIGH")

        assert result.status == "awaiting_hitl"
        assert result.hitl_request_id == "req-1"

    @pytest.mark.asyncio
    async def test_notification_failure_keeps_pending_request(self):
        """A created request stays approvable even if notification fails."""
        policy = AutonomyPolicy.from_preset("defense_contractor")
        hitl = _hitl_mock()
        notifier = AsyncMock()
        notifier.send_approval_notification = AsyncMock(
            side_effect=RuntimeError("ses down")
        )
        orchestrator = MetaOrchestrator(
            autonomy_policy=policy, hitl_service=hitl, notification_service=notifier
        )
        _single_task(orchestrator, AgentCapability.CODE_GENERATION)

        result = await orchestrator.execute(task="Fix bug", severity="HIGH")

        assert result.status == "awaiting_hitl"
        assert result.hitl_request_id == "approval-abc"

    def test_unknown_severity_passed_through(self):
        """Non-standard severities are passed as-is rather than crashing."""
        assert MetaOrchestrator._to_patch_severity("weird") == "weird"
        assert MetaOrchestrator._to_patch_severity("low") == PatchSeverity.LOW
