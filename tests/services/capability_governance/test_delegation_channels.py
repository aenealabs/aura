"""
Tests for delegation channel verifiers (ADR-086 Phase 3).

Tests all 7 channel-specific verifiers and the registry.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.capability_governance.delegation_channels import (
    A2ADirectVerifier,
    ChannelVerifierRegistry,
    ExternalAdapterVerifier,
    HITLRoundTripVerifier,
    MemoryMediatedVerifier,
    ScheduledVerifier,
    ToolMediatedVerifier,
    WebhookVerifier,
    get_channel_verifier_registry,
    reset_channel_verifier_registry,
)
from src.services.capability_governance.delegation_envelope import (
    CapabilityGrant,
    DelegationAssertion,
    DelegationChannel,
    DelegationVerifier,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_channel_verifier_registry()


@pytest.fixture
def verifier():
    """Create a delegation verifier for minting assertions."""
    return DelegationVerifier()


@pytest.fixture
def sample_caps():
    """Sample capabilities."""
    return frozenset(
        {
            CapabilityGrant(tool_name="semantic_search", action="execute"),
            CapabilityGrant(tool_name="query_code_graph", action="read"),
        }
    )


def _make_assertion(
    verifier,
    caps,
    channel,
    depth=0,
    delegator="orch",
    delegate="coder",
    ttl_minutes=15,
    max_depth=3,
):
    """Helper to mint a test assertion on a specific channel."""
    return verifier.mint_root(
        delegator_agent_id=delegator,
        delegate_agent_id=delegate,
        human_principal_id="user@test.com",
        capability_subset=caps,
        channel=channel,
        max_depth=max_depth,
        ttl_minutes=ttl_minutes,
    )


# =============================================================================
# A2ADirectVerifier Tests
# =============================================================================


class TestA2ADirectVerifier:
    """Tests for A2A_DIRECT channel verifier."""

    def test_passes_when_no_registry(self, verifier, sample_caps):
        """No registered agents means pass-through."""
        v = A2ADirectVerifier()
        a = _make_assertion(verifier, sample_caps, DelegationChannel.A2A_DIRECT)
        assert v.verify(a) is True

    def test_passes_with_registered_agents(self, verifier, sample_caps):
        """Both agents registered passes."""
        v = A2ADirectVerifier(registered_agents={"orch", "coder"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.A2A_DIRECT)
        assert v.verify(a) is True

    def test_fails_unregistered_delegator(self, verifier, sample_caps):
        """Unregistered delegator fails."""
        v = A2ADirectVerifier(registered_agents={"coder"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.A2A_DIRECT)
        assert v.verify(a) is False

    def test_fails_unregistered_delegate(self, verifier, sample_caps):
        """Unregistered delegate fails."""
        v = A2ADirectVerifier(registered_agents={"orch"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.A2A_DIRECT)
        assert v.verify(a) is False

    def test_channel_property(self):
        """Channel property returns A2A_DIRECT."""
        assert A2ADirectVerifier().channel == DelegationChannel.A2A_DIRECT


# =============================================================================
# ToolMediatedVerifier Tests
# =============================================================================


class TestToolMediatedVerifier:
    """Tests for TOOL_MEDIATED channel verifier."""

    def test_passes_no_restrictions(self, verifier, sample_caps):
        """No tool restrictions means pass-through."""
        v = ToolMediatedVerifier()
        a = _make_assertion(verifier, sample_caps, DelegationChannel.TOOL_MEDIATED)
        assert v.verify(a) is True

    def test_passes_with_matching_tool(self, verifier, sample_caps):
        """Assertion with matching tool passes."""
        v = ToolMediatedVerifier(allowed_spawning_tools={"semantic_search"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.TOOL_MEDIATED)
        assert v.verify(a) is True

    def test_fails_no_matching_tool(self, verifier):
        """Assertion with no matching spawning tool fails."""
        caps = frozenset({CapabilityGrant(tool_name="other_tool", action="read")})
        v = ToolMediatedVerifier(allowed_spawning_tools={"semantic_search"})
        a = _make_assertion(verifier, caps, DelegationChannel.TOOL_MEDIATED)
        assert v.verify(a) is False

    def test_channel_property(self):
        """Channel property returns TOOL_MEDIATED."""
        assert ToolMediatedVerifier().channel == DelegationChannel.TOOL_MEDIATED


# =============================================================================
# ScheduledVerifier Tests
# =============================================================================


class TestScheduledVerifier:
    """Tests for SCHEDULED channel verifier."""

    def test_passes_within_ttl(self, verifier, sample_caps):
        """TTL within max passes."""
        v = ScheduledVerifier(max_schedule_ttl_hours=24)
        a = _make_assertion(
            verifier, sample_caps, DelegationChannel.SCHEDULED, ttl_minutes=60
        )
        assert v.verify(a) is True

    def test_fails_excessive_ttl(self, verifier, sample_caps):
        """TTL exceeding max fails."""
        v = ScheduledVerifier(max_schedule_ttl_hours=1)
        a = _make_assertion(
            verifier, sample_caps, DelegationChannel.SCHEDULED, ttl_minutes=120
        )
        assert v.verify(a) is False

    def test_channel_property(self):
        """Channel property returns SCHEDULED."""
        assert ScheduledVerifier().channel == DelegationChannel.SCHEDULED


# =============================================================================
# MemoryMediatedVerifier Tests
# =============================================================================


class TestMemoryMediatedVerifier:
    """Tests for MEMORY_MEDIATED channel verifier."""

    def test_passes_depth_0(self, verifier, sample_caps):
        """Depth 0 passes."""
        v = MemoryMediatedVerifier(max_memory_depth=1)
        a = _make_assertion(verifier, sample_caps, DelegationChannel.MEMORY_MEDIATED)
        assert v.verify(a) is True

    def test_fails_depth_exceeded(self, verifier, sample_caps):
        """Depth exceeding max fails."""
        v = MemoryMediatedVerifier(max_memory_depth=0)
        root = _make_assertion(verifier, sample_caps, DelegationChannel.MEMORY_MEDIATED)
        child = verifier.remint(
            root, "agent-2", sample_caps, DelegationChannel.MEMORY_MEDIATED
        )
        assert child is not None
        assert v.verify(child) is False

    def test_channel_property(self):
        """Channel property returns MEMORY_MEDIATED."""
        assert MemoryMediatedVerifier().channel == DelegationChannel.MEMORY_MEDIATED


# =============================================================================
# HITLRoundTripVerifier Tests
# =============================================================================


class TestHITLRoundTripVerifier:
    """Tests for HITL_ROUND_TRIP channel verifier."""

    def test_passes_root(self, verifier, sample_caps):
        """Root assertion passes."""
        v = HITLRoundTripVerifier()
        a = _make_assertion(verifier, sample_caps, DelegationChannel.HITL_ROUND_TRIP)
        assert v.verify(a) is True

    def test_fails_non_root(self, verifier, sample_caps):
        """Non-root assertion fails."""
        v = HITLRoundTripVerifier()
        root = _make_assertion(verifier, sample_caps, DelegationChannel.HITL_ROUND_TRIP)
        child = verifier.remint(
            root, "agent-2", sample_caps, DelegationChannel.HITL_ROUND_TRIP
        )
        assert child is not None
        assert v.verify(child) is False

    def test_channel_property(self):
        """Channel property returns HITL_ROUND_TRIP."""
        assert HITLRoundTripVerifier().channel == DelegationChannel.HITL_ROUND_TRIP


# =============================================================================
# WebhookVerifier Tests
# =============================================================================


class TestWebhookVerifier:
    """Tests for WEBHOOK channel verifier."""

    def test_passes_no_allowlist(self, verifier, sample_caps):
        """No allowlist means pass-through."""
        v = WebhookVerifier()
        a = _make_assertion(verifier, sample_caps, DelegationChannel.WEBHOOK)
        assert v.verify(a) is True

    def test_passes_origin_in_allowlist(self, verifier, sample_caps):
        """Origin in allowlist passes."""
        v = WebhookVerifier(allowed_origins={"orch"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.WEBHOOK)
        assert v.verify(a) is True

    def test_fails_origin_not_in_allowlist(self, verifier, sample_caps):
        """Origin not in allowlist fails."""
        v = WebhookVerifier(allowed_origins={"other-origin"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.WEBHOOK)
        assert v.verify(a) is False

    def test_channel_property(self):
        """Channel property returns WEBHOOK."""
        assert WebhookVerifier().channel == DelegationChannel.WEBHOOK


# =============================================================================
# ExternalAdapterVerifier Tests
# =============================================================================


class TestExternalAdapterVerifier:
    """Tests for EXTERNAL_ADAPTER channel verifier."""

    def test_passes_no_known_adapters(self, verifier, sample_caps):
        """No known adapters means pass-through."""
        v = ExternalAdapterVerifier()
        a = _make_assertion(verifier, sample_caps, DelegationChannel.EXTERNAL_ADAPTER)
        assert v.verify(a) is True

    def test_passes_known_adapter(self, verifier, sample_caps):
        """Known adapter passes."""
        v = ExternalAdapterVerifier(known_adapters={"orch"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.EXTERNAL_ADAPTER)
        assert v.verify(a) is True

    def test_fails_unknown_adapter(self, verifier, sample_caps):
        """Unknown adapter fails."""
        v = ExternalAdapterVerifier(known_adapters={"palantir-adapter"})
        a = _make_assertion(verifier, sample_caps, DelegationChannel.EXTERNAL_ADAPTER)
        assert v.verify(a) is False

    def test_channel_property(self):
        """Channel property returns EXTERNAL_ADAPTER."""
        assert ExternalAdapterVerifier().channel == DelegationChannel.EXTERNAL_ADAPTER


# =============================================================================
# ChannelVerifierRegistry Tests
# =============================================================================


class TestChannelVerifierRegistry:
    """Tests for ChannelVerifierRegistry."""

    def test_register_defaults(self):
        """register_defaults registers all 7 channels."""
        reg = ChannelVerifierRegistry()
        reg.register_defaults()
        assert len(reg.registered_channels) == 7

    def test_verify_unregistered_channel(self):
        """Unregistered channel returns True (pass-through)."""
        reg = ChannelVerifierRegistry()
        # Don't register anything — verify with no verifiers returns True
        v = DelegationVerifier()
        a = v.mint_root(
            delegator_agent_id="orch",
            delegate_agent_id="coder",
            human_principal_id="user",
            capability_subset=frozenset(),
            channel=DelegationChannel.A2A_DIRECT,
        )
        assert reg.verify(DelegationChannel.A2A_DIRECT, a) is True

    def test_to_callable_map(self):
        """to_callable_map produces dict of callables."""
        reg = ChannelVerifierRegistry()
        reg.register_defaults()
        cmap = reg.to_callable_map()
        assert len(cmap) == 7
        for channel, func in cmap.items():
            assert callable(func)

    def test_get_verifier(self):
        """get_verifier returns the registered verifier."""
        reg = ChannelVerifierRegistry()
        v = A2ADirectVerifier()
        reg.register(v)
        assert reg.get_verifier(DelegationChannel.A2A_DIRECT) is v

    def test_get_verifier_none(self):
        """get_verifier returns None for unregistered channel."""
        reg = ChannelVerifierRegistry()
        assert reg.get_verifier(DelegationChannel.WEBHOOK) is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestRegistrySingleton:
    """Tests for registry singleton."""

    def test_get_returns_same_instance(self):
        """get_channel_verifier_registry returns same instance."""
        r1 = get_channel_verifier_registry()
        r2 = get_channel_verifier_registry()
        assert r1 is r2

    def test_defaults_registered(self):
        """Singleton has defaults registered."""
        r = get_channel_verifier_registry()
        assert len(r.registered_channels) == 7

    def test_reset_clears(self):
        """Reset creates fresh instance."""
        r1 = get_channel_verifier_registry()
        reset_channel_verifier_registry()
        r2 = get_channel_verifier_registry()
        assert r1 is not r2
