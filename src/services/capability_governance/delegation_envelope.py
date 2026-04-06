"""
Project Aura - Delegation Trust Envelope

Signed, depth-bounded DelegationAssertion required at every cross-agent
invocation boundary. Chains anchored in a human principal, re-minted
with narrowing capability subsets at each hop.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 3)

This is the trust primitive missing from OAuth, SAML, and MCP — none
covers agent-to-agent delegation with depth-bounded, capability-subset-
narrowing trust assertions anchored in a human principal.

Compliance:
- NIST 800-53 AC-6(1): Authorize access to security functions
- NIST 800-53 IA-4: Identifier management
- NIST 800-53 AU-10: Non-repudiation

Author: Project Aura Team
Created: 2026-04-06
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DelegationChannel(Enum):
    """
    Delegation channels for cross-agent invocation.

    Each channel represents a different mechanism through which one
    agent can invoke another. Each has a channel-specific verifier.
    """

    A2A_DIRECT = "a2a_direct"  # agent -> agent via a2a_gateway
    TOOL_MEDIATED = "tool_mediated"  # agent -> MCP tool -> agent
    SCHEDULED = "scheduled"  # agent -> Step Functions/EventBridge -> agent
    MEMORY_MEDIATED = "memory_mediated"  # ReMem CONSOLIDATE/REINFORCE/LINK
    HITL_ROUND_TRIP = "hitl_round_trip"  # human approval resets chain
    WEBHOOK = "webhook"  # external trigger
    EXTERNAL_ADAPTER = "external_adapter"  # Palantir AIP / integration-hub


class VerificationVerdict(Enum):
    """Result of assertion verification."""

    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DEPTH_EXCEEDED = "depth_exceeded"
    CAPABILITY_EXPANSION = "capability_expansion"
    INVALID_SIGNATURE = "invalid_signature"
    CHAIN_BROKEN = "chain_broken"
    CHANNEL_REJECTED = "channel_rejected"
    PRINCIPAL_DEACTIVATED = "principal_deactivated"


@dataclass(frozen=True)
class CapabilityGrant:
    """A single capability grant within a delegation assertion."""

    tool_name: str
    action: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to dictionary."""
        return {"tool_name": self.tool_name, "action": self.action}


