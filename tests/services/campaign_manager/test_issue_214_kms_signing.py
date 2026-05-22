"""Regression tests for issue #214 S1+S2: KMS signing.

Sally's review surfaced two T1565.001 (Stored Data Manipulation)
attacks on PR #208:

  - S1: ``CampaignDefinition.definition_signature`` defaulted to ``""``
    and was never verified. Anyone with DynamoDB write could mutate
    ``cost_cap_usd``, ``approver_quorum``, or ``hitl_milestones``
    post-creation.
  - S2: ``PhaseCheckpoint.kms_signature`` was populated by
    ``_dummy_kms_signature()`` returning ``"unsigned:<id>"``. The
    resume path trusted any non-empty string.

These tests must FAIL against the pre-fix code (no signature
enforcement, dummy signatures) and PASS against the fixed
implementation. Tests cover positive paths, tamper detection,
fail-closed semantics for ``require_signed_input``, and the
canonical-bytes contract.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace

import pytest

from src.services.campaign_manager.checkpoint_store import InMemoryCheckpointStore
from src.services.campaign_manager.contracts import (
    CampaignDefinition,
    CampaignStatus,
    CampaignType,
    PhaseCheckpoint,
)
from src.services.campaign_manager.exceptions import TamperedStateError
from src.services.campaign_manager.kms_signing import (
    DeterministicCampaignSigner,
    SignatureVerificationError,
    canonicalize_campaign_definition,
    canonicalize_phase_checkpoint,
)
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases.compliance_hardening import (
    ComplianceHardeningWorker,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup

# =============================================================================
# Canonical bytes
# =============================================================================


def _unsigned_definition(**overrides) -> CampaignDefinition:
    defaults = dict(
        campaign_id=str(uuid.uuid4()),
        tenant_id="tenant-sig",
        campaign_type=CampaignType.COMPLIANCE_HARDENING,
        target={"repo": "acme/api"},
        success_criteria={"standard": "NIST-800-53"},
        cost_cap_usd=200.0,
        wall_clock_budget_hours=12.0,
        autonomy_policy_id="policy-conservative",
        hitl_milestones=("hitl_review",),
        approver_quorum=2,
        creator_principal_arn="arn:aws:iam::123:user/alice",
    )
    defaults.update(overrides)
    return CampaignDefinition(**defaults)


class TestCanonicalBytes:
    def test_signature_field_excluded_from_canonical_bytes(self):
        d1 = _unsigned_definition()
        d2 = replace(d1, definition_signature="some-other-sig")
        # Two definitions identical except for the signature must
        # produce the same canonical bytes (otherwise signing would
        # be impossible).
        assert canonicalize_campaign_definition(d1) == canonicalize_campaign_definition(
            d2
        )

    def test_field_change_changes_canonical_bytes(self):
        d1 = _unsigned_definition(cost_cap_usd=100.0)
        d2 = replace(d1, cost_cap_usd=999.0)
        assert canonicalize_campaign_definition(d1) != canonicalize_campaign_definition(
            d2
        )

    def test_created_at_excluded_from_canonical_bytes(self):
        # Time-of-creation must not be part of the signed payload --
        # otherwise tests would fail any time the clock advanced.
        import datetime

        d1 = _unsigned_definition()
        d2 = replace(
            d1, created_at=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        )
        assert canonicalize_campaign_definition(d1) == canonicalize_campaign_definition(
            d2
        )

    def test_checkpoint_canonical_excludes_signature(self):
        cp = PhaseCheckpoint(
            campaign_id="c1",
            phase_id="p1",
            artifact_manifest=(),
            success_criteria_progress=(),
            phase_summary="done",
            kms_signature="sig-A",
        )
        cp_other_sig = replace(cp, kms_signature="sig-B")
        assert canonicalize_phase_checkpoint(cp) == canonicalize_phase_checkpoint(
            cp_other_sig
        )


# =============================================================================
# DeterministicCampaignSigner
# =============================================================================


class TestDeterministicSigner:
    def test_sign_then_verify_passes(self):
        signer = DeterministicCampaignSigner()
        sig = signer.sign(payload=b"hello", key_id="k1")
        assert signer.verify(payload=b"hello", signature=sig, key_id="k1")

    def test_modified_payload_fails_verify(self):
        signer = DeterministicCampaignSigner()
        sig = signer.sign(payload=b"hello", key_id="k1")
        assert not signer.verify(payload=b"goodbye", signature=sig, key_id="k1")

    def test_wrong_key_id_fails_verify(self):
        signer = DeterministicCampaignSigner()
        sig = signer.sign(payload=b"hello", key_id="k1")
        assert not signer.verify(payload=b"hello", signature=sig, key_id="k2")

    def test_two_signers_with_different_seeds_disagree(self):
        a = DeterministicCampaignSigner(seed=b"alpha")
        b = DeterministicCampaignSigner(seed=b"beta")
        sig = a.sign(payload=b"x", key_id="k")
        assert b.verify(payload=b"x", signature=sig, key_id="k") is False

    def test_deterministic_signature(self):
        signer = DeterministicCampaignSigner()
        a = signer.sign(payload=b"x", key_id="k")
        b = signer.sign(payload=b"x", key_id="k")
        assert a == b


# =============================================================================
# S1: definition signing in the orchestrator
# =============================================================================


@pytest.fixture()
async def orchestrator_with_default_signer() -> CampaignOrchestrator:
    rollup = InMemoryTenantCostRollup()
    await rollup.set_cap("tenant-sig", "2026-05", cap_usd=10_000.0)
    return CampaignOrchestrator(
        state_store=InMemoryCampaignStateStore(),
        checkpoint_store=InMemoryCheckpointStore(),
        operation_ledger=InMemoryOperationLedger(),
        tenant_rollup=rollup,
        worker_registry={
            CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
        },
    )


class TestS1DefinitionSignature:
    @pytest.mark.asyncio
    async def test_unsigned_definition_is_signed_by_default(
        self, orchestrator_with_default_signer
    ):
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        assert unsigned.definition_signature == ""
        state = await orch.create_campaign(unsigned, "2026-05")
        # Orchestrator stored a signed copy internally.
        signed = orch._signed_definitions[(unsigned.tenant_id, unsigned.campaign_id)]
        assert signed.definition_signature != ""
        assert state.status == CampaignStatus.CREATED

    @pytest.mark.asyncio
    async def test_tampered_definition_is_rejected_on_next_call(
        self, orchestrator_with_default_signer
    ):
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        signed = orch._signed_definitions[(unsigned.tenant_id, unsigned.campaign_id)]
        # An attacker mutates cost_cap_usd, keeping the old signature.
        tampered = replace(signed, cost_cap_usd=1_000_000.0)
        with pytest.raises(SignatureVerificationError, match="does not verify"):
            await orch.run_next_phase(tampered)

    @pytest.mark.asyncio
    async def test_tampered_quorum_is_rejected(self, orchestrator_with_default_signer):
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        signed = orch._signed_definitions[(unsigned.tenant_id, unsigned.campaign_id)]
        # Attacker lowers approver_quorum from 2 to 1 to skip co-approval.
        tampered = replace(signed, approver_quorum=1)
        with pytest.raises(SignatureVerificationError):
            await orch.approve_milestone(
                tampered, approver_principal_arn="arn:aws:iam::123:user/bob"
            )

    @pytest.mark.asyncio
    async def test_signed_definition_round_trips(
        self, orchestrator_with_default_signer
    ):
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        # External pre-sign (production-shape: API layer signs).
        pre_signed = orch._sign_definition(unsigned)
        state = await orch.create_campaign(pre_signed, "2026-05")
        assert state.status == CampaignStatus.CREATED
        # Now run a phase using the externally-signed definition.
        state = await orch.run_next_phase(pre_signed)
        assert state.status != CampaignStatus.FAILED

    @pytest.mark.asyncio
    async def test_require_signed_input_rejects_unsigned(self):
        rollup = InMemoryTenantCostRollup()
        await rollup.set_cap("tenant-sig", "2026-05", cap_usd=10_000.0)
        orch = CampaignOrchestrator(
            state_store=InMemoryCampaignStateStore(),
            checkpoint_store=InMemoryCheckpointStore(),
            operation_ledger=InMemoryOperationLedger(),
            tenant_rollup=rollup,
            worker_registry={
                CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
            },
            require_signed_input=True,
        )
        unsigned = _unsigned_definition()
        with pytest.raises(SignatureVerificationError, match="API layer must sign"):
            await orch.create_campaign(unsigned, "2026-05")

    @pytest.mark.asyncio
    async def test_require_signed_input_accepts_pre_signed(self):
        rollup = InMemoryTenantCostRollup()
        await rollup.set_cap("tenant-sig", "2026-05", cap_usd=10_000.0)
        signer = DeterministicCampaignSigner()
        orch = CampaignOrchestrator(
            state_store=InMemoryCampaignStateStore(),
            checkpoint_store=InMemoryCheckpointStore(),
            operation_ledger=InMemoryOperationLedger(),
            tenant_rollup=rollup,
            worker_registry={
                CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
            },
            signer=signer,
            require_signed_input=True,
        )
        unsigned = _unsigned_definition()
        # Sign with the same signer the orchestrator was given.
        signed = orch._sign_definition(unsigned)
        state = await orch.create_campaign(signed, "2026-05")
        assert state.status == CampaignStatus.CREATED


# =============================================================================
# S2: checkpoint signing in the orchestrator
# =============================================================================


class TestS2CheckpointSignature:
    @pytest.mark.asyncio
    async def test_checkpoint_carries_real_signature_not_dummy(
        self, orchestrator_with_default_signer
    ):
        orch = orchestrator_with_default_signer
        store: InMemoryCheckpointStore = orch._checkpoint_store  # type: ignore[assignment]
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        await orch.run_next_phase(unsigned)
        # The first phase (baseline_scan) wrote a checkpoint.
        cp = await store.read(unsigned.campaign_id, "baseline_scan")
        assert cp is not None
        assert cp.kms_signature != ""
        # The pre-fix _dummy_kms_signature returned 'unsigned:<id>'.
        assert not cp.kms_signature.startswith("unsigned:")

    @pytest.mark.asyncio
    async def test_checkpoint_verifies_on_resume(
        self, orchestrator_with_default_signer
    ):
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        # Drive past the first phase so a checkpoint exists.
        state = await orch.run_next_phase(unsigned)
        assert state.status != CampaignStatus.FAILED
        # Subsequent run_next_phase reads + verifies the prior checkpoint.
        # Should NOT raise.
        state2 = await orch.run_next_phase(unsigned)
        assert state2.status != CampaignStatus.FAILED

    @pytest.mark.asyncio
    async def test_tampered_checkpoint_raises_on_verify(
        self, orchestrator_with_default_signer
    ):
        # The orchestrator's resume path only reads the current phase's
        # prior checkpoint (used for retry / resume within the same
        # phase). To exercise the tamper-detection contract without
        # adding a retry-from-failed path to the state machine, call
        # the verifier directly on a tampered checkpoint -- this is
        # the exact code path the orchestrator runs after every
        # checkpoint_store.read().
        orch = orchestrator_with_default_signer
        store: InMemoryCheckpointStore = orch._checkpoint_store  # type: ignore[assignment]
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        await orch.run_next_phase(unsigned)
        # Read the stored checkpoint, tamper with phase_summary while
        # keeping the old signature.
        original = await store.read(unsigned.campaign_id, "baseline_scan")
        assert original is not None
        tampered = replace(original, phase_summary="MALICIOUS REPLACEMENT")
        signed_def = orch._signed_definitions[
            (unsigned.tenant_id, unsigned.campaign_id)
        ]
        with pytest.raises(TamperedStateError, match="does not verify"):
            orch._verify_checkpoint(tampered, signed_def)

    @pytest.mark.asyncio
    async def test_tampered_checkpoint_with_pristine_signature_still_verifies(
        self, orchestrator_with_default_signer
    ):
        # Sanity check: an UN-tampered checkpoint must verify cleanly.
        orch = orchestrator_with_default_signer
        store: InMemoryCheckpointStore = orch._checkpoint_store  # type: ignore[assignment]
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        await orch.run_next_phase(unsigned)
        cp = await store.read(unsigned.campaign_id, "baseline_scan")
        assert cp is not None
        signed_def = orch._signed_definitions[
            (unsigned.tenant_id, unsigned.campaign_id)
        ]
        # Should NOT raise.
        orch._verify_checkpoint(cp, signed_def)

    @pytest.mark.asyncio
    async def test_signer_rotation_invalidates_old_checkpoints(self):
        # Two signers with distinct seeds simulate a key rotation.
        rollup = InMemoryTenantCostRollup()
        await rollup.set_cap("tenant-sig", "2026-05", cap_usd=10_000.0)
        old_signer = DeterministicCampaignSigner(seed=b"old-key")
        store = InMemoryCheckpointStore()
        ledger = InMemoryOperationLedger()
        state_store = InMemoryCampaignStateStore()

        orch_old = CampaignOrchestrator(
            state_store=state_store,
            checkpoint_store=store,
            operation_ledger=ledger,
            tenant_rollup=rollup,
            worker_registry={
                CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
            },
            signer=old_signer,
        )
        unsigned = _unsigned_definition()
        signed = orch_old._sign_definition(unsigned)
        await orch_old.create_campaign(signed, "2026-05")
        await orch_old.run_next_phase(signed)
        # A new orchestrator with a different key tries to resume.
        new_signer = DeterministicCampaignSigner(seed=b"new-key")
        orch_new = CampaignOrchestrator(
            state_store=state_store,
            checkpoint_store=store,
            operation_ledger=ledger,
            tenant_rollup=rollup,
            worker_registry={
                CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
            },
            signer=new_signer,
        )
        # Verification of the existing signed definition under the new
        # key fails (T1565: definition path is the first wall).
        with pytest.raises(SignatureVerificationError):
            await orch_new.run_next_phase(signed)


# =============================================================================
# Backward compatibility -- the 42 original tests must still pass
# (covered by running the full suite; this is a smoke test).
# =============================================================================


class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_unsigned_definitions_still_work_in_legacy_mode(
        self, orchestrator_with_default_signer
    ):
        # The 42 pre-existing tests pass unsigned definitions to the
        # orchestrator. Default require_signed_input=False auto-signs
        # them so those tests keep passing without modification.
        orch = orchestrator_with_default_signer
        unsigned = _unsigned_definition()
        await orch.create_campaign(unsigned, "2026-05")
        bob = "arn:aws:iam::123:user/bob"
        carol = "arn:aws:iam::123:user/carol"
        for _ in range(40):
            state = await orch.run_next_phase(unsigned)
            if state.status == CampaignStatus.AWAITING_HITL:
                await orch.approve_milestone(unsigned, approver_principal_arn=bob)
                state = await orch.approve_milestone(
                    unsigned, approver_principal_arn=carol
                )
                continue
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.COMPLETED
