"""
Tests for the Delegation Trust Envelope (ADR-086 Phase 3).

Tests DelegationAssertion creation, 7-step verification, chain walking,
revocation, untrusted-origin profile, and singleton lifecycle.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.services.capability_governance.delegation_envelope import (
    UNTRUSTED_ORIGIN_CAPABILITIES,
    CapabilityGrant,
    DelegationAssertion,
    DelegationChannel,
    DelegationVerifier,
    VerificationResult,
    VerificationVerdict,
    get_delegation_verifier,
    reset_delegation_verifier,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_delegation_verifier()


@pytest.fixture
def verifier():
    """Create a fresh verifier."""
    return DelegationVerifier()


@pytest.fixture
def sample_caps():
    """Sample capability grants."""
    return frozenset(
        {
            CapabilityGrant(tool_name="semantic_search", action="execute"),
            CapabilityGrant(tool_name="query_code_graph", action="read"),
            CapabilityGrant(tool_name="get_documentation", action="read"),
        }
    )


@pytest.fixture
def narrow_caps():
    """Narrowed capability subset."""
    return frozenset(
        {
            CapabilityGrant(tool_name="semantic_search", action="execute"),
        }
    )


@pytest.fixture
def root_assertion(verifier, sample_caps):
    """Mint a root assertion."""
    return verifier.mint_root(
        delegator_agent_id="orchestrator-001",
        delegate_agent_id="coder-agent-001",
        human_principal_id="user@example.com",
        capability_subset=sample_caps,
        channel=DelegationChannel.A2A_DIRECT,
        max_depth=3,
    )


# =============================================================================
# CapabilityGrant Tests
# =============================================================================


class TestCapabilityGrant:
    """Tests for CapabilityGrant dataclass."""

    def test_create(self):
        """Test creating a grant."""
        g = CapabilityGrant(tool_name="search", action="read")
        assert g.tool_name == "search"
        assert g.action == "read"

    def test_frozen(self):
        """Grant is immutable."""
        g = CapabilityGrant(tool_name="search", action="read")
        with pytest.raises(AttributeError):
            g.tool_name = "other"

    def test_hashable(self):
        """Grants work in frozensets."""
        g1 = CapabilityGrant(tool_name="a", action="r")
        g2 = CapabilityGrant(tool_name="a", action="r")
        assert g1 == g2
        assert len(frozenset({g1, g2})) == 1

    def test_to_dict(self):
        """Test serialization."""
        g = CapabilityGrant(tool_name="search", action="execute")
        assert g.to_dict() == {"tool_name": "search", "action": "execute"}


# =============================================================================
# DelegationAssertion Tests
# =============================================================================


class TestDelegationAssertion:
    """Tests for DelegationAssertion dataclass."""

    def test_root_assertion_properties(self, root_assertion):
        """Root assertion has correct properties."""
        assert root_assertion.is_root is True
        assert root_assertion.depth == 0
        assert root_assertion.root_assertion_id == root_assertion.assertion_id
        assert root_assertion.parent_assertion_id is None

    def test_is_expired_false(self, root_assertion):
        """Fresh assertion is not expired."""
        assert root_assertion.is_expired is False

    def test_capability_names(self, root_assertion):
        """capability_names extracts tool names."""
        names = root_assertion.capability_names
        assert "semantic_search" in names
        assert "query_code_graph" in names
        assert "get_documentation" in names

    def test_to_dict(self, root_assertion):
        """Serialization produces expected keys."""
        d = root_assertion.to_dict()
        assert d["assertion_id"] == root_assertion.assertion_id
        assert d["depth"] == 0
        assert d["is_root"] is True
        assert d["channel"] == "a2a_direct"
        assert len(d["capability_subset"]) == 3

    def test_frozen(self, root_assertion):
        """Assertion is immutable."""
        with pytest.raises(AttributeError):
            root_assertion.depth = 99

    def test_signature_present(self, root_assertion):
        """Minted assertion has a signature."""
        assert len(root_assertion.signature) > 0


# =============================================================================
# Minting Tests
# =============================================================================


class TestMinting:
    """Tests for assertion minting and re-minting."""

    def test_mint_root(self, verifier, sample_caps):
        """Minting a root assertion succeeds."""
        a = verifier.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user@test.com",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
        )
        assert a.is_root
        assert a.depth == 0
        assert a.human_principal_id == "user@test.com"
        assert verifier.get_assertion(a.assertion_id) is a

    def test_remint_narrows_capabilities(self, verifier, root_assertion, narrow_caps):
        """Re-minting with subset succeeds and increments depth."""
        child = verifier.remint(
            parent=root_assertion,
            delegate_agent_id="validator-001",
            capability_subset=narrow_caps,
            channel=DelegationChannel.TOOL_MEDIATED,
        )
        assert child is not None
        assert child.depth == 1
        assert child.parent_assertion_id == root_assertion.assertion_id
        assert child.root_assertion_id == root_assertion.root_assertion_id
        assert child.capability_subset == narrow_caps

    def test_remint_rejects_expansion(self, verifier, root_assertion):
        """Re-minting with superset capabilities returns None."""
        expanded = frozenset(
            {
                CapabilityGrant(tool_name="semantic_search", action="execute"),
                CapabilityGrant(tool_name="DANGEROUS_TOOL", action="execute"),
            }
        )
        result = verifier.remint(
            parent=root_assertion,
            delegate_agent_id="evil-agent",
            capability_subset=expanded,
            channel=DelegationChannel.A2A_DIRECT,
        )
        assert result is None

    def test_remint_rejects_depth_exceeded(self, verifier, sample_caps, narrow_caps):
        """Re-minting beyond max_depth returns None."""
        root = verifier.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="a1",
            human_principal_id="user@test.com",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
            max_depth=1,
        )
        child = verifier.remint(
            parent=root,
            delegate_agent_id="a2",
            capability_subset=narrow_caps,
            channel=DelegationChannel.A2A_DIRECT,
        )
        assert child is not None
        assert child.depth == 1

        # Depth 2 exceeds max_depth=1
        grandchild = verifier.remint(
            parent=child,
            delegate_agent_id="a3",
            capability_subset=narrow_caps,
            channel=DelegationChannel.A2A_DIRECT,
        )
        assert grandchild is None

    def test_chain_depth_3(self, verifier, sample_caps, narrow_caps):
        """Full 3-hop chain succeeds when max_depth allows."""
        root = verifier.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="a1",
            human_principal_id="user@test.com",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
            max_depth=3,
        )
        c1 = verifier.remint(root, "a2", narrow_caps, DelegationChannel.A2A_DIRECT)
        c2 = verifier.remint(c1, "a3", narrow_caps, DelegationChannel.TOOL_MEDIATED)
        c3 = verifier.remint(c2, "a4", narrow_caps, DelegationChannel.SCHEDULED)
        assert c3 is not None
        assert c3.depth == 3


# =============================================================================
# 7-Step Verification Tests
# =============================================================================


class TestVerification:
    """Tests for the 7-step verification pipeline."""

    def test_valid_root_assertion(self, verifier, root_assertion):
        """Valid root assertion passes verification."""
        result = verifier.verify(root_assertion)
        assert result.is_valid
        assert result.verdict == VerificationVerdict.VALID

    def test_valid_child_assertion(self, verifier, root_assertion, narrow_caps):
        """Valid child assertion passes verification."""
        child = verifier.remint(
            root_assertion, "validator", narrow_caps, DelegationChannel.A2A_DIRECT
        )
        result = verifier.verify(child)
        assert result.is_valid

    def test_step1_invalid_signature(self, verifier, root_assertion):
        """Assertion with bad signature fails step 1."""
        tampered = DelegationAssertion(
            assertion_id=root_assertion.assertion_id,
            delegator_agent_id=root_assertion.delegator_agent_id,
            delegate_agent_id=root_assertion.delegate_agent_id,
            human_principal_id=root_assertion.human_principal_id,
            root_assertion_id=root_assertion.root_assertion_id,
            parent_assertion_id=root_assertion.parent_assertion_id,
            capability_subset=root_assertion.capability_subset,
            depth=root_assertion.depth,
            max_depth=root_assertion.max_depth,
            channel=root_assertion.channel,
            nonce=root_assertion.nonce,
            issued_at=root_assertion.issued_at,
            expires_at=root_assertion.expires_at,
            signature=b"forged-signature",
        )
        result = verifier.verify(tampered)
        assert result.verdict == VerificationVerdict.INVALID_SIGNATURE

    def test_step1_no_signature(self, verifier):
        """Assertion with empty signature fails step 1."""
        unsigned = DelegationAssertion(
            assertion_id="da-unsigned",
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user",
            root_assertion_id="da-unsigned",
            parent_assertion_id=None,
            capability_subset=frozenset(),
            depth=0,
            max_depth=3,
            channel=DelegationChannel.A2A_DIRECT,
            nonce=b"nonce",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            signature=b"",
        )
        result = verifier.verify(unsigned)
        assert result.verdict == VerificationVerdict.INVALID_SIGNATURE

    def test_step2_expired(self, verifier, sample_caps):
        """Expired assertion fails step 2."""
        expired = verifier.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
            ttl_minutes=-1,  # already expired
        )
        result = verifier.verify(expired)
        assert result.verdict == VerificationVerdict.EXPIRED

    def test_step3_revoked(self, verifier, root_assertion):
        """Revoked assertion fails step 3."""
        verifier.revoke(root_assertion.assertion_id)
        result = verifier.verify(root_assertion)
        assert result.verdict == VerificationVerdict.REVOKED

    def test_step4_depth_exceeded(self, verifier):
        """Assertion exceeding max_depth fails step 4."""
        # Construct assertion with depth > max_depth
        now = datetime.now(timezone.utc)
        a = DelegationAssertion(
            assertion_id="da-deep",
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user",
            root_assertion_id="da-deep",
            parent_assertion_id=None,
            capability_subset=frozenset(),
            depth=5,
            max_depth=3,
            channel=DelegationChannel.A2A_DIRECT,
            nonce=uuid.uuid4().bytes,
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        signed = verifier._sign(a)
        result = verifier.verify(signed)
        assert result.verdict == VerificationVerdict.DEPTH_EXCEEDED

    def test_step6_ancestor_revoked(self, verifier, root_assertion, narrow_caps):
        """Revoking an ancestor breaks the chain (step 6)."""
        child = verifier.remint(
            root_assertion, "validator", narrow_caps, DelegationChannel.A2A_DIRECT
        )
        verifier.revoke(root_assertion.assertion_id)
        result = verifier.verify(child)
        assert result.verdict == VerificationVerdict.REVOKED
        assert "Ancestor" in result.explanation

    def test_step6_principal_deactivated(self, verifier, sample_caps):
        """Deactivated principal fails step 6."""
        checker = DelegationVerifier(
            principal_checker=lambda pid: False,
        )
        root = checker.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="deactivated@test.com",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
        )
        result = checker.verify(root)
        assert result.verdict == VerificationVerdict.PRINCIPAL_DEACTIVATED

    def test_step7_channel_rejected(self, verifier, sample_caps):
        """Channel verifier rejection fails step 7."""
        verifier_with_channel = DelegationVerifier(
            channel_verifiers={
                DelegationChannel.WEBHOOK: lambda a: False,
            },
        )
        root = verifier_with_channel.mint_root(
            delegator_agent_id="webhook-source",
            delegate_agent_id="coder",
            human_principal_id="user",
            capability_subset=sample_caps,
            channel=DelegationChannel.WEBHOOK,
        )
        result = verifier_with_channel.verify(root)
        assert result.verdict == VerificationVerdict.CHANNEL_REJECTED

    def test_valid_passes_all_steps(self, verifier, root_assertion):
        """A valid assertion passes all 7 steps."""
        result = verifier.verify(root_assertion)
        assert result.is_valid
        assert result.explanation == "All verification steps passed"


# =============================================================================
# Revocation Tests
# =============================================================================


class TestRevocation:
    """Tests for assertion revocation."""

    def test_revoke_returns_true(self, verifier, root_assertion):
        """Revocation returns True."""
        assert verifier.revoke(root_assertion.assertion_id) is True

    def test_revoked_assertion_rejected(self, verifier, root_assertion):
        """Revoked assertions fail verification."""
        verifier.revoke(root_assertion.assertion_id)
        result = verifier.verify(root_assertion)
        assert not result.is_valid

    def test_external_revocation_checker(self, sample_caps):
        """External revocation checker is consulted."""
        revoked_ids = {"da-external-001"}
        v = DelegationVerifier(
            revocation_checker=lambda aid: aid in revoked_ids,
        )
        root = v.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user",
            capability_subset=sample_caps,
            channel=DelegationChannel.A2A_DIRECT,
        )
        # Not in revoked set — passes
        result = v.verify(root)
        assert result.is_valid


# =============================================================================
# Untrusted Origin Profile Tests
# =============================================================================


class TestUntrustedOrigin:
    """Tests for untrusted-origin capability degradation."""

    def test_untrusted_capabilities_are_readonly(self, verifier):
        """Untrusted profile only contains read-only operations."""
        caps = verifier.get_untrusted_capabilities()
        assert len(caps) > 0
        for cap in caps:
            assert cap.action == "read"

    def test_untrusted_profile_matches_constant(self, verifier):
        """get_untrusted_capabilities returns the module constant."""
        assert verifier.get_untrusted_capabilities() == UNTRUSTED_ORIGIN_CAPABILITIES


# =============================================================================
# Metrics Tests
# =============================================================================


class TestVerifierMetrics:
    """Tests for operational metrics."""

    def test_initial_metrics(self, verifier):
        """Initial metrics are zero."""
        m = verifier.get_metrics()
        assert m["assertions_minted"] == 0
        assert m["verifications_performed"] == 0

    def test_metrics_after_operations(self, verifier, root_assertion):
        """Metrics update after minting and verification."""
        verifier.verify(root_assertion)
        m = verifier.get_metrics()
        assert m["assertions_minted"] == 1
        assert m["verifications_performed"] == 1
        assert m["valid_count"] == 1

    def test_metrics_after_rejection(self, verifier, root_assertion):
        """Rejected verifications increment rejected_count."""
        verifier.revoke(root_assertion.assertion_id)
        verifier.verify(root_assertion)
        m = verifier.get_metrics()
        assert m["rejected_count"] == 1
        assert m["revoked_count"] == 1


# =============================================================================
# VerificationResult Tests
# =============================================================================


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_valid_result(self):
        """Valid result properties."""
        r = VerificationResult(
            assertion_id="da-1",
            verdict=VerificationVerdict.VALID,
            explanation="OK",
        )
        assert r.is_valid is True

    def test_invalid_result(self):
        """Invalid result properties."""
        r = VerificationResult(
            assertion_id="da-2",
            verdict=VerificationVerdict.EXPIRED,
            explanation="Expired",
        )
        assert r.is_valid is False

    def test_to_dict(self):
        """Serialization produces expected keys."""
        r = VerificationResult(
            assertion_id="da-3",
            verdict=VerificationVerdict.REVOKED,
            explanation="Revoked",
        )
        d = r.to_dict()
        assert d["verdict"] == "revoked"
        assert d["is_valid"] is False
        assert "verified_at" in d


# =============================================================================
# Singleton Lifecycle Tests
# =============================================================================


class TestSingletonLifecycle:
    """Tests for singleton pattern."""

    def test_get_returns_same_instance(self):
        """get_delegation_verifier returns same instance."""
        v1 = get_delegation_verifier()
        v2 = get_delegation_verifier()
        assert v1 is v2

    def test_reset_clears_instance(self):
        """reset creates fresh instance on next get."""
        v1 = get_delegation_verifier()
        reset_delegation_verifier()
        v2 = get_delegation_verifier()
        assert v1 is not v2


# =============================================================================
# DelegationChannel Enum Tests
# =============================================================================


class TestDelegationChannel:
    """Tests for DelegationChannel enum."""

    def test_all_channels_exist(self):
        """All 7 channels are defined."""
        assert len(DelegationChannel) == 7

    def test_channel_values(self):
        """Channel values match expected strings."""
        expected = {
            "a2a_direct",
            "tool_mediated",
            "scheduled",
            "memory_mediated",
            "hitl_round_trip",
            "webhook",
            "external_adapter",
        }
        actual = {c.value for c in DelegationChannel}
        assert actual == expected
