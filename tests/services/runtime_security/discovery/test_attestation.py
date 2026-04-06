"""
Tests for the Decommission Attestation Service (ADR-086 Phase 1).

Covers attestation creation, verifier signing, HITL co-signing,
rejection, tier-based requirements, and KMS fallback.
"""

from unittest.mock import MagicMock

import pytest

from src.services.runtime_security.discovery.attestation import (
    AttestationService,
    AttestationStatus,
    DecommissionAttestation,
)


class TestDecommissionAttestation:
    """Tests for DecommissionAttestation dataclass."""

    def test_tier_1_requires_cosign(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=1,
            status=AttestationStatus.PENDING_VERIFICATION,
        )
        assert a.requires_cosign is True

    def test_tier_2_requires_cosign(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=2,
            status=AttestationStatus.PENDING_VERIFICATION,
        )
        assert a.requires_cosign is True

    def test_tier_3_no_cosign(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=3,
            status=AttestationStatus.PENDING_VERIFICATION,
        )
        assert a.requires_cosign is False

    def test_tier_4_no_cosign(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=4,
            status=AttestationStatus.PENDING_VERIFICATION,
        )
        assert a.requires_cosign is False

    def test_is_complete_tier_3_signed(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=3,
            status=AttestationStatus.ATTESTED,
            verifier_signature="sig-abc",
        )
        assert a.is_complete is True

    def test_is_complete_tier_1_needs_cosign(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=1,
            status=AttestationStatus.ATTESTED,
            verifier_signature="sig-abc",
        )
        assert a.is_complete is False  # Missing cosigner

    def test_is_complete_tier_1_fully_signed(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=1,
            status=AttestationStatus.ATTESTED,
            verifier_signature="sig-abc",
            human_cosigner_id="admin",
        )
        assert a.is_complete is True

    def test_to_dict(self):
        a = DecommissionAttestation(
            attestation_id="att-1",
            agent_id="a1",
            agent_tier=2,
            status=AttestationStatus.PENDING_COSIGN,
        )
        d = a.to_dict()
        assert d["attestation_id"] == "att-1"
        assert d["status"] == "pending_cosign"
        assert d["requires_cosign"] is True


class TestAttestationService:
    """Tests for AttestationService."""

    def setup_method(self):
        self.service = AttestationService()

    def test_create_attestation_zero_confirmed(self):
        summary = {
            "results": [
                {"zero_confirmed": True},
                {"zero_confirmed": True},
            ]
        }
        att = self.service.create_attestation("a1", 3, summary)
        assert att.status == AttestationStatus.PENDING_VERIFICATION

    def test_create_attestation_residual_fails(self):
        summary = {
            "results": [
                {"zero_confirmed": True},
                {"zero_confirmed": False},
            ]
        }
        att = self.service.create_attestation("a1", 3, summary)
        assert att.status == AttestationStatus.FAILED

    def test_sign_verification_tier_3(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 3, summary)
        success = self.service.sign_verification(att.attestation_id)
        assert success is True
        att = self.service.get_attestation(att.attestation_id)
        assert att.status == AttestationStatus.ATTESTED
        assert att.verifier_signature is not None

    def test_sign_verification_tier_2_pending_cosign(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 2, summary)
        success = self.service.sign_verification(att.attestation_id)
        assert success is True
        att = self.service.get_attestation(att.attestation_id)
        assert att.status == AttestationStatus.PENDING_COSIGN

    def test_cosign(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 1, summary)
        self.service.sign_verification(att.attestation_id)
        success = self.service.cosign(att.attestation_id, "admin-user")
        assert success is True
        att = self.service.get_attestation(att.attestation_id)
        assert att.status == AttestationStatus.ATTESTED
        assert att.human_cosigner_id == "admin-user"
        assert att.cosigned_at is not None

    def test_cosign_wrong_state_fails(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 3, summary)
        # Not yet signed
        success = self.service.cosign(att.attestation_id, "admin")
        assert success is False

    def test_reject(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 3, summary)
        success = self.service.reject(att.attestation_id, "Residual IAM role found")
        assert success is True
        att = self.service.get_attestation(att.attestation_id)
        assert att.status == AttestationStatus.REJECTED
        assert att.rejection_reason == "Residual IAM role found"

    def test_sign_nonexistent_fails(self):
        assert self.service.sign_verification("nonexistent") is False

    def test_cosign_nonexistent_fails(self):
        assert self.service.cosign("nonexistent", "admin") is False

    def test_reject_nonexistent_fails(self):
        assert self.service.reject("nonexistent", "reason") is False

    def test_sign_already_signed_fails(self):
        summary = {"all_zero_confirmed": True}
        att = self.service.create_attestation("a1", 3, summary)
        self.service.sign_verification(att.attestation_id)
        # Now it's ATTESTED (tier 3), cannot sign again
        success = self.service.sign_verification(att.attestation_id)
        assert success is False

    def test_get_attestations_for_agent(self):
        summary = {"all_zero_confirmed": True}
        self.service.create_attestation("a1", 3, summary)
        self.service.create_attestation("a1", 3, summary)
        self.service.create_attestation("a2", 3, summary)
        atts = self.service.get_attestations_for_agent("a1")
        assert len(atts) == 2

    def test_kms_signing_fallback(self):
        """Without KMS client, uses local HMAC fallback."""
        service = AttestationService(kms_client=None)
        summary = {"all_zero_confirmed": True}
        att = service.create_attestation("a1", 3, summary)
        service.sign_verification(att.attestation_id)
        att = service.get_attestation(att.attestation_id)
        assert att.verifier_signature is not None
        assert len(att.verifier_signature) == 64  # SHA-256 hex

    def test_kms_signing_with_client(self):
        """With KMS client, uses KMS signing."""
        mock_kms = MagicMock()
        mock_kms.sign.return_value = {"Signature": b"\x01\x02\x03\x04"}
        service = AttestationService(kms_client=mock_kms)
        summary = {"all_zero_confirmed": True}
        att = service.create_attestation("a1", 3, summary)
        service.sign_verification(att.attestation_id)
        att = service.get_attestation(att.attestation_id)
        assert att.verifier_signature == "01020304"
        mock_kms.sign.assert_called_once()
