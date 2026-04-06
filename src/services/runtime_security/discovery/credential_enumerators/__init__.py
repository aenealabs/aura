"""
Project Aura - Pluggable Credential Enumerator Registry

Provides the protocol for credential enumeration and a registry
for discovering all credentials held by an agent across integrations.

New integrations register enumerators at import time. A CI check
rejects new credential-issuing integrations without a matching
enumerator.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Compliance:
- NIST 800-53 AC-2: Account management
- NIST 800-53 IA-4: Identifier management
- NIST 800-53 PS-4: Personnel termination

Author: Project Aura Team
Created: 2026-04-06
"""

from .registry import (
    CredentialEnumerator,
    CredentialRecord,
    CredentialStatus,
    EnumerationResult,
    EnumeratorRegistry,
    get_enumerator_registry,
    reset_enumerator_registry,
)

__all__ = [
    "CredentialEnumerator",
    "CredentialRecord",
    "CredentialStatus",
    "EnumerationResult",
    "EnumeratorRegistry",
    "get_enumerator_registry",
    "reset_enumerator_registry",
]
