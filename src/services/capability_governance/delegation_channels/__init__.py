"""
Project Aura - Delegation Channel Verifiers

Pluggable per-channel verification for the 7 delegation channels
defined in ADR-086 Phase 3. Each channel has specific validation
rules beyond the core 7-step verification.

Channels:
- A2A_DIRECT: Agent-to-agent via a2a_gateway
- TOOL_MEDIATED: Agent -> MCP tool -> agent
- SCHEDULED: Agent -> Step Functions/EventBridge -> agent
- MEMORY_MEDIATED: ReMem CONSOLIDATE/REINFORCE/LINK
- HITL_ROUND_TRIP: Human approval resets chain to new root
- WEBHOOK: External trigger (requires origin allowlist)
- EXTERNAL_ADAPTER: Palantir AIP / integration-hub return-path

Author: Project Aura Team
Created: 2026-04-06
"""

from .verifiers import (
    A2ADirectVerifier,
    BaseChannelVerifier,
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

__all__ = [
    "A2ADirectVerifier",
    "BaseChannelVerifier",
    "ChannelVerifierRegistry",
    "ExternalAdapterVerifier",
    "HITLRoundTripVerifier",
    "MemoryMediatedVerifier",
    "ScheduledVerifier",
    "ToolMediatedVerifier",
    "WebhookVerifier",
    "get_channel_verifier_registry",
    "reset_channel_verifier_registry",
]