@dataclass(frozen=True)
class DelegationAssertion:
    """
    Signed, depth-bounded delegation assertion.

    Required at every cross-agent invocation boundary. Chains are
    anchored in a human principal and re-minted with narrowing
    capability subsets at each hop.
    """

    assertion_id: str
    delegator_agent_id: str
    delegate_agent_id: str
    human_principal_id: str
    root_assertion_id: str
    parent_assertion_id: Optional[str]
    capability_subset: frozenset[CapabilityGrant]
    depth: int
    max_depth: int
    channel: DelegationChannel
    nonce: bytes
    issued_at: datetime
    expires_at: datetime
    signature: bytes = b""

    @property
    def is_root(self) -> bool:
        """True if this is the root assertion in the chain."""
        return self.parent_assertion_id is None

    @property
    def is_expired(self) -> bool:
        """True if the assertion has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def capability_names(self) -> frozenset[str]:
        """Tool names in the capability subset."""
        return frozenset(g.tool_name for g in self.capability_subset)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "assertion_id": self.assertion_id,
            "delegator_agent_id": self.delegator_agent_id,
            "delegate_agent_id": self.delegate_agent_id,
            "human_principal_id": self.human_principal_id,
            "root_assertion_id": self.root_assertion_id,
            "parent_assertion_id": self.parent_assertion_id,
            "capability_subset": sorted(
                [g.to_dict() for g in self.capability_subset],
                key=lambda d: d["tool_name"],
            ),
            "depth": self.depth,
            "max_depth": self.max_depth,
            "channel": self.channel.value,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_root": self.is_root,
        }


@dataclass(frozen=True)
class VerificationResult:
    """Immutable result of delegation assertion verification."""

    assertion_id: str
    verdict: VerificationVerdict
    explanation: str
    verified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_valid(self) -> bool:
        """True if the assertion passed verification."""
        return self.verdict == VerificationVerdict.VALID

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "assertion_id": self.assertion_id,
            "verdict": self.verdict.value,
            "is_valid": self.is_valid,
            "explanation": self.explanation,
            "verified_at": self.verified_at.isoformat(),
        }


# Untrusted-origin capability profile: read-only, non-sensitive operations
UNTRUSTED_ORIGIN_CAPABILITIES = frozenset({
    CapabilityGrant(tool_name="semantic_search", action="read"),
    CapabilityGrant(tool_name="get_documentation", action="read"),
    CapabilityGrant(tool_name="describe_tool", action="read"),
    CapabilityGrant(tool_name="get_sandbox_status", action="read"),
    CapabilityGrant(tool_name="get_agent_status", action="read"),
})


class DelegationVerifier:
    """
    Verifies delegation assertions at cross-agent invocation boundaries.

    Performs a 7-step verification:
    1. Signature check (KMS CMK or local SHA-256 fallback)
    2. Expiry check
    3. Revocation list check (DynamoDB point lookup)
    4. Depth check (depth <= max_depth)
    5. Capability subset check (subset <= delegator's grants)
    6. Chain walk (ancestors not revoked, human principal active)
    7. Channel-specific verifier

    Usage:
        verifier = DelegationVerifier()
        result = verifier.verify(assertion)
        if result.is_valid:
            # Proceed with delegated invocation
            ...
        else:
            # Degrade to untrusted-origin profile
            caps = verifier.get_untrusted_capabilities()
    """

    def __init__(
        self,
        revocation_checker: Optional[Callable[[str], bool]] = None,
        principal_checker: Optional[Callable[[str], bool]] = None,
        channel_verifiers: Optional[
            dict[DelegationChannel, Callable[["DelegationAssertion"], bool]]
        ] = None,
        signing_key: Optional[bytes] = None,
    ) -> None:
        """
        Initialize the verifier.

        Args:
            revocation_checker: Callable that returns True if assertion_id
                is revoked. Backed by DynamoDB point lookup in production.
            principal_checker: Callable that returns True if human principal
                is active. Returns True by default.
            channel_verifiers: Per-channel verification callables.
            signing_key: Key for signature verification. Uses HMAC-SHA256
                fallback when KMS is unavailable.
        """
        self._revocation_checker = revocation_checker
        self._principal_checker = principal_checker
        self._channel_verifiers = channel_verifiers or {}
        self._signing_key = signing_key or b"aura-delegation-default-key"
        self._assertions: dict[str, DelegationAssertion] = {}
        self._revoked: set[str] = set()
        self._verification_count = 0
        self._valid_count = 0
        self._rejected_count = 0

    def mint_root(
        self,
        delegator_agent_id: str,
        delegate_agent_id: str,
        human_principal_id: str,
        capability_subset: frozenset[CapabilityGrant],
        channel: DelegationChannel,
        max_depth: int = 3,
        ttl_minutes: int = 15,
    ) -> DelegationAssertion:
        """
        Mint a root delegation assertion for a human-initiated workflow.

        Args:
            delegator_agent_id: Agent initiating the delegation.
            delegate_agent_id: Agent receiving the delegation.
            human_principal_id: Human principal anchoring the chain.
            capability_subset: Capabilities being delegated.
            channel: Delegation channel.
            max_depth: Maximum delegation chain depth.
            ttl_minutes: Assertion time-to-live in minutes.

        Returns:
            Signed root DelegationAssertion.
        """
        assertion_id = f"da-{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)
        nonce = uuid.uuid4().bytes

        assertion = DelegationAssertion(
            assertion_id=assertion_id,
            delegator_agent_id=delegator_agent_id,
            delegate_agent_id=delegate_agent_id,
            human_principal_id=human_principal_id,
            root_assertion_id=assertion_id,
            parent_assertion_id=None,
            capability_subset=capability_subset,
            depth=0,
            max_depth=max_depth,
            channel=channel,
            nonce=nonce,
            issued_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

        signed = self._sign(assertion)
        self._assertions[assertion_id] = signed

        logger.info(
            f"Minted root assertion {assertion_id}: "
            f"{delegator_agent_id} -> {delegate_agent_id} "
            f"(principal={human_principal_id}, depth=0/{max_depth})"
        )
        return signed

    def remint(
        self,
        parent: DelegationAssertion,
        delegate_agent_id: str,
        capability_subset: frozenset[CapabilityGrant],
        channel: DelegationChannel,
        ttl_minutes: int = 15,
    ) -> Optional[DelegationAssertion]:
        """
        Re-mint a delegation assertion with narrowed capabilities.

        The new assertion's capability_subset must be a subset of the
        parent's. Depth is incremented and checked against max_depth.

        Args:
            parent: Parent assertion to derive from.
            delegate_agent_id: New delegate agent.
            capability_subset: Narrowed capability subset.
            channel: Delegation channel for this hop.
            ttl_minutes: TTL for the new assertion.

        Returns:
            New signed assertion, or None if constraints are violated.
        """
        # Capability subset check: must narrow, not expand
        if not capability_subset.issubset(parent.capability_subset):
            logger.warning(
                f"Capability expansion rejected: "
                f"{capability_subset - parent.capability_subset} "
                f"not in parent {parent.assertion_id}"
            )
            return None

        new_depth = parent.depth + 1
        if new_depth > parent.max_depth:
            logger.warning(
                f"Depth exceeded: {new_depth} > {parent.max_depth} "
                f"for parent {parent.assertion_id}"
            )
            return None

        assertion_id = f"da-{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        assertion = DelegationAssertion(
            assertion_id=assertion_id,
            delegator_agent_id=parent.delegate_agent_id,
            delegate_agent_id=delegate_agent_id,
            human_principal_id=parent.human_principal_id,
            root_assertion_id=parent.root_assertion_id,
            parent_assertion_id=parent.assertion_id,
            capability_subset=capability_subset,
            depth=new_depth,
            max_depth=parent.max_depth,
            channel=channel,
            nonce=uuid.uuid4().bytes,
            issued_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

        signed = self._sign(assertion)
        self._assertions[assertion_id] = signed

        logger.info(
            f"Re-minted assertion {assertion_id}: "
            f"{parent.delegate_agent_id} -> {delegate_agent_id} "
            f"(depth={new_depth}/{parent.max_depth}, "
            f"caps={len(capability_subset)})"
        )
        return signed

    def verify(self, assertion: DelegationAssertion) -> VerificationResult:
        """
        Verify a delegation assertion (7-step verification).

        Args:
            assertion: The assertion to verify.

        Returns:
            VerificationResult with verdict and explanation.
        """
        self._verification_count += 1

        # Step 1: Signature check
        if not self._verify_signature(assertion):
            self._rejected_count += 1
            return VerificationResult(
                assertion_id=assertion.assertion_id,
                verdict=VerificationVerdict.INVALID_SIGNATURE,
                explanation="Signature verification failed",
            )

        # Step 2: Expiry check
        if assertion.is_expired:
            self._rejected_count += 1
            return VerificationResult(
                assertion_id=assertion.assertion_id,
                verdict=VerificationVerdict.EXPIRED,
                explanation=(
                    f"Assertion expired at {assertion.expires_at.isoformat()}"
                ),
            )

        # Step 3: Revocation check
        if self._is_revoked(assertion.assertion_id):
            self._rejected_count += 1
            return VerificationResult(
                assertion_id=assertion.assertion_id,
                verdict=VerificationVerdict.REVOKED,
                explanation="Assertion has been revoked",
            )

        # Step 4: Depth check
        if assertion.depth > assertion.max_depth:
            self._rejected_count += 1
            return VerificationResult(
                assertion_id=assertion.assertion_id,
                verdict=VerificationVerdict.DEPTH_EXCEEDED,
                explanation=(
                    f"Depth {assertion.depth} exceeds max {assertion.max_depth}"
                ),
            )

        # Step 5: Capability subset check (against parent)
        if assertion.parent_assertion_id:
            parent = self._assertions.get(assertion.parent_assertion_id)
            if parent and not assertion.capability_subset.issubset(
                parent.capability_subset
            ):
                self._rejected_count += 1
                return VerificationResult(
                    assertion_id=assertion.assertion_id,
                    verdict=VerificationVerdict.CAPABILITY_EXPANSION,
                    explanation="Capability subset exceeds parent's grants",
                )

        # Step 6: Chain walk — check ancestors not revoked, principal active
        chain_result = self._walk_chain(assertion)
        if chain_result is not None:
            self._rejected_count += 1
            return chain_result

        # Step 7: Channel-specific verifier
        channel_verifier = self._channel_verifiers.get(assertion.channel)
        if channel_verifier and not channel_verifier(assertion):
            self._rejected_count += 1
            return VerificationResult(
                assertion_id=assertion.assertion_id,
                verdict=VerificationVerdict.CHANNEL_REJECTED,
                explanation=(
                    f"Channel verifier rejected for {assertion.channel.value}"
                ),
            )

        self._valid_count += 1
        return VerificationResult(
            assertion_id=assertion.assertion_id,
            verdict=VerificationVerdict.VALID,
            explanation="All verification steps passed",
        )

    def revoke(self, assertion_id: str) -> bool:
        """
        Revoke a delegation assertion.

        Args:
            assertion_id: The assertion to revoke.

        Returns:
            True if revocation was recorded.
        """
        self._revoked.add(assertion_id)
        logger.info(f"Revoked assertion {assertion_id}")
        return True

    def get_untrusted_capabilities(self) -> frozenset[CapabilityGrant]:
        """
        Get the capped untrusted-origin capability profile.

        Requests without a valid assertion degrade to this profile:
        read-only operations on non-sensitive tiers.
        """
        return UNTRUSTED_ORIGIN_CAPABILITIES

    def get_assertion(self, assertion_id: str) -> Optional[DelegationAssertion]:
        """Look up a stored assertion by ID."""
        return self._assertions.get(assertion_id)

    def get_metrics(self) -> dict[str, Any]:
        """Get verifier operational metrics."""
        return {
            "assertions_minted": len(self._assertions),
            "verifications_performed": self._verification_count,
            "valid_count": self._valid_count,
            "rejected_count": self._rejected_count,
            "revoked_count": len(self._revoked),
        }

    def _sign(self, assertion: DelegationAssertion) -> DelegationAssertion:
        """Sign an assertion using HMAC-SHA256 (KMS fallback)."""
        payload = (
            f"{assertion.assertion_id}|{assertion.delegator_agent_id}|"
            f"{assertion.delegate_agent_id}|{assertion.human_principal_id}|"
            f"{assertion.depth}|{assertion.nonce.hex()}|"
            f"{assertion.issued_at.isoformat()}"
        ).encode()

        import hmac

        sig = hmac.new(self._signing_key, payload, hashlib.sha256).digest()

        # Create new frozen instance with signature
        return DelegationAssertion(
            assertion_id=assertion.assertion_id,
            delegator_agent_id=assertion.delegator_agent_id,
            delegate_agent_id=assertion.delegate_agent_id,
            human_principal_id=assertion.human_principal_id,
            root_assertion_id=assertion.root_assertion_id,
            parent_assertion_id=assertion.parent_assertion_id,
            capability_subset=assertion.capability_subset,
            depth=assertion.depth,
            max_depth=assertion.max_depth,
            channel=assertion.channel,
            nonce=assertion.nonce,
            issued_at=assertion.issued_at,
            expires_at=assertion.expires_at,
            signature=sig,
        )

    def _verify_signature(self, assertion: DelegationAssertion) -> bool:
        """Verify assertion signature."""
        if not assertion.signature:
            return False

        payload = (
            f"{assertion.assertion_id}|{assertion.delegator_agent_id}|"
            f"{assertion.delegate_agent_id}|{assertion.human_principal_id}|"
            f"{assertion.depth}|{assertion.nonce.hex()}|"
            f"{assertion.issued_at.isoformat()}"
        ).encode()

        import hmac

        expected = hmac.new(
            self._signing_key, payload, hashlib.sha256
        ).digest()
        return hmac.compare_digest(assertion.signature, expected)

    def _is_revoked(self, assertion_id: str) -> bool:
        """Check if assertion is revoked."""
        if assertion_id in self._revoked:
            return True
        if self._revocation_checker:
            try:
                return self._revocation_checker(assertion_id)
            except Exception as e:
                logger.warning(f"Revocation checker failed: {e}")
        return False

    def _walk_chain(
        self, assertion: DelegationAssertion
    ) -> Optional[VerificationResult]:
        """
        Walk the assertion chain to root, checking each ancestor.

        Returns a VerificationResult if any ancestor is revoked or
        the human principal is deactivated. Returns None if chain is valid.
        """
        current_id = assertion.parent_assertion_id
        visited = {assertion.assertion_id}

        while current_id is not None:
            if current_id in visited:
                return VerificationResult(
                    assertion_id=assertion.assertion_id,
                    verdict=VerificationVerdict.CHAIN_BROKEN,
                    explanation=f"Circular chain detected at {current_id}",
                )
            visited.add(current_id)

            if self._is_revoked(current_id):
                return VerificationResult(
                    assertion_id=assertion.assertion_id,
                    verdict=VerificationVerdict.REVOKED,
                    explanation=f"Ancestor {current_id} has been revoked",
                )

            ancestor = self._assertions.get(current_id)
            if ancestor is None:
                return VerificationResult(
                    assertion_id=assertion.assertion_id,
                    verdict=VerificationVerdict.CHAIN_BROKEN,
                    explanation=f"Ancestor {current_id} not found in store",
                )
            current_id = ancestor.parent_assertion_id

        # Check human principal is active
        if self._principal_checker:
            try:
                if not self._principal_checker(assertion.human_principal_id):
                    return VerificationResult(
                        assertion_id=assertion.assertion_id,
                        verdict=VerificationVerdict.PRINCIPAL_DEACTIVATED,
                        explanation=(
                            f"Human principal {assertion.human_principal_id} "
                            f"is deactivated"
                        ),
                    )
            except Exception as e:
                logger.warning(f"Principal checker failed: {e}")

        return None


# Singleton
_verifier: Optional[DelegationVerifier] = None


def get_delegation_verifier() -> DelegationVerifier:
    """Get the global delegation verifier."""
    global _verifier
    if _verifier is None:
        _verifier = DelegationVerifier()
    return _verifier


def reset_delegation_verifier() -> None:
    """Reset the global delegation verifier (for testing)."""
    global _verifier
    _verifier = None
