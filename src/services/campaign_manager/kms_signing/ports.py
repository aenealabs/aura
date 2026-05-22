"""Signer / verifier Port for campaign-manager state objects (issue #214)."""

from __future__ import annotations

from typing import Protocol


class SignatureVerificationError(Exception):
    """Raised when a signature does not verify against the payload.

    Distinct from ``TamperedStateError`` (which is raised by the
    checkpoint store on tamper). This exception is raised by the
    orchestrator's verification path, with a structured reason
    string that names the failing artifact (definition vs
    checkpoint) and the tenant + campaign for forensics.
    """


class CampaignSignerPort(Protocol):
    """Sign and verify canonical bytes for campaign-state artifacts.

    Implementations MUST be deterministic for a given (payload,
    key_id) pair so re-signing the same artifact yields the same
    signature. The deterministic property is required for the
    audit trail; production KMS-backed signers achieve it via
    asymmetric Sign (RSASSA_PSS_SHA_256 deterministic mode).

    ``key_id`` is the logical key identifier -- tenant-scoped in
    production (e.g. ``alias/aura/campaign-signing/<tenant>``). The
    Port is intentionally string-keyed so test implementations don't
    have to model the full KMS alias hierarchy.
    """

    def sign(self, *, payload: bytes, key_id: str) -> str:
        """Sign ``payload`` and return a base64-encoded signature string."""

    def verify(self, *, payload: bytes, signature: str, key_id: str) -> bool:
        """Verify ``signature`` against ``payload``. Returns True iff valid.

        Implementations MUST NOT raise on mismatch -- the caller
        decides how to escalate. Implementations MAY raise on
        unrecoverable errors (e.g. KMS key revoked or unreachable);
        the orchestrator translates those to
        ``SignatureVerificationError``.
        """
