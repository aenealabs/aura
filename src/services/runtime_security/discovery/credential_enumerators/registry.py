"""
Project Aura - Credential Enumerator Protocol and Registry

Defines the pluggable protocol for credential enumeration and
the central registry that aggregates results across all
integration-specific enumerators.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class CredentialStatus(Enum):
    """Status of a discovered credential."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_REVOCATION = "pending_revocation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CredentialRecord:
    """Immutable record of a single credential found for an agent."""

    credential_class: str
    credential_id: str
    agent_id: str
    status: CredentialStatus
    description: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def is_active(self) -> bool:
        """Check if this credential is still active."""
        return self.status == CredentialStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "credential_class": self.credential_class,
            "credential_id": self.credential_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "metadata": dict(self.metadata),
        }


@dataclass
class EnumerationResult:
    """Result of enumerating credentials for an agent within one class."""

    credential_class: str
    agent_id: str
    credentials: list[CredentialRecord] = field(default_factory=list)
    zero_confirmed: bool = False
    error: Optional[str] = None
    enumerated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def active_count(self) -> int:
        """Count of active (non-revoked, non-expired) credentials."""
        return sum(1 for c in self.credentials if c.is_active)

    @property
    def needs_remediation(self) -> bool:
        """True if active credentials remain that must be revoked."""
        return not self.zero_confirmed and self.active_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "credential_class": self.credential_class,
            "agent_id": self.agent_id,
            "credential_count": len(self.credentials),
            "active_count": self.active_count,
            "zero_confirmed": self.zero_confirmed,
            "needs_remediation": self.needs_remediation,
            "error": self.error,
            "enumerated_at": self.enumerated_at.isoformat(),
        }


@runtime_checkable
class CredentialEnumerator(Protocol):
    """Protocol for credential enumeration plugins."""

    credential_class: str

    def enumerate(self, agent_id: str) -> EnumerationResult:
        """
        Enumerate all credentials of this class held by an agent.

        Args:
            agent_id: The agent to enumerate credentials for.

        Returns:
            EnumerationResult with discovered credentials and zero_confirmed flag.
        """
        ...


class EnumeratorRegistry:
    """
    Central registry of credential enumerators.

    New enumerators register at import time. The decommission verifier
    iterates all registered enumerators to confirm zero residual
    credentials before issuing attestation.
    """

    def __init__(self) -> None:
        self._enumerators: dict[str, CredentialEnumerator] = {}

    def register(self, enumerator: CredentialEnumerator) -> None:
        """
        Register a credential enumerator.

        Args:
            enumerator: Enumerator instance implementing the protocol.
        """
        self._enumerators[enumerator.credential_class] = enumerator
        logger.info(f"Registered credential enumerator: {enumerator.credential_class}")

    def unregister(self, credential_class: str) -> bool:
        """Remove an enumerator. Returns True if it existed."""
        if credential_class in self._enumerators:
            del self._enumerators[credential_class]
            return True
        return False

    def get(self, credential_class: str) -> Optional[CredentialEnumerator]:
        """Get enumerator by credential class."""
        return self._enumerators.get(credential_class)

    def list_classes(self) -> list[str]:
        """List all registered credential classes."""
        return list(self._enumerators.keys())

    def enumerate_all(self, agent_id: str) -> list[EnumerationResult]:
        """
        Run all registered enumerators for an agent.

        Args:
            agent_id: Agent to enumerate.

        Returns:
            List of EnumerationResult from each enumerator.
        """
        results: list[EnumerationResult] = []
        for credential_class, enumerator in self._enumerators.items():
            try:
                result = enumerator.enumerate(agent_id)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Enumerator {credential_class} failed for "
                    f"agent {agent_id}: {e}"
                )
                results.append(
                    EnumerationResult(
                        credential_class=credential_class,
                        agent_id=agent_id,
                        error=str(e),
                    )
                )
        return results

    def all_zero_confirmed(self, results: list[EnumerationResult]) -> bool:
        """
        Check if all enumeration results confirm zero active credentials.

        Args:
            results: List of enumeration results.

        Returns:
            True only if every result has zero_confirmed=True and no errors.
        """
        if not results:
            return False
        return all(r.zero_confirmed and r.error is None for r in results)

    @property
    def count(self) -> int:
        """Number of registered enumerators."""
        return len(self._enumerators)


# Global singleton
_enumerator_registry: Optional[EnumeratorRegistry] = None


def get_enumerator_registry() -> EnumeratorRegistry:
    """Get the global enumerator registry."""
    global _enumerator_registry
    if _enumerator_registry is None:
        _enumerator_registry = EnumeratorRegistry()
    return _enumerator_registry


def reset_enumerator_registry() -> None:
    """Reset the global enumerator registry (for testing)."""
    global _enumerator_registry
    _enumerator_registry = None
