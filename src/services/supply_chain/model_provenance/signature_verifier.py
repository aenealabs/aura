"""Cryptographic signature verification for model artifacts.

Verifies detached signatures over the model's ``weights_digest``
using provider-specific public keys. Soft-imports the ``cryptography``
package — if unavailable, every signed artifact returns
``VERIFICATION_ERROR`` (deterministic failure, never silent pass).

Supported algorithms:
    Ed25519 — preferred (Sigstore default, fast, no parameter choices).
    RSA-PSS / ECDSA — accepted via fall-through to ``cryptography``'s
        public-key dispatch when the PEM material identifies them.

The verifier never raises on input it can't parse — it returns the
appropriate :class:`SignatureStatus`. This is a deliberate choice:
the provenance pipeline must produce an outcome for every candidate
so the audit record is complete; raising on malformed input would
leave audits with missing evaluations.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from src.services.supply_chain.model_provenance.contracts import (
    ModelArtifact,
    ProviderSigningKey,
    SignatureStatus,
)

logger = logging.getLogger(__name__)


try:  # pragma: no cover — exercised via mock-mode tests
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import (
        ed25519,
        padding,
        rsa,
        ec,
    )
    from cryptography.exceptions import InvalidSignature

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:  # pragma: no cover
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    ed25519 = None  # type: ignore[assignment]
    padding = None  # type: ignore[assignment]
    rsa = None  # type: ignore[assignment]
    ec = None  # type: ignore[assignment]
    InvalidSignature = Exception  # type: ignore[misc,assignment]
    CRYPTOGRAPHY_AVAILABLE = False


@dataclass(frozen=True)
class VerificationOutcome:
    """Detail-rich outcome of one signature check."""

    status: SignatureStatus
    detail: str = ""

    @property
    def is_verified(self) -> bool:
        return self.status is SignatureStatus.VERIFIED


class SignatureVerifier:
    """Verifies model-artifact signatures against provider keys.

    The verifier is stateless — keys are passed in per-call so the
    allowlist module owns key lifecycle. This avoids a hidden
    coupling that would make key rotation harder.
    """

    def __init__(
        self,
        *,
        keys_by_id: Mapping[str, ProviderSigningKey] | None = None,
    ) -> None:
        self._keys = dict(keys_by_id or {})

    def register_key(self, key: ProviderSigningKey) -> None:
        self._keys[key.key_id] = key

    def verify(
        self,
        artifact: ModelArtifact,
        *,
        now: datetime | None = None,
    ) -> VerificationOutcome:
        """Run the full verification sequence on ``artifact``.

        Sequence (returns at first decisive outcome):
            1. No signature material on the artifact → UNSIGNED.
            2. cryptography library missing → VERIFICATION_ERROR.
            3. signing_key_id not registered → SIGNING_KEY_UNKNOWN.
            4. Key not active (revoked / not-yet-valid / expired) →
               SIGNING_KEY_EXPIRED.
            5. Signature parsing or algorithm dispatch fails →
               VERIFICATION_ERROR.
            6. Cryptographic check fails → SIGNATURE_INVALID.
            7. Otherwise → VERIFIED.
        """
        if artifact.signature_b64 is None or artifact.signing_key_id is None:
            return VerificationOutcome(SignatureStatus.UNSIGNED)

        if not CRYPTOGRAPHY_AVAILABLE:
            return VerificationOutcome(
                SignatureStatus.VERIFICATION_ERROR,
                detail="cryptography package not available",
            )

        key = self._keys.get(artifact.signing_key_id)
        if key is None:
            return VerificationOutcome(
                SignatureStatus.SIGNING_KEY_UNKNOWN,
                detail=f"unknown signing_key_id={artifact.signing_key_id!r}",
            )

        ts = now or datetime.now(timezone.utc)
        if not key.is_active_at(ts):
            return VerificationOutcome(
                SignatureStatus.SIGNING_KEY_EXPIRED,
                detail=(
                    f"key {key.key_id} not active at {ts.isoformat()}: "
                    f"valid={key.not_before.isoformat()}..{key.not_after.isoformat()}, "
                    f"revoked={key.revoked}"
                ),
            )

        try:
            signature_bytes = base64.b64decode(artifact.signature_b64)
            public_key = serialization.load_pem_public_key(
                key.public_key_pem.encode("utf-8")
            )
        except Exception as exc:
            return VerificationOutcome(
                SignatureStatus.VERIFICATION_ERROR,
                detail=f"failed to load key/signature: {exc}",
            )

        # The signed payload is the weights digest bytes (canonical UTF-8 hex).
        # Using the digest rather than the full weights blob lets the
        # verifier work even when the actual weights are too large to
        # download — Bedrock provides the digest in metadata.
        message = artifact.weights_digest.encode("utf-8")

        try:
            if isinstance(public_key, ed25519.Ed25519PublicKey):
                public_key.verify(signature_bytes, message)
            elif isinstance(public_key, rsa.RSAPublicKey):
                public_key.verify(
                    signature_bytes,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            elif isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(
                    signature_bytes,
                    message,
                    ec.ECDSA(hashes.SHA256()),
                )
            else:
                return VerificationOutcome(
                    SignatureStatus.VERIFICATION_ERROR,
                    detail=f"unsupported key type: {type(public_key).__name__}",
                )
        except Exception as exc:
            # Re-resolve InvalidSignature at runtime rather than relying
            # on the module-level import alias. Some test harnesses
            # re-import cryptography.exceptions between tests, which
            # invalidates the class identity captured at import time
            # and would otherwise misroute genuine signature failures
            # to VERIFICATION_ERROR.
            try:
                from cryptography.exceptions import InvalidSignature as _IS
            except ImportError:
                _IS = type(None)  # never matches
            if (
                isinstance(exc, InvalidSignature)
                or isinstance(exc, _IS)
                or type(exc).__name__ == "InvalidSignature"
            ):
                return VerificationOutcome(
                    SignatureStatus.SIGNATURE_INVALID,
                    detail="signature did not verify against weights_digest",
                )
            return VerificationOutcome(
                SignatureStatus.VERIFICATION_ERROR,
                detail=f"verification raised: {exc}",
            )

        return VerificationOutcome(SignatureStatus.VERIFIED)
