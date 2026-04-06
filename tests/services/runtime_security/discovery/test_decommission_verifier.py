"""
Tests for the Decommission Verifier (ADR-086 Phase 1).

Covers the orchestration flow: state transitions, credential enumeration,
attestation creation, HITL co-signing for tier 1/2, and remediation routing.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.runtime_security.discovery.attestation import (
    AttestationService,
    AttestationStatus,
)
from src.services.runtime_security.discovery.credential_enumerators.enumerators import (
    IAMRoleEnumerator,
)
from src.services.runtime_security.discovery.credential_enumerators.registry import (
    CredentialRecord,
    CredentialStatus,
    EnumerationResult,
    EnumeratorRegistry,
)
from src.services.runtime_security.discovery.decommission_verifier import (
    DecommissionReport,
    DecommissionVerifier,
)
from src.services.runtime_security.discovery.lifecycle_state_machine import (
    DecommissionTrigger,
    LifecycleState,
    LifecycleStateMachine,
)


class TestDecommissionVerifier:
    """Tests for DecommissionVerifier orchestration."""

    def setup_method(self):
        self.sm = LifecycleStateMachine()
        self.registry = EnumeratorRegistry()
        self.attestation = AttestationService()
        self.verifier = DecommissionVerifier(
            state_machine=self.sm,
            enumerator_registry=self.registry,
            attestation_service=self.attestation,
        )

    def _register_zero_enumerator(self):
        """Register an enumerator that reports zero credentials."""
        enum = IAMRoleEnumerator()  # No client = zero_confirmed
        self.registry.register(enum)

    def _register_active_enumerator(self):
        """Register an enumerator that reports active credentials."""
        mock_client = MagicMock()
        mock_client.list_roles_for_agent.return_value = [
            {"role_arn": "arn:aws:iam::123:role/test", "role_name": "test"},
        ]
        enum = IAMRoleEnumerator(client=mock_client)
        self.registry.register(enum)

    def test_happy_path_tier_4_auto_attested(self):
        """Tier 4 agent with zero credentials auto-attests."""
        self.sm.register_agent("a1", agent_tier=4)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )

        assert report.all_zero_confirmed is True
        assert report.requires_hitl is False
        assert report.attestation is not None
        assert report.attestation.status == AttestationStatus.ATTESTED
        assert self.sm.get_state("a1") == LifecycleState.ATTESTED

    def test_happy_path_tier_3_auto_attested(self):
        """Tier 3 agent with zero credentials auto-attests."""
        self.sm.register_agent("a1", agent_tier=3)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.DORMANCY_THRESHOLD
        )

        assert report.all_zero_confirmed is True
        assert report.requires_hitl is False
        assert self.sm.get_state("a1") == LifecycleState.ATTESTED

    def test_tier_2_requires_hitl(self):
        """Tier 2 agent with zero credentials requires HITL co-sign."""
        self.sm.register_agent("a1", agent_tier=2)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )

        assert report.all_zero_confirmed is True
        assert report.requires_hitl is True
        assert report.attestation is not None
        assert report.attestation.status == AttestationStatus.PENDING_COSIGN
        # Should still be in DECOMMISSIONING (awaiting cosign)
        assert self.sm.get_state("a1") == LifecycleState.DECOMMISSIONING

    def test_tier_1_requires_hitl(self):
        """Tier 1 agent requires HITL co-sign."""
        self.sm.register_agent("a1", agent_tier=1)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.OWNER_DEACTIVATED
        )

        assert report.requires_hitl is True
        assert report.attestation.status == AttestationStatus.PENDING_COSIGN

    def test_residual_credentials_routes_to_remediation(self):
        """Agent with active credentials goes to REMEDIATION_REQUIRED."""
        self.sm.register_agent("a1", agent_tier=3)
        self._register_active_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )

        assert report.all_zero_confirmed is False
        assert report.residual_credential_count == 1
        assert report.attestation is None
        assert self.sm.get_state("a1") == LifecycleState.REMEDIATION_REQUIRED

    def test_unregistered_agent_returns_error(self):
        """Verifying unregistered agent returns error."""
        report = self.verifier.verify_decommission(
            "nonexistent", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )
        assert report.error is not None
        assert "not registered" in report.error

    def test_complete_cosign(self):
        """Test completing HITL co-sign for tier 2."""
        self.sm.register_agent("a1", agent_tier=2)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )

        success = self.verifier.complete_cosign(
            "a1", report.attestation.attestation_id, "admin-user"
        )
        assert success is True
        assert self.sm.get_state("a1") == LifecycleState.ATTESTED

    def test_archive(self):
        """Test archiving an attested agent."""
        self.sm.register_agent("a1", agent_tier=4)
        self._register_zero_enumerator()

        self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )
        success = self.verifier.archive("a1")
        assert success is True
        assert self.sm.get_state("a1") == LifecycleState.ARCHIVED

    def test_archive_non_attested_fails(self):
        """Cannot archive an agent that isn't attested."""
        self.sm.register_agent("a1")
        success = self.verifier.archive("a1")
        assert success is False

    def test_report_to_dict(self):
        """Test DecommissionReport serialization."""
        self.sm.register_agent("a1", agent_tier=4)
        self._register_zero_enumerator()

        report = self.verifier.verify_decommission(
            "a1", DecommissionTrigger.EXPLICIT_SHUTDOWN
        )
        d = report.to_dict()
        assert d["agent_id"] == "a1"
        assert d["trigger"] == "explicit_shutdown"
        assert d["all_zero_confirmed"] is True
        assert d["attestation"] is not None
