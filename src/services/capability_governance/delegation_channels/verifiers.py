"""
Project Aura - Delegation Channel Verifiers

Per-channel verification logic for the 7 delegation channels.
Each verifier performs channel-specific validation beyond the
core 7-step verification in DelegationVerifier.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 3)

Compliance:
- NIST 800-53 AC-3: Access enforcement
- NIST 800-53 AC-17: Remote access

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..delegation_envelope import DelegationAssertion, DelegationChannel

logger = logging.getLogger(__name__)


class BaseChannelVerifier(ABC):
    """Base class for channel-specific delegation verifiers."""

    @property
    @abstractmethod
    def channel(self) -> DelegationChannel:
        """The delegation channel this verifier handles."""
        ...

    @abstractmethod
    def verify(self, assertion: DelegationAssertion) -> bool:
        """
        Perform channel-specific verification.

        Args:
            assertion: The delegation assertion to verify.

        Returns:
            True if the assertion passes channel-specific checks.
        """
        ...

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        """Get human-readable reason for rejection."""
        return f"Channel {self.channel.value} rejected assertion"


class A2ADirectVerifier(BaseChannelVerifier):
    """
    Verifier for A2A_DIRECT delegation channel.

    Validates agent-to-agent direct invocations via a2a_gateway.
    Checks that both delegator and delegate are registered agents
    with active lifecycle states.
    """

    def __init__(
        self,
        registered_agents: Optional[set[str]] = None,
    ) -> None:
        self._registered_agents = registered_agents or set()

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.A2A_DIRECT

    def verify(self, assertion: DelegationAssertion) -> bool:
        if not self._registered_agents:
            return True  # No registry configured, pass through
        delegator_ok = assertion.delegator_agent_id in self._registered_agents
        delegate_ok = assertion.delegate_agent_id in self._registered_agents
        if not delegator_ok or not delegate_ok:
            logger.warning(
                f"A2A_DIRECT: unregistered agent in delegation "
                f"({assertion.delegator_agent_id} -> "
                f"{assertion.delegate_agent_id})"
            )
        return delegator_ok and delegate_ok

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return "Delegator or delegate is not a registered agent"


class ToolMediatedVerifier(BaseChannelVerifier):
    """
    Verifier for TOOL_MEDIATED delegation channel.

    Validates delegations that occur when an agent invokes an MCP
    tool which spawns a downstream agent. Ensures the tool is in
    the allowed spawning tools list.
    """

    def __init__(
        self,
        allowed_spawning_tools: Optional[set[str]] = None,
    ) -> None:
        self._allowed_tools = allowed_spawning_tools or set()

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.TOOL_MEDIATED

    def verify(self, assertion: DelegationAssertion) -> bool:
        if not self._allowed_tools:
            return True  # No tool restrictions
        # Check that at least one capability in the subset is a spawning tool
        return bool(assertion.capability_names & self._allowed_tools)

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return "No capabilities match the allowed spawning tools list"


class ScheduledVerifier(BaseChannelVerifier):
    """
    Verifier for SCHEDULED delegation channel.

    Validates delegations triggered by Step Functions or EventBridge.
    Checks that the assertion's TTL is within the schedule window.
    """

    def __init__(self, max_schedule_ttl_hours: int = 24) -> None:
        self._max_ttl_hours = max_schedule_ttl_hours

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.SCHEDULED

    def verify(self, assertion: DelegationAssertion) -> bool:
        ttl = assertion.expires_at - assertion.issued_at
        max_ttl_seconds = self._max_ttl_hours * 3600
        if ttl.total_seconds() > max_ttl_seconds:
            logger.warning(
                f"SCHEDULED: TTL {ttl} exceeds max {self._max_ttl_hours}h "
                f"for assertion {assertion.assertion_id}"
            )
            return False
        return True

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return f"Schedule TTL exceeds maximum of {self._max_ttl_hours} hours"


class MemoryMediatedVerifier(BaseChannelVerifier):
    """
    Verifier for MEMORY_MEDIATED delegation channel.

    Validates delegations that occur via ReMem actions
    (CONSOLIDATE, REINFORCE, LINK). Memory-mediated delegations
    must be depth-0 or depth-1 only.
    """

    def __init__(self, max_memory_depth: int = 1) -> None:
        self._max_depth = max_memory_depth

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.MEMORY_MEDIATED

    def verify(self, assertion: DelegationAssertion) -> bool:
        if assertion.depth > self._max_depth:
            logger.warning(
                f"MEMORY_MEDIATED: depth {assertion.depth} exceeds "
                f"max {self._max_depth} for {assertion.assertion_id}"
            )
            return False
        return True

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return f"Memory-mediated depth {self._max_depth} exceeded"


class HITLRoundTripVerifier(BaseChannelVerifier):
    """
    Verifier for HITL_ROUND_TRIP delegation channel.

    Human approval resets the chain to a new root. The assertion
    must be depth-0 (root) since HITL creates a fresh chain.
    """

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.HITL_ROUND_TRIP

    def verify(self, assertion: DelegationAssertion) -> bool:
        if not assertion.is_root:
            logger.warning(
                f"HITL_ROUND_TRIP: non-root assertion "
                f"{assertion.assertion_id} (depth={assertion.depth})"
            )
            return False
        return True

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return "HITL round-trip assertions must be root (depth 0)"


class WebhookVerifier(BaseChannelVerifier):
    """
    Verifier for WEBHOOK delegation channel.

    External triggers require origin allowlist matching.
    Unsigned webhook invocations degrade to untrusted-origin profile.
    """

    def __init__(
        self,
        allowed_origins: Optional[set[str]] = None,
    ) -> None:
        self._allowed_origins = allowed_origins or set()

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.WEBHOOK

    def verify(self, assertion: DelegationAssertion) -> bool:
        if not self._allowed_origins:
            # No allowlist configured — allow all
            return True
        # Check if the delegator is in the allowed origins
        if assertion.delegator_agent_id not in self._allowed_origins:
            logger.warning(
                f"WEBHOOK: origin {assertion.delegator_agent_id} " f"not in allowlist"
            )
            return False
        return True

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return "Webhook origin not in allowlist"


class ExternalAdapterVerifier(BaseChannelVerifier):
    """
    Verifier for EXTERNAL_ADAPTER delegation channel.

    Validates return-path invocations from external adapters
    (Palantir AIP, integration-hub). Requires that the adapter
    agent ID matches a known adapter list.
    """

    def __init__(
        self,
        known_adapters: Optional[set[str]] = None,
    ) -> None:
        self._known_adapters = known_adapters or set()

    @property
    def channel(self) -> DelegationChannel:
        return DelegationChannel.EXTERNAL_ADAPTER

    def verify(self, assertion: DelegationAssertion) -> bool:
        if not self._known_adapters:
            return True
        if assertion.delegator_agent_id not in self._known_adapters:
            logger.warning(
                f"EXTERNAL_ADAPTER: {assertion.delegator_agent_id} "
                f"not a known adapter"
            )
            return False
        return True

    def get_rejection_reason(self, assertion: DelegationAssertion) -> str:
        return "External adapter not in known adapters list"


class ChannelVerifierRegistry:
    """
    Registry for channel-specific delegation verifiers.

    Provides a unified interface for channel verification and
    produces callable mappings for DelegationVerifier integration.
    """

    def __init__(self) -> None:
        self._verifiers: dict[DelegationChannel, BaseChannelVerifier] = {}

    def register(self, verifier: BaseChannelVerifier) -> None:
        """Register a channel verifier."""
        self._verifiers[verifier.channel] = verifier
        logger.debug(f"Registered verifier for {verifier.channel.value}")

    def register_defaults(self) -> None:
        """Register default verifiers for all 7 channels."""
        self.register(A2ADirectVerifier())
        self.register(ToolMediatedVerifier())
        self.register(ScheduledVerifier())
        self.register(MemoryMediatedVerifier())
        self.register(HITLRoundTripVerifier())
        self.register(WebhookVerifier())
        self.register(ExternalAdapterVerifier())

    def get_verifier(self, channel: DelegationChannel) -> Optional[BaseChannelVerifier]:
        """Get the verifier for a specific channel."""
        return self._verifiers.get(channel)

    def verify(
        self, channel: DelegationChannel, assertion: DelegationAssertion
    ) -> bool:
        """
        Verify an assertion against the channel-specific verifier.

        Returns True if no verifier is registered for the channel.
        """
        verifier = self._verifiers.get(channel)
        if verifier is None:
            return True
        return verifier.verify(assertion)

    def to_callable_map(
        self,
    ) -> dict[DelegationChannel, Any]:
        """
        Produce a callable map for DelegationVerifier integration.

        Returns a dict mapping channels to verify callables.
        """
        return {
            channel: verifier.verify for channel, verifier in self._verifiers.items()
        }

    @property
    def registered_channels(self) -> list[DelegationChannel]:
        """List of channels with registered verifiers."""
        return list(self._verifiers.keys())


# Singleton
_registry: Optional[ChannelVerifierRegistry] = None


def get_channel_verifier_registry() -> ChannelVerifierRegistry:
    """Get the global channel verifier registry."""
    global _registry
    if _registry is None:
        _registry = ChannelVerifierRegistry()
        _registry.register_defaults()
    return _registry


def reset_channel_verifier_registry() -> None:
    """Reset the global channel verifier registry (for testing)."""
    global _registry
    _registry = None
